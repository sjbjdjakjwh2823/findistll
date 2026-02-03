#!/usr/bin/env bash
# Preciso Sovereign Deployment Script (Foundry/Apollo Style)
set -euo pipefail

IMAGE_NAME="preciso-sovereign-gateway"
TAG=$(date +%Y%m%d%H%M)

echo "--- Building Sovereign Image: $IMAGE_NAME:$TAG ---"
docker build -t "$IMAGE_NAME:$TAG" -t "$IMAGE_NAME:latest" .

echo "--- Running Sanity Checks on Container ---"
docker run --rm "$IMAGE_NAME:latest" python -c "from app.services.toolkit import PrecisoToolkit; print('Toolkit Integrity: OK')"

echo "--- Deployment Package Ready ---"
echo "To deploy in a sovereign environment, run:"
echo "docker run -d -p 8004:8004 --env-file .env $IMAGE_NAME:latest"

# Save audit log of deployment
date_iso=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "{\"event\": \"deployment\", \"image\": \"$IMAGE_NAME:$TAG\", \"timestamp\": \"$date_iso\"}" >> deploy_history.json
