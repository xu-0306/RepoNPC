"""Tiny pinned-manifest fixtures exercise local streaming without a network."""

from __future__ import annotations

import io
import os
import socket
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import reponpc.providers.builtin_download as download
from reponpc.providers.builtin_artifacts import (
    BuiltinArtifactFile,
    BuiltinEmbeddingManifest,
    load_builtin_manifest,
)
from reponpc.providers.builtin_download import (
    BuiltinDownloadCancelled,
    BuiltinDownloadError,
    DownloadResponse,
    download_builtin_model,
)


def tiny_manifest(contents: Mapping[str, bytes]) -> BuiltinEmbeddingManifest:
    raw = load_builtin_manifest().model_dump()
    raw["files"] = [
        {"name": name, "bytes": len(content), "sha256": sha256(content).hexdigest()}
        for name, content in contents.items()
    ]
    return BuiltinEmbeddingManifest.model_validate(raw)


class TinyStream(io.BytesIO):
    def __init__(self, content: bytes, *, read_limit: int = 3) -> None:
        super().__init__(content)
        self.read_limit = read_limit
        self.requests: list[int] = []
        self.after_read: Callable[[], None] = lambda: None

    def read(self, size: int | None = -1) -> bytes:
        assert size is not None and size > 0, "download attempted an unbounded read"
        self.requests.append(size)
        value = super().read(min(size, self.read_limit))
        self.after_read()
        return value


class FakeTransport:
    def __init__(self, contents: Mapping[str, bytes]) -> None:
        self.contents = contents
        self.calls: list[tuple[str, int]] = []
        self.streams: list[TinyStream] = []
        self.response: Callable[[BuiltinArtifactFile, int], DownloadResponse] | None = None

    @contextmanager
    def open(self, artifact: BuiltinArtifactFile, *, offset: int) -> Iterator[DownloadResponse]:
        self.calls.append((artifact.name, offset))
        if self.response is not None:
            response = self.response(artifact, offset)
        else:
            stream = TinyStream(self.contents[artifact.name][offset:])
            headers = {"Content-Length": str(artifact.bytes - offset)}
            if offset:
                headers["Content-Range"] = f"bytes {offset}-{artifact.bytes - 1}/{artifact.bytes}"
            response = DownloadResponse(206 if offset else 200, headers, stream)
        if isinstance(response.stream, TinyStream):
            self.streams.append(response.stream)
        try:
            yield response
        finally:
            response.stream.close()


def run_download(
    root: Path, contents: Mapping[str, bytes], transport: FakeTransport, **kwargs: Any
) -> Path:
    return download_builtin_model(
        root,
        transport=transport,
        cancelled=kwargs.pop("cancelled", lambda: False),
        on_progress=kwargs.pop("on_progress", lambda current, total: None),
        manifest=tiny_manifest(contents),
        **kwargs,
    )


def assert_safe(error: BuiltinDownloadError, code: str) -> None:
    assert error.code == code
    assert str(error) == "built-in embedding download failed"
    assert error.__cause__ is None


def test_eight_files_stream_in_manifest_order_and_publish_only_verified_bytes(
    tmp_path: Path,
) -> None:
    contents = {f"fixture-{number}.data": bytes([number]) * 7 for number in range(8)}
    transport = FakeTransport(contents)
    progress = []
    root = tmp_path / "model"
    assert (
        run_download(root, contents, transport, on_progress=lambda *pair: progress.append(pair))
        == root
    )
    assert transport.calls == [(name, 0) for name in contents]
    assert {path.name for path in root.iterdir()} == set(contents)
    assert all((root / name).read_bytes() == content for name, content in contents.items())
    assert progress[-1] == (56, 56)
    assert all(0 <= current <= total == 56 for current, total in progress)
    assert all(stream.closed for stream in transport.streams)
    assert not (tmp_path / "model.download").exists()


