import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from app.services.storage_service import (
    store_conversation_data,
    process_topics,
    process_participants,
    process_transcripts,
)


# Sample data for testing
@pytest.fixture
def sample_analysis_result():
    return {
        "phrases": [
            {
                "text": "Buenos días, ¿en qué puedo ayudarle?",
                "speaker": 1,
                "role": "agent",
                "confidence": 0.95,
                "offsetMilliseconds": 1000,
                "positive": 0.7,
                "negative": 0.1,
                "neutral": 0.2,
            },
            {
                "text": "Hola, tengo un problema con mi servicio de internet.",
                "speaker": 2,
                "role": "client",
                "confidence": 0.92,
                "offsetMilliseconds": 5000,
                "positive": 0.2,
                "negative": 0.6,
                "neutral": 0.2,
            },
        ],
        "summary": {
            "Issue task": {"issue": "Problema con servicio de internet"},
            "Resolution task": {"resolution": "Soporte técnico proporcionado"},
        },
        "topics": ["internet", "servicio técnico", "soporte"],
    }


# Test store_conversation_data
@pytest.mark.asyncio
async def test_store_conversation_data(sample_analysis_result):
    # Mock supabase
    mock_supabase = MagicMock()

    # Mock conversation
    conversation_mock = MagicMock()
    conversation_mock.execute.return_value.data = [
        {"conversation_id": "test-conversation-id"}
    ]
    mock_supabase.table.return_value.insert.return_value = conversation_mock

    # Test data
    audio_id = "test-audio-id"
    date_time = datetime.now()
    duration = 120
    company_id = "test-company-id"
    participant_list = ["user1-id", "user2-id"]
    embeddings_results = [
        {
            "chunk_index": 0,
            "content": "Speaker A: Buenos días, ¿en qué puedo ayudarle?",
            "vector": [0.1, 0.2, 0.3],
        },
        {
            "chunk_index": 1,
            "content": "Speaker B: Hola, tengo un problema con mi servicio de internet.",
            "vector": [0.4, 0.5, 0.6],
        },
    ]

    # Mock the sub-functions to isolate the main function
    with (
        patch(
            "app.services.storage_service.process_topics", new=AsyncMock()
        ) as mock_process_topics,
        patch(
            "app.services.storage_service.process_participants", new=AsyncMock()
        ) as mock_process_participants,
        patch(
            "app.services.storage_service.process_transcripts", new=AsyncMock()
        ) as mock_process_transcripts,
    ):
        # Set them up as AsyncMock since they're async functions
        mock_process_topics.side_effect = AsyncMock()
        mock_process_participants.side_effect = AsyncMock()
        mock_process_transcripts.side_effect = AsyncMock()

        # Call the function
        conversation_id = await store_conversation_data(
            mock_supabase,
            audio_id,
            date_time,
            duration,
            company_id,
            sample_analysis_result,
            participant_list,
            embeddings_results,
        )

        # Basic assertions
        assert conversation_id == "test-conversation-id"

        # Verify the mocked functions were called
        mock_process_topics.assert_called_once()
        mock_process_participants.assert_called_once()
        mock_process_transcripts.assert_called_once()


# Test process_topics
@pytest.mark.asyncio
async def test_process_topics():
    # Mock supabase
    mock_supabase = MagicMock()

    # Mock select response for existing topics check
    select_mock = MagicMock()
    select_mock.eq.return_value.execute.return_value.data = []
    mock_supabase.table.return_value.select.return_value = select_mock

    # Mock insert response for topics
    topic_insert_mock = MagicMock()
    topic_insert_mock.execute.return_value.data = [{"topic_id": "test-topic-id"}]

    # Mock insert response for junction table
    junction_insert_mock = MagicMock()
    junction_insert_mock.execute.return_value.data = [{"id": 1}]

    # Set up the table.insert method to return different mocks depending on args
    mock_supabase.table.return_value.insert.side_effect = [
        topic_insert_mock,  # First call - for topic
        junction_insert_mock,  # Second call - for junction
        topic_insert_mock,  # Repeat for additional topics
        junction_insert_mock,
        topic_insert_mock,
        junction_insert_mock,
    ]

    # Test data
    topics = ["facturación", "soporte", "internet"]
    conversation_id = "test-conversation-id"

    # Call the function
    await process_topics(mock_supabase, topics, conversation_id)

    # Verify only that the function completed without error
    assert True


