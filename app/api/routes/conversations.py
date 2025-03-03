from fastapi import APIRouter

router = APIRouter(prefix="/conversations", tags=["conversations"]) 

@router.get("/")
async def get_all():
    return {"message": "This endpoint is not implemented yet"}
