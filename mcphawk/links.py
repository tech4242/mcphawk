"""Stable web UI URLs, handed out by the MCP server so agents can point
people at exactly what they are talking about."""

import os
from urllib.parse import quote

DEFAULT_URL = "http://127.0.0.1:8484"


def base_url() -> str:
    return os.environ.get("MCPHAWK_URL", DEFAULT_URL).rstrip("/")


def session_url(session_id: str) -> str:
    return f"{base_url()}/s/{session_id}"


def exchange_url(exchange_id: int) -> str:
    return f"{base_url()}/x/{exchange_id}"


def run_url(run_key: str) -> str:
    return f"{base_url()}/r/{quote(run_key, safe='')}"


def compare_url(before: str, after: str) -> str:
    return f"{base_url()}/compare?before={before}&after={after}"
