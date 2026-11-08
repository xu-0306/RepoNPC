"""One-click GPU runtime (ADR-084): manifest, detection, install, activation, self-check."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import platform
import re
import shutil
import socket
import stat
import subprocess
import sys
import sysconfig
import time
import zipfile
from collections import namedtuple
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from http.client import HTTPException
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from urllib.parse import urlsplit

import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]
import pytest
from pydantic import ValidationError

import reponpc.providers.builtin_http as builtin_http
import reponpc.providers.builtin_onnx as builtin_onnx
import reponpc.providers.gpu_runtime as gpu_runtime
from reponpc.admin import operations as operation_module
from reponpc.admin.embedding_profiles import EmbeddingProfileError
from reponpc.admin.model_operations import GPU_RUNTIME_MODEL_ID, OllamaModelOperationCoordinator
from reponpc.admin.operations import AdminOperations
from reponpc.providers.builtin_artifacts import BuiltinArtifactFile
from reponpc.providers.builtin_download import (
    BuiltinDownloadCancelled,
    BuiltinDownloadError,
    DownloadResponse,
)
from reponpc.providers.gpu_runtime import (
    GpuDetection,
    GpuRuntimeError,
    GpuRuntimeManifest,
    GpuRuntimeWheel,
    activate_gpu_runtime,
    detect_gpu,
    install_gpu_runtime,
    installed_runtime,
    load_gpu_runtime_manifest,
    run_self_check,
)
from reponpc.providers.gpu_runtime_check import check_model

ROOT = Path(__file__).resolve().parents[2]
PYTHON_TAG = f"cp{sys.version_info.major}{sys.version_info.minor}"
MAIN_WHEEL = f"onnxruntime_gpu-1.0.0-{PYTHON_TAG}-{PYTHON_TAG}-win_amd64.whl"
CUDA_WHEEL = "nvidia_cublas-1.0-py3-none-win_amd64.whl"
REAL_INSTALL_SUPPORTED = gpu_runtime.install_supported  # before the autouse override below


@pytest.fixture(autouse=True)
def supported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run the logic on any host; real platform support is checked on its own below."""
    monkeypatch.setattr(gpu_runtime, "install_supported", lambda manifest=None: True)


def _fresh(tmp_path: Path, name: str) -> Path:
    folder = tmp_path / name
    folder.mkdir()
    return folder


# --- the pinned manifest -------------------------------------------------------------


def test_pinned_manifest_matches_the_cpu_runtime_pin_and_serves_only_pythonhosted() -> None:
    manifest = load_gpu_runtime_manifest()
    pin = re.search(r'"onnxruntime==([0-9.]+)"', (ROOT / "pyproject.toml").read_text("utf-8"))
    assert pin is not None and manifest.onnxruntime_version == pin.group(1)
    assert manifest.runtime_id.startswith(f"ort-{pin.group(1)}-")
    assert manifest.min_driver_major == 580 and manifest.min_compute_capability == "7.5"
    assert {urlsplit(wheel.url).hostname for wheel in manifest.wheels} == {"files.pythonhosted.org"}
    assert manifest.total_bytes == sum(wheel.bytes for wheel in manifest.wheels) > 0
    assert any(wheel.name.startswith("onnxruntime_gpu-") for wheel in manifest.wheels)
    assert all(wheel.name.endswith("-win_amd64.whl") for wheel in manifest.wheels)


def _wheel_entry(name: str = MAIN_WHEEL, **changes: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "name": name,
        "url": f"https://files.pythonhosted.org/packages/ab/cd/{name}",
        "bytes": 10,
        "sha256": "a" * 64,
    }
    return {**entry, **changes}


