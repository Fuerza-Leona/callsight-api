from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from app.services.teams_service import TeamsService
from app.core.config import settings
from app.api.deps import get_current_user
from app.db.session import get_supabase
import json
import logging
import httpx
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

logger = logging.getLogger("uvicorn.app")

router = APIRouter(prefix="/teams", tags=["teams"])

class TranscriptSummary(BaseModel):
    total_meetings: int
    total_transcripts: int
    successful_transcripts: int
    date_range: Dict[str, Optional[str]]

class TranscriptContent(BaseModel):
    id: str
    content: str
    content_type: Optional[str] = None

class TranscriptsResponse(BaseModel):
    transcripts: List[Dict[str, Any]]
    summary: TranscriptSummary

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
    supabase=Depends(get_supabase)
):
    """Start Microsoft Teams integration OAuth flow"""
    # Get user's company ID
    user_response = supabase.table("users").select("company_id").eq("user_id", current_user.id).execute()
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    company_id = user_response.data[0]["company_id"]
    
    # Get company information to determine tenant ID
    company_response = supabase.table("company_client").select("*").eq("company_id", company_id).execute()
    if not company_response.data:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Initialize Teams service
    teams_service = TeamsService()
    
    # Generate callback URL
    base_url = str(request.base_url)
    if base_url.endswith('/'):
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
        500: {"description": "Token exchange or storage failed"}
    }
)
async def teams_callback(
    request: Request,
    code: str,
    state: str = None,
    error: str = None,
    error_description: str = None,
    supabase = Depends(get_supabase)
):
    """Handle Microsoft OAuth callback"""
    logger.info("Callback received! code: %s... error: %s state: %s", code[:10], error, state)
    
    try:
        state_data = json.loads(state) if state else {}
        company_id = state_data.get("company_id")
        tenant_id = state_data.get("tenant_id")
        
        if not company_id:
            raise HTTPException(
                status_code=400, 
                detail="Missing company context. Restart authorization."
            )
        
        teams_service = TeamsService(tenant_id=tenant_id, supabase=supabase)
        
            # Exchange code for tokens
        base_url = str(request.base_url)
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        callback_url = f"{base_url}{settings.API_V1_STR}/teams/callback"
        
        token_result = await teams_service.get_token_from_code(code, callback_url)
        
        if "error" in token_result:
            raise HTTPException(
                status_code=400, 
                detail=f"Token error: {token_result.get('error_description')}"
            )
            
        # Store tokens in database
        await teams_service.store_tokens(company_id, token_result)
        
        # Set up webhook for notifications
        if base_url.startswith("http://"):
            logger.info("Skipping webhook setup in non-secure environment...")
        else:
            notification_url = f"{base_url}{settings.API_V1_STR}/teams/notifications"
            try:
                await teams_service.setup_notification_subscription(
                    token_result["access_token"],
                    notification_url
                )
            except Exception as e:
                logger.info("Warning: Failed to set up notification subscription: %s", str(e), exc_info=True)
        
        # Success and redirect
        devenv = settings.NODE_ENV
        
        redirect_url = f"{base_url}/perfil" if devenv != "development" else "http://localhost:3000/perfil"
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Integration error: {str(e)}")

@router.post("/notifications")
async def handle_notifications(
    request: Request,
    supabase=Depends(get_supabase)
):
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
            resource_data = change_notification.get("resourceData", {})
            
            # For demonstration purposes, just log it
            logger.info("Received notification: %s", json.dumps(change_notification))
        
        # Acknowledge receipt of the notification
        return Response(status_code=202)
    except Exception as e:
        logger.info("Error processing notification: ", str(e), exc_info=True)
        return Response(status_code=500)
    
