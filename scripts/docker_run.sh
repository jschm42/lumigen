#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="lumigen:latest"
CONTAINER_NAME="lumigen"
ENV_FILE="$ROOT_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

DATA_DIR="${DOCKER_DATA_DIR:-$ROOT_DIR/data}"
if [[ "$DATA_DIR" != /* ]]; then
  DATA_DIR="$ROOT_DIR/$DATA_DIR"
fi

mkdir -p "$DATA_DIR"

echo "Building image $IMAGE_NAME..."
docker build -t "$IMAGE_NAME" "$ROOT_DIR"

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

echo "Starting container $CONTAINER_NAME on port 7003..."
DOCKER_ENV_ARGS=()
for env_key in PROVIDER_CONFIG_KEY SESSION_HTTPS_ONLY PROXY_HEADERS_ENABLED PROXY_HEADERS_TRUSTED_HOSTS; do
  env_value="${!env_key-}"
  if [[ -n "$env_value" ]]; then
    DOCKER_ENV_ARGS+=("-e" "$env_key=$env_value")
  fi
done

DOCKER_ENV_FILE_ARGS=()
if [[ -f "$ENV_FILE" ]]; then
  DOCKER_ENV_FILE_ARGS+=("--env-file" "$ENV_FILE")
fi

docker run -d --name "$CONTAINER_NAME" \
  -p 7003:7003 \
  -e HOST=0.0.0.0 \
  -e PORT=7003 \
  "${DOCKER_ENV_FILE_ARGS[@]}" \
  "${DOCKER_ENV_ARGS[@]}" \
  -v "$DATA_DIR:/app/data" \
  "$IMAGE_NAME" >/dev/null

echo "Done. Open http://127.0.0.1:7003"
