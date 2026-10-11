[CmdletBinding()]
param(
    [switch]$SkipInstaller,
    [string]$IsccPath = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if ($env:OS -ne "Windows_NT") { throw "Windows packaging requires a Windows build host." }

function Assert-NoReparsePath([string]$Path) {
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Build paths must not contain symlinks or reparse points: $cursor"
            }
        }
        $parent = [IO.Directory]::GetParent($cursor)
        $cursor = if ($null -eq $parent) { $null } else { $parent.FullName }
    }
}

function Assert-BuildPath([string]$Path, [string]$Root) {
    $absolute = [IO.Path]::GetFullPath($Path)
    $prefix = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    if (-not $absolute.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Build path is outside the dedicated Windows output directory: $absolute"
    }
    Assert-NoReparsePath $absolute
}

function Get-SafeFiles([string]$Path) {
    Assert-NoReparsePath $Path
    foreach ($item in Get-ChildItem -LiteralPath $Path -Force) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Build trees must not contain symlinks or reparse points: $($item.FullName)"
        }
        if ($item.PSIsContainer) { Get-SafeFiles $item.FullName }
        else { $item }
    }
}

function Invoke-BuildCommand([string]$Executable, [string[]]$Arguments) {
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE." }
}

$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$outputRoot = Join-Path $repoRoot "dist/windows"
$buildRoot = Join-Path $outputRoot "RepoNPC"
$workRoot = Join-Path $outputRoot "pyinstaller-work"
$marker = Join-Path $outputRoot ".reponpc-windows-build"
Assert-NoReparsePath $repoRoot
Assert-NoReparsePath $outputRoot
foreach ($path in @($buildRoot, $workRoot, $marker)) { Assert-BuildPath $path $outputRoot }
if (Test-Path -LiteralPath $outputRoot) {
    $null = @(Get-SafeFiles $outputRoot)
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) {
        throw "Refusing to overwrite an unrecognized dist/windows directory."
    }
    if ([IO.File]::ReadAllText($marker) -ne "RepoNPC Windows build output v1") {
        throw "Windows build ownership marker is invalid."
    }
}
foreach ($inputPath in @("pyproject.toml", "uv.lock", "packaging/windows/reponpc.spec", "packaging/windows/launch.py", "tools/generate_windows_notices.py", "pnpm-lock.yaml")) {
    Assert-NoReparsePath (Join-Path $repoRoot $inputPath)
}
$null = @(Get-SafeFiles (Join-Path $repoRoot "src/reponpc"))
$null = @(Get-SafeFiles (Join-Path $repoRoot "apps/web/src"))

# Resolve the compiler before dependency installs or output mutation. No fake
# installer receipt is produced when Inno Setup is absent.
$compiler = $null
if (-not $SkipInstaller) {
    if ($IsccPath) { $compiler = [IO.Path]::GetFullPath($IsccPath) }
    else {
        $found = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
        if ($found) { $compiler = $found.Source }
    }
    if (-not $compiler -or -not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
        throw "Inno Setup compiler is required. Supply -IsccPath or explicitly use -SkipInstaller."
    }
    Assert-NoReparsePath $compiler
    # Official portable ISCC builds may have 0.0.0.0 PE version resources.
    # Ask ISPP for its own version with output disabled in an existing directory.
    $compilerProbe = @'
#if Ver < EncodeVer(6,3,0)
  #error Inno Setup 6.3 or newer is required
#endif
#pragma message "RepoNPC compiler check: " + DecodeVer(Ver)
[Setup]
AppName=RepoNPC compiler check
AppVersion=0
DefaultDirName={tmp}\reponpc-compiler-check
Output=no
OutputDir={#CompilerPath}
'@
    $compilerProbe | & $compiler "-"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup 6.3 or newer is required for the x64compatible installer recipe."
    }
    Assert-NoReparsePath (Join-Path $repoRoot "packaging/windows/reponpc.iss")
}

