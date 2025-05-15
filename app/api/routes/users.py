from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client

from app.api.deps import get_current_user
from app.db.session import get_supabase

router = APIRouter(prefix="/users", tags=["users"])


class User(BaseModel):
    username: str
    email: str
    password: str
    department: str
    role: str
    company: str


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


@router.post("/create")
async def create_company(user: User, supabase: Client = Depends(get_supabase)):
    try:
        responseCategory = (
            supabase.table("company_client")
            .select("company_id, name")
            .eq("name", user.company)
            .execute()
        )
        print(responseCategory.data[0])
        print(responseCategory.data[0]["company_id"])

        if len(responseCategory.data) == 0:
            raise HTTPException(status_code=404, detail="Category not found")

        response = supabase.auth.sign_up(
            {
                "email": user.email,
                "password": user.password,
            }
        )

        user_data = {
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "department": user.department,
            "company_id": responseCategory.data[0]["company_id"],
        }

        response = supabase.table("users").insert(user_data).execute()
        return {"message": "User created successfully", "user": response.data}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=str(e))
