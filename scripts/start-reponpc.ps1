[CmdletBinding()]
param(
    [ValidateRange(0, 65535)]
    [int]$Port = 0,
    [string]$DataDir = "",
    [string]$ChatModel = "",
    [switch]$SkipBuild,
    [switch]$NoBrowser,
    [switch]$NoPause,
    [switch]$SmokeTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDirectory

function Write-Step {
    param([string]$Message)

    Write-Host "[RepoNPC] $Message" -ForegroundColor Cyan
}

function Get-ProcessEnvironmentValue {
    param([string]$Name)

    return [Environment]::GetEnvironmentVariable($Name, "Process")
}

function Set-ProcessEnvironmentValue {
    param(
        [string]$Name,
        [AllowNull()]
        [string]$Value
    )

    [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
}

function Set-ProcessEnvironmentDefault {
    param(
        [string]$Name,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace((Get-ProcessEnvironmentValue $Name))) {
        Set-ProcessEnvironmentValue $Name $Value
    }
}

function Import-RepoNpcDotEnv {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }

    Write-Step "Loading local overrides from .env."
    foreach ($line in [IO.File]::ReadAllLines($Path)) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }
        if ($trimmed -notmatch '^([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
            throw "Invalid .env line. Expected NAME=VALUE."
        }

        $name = $Matches[1]
        $value = $Matches[2].Trim()
        if (-not $name.StartsWith("REPONPC_", [StringComparison]::Ordinal)) {
            continue
        }
        if ($value.Length -ge 2) {
            $first = $value[0]
            $last = $value[$value.Length - 1]
            if (($first -eq '"' -and $last -eq '"') -or ($first -eq "'" -and $last -eq "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        if ([string]::IsNullOrWhiteSpace((Get-ProcessEnvironmentValue $name))) {
            Set-ProcessEnvironmentValue $name $value
        }
    }
}

function Resolve-LocalSecretPath {
    param([string]$ConfiguredPath)

    $normalized = $ConfiguredPath.Replace("\", "/")
    if ($normalized.StartsWith("/run/secrets/", [StringComparison]::Ordinal)) {
        return Join-Path (Join-Path $repoRoot "secrets") ([IO.Path]::GetFileName($normalized))
    }
    if ([IO.Path]::IsPathRooted($ConfiguredPath)) {
        return $ConfiguredPath
    }
    return Join-Path $repoRoot $ConfiguredPath
}

function Import-LocalSecretFiles {
    $pairs = @(
        @{ Direct = "REPONPC_CHAT_API_KEY"; File = "REPONPC_CHAT_API_KEY_FILE"; Required = $false },
        @{ Direct = "REPONPC_EMBEDDING_API_KEY"; File = "REPONPC_EMBEDDING_API_KEY_FILE"; Required = $false },
        @{ Direct = "REPONPC_IP_HASH_KEY"; File = "REPONPC_IP_HASH_KEY_FILE"; Required = $true }
    )

    foreach ($pair in $pairs) {
        $directName = [string]$pair.Direct
        $fileName = [string]$pair.File
        $directValue = Get-ProcessEnvironmentValue $directName
        $fileValue = Get-ProcessEnvironmentValue $fileName
        if (-not [string]::IsNullOrWhiteSpace($directValue) -and -not [string]::IsNullOrWhiteSpace($fileValue)) {
            throw "Set either $directName or $fileName, not both."
        }

        if (-not [string]::IsNullOrWhiteSpace($fileValue)) {
            $localPath = Resolve-LocalSecretPath $fileValue
            if (Test-Path -LiteralPath $localPath -PathType Leaf) {
                $secret = [IO.File]::ReadAllText($localPath).Trim()
                if ([string]::IsNullOrWhiteSpace($secret)) {
                    throw "$fileName points to an empty local secret file."
                }
                Set-ProcessEnvironmentValue $directName $secret
            }
            elseif (-not [bool]$pair.Required) {
                Write-Warning "$fileName was not found locally; its optional capability remains disabled."
            }
            Set-ProcessEnvironmentValue $fileName $null
        }
    }
}

function Ensure-LocalIpHashKey {
    if (-not [string]::IsNullOrWhiteSpace((Get-ProcessEnvironmentValue "REPONPC_IP_HASH_KEY"))) {
        return
    }

    $secretDirectory = Join-Path $repoRoot "secrets"
    $secretPath = Join-Path $secretDirectory "local-ip-hash-key"
    [IO.Directory]::CreateDirectory($secretDirectory) | Out-Null
    if (Test-Path -LiteralPath $secretPath -PathType Leaf) {
        $key = [IO.File]::ReadAllText($secretPath).Trim()
        if ([string]::IsNullOrWhiteSpace($key)) {
            throw "The local IP-HMAC secret file is empty."
        }
    }
    else {
        $bytes = New-Object byte[] 48
        $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $generator.GetBytes($bytes)
        }
        finally {
            $generator.Dispose()
        }
        $key = [Convert]::ToBase64String($bytes)
        [IO.File]::WriteAllText($secretPath, $key, (New-Object Text.UTF8Encoding($false)))
        Write-Step "Created an ignored local IP-HMAC key in secrets/."
    }
    Set-ProcessEnvironmentValue "REPONPC_IP_HASH_KEY" $key
    Set-ProcessEnvironmentValue "REPONPC_IP_HASH_KEY_FILE" $null
}

function Resolve-ExternalCommand {
    param([string[]]$Names)

    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -ne $command) {
            return $command.Source
        }
    }
    return $null
}

