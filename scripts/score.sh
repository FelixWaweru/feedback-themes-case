#!/usr/bin/env bash
# Activate .venv and run the Compethic score checker with UTF-8 stdio.
# score.py itself is unmodified (stdlib-only); PYTHONUTF8 avoids Windows
# console encode errors when printing theme names.
# Usage:
#   ./scripts/score.sh
#   ./scripts/score.sh --pred out/flat.json
#   ./scripts/score.sh --pred out/runs/kimi-k3-20260731_201440/flat.json

set -euo pipefail
export PYTHONUTF8=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .venv/bin/activate ]]; then
  echo ".venv missing. Run ./scripts/setup.sh first." >&2
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if [[ $# -eq 0 ]]; then
  python score.py --pred out/flat.json
else
  python score.py "$@"
fi
