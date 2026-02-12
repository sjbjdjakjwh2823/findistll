#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${SUPABASE_DB_URL:-}" ]]; then
  echo "SUPABASE_DB_URL not set"
  exit 1
fi

file="${1:-}"
if [[ -z "${file}" ]]; then
  echo "Usage: restore_postgres.sh <backup.sql>"
  exit 1
fi

psql "${SUPABASE_DB_URL}" < "${file}"
echo "Restore completed: ${file}"
