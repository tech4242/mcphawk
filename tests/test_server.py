import pytest
import os
import tempfile
from fastapi.testclient import TestClient
from mcp_shark.web.server import app
from mcp_shark.logger import init_db, set_db_path

# Use a separate test database for this module
TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "test_server_mcp_shark.db")


@pytest.fixture(scope="module")
def client():
    # Set up test database
    set_db_path(TEST_DB_PATH)
    init_db()
    yield TestClient(app)
    # Cleanup
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


def test_logs_endpoint(client):
    """
    Ensure /logs returns a valid JSON list.
    """
    response = client.get("/logs?limit=1")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
