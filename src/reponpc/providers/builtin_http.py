"""Pinned, credential-free streaming download from the official model source."""

from __future__ import annotations

import socket
import time
from collections.abc import Iterator
from contextlib import contextmanager
from http.client import HTTPConnection, HTTPException, HTTPResponse
from typing import Any, BinaryIO, cast
from urllib.parse import urljoin, urlsplit

from reponpc.providers.builtin_artifacts import BuiltinArtifactFile, load_builtin_manifest
from reponpc.providers.builtin_download import BuiltinDownloadError, DownloadResponse
from reponpc.providers.contracts import ProviderError
from reponpc.providers.http_transport import _PinnedHTTPSConnection, _resolve_provider_destination


class _DeadlineStream:
    def __init__(self, response: HTTPResponse) -> None:
        self._response = response
        self._deadline = time.monotonic() + 21_600

    def read(self, size: int = -1) -> bytes:
        if size < 1 or size > 1024 * 1024 or time.monotonic() >= self._deadline:
            raise BuiltinDownloadError("builtin_download_http")
        try:
            result = self._response.read(size)
            if time.monotonic() >= self._deadline:
                raise BuiltinDownloadError("builtin_download_http")
            return result
        except HTTPException, OSError:
            raise BuiltinDownloadError("builtin_download_http") from None


class PinnedBuiltinHttpTransport:
    """No owner URL, credentials, proxy environment, cookies or model network access.

    Only the pinned manifest constructs the first URL. Hugging Face redirects
    to its public storage hosts; each hop is HTTPS and independently DNS-pinned.
    Signed redirect URLs remain local to this request and are never exposed.
    """

    def _connection(self, url: str) -> tuple[HTTPConnection, str]:
        try:
            parsed = urlsplit(url)
            host = parsed.hostname
            if (
                parsed.scheme != "https"
                or host is None
                or not (
                    host == "huggingface.co"
                    or host.endswith(".huggingface.co")
                    or host == "hf.co"
                    or host.endswith(".hf.co")
                )
                or parsed.port not in {None, 443}
                or parsed.username is not None
                or parsed.password is not None
                or parsed.fragment
                or any(not 33 <= ord(char) <= 126 for char in url)
                or len(url) > 16_384
            ):
                raise ValueError
            address = _resolve_provider_destination(
                host, 443, resolver=cast(Any, socket.getaddrinfo), allow_private=False
            )
            target = parsed.path or "/"
            if parsed.query:
                target += "?" + parsed.query
            return _PinnedHTTPSConnection(host, 443, address, 15.0), target
        except ValueError, OSError, ProviderError:
            raise BuiltinDownloadError("builtin_download_http") from None

    @contextmanager
    def open(self, artifact: BuiltinArtifactFile, *, offset: int) -> Iterator[DownloadResponse]:
        manifest = load_builtin_manifest()
        if (
            artifact not in manifest.files
            or type(offset) is not int
            or not 0 <= offset < artifact.bytes
        ):
            raise BuiltinDownloadError("builtin_download_http")
        url = (
            f"https://huggingface.co/{manifest.model_id}/resolve/{manifest.revision}/onnx/"
            f"{artifact.name}"
        )
        headers = {"Accept-Encoding": "identity", "User-Agent": "RepoNPC/1.0"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        for hop in range(5):
            connection, target = self._connection(url)
            try:
                connection.request("GET", target, headers=headers)
                response = connection.getresponse()
                items = response.getheaders()
                names = [name.lower() for name, _value in items]
                if len(names) != len(set(names)):
                    raise BuiltinDownloadError("builtin_download_http")
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader("Location")
                    if not location or hop == 4:
                        raise BuiltinDownloadError("builtin_download_http")
                    url = urljoin(url, location)
                    continue
                yield DownloadResponse(
                    status=response.status,
                    headers={name.lower(): value for name, value in items},
                    stream=cast(BinaryIO, _DeadlineStream(response)),
                )
                return
            except HTTPException, OSError, ValueError, UnicodeError:
                raise BuiltinDownloadError("builtin_download_http") from None
            finally:
                connection.close()
