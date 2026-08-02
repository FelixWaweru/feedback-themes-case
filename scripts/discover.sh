#!/usr/bin/env bash
# Activate .venv and run theme discovery (+ optional extraction).
# Usage:
#   ./scripts/discover.sh
#   ./scripts/discover.sh --discover-only --limit-batches 1
#   ./scripts/discover.sh --extract-only --themes-dir out/themes/theme-20260731_175600

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

python discover_themes.py "$@"
