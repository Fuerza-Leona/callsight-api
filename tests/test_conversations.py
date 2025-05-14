import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import app
from app.db.session import get_supabase
from app.api.deps import get_current_user


client = TestClient(app)


@pytest.fixture
def mock_current_user():
    mock_user = MagicMock()
    mock_user.id = "00000000-0000-0000-0000-000000000000"
    return mock_user


@pytest.fixture
def mock_supabase():
    mock_client = MagicMock()
    return mock_client


@pytest.fixture(autouse=True)
def override_dependencies(mock_current_user, mock_supabase):
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    yield
    app.dependency_overrides = {}


# TC - 01
def test_get_conversations_with_params_admin(mock_current_user, mock_supabase):
    mock_conversations = [
        {
            "conversation_id": "ea06921f-5f92-427f-b7f8-9b6826684fff",
            "start_time": "2025-05-04T00:00:00+00:00",
            "end_time": "2025-05-04T00:02:25+00:00",
            "category": "Construcción",
            "company": "Cemex",
            "participants": 7,
        }
    ]
    mock_supabase.rpc().execute.return_value.data = mock_conversations
    with patch("app.api.routes.conversations.check_user_role", return_value="admin"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={
                "agents": [
                    "57824f03-11a2-41ff-81e1-64942051c712",
                    "6c6a2991-b0df-454a-8516-552b8473c040",
                ]
            },
        )
    assert response.status_code == 200
    assert "conversations" in response.json()
    assert response.json()["conversations"] == mock_conversations


# TC - 02
def test_get_conversations_with_params_agent(mock_current_user, mock_supabase):
    mock_conversations = [
        {
            "conversation_id": "ea06921f-5f92-427f-b7f8-9b6826684fff",
            "start_time": "2025-05-04T00:00:00+00:00",
            "end_time": "2025-05-04T00:02:25+00:00",
            "category": "Construcción",
            "company": "Cemex",
            "participants": 7,
        }
    ]

    mock_supabase.rpc().execute.return_value.data = mock_conversations
    with patch("app.api.routes.conversations.check_user_role", return_value="agent"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={
                "clients": [
                    "757334fc-b171-44b3-9814-b3e8fed3d1d8",
                    "f57c8dc3-8a30-44be-8647-f88824602afc",
                ]
            },
        )
    assert response.status_code == 200
    assert "conversations" in response.json()
    assert response.json()["conversations"] == mock_conversations


# TC - 03
def test_get_conversations_with_params_client(mock_current_user, mock_supabase):
    mock_conversations = [
        {
            "conversation_id": "ea06921f-5f92-427f-b7f8-9b6826684fff",
            "start_time": "2025-05-04T00:00:00+00:00",
            "end_time": "2025-05-04T00:02:25+00:00",
            "category": "Construcción",
            "company": "Cemex",
            "participants": 7,
        }
    ]

    mock_supabase.rpc().execute.return_value.data = mock_conversations
    with patch("app.api.routes.conversations.check_user_role", return_value="client"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={"startDate": "2025-05-01", "endDate": "2025-05-30"},
        )
    assert response.status_code == 200
    assert "conversations" in response.json()
    assert response.json()["conversations"] == mock_conversations


# TC - 04
def test_get_conversationn_with_id(mock_current_user, mock_supabase):
    mock_conversations = [
        {
            "conversation_id": "ea06921f-5f92-427f-b7f8-9b6826684fff",
            "start_time": "2025-05-04T00:00:00+00:00",
            "end_time": "2025-05-04T00:02:25+00:00",
            "category": "Construcción",
            "company": "Cemex",
            "participants": 7,
        }
    ]

    mock_supabase.rpc().execute.return_value.data = mock_conversations
    with patch("app.api.routes.conversations.check_user_role", return_value="admin"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={"conversation_id": "ea06921f-5f92-427f-b7f8-9b6826684fff"},
        )
    assert response.status_code == 200
    assert "conversations" in response.json()
    assert response.json()["conversations"] == mock_conversations


