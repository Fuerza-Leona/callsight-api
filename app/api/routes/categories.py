from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.db.session import get_supabase

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("/")
async def get_categories(supabase: Client = Depends(get_supabase)):
    try:
        response = supabase.table("category").select("category_id, name").execute()
        return {"categories": response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