def test_cancel_after_write_keeps_prefix_and_next_call_resumes_range(tmp_path: Path) -> None:
    contents = {"fixture.data": b"abcdefgh"}
    root = tmp_path / "model"
    transport = FakeTransport(contents)
    flag = {"cancel": False}

    def progress(current: int, total: int) -> None:
        assert total == 8
        if current >= 3:
            flag["cancel"] = True

    with pytest.raises(BuiltinDownloadCancelled, match="built-in embedding download cancelled"):
        run_download(
            root, contents, transport, cancelled=lambda: flag["cancel"], on_progress=progress
        )
    assert not root.exists()
    assert (tmp_path / "model.download" / "fixture.data.part").read_bytes() == b"abc"
    assert transport.streams[0].closed
    resumed = FakeTransport(contents)
    run_download(root, contents, resumed)
    assert resumed.calls == [("fixture.data", 3)]
    assert (root / "fixture.data").read_bytes() == b"abcdefgh"


def test_cancel_before_and_after_read_and_before_publish(tmp_path: Path) -> None:
    contents = {"fixture.data": b"abcdef"}
    root = tmp_path / "model"
    transport = FakeTransport(contents)
    with pytest.raises(BuiltinDownloadCancelled):
        run_download(root, contents, transport, cancelled=lambda: True)
    assert not transport.calls and not (tmp_path / "model.download").exists()
    flag = {"cancel": False}
    stream = TinyStream(b"abcdef")
    stream.after_read = lambda: flag.update(cancel=True)
    transport.response = lambda artifact, offset: DownloadResponse(200, {}, stream)
    with pytest.raises(BuiltinDownloadCancelled):
        run_download(root, contents, transport, cancelled=lambda: flag["cancel"])
    assert (tmp_path / "model.download" / "fixture.data.part").stat().st_size == 0
    flag["cancel"] = False
    transport = FakeTransport(contents)
    with pytest.raises(BuiltinDownloadCancelled):
        run_download(
            root,
            contents,
            transport,
            cancelled=lambda: flag["cancel"],
            on_progress=lambda current, total: flag.update(cancel=current == total),
        )
    assert not root.exists()
    resumed = FakeTransport(contents)
    run_download(root, contents, resumed)
    assert not resumed.calls  # Complete part is locally hashed before publication.


def test_verified_stage_files_are_skipped_on_restart(tmp_path: Path) -> None:
    contents = {"first.data": b"abc", "second.data": b"defghi"}
    stage = tmp_path / "model.download"
    stage.mkdir()
    (stage / "first.data").write_bytes(b"abc")
    (stage / "first.data.part").write_bytes(b"unused")
    transport = FakeTransport(contents)
    run_download(tmp_path / "model", contents, transport)
    assert transport.calls == [("second.data", 0)]
    assert not (tmp_path / "model" / "first.data.part").exists()


def test_ignored_range_safely_restarts_without_appending_prefix(tmp_path: Path) -> None:
    contents = {"fixture.data": b"abcdef"}
    stage = tmp_path / "model.download"
    stage.mkdir()
    (stage / "fixture.data.part").write_bytes(b"ab")
    transport = FakeTransport(contents)
    transport.response = lambda artifact, offset: DownloadResponse(
        200, {"Content-Length": "6"}, TinyStream(b"abcdef")
    )
    run_download(tmp_path / "model", contents, transport)
    assert transport.calls == [("fixture.data", 2)]
    assert (tmp_path / "model" / "fixture.data").read_bytes() == b"abcdef"


@pytest.mark.parametrize(
    "status,headers,code",
    [
        (416, {}, "builtin_download_http"),
        (500, {}, "builtin_download_http"),
        (True, {}, "builtin_download_http"),
        (206, {}, "builtin_download_range"),
        (206, {"Content-Range": "bytes 0-5/6"}, "builtin_download_range"),
        (206, {"Content-Range": "bytes 2-4/6"}, "builtin_download_range"),
        (206, {"Content-Range": "bytes 2-5/7"}, "builtin_download_range"),
        (206, {"Content-Range": "bytes 2-5/*"}, "builtin_download_range"),
        (206, {"Content-Range": "bytes -2-5/6"}, "builtin_download_range"),
        (206, {"Content-Range": "bytes 2-5/6 "}, "builtin_download_range"),
        (
            206,
            {"Content-Range": "bytes 2-5/6", "Content-Encoding": "identity"},
            "builtin_download_range",
        ),
        (206, {"Content-Range": "bytes 2-5/6", "Content-Length": "3"}, "builtin_download_size"),
        (206, {"Content-Range": "bytes 2-5/6", "Content-Length": "+4"}, "builtin_download_size"),
        (
            206,
            {"Content-Range": "bytes 2-5/6", "content-range": "bytes 2-5/6"},
            "builtin_download_range",
        ),
        (200, {"Content-Range": "bytes 2-5/6"}, "builtin_download_range"),
    ],
)
def test_invalid_http_metadata_fails_without_publication(
    tmp_path: Path, status: int, headers: dict[str, str], code: str
) -> None:
    contents = {"fixture.data": b"abcdef"}
    stage = tmp_path / "model.download"
    stage.mkdir()
    (stage / "fixture.data.part").write_bytes(b"ab")
    transport = FakeTransport(contents)
    transport.response = lambda artifact, offset: DownloadResponse(
        status, headers, TinyStream(b"cdef")
    )
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(tmp_path / "model", contents, transport)
    assert_safe(error.value, code)
    assert not (tmp_path / "model").exists()
    assert (stage / "fixture.data.part").read_bytes() == b"ab"
    assert transport.streams[0].closed


