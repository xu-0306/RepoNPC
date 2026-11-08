import re
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
    assert "REPONPC_CHAT_API_KEY" in script
    assert "REPONPC_GITHUB_OAUTH_CLIENT_SECRET" not in script
    assert "REPONPC_CREDENTIAL_ENCRYPTION_KEY" not in script
    assert "REPONPC_GITHUB_OAUTH_CLIENT_SECRET_FILE" not in script
    assert "REPONPC_CREDENTIAL_ENCRYPTION_KEY_FILE" not in script
    assert "optional capability remains disabled" in script
    assert "format_environment_error" in script
    assert "except EnvironmentValidationError as exc:" in script
    assert "print(format_environment_error(exc), file=sys.stderr)" in script
    assert "sys.exit(check_environment())" in script
    assert "$environmentOutput = @(& $pythonExe -c $environmentCheck 2>&1)" in script
    assert 'throw (($environmentOutput -join "`n") + ". Review .env and try again.")' in script


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


def test_local_launcher_sets_host_allowlist_before_server_and_smoke_probe() -> None:
    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")
    allowlist = 'Set-ProcessEnvironmentValue "REPONPC_TRUSTED_HOSTS" "localhost,127.0.0.1"'
    assert script.count(allowlist) == 1
    assert script.index(allowlist) < script.index(
        '    if ($deploymentProfile -eq "loopback_evaluation") {'
    )
    assert script.index(allowlist) < script.index("$server = Start-Process -FilePath $pythonExe")
    assert '$probeBaseUrl = "http://127.0.0.1:$Port"' in script
    assert "Wait-RepoNpcHealth $probeBaseUrl $server" in script
    assert 'Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/healthz"' in script


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


def test_local_launcher_stops_its_server_with_the_window() -> None:
    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")

    # A person at a window gets a server tied to the launcher process by a kill-on-close job
    # object, so closing the window (or Enter at the prompt) stops RepoNPC and a restart really
    # restarts it. Scripted runs (-NoPause, -SmokeTest) keep the detached server.
    assert "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" in script
    assert "Get-ProcessTreeIds $ServerId" in script
    assert "if (-not $NoPause -and -not $SmokeTest) {" in script
    assert "Join-ServerToLauncher $server.Id" in script
    assert "if ($processId -eq $ServerId) {" in script
    assert "RepoNPC stops when this window closes" in script
    assert "Press Enter to stop RepoNPC and close this launcher" in script
    assert "RepoNPC keeps running in the background after this window closes." in script


def test_local_launcher_selects_only_explicit_supported_profiles() -> None:
    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")
    profile_read = script.index(
        '$deploymentProfile = Get-ProcessEnvironmentValue "REPONPC_DEPLOYMENT_PROFILE"'
    )
    assert script.index('Import-RepoNpcDotEnv (Join-Path $repoRoot ".env")') < profile_read
    assert "if ([string]::IsNullOrEmpty($deploymentProfile)) {" in script
    assert '$deploymentProfile = "loopback_evaluation"' in script
    assert '$deploymentProfile -cnotin @("loopback_evaluation", "production")' in script
    assert 'throw "REPONPC_DEPLOYMENT_PROFILE is not supported."' in script
    assert 'Set-ProcessEnvironmentValue "REPONPC_DEPLOYMENT_PROFILE" $deploymentProfile' in script
    assert (
        'Set-ProcessEnvironmentValue "REPONPC_DEPLOYMENT_PROFILE" "loopback_evaluation"'
        not in script
    )


def test_local_launcher_separates_trial_and_production_preparation() -> None:
    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")
    start = script.index('    if ($deploymentProfile -eq "loopback_evaluation") {')
    end = script.index("    $pythonExe = Join-Path", start)
    trial, production = script[start:end].split("    else {", 1)
    for statement in (
        "[IO.Directory]::CreateDirectory($resolvedDataDir)",
        'Set-ProcessEnvironmentValue "REPONPC_ENV" "development"',
        "Import-LocalSecretFiles",
        "Ensure-LocalIpHashKey",
    ):
        assert statement in trial and statement not in production
    assert 'Set-ProcessEnvironmentValue "REPONPC_ENV" "production"' in production
    origins = 'Set-ProcessEnvironmentValue "REPONPC_ADMIN_ORIGINS" $baseUrl'
    assert script.count(origins) == 1
    assert script.index(origins) < start
    for name in ("REPONPC_CHAT_API_KEY", "REPONPC_EMBEDDING_API_KEY", "REPONPC_IP_HASH_KEY"):
        assert f'"{name}"' in production
    assert "$configuredDirectSecrets = @($directSecretNames | Where-Object {" in production
    assert "IsNullOrEmpty((Get-ProcessEnvironmentValue $_))" in production
    assert '$configuredDirectSecrets -join ", "' in production
    assert "file under $resolvedDataDir\\private and use the _FILE variable." in production
    assert '$fileName = $name + "_FILE"' in production
    assert "Join-Path $repoRoot $fileValue" in production
    assert (
        "Set-ProcessEnvironmentValue $fileName ([IO.Path]::GetFullPath($fileValue))" in production
    )


