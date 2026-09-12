"""Bounded, untranslated error text at the provider response boundary.

Recognize error envelope fields, not provider names or message vocabulary.
Never forward an entire JSON document, HTML error page, or response headers.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from urllib.parse import quote, quote_plus, urlsplit

MAX_ERROR_MESSAGE_CHARS = 2000
_MAX_ERROR_BODY_BYTES = 65536
_URL = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://[^\s<>\"']+")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069\ud800-\udfff]")


def provider_error_message(
    body: bytes,
    headers: Mapping[str, str],
    *,
    private_values: Iterable[str | None] = (),
) -> str | None:
    """Extract a message, redact known private values, and keep its original language."""
    if not body or len(body) > _MAX_ERROR_BODY_BYTES:
        return None
    try:
        text = body.decode("utf-8", errors="strict")
    except UnicodeError:
        return None
    media_type = next(
        (
            value.split(";", 1)[0].strip().lower()
            for key, value in headers.items()
            if key.lower() == "content-type"
        ),
        "",
    )
    try:
        payload = json.loads(text)
    except (ValueError, RecursionError):
        if media_type != "text/plain" or text.lstrip().startswith("<"):
            return None
        message = text
    else:
        if not isinstance(payload, dict):
            return None
        error = payload.get("error")
        candidates = (
            error.get("message") if isinstance(error, dict) else error,
            payload.get("message"),
            payload.get("detail"),
        )
        message = next(
            (value for value in candidates if isinstance(value, str) and value.strip()), ""
        )
    if not message.strip():
        return None
    # Work on the complete bounded message before truncation, so a secret at
    # the display cutoff cannot leak its prefix. No language-specific patterns.
    private: set[str] = set()
    for value in private_values:
        if not value:
            continue
        private.update((value, quote(value, safe=""), quote_plus(value, safe="")))
        if "://" in value:
            try:
                hostname = urlsplit(value).hostname
            except ValueError:
                # A key can contain URL-like punctuation without being a URL.
                hostname = None
            if hostname:
                private.add(hostname)
    for value in sorted(private, key=len, reverse=True):
        message = message.replace(value, "[redacted]")
    message = _CONTROL.sub("", _URL.sub("[redacted URL]", message)).strip()
    if not message:
        return None
    return (
        message[: MAX_ERROR_MESSAGE_CHARS - 1] + "…"
        if len(message) > MAX_ERROR_MESSAGE_CHARS
        else message
    )
