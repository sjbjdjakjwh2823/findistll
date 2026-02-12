#!/usr/bin/env bash
set -euo pipefail

base="${1:-http://localhost:8004}"

curl -sf "${base}/api/v1/status" >/dev/null
echo "status ok"