@pytest.mark.parametrize("body", [b"abc", b"abcdefg"])
def test_short_or_extra_stream_is_not_published_and_can_retry(tmp_path: Path, body: bytes) -> None:
    contents = {"fixture.data": b"abcdef"}
    transport = FakeTransport(contents)
    transport.response = lambda artifact, offset: DownloadResponse(200, {}, TinyStream(body))
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(tmp_path / "model", contents, transport)
    assert_safe(error.value, "builtin_download_size")
    assert not (tmp_path / "model").exists()
    run_download(tmp_path / "model", contents, FakeTransport(contents))
    assert (tmp_path / "model" / "fixture.data").read_bytes() == b"abcdef"


def test_hash_mismatch_is_discarded_then_retry_starts_at_zero(tmp_path: Path) -> None:
    contents = {"fixture.data": b"abcdef"}
    transport = FakeTransport({"fixture.data": b"xxxxxx"})
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(tmp_path / "model", contents, transport)
    assert_safe(error.value, "builtin_download_checksum")
    assert not (tmp_path / "model").exists()
    assert not (tmp_path / "model.download" / "fixture.data.part").exists()
    transport = FakeTransport(contents)
    run_download(tmp_path / "model", contents, transport)
    assert transport.calls == [("fixture.data", 0)]


@pytest.mark.parametrize("name", ["fixture.data", "fixture.data.part"])
def test_corrupt_complete_stage_file_is_safely_reacquired(tmp_path: Path, name: str) -> None:
    contents = {"fixture.data": b"abcdef"}
    stage = tmp_path / "model.download"
    stage.mkdir()
    (stage / name).write_bytes(b"xxxxxx")
    transport = FakeTransport(contents)
    run_download(tmp_path / "model", contents, transport)
    assert transport.calls == [("fixture.data", 0)]


def test_reads_are_chunk_bounded_not_whole_body(tmp_path: Path, monkeypatch: Any) -> None:
    assert download._CHUNK_BYTES == 1024 * 1024
    monkeypatch.setattr(download, "_CHUNK_BYTES", 4)
    contents = {"fixture.data": b"abcdefghijkl"}
    transport = FakeTransport(contents)
    run_download(tmp_path / "model", contents, transport)
    assert all(size <= 4 for size in transport.streams[0].requests)
    assert len(transport.streams[0].requests) >= 4


def test_valid_final_returns_without_transport_and_invalid_final_is_untouched(
    tmp_path: Path,
) -> None:
    contents = {"fixture.data": b"abcdef"}
    root = tmp_path / "model"
    root.mkdir()
    target = root / "fixture.data"
    target.write_bytes(b"abcdef")
    transport = FakeTransport(contents)
    assert run_download(root, contents, transport) == root
    assert not transport.calls
    target.write_bytes(b"xxxxxx")
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(root, contents, transport)
    assert_safe(error.value, "builtin_download_conflict")
    assert target.read_bytes() == b"xxxxxx"
    assert not transport.calls and not (tmp_path / "model.download").exists()


