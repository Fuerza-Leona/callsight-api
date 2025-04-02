from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from pydantic import BaseModel
from datetime import datetime
import uuid

from app.db.session import get_supabase
from app.api.deps import get_current_user
from app.api.routes.auth import check_admin_role

router = APIRouter(prefix="/conversations", tags=["conversations"])

class AddConversationRequest(BaseModel):
    audio_id: str
    start_time: datetime
    end_time: datetime
    sentiment_score: float
    confidence_score: float
    participants: list[(str, int)]

#TODO: agregar admin access despues de sprint 1
@router.get("/")
async def get_conversations(supabase: Client = Depends(get_supabase)):
    response = supabase.table("conversations").select("*").execute()
    return {"conversations": response.data}


@router.get("/mine")
async def get_mine(
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):

    user_id = current_user.id
    participant_response = supabase.table("participants").select("conversation_id").eq("user_id", user_id).execute()
    
    if not participant_response.data:
        return {"conversations": []}
    
    conversation_ids = [item["conversation_id"] for item in participant_response.data]
    
    conversations_response = supabase.table("conversations").select("*").in_("conversation_id", conversation_ids).execute()
    
    return {"conversations": conversations_response.data}
    
@router.get("/myClientEmotions")
async def get_emotions(
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    user_id = current_user.id
    participant_response = supabase.table("participants").select("conversation_id").eq("user_id", user_id).execute()
    
    if not participant_response.data:
        return {"conversations": []}
    
    conversation_ids = [item["conversation_id"] for item in participant_response.data]
    
    response = supabase.table("messages").select("positive, negative, neutral").in_("conversation_id", conversation_ids).execute()
    
    return {"emotions": response}

    
@router.get("/call/{call_id}")
async def get_call(
    call_id: str = "",
    supabase: Client = Depends(get_supabase)
):
    try:
        conversation_response = (
            supabase.table("conversations")
            .select("conversation_id, audio_id, start_time, end_time, sentiment_score, confidence_score")
            .eq("conversation_id", call_id)
            .execute()
        )

        return {"conversations": conversation_response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

     
@router.post("/add", dependencies=[Depends(check_admin_role)])
async def add_conversation(
    conversation_data: AddConversationRequest,
    supabase: Client = Depends(get_supabase)
):
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