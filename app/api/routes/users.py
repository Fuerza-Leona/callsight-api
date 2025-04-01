from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.db.session import get_supabase

router = APIRouter(prefix="/users", tags=["users"]) 

@router.get("/")
async def get_all(supabase: Client = Depends(get_supabase)):
    try:
        response = supabase.table("users").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/employees")
async def get_all(supabase: Client = Depends(get_supabase)):
    try:
        response = supabase.table("users").select("user_id, username").neq("role", "client").execute()
        users = [i["username"] for i in response.data]
        return {"data": response.data, "users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/client")
async def get_all(supabase: Client = Depends(get_supabase)):
    try:
        response = supabase.table("users").select("user_id, username").eq("role", "client").execute()
        users = [i["username"] for i in response.data]
        return {"data": response.data, "users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
@router.get("/employees/{company_id}")
async def get_companies(
    company_id: str,
    supabase: Client = Depends(get_supabase)
):
    try:
        response = supabase.table("users").select("*").eq("company_id", company_id).execute()
        return {"companies": response.data}
    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))