from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from openai import OpenAI
from app.services.analysis_service import (
    analyze_messages_sentiment_openai,
    extract_important_topics2,
    summarize_conversation,
)
from app.services.storage_service import process_topics
from app.services.teams_service import TeamsService
from app.core.config import settings
from app.api.deps import get_current_user
from app.db.session import get_supabase
import json
import httpx
import logging
from pydantic import BaseModel
from typing import Dict, Optional, Any, List

from app.services.transcription_service import (
    BATCH_SIZE,
    EMBEDDING_MODEL,
    classify_speakers_with_gpt_transcript_version,
    convert_messages_to_chunks,
)

router = APIRouter(prefix="/teams", tags=["teams"])
logger = logging.getLogger("uvicorn.app")


class TranscriptSummary(BaseModel):
    total_meetings: int
    total_transcripts: int
    successful_transcripts: int
    date_range: Dict[str, Optional[str]]


class TranscriptContent(BaseModel):
    id: str
    content: str
    content_type: Optional[str] = None


class AuthUrlResponse(BaseModel):
    auth_url: str


@router.get(
    "/connect",
    response_model=AuthUrlResponse,
    summary="Start Microsoft Teams OAuth flow",
    description="Initiates the OAuth flow for Microsoft Teams integration. Returns an authorization URL that users should visit to grant permissions.",
)
async def connect_teams(
    request: Request,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    """Start Microsoft Teams integration OAuth flow"""
    # Get user's company ID
    user_response = (
        supabase.table("users")
        .select("company_id")
        .eq("user_id", current_user.id)
        .execute()
    )
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")

    company_id = user_response.data[0]["company_id"]

    # Get company information to determine tenant ID
    company_response = (
        supabase.table("company_client")
        .select("*")
        .eq("company_id", company_id)
        .execute()
    )
    if not company_response.data:
        raise HTTPException(status_code=404, detail="Company not found")

    # Initialize Teams service
    teams_service = TeamsService()

    # Generate callback URL
    base_url = str(request.base_url)
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    callback_url = f"{base_url}{settings.API_V1_STR}/teams/callback"

    # Generate auth URL
    state = json.dumps({"company_id": company_id, "tenant_id": "common"})

    auth_url = teams_service.get_auth_url(callback_url, state=state)

    # Save company_id in session or cookie
    response = Response()
    response.set_cookie(key="connecting_company_id", value=company_id, httponly=True)
    logger.info("Set company id to: %s", company_id)

    return {"auth_url": auth_url}


@router.get(
    "/callback",
    summary="Handle Microsoft OAuth callback",
    description="Processes the OAuth callback from Microsoft, exchanges code for tokens, and stores them securely.",
    responses={
        302: {"description": "Redirect to profile page on success"},
        400: {"description": "Invalid authorization code or missing company context"},
        500: {"description": "Token exchange or storage failed"},
    },
)
async def teams_callback(
    request: Request,
    code: str,
    state: str = None,
    error: str = None,
    error_description: str = None,
    supabase=Depends(get_supabase),
    current_user=Depends(get_current_user),
):
    """Handle Microsoft OAuth callback"""
    logger.info(
        "Callback received! code: %s... error: %s state: %s", code[:10], error, state
    )

    try:
        state_data = json.loads(state) if state else {}
        company_id = state_data.get("company_id")
        tenant_id = state_data.get("tenant_id")

        if not company_id:
            raise HTTPException(
                status_code=400,
                detail="Missing company context. Restart authorization.",
            )

        teams_service = TeamsService(tenant_id=tenant_id, supabase=supabase)

        # Exchange code for tokens
        base_url = str(request.base_url)
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        callback_url = f"{base_url}{settings.API_V1_STR}/teams/callback"

        token_result = await teams_service.get_token_from_code(code, callback_url)

        if "error" in token_result:
            raise HTTPException(
                status_code=400,
                detail=f"Token error: {token_result.get('error_description')}",
            )

        # Store tokens in database
        await teams_service.store_tokens(company_id, token_result)

        supabase.table("users").update({"isConnected": True}).eq(
            "user_id", current_user.id
        ).execute()

        # Set up webhook for notifications
        if base_url.startswith("http://"):
            logger.info("Skipping webhook setup in non-secure environment...")
        else:
            notification_url = f"{base_url}{settings.API_V1_STR}/teams/notifications"
            try:
                await teams_service.setup_notification_subscription(
                    token_result["access_token"], notification_url
                )
            except Exception as e:
                logger.info(
                    "Warning: Failed to set up notification subscription: %s",
                    str(e),
                    exc_info=True,
                )

        # Success and redirect
        devenv = settings.NODE_ENV

        redirect_url = (
            f"{base_url}/calls/dashboard"
            if devenv != "development"
            else "http://localhost:3000/perfil"
        )
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Integration error: {str(e)}")


@router.post("/notifications")
async def handle_notifications(request: Request, supabase=Depends(get_supabase)):
    """Webhook endpoint to receive notifications about new recordings"""
    try:
        # Get the notification payload
        notification = await request.json()

        # Verify the notification
        validation_token = request.query_params.get("validationToken")
        if validation_token:
            # This is a subscription validation request
            return Response(content=validation_token, media_type="text/plain")

        # Check clientState for security
        client_state = notification.get("clientState")
        if client_state != "callsightSecretState":
            return Response(status_code=401)

        # Process the notification
        value = notification.get("value", [])
        for change_notification in value:
            # resource_data = change_notification.get("resourceData", {})

            # For demonstration purposes, just log it
            logger.info("Received notification: %s", json.dumps(change_notification))

        # Acknowledge receipt of the notification
        return Response(status_code=202)
    except Exception as e:
        print(f"Error processing notification: {str(e)}")
        return Response(status_code=500)


@router.get(
    "/transcripts",
    summary="Get user's Teams meeting transcripts",
    description="""
    Retrieves all transcripts from the authenticated user's Teams meetings.
    
    - Requires Microsoft Teams integration to be set up for the user's company
    - Fetches calendar events, extracts meeting URLs, and retrieves transcripts
    - Returns both successful and failed transcript attempts with summary statistics
    - Date range is optional; defaults to last 90 days if not specified
    """,
    responses={
        404: {"description": "User not found or Teams integration not set up"},
        500: {"description": "Failed to fetch calendar events or transcripts"},
    },
)
async def get_user_transcripts(
    start_date: str = None,
    end_date: str = None,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    """Get all transcripts for the authenticated user from their Teams meetings"""
    try:
        # Get user's company and tokens
        user_response = (
            supabase.table("users")
            .select("company_id")
            .eq("user_id", current_user.id)
            .execute()
        )
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")

        company_id = user_response.data[0]["company_id"]

        # Check if Teams integration is set up
        tokens_response = (
            supabase.table("microsoft_tokens")
            .select("*")
            .eq("company_id", company_id)
            .execute()
        )
        if not tokens_response.data:
            raise HTTPException(
                status_code=404,
                detail="Microsoft Teams integration not set up for your company",
            )

        # Initialize service and refresh token
        teams_service = TeamsService(supabase=supabase)
        access_token = await teams_service.refresh_token(company_id)

        # Get calendar events
        calendar_events = await teams_service.get_calendar_events(
            access_token, start_date, end_date
        )

        if isinstance(calendar_events, dict) and "error" in calendar_events:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch calendar events: {calendar_events['error']}",
            )

        # Extract join URLs from events
        join_urls = [
            identifier["value"]
            for event in calendar_events
            for identifier in event.get("meeting_identifiers", [])
            if identifier.get("type") == "joinUrl"
        ]

        if not join_urls:
            return {
                "transcripts": [],
                "summary": {"total_meetings": 0, "total_transcripts": 0},
            }

        # Get meetings from join URLs
        all_meetings = []
        for url in join_urls:
            try:
                meetings = await teams_service.get_online_meetings_from_events(
                    access_token, url
                )
                all_meetings.extend(meetings)
            except Exception as e:
                logger.info("Failed to get meetings for URL %s: %s", url, str(e))
                continue

        if not all_meetings:
            return {
                "transcripts": [],
                "summary": {"total_meetings": 0, "total_transcripts": 0},
            }

        # Get transcripts from meetings
        transcripts = await teams_service.get_transcripts_from_meetings(
            access_token, all_meetings
        )

        if isinstance(transcripts, dict) and "error" in transcripts:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch transcripts: {transcripts['error']}",
            )

        successful_transcripts = [
            t
            for t in transcripts
            if not t.get("content", "").startswith("Failed to fetch")
        ]

        return {
            "transcripts": successful_transcripts,
            "summary": {
                "total_meetings": len(all_meetings),
                "total_transcripts": len(transcripts),
                "successful_transcripts": len(successful_transcripts),
                "date_range": [start_date, end_date],
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.info("Error in get_user_transcripts: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get(
    "/meetings_transcripts",
    summary="Get user's Teams meeting transcripts",
    description="""
    Retrieves all transcripts from the authenticated user's Teams meetings.
    
    - Requires Microsoft Teams integration to be set up for the user's company
    - Fetches calendar events, extracts meeting URLs, and retrieves transcripts
    - Returns both successful and failed transcript attempts with summary statistics
    - Date range is optional; defaults to last 90 days if not specified
    """,
    responses={
        404: {"description": "User not found or Teams integration not set up"},
        500: {"description": "Failed to fetch calendar events or transcripts"},
    },
)
async def get_meetings_transcripts(
    start_date: str = None,
    end_date: str = None,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    """Get all transcripts for the authenticated user from their Teams meetings"""
    try:
        # Get user's company and tokens
        user_response = (
            supabase.table("users")
            .select("company_id")
            .eq("user_id", current_user.id)
            .execute()
        )
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")

        company_id = user_response.data[0]["company_id"]

        # Check if Teams integration is set up
        tokens_response = (
            supabase.table("microsoft_tokens")
            .select("*")
            .eq("company_id", company_id)
            .execute()
        )
        if not tokens_response.data:
            raise HTTPException(
                status_code=404,
                detail="Microsoft Teams integration not set up for your company",
            )

        # Initialize service and refresh token
        teams_service = TeamsService(supabase=supabase)
        access_token = await teams_service.refresh_token(company_id)

        # Get calendar events
        calendar_events = await teams_service.get_calendar_events(
            access_token, start_date, end_date
        )

        if isinstance(calendar_events, dict) and "error" in calendar_events:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch calendar events: {calendar_events['error']}",
            )

        # Extract join URLs from events
        join_urls = [
            identifier["value"]
            for event in calendar_events
            for identifier in event.get("meeting_identifiers", [])
            if identifier.get("type") == "joinUrl"
        ]

        if not join_urls:
            return {
                "transcripts": [],
                "summary": {"total_meetings": 0, "total_transcripts": 0},
            }

        # Get meetings from join URLs
        all_meetings = []
        for url in join_urls:
            try:
                meetings = await teams_service.get_online_meetings_from_events(
                    access_token, url
                )
                all_meetings.extend(meetings)
            except Exception as e:
                logger.info("Failed to get meetings for URL %s: %s", url, str(e))
                continue

        if not all_meetings:
            return {
                "transcripts": [],
                "summary": {"total_meetings": 0, "total_transcripts": 0},
            }

        all_meetings_ids = [meeting["id"] for meeting in all_meetings]
        print(f"All meetings IDs: {all_meetings_ids}")
        user_converations = (
            supabase.table("participants")
            .select("conversation_id")
            .eq("user_id", current_user.id)
            .execute()
        )

        saved_meetings = []
        for conversation in user_converations.data:
            conversation_id = conversation["conversation_id"]
            meeting = (
                supabase.table("conversations")
                .select("meeting_id")
                .eq("conversation_id", conversation_id)
                .execute()
            )
            if meeting.data:
                saved_meetings.append(meeting.data[0]["meeting_id"])

        missing_meetings = []
        for meeting_id in all_meetings_ids:
            if meeting_id not in saved_meetings:
                missing_meetings.append(meeting_id)

        # Get transcripts from meetings
        transcripts = await teams_service.get_transcripts_from_meetings(
            access_token, missing_meetings
        )

        successful_transcripts = [
            t
            for t in transcripts
            if len(t["content"]) > 0 and "Failed to fetch" not in t["content"][0]
        ]

        meetings = await teams_service.get_user_from_meetings(
            access_token, successful_transcripts
        )

        data = []

        for meeting in meetings:
            attendance_report = meeting["attendanceReports"][0]
            start = attendance_report[
                "meetingStartDateTime"
            ]  # 2025-06-03T16:00:07.962Z
            end = attendance_report["meetingEndDateTime"]  # 2025-06-03T16:08:29.254Z"

            start_time = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(end.replace("Z", "+00:00"))

            duration = int((end_time - start_time).total_seconds())

            audio = (
                supabase.table("audio_files")
                .insert(
                    {
                        "duration_seconds": duration,
                        "source": "onedrive",
                        "uploaded_by": current_user.id,
                    }
                )
                .execute()
            )

            audio_id = audio.data[0]["audio_id"]

            result = (
                supabase.table("conversations")
                .insert(
                    {
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "company_id": company_id,
                        "meeting_id": meeting["meetingId"],
                        "audio_id": audio_id,
                    }
                )
                .execute()
            )

            conversation_id = result.data[0]["conversation_id"]

            for participant in attendance_report["participants"]:
                email = participant["emailAddress"]
                user_response = (
                    supabase.table("users")
                    .select("user_id")
                    .eq("email", email)
                    .execute()
                )
                if user_response.data:
                    user_id = user_response.data[0]["user_id"]
                    supabase.table("participants").insert(
                        {"conversation_id": conversation_id, "user_id": user_id}
                    ).execute()
            messages = meeting["transcript"]["content"]
            roles = classify_speakers_with_gpt_transcript_version(messages)
            sentiment_analysis = await analyze_messages_sentiment_openai(messages)

            for i, message in enumerate(sentiment_analysis["messages"]):
                speaker = message["text"].split(":")[0].strip()
                if speaker in roles:
                    message["role"] = roles[speaker]
                else:
                    message["role"] = None

                message["offsetmilliseconds"] = i

                supabase.table("messages").insert(
                    {
                        "conversation_id": conversation_id,
                        "text": message["text"],
                        "role": message["role"],
                        "offsetmilliseconds": message["offsetmilliseconds"],
                        "positive": message["positive"],
                        "negative": message["negative"],
                        "neutral": message["neutral"],
                        "confidence": message["confidence"],
                    }
                ).execute()

            summary = summarize_conversation(sentiment_analysis["messages"])

            supabase.table("summaries").insert(
                {
                    "conversation_id": conversation_id,
                    "problem": summary["Issue task"]["issue"],
                    "solution": summary["Resolution task"]["resolution"],
                }
            ).execute()

            topics = extract_important_topics2(sentiment_analysis["messages"])
            await process_topics(supabase, topics, conversation_id)

            chunks = convert_messages_to_chunks(meeting["transcript"]["content"])

            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            embeddings = []
            for batch_start in range(0, len(chunks), BATCH_SIZE):
                batch_end = batch_start + BATCH_SIZE
                batch = chunks[batch_start:batch_end]
                response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
                for i, e in enumerate(response.data):
                    assert i == e.index
                    global_index = batch_start + i
                    embeddings.append(
                        {
                            "chunk_index": global_index,
                            "content": batch[i],
                            "vector": e.embedding,
                        }
                    )

            for embedding in embeddings:
                embedding["conversation_id"] = conversation_id

            supabase.table("conversation_chunks").insert(embeddings).execute()

            data.append(
                {
                    "meeting": meeting,
                    "roles": roles,
                    "sentiment_analysis": sentiment_analysis,
                    "summary": summary,
                    "topics": topics,
                }
            )
        return {"meetings": len(meetings), "data": data}

    except HTTPException:
        raise
    except Exception as e:
        logger.info("Error in get_user_transcripts: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/test-calendar")
async def test_calendar(
    start_date: str = None,  # Format: YYYY-MM-DDTHH:MM:SSZ
    end_date: str = None,  # Format: YYYY-MM-DDTHH:MM:SSZ
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    """Test the enhanced calendar events method"""
    # Get tokens (same as other endpoints)
    user_response = (
        supabase.table("users")
        .select("company_id")
        .eq("user_id", current_user.id)
        .execute()
    )
    company_id = user_response.data[0]["company_id"]
    tokens_response = (
        supabase.table("microsoft_tokens")
        .select("*")
        .eq("company_id", company_id)
        .execute()
    )
    if not tokens_response.data:
        raise HTTPException(
            status_code=404, detail="Microsoft Teams integration not set up"
        )

    teams_service = TeamsService(supabase=supabase)
    access_token = await teams_service.refresh_token(company_id)

    # Test the enhanced calendar method
    events = await teams_service.get_calendar_events(access_token, start_date, end_date)

    return {
        "events": events,
        "summary": {
            "total_events": len(events) if isinstance(events, list) else 0,
            "events_with_identifiers": len(
                [
                    e
                    for e in events
                    if isinstance(events, list) and e.get("meeting_identifiers")
                ]
            )
            if isinstance(events, list)
            else 0,
        },
    }


@router.get("/test-meetings")
async def test_meetings(
    start_date: str = None,  # Format: YYYY-MM-DDTHH:MM:SSZ
    end_date: str = None,  # Format: YYYY-MM-DDTHH:MM:SSZ
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    # Get tokens
    user_response = (
        supabase.table("users")
        .select("company_id")
        .eq("user_id", current_user.id)
        .execute()
    )
    company_id = user_response.data[0]["company_id"]
    teams_service = TeamsService(supabase=supabase)
    access_token = await teams_service.refresh_token(company_id)

    # Call the service method directly
    calendar_events = await teams_service.get_calendar_events(
        access_token, start_date, end_date
    )

    join_urls = [
        identifier["value"]
        for event in calendar_events
        for identifier in event.get("meeting_identifiers", [])
        if identifier.get("type") == "joinUrl"
    ]

    meetings = []
    for url in join_urls:
        meeting = await teams_service.get_online_meetings_from_events(access_token, url)
        meetings.extend(meeting)
        pass

    return {"meetings": meetings}


@router.get("/test-transcripts")
async def test_transcripts(
    start_date: str = None,
    end_date: str = None,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    # Get tokens
    user_response = (
        supabase.table("users")
        .select("company_id")
        .eq("user_id", current_user.id)
        .execute()
    )
    company_id = user_response.data[0]["company_id"]
    teams_service = TeamsService(supabase=supabase)
    access_token = await teams_service.refresh_token(company_id)

    # Call the service method directly
    calendar_events = await teams_service.get_calendar_events(
        access_token, start_date, end_date
    )

    join_urls = [
        identifier["value"]
        for event in calendar_events
        for identifier in event.get("meeting_identifiers", [])
        if identifier.get("type") == "joinUrl"
    ]

    meetings = []
    for url in join_urls:
        meeting = await teams_service.get_online_meetings_from_events(access_token, url)
        meetings.extend(meeting)
        pass

    transcripts = await teams_service.get_transcripts_from_meetings(
        access_token, meetings
    )

    return {"transcripts": transcripts}


class ParticipantRecord(BaseModel):
    identity: Dict[str, Any]
    totalAttendanceInSeconds: int
    role: Optional[str] = None
    attendanceIntervals: List[Dict[str, Any]]


class AttendanceReport(BaseModel):
    id: str
    totalParticipantCount: int
    meetingStartDateTime: str
    meetingEndDateTime: str
    participants: List[ParticipantRecord]


@router.get(
    "/participants",
    summary="Get meeting participants and attendance",
    description="""
    Retrieves attendance reports and participant information from Teams meetings.
    
    - Requires Microsoft Teams integration to be set up for the user's company
    - Fetches calendar events, extracts meeting URLs, and retrieves attendance reports
    - Returns participant details including attendance duration and intervals
    - Date range is optional; defaults to last 90 days if not specified
    """,
    responses={
        404: {"description": "User not found or Teams integration not set up"},
        500: {"description": "Failed to fetch calendar events or attendance reports"},
    },
)
async def get_meeting_participants(
    start_date: str = None,
    end_date: str = None,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    """Get meeting participants and attendance reports for the authenticated user"""
    try:
        # Get user's company and tokens (same pattern as transcripts endpoint)
        user_response = (
            supabase.table("users")
            .select("company_id")
            .eq("user_id", current_user.id)
            .execute()
        )
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")

        company_id = user_response.data[0]["company_id"]

        # Check if Teams integration is set up
        tokens_response = (
            supabase.table("microsoft_tokens")
            .select("*")
            .eq("company_id", company_id)
            .execute()
        )
        if not tokens_response.data:
            raise HTTPException(
                status_code=404,
                detail="Microsoft Teams integration not set up for your company",
            )

        # Initialize service and refresh token
        teams_service = TeamsService(supabase=supabase)
        access_token = await teams_service.refresh_token(company_id)

        # Get calendar events
        calendar_events = await teams_service.get_calendar_events(
            access_token, start_date, end_date
        )

        if isinstance(calendar_events, dict) and "error" in calendar_events:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch calendar events: {calendar_events['error']}",
            )

        join_urls = [
            identifier["value"]
            for event in calendar_events
            for identifier in event.get("meeting_identifiers", [])
            if identifier.get("type") == "joinUrl"
        ]

        if not join_urls:
            return {
                "attendance_reports": [],
                "summary": {"total_meetings": 0, "total_reports": 0},
            }

        all_meetings = []
        for url in join_urls:
            try:
                meetings = await teams_service.get_online_meetings_from_events(
                    access_token, url
                )
                all_meetings.extend(meetings)
            except Exception as e:
                logger.info("Failed to get meetings for URL %s: %s", url, str(e))
                continue

        if not all_meetings:
            return {
                "attendance_reports": [],
                "summary": {"total_meetings": 0, "total_reports": 0},
            }

        # Get attendance reports from meetings
        attendance_reports = await teams_service.get_attendance_reports_from_meetings(
            access_token, all_meetings
        )

        if isinstance(attendance_reports, dict) and "error" in attendance_reports:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch attendance reports: {attendance_reports['error']}",
            )

        return {
            "attendance_reports": attendance_reports,
            "summary": {
                "total_meetings": len(all_meetings),
                "total_reports": len(attendance_reports),
                "date_range": {"start": start_date, "end": end_date},
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.info("Error in get_meeting_participants: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get(
    "/users",
    summary="Get meeting participants and attendance",
    description="""
    Retrieves attendance reports and participant information from Teams meetings.
    
    - Requires Microsoft Teams integration to be set up for the user's company
    - Fetches calendar events, extracts meeting URLs, and retrieves attendance reports
    - Returns participant details including attendance duration and intervals
    - Date range is optional; defaults to last 90 days if not specified
    """,
    responses={
        404: {"description": "User not found or Teams integration not set up"},
        500: {"description": "Failed to fetch calendar events or attendance reports"},
    },
)
async def get_participants(
    start_date: str = None,
    end_date: str = None,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase),
):
    """Get meeting participants and attendance reports for the authenticated user"""
    try:
        # Get user's company and tokens (same pattern as transcripts endpoint)
        user_response = (
            supabase.table("users")
            .select("company_id")
            .eq("user_id", current_user.id)
            .execute()
        )
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")

        company_id = user_response.data[0]["company_id"]

        # Check if Teams integration is set up
        tokens_response = (
            supabase.table("microsoft_tokens")
            .select("*")
            .eq("company_id", company_id)
            .execute()
        )
        if not tokens_response.data:
            raise HTTPException(
                status_code=404,
                detail="Microsoft Teams integration not set up for your company",
            )

        # Initialize service and refresh token
        teams_service = TeamsService(supabase=supabase)
        access_token = await teams_service.refresh_token(company_id)

        # Get calendar events
        calendar_events = await teams_service.get_calendar_events(
            access_token, start_date, end_date
        )

        if isinstance(calendar_events, dict) and "error" in calendar_events:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch calendar events: {calendar_events['error']}",
            )

        join_urls = [
            identifier["value"]
            for event in calendar_events
            for identifier in event.get("meeting_identifiers", [])
            if identifier.get("type") == "joinUrl"
        ]

        if not join_urls:
            return {
                "attendance_reports": [],
                "summary": {"total_meetings": 0, "total_reports": 0},
            }

        all_meetings = []
        for url in join_urls:
            try:
                meetings = await teams_service.get_online_meetings_from_events(
                    access_token, url
                )
                all_meetings.extend(meetings)
            except Exception as e:
                logger.info("Failed to get meetings for URL %s: %s", url, str(e))
                continue

        if not all_meetings:
            return {
                "attendance_reports": [],
                "summary": {"total_meetings": 0, "total_reports": 0},
            }

        participants = await teams_service.get_participants_from_meetings(
            access_token, all_meetings
        )

        return {"participants": participants}

    except HTTPException:
        raise
    except Exception as e:
        logger.info("Error in get_meeting_participants: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@router.get("/test-config")
async def test_config():
    teams_service = TeamsService()
    test_url = teams_service.get_auth_url("https://example.com/callback")
    parsed_url = httpx.URL(test_url)
    query_params = dict(parsed_url.params)

    safe_params = {
        k: (v[:10] + "..." if k == "client_id" else v) for k, v in query_params.items()
    }

    return {
        "auth_url_generated": True,
        "url_params": safe_params,
        "microsoft_config_valid": bool(
            settings.MICROSOFT_CLIENT_ID and settings.MICROSOFT_CLIENT_SECRET
        ),
    }