def test_stage_junk_and_nonregular_files_are_preserved_and_rejected(tmp_path: Path) -> None:
    contents = {"fixture.data": b"abcdef"}
    stage = tmp_path / "model.download"
    stage.mkdir()
    unrelated = stage / "unrelated.txt"
    unrelated.write_bytes(b"preserve")
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(tmp_path / "model", contents, FakeTransport(contents))
    assert_safe(error.value, "builtin_download_conflict")
    assert unrelated.read_bytes() == b"preserve"
    unrelated.unlink()
    (stage / "fixture.data.part").mkdir()
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(tmp_path / "model", contents, FakeTransport(contents))
    assert_safe(error.value, "builtin_download_path_invalid")
    assert not (tmp_path / "model").exists()


@pytest.mark.parametrize("location", ["final", "stage", "ancestor", "ready", "part"])
@pytest.mark.parametrize("kind", ["symlink", "junction"])
def test_link_guards_reject_roots_ancestors_and_files(
    tmp_path: Path, monkeypatch: Any, location: str, kind: str
) -> None:
    contents = {"fixture.data": b"abcdef"}
    root = tmp_path / "model"
    stage = tmp_path / "model.download"
    stage.mkdir()
    paths = {
        "final": root,
        "stage": stage,
        "ancestor": tmp_path,
        "ready": stage / "fixture.data",
        "part": stage / "fixture.data.part",
    }
    marked = paths[location]
    if location == "final":
        root.mkdir()
    elif location in ("ready", "part"):
        marked.write_bytes(b"ab")
    attribute = "is_symlink" if kind == "symlink" else "is_junction"
    original = getattr(Path, attribute)
    monkeypatch.setattr(Path, attribute, lambda path: path == marked or original(path))
    transport = FakeTransport(contents)
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(root, contents, transport)
    assert_safe(error.value, "builtin_download_path_invalid")
    assert not transport.calls


@pytest.mark.parametrize("location", ["final", "ready", "part"])
def test_real_hardlinks_are_rejected_without_modifying_external_file(
    tmp_path: Path, location: str
) -> None:
    contents = {"fixture.data": b"abcdef"}
    external = tmp_path / "external.data"
    external.write_bytes(b"abcdef")
    root = tmp_path / "model"
    directory = root if location == "final" else tmp_path / "model.download"
    directory.mkdir()
    name = "fixture.data.part" if location == "part" else "fixture.data"
    os.link(external, directory / name)
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(root, contents, FakeTransport(contents))
    assert_safe(error.value, "builtin_download_path_invalid")
    assert external.read_bytes() == b"abcdef"
    assert external.stat().st_nlink == 2


