"""Official-source HTTP streaming safety without live DNS or socket access."""

from __future__ import annotations

import io
import socket
from http.client import HTTPException
from typing import Any

import pytest

import reponpc.providers.builtin_http as builtin_http
from reponpc.providers.builtin_artifacts import BuiltinArtifactFile, load_builtin_manifest
from reponpc.providers.builtin_download import BuiltinDownloadError
from reponpc.providers.builtin_http import PinnedBuiltinHttpTransport


class Response:
    def __init__(self, status: int = 200, headers: list[tuple[str, str]] | None = None) -> None:
        self.status = status
        self.headers = headers or []
        self.body = io.BytesIO(b"example-nonsecret-body")
        self.reads: list[int] = []
        self.failure: Exception | None = None
        self.after_read: Any = lambda: None

    def getheader(self, name: str) -> str | None:
        values = [value for key, value in self.headers if key.lower() == name.lower()]
        return ", ".join(values) if values else None

    def getheaders(self) -> list[tuple[str, str]]:
        return self.headers[:]

    def read(self, size: int) -> bytes:
        assert 0 < size <= 1024 * 1024
        self.reads.append(size)
        if self.failure is not None:
            raise self.failure
        result = self.body.read(size)
        self.after_read()
        return result


class Connection:
    def __init__(self, response: Response) -> None:
        self.response = response
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.closed = 0
        self.request_failure: Exception | None = None
        self.response_failure: Exception | None = None

    def request(self, method: str, target: str, *, headers: dict[str, str]) -> None:
        self.requests.append((method, target, dict(headers)))
        if self.request_failure is not None:
            raise self.request_failure

    def getresponse(self) -> Response:
        if self.response_failure is not None:
            raise self.response_failure
        return self.response

    def close(self) -> None:
        self.closed += 1


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch: Any) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("HTTP transport test attempted real DNS or socket access")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


def public_dns(address: str = "8.8.8.8") -> list[tuple[Any, ...]]:
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]


def pinned_connections(
    monkeypatch: Any, responses: list[Response]
) -> tuple[list[Connection], list[tuple[Any, ...]], list[tuple[str, int]]]:
    connections: list[Connection] = []
    pins: list[tuple[Any, ...]] = []
    resolutions: list[tuple[str, int]] = []

    def resolve(host: str, port: int, *, type: int) -> list[tuple[Any, ...]]:
        assert type == socket.SOCK_STREAM
        resolutions.append((host, port))
        return public_dns()

    def connect(host: str, port: int, address: Any, timeout: float) -> Connection:
        connection = Connection(responses[len(connections)])
        connections.append(connection)
        pins.append((host, port, address, timeout))
        return connection

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(builtin_http, "_PinnedHTTPSConnection", connect)
    return connections, pins, resolutions


def artifact() -> BuiltinArtifactFile:
    return load_builtin_manifest().files[0]


def assert_safe(error: BuiltinDownloadError) -> None:
    assert error.code == "builtin_download_http"
    assert str(error) == "built-in embedding download failed"
    assert error.__cause__ is None


@pytest.mark.parametrize("offset", [0, 1])
def test_first_request_uses_sole_manifest_and_credential_free_streaming_headers(
    monkeypatch: Any, offset: int
) -> None:
    response = Response()
    connections, pins, resolutions = pinned_connections(monkeypatch, [response])
    monkeypatch.setenv("HTTPS_PROXY", "http://example-nonsecret.invalid:9999")
    manifest = load_builtin_manifest()
    with PinnedBuiltinHttpTransport().open(artifact(), offset=offset) as result:
        assert result.status == 200
        assert not response.reads
        assert result.stream.read(2) == b"ex"
        assert response.reads == [2]
        assert connections[0].closed == 0
        assert "example-nonsecret-body" not in repr(result)
    assert connections[0].closed == 1
    method, target, headers = connections[0].requests[0]
    assert method == "GET"
    assert target == f"/{manifest.model_id}/resolve/{manifest.revision}/onnx/{artifact().name}"
    expected_headers = {"Accept-Encoding": "identity", "User-Agent": "RepoNPC/1.0"}
    if offset:
        expected_headers["Range"] = "bytes=1-"
    assert headers == expected_headers
    assert resolutions == [("huggingface.co", 443)]
    assert pins == [("huggingface.co", 443, (*public_dns()[0][:3], public_dns()[0][4]), 15.0)]


