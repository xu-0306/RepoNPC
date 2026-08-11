$ErrorActionPreference = "Stop"

$baselinePath = Join-Path $PSScriptRoot "..\production-baseline.txt"
$rows = foreach ($line in Get-Content $baselinePath) {
    if ($line -notmatch "^[^|]+\|[0-9a-f]{64}\|[0-9]+$") {
        continue
    }
    $parts = $line.Split("|")
    $actual = if (Test-Path -LiteralPath $parts[0]) {
        (Get-FileHash -Algorithm SHA256 -LiteralPath $parts[0]).Hash.ToLowerInvariant()
    } else {
        "MISSING"
    }
    [pscustomobject]@{
        Path = $parts[0]
        Expected = $parts[1]
        Actual = $actual
        Match = ($actual -eq $parts[1])
    }
}

$outputPath = Join-Path $PSScriptRoot "..\artifacts\post-probe-integrity.txt"
$rows | Format-Table -AutoSize | Out-String -Width 240 | Tee-Object -FilePath $outputPath

if (($rows | Where-Object { -not $_.Match }).Count -gt 0) {
    exit 1
}
