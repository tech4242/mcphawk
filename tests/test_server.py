import pytest
from fastapi.testclient import TestClient
from mcp_shark.web.server import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_logs_endpoint(client):
    """
    Ensure /logs returns a valid JSON list.
    """
    response = client.get("/logs?limit=1")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
