from fastapi import UploadFile, HTTPException
from supabase import Client
import uuid
import librosa
import io
import os
import boto3
from botocore.exceptions import ClientError
from app.services.convert_audio_service import convert_audio
from app.core.config import settings


async def process_audio(file: UploadFile, supabase: Client, current_user):
    """Uploads an audio file to AWS S3 and returns the file URL"""
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

        # Upload to AWS S3
        bucket_name = settings.AWS_S3_BUCKET_NAME
        aws_access_key = settings.AWS_ACCESS_KEY_ID
        aws_secret_key = settings.AWS_SECRET_ACCESS_KEY
        aws_region = settings.AWS_REGION

        try:
            # Create an S3 client
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region,
            )

            # Upload the file to S3
            s3_client.put_object(
                Bucket=bucket_name,
                Key=storage_path,
                Body=file_content,
                ContentType=file.content_type,
            )

            # Get the S3 file URL
            file_url = (
                f"https://{bucket_name}.s3.{aws_region}.amazonaws.com/{storage_path}"
            )

        except ClientError as upload_error:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file to AWS S3: {str(upload_error)}",
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
