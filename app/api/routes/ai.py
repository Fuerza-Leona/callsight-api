from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import Optional, List
from datetime import date, timedelta
from pydantic import BaseModel
import uuid
import io
import librosa

from supabase import Client
from app.db.session import get_supabase
import assemblyai as aai
from openai import OpenAI
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from app.core.config import settings
from app.services.call_analysis.main import run as analyze_call
from azure.ai.language.conversations import ConversationAnalysisClient
from app.api.deps import get_current_user

router = APIRouter(prefix="/ai", tags=["ai"])

class AudioAnalysisRequest(BaseModel):
    audio_url: str
    language: Optional[str] = "en"
    locale: Optional[str] = "en-US"
    use_stereo_audio: Optional[bool] = False
    output_file: Optional[bool] = False

async def upload_audio_file(file: UploadFile, supabase: Client, current_user):
    """Uploads an audio file to Supabase storage and returns the file URL"""
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
        
        # Upload to Supabase
        try:
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
        
        return file_url, audio_id, duration
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

def classify_speakers_with_gpt(utterances):
    # Get the first few utterances to analyze patterns
    sample_conversation = []
    for i, utterance in enumerate(utterances):
        sample_conversation.append(f"Speaker {utterance.speaker}: {utterance.text}")
    
    conversation_text = "\n".join(sample_conversation)
    
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert in analyzing call center conversations. Identify which speaker is the agent and which is the client."},
            {"role": "user", "content": f"Below is the beginning of a call center conversation in Spanish. Identify which speaker is the agent and which is the client. Return your answer as a simple JSON with speaker letters as keys and 'agent' or 'client' as values.\n\n{conversation_text}"}
        ],
        response_format={"type": "json_object"}
    )
    
    try:
        roles = eval(response.choices[0].message.content)
        return roles
    except:
        return {}

def analyze_sentiment_azure(text):
    # Get Azure credentials from environment variables
    azure_key = settings.AZURE_AI_KEY
    azure_endpoint = settings.AZURE_AI_LANGUAGE_ENDPOINT
    
    # Initialize the client
    credential = AzureKeyCredential(azure_key)
    text_analytics_client = TextAnalyticsClient(endpoint=azure_endpoint, credential=credential)
    
    # Analyze sentiment
    documents = [text]
    response = text_analytics_client.analyze_sentiment(documents, language="es")
    
    # Get the sentiment result
    result = response[0]
    if not result.is_error:
        return {
                "positive": result.confidence_scores.positive,
                "negative": result.confidence_scores.negative,
                "neutral": result.confidence_scores.neutral
            }
    return {"positive": 0, "negative": 0, "neutral": 1}

def getTranscription(file_url: str):
    # Replace with your API key
    aai.settings.api_key = settings.ASSEMBLYAI_API_KEY

    config = aai.TranscriptionConfig(
        speaker_labels=True,
        language_code="es",
    )

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(
        file_url,
        config=config
    )
    
    # Use LLM to classify speakers
    speaker_roles = classify_speakers_with_gpt(transcript.utterances)
    
    output = {
        "confidence": transcript.confidence,
        "phrases": []
    }

    for utterance in transcript.utterances:
        score = analyze_sentiment_azure(utterance.text)
        speaker_number = ord(utterance.speaker) - ord('A') + 1
        output["phrases"].append({
            "text": utterance.text,
            "speaker": speaker_number,
            "role": speaker_roles.get(f"Speaker {utterance.speaker}", None),
            "confidence": utterance.confidence,
            "offsetMilliseconds": utterance.start,
            "positive": score["positive"],
            "negative": score["negative"],
            "neutral": score["neutral"]
        })
    return output

