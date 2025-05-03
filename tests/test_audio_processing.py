import pytest
import io
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import UploadFile

from app.main import app
from app.db.session import get_supabase
from app.api.deps import get_current_user
from app.services.audio_service import process_audio
from app.services.transcription_service import get_transcription

# Create test client
client = TestClient(app)


# Mock user for authentication
@pytest.fixture
def mock_current_user():
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    return mock_user


# Mock Supabase client
@pytest.fixture
def mock_supabase():
    mock_client = MagicMock()

    # Mock storage functionality
    storage_mock = MagicMock()
    storage_mock.upload.return_value = None
    storage_mock.get_public_url.return_value = "https://example.com/test-audio.mp3"

    mock_client.storage.from_.return_value = storage_mock

    # Mock table insertion
    table_mock = MagicMock()
    table_mock.insert.return_value.execute.return_value.data = [
        {"audio_id": "test-audio-id"}
    ]
    mock_client.table.return_value = table_mock

    return mock_client


# Override dependencies for testing
@pytest.fixture(autouse=True)
def override_dependencies(mock_current_user, mock_supabase):
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    yield
    app.dependency_overrides = {}


# Mock file for testing
@pytest.fixture
def mock_audio_file():
    file_content = b"test audio content"
    return io.BytesIO(file_content)


# Test audio upload and processing
@pytest.mark.asyncio
async def test_process_audio(mock_supabase, mock_current_user, mock_audio_file):
    # Create a mock FastAPI UploadFile
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "test_audio.mp3"
    mock_file.content_type = "audio/mpeg"
    mock_file.read = AsyncMock(return_value=mock_audio_file.getvalue())
    mock_file.seek = AsyncMock()

    mock_supabase.reset_mock()

    storage_mock = MagicMock()
    storage_mock.upload.return_value = None
    storage_mock.get_public_url.return_value = "https://example.com/test-audio.mp3"
    mock_supabase.storage.from_.return_value = storage_mock

    # Mock librosa duration calculation
    with (
        patch("librosa.load") as mock_load,
        patch("librosa.get_duration") as mock_duration,
    ):
        mock_load.return_value = (None, None)  # y, sr values
        mock_duration.return_value = 60  # 60 seconds

        # Call the function
        file_url, audio_id, duration = await process_audio(
            mock_file, mock_supabase, mock_current_user
        )

    # Assertions
    assert file_url == "https://example.com/test-audio.mp3"
    assert duration == 60
    assert audio_id is not None

    # Verify mock calls - only check the critical parts
    assert mock_supabase.storage.from_.called
    assert mock_supabase.table.called


# Test transcription service
@pytest.mark.asyncio
async def test_transcription_service():
    file_url = "https://example.com/test-audio.mp3"

    # Mock assemblyai transcription
    with (
        patch("assemblyai.Transcriber") as mock_transcriber_class,
        patch(
            "app.services.transcription_service.classify_speakers_with_gpt"
        ) as mock_classify,
        patch("app.services.transcription_service.analyze_sentiment") as mock_sentiment,
        patch("app.services.transcription_service.OpenAI") as mock_openai_class,
        patch("app.services.transcription_service.convert_to_chunks") as mock_chunks,
    ):
        # mock OpenAI client patch
        mock_openai_instance = MagicMock()
        mock_openai_class.return_value = mock_openai_instance

        mock_chunks.return_value = [
            "Speaker A: Hello, how can I help you today?",
            "Speaker B: I'm having an issue with my account.",
        ]

        mock_embeddings = MagicMock()
        mock_embeddings.create.return_value = MagicMock(
            data=[
                MagicMock(index=0, embedding=[0.1, 0.2, 0.3]),
                MagicMock(index=1, embedding=[0.4, 0.5, 0.6]),
            ]
        )
        mock_openai_instance.embeddings = mock_embeddings

        # Set up mock transcriber
        mock_transcriber = MagicMock()
        mock_transcriber_class.return_value = mock_transcriber

        # Set up mock transcript result
        mock_transcript = MagicMock()
        mock_transcript.confidence = 0.95

        # Create mock utterances
        mock_utterance1 = MagicMock()
        mock_utterance1.speaker = "A"
        mock_utterance1.text = "Hello, how can I help you today?"
        mock_utterance1.confidence = 0.98
        mock_utterance1.start = 1000

        mock_utterance2 = MagicMock()
        mock_utterance2.speaker = "B"
        mock_utterance2.text = "I'm having an issue with my account."
        mock_utterance2.confidence = 0.92
        mock_utterance2.start = 5000

        # Add utterances to transcript
        mock_transcript.utterances = [mock_utterance1, mock_utterance2]

        # Set up transcribe return value
        mock_transcriber.transcribe.return_value = mock_transcript

        # Set up speaker classification mock
        mock_classify.return_value = {"Speaker A": "agent", "Speaker B": "client"}

        # Set up sentiment analysis mock
        mock_sentiment.side_effect = [
            {"positive": 0.8, "negative": 0.1, "neutral": 0.1},  # For utterance 1
            {"positive": 0.3, "negative": 0.6, "neutral": 0.1},  # For utterance 2
        ]

        # Call the function
        result, embeddings_results = get_transcription(file_url)

        # Assertions
        assert result["confidence"] == 0.95
        assert len(result["phrases"]) == 2

        # Check first phrase (agent)
        assert result["phrases"][0]["text"] == "Hello, how can I help you today?"
        assert result["phrases"][0]["speaker"] == 1
        assert result["phrases"][0]["role"] == "agent"
        assert result["phrases"][0]["positive"] == 0.8

        # Check second phrase (client)
        assert result["phrases"][1]["text"] == "I'm having an issue with my account."
        assert result["phrases"][1]["speaker"] == 2
        assert result["phrases"][1]["role"] == "client"
        assert result["phrases"][1]["negative"] == 0.6

        # Verify mock calls
        mock_transcriber.transcribe.assert_called_once_with(
            file_url, config=mock_transcriber_class().transcribe.call_args[1]["config"]
        )
        assert mock_classify.call_count == 1
        assert mock_sentiment.call_count == 2


