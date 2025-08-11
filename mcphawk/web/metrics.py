"""Metrics API endpoints for MCPHawk analytics."""

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from mcphawk.logger import get_db_connection
from mcphawk.utils import get_message_type

logger = logging.getLogger(__name__)


def get_timeseries_metrics(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    interval_minutes: int = 5,
    transport_type: Optional[str] = None,
    server_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Get time series metrics for message traffic.

    Args:
        start_time: Start of time range (defaults to all available data)
        end_time: End of time range (defaults to all available data)
        interval_minutes: Aggregation interval in minutes
        transport_type: Filter by transport type
        server_name: Filter by server name
    Returns:
        Time series data with counts by message type
    """
    logger.debug(f"get_timeseries_metrics called with start_time={start_time}, end_time={end_time}")
    
    # If no time range specified, get the full range from database
    if not start_time or not end_time:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM logs")
            row = cur.fetchone()
            if row and row["min_ts"] and row["max_ts"]:
                if not start_time:
                    start_time = datetime.fromisoformat(row["min_ts"])
                if not end_time:
                    end_time = datetime.fromisoformat(row["max_ts"])
            else:
                # No data, use defaults
                if not end_time:
                    end_time = datetime.now(timezone.utc)
                if not start_time:
                    start_time = end_time - timedelta(hours=1)

    with get_db_connection() as conn:
        cur = conn.cursor()

        query = """
            SELECT timestamp, message, metadata
            FROM logs
            WHERE timestamp >= ? AND timestamp <= ?
        """
        params = [start_time.isoformat(), end_time.isoformat()]

        if transport_type:
            query += " AND transport_type = ?"
            params.append(transport_type)

        if server_name:
            query += " AND metadata LIKE ?"
            params.append(f'%"server_name":"{server_name}"%')

        query += " ORDER BY timestamp ASC"

        cur.execute(query, params)
        rows = cur.fetchall()

    # Group by time intervals
    time_buckets = defaultdict(lambda: {
        "requests": 0,
        "responses": 0,
        "notifications": 0,
        "errors": 0
    })

    for row in rows:
        timestamp = datetime.fromisoformat(row["timestamp"])
        # Round down to interval
        bucket_time = timestamp.replace(second=0, microsecond=0)
        bucket_time = bucket_time - timedelta(minutes=bucket_time.minute % interval_minutes)

        msg_type = get_message_type(row["message"])

        if msg_type == "request":
            time_buckets[bucket_time]["requests"] += 1
        elif msg_type == "response":
            time_buckets[bucket_time]["responses"] += 1
        elif msg_type == "notification":
            time_buckets[bucket_time]["notifications"] += 1
        elif msg_type == "error":
            time_buckets[bucket_time]["errors"] += 1

        # Check for errors in responses
        try:
            msg_data = json.loads(row["message"])
            if "error" in msg_data:
                time_buckets[bucket_time]["errors"] += 1
        except Exception:
            pass

    # Convert to sorted list
    result = []
    for time_key in sorted(time_buckets.keys()):
        result.append({
            "timestamp": time_key.isoformat(),
            **time_buckets[time_key]
        })

    return {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "interval_minutes": interval_minutes,
        "data": result
    }


def get_method_frequency(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 20,
    transport_type: Optional[str] = None,
    server_name: Optional[str] = None,
) -> dict[str, Any]:
    """
    Get frequency of JSON-RPC methods.

    Args:
        start_time: Start of time range
        end_time: End of time range
        limit: Max number of methods to return
        transport_type: Filter by transport type
        server_name: Filter by server name
    Returns:
        Method frequency data
    """
    # If no time range specified, get the full range from database
    if not start_time or not end_time:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM logs")
            row = cur.fetchone()
            if row and row["min_ts"] and row["max_ts"]:
                if not start_time:
                    start_time = datetime.fromisoformat(row["min_ts"])
                if not end_time:
                    end_time = datetime.fromisoformat(row["max_ts"])
            else:
                # No data, use defaults
                if not end_time:
                    end_time = datetime.now(timezone.utc)
                if not start_time:
                    start_time = end_time - timedelta(hours=1)

    with get_db_connection() as conn:
        cur = conn.cursor()

        query = """
            SELECT message
            FROM logs
            WHERE timestamp >= ? AND timestamp <= ?
        """
        params = [start_time.isoformat(), end_time.isoformat()]

        if transport_type:
            query += " AND transport_type = ?"
            params.append(transport_type)

        if server_name:
            query += " AND metadata LIKE ?"
            params.append(f'%"server_name":"{server_name}"%')

        cur.execute(query, params)
        rows = cur.fetchall()

    method_counts = Counter()

    for row in rows:
        try:
            msg_data = json.loads(row["message"])
            if "method" in msg_data:
                method_counts[msg_data["method"]] += 1
        except Exception:
            pass

    # Get top methods
    top_methods = method_counts.most_common(limit)

    return {
        "methods": [
            {"method": method, "count": count}
            for method, count in top_methods
        ],
        "total_unique_methods": len(method_counts)
    }


def get_transport_distribution(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> dict[str, Any]:
    """
    Get distribution of messages by transport type.

    Args:
        start_time: Start of time range
        end_time: End of time range
    Returns:
        Transport type distribution
    """
    # If no time range specified, get the full range from database
    if not start_time or not end_time:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM logs")
            row = cur.fetchone()
            if row and row["min_ts"] and row["max_ts"]:
                if not start_time:
                    start_time = datetime.fromisoformat(row["min_ts"])
                if not end_time:
                    end_time = datetime.fromisoformat(row["max_ts"])
            else:
                # No data, use defaults
                if not end_time:
                    end_time = datetime.now(timezone.utc)
                if not start_time:
                    start_time = end_time - timedelta(hours=1)

    with get_db_connection() as conn:
        cur = conn.cursor()

        query = """
            SELECT transport_type, COUNT(*) as count
            FROM logs
            WHERE timestamp >= ? AND timestamp <= ?
            GROUP BY transport_type
        """

        cur.execute(query, [start_time.isoformat(), end_time.isoformat()])
        rows = cur.fetchall()

    distribution = []
    total = 0

    for row in rows:
        transport = row["transport_type"] or "unknown"
        count = row["count"]
        distribution.append({
            "transport_type": transport,
            "count": count
        })
        total += count

    # Add percentages
    for item in distribution:
        item["percentage"] = (item["count"] / total * 100) if total > 0 else 0

    return {
        "distribution": distribution,
        "total": total
    }


def get_message_type_distribution(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    transport_type: Optional[str] = None,
) -> dict[str, Any]:
    """
    Get distribution of messages by type.

    Args:
        start_time: Start of time range
        end_time: End of time range
        transport_type: Filter by transport type
    Returns:
        Message type distribution
    """
    # If no time range specified, get the full range from database
    if not start_time or not end_time:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM logs")
            row = cur.fetchone()
            if row and row["min_ts"] and row["max_ts"]:
                if not start_time:
                    start_time = datetime.fromisoformat(row["min_ts"])
                if not end_time:
                    end_time = datetime.fromisoformat(row["max_ts"])
            else:
                # No data, use defaults
                if not end_time:
                    end_time = datetime.now(timezone.utc)
                if not start_time:
                    start_time = end_time - timedelta(hours=1)

    with get_db_connection() as conn:
        cur = conn.cursor()

        query = """
            SELECT message
            FROM logs
            WHERE timestamp >= ? AND timestamp <= ?
        """
        params = [start_time.isoformat(), end_time.isoformat()]

        if transport_type:
            query += " AND transport_type = ?"
            params.append(transport_type)

        cur.execute(query, params)
        rows = cur.fetchall()

    type_counts = Counter()
    error_count = 0

    for row in rows:
        msg_type = get_message_type(row["message"])
        type_counts[msg_type] += 1

        # Check for errors
        try:
            msg_data = json.loads(row["message"])
            if "error" in msg_data:
                error_count += 1
        except Exception:
            pass

    total = sum(type_counts.values())

    distribution = []
    for msg_type, count in type_counts.items():
        distribution.append({
            "type": msg_type,
            "count": count,
            "percentage": (count / total * 100) if total > 0 else 0
        })

    return {
        "distribution": distribution,
        "error_count": error_count,
        "total": total
    }


def get_performance_metrics(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    transport_type: Optional[str] = None,
) -> dict[str, Any]:
    """
    Calculate performance metrics including response times.

    Args:
        start_time: Start of time range
        end_time: End of time range
        transport_type: Filter by transport type
    Returns:
        Performance metrics including response time distribution
    """
    # If no time range specified, get the full range from database
    if not start_time or not end_time:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM logs")
            row = cur.fetchone()
            if row and row["min_ts"] and row["max_ts"]:
                if not start_time:
                    start_time = datetime.fromisoformat(row["min_ts"])
                if not end_time:
                    end_time = datetime.fromisoformat(row["max_ts"])
            else:
                # No data, use defaults
                if not end_time:
                    end_time = datetime.now(timezone.utc)
                if not start_time:
                    start_time = end_time - timedelta(hours=1)

    with get_db_connection() as conn:
        cur = conn.cursor()

        query = """
            SELECT timestamp, message, direction
            FROM logs
            WHERE timestamp >= ? AND timestamp <= ?
        """
        params = [start_time.isoformat(), end_time.isoformat()]

        if transport_type:
            query += " AND transport_type = ?"
            params.append(transport_type)

        query += " ORDER BY timestamp ASC"

        cur.execute(query, params)
        rows = cur.fetchall()

    # Track requests and match with responses
    pending_requests = {}  # id -> (timestamp, method)
    response_times = []
    method_response_times = defaultdict(list)

    for row in rows:
        try:
            msg_data = json.loads(row["message"])
            timestamp = datetime.fromisoformat(row["timestamp"])

            # Track requests
            if "method" in msg_data and "id" in msg_data:
                msg_id = msg_data["id"]
                method = msg_data["method"]
                pending_requests[msg_id] = (timestamp, method)

            # Match responses with requests
            elif ("result" in msg_data or "error" in msg_data) and "id" in msg_data:
                msg_id = msg_data["id"]
                if msg_id in pending_requests:
                    req_time, method = pending_requests[msg_id]
                    response_time = (timestamp - req_time).total_seconds() * 1000  # in ms
                    response_times.append(response_time)
                    method_response_times[method].append(response_time)
                    del pending_requests[msg_id]
        except Exception:
            pass

    # Calculate percentiles
    response_times.sort()
    percentiles = {}

    if response_times:
        n = len(response_times)
        percentiles = {
            "p50": response_times[int(n * 0.5)],
            "p90": response_times[int(n * 0.9)],
            "p95": response_times[int(n * 0.95)],
            "p99": response_times[min(int(n * 0.99), n - 1)],
            "min": response_times[0],
            "max": response_times[-1],
            "avg": sum(response_times) / n
        }

    # Calculate per-method stats
    method_stats = []
    for method, times in method_response_times.items():
        times.sort()
        n = len(times)
        if n > 0:
            method_stats.append({
                "method": method,
                "count": n,
                "avg": sum(times) / n,
                "p50": times[int(n * 0.5)],
                "p95": times[min(int(n * 0.95), n - 1)] if n > 1 else times[0]
            })

    # Sort by average response time
    method_stats.sort(key=lambda x: x["avg"], reverse=True)

    # Create histogram buckets
    histogram = []
    if response_times:
        buckets = [0, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, float('inf')]
        for i in range(len(buckets) - 1):
            lower = buckets[i]
            upper = buckets[i + 1]
            count = sum(1 for t in response_times if lower <= t < upper)
            label = f"{lower}-{upper}ms" if upper != float('inf') else f"{lower}ms+"
            histogram.append({
                "range": label,
                "count": count,
                "percentage": (count / len(response_times) * 100) if response_times else 0
            })

    return {
        "response_times": {
            "percentiles": percentiles,
            "total_requests": len(response_times),
            "pending_requests": len(pending_requests)
        },
        "method_stats": method_stats[:10],  # Top 10 slowest methods
        "histogram": histogram
    }


def get_error_timeline(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    interval_minutes: int = 5,
) -> dict[str, Any]:
    """
    Get timeline of errors.

    Args:
        start_time: Start of time range
        end_time: End of time range
        interval_minutes: Aggregation interval
    Returns:
        Error timeline with error rates
    """
    # If no time range specified, get the full range from database
    if not start_time or not end_time:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT MIN(timestamp) as min_ts, MAX(timestamp) as max_ts FROM logs")
            row = cur.fetchone()
            if row and row["min_ts"] and row["max_ts"]:
                if not start_time:
                    start_time = datetime.fromisoformat(row["min_ts"])
                if not end_time:
                    end_time = datetime.fromisoformat(row["max_ts"])
            else:
                # No data, use defaults
                if not end_time:
                    end_time = datetime.now(timezone.utc)
                if not start_time:
                    start_time = end_time - timedelta(hours=1)

    with get_db_connection() as conn:
        cur = conn.cursor()

        query = """
            SELECT timestamp, message
            FROM logs
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """

        cur.execute(query, [start_time.isoformat(), end_time.isoformat()])
        rows = cur.fetchall()

    # Group by time intervals
    time_buckets = defaultdict(lambda: {"errors": 0, "total": 0})

    for row in rows:
        timestamp = datetime.fromisoformat(row["timestamp"])
        # Round down to interval
        bucket_time = timestamp.replace(second=0, microsecond=0)
        bucket_time = bucket_time - timedelta(minutes=bucket_time.minute % interval_minutes)

        time_buckets[bucket_time]["total"] += 1

        # Check for errors
        try:
            msg_data = json.loads(row["message"])
            if "error" in msg_data:
                time_buckets[bucket_time]["errors"] += 1
        except Exception:
            pass

        # Also count error message types
        msg_type = get_message_type(row["message"])
        if msg_type == "error":
            time_buckets[bucket_time]["errors"] += 1

    # Convert to sorted list with error rates
    result = []
    for time_key in sorted(time_buckets.keys()):
        bucket = time_buckets[time_key]
        error_rate = (bucket["errors"] / bucket["total"] * 100) if bucket["total"] > 0 else 0
        result.append({
            "timestamp": time_key.isoformat(),
            "errors": bucket["errors"],
            "total": bucket["total"],
            "error_rate": error_rate
        })

    return {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "interval_minutes": interval_minutes,
        "data": result
    }
