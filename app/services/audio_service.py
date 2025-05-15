from fastapi import UploadFile, HTTPException
from supabase import Client
import uuid
import librosa
import io
import os
from chainlit.data.storage_clients.azure_blob import AzureBlobStorageClient
from app.services.convert_audio_service import convert_audio
from app.core.config import settings


async def process_audio(file: UploadFile, supabase: Client, current_user):
    """Uploads an audio file to Azure Blob Storage and returns the file URL"""
    try:
        source = "local"
        audio_id = str(uuid.uuid4())
        user_id = current_user.id

        # Extract file extension and create path
        file_ext = file.filename.split(".")[-1] if "." in file.filename else ""

        allowed_extensions = ["mp3", "mp4", "wav"]
        if file_ext.lower() not in allowed_extensions:
            file = convert_audio(file)
            file_ext = file.filename.split(".")[-1] if "." in file.filename else ""
            if file_ext.lower() not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file format. Only {', '.join(allowed_extensions)} files are allowed.",
                )

        storage_path = f"{audio_id}.{file_ext}" if file_ext else audio_id

        # Get file content from UploadFile
        file_content = await file.read()

        # Upload to Azure Blob Storage

        container = settings.AZURE_STORAGE_CONTAINER_NAME
        azure_storage_account = settings.AZURE_STORAGE_ACCOUNT_NAME
        azure_storage_key = settings.AZURE_STORAGE_ACCOUNT_KEY
        try:
            # Create a blob service client using Chainlit
            blob_service_client = AzureBlobStorageClient(
                container_name=container,
                storage_account=azure_storage_account,
                storage_key=azure_storage_key,
            )

            # Upload the file using Chainlit's client
            blob_name = storage_path
            await blob_service_client.upload_file(
                object_key=blob_name,
                data=file_content,
                mime=file.content_type,
                overwrite=True,
            )

            # Get the blob URL
            file_url = f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{settings.AZURE_STORAGE_CONTAINER_NAME}/{storage_path}"

        except Exception as upload_error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file to Azure storage: {str(upload_error)}",
            )

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

        # Clean up temp file used in convert_audio() after the file was converted
        try:
            file.file.close()
            if hasattr(file.file, "name") and os.path.exists(file.file.name):
                os.remove(file.file.name)
        except Exception as cleanup_err:
            print(f"Failed to clean up temp file: {cleanup_err}")

        if not db_response.data:
            raise HTTPException(
                status_code=500, detail="Failed to insert record into database"
            )

        return file_url, audio_id, duration
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
