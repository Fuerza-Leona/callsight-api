from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel

from supabase import Client
from app.db.session import get_supabase

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
