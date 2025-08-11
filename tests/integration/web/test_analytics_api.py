"""Integration tests for analytics API endpoints."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from mcphawk.logger import init_db, log_message, set_db_path
from mcphawk.web.server import app


@pytest.fixture
def test_db(tmp_path):
    """Create a test database."""
    db_path = tmp_path / "test_analytics.db"
    set_db_path(str(db_path))
    init_db()
    yield db_path


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_logs(test_db):
    """Insert sample logs into test database."""
    base_time = datetime.now(timezone.utc)

    logs = [
        # Initialize request/response pair (stdio)
        {
            "log_id": "1",
            "timestamp": base_time - timedelta(minutes=30),
            "src_ip": "client",
            "src_port": None,
            "dst_ip": "server",
            "dst_port": None,
            "direction": "outgoing",
            "message": json.dumps({
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {"capabilities": {}},
                "id": 1
            }),
            "transport_type": "stdio",
            "metadata": json.dumps({"server_name": "test-server", "server_version": "1.0"}),
            "pid": 1234
        },
        {
            "log_id": "2",
            "timestamp": base_time - timedelta(minutes=29, seconds=50),
            "src_ip": "server",
            "src_port": None,
            "dst_ip": "client",
            "dst_port": None,
            "direction": "incoming",
            "message": json.dumps({
                "jsonrpc": "2.0",
                "result": {"capabilities": {}},
                "id": 1
            }),
            "transport_type": "stdio",
            "metadata": json.dumps({"server_name": "test-server", "server_version": "1.0"}),
            "pid": 1234
        },

        # Tools list request/response (http)
        {
            "log_id": "3",
            "timestamp": base_time - timedelta(minutes=25),
            "src_ip": "127.0.0.1",
            "src_port": 50000,
            "dst_ip": "127.0.0.1",
            "dst_port": 3000,
            "direction": "outgoing",
            "message": json.dumps({
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 2
            }),
            "transport_type": "http",
            "metadata": json.dumps({"server_name": "another-server", "server_version": "2.0"}),
            "pid": None
        },
        {
            "log_id": "4",
            "timestamp": base_time - timedelta(minutes=24, seconds=55),
            "src_ip": "127.0.0.1",
            "src_port": 3000,
            "dst_ip": "127.0.0.1",
            "dst_port": 50000,
            "direction": "incoming",
            "message": json.dumps({
                "jsonrpc": "2.0",
                "result": {"tools": []},
                "id": 2
            }),
            "transport_type": "http",
            "metadata": json.dumps({"server_name": "another-server", "server_version": "2.0"}),
            "pid": None
        },

        # Notification
        {
            "log_id": "5",
            "timestamp": base_time - timedelta(minutes=20),
            "src_ip": "127.0.0.1",
            "src_port": 50000,
            "dst_ip": "127.0.0.1",
            "dst_port": 3000,
            "direction": "outgoing",
            "message": json.dumps({
                "jsonrpc": "2.0",
                "method": "notification/test",
                "params": {}
            }),
            "transport_type": "http",
            "metadata": json.dumps({"server_name": "another-server", "server_version": "2.0"}),
            "pid": None
        },

        # Error response
        {
            "log_id": "6",
            "timestamp": base_time - timedelta(minutes=15),
            "src_ip": "127.0.0.1",
            "src_port": 3000,
            "dst_ip": "127.0.0.1",
            "dst_port": 50000,
            "direction": "incoming",
            "message": json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": "Method not found"},
                "id": 3
            }),
            "transport_type": "http",
            "metadata": json.dumps({"server_name": "another-server", "server_version": "2.0"}),
            "pid": None
        },

        # More recent requests for frequency testing
        {
            "log_id": "7",
            "timestamp": base_time - timedelta(minutes=10),
            "src_ip": "client",
            "src_port": None,
            "dst_ip": "server",
            "dst_port": None,
            "direction": "outgoing",
            "message": json.dumps({
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {},
                "id": 10
            }),
            "transport_type": "stdio",
            "metadata": json.dumps({"server_name": "test-server", "server_version": "1.0"}),
            "pid": 5678
        },
        {
            "log_id": "8",
            "timestamp": base_time - timedelta(minutes=5),
            "src_ip": "client",
            "src_port": None,
            "dst_ip": "server",
            "dst_port": None,
            "direction": "outgoing",
            "message": json.dumps({
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {},
                "id": 11
            }),
            "transport_type": "stdio",
            "metadata": json.dumps({"server_name": "test-server", "server_version": "1.0"}),
            "pid": 5678
        },
    ]

    # Insert logs into database
    for log_entry in logs:
        log_message(log_entry)

    return logs


class TestTimeseriesEndpoint:
    """Tests for timeseries metrics endpoint."""

    def test_timeseries_basic(self, client, sample_logs):
        """Test basic timeseries endpoint."""
        response = client.get("/api/metrics/timeseries")
        assert response.status_code == 200

        data = response.json()
        assert "start_time" in data
        assert "end_time" in data
        assert "interval_minutes" in data
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_timeseries_with_interval(self, client, sample_logs):
        """Test timeseries with custom interval."""
        response = client.get("/api/metrics/timeseries?interval_minutes=10")
        assert response.status_code == 200

        data = response.json()
        assert data["interval_minutes"] == 10

    def test_timeseries_with_time_range(self, client, sample_logs):
        """Test timeseries with time range."""
        from urllib.parse import quote
        start_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        end_time = datetime.now(timezone.utc).isoformat()

        response = client.get(
            f"/api/metrics/timeseries?start_time={quote(start_time)}&end_time={quote(end_time)}"
        )
        assert response.status_code == 200

        data = response.json()
        assert data["start_time"] == start_time
        assert data["end_time"] == end_time

    def test_timeseries_with_filters(self, client, sample_logs):
        """Test timeseries with transport and server filters."""
        response = client.get(
            "/api/metrics/timeseries?transport_type=stdio&server_name=test-server"
        )
        assert response.status_code == 200

        data = response.json()
        assert "data" in data

        # All data should be from stdio transport
        # (actual filtering is tested in unit tests)

    def test_timeseries_invalid_interval(self, client, sample_logs):
        """Test timeseries with invalid interval."""
        response = client.get("/api/metrics/timeseries?interval_minutes=100")
        assert response.status_code == 422  # Validation error


class TestMethodsEndpoint:
    """Tests for methods frequency endpoint."""

    def test_methods_basic(self, client, sample_logs):
        """Test basic methods endpoint."""
        response = client.get("/api/metrics/methods")
        assert response.status_code == 200

        data = response.json()
        assert "methods" in data
        assert "total_unique_methods" in data
        assert isinstance(data["methods"], list)

        # Should have initialize as most frequent (3 times)
        if data["methods"]:
            assert data["methods"][0]["method"] == "initialize"
            assert data["methods"][0]["count"] == 3

    def test_methods_with_limit(self, client, sample_logs):
        """Test methods with custom limit."""
        response = client.get("/api/metrics/methods?limit=2")
        assert response.status_code == 200

        data = response.json()
        assert len(data["methods"]) <= 2

    def test_methods_with_transport_filter(self, client, sample_logs):
        """Test methods filtered by transport."""
        response = client.get("/api/metrics/methods?transport_type=http")
        assert response.status_code == 200

        data = response.json()
        # Should only have methods from HTTP transport
        methods = [m["method"] for m in data["methods"]]
        assert "initialize" not in methods or data["methods"][0]["count"] < 3


class TestTransportEndpoint:
    """Tests for transport distribution endpoint."""

    def test_transport_distribution(self, client, sample_logs):
        """Test transport distribution endpoint."""
        response = client.get("/api/metrics/transport")
        assert response.status_code == 200

        data = response.json()
        assert "distribution" in data
        assert "total" in data
        assert data["total"] == len(sample_logs)

        # Check distribution structure
        for item in data["distribution"]:
            assert "transport_type" in item
            assert "count" in item
            assert "percentage" in item

        # Should have both stdio and http
        transport_types = [d["transport_type"] for d in data["distribution"]]
        assert "stdio" in transport_types
        assert "http" in transport_types

    def test_transport_with_time_range(self, client, sample_logs):
        """Test transport distribution with time range."""
        from urllib.parse import quote
        # Only get last 10 minutes
        start_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        end_time = datetime.now(timezone.utc).isoformat()

        response = client.get(
            f"/api/metrics/transport?start_time={quote(start_time)}&end_time={quote(end_time)}"
        )
        assert response.status_code == 200

        data = response.json()
        # Should have fewer entries
        assert data["total"] < len(sample_logs)


class TestMessageTypesEndpoint:
    """Tests for message types distribution endpoint."""

    def test_message_types_basic(self, client, sample_logs):
        """Test message types endpoint."""
        response = client.get("/api/metrics/message-types")
        assert response.status_code == 200

        data = response.json()
        assert "distribution" in data
        assert "error_count" in data
        assert "total" in data

        # Should have requests, responses, notifications, and errors
        types = [d["type"] for d in data["distribution"]]
        assert "request" in types
        assert "response" in types
        assert "notification" in types
        assert data["error_count"] == 1

    def test_message_types_with_transport_filter(self, client, sample_logs):
        """Test message types filtered by transport."""
        response = client.get("/api/metrics/message-types?transport_type=stdio")
        assert response.status_code == 200

        data = response.json()
        # Should not have error (only in http logs)
        assert data["error_count"] == 0


class TestPerformanceEndpoint:
    """Tests for performance metrics endpoint."""

    def test_performance_basic(self, client, sample_logs):
        """Test performance metrics endpoint."""
        response = client.get("/api/metrics/performance")
        assert response.status_code == 200

        data = response.json()
        assert "response_times" in data
        assert "method_stats" in data
        assert "histogram" in data

        # Check response times structure
        rt = data["response_times"]
        assert "percentiles" in rt
        assert "total_requests" in rt
        assert "pending_requests" in rt

        # Should have calculated response times for request/response pairs
        assert rt["total_requests"] >= 2  # At least initialize and tools/list

    def test_performance_with_transport_filter(self, client, sample_logs):
        """Test performance metrics filtered by transport."""
        response = client.get("/api/metrics/performance?transport_type=stdio")
        assert response.status_code == 200

        data = response.json()
        # Should only have stdio response times
        assert data["response_times"]["total_requests"] >= 1


class TestErrorsEndpoint:
    """Tests for errors timeline endpoint."""

    def test_errors_timeline(self, client, sample_logs):
        """Test errors timeline endpoint."""
        response = client.get("/api/metrics/errors")
        assert response.status_code == 200

        data = response.json()
        assert "start_time" in data
        assert "end_time" in data
        assert "interval_minutes" in data
        assert "data" in data

        # Check data structure
        for bucket in data["data"]:
            assert "timestamp" in bucket
            assert "errors" in bucket
            assert "total" in bucket
            assert "error_rate" in bucket

        # Should have at least one error
        total_errors = sum(b["errors"] for b in data["data"])
        assert total_errors >= 1

    def test_errors_with_custom_interval(self, client, sample_logs):
        """Test errors timeline with custom interval."""
        response = client.get("/api/metrics/errors?interval_minutes=15")
        assert response.status_code == 200

        data = response.json()
        assert data["interval_minutes"] == 15


class TestEmptyDatabase:
    """Tests for endpoints with empty database."""

    def test_all_endpoints_empty_db(self, client, test_db):
        """Test all endpoints work with empty database."""
        # All endpoints should return valid responses even with no data

        response = client.get("/api/metrics/timeseries")
        assert response.status_code == 200
        assert response.json()["data"] == []

        response = client.get("/api/metrics/methods")
        assert response.status_code == 200
        assert response.json()["methods"] == []

        response = client.get("/api/metrics/transport")
        assert response.status_code == 200
        assert response.json()["total"] == 0

        response = client.get("/api/metrics/message-types")
        assert response.status_code == 200
        assert response.json()["total"] == 0

        response = client.get("/api/metrics/performance")
        assert response.status_code == 200
        assert response.json()["response_times"]["total_requests"] == 0

        response = client.get("/api/metrics/errors")
        assert response.status_code == 200
        assert response.json()["data"] == []


class TestDateTimeFormats:
    """Tests for different datetime formats."""

    def test_iso_format_with_timezone(self, client, sample_logs):
        """Test ISO format with timezone."""
        from urllib.parse import quote
        start_time = "2024-01-01T00:00:00+00:00"
        end_time = "2025-12-31T23:59:59+00:00"

        response = client.get(
            f"/api/metrics/timeseries?start_time={quote(start_time)}&end_time={quote(end_time)}"
        )
        assert response.status_code == 200

    def test_iso_format_without_timezone(self, client, sample_logs):
        """Test ISO format without timezone."""
        start_time = "2024-01-01T00:00:00"
        end_time = "2025-12-31T23:59:59"

        response = client.get(
            f"/api/metrics/timeseries?start_time={start_time}&end_time={end_time}"
        )
        assert response.status_code == 200
