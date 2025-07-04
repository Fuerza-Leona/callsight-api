from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from supabase import Client
from app.db.session import get_supabase
from app.api.deps import get_current_user

from app.services.input_service import parse_inputs
from app.services.audio_service import process_audio
from app.services.transcription_service import get_transcription
from app.services.analysis_service import analyze_conversation
from app.services.storage_service import store_conversation_data
from app.services.company_service import get_company_id

router = APIRouter(prefix="/ai", tags=["ai"])


class AnalysisResponse(BaseModel):
    success: bool
    conversation_id: str


@router.post(
    "/alternative-analysis",
    response_model=AnalysisResponse,
    status_code=201,
    responses={
        201: {
            "description": "Successfully analyzed audio and created conversation",
            "model": AnalysisResponse,
        },
        400: {
            "description": "Bad request - invalid inputs",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid date format. Expected YYYY-MM-DD HH:MM"
                    }
                }
            },
        },
        401: {
            "description": "Unauthorized - authentication required",
            "content": {
                "application/json": {"example": {"detail": "Not authenticated"}}
            },
        },
        500: {
            "description": "Internal server error during processing",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "File upload failed: Could not connect to storage"
                    }
                }
            },
        },
    },
    summary="Analyze an audio call recording",
    description="""
    Process an audio recording of a call center conversation.

    This endpoint performs several operations:
    1. Uploads and processes the audio file
    2. Transcribes the conversation using speaker recognition
    3. Analyzes the content (sentiment, topic extraction, summarization)
    4. Stores the results in the database

    The audio file should be in MP3, MP4, or WAV format.
    """,
)
async def alternative_analysis(
    file: UploadFile = File(
        ..., description="Audio file of the call recording (MP3, MP4, or WAV format)"
    ),
    date_string: str = Form(
        ..., description="Date and time of the call in format 'YYYY-MM-DD HH:MM:SS'"
    ),
    participants: str = Form(
        "", description="Comma-separated list of participant UUIDs"
    ),
    company_id: str = Form(
        ..., description="UUID of the company associated with this call"
    ),
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """
    Process and analyze a call center audio recording.

    This comprehensive endpoint handles the full processing pipeline for call center audio:
    - Audio file validation and upload to storage
    - Transcription with speaker identification
    - Sentiment analysis of the conversation
    - Topic extraction and categorization
    - Conversation summarization
    - Problem and solution identification
    - Complete data storage in the database

    The analysis is performed using a combination of Azure AI services and OpenAI.
    """

    # get company_id
    company_id = await get_company_id(supabase, company_id)

    # Parse inputs
    date_time, participant_list = parse_inputs(date_string, participants)

    # Audio processing
    try:
        file_url, audio_id, duration = await process_audio(file, supabase, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

    # Transcription and Analysis
    try:
        print(f"Transcribing audio from URL: {file_url}")
        transcript_result, embeddings_results = get_transcription(file_url)
        analysis_result = analyze_conversation(transcript_result["phrases"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    # Database storage
    try:
        conversation_id = await store_conversation_data(
            supabase,
            audio_id,
            date_time,
            duration,
            company_id,
            analysis_result,
            participant_list,
            embeddings_results,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Database operation failed: {str(e)}"
        )

    return AnalysisResponse(success=True, conversation_id=conversation_id)


# async def process_audio_for_analysis(file: UploadFile, supabase: Client, current_user):
#     """Uploads an audio file to Supabase storage and returns the file URL"""
#     try:
#         source = "local"
#         audio_id = str(uuid.uuid4())
#         user_id = current_user.id

#         # Extract file extension and create path
#         file_ext = file.filename.split(".")[-1] if "." in file.filename else ""

#         allowed_extensions = ["mp3", "mp4", "wav"]
#         if file_ext.lower() not in allowed_extensions:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Unsupported file format. Only {', '.join(allowed_extensions)} files are allowed."
#             )

#         storage_path = f"{audio_id}.{file_ext}" if file_ext else audio_id

#         # Get file content from UploadFile
#         file_content = await file.read()

#         # Upload to Supabase
#         try:
#             supabase.storage.from_("audios").upload(
#                 storage_path,
#                 file_content,
#                 file_options={"content_type": file.content_type}
#             )
#         except Exception as upload_error:
#             raise HTTPException(
#                 status_code=500,
#                 detail=f"Failed to upload file to storage: {str(upload_error)}"
#             )

#         # Get the public URL of the uploaded file
#         file_url = supabase.storage.from_("audios").get_public_url(storage_path)

#         # Calculate duration
#         duration = None
#         try:
#             # We need to seek back to start since we've already read the file
#             await file.seek(0)
#             audio_content = await file.read()
#             audio_bytes = io.BytesIO(audio_content)
#             y, sr = librosa.load(audio_bytes, sr=None)
#             duration = int(librosa.get_duration(y=y, sr=sr))
#         except Exception as e:
#             print(f"Could not calculate duration: {str(e)}")

#         # Create a record in the database
#         file_data = {
#             "audio_id": audio_id,
#             "file_name": file.filename,
#             "file_path": file_url,
#             "source": source,
#             "duration_seconds": duration,
#             "uploaded_at": None,  # Supabase will set this with default now()
#             "uploaded_by": user_id,
#         }

#         db_response = supabase.table("audio_files").insert(file_data).execute()

#         if not db_response.data:
#             raise HTTPException(status_code=500, detail="Failed to insert record into database")

#         return file_url, audio_id, duration
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# def classify_speakers_with_gpt(utterances):
#     # Get the first few utterances to analyze patterns
#     sample_conversation = []
#     for i, utterance in enumerate(utterances):
#         sample_conversation.append(f"Speaker {utterance.speaker}: {utterance.text}")

#     conversation_text = "\n".join(sample_conversation)

#     client = OpenAI(api_key=settings.OPENAI_API_KEY)

#     response = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[
#             {"role": "system", "content": "You are an expert in analyzing call center conversations. Identify which speaker is the agent and which is the client."},
#             {"role": "user", "content": f"Below is the beginning of a call center conversation in Spanish. Identify which speaker is the agent and which is the client. Return your answer as a simple JSON with speaker letters as keys and 'agent' or 'client' as values.\n\n{conversation_text}"}
#         ],
#         response_format={"type": "json_object"}
#     )

#     try:
#         roles = eval(response.choices[0].message.content)
#         return roles
#     except:
#         return {}

# def analyze_sentiment_azure(text):
#     # Get Azure credentials from environment variables
#     azure_key = settings.AZURE_AI_KEY
#     azure_endpoint = settings.AZURE_AI_LANGUAGE_ENDPOINT

#     # Initialize the client
#     credential = AzureKeyCredential(azure_key)
#     text_analytics_client = TextAnalyticsClient(endpoint=azure_endpoint, credential=credential)

#     # Analyze sentiment
#     documents = [text]
#     response = text_analytics_client.analyze_sentiment(documents, language="es")

#     # Get the sentiment result
#     result = response[0]
#     if not result.is_error:
#         return {
#                 "positive": result.confidence_scores.positive,
#                 "negative": result.confidence_scores.negative,
#                 "neutral": result.confidence_scores.neutral
#             }
#     return {"positive": 0, "negative": 0, "neutral": 1}

# def getTranscription(file_url: str):
#     # Replace with your API key
#     aai.settings.api_key = settings.ASSEMBLYAI_API_KEY

#     config = aai.TranscriptionConfig(
#         speaker_labels=True,
#         language_code="es",
#     )

#     transcriber = aai.Transcriber()
#     transcript = transcriber.transcribe(
#         file_url,
#         config=config
#     )

#     # Use LLM to classify speakers
#     speaker_roles = classify_speakers_with_gpt(transcript.utterances)

#     output = {
#         "confidence": transcript.confidence,
#         "phrases": []
#     }

#     for utterance in transcript.utterances:
#         score = analyze_sentiment_azure(utterance.text)
#         speaker_number = ord(utterance.speaker) - ord('A') + 1
#         output["phrases"].append({
#             "text": utterance.text,
#             "speaker": speaker_number,
#             "role": speaker_roles.get(f"Speaker {utterance.speaker}", None),
#             "confidence": utterance.confidence,
#             "offsetMilliseconds": utterance.start,
#             "positive": score["positive"],
#             "negative": score["negative"],
#             "neutral": score["neutral"]
#         })
#     return output

# def summarize_conversation(transcript):
#     #Summarize the conversation using the previously generated transcript.
#     azure_key = settings.AZURE_AI_KEY
#     azure_endpoint = settings.AZURE_AI_LANGUAGE_ENDPOINT

#     conversation_data = {
#         "conversations": [
#             {
#                 "conversationItems": [
#                     {
#                         "text": phrase["text"],
#                         "modality": "text",
#                         "id": str(i + 1),
#                         "participantId": (
#                             "Agent" if phrase.get("role", "").lower() == "agent"
#                             else "Customer" if phrase.get("role", "").lower() in ["client", "customer"]
#                             else f"Speaker {phrase['speaker']}"
#                         )
#                     }
#                     for i, phrase in enumerate(transcript)
#                 ],
#                 "modality": "text",
#                 "id": "conversation1",
#                 "language": "es"
#             }
#         ]
#     }

#     credential = AzureKeyCredential(azure_key)
#     client = ConversationAnalysisClient(endpoint=azure_endpoint, credential=credential)

#     with client:
#         poller = client.begin_conversation_analysis(
#             task={
#                 "displayName": "Analyze conversations from transcript",
#                 "analysisInput": conversation_data,
#                 "tasks": [
#                     {
#                         "taskName": "Issue task",
#                         "kind": "ConversationalSummarizationTask",
#                         "parameters": {"summaryAspects": ["issue"]}
#                     },
#                     {
#                         "taskName": "Resolution task",
#                         "kind": "ConversationalSummarizationTask",
#                         "parameters": {"summaryAspects": ["resolution"]}
#                     }
#                 ]
#             }
#         )

#         result = poller.result()
#         task_results = result["tasks"]["items"]
#         structured_summary = {}

#         for task in task_results:
#             task_name = task["taskName"]
#             task_result = task["results"]

#             if task_result["errors"]:
#                 structured_summary[task_name] = "Error occurred"
#             else:
#                 conversation_result = task_result["conversations"][0]
#                 structured_summary[task_name] = {
#                     summary["aspect"]: summary["text"] for summary in conversation_result["summaries"]
#                 }

#         return structured_summary

# def extract_important_topics(transcript):
#     """Extracts the 3 most important topics from a conversation transcript using OpenAI."""
#     # Prepare the conversation text
#     conversation_text = "\n".join([
#         f"Speaker {phrase['speaker']}: {phrase['text']}"
#         for phrase in transcript
#     ])

#     client = OpenAI(api_key=settings.OPENAI_API_KEY)

#     response = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[
#             {"role": "system", "content": "Eres un experto en análisis de conversaciones de call center. Identifica los 3 temas más importantes discutidos en la conversación."},
#             {"role": "user", "content": f"A continuación hay una transcripción de una conversación de call center en español. Identifica los 3 temas más importantes que se discutieron. Devuelve tu respuesta como un JSON con una lista de 3 temas importantes, cada tema debe de tener una longitud no mayor a 3 palabras.\n\n{conversation_text}"}
#         ],
#         response_format={"type": "json_object"}
#     )

#     # Print just the content, not the whole response object
#     response_content = response.choices[0].message.content

#     try:
#         # Use json module instead of eval for safer parsing
#         import json
#         topics_data = json.loads(response_content)
#         topics = topics_data.get("temas_importantes", [])
#         print(f"Extracted topics: {topics}")
#         return topics
#     except Exception as e:
#         print(f"Error extracting topics: {str(e)}")
#         return []

# def process_topics(supabase: Client, topics: List[str], conversation_id: str) -> None:
#     """Process and insert topics with proper error handling."""
#     for topic in topics:
#         try:
#             topic_text = topic.lower()
#             # Check if topic already exists
#             existing_topic = supabase.table("topics").select("*").eq("topic", topic_text).execute()

#             if existing_topic.data and len(existing_topic.data) > 0:
#                 topic_id = existing_topic.data[0].get("topic_id")
#                 if not topic_id:
#                     print(f"WARNING: Retrieved topic '{topic_text}' is missing topic_id")
#                     continue
#             else:
#                 # Create new topic if it doesn't exist
#                 topic_query = supabase.table("topics").insert({"topic": topic_text}).execute()
#                 if not topic_query.data or len(topic_query.data) == 0:
#                     print(f"WARNING: Failed to insert new topic '{topic_text}'")
#                     continue

#                 topic_id = topic_query.data[0].get("topic_id")
#                 if not topic_id:
#                     print(f"WARNING: New topic '{topic_text}' is missing topic_id")
#                     continue

#             # Create relationship in junction table
#             junction_query = supabase.table("topics_conversations").insert({
#                 "topic_id": topic_id,
#                 "conversation_id": conversation_id
#             }).execute()

#             if not junction_query.data or len(junction_query.data) == 0:
#                 print(f"WARNING: Failed to create relationship for topic '{topic_text}'")

#         except Exception as e:
#             print(f"ERROR: Error processing topic '{topic}': {str(e)}")
#             # Continue processing other topics


# def process_participants(supabase: Client, participants: List[str], conversation_id: str) -> None:
#     """Process and insert participants with proper validation."""
#     valid_participants = []

#     for participant in participants:
#         try:
#             # Just validate UUID format without converting to UUID object and back
#             uuid.UUID(participant)  # This will raise ValueError if invalid
#             valid_participants.append({
#                 "conversation_id": conversation_id,
#                 "user_id": participant  # Use the string directly
#             })
#         except ValueError:
#             print(f"ERROR: Invalid UUID format for participant: {participant}")

#     if valid_participants:
#         try:
#             participant_query = supabase.table("participants").insert(valid_participants).execute()
#             if not participant_query.data or len(participant_query.data) == 0:
#                 print("WARNING: Participant insertion may have failed")
#         except Exception as e:
#             print(f"ERROR: Failed to insert participants: {str(e)}")


# def process_transcripts(supabase: Client, phrases: List[Dict[str, Any]], conversation_id: str) -> None:
#     """Process and insert transcript messages with proper error handling."""
#     for i, phrase in enumerate(phrases):
#         try:
#             transcript_query = supabase.table("messages").insert({
#                 "conversation_id": conversation_id,
#                 "text": phrase["text"],
#                 "speaker": phrase["speaker"],
#                 "offsetmilliseconds": phrase["offsetMilliseconds"],
#                 "role": phrase.get("role"),
#                 "confidence": phrase["confidence"],
#                 "positive": phrase["positive"],
#                 "negative": phrase["negative"],
#                 "neutral": phrase["neutral"]
#             }).execute()

#             if not transcript_query.data or len(transcript_query.data) == 0:
#                 print(f"ERROR: Failed to insert transcript {i}")
#         except Exception as e:
#             print(f"ERROR: Error inserting transcript {i}: {str(e)}")
