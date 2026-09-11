"""Bounded injectable HTTP transport for configured model providers."""

from __future__ import annotations

import ipaddress
import socket
import ssl
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from http.client import HTTPConnection, HTTPException, HTTPMessage, HTTPSConnection
from typing import IO, Protocol, cast
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener  # noqa: F401

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
    """Production stdlib transport with pinned, policy-checked destinations."""

    def __init__(
        self,
        *,
        max_response_bytes: int = 2 * 1024 * 1024,
        resolver: Callable[..., list[tuple[object, ...]]] | None = None,
    ) -> None:
        if isinstance(max_response_bytes, bool) or max_response_bytes <= 0:
            raise ValueError("provider response limit must be positive")
        self._max_response_bytes = max_response_bytes
        self._resolver = cast(
            Callable[..., list[tuple[object, ...]]], resolver or socket.getaddrinfo
        )

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
        connection, target = self._connection(url, timeout)
        try:
            connection.request(method, target, body=body, headers=dict(headers))
            response = connection.getresponse()
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
        except TimeoutError as exc:
            raise ProviderError(ProviderFailureCode.TIMEOUT) from exc
        except (HTTPException, OSError) as exc:
            raise ProviderError(ProviderFailureCode.UNAVAILABLE) from exc
        finally:
            connection.close()

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
        connection, target = self._connection(url, timeout)
        consumed = 0
        try:
            connection.request(method, target, body=body, headers=dict(headers))
            response = connection.getresponse()
            if response.status >= 300:
                return int(response.status)
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
        except TimeoutError as exc:
            raise ProviderError(ProviderFailureCode.TIMEOUT) from exc
        except (HTTPException, OSError) as exc:
            raise ProviderError(ProviderFailureCode.UNAVAILABLE) from exc
        finally:
            connection.close()

    def _connection(self, url: str, timeout: float) -> tuple[HTTPConnection, str]:
        try:
            parsed = urlsplit(url)
            hostname = parsed.hostname
            if (
                parsed.scheme not in {"http", "https"}
                or hostname is None
                or parsed.username is not None
                or parsed.password is not None
                or parsed.fragment
            ):
                raise ValueError
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            address = _resolve_provider_destination(
                hostname,
                port,
                resolver=self._resolver,
                allow_private=_is_private_provider_host(hostname),
            )
            target = parsed.path or "/"
            if parsed.query:
                target = f"{target}?{parsed.query}"
            if parsed.scheme == "https":
                return _PinnedHTTPSConnection(hostname, port, address, timeout), target
            return _PinnedHTTPConnection(hostname, port, address, timeout), target
        except ProviderError:
            raise
        except (OSError, ValueError, TypeError):
            raise ProviderError(ProviderFailureCode.UNAVAILABLE) from None


class _PinnedHTTPConnection(HTTPConnection):
    def __init__(
        self,
        hostname: str,
        port: int,
        address: tuple[int, int, int, tuple[object, ...]],
        timeout: float,
    ) -> None:
        super().__init__(hostname, port, timeout=timeout)
        self._provider_address = address

    def connect(self) -> None:
        family, socktype, protocol, sockaddr = self._provider_address
        sock = socket.socket(family, socktype, protocol)
        try:
            sock.settimeout(self.timeout)
            sock.connect(sockaddr)
            self.sock = sock
        except Exception:
            sock.close()
            raise


class _PinnedHTTPSConnection(HTTPSConnection):
    def __init__(
        self,
        hostname: str,
        port: int,
        address: tuple[int, int, int, tuple[object, ...]],
        timeout: float,
    ) -> None:
        context = ssl.create_default_context()
        super().__init__(hostname, port, timeout=timeout, context=context)
        self._provider_address = address
        self._provider_context = context

    def connect(self) -> None:
        family, socktype, protocol, sockaddr = self._provider_address
        sock = socket.socket(family, socktype, protocol)
        try:
            sock.settimeout(self.timeout)
            sock.connect(sockaddr)
            self.sock = self._provider_context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


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


def _resolve_provider_destination(
    hostname: str,
    port: int,
    *,
    resolver: Callable[..., list[tuple[object, ...]]],
    allow_private: bool,
) -> tuple[int, int, int, tuple[object, ...]]:
    """Resolve once, reject the full set if any address violates egress policy."""

    try:
        resolved = resolver(hostname, port, type=socket.SOCK_STREAM)
        candidates: list[tuple[int, int, int, tuple[object, ...]]] = []
        for item in resolved:
            family = int(cast(int, item[0]))
            socktype = int(cast(int, item[1]))
            protocol = int(cast(int, item[2]))
            sockaddr: tuple[object, ...] = tuple(cast(tuple[object, ...], item[4]))
            address = ipaddress.ip_address(str(sockaddr[0]))
            candidate = (
                address.ipv4_mapped
                if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped
                else address
            )
            if (
                family not in {socket.AF_INET, socket.AF_INET6}
                or candidate.is_link_local
                or candidate.is_multicast
                or candidate.is_unspecified
                or candidate.is_reserved
                or (not allow_private and not candidate.is_global)
            ):
                raise ProviderError(ProviderFailureCode.UNAVAILABLE)
            candidates.append((family, socktype, protocol, sockaddr))
    except ProviderError:
        raise
    except (OSError, ValueError, IndexError, TypeError):
        raise ProviderError(ProviderFailureCode.UNAVAILABLE) from None
    if not candidates:
        raise ProviderError(ProviderFailureCode.UNAVAILABLE)
    return candidates[0]


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
