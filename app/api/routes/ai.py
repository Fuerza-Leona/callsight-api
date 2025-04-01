from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel

from supabase import Client
from app.db.session import get_supabase
import assemblyai as aai
from openai import OpenAI
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential
from app.core.config import settings
from app.services.call_analysis.main import run as analyze_call

router = APIRouter(prefix="/ai", tags=["ai"])

class AudioAnalysisRequest(BaseModel):
    audio_url: str
    language: Optional[str] = "en"
    locale: Optional[str] = "en-US"
    use_stereo_audio: Optional[bool] = False
    output_file: Optional[bool] = False

@router.post("/call-analysis")
async def analyze_audio(
    request: AudioAnalysisRequest,
    supabase: Client = Depends(get_supabase)
):
    try:
        analysis_result = analyze_call({
            "input_audio_url": request.audio_url,
            "language": request.language,
            "locale": request.locale,
            "use_stereo_audio": request.use_stereo_audio,
            "output_file": request.output_file
        })
        
        return analysis_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alternative-analysis")
async def analyze_audio(
    request: str = "https://qkbitpdsagffscsttvxt.supabase.co/storage/v1/object/public/audios//recording4.mp3",
    supabase: Client = Depends(get_supabase)
):

    def getTranscription(file_url = "https://qkbitpdsagffscsttvxt.supabase.co/storage/v1/object/public/audios//recording4.mp3"):
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
                "role": speaker_roles.get(f"Speaker {utterance.speaker}", "unknown"),
                "confidence": utterance.confidence,
                "offsetMilliseconds": utterance.start,
                "positive": score["positive"],
                "negative": score["negative"],
                "neutral": score["neutral"]
            })
        return output

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
                {"role": "system", "content": "You are an expert in analyzing call center conversations. Identify which speaker is the agent and which is the customer."},
                {"role": "user", "content": f"Below is the beginning of a call center conversation in Spanish. Identify which speaker is the agent and which is the customer. Return your answer as a simple JSON with speaker letters as keys and 'agent' or 'customer' as values.\n\n{conversation_text}"}
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
    
    try:
        result = getTranscription(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))