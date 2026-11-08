"""Pinned, credential-free streaming downloads from fixed official sources.

Two transports share one hardened core: the built-in embedding model from
Hugging Face, and the GPU runtime wheels from files.pythonhosted.org (ADR-084).
"""

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
from reponpc.providers.gpu_runtime import load_gpu_runtime_manifest
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


class _PinnedTransport:
    """No owner URL, credentials, proxy environment, cookies or model network access.

    Only a pinned manifest constructs the first URL. Each hop is HTTPS and
    independently DNS-pinned. Signed redirect URLs remain local to this request
    and are never exposed. A subclass names its allowed hosts and its URL.
    """

    _max_redirects = 4

    def _host_allowed(self, host: str) -> bool:
        raise NotImplementedError

    def _pinned_url(self, artifact: BuiltinArtifactFile) -> str:
        raise NotImplementedError

    def _connection(self, url: str) -> tuple[HTTPConnection, str]:
        try:
            parsed = urlsplit(url)
            host = parsed.hostname
            if (
                parsed.scheme != "https"
                or host is None
                or not self._host_allowed(host)
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
        url = self._pinned_url(artifact)
        if type(offset) is not int or not 0 <= offset < artifact.bytes:
            raise BuiltinDownloadError("builtin_download_http")
        headers = {"Accept-Encoding": "identity", "User-Agent": "RepoNPC/1.0"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        for hop in range(self._max_redirects + 1):
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
                    if not location or hop == self._max_redirects:
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


class PinnedBuiltinHttpTransport(_PinnedTransport):
    """The built-in model files; Hugging Face redirects to its public storage hosts."""

    def _host_allowed(self, host: str) -> bool:
        return (
            host == "huggingface.co"
            or host.endswith(".huggingface.co")
            or host == "hf.co"
            or host.endswith(".hf.co")
        )

    def _pinned_url(self, artifact: BuiltinArtifactFile) -> str:
        manifest = load_builtin_manifest()
        if artifact not in manifest.files:
            raise BuiltinDownloadError("builtin_download_http")
        return (
            f"https://huggingface.co/{manifest.model_id}/resolve/{manifest.revision}/onnx/"
            f"{artifact.name}"
        )


class PinnedGpuWheelTransport(_PinnedTransport):
    """The GPU runtime wheels; the pinned URL is served directly, so a redirect is refused."""

    _max_redirects = 0

    def _host_allowed(self, host: str) -> bool:
        return host == "files.pythonhosted.org"

    def _pinned_url(self, artifact: BuiltinArtifactFile) -> str:
        for wheel in load_gpu_runtime_manifest().wheels:
            if (wheel.name, wheel.bytes, wheel.sha256) == (
                artifact.name,
                artifact.bytes,
                artifact.sha256,
            ):
                return wheel.url
        raise BuiltinDownloadError("builtin_download_http")
