#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_IMAGE_DIR="${PROJECT_ROOT}/base_images"
BASE_IMAGE_NAME="${BASE_IMAGE_NAME:-ml_base}"
DOCKERFILE="${DOCKERFILE:-${BASE_IMAGE_DIR}/${BASE_IMAGE_NAME}/Dockerfile}"
BUILD_CONTEXT="${BUILD_CONTEXT:-${BASE_IMAGE_DIR}/${BASE_IMAGE_NAME}}"

if [[ ! -f "${DOCKERFILE}" ]]; then
    echo "Error: Dockerfile does not exist: ${DOCKERFILE}" >&2
    exit 1
fi

echo "Building base image: ${BASE_IMAGE_NAME}"
echo "Dockerfile: ${DOCKERFILE}"
echo "Build context: ${BUILD_CONTEXT}"

docker buildx build \
    -t "${BASE_IMAGE_NAME}" \
    -f "${DOCKERFILE}" \
    "${BUILD_CONTEXT}"
