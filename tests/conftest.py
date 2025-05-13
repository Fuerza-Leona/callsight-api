import os
import pytest
import pytest_asyncio
from dotenv import load_dotenv

# Set test environment variables
os.environ["TESTING"] = "True"




@pytest.fixture(autouse=True)
def test_env(monkeypatch):
    load_dotenv(dotenv_path=".env", override=True)

    monkeypatch.setenv("TESTING", "True")

    # Pull from actual environment to avoid hardcoding
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "")

    monkeypatch.setenv("SUPABASE_URL", supabase_url)
    monkeypatch.setenv("SUPABASE_KEY", supabase_key)


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
