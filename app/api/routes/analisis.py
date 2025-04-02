from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from supabase import Client
import uuid
from typing import Optional

from app.db.session import get_supabase
from app.api.deps import get_current_user

router = APIRouter(prefix="/analisis", tags=["analisis"])

@router.get("/problem/{convo}")
async def get_problems(
    supabase: Client = Depends(get_supabase),
    convo: str = "dd5b20c7-d36b-47fd-8dda-c3511235429b"
):
    try:
        response = supabase.table("summaries").select("summary, problem, solution").eq("conversation_id", convo).execute()
        return {"data": response.data.pop()}
          
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