@pytest.mark.parametrize(
    "changes",
    [
        {"url": "https://evil.example/packages/ab/cd/" + MAIN_WHEEL},
        {"url": "http://files.pythonhosted.org/packages/ab/cd/" + MAIN_WHEEL},
        {"url": "https://files.pythonhosted.org:8443/packages/ab/cd/" + MAIN_WHEEL},
        {"url": "https://user@files.pythonhosted.org/packages/ab/cd/" + MAIN_WHEEL},
        {"url": f"https://files.pythonhosted.org/packages/ab/cd/{MAIN_WHEEL}?token=x"},
        {"url": f"https://files.pythonhosted.org/packages/ab/cd/{MAIN_WHEEL}#x"},
        {"url": "https://files.pythonhosted.org/packages/ab/cd/other.whl"},
        {"url": "https://files.pythonhosted.org/simple/" + MAIN_WHEEL},
        {"sha256": "A" * 64},
        {"bytes": 0},
        {"name": "../x.whl"},
    ],
)
def test_manifest_rejects_foreign_urls_and_malformed_pins(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        GpuRuntimeWheel.model_validate(_wheel_entry(**changes))


def _manifest(wheels: list[dict[str, object]], **changes: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": 1,
        "runtime_id": "ort-1.0.0-cuda13-test",
        "onnxruntime_version": "1.0.0",
        "python_tag": PYTHON_TAG,
        "platform_tag": "win_amd64",
        "min_driver_major": 580,
        "min_compute_capability": "7.5",
        "wheels": wheels,
    }
    return {**base, **changes}


def test_manifest_needs_exactly_one_matching_runtime_and_unique_wheels() -> None:
    GpuRuntimeManifest.model_validate(_manifest([_wheel_entry(), _wheel_entry(CUDA_WHEEL)]))
    for wheels in (
        [_wheel_entry(CUDA_WHEEL)],
        [_wheel_entry(), _wheel_entry()],
        [_wheel_entry("onnxruntime_gpu-2.0.0-cp1-cp1-win_amd64.whl")],
    ):
        with pytest.raises(ValidationError):
            GpuRuntimeManifest.model_validate(_manifest(wheels))
    with pytest.raises(ValidationError):
        GpuRuntimeManifest.model_validate(_manifest([_wheel_entry()], platform_tag="linux_x86_64"))
    with pytest.raises(ValidationError):
        GpuRuntimeManifest.model_validate(_manifest([_wheel_entry()], extra_field=1))


# --- GPU detection -------------------------------------------------------------------


def _detect(three: str | None, two: str | None = None) -> GpuDetection:
    return detect_gpu(
        load_gpu_runtime_manifest(), query=lambda capability: three if capability else two
    )


@pytest.mark.parametrize(
    ("output", "state", "name", "driver"),
    [
        (
            "NVIDIA GeForce RTX 3090, 610.88, 8.6\n",
            "can_install",
            "NVIDIA GeForce RTX 3090",
            "610.88",
        ),
        (
            "NVIDIA GeForce RTX 2060, 580.12, 7.5\n",
            "can_install",
            "NVIDIA GeForce RTX 2060",
            "580.12",
        ),
        (
            "NVIDIA GeForce RTX 3090, 535.54, 8.6\n",
            "driver_too_old",
            "NVIDIA GeForce RTX 3090",
            "535.54",
        ),
        (
            "NVIDIA GeForce GTX 1080, 610.88, 6.1\n",
            "gpu_too_old",
            "NVIDIA GeForce GTX 1080",
            "610.88",
        ),
        (
            "NVIDIA GeForce GTX 1080, 610.88, 6.1\nNVIDIA GeForce RTX 3090, 610.88, 8.6\n",
            "can_install",
            "NVIDIA GeForce RTX 3090",
            "610.88",
        ),
        (
            "NVIDIA, Inc. RTX A4000, 610.88, 8.6\n",
            "can_install",
            "NVIDIA, Inc. RTX A4000",
            "610.88",
        ),
        (
            "NVIDIA GeForce RTX 3090, 610.88, [N/A]\n",
            "can_install",
            "NVIDIA GeForce RTX 3090",
            "610.88",
        ),
        ("", "no_nvidia_gpu", None, None),
        ("not csv at all\n\nGPU, abc, 8.6\n", "no_nvidia_gpu", None, None),
    ],
)
def test_detection_decides_from_driver_and_architecture(
    output: str, state: Any, name: str | None, driver: str | None
) -> None:
    assert _detect(output) == GpuDetection(state, name, driver)


def test_detection_falls_back_when_the_driver_cannot_report_capability() -> None:
    assert _detect(None, "NVIDIA GeForce RTX 3090, 610.88\n") == GpuDetection(
        "can_install", "NVIDIA GeForce RTX 3090", "610.88"
    )
    assert _detect(None, "NVIDIA GeForce RTX 3090, 470.10\n").state == "driver_too_old"
    assert _detect(None, None) == GpuDetection("no_nvidia_gpu")


def test_detection_asks_nothing_on_an_unsupported_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gpu_runtime, "install_supported", lambda manifest=None: False)

    def forbidden(_: bool) -> str:
        raise AssertionError("must not run nvidia-smi")

    assert detect_gpu(query=forbidden) == GpuDetection("unsupported_platform")


def test_real_platform_support_is_windows_source_launcher_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = load_gpu_runtime_manifest().model_copy(update={"python_tag": PYTHON_TAG})
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert REAL_INSTALL_SUPPORTED(manifest) is True
    other_python = manifest.model_copy(update={"python_tag": "cp399"})
    assert REAL_INSTALL_SUPPORTED(other_python) is False
    with monkeypatch.context() as scope:
        scope.setattr(sys, "platform", "linux")
        assert REAL_INSTALL_SUPPORTED(manifest) is False
    with monkeypatch.context() as scope:
        scope.setattr(sys, "frozen", True, raising=False)
        assert REAL_INSTALL_SUPPORTED(manifest) is False
    with monkeypatch.context() as scope:
        scope.setattr(platform, "machine", lambda: "ARM64")
        assert REAL_INSTALL_SUPPORTED(manifest) is False
    with monkeypatch.context() as scope:
        scope.setattr(sysconfig, "get_config_var", lambda name: 1)
        assert REAL_INSTALL_SUPPORTED(manifest) is False