$previousPyinstallerConfig = $env:PYINSTALLER_CONFIG_DIR
Push-Location $repoRoot
try {
    Invoke-BuildCommand "uv" @("sync", "--locked", "--group", "windows-build")
    $versionCode = 'import pathlib,tomllib; print(tomllib.loads(pathlib.Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])'
    $appVersion = ($versionCode | & uv run --locked --group windows-build python - | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $appVersion -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') {
        throw "Could not read a supported installer version from pyproject metadata."
    }
    Invoke-BuildCommand "pnpm" @("install", "--frozen-lockfile")
    Invoke-BuildCommand "pnpm" @("run", "web:build")
    $null = @(Get-SafeFiles (Join-Path $repoRoot "apps/web/dist"))
    Invoke-BuildCommand "uv" @(
        "run", "--locked", "--group", "windows-build", "python",
        "tools/generate_windows_notices.py", "--output", "packaging/windows/THIRD_PARTY_NOTICES.txt"
    )
    $noticePath = Join-Path $repoRoot "packaging/windows/THIRD_PARTY_NOTICES.txt"
    Assert-NoReparsePath $noticePath
    if (-not (Test-Path -LiteralPath $noticePath -PathType Leaf)) {
        throw "Generate THIRD_PARTY_NOTICES.txt from the locked runtime before freezing."
    }
    [IO.Directory]::CreateDirectory($outputRoot) | Out-Null
    [IO.File]::WriteAllText($marker, "RepoNPC Windows build output v1")
    $env:PYINSTALLER_CONFIG_DIR = Join-Path $outputRoot "pyinstaller-cache"
    Assert-BuildPath $env:PYINSTALLER_CONFIG_DIR $outputRoot
    Invoke-BuildCommand "uv" @(
        "run", "--locked", "--group", "windows-build", "pyinstaller", "--noconfirm", "--clean",
        "--distpath", $outputRoot, "--workpath", $workRoot, "packaging/windows/reponpc.spec"
    )
    Assert-BuildPath (Join-Path $buildRoot "RepoNPC.exe") $outputRoot
    if (-not (Test-Path -LiteralPath (Join-Path $buildRoot "RepoNPC.exe") -PathType Leaf)) {
        throw "The frozen executable was not produced."
    }
    $builtFiles = @(Get-SafeFiles $buildRoot)
    if (-not $SkipInstaller) {
        $installer = Join-Path $outputRoot "RepoNPC-Setup-$appVersion.exe"
        Assert-BuildPath $installer $outputRoot
        if (Test-Path -LiteralPath $installer) { Remove-Item -LiteralPath $installer -Force }
        Invoke-BuildCommand $compiler @(
            "/DAppVersion=$appVersion", "/DBuildRoot=$buildRoot", "/DOutputRoot=$outputRoot",
            "packaging/windows/reponpc.iss"
        )
        Assert-BuildPath $installer $outputRoot
        if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
            throw "Inno Setup did not produce the expected installer."
        }
        $builtFiles += Get-Item -LiteralPath $installer
    }
    $gatePath = Join-Path $outputRoot "RELEASE-GATES.txt"
    $checksumPath = Join-Path $outputRoot "SHA256SUMS"
    foreach ($path in @($gatePath, $checksumPath)) { Assert-BuildPath $path $outputRoot }
    $gates = @(
        "Local build only; public release and AC-069 clean-Windows acceptance are incomplete.",
        "Unsigned executable/installer: publish SmartScreen guidance with exact SHA-256 checksums.",
        "Clean-account launch, health, upgrade, uninstall and data-preservation walkthrough remains required."
    )
    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "LICENSE") -PathType Leaf)) {
        $gates += "BLOCKED: root LICENSE is missing; project metadata is not a substitute for the release license file."
    }
    if ($SkipInstaller) { $gates += "Installer deliberately skipped; no installer artifact or installer acceptance claimed." }
    [IO.File]::WriteAllLines($gatePath, $gates, [Text.UTF8Encoding]::new($false))
    $builtFiles += Get-Item -LiteralPath $gatePath
    $checksums = foreach ($file in ($builtFiles | Sort-Object FullName)) {
        $relative = $file.FullName.Substring($outputRoot.Length + 1).Replace('\', '/')
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $relative"
    }
    [IO.File]::WriteAllLines($checksumPath, [string[]]$checksums, [Text.UTF8Encoding]::new($false))
    Write-Host "Windows artifacts: $outputRoot"
    Write-Warning "Local build complete; read RELEASE-GATES.txt before release."
}
finally {
    $env:PYINSTALLER_CONFIG_DIR = $previousPyinstallerConfig
    Pop-Location
}
