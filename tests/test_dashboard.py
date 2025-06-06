import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.db.session import get_supabase
from app.api.deps import get_current_user

client = TestClient(app)


@pytest.fixture
def mock_current_user():
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
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


def test_get_users_clients(mock_current_user, mock_supabase):
    mock_db_response = MagicMock()
    mock_db_response.data = [
        {
            "user_id": "00000000-0000-0000-0000-000000000000",
            "username": "Miguel Mendoza",
        },
        {
            "user_id": "00000000-0000-0000-0000-000000000001",
            "username": "Fernando Monroy",
        },
    ]
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_db_response
    response = client.get("/api/v1/users/client")
    assert response.status_code == 200
    assert "clients" in response.json()
    assert len(response.json()["clients"]) == 2
    assert (
        response.json()["clients"][0]["user_id"]
        == "00000000-0000-0000-0000-000000000000"
    )
    assert response.json()["clients"][0]["username"] == "Miguel Mendoza"
    assert (
        response.json()["clients"][1]["user_id"]
        == "00000000-0000-0000-0000-000000000001"
    )
    assert response.json()["clients"][1]["username"] == "Fernando Monroy"


"""
def test_get_categories(mock_current_user, mock_supabase):
    with patch("app.api.routes.conversations.check_user_role", return_value="agent"):
        mock_rpc_response = MagicMock()
        mock_rpc_response.data = [{"category": "support"}, {"category": "billing"}]
        mock_supabase.rpc.return_value.execute.return_value = mock_rpc_response

        response = client.post(
            "/api/v1/conversations/myClientCategories",
            json={
                "clients": [],
                "categories": [],
                "startDate": "2023-01-01",
                "endDate": "2023-01-31",
            },
        )

    assert response.status_code == 200
    assert "categories" in response.json()
"""

"""
def test_get_emotions(mock_current_user, mock_supabase):
    with patch("app.api.routes.conversations.check_user_role", return_value="agent"):
        mock_rpc_response = MagicMock()
        mock_rpc_response.data = [{"positive": 0.65, "negative": 0.15, "neutral": 0.2}]
        mock_supabase.rpc.return_value.execute.return_value = mock_rpc_response

        response = client.post(
            "/api/v1/conversations/myClientEmotions",
            json={
                "clients": [],
                "categories": [],
                "startDate": "2023-01-01",
                "endDate": "2023-01-31",
            },
        )

    assert response.status_code == 200
    assert "emotions" in response.json()
    assert "positive" in response.json()["emotions"]
    assert "negative" in response.json()["emotions"]
    assert "neutral" in response.json()["emotions"]
    assert response.json()["emotions"]["positive"] == 0.65
    assert response.json()["emotions"]["negative"] == 0.15
    assert response.json()["emotions"]["neutral"] == 0.2
"""
