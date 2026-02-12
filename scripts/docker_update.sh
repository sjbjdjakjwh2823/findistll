#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.onprem.yml}"

echo "[preciso] pulling images (compose file: ${COMPOSE_FILE})"
docker compose -f "${COMPOSE_FILE}" pull

echo "[preciso] restarting services"
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans

echo "[preciso] status"
docker compose -f "${COMPOSE_FILE}" ps
