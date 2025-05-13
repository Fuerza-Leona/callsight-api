import os
import pytest
import pytest_asyncio

# Set test environment variables
os.environ["TESTING"] = "True"
os.environ["SUPABASE_URL"] = "https://qkbitpdsagffscsttvxt.supabase.co"
os.environ["SUPABASE_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFrYml0cGRzYWdmZnNjc3R0dnh0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDEwMTU4NDgsImV4cCI6MjA1NjU5MTg0OH0.8ZMedGXwP6lpgFCXVaJUWvdilx_EPm03GXvh6CDFMPM"

# Override any settings for testing if needed
# For example, you might want to use a test database
# settings.DATABASE_URL = "your_test_database_url"

# Configure pytest-asyncio
pytest_asyncio.config_mode = "strict"


def pytest_configure(config):
    config.option.asyncio_mode = "strict"
    config.option.asyncio_default_fixture_loop_scope = "function"


@pytest.fixture
def test_app():
    """
    Create a fresh test application for each test.
    This can be used instead of the global client if needed for isolation.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        yield client
