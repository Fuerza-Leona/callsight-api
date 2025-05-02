import time
from uuid import uuid4
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.db.session import get_supabase


client = TestClient(app)


def make_openai_side_effect():
    """Return [assistant_response, title_response] for OpenAI mock."""
    now = time.time()
    assistant = MagicMock(
        id="resp_" + uuid4().hex, output_text="Assistant response", created_at=now
    )
    title = MagicMock(
        id="title_" + uuid4().hex, output_text='"Test title"', created_at=now
    )
    return [assistant, title]


@pytest.fixture
def override_deps():
    supabase = MagicMock()
    app.dependency_overrides[get_supabase] = lambda: supabase
    app.dependency_overrides[get_current_user] = lambda: MagicMock(id="user-123")
    yield supabase
    app.dependency_overrides.clear()


@pytest.fixture
def openai_mock():
    with patch("app.api.routes.chatbot.client") as mocked_openai_client:
        yield mocked_openai_client


# Post Chat
# /chatbot/chat
def test_post_chat_success(override_deps, openai_mock):
    # OpenAI returns assistant response + title on two successive calls
    openai_mock.responses.create.side_effect = make_openai_side_effect()
    override_deps.table.return_value.insert.return_value.execute.return_value = None

    resp = client.post("/api/v1/chatbot/chat", json={"prompt": "Hola, ¿qué tal?"})

    assert resp.status_code == 200
    data = resp.json()
    assert set(data) == {"response", "title", "conversation_id"}
    assert data["response"] == "Assistant response"
    assert data["title"] == '"Test title"'


def test_post_chat_db_failure(override_deps, openai_mock):
    # DB.execute() raising an exception
    openai_mock.responses.create.side_effect = make_openai_side_effect()
    override_deps.table.return_value.insert.return_value.execute.side_effect = (
        Exception("Connection cannot be established")
    )

    resp = client.post("/api/v1/chatbot/chat", json={"prompt": "Hola"})
    assert resp.status_code == 500


# Continue Chat
# /chatbot/continue/{conversation_id}
def test_continue_chat_success(override_deps, openai_mock):
    # Look-ups & inserts
    override_deps.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [  # noqa: E501
        {"last_response_id": "resp_prev"}
    ]
    override_deps.table.return_value.insert.return_value.execute.return_value = None
    override_deps.table.return_value.update.return_value.eq.return_value.execute.return_value = None
    reply = MagicMock(
        id="resp_new", output_text="Assistant follow-up", created_at=time.time()
    )
    openai_mock.responses.create.return_value = reply

    resp = client.post("/api/v1/chatbot/continue/abc-123", json={"prompt": "¿Seguro?"})

    assert resp.status_code == 200
    assert resp.json() == {"response": "Assistant follow-up"}


def test_continue_chat_updates_db_and_inserts_msgs(override_deps, openai_mock):
    # Stub previous_response_id fetch
    override_deps.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [  # noqa: E501
        {"last_response_id": "resp_prev"}
    ]
    override_deps.table.return_value.insert.return_value.execute.return_value = None
    override_deps.table.return_value.update.return_value.eq.return_value.execute.return_value = None
    openai_mock.responses.create.return_value = MagicMock(
        id="resp_new", output_text="ok", created_at=time.time()
    )

    client.post("/api/v1/chatbot/continue/conv-1", json={"prompt": "¿Seguro?"})

    # There should be at least one update (last_response_id) and 2 inserts (user and assistant)
    assert override_deps.table.return_value.update.called, (
        "last_response_id update missing"
    )
    assert override_deps.table.return_value.insert.call_count == 2, (
        "message inserts missing"
    )


# Get All Chats
# /chatbot/all_chats
def test_get_all_chats_success(override_deps):
    override_deps.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [  # noqa: E501
        {"chatbot_conversation_id": "conversation1", "title": '"title1"'}
    ]

    resp = client.get("/api/v1/chatbot/all_chats")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["chatbot_conversation_id"] == "conversation1"
    assert data[0]["title"] == '"title1"'


def test_get_all_chats_empty(override_deps):
    override_deps.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    resp = client.get("/api/v1/chatbot/all_chats")
    assert resp.status_code == 404


# Get Chat History
# chatbot/chat_history/{conversation_id}
def test_get_chat_history_success(override_deps):
    conversation_table = MagicMock()
    conversation_table.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = True  # noqa: E501

    msg_table = MagicMock()
    msg_table.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "role": "user",
            "created_at": "2025-05-01T19:59:09",
            "content": "User Message",
            "previous_response_id": None,
        },
        {
            "role": "assistant",
            "created_at": "2025-05-01T19:59:10",
            "content": "Assistant Message",
            "previous_response_id": None,
        },
    ]

    override_deps.table.side_effect = (
        lambda name: conversation_table
        if name == "chatbot_conversations"
        else msg_table
    )

    resp = client.get("/api/v1/chatbot/chat_history/conv-1")

    assert resp.status_code == 200
    chatHistory = resp.json()
    assert chatHistory[0]["role"] == "user"
    assert chatHistory[0]["content"] == "User Message"
    assert chatHistory[0]["previous_response_id"] is None
    assert chatHistory[1]["role"] == "assistant"
    assert chatHistory[1]["content"] == "Assistant Message"
    assert chatHistory[1]["previous_response_id"] is None


def test_get_chat_history_nonexistent(override_deps):
    conversation_table = MagicMock()
    # ownership check returns no data
    conversation_table.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = None  # noqa: E501
    override_deps.table.side_effect = lambda name: conversation_table

    resp = client.get("/api/v1/chatbot/chat_history/fakeCall")
    assert resp.status_code == 404
