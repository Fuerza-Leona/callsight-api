import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
from app.main import app
from app.db.session import get_supabase
from app.api.deps import get_current_user
from types import SimpleNamespace

client = TestClient(app)

@pytest.fixture
def mock_supabase():
    mock_supabase = MagicMock()
    mock_company_response = MagicMock()
    mock_company_response.data = [{"company_id": "5c9d62d2-df16-45b7-ae4a-4b4aaa0c5ae8"}]
    
    print("Mock company response: ", mock_company_response.data)

    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
        mock_company_response,  
        MagicMock(data=[  
            {"ticket_id": "c7732206-54ac-4d75-b886-9c013802125e", "subject": "Hector prueba 26/04/2025", "company_id": "5c9d62d2-df16-45b7-ae4a-4b4aaa0c5ae8"},
            {"ticket_id": "fdc41d83-c48e-450b-a775-38df36a97c40", "subject": "Nuevos cambios", "company_id": "5c9d62d2-df16-45b7-ae4a-4b4aaa0c5ae8"},
            {"ticket_id": "22768581-c415-40ac-a50f-9d3a7268bf71", "subject": "Falla en app principal", "company_id": "5c9d62d2-df16-45b7-ae4a-4b4aaa0c5ae8"}
        ])
    ]
    
    return mock_supabase

@pytest.fixture(autouse=True)
def override_supabase(mock_supabase):
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    yield
    app.dependency_overrides = {}


# 1. Un agente puede crear tickets para una empresa
def test_agent_can_create_ticket(mock_supabase):
    mock_user = SimpleNamespace(
        role="agent",
        id="agent-007",
        company_id="agent-company-id"  # Added company_id just in case
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user

    company_id = "empresa-456"
    ticket_data = {
        "subject": "Nuevo error",
        "description": "Se cayó el servidor",
        "status": "open"
    }

    mock_insert_response = MagicMock()
    mock_insert_response.data = [
        {
            "ticket_id": "nuevo-ticket-123",
            "subject": "Nuevo error",
            "description": "Se cayó el servidor",
            "status": "open",
            "company_id": company_id,
            "created_by": mock_user.id
        }
    ]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_insert_response

    response = client.post(f"/api/v1/tickets/companies/{company_id}/tickets", json=ticket_data)
    print(response.status_code)
    try:
        print(response.json())
    except Exception as e:
        print("No se pudo decodificar JSON:", e)
        print("Texto plano:", response.text)
        
    assert response.status_code == 201
    assert response.json()["success"] is True


# 2. Un administrador puede crear un ticket para una empresa
def test_admin_can_create_ticket(mock_supabase):
    mock_user = SimpleNamespace(
        role="admin",
        id="admin-123",
        company_id="admin-company-id"
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user

    company_id = "empresa-cliente-789"
    ticket_data = {
        "subject": "Error crítico",
        "description": "Problema en sistema de producción",
        "status": "open"
    }

    mock_insert_response = MagicMock()
    mock_insert_response.data = [
        {
            "ticket_id": "ticket-admin-123",
            "subject": "Error crítico",
            "description": "Problema en sistema de producción",
            "status": "open",
            "company_id": company_id,
            "created_by": mock_user.id
        }
    ]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_insert_response

    response = client.post(f"/api/v1/tickets/companies/{company_id}/tickets", json=ticket_data)
    print(response.status_code)
    try:
        print(response.json())
    except Exception as e:
        print("No se pudo decodificar JSON:", e)
        print("Texto plano:", response.text)
        
    assert response.status_code == 201
    assert response.json()["success"] is True
    assert "ticket_id" in response.json()

# 3. Un cliente puede crear un ticket para su propia empresa
def test_client_can_create_ticket(mock_supabase):
    client_company_id = "empresa-cliente-123"
    mock_user = SimpleNamespace(
        role="client",
        id="client-456",
        company_id=client_company_id
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user

    ticket_data = {
        "subject": "Falla en la aplicación",
        "description": "No puedo iniciar sesión en el sistema",
        "status": "open"
    }

    mock_insert_response = MagicMock()
    mock_insert_response.data = [
        {
            "ticket_id": "ticket-cliente-789",
            "subject": "Falla en la aplicación",
            "description": "No puedo iniciar sesión en el sistema",
            "status": "open",
            "company_id": client_company_id,
            "created_by": mock_user.id
        }
    ]
    mock_supabase.table.return_value.insert.return_value.execute.return_value = mock_insert_response

    # El cliente solo puede crear tickets para su propia empresa
    response = client.post(f"/api/v1/tickets/companies/{client_company_id}/tickets", json=ticket_data)
    print(response.status_code)
    try:
        print(response.json())
    except Exception as e:
        print("No se pudo decodificar JSON:", e)
        print("Texto plano:", response.text)
        
    assert response.status_code == 201
    assert response.json()["success"] is True
    assert "ticket_id" in response.json()

# 4. Error al intentar crear un ticket sin información requerida
def test_create_ticket_missing_information(mock_supabase):
    mock_user = SimpleNamespace(
        role="agent",
        id="agent-123",
        company_id="agent-company-id"
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user

    company_id = "empresa-456"
    
    # Faltan campos requeridos (subject)
    incomplete_ticket_data = {
        "description": "Descripción sin asunto",
        "status": "open"
    }

    response = client.post(f"/api/v1/tickets/companies/{company_id}/tickets", json=incomplete_ticket_data)
    print(response.status_code)
    try:
        print(response.json())
    except Exception as e:
        print("No se pudo decodificar JSON:", e)
        print("Texto plano:", response.text)
        
    assert response.status_code in [400, 422]  

# 5. Cliente intentando crear ticket para otra empresa (debe fallar)
def test_client_cannot_create_ticket_for_other_company(mock_supabase):
    client_company_id = "empresa-cliente-123"
    other_company_id = "empresa-ajena-456"
    
    mock_user = SimpleNamespace(
        role="client",
        id="client-789",
        company_id=client_company_id
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user

    ticket_data = {
        "subject": "Ticket para otra empresa",
        "description": "Esto no debería ser permitido",
        "status": "open"
    }

    response = client.post(f"/api/v1/tickets/companies/{other_company_id}/tickets", json=ticket_data)
    print(response.status_code)
    try:
        print(response.json())
    except Exception as e:
        print("No se pudo decodificar JSON:", e)
        print("Texto plano:", response.text)
        
    assert response.status_code == 403  # Acceso prohibido

