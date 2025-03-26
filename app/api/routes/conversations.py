from fastapi import APIRouter, Depends
from supabase import Client

from app.db.session import get_supabase

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.get("/")
async def get_all(supabase: Client = Depends(get_supabase)):
    response = supabase.table("conversations").select("*").execute()
    return {"conversations": response.data}