# TC - 05
def test_get_conversations_without_params(mock_current_user, mock_supabase):
    mock_conversations = [
        {
            "conversation_id": "7c2cf77c-8ebd-4c5d-8dbb-77095ca6f68c",
            "start_time": "2025-05-04T00:00:00+00:00",
            "end_time": "2025-05-04T00:02:25+00:00",
            "category": "Construcción",
            "company": "Cemex",
            "participants": 2,
        },
        {
            "conversation_id": "ea06921f-5f92-427f-b7f8-9b6826684fff",
            "start_time": "2025-05-04T00:00:00+00:00",
            "end_time": "2025-05-04T00:02:25+00:00",
            "category": "Construcción",
            "company": "Cemex",
            "participants": 7,
        },
    ]

    with patch("app.api.routes.conversations.check_user_role", return_value="admin"):
        mock_supabase.rpc().execute.return_value.data = mock_conversations
        response = client.post("/api/v1/conversations/mine", json={})

    assert response.status_code == 200
    assert "conversations" in response.json()
    assert response.json()["conversations"] == mock_conversations


# TC - 06
def test_get_conversations_wrong_order_dates_params(mock_current_user, mock_supabase):
    with patch("app.api.routes.conversations.check_user_role", return_value="agent"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={"startDate": "2025-02-01", "endDate": "2025-01-01"},
        )
    assert response.status_code == 400
    assert "Invalid filter" in response.json()["detail"]


# TC - 07
def test_get_conversations_invalid_dates_params(mock_current_user, mock_supabase):
    with patch("app.api.routes.conversations.check_user_role", return_value="agent"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={"startDate": "12 May", "endDate": "2025-06-06"},
        )
    assert response.status_code == 400
    assert "Invalid filter" in response.json()["detail"]


# TC - 08
def test_get_conversation_invalid_id(mock_current_user, mock_supabase):
    with patch("app.api.routes.conversations.check_user_role", return_value="admin"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={"conversation_id": "1"},
        )
    assert response.status_code == 400
    assert "Invalid conversation_id format" in response.json()["detail"]


# TC - 09
def test_get_conversation_invalid_agents(mock_current_user, mock_supabase):
    with patch("app.api.routes.conversations.check_user_role", return_value="admin"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={"agents": ["1"]},
        )
    assert response.status_code == 400
    assert "Invalid filter: Invalid UUID in agents: 1" in response.json()["detail"]


# TC - 10
def test_get_conversation_invalid_companies(mock_current_user, mock_supabase):
    with patch("app.api.routes.conversations.check_user_role", return_value="admin"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={"companies": ["1"]},
        )
    assert response.status_code == 400
    assert "Invalid filter: Invalid UUID in companies: 1" in response.json()["detail"]


# TC - 11
def test_get_conversation_invalid_clients(mock_current_user, mock_supabase):
    with patch("app.api.routes.conversations.check_user_role", return_value="admin"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={"clients": ["1"]},
        )
    assert response.status_code == 400
    assert "Invalid filter: Invalid UUID in clients: 1" in response.json()["detail"]


# TC - 12
def test_client_cannot_filter_by_agents(mock_current_user, mock_supabase):
    with patch("app.api.routes.conversations.check_user_role", return_value="client"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={"agents": ["57824f03-11a2-41ff-81e1-64942051c712"]},
        )
    assert response.status_code == 400
    assert (
        "Clients cannot filter by agents, companies or clients"
        in response.json()["detail"]
    )


# TC - 13
def test_client_cannot_filter_by_companies(mock_current_user, mock_supabase):
    with patch("app.api.routes.conversations.check_user_role", return_value="client"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={"companies": ["57824f03-11a2-41ff-81e1-64942051c712"]},
        )
    assert response.status_code == 400
    assert (
        "Clients cannot filter by agents, companies or clients"
        in response.json()["detail"]
    )


# TC - 14
def test_client_cannot_filter_by_clients(mock_current_user, mock_supabase):
    with patch("app.api.routes.conversations.check_user_role", return_value="client"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={"clients": ["57824f03-11a2-41ff-81e1-64942051c712"]},
        )
    assert response.status_code == 400
    assert (
        "Clients cannot filter by agents, companies or clients"
        in response.json()["detail"]
    )


# TC - 15
def test_agent_cannot_filter_by_agents(mock_current_user, mock_supabase):
    with patch("app.api.routes.conversations.check_user_role", return_value="agent"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={"agents": ["57824f03-11a2-41ff-81e1-64942051c712"]},
        )
    assert response.status_code == 400
    assert "Agents cannot filter other agents" in response.json()["detail"]
