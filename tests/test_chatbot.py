import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from uuid import UUID
from datetime import datetime

from app.api.routes.chatbot import (
    create_messages_for_supabase,
    needs_context,
    post_chat,
    continue_chat,
    get_all_chats,
    get_chat_history,
    ChatRequest,
)


def test_create_messages_for_supabase():
    """Helper function needed for database operations"""

    conversation_id = "test-conversation-id"
    prompt = "Hello"
    response_id = "test-response-id"
    response_output_text = "Hello there!"
    response_created_at = datetime.now().timestamp()

    user_message, chatbot_message = create_messages_for_supabase(
        conversation_id, prompt, response_id, response_output_text, response_created_at
    )

    # Assert
    assert user_message["chatbot_conversation_id"] == conversation_id
    assert user_message["role"] == "user"
    assert user_message["content"] == prompt
    assert UUID(user_message["chatbot_message_id"]) is not None

    assert chatbot_message["chatbot_conversation_id"] == conversation_id
    assert chatbot_message["role"] == "assistant"
    assert chatbot_message["content"] == response_output_text
    assert chatbot_message["chatbot_message_id"] == response_id


class TestChatEndpoints:
    """Test the chat endpoints"""

    @pytest.mark.asyncio
    @patch("app.api.routes.chatbot.client")
    @patch("app.api.routes.chatbot.needs_context", return_value=False)
    @patch("app.api.routes.chatbot.uuid4")
    async def test_post_chat_new_conversation(
        self, mock_uuid4, mock_needs_context, mock_client
    ):
        """Test T01-HU022 - Creating a new chat"""

        conversation_id = "test-conv-id"
        response_id = "test-response-id"
        mock_uuid4.return_value = conversation_id

        request = ChatRequest(prompt="Hola")
        current_user = MagicMock()
        current_user.id = "user-123"

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value = None

        # Create response mocks
        mock_response = MagicMock()
        mock_response.id = response_id
        mock_response.output_text = "Hola, ¿cómo puedo ayudarte?"
        mock_response.created_at = datetime.now().timestamp()

        mock_title_response = MagicMock()
        mock_title_response.output_text = "Nueva conversación"

        # Configure the mock client to return different responses for each call
        mock_create = MagicMock()
        mock_create.side_effect = [mock_response, mock_title_response]
        mock_client.responses.create = mock_create

        result = await post_chat(request, current_user, mock_supabase)

        # Assert
        assert result["response"] == mock_response.output_text
        assert result["title"] == mock_title_response.output_text
        assert result["conversation_id"] == conversation_id

        # Verify the calls to insert data into supabase
        assert mock_supabase.table.call_count == 3
        mock_supabase.table.assert_any_call("chatbot_conversations")
        mock_supabase.table.assert_any_call("chatbot_messages")

    @pytest.mark.asyncio
    async def test_post_chat_error_handling(self):
        """Test T02-HU022 - Error handling in chat creation"""

        request = ChatRequest(prompt="Hola")
        current_user = MagicMock()

        # Simulate database error
        mock_supabase = MagicMock()
        mock_supabase.table.side_effect = Exception("Connection error")

        # Assert
        with pytest.raises(HTTPException) as excinfo:
            await post_chat(request, current_user, mock_supabase)

        assert excinfo.value.status_code == 500
        assert "Connection error" in str(excinfo.value.detail)

    @pytest.mark.asyncio
    @patch("app.api.routes.chatbot.client")
    @patch("app.api.routes.chatbot.needs_context", return_value=False)
    async def test_continue_chat(self, mock_needs_context, mock_client):
        """Test T03-HU024 - Continuing an existing chat with a new message"""

        conversation_id = "existing-conversation"
        request = ChatRequest(prompt="¿Seguro?")
        current_user = MagicMock()
        current_user.id = "user-123"

        mock_supabase = MagicMock()
        # Mock the response for getting the previous response id
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"last_response_id": "prev-response-id"}
        ]

        mock_response = MagicMock()
        mock_response.id = "new-response-id"
        mock_response.output_text = "Sí, estoy seguro."
        mock_response.created_at = datetime.now().timestamp()

        # Configure the mock client properly
        mock_create = MagicMock()
        mock_create.return_value = mock_response
        mock_client.responses.create = mock_create

        result = await continue_chat(
            request, conversation_id, current_user, mock_supabase
        )

        # Assert
        assert result["response"] == "Sí, estoy seguro."
        # Verify the calls to update and insert data into supabase
        mock_supabase.table.assert_any_call("chatbot_conversations")
        mock_supabase.table.assert_any_call("chatbot_messages")

    @pytest.mark.asyncio
    async def test_continue_chat_error_handling(self):
        """Test T04-HU024 - Error handling in continuing chat"""

        conversation_id = "existing-conversation"
        request = ChatRequest(prompt="¿Seguro?")
        current_user = MagicMock()

        # Simulate database error
        mock_supabase = MagicMock()
        mock_supabase.table.side_effect = Exception("Connection error")

        # Assert
        with pytest.raises(HTTPException) as excinfo:
            await continue_chat(request, conversation_id, current_user, mock_supabase)

        assert excinfo.value.status_code == 500
        assert "Connection error" in str(excinfo.value.detail)

    @pytest.mark.asyncio
    @patch("app.api.routes.chatbot.client")
    async def test_needs_context_contextual_query(self, mock_client):
        """Test T01-HU036 - Detection when context is needed"""

        # Mock response where context is needed
        mock_judgment = MagicMock()
        mock_judgment.output_text = "needs context"
        mock_client.responses.create.return_value = mock_judgment

        # Test with a contextual question
        result = needs_context("¿Ya resolvieron lo de Mikey?")

        # Assert context was needed
        assert result is True

    @pytest.mark.asyncio
    @patch("app.api.routes.chatbot.client")
    async def test_needs_context_general_query(self, mock_client):
        """Test T02-HU036 - Detection when context is not needed"""

        # Mock response where no context is needed
        mock_judgment = MagicMock()
        mock_judgment.output_text = "no context"
        mock_client.responses.create.return_value = mock_judgment

        # Test with a general question
        result = needs_context("¿Quién es el CEO de Google?")

        # Assert context was not needed
        assert result is False

    @pytest.mark.asyncio
    @patch("app.api.routes.chatbot.client")
    async def test_needs_context_with_previous_conversation(self, mock_client):
        """Test T03-HU036 - Detection with previous conversation context"""

        # Mock response where no context is needed
        mock_judgment = MagicMock()
        mock_judgment.output_text = "no context"
        mock_client.responses.create.return_value = mock_judgment

        # Test with a follow-up question and previous response id
        result = needs_context("¿Y cuál es su opinión sobre eso?", "prev-response-id")

        assert result is False

    @pytest.mark.asyncio
    @patch("app.api.routes.chatbot.client")
    @patch("app.api.routes.chatbot.chat_with_context")
    @patch("app.api.routes.chatbot.needs_context", return_value=True)
    @patch("app.api.routes.chatbot.uuid4")
    async def test_post_chat_with_insufficient_context(
        self, mock_uuid4, mock_needs_context, mock_chat_with_context, mock_client
    ):
        """Test T01-HU035 - Chatbot gives general response when insufficient context"""

        # Setup
        conversation_id = "test-conv-id"
        response_id = "test-response-id"
        mock_uuid4.return_value = conversation_id

        request = ChatRequest(prompt="¿Qué pasó con el proyecto pasado?")
        current_user = MagicMock()
        current_user.id = "user-123"

        # Mock chat_with_context to return message with introduction about insufficient match
        mock_chat_with_context.return_value = "The following are pieces of a transcript... [No relevant matches found]... Question: ¿Qué pasó con el proyecto Alpha?"

        # Mock client response
        mock_response = MagicMock()
        mock_response.id = response_id
        mock_response.output_text = "No tengo más información específica sobre ese tema. ¿Hay alguna otra cosa en la que pueda ayudarte?"
        mock_response.created_at = datetime.now().timestamp()

        mock_title_response = MagicMock()
        mock_title_response.output_text = "Consulta sobre proyecto pasado"

        mock_create = MagicMock()
        mock_create.side_effect = [mock_response, mock_title_response]
        mock_client.responses.create = mock_create

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value = None

        # Execute
        result = await post_chat(request, current_user, mock_supabase)

        # Assert that API was called with the right content
        mock_chat_with_context.assert_called_once()
        mock_client.responses.create.assert_called()
        assert result["response"] == mock_response.output_text

    @pytest.mark.asyncio
    @patch("app.api.routes.chatbot.chat_with_context")
    @patch("app.api.routes.chatbot.client")
    @patch("app.api.routes.chatbot.needs_context", return_value=True)
    async def test_continue_chat_with_insufficient_context(
        self, mock_needs_context, mock_client, mock_chat_with_context
    ):
        """Test T02-HU035 - Continuing chat with insufficient context"""

        # Setup
        conversation_id = "existing-conversation"
        request = ChatRequest(prompt="¿Y qué más me cuentas sobre ese tema?")
        current_user = MagicMock()
        current_user.id = "user-123"

        # Mock database responses
        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"last_response_id": "prev-response-id"}
        ]

        # Mock chat_with_context to return message indicating no relevant matches
        mock_chat_with_context.return_value = "The following are pieces of a transcript... [No relevant matches found]... Question: ¿Y qué más me cuentas sobre ese tema?"

        # Mock client response
        mock_response = MagicMock()
        mock_response.id = "new-response-id"
        mock_response.output_text = "No tengo más información específica sobre ese tema. ¿Hay alguna otra cosa en la que pueda ayudarte?"
        mock_response.created_at = datetime.now().timestamp()
        mock_client.responses.create.return_value = mock_response

        # Execute
        result = await continue_chat(
            request, conversation_id, current_user, mock_supabase
        )

        # Assert that the system was triggered to look for context but used general knowledge
        mock_needs_context.assert_called_once()
        mock_chat_with_context.assert_called_once()
        assert result["response"] == mock_response.output_text

    @pytest.mark.asyncio
    @patch("app.api.routes.chatbot.client")
    @patch("app.api.routes.chatbot.chat_with_context")
    @patch("app.api.routes.chatbot.needs_context", return_value=True)
    @patch("app.api.routes.chatbot.uuid4")
    async def test_post_chat_with_company_context(
        self, mock_uuid4, mock_needs_context, mock_chat_with_context, mock_client
    ):
        """Test T01-HU034 - Starting conversation with company context"""

        # Setup
        conversation_id = "test-conv-id"
        response_id = "test-response-id"
        mock_uuid4.return_value = conversation_id

        request = ChatRequest(prompt="Necesito información de los acuerdos de servicio")
        current_user = MagicMock()
        current_user.id = "user-123"

        # Mock chat_with_context to return message with company context
        company_context = """The following are pieces of a transcript or from multiple transcripts from calls between a call center and a client company.
Transcript chunk:
\"\"\"
Cliente: NEORIS
Acuerdo: Los SLAs establecen tiempos de respuesta máximos de 4 horas para incidentes críticos
\"\"\"
Transcript chunk:
\"\"\"
El contrato con NEORIS incluye soporte 24/7 para servicios críticos y 8x5 para servicios estándar
\"\"\"
Question: Necesito información de los acuerdos de servicio"""

        mock_chat_with_context.return_value = company_context

        # Mock client response
        mock_response = MagicMock()
        mock_response.id = response_id
        mock_response.output_text = "Como se mencionó durante una llamada previa, los acuerdos de servicio con NEORIS establecen tiempos de respuesta máximos de 4 horas para incidentes críticos. Además, el contrato incluye soporte 24/7 para servicios críticos y 8x5 (horario laboral) para servicios estándar."
        mock_response.created_at = datetime.now().timestamp()

        mock_title_response = MagicMock()
        mock_title_response.output_text = "Información sobre Neoris"

        mock_create = MagicMock()
        mock_create.side_effect = [mock_response, mock_title_response]
        mock_client.responses.create = mock_create

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute.return_value = None

        # Execute
        result = await post_chat(request, current_user, mock_supabase)

        # Assert embeddings were used and the response includes context
        mock_chat_with_context.assert_called_once_with(
            current_user=current_user,
            supabase=mock_supabase,
            query=request.prompt,
            token_budget=4096 - 500,
        )
        assert (
            "como se mencionó durante una llamada previa" in result["response"].lower()
        )
        assert "neoris" in result["response"].lower()


