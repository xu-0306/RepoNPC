$ErrorActionPreference = "Stop"
$root = "D:\RepoNPC"
$stdout = Join-Path $root ".agent-foreman\phase3-grounded-visitor\artifacts\fresh-browser-server-out.txt"
$stderr = Join-Path $root ".agent-foreman\phase3-grounded-visitor\artifacts\fresh-browser-server-err.txt"
$arguments = @(
  "--app-dir", ".agent-foreman/phase3-grounded-visitor/evaluation/fresh",
  "fresh_browser_fixture_app:app", "--host", "127.0.0.1", "--port", "8876"
)
$info = [System.Diagnostics.ProcessStartInfo]::new()
$info.FileName = "D:\RepoNPC\.venv\Scripts\uvicorn.exe"
$info.WorkingDirectory = $root
$info.UseShellExecute = $false
$info.CreateNoWindow = $true
$info.RedirectStandardOutput = $true
$info.RedirectStandardError = $true
$info.Arguments = ($arguments -join " ")
$process = [System.Diagnostics.Process]::new()
$process.StartInfo = $info
[void]$process.Start()
$process.BeginOutputReadLine()
$process.BeginErrorReadLine()
$process.Id