@pytest.mark.parametrize("offset", [-1, True, 1.5, "1", artifact().bytes, artifact().bytes + 1])
def test_invalid_offsets_fail_before_dns(offset: Any) -> None:
    with (
        pytest.raises(BuiltinDownloadError) as error,
        PinnedBuiltinHttpTransport().open(artifact(), offset=offset),
    ):
        pytest.fail("invalid offset was accepted")
    assert_safe(error.value)


def test_unknown_or_altered_manifest_record_cannot_select_first_url() -> None:
    supplied = artifact().model_copy(update={"sha256": "0" * 64})
    with (
        pytest.raises(BuiltinDownloadError) as error,
        PinnedBuiltinHttpTransport().open(supplied, offset=0),
    ):
        pytest.fail("non-pinned artifact was accepted")
    assert_safe(error.value)


@pytest.mark.parametrize(
    "host", ["huggingface.co", "cdn-lfs.huggingface.co", "hf.co", "cas-bridge.xethub.hf.co"]
)
def test_owned_root_and_dot_boundary_suffix_hosts_are_dns_pinned(
    monkeypatch: Any, host: str
) -> None:
    connections, pins, resolutions = pinned_connections(monkeypatch, [Response()])
    connection, target = PinnedBuiltinHttpTransport()._connection(
        f"https://{host}:443/file?X-Amz-Signature=example-nonsecret"
    )
    assert connection is connections[0]
    assert target == "/file?X-Amz-Signature=example-nonsecret"
    assert resolutions == [(host, 443)]
    assert pins[0][0:2] == (host, 443)
    connection.close()


@pytest.mark.parametrize(
    "url",
    [
        "http://huggingface.co/file",
        "https://evil-huggingface.co/file",
        "https://huggingface.co.evil.invalid/file",
        "https://evilhf.co/file",
        "https://hf.co.evil.invalid/file",
        "https://huggingface.co./file",
        "https://huggingface.co:444/file",
        "https://user:example-nonsecret@huggingface.co/file",
        "https://huggingface.co@127.0.0.1/file",
        "https://huggingface.co/file#example-nonsecret",
        "https://huggingface.co/file\nheader",
        "https://huggingface.co/file\x7f",
        "https://huggingface.co/file\x85",
        "https://huggingface.co/file name",
        "https://huggingface.co:invalid/file",
        "https://huggingface.co/" + "a" * 16384,
    ],
)
def test_hostile_urls_are_rejected_before_dns(url: str) -> None:
    with pytest.raises(BuiltinDownloadError) as error:
        PinnedBuiltinHttpTransport()._connection(url)
    assert_safe(error.value)


@pytest.mark.parametrize(
    "addresses", [["127.0.0.1"], ["10.0.0.1"], ["169.254.1.2"], ["8.8.8.8", "10.0.0.1"], []]
)
def test_private_or_mixed_dns_is_rejected_without_connection(
    monkeypatch: Any, addresses: list[str]
) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [item for address in addresses for item in public_dns(address)],
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("unsafe DNS address was used to construct a connection")

    monkeypatch.setattr(builtin_http, "_PinnedHTTPSConnection", forbidden)
    with pytest.raises(BuiltinDownloadError) as error:
        PinnedBuiltinHttpTransport()._connection("https://huggingface.co/file")
    assert_safe(error.value)


