# Activate .venv and run the extraction pipeline.
# Usage:
#   .\scripts\run.ps1
#   .\scripts\run.ps1 --limit 10
#   .\scripts\run.ps1 --themes-dir out/themes/theme-20260731_175600

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Activate = Join-Path $Root ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $Activate)) {
    Write-Error ".venv missing. Run .\scripts\setup.ps1 first."
}
. $Activate

python pipeline.py @args