function Repair-WindowsPathEnvironment {
    if ($env:OS -ne "Windows_NT") {
        return
    }

    $pathValue = [Environment]::GetEnvironmentVariable("Path", "Process")
    [Environment]::SetEnvironmentVariable("PATH", $null, "Process")
    [Environment]::SetEnvironmentVariable("Path", $pathValue, "Process")
}

function Invoke-Pnpm {
    param([string[]]$Arguments)

    $pnpm = Resolve-ExternalCommand @("pnpm.cmd", "pnpm")
    if ($null -ne $pnpm) {
        & $pnpm @Arguments
    }
    else {
        $corepack = Resolve-ExternalCommand @("corepack.cmd", "corepack")
        if ($null -eq $corepack) {
            throw "pnpm 11 is required. Install Node.js/Corepack, then run this launcher again."
        }
        & $corepack pnpm @Arguments
    }
    if ($LASTEXITCODE -ne 0) {
        throw "pnpm failed with exit code $LASTEXITCODE."
    }
}

function Test-WebBuildRequired {
    $builtIndex = Join-Path $repoRoot "apps\web\dist\index.html"
    if (-not (Test-Path -LiteralPath $builtIndex -PathType Leaf)) {
        return $true
    }

    $builtAt = (Get-Item -LiteralPath $builtIndex).LastWriteTimeUtc
    $inputs = @(
        (Join-Path $repoRoot "apps\web\src"),
        (Join-Path $repoRoot "apps\web\package.json"),
        (Join-Path $repoRoot "apps\web\vite.config.ts"),
        (Join-Path $repoRoot "pnpm-lock.yaml")
    )
    foreach ($input in $inputs) {
        if (Test-Path -LiteralPath $input -PathType Container) {
            $newer = Get-ChildItem -LiteralPath $input -Recurse -File |
                Where-Object { $_.LastWriteTimeUtc -gt $builtAt } |
                Select-Object -First 1
            if ($null -ne $newer) {
                return $true
            }
        }
        elseif ((Test-Path -LiteralPath $input -PathType Leaf) -and
            (Get-Item -LiteralPath $input).LastWriteTimeUtc -gt $builtAt) {
            return $true
        }
    }
    return $false
}

function Test-RepoNpcHealth {
    param([string]$BaseUrl)

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "$BaseUrl/healthz" -TimeoutSec 2
        if ($response.StatusCode -ne 200) {
            return $false
        }
        $payload = $response.Content | ConvertFrom-Json
        return $payload.status -eq "alive"
    }
    catch {
        Write-Verbose "Health probe failed: $($_.Exception.Message)"
        return $false
    }
}

