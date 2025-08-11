"""Unit tests for metrics module."""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from mcphawk.web.metrics import (
    get_error_timeline,
    get_message_type_distribution,
    get_method_frequency,
    get_performance_metrics,
    get_timeseries_metrics,
    get_transport_distribution,
)


@pytest.fixture
def mock_db_rows():
    """Create mock database rows for testing."""
    base_time = datetime.now(timezone.utc)
    return [
        {
            "timestamp": (base_time - timedelta(minutes=10)).isoformat(),
            "message": json.dumps({
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {},
                "id": 1
            }),
            "direction": "outgoing",
            "transport_type": "stdio",
            "metadata": json.dumps({"server_name": "test-server", "server_version": "1.0"})
        },
        {
            "timestamp": (base_time - timedelta(minutes=9)).isoformat(),
            "message": json.dumps({
                "jsonrpc": "2.0",
                "result": {"capabilities": {}},
                "id": 1
            }),
            "direction": "incoming",
            "transport_type": "stdio",
            "metadata": json.dumps({"server_name": "test-server", "server_version": "1.0"})
        },
        {
            "timestamp": (base_time - timedelta(minutes=8)).isoformat(),
            "message": json.dumps({
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": 2
            }),
            "direction": "outgoing",
            "transport_type": "http",
            "metadata": json.dumps({"server_name": "test-server", "server_version": "1.0"})
        },
        {
            "timestamp": (base_time - timedelta(minutes=7)).isoformat(),
            "message": json.dumps({
                "jsonrpc": "2.0",
                "result": {"tools": []},
                "id": 2
            }),
            "direction": "incoming",
            "transport_type": "http",
            "metadata": json.dumps({"server_name": "test-server", "server_version": "1.0"})
        },
        {
            "timestamp": (base_time - timedelta(minutes=5)).isoformat(),
            "message": json.dumps({
                "jsonrpc": "2.0",
                "method": "notification",
                "params": {}
            }),
            "direction": "outgoing",
            "transport_type": "http",
            "metadata": json.dumps({"server_name": "test-server", "server_version": "1.0"})
        },
        {
            "timestamp": (base_time - timedelta(minutes=3)).isoformat(),
            "message": json.dumps({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": "Method not found"},
                "id": 3
            }),
            "direction": "incoming",
            "transport_type": "http",
            "metadata": json.dumps({"server_name": "test-server", "server_version": "1.0"})
        },
    ]


@pytest.fixture
def mock_db_connection(mock_db_rows):
    """Mock database connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()

    # Mock MIN/MAX timestamp query
    mock_cursor.fetchone.side_effect = [
        {
            "min_ts": mock_db_rows[0]["timestamp"],
            "max_ts": mock_db_rows[-1]["timestamp"]
        },
        None  # For subsequent calls
    ]

    # Mock main data query
    mock_cursor.fetchall.return_value = mock_db_rows
    mock_conn.cursor.return_value = mock_cursor

    return mock_conn


class TestTimeseriesMetrics:
    """Tests for timeseries metrics."""

    @patch("mcphawk.web.metrics.get_db_connection")
    def test_get_timeseries_metrics_basic(self, mock_get_db, mock_db_connection):
        """Test basic timeseries metrics retrieval."""
        mock_get_db.return_value.__enter__.return_value = mock_db_connection

        result = get_timeseries_metrics(interval_minutes=5)

        assert "start_time" in result
        assert "end_time" in result
        assert "interval_minutes" in result
        assert result["interval_minutes"] == 5
        assert "data" in result
        assert isinstance(result["data"], list)

    @patch("mcphawk.web.metrics.get_db_connection")
    def test_get_timeseries_metrics_with_filters(self, mock_get_db, mock_db_connection):
        """Test timeseries metrics with transport and server filters."""
        mock_get_db.return_value.__enter__.return_value = mock_db_connection

        start_time = datetime.now(timezone.utc) - timedelta(hours=1)
        end_time = datetime.now(timezone.utc)

        result = get_timeseries_metrics(
            start_time=start_time,
            end_time=end_time,
            interval_minutes=10,
            transport_type="stdio",
            server_name="test-server"
        )

        assert result["start_time"] == start_time.isoformat()
        assert result["end_time"] == end_time.isoformat()
        assert result["interval_minutes"] == 10

        # Verify SQL query was called with correct parameters
        mock_cursor = mock_db_connection.cursor.return_value
        assert mock_cursor.execute.called
        call_args = mock_cursor.execute.call_args[0]
        assert "transport_type = ?" in call_args[0]
        assert "metadata LIKE ?" in call_args[0]

    @patch("mcphawk.web.metrics.get_db_connection")
    def test_get_timeseries_metrics_aggregation(self, mock_get_db, mock_db_rows):
        """Test that timeseries metrics properly aggregate by message type."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Return time range first, then data
        mock_cursor.fetchone.return_value = {
            "min_ts": mock_db_rows[0]["timestamp"],
            "max_ts": mock_db_rows[-1]["timestamp"]
        }
        mock_cursor.fetchall.return_value = mock_db_rows
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        result = get_timeseries_metrics(interval_minutes=15)

        # Should have aggregated data
        assert len(result["data"]) > 0

        # Check that buckets have correct structure
        for bucket in result["data"]:
            assert "timestamp" in bucket
            assert "requests" in bucket
            assert "responses" in bucket
            assert "notifications" in bucket
            assert "errors" in bucket

            # Verify counts are non-negative (actual values depend on bucket boundaries)
            assert bucket["requests"] >= 0
            assert bucket["responses"] >= 0
            assert bucket["notifications"] >= 0
            assert bucket["errors"] >= 0

        # Verify total counts across all buckets match the mock data
        total_requests = sum(b["requests"] for b in result["data"])
        total_responses = sum(b["responses"] for b in result["data"])
        total_notifications = sum(b["notifications"] for b in result["data"])
        total_errors = sum(b["errors"] for b in result["data"])

        assert total_requests == 2  # initialize and tools/list
        assert total_responses == 2  # Two responses
        assert total_notifications == 1  # One notification
        assert total_errors >= 1  # At least one error response


