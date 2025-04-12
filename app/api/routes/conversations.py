from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from pydantic import BaseModel
from datetime import datetime
import uuid

from app.db.session import get_supabase
from app.api.deps import get_current_user
from app.api.routes.auth import check_admin_role

from datetime import datetime
from dateutil.relativedelta import relativedelta

from pydantic import BaseModel

from app.db.session import execute_query
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
    conversation_id: str = "",
    supabase: Client = Depends(get_supabase)
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
                    categories.append(participant["users"]["company_client"]["category"]["name"])

        return list(set(categories))
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))

#TODO: agregar admin access despues de sprint 1
@router.get("/")
async def get_conversations(supabase: Client = Depends(get_supabase)):
    """Get conversations for the currently authorized user"""
    response = supabase.table("conversations").select("*").execute()
    for i in response.data:
        i["categories"] = await get_categories(i["conversation_id"], supabase)
    return {"conversations": response.data}


@router.get("/mine")
async def get_mine(
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Get conversations for the currently authorized user"""
    user_id = current_user.id
    participant_response = supabase.table("participants").select("conversation_id").eq("user_id", user_id).execute()

    if not participant_response.data:
        return {"conversations": []}

    conversation_ids = [item["conversation_id"] for item in participant_response.data]

    conversations_response = supabase.table("conversations").select("*").in_("conversation_id", conversation_ids).execute()

    for i in conversations_response.data:
        i["categories"] = await get_categories(i["conversation_id"], supabase)

    return {"conversations": conversations_response.data}

@router.get("/myClientEmotions")
async def get_emotions(
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Return emotions across all messages in conversations for the currently authorized user"""
    user_id = current_user.id
    #TODO: enable after multiple calls: participant_response = supabase.table("participants").select("conversation_id").execute()
    participant_response = supabase.table("participants").select("conversation_id").eq("user_id", user_id).execute()

    print(participant_response)
    if not participant_response.data:
        return {"conversations": []}

    conversation_ids = [item["conversation_id"] for item in participant_response.data]
    response = supabase.table("messages").select("positive, negative, neutral").in_("conversation_id", conversation_ids).execute()

    positive_sum = round(sum(item["positive"] for item in response.data) / len(response.data) * 100) if response.data else 0
    negative_sum = round(sum(item["negative"] for item in response.data) / len(response.data) * 100) if response.data else 0
    neutral_sum = round(sum(item["neutral"] for item in response.data) / len(response.data) * 100) if response.data else 0

    return {"emotions": {"positive": positive_sum, "negative": negative_sum, "neutral": neutral_sum}}


@router.get("/{conversation_id}")
async def get_call(
    conversation_id: str,
    supabase: Client = Depends(get_supabase)
):
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
async def get_call(
    conversation_id: str,
    supabase: Client = Depends(get_supabase)
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

        conversation_ids = [item["conversation_id"] for item in conversation_response.data]

        messages_response = supabase.table("messages").select("*").in_("conversation_id", conversation_ids).execute()

        return {"messages": messages_response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/call/{call_id}/summary")
async def get_call(
    call_id: str = None,
    supabase: Client = Depends(get_supabase)
):
    """Get summary for a given conversation"""
    try:
        conversation = supabase.table("conversations").select("*").eq("conversation_id", call_id).execute()

        summary_response = supabase.table("summaries").select("*").eq("conversation_id", call_id).execute()

        messages = supabase.table("messages").select("*").eq("conversation_id", call_id).execute()
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
        summary_response.data[0]["duration"] = int((end_time - start_time).total_seconds() / 60)

        summary_response.data[0]["positive"] = positive / counter if messages.data else 0
        summary_response.data[0]["neutral"] = neutral / counter if messages.data else 0
        summary_response.data[0]["negative"] = negative  / counter if messages.data else 0

        return {"summary": summary_response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/call/{call_id}/participants")
async def get_call(
    call_id: str = None,
    supabase: Client = Depends(get_supabase)
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
    conversation_data: AddConversationRequest,
    supabase: Client = Depends(get_supabase)
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
            "confidence_score": conversation_data.confidence_score
        }

        conversation_response = supabase.table("conversations").insert(conversation).execute()

        participants = []
        for participant_id, speaker in conversation_data.participants:
            participants.append({
                "participant_id": str(uuid.uuid4()),
                "conversation_id": conversation_id,
                "user_id": participant_id,
                "speaker": speaker
            })

        if participants:
            participant_response = supabase.table("participants").insert(participants).execute()

        return {
            "conversation_id": conversation_id,
            "participants": participants
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/call/{call_id}")
async def get_info_pertaining_call(
    call_id: str,
    supabase: Client = Depends(get_supabase)
):
    try:
        conversation_response = supabase.table("conversations").select("*").eq("conversation_id", call_id).execute()
        summary_response = supabase.table("summaries").select("*").eq("conversation_id", call_id).execute()
        summary = summary_response.data[0] if summary_response.data else {}
        messages_response = supabase.table("messages").select("*").eq("conversation_id", call_id).execute()
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

        participants = participants_response.data or []

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        from dateutil import parser

        start_time = parser.parse(conversation[0]["start_time"])
        end_time = parser.parse(conversation[0]["end_time"])
        summary["duration"] = int((end_time - start_time).total_seconds() / 60)

        summary["positive"] = positive / counter if counter else 0
        summary["neutral"] = neutral / counter if counter else 0
        summary["negative"] = negative  / counter if counter else 0

        return {
            "conversation": conversation,
            "summary": summary,
            "messages": messages,
            "participants": participants
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
async def build_conversations_summary(start_date, end_date, role, user_id, clients, categories):
    base_query = """
        SELECT 
            ROUND(AVG(a.duration_seconds) / 60, 2) AS average_minutes,
            COUNT(DISTINCT c.conversation_id) AS conversation_count 
        FROM 
            conversations c
        INNER JOIN 
            audio_files a ON c.audio_id = a.audio_id"""
    
    conditions = ["c.start_time BETWEEN %s AND %s"]
    params = [start_date, end_date]


    if role == "agent":
        base_query += """
        INNER JOIN participants p_agent ON c.conversation_id = p_agent.conversation_id"""
        conditions.append("p_agent.user_id = %s")
        params.append(user_id)


    if clients:
        base_query += """
        INNER JOIN participants p_client ON c.conversation_id = p_client.conversation_id"""
        conditions.append("p_client.user_id = ANY(%s::uuid[])")
        params.append(clients)

        
    if categories:
        base_query += """
        INNER JOIN company_client cc ON c.company_id = cc.company_id"""        
        conditions.append("cc.category_id = ANY(%s::uuid[])")
        params.append(categories)

        
    if conditions:
        base_query += """
        WHERE """ + "\n        AND ".join(conditions)

    return base_query, params

class ConversationSummaryRequest(BaseModel):
    clients: List[str] = []
    categories: List[str] = []
    startDate: Optional[str] = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    endDate: Optional[str] = (datetime.now().replace(day=1) + relativedelta(months=1, days=-1)).strftime("%Y-%m-%d")

@router.post("/summary")
async def get_conversation_summary(
    request: ConversationSummaryRequest,
    current_user=Depends(get_current_user),
    supabase: Client=Depends(get_supabase)
):
    clients = request.clients
    categories = request.categories
    startDate = request.startDate
    endDate = request.endDate
    user_id = current_user.id

    try:
        start_date = datetime.strptime(startDate, "%Y-%m-%d").date()
        end_date = datetime.strptime(endDate, "%Y-%m-%d").date()
        if start_date > end_date:
            raise ValueError("Start date cannot be after end date")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
            
    user_id = current_user.id
    role = await check_user_role(current_user, supabase)
        
    if role not in ["admin", "agent"]:
        raise HTTPException(status_code=403, detail="Access denied")
        
    query, params = await build_conversations_summary(start_date, end_date, role, user_id, clients, categories) 
    try: 
        result = await execute_query(query, *params)
        return {"summary": result[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