# Test the full AI analysis endpoint
@pytest.mark.asyncio
async def test_alternative_analysis_endpoint(
    mock_supabase, mock_current_user, mock_audio_file
):
    # Setup mocks for all dependent services
    with (
        patch("app.api.routes.ai.process_audio") as mock_process_audio,
        patch("app.api.routes.ai.get_transcription") as mock_get_transcription,
        patch("app.api.routes.ai.analyze_conversation") as mock_analyze,
        patch("app.api.routes.ai.store_conversation_data") as mock_store,
    ):
        # Set up return values
        mock_process_audio.return_value = (
            "https://example.com/test-audio.mp3",
            "test-audio-id",
            60,
        )

        mock_transcript_result = {
            "confidence": 0.95,
            "phrases": [
                {
                    "text": "Hello, how can I help you today?",
                    "speaker": 1,
                    "role": "agent",
                    "confidence": 0.98,
                    "offsetMilliseconds": 1000,
                    "positive": 0.8,
                    "negative": 0.1,
                    "neutral": 0.1,
                },
                {
                    "text": "I'm having an issue with my account.",
                    "speaker": 2,
                    "role": "client",
                    "confidence": 0.92,
                    "offsetMilliseconds": 5000,
                    "positive": 0.3,
                    "negative": 0.6,
                    "neutral": 0.1,
                },
            ],
        }
        mock_get_transcription.return_value = (
            mock_transcript_result,
            [
                {
                    "chunk_index": 0,
                    "content": "Speaker A: Hello, how can I help you today?",
                    "vector": [0.1, 0.2, 0.3],
                },
                {
                    "chunk_index": 1,
                    "content": "Speaker B: I'm having an issue with my account.",
                    "vector": [0.4, 0.5, 0.6],
                },
            ],
        )

        mock_analysis_result = {
            "phrases": mock_transcript_result["phrases"],
            "summary": {
                "Issue task": {"issue": "Account access problem"},
                "Resolution task": {"resolution": "Reset account credentials"},
            },
            "topics": ["account access", "password reset", "login issues"],
        }
        mock_analyze.return_value = mock_analysis_result

        mock_store.return_value = "test-conversation-id"

        # Create test file
        test_file = ("file", ("test_audio.mp3", mock_audio_file, "audio/mpeg"))

        # Make request to the API endpoint
        response = client.post(
            "/api/v1/ai/alternative-analysis",
            files=[test_file],
            data={
                "date_string": "2023-05-15 14:30",
                "participants": "user-id-1,user-id-2",
                "company_id": "company-id-1",
            },
        )

        # Assertions
        assert response.status_code == 201
        assert response.json()["success"] is True
        assert response.json()["conversation_id"] == "test-conversation-id"

        # Verify mock calls
        mock_process_audio.assert_called_once()
        mock_get_transcription.assert_called_once_with(
            "https://example.com/test-audio.mp3"
        )
        mock_analyze.assert_called_once_with(mock_transcript_result["phrases"])
        mock_store.assert_called_once()