def test_nvidia_smi_is_looked_up_in_absolute_places_and_run_without_a_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = _fresh(tmp_path, "bin")
    executable = folder / "nvidia-smi.exe"
    executable.write_bytes(b"")
    monkeypatch.setenv("SystemRoot", str(tmp_path / "no-system-root"))
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "no-program-files"))
    monkeypatch.setenv("PATH", "relative-folder")
    assert gpu_runtime._find_nvidia_smi() is None
    monkeypatch.setenv("PATH", os.pathsep.join(["relative-folder", str(folder)]))
    assert gpu_runtime._find_nvidia_smi() == str(executable)

    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(command: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
        calls.append((command, options))
        return subprocess.CompletedProcess(command, 0, stdout="GPU, 610.1, 8.6\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gpu_runtime.query_nvidia_smi(True) == "GPU, 610.1, 8.6\n"
    command, options = calls[0]
    assert command == [
        str(executable),
        "--query-gpu=name,driver_version,compute_cap",
        "--format=csv,noheader,nounits",
    ]
    assert options["timeout"] == 10 and "shell" not in options and options["check"] is False
    gpu_runtime.query_nvidia_smi(False)
    assert calls[1][0][1] == "--query-gpu=name,driver_version"


@pytest.mark.parametrize("failure", ["exit", "timeout", "missing", "huge"])
def test_nvidia_smi_failures_read_as_no_gpu(
    failure: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gpu_runtime, "_find_nvidia_smi", lambda: str(tmp_path / "nvidia-smi.exe"))

    def fake_run(command: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 10)
        if failure == "missing":
            raise FileNotFoundError
        return subprocess.CompletedProcess(
            command, 9 if failure == "exit" else 0, stdout="x" * 70_000, stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert gpu_runtime.query_nvidia_smi(True) is None


def test_nvidia_smi_absent_from_every_place_reads_as_no_gpu(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gpu_runtime, "_find_nvidia_smi", lambda: None)
    assert gpu_runtime.query_nvidia_smi(True) is None
    assert detect_gpu() == GpuDetection("no_nvidia_gpu")


def test_cached_detection_asks_once_per_window(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def counted() -> GpuDetection:
        calls.append(1)
        return GpuDetection("no_nvidia_gpu")

    clock = [100.0]
    monkeypatch.setattr(gpu_runtime, "detect_gpu", counted)
    monkeypatch.setattr(gpu_runtime, "_detection_cache", None)
    monkeypatch.setattr(gpu_runtime, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    gpu_runtime.detect_gpu_cached()
    gpu_runtime.detect_gpu_cached()
    assert len(calls) == 1
    clock[0] += 31
    gpu_runtime.detect_gpu_cached()
    assert len(calls) == 2


# --- unpacking -----------------------------------------------------------------------


def _zip_bytes(members: dict[str, bytes], *, symlink: str | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
        if symlink is not None:
            info = zipfile.ZipInfo(symlink)
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, b"target")
    return buffer.getvalue()


def _extract(folder: Path, data: bytes, cancelled: Callable[[], bool] = lambda: False) -> Path:
    wheel = folder / "w.whl"
    wheel.write_bytes(data)
    destination = folder / "out"
    destination.mkdir(exist_ok=True)
    gpu_runtime._extract(wheel, destination, cancelled)
    return destination


def test_extraction_keeps_only_the_package_and_nvidia_dlls(tmp_path: Path) -> None:
    out = _extract(
        tmp_path,
        _zip_bytes(
            {
                "onnxruntime/__init__.py": b"x = 1",
                "onnxruntime/capi/provider.dll": b"dll",
                "nvidia/cu13/bin/x86_64/cublas64_13.dll": b"dll",
                "nvidia/cu13/include/cublas.h": b"header",
                "nvidia/cudnn/lib/cudnn.lib": b"lib",
                "onnxruntime_gpu-1.0.0.dist-info/METADATA": b"meta",
            }
        ),
    )
    found = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert found == [
        "nvidia/cu13/bin/x86_64/cublas64_13.dll",
        "onnxruntime/__init__.py",
        "onnxruntime/capi/provider.dll",
    ]


@pytest.mark.parametrize(
    "member", ["nvidia/../evil.dll", "onnxruntime/C:evil.py", "onnxruntime/a//b.py"]
)
def test_extraction_refuses_names_that_could_escape(tmp_path: Path, member: str) -> None:
    folder = _fresh(tmp_path, "case")
    with pytest.raises(GpuRuntimeError) as error:
        _extract(folder, _zip_bytes({member: b"x"}))
    assert error.value.code == "gpu_runtime_extract"
    assert not (folder / "evil.dll").exists()


def test_extraction_refuses_links_duplicates_oversize_and_broken_archives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(GpuRuntimeError) as link:
        _extract(_fresh(tmp_path, "link"), _zip_bytes({}, symlink="onnxruntime/link"))
    assert link.value.code == "gpu_runtime_extract"

    twice = _fresh(tmp_path, "twice")
    _extract(twice, _zip_bytes({"onnxruntime/a.py": b"one"}))
    with pytest.raises(GpuRuntimeError):  # a second wheel may not overwrite the first
        gpu_runtime._extract(twice / "w.whl", twice / "out", lambda: False)

    with pytest.raises(GpuRuntimeError):
        _extract(_fresh(tmp_path, "broken"), b"not a zip")

    monkeypatch.setattr(gpu_runtime, "_MAX_MEMBER_BYTES", 3)
    with pytest.raises(GpuRuntimeError):
        _extract(_fresh(tmp_path, "big"), _zip_bytes({"onnxruntime/big.bin": b"12345"}))


def test_extraction_refuses_paths_over_the_windows_limit_and_honours_cancel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deep = _zip_bytes({"onnxruntime/capi/deep/name.dll": b"x"})
    with monkeypatch.context() as scope:
        scope.setattr(gpu_runtime, "_MAX_PATH", 20)
        with pytest.raises(GpuRuntimeError) as error:
            _extract(_fresh(tmp_path, "long"), deep)
    assert error.value.code == "gpu_runtime_path"
    with pytest.raises(BuiltinDownloadCancelled):
        _extract(_fresh(tmp_path, "stop"), _zip_bytes({"onnxruntime/a.py": b"data"}), lambda: True)


# --- the install ---------------------------------------------------------------------


class FakeTransport:
    def __init__(self, blobs: dict[str, bytes]) -> None:
        self.blobs = blobs
        self.opened: list[tuple[str, int]] = []
        self.on_open: Callable[[], None] = lambda: None

    @contextmanager
    def open(self, artifact: BuiltinArtifactFile, *, offset: int) -> Iterator[DownloadResponse]:
        self.opened.append((artifact.name, offset))
        self.on_open()
        data = self.blobs[artifact.name]
        headers = {"content-length": str(len(data) - offset)}
        if offset:
            headers["content-range"] = f"bytes {offset}-{len(data) - 1}/{len(data)}"
        yield DownloadResponse(206 if offset else 200, headers, io.BytesIO(data[offset:]))


def _fixture_wheels() -> tuple[GpuRuntimeManifest, dict[str, bytes]]:
    blobs = {
        MAIN_WHEEL: _zip_bytes(
            {
                "onnxruntime/__init__.py": b"import numpy",
                "onnxruntime/capi/onnxruntime_providers_cuda.dll": b"provider" * 100,
                "onnxruntime_gpu-1.0.0.dist-info/METADATA": b"skipped",
            }
        ),
        CUDA_WHEEL: _zip_bytes({"nvidia/cu13/bin/x86_64/cublas64_13.dll": b"cublas" * 500}),
    }
    manifest = GpuRuntimeManifest.model_validate(
        _manifest(
            [
                _wheel_entry(name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
                for name, data in blobs.items()
            ]
        )
    )
    return manifest, blobs


def _install(
    tmp_path: Path,
    manifest: GpuRuntimeManifest,
    transport: FakeTransport,
    *,
    self_check: Callable[[Path, Callable[[], bool]], None] | None = None,
    cancelled: Callable[[], bool] = lambda: False,
    progress: list[tuple[int, int]] | None = None,
) -> Path:
    seen = progress if progress is not None else []
    return install_gpu_runtime(
        tmp_path,
        transport=transport,
        cancelled=cancelled,
        on_progress=lambda done, total: seen.append((done, total)),
        manifest=manifest,
        self_check=self_check or (lambda root, stop: None),
    )


def test_install_downloads_verifies_unpacks_proves_and_publishes(tmp_path: Path) -> None:
    manifest, blobs = _fixture_wheels()
    transport = FakeTransport(blobs)
    checked: list[tuple[Path, bool]] = []

    def self_check(root: Path, stop: Callable[[], bool]) -> None:
        checked.append((root, (root / "onnxruntime" / "__init__.py").is_file()))

    progress: list[tuple[int, int]] = []
    final = _install(tmp_path, manifest, transport, self_check=self_check, progress=progress)
    folder = tmp_path / "gpu-runtime"
    assert final == folder / manifest.runtime_id
    assert installed_runtime(tmp_path, manifest) == final
    provider = final / "onnxruntime" / "capi" / "onnxruntime_providers_cuda.dll"
    assert provider.read_bytes() == b"provider" * 100
    assert (final / "nvidia" / "cu13" / "bin" / "x86_64" / "cublas64_13.dll").is_file()
    assert not (final / "onnxruntime_gpu-1.0.0.dist-info").exists()
    assert json.loads((final / "READY.json").read_text()) == {
        "runtime_id": manifest.runtime_id,
        "wheels": {wheel.name: wheel.sha256 for wheel in manifest.wheels},
    }
    assert [item.name for item in folder.iterdir()] == [manifest.runtime_id]
    assert [name for name, _ in transport.opened] == [wheel.name for wheel in manifest.wheels]
    assert checked == [(folder / f"{manifest.runtime_id}.staging", True)]
    done = [value for value, _ in progress]
    assert done == sorted(done) and progress[-1] == (manifest.total_bytes, manifest.total_bytes)
    assert {total for _, total in progress} == {manifest.total_bytes}
    # A second run finds the published folder and fetches nothing.
    again: list[tuple[int, int]] = []
    assert _install(tmp_path, manifest, transport, progress=again) == final
    assert len(transport.opened) == 2 and again == [(manifest.total_bytes, manifest.total_bytes)]


def test_install_refuses_a_download_that_does_not_match_its_pin(tmp_path: Path) -> None:
    manifest, blobs = _fixture_wheels()
    tampered = bytearray(blobs[CUDA_WHEEL])
    tampered[-1] ^= 0xFF
    transport = FakeTransport({**blobs, CUDA_WHEEL: bytes(tampered)})
    with pytest.raises(BuiltinDownloadError) as error:
        _install(tmp_path, manifest, transport)
    assert error.value.code == "builtin_download_checksum"
    folder = tmp_path / "gpu-runtime"
    assert installed_runtime(tmp_path, manifest) is None
    assert not (folder / manifest.runtime_id).exists()
    assert not list((folder / f"{manifest.runtime_id}.download").glob("*.part"))


def test_failed_self_check_publishes_nothing_and_keeps_verified_wheels_for_a_retry(
    tmp_path: Path,
) -> None:
    manifest, blobs = _fixture_wheels()
    transport = FakeTransport(blobs)

    def refuse(root: Path, stop: Callable[[], bool]) -> None:
        raise GpuRuntimeError("gpu_runtime_self_check")

    with pytest.raises(GpuRuntimeError) as error:
        _install(tmp_path, manifest, transport, self_check=refuse)
    assert error.value.code == "gpu_runtime_self_check"
    folder = tmp_path / "gpu-runtime"
    assert installed_runtime(tmp_path, manifest) is None
    assert not (folder / f"{manifest.runtime_id}.staging").exists()
    assert not (folder / manifest.runtime_id).exists()
    kept = sorted(path.name for path in (folder / f"{manifest.runtime_id}.download").iterdir())
    assert kept == sorted(wheel.name for wheel in manifest.wheels)
    opened = len(transport.opened)
    assert _install(tmp_path, manifest, transport).name == manifest.runtime_id
    assert len(transport.opened) == opened, "the retry reuses the verified wheels"
    assert not (folder / f"{manifest.runtime_id}.download").exists()


def test_cancelled_install_stops_and_publishes_nothing(tmp_path: Path) -> None:
    manifest, blobs = _fixture_wheels()
    transport = FakeTransport(blobs)
    stop = [False]
    transport.on_open = lambda: stop.__setitem__(0, True)
    with pytest.raises(BuiltinDownloadCancelled):
        _install(tmp_path, manifest, transport, cancelled=lambda: stop[0])
    assert installed_runtime(tmp_path, manifest) is None
    assert not (tmp_path / "gpu-runtime" / manifest.runtime_id).exists()


def test_install_checks_free_space_before_downloading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, blobs = _fixture_wheels()
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda path: usage(10**9, 10**9 - 5, 5))
    transport = FakeTransport(blobs)
    with pytest.raises(BuiltinDownloadError) as error:
        _install(tmp_path, manifest, transport)
    assert error.value.code == "builtin_download_disk_space" and transport.opened == []


def test_install_replaces_an_invalid_folder_and_removes_only_its_own_old_versions(
    tmp_path: Path,
) -> None:
    manifest, blobs = _fixture_wheels()
    folder = tmp_path / "gpu-runtime"
    broken = folder / manifest.runtime_id
    broken.mkdir(parents=True)
    (broken / "junk.txt").write_text("no marker")
    old = _fresh(folder, "ort-0.9.0-cuda13-test")
    (old / "stale.dll").write_bytes(b"x")
    unrelated = _fresh(folder, "keep-me")
    final = _install(tmp_path, manifest, FakeTransport(blobs))
    assert not (final / "junk.txt").exists() and installed_runtime(tmp_path, manifest) == final
    assert not old.exists() and unrelated.is_dir()


def test_install_refuses_when_the_platform_is_not_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, blobs = _fixture_wheels()
    monkeypatch.setattr(gpu_runtime, "install_supported", lambda manifest=None: False)
    transport = FakeTransport(blobs)
    with pytest.raises(GpuRuntimeError) as error:
        _install(tmp_path, manifest, transport)
    assert error.value.code == "gpu_runtime_unsupported" and transport.opened == []


def test_a_marker_for_other_wheels_does_not_count_as_installed(tmp_path: Path) -> None:
    manifest, blobs = _fixture_wheels()
    final = _install(tmp_path, manifest, FakeTransport(blobs))
    assert installed_runtime(tmp_path, manifest) == final
    (final / "READY.json").write_text(json.dumps({"runtime_id": manifest.runtime_id}))
    assert installed_runtime(tmp_path, manifest) is None
    (final / "READY.json").write_text("not json")
    assert installed_runtime(tmp_path, manifest) is None
    (final / "READY.json").unlink()
    assert installed_runtime(tmp_path, manifest) is None


# --- activation ----------------------------------------------------------------------


def _published_runtime(data_dir: Path) -> Path:
    manifest = load_gpu_runtime_manifest()
    root = gpu_runtime.runtime_directory(data_dir) / manifest.runtime_id
    (root / "onnxruntime" / "capi").mkdir(parents=True)
    cublas = root / "nvidia" / "cu13" / "bin" / "x86_64"
    cublas.mkdir(parents=True)
    (cublas / "cublas64_13.dll").write_bytes(b"x")
    cudnn = root / "nvidia" / "cudnn" / "bin"
    cudnn.mkdir(parents=True)
    (cudnn / "cudnn64_9.dll").write_bytes(b"x")
    (root / "READY.json").write_text(json.dumps(gpu_runtime._ready_payload(manifest)))
    return root


def test_activation_puts_the_runtime_first_only_before_onnxruntime_is_imported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _published_runtime(tmp_path)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setenv("PATH", "base")
    monkeypatch.setattr(gpu_runtime, "_active_runtime", None)
    added: list[str] = []
    monkeypatch.setattr(os, "add_dll_directory", added.append, raising=False)

    assert "onnxruntime" in sys.modules, "an earlier import means it is too late to switch"
    assert activate_gpu_runtime(tmp_path) is False and not gpu_runtime.gpu_runtime_active()
    assert str(root) not in sys.path

    monkeypatch.delitem(sys.modules, "onnxruntime")
    assert activate_gpu_runtime(tmp_path) is True and gpu_runtime.gpu_runtime_active()
    assert sys.path[0] == str(root)
    folders = [
        str(root / "onnxruntime" / "capi"),
        str(root / "nvidia" / "cu13" / "bin" / "x86_64"),
        str(root / "nvidia" / "cudnn" / "bin"),
    ]
    assert added == folders
    assert os.environ["PATH"].split(os.pathsep) == [*folders, "base"]
    assert activate_gpu_runtime(tmp_path) is True and sys.path.count(str(root)) == 1


def test_activation_ignores_a_missing_or_mismatched_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(gpu_runtime, "_active_runtime", None)
    monkeypatch.delitem(sys.modules, "onnxruntime")
    before = list(sys.path)
    assert activate_gpu_runtime(tmp_path) is False
    root = _published_runtime(tmp_path)
    (root / "READY.json").write_text(json.dumps({"runtime_id": "other"}))
    assert activate_gpu_runtime(tmp_path) is False and sys.path == before
    (root / "READY.json").write_text(
        json.dumps(gpu_runtime._ready_payload(load_gpu_runtime_manifest()))
    )
    monkeypatch.setattr(gpu_runtime, "install_supported", lambda manifest=None: False)
    assert activate_gpu_runtime(tmp_path) is False and sys.path == before


def test_onnxruntime_import_preloads_cuda_libraries_once_when_the_runtime_is_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    monkeypatch.setattr(ort, "preload_dlls", lambda: calls.append(1), raising=False)
    monkeypatch.setattr(builtin_onnx, "_cuda_preloaded", False)
    monkeypatch.setattr(builtin_onnx, "gpu_runtime_active", lambda: False)
    assert builtin_onnx._ort() is ort and calls == []
    monkeypatch.setattr(builtin_onnx, "gpu_runtime_active", lambda: True)
    builtin_onnx._ort()
    builtin_onnx._ort()
    assert calls == [1]


def test_gpu_counts_as_available_once_the_runtime_is_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ort, "get_available_providers", lambda: ["CPUExecutionProvider"])
    monkeypatch.setattr(builtin_onnx, "gpu_runtime_active", lambda: False)
    assert builtin_onnx.gpu_available() is False
    monkeypatch.setattr(builtin_onnx, "gpu_runtime_active", lambda: True)
    monkeypatch.setattr(builtin_onnx, "_cuda_preloaded", True)
    assert builtin_onnx.gpu_available() is True


# --- the proof in a child process ----------------------------------------------------

_STUB = """
import numpy as np


def preload_dlls():
    pass


class SessionOptions:
    log_severity_level = 0


class InferenceSession:
    def __init__(self, model, sess_options=None, providers=None):
        assert isinstance(model, bytes) and providers[0] == "CUDAExecutionProvider"
        {constructor}

    def disable_fallback(self):
        pass

    def get_providers(self):
        return {providers}

    def run(self, names, feed):
        return [feed["x"] + {offset}]
"""


class _Records(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture
def records() -> Iterator[_Records]:
    handler = _Records()
    logger = logging.getLogger("reponpc.providers.gpu_runtime")
    level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    yield handler
    logger.removeHandler(handler)
    logger.setLevel(level)


def _stub_runtime(
    tmp_path: Path,
    *,
    constructor: str = "pass",
    providers: str = '["CUDAExecutionProvider", "CPUExecutionProvider"]',
    offset: str = "0.0",
) -> Path:
    package = tmp_path / "runtime" / "onnxruntime"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        _STUB.format(constructor=constructor, providers=providers, offset=offset)
    )
    return package.parent


def test_self_check_child_accepts_a_runtime_that_creates_a_cuda_session(
    tmp_path: Path, records: _Records
) -> None:
    run_self_check(_stub_runtime(tmp_path), lambda: False)
    assert records.messages == []


@pytest.mark.parametrize(
    ("variant", "exit_code"),
    [
        ({"constructor": 'raise RuntimeError("no CUDA")'}, 4),
        ({"providers": '["CPUExecutionProvider"]'}, 5),
        ({"offset": "1.0"}, 7),
    ],
)
def test_self_check_child_names_the_failed_stage_without_leaking_detail(
    tmp_path: Path, records: _Records, variant: dict[str, str], exit_code: int
) -> None:
    with pytest.raises(GpuRuntimeError) as error:
        run_self_check(_stub_runtime(tmp_path, **variant), lambda: False)
    assert error.value.code == "gpu_runtime_self_check"
    assert str(error.value) == "GPU runtime installation failed"
    assert records.messages == [f"gpu_runtime_self_check_failed exit={exit_code}"]


def test_self_check_child_rejects_a_runtime_folder_without_its_own_onnxruntime(
    tmp_path: Path, records: _Records
) -> None:
    with pytest.raises(GpuRuntimeError):
        run_self_check(_fresh(tmp_path, "empty"), lambda: False)
    assert records.messages == ["gpu_runtime_self_check_failed exit=3"]


class _HungProcess:
    killed = 0

    def wait(self, timeout: float | None = None) -> int:
        if self.killed:
            return -9
        raise subprocess.TimeoutExpired("child", timeout or 0)

    def kill(self) -> None:
        self.killed += 1


def test_self_check_stops_the_child_on_cancel_and_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hung = _HungProcess()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: hung)
    with pytest.raises(BuiltinDownloadCancelled):
        run_self_check(tmp_path, lambda: True)
    assert hung.killed == 1
    other = _HungProcess()
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: other)
    monkeypatch.setattr(gpu_runtime, "_SELF_CHECK_SECONDS", 0)
    with pytest.raises(GpuRuntimeError):
        run_self_check(tmp_path, lambda: False)
    assert other.killed == 1


def test_hand_encoded_check_model_is_valid_and_computes_a_matmul() -> None:
    session = ort.InferenceSession(check_model(), providers=["CPUExecutionProvider"])
    (answer,) = session.run(None, {"x": np.array([[3.0]], dtype=np.float32)})
    assert float(answer[0][0]) == 3.0


# --- the pinned download transport ---------------------------------------------------


class _Response:
    def __init__(self, status: int = 200, headers: list[tuple[str, str]] | None = None) -> None:
        self.status = status
        self.headers = headers or []
        self.body = io.BytesIO(b"wheel-bytes")

    def getheader(self, name: str) -> str | None:
        values = [value for key, value in self.headers if key.lower() == name.lower()]
        return ", ".join(values) if values else None

    def getheaders(self) -> list[tuple[str, str]]:
        return self.headers[:]

    def read(self, size: int) -> bytes:
        return self.body.read(size)


class _Connection:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.closed = 0

    def request(self, method: str, target: str, *, headers: dict[str, str]) -> None:
        self.requests.append((method, target, dict(headers)))

    def getresponse(self) -> _Response:
        return self.response

    def close(self) -> None:
        self.closed += 1


def _public_dns() -> list[tuple[Any, ...]]:
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))]


