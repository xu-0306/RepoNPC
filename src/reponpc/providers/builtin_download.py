"""Bounded local download staging; HTTP and owner operation state belong to Main.

The caller supplies a private existing parent directory and serializes operations
for this model root. Cancellation wins until the final rename commit point.
No URL, credentials, alternate pin, or network implementation lives here.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO, Protocol

from reponpc.providers.builtin_artifacts import (
    BuiltinArtifactFile,
    BuiltinEmbeddingManifest,
    load_builtin_manifest,
    verify_builtin_artifacts,
)

_CHUNK_BYTES = 1024 * 1024
_CONTENT_RANGE = re.compile(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)")


@dataclass(frozen=True, slots=True)
class DownloadResponse:
    status: int
    headers: Mapping[str, str]
    stream: BinaryIO


class BuiltinDownloadTransport(Protocol):
    def open(
        self, artifact: BuiltinArtifactFile, *, offset: int
    ) -> AbstractContextManager[DownloadResponse]:
        """Open one pinned artifact's remaining bytes; the caller closes it."""


class BuiltinDownloadCancelled(Exception):
    def __init__(self) -> None:
        super().__init__("built-in embedding download cancelled")


class BuiltinDownloadError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("built-in embedding download failed")


def _check_cancel(cancelled: Callable[[], bool]) -> None:
    if cancelled():
        raise BuiltinDownloadCancelled


def _checked_stat(path: Path, *, directory: bool) -> os.stat_result | None:
    try:
        value = path.lstat()
    except FileNotFoundError:
        return None
    if path.is_symlink() or path.is_junction():
        raise BuiltinDownloadError("builtin_download_path_invalid")
    if directory:
        if not stat.S_ISDIR(value.st_mode):
            raise BuiltinDownloadError("builtin_download_path_invalid")
    elif not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise BuiltinDownloadError("builtin_download_path_invalid")
    return value


def _check_parents(path: Path) -> None:
    for parent in reversed(path.parents):
        if _checked_stat(parent, directory=True) is None:
            raise BuiltinDownloadError("builtin_download_path_invalid")


def _same_file(left: os.stat_result, right: os.stat_result) -> bool:
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _open_file(path: Path, *, create: bool = False, writable: bool = False) -> BinaryIO:
    _check_parents(path)
    before = _checked_stat(path, directory=False)
    flags = os.O_RDWR if writable else os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    if before is None:
        if not create:
            raise BuiltinDownloadError("builtin_download_path_invalid")
        flags |= os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        _check_parents(path)
        opened = os.fstat(descriptor)
        current = _checked_stat(path, directory=False)
        if (
            current is None
            or not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or not _same_file(current, opened)
            or (before is not None and not _same_file(before, opened))
        ):
            raise BuiltinDownloadError("builtin_download_path_invalid")
        return os.fdopen(descriptor, "r+b" if writable else "rb")
    except BaseException:
        os.close(descriptor)
        raise


def _hash_matches(path: Path, artifact: BuiltinArtifactFile, cancelled: Callable[[], bool]) -> bool:
    before = _checked_stat(path, directory=False)
    if before is None or before.st_size != artifact.bytes:
        return False
    digest = sha256()
    remaining = artifact.bytes
    with _open_file(path) as stream:
        while remaining:
            _check_cancel(cancelled)
            chunk = stream.read(min(remaining, _CHUNK_BYTES))
            _check_cancel(cancelled)
            if not chunk:
                return False
            digest.update(chunk)
            remaining -= len(chunk)
        _check_cancel(cancelled)
        extra = stream.read(1)
        _check_cancel(cancelled)
        if extra:
            return False
    after = _checked_stat(path, directory=False)
    return (
        after is not None
        and _same_file(before, after)
        and before.st_size == after.st_size
        and before.st_mtime_ns == after.st_mtime_ns
        and digest.hexdigest() == artifact.sha256
    )


def _remove_owned_file(path: Path, stage: Path) -> None:
    if path.parent != stage:
        raise BuiltinDownloadError("builtin_download_path_invalid")
    _check_parents(path)
    if _checked_stat(path, directory=False) is not None:
        path.unlink()


