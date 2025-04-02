from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from supabase import Client
import uuid
from typing import Optional

from app.db.session import get_supabase
from app.api.deps import get_current_user

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/problem/{conversation_id}")
async def get_problems(
    supabase: Client = Depends(get_supabase),
    conversation_id: str = "dd5b20c7-d36b-47fd-8dda-c3511235429b"
):
    """Get summary, problem, and solution for a given conversation"""
    try:
        response = supabase.table("summaries").select("summary, problem, solution").eq("conversation_id", conversation_id).execute()
        return {"data": response.data.pop()}
          
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

