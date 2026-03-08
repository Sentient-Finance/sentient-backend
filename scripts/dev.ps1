$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  throw "Missing .venv. Run .\scripts\bootstrap.ps1 first."
}

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}

$port = $env:PORT
if ([string]::IsNullOrWhiteSpace($port)) {
  $port = "8001"
}

# Kill process using port (force fresh start)
try {
  $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
  if ($connections) {
  $pids = $connections.OwningProcess | Sort-Object -Unique
  foreach ($procId in $pids) {
    Write-Host "Killing process $procId on port $port"
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
  }
    Start-Sleep -Seconds 2
  }
} catch {
  $lines = netstat -ano 2>$null | Select-String ":$port\s+.*LISTENING"
  foreach ($l in $lines) {
    $parts = ($l -split '\s+')
    $procId = $parts[-1]
    if ($procId -match '^\d+$') {
      Write-Host "Killing PID $procId on port $port"
      taskkill /PID $procId /F 2>$null
      Start-Sleep -Seconds 2
      break
    }
  }
}

# Clear Python cache
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path . -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
Write-Host "Cache cleared. Starting API on port $port"

& $python -m uvicorn apps.api.app.main:app --reload --reload-dir apps --reload-dir libs --port $port

