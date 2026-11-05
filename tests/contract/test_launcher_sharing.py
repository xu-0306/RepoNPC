"""Source-launcher permissions and console copy use the same Windows policy."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

from reponpc.config.private_files import is_owner_only

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows launcher DACL boundary")
@pytest.mark.parametrize("profile", ["loopback_evaluation", "production"])
@pytest.mark.parametrize("custom", [False, True])
def test_source_preparation_runs_shared_permissions_policy(tmp_path, profile, custom):
    script = (ROOT / "scripts" / "start-reponpc.ps1").read_text(encoding="utf-8")
    start = script.index('    $prepareDataDirectory = @"\n') + len(
        '    $prepareDataDirectory = @"\n'
    )
    end = script.index('\n"@', start)
    default = tmp_path / "repo" / "runtime-data" / "local"
    data = tmp_path / "custom data" if custom else default
    data.mkdir(parents=True)
    canary = data / "saved.txt"
    canary.write_text("saved data", encoding="utf-8")
    for path in (data, canary):
        subprocess.run(
            ["icacls", str(path), "/grant", "*S-1-5-32-545:(R)"],
            check=True,
            capture_output=True,
        )
    result = subprocess.run(
        [sys.executable, "-B", "-c", script[start:end], str(data), profile, str(default)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert canary.read_text(encoding="utf-8") == "saved data"
    if custom:
        assert result.returncode == 3
        assert not is_owner_only(data, posix_forbidden_mode=0)
        assert not (data / "private").exists()
        assert len(result.stdout.splitlines()) == 2
        assert result.stdout.splitlines()[1].startswith(f'icacls "{data}" /inheritance:r ')
    else:
        assert result.returncode == 0, result.stderr
        key = Path(result.stdout.strip())
        assert key == data / "private" / "ip-hash-key"
        for path in (data, canary, key):
            assert is_owner_only(path, posix_forbidden_mode=0)


def test_launcher_console_instructions_have_no_mode_choice():
    forbidden = re.compile(r"trial|evaluation|production|\u8a66\u7528|\u6b63\u5f0f", re.I)
    script = (ROOT / "scripts" / "start-reponpc.ps1").read_text(encoding="utf-8")
    for line in script.splitlines():
        if re.match(r"\s*(?:throw|Write-(?:Host|Step|Warning))\b", line):
            assert not forbidden.search(line), line
    tree = ast.parse((ROOT / "src" / "reponpc" / "windows_launcher.py").read_text(encoding="utf-8"))
    messages = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"print", "write", "input"}
        ):
            messages.extend(
                constant.value
                for argument in node.args
                for constant in ast.walk(argument)
                if isinstance(constant, ast.Constant) and isinstance(constant.value, str)
            )
    assert messages
    assert not any(forbidden.search(message) for message in messages)
