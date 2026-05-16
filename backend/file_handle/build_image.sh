#!/bin/bash
set -e

docker buildx build --platform linux/amd64 --provenance=false -t howardliao0211:upload_image .
