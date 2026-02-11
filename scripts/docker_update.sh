#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="pixelforge:latest"
CONTAINER_NAME="pixelforge"
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

echo "Rebuilding image $IMAGE_NAME..."
docker build --pull -t "$IMAGE_NAME" "$ROOT_DIR"

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

echo "Restarting container $CONTAINER_NAME on port 7003..."
docker run -d --name "$CONTAINER_NAME" \
  -p 7003:7003 \
  -e HOST=0.0.0.0 \
  -e PORT=7003 \
  -v "$DATA_DIR:/app/data" \
  "$IMAGE_NAME" >/dev/null

echo "Done. Open http://127.0.0.1:7003"
