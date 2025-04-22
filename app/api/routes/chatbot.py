from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from app.db.session import get_supabase
from app.api.deps import get_current_user
from app.core.config import settings

from uuid import uuid4
from datetime import datetime

from openai import OpenAI
from pydantic import BaseModel

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

client = OpenAI(api_key=settings.OPENAI_API_KEY)

class ChatRequest(BaseModel):
    prompt: str

@router.post("/chat")
async def post_chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Create a new chat"""
    try:
        conversation_id = str(uuid4())
        gpt_model = "gpt-3.5-turbo"
        response = client.responses.create(
            model=gpt_model,
            input=[
                {"role": "system", "content": "You are a helpful assistant for a call center."},
                {"role": "user", "content": request.prompt},
            ],
        )
        title = client.responses.create(
            model=gpt_model,
            previous_response_id=response.id,
            input=[
                {"role": "user", "content": "create a title for this conversation"},
            ],
        )
        created_at = datetime.fromtimestamp(response.created_at).isoformat()
        chatbot_conversation = {
            "chatbot_conversation_id": conversation_id,
            "user_id": current_user.id,
            "title": title.output_text,
            "last_response_id": response.id,
            "model": gpt_model
        }
        user_message = {
            "chatbot_message_id": str(uuid4()),
            "chatbot_conversation_id": conversation_id,
            "role": 'user',
            "content": request.prompt,
            "created_at": created_at,
            "previous_response_id": None
        }
        chatbot_message = {
            "chatbot_message_id": response.id,
            "chatbot_conversation_id": conversation_id,
            "role": 'assistant',
            "content": response.output_text,
            "created_at": created_at,
            "previous_response_id": None
        }

        supabase.table("chatbot_conversations").insert(chatbot_conversation).execute()
        supabase.table("chatbot_messages").insert(user_message).execute()
        supabase.table("chatbot_messages").insert(chatbot_message).execute()
        
        #return {"response": response}
        return {"response": response.output_text, "title": title.output_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/continue/{conversation_id}")
async def continue_chat(
    request: ChatRequest,
    conversation_id: str,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Continuar un chat existente
    
    Test id: resp_6807cc6371d8819185c5832054ff4c910413c6fd1ef76301
    """
    try:
        #select last response from conversation where conversation = conversation_id
        previous_response_id = (supabase.table("chatbot_conversations").select("last_response_id").eq("chatbot_conversation_id", conversation_id).execute()).data[0]
        previous_response_id = previous_response_id["last_response_id"]
        response = client.responses.create(
            model="gpt-3.5-turbo",
            previous_response_id=previous_response_id,
            input=[
                {"role": "system", "content": "You are a helpful assistant for a call center."},
                {"role": "user", "content": request.prompt},
            ],
        )
        created_at = datetime.fromtimestamp(response.created_at).isoformat()
        user_message = {
            "chatbot_message_id": str(uuid4()),
            "chatbot_conversation_id": conversation_id,
            "role": 'user',
            "content": request.prompt,
            "created_at": created_at,
            "previous_response_id": previous_response_id
        }
        chatbot_message = {
            "chatbot_message_id": response.id,
            "chatbot_conversation_id": conversation_id,
            "role": 'assistant',
            "content": response.output_text,
            "created_at": created_at,
            "previous_response_id": previous_response_id
        }

        #modify the table to change the last message
        supabase.table("chatbot_conversations").update({"last_response_id": response.id}).eq("chatbot_conversation_id", conversation_id).execute() #modify the table to change the last message
        
        supabase.table("chatbot_messages").insert(user_message).execute()
        supabase.table("chatbot_messages").insert(chatbot_message).execute()
        return {"response": response.output_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

""" @router.get("/{conversation_id}")
async def get_chat(
    conversation_id: str = "",
    #current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    try:
        response = client.responses.input_items.list("resp_6807ce331a188191a41ef49b9fa9b13c0413c6fd1ef76301")
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) """

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