def _pinned(
    monkeypatch: pytest.MonkeyPatch, responses: list[_Response]
) -> tuple[list[_Connection], list[tuple[Any, ...]], list[tuple[str, int]]]:
    connections: list[_Connection] = []
    pins: list[tuple[Any, ...]] = []
    resolutions: list[tuple[str, int]] = []

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("transport test attempted real socket access")

    def resolve(host: str, port: int, *, type: int) -> list[tuple[Any, ...]]:
        assert type == socket.SOCK_STREAM
        resolutions.append((host, port))
        return _public_dns()

    def connect(host: str, port: int, address: Any, timeout: float) -> _Connection:
        connection = _Connection(responses[len(connections)])
        connections.append(connection)
        pins.append((host, port, address, timeout))
        return connection

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(builtin_http, "_PinnedHTTPSConnection", connect)
    return connections, pins, resolutions


def _first_wheel() -> GpuRuntimeWheel:
    return load_gpu_runtime_manifest().wheels[0]


def _artifact(wheel: GpuRuntimeWheel | None = None) -> BuiltinArtifactFile:
    wheel = wheel or _first_wheel()
    return BuiltinArtifactFile(name=wheel.name, bytes=wheel.bytes, sha256=wheel.sha256)


def test_wheel_transport_streams_only_the_pinned_url_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = _Response()
    connections, pins, resolutions = _pinned(monkeypatch, [response])
    monkeypatch.setenv("HTTPS_PROXY", "http://example-nonsecret.invalid:9999")
    with builtin_http.PinnedGpuWheelTransport().open(_artifact(), offset=7) as result:
        assert result.status == 200 and result.stream.read(5) == b"wheel"
        assert connections[0].closed == 0
    assert connections[0].closed == 1
    method, target, headers = connections[0].requests[0]
    assert method == "GET" and target == urlsplit(_first_wheel().url).path
    assert headers == {
        "Accept-Encoding": "identity",
        "User-Agent": "RepoNPC/1.0",
        "Range": "bytes=7-",
    }
    assert resolutions == [("files.pythonhosted.org", 443)]
    address = (*_public_dns()[0][:3], _public_dns()[0][4])
    assert pins == [("files.pythonhosted.org", 443, address, 15.0)]


