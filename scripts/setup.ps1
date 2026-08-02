# Setup: create venv, install requirements, seed .env if missing.
# Usage (from repo root):
#   .\scripts\setup.ps1

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Repo: $Root"

$PyCmd = $null
$PyArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -c "import sys" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $PyCmd = "py"
        $PyArgs = @("-3")
    }
}
if (-not $PyCmd) {
    foreach ($name in @("python", "python3")) {
        if (Get-Command $name -ErrorAction SilentlyContinue) {
            $PyCmd = $name
            $PyArgs = @()
            break
        }
    }
}
if (-not $PyCmd) {
    Write-Error "Python 3.10+ not found. Install Python or the 'py' launcher and retry."
}
Write-Host "Using: $PyCmd $($PyArgs -join ' ')"

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating .venv ..."
    & $PyCmd @PyArgs -m venv .venv
}

$Activate = Join-Path $Root ".venv\Scripts\Activate.ps1"
. $Activate

python -m pip install --upgrade pip
pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example - add your OPENROUTER_API_KEY"
} else {
    Write-Host ".env already present"
}

Write-Host ""
Write-Host "Setup complete. Activate with: .\.venv\Scripts\Activate.ps1"
Write-Host "PYTHONUTF8=1 is set for this session (recommended on Windows)."
Write-Host "Then: python pipeline.py   OR   python discover_themes.py"
