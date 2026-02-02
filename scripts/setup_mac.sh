#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3.12 first."
  exit 1
fi

py_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$py_version" != "3.12" ]]; then
  echo "Python 3.12 required. Current: $py_version"
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "node not found. Install Node 22+ first."
  exit 1
fi

node_major="$(node -p 'process.versions.node.split(".")[0]')"
if [[ "$node_major" -lt 22 ]]; then
  echo "Node 22+ required. Current: $(node -v)"
  exit 1
fi

python3 -m venv "$repo_root/.venv"
source "$repo_root/.venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$repo_root/requirements.txt"

echo "Setup complete."
