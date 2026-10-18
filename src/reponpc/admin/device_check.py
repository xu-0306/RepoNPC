"""Bounded, read-only resource observations for the authenticated owner surface.

Only numeric capacity facts leave this module. Failure to observe a capacity is
unknown, never zero. No model, network, provider selection or persisted state is
involved, and bandwidth is deliberately not guessed.
"""

from __future__ import annotations

import ctypes
import os
import re
import shutil
import subprocess
import sys
from contextlib import suppress
from pathlib import Path, PurePosixPath
from threading import Thread

from reponpc.admin.model_guidance import HardwareProfile

_MAX_BYTES = 2**63 - 1
_PROC_READ_LIMIT = 131_072
_GPU_OUTPUT_LIMIT = 8_192
_GPU_TIMEOUT_SECONDS = 2.0
_MIB = 1024 * 1024


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_uint32),
        ("dwMemoryLoad", ctypes.c_uint32),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]


def collect_hardware_profile(data_directory: Path) -> HardwareProfile:
    """Observe effective RAM, data-volume free disk and optional single-GPU VRAM.

    Linux cgroup limits and their current usage constrain physical observations.
    An unreadable/unsupported memory scope cannot imply all host RAM is usable.
    NVIDIA is optional; other GPUs and memory bandwidth remain unknown.
    """
    total: int | None = None
    available: int | None = None
    gpu_total: int | None = None
    gpu_free: int | None = None
    if sys.platform == "win32":
        total, available = _windows_memory()
        gpu_total, gpu_free = _nvidia_memory()
    elif sys.platform.startswith("linux"):
        total, available = _linux_memory()
        gpu_total, gpu_free = _nvidia_memory()
    try:
        free_disk = _capacity(shutil.disk_usage(data_directory).free)
    except OSError, ValueError:
        free_disk = None
    return HardwareProfile(
        host_ram_bytes=total,
        free_memory_bytes=available,
        free_disk_bytes=free_disk,
        gpu_vram_bytes=gpu_total,
        gpu_free_vram_bytes=gpu_free,
    )


def _windows_memory() -> tuple[int | None, int | None]:
    try:
        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        function = ctypes.WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx
        function.argtypes = [ctypes.POINTER(_MemoryStatus)]
        function.restype = ctypes.c_int
        if not function(ctypes.byref(status)):
            return None, None
    except AttributeError, OSError, ValueError:
        return None, None
    return _coherent_memory(
        _capacity(status.ullTotalPhys, positive=True), _capacity(status.ullAvailPhys)
    )


def _read_text(path: Path, *, missing: str | None = None) -> str | None:
    try:
        with path.open("r", encoding="utf-8") as source:
            text = source.read(_PROC_READ_LIMIT + 1)
    except FileNotFoundError:
        return missing
    except OSError, UnicodeError:
        return None
    return text if len(text) <= _PROC_READ_LIMIT else None


def _linux_memory() -> tuple[int | None, int | None]:
    text = _read_text(Path("/proc/meminfo"))
    values: dict[str, int | None] = {}
    if text is not None:
        for line in text.splitlines():
            name, separator, value = line.partition(":")
            if separator and name in {"MemTotal", "MemAvailable"}:
                match = re.fullmatch(r"\s*([0-9]{1,19})\s+kB\s*", value)
                parsed = _capacity(int(match[1]) * 1024) if match else None
                values[name] = parsed if name not in values else None
    total = values.get("MemTotal") or _sysconf_memory("SC_PHYS_PAGES")
    available = values.get("MemAvailable")
    if available is None:
        available = _sysconf_memory("SC_AVPHYS_PAGES")
    total, available = _coherent_memory(total, available)
    return _effective_linux_memory(total, available)


def _sysconf_memory(page_count_name: str) -> int | None:
    sysconf = getattr(os, "sysconf", None)
    if not callable(sysconf):
        return None
    try:
        pages = sysconf(page_count_name)
        page_size = sysconf("SC_PAGE_SIZE")
    except AttributeError, OSError, ValueError:
        return None
    if type(pages) is not int or pages < 0 or type(page_size) is not int or page_size <= 0:
        return None
    return _capacity(pages * page_size, positive=page_count_name == "SC_PHYS_PAGES")


