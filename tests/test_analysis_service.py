import pytest
from unittest.mock import MagicMock, patch
import json

# Sample transcript data for testing
@pytest.fixture
def sample_transcript():
    return [
        {
            "text": "Buenos días, gracias por llamar a Servicio al Cliente. ¿En qué puedo ayudarle hoy?",
            "speaker": 1,
            "role": "agent",
            "confidence": 0.95,
            "offsetMilliseconds": 1000,
            "positive": 0.7,
            "negative": 0.1,
            "neutral": 0.2
        },
        {
            "text": "Hola, tengo un problema con mi factura. Hay un cargo que no reconozco.",
            "speaker": 2,
            "role": "client",
            "confidence": 0.92,
            "offsetMilliseconds": 5000,
            "positive": 0.2,
            "negative": 0.6,
            "neutral": 0.2
        },
        {
            "text": "Entiendo su preocupación. Permítame revisar su cuenta para verificar ese cargo.",
            "speaker": 1,
            "role": "agent",
            "confidence": 0.94,
            "offsetMilliseconds": 12000,
            "positive": 0.6,
            "negative": 0.1,
            "neutral": 0.3
        },
        {
            "text": "Gracias, el cargo es del 15 de abril por $49.99.",
            "speaker": 2,
            "role": "client",
            "confidence": 0.93,
            "offsetMilliseconds": 18000,
            "positive": 0.3,
            "negative": 0.4,
            "neutral": 0.3
        }
    ]

# Test analyze_sentiment function
@patch('app.services.analysis_service.AzureKeyCredential')
@patch('app.services.analysis_service.TextAnalyticsClient')
def test_analyze_sentiment(mock_text_analytics_client, mock_azure_credential):
    from app.services.analysis_service import analyze_sentiment

    mock_client_instance = MagicMock()
    mock_text_analytics_client.return_value = mock_client_instance

    mock_response = [MagicMock()]
    mock_response[0].is_error = False
    mock_response[0].confidence_scores.positive = 0.85
    mock_response[0].confidence_scores.negative = 0.05
    mock_response[0].confidence_scores.neutral = 0.10

    mock_client_instance.analyze_sentiment.return_value = mock_response

    # Call the function
    text = "Estoy muy contento con el servicio que me brindaron."
    result = analyze_sentiment(text)

    # Assertions
    assert result["positive"] == 0.85
    assert result["negative"] == 0.05
    assert result["neutral"] == 0.10

    # Verify mock calls
    mock_client_instance.analyze_sentiment.assert_called_once_with([text], language="es")

# Test analyze_sentiment with error
@patch('app.services.analysis_service.AzureKeyCredential')
@patch('app.services.analysis_service.TextAnalyticsClient')
def test_analyze_sentiment_error(mock_text_analytics_client, mock_azure_credential):
    from app.services.analysis_service import analyze_sentiment

    # Set up mock client and response
    mock_client_instance = MagicMock()
    mock_text_analytics_client.return_value = mock_client_instance

    mock_response = [MagicMock()]
    mock_response[0].is_error = True

    mock_client_instance.analyze_sentiment.return_value = mock_response

    # Call the function
    text = "Texto para probar el error."
    result = analyze_sentiment(text)

    # Assertions - should return default values
    assert result["positive"] == 0
    assert result["negative"] == 0
    assert result["neutral"] == 1

class MockConversationClient:
    def __init__(self, *args, **kwargs):
        self.begin_conversation_analysis = MagicMock()
        self.poller = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

# Test summarize_conversation function
def test_summarize_conversation(sample_transcript):
    from app.services.analysis_service import summarize_conversation

    # Create mock result
    mock_result = {
        "tasks": {
            "items": [
                {
                    "taskName": "Issue task",
                    "results": {
                        "errors": [],
                        "conversations": [
                            {
                                "summaries": [
                                    {
                                        "aspect": "issue",
                                        "text": "El cliente reporta un cargo no reconocido en su factura por $49.99 del 15 de abril."
                                    }
                                ]
                            }
                        ]
                    }
                },
                {
                    "taskName": "Resolution task",
                    "results": {
                        "errors": [],
                        "conversations": [
                            {
                                "summaries": [
                                    {
                                        "aspect": "resolution",
                                        "text": "El agente ofreció revisar la cuenta del cliente para verificar el cargo."
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }
    }

    # Create mock poller
    mock_poller = MagicMock()
    mock_poller.result.return_value = mock_result

    # Create a mock client
    mock_client = MockConversationClient()
    mock_client.begin_conversation_analysis.return_value = mock_poller

    # Patch both credential and client
    with patch('app.services.analysis_service.AzureKeyCredential') as mock_credential, \
         patch('app.services.analysis_service.ConversationAnalysisClient', return_value=mock_client):

        # Call the function
        result = summarize_conversation(sample_transcript)

        # Assertions
        assert "Issue task" in result
        assert "issue" in result["Issue task"]
        assert "Resolution task" in result
        assert "resolution" in result["Resolution task"]
        assert "El cliente reporta un cargo no reconocido" in result["Issue task"]["issue"]
        assert "El agente ofreció revisar la cuenta" in result["Resolution task"]["resolution"]

# Test extract_important_topics function
@patch('app.services.analysis_service.OpenAI')
def test_extract_important_topics(mock_openai, sample_transcript):
    from app.services.analysis_service import extract_important_topics

    # Set up mock client and response
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = json.dumps({"temas_importantes": ["facturación", "cargo desconocido", "verificación cuenta"]})
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    # Call the function
    result = extract_important_topics(sample_transcript)

    # Assertions
    assert len(result) == 3
    assert "facturación" in result
    assert "cargo desconocido" in result
    assert "verificación cuenta" in result

    # Verify mock calls
    mock_client.chat.completions.create.assert_called_once()
    assert mock_client.chat.completions.create.call_args[1]["model"] == "gpt-4o"

# Test analyze_conversation function (integration of the above functions)
@patch('app.services.analysis_service.extract_important_topics')
@patch('app.services.analysis_service.summarize_conversation')
def test_analyze_conversation(mock_summarize, mock_topics, sample_transcript):
    from app.services.analysis_service import analyze_conversation

   # Set up mock return values
    mock_summarize.return_value = {
        "Issue task": {"issue": "Cargo no reconocido en factura"},
        "Resolution task": {"resolution": "Revisión de cuenta"}
    }

    mock_topics.return_value = ["facturación", "cargo desconocido", "verificación cuenta"]

    # Call the function
    result = analyze_conversation(sample_transcript)

    # Assertions
    assert "phrases" in result
    assert result["phrases"] == sample_transcript

    assert "summary" in result
    assert result["summary"]["Issue task"]["issue"] == "Cargo no reconocido en factura"

    assert "topics" in result
    assert len(result["topics"]) == 3
    assert "facturación" in result["topics"]

    # Verify mock calls
    mock_summarize.assert_called_once_with(sample_transcript)
    mock_topics.assert_called_once_with(sample_transcript)
