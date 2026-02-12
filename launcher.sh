#!/bin/bash
set -euo pipefail

REGISTRY=${REGISTRY:-""}
IMAGES=("preciso-frontend" "preciso-backend" "preciso-worker")

if [ -n "$REGISTRY" ]; then
  echo "Checking for updates from $REGISTRY..."
  for IMAGE in "${IMAGES[@]}"; do
    echo "Pulling $REGISTRY/$IMAGE:latest"
    docker pull "$REGISTRY/$IMAGE:latest" || true
  done
fi

echo "Starting Preciso on-prem stack..."
docker compose -f docker-compose.onprem.yml up -d

sleep 5
if curl -fsS http://localhost:3000/health >/dev/null 2>&1; then
  echo "Preciso is running on http://localhost:3000"
else
  echo "Startup check failed. Use: docker compose -f docker-compose.onprem.yml logs"
  exit 1
fi
