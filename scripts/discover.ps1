# Activate .venv and run theme discovery (+ optional extraction).
# Usage:
#   .\scripts\discover.ps1
#   .\scripts\discover.ps1 --discover-only --limit-batches 1
#   .\scripts\discover.ps1 --extract-only --themes-dir out/themes/theme-20260731_175600

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Activate = Join-Path $Root ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $Activate)) {
    Write-Error ".venv missing. Run .\scripts\setup.ps1 first."
}
. $Activate

python discover_themes.py @args
