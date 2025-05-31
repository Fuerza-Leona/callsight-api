import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta

from app.services.report_service import create_monthly_report, save_report_to_storage


# Integration test for monthly report generation
@pytest.mark.asyncio
async def test_report_generation_integration():
    """
    Integration test for report generation flow.
    This test simulates the entire report generation process without making actual API calls.
    """
    # Sample data
    company_name = "Integration Test Company"
    start_date = datetime.now().replace(day=1) - timedelta(days=30)  # Previous month
    end_date = datetime.now().replace(day=1) - timedelta(
        days=1
    )  # Last day of previous month

    summary_data = {
        "total_calls": 235,
        "avg_duration": 6.8,
        "avg_satisfaction": 0.79,
    }

    topics_data = [
        {"topic": "technical issues", "count": 78},
        {"topic": "billing inquiries", "count": 55},
        {"topic": "account changes", "count": 40},
        {"topic": "product questions", "count": 38},
        {"topic": "general support", "count": 24},
    ]

    categories_data = [
        {"name": "Tech Support", "count": 110},
        {"name": "Customer Service", "count": 75},
        {"name": "Billing Department", "count": 50},
    ]

    ratings_data = [
        {"rating": 5, "count": 95},
        {"rating": 4, "count": 70},
        {"rating": 3, "count": 40},
        {"rating": 2, "count": 20},
        {"rating": 1, "count": 10},
    ]

    emotions_data = {
        "positive": 0.62,
        "neutral": 0.28,
        "negative": 0.10,
    }

    # Step 1: Create the PDF report
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

    # Verify PDF was created
    assert isinstance(pdf_data, bytes)
    assert len(pdf_data) > 0
    assert pdf_data.startswith(b"%PDF")

    # Step 2: Simulate saving the report to storage
    # Create a mock Supabase client
    mock_supabase = MagicMock()

    # Mock storage functionality
    storage_mock = MagicMock()
    storage_mock.upload.return_value = None
    storage_mock.get_public_url.return_value = (
        "https://example.com/test-integration-report.pdf"
    )
    mock_supabase.storage.from_.return_value = storage_mock

    # Mock database insertion
    table_mock = MagicMock()
    table_mock.insert.return_value.execute.return_value.data = [
        {"report_id": "test-integration-id"}
    ]
    mock_supabase.table.return_value = table_mock

    # Mock user ID
    user_id = "integration-test-user"

    # Call save_report_to_storage
    result = await save_report_to_storage(
        mock_supabase, pdf_data, company_name, start_date, end_date, user_id
    )

    # Verify the result
    assert "report_id" in result
    assert "file_url" in result
    assert "report_name" in result
    assert "created_at" in result

    # Verify the file URL is as expected
    assert result["file_url"] == "https://example.com/test-integration-report.pdf"

    # Verify uploads were called with the correct data types
    mock_supabase.storage.from_.assert_called_with("reports")
    args, kwargs = storage_mock.upload.call_args
    assert "file_options" in kwargs
    assert kwargs["file_options"]["content-type"] == "application/pdf"

    # Step 3: Simulate response handling
    assert "report_id" in result
    assert company_name in result["report_name"]
