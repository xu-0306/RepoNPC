"""Device-check fixtures never invoke a real GPU tool or inspect owner runtime."""

from __future__ import annotations

import ctypes
import io
import subprocess
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from reponpc.admin import device_check as device

GIB = 1024**3
MIB = 1024**2


@pytest.fixture(autouse=True)
def isolated_observations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(device.sys, "platform", "linux")
    monkeypatch.setattr(device.shutil, "which", lambda _name: None)
    monkeypatch.setattr(device.shutil, "disk_usage", lambda _path: SimpleNamespace(free=10 * GIB))
    monkeypatch.setattr(device.os, "sysconf", lambda _name: -1, raising=False)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a real process must not run during device unit tests")

    monkeypatch.setattr(device.subprocess, "Popen", forbidden)


def _proc(monkeypatch: pytest.MonkeyPatch, **changes: str | None) -> dict[str, str | None]:
    files: dict[str, str | None] = {
        "/proc/meminfo": "MemTotal: 16777216 kB\nMemAvailable: 8388608 kB\n",
        "/proc/self/cgroup": "0::/\n",
        "/proc/self/mountinfo": "29 23 0:26 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n",
        "/sys/fs/cgroup/memory.max": "max\n",
        **changes,
    }

    def read(path: Path, *, missing: str | None = None) -> str | None:
        return files.get(path.as_posix(), missing)

    monkeypatch.setattr(device, "_read_text", read)
    return files


def _windows(
    monkeypatch: pytest.MonkeyPatch,
    *,
    total: int = 16 * GIB,
    free: int = 6 * GIB,
    success: bool = True,
) -> None:
    monkeypatch.setattr(device.sys, "platform", "win32")

    def memory(pointer: Any) -> int:
        status = ctypes.cast(pointer, ctypes.POINTER(device._MemoryStatus)).contents
        assert status.dwLength == ctypes.sizeof(device._MemoryStatus)
        status.ullTotalPhys, status.ullAvailPhys = total, free
        return int(success)

    def library(name: str, *, use_last_error: bool) -> SimpleNamespace:
        assert name == "kernel32" and use_last_error
        return SimpleNamespace(GlobalMemoryStatusEx=memory)

    monkeypatch.setattr(device.ctypes, "WinDLL", library, raising=False)


def test_windows_observes_physical_available_and_data_volume_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _windows(monkeypatch)
    visited = []

    def disk(path: Path) -> SimpleNamespace:
        visited.append(path)
        return SimpleNamespace(free=7 * GIB)

    monkeypatch.setattr(device.shutil, "disk_usage", disk)
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes == 16 * GIB
    assert result.free_memory_bytes == 6 * GIB
    assert result.free_disk_bytes == 7 * GIB
    assert result.gpu_vram_bytes is None
    assert visited == [tmp_path]
    assert result.host_memory_bandwidth_bytes_per_second is None
    assert result.gpu_memory_bandwidth_bytes_per_second is None


def test_windows_failure_and_inconsistent_observation_stay_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _windows(monkeypatch, success=False)
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes is None and result.free_memory_bytes is None
    _windows(monkeypatch, total=1, free=2)
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes == 1 and result.free_memory_bytes is None


def test_windows_native_access_denied_is_not_exposed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(device.sys, "platform", "win32")

    def denied(*_args: object, **_kwargs: object) -> None:
        raise OSError("synthetic-private-path-and-identity")

    monkeypatch.setattr(device.ctypes, "WinDLL", denied, raising=False)
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes is None and result.free_memory_bytes is None
    assert "synthetic-private" not in repr(result)