def test_every_redirect_is_separately_dns_pinned_and_all_hops_close(monkeypatch: Any) -> None:
    redirect = Response(
        302, [("Location", "https://cas-bridge.xethub.hf.co/file?sig=example-nonsecret")]
    )
    final = Response(206, [("Content-Range", "bytes 1-3/4")])
    connections, _, resolutions = pinned_connections(monkeypatch, [redirect, final])
    with PinnedBuiltinHttpTransport().open(artifact(), offset=1) as result:
        assert result.status == 206
        assert result.headers["content-range"] == "bytes 1-3/4"
        assert not redirect.reads and not final.reads
        assert connections[0].closed == 1 and connections[1].closed == 0
    assert resolutions == [("huggingface.co", 443), ("cas-bridge.xethub.hf.co", 443)]
    assert all(connection.closed == 1 for connection in connections)
    assert all(connection.requests[0][2].get("Range") == "bytes=1-" for connection in connections)
    assert connections[1].requests[0][1] == "/file?sig=example-nonsecret"


@pytest.mark.parametrize("redirect_count", [4, 5])
def test_redirect_limit_allows_four_hops_and_closes_fifth_redirect(
    monkeypatch: Any, redirect_count: int
) -> None:
    responses = [Response(302, [("Location", f"/hop-{index}")]) for index in range(redirect_count)]
    responses.append(Response())
    connections, _, _ = pinned_connections(monkeypatch, responses)
    if redirect_count == 4:
        with PinnedBuiltinHttpTransport().open(artifact(), offset=0):
            pass
    else:
        with (
            pytest.raises(BuiltinDownloadError) as error,
            PinnedBuiltinHttpTransport().open(artifact(), offset=0),
        ):
            pytest.fail("fifth redirect was accepted")
        assert_safe(error.value)
    assert len(connections) == 5
    assert all(connection.closed == 1 for connection in connections)
    assert not any(response.reads for response in responses)


