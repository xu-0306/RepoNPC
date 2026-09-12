"""Structural extraction must not depend on provider names or error vocabulary."""

import json
from urllib.parse import quote

import pytest

from reponpc.providers.contracts import ProviderError, ProviderFailureCode
from reponpc.providers.error_messages import MAX_ERROR_MESSAGE_CHARS, provider_error_message


@pytest.mark.parametrize(
    "message",
    [
        "Credit check failed: account 82.",
        "容量が足りません。",
        "服務繁忙，請稍後。",  # noqa: RUF001 - preserve the provider's original language.
        "Échec du nœud Ω-7.",
        "xZ9_28!\nnext line",
    ],
)
@pytest.mark.parametrize("shape", ["nested", "error", "message", "detail", "plain"])
def test_preserves_unknown_messages_and_languages(message, shape):
    payload = {"error": {"message": message}} if shape == "nested" else {shape: message}
    body = message.encode() if shape == "plain" else json.dumps(payload).encode()
    assert provider_error_message(body, {"Content-Type": "text/plain; charset=utf-8"}) == message


@pytest.mark.parametrize(
    "body,headers",
    [
        (b"", {}),
        (b"null", {}),
        (b"[]", {}),
        (b'"unexpected"', {}),
        (b'{"error":{"message":42}}', {}),
        (b'{"error":{"message":" "}}', {}),
        (b'{"metadata":{"message":"not the error"}}', {}),
        (b"<html>private upstream page</html>", {"content-type": "text/plain"}),
        (b"not json", {}),
        (b"\xff", {"content-type": "text/plain"}),
        pytest.param(b"x" * 65537, {"content-type": "text/plain"}, id="oversize-body"),
    ],
)
def test_unsupported_responses_have_no_invented_message(body, headers):
    assert provider_error_message(body, headers) is None


def test_redacts_known_credentials_urls_and_encoded_values_before_truncation():
    key = "synthetic-key/+&=canary"
    url = "https://private.example.test/service"
    message = f"Rejected {key} {quote(key, safe='')} {url} private.example.test https://other.test/path?secret=123"
    result = provider_error_message(
        json.dumps({"error": {"message": message}, "metadata": "ignored"}).encode(),
        {},
        private_values=(key, url),
    )
    assert result == "Rejected [redacted] [redacted] [redacted] [redacted] [redacted URL]"
    crossing = "a" * (MAX_ERROR_MESSAGE_CHARS - 5) + key + "x" * 30
    bounded = provider_error_message(
        json.dumps({"error": crossing}).encode(), {}, private_values=(key,)
    )
    assert len(bounded) == MAX_ERROR_MESSAGE_CHARS
    assert "synt" not in bounded
    assert bounded.endswith("…")


def test_exception_text_never_contains_provider_message():
    error = ProviderError(
        ProviderFailureCode.UNAVAILABLE,
        upstream_status=503,
        upstream_message="Original private diagnostic",
    )
    assert error.upstream_message == "Original private diagnostic"
    assert "diagnostic" not in str(error) + repr(error)


def test_preserves_text_as_data_and_removes_display_controls():
    message = '<script>alert("data")</script>\n\u202efailure\x00'
    assert (
        provider_error_message(json.dumps({"message": message}).encode(), {})
        == '<script>alert("data")</script>\nfailure'
    )


def test_escaped_invalid_unicode_and_url_like_key_do_not_lose_http_diagnostic():
    key = "synthetic://[malformed-key"
    body = json.dumps({"error": f"Failure\ud800: {key}"}).encode()
    assert provider_error_message(body, {}, private_values=(key,)) == "Failure: [redacted]"
