#!/usr/bin/env bash
set -euo pipefail

MODE="${PRECISO_ROLLBACK_MODE:-}"
COMPOSE_FILE="${PRECISO_DOCKER_COMPOSE_FILE:-docker-compose.yml}"
SERVICE_NAME="${PRECISO_DOCKER_SERVICE:-preciso}"
PREV_IMAGE="${PRECISO_PREV_IMAGE:-}"
SYSTEMD_SERVICE="${PRECISO_SYSTEMD_SERVICE:-}"
PREV_DIR="${PRECISO_PREV_DIR:-}"
CURRENT_SYMLINK="${PRECISO_CURRENT_SYMLINK:-/opt/preciso/current}"

echo "Rollback mode: ${MODE:-unset}"

if [[ "$MODE" == "compose" ]]; then
  if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "Compose file not found: $COMPOSE_FILE"
    exit 1
  fi
  if [[ -z "$PREV_IMAGE" ]]; then
    echo "Set PRECISO_PREV_IMAGE to rollback (e.g. registry/preciso:sha)."
    exit 1
  fi
  echo "Rolling back via docker compose..."
  export PRECISO_IMAGE="$PREV_IMAGE"
  docker compose -f "$COMPOSE_FILE" pull "$SERVICE_NAME"
  docker compose -f "$COMPOSE_FILE" up -d "$SERVICE_NAME"
  echo "Rollback complete. Run smoke tests manually."
  exit 0
fi

if [[ "$MODE" == "systemd" ]]; then
  if [[ -z "$SYSTEMD_SERVICE" ]]; then
    echo "Set PRECISO_SYSTEMD_SERVICE for systemd rollback."
    exit 1
  fi
  if [[ -z "$PREV_DIR" ]]; then
    echo "Set PRECISO_PREV_DIR to the previous release directory."
    exit 1
  fi
  echo "Rolling back via systemd..."
  if [[ -d "$PREV_DIR" ]]; then
    ln -sfn "$PREV_DIR" "$CURRENT_SYMLINK"
  else
    echo "Previous release directory missing: $PREV_DIR"
    exit 1
  fi
  systemctl restart "$SYSTEMD_SERVICE"
  echo "Rollback complete. Run smoke tests manually."
  exit 0
fi

echo "No rollback executed. Set PRECISO_ROLLBACK_MODE to 'compose' or 'systemd'."
echo "Also configure required variables: PRECISO_PREV_IMAGE or PRECISO_PREV_DIR."
exit 1
