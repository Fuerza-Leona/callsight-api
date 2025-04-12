from fastapi import APIRouter, Depends
from supabase import Client

from app.db.session import get_supabase
from app.api.deps import get_current_user

router = APIRouter(prefix="/chatbot", tags=["chatbot"])


@router.get("/")
async def get_companies(
    current_user=Depends(get_current_user), supabase: Client = Depends(get_supabase)
):
    try:
        return {"response": "Wasaaa el hector no me ha implementado"}
    except Exception:
        pass
