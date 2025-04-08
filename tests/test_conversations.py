import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import app
from app.db.session import get_supabase
from app.api.deps import get_current_user

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
    return mock_client

# Override dependencies for testing
@pytest.fixture(autouse=True)
def override_dependencies(mock_current_user, mock_supabase):
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    yield
    app.dependency_overrides = {}

# Test getting all conversations
def test_get_conversations(mock_supabase):
    # Setup mock responses
    mock_data = [
        {
            "conversation_id": "test-conv-1",
            "start_time": "2023-01-01T10:00:00",
            "end_time": "2023-01-01T10:15:00"
        }
    ]
    mock_supabase.table().select().execute.return_value.data = mock_data
    
    # Mock the get_categories function to return some test categories
    with patch("app.api.routes.conversations.get_categories", return_value=["support", "billing"]):
        # Make request to the API
        response = client.get("/api/v1/conversations/")
    
    # Assert response
    assert response.status_code == 200
    assert "conversations" in response.json()
    assert len(response.json()["conversations"]) == 1
    assert response.json()["conversations"][0]["conversation_id"] == "test-conv-1"

# Test getting conversations for the current user
def test_get_mine(mock_current_user, mock_supabase):
    # Setup mock responses for participants query
    mock_participants = [{"conversation_id": "test-conv-1"}]
    mock_supabase.table().select().eq().execute.return_value.data = mock_participants
    
    # Setup mock responses for conversations query
    mock_conversations = [
        {
            "conversation_id": "test-conv-1",
            "start_time": "2023-01-01T10:00:00",
            "end_time": "2023-01-01T10:15:00"
        }
    ]
    mock_supabase.table().select().in_().execute.return_value.data = mock_conversations
    
    # Mock the get_categories function
    with patch("app.api.routes.conversations.get_categories", return_value=["support"]):
        # Make request to the API
        response = client.get("/api/v1/conversations/mine")
    
    # Assert response
    assert response.status_code == 200
    assert "conversations" in response.json()
    assert len(response.json()["conversations"]) == 1
    assert response.json()["conversations"][0]["conversation_id"] == "test-conv-1"

# Test getting emotions data
def test_get_emotions(mock_current_user, mock_supabase):
    # Setup mock responses for participants query
    mock_participants = [{"conversation_id": "test-conv-1"}]
    mock_supabase.table().select().eq().execute.return_value.data = mock_participants
    
    # Setup mock responses for messages query
    mock_messages = [
        {"positive": 0.7, "negative": 0.1, "neutral": 0.2},
        {"positive": 0.6, "negative": 0.2, "neutral": 0.2}
    ]
    mock_supabase.table().select().in_().execute.return_value.data = mock_messages
    
    # Make request to the API
    response = client.get("/api/v1/conversations/myClientEmotions")
    
    # Assert response
    assert response.status_code == 200
    assert "emotions" in response.json()
    assert "positive" in response.json()["emotions"]
    assert "negative" in response.json()["emotions"]
    assert "neutral" in response.json()["emotions"]