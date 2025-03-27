from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.db.session import get_supabase

router = APIRouter(prefix="/users", tags=["users"]) 

@router.get("/")
async def get_all(supabase: Client = Depends(get_supabase)):
    try:
        response = supabase.table("users").select("*").execute()
        return response.data
    except:
        print("Error getting client")

