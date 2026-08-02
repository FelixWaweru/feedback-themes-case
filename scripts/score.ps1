# Activate .venv and run the Compethic score checker with UTF-8 stdio.
# score.py itself is unmodified (stdlib-only); PYTHONUTF8 avoids Windows
# console encode errors when printing theme names.
# Usage:
#   .\scripts\score.ps1
#   .\scripts\score.ps1 --pred out/flat.json
#   .\scripts\score.ps1 --pred out/runs/kimi-k3-20260731_201440/flat.json

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Activate = Join-Path $Root ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $Activate)) {
    Write-Error ".venv missing. Run .\scripts\setup.ps1 first."
}
. $Activate

if ($args.Count -eq 0) {
    python score.py --pred out/flat.json
} else {
    python score.py @args
}
