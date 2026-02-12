#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${SUPABASE_DB_URL:-}" ]]; then
  echo "SUPABASE_DB_URL not set"
  exit 1
fi

ts="$(date +%Y%m%d_%H%M%S)"
out="backup_${ts}.sql"
pg_dump "${SUPABASE_DB_URL}" > "${out}"
echo "Backup created: ${out}"
