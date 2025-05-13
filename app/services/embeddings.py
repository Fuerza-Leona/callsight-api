from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from app.db.session import get_supabase
from app.api.deps import get_current_user
from app.core.config import settings
from pydantic import BaseModel, Field
import tiktoken

from openai import OpenAI

import os

GPT_MODEL = os.getenv("GPT_MODEL", "gpt-4o-mini")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 1000))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 1000))

router = APIRouter(prefix="/embeddings", tags=["embeddings"])

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class EmbeddingQuery(BaseModel):
    password: str = Field(..., min_length=1, description="Query to embed and search")


def num_tokens(text: str, model: str = EMBEDDING_MODEL) -> int:
    """Return the number of tokens in a string."""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))


""" @router.get("/")
async def new_chat_with_context(
    current_user=Depends(get_current_user), 
    supabase: Client = Depends(get_supabase),
    query: str = EmbeddingQuery,
    token_budget: int = 4096 - 500,
):
    
    #Get the top 3 vector matches for the user embedding query
    
    try:
        response = client.embeddings.create(
            input=query,
            model=EMBEDDING_MODEL
        )

        response = supabase.rpc('get_nearest_neighbor_l2distance', params={'query_embedding': response.data[0].embedding}).execute()
        print(response)
        if response.data is None or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="No data could be matched using this query")

        introduction = (
            "The following are pieces of a transcript or from multiple transcripts from calls between a call center and a client company. "
            "Use this information to answer the subsequent question as accurately as possible *only if it clearly contains the answer or allows a strong inference*. "
            "If the answer is directly stated in the transcript, give it, but don't use the word 'transcript' to refer to your source, say 'como se mencionó durante una llamada previa.'. "
            "If it can be reasonably inferred, explain your reasoning. "
            "If the context seems off-topic, vague, or unhelpful, IGNORE it completely and answer the question from general knowledge. "
            "If the answer cannot be found or reasonably inferred, ignore all context and answer as you would if you only got the question and no additional data"
            )
        #introduction = 'The following are pieces of a transcript or from multiple transcripts from calls between a call center and a client company. Use this information to answer the subsequent question. If the answer cannot be found in the transcripts, answer as you would with no additional context, but start by saying "No pude encontrar una respuesta en el contexto que tengo, pero..."'
        question = f"\n\nQuestion: {query}"
        message = introduction + question
        #for transcript_chunk in [chunk['content'] for chunk in response.data]:
        for transcript_chunk in (chunk['content'] for chunk in response.data):
            #next_chunk = f'\n\nTranscript chunk:\n" ""\n{transcript_chunk}\n" ""'
            if (
                num_tokens(message + next_chunk, model=GPT_MODEL)
                > token_budget
            ):
                break
            else:
                message += next_chunk

        #DEBUG
        #print("message: ",message)

        response = client.responses.create(
            model=GPT_MODEL,
            input=[
                {"role": "system", "content": "You answer questions for agents of a call center working with multiple companies."},
                {"role": "user", "content": message},
            ],
        )
        #return response.output_text
        return {
            "response": response.output_text
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) """


async def chat_with_context(
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
    query: str = EmbeddingQuery,
    token_budget: int = 4096 - 500,
):
    response = client.embeddings.create(input=query, model=EMBEDDING_MODEL)

    response = supabase.rpc(
        "get_nearest_neighbor_l2distance",
        params={"query_embedding": response.data[0].embedding},
    ).execute()
    if response.data is None or len(response.data) == 0:
        raise HTTPException(
            status_code=404, detail="No data could be matched using this query"
        )
    introduction = (
        "The following are pieces of a transcript or from multiple transcripts from calls between a call center and a client company. "
        "Use this information to answer the subsequent question as accurately as possible *only if it clearly contains the answer or allows a strong inference*. "
        "If the answer is directly stated in the transcript, give it, but don't use the word 'transcript' to refer to your source, say 'como se mencionó durante una llamada previa.'. "
        "If it can be reasonably inferred, explain your reasoning. "
        "If the context seems off-topic, vague, or unhelpful, IGNORE it completely and answer the question from general knowledge. "
        "If the answer cannot be found or reasonably inferred, ignore all context and answer as you would if you only got the question and no additional data"
    )
    question = f"\n\nQuestion: {query}"
    message = introduction + question
    for transcript_chunk in (chunk["content"] for chunk in response.data):
        next_chunk = f'\n\nTranscript chunk:\n"""\n{transcript_chunk}\n"""'
        if num_tokens(message + next_chunk, model=GPT_MODEL) > token_budget:
            break
        else:
            message += next_chunk

    return message


# @router.get("/last")
async def get_last_embeddings(
    current_user=Depends(get_current_user), supabase: Client = Depends(get_supabase)
):
    """
    Get last embeddings for a specific user
    """

    embeddings_response = supabase.rpc(
        "get_latest_embeddings", params={"user_id": current_user.id}
    ).execute()

    return embeddings_response.data


async def suggestions_with_context(
    response_data: list,
    token_budget: int = 4096 - 500,
):
    message = (
        "The following are pieces of a transcript or from multiple transcripts from calls between a call center and a client company. This might be a complete or uncomplete transcript, or may also contain chunks from multiple transcripts. "
        "Use this information to generate 3 prompt suggestions or follow up questions that a user could ask. "
        "Don't mention your source, only give the suggestions. "
        "If the context seems vague, or unhelpful, IGNORE it completely and give 3 suggestions an agent could ask ChatGPT so as to enhance their performance or gain insights from similar cases or colleagues. "
        "If you can't get reasonably inferred questions, ignore all context and answer as you would if you had received only the prompt with no additional information."
    )
    for transcript_chunk in (chunk["content"] for chunk in response_data):
        next_chunk = f'\n\nTranscript chunk:\n"""\n{transcript_chunk}\n"""'
        if num_tokens(message + next_chunk, model=GPT_MODEL) > token_budget:
            break
        else:
            message += next_chunk

    return message
