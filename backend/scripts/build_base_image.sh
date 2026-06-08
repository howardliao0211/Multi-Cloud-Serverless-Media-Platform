#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_IMAGE_DIR="${PROJECT_ROOT}/base_images"
BASE_IMAGE_NAME="${BASE_IMAGE_NAME:-ml_base}"
DOCKERFILE="${DOCKERFILE:-${BASE_IMAGE_DIR}/${BASE_IMAGE_NAME}/Dockerfile}"
BUILD_CONTEXT="${BUILD_CONTEXT:-${BASE_IMAGE_DIR}/${BASE_IMAGE_NAME}}"
ARCHITECTURE="${ARCHITECTURE:-${AWS_ARCHITECTURE:-x86_64}}"

case "${ARCHITECTURE}" in
  x86_64)
    DOCKER_PLATFORM="linux/amd64"
    ;;
  arm64)
    DOCKER_PLATFORM="linux/arm64"
    ;;
  *)
    echo "Error: unsupported ARCHITECTURE '${ARCHITECTURE}'. Use x86_64 or arm64." >&2
    exit 1
    ;;
esac

if [[ ! -f "${DOCKERFILE}" ]]; then
    echo "Error: Dockerfile does not exist: ${DOCKERFILE}" >&2
    exit 1
fi

echo "Building base image: ${BASE_IMAGE_NAME}"
echo "Dockerfile: ${DOCKERFILE}"
echo "Build context: ${BUILD_CONTEXT}"
echo "Platform: ${DOCKER_PLATFORM}"

docker build \
    --platform "${DOCKER_PLATFORM}" \
    -t "${BASE_IMAGE_NAME}" \
    -f "${DOCKERFILE}" \
    "${BUILD_CONTEXT}"
