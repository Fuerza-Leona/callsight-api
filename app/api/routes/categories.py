from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.db.session import get_supabase

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("/")
async def get_categories(supabase: Client = Depends(get_supabase)):
    try:
        response = supabase.table("category").select("name").execute()
        names = [i["name"]for i in response.data]
        return {"categories": names}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
