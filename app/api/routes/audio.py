from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from supabase import Client
import uuid
from typing import Optional

from app.db.session import get_supabase
from app.api.deps import get_current_user

router = APIRouter(prefix="/audio", tags=["audio"])

@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    supabase: Client = Depends(get_supabase),
    current_user = Depends(get_current_user),
):
    try:
        source = "local"
        audio_id = str(uuid.uuid4())
        user_id = current_user.id
        
        # Extract file extension and create path
        file_ext = file.filename.split(".")[-1] if "." in file.filename else ""

        allowed_extensions = ["mp3", "mp4", "wav"]
        if file_ext.lower() not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file format. Only {', '.join(allowed_extensions)} files are allowed."
            )

        storage_path = f"{audio_id}.{file_ext}" if file_ext else audio_id
        
        # Get file content from UploadFile
        file_content = await file.read()
        
        # Upload to Supabase - don't check for .data attribute
        try:
            # Just try to upload without checking response.data
            supabase.storage.from_("audios").upload(
                storage_path,
                file_content,
                file_options={"content_type": file.content_type}
            )
        except Exception as upload_error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file to storage: {str(upload_error)}"
            )
        
        # Get the public URL of the uploaded file
        file_url = supabase.storage.from_("audios").get_public_url(storage_path)
        print(f"File URL: {file_url}")

        # For duration calculation, we need to use the original file
        import io
        import librosa
        
        # Calculate duration
        duration = None
        try:
            # We need to seek back to start since we've already read the file
            await file.seek(0)
            audio_content = await file.read()
            audio_bytes = io.BytesIO(audio_content)
            y, sr = librosa.load(audio_bytes, sr=None)
            duration = int(librosa.get_duration(y=y, sr=sr))
        except Exception as e:
            print(f"Could not calculate duration: {str(e)}")
        
        # Create a record in the database
        file_data = {
            "audio_id": audio_id,
            "file_name": file.filename,
            "file_path": file_url,
            "source": source,
            "duration_seconds": duration,
            "uploaded_at": None,  # Supabase will set this with default now()
            "uploaded_by": user_id,
        }
        
        db_response = supabase.table("audio_files").insert(file_data).execute()

        if not db_response.data:
            raise HTTPException(status_code=500, detail="Failed to insert record into database")
        

        return {
            "audio_id": audio_id,
            "file_name": file.filename,
            "file_url": file_url,  # Add URL to response
            "status": "uploaded"
        }
          
    except Exception as e:
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
