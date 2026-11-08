"""One-click GPU runtime for the built-in embedding model (ADR-084).

The shipped `onnxruntime` wheel is CPU-only. This module detects an NVIDIA GPU,
downloads the pinned `onnxruntime-gpu` and NVIDIA runtime wheels (pinned URL,
size and SHA-256 in `gpu_runtime_manifest.yml`) into a private folder beside the
runtime data, proves a CUDA session works in a child process, and publishes the
folder with an atomic rename. The managed Python environment is never changed:
the folder is put first on `sys.path` before ONNX Runtime is first imported, so
the GPU build is used from the next start. No wheel code is ever run.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import sysconfig
import threading
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Annotated, Final, Literal
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from reponpc.providers.builtin_artifacts import BuiltinArtifactFile
from reponpc.providers.builtin_download import (
    BuiltinDownloadCancelled,
    BuiltinDownloadError,
    BuiltinDownloadTransport,
    _check_cancel,
    _checked_stat,
    _ensure_space,
    _fetch,
    _hash_matches,
    _remove_owned_file,
)

logger = logging.getLogger(__name__)

_WHEEL_HOST: Final = "files.pythonhosted.org"
_READY_FILE: Final = "READY.json"
# Download plus the unpacked tree; the wheels are deleted after a successful install.
SPACE_FACTOR: Final = 3
_MAX_PATH: Final = 240
_MAX_MEMBER_BYTES: Final = 2 * 1024**3
_MAX_TOTAL_BYTES: Final = 8 * 1024**3
_SELF_CHECK_SECONDS: Final = 180
_DETECTION_TTL_SECONDS: Final = 30.0
# Only what ONNX Runtime and its CUDA libraries load: the package and the NVIDIA DLLs.
_MEMBER: Final = re.compile(r"onnxruntime/[^/].*|nvidia/.+\.dll")


class GpuRuntimeError(RuntimeError):
    """Internal failure that reveals no path, driver text or wheel content."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__("GPU runtime installation failed")


class GpuRuntimeWheel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    name: Annotated[str, Field(pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}\.whl$")]
    url: Annotated[str, Field(max_length=512)]
    bytes: Annotated[int, Field(gt=0)]
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]

    @model_validator(mode="after")
    def validate_url(self) -> GpuRuntimeWheel:
        parts = urlsplit(self.url)
        if (
            parts.scheme != "https"
            or parts.hostname != _WHEEL_HOST
            or parts.port is not None
            or parts.username is not None
            or parts.password is not None
            or parts.query
            or parts.fragment
            or not parts.path.startswith("/packages/")
            or parts.path.rsplit("/", 1)[-1] != self.name
        ):
            raise ValueError("a wheel URL must be a direct files.pythonhosted.org link")
        return self


class GpuRuntimeManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    runtime_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")]
    onnxruntime_version: Annotated[str, Field(pattern=r"^[0-9]+(\.[0-9]+){1,3}$")]
    python_tag: Annotated[str, Field(pattern=r"^cp3[0-9]{1,2}$")]
    platform_tag: Literal["win_amd64"]
    min_driver_major: Annotated[int, Field(gt=0)]
    min_compute_capability: Annotated[str, Field(pattern=r"^[0-9]+\.[0-9]+$")]
    wheels: Annotated[tuple[GpuRuntimeWheel, ...], Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    def validate_wheels(self) -> GpuRuntimeManifest:
        names = [wheel.name for wheel in self.wheels]
        main = (
            f"onnxruntime_gpu-{self.onnxruntime_version}-"
            f"{self.python_tag}-{self.python_tag}-{self.platform_tag}.whl"
        )
        if len(names) != len(set(names)) or names.count(main) != 1:
            raise ValueError("wheels must be unique and include the matching onnxruntime-gpu")
        return self

    @property
    def total_bytes(self) -> int:
        return sum(wheel.bytes for wheel in self.wheels)


@cache
def load_gpu_runtime_manifest() -> GpuRuntimeManifest:
    """Load only the pinned application resource, without external I/O."""

    try:
        raw = files("reponpc.providers").joinpath("gpu_runtime_manifest.yml").read_text("utf-8")
        return GpuRuntimeManifest.model_validate(yaml.safe_load(raw))
    except OSError, UnicodeError, yaml.YAMLError, ValidationError:
        raise GpuRuntimeError("gpu_runtime_manifest_invalid") from None


def install_supported(manifest: GpuRuntimeManifest | None = None) -> bool:
    """One-click install covers the Windows x86-64 source launcher on the pinned Python."""

    expected = manifest or load_gpu_runtime_manifest()
    return (
        sys.platform == "win32"
        and platform.machine().lower() in {"amd64", "x86_64"}
        and not getattr(sys, "frozen", False)
        and not sysconfig.get_config_var("Py_GIL_DISABLED")
        and f"cp{sys.version_info.major}{sys.version_info.minor}" == expected.python_tag
    )


DetectionState = Literal[
    "unsupported_platform", "no_nvidia_gpu", "driver_too_old", "gpu_too_old", "can_install"
]


@dataclass(frozen=True, slots=True)
class GpuDetection:
    state: DetectionState
    gpu_name: str | None = None
    driver_version: str | None = None


def _find_nvidia_smi() -> str | None:
    """The first existing `nvidia-smi.exe` on an absolute PATH entry or a standard folder."""

    candidates = [
        Path(entry) / "nvidia-smi.exe"
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry and Path(entry).is_absolute()
    ]
    for variable, tail in (
        ("SystemRoot", "System32"),
        ("ProgramFiles", "NVIDIA Corporation/NVSMI"),
    ):
        base = os.environ.get(variable)
        if base and Path(base).is_absolute():
            candidates.append(Path(base) / tail / "nvidia-smi.exe")
    return next((str(path) for path in candidates if path.is_file()), None)


def query_nvidia_smi(with_capability: bool) -> str | None:
    """Run the one fixed `nvidia-smi` query; no shell, short timeout, capped output."""

    executable = _find_nvidia_smi()
    if executable is None:
        return None
    fields = "name,driver_version" + (",compute_cap" if with_capability else "")
    try:
        result = subprocess.run(
            [executable, f"--query-gpu={fields}", "--format=csv,noheader,nounits"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError, subprocess.SubprocessError:
        return None
    if result.returncode != 0 or len(result.stdout) > 65_536:
        return None
    return result.stdout


def _parse_gpus(
    output: str, *, with_capability: bool
) -> list[tuple[str, str, tuple[int, int] | None]]:
    gpus: list[tuple[str, str, tuple[int, int] | None]] = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.rsplit(",", 2 if with_capability else 1)]
        if len(parts) != (3 if with_capability else 2):
            continue
        name, driver = parts[0], parts[1]
        if not name or re.fullmatch(r"[0-9]+(\.[0-9]+)*", driver) is None:
            continue
        capability: tuple[int, int] | None = None
        if with_capability and re.fullmatch(r"[0-9]+\.[0-9]+", parts[2]):
            major, minor = parts[2].split(".")
            capability = (int(major), int(minor))
        gpus.append((name[:120], driver, capability))
    return gpus


def detect_gpu(
    manifest: GpuRuntimeManifest | None = None,
    *,
    query: Callable[[bool], str | None] = query_nvidia_smi,
) -> GpuDetection:
    """Say whether this machine can take the pinned CUDA 13 runtime."""

    expected = manifest or load_gpu_runtime_manifest()
    if not install_supported(expected):
        return GpuDetection("unsupported_platform")
    output, with_capability = query(True), True
    if output is None:
        output, with_capability = query(False), False
    gpus = _parse_gpus(output or "", with_capability=with_capability)
    if not gpus:
        return GpuDetection("no_nvidia_gpu")
    first_name, driver, _ = gpus[0]
    if int(driver.split(".")[0]) < expected.min_driver_major:
        return GpuDetection("driver_too_old", first_name, driver)
    needed = tuple(int(part) for part in expected.min_compute_capability.split("."))
    usable = [gpu for gpu in gpus if gpu[2] is None or gpu[2] >= needed]
    if not usable:
        return GpuDetection("gpu_too_old", first_name, driver)
    return GpuDetection("can_install", usable[0][0], driver)


_detection_lock = threading.Lock()
_detection_cache: tuple[float, GpuDetection] | None = None


def detect_gpu_cached() -> GpuDetection:
    """Cache detection briefly: the admin page asks on every refresh."""

    global _detection_cache
    with _detection_lock:
        now = time.monotonic()
        if _detection_cache is None or now - _detection_cache[0] > _DETECTION_TTL_SECONDS:
            _detection_cache = (now, detect_gpu())
        return _detection_cache[1]


def runtime_directory(data_dir: Path) -> Path:
    return data_dir / "gpu-runtime"


def _ready_payload(manifest: GpuRuntimeManifest) -> dict[str, object]:
    return {
        "runtime_id": manifest.runtime_id,
        "wheels": {wheel.name: wheel.sha256 for wheel in manifest.wheels},
    }


def installed_runtime(data_dir: Path, manifest: GpuRuntimeManifest | None = None) -> Path | None:
    """The published folder when its marker matches this build's pinned manifest."""

    expected = manifest or load_gpu_runtime_manifest()
    final = runtime_directory(data_dir) / expected.runtime_id
    try:
        marker = final / _READY_FILE
        if (
            final.is_symlink()
            or final.is_junction()
            or not final.is_dir()
            or marker.is_symlink()
            or not marker.is_file()
            or marker.stat().st_size > 65_536
        ):
            return None
        stored = json.loads(marker.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    return final if stored == _ready_payload(expected) else None


_activation_lock = threading.Lock()
_active_runtime: str | None = None


def prepare_import_path(root: Path) -> None:
    """Make `import onnxruntime` find the GPU build first, with its DLL folders searchable."""

    text = str(root)
    if text not in sys.path:
        sys.path.insert(0, text)
    folders = [root / "onnxruntime" / "capi"]
    nvidia = root / "nvidia"
    if nvidia.is_dir():
        folders += sorted({path.parent for path in nvidia.rglob("*.dll")})
    existing = [str(folder) for folder in folders if folder.is_dir()]
    if hasattr(os, "add_dll_directory"):
        for folder in existing:
            os.add_dll_directory(folder)
    os.environ["PATH"] = os.pathsep.join([*existing, os.environ.get("PATH", "")])


def activate_gpu_runtime(data_dir: Path) -> bool:
    """Use the installed GPU runtime for this process; call before ONNX Runtime is imported."""

    global _active_runtime
    manifest = load_gpu_runtime_manifest()
    if not install_supported(manifest):
        return False
    with _activation_lock:
        if _active_runtime == manifest.runtime_id:
            return True
        root = installed_runtime(data_dir, manifest)
        if root is None or "onnxruntime" in sys.modules:
            return False
        prepare_import_path(root)
        _active_runtime = manifest.runtime_id
    logger.info("gpu_runtime_activated")
    return True


def gpu_runtime_active() -> bool:
    return _active_runtime is not None


def _within(root: Path, path: Path) -> bool:
    return path.parent == root and not path.is_symlink() and not path.is_junction()


def _remove_tree(root: Path, path: Path, *, strict: bool) -> None:
    """Delete one folder this module owns directly under the runtime folder."""

    if not _within(root, path):
        if path.exists() or path.is_symlink():
            raise GpuRuntimeError("gpu_runtime_extract")
        return
    if path.exists():
        shutil.rmtree(path, ignore_errors=not strict)


def _extract(wheel: Path, destination: Path, cancelled: Callable[[], bool]) -> None:
    """Unpack only the allowed members; refuse links, escapes, duplicates and oversize."""

    try:
        with zipfile.ZipFile(wheel) as archive:
            infos = [
                info
                for info in archive.infolist()
                if not info.is_dir() and _MEMBER.fullmatch(info.filename)
            ]
            if sum(info.file_size for info in infos) > _MAX_TOTAL_BYTES or any(
                info.file_size > _MAX_MEMBER_BYTES for info in infos
            ):
                raise GpuRuntimeError("gpu_runtime_extract")
            for info in infos:
                parts = info.filename.split("/")
                if (
                    "\\" in info.filename
                    or ":" in info.filename
                    or any(part in {"", ".", ".."} for part in parts)
                    or stat.S_ISLNK(info.external_attr >> 16)
                ):
                    raise GpuRuntimeError("gpu_runtime_extract")
                target = destination.joinpath(*parts)
                if len(str(target)) > _MAX_PATH:
                    raise GpuRuntimeError("gpu_runtime_path")
                target.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with archive.open(info) as source, open(target, "xb") as sink:
                    while chunk := source.read(1024 * 1024):
                        _check_cancel(cancelled)
                        written += len(chunk)
                        if written > info.file_size:
                            raise GpuRuntimeError("gpu_runtime_extract")
                        sink.write(chunk)
                if written != info.file_size:
                    raise GpuRuntimeError("gpu_runtime_extract")
    except BuiltinDownloadCancelled, GpuRuntimeError:
        raise
    except zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError:
        raise GpuRuntimeError("gpu_runtime_extract") from None


def run_self_check(root: Path, cancelled: Callable[[], bool]) -> None:
    """Prove a CUDA session works from `root` in a child, so this process stays untouched."""

    process = subprocess.Popen(
        [sys.executable, "-I", "-m", "reponpc.providers.gpu_runtime_check", str(root)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    deadline = time.monotonic() + _SELF_CHECK_SECONDS
    while True:
        try:
            code = process.wait(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            stop = cancelled()
            if stop or time.monotonic() >= deadline:
                process.kill()
                process.wait()
                if stop:
                    raise BuiltinDownloadCancelled from None
                logger.warning("gpu_runtime_self_check_timeout")
                raise GpuRuntimeError("gpu_runtime_self_check") from None
    if code != 0:
        logger.warning("gpu_runtime_self_check_failed exit=%s", code)
        raise GpuRuntimeError("gpu_runtime_self_check")


def install_gpu_runtime(
    data_dir: Path,
    *,
    transport: BuiltinDownloadTransport,
    cancelled: Callable[[], bool],
    on_progress: Callable[[int, int], None],
    manifest: GpuRuntimeManifest | None = None,
    self_check: Callable[[Path, Callable[[], bool]], None] = run_self_check,
) -> Path:
    """Download, verify, unpack, prove and atomically publish the pinned GPU runtime.

    A failed or cancelled run leaves the previous state alone: verified wheels stay
    for a quick retry, the unpacked tree is removed, and nothing is published.
    """

    expected = manifest or load_gpu_runtime_manifest()
    if not install_supported(expected):
        raise GpuRuntimeError("gpu_runtime_unsupported")
    _check_cancel(cancelled)
    total = expected.total_bytes
    existing = installed_runtime(data_dir, expected)
    if existing is not None:
        on_progress(total, total)
        return existing
    root = runtime_directory(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    final = root / expected.runtime_id
    download = root / f"{expected.runtime_id}.download"
    staging = root / f"{expected.runtime_id}.staging"
    _ensure_space(root, total * SPACE_FACTOR)
    if _checked_stat(download, directory=True) is None:
        download.mkdir(mode=0o700)
    artifacts = [
        BuiltinArtifactFile(name=wheel.name, bytes=wheel.bytes, sha256=wheel.sha256)
        for wheel in expected.wheels
    ]
    completed = 0

    def progress(current: int) -> None:
        on_progress(completed + current, total)

    for artifact in artifacts:
        _check_cancel(cancelled)
        ready = download / artifact.name
        part = download / (artifact.name + ".part")
        if _hash_matches(ready, artifact, cancelled):
            _remove_owned_file(part, download)
        else:
            _remove_owned_file(ready, download)
            leftover = _checked_stat(part, directory=False)
            if leftover is not None and leftover.st_size >= artifact.bytes:
                _remove_owned_file(part, download)
            _fetch(part, artifact, transport=transport, cancelled=cancelled, progress=progress)
            if not _hash_matches(part, artifact, cancelled):
                _remove_owned_file(part, download)
                raise BuiltinDownloadError("builtin_download_checksum")
            os.replace(part, ready)
        completed += artifact.bytes
        on_progress(completed, total)
    _remove_tree(root, staging, strict=True)
    staging.mkdir(mode=0o700)
    try:
        for artifact in artifacts:
            _check_cancel(cancelled)
            _extract(download / artifact.name, staging, cancelled)
        _check_cancel(cancelled)
        self_check(staging, cancelled)
        _check_cancel(cancelled)
        (staging / _READY_FILE).write_text(json.dumps(_ready_payload(expected)), encoding="utf-8")
        _remove_tree(root, final, strict=True)
        os.replace(staging, final)
    except BaseException:
        _remove_tree(root, staging, strict=False)
        raise
    _remove_tree(root, download, strict=False)
    for old in root.glob("ort-*"):
        if old.name not in {expected.runtime_id, download.name, staging.name} and old.is_dir():
            _remove_tree(root, old, strict=False)
    logger.info("gpu_runtime_installed")
    return final
