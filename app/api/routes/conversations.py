from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from dateutil import parser

from app.db.session import get_supabase
from app.api.deps import get_current_user
from app.api.routes.auth import check_admin_role


from app.api.routes.auth import check_user_role

router = APIRouter(prefix="/conversations", tags=["conversations"])


class AddConversationRequest(BaseModel):
    audio_id: str
    start_time: datetime
    end_time: datetime
    sentiment_score: float
    confidence_score: float
    participants: list[(str, int)]


async def get_categories(
    conversation_id: str = "", supabase: Client = Depends(get_supabase)
):
    """Get categories for a given conversation"""
    try:
        conversation_response = (
            supabase.table("conversations")
            .select("participants(users(company_client(category(name))))")
            .eq("conversation_id", conversation_id)
            .execute()
        )

        categories = []

        for item in conversation_response.data:
            for participant in item["participants"]:
                if participant["users"]["company_client"]["category"]:
                    categories.append(
                        participant["users"]["company_client"]["category"]["name"]
                    )

        return list(set(categories))
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))


# TODO: agregar admin access despues de sprint 1
@router.get("/")
async def get_conversations(supabase: Client = Depends(get_supabase)):
    """Get conversations for the currently authorized user"""
    response = supabase.table("conversations").select("*").execute()
    for i in response.data:
        i["categories"] = await get_categories(i["conversation_id"], supabase)
    return {"conversations": response.data}


class ConversationsFilteringParameters(BaseModel):
    clients: Optional[List[str]] = None
    agents: Optional[List[str]] = None
    companies: Optional[List[str]] = None
    startDate: Optional[str] = (
        datetime.now()
        .replace(day=1, hour=0, minute=0, second=0)
        .strftime("%Y-%m-%d::%H:%M:%S")
    )
    endDate: Optional[str] = (
        datetime.now()
        .replace(hour=23, minute=59, second=59)
        .strftime("%Y-%m-%d::%H:%M:%S")
    )


class MyConversationsFilteringParameters(ConversationsFilteringParameters):
    conversation_id: Optional[str] = None


