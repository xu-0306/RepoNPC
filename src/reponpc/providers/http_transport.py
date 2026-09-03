"""Bounded injectable HTTP transport for configured model providers."""

from __future__ import annotations

import ipaddress
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from http.client import HTTPMessage
from typing import IO, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from reponpc.providers.contracts import ProviderError, ProviderFailureCode


@dataclass(frozen=True, slots=True)
class ProviderHttpResponse:
    """One bounded response without request URL or exception reflection."""

    status: int
    headers: Mapping[str, str]
    body: bytes


class ProviderHttpTransport(Protocol):
    """Injectable request boundary used by provider contract tests."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout: float,
    ) -> ProviderHttpResponse:
        """Issue one request inside the caller's remaining deadline."""


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> Request | None:
        del req, fp, code, msg, headers, newurl
        return None


class UrllibProviderHttpTransport:
    """Production stdlib transport that rejects redirects and bounds bodies."""

    def __init__(self, *, max_response_bytes: int = 2 * 1024 * 1024) -> None:
        if isinstance(max_response_bytes, bool) or max_response_bytes <= 0:
            raise ValueError("provider response limit must be positive")
        self._max_response_bytes = max_response_bytes

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout: float,
    ) -> ProviderHttpResponse:
        if not method or timeout <= 0:
            raise ProviderError(ProviderFailureCode.TIMEOUT)
        request = Request(url, data=body, headers=dict(headers), method=method)
        try:
            with build_opener(_RejectRedirects()).open(request, timeout=timeout) as response:
                payload = response.read(self._max_response_bytes + 1)
                if len(payload) > self._max_response_bytes:
                    raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
                return ProviderHttpResponse(
                    status=int(response.status),
                    headers=dict(response.headers.items()),
                    body=payload,
                )
        except ProviderError:
            raise
        except HTTPError as exc:
            payload = exc.read(self._max_response_bytes + 1)
            if len(payload) > self._max_response_bytes:
                payload = b""
            return ProviderHttpResponse(
                status=int(exc.code),
                headers=dict(exc.headers.items()),
                body=payload,
            )
        except TimeoutError as exc:
            raise ProviderError(ProviderFailureCode.TIMEOUT) from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise ProviderError(ProviderFailureCode.TIMEOUT) from exc
            raise ProviderError(ProviderFailureCode.UNAVAILABLE) from exc
        except OSError as exc:
            raise ProviderError(ProviderFailureCode.UNAVAILABLE) from exc

    def stream_lines(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout: float,
        cancelled: Callable[[], bool],
        on_line: Callable[[bytes], None],
    ) -> int:
        """Read a bounded NDJSON response while honoring cooperative cancellation."""

        if not method or timeout <= 0:
            raise ProviderError(ProviderFailureCode.TIMEOUT)
        request = Request(url, data=body, headers=dict(headers), method=method)
        consumed = 0
        try:
            with build_opener(_RejectRedirects()).open(request, timeout=timeout) as response:
                while True:
                    if cancelled():
                        raise InterruptedError
                    line = response.readline(min(64 * 1024, self._max_response_bytes) + 1)
                    if not line:
                        break
                    consumed += len(line)
                    if len(line) > 64 * 1024 or consumed > self._max_response_bytes:
                        raise ProviderError(ProviderFailureCode.INVALID_RESPONSE)
                    on_line(line)
                return int(response.status)
        except InterruptedError:
            raise
        except ProviderError:
            raise
        except HTTPError as exc:
            return int(exc.code)
        except TimeoutError as exc:
            raise ProviderError(ProviderFailureCode.TIMEOUT) from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise ProviderError(ProviderFailureCode.TIMEOUT) from exc
            raise ProviderError(ProviderFailureCode.UNAVAILABLE) from exc
        except OSError as exc:
            raise ProviderError(ProviderFailureCode.UNAVAILABLE) from exc


@dataclass(frozen=True, slots=True)
class ProviderOrigin:
    """One explicitly configured provider origin and optional fixed path prefix."""

    base_url: str = field(repr=False)
    allow_private_http: bool

    def __post_init__(self) -> None:
        parsed = urlsplit(self.base_url)
        if (
            not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.scheme not in {"http", "https"}
        ):
            raise ValueError("provider base URL is invalid")
        if parsed.scheme == "http" and not (
            self.allow_private_http and _is_private_provider_host(parsed.hostname)
        ):
            raise ValueError("insecure provider URL is not private")

    def endpoint(self, path: str) -> str:
        """Join an adapter-owned relative path without changing origin."""

        if not path or path.startswith("//"):
            raise ValueError("provider endpoint path is invalid")
        base = self.base_url.rstrip("/") + "/"
        result = urljoin(base, path.lstrip("/"))
        source = urlsplit(self.base_url)
        target = urlsplit(result)
        if (target.scheme, target.hostname, target.port) != (
            source.scheme,
            source.hostname,
            source.port,
        ):
            raise ValueError("provider endpoint changed origin")
        return result


def _is_private_provider_host(hostname: str) -> bool:
    normalized = hostname.rstrip(".").casefold()
    if normalized in {"localhost", "host.docker.internal"} or normalized.endswith(".local"):
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        # Docker Compose service names are single-label private network names.
        return "." not in normalized
    return address.is_private or address.is_loopback or address.is_link_local


def failure_for_status(status: int) -> ProviderFailureCode:
    """Normalize upstream HTTP status without inspecting or reflecting its body."""

    if status in {401, 403}:
        return ProviderFailureCode.AUTHENTICATION
    if status == 429:
        return ProviderFailureCode.RATE_LIMIT
    if status in {408, 504}:
        return ProviderFailureCode.TIMEOUT
    if 500 <= status <= 599:
        return ProviderFailureCode.UNAVAILABLE
    return ProviderFailureCode.INVALID_RESPONSE
