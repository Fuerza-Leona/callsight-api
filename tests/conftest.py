import os
import pytest
import pytest_asyncio

# Set test environment variables
os.environ["TESTING"] = "True"
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_KEY"] = ""


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