def _check_stage(stage: Path, manifest: BuiltinEmbeddingManifest, *, complete: bool) -> None:
    _check_parents(stage)
    if _checked_stat(stage, directory=True) is None:
        raise BuiltinDownloadError("builtin_download_path_invalid")
    names = {artifact.name for artifact in manifest.files}
    partials = {f"{name}.part" for name in names}
    if names & partials:
        raise BuiltinDownloadError("builtin_download_conflict")
    allowed = names if complete else names | partials
    actual = set()
    for path in stage.iterdir():
        if path.name not in allowed:
            raise BuiltinDownloadError("builtin_download_conflict")
        _checked_stat(path, directory=False)
        actual.add(path.name)
    if complete and actual != names:
        raise BuiltinDownloadError("builtin_download_verification")


def _ensure_space(path: Path, needed: int) -> None:
    if shutil.disk_usage(path).free < needed:
        raise BuiltinDownloadError("builtin_download_disk_space")


def _body_offset(response: DownloadResponse, artifact: BuiltinArtifactFile, offset: int) -> int:
    headers: dict[str, str] = {}
    for name, value in response.headers.items():
        if not isinstance(name, str) or not isinstance(value, str) or name.lower() in headers:
            raise BuiltinDownloadError("builtin_download_range")
        headers[name.lower()] = value
    if "content-encoding" in headers:
        raise BuiltinDownloadError("builtin_download_range")
    if type(response.status) is not int or response.status not in (200, 206):
        raise BuiltinDownloadError("builtin_download_http")
    if response.status == 200:
        if "content-range" in headers:
            raise BuiltinDownloadError("builtin_download_range")
        start = 0  # The server ignored Range: explicitly discard the old prefix.
    else:
        match = _CONTENT_RANGE.fullmatch(headers.get("content-range", ""))
        if match is None:
            raise BuiltinDownloadError("builtin_download_range")
        start, end, total = map(int, match.groups())
        if start != offset or end != artifact.bytes - 1 or total != artifact.bytes:
            raise BuiltinDownloadError("builtin_download_range")
    if "content-length" in headers:
        length = headers["content-length"]
        if re.fullmatch(r"[0-9]+", length) is None or int(length) != artifact.bytes - start:
            raise BuiltinDownloadError("builtin_download_size")
    return start


def _fetch(
    part: Path,
    artifact: BuiltinArtifactFile,
    *,
    transport: BuiltinDownloadTransport,
    cancelled: Callable[[], bool],
    progress: Callable[[int], None],
) -> None:
    before = _checked_stat(part, directory=False)
    offset = before.st_size if before is not None else 0
    _ensure_space(part.parent, artifact.bytes - offset)
    _check_cancel(cancelled)
    try:
        with transport.open(artifact, offset=offset) as response:
            _check_cancel(cancelled)
            start = _body_offset(response, artifact, offset)
            with _open_file(part, create=True, writable=True) as target:
                if start == 0:
                    target.truncate(0)
                target.seek(start)
                progress(start)
                remaining = artifact.bytes - start
                while remaining:
                    _check_cancel(cancelled)
                    size = min(remaining, _CHUNK_BYTES)
                    chunk = response.stream.read(size)
                    _check_cancel(cancelled)
                    if not isinstance(chunk, bytes) or len(chunk) > size:
                        raise BuiltinDownloadError("builtin_download_size")
                    if not chunk:
                        raise BuiltinDownloadError("builtin_download_size")
                    target.write(chunk)
                    remaining -= len(chunk)
                    progress(artifact.bytes - remaining)
                    _check_cancel(cancelled)
                _check_cancel(cancelled)
                extra = response.stream.read(1)
                _check_cancel(cancelled)
                if not isinstance(extra, bytes) or extra:
                    raise BuiltinDownloadError("builtin_download_size")
                target.flush()
                os.fsync(target.fileno())
    except BuiltinDownloadCancelled, BuiltinDownloadError:
        raise
    except OSError:
        raise BuiltinDownloadError("builtin_download_io") from None
    except Exception:
        raise BuiltinDownloadError("builtin_download_http") from None


