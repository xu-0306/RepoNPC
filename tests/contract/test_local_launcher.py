from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POWERSHELL_LAUNCHER = ROOT / "scripts" / "start-reponpc.ps1"
DOUBLE_CLICK_LAUNCHER = ROOT / "start-reponpc.cmd"


def test_windows_double_click_launcher_targets_reviewable_powershell_script() -> None:
    command = DOUBLE_CLICK_LAUNCHER.read_text(encoding="utf-8")

    assert "scripts\\start-reponpc.ps1" in command
    assert "powershell.exe" in command
    assert "%~dp0" in command
    assert "%*" in command


def test_local_launcher_preserves_first_owner_and_secret_boundaries() -> None:
    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")

    assert "RandomNumberGenerator" in script
    assert '"REPONPC_IP_HASH_KEY"' in script
    assert "admin setup-code --data-dir" in script
    assert "First-owner setup code (shown only here)" in script
    assert "REPONPC_ADMIN_PASSWORD_HASH" not in script
    assert "REPONPC_GITHUB_TOKEN" in script
    assert 'Direct = "REPONPC_GITHUB_OAUTH_CLIENT_SECRET"' in script
    assert 'File = "REPONPC_GITHUB_OAUTH_CLIENT_SECRET_FILE"' in script
    assert 'Direct = "REPONPC_CREDENTIAL_ENCRYPTION_KEY"' in script
    assert 'File = "REPONPC_CREDENTIAL_ENCRYPTION_KEY_FILE"' in script
    assert "Set either $directName or $fileName, not both." in script
    assert "$fileName was not found locally" in script
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
    assert '"$probeBaseUrl/api/admin/setup"' in script
    assert '"$baseUrl/admin"' in script
    assert 'Invoke-Pnpm @("run", "web:build")' in script
    assert "Start-Process -FilePath $pythonExe" in script
    assert "Repair-WindowsPathEnvironment" in script
    assert "Isolated startup smoke test passed" in script
    assert "-RedirectStandardOutput" in script
    assert "-RedirectStandardError" in script


def test_local_launcher_uses_locked_runtime_without_a_local_embedding_extra() -> None:
    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")

    assert '"REPONPC_EMBEDDING_PROVIDER"' in script
    assert 'Set-ProcessEnvironmentDefault "REPONPC_EMBEDDING_PROVIDER" "ollama"' in script
    assert 'Set-ProcessEnvironmentDefault "REPONPC_EMBEDDING_MODEL"' in script
    assert '"qwen3-embedding:0.6b"' in script
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
