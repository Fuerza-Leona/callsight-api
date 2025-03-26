from fastapi import APIRouter, Depends
from supabase import Client

from app.db.session import get_supabase

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/")
async def get_all(supabase: Client = Depends(get_supabase)):
    response = supabase.table("analysis").select("*").execute()
    return {"analysis": response.data}