class TestHistoryEndpoints:
    """Test the chat history endpoints"""

    @pytest.mark.asyncio
    async def test_get_all_chats_success(self):
        """Test T01-HU023 - Getting all chats for a user"""

        current_user = MagicMock()
        current_user.id = "user-123"

        mock_supabase = MagicMock()
        # Mock successful response with chat data
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"chatbot_conversation_id": "conv1", "title": "First conversation"},
            {"chatbot_conversation_id": "conv2", "title": "Second conversation"},
        ]

        result = await get_all_chats(current_user, mock_supabase)

        # Assert
        assert len(result) == 2
        assert result[0]["chatbot_conversation_id"] == "conv1"
        assert result[0]["title"] == "First conversation"
        assert result[1]["chatbot_conversation_id"] == "conv2"
        mock_supabase.table.assert_called_once_with("chatbot_conversations")

    @pytest.mark.asyncio
    async def test_get_all_chats_empty(self):
        """Test T02-HU023 - Getting all chats when user has no chats"""

        current_user = MagicMock()
        current_user.id = "user-123"

        mock_supabase = MagicMock()
        # Mock empty response (no conversations)
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

        # Assert
        with pytest.raises(HTTPException) as excinfo:
            await get_all_chats(current_user, mock_supabase)

        assert excinfo.value.status_code == 404
        assert "There are no conversations saved" in str(excinfo.value.detail)

    @pytest.mark.asyncio
    async def test_get_all_chats_error(self):
        """Test T03-HU023 - Error handling when getting all chats"""

        current_user = MagicMock()
        current_user.id = "user-123"

        # Simulate database error
        mock_supabase = MagicMock()
        mock_supabase.table.side_effect = Exception("Connection error")

        # Assert
        with pytest.raises(HTTPException) as excinfo:
            await get_all_chats(current_user, mock_supabase)

        assert excinfo.value.status_code == 500
        assert "Connection error" in str(excinfo.value.detail)

    @pytest.mark.asyncio
    async def test_get_chat_history_success(self):
        """Test T01-HU024 - Getting chat history for a specific conversation"""

        conversation_id = "existing-conversation"
        current_user = MagicMock()
        current_user.id = "user-123"

        mock_supabase = MagicMock()
        # Mock successful validation of chat ownership
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "chatbot_conversation_id": conversation_id
        }

        # Mock successful response with chat messages
        chat_history_response = MagicMock()
        chat_history_response.data = [
            {
                "role": "user",
                "created_at": "2023-01-01T12:00:00",
                "content": "Hola",
                "previous_response_id": None,
            },
            {
                "role": "assistant",
                "created_at": "2023-01-01T12:00:01",
                "content": "Hola, ¿cómo puedo ayudarte?",
                "previous_response_id": None,
            },
        ]
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = chat_history_response

        result = await get_chat_history(conversation_id, current_user, mock_supabase)

        # Assert
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hola"
        assert result[1]["role"] == "assistant"
        mock_supabase.table.assert_any_call("chatbot_conversations")
        mock_supabase.table.assert_any_call("chatbot_messages")

    @pytest.mark.asyncio
    async def test_get_chat_history_message_order(self):
        """Test T02-HU024 - Verify chronological order of messages"""

        conversation_id = "existing-conversation"
        current_user = MagicMock()
        current_user.id = "user-123"

        mock_supabase = MagicMock()
        # Mock successful validation of chat ownership
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "chatbot_conversation_id": conversation_id
        }

        # Mock successful response with chat messages in chronological order
        chat_history_response = MagicMock()
        chat_history_response.data = [
            {
                "role": "user",
                "created_at": "2023-01-01T12:00:00",
                "content": "Hola",
                "previous_response_id": None,
            },
            {
                "role": "assistant",
                "created_at": "2023-01-01T12:00:01",
                "content": "Hola, ¿cómo puedo ayudarte?",
                "previous_response_id": None,
            },
            {
                "role": "user",
                "created_at": "2023-01-01T12:01:00",
                "content": "¿Puedes ayudarme con algo?",
                "previous_response_id": "msg1",
            },
            {
                "role": "assistant",
                "created_at": "2023-01-01T12:01:02",
                "content": "Claro, dime en qué puedo ayudarte",
                "previous_response_id": "msg2",
            },
        ]
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = chat_history_response

        result = await get_chat_history(conversation_id, current_user, mock_supabase)

        # Assert
        assert len(result) == 4
        # Verify the messages are in chronological order
        assert result[0]["created_at"] == "2023-01-01T12:00:00"
        assert result[1]["created_at"] == "2023-01-01T12:00:01"
        assert result[2]["created_at"] == "2023-01-01T12:01:00"
        assert result[3]["created_at"] == "2023-01-01T12:01:02"
        # Verify the order function was called in supabase
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.assert_called_once()
