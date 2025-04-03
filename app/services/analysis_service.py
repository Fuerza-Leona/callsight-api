from app.core.config import settings
from azure.core.credentials import AzureKeyCredential
from azure.ai.textanalytics import TextAnalyticsClient
from azure.ai.language.conversations import ConversationAnalysisClient
from openai import OpenAI

def analyze_conversation(transcript):
    """Combines all analysis operations on a transcript"""
    summary = summarize_conversation(transcript)
    topics = extract_important_topics(transcript)
    return {
        "phrases": transcript,
        "summary": summary,
        "topics": topics
    }
    
def analyze_sentiment(text):
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
    
def extract_important_topics(transcript):
    """Extracts the 3 most important topics from a conversation transcript using OpenAI."""
    # Prepare the conversation text
    conversation_text = "\n".join([
        f"Speaker {phrase['speaker']}: {phrase['text']}"
        for phrase in transcript
    ])
    
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Eres un experto en análisis de conversaciones de call center. Identifica los 3 temas más importantes discutidos en la conversación."},
            {"role": "user", "content": f"A continuación hay una transcripción de una conversación de call center en español. Identifica los 3 temas más importantes que se discutieron. Devuelve tu respuesta como un JSON con una lista de 3 temas importantes, cada tema debe de tener una longitud no mayor a 3 palabras.\n\n{conversation_text}"}
        ],
        response_format={"type": "json_object"}
    )

    # Print just the content, not the whole response object
    response_content = response.choices[0].message.content
    
    try:
        # Use json module instead of eval for safer parsing
        import json
        topics_data = json.loads(response_content)
        topics = topics_data.get("temas_importantes", [])
        print(f"Extracted topics: {topics}")
        return topics
    except Exception as e:
        print(f"Error extracting topics: {str(e)}")
        return []