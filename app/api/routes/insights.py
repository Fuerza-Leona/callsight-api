from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from app.db.session import get_supabase
from app.api.deps import get_current_user
from app.services.embeddings import suggestions_with_context
from app.core.config import settings
from openai import OpenAI
import json
import os

router = APIRouter(prefix="/insights", tags=["insights"])

client = OpenAI(api_key=settings.OPENAI_API_KEY)

GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4o-mini")


@router.post("/")
async def get_insights(
    company_id: str,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        embeddings_response = supabase.rpc(
            "get_latest_embeddings_for_company", params={"company_id": company_id}
        ).execute()

        if embeddings_response.data is None or len(embeddings_response.data) == 0:
            raise HTTPException(
                status_code=404, detail="No embeddings found for this company"
            )

        message = await suggestions_with_context(embeddings_response.data)

        response = client.responses.create(
            model=GPT_MODEL,
            input=[
                {
                    "role": "system",
                    "content": 'Eres un asistente útil para un agente de soporte a cliente de la empresa NEORIS. Tu tarea es dar 3 insights que este agente pueda encontrar utiles para mejorar su trabajo con una empresa cliente especifica. Solo respondes en JSON con el siguiente formato: { "insights": [ "insight1", "insight2", "insight3"] }, sin usar formato markdown. UNICAMENTE DEVUELVE EL JSON EN FORMATO SIMPLE. ',
                },
                {
                    "role": "user",
                    "content": message,
                },
            ],
        )
        json_string = response.output_text
        print(f"JSON String: {json_string}")
        parsed = json.loads(json_string)
        return parsed

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
