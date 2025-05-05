from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.api.deps import get_current_user
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
async def get_employees(supabase: Client = Depends(get_supabase)):
    try:
        response = (
            supabase.table("users")
            .select("user_id, username")
            .neq("role", "client")
            .execute()
        )
        users = [i["username"] for i in response.data]
        return {"data": response.data, "users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
async def get_client(
    supabase: Client = Depends(get_supabase), current_user=Depends(get_current_user)
):
    id = current_user.id
    try:
        response = supabase.table("users").select("*").eq("user_id", id).execute()
        return {"user": response.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/client")
async def get_clients(supabase: Client = Depends(get_supabase)):
    try:
        response = (
            supabase.table("users")
            .select("user_id, username")
            .eq("role", "client")
            .execute()
        )
        return {"clients": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/employees/{company_id}")
async def get_companies(company_id: str, supabase: Client = Depends(get_supabase)):
    try:
        response = (
            supabase.table("users").select("*").eq("company_id", company_id).execute()
        )
        return {"companies": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
