from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

import pytest

from reponpc.config.private_files import (
    _evaluate_owner_only_acl,
    is_owner_only,
    restrict_owner_only,
)

USER = "S-1-5-21-100-200-300-400"
SYSTEM = "S-1-5-18"
ADMINS = "S-1-5-32-544"
CREATOR = "S-1-3-0"


def test_acl_logic_rejects_wrong_owner_and_null_dacl() -> None:
    entries = [(0, 0, USER), (0, 0, SYSTEM), (0, 0, ADMINS)]
    assert _evaluate_owner_only_acl("S-1-1-0", entries, USER) is False
    assert _evaluate_owner_only_acl(USER, entries, USER, dacl_present=False) is False


def test_acl_logic_rejects_unknown_allow_types_and_effective_creator_owner() -> None:
    assert _evaluate_owner_only_acl(USER, [(5, 0, USER)], USER) is False
    assert _evaluate_owner_only_acl(USER, [(0, 0, CREATOR)], USER) is False
    assert _evaluate_owner_only_acl(USER, [(0, 8, CREATOR)], USER) is True


def test_acl_logic_accepts_owner_rights_only_with_an_allowed_owner() -> None:
    entries = [(0, 3, SYSTEM), (0, 3, ADMINS), (0, 3, "S-1-3-4")]
    assert _evaluate_owner_only_acl(USER, entries, USER) is True
    assert _evaluate_owner_only_acl("S-1-5-32-545", entries, USER) is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DACL behavior only")
def test_windows_python_private_mkdir_is_owner_only(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    child = directory / "child"
    child.write_text("canary", encoding="utf-8")

    assert is_owner_only(directory, posix_forbidden_mode=0)
    assert is_owner_only(child, posix_forbidden_mode=0)


def test_acl_logic_ignores_deny_aces() -> None:
    assert _evaluate_owner_only_acl(USER, [(1, 0, "S-1-1-0"), (0, 0, USER)], USER) is True


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode behavior only")
def test_posix_owner_only_modes_are_preserved(tmp_path: Path) -> None:
    file_path = tmp_path / "secret"
    file_path.write_text("canary", encoding="utf-8")
    directory = tmp_path / "private"
    directory.mkdir()

    restrict_owner_only(file_path)
    restrict_owner_only(directory)

    assert stat.S_IMODE(file_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert is_owner_only(file_path, posix_forbidden_mode=stat.S_IRGRP | stat.S_IROTH)


windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows DACL behavior only")


def _grant_read(path: Path, sid: str, inheritance: str = "") -> None:
    subprocess.run(
        ["icacls", str(path), "/grant", f"*{sid}:{inheritance}(R)"],
        check=True,
        capture_output=True,
    )


@windows_only
def test_windows_restricted_file_directory_and_inheriting_child_are_owner_only(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "secret"
    file_path.write_text("canary", encoding="utf-8")
    directory = tmp_path / "private"
    directory.mkdir()

    restrict_owner_only(file_path)
    restrict_owner_only(directory)
    child = directory / "child"
    child.write_text("canary", encoding="utf-8")

    for path in (file_path, directory, child):
        assert is_owner_only(path, posix_forbidden_mode=0), path.name


@windows_only
@pytest.mark.parametrize("sid", ["S-1-5-32-545", "S-1-5-11", "S-1-1-0"])
def test_windows_rejects_an_explicit_entry_for_another_account(tmp_path: Path, sid: str) -> None:
    file_path = tmp_path / "secret"
    file_path.write_text("canary", encoding="utf-8")
    restrict_owner_only(file_path)
    assert is_owner_only(file_path, posix_forbidden_mode=0)

    _grant_read(file_path, sid)

    assert not is_owner_only(file_path, posix_forbidden_mode=0)


@windows_only
def test_windows_rejects_a_child_inheriting_a_broad_parent_entry(tmp_path: Path) -> None:
    directory = tmp_path / "shared"
    directory.mkdir()
    restrict_owner_only(directory)
    _grant_read(directory, "S-1-5-32-545", "(OI)(CI)")
    child = directory / "child"
    child.write_text("canary", encoding="utf-8")

    assert not is_owner_only(directory, posix_forbidden_mode=0)
    assert not is_owner_only(child, posix_forbidden_mode=0)
