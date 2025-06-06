import pytest
from datetime import datetime

from app.services.report_service import create_monthly_report


# Sample data for testing reports
@pytest.fixture
def sample_report_data():
    return {
        "company_name": "Test Company",
        "start_date": datetime(2025, 4, 1),
        "end_date": datetime(2025, 4, 30),
        "summary_data": {
            "total_calls": 120,
            "avg_duration": 8.5,
            "avg_satisfaction": 0.87,
        },
        "topics_data": [
            {"topic": "technical support", "count": 35},
            {"topic": "billing", "count": 28},
            {"topic": "product information", "count": 21},
            {"topic": "complaints", "count": 15},
            {"topic": "account issues", "count": 10},
        ],
        "categories_data": [
            {"name": "Support", "count": 65},
            {"name": "Sales", "count": 30},
            {"name": "Billing", "count": 25},
        ],
        "ratings_data": [
            {"rating": 5, "count": 45},
            {"rating": 4, "count": 35},
            {"rating": 3, "count": 20},
            {"rating": 2, "count": 12},
            {"rating": 1, "count": 8},
        ],
        "emotions_data": {
            "positive": 0.65,
            "neutral": 0.25,
            "negative": 0.10,
        },
    }


# Test create_monthly_report function
def test_create_monthly_report(sample_report_data):
    """Test that PDF report generation works without errors and returns bytes"""
    # Extract all the arguments from the fixture
    company_name = sample_report_data["company_name"]
    start_date = sample_report_data["start_date"]
    end_date = sample_report_data["end_date"]
    summary_data = sample_report_data["summary_data"]
    topics_data = sample_report_data["topics_data"]
    categories_data = sample_report_data["categories_data"]
    ratings_data = sample_report_data["ratings_data"]
    emotions_data = sample_report_data["emotions_data"]

    # Call the function
    pdf_data = create_monthly_report(
        company_name,
        start_date,
        end_date,
        summary_data,
        topics_data,
        categories_data,
        ratings_data,
        emotions_data,
    )

    # Verify it returned bytes
    assert isinstance(pdf_data, bytes)
    assert len(pdf_data) > 0

    # Basic check for PDF format (should start with %PDF)
    assert pdf_data.startswith(b"%PDF")


# Test create_monthly_report with minimal data
def test_create_monthly_report_minimal():
    """Test that PDF generation works with minimal data"""
    # Minimal test data
    company_name = "Test Company"
    start_date = datetime(2025, 4, 1)
    end_date = datetime(2025, 4, 30)
    summary_data = {"total_calls": 0, "avg_duration": 0, "avg_satisfaction": 0}
    topics_data = []
    categories_data = []
    ratings_data = []
    emotions_data = {"positive": 0, "neutral": 0, "negative": 0}

    # Call the function
    pdf_data = create_monthly_report(
        company_name,
        start_date,
        end_date,
        summary_data,
        topics_data,
        categories_data,
        ratings_data,
        emotions_data,
    )

    # Verify basic output
    assert isinstance(pdf_data, bytes)
    assert len(pdf_data) > 0


"""
# Test save_report_to_storage
@patch("app.services.report_service.check_report_exists", return_value=False)
@pytest.mark.asyncio
async def test_save_report_to_storage(mock_check):
    # Mock Supabase client
    mock_supabase = MagicMock()

    # Mock storage and table functions
    storage_mock = MagicMock()
    storage_mock.upload.return_value = None
    storage_mock.get_public_url.return_value = "https://example.com/test-report.pdf"
    mock_supabase.storage.from_.return_value = storage_mock

    table_mock = MagicMock()
    table_mock.insert.return_value.execute.return_value.data = [
        {"report_id": "test-report-id"}
    ]
    mock_supabase.table.return_value = table_mock

    # Test data
    pdf_data = b"%PDF-1.4 test pdf content"
    company_name = "Test Company"
    start_date = datetime(2025, 4, 1)
    user_id = "test-user-id"

    # Call the function
    result = await save_report_to_storage(
        mock_supabase, pdf_data, company_name, start_date, user_id
    )

    # Verify the result
    assert isinstance(result, dict)
    assert "report_id" in result
    assert "file_url" in result
    assert "report_name" in result
    assert "created_at" in result

    # Verify Supabase calls
    mock_supabase.storage.from_.assert_called_with("reports")
    storage_mock.upload.assert_called_once()
    storage_mock.get_public_url.assert_called_once()
    mock_supabase.table.assert_called_once_with("reports")
    table_mock.insert.assert_called_once()


# Test report storage with error
@patch("app.services.report_service.check_report_exists", return_value=False)
@pytest.mark.asyncio
async def test_save_report_storage_error(mock_check):
    # Mock Supabase with an error on upload
    mock_supabase = MagicMock()

    storage_mock = MagicMock()
    storage_mock.upload.side_effect = Exception("Storage upload failed")
    mock_supabase.storage.from_.return_value = storage_mock

    # Test data
    pdf_data = b"%PDF-1.4 test pdf content"
    company_name = "Test Company"
    start_date = datetime(2025, 4, 1)
    user_id = "test-user-id"

    # Call the function and expect exception
    with pytest.raises(Exception) as excinfo:
        await save_report_to_storage(
            mock_supabase, pdf_data, company_name, start_date, user_id
        )

    # Verify the error message
    assert "Failed to upload report to storage" in str(excinfo.value)
"""
