import os
import pytest
from app.core.config import settings

# Set test environment variables
os.environ["TESTING"] = "True"

# Override any settings for testing if needed
# For example, you might want to use a test database
# settings.DATABASE_URL = "your_test_database_url"

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