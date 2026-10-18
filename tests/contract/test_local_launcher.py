import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POWERSHELL_LAUNCHER = ROOT / "scripts" / "start-reponpc.ps1"
DOUBLE_CLICK_LAUNCHER = ROOT / "start-reponpc.cmd"


def test_windows_double_click_launcher_targets_reviewable_powershell_script() -> None:
    command = DOUBLE_CLICK_LAUNCHER.read_text(encoding="utf-8")

    assert "scripts\\start-reponpc.ps1" in command
    assert "powershell.exe" in command
    assert "%~dp0" in command
    assert "%*" in command


def test_local_launcher_preserves_launch_and_secret_boundaries() -> None:
    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")

    assert "RandomNumberGenerator" in script
    assert '"REPONPC_IP_HASH_KEY"' in script
    assert "admin launch-token --data-dir" in script
    assert "admin setup-code --data-dir" not in script
    assert "First-owner setup code (shown only here)" not in script
    assert '"$baseUrl/admin#local-launch="' in script
    assert "Issuing a fresh 15-minute first-owner setup code." not in script
    assert "REPONPC_ADMIN_PASSWORD_HASH" not in script
    assert "REPONPC_GITHUB_TOKEN" in script
    assert "REPONPC_GITHUB_OAUTH_CLIENT_SECRET" not in script
    assert "REPONPC_CREDENTIAL_ENCRYPTION_KEY" not in script
    assert "REPONPC_GITHUB_OAUTH_CLIENT_SECRET_FILE" not in script
    assert "REPONPC_CREDENTIAL_ENCRYPTION_KEY_FILE" not in script
    assert "optional capability remains disabled" in script


def test_local_launcher_builds_same_origin_app_and_checks_real_health_route() -> None:
    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")

    assert "$parsedPort = 8090" in script
    assert "$parsedPort = 8000" not in script
    assert '"http://localhost:$Port"' in script
    assert '"http://127.0.0.1:$Port"' in script
    assert '"127.0.0.1"' in script
    assert '"$BaseUrl/healthz"' in script
    assert '$payload.status -eq "alive"' in script
    assert '"$probeBaseUrl/api/admin/setup"' not in script
    assert 'Invoke-Pnpm @("run", "web:build")' in script
    assert "Start-Process -FilePath $pythonExe" in script
    assert "Repair-WindowsPathEnvironment" in script
    assert "Isolated startup smoke test passed" in script
    assert "-RedirectStandardOutput" in script
    assert "-RedirectStandardError" in script


def test_local_launcher_keeps_model_setup_provider_neutral() -> None:
    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")

    assert 'Set-ProcessEnvironmentDefault "REPONPC_EMBEDDING_PROVIDER"' not in script
    assert 'Set-ProcessEnvironmentDefault "REPONPC_EMBEDDING_MODEL"' not in script
    assert 'Set-ProcessEnvironmentDefault "REPONPC_CHAT_PROVIDER"' not in script
    assert 'Set-ProcessEnvironmentDefault "REPONPC_CHAT_MODEL"' not in script
    assert '"local_sentence_transformers"' not in script
    assert "Test-PythonModuleAvailable" not in script
    assert "sentence_transformers" not in script
    assert 'Join-Path $repoRoot ".uv-cache"' in script
    assert '@("--cache-dir", $uvCacheDirectory, "sync", "--frozen")' in script
    assert '"--extra"' not in script


def test_local_launcher_reconciles_only_owned_stale_processes() -> None:
    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")

    assert "Read-LauncherState" in script
    assert "Get-LauncherInputWriteTimeUtc" in script
    assert "Test-LauncherStateStale" in script
    assert "Stop-LauncherOwnedInstance" in script
    assert "taskkill.exe /PID $processId /T /F" in script
    assert "Stop-Process -Id $processId -Force" in script
    assert "$null -eq $process.Path" in script
    assert "not managed by this RepoNPC launcher" in script
    assert "[string]$State.started_at" in script


@pytest.mark.parametrize(
    ("config", "missing_executable", "needs_sync"),
    [
        ("version_info = 3.13.15\n", None, True),
        ("version = 3.13.15\n", None, True),
        ("version_info = 3.14.0\n", None, False),
        ("version = 3.14.7\n", None, False),
        ("home = C:\\Python315\nversion_info = 3.15.1\n", None, False),
        ("version_info = 3.9.20\n", None, True),
        ("version_info = invalid\n", None, True),
        ("version = 3.14.invalid\n", None, True),
        ("version_info = 3.14.7invalid\n", None, True),
        ("version_info = 999999999999.14.7\n", None, True),
        (" version_info = 3.14.7\r\n", None, False),
        ("", None, True),
        ("home = C:\\Python314\n", None, True),
        (None, None, True),
        ("version_info = 3.14.7\n", "python.exe", True),
        ("version_info = 3.14.7\n", "reponpc.exe", True),
    ],
)
def test_local_launcher_syncs_missing_or_incompatible_python_environment(
    tmp_path: Path, config: str | None, missing_executable: str | None, needs_sync: bool
) -> None:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        pytest.skip("PowerShell is unavailable on this host")
    scripts = tmp_path / ".venv" / "Scripts"
    scripts.mkdir(parents=True)
    for executable in ("python.exe", "reponpc.exe"):
        if executable != missing_executable:
            (scripts / executable).touch()
    if config is not None:
        (tmp_path / ".venv" / "pyvenv.cfg").write_text(config, encoding="utf-8")

    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")
    start = script.index('    $pythonExe = Join-Path $repoRoot ".venv\\Scripts\\python.exe"')
    end = script.index("    if ($pythonEnvironmentNeedsSync) {", start)
    decision = script[start:end]
    command = (
        "Set-StrictMode -Version Latest; $ErrorActionPreference = 'Stop'; "
        f"$repoRoot = '{str(tmp_path).replace(chr(39), chr(39) * 2)}';\n"
        + decision
        + "\nWrite-Output $pythonEnvironmentNeedsSync"
    )
    result = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == str(needs_sync)