def _effective_linux_memory(
    total: int | None, available: int | None
) -> tuple[int | None, int | None]:
    membership = _read_text(Path("/proc/self/cgroup"))
    mounts = _read_text(Path("/proc/self/mountinfo"))
    if membership is None or mounts is None:
        return None, None
    scopes: list[tuple[str, PurePosixPath]] = []
    for line in membership.splitlines():
        fields = line.split(":", 2)
        if len(fields) != 3 or not re.fullmatch(r"[0-9]+", fields[0]):
            return None, None
        if fields[0] == "0" and not fields[1]:
            version = "cgroup2"
        elif "memory" in fields[1].split(","):
            version = "cgroup"
        else:
            continue
        path = _absolute_linux_path(fields[2])
        if path is None:
            return None, None
        scopes.append((version, path))
    if not membership.strip():
        return None, None
    if not scopes:
        # A readable v1 membership without a memory controller has no such cap.
        return total, available
    if len(scopes) != 1:
        return None, None
    version, member = scopes[0]
    candidates: list[tuple[PurePosixPath, PurePosixPath]] = []
    for line in mounts.splitlines():
        before, separator, after = line.partition(" - ")
        fields, filesystem = before.split(), after.split()
        if not separator or len(fields) < 6 or len(filesystem) < 3:
            continue
        if filesystem[0] != version:
            continue
        if version == "cgroup" and "memory" not in filesystem[2].split(","):
            continue
        root = _absolute_linux_path(_unescape_mount_path(fields[3]))
        mount = _absolute_linux_path(_unescape_mount_path(fields[4]))
        if root is not None and mount is not None and member.is_relative_to(root):
            candidates.append((root, mount))
    if not candidates:
        return None, None
    root, mount = max(candidates, key=lambda pair: len(pair[0].parts))
    current = mount / member.relative_to(root)
    for scope in (current, *current.parents):
        if not scope.is_relative_to(mount):
            break
        limit_name, usage_name = (
            ("memory.max", "memory.current")
            if version == "cgroup2"
            else ("memory.limit_in_bytes", "memory.usage_in_bytes")
        )
        # An absent interface cannot prove that outer namespace limits are
        # absent. Keep the effective capacity unknown in that case.
        limit_text = _read_text(Path(scope / limit_name))
        if limit_text is None:
            return None, None
        if version == "cgroup2" and limit_text.strip() == "max":
            continue
        limit = _decimal_capacity(limit_text)
        if limit is None:
            return None, None
        total = limit if total is None else min(total, limit)
        usage_text = _read_text(Path(scope / usage_name))
        usage = _decimal_capacity(usage_text)
        if usage is None:
            available = None
        elif available is not None:
            available = min(available, max(0, limit - usage))
    return _coherent_memory(total, available)


def _absolute_linux_path(value: str) -> PurePosixPath | None:
    path = PurePosixPath(value)
    if not path.is_absolute() or ".." in path.parts or "\x00" in value:
        return None
    return path


def _unescape_mount_path(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), value)


def _nvidia_memory() -> tuple[int | None, int | None]:
    try:
        executable = shutil.which("nvidia-smi")
    except OSError, ValueError:
        return None, None
    if executable is None:
        return None, None
    try:
        process = subprocess.Popen(
            [executable, "--query-gpu=memory.total,memory.free", "--format=csv,noheader,nounits"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except OSError:
        return None, None
    output: list[bytes] = []
    stream = process.stdout
    if stream is None:
        with suppress(OSError, subprocess.TimeoutExpired):
            process.kill()
            process.wait(timeout=0.2)
        return None, None

    def read_bounded_output() -> None:
        with suppress(OSError):
            output.append(stream.read(_GPU_OUTPUT_LIMIT + 1))

    reader = Thread(target=read_bounded_output, daemon=True)
    try:
        reader.start()
        reader.join(_GPU_TIMEOUT_SECONDS)
        if reader.is_alive() or not output or len(output[0]) > _GPU_OUTPUT_LIMIT:
            return None, None
        if process.wait(timeout=0.2) != 0:
            return None, None
        return _parse_nvidia_memory(output[0])
    except OSError, RuntimeError, subprocess.TimeoutExpired:
        return None, None
    finally:
        try:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=0.2)
        except OSError, subprocess.TimeoutExpired:
            pass
        if not reader.is_alive():
            with suppress(OSError):
                stream.close()


def _parse_nvidia_memory(output: bytes) -> tuple[int | None, int | None]:
    try:
        text = output.decode("ascii").strip()
    except UnicodeError:
        return None, None
    rows: list[tuple[int, int]] = []
    for line in text.splitlines():
        match = re.fullmatch(r"\s*([0-9]{1,19})\s*,\s*([0-9]{1,19})\s*", line)
        if match is None:
            return None, None
        total = _capacity(int(match[1]) * _MIB, positive=True)
        free = _capacity(int(match[2]) * _MIB)
        if total is None or free is None or free > total:
            return None, None
        rows.append((total, free))
    return max(rows, key=lambda row: row[1]) if rows else (None, None)


def _decimal_capacity(value: str | None) -> int | None:
    if value is None or not re.fullmatch(r"[0-9]{1,19}", value.strip()):
        return None
    return _capacity(int(value.strip()))


def _capacity(value: object, *, positive: bool = False) -> int | None:
    if type(value) is not int or not (1 if positive else 0) <= value <= _MAX_BYTES:
        return None
    return value


def _coherent_memory(total: int | None, available: int | None) -> tuple[int | None, int | None]:
    if total is not None and available is not None and available > total:
        available = None
    return total, available