class TestMethodFrequency:
    """Tests for method frequency metrics."""

    @patch("mcphawk.web.metrics.get_db_connection")
    def test_get_method_frequency_basic(self, mock_get_db, mock_db_connection):
        """Test basic method frequency retrieval."""
        mock_get_db.return_value.__enter__.return_value = mock_db_connection

        result = get_method_frequency(limit=10)

        assert "methods" in result
        assert "total_unique_methods" in result
        assert isinstance(result["methods"], list)

        # Check method structure
        for method in result["methods"]:
            assert "method" in method
            assert "count" in method

    @patch("mcphawk.web.metrics.get_db_connection")
    def test_get_method_frequency_sorting(self, mock_get_db, mock_db_rows):
        """Test that methods are sorted by frequency."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Add duplicate method to test sorting
        test_rows = [*mock_db_rows, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": json.dumps({
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {},
                "id": 10
            })
        }]

        mock_cursor.fetchone.return_value = {
            "min_ts": test_rows[0]["timestamp"],
            "max_ts": test_rows[-1]["timestamp"]
        }
        mock_cursor.fetchall.return_value = test_rows
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        result = get_method_frequency(limit=5)

        # Initialize should be first (appears twice)
        assert result["methods"][0]["method"] == "initialize"
        assert result["methods"][0]["count"] == 2
        assert result["total_unique_methods"] == 3  # initialize, tools/list, notification


class TestTransportDistribution:
    """Tests for transport distribution metrics."""

    @patch("mcphawk.web.metrics.get_db_connection")
    def test_get_transport_distribution(self, mock_get_db):
        """Test transport distribution calculation."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Mock time range query
        mock_cursor.fetchone.return_value = {
            "min_ts": datetime.now(timezone.utc).isoformat(),
            "max_ts": datetime.now(timezone.utc).isoformat()
        }

        # Mock transport distribution query
        mock_cursor.fetchall.return_value = [
            {"transport_type": "stdio", "count": 10},
            {"transport_type": "http", "count": 20},
            {"transport_type": None, "count": 5}
        ]

        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        result = get_transport_distribution()

        assert "distribution" in result
        assert "total" in result
        assert result["total"] == 35

        # Check distribution structure and percentages
        for item in result["distribution"]:
            assert "transport_type" in item
            assert "count" in item
            assert "percentage" in item

        # Verify percentages
        stdio_item = next(i for i in result["distribution"] if i["transport_type"] == "stdio")
        assert stdio_item["percentage"] == pytest.approx(10/35 * 100)

        # Check that None is converted to "unknown"
        unknown_item = next(i for i in result["distribution"] if i["transport_type"] == "unknown")
        assert unknown_item["count"] == 5


