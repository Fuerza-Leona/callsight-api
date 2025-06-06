from typing import Dict, List

from app.core.config import settings
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient
from azure.ai.language.conversations import ConversationAnalysisClient
from openai import OpenAI
import json


def analyze_conversation(transcript):
    """Combines all analysis operations on a transcript"""
    summary = summarize_conversation(transcript)
    topics = extract_important_topics(transcript)
    return {"phrases": transcript, "summary": summary, "topics": topics}


def analyze_sentiment(text):
    # Get Azure credentials from environment variables
    azure_key = settings.AZURE_AI_KEY
    azure_endpoint = settings.AZURE_AI_LANGUAGE_ENDPOINT

    # Initialize the client
    credential = AzureKeyCredential(azure_key)
    text_analytics_client = TextAnalyticsClient(
        endpoint=azure_endpoint, credential=credential
    )

    # Analyze sentiment
    documents = [text]
    response = text_analytics_client.analyze_sentiment(documents, language="es")

    # Get the sentiment result
    result = response[0]
    if not result.is_error:
        return {
            "positive": result.confidence_scores.positive,
            "negative": result.confidence_scores.negative,
            "neutral": result.confidence_scores.neutral,
        }
    return {"positive": 0, "negative": 0, "neutral": 1}


def summarize_conversation(transcript):
    # Summarize the conversation using the previously generated transcript.
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
                            "Agent"
                            if phrase.get("role", "").lower() == "agent"
                            else "Customer"
                            if phrase.get("role", "").lower() in ["client", "customer"]
                            else f"Speaker {phrase['speaker']}"
                        ),
                    }
                    for i, phrase in enumerate(transcript)
                ],
                "modality": "text",
                "id": "conversation1",
                "language": "es",
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
                        "parameters": {"summaryAspects": ["issue"]},
                    },
                    {
                        "taskName": "Resolution task",
                        "kind": "ConversationalSummarizationTask",
                        "parameters": {"summaryAspects": ["resolution"]},
                    },
                ],
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
                    summary["aspect"]: summary["text"]
                    for summary in conversation_result["summaries"]
                }

        return structured_summary


async def analyze_messages_sentiment_openai(messages: List[str]) -> Dict:
    """
    Alternative sentiment analysis using OpenAI (more reliable)
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    messages_text = ""
    for i, message in enumerate(messages):
        clean_message = (
            message.replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
        )
        messages_text += f"Mensaje {i + 1}: {clean_message}\n"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": 'Eres un experto en análisis de sentimientos para conversaciones de call center. Analiza el sentimiento de cada mensaje y devuelve un JSON válido con el formato exacto: {"messages": [{"text": "mensaje original", "positive": 0.0, "negative": 0.0, "neutral": 0.0, "confidence": 1.0}, {text:...}]}. Los valores de positive, negative y neutral deben sumar 1.0. Centrate más en los valores positive y negative, no tanto en neutral. NO agregues texto adicional, solo el JSON.',
            },
            {
                "role": "user",
                "content": f"Analiza el sentimiento de estos mensajes:\n{messages_text}",
            },
        ],
        temperature=0.0,  # Set to 0 for more consistent responses
        response_format={"type": "json_object"},
    )

    try:
        response_content = response.choices[0].message.content
        response_content = response_content.strip()

        sentiment_data = json.loads(response_content)
        return sentiment_data

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        print(f"Error: {str(e)}")
        return {
            "messages": [
                {
                    "text": message,
                    "positive": 0.1,
                    "negative": 0.1,
                    "neutral": 0.8,
                    "confidence": 1.0,
                }
                for message in messages
            ]
        }


def extract_important_topics(transcript):
    """Extracts the 3 most important topics from a conversation transcript using OpenAI."""
    # Prepare the conversation text
    try:
        conversation_text = "\n".join(
            [f"Speaker {phrase['speaker']}: {phrase['text']}" for phrase in transcript]
        )
    except Exception as e:
        print(f"Error preparing conversation text: {str(e)}")
        return []

    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
    except Exception as e:
        print(f"Error creating OpenAI client: {str(e)}")
        return []

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un experto en análisis de conversaciones de call center. Identifica los 3 temas más importantes discutidos en la conversación.",
                },
                {
                    "role": "user",
                    "content": f"A continuación hay una transcripción de una conversación de call center en español. Identifica los 3 temas más importantes que se discutieron. Devuelve tu respuesta como un JSON con una lista de 3 temas importantes, cada tema debe de tener una longitud no mayor a 3 palabras.\n\n{conversation_text}",
                },
            ],
            response_format={"type": "json_object"},
        )
    except Exception as e:
        print(f"Error making OpenAI API call: {str(e)}")
        return []

    try:
        response_content = response.choices[0].message.content
    except Exception as e:
        print(f"Error extracting response content: {str(e)}")
        return []

    try:
        topics_data = json.loads(response_content)
        topics = topics_data.get("temas_importantes", [])

        # Try alternative keys if the expected one doesn't exist
        if not topics:
            alternative_keys = ["topics", "important_topics", "temas", "topicos"]
            for key in alternative_keys:
                if key in topics_data:
                    topics = topics_data[key]
                    print(f"Found topics using key '{key}': {topics}")
                    break

            if not topics:
                print(
                    f"No topics found with any key. Available keys: {list(topics_data.keys())}"
                )

        return topics
    except json.JSONDecodeError:
        try:
            # Try to clean the response content
            cleaned_content = response_content.strip()
            if cleaned_content.startswith("```json"):
                cleaned_content = (
                    cleaned_content.replace("```json", "").replace("```", "").strip()
                )
            topics_data = json.loads(cleaned_content)
            topics = topics_data.get("temas_importantes", [])
            return topics
        except Exception as clean_error:
            print(f"Error even after cleaning: {str(clean_error)}")
            return []
    except Exception as e:
        print(f"Error extracting topics: {str(e)}")
        print(f"Exception type: {type(e)}")
        return []


def extract_important_topics2(transcript):
    """Extracts the 3 most important topics from a conversation transcript using OpenAI."""
    # Prepare the conversation text
    conversation_text = "\n".join([phrase["text"] for phrase in transcript])

    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "Eres un experto en análisis de conversaciones de call center. Identifica los 3 temas más importantes discutidos en la conversación.",
            },
            {
                "role": "user",
                "content": f"A continuación hay una transcripción de una conversación de call center en español. Identifica los 3 temas más importantes que se discutieron. Devuelve tu respuesta como un JSON con una lista de 3 temas importantes, cada tema debe de tener una longitud no mayor a 3 palabras.\n\n{conversation_text}",
            },
        ],
        response_format={"type": "json_object"},
    )

    # Print just the content, not the whole response object
    response_content = response.choices[0].message.content

    try:
        topics_data = json.loads(response_content)
        topics = topics_data.get("temas_importantes", [])
        return topics
    except Exception as e:
        print(f"Error extracting topics: {str(e)}")
        return []
