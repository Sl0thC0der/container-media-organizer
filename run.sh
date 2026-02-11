#!/bin/bash
# Media Library Organization (Standalone)
# Requires Docker Desktop with Model Runner enabled

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export MEDIA_PATH="${MEDIA_PATH:-/path/to/media/library}"
cd "$SCRIPT_DIR"

echo "Media Library Organization"
echo "=========================="
echo ""
echo "MEDIA_PATH=$MEDIA_PATH"
echo "Running in Docker container..."
docker-compose up --abort-on-container-exit media-organizer