def test_insufficient_disk_fails_before_transport(tmp_path: Path, monkeypatch: Any) -> None:
    contents = {"fixture.data": b"abcdef"}
    transport = FakeTransport(contents)
    monkeypatch.setattr(download.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(tmp_path / "model", contents, transport)
    assert_safe(error.value, "builtin_download_disk_space")
    assert not transport.calls and not (tmp_path / "model").exists()


def test_post_commit_verification_failure_restores_stage(tmp_path: Path, monkeypatch: Any) -> None:
    contents = {"fixture.data": b"abcdef"}

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise OSError("private/path key=secret")

    monkeypatch.setattr(download, "verify_builtin_artifacts", fail)
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(tmp_path / "model", contents, FakeTransport(contents))
    assert_safe(error.value, "builtin_download_verification")
    assert not (tmp_path / "model").exists()
    assert (tmp_path / "model.download" / "fixture.data").read_bytes() == b"abcdef"


def test_transport_failure_is_safe_and_local_download_has_no_network(
    tmp_path: Path, monkeypatch: Any
) -> None:
    contents = {"fixture.data": b"abcdef"}

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("local download leaf attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    transport = FakeTransport(contents)

    def fail(artifact: BuiltinArtifactFile, offset: int) -> DownloadResponse:
        raise ValueError("upstream body private/url secret-key")

    transport.response = fail
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(tmp_path / "model", contents, transport)
    assert_safe(error.value, "builtin_download_http")
    run_download(tmp_path / "model", contents, FakeTransport(contents))


def test_none_manifest_uses_only_application_pin_loader(tmp_path: Path, monkeypatch: Any) -> None:
    contents = {"fixture.data": b"abcdef"}
    manifest = tiny_manifest(contents)
    calls = []

    def pinned() -> BuiltinEmbeddingManifest:
        calls.append("pin")
        return manifest

    monkeypatch.setattr(download, "load_builtin_manifest", pinned)
    download_builtin_model(
        tmp_path / "model",
        transport=FakeTransport(contents),
        cancelled=lambda: False,
        on_progress=lambda current, total: None,
    )
    assert calls == ["pin"]


def test_corrupt_partial_prefix_cannot_be_promoted_after_resume(tmp_path: Path) -> None:
    contents = {"fixture.data": b"abcdef"}
    stage = tmp_path / "model.download"
    stage.mkdir()
    (stage / "fixture.data.part").write_bytes(b"xx")
    transport = FakeTransport(contents)
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(tmp_path / "model", contents, transport)
    assert_safe(error.value, "builtin_download_checksum")
    assert transport.calls == [("fixture.data", 2)]
    assert not (tmp_path / "model").exists()
    assert not (stage / "fixture.data.part").exists()
    retry = FakeTransport(contents)
    run_download(tmp_path / "model", contents, retry)
    assert retry.calls == [("fixture.data", 0)]


def test_stream_exceeding_requested_read_bound_is_rejected(tmp_path: Path) -> None:
    contents = {"fixture.data": b"abcd"}

    class OversizedStream(TinyStream):
        def read(self, size: int | None = -1) -> bytes:
            return b"abcd-extra"

    transport = FakeTransport(contents)
    transport.response = lambda artifact, offset: DownloadResponse(200, {}, OversizedStream(b""))
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(tmp_path / "model", contents, transport)
    assert_safe(error.value, "builtin_download_size")
    assert not (tmp_path / "model").exists()
    assert (tmp_path / "model.download" / "fixture.data.part").stat().st_size == 0


def test_interrupted_stream_keeps_written_prefix_for_retry(tmp_path: Path) -> None:
    contents = {"fixture.data": b"abcdef"}

    class InterruptedStream(TinyStream):
        def read(self, size: int | None = -1) -> bytes:
            if self.tell() >= 3:
                raise OSError("private/path upstream body secret")
            return super().read(size)

    transport = FakeTransport(contents)
    transport.response = lambda artifact, offset: DownloadResponse(
        200, {}, InterruptedStream(b"abcdef")
    )
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(tmp_path / "model", contents, transport)
    assert_safe(error.value, "builtin_download_io")
    assert (tmp_path / "model.download" / "fixture.data.part").read_bytes() == b"abc"
    retry = FakeTransport(contents)
    run_download(tmp_path / "model", contents, retry)
    assert retry.calls == [("fixture.data", 3)]


def test_real_file_symlink_is_rejected_without_touching_target(tmp_path: Path) -> None:
    contents = {"fixture.data": b"abcdef"}
    external = tmp_path / "external.data"
    external.write_bytes(b"abcdef")
    stage = tmp_path / "model.download"
    stage.mkdir()
    link = stage / "fixture.data.part"
    try:
        link.symlink_to(external)
    except OSError:
        pytest.skip("this host does not permit unprivileged symlink creation")
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(tmp_path / "model", contents, FakeTransport(contents))
    assert_safe(error.value, "builtin_download_path_invalid")
    assert external.read_bytes() == b"abcdef" and link.is_symlink()


def test_publication_io_failure_keeps_verified_stage_and_does_not_touch_other_files(
    tmp_path: Path, monkeypatch: Any
) -> None:
    contents = {"fixture.data": b"abcdef"}
    unrelated = tmp_path / "unrelated.data"
    unrelated.write_bytes(b"preserve")
    original = os.replace

    def fail_final(source: Path, destination: Path) -> None:
        if destination == tmp_path / "model":
            raise OSError("private/path disk error secret")
        original(source, destination)

    monkeypatch.setattr(download.os, "replace", fail_final)
    with pytest.raises(BuiltinDownloadError) as error:
        run_download(tmp_path / "model", contents, FakeTransport(contents))
    assert_safe(error.value, "builtin_download_io")
    assert not (tmp_path / "model").exists()
    assert (tmp_path / "model.download" / "fixture.data").read_bytes() == b"abcdef"
    assert unrelated.read_bytes() == b"preserve"
