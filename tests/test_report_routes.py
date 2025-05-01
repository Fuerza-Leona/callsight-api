import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

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

    # Mock RPC functions
    rpc_mock = MagicMock()

    # For summary data
    summary_response = MagicMock()
    summary_response.data = [
        {"total_calls": 150, "avg_duration": 7.5, "avg_satisfaction": 0.85}
    ]

    # For topics data
    topics_response = MagicMock()
    topics_response.data = [
        {"topic": "technical support", "count": 42},
        {"topic": "billing", "count": 31},
        {"topic": "product info", "count": 24},
    ]

    # For categories data
    categories_response = MagicMock()
    categories_response.data = [
        {"name": "Support", "count": 70},
        {"name": "Sales", "count": 45},
        {"name": "Billing", "count": 35},
    ]

    # For ratings data
    ratings_response = MagicMock()
    ratings_response.data = [
        {"rating": 5, "count": 50},
        {"rating": 4, "count": 40},
        {"rating": 3, "count": 30},
        {"rating": 2, "count": 20},
        {"rating": 1, "count": 10},
    ]

    # For emotions data
    emotions_response = MagicMock()
    emotions_response.data = [{"positive": 0.7, "negative": 0.1, "neutral": 0.2}]

    # Set up different responses based on function name
    def rpc_side_effect(function_name, *args, **kwargs):
        if function_name == "build_conversations_summary":
            return summary_response
        elif function_name == "build_topics_query":
            return topics_response
        elif function_name == "build_conversations_categories_query":
            return categories_response
        elif function_name == "build_conversations_ratings_query":
            return ratings_response
        elif function_name == "build_client_emotions_query":
            return emotions_response
        else:
            mock_response = MagicMock()
            mock_response.data = []
            return mock_response

    rpc_mock.execute.side_effect = lambda: rpc_mock.response
    mock_client.rpc.side_effect = rpc_side_effect

    # Mock company info lookup
    company_select_mock = MagicMock()
    company_select_mock.eq.return_value.execute.return_value.data = [
        {"name": "Test Company"}
    ]
    mock_client.table.return_value.select.return_value = company_select_mock

    # Mock users lookup
    users_select_mock = MagicMock()
    users_select_mock.eq.return_value.execute.return_value.data = [
        {"user_id": "user1"},
        {"user_id": "user2"},
    ]

    def table_select_side_effect(columns):
        if columns == "name":
            return company_select_mock
        elif columns == "user_id":
            return users_select_mock
        elif columns == "*":
            reports_mock = MagicMock()
            reports_mock.eq.return_value.order.return_value.range.return_value.execute.return_value.data = [
                {
                    "report_id": "test-report-1",
                    "name": "Monthly Report - Test Company - 2025-04",
                    "created_at": "2025-05-01T10:00:00",
                }
            ]
            return reports_mock
        else:
            default_mock = MagicMock()
            default_mock.eq.return_value.execute.return_value.data = []
            return default_mock

    mock_client.table.return_value.select.side_effect = table_select_side_effect

    return mock_client


# Override dependencies for testing
@pytest.fixture
def setup_dependencies(mock_current_user, mock_supabase):
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_supabase] = lambda: mock_supabase
    yield
    app.dependency_overrides = {}


# Mock the check_user_role function
@pytest.fixture
def mock_check_user_role():
    with patch("app.api.routes.reports.check_user_role", return_value="admin") as mock:
        yield mock


# Mock PDF generation and storage
@pytest.fixture
def mock_report_services():
    with (
        patch(
            "app.api.routes.reports.create_monthly_report", return_value=b"%PDF-test"
        ) as mock_create,
        patch(
            "app.api.routes.reports.save_report_to_storage", new_callable=AsyncMock
        ) as mock_save,
    ):
        mock_save.return_value = {
            "report_id": "test-report-id",
            "report_name": "Monthly Report - Test Company - 2025-04",
            "file_url": "https://example.com/test-report.pdf",
            "created_at": "2025-05-01T10:00:00",
        }
        yield mock_create, mock_save


# Test generate_monthly_report endpoint
@pytest.mark.asyncio
async def test_generate_monthly_report(
    setup_dependencies, mock_check_user_role, mock_report_services
):
    """Test generating a monthly report with specific month and year"""
    mock_create, mock_save = mock_report_services

    # Make request to the API
    response = client.post(
        "/api/v1/reports/monthly",
        json={"month": 4, "year": 2025, "company_id": "test-company-id"},
    )

    # Assert response
    assert response.status_code == 200
    assert "success" in response.json()
    assert response.json()["success"] is True
    assert "report" in response.json()
    assert "period" in response.json()
    assert response.json()["period"]["month"] == 4
    assert response.json()["period"]["year"] == 2025

    # Verify mocks were called
    assert mock_check_user_role.called
    assert mock_create.called
    assert mock_save.called


# Test generate_monthly_report with default date (previous month)
@pytest.mark.asyncio
async def test_generate_monthly_report_default_date(
    setup_dependencies, mock_check_user_role, mock_report_services
):
    """Test generating a monthly report with default date (previous month)"""
    mock_create, mock_save = mock_report_services

    # Make request to the API
    response = client.post("/api/v1/reports/monthly", json={})

    # Assert response
    assert response.status_code == 200
    assert "success" in response.json()
    assert response.json()["success"] is True
    assert "report" in response.json()
    assert "period" in response.json()

    # Verify mocks were called
    assert mock_check_user_role.called
    assert mock_create.called
    assert mock_save.called


# Test invalid month
@pytest.mark.asyncio
async def test_generate_monthly_report_invalid_month(
    setup_dependencies, mock_check_user_role
):
    """Test generating a report with an invalid month"""

    # Make request with invalid month
    response = client.post(
        "/api/v1/reports/monthly",
        json={
            "month": 13,  # Invalid month
            "year": 2025,
        },
    )

    # Assert error response
    assert response.status_code in [400, 500]
    assert "detail" in response.json()
    assert "Invalid month" in response.json()["detail"]


# Test unauthorized access
@pytest.mark.asyncio
async def test_generate_monthly_report_unauthorized(setup_dependencies):
    """Test generating a report with insufficient permissions"""

    # Mock the check_user_role function to return 'client'
    with patch("app.api.routes.reports.check_user_role", return_value="client"):
        # Make request to the API
        response = client.post(
            "/api/v1/reports/monthly", json={"month": 4, "year": 2025}
        )

    # Assert error response
    assert response.status_code in [403, 500]
    assert "detail" in response.json()
    assert "Access denied" in response.json()["detail"]


# Test list_reports endpoint
@pytest.mark.asyncio
async def test_list_reports(setup_dependencies):
    """Test listing reports for the current user"""

    # Make request to the API
    response = client.get("/api/v1/reports")

    # Assert response
    assert response.status_code == 200
    assert "reports" in response.json()
    assert (
        len(response.json()["reports"]) > 0
    )  # Should have at least one report from the mock
