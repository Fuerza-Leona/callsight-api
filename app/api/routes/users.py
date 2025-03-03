from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])  # change for each file

@router.get("/")
async def get_all():
    return {"message": "This endpoint is not implemented yet"}
