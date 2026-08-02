#!/usr/bin/env bash
# Setup: create venv, install requirements, seed .env if missing.
# Usage (from repo root):
#   bash scripts/setup.sh
#   ./scripts/setup.sh

set -euo pipefail
export PYTHONUTF8=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Repo: $ROOT"

if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "python3/python not found. Install Python 3.10+ and retry." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Creating .venv ..."
  "$PY" -m venv .venv
else
  echo ".venv already exists"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — add your OPENROUTER_API_KEY"
else
  echo ".env already present"
fi

echo ""
echo "Setup complete. Activate with: source .venv/bin/activate"
echo "Then: python pipeline.py   OR   python discover_themes.py"
