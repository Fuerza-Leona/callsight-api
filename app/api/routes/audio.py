from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from supabase import Client
import uuid
import time
from typing import Optional

from app.db.session import get_supabase

router = APIRouter(prefix="/audio", tags=["audio"])

@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    user_id: Optional[str] = None,
    source: str = "local",
    supabase: Client = Depends(get_supabase)
):
    try:
        audio_id = str(uuid.uuid4())
        
        # Extract file extension and create path
        file_ext = file.filename.split(".")[-1] if "." in file.filename else ""
        storage_path = f"{audio_id}.{file_ext}" if file_ext else audio_id
        
        # Upload to Supabase storage
        file_content = await file.read()
        storage_response = supabase.storage.from_("audio_files").upload(
            storage_path, file_content
        )
        
        import io
        import librosa
        
        # Calculate duration
        duration = None
        try:
            # Reset the file pointer
            file_content_copy = io.BytesIO(file_content)
            # Load audio and get duration
            y, sr = librosa.load(file_content_copy, sr=None)
            duration = int(librosa.get_duration(y=y, sr=sr))
        except Exception as e:
            print(f"Could not calculate duration: {str(e)}")
        
        # Create a record in the database
        file_data = {
            "audio_id": audio_id,
            "file_name": file.filename,
            "file_path": storage_path,
            "duration_seconds": duration,
            "source": source,
            "status": "uploaded",
            "uploaded_at": None,  # Supabase will set this with default now()
            "uploaded_by": user_id,
            # Note: duration_seconds is not set initially,
            # it would be updated after processing
        }
        
        db_response = supabase.table("audio_files").insert(file_data).execute()
        
        return {
            "audio_id": audio_id,
            "file_name": file.filename,
            "status": "uploaded"
        }
        
    except Exception as e:
        # Update status and error message if there's an exception
        if 'audio_id' in locals():
            try:
                supabase.table("audio_files").update({
                    "status": "error",
                    "error_message": str(e)
                }).eq("audio_id", audio_id).execute()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")



@router.get("/")
async def list_audio(
    skip: int = 0, 
    limit: int = 100,
    supabase: Client = Depends(get_supabase)
):
    response = supabase.table("audio_files").select("*").range(skip, skip + limit - 1).execute()
    return {"files": response.data}


@router.get("/{audio_id}")
async def get_audio(
    audio_id: str,
    supabase: Client = Depends(get_supabase)
):
    response = supabase.table("audio_files").select("*").eq("audio_id", audio_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="Audio file not found")
    return response.data[0]
