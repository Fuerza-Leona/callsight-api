import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.db.session import get_supabase

# Create test client
client = TestClient(app)

# Mock Supabase client
@pytest.fixture
def mock_supabase():
    mock_client = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: mock_client
    yield mock_client
    app.dependency_overrides = {}

def test_login(mock_supabase):
    # Setup mock user and session response
    mock_auth_response = MagicMock()
    mock_auth_response.user.id = "test-user-id"
    mock_auth_response.session.access_token = "fake-access-token"
    mock_auth_response.session.refresh_token = "fake-refresh-token"

    mock_supabase.auth.sign_in_with_password.return_value = mock_auth_response

    # Setup mock user data response
    mock_user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "role": "agent",
        "department": "support"
    }
    mock_supabase.table().select().eq().execute.return_value.data = [mock_user_data]

    # Make request to the API
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "TestPass123"}
    )

    # Assert response
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()
    assert "user" in response.json()
    assert response.json()["user"]["username"] == "testuser"
    assert response.json()["user"]["role"] == "agent"

    # Verify the correct methods were called
    mock_supabase.auth.sign_in_with_password.assert_called_once()
    mock_supabase.table().select().eq().execute.assert_called_once()

def test_signup(mock_supabase):
    # Setup mock responses
    # First check if email exists - should return empty array
    mock_supabase.table().select().eq().execute.return_value.data = []

    # Mock company check and response
    company_check_response = MagicMock()
    company_check_response.data = [{"company_id": "test-company-id"}]

    # Create a sequence of responses for different calls
    mock_supabase.table().select().eq().execute.side_effect = [
        MagicMock(data=[]),  # Email check - no existing user
        company_check_response  # Company check - existing company
    ]

    # Mock auth signup response
    mock_auth_user = MagicMock()
    mock_auth_user.id = "test-user-id"

    mock_auth_response = MagicMock()
    mock_auth_response.user = mock_auth_user

    mock_supabase.auth.sign_up.return_value = mock_auth_response

    # Mock user creation response
    mock_user_creation = MagicMock()
    mock_user_creation.data = [{"user_id": "test-user-id"}]
    mock_supabase.table().insert().execute.return_value = mock_user_creation

    # Make request to the API
    response = client.post(
        "/api/v1/auth/signup",
        json={
            "email": "newuser@example.com",
            "password": "StrongPass123",
            "username": "newuser",
            "company_name": "Existing Company",
            "role": "agent",
            "department": "sales"
        }
    )

    # Assert response
    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["user_id"] == "test-user-id"
    assert response.json()["username"] == "newuser"
    assert response.json()["role"] == "agent"