class TestMessageTypeDistribution:
    """Tests for message type distribution metrics."""

    @patch("mcphawk.web.metrics.get_db_connection")
    def test_get_message_type_distribution(self, mock_get_db, mock_db_rows):
        """Test message type distribution calculation."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchone.return_value = {
            "min_ts": mock_db_rows[0]["timestamp"],
            "max_ts": mock_db_rows[-1]["timestamp"]
        }
        mock_cursor.fetchall.return_value = mock_db_rows
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        result = get_message_type_distribution()

        assert "distribution" in result
        assert "error_count" in result
        assert "total" in result

        # Verify counts based on mock data
        assert result["total"] == len(mock_db_rows)
        assert result["error_count"] == 1  # One error message

        # Check distribution structure
        for item in result["distribution"]:
            assert "type" in item
            assert "count" in item
            assert "percentage" in item


class TestPerformanceMetrics:
    """Tests for performance metrics."""

    @patch("mcphawk.web.metrics.get_db_connection")
    def test_get_performance_metrics_basic(self, mock_get_db, mock_db_rows):
        """Test basic performance metrics calculation."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchone.return_value = {
            "min_ts": mock_db_rows[0]["timestamp"],
            "max_ts": mock_db_rows[-1]["timestamp"]
        }
        mock_cursor.fetchall.return_value = mock_db_rows
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        result = get_performance_metrics()

        assert "response_times" in result
        assert "method_stats" in result
        assert "histogram" in result

        # Check response times structure
        rt = result["response_times"]
        assert "percentiles" in rt
        assert "total_requests" in rt
        assert "pending_requests" in rt

    @patch("mcphawk.web.metrics.get_db_connection")
    def test_get_performance_metrics_response_time_calculation(self, mock_get_db):
        """Test that response times are correctly calculated."""
        base_time = datetime.now(timezone.utc)

        # Create request-response pairs with known delays
        test_rows = [
            {
                "timestamp": base_time.isoformat(),
                "message": json.dumps({
                    "jsonrpc": "2.0",
                    "method": "test",
                    "id": 1
                }),
                "direction": "outgoing"
            },
            {
                "timestamp": (base_time + timedelta(milliseconds=50)).isoformat(),
                "message": json.dumps({
                    "jsonrpc": "2.0",
                    "result": {},
                    "id": 1
                }),
                "direction": "incoming"
            },
            {
                "timestamp": (base_time + timedelta(seconds=1)).isoformat(),
                "message": json.dumps({
                    "jsonrpc": "2.0",
                    "method": "slow",
                    "id": 2
                }),
                "direction": "outgoing"
            },
            {
                "timestamp": (base_time + timedelta(seconds=2)).isoformat(),
                "message": json.dumps({
                    "jsonrpc": "2.0",
                    "result": {},
                    "id": 2
                }),
                "direction": "incoming"
            }
        ]

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {
            "min_ts": test_rows[0]["timestamp"],
            "max_ts": test_rows[-1]["timestamp"]
        }
        mock_cursor.fetchall.return_value = test_rows
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        result = get_performance_metrics()

        # Should have calculated 2 response times: 50ms and 1000ms
        assert result["response_times"]["total_requests"] == 2
        percentiles = result["response_times"]["percentiles"]
        assert percentiles["min"] == pytest.approx(50.0, rel=1)
        assert percentiles["max"] == pytest.approx(1000.0, rel=1)
        assert percentiles["avg"] == pytest.approx(525.0, rel=1)

        # Check method stats
        assert len(result["method_stats"]) == 2
        slow_method = next(m for m in result["method_stats"] if m["method"] == "slow")
        assert slow_method["avg"] == pytest.approx(1000.0, rel=1)


class TestErrorTimeline:
    """Tests for error timeline metrics."""

    @patch("mcphawk.web.metrics.get_db_connection")
    def test_get_error_timeline(self, mock_get_db, mock_db_rows):
        """Test error timeline generation."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchone.return_value = {
            "min_ts": mock_db_rows[0]["timestamp"],
            "max_ts": mock_db_rows[-1]["timestamp"]
        }
        mock_cursor.fetchall.return_value = mock_db_rows
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        result = get_error_timeline(interval_minutes=5)

        assert "start_time" in result
        assert "end_time" in result
        assert "interval_minutes" in result
        assert "data" in result

        # Check data structure
        for bucket in result["data"]:
            assert "timestamp" in bucket
            assert "errors" in bucket
            assert "total" in bucket
            assert "error_rate" in bucket

            # Verify error rate calculation
            if bucket["total"] > 0:
                expected_rate = (bucket["errors"] / bucket["total"]) * 100
                assert bucket["error_rate"] == pytest.approx(expected_rate)

    @patch("mcphawk.web.metrics.get_db_connection")
    def test_get_error_timeline_no_data(self, mock_get_db):
        """Test error timeline with no data."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # No data in database
        mock_cursor.fetchone.return_value = {"min_ts": None, "max_ts": None}
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        result = get_error_timeline()

        assert "data" in result
        assert result["data"] == []

        # Should have default time range
        assert "start_time" in result
        assert "end_time" in result


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @patch("mcphawk.web.metrics.get_db_connection")
    def test_invalid_json_messages(self, mock_get_db):
        """Test handling of invalid JSON messages."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        test_rows = [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "not valid json",
                "transport_type": "http",
                "metadata": "{}"
            },
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": json.dumps({"jsonrpc": "2.0", "method": "test", "id": 1}),
                "transport_type": "http",
                "metadata": "{}"
            }
        ]

        mock_cursor.fetchone.return_value = {
            "min_ts": test_rows[0]["timestamp"],
            "max_ts": test_rows[-1]["timestamp"]
        }
        mock_cursor.fetchall.return_value = test_rows
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        # Should not raise exception
        result = get_method_frequency()
        assert result["total_unique_methods"] == 1  # Only valid message counted

    @patch("mcphawk.web.metrics.get_db_connection")
    def test_empty_database(self, mock_get_db):
        """Test all metrics functions with empty database."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        mock_cursor.fetchone.return_value = {"min_ts": None, "max_ts": None}
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        # Test all functions - none should raise exceptions
        assert get_timeseries_metrics()["data"] == []
        assert get_method_frequency()["methods"] == []
        assert get_transport_distribution()["total"] == 0
        assert get_message_type_distribution()["total"] == 0
        assert get_performance_metrics()["response_times"]["total_requests"] == 0
        assert get_error_timeline()["data"] == []