def test_signed_redirect_with_private_dns_is_rejected_and_origin_closes(monkeypatch: Any) -> None:
    response = Response(
        302, [("Location", "https://cas-bridge.xethub.hf.co/file?sig=example-nonsecret")]
    )
    connections, _, _ = pinned_connections(monkeypatch, [response])

    def resolve(host: str, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        return public_dns("8.8.8.8" if host == "huggingface.co" else "127.0.0.1")

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    with (
        pytest.raises(BuiltinDownloadError) as error,
        PinnedBuiltinHttpTransport().open(artifact(), offset=0),
    ):
        pytest.fail("private redirect was accepted")
    assert_safe(error.value)
    assert len(connections) == 1 and connections[0].closed == 1


@pytest.mark.parametrize("status", [401, 403, 416, 500])
def test_non_success_status_is_left_to_leaf_without_reading_error_body(
    monkeypatch: Any, status: int
) -> None:
    response = Response(status)
    connections, _, _ = pinned_connections(monkeypatch, [response])
    with PinnedBuiltinHttpTransport().open(artifact(), offset=0) as result:
        assert result.status == status
        assert not response.reads
        assert "example-nonsecret-body" not in repr(result)
    assert connections[0].closed == 1


@pytest.mark.parametrize("name", ["Content-Length", "Content-Range", "Content-Encoding", "ETag"])
def test_duplicate_headers_are_rejected_instead_of_collapsed(monkeypatch: Any, name: str) -> None:
    response = Response(200, [(name, "example-first"), (name.lower(), "example-second")])
    connections, _, _ = pinned_connections(monkeypatch, [response])
    with (
        pytest.raises(BuiltinDownloadError) as error,
        PinnedBuiltinHttpTransport().open(artifact(), offset=0),
    ):
        pytest.fail("duplicate response header was accepted")
    assert_safe(error.value)
    assert connections[0].closed == 1 and not response.reads


@pytest.mark.parametrize("name", ["Content-Length", "ETag"])
def test_duplicate_redirect_headers_are_rejected_before_following(
    monkeypatch: Any, name: str
) -> None:
    redirect = Response(
        302, [("Location", "/next"), (name, "example-first"), (name.lower(), "example-second")]
    )
    connections, _, _ = pinned_connections(monkeypatch, [redirect, Response()])
    with (
        pytest.raises(BuiltinDownloadError) as error,
        PinnedBuiltinHttpTransport().open(artifact(), offset=0),
    ):
        pytest.fail("duplicate redirect header was accepted")
    assert_safe(error.value)
    assert len(connections) == 1 and connections[0].closed == 1
    assert not redirect.reads


@pytest.mark.parametrize("phase", ["request", "response", "read"])
@pytest.mark.parametrize(
    "exception",
    [TimeoutError("example-nonsecret-signed-url"), HTTPException("example-nonsecret-body")],
)
def test_network_timeouts_and_http_failures_are_safe_and_close_connection(
    monkeypatch: Any, phase: str, exception: Exception
) -> None:
    response = Response()
    connections, _, _ = pinned_connections(monkeypatch, [response])
    original: Any = builtin_http._PinnedHTTPSConnection

    def connect(*args: Any, **kwargs: Any) -> Connection:
        connection = original(*args, **kwargs)
        if phase == "request":
            connection.request_failure = exception
        elif phase == "response":
            connection.response_failure = exception
        else:
            response.failure = exception
        return connection

    monkeypatch.setattr(builtin_http, "_PinnedHTTPSConnection", connect)
    with (
        pytest.raises(BuiltinDownloadError) as error,
        PinnedBuiltinHttpTransport().open(artifact(), offset=0) as result,
    ):
        result.stream.read(3)
    assert_safe(error.value)
    assert connections[0].closed == 1


def test_request_value_error_is_sanitized_without_signed_target_leak(monkeypatch: Any) -> None:
    response = Response()
    connections, _, _ = pinned_connections(monkeypatch, [response])
    original: Any = builtin_http._PinnedHTTPSConnection

    def connect(*args: Any, **kwargs: Any) -> Connection:
        connection = original(*args, **kwargs)
        connection.request_failure = ValueError("example-nonsecret-signed-url")
        return connection

    monkeypatch.setattr(builtin_http, "_PinnedHTTPSConnection", connect)
    with (
        pytest.raises(BuiltinDownloadError) as error,
        PinnedBuiltinHttpTransport().open(artifact(), offset=0),
    ):
        pytest.fail("request failure was ignored")
    assert_safe(error.value)
    assert connections[0].closed == 1


@pytest.mark.parametrize("size", [-1, 0, 1024 * 1024 + 1])
def test_stream_rejects_unbounded_or_oversized_reads(monkeypatch: Any, size: int) -> None:
    response = Response()
    connections, _, _ = pinned_connections(monkeypatch, [response])
    with (
        pytest.raises(BuiltinDownloadError) as error,
        PinnedBuiltinHttpTransport().open(artifact(), offset=0) as result,
    ):
        result.stream.read(size)
    assert_safe(error.value)
    assert not response.reads and connections[0].closed == 1


def test_six_hour_deadline_is_checked_before_and_after_read(monkeypatch: Any) -> None:
    now = {"value": 0.0}
    monkeypatch.setattr(builtin_http.time, "monotonic", lambda: now["value"])
    response = Response()
    connections, _, _ = pinned_connections(monkeypatch, [response])
    with (
        pytest.raises(BuiltinDownloadError) as error,
        PinnedBuiltinHttpTransport().open(artifact(), offset=0) as result,
    ):
        now["value"] = 21_600
        result.stream.read(1)
    assert_safe(error.value)
    assert not response.reads and connections[0].closed == 1
    now["value"] = 0.0
    response = Response()
    response.after_read = lambda: now.update(value=21_600)
    connections, _, _ = pinned_connections(monkeypatch, [response])
    with (
        pytest.raises(BuiltinDownloadError) as error,
        PinnedBuiltinHttpTransport().open(artifact(), offset=0) as result,
    ):
        result.stream.read(1)
    assert_safe(error.value)
    assert response.reads == [1] and connections[0].closed == 1
