"""
Redaction helpers for provider credentials in logs and error messages.

RPC providers put API keys in URL paths (Alchemy ``/v2/<key>``, Infura
``/v3/<key>``) or query strings, and transport exceptions embed the full
URL in their message. Use ``format_exception_safe`` instead of ``str(exc)``
whenever an exception may reach a log line or an error message.
"""

import re
from typing import List, Pattern, Tuple

_PATTERNS: List[Tuple[Pattern[str], str]] = [
    # Path-embedded keys: /v2/<key> (Alchemy), /v3/<key> (Infura), ...
    (re.compile(r"(/v[0-9]+/)[A-Za-z0-9_-]{16,}"), r"\1***"),
    # Query/body credentials: apikey=..., token=..., key=...
    (
        re.compile(
            r"(?i)\b(apikey|api_key|api-key|access_key|secret|token|key)"
            r"=([^&\s\"']+)"
        ),
        r"\1=***",
    ),
    # URL userinfo: https://user:pass@host
    (re.compile(r"://([^/@\s]+)@"), r"://***@"),
]


def redact_secrets(text: str) -> str:
    """Mask credential-looking segments in ``text``."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def format_exception_safe(exc: BaseException) -> str:
    """``str(exc)`` with provider credentials masked, prefixed by the type."""
    return f"{type(exc).__name__}: {redact_secrets(str(exc))}"
