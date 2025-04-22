from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from app.db.session import get_supabase
from app.api.deps import get_current_user
from app.core.config import settings

from openai import OpenAI
from pydantic import BaseModel

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

client = OpenAI(api_key=settings.OPENAI_API_KEY)

class ChatRequest(BaseModel):
    prompt: str


@router.post("/chat")
async def post_chat(
    request: ChatRequest,
    #current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    try:
        response = client.responses.create(
            model="gpt-3.5-turbo",
            input=[
                {"role": "system", "content": "You are a helpful assistant for a call center."},
                {"role": "user", "content": request.prompt},
            ],
        )
        return {"response": response.output_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/continue/{conversation_id}")
async def continue_chat(
    conversation_id: str,
    request: ChatRequest,
    #current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """Test id: resp_6807cc6371d8819185c5832054ff4c910413c6fd1ef76301"""
    try:
        response = client.responses.create(
            model="gpt-3.5-turbo",
            previous_response_id=conversation_id,
            input=[
                {"role": "system", "content": "You are a helpful assistant for a call center."},
                {"role": "user", "content": request.prompt},
            ],
        )
        return {"response": response.output_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/suggestions")
async def post_chat(
    request: ChatRequest,
    #current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant for a call center that gives 3 reccomendations on helpful things to ask."},
                {"role": "user", "content": request.prompt},
            ],
        )
        return {"response": response.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))