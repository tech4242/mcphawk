"""Secret masking applied before anything is written to disk.

Captured traffic is shown to people and, through the MCPHawk MCP server, to
agents; credentials in it should not travel further than the wire they were
seen on. Masking is on by default and can be disabled with ``--no-mask``.
"""

import re
from typing import Any

MASK = "••••"

_SECRET_KEY = re.compile(
    r"^(.*[_\-.])?("
    r"token|access[_-]?token|refresh[_-]?token|id[_-]?token|secret|client[_-]?secret|"
    r"password|passwd|pwd|api[_-]?key|apikey|authorization|auth|cookie|"
    r"credentials?|private[_-]?key|session[_-]?key|signature"
    r")$",
    re.IGNORECASE,
)

_SECRET_HEADERS = frozenset({
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
    "x-auth-token",
})

_SECRET_PATTERNS = [
    re.compile(r"\b(sk|pk|rk)-[A-Za-z0-9_\-]{16,}"),            # OpenAI/Anthropic/Stripe style
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),                 # GitHub
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"),              # Slack
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                          # AWS access key id
    re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),                    # Google API key
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),  # JWT
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/\-]{12,}=*"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
]


def mask_text(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(MASK, text)
    return text


def mask_value(value: Any) -> Any:
    """Recursively mask secret-looking keys and token patterns in JSON data."""
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            if isinstance(item, str) and item and _SECRET_KEY.match(str(key)):
                masked[key] = MASK
            else:
                masked[key] = mask_value(item)
        return masked
    if isinstance(value, list):
        return [mask_value(item) for item in value]
    if isinstance(value, str):
        return mask_text(value)
    return value


def mask_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        name: MASK if name.lower() in _SECRET_HEADERS else mask_text(value)
        for name, value in headers.items()
    }


def mask_argv(argv: list[str]) -> list[str]:
    """Mask ``--token=x`` / ``--api-key x`` style arguments in a command line."""
    masked: list[str] = []
    hide_next = False
    for arg in argv:
        if hide_next:
            masked.append(MASK)
            hide_next = False
            continue
        if arg.startswith("-"):
            name, eq, _ = arg.lstrip("-").partition("=")
            if _SECRET_KEY.match(name):
                if eq:
                    masked.append(arg.split("=", 1)[0] + "=" + MASK)
                else:
                    masked.append(arg)
                    hide_next = True
                continue
        masked.append(mask_text(arg))
    return masked
