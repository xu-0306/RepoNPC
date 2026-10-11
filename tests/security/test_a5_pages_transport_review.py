"""Pages transport checks use synthetic DNS/sockets and make no public requests."""

from __future__ import annotations

import socket
import ssl
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from reponpc.sharing import pages_transport as transport
from reponpc.sharing.manifest import SiteExportError

ORIGIN = "https://fixture.github.io"
URL = ORIGIN + "/portfolio/export-manifest.json"


def _dns(address: str) -> tuple[object, ...]:
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    peer = (address, 443, 0, 0) if family == socket.AF_INET6 else (address, 443)
    return (family, socket.SOCK_STREAM, 6, "", peer)


def _fetch(*, limit: int = 100, duration: float = 1) -> object:
    return transport.fetch_pages_resource(
        URL, pages_origin=ORIGIN, deadline=time.monotonic() + duration, max_response_bytes=limit
    )


class FixtureSocket:
    def __init__(self, peer: tuple[str, int]) -> None:
        self.peer = peer
        self.connected = None
        self.shutdown_event = threading.Event()
        self.closed = False

    def connect(self, address: object) -> None:
        self.connected = address

    def settimeout(self, _timeout: float) -> None:
        pass

    def getpeername(self) -> tuple[str, int]:
        return self.peer

    def shutdown(self, _how: int) -> None:
        self.shutdown_event.set()

    def close(self) -> None:
        self.closed = True


class FixtureResponse:
    status = 200

    def __init__(self, body: bytes = b"public fixture") -> None:
        self.body = body
        self.offset = 0
        self.reads = 0
        self.headers = {"Content-Type": "application/json"}

    def getheader(self, key: str, default: str | None = None) -> str | None:
        return self.headers.get(key, default)

    def read1(self, count: int) -> bytes:
        self.reads += 1
        chunk = self.body[self.offset : self.offset + count]
        self.offset += len(chunk)
        return chunk


def _wire(
    monkeypatch: pytest.MonkeyPatch,
    *,
    peer: tuple[str, int] = ("8.8.8.8", 443),
    response: FixtureResponse | None = None,
) -> tuple[FixtureSocket, list[str], list[object], FixtureResponse]:
    sock = FixtureSocket(peer)
    names: list[str] = []
    requests: list[object] = []
    reply = response or FixtureResponse()

    class Context:
        def wrap_socket(self, value: FixtureSocket, *, server_hostname: str) -> FixtureSocket:
            names.append(server_hostname)
            return value

    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [_dns("8.8.8.8")])
    monkeypatch.setattr(socket, "socket", lambda *_args, **_kwargs: sock)
    monkeypatch.setattr(ssl, "create_default_context", Context)
    monkeypatch.setattr(
        transport._PagesConnection,
        "request",
        lambda _self, *args, **kwargs: requests.append((args, kwargs)),
    )
    monkeypatch.setattr(transport._PagesConnection, "getresponse", lambda _self: reply)
    return sock, names, requests, reply


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/",
        "https://other.github.io/",
        ORIGIN + ":443/",
        URL + "?secret=x",
        ORIGIN + "/%2e%2e/",
    ],
)
def test_unconfigured_destination_never_resolves(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    def unexpected(*_args: object, **_kwargs: object) -> object:
        pytest.fail("invalid URL reached DNS")

    monkeypatch.setattr(socket, "getaddrinfo", unexpected)
    with pytest.raises(SiteExportError):
        transport.fetch_pages_resource(
            url, pages_origin=ORIGIN, deadline=time.monotonic() + 1, max_response_bytes=100
        )


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "::ffff:10.0.0.1"])
def test_one_private_dns_candidate_rejects_entire_set(
    monkeypatch: pytest.MonkeyPatch, address: str
) -> None:
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *_args, **_kwargs: [_dns("8.8.8.8"), _dns(address)]
    )
    monkeypatch.setattr(
        socket, "socket", lambda *_args, **_kwargs: pytest.fail("private DNS reached socket")
    )
    with pytest.raises(SiteExportError):
        _fetch()


@pytest.mark.parametrize("peer", [("127.0.0.1", 443), ("1.1.1.1", 443), ("8.8.8.8", 8443)])
def test_actual_peer_is_checked_before_tls_or_http(
    monkeypatch: pytest.MonkeyPatch, peer: tuple[str, int]
) -> None:
    sock, names, requests, _reply = _wire(monkeypatch, peer=peer)
    with pytest.raises(SiteExportError):
        _fetch()
    assert sock.closed and not names and not requests


def test_original_tls_name_pinned_address_and_credential_free_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sock, names, requests, reply = _wire(monkeypatch)
    result = _fetch()
    assert result.body == reply.body
    assert sock.connected == ("8.8.8.8", 443)
    assert names == ["fixture.github.io"]
    assert requests == [
        (
            ("GET", "/portfolio/export-manifest.json"),
            {"headers": {"Accept-Encoding": "identity", "Connection": "close"}},
        )
    ]
    assert sock.closed


def test_redirect_is_not_followed_or_read(monkeypatch: pytest.MonkeyPatch) -> None:
    reply = FixtureResponse()
    reply.status = 302
    reply.headers["Location"] = "https://127.0.0.1/admin"
    _sock, _names, requests, _reply = _wire(monkeypatch, response=reply)
    with pytest.raises(SiteExportError):
        _fetch()
    assert len(requests) == 1 and reply.reads == 0


@pytest.mark.parametrize("declared", [False, True])
def test_response_size_is_bounded_with_or_without_content_length(
    monkeypatch: pytest.MonkeyPatch, declared: bool
) -> None:
    reply = FixtureResponse(b"x" * 101)
    if declared:
        reply.headers["Content-Length"] = "101"
    _wire(monkeypatch, response=reply)
    with pytest.raises(SiteExportError):
        _fetch(limit=100)
    if declared:
        assert reply.reads == 0
    else:
        assert reply.offset == 101


@pytest.mark.parametrize("phase", ["headers", "body"])
def test_total_deadline_interrupts_slow_headers_and_body(
    monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    sock, _names, _requests, reply = _wire(monkeypatch)

    def blocked(*_args: object) -> object:
        assert sock.shutdown_event.wait(1), "total deadline did not interrupt the socket"
        raise TimeoutError

    if phase == "headers":
        monkeypatch.setattr(transport._PagesConnection, "getresponse", blocked)
    else:
        monkeypatch.setattr(reply, "read1", blocked)
    started = time.monotonic()
    with pytest.raises(SiteExportError):
        _fetch(duration=0.08)
    assert sock.shutdown_event.is_set() and sock.closed
    assert time.monotonic() - started < 0.5


def test_stuck_dns_has_bounded_workers_and_returns_at_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = threading.Event()
    all_started = threading.Event()
    lock = threading.Lock()
    count = 0

    def blocked_dns(*_args: object, **_kwargs: object) -> list[tuple[object, ...]]:
        nonlocal count
        with lock:
            count += 1
            if count == 4:
                all_started.set()
        assert release.wait(1)
        return [_dns("8.8.8.8")]

    monkeypatch.setattr(socket, "getaddrinfo", blocked_dns)
    try:
        with ThreadPoolExecutor(max_workers=4) as callers:
            futures = [callers.submit(_fetch, duration=0.15) for _ in range(4)]
            assert all_started.wait(0.5)
            with pytest.raises(SiteExportError):
                _fetch()
            for future in futures:
                with pytest.raises(SiteExportError):
                    future.result(timeout=0.5)
            assert count == 4
    finally:
        release.set()