# Test process_participants
@pytest.mark.asyncio
async def test_process_participants():
    # Create mock supabase client
    mock_supabase = MagicMock()

    # Configure the response
    insert_mock = MagicMock()
    insert_mock.execute.return_value.data = [{"participant_id": "test-participant-id"}]
    mock_supabase.table.return_value.insert.return_value = insert_mock

    # Test data
    participants = [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
    ]
    conversation_id = "test-conversation-id"

    # Call the function
    await process_participants(mock_supabase, participants, conversation_id)

    # Basic assertion to ensure function was called
    assert mock_supabase.table.called

    # Check that data with correct format was passed
    insert_call_args = mock_supabase.table.return_value.insert.call_args
    assert insert_call_args is not None

    # Get the data passed to insert
    inserted_data = insert_call_args[0][0]

    # Check there are two participants
    assert isinstance(inserted_data, list)
    assert len(inserted_data) == 2

    # Check participant data format
    for item in inserted_data:
        assert "conversation_id" in item
        assert "user_id" in item
        assert item["conversation_id"] == conversation_id


# Test process_participants with invalid UUID
@pytest.mark.asyncio
async def test_process_participants_invalid_uuid():
    # Create mock supabase client
    mock_supabase = MagicMock()

    # Configure the response
    insert_response = MagicMock()
    insert_response.execute.return_value.data = [
        {"participant_id": "test-participant-id"}
    ]
    mock_supabase.table.return_value.insert.return_value = insert_response

    # Test data with one valid and one invalid UUID
    participants = ["00000000-0000-0000-0000-000000000001", "invalid-uuid"]
    conversation_id = "test-conversation-id"

    # Call the function
    await process_participants(mock_supabase, participants, conversation_id)

    # Check that data with correct format was passed
    insert_call_args = mock_supabase.table.return_value.insert.call_args
    assert insert_call_args is not None

    # Get the data passed to insert
    inserted_data = insert_call_args[0][0]

    # Check there is only one participant (the valid UUID)
    assert isinstance(inserted_data, list)
    assert len(inserted_data) == 1
    assert inserted_data[0]["user_id"] == participants[0]


# Test process_transcripts
@pytest.mark.asyncio
async def test_process_transcripts():
    # Create mock supabase client
    mock_supabase = MagicMock()

    # Configure the response
    insert_response = MagicMock()
    insert_response.execute.return_value.data = [{"message_id": "test-message-id"}]
    mock_supabase.table.return_value.insert.return_value = insert_response

    # Test data
    phrases = [
        {
            "text": "Buenos días, ¿en qué puedo ayudarle?",
            "speaker": 1,
            "role": "agent",
            "confidence": 0.95,
            "offsetMilliseconds": 1000,
            "positive": 0.7,
            "negative": 0.1,
            "neutral": 0.2,
        },
        {
            "text": "Hola, tengo un problema con mi servicio de internet.",
            "speaker": 2,
            "role": "client",
            "confidence": 0.92,
            "offsetMilliseconds": 5000,
            "positive": 0.2,
            "negative": 0.6,
            "neutral": 0.2,
        },
    ]
    conversation_id = "test-conversation-id"

    # Call the function
    await process_transcripts(mock_supabase, phrases, conversation_id)

    # Verify the function was called
    assert mock_supabase.table.called

    # Check the number of insertions matches the number of phrases
    insert_calls = mock_supabase.table.return_value.insert.call_args_list
    assert len(insert_calls) == len(phrases)

    # Check the data format for the first phrase
    first_insert_data = insert_calls[0][0][0]
    assert first_insert_data["conversation_id"] == conversation_id
    assert first_insert_data["text"] == phrases[0]["text"]
    assert first_insert_data["offsetmilliseconds"] == phrases[0]["offsetMilliseconds"]
