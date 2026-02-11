#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="img-hub:latest"
CONTAINER_NAME="img-hub"
DATA_DIR="$ROOT_DIR/data"

mkdir -p "$DATA_DIR"

echo "Building image $IMAGE_NAME..."
docker build -t "$IMAGE_NAME" "$ROOT_DIR"

docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true

echo "Starting container $CONTAINER_NAME on port 7003..."
docker run -d --name "$CONTAINER_NAME" \
  -p 7003:7003 \
  -e HOST=0.0.0.0 \
  -e PORT=7003 \
  -v "$DATA_DIR:/app/data" \
  "$IMAGE_NAME" >/dev/null

echo "Done. Open http://127.0.0.1:7003"