@router.get(
    "/transcripts",
    response_model=TranscriptsResponse,
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
        500: {"description": "Failed to fetch calendar events or transcripts"}
    }
)
async def get_user_transcripts(
    start_date: str = None,
    end_date: str = None,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """Get all transcripts for the authenticated user from their Teams meetings"""
    try:
        # Get user's company and tokens
        user_response = supabase.table("users").select("company_id").eq("user_id", current_user.id).execute()
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        company_id = user_response.data[0]["company_id"]
        
        # Check if Teams integration is set up
        tokens_response = supabase.table("microsoft_tokens").select("*").eq("company_id", company_id).execute()
        if not tokens_response.data:
            raise HTTPException(status_code=404, detail="Microsoft Teams integration not set up for your company")
        
        # Initialize service and refresh token
        teams_service = TeamsService(supabase=supabase)
        access_token = await teams_service.refresh_token(company_id)
        
        # Get calendar events
        calendar_events = await teams_service.get_calendar_events(access_token, start_date, end_date)
        
        if isinstance(calendar_events, dict) and "error" in calendar_events:
            raise HTTPException(status_code=500, detail=f"Failed to fetch calendar events: {calendar_events['error']}")
        
        # Extract join URLs from events
        join_urls = [
            identifier["value"]
            for event in calendar_events 
            for identifier in event.get("meeting_identifiers", []) 
            if identifier.get("type") == "joinUrl"
        ]
        
        if not join_urls:
            return {"transcripts": [], "summary": {"total_meetings": 0, "total_transcripts": 0}}
        
        # Get meetings from join URLs
        all_meetings = []
        for url in join_urls:
            try:
                meetings = await teams_service.get_online_meetings_from_events(access_token, url)
                all_meetings.extend(meetings)
            except Exception as e:
                logger.info("Failed to get meetings for URL %s: %s", url, str(e))
                continue
        
        if not all_meetings:
            return {"transcripts": [], "summary": {"total_meetings": 0, "total_transcripts": 0}}
        
        # Get transcripts from meetings
        transcripts = await teams_service.get_transcripts_from_meetings(access_token, all_meetings)
        
        if isinstance(transcripts, dict) and "error" in transcripts:
            raise HTTPException(status_code=500, detail=f"Failed to fetch transcripts: {transcripts['error']}")
        
        # Filter out failed transcripts for summary
        successful_transcripts = [t for t in transcripts if not t.get("content", "").startswith("Failed to fetch")]
        
        return {
            "transcripts": transcripts,
            "summary": {
                "total_meetings": len(all_meetings),
                "total_transcripts": len(transcripts),
                "successful_transcripts": len(successful_transcripts),
                "date_range": {"start": start_date, "end": end_date}
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.info("Error in get_user_transcripts: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")
    
@router.get("/test-calendar")
async def test_calendar(
    start_date: str = None,  # Format: YYYY-MM-DDTHH:MM:SSZ
    end_date: str = None,    # Format: YYYY-MM-DDTHH:MM:SSZ
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """Test the enhanced calendar events method"""
    # Get tokens (same as other endpoints)
    user_response = supabase.table("users").select("company_id").eq("user_id", current_user.id).execute()
    company_id = user_response.data[0]["company_id"]
    tokens_response = supabase.table("microsoft_tokens").select("*").eq("company_id", company_id).execute()
    if not tokens_response.data:
        raise HTTPException(status_code=404, detail="Microsoft Teams integration not set up")
    
    teams_service = TeamsService(supabase=supabase)
    access_token = await teams_service.refresh_token(company_id)
    
    # Test the enhanced calendar method
    events = await teams_service.get_calendar_events(access_token, start_date, end_date)
    
    return {
        "events": events,
        "summary": {
            "total_events": len(events) if isinstance(events, list) else 0,
            "events_with_identifiers": len([e for e in events if isinstance(events, list) and e.get("meeting_identifiers")]) if isinstance(events, list) else 0
        }
    }
    
@router.get("/test-meetings")
async def test_meetings(
    start_date: str = None,  # Format: YYYY-MM-DDTHH:MM:SSZ
    end_date: str = None,    # Format: YYYY-MM-DDTHH:MM:SSZ
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase)
):
   # Get tokens
    user_response = supabase.table("users").select("company_id").eq("user_id", current_user.id).execute()
    company_id = user_response.data[0]["company_id"]
    teams_service = TeamsService(supabase=supabase)
    access_token = await teams_service.refresh_token( company_id)
    
    # Call the service method directly
    calendar_events = await teams_service.get_calendar_events(access_token, start_date, end_date)
    
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
    
    return {
        "meetings": meetings
    }
    
@router.get("/test-transcripts")
async def test_transcripts(
    start_date: str = None,
    end_date: str = None,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase)
):
   # Get tokens
    user_response = supabase.table("users").select("company_id").eq("user_id", current_user.id).execute()
    company_id = user_response.data[0]["company_id"]
    teams_service = TeamsService(supabase=supabase)
    access_token = await teams_service.refresh_token(company_id)
    
    # Call the service method directly
    calendar_events = await teams_service.get_calendar_events(access_token, start_date, end_date)
    
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
    
    transcripts = await teams_service.get_transcripts_from_meetings(access_token, meetings)
    
    return {
        "transcripts": transcripts
    }
    
@router.get("/test-config")
async def test_config():
    teams_service = TeamsService()
    test_url = teams_service.get_auth_url("https://example.com/callback")
    parsed_url = httpx.URL(test_url)
    query_params = dict(parsed_url.params)
    
    safe_params = {k: (v[:10] + "..." if k == "client_id" else v) for k, v in query_params.items()}
    
    return {
        "auth_url_generated": True,
        "url_params": safe_params,
        "microsoft_config_valid": bool(settings.MICROSOFT_CLIENT_ID and settings.MICROSOFT_CLIENT_SECRET)
    }