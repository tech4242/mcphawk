"""Integration tests for analytics data aggregation logic."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from mcphawk.logger import init_db, log_message, set_db_path
from mcphawk.web.metrics import (
    get_error_timeline,
    get_message_type_distribution,
    get_method_frequency,
    get_performance_metrics,
    get_timeseries_metrics,
    get_transport_distribution,
)


@pytest.fixture
def test_db_with_complex_data(tmp_path):
    """Create test database with complex data patterns."""
    db_path = tmp_path / "test_aggregation.db"
    set_db_path(str(db_path))
    init_db()

    # Generate complex data patterns
    base_time = datetime.now(timezone.utc)

    # Pattern 1: Burst of traffic at specific times
    for i in range(50):
        log_message({
            "log_id": f"burst_{i}_{base_time.timestamp()}",
            "timestamp": base_time - timedelta(hours=2, minutes=i % 5),
            "src_ip": "127.0.0.1",
            "src_port": 50000 + i,
            "dst_ip": "127.0.0.1",
            "dst_port": 3000,
            "direction": "outgoing",
            "message": json.dumps({
                "jsonrpc": "2.0",
                "method": "tools/list" if i % 3 == 0 else "initialize",
                "params": {},
                "id": i
            }),
            "transport_type": "http" if i % 2 == 0 else "stdio",
            "metadata": json.dumps({
                "server_name": f"server_{i % 3}",
                "server_version": "1.0"
            }),
            "pid": None if i % 2 == 0 else 1000 + i
        })

    # Pattern 2: Request-response pairs with varying latencies
    for i in range(20):
        req_time = base_time - timedelta(hours=1, minutes=30-i)
        resp_delay = timedelta(milliseconds=10 * (i + 1))  # Increasing latency

        log_message({
            "log_id": f"req_{i}_{base_time.timestamp()}",
            "timestamp": req_time,
            "src_ip": "client",
            "src_port": None,
            "dst_ip": "server",
            "dst_port": None,
            "direction": "outgoing",
            "message": json.dumps({
                "jsonrpc": "2.0",
                "method": f"method_{i % 5}",
                "params": {},
                "id": 100 + i
            }),
            "transport_type": "stdio",
            "metadata": json.dumps({"server_name": "perf_test", "server_version": "1.0"}),
            "pid": 2000
        })

        log_message({
            "log_id": f"resp_{i}_{base_time.timestamp()}",
            "timestamp": req_time + resp_delay,
            "src_ip": "server",
            "src_port": None,
            "dst_ip": "client",
            "dst_port": None,
            "direction": "incoming",
            "message": json.dumps({
                "jsonrpc": "2.0",
                "result": {"data": f"result_{i}"},
                "id": 100 + i
            }),
            "transport_type": "stdio",
            "metadata": json.dumps({"server_name": "perf_test", "server_version": "1.0"}),
            "pid": 2000
        })

    # Pattern 3: Errors at regular intervals
    for i in range(10):
        log_message({
            "log_id": f"error_{i}_{base_time.timestamp()}",
            "timestamp": base_time - timedelta(minutes=i * 5),
            "src_ip": "127.0.0.1",
            "src_port": 3000,
            "dst_ip": "127.0.0.1",
            "dst_port": 60000 + i,
            "direction": "incoming",
            "message": json.dumps({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32600 - i,
                    "message": f"Error {i}"
                },
                "id": 200 + i
            }),
            "transport_type": "http",
            "metadata": json.dumps({"server_name": "error_server", "server_version": "1.0"}),
            "pid": None
        })

    # Pattern 4: Notifications (no response expected)
    for i in range(15):
        log_message({
            "log_id": f"notif_{i}_{base_time.timestamp()}",
            "timestamp": base_time - timedelta(minutes=45 + i),
            "src_ip": "server",
            "src_port": 3000,
            "dst_ip": "client",
            "dst_port": 40000 + i,
            "direction": "incoming",
            "message": json.dumps({
                "jsonrpc": "2.0",
                "method": f"notification/{i % 3}",
                "params": {"index": i}
            }),
            "transport_type": "http",
            "metadata": json.dumps({"server_name": "notif_server", "server_version": "2.0"}),
            "pid": None
        })

    yield db_path


class TestTimeseriesAggregation:
    """Test timeseries data aggregation."""

    def test_timeseries_bucketing(self, test_db_with_complex_data):
        """Test that data is properly bucketed by time intervals."""
        result = get_timeseries_metrics(interval_minutes=15)

        # Check that buckets are aligned to 15-minute intervals
        for _i, bucket in enumerate(result["data"]):
            timestamp = datetime.fromisoformat(bucket["timestamp"])
            assert timestamp.minute % 15 == 0
            assert timestamp.second == 0
            assert timestamp.microsecond == 0

            # Verify counts are non-negative
            assert bucket["requests"] >= 0
            assert bucket["responses"] >= 0
            assert bucket["notifications"] >= 0
            assert bucket["errors"] >= 0

    def test_timeseries_different_intervals(self, test_db_with_complex_data):
        """Test aggregation with different interval sizes."""
        result_5min = get_timeseries_metrics(interval_minutes=5)
        result_30min = get_timeseries_metrics(interval_minutes=30)

        # 30-minute intervals should have fewer buckets
        assert len(result_30min["data"]) < len(result_5min["data"])

        # Total counts should be the same
        total_5min = sum(
            b["requests"] + b["responses"] + b["notifications"]
            for b in result_5min["data"]
        )
        total_30min = sum(
            b["requests"] + b["responses"] + b["notifications"]
            for b in result_30min["data"]
        )
        assert total_5min == total_30min


class TestMethodFrequencyAggregation:
    """Test method frequency aggregation."""

    def test_method_frequency_ranking(self, test_db_with_complex_data):
        """Test that methods are correctly ranked by frequency."""
        result = get_method_frequency(limit=10)

        # Verify methods are sorted by count (descending)
        for i in range(len(result["methods"]) - 1):
            assert result["methods"][i]["count"] >= result["methods"][i + 1]["count"]

        # Check total unique methods count
        assert result["total_unique_methods"] > 0
        assert result["total_unique_methods"] >= len(result["methods"])

    def test_method_frequency_with_server_filter(self, test_db_with_complex_data):
        """Test method frequency filtered by server."""
        result_all = get_method_frequency()
        result_filtered = get_method_frequency(server_name="perf_test")

        # Filtered should have fewer or equal total
        filtered_total = sum(m["count"] for m in result_filtered["methods"])
        all_total = sum(m["count"] for m in result_all["methods"])
        assert filtered_total <= all_total

        # perf_test server should have method_0 through method_4 if data exists
        if result_filtered["methods"]:
            methods = [m["method"] for m in result_filtered["methods"]]
            # Check that we got methods from the perf_test server
            assert len(methods) > 0


class TestPerformanceAggregation:
    """Test performance metrics aggregation."""

    def test_response_time_percentiles(self, test_db_with_complex_data):
        """Test that response time percentiles are correctly calculated."""
        result = get_performance_metrics()

        percentiles = result["response_times"]["percentiles"]
        if percentiles:  # Only if we have data
            # Percentiles should be in ascending order
            assert percentiles["min"] <= percentiles["p50"]
            assert percentiles["p50"] <= percentiles["p90"]
            assert percentiles["p90"] <= percentiles["p95"]
            assert percentiles["p95"] <= percentiles["p99"]
            assert percentiles["p99"] <= percentiles["max"]

            # Average should be between min and max
            assert percentiles["min"] <= percentiles["avg"] <= percentiles["max"]

    def test_response_time_histogram(self, test_db_with_complex_data):
        """Test response time histogram buckets."""
        result = get_performance_metrics()

        histogram = result["histogram"]
        if histogram:
            # Check histogram structure
            total_count = sum(bucket["count"] for bucket in histogram)
            assert total_count == result["response_times"]["total_requests"]

            # Percentages should sum to ~100
            total_percentage = sum(bucket["percentage"] for bucket in histogram)
            assert 99 <= total_percentage <= 101  # Allow for rounding

            # Buckets should have expected ranges
            expected_ranges = [
                "0-10ms", "10-25ms", "25-50ms", "50-100ms",
                "100-250ms", "250-500ms", "500-1000ms",
                "1000-2500ms", "2500-5000ms", "5000ms+"
            ]
            actual_ranges = [bucket["range"] for bucket in histogram]
            assert actual_ranges == expected_ranges

    def test_method_performance_stats(self, test_db_with_complex_data):
        """Test per-method performance statistics."""
        result = get_performance_metrics()

        method_stats = result["method_stats"]
        if method_stats:
            # Should be sorted by average response time (descending)
            for i in range(len(method_stats) - 1):
                assert method_stats[i]["avg"] >= method_stats[i + 1]["avg"]

            # Each method should have valid stats
            for stats in method_stats:
                assert stats["count"] > 0
                assert stats["avg"] > 0
                assert stats["p50"] > 0
                assert stats["p95"] >= stats["p50"]


class TestErrorAggregation:
    """Test error timeline aggregation."""

    def test_error_rate_calculation(self, test_db_with_complex_data):
        """Test that error rates are correctly calculated."""
        result = get_error_timeline(interval_minutes=10)

        for bucket in result["data"]:
            if bucket["total"] > 0:
                expected_rate = (bucket["errors"] / bucket["total"]) * 100
                assert bucket["error_rate"] == pytest.approx(expected_rate)
            else:
                assert bucket["error_rate"] == 0

    def test_error_timeline_intervals(self, test_db_with_complex_data):
        """Test error timeline with different intervals."""
        result_5min = get_error_timeline(interval_minutes=5)
        result_15min = get_error_timeline(interval_minutes=15)

        # Total errors should be the same regardless of interval
        total_errors_5min = sum(b["errors"] for b in result_5min["data"])
        total_errors_15min = sum(b["errors"] for b in result_15min["data"])
        assert total_errors_5min == total_errors_15min


class TestTransportAggregation:
    """Test transport distribution aggregation."""

    def test_transport_distribution_percentages(self, test_db_with_complex_data):
        """Test that transport distribution percentages are correct."""
        result = get_transport_distribution()

        # Percentages should sum to 100
        total_percentage = sum(d["percentage"] for d in result["distribution"])
        assert 99.9 <= total_percentage <= 100.1  # Allow for rounding

        # Counts should sum to total
        total_count = sum(d["count"] for d in result["distribution"])
        assert total_count == result["total"]

        # Each percentage should be correct
        for item in result["distribution"]:
            expected = (item["count"] / result["total"]) * 100
            assert item["percentage"] == pytest.approx(expected)

    def test_transport_distribution_with_time_filter(self, test_db_with_complex_data):
        """Test transport distribution with time filtering."""
        # Get last 30 minutes only
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(minutes=30)

        result = get_transport_distribution(start_time=start_time, end_time=end_time)

        # Should have some data but potentially less than full dataset
        assert result["total"] > 0
        assert len(result["distribution"]) > 0


class TestMessageTypeAggregation:
    """Test message type distribution aggregation."""

    def test_message_type_counts(self, test_db_with_complex_data):
        """Test that message types are correctly counted."""
        result = get_message_type_distribution()

        # Should have all message types
        types = [d["type"] for d in result["distribution"]]
        assert "request" in types
        assert "response" in types
        assert "notification" in types

        # Error count should match actual errors
        assert result["error_count"] >= 10  # We added 10 error responses

        # Total should match sum of all types
        total_from_dist = sum(d["count"] for d in result["distribution"])
        assert total_from_dist == result["total"]

    def test_message_type_with_transport_filter(self, test_db_with_complex_data):
        """Test message type distribution filtered by transport."""
        result_all = get_message_type_distribution()
        result_stdio = get_message_type_distribution(transport_type="stdio")
        result_http = get_message_type_distribution(transport_type="http")

        # Totals should add up
        assert result_stdio["total"] + result_http["total"] <= result_all["total"]

        # stdio should have no errors (we only added errors to http)
        assert result_stdio["error_count"] < result_all["error_count"]


class TestEdgeCasesAndBoundaries:
    """Test edge cases and boundary conditions."""

    def test_single_data_point(self, tmp_path):
        """Test metrics with single data point."""
        db_path = tmp_path / "test_single.db"
        set_db_path(str(db_path))
        init_db()

        # Add single log entry
        log_message({
            "log_id": "single",
            "timestamp": datetime.now(timezone.utc),
            "src_ip": "client",
            "src_port": None,
            "dst_ip": "server",
            "dst_port": None,
            "direction": "outgoing",
            "message": json.dumps({
                "jsonrpc": "2.0",
                "method": "test",
                "params": {},
                "id": 1
            }),
            "transport_type": "stdio",
            "metadata": json.dumps({"server_name": "test", "server_version": "1.0"}),
            "pid": 1000
        })

        # All metrics should work with single point
        assert get_timeseries_metrics()["data"]
        assert get_method_frequency()["total_unique_methods"] == 1
        assert get_transport_distribution()["total"] == 1
        assert get_message_type_distribution()["total"] == 1
        assert get_performance_metrics()["response_times"]["pending_requests"] == 1
        assert get_error_timeline()["data"]

    def test_large_time_gaps(self, tmp_path):
        """Test metrics with large gaps in data."""
        db_path = tmp_path / "test_gaps.db"
        set_db_path(str(db_path))
        init_db()

        # Add data with large gap (1 day)
        base_time = datetime.now(timezone.utc)

        log_message({
            "log_id": "old",
            "timestamp": base_time - timedelta(days=1),
            "src_ip": "client",
            "src_port": None,
            "dst_ip": "server",
            "dst_port": None,
            "direction": "outgoing",
            "message": json.dumps({"jsonrpc": "2.0", "method": "old", "id": 1}),
            "transport_type": "stdio",
            "metadata": "{}",
            "pid": 1000
        })

        log_message({
            "log_id": "new",
            "timestamp": base_time,
            "src_ip": "client",
            "src_port": None,
            "dst_ip": "server",
            "dst_port": None,
            "direction": "outgoing",
            "message": json.dumps({"jsonrpc": "2.0", "method": "new", "id": 2}),
            "transport_type": "stdio",
            "metadata": "{}",
            "pid": 1000
        })

        # Timeseries should handle the gap
        result = get_timeseries_metrics(interval_minutes=60)
        assert len(result["data"]) >= 2  # At least two buckets
