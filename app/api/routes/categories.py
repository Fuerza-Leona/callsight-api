from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.db.session import get_supabase
from app.api.routes.auth import check_admin_role

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("/")
async def get_categories(supabase: Client = Depends(get_supabase)):
    try:
        response = supabase.table("category").select("*").execute()
        return {"categories": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))