@router.post("/mine")
async def get_mine(
    request: MyConversationsFilteringParameters,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    clients = request.clients
    agents = request.agents
    companies = request.companies
    startDate = request.startDate
    endDate = request.endDate
    conversation_id = request.conversation_id
    user_id = current_user.id

    role = await check_user_role(current_user, supabase)

    if role == "client" and (agents or companies or clients):
        raise HTTPException(
            status_code=400,
            detail="Clients cannot filter by agents, companies or clients",
        )

    if role == "agent" and agents:
        raise HTTPException(status_code=400, detail="Agents cannot filter other agents")

    if conversation_id:
        clients = None
        agents = None
        companies = None
        startDate = None
        endDate = None
        try:
            UUID(conversation_id)
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid conversation_id format"
            )
    else:
        try:
            start_date = datetime.strptime(startDate, "%Y-%m-%d::%H:%M:%S").date()
            end_date = datetime.strptime(endDate, "%Y-%m-%d::%H:%M:%S").date()
            if start_date > end_date:
                raise ValueError("Start date cannot be after end date")

            def validate_uuids(items, name):
                if items:
                    for item in items:
                        try:
                            UUID(item)
                        except ValueError:
                            raise ValueError(f"Invalid UUID in {name}: {item}")

            validate_uuids(clients, "clients")
            validate_uuids(agents, "agents")
            validate_uuids(companies, "companies")

        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid filter: {str(e)}")

    try:
        params = {
            "start_date": startDate,
            "end_date": endDate,
            "user_role": role,
            "id": user_id,
            "conv_id": conversation_id,
            "clients": clients,
            "agents": agents,
            "companies": companies,
        }
        response = supabase.rpc(
            "new_build_get_my_conversations_query", params
        ).execute()
        return {"conversations": response.data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")


@router.get("/minenumber")
async def get_mine_number(
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        response = (
            supabase.table("participants")
            .select("*")
            .eq("user_id", current_user.id)
            .execute()
        )
        return {"number": len(response.data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")


@router.get("/mineratings")
async def get_mine_ratings(
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        response = (
            supabase.table("participants")
            .select("conversations(ratings(rating))")
            .eq("user_id", current_user.id)
            .execute()
        )
        ratings = []
        for participant in response.data:
            conversations = participant.get("conversations", [])
            if not isinstance(conversations, list):
                conversations = [conversations]
            for conv in conversations:
                conv_ratings = conv.get("ratings", [])
                if not isinstance(conv_ratings, list):
                    conv_ratings = [conv_ratings]
                for rating in conv_ratings:
                    if rating and "rating" in rating:
                        ratings.append(rating["rating"])
        return {"rating": round(sum(ratings) / len(ratings), 2) if ratings else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")


@router.get("/myDuration")
async def get_mine_duration(
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        response = (
            supabase.table("participants")
            .select("conversations(start_time, end_time)")
            .eq("user_id", current_user.id)
            .execute()
        )
        durations = []
        for i in response.data:
            start_time = parser.parse(i["conversations"]["start_time"])
            end_time = parser.parse(i["conversations"]["end_time"])
            duration = (end_time - start_time).total_seconds() / 60
            durations.append(duration)
        return {"duration": round(sum(durations) / len(durations)) if durations else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")


@router.post("/myClientEmotions")
async def get_emotions(
    request: ConversationsFilteringParameters,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    clients = request.clients
    agents = request.agents
    companies = request.companies
    startDate = request.startDate
    endDate = request.endDate
    user_id = current_user.id

    try:
        start_date = datetime.strptime(startDate, "%Y-%m-%d::%H:%M:%S").date()
        end_date = datetime.strptime(endDate, "%Y-%m-%d::%H:%M:%S").date()
        if start_date > end_date:
            raise ValueError("Start date cannot be after end date")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

    role = await check_user_role(current_user, supabase)

    try:
        response = supabase.rpc(
            "new_build_client_emotions_query",
            {
                "start_date": startDate,
                "end_date": endDate,
                "user_role": role,
                "id": user_id,
                "clients": clients if clients else None,
                "agents": agents if agents else None,
                "companies": companies if companies else None,
            },
        ).execute()

        if response.data:
            row = response.data[0]
            return {
                "emotions": {
                    "positive": row["positive"],
                    "negative": row["negative"],
                    "neutral": row["neutral"],
                }
            }
        return {"emotions": {"positive": 0, "negative": 0, "neutral": 0}}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")


@router.get("/{conversation_id}")
async def get_call(conversation_id: str, supabase: Client = Depends(get_supabase)):
    """Get a given conversation by id"""
    try:
        conversation_response = (
            supabase.table("conversations")
            .select("conversation_id, audio_id, start_time, end_time")
            .eq("conversation_id", conversation_id)
            .execute()
        )

        return conversation_response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/messages")
async def get_call_messages(
    conversation_id: str, supabase: Client = Depends(get_supabase)
):
    """Get messages for a given conversation"""
    try:
        conversation_response = (
            supabase.table("conversations")
            .select("conversation_id")
            .eq("conversation_id", conversation_id)
            .execute()
        )

        if not conversation_response:
            return {"messages": []}

        conversation_ids = [
            item["conversation_id"] for item in conversation_response.data
        ]

        messages_response = (
            supabase.table("messages")
            .select("*")
            .in_("conversation_id", conversation_ids)
            .execute()
        )

        return {"messages": messages_response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/call/{call_id}/summary")
async def get_call_summary(
    call_id: str = None, supabase: Client = Depends(get_supabase)
):
    """Get summary for a given conversation"""
    try:
        conversation = (
            supabase.table("conversations")
            .select("*")
            .eq("conversation_id", call_id)
            .execute()
        )

        summary_response = (
            supabase.table("summaries")
            .select("*")
            .eq("conversation_id", call_id)
            .execute()
        )

        messages = (
            supabase.table("messages")
            .select("*")
            .eq("conversation_id", call_id)
            .execute()
        )
        positive = neutral = negative = 0
        counter = 0
        for message in messages.data:
            if message["role"] == "agent":
                counter += 1
                positive += message["positive"]
                neutral += message["neutral"]
                negative += message["negative"]

        from dateutil import parser

        # ...existing code...

        # Replace the datetime parsing lines with this:
        start_time = parser.parse(conversation.data[0]["start_time"])
        end_time = parser.parse(conversation.data[0]["end_time"])
        summary_response.data[0]["duration"] = int(
            (end_time - start_time).total_seconds() / 60
        )

        summary_response.data[0]["positive"] = (
            positive / counter if messages.data else 0
        )
        summary_response.data[0]["neutral"] = neutral / counter if messages.data else 0
        summary_response.data[0]["negative"] = (
            negative / counter if messages.data else 0
        )

        return {"summary": summary_response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/call/{call_id}/participants")
async def get_call_participants(
    call_id: str = None, supabase: Client = Depends(get_supabase)
):
    """Get participants a given conversation"""
    try:
        participants = (
            supabase.table("participants")
            .select("users(username, role)")
            .eq("conversation_id", call_id)
            .execute()
        )
        return {"participants": participants.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add", dependencies=[Depends(check_admin_role)])
async def add_conversation(
    conversation_data: AddConversationRequest, supabase: Client = Depends(get_supabase)
):
    """Add a conversation (call) - Admin only endpoint"""
    try:
        # Generate a UUID for the new conversation
        conversation_id = str(uuid.uuid4())

        # Create conversation record
        conversation = {
            "conversation_id": conversation_id,
            "audio_id": conversation_data.audio_id,
            "start_time": conversation_data.start_time.isoformat(),
            "end_time": conversation_data.end_time.isoformat(),
            "sentiment_score": conversation_data.sentiment_score,
            "confidence_score": conversation_data.confidence_score,
        }

        supabase.table("conversations").insert(conversation).execute()

        participants = []
        for participant_id, speaker in conversation_data.participants:
            participants.append(
                {
                    "participant_id": str(uuid.uuid4()),
                    "conversation_id": conversation_id,
                    "user_id": participant_id,
                    "speaker": speaker,
                }
            )

        if participants:
            supabase.table("participants").insert(participants).execute()

        return {"conversation_id": conversation_id, "participants": participants}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/call/{call_id}")
async def get_info_pertaining_call(
    call_id: str, supabase: Client = Depends(get_supabase)
):
    try:
        conversation_response = (
            supabase.table("conversations")
            .select("*")
            .eq("conversation_id", call_id)
            .execute()
        )
        summary_response = (
            supabase.table("summaries")
            .select("*")
            .eq("conversation_id", call_id)
            .execute()
        )
        summary = summary_response.data[0] if summary_response.data else {}
        messages_response = (
            supabase.table("messages")
            .select("*")
            .eq("conversation_id", call_id)
            .execute()
        )
        positive = neutral = negative = 0
        counter = 0
        messages = messages_response.data or []
        conversation = conversation_response.data or []
        for message in messages:
            counter += 1
            positive += message["positive"]
            neutral += message["neutral"]
            negative += message["negative"]

        participants_response = (
            supabase.table("participants")
            .select("users(username, role)")
            .eq("conversation_id", call_id)
            .execute()
        )

        company_response = (
            supabase.table("company_client")
            .select("name, logo")
            .eq("company_id", conversation[0]["company_id"])
            .execute()
        )

        company = company_response.data[0] if company_response.data else {}

        participants = participants_response.data or []

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        from dateutil import parser

        start_time = parser.parse(conversation[0]["start_time"])
        end_time = parser.parse(conversation[0]["end_time"])
        summary["duration"] = int((end_time - start_time).total_seconds() / 60)

        summary["positive"] = positive / counter if counter else 0
        summary["neutral"] = neutral / counter if counter else 0
        summary["negative"] = negative / counter if counter else 0

        ratings = (
            supabase.table("ratings")
            .select("rating")
            .eq("conversation_id", call_id)
            .execute()
        )
        average = 0.0
        length = len(ratings.data)
        if ratings.data:
            average = float(sum([i["rating"] for i in ratings.data]) / length)
        rating = {
            "average": average,
            "count": length,
        }

        return {
            "conversation": conversation,
            "summary": summary,
            "messages": messages,
            "participants": participants,
            "company": company,
            "rating": rating,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summary")
async def get_conversation_summary(
    request: ConversationsFilteringParameters,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    clients = request.clients
    companies = request.companies
    agents = request.agents
    startDate = request.startDate
    endDate = request.endDate
    user_id = current_user.id

    try:
        start_date = datetime.strptime(startDate, "%Y-%m-%d::%H:%M:%S").date()
        end_date = datetime.strptime(endDate, "%Y-%m-%d::%H:%M:%S").date()
        if start_date > end_date:
            raise ValueError("Start date cannot be after end date")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

    user_id = current_user.id
    role = await check_user_role(current_user, supabase)

    if role not in ["admin", "agent"]:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        result = supabase.rpc(
            "new_build_conversations_summary",
            {
                "start_date": startDate,
                "end_date": endDate,
                "user_role": role,
                "id": user_id,
                "clients": clients if clients else None,
                "agents": agents if agents else None,
                "companies": companies if companies else None,
            },
        ).execute()
        return {"summary": result.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")


@router.post("/categories")
async def get_conversations_categories(
    request: ConversationsFilteringParameters,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    clients = request.clients
    categories = request.categories
    startDate = request.startDate
    endDate = request.endDate
    user_id = current_user.id

    try:
        start_date = datetime.strptime(startDate, "%Y-%m-%d::%H:%M:%S").date()
        end_date = datetime.strptime(endDate, "%Y-%m-%d::%H:%M:%S").date()
        if start_date > end_date:
            raise ValueError("Start date cannot be after end date")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

    user_id = current_user.id
    role = await check_user_role(current_user, supabase)

    if role not in ["admin", "agent"]:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        result = supabase.rpc(
            "build_conversations_categories_query",
            {
                "start_date": startDate,
                "end_date": endDate,
                "user_role": role,
                "id": user_id,
                "clients": clients if clients else None,
                "categories": categories if categories else None,
            },
        ).execute()
        return {"categories": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")


@router.post("/ratings")
async def get_conversations_ratings(
    request: ConversationsFilteringParameters,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    clients = request.clients
    agents = request.agents
    companies = request.companies
    startDate = request.startDate
    endDate = request.endDate
    user_id = current_user.id

    try:
        start_date = datetime.strptime(startDate, "%Y-%m-%d::%H:%M:%S").date()
        end_date = datetime.strptime(endDate, "%Y-%m-%d::%H:%M:%S").date()
        if start_date > end_date:
            raise ValueError("Start date cannot be after end date")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

    user_id = current_user.id
    role = await check_user_role(current_user, supabase)

    if role not in ["admin", "agent"]:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        result = supabase.rpc(
            "new_build_conversations_ratings_query",
            {
                "start_date": startDate,
                "end_date": endDate,
                "user_role": role,
                "id": user_id,
                "clients": clients if clients else None,
                "agents": agents if agents else None,
                "companies": companies if companies else None,
            },
        ).execute()
        return {"ratings": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")


@router.get("/call/{call_id}/rating")
async def get_call_rating(
    call_id: str = None,
    supabase: Client = Depends(get_supabase),
    current_user=Depends(get_current_user),
):
    try:
        id = current_user.id

        participant_response = (
            supabase.table("participants")
            .select("*")
            .eq("conversation_id", call_id)
            .eq("user_id", id)
            .execute()
        )

        if not participant_response.data:
            raise HTTPException(status_code=401, detail="User is not a participant")

        role = await check_user_role(current_user, supabase)

        if role != "client":
            raise HTTPException(
                status_code=400, detail="Only clients can give a review"
            )

        rating = (
            supabase.table("ratings")
            .select("*")
            .eq("conversation_id", call_id)
            .eq("user_id", id)
            .execute()
        )

        rating = rating.data[0].get("rating", 0) if rating.data else 0

        return {"rating": rating}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RatingRequest(BaseModel):
    rating: int
    conversation_id: str


@router.post("/call/rating")
async def post_call_rating(
    request: RatingRequest,
    supabase: Client = Depends(get_supabase),
    current_user=Depends(get_current_user),
):
    try:
        id = current_user.id
        call_id = request.conversation_id
        user_rating = request.rating

        if user_rating < 1 or user_rating > 5:
            raise HTTPException(
                status_code=400, detail="Rating must be between 1 and 5"
            )

        participant_response = (
            supabase.table("participants")
            .select("*")
            .eq("conversation_id", call_id)
            .eq("user_id", id)
            .execute()
        )

        if not participant_response.data:
            raise HTTPException(status_code=401, detail="User is not a participant")

        role = await check_user_role(current_user, supabase)

        if role != "client":
            raise HTTPException(
                status_code=400, detail="Only clients can give a review"
            )

        existing_rating = (
            supabase.table("ratings")
            .select("*")
            .eq("conversation_id", call_id)
            .eq("user_id", id)
            .execute()
        )

        if existing_rating.data:
            raise HTTPException(status_code=400, detail="Cannot give a review twice")

        supabase.table("ratings").insert(
            {"rating": user_rating, "conversation_id": call_id, "user_id": id}
        ).execute()

        return {"message": "Rating added successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
