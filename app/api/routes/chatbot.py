from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from app.db.session import get_supabase
from app.api.deps import get_current_user
from app.services.embeddings import (
    chat_with_context,
    suggestions_with_context,
    get_last_embeddings,
)
from app.core.config import settings
import os

import json
from uuid import uuid4
from datetime import datetime, timedelta

from openai import OpenAI
from pydantic import BaseModel

router = APIRouter(prefix="/chatbot", tags=["chatbot"])

client = OpenAI(api_key=settings.OPENAI_API_KEY)

GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4o-mini")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 1000))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 1000))


class ChatRequest(BaseModel):
    prompt: str


def needs_context(prompt: str, previous_response_id: str = None):
    judgment = client.responses.create(
        model=GPT_MODEL,
        previous_response_id=previous_response_id,
        input=[
            {
                "role": "system",
                "content": "You're an assistant helping decide whether a user's question "
                "requires searching previous customer service transcripts. "
                "If the question is about a person, event, or conversation that may have occurred "
                "in a past interaction, reply with 'needs context'. If it's a general question "
                "that can be answered without having to retrieve any more past data, reply with 'no context'. "
                "Only reply with one of these two phrases.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    if "needs context" in judgment.output_text.lower():
        use_context = True
    else:
        use_context = False
    return use_context


def create_messages_for_supabase(
    conversation_id: str,
    prompt: str,
    response_id: str,
    response_output_text: str,
    response_created_at: str,
    prev_response_id: str = None,
):
    created_at = datetime.fromtimestamp(response_created_at)
    user_created_at = (created_at - timedelta(seconds=1)).isoformat()
    created_at = created_at.isoformat()
    user_message = {
        "chatbot_message_id": str(uuid4()),
        "chatbot_conversation_id": conversation_id,
        "role": "user",
        "content": prompt,
        "created_at": user_created_at,
        "previous_response_id": prev_response_id,
    }
    chatbot_message = {
        "chatbot_message_id": response_id,
        "chatbot_conversation_id": conversation_id,
        "role": "assistant",
        "content": response_output_text,
        "created_at": created_at,
        "previous_response_id": prev_response_id,
    }
    return user_message, chatbot_message


@router.post("/chat")
async def post_chat(
    request: ChatRequest,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
    token_budget: int = 4096 - 500,
):
    """Create a new chat"""
    try:
        conversation_id = str(uuid4())
        gpt_model = GPT_MODEL
        # if the question needs previous context, start a new chat with added embeddings
        if needs_context(request.prompt):
            message = await chat_with_context(
                current_user=current_user,
                supabase=supabase,
                query=request.prompt,
                token_budget=token_budget,
            )
        else:
            message = request.prompt

        response = client.responses.create(
            model=GPT_MODEL,
            input=[
                {
                    "role": "system",
                    "content": "You answer questions for agents of a call center working with multiple companies.",
                },
                {"role": "user", "content": message},
            ],
        )
        title = client.responses.create(
            model=gpt_model,
            previous_response_id=response.id,
            input=[
                {"role": "user", "content": "Crea un titulo para esta conversación"},
            ],
        )
        chatbot_conversation = {
            "chatbot_conversation_id": conversation_id,
            "user_id": current_user.id,
            "title": title.output_text,
            "last_response_id": response.id,
            "model": gpt_model,
        }

        user_message, chatbot_message = create_messages_for_supabase(
            conversation_id,
            request.prompt,
            response.id,
            response.output_text,
            response.created_at,
        )

        supabase.table("chatbot_conversations").insert(chatbot_conversation).execute()
        supabase.table("chatbot_messages").insert(user_message).execute()
        supabase.table("chatbot_messages").insert(chatbot_message).execute()

        return {
            "response": response.output_text,
            "title": title.output_text,
            "conversation_id": conversation_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/continue/{conversation_id}")
async def continue_chat(
    request: ChatRequest,
    conversation_id: str,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
    token_budget: int = 4096 - 500,
):
    """
    Continuar un chat existente
    """
    try:
        # select last response from conversation where conversation = conversation_id
        previous_response_id = (
            supabase.table("chatbot_conversations")
            .select("last_response_id")
            .eq("chatbot_conversation_id", conversation_id)
            .execute()
        ).data[0]
        previous_response_id = previous_response_id["last_response_id"]

        # if the question needs previous context, start use added embeddings
        if needs_context(request.prompt, previous_response_id):
            message = await chat_with_context(
                current_user=current_user,
                supabase=supabase,
                query=request.prompt,
                token_budget=token_budget,
            )
        else:
            message = request.prompt

        response = client.responses.create(
            model=GPT_MODEL,
            previous_response_id=previous_response_id,
            input=[
                {"role": "system", "content": "Eres un asistente para un call center."},
                {"role": "user", "content": message},
            ],
        )

        # use the obtained info to generate supabase appropiate objects
        user_message, chatbot_message = create_messages_for_supabase(
            conversation_id,
            request.prompt,
            response.id,
            response.output_text,
            response.created_at,
            previous_response_id,
        )

        # modify the table to change the last message
        supabase.table("chatbot_conversations").update(
            {"last_response_id": response.id}
        ).eq(
            "chatbot_conversation_id", conversation_id
        ).execute()  # modify the table to change the last message

        supabase.table("chatbot_messages").insert(user_message).execute()
        supabase.table("chatbot_messages").insert(chatbot_message).execute()
        return {"response": response.output_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suggestions")
async def get_suggestions(
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        response = await get_last_embeddings(current_user, supabase)

        if response is None or len(response) == 0:
            message = "Dame 3 recomendaciones de prompts que te pueda preguntar, en formato json"
            system_content = 'Eres un asistente útil para un agente de soporte a cliente de la empresa NEORIS. Tu tarea es dar 3 recomendaciones de prompts que este agente le puede preguntar a ChatGPT para mejorar su trabajo o resolver dudas. Solo respondes en JSON con el siguiente formato: { "recommendations": [ "Prompt1", "Prompt2", "Prompt3"] }, sin usar formato markdown. UNICAMENTE DEVUELVE EL JSON EN FORMATO SIMPLE. Las preguntas deben ser generales y útiles para cualquier agente de soporte en un centro de llamadas. Algunos ejemplos: [Cómo explicar una política de reembolsos, Frases para calmar a un cliente molesto, Cómo manejar una llamada difícil, Pasos para resolver un problema técnico, Mejores prácticas para comunicarse con claridad, Qué hacer si un cliente interrumpe mucho, Cómo empatizar sin comprometerse, Técnicas para escuchar activamente].'

        else:
            message = await suggestions_with_context(response_data=response)
            system_content = 'Eres un asistente útil para un agente de soporte de NEORIS. Tu tarea es proponer 3 preguntas que el agente podría hacerle a ChatGPT, usando los siguientes fragmentos de transcripción. Las preguntas deben reflejar lo que está ocurriendo en las conversaciones — por ejemplo, preguntar si un problema fue resuelto, redactar planes de acción, o pedir seguimiento. Solo responde con JSON sin formato markdown. Usa este formato: { "recommendations": [ "Prompt1", "Prompt2", "Prompt3"] }. NO repitas el contenido. NO respondas con consejos'

        response = client.responses.create(
            model=GPT_MODEL,
            input=[
                {
                    "role": "system",
                    "content": system_content,
                },
                {
                    "role": "user",
                    "content": message,
                },
            ],
        )
        json_string = response.output_text
        parsed = json.loads(json_string)
        return parsed

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all_chats")
async def get_all_chats(
    current_user=Depends(get_current_user), supabase: Client = Depends(get_supabase)
):
    try:
        user_id = current_user.id
        response = (
            supabase.table("chatbot_conversations")
            .select("chatbot_conversation_id", "title")
            .eq("user_id", user_id)
            .execute()
        )

        if response.data is None or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="User profile not found")

        return response.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat_history/{conversation_id}")
async def get_chat_history(
    conversation_id: str,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        user_id = current_user.id
        valid_chat = (
            supabase.table("chatbot_conversations")
            .select("chatbot_conversation_id")
            .eq("user_id", user_id)
            .eq("chatbot_conversation_id", conversation_id)
            .single()
            .execute()
        )

        if not valid_chat.data:
            raise HTTPException(
                status_code=404,
                detail="No chatbot history matching this conversation_id for this use",
            )

        response = (
            supabase.table("chatbot_messages")
            .select("role, created_at, content, previous_response_id")
            .eq("chatbot_conversation_id", conversation_id)
            .order("created_at", desc=False)
            .execute()
        )

        if response.data is None or len(response.data) == 0:
            raise HTTPException(
                status_code=404,
                detail="No chatbot history matching this conversation_id for this user",
            )

        return response.data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