def summarize_conversation(transcript):
    #Summarize the conversation using the previously generated transcript.
    azure_key = settings.AZURE_AI_KEY
    azure_endpoint = settings.AZURE_AI_LANGUAGE_ENDPOINT

    conversation_data = {
        "conversations": [
            {
                "conversationItems": [
                    {
                        "text": phrase["text"],
                        "modality": "text",
                        "id": str(i + 1),
                        "participantId": (
                            "Agent" if phrase.get("role", "").lower() == "agent"
                            else "Customer" if phrase.get("role", "").lower() in ["client", "customer"]
                            else f"Speaker {phrase['speaker']}"
                        )
                    }
                    for i, phrase in enumerate(transcript)
                ],
                "modality": "text",
                "id": "conversation1",
                "language": "es"
            }
        ]
    }

    credential = AzureKeyCredential(azure_key)
    client = ConversationAnalysisClient(endpoint=azure_endpoint, credential=credential)

    with client:
        poller = client.begin_conversation_analysis(
            task={
                "displayName": "Analyze conversations from transcript",
                "analysisInput": conversation_data,
                "tasks": [
                    {
                        "taskName": "Issue task",
                        "kind": "ConversationalSummarizationTask",
                        "parameters": {"summaryAspects": ["issue"]}
                    },
                    {
                        "taskName": "Resolution task",
                        "kind": "ConversationalSummarizationTask",
                        "parameters": {"summaryAspects": ["resolution"]}
                    }
                ]
            }
        )

        result = poller.result()
        task_results = result["tasks"]["items"]
        structured_summary = {}

        for task in task_results:
            task_name = task["taskName"]
            task_result = task["results"]

            if task_result["errors"]:
                structured_summary[task_name] = "Error occurred"
            else:
                conversation_result = task_result["conversations"][0]
                structured_summary[task_name] = {
                    summary["aspect"]: summary["text"] for summary in conversation_result["summaries"]
                }

        return structured_summary
    

@router.post("/alternative-analysis")
async def alternative_analysis(
    file: UploadFile = File(...),
    date: date = None,
    participants: List[str] = [],
    current_user = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    try:
        # Check if date is provided
        if date is None:
            raise ValueError("Date parameter is required")
            
        # File upload step
        try:
            file_url, audio_id, duration = await upload_audio_file(file, supabase, current_user)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")
        
        # Transcription step
        try:
            result = getTranscription(file_url)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
        
        # Summarization step
        try:
            summary = summarize_conversation(result["phrases"])
            result["summary"] = summary
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")

        problem = summary.get("Issue task", {}).get("issue", "")
        solution = summary.get("Resolution task", {}).get("resolution", "")

        start_time = date
        end_time = start_time + timedelta(seconds=duration)

        # Database operations step
        try:
            query = supabase.table("conversations").insert({
                "audio_id": audio_id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }).execute()

            if not query.data or len(query.data) == 0:
                raise ValueError("Failed to insert conversation record")
                
            conversation_id = query.data[0].get("conversation_id")
            if not conversation_id:
                raise ValueError("No conversation_id returned from database")
                
            result["conversation_id"] = conversation_id
            
            # Insert summary
            supabase.table("summaries").insert({
                "conversation_id": conversation_id,
                "problem": problem,
                "solution": solution
            }).execute()



            if participants:
                # Validate that participants are valid UUIDs
                valid_participants = []
                for participant in participants:
                    try:
                        # Attempt to validate UUID format
                        uuid_obj = uuid.UUID(participant)
                        valid_participants.append({"conversation_id": conversation_id, "user_id": str(uuid_obj)})
                    except ValueError:
                        print(f"Warning: Invalid UUID format for participant: {participant}")
                
                if valid_participants:
                    supabase.table("participants").insert(valid_participants).execute()

            # Insert transcripts
            for i, phrases in enumerate(result["phrases"]):
                try:
                    transcript_query = supabase.table("messages").insert({
                        "conversation_id": conversation_id,
                        "text": phrases["text"],
                        "speaker": phrases["speaker"],
                        "offsetmilliseconds": phrases["offsetMilliseconds"],
                        "role": phrases.get("role", None),
                        "confidence": phrases["confidence"],
                        "positive": phrases["positive"],
                        "negative": phrases["negative"],
                        "neutral": phrases["neutral"]
                    }).execute()
                    if not transcript_query.data:
                        print(f"Warning: Failed to insert transcript {i}")
                except Exception as e:
                    print(f"Error inserting transcript {i}: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database operation failed: {str(e)}")
        
        return result
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        import traceback
        error_detail = f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)  # This will show in your logs
        raise HTTPException(status_code=500, detail=error_detail)