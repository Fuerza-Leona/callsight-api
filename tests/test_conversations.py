from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from dateutil.relativedelta import relativedelta

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


def test_get_conversations_without_params_agent_role(mock_current_user, mock_supabase):
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

    mock_supabase.rpc().execute.return_value.data = mock_conversations

    with patch("app.api.routes.conversations.check_user_role", return_value="agent"):
        response = client.post("/api/v1/conversations/mine", json={})

    startDate = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    endDate = (
        datetime.now().replace(day=1) + relativedelta(months=1, days=-1)
    ).strftime("%Y-%m-%d")

    mock_supabase.rpc.assert_called_with(
        "new_build_get_my_conversations_query",
        {
            "start_date": startDate,
            "end_date": endDate,
            "user_role": "agent",
            "id": mock_current_user.id,
            "conv_id": None,
            "clients": None,
            "agents": None,
            "companies": None,
        },
    )

    assert response.status_code == 200
    assert "conversations" in response.json()
    assert response.json()["conversations"] == mock_conversations


def test_get_conversations_without_params_client_role(mock_current_user, mock_supabase):
    mock_conversations = [
        {
            "conversation_id": "1e5706e9-9652-41b5-969d-71e51fe9fe31",
            "start_time": "2025-05-04T00:00:00+00:00",
            "end_time": "2025-05-04T00:02:25+00:00",
            "category": "Construcción",
            "company": "Cemex",
            "participants": 2,
        }
    ]

    mock_supabase.rpc().execute.return_value.data = mock_conversations

    with patch("app.api.routes.conversations.check_user_role", return_value="client"):
        response = client.post("/api/v1/conversations/mine", json={})

    startDate = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    endDate = (
        datetime.now().replace(day=1) + relativedelta(months=1, days=-1)
    ).strftime("%Y-%m-%d")

    mock_supabase.rpc.assert_called_with(
        "new_build_get_my_conversations_query",
        {
            "start_date": startDate,
            "end_date": endDate,
            "user_role": "client",
            "id": mock_current_user.id,
            "conv_id": None,
            "clients": None,
            "agents": None,
            "companies": None,
        },
    )

    assert response.status_code == 200
    assert "conversations" in response.json()
    assert response.json()["conversations"] == mock_conversations


def test_get_conversations_without_params_admin_role(mock_current_user, mock_supabase):
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
        {
            "conversation_id": "1e5706e9-9652-41b5-969d-71e51fe9fe31",
            "start_time": "2025-05-04T00:00:00+00:00",
            "end_time": "2025-05-04T00:02:25+00:00",
            "category": "Construcción",
            "company": "Cemex",
            "participants": 2,
        },
    ]

    mock_supabase.rpc().execute.return_value.data = mock_conversations

    with patch("app.api.routes.conversations.check_user_role", return_value="admin"):
        response = client.post("/api/v1/conversations/mine", json={})

    startDate = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    endDate = (
        datetime.now().replace(day=1) + relativedelta(months=1, days=-1)
    ).strftime("%Y-%m-%d")

    mock_supabase.rpc.assert_called_with(
        "new_build_get_my_conversations_query",
        {
            "start_date": startDate,
            "end_date": endDate,
            "user_role": "admin",
            "id": mock_current_user.id,
            "conv_id": None,
            "clients": None,
            "agents": None,
            "companies": None,
        },
    )

    assert response.status_code == 200
    assert "conversations" in response.json()
    assert response.json()["conversations"] == mock_conversations


def test_get_conversations_with_params(mock_current_user, mock_supabase):
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

    startDate = "2023-05-01"
    endDate = "2023-05-30"
    clients = [
        "00000000-0000-0000-0000-000000000003",
        "00000000-0000-0000-0000-000000000004",
    ]
    agents = ["00000000-0000-0000-0000-000000000004"]
    companies = ["00000000-0000-0000-0000-000000000005"]
    conversation_id = "ea06921f-5f92-427f-b7f8-9b6826684fff"

    mock_supabase.rpc().execute.return_value.data = mock_conversations

    with patch("app.api.routes.conversations.check_user_role", return_value="admin"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={
                "clients": clients,
                "agents": agents,
                "companies": companies,
                "conversation_id": conversation_id,
                "startDate": startDate,
                "endDate": endDate,
            },
        )

    mock_supabase.rpc.assert_called_with(
        "new_build_get_my_conversations_query",
        {
            "start_date": startDate,
            "end_date": endDate,
            "user_role": "admin",
            "id": mock_current_user.id,
            "conv_id": conversation_id,
            "clients": clients,
            "agents": agents,
            "companies": companies,
        },
    )

    assert response.status_code == 200
    assert "conversations" in response.json()
    assert response.json()["conversations"] == mock_conversations


def test_get_conversations_wrong_order_dates_params(mock_current_user, mock_supabase):
    with patch("app.api.routes.conversations.check_user_role", return_value="agent"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={"startDate": "2023-02-01", "endDate": "2023-01-01"},
        )
    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]


def test_get_conversations_invalid_dates_params(mock_current_user, mock_supabase):
    with patch("app.api.routes.conversations.check_user_role", return_value="agent"):
        response = client.post(
            "/api/v1/conversations/mine",
            json={"startDate": "01-01-2023", "endDate": "23 June 2023"},
        )
    assert response.status_code == 400
    assert "Invalid date format" in response.json()["detail"]
