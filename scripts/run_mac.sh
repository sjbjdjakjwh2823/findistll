#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$repo_root/.env" ]]; then
  echo ".env not found. Copy .env.example to .env and fill in values."
  exit 1
fi

if [[ ! -d "$repo_root/.venv" ]]; then
  echo ".venv not found. Run scripts/setup_mac.sh first."
  exit 1
fi

source "$repo_root/.venv/bin/activate"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8004
