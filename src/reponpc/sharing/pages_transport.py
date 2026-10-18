"""Public-only pinned HTTPS reads for owner-triggered Pages verification."""

from __future__ import annotations

import ipaddress
import math
import socket
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from http.client import HTTPException
from typing import cast
from urllib.parse import urlsplit

from reponpc.providers.contracts import ProviderError
from reponpc.providers.http_transport import (
    ProviderHttpResponse,
    _PinnedHTTPSConnection,
    _resolve_provider_destination,
)
from reponpc.sharing.manifest import SiteExportError, pages_target

# ponytail: four OS DNS calls bound stuck resolvers; use a resolver process if OS hangs matter.
_DNS_WORKERS = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pages-dns")
_DNS_SLOTS = threading.BoundedSemaphore(4)
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise SiteExportError("SHARING_VERIFICATION_UNAVAILABLE")
    return remaining


def _public_ip(value: object) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    address = ipaddress.ip_address(str(value))
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    if (
        not address.is_global
        or address.is_multicast
        or address.is_reserved
        or address.is_link_local
        or address.is_unspecified
    ):
        raise SiteExportError("SHARING_VERIFICATION_FAILED")
    return address


def _check_peer(sock: socket.socket, expected: tuple[object, ...]) -> None:
    peer = sock.getpeername()
    if _public_ip(peer[0]) != _public_ip(expected[0]) or peer[1] != 443:
        raise SiteExportError("SHARING_VERIFICATION_FAILED")


class _PagesConnection(_PinnedHTTPSConnection):
    def __init__(
        self,
        hostname: str,
        address: tuple[int, int, int, tuple[object, ...]],
        deadline: float,
    ) -> None:
        super().__init__(hostname, 443, address, _remaining(deadline))
        self._deadline = deadline

    def connect(self) -> None:
        family, socktype, protocol, sockaddr = self._provider_address
        sock = socket.socket(family, socktype, protocol)
        try:
            sock.settimeout(_remaining(self._deadline))
            sock.connect(sockaddr)
            _check_peer(sock, sockaddr)
            sock.settimeout(_remaining(self._deadline))
            self.sock = self._provider_context.wrap_socket(sock, server_hostname=self.host)
            _check_peer(self.sock, sockaddr)
        except BaseException:
            sock.close()
            if self.sock is not None:
                self.sock.close()
            raise


def fetch_pages_resource(
    url: str,
    *,
    pages_origin: str,
    deadline: float,
    max_response_bytes: int,
) -> ProviderHttpResponse:
    """Fetch one exact Pages resource; callers share a deadline across both reads."""

    if not isinstance(url, str) or any(
        character.isspace() or ord(character) < 32 for character in url
    ):
        raise SiteExportError("SHARING_CONFIGURATION_INVALID")
    pages_target(url, pages_origin)
    parsed = urlsplit(url)
    if parsed.scheme + "://" + parsed.netloc != pages_origin:
        raise SiteExportError("SHARING_CONFIGURATION_INVALID")
    if (
        isinstance(deadline, bool)
        or not math.isfinite(deadline)
        or not 0 < deadline - time.monotonic() <= 30
        or isinstance(max_response_bytes, bool)
        or not 0 < max_response_bytes <= _MAX_RESPONSE_BYTES
    ):
        raise SiteExportError("SHARING_VERIFICATION_UNAVAILABLE")
    if not _DNS_SLOTS.acquire(blocking=False):
        raise SiteExportError("SHARING_VERIFICATION_UNAVAILABLE")
    try:
        future = _DNS_WORKERS.submit(
            _resolve_provider_destination,
            cast(str, parsed.hostname),
            443,
            resolver=cast(Callable[..., list[tuple[object, ...]]], socket.getaddrinfo),
            allow_private=False,
        )
    except RuntimeError:
        _DNS_SLOTS.release()
        raise SiteExportError("SHARING_VERIFICATION_UNAVAILABLE") from None
    future.add_done_callback(lambda _future: _DNS_SLOTS.release())
    try:
        address = future.result(timeout=_remaining(deadline))
    except TimeoutError, ProviderError, OSError, ValueError:
        future.cancel()
        raise SiteExportError("SHARING_VERIFICATION_UNAVAILABLE") from None
    if address[1] != socket.SOCK_STREAM or address[3][1] != 443:
        raise SiteExportError("SHARING_VERIFICATION_FAILED")

    connection: _PagesConnection | None = None
    timer: threading.Timer | None = None
    expired = threading.Event()
    try:
        connection = _PagesConnection(cast(str, parsed.hostname), address, deadline)
        connection.connect()
        network_socket = connection.sock
        if network_socket is None:
            raise SiteExportError("SHARING_VERIFICATION_FAILED")

        def interrupt() -> None:
            expired.set()
            with suppress(OSError, ValueError):
                network_socket.shutdown(socket.SHUT_RDWR)

        # Closing the actual socket also bounds drip-fed headers and chunked bodies.
        timer = threading.Timer(_remaining(deadline), interrupt)
        timer.daemon = True
        timer.start()
        network_socket.settimeout(_remaining(deadline))
        connection.request(
            "GET",
            parsed.path or "/",
            headers={"Accept-Encoding": "identity", "Connection": "close"},
        )
        response = connection.getresponse()
        if response.status != 200:
            raise SiteExportError("SHARING_VERIFICATION_FAILED")
        length = response.getheader("Content-Length")
        if length is not None and (not length.isdecimal() or int(length) > max_response_bytes):
            raise SiteExportError("SHARING_VERIFICATION_FAILED")
        if response.getheader("Content-Encoding", "identity").casefold() != "identity":
            raise SiteExportError("SHARING_VERIFICATION_FAILED")
        payload = bytearray()
        while True:
            network_socket.settimeout(_remaining(deadline))
            chunk = response.read1(min(64 * 1024, max_response_bytes - len(payload) + 1))
            if not chunk:
                break
            payload.extend(chunk)
            if len(payload) > max_response_bytes:
                raise SiteExportError("SHARING_VERIFICATION_FAILED")
        _remaining(deadline)
        if expired.is_set() or (length is not None and len(payload) != int(length)):
            raise SiteExportError("SHARING_VERIFICATION_FAILED")
        return ProviderHttpResponse(
            status=200,
            headers={"content-type": response.getheader("Content-Type", "")},
            body=bytes(payload),
        )
    except SiteExportError:
        raise
    except HTTPException, OSError, ValueError:
        raise SiteExportError("SHARING_VERIFICATION_UNAVAILABLE") from None
    finally:
        if timer is not None:
            timer.cancel()
        if connection is not None:
            connection.close()