def test_local_launcher_production_uses_shared_helpers_after_python_sync() -> None:
    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")
    preparation_start = script.index('    $prepareDataDirectory = @"')
    preparation_end = script.index("    if (-not $SkipBuild", preparation_start)
    preparation = script[preparation_start:preparation_end]
    assert script.index("& $uv @syncArguments") < preparation_start
    assert "Path(sys.argv[1])," in preparation
    assert "production=sys.argv[2] == 'production'" in preparation
    assert "default_directory=Path(sys.argv[3])" in preparation
    assert "except UnsafeDataDirectory as exc:" in preparation
    assert "print(owner_only_fix_command(exc.path, root=exc.root))" in preparation
    assert "sys.exit(3)" in preparation
    # A refused link or multi-name entry is reported and stops with exit 3, never a traceback.
    assert "except UnsafeDataEntry as exc:" in preparation
    assert "print(*unsafe_entry_lines(exc.path), sep='\\n')" in preparation
    assert preparation.count("sys.exit(3)") == 2
    assert "$preparationExitCode -eq 3" in preparation
    assert (
        "$pythonExe -c $prepareDataDirectory $resolvedDataDir $deploymentProfile $defaultDataDir"
        in preparation
    )
    assert (
        '$defaultDataDir = [IO.Path]::GetFullPath((Join-Path $repoRoot "runtime-data\\local"))'
        in script
    )
    assert (
        'Set-ProcessEnvironmentValue "REPONPC_IP_HASH_KEY_FILE" ([string]$preparationOutput[0])'
        in preparation
    )
    assert 'IsNullOrEmpty((Get-ProcessEnvironmentValue "REPONPC_IP_HASH_KEY_FILE"))' in preparation
    console_start = script.index(
        '    if ($deploymentProfile -eq "production" -and -not $SmokeTest) {'
    )
    console_end = script.index("    $startedHere", console_start)
    console = script[console_start:console_end]
    assert script.index("if ($environmentExitCode -ne 0)") < console_start
    assert "run_owner_console(Path(sys.argv[1]), environ=os.environ)" in console
    assert "& $pythonExe -c $ownerConsole $resolvedDataDir\n" in console
    assert "2>&1" not in console and "RedirectStandard" not in console
    assert "Owner setup was not completed." in console


def test_local_launcher_python_here_strings_have_no_double_quotes() -> None:
    # Windows PowerShell 5.1 drops double quotes when it passes a string to a
    # native program, so Python code sent with -c must use single quotes. A real
    # launcher run found `== "production"` reaching Python as a bare name.
    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")
    blocks = re.findall(r'@"\r?\n(.*?)\r?\n"@', script, flags=re.DOTALL)
    assert len(blocks) >= 3
    for block in blocks:
        assert '"' not in block, block


def test_local_launcher_only_trial_issues_fragment_grants() -> None:
    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")
    start = script.index(
        '    if ($deploymentProfile -eq "loopback_evaluation") {\n        $launchOutput'
    )
    end = script.index("    if ($SmokeTest)", start)
    trial, production = script[start:end].split("    else {", 1)
    assert "admin launch-token --data-dir" in trial
    assert "#local-launch=" in trial
    assert "admin launch-token" not in script[:start] + production + script[end:]
    assert "#local-launch=" not in script[:start] + production + script[end:]
    assert '$adminUrl = "$baseUrl/admin"' in production
    assert "Start-Process -FilePath $adminUrl" in script[end:]
    assert "Write-Host $adminUrl" in script[end:]


@pytest.mark.parametrize(
    "argument, configured, relative",
    [
        ("", "", "runtime-data/local"),
        ("", "/var/lib/reponpc", "runtime-data/local"),
        ("", "custom one", "custom one"),
        ("custom two", "ignored folder", "custom two"),
        ("runtime-data/local", "ignored folder", "runtime-data/local"),
    ],
)
def test_source_default_folder_decision_uses_the_resolved_path(
    tmp_path: Path, argument: str, configured: str, relative: str
) -> None:
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if shell is None:
        pytest.skip("PowerShell is unavailable on this host")
    script = POWERSHELL_LAUNCHER.read_text(encoding="utf-8")
    start = script.index("    if ([string]::IsNullOrWhiteSpace($DataDir)) {")
    end = script.index('    $baseUrl = "http://localhost:$Port"', start)

    def quoted(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    command = (
        "Set-StrictMode -Version Latest; $ErrorActionPreference = 'Stop';\n"
        f"$repoRoot = {quoted(str(tmp_path))}; $DataDir = {quoted(argument)};\n"
        f"function Get-ProcessEnvironmentValue {{ return {quoted(configured)} }}\n"
        + script[start:end]
        + "\nWrite-Output $resolvedDataDir; Write-Output $defaultDataDir"
    )
    result = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert list(map(Path, result.stdout.splitlines())) == [
        tmp_path / relative,
        tmp_path / "runtime-data" / "local",
    ]


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
