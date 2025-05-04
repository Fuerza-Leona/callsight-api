import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import app
from app.db.session import get_supabase
from app.api.routes.auth import check_admin_role

# Create test client
client = TestClient(app)

# Mock Supabase client
@pytest.fixture
def mock_supabase():
    mock_client = MagicMock()
    return mock_client

# Override dependencies for testing
@pytest.fixture(autouse=True)
def override_dependencies(mock_supabase):
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    app.dependency_overrides[check_admin_role] = lambda: True
    yield
    app.dependency_overrides = {}

"""def test_companies_no_access():
    app.dependency_overrides[get_supabase] = lambda: True
    app.dependency_overrides[check_admin_role] = lambda: False
    response = client.get("/api/v1/companies/")
    assert response.status_code == 403
    app.dependency_overrides = {}"""
    


def test_companies(mock_supabase):
    mock_data = [{"company_id": "test-company-id", "name": "Test Company", "logo": "test_logo.png", "category_id": "test_category"}]
    mock_supabase.table("company_client").select("*").execute.return_value.data = mock_data
    response = client.get("/api/v1/companies/")
    
    assert response.status_code == 200
    assert "companies" in response.json()
    assert len(response.json()["companies"]) == 1
    assert response.json()["companies"][0] == {"company_id": "test-company-id", "name": "Test Company", "logo": "test_logo.png", "category_id": "test_category"}

def test_companies_supabase_error(mock_supabase):
    mock_supabase.table("company_client").select("*").execute.side_effect = Exception("Supabase error")
    response = client.get("/api/v1/companies/")
    
    assert response.status_code == 500
    assert response.json() == {"detail": "Supabase error"}


def test_company_size(mock_supabase):
    mock_data = [
        {
            "name": "Test Company",
            "users": [{"count": 5}],
        }
    ]
    mock_supabase.table("company_client").select("*, users(count)").execute.return_value.data = mock_data
    response = client.get("/api/v1/companies/companySize")
    
    assert response.status_code == 200
    assert len(response.json()["info"]) == 1
    assert response.json()["info"][0] == {"name": "Test Company", "size": 5}

def test_company_size_supabase_error(mock_supabase):
    mock_supabase.table("company_client").select("*, users(count)").execute.side_effect = Exception("Supabase error")
    response = client.get("/api/v1/companies/companySize")
    
    assert response.status_code == 500
    assert response.json() == {"detail": "Supabase error"}