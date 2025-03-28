from fastapi import APIRouter, Depends
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

@router.get("/employees")
async def get_all(supabase: Client = Depends(get_supabase)):
    try:
        response = supabase.table("users").select("user_id, username").neq("role", "client").execute()
        users = [i["username"] for i in response.data]
        return {"data": response.data, "users": users}
    except:
        print("Error getting client")

@router.get("/client")
async def get_all(supabase: Client = Depends(get_supabase)):
    try:
        response = supabase.table("users").select("user_id, username").eq("role", "client").execute()
        users = [i["username"] for i in response.data]
        return {"data": response.data, "users": users}
    except:
        print("Error getting client")