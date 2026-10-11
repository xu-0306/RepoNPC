"""Privacy projection for complete provider-defined public summary paragraphs."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from urllib.parse import quote, quote_plus, unquote, urlsplit

MAX_SUMMARY_CHARACTERS = 4096
MAX_SUMMARY_PARAGRAPHS = 8
_COPY_WINDOW = 32
_URL = re.compile(r"(?:https?://|www\.)", re.IGNORECASE)


def _normalized(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", unquote(value)).casefold().split())


class PublicSummaryFilter:
    """Suppress unsafe paragraphs before any publication or truncation.

    Provider summaries remain unverified prose, never grounded answers. Known
    secrets and copied prompt spans are blocked; this is defense in depth, not
    an assertion that arbitrary paraphrased leakage can be recognized.
    """

    def __init__(self, prompts: Iterable[str], private_values: Iterable[str | None]) -> None:
        normalized_prompts = tuple(_normalized(value) for value in prompts if value)
        self._copies = {
            prompt[index : index + _COPY_WINDOW]
            for prompt in normalized_prompts
            for index in range(max(0, len(prompt) - _COPY_WINDOW + 1))
        }
        self._short_prompts = tuple(
            prompt for prompt in normalized_prompts if 8 <= len(prompt) < _COPY_WINDOW
        )
        self._private: set[str] = set()
        for value in private_values:
            if not value:
                continue
            for variant in (value, quote(value, safe=""), quote_plus(value, safe="")):
                self._private.add(_normalized(variant))
            hostname = urlsplit(value).hostname if "://" in value else None
            if hostname:
                self._private.add(_normalized(hostname))
        self._characters = 0
        self._paragraphs = 0
        self._suppressed = False

    def project(self, text: object) -> str | None:
        if self._suppressed or not isinstance(text, str) or not text.strip():
            return None
        normalized = _normalized(text)
        if (
            len(text) > MAX_SUMMARY_CHARACTERS
            or _URL.search(text)
            or _URL.search(normalized)
            or any(
                unicodedata.category(char).startswith("C") and char not in "\n\t" for char in text
            )
            or any(value in normalized for value in self._private | set(self._short_prompts))
            or any(
                normalized[index : index + _COPY_WINDOW] in self._copies
                for index in range(max(0, len(normalized) - _COPY_WINDOW + 1))
            )
        ):
            self._suppressed = True
            return None
        # Never truncate an unsafe paragraph into an apparently safe prefix.
        if (
            self._paragraphs >= MAX_SUMMARY_PARAGRAPHS
            or self._characters + len(text) > MAX_SUMMARY_CHARACTERS
        ):
            return None
        self._paragraphs += 1
        self._characters += len(text)
        return text
