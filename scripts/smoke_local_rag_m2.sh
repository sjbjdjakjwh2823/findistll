#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${PRECISO_BASE_URL:-http://localhost:8000}"
TENANT="${DEFAULT_TENANT_ID:-public}"
Q='Fed rate hike impact on leveraged suppliers'

echo "[1/3] Health check"
curl -fsS "${BASE_URL}/health" | sed 's/.*/ok/'

echo "[2/3] Status check"
curl -fsS "${BASE_URL}/api/v1/status" >/dev/null

echo "[3/3] RAG query check"
RESP="$(curl -fsS -X POST "${BASE_URL}/api/v1/rag/query" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: ${TENANT}" \
  -d "{\"query\":\"${Q}\",\"top_k\":5,\"threshold\":0.55}")"

RESP_JSON="${RESP}" /Users/leesangmin/Desktop/preciso/venv/bin/python - <<'PY'
import json
import os
payload = json.loads(os.environ.get("RESP_JSON", "{}") or "{}")
required = ["evidence", "cause_chain", "effect_chain", "prediction"]
missing = [k for k in required if k not in payload]
if missing:
    print(f"FAIL missing keys: {missing}")
    raise SystemExit(2)
print("PASS rag response schema")
PY

echo "Local RAG smoke passed."
