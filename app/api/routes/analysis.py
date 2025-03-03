from fastapi import APIRouter

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.get("/")
async def get_all():
    return {"message": "This endpoint is not implemented yet"}