function Test-TcpPortOpen {
    param([int]$TargetPort)

    $client = New-Object Net.Sockets.TcpClient
    try {
        $task = $client.ConnectAsync("127.0.0.1", $TargetPort)
        if (-not $task.Wait(500)) {
            return $false
        }
        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Wait-RepoNpcHealth {
    param(
        [string]$BaseUrl,
        [Diagnostics.Process]$Process
    )

    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        if ($Process.HasExited) {
            return $false
        }
        if (Test-RepoNpcHealth $BaseUrl) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Test-LauncherOwnsRunningInstance {
    param(
        [string]$StatePath,
        [string]$BaseUrl,
        [string]$ResolvedDataDir
    )

    $state = Read-LauncherState $StatePath
    return $null -ne $state -and
        $state.base_url -eq $BaseUrl -and
        $state.data_dir -eq $ResolvedDataDir -and
        [int]$state.pid -gt 0
}

function Read-LauncherState {
    param([string]$StatePath)

    if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
        return $null
    }
    try {
        return Get-Content -Raw -LiteralPath $StatePath | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Get-LauncherInputWriteTimeUtc {
    $latest = [DateTime]::MinValue.ToUniversalTime()
    $inputs = @(
        (Join-Path $repoRoot "src\reponpc"),
        (Join-Path $repoRoot "apps\web\src"),
        (Join-Path $repoRoot "scripts\start-reponpc.ps1"),
        (Join-Path $repoRoot "apps\web\package.json"),
        (Join-Path $repoRoot "pnpm-lock.yaml"),
        (Join-Path $repoRoot "pyproject.toml"),
        (Join-Path $repoRoot "uv.lock"),
        (Join-Path $repoRoot ".env")
    )
    foreach ($input in $inputs) {
        if (Test-Path -LiteralPath $input -PathType Container) {
            foreach ($file in @(Get-ChildItem -LiteralPath $input -Recurse -File)) {
                if ($file.LastWriteTimeUtc -gt $latest) {
                    $latest = $file.LastWriteTimeUtc
                }
            }
        }
        elseif (Test-Path -LiteralPath $input -PathType Leaf) {
            $file = Get-Item -LiteralPath $input
            if ($file.LastWriteTimeUtc -gt $latest) {
                $latest = $file.LastWriteTimeUtc
            }
        }
    }
    return $latest
}

function Test-LauncherStateStale {
    param([psobject]$State)

    if ($null -eq $State -or [string]::IsNullOrWhiteSpace([string]$State.started_at)) {
        return $true
    }
    try {
        $startedAt = [DateTimeOffset]::Parse([string]$State.started_at).UtcDateTime
        return (Get-LauncherInputWriteTimeUtc) -gt $startedAt
    }
    catch {
        return $true
    }
}

function Stop-LauncherOwnedInstance {
    param(
        [psobject]$State,
        [string]$PythonPath,
        [string]$BaseUrl
    )

    $processId = 0
    if (-not [int]::TryParse([string]$State.pid, [ref]$processId) -or $processId -le 0) {
        throw "Launcher state does not contain a valid server PID."
    }
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return
    }
    if ($null -eq $process.Path -or
        [IO.Path]::GetFullPath($process.Path) -ne [IO.Path]::GetFullPath($PythonPath)) {
        throw "Launcher state PID does not match the configured RepoNPC Python process."
    }

    Write-Step "Stopping the stale launcher-managed server (PID $processId)."
    & taskkill.exe /PID $processId /T /F | Out-Null
    if ($LASTEXITCODE -ne 0) {
        # taskkill can reject an otherwise accessible process when its tree contains
        # a handle from another elevation context. The PID and executable were
        # validated above, so a direct stop is still bounded to our owned process.
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
        }
        catch {
            throw "Unable to stop the stale launcher-managed server (PID $processId)."
        }
    }
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if (-not (Test-RepoNpcHealth $BaseUrl)) {
            return
        }
        Start-Sleep -Milliseconds 250
    }
    throw "The stale launcher-managed server did not stop cleanly."
}

function Invoke-RepoNpcLauncher {
    Set-Location -LiteralPath $repoRoot
    Repair-WindowsPathEnvironment
    Import-RepoNpcDotEnv (Join-Path $repoRoot ".env")

    $deploymentProfile = Get-ProcessEnvironmentValue "REPONPC_DEPLOYMENT_PROFILE"
    if ([string]::IsNullOrEmpty($deploymentProfile)) {
        $deploymentProfile = "loopback_evaluation"
    }
    if ($deploymentProfile -cnotin @("loopback_evaluation", "production")) {
        throw "REPONPC_DEPLOYMENT_PROFILE must be loopback_evaluation or production."
    }
    Set-ProcessEnvironmentValue "REPONPC_DEPLOYMENT_PROFILE" $deploymentProfile

    if ($Port -eq 0) {
        $configuredPort = Get-ProcessEnvironmentValue "REPONPC_PORT"
        $parsedPort = 0
        if (-not [int]::TryParse($configuredPort, [ref]$parsedPort) -or $parsedPort -lt 1 -or $parsedPort -gt 65535) {
            $parsedPort = 8090
        }
        $script:Port = $parsedPort
    }

    if ([string]::IsNullOrWhiteSpace($DataDir)) {
        $configuredDataDir = Get-ProcessEnvironmentValue "REPONPC_DATA_DIR"
        if ([string]::IsNullOrWhiteSpace($configuredDataDir) -or
            $configuredDataDir.Replace("\", "/") -eq "/var/lib/reponpc") {
            $resolvedDataDir = Join-Path $repoRoot "runtime-data\local"
        }
        elseif ([IO.Path]::IsPathRooted($configuredDataDir)) {
            $resolvedDataDir = $configuredDataDir
        }
        else {
            $resolvedDataDir = Join-Path $repoRoot $configuredDataDir
        }
    }
    elseif ([IO.Path]::IsPathRooted($DataDir)) {
        $resolvedDataDir = $DataDir
    }
    else {
        $resolvedDataDir = Join-Path $repoRoot $DataDir
    }
    $resolvedDataDir = [IO.Path]::GetFullPath($resolvedDataDir)

    $baseUrl = "http://localhost:$Port"
    Set-ProcessEnvironmentValue "REPONPC_PUBLIC_BASE_URL" $baseUrl
    Set-ProcessEnvironmentValue "REPONPC_HOST" "127.0.0.1"
    Set-ProcessEnvironmentValue "REPONPC_PORT" ([string]$Port)
    Set-ProcessEnvironmentValue "REPONPC_DATA_DIR" $resolvedDataDir
    Set-ProcessEnvironmentValue "REPONPC_TRUSTED_HOSTS" "localhost,127.0.0.1"
    Set-ProcessEnvironmentValue "REPONPC_ALLOWED_ORIGINS" $null
    Set-ProcessEnvironmentValue "REPONPC_TRUSTED_PROXY_CIDRS" $null
    if (-not [string]::IsNullOrWhiteSpace($ChatModel)) {
        Set-ProcessEnvironmentValue "REPONPC_CHAT_MODEL" $ChatModel
    }
    if ($deploymentProfile -eq "loopback_evaluation") {
        [IO.Directory]::CreateDirectory($resolvedDataDir) | Out-Null
        Set-ProcessEnvironmentValue "REPONPC_ENV" "development"
        Import-LocalSecretFiles
        Ensure-LocalIpHashKey
    }
    else {
        Set-ProcessEnvironmentValue "REPONPC_ENV" "production"
        Set-ProcessEnvironmentValue "REPONPC_ADMIN_ORIGINS" $baseUrl
        $directSecretNames = @(
            "REPONPC_CHAT_API_KEY", "REPONPC_EMBEDDING_API_KEY", "REPONPC_IP_HASH_KEY"
        )
        $configuredDirectSecrets = @($directSecretNames | Where-Object {
            -not [string]::IsNullOrEmpty((Get-ProcessEnvironmentValue $_))
        })
        if ($configuredDirectSecrets.Count -gt 0) {
            throw (($configuredDirectSecrets -join ", ") + ": put the value in a file under $resolvedDataDir\private and use the _FILE variable.")
        }
        foreach ($name in $directSecretNames) {
            $fileName = $name + "_FILE"
            $fileValue = Get-ProcessEnvironmentValue $fileName
            if (-not [string]::IsNullOrEmpty($fileValue)) {
                if (-not [IO.Path]::IsPathRooted($fileValue)) {
                    $fileValue = Join-Path $repoRoot $fileValue
                }
                Set-ProcessEnvironmentValue $fileName ([IO.Path]::GetFullPath($fileValue))
            }
        }
    }

    $pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
    $reponpcExe = Join-Path $repoRoot ".venv\Scripts\reponpc.exe"
    $pythonEnvironmentNeedsSync =
        -not (Test-Path -LiteralPath $pythonExe -PathType Leaf) -or
        -not (Test-Path -LiteralPath $reponpcExe -PathType Leaf)
    if (-not $pythonEnvironmentNeedsSync) {
        $pythonEnvironmentNeedsSync = $true
        try {
            $venvConfig = [IO.File]::ReadAllText((Join-Path $repoRoot ".venv\pyvenv.cfg"))
            if ($venvConfig -match '(?m)^\s*version(?:_info)?\s*=\s*(\d+\.\d+\.\d+)\s*$') {
                $pythonEnvironmentNeedsSync = [version]$Matches[1] -lt [version]"3.14"
            }
        }
        catch {
            $pythonEnvironmentNeedsSync = $true
        }
    }
    if ($pythonEnvironmentNeedsSync) {
        $uv = Resolve-ExternalCommand @("uv.exe", "uv")
        if ($null -eq $uv) {
            throw "The launcher needs uv to prepare Python 3.14. Install uv, then run this launcher again."
        }
        Write-Step "Installing locked Python dependencies."
        $uvCacheDirectory = Join-Path $repoRoot ".uv-cache"
        [IO.Directory]::CreateDirectory($uvCacheDirectory) | Out-Null
        $syncArguments = @("--cache-dir", $uvCacheDirectory, "sync", "--frozen")
        & $uv @syncArguments
        if ($LASTEXITCODE -ne 0) {
            throw "uv sync failed with exit code $LASTEXITCODE."
        }
    }

    if ($deploymentProfile -eq "production") {
        $prepareDataDirectory = @"
import sys
from pathlib import Path
from reponpc.windows_launcher import UnsafeDataDirectory, owner_only_fix_command, prepare_data_directory

try:
    key_path = prepare_data_directory(Path(sys.argv[1]), production=True)
except UnsafeDataDirectory as exc:
    print(f'\u79c1\u5bc6\u8def\u5f91\u6b0a\u9650\u904e\u5bec / Private path is not owner-only: {exc.path}')
    print(owner_only_fix_command(exc.path, root=exc.root))
    sys.exit(3)
print(key_path)
"@
        $preparationOutput = @(& $pythonExe -c $prepareDataDirectory $resolvedDataDir)
        $preparationExitCode = $LASTEXITCODE
        if ($preparationExitCode -eq 3) {
            $preparationOutput | ForEach-Object { Write-Host $_ }
            throw "Production data directory preparation stopped."
        }
        if ($preparationExitCode -ne 0 -or $preparationOutput.Count -ne 1) {
            throw "Unable to prepare the production data directory."
        }
        if ([string]::IsNullOrEmpty((Get-ProcessEnvironmentValue "REPONPC_IP_HASH_KEY_FILE"))) {
            Set-ProcessEnvironmentValue "REPONPC_IP_HASH_KEY_FILE" ([string]$preparationOutput[0])
        }
    }

    if (-not $SkipBuild -and (Test-WebBuildRequired)) {
        if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "node_modules") -PathType Container)) {
            Write-Step "Installing locked Web dependencies."
            Invoke-Pnpm @("install", "--frozen-lockfile")
        }
        Write-Step "Building the Web interface."
        Invoke-Pnpm @("run", "web:build")
    }

    Write-Step "Validating the local deployment environment."
    $environmentCheck = @"
