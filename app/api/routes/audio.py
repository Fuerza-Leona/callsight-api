from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(prefix="/audio", tags=["audio"])

@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Placeholder - save the file and create a db entry
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "status": "uploaded"
    }

@router.get("/")
async def list_audio(
    skip: int = 0, 
    limit: int = 100,
    db: Session = Depends(get_db)
):
    # Query the db
    return {"files": []}
