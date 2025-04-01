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

@router.get("/", dependencies=[Depends(check_admin_role)])
async def get_all(supabase: Client = Depends(get_supabase)):
    try:
        response = supabase.table("conversations").select("*").execute()
        return {"conversations": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mine")
async def get_all(
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    try:
        user_id = current_user.id
        participant_response = supabase.table("participants").select("conversation_id").eq("user_id", user_id).execute();
        
        if not participant_response.data:
            return {"conversations": []}
        
        conversation_ids = [item["conversation_id"] for item in participant_response.data]
        
        conversations_response = supabase.table("conversations").select("*").in_("conversation_id", conversation_ids).execute()
        
        return {"conversations": conversations_response.data}
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