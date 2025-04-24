from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.db.session import get_supabase
from app.api.routes.auth import check_admin_role

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/", dependencies=[Depends(check_admin_role)])
async def get_all_companies(supabase: Client = Depends(get_supabase)):
    try:
        response = supabase.table("company_client").select("*").execute()
        return {"companies": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}/list")
async def get_users_in_company(name: str, supabase: Client = Depends(get_supabase)):
    try:
        company_response = (
            supabase.table("company_client")
            .select("comany_id")
            .eq("name", name)
            .execute()
        )

        if not company_response.data:
            raise HTTPException(status_code=404, detail="Company not found")

        company_id = company_response.data[0]["id"]

        users_response = (
            supabase.table("users").select("*").eq("company_id", company_id).execute()
        )

        return {"participants": users_response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