import sys
from reponpc.config.environment import EnvironmentValidationError, format_environment_error, load_environment

def check_environment():
    try:
        load_environment()
    except EnvironmentValidationError as exc:
        print(format_environment_error(exc), file=sys.stderr)
        return 2
    return 0

sys.exit(check_environment())
"@
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell treats native stderr as an error record.
        $ErrorActionPreference = "Continue"
        $environmentOutput = @(& $pythonExe -c $environmentCheck 2>&1)
        $environmentExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($environmentExitCode -ne 0) {
        throw (($environmentOutput -join "`n") + ". Review .env and try again.")
    }

    if ($deploymentProfile -eq "production" -and -not $SmokeTest) {
        $ownerConsole = @"
import os
import sys
from pathlib import Path
from reponpc.windows_launcher import run_owner_console

sys.exit(0 if run_owner_console(Path(sys.argv[1]), environ=os.environ) else 2)
"@
        & $pythonExe -c $ownerConsole $resolvedDataDir
        if ($LASTEXITCODE -ne 0) {
            throw "Production owner setup was not completed."
        }
    }

    $startedHere = $false
    $logsDirectory = Join-Path $resolvedDataDir "logs"
    $statePath = Join-Path $resolvedDataDir "launcher-state.json"
    $probeBaseUrl = "http://127.0.0.1:$Port"
    $running = Test-RepoNpcHealth $probeBaseUrl
    $state = Read-LauncherState $statePath
    if ($running -and -not (Test-LauncherOwnsRunningInstance $statePath $baseUrl $resolvedDataDir)) {
        throw "A healthy process is already using $baseUrl but is not managed by this RepoNPC launcher. Stop it or choose another port."
    }
    if ($running -and (Test-LauncherStateStale $state)) {
        Stop-LauncherOwnedInstance -State $state -PythonPath $pythonExe -BaseUrl $probeBaseUrl
        $running = $false
    }
    if ($running) {
        Write-Step "RepoNPC is already running at $baseUrl."
    }
    else {
        if (Test-TcpPortOpen $Port) {
            throw "Port $Port is already used by another application. Run scripts\start-reponpc.ps1 -Port <port>."
        }
        [IO.Directory]::CreateDirectory($logsDirectory) | Out-Null
        $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
        $stdoutLog = Join-Path $logsDirectory "server-$stamp.out.log"
        $stderrLog = Join-Path $logsDirectory "server-$stamp.err.log"
        Write-Step "Starting the local server. Logs: $logsDirectory"
        $server = Start-Process -FilePath $pythonExe `
            -ArgumentList @("-m", "reponpc.cli", "serve") `
            -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog
        if (-not (Wait-RepoNpcHealth $probeBaseUrl $server)) {
            throw "RepoNPC did not become healthy. Review $stderrLog."
        }
        $startedHere = $true
        @{
            pid = $server.Id
            base_url = $baseUrl
            data_dir = $resolvedDataDir
            started_at = [DateTime]::UtcNow.ToString("o")
        } | ConvertTo-Json | Set-Content -LiteralPath $statePath -Encoding UTF8
        Write-Step "Server is healthy."
    }

    if ($deploymentProfile -eq "loopback_evaluation") {
        $launchOutput = @(& $reponpcExe admin launch-token --data-dir $resolvedDataDir 2>&1)
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to issue the local launch URL."
        }
        if ($launchOutput.Count -ne 1) {
            throw "The local launch command returned an invalid response."
        }
        $adminUrl = ([string]$launchOutput[0]).Trim()
        $expectedLaunchPrefix = "$baseUrl/admin#local-launch="
        if (-not $adminUrl.StartsWith($expectedLaunchPrefix, [StringComparison]::Ordinal) -or
            $adminUrl.Substring($expectedLaunchPrefix.Length) -notmatch '^[A-Za-z0-9_-]{43}$') {
            throw "The local launch command returned an invalid response."
        }
    }
    else {
        $adminUrl = "$baseUrl/admin"
    }

    if ($SmokeTest) {
        if (-not $startedHere -or $null -eq $server -or $server.HasExited) {
            throw "The isolated smoke-test server is not running."
        }
        Stop-Process -Id $server.Id -Force
        Wait-Process -Id $server.Id -Timeout 10 -ErrorAction SilentlyContinue
        Write-Step "Isolated startup smoke test passed and its server was stopped."
    }
    elseif (-not $NoBrowser) {
        Write-Step "Opening RepoNPC Admin."
        Start-Process -FilePath $adminUrl | Out-Null
    }
    else {
        if ($deploymentProfile -eq "loopback_evaluation") {
            Write-Host "One-use Admin URL (expires in two minutes):" -ForegroundColor Yellow
        }
        Write-Host $adminUrl -ForegroundColor White
    }

    if (-not $SmokeTest) {
        Write-Host "RepoNPC keeps running in the background after this window closes." -ForegroundColor Green
    }
}

$exitCode = 0
try {
    Invoke-RepoNpcLauncher
}
catch {
    $exitCode = 1
    Write-Host ""
    Write-Host "RepoNPC startup failed: $($_.Exception.Message)" -ForegroundColor Red
}
finally {
    if (-not $NoPause) {
        Write-Host ""
        [void](Read-Host "Press Enter to close this launcher")
    }
}
exit $exitCode