def test_linux_unlimited_cgroup_uses_observed_ram(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _proc(monkeypatch)
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes == 16 * GIB
    assert result.free_memory_bytes == 8 * GIB


def test_linux_zero_available_is_a_known_observation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _proc(monkeypatch, **{"/proc/meminfo": "MemTotal: 16777216 kB\nMemAvailable: 0 kB\n"})
    assert device.collect_hardware_profile(tmp_path).free_memory_bytes == 0


def test_linux_sysconf_fallback_requires_real_valid_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _proc(monkeypatch, **{"/proc/meminfo": None})
    values = {"SC_PHYS_PAGES": 1_000_000, "SC_AVPHYS_PAGES": 500_000, "SC_PAGE_SIZE": 4096}
    monkeypatch.setattr(device.os, "sysconf", lambda name: values[name])
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes == 4_096_000_000
    assert result.free_memory_bytes == 2_048_000_000


@pytest.mark.parametrize("value", [-1, True, 1.5, "1024", 2**64])
def test_invalid_sysconf_values_are_not_capacities(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: Any
) -> None:
    _proc(monkeypatch, **{"/proc/meminfo": None})
    monkeypatch.setattr(device.os, "sysconf", lambda _name: value)
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes is None and result.free_memory_bytes is None


def test_linux_child_and_parent_cgroup_constraints_both_apply(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _proc(
        monkeypatch,
        **{
            "/proc/self/cgroup": "0::/group/child\n",
            "/sys/fs/cgroup/group/child/memory.max": str(6 * GIB),
            "/sys/fs/cgroup/group/child/memory.current": str(2 * GIB),
            "/sys/fs/cgroup/group/memory.max": str(8 * GIB),
            "/sys/fs/cgroup/group/memory.current": str(7 * GIB),
        },
    )
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes == 6 * GIB
    assert result.free_memory_bytes == GIB


def test_linux_mount_root_is_mapped_to_process_membership(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _proc(
        monkeypatch,
        **{
            "/proc/self/cgroup": "0::/container-private/child\n",
            "/proc/self/mountinfo": (
                "29 23 0:26 /container-private /sys/fs/cgroup rw - cgroup2 cgroup rw\n"
            ),
            "/sys/fs/cgroup/child/memory.max": str(4 * GIB),
            "/sys/fs/cgroup/child/memory.current": str(GIB),
        },
    )
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes == 4 * GIB
    assert result.free_memory_bytes == 3 * GIB
    assert "container-private" not in repr(result)


def test_linux_v1_memory_controller_limit_is_effective(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _proc(
        monkeypatch,
        **{
            "/proc/self/cgroup": "5:memory:/box\n4:cpu,cpuacct:/box\n",
            "/proc/self/mountinfo": (
                "31 23 0:28 / /sys/fs/cgroup/memory rw - cgroup cgroup rw,memory\n"
            ),
            "/sys/fs/cgroup/memory/box/memory.limit_in_bytes": str(4 * GIB),
            "/sys/fs/cgroup/memory/box/memory.usage_in_bytes": str(3 * GIB),
            "/sys/fs/cgroup/memory/memory.limit_in_bytes": "9223372036854771712",
            "/sys/fs/cgroup/memory/memory.usage_in_bytes": "0",
        },
    )
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes == 4 * GIB
    assert result.free_memory_bytes == GIB


def test_linux_known_v1_membership_without_memory_controller(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _proc(monkeypatch, **{"/proc/self/cgroup": "4:cpu,cpuacct:/box\n"})
    assert device.collect_hardware_profile(tmp_path).free_memory_bytes == 8 * GIB


@pytest.mark.parametrize(
    "path,value",
    [
        ("/proc/self/cgroup", None),
        ("/proc/self/cgroup", ""),
        ("/proc/self/cgroup", "unsupported line"),
        ("/proc/self/cgroup", "0::relative"),
        ("/proc/self/cgroup", "0::/../escape"),
        ("/proc/self/cgroup", "0::/\n0::/other"),
        ("/proc/self/mountinfo", None),
        ("/proc/self/mountinfo", "malformed"),
        ("/sys/fs/cgroup/memory.max", None),
        ("/sys/fs/cgroup/memory.max", "unlimited"),
        ("/sys/fs/cgroup/memory.max", "-1"),
        ("/sys/fs/cgroup/memory.max", str(2**64)),
    ],
)
def test_unknown_or_malformed_memory_scope_cannot_use_all_host_ram(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, path: str, value: str | None
) -> None:
    _proc(monkeypatch, **{path: value})
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes is None and result.free_memory_bytes is None
    assert result.free_disk_bytes == 10 * GIB


def test_known_limit_with_unknown_usage_does_not_invent_free_memory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _proc(
        monkeypatch,
        **{"/sys/fs/cgroup/memory.max": str(4 * GIB), "/sys/fs/cgroup/memory.current": None},
    )
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes == 4 * GIB and result.free_memory_bytes is None


def test_usage_above_current_limit_means_zero_headroom(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _proc(
        monkeypatch,
        **{"/sys/fs/cgroup/memory.max": str(GIB), "/sys/fs/cgroup/memory.current": str(2 * GIB)},
    )
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes == GIB and result.free_memory_bytes == 0


def test_unknown_platform_has_unknown_ram_and_gpu(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(device.sys, "platform", "unseen-os")
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes is None and result.free_memory_bytes is None
    assert result.gpu_vram_bytes is None and result.gpu_free_vram_bytes is None
    assert result.free_disk_bytes == 10 * GIB


@pytest.mark.parametrize("value", [True, -1, 1.5, "1024", 2**64])
def test_invalid_disk_read_is_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, value: Any
) -> None:
    _windows(monkeypatch)
    monkeypatch.setattr(device.shutil, "disk_usage", lambda _path: SimpleNamespace(free=value))
    assert device.collect_hardware_profile(tmp_path).free_disk_bytes is None


def test_disk_permission_failure_is_unknown_not_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _windows(monkeypatch)

    def denied(_path: Path) -> None:
        raise PermissionError("private volume")

    monkeypatch.setattr(device.shutil, "disk_usage", denied)
    result = device.collect_hardware_profile(tmp_path)
    assert result.free_disk_bytes is None
    assert result.host_ram_bytes == 16 * GIB


class _Stream(io.BytesIO):
    reads: list[int | None]

    def __init__(self, content: bytes) -> None:
        super().__init__(content)
        self.reads = []

    def read(self, size: int | None = -1) -> bytes:
        self.reads.append(size)
        return super().read(size)


class _Process:
    def __init__(self, content: bytes, *, code: int = 0, timeout: bool = False) -> None:
        self.stdout = _Stream(content)
        self.code, self.timeout = code, timeout
        self.killed = False
        self.finished = False
        self.wait_timeouts: list[float] = []

    def wait(self, *, timeout: float) -> int:
        self.wait_timeouts.append(timeout)
        if self.timeout:
            raise subprocess.TimeoutExpired("fixture-tool", timeout)
        self.finished = True
        return self.code

    def poll(self) -> int | None:
        return self.code if self.finished else None

    def kill(self) -> None:
        self.killed = True


def _gpu(monkeypatch: pytest.MonkeyPatch, process: _Process) -> dict[str, Any]:
    calls: dict[str, Any] = {}
    monkeypatch.setattr(device.shutil, "which", lambda _name: "fixture-nvidia-smi")

    def launch(argv: list[str], **kwargs: Any) -> _Process:
        calls.update(argv=argv, **kwargs)
        return process

    monkeypatch.setattr(device.subprocess, "Popen", launch)
    return calls


def test_nvidia_selects_largest_free_single_row_with_bounded_numeric_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _Process(b"24576, 1000\n8192, 7000\n16384, 6000\n")
    calls = _gpu(monkeypatch, process)
    assert device._nvidia_memory() == (8192 * MIB, 7000 * MIB)
    assert calls["argv"] == [
        "fixture-nvidia-smi",
        "--query-gpu=memory.total,memory.free",
        "--format=csv,noheader,nounits",
    ]
    assert calls["shell"] is False and calls["stderr"] == subprocess.DEVNULL
    assert calls["stdin"] == subprocess.DEVNULL and calls["creationflags"] == 0
    assert process.stdout.reads == [8193]
    assert process.stdout.closed
    assert all(0 < value <= 0.2 for value in process.wait_timeouts)


def test_nvidia_windows_process_is_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(device.sys, "platform", "win32")
    monkeypatch.setattr(device.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    process = _Process(b"1024, 0\n")
    calls = _gpu(monkeypatch, process)
    assert device._nvidia_memory() == (1024 * MIB, 0)
    assert calls["creationflags"] == 0x08000000


@pytest.mark.parametrize(
    "output",
    [
        b"",
        b"N/A, N/A",
        b"8192, 8000\nbroken",
        b"8192, 9000",
        b"0, 0",
        b"8192 MiB, 8000 MiB",
        b"-1, 0",
        b"1.5, 1",
        b"\xff",
        b"9" * 8192,
        b"1, 1\n\n2, 2",
        b"9999999999999999999, 0",
    ],
)
def test_malformed_gpu_output_is_unknown(monkeypatch: pytest.MonkeyPatch, output: bytes) -> None:
    _gpu(monkeypatch, _Process(output))
    assert device._nvidia_memory() == (None, None)


def test_oversized_gpu_output_is_killed_and_not_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    process = _Process(b"1024, 1000\n" * 1000)
    _gpu(monkeypatch, process)
    assert device._nvidia_memory() == (None, None)
    assert process.stdout.reads == [8193] and process.killed


def test_gpu_wait_timeout_and_nonzero_exit_are_optional_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _Process(b"8192, 7000\n", timeout=True)
    _gpu(monkeypatch, process)
    assert device._nvidia_memory() == (None, None)
    assert process.killed
    _gpu(monkeypatch, _Process(b"8192, 7000\n", code=1))
    assert device._nvidia_memory() == (None, None)


def test_gpu_reader_deadline_does_not_block_request(monkeypatch: pytest.MonkeyPatch) -> None:
    process = _Process(b"8192, 7000\n")
    _gpu(monkeypatch, process)
    waits = []

    class NeverFinishedReader:
        def __init__(self, **kwargs: Any) -> None:
            assert kwargs["daemon"] is True

        def start(self) -> None:
            pass

        def join(self, timeout: float) -> None:
            waits.append(timeout)

        def is_alive(self) -> bool:
            return True

    monkeypatch.setattr(device, "Thread", NeverFinishedReader)
    assert device._nvidia_memory() == (None, None)
    assert waits == [2.0] and process.killed
    process.stdout.close()


def test_gpu_missing_or_permission_denied_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    assert device._nvidia_memory() == (None, None)
    monkeypatch.setattr(device.shutil, "which", lambda _name: "fixture-tool")

    def denied(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("synthetic-private-executable")

    monkeypatch.setattr(device.subprocess, "Popen", denied)
    assert device._nvidia_memory() == (None, None)


def test_proc_file_read_is_bounded_and_failure_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "numeric.txt"
    path.write_text("max", encoding="utf-8")
    assert device._read_text(path) == "max"
    path.write_text("x" * 131_073, encoding="utf-8")
    assert device._read_text(path) is None
    assert device._read_text(tmp_path / "missing", missing="max") == "max"

    def denied(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("synthetic-private-path")

    monkeypatch.setattr(Path, "open", denied)
    assert device._read_text(path, missing="max") is None


def test_return_has_no_identity_paths_or_side_effects(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _proc(monkeypatch)
    sentinel = tmp_path / "owner-file.txt"
    sentinel.write_bytes(b"unchanged synthetic owner file")
    before = sentinel.read_bytes()
    result = device.collect_hardware_profile(tmp_path)
    assert all(value is None or type(value) is int for value in asdict(result).values())
    assert str(tmp_path) not in repr(result)
    assert sentinel.read_bytes() == before
    assert list(tmp_path.iterdir()) == [sentinel]


@pytest.mark.parametrize(
    "text",
    [
        "MemTotal: invalid\nMemAvailable: invalid\n",
        "MemTotal: 16777216 kB\nMemTotal: 16777216 kB\nMemAvailable: invalid\n",
        "MemTotal: " + "9" * 5000 + " kB\nMemAvailable: -1 kB\n",
    ],
)
def test_malformed_meminfo_does_not_crash_or_invent_capacity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str
) -> None:
    _proc(monkeypatch, **{"/proc/meminfo": text})
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes is None and result.free_memory_bytes is None


def test_sysconf_permission_failure_is_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _proc(monkeypatch, **{"/proc/meminfo": None})

    def denied(_name: str) -> None:
        raise OSError("unsupported or denied")

    monkeypatch.setattr(device.os, "sysconf", denied)
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes is None and result.free_memory_bytes is None


def test_actual_v2_root_absent_interface_does_not_claim_a_finite_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    files = _proc(monkeypatch)
    del files["/sys/fs/cgroup/memory.max"]
    assert device.collect_hardware_profile(tmp_path).host_ram_bytes is None
    files["/proc/self/cgroup"] = "0::/child\n"
    assert device.collect_hardware_profile(tmp_path).host_ram_bytes is None


def test_mountinfo_escaped_mount_path_is_structural(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _proc(
        monkeypatch,
        **{
            "/proc/self/mountinfo": (
                "29 23 0:26 / /sys/fs/cgroup\\040memory rw - cgroup2 cgroup rw\n"
            ),
            "/sys/fs/cgroup memory/memory.max": str(4 * GIB),
            "/sys/fs/cgroup memory/memory.current": str(GIB),
        },
    )
    result = device.collect_hardware_profile(tmp_path)
    assert result.host_ram_bytes == 4 * GIB and result.free_memory_bytes == 3 * GIB


def test_zero_disk_space_is_a_known_observation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _windows(monkeypatch)
    monkeypatch.setattr(device.shutil, "disk_usage", lambda _path: SimpleNamespace(free=0))
    assert device.collect_hardware_profile(tmp_path).free_disk_bytes == 0
