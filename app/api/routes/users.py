from fastapi import APIRouter, Depends
from supabase import Client

from app.db.session import get_supabase

router = APIRouter(prefix="/users", tags=["users"]) 

@router.get("/")
async def get_all(supabase: Client = Depends(get_supabase)):
    response = supabase.table("users").select("*").execute()
    return response.data