from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.db.session import get_supabase

router = APIRouter(prefix="/audio", tags=["audio"])


@router.get("/")
async def list_audio(
    skip: int = 0, limit: int = 100, supabase: Client = Depends(get_supabase)
):
    response = (
        supabase.table("audio_files")
        .select("*")
        .range(skip, skip + limit - 1)
        .execute()
    )
    return {"files": response.data}


@router.get("/{audio_id}")
async def get_audio(audio_id: str, supabase: Client = Depends(get_supabase)):
    response = (
        supabase.table("audio_files").select("*").eq("audio_id", audio_id).execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Audio file not found")
    return response.data[0]