def download_builtin_model(
    model_dir: Path,
    *,
    transport: BuiltinDownloadTransport,
    cancelled: Callable[[], bool],
    on_progress: Callable[[int, int], None],
    manifest: BuiltinEmbeddingManifest | None = None,
) -> Path:
    """Resume verified local staging and atomically publish a complete model.

    Existing final directories are immutable, including invalid ones. Unknown
    stage entries are rejected and never deleted or carried into the final root.
    The manifest argument is only an internal tiny-fixture seam.
    """

    try:
        _check_cancel(cancelled)
        expected = manifest if manifest is not None else load_builtin_manifest()
        final = model_dir.absolute()
        if not final.name or ".." in final.parts:
            raise BuiltinDownloadError("builtin_download_path_invalid")
        _check_parents(final)
        if _checked_stat(final, directory=True) is not None:
            _check_stage(final, expected, complete=True)
            try:
                result = verify_builtin_artifacts(final, expected)
            except Exception:
                raise BuiltinDownloadError("builtin_download_conflict") from None
            _check_cancel(cancelled)
            on_progress(expected.total_bytes, expected.total_bytes)
            return result
        stage = final.with_name(final.name + ".download")
        if _checked_stat(stage, directory=True) is None:
            stage.mkdir(mode=0o700)
        _check_stage(stage, expected, complete=False)
        remaining = sum(
            artifact.bytes
            - min(
                artifact.bytes,
                max(
                    (path.stat().st_size if path.exists() else 0)
                    for path in (stage / artifact.name, stage / (artifact.name + ".part"))
                ),
            )
            for artifact in expected.files
        )
        _ensure_space(stage, remaining)
        completed = 0

        def progress(current: int) -> None:
            on_progress(completed + current, expected.total_bytes)

        for artifact in expected.files:
            _check_cancel(cancelled)
            ready = stage / artifact.name
            part = stage / (artifact.name + ".part")
            if _hash_matches(ready, artifact, cancelled):
                _remove_owned_file(part, stage)
            else:
                _remove_owned_file(ready, stage)
                existing = _checked_stat(part, directory=False)
                part_verified = (
                    existing is not None
                    and existing.st_size == artifact.bytes
                    and _hash_matches(part, artifact, cancelled)
                )
                if (
                    existing is not None
                    and existing.st_size >= artifact.bytes
                    and not part_verified
                ):
                    _remove_owned_file(part, stage)
                if not part_verified:
                    _fetch(
                        part,
                        artifact,
                        transport=transport,
                        cancelled=cancelled,
                        progress=progress,
                    )
                if not part_verified and not _hash_matches(part, artifact, cancelled):
                    _remove_owned_file(part, stage)
                    raise BuiltinDownloadError("builtin_download_checksum")
                _check_cancel(cancelled)
                _check_parents(part)
                if _checked_stat(part, directory=False) is None:
                    raise BuiltinDownloadError("builtin_download_path_invalid")
                if _checked_stat(ready, directory=False) is not None:
                    raise BuiltinDownloadError("builtin_download_conflict")
                os.replace(part, ready)
            completed += artifact.bytes
            on_progress(completed, expected.total_bytes)
        _check_stage(stage, expected, complete=True)
        _check_parents(final)
        if _checked_stat(final, directory=True) is not None:
            raise BuiltinDownloadError("builtin_download_conflict")
        _check_cancel(cancelled)
        os.replace(stage, final)
        # Cancellation after publication did not win the commit race. A failed
        # integrity gate restores only our new directory, never an old final.
        try:
            return verify_builtin_artifacts(final, expected)
        except Exception:
            os.replace(final, stage)
            raise BuiltinDownloadError("builtin_download_verification") from None
    except BuiltinDownloadCancelled, BuiltinDownloadError:
        raise
    except Exception:
        raise BuiltinDownloadError("builtin_download_io") from None