@pytest.mark.parametrize(
    "url",
    [
        "https://huggingface.co/x.whl",
        "https://cdn-lfs.huggingface.co/x.whl",
        "https://files.pythonhosted.org.evil.invalid/x.whl",
        "https://evilfiles.pythonhosted.org/x.whl",
        "http://files.pythonhosted.org/x.whl",
        "https://files.pythonhosted.org:444/x.whl",
        "https://user:example-nonsecret@files.pythonhosted.org/x.whl",
        "https://files.pythonhosted.org@127.0.0.1/x.whl",
        "https://files.pythonhosted.org/x.whl#example-nonsecret",
        "https://files.pythonhosted.org/x name.whl",
    ],
)
def test_wheel_transport_refuses_other_hosts_and_unsafe_urls(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    connections, pins, resolutions = _pinned(monkeypatch, [])
    with pytest.raises(BuiltinDownloadError) as error:
        builtin_http.PinnedGpuWheelTransport()._connection(url)
    assert error.value.code == "builtin_download_http"
    assert connections == pins == resolutions == []


def test_the_two_transports_do_not_share_their_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    connections, _, _ = _pinned(monkeypatch, [])
    with pytest.raises(BuiltinDownloadError):
        builtin_http.PinnedBuiltinHttpTransport()._connection("https://files.pythonhosted.org/x")
    assert connections == []


def test_wheel_transport_refuses_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    redirect = _Response(302, [("Location", "https://files.pythonhosted.org/elsewhere.whl")])
    connections, _, resolutions = _pinned(monkeypatch, [redirect, _Response()])
    with (
        pytest.raises(BuiltinDownloadError) as error,
        builtin_http.PinnedGpuWheelTransport().open(_artifact(), offset=0),
    ):
        pytest.fail("a redirect was followed")
    assert error.value.code == "builtin_download_http"
    assert len(connections) == 1 and connections[0].closed == 1
    assert resolutions == [("files.pythonhosted.org", 443)]


def test_wheel_transport_refuses_unpinned_files_and_bad_offsets_before_any_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connections, _, resolutions = _pinned(monkeypatch, [])
    altered = _artifact().model_copy(update={"sha256": "b" * 64})
    transport = builtin_http.PinnedGpuWheelTransport()
    for artifact, offset in ((altered, 0), (_artifact(), -1), (_artifact(), _first_wheel().bytes)):
        with pytest.raises(BuiltinDownloadError), transport.open(artifact, offset=offset):
            pytest.fail("an unpinned request was opened")
    assert connections == resolutions == []


@pytest.mark.parametrize("phase", ["request", "read"])
def test_wheel_transport_turns_network_failures_into_a_safe_error(
    monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    response = _Response()
    connections, _, _ = _pinned(monkeypatch, [response])
    failure = HTTPException("example-nonsecret-body")
    if phase == "request":

        def broken(self: _Connection, *args: Any, **kwargs: Any) -> None:
            raise failure

        monkeypatch.setattr(_Connection, "request", broken)
    else:
        response.read = cast(Any, lambda size: (_ for _ in ()).throw(failure))  # type: ignore[method-assign]
    with (
        pytest.raises(BuiltinDownloadError) as error,
        builtin_http.PinnedGpuWheelTransport().open(_artifact(), offset=0) as result,
    ):
        result.stream.read(3)
    assert error.value.code == "builtin_download_http" and error.value.__cause__ is None
    assert connections[0].closed == 1


# --- the operation lane and the admin status -----------------------------------------


def _wait_terminal(coordinator: OllamaModelOperationCoordinator, operation_id: str) -> Any:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        operation = coordinator.get(operation_id)
        if operation.status in {"succeeded", "failed", "cancelled"}:
            return operation
        time.sleep(0.01)
    raise AssertionError("operation did not finish")


def test_gpu_operation_needs_consent_and_reports_failures_by_stable_code() -> None:
    def fail(*, cancelled: Callable[[], bool], on_progress: Callable[[int, int], None]) -> None:
        on_progress(1, 2)
        raise GpuRuntimeError("gpu_runtime_self_check")

    coordinator = OllamaModelOperationCoordinator(cast(Any, object()), gpu_runtime_install=fail)
    try:
        for confirmed in (False, None):
            with pytest.raises(EmbeddingProfileError) as refused:
                coordinator.queue_gpu_runtime(confirmed=cast(Any, confirmed))
            assert refused.value.code == "VALIDATION_ERROR"
        assert coordinator.latest_gpu_runtime() is None
        started = coordinator.queue_gpu_runtime(confirmed=True)
        assert started.model_id == GPU_RUNTIME_MODEL_ID and started.profile_id == ""
        done = _wait_terminal(coordinator, started.operation_id)
        assert done.status == "failed" and done.error_code == "GPU_RUNTIME_SELF_CHECK"
        assert (done.completed, done.total) == (1, 2)
        assert coordinator.latest_gpu_runtime() == done
        assert coordinator.latest_builtin() is None
    finally:
        coordinator.shutdown()
    unconfigured = OllamaModelOperationCoordinator(cast(Any, object()))
    try:
        with pytest.raises(EmbeddingProfileError):
            unconfigured.queue_gpu_runtime(confirmed=True)
    finally:
        unconfigured.shutdown()


def test_gpu_operation_success_does_not_touch_any_embedding_profile() -> None:
    def work(*, cancelled: Callable[[], bool], on_progress: Callable[[int, int], None]) -> None:
        on_progress(2, 2)

    class NoProfiles:
        def __getattr__(self, name: str) -> Any:
            raise AssertionError(f"the profile registry must not be used: {name}")

    coordinator = OllamaModelOperationCoordinator(cast(Any, NoProfiles()), gpu_runtime_install=work)
    try:
        started = coordinator.queue_gpu_runtime(confirmed=True)
        done = _wait_terminal(coordinator, started.operation_id)
        assert done.status == "succeeded" and done.error_code is None
    finally:
        coordinator.shutdown()


def _status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, detection: GpuDetection, available: bool
) -> dict[str, Any]:
    monkeypatch.setattr(operation_module, "detect_gpu_cached", lambda: detection)
    monkeypatch.setattr(operation_module, "gpu_available", lambda: available)
    operations = AdminOperations(
        database=cast(Any, None), public_base_url="", data_directory=tmp_path
    )
    return cast(dict[str, Any], operations.gpu_runtime_status())


def test_status_reports_what_blocks_the_install_or_that_it_can_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = load_gpu_runtime_manifest()
    can = GpuDetection("can_install", "NVIDIA GeForce RTX 3090", "610.88")
    assert _status(tmp_path, monkeypatch, detection=can, available=False) == {
        "state": "can_install",
        "gpu_name": "NVIDIA GeForce RTX 3090",
        "driver_version": "610.88",
        "minimum_driver": 580,
        "download_bytes": manifest.total_bytes,
        "required_free_bytes": manifest.total_bytes * gpu_runtime.SPACE_FACTOR,
        "operation": None,
    }
    for state in ("no_nvidia_gpu", "driver_too_old", "gpu_too_old", "unsupported_platform"):
        blocked = _status(
            tmp_path, monkeypatch, detection=GpuDetection(cast(Any, state)), available=False
        )
        assert blocked["state"] == state


def test_status_says_restart_required_once_installed_and_ready_once_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    can = GpuDetection("can_install", "NVIDIA GeForce RTX 3090", "610.88")
    _published_runtime(tmp_path)
    restart = _status(tmp_path, monkeypatch, detection=can, available=False)
    assert restart["state"] == "restart_required"
    assert _status(tmp_path, monkeypatch, detection=can, available=True)["state"] == "ready"
    none = GpuDetection("no_nvidia_gpu")
    assert _status(tmp_path, monkeypatch, detection=none, available=True)["state"] == "ready"
