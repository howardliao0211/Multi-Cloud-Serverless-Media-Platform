#!/bin/bash
set -euo pipefail

LOCAL_IMAGE="${LOCAL_IMAGE:-howardliao0211:upload_image}"

docker buildx build --platform linux/amd64 --provenance=false --no-cache -t "$LOCAL_IMAGE" .
