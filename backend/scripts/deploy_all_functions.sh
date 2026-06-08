#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_BASE_SCRIPT="${PROJECT_ROOT}/scripts/build_base_image.sh"
DEPLOY_SCRIPT="${PROJECT_ROOT}/scripts/deploy_container_function.sh"
FUNCTIONS_DIR="${PROJECT_ROOT}/container_functions"
BASE_IMAGE_NAME="${BASE_IMAGE_NAME:-gcp_client_base}"

if [[ ! -d "${FUNCTIONS_DIR}" ]]; then
  echo "Error: functions directory not found: ${FUNCTIONS_DIR}" >&2
  exit 1
fi

if [[ ! -f "${DEPLOY_SCRIPT}" ]]; then
  echo "Error: deploy script not found: ${DEPLOY_SCRIPT}" >&2
  exit 1
fi

if [[ ! -f "${BUILD_BASE_SCRIPT}" ]]; then
  echo "Error: build base image script not found: ${BUILD_BASE_SCRIPT}" >&2
  exit 1
fi

mapfile -t FUNCTIONS < <(
  find "${FUNCTIONS_DIR}" \
    -mindepth 1 \
    -maxdepth 1 \
    -type d \
    -printf '%f\n' | sort
)

if [[ "${#FUNCTIONS[@]}" -eq 0 ]]; then
  echo "Error: no function folders found in ${FUNCTIONS_DIR}" >&2
  exit 1
fi

chmod +x "${DEPLOY_SCRIPT}"
chmod +x "${BUILD_BASE_SCRIPT}"

echo "Building shared container base image: ${BASE_IMAGE_NAME}"
BASE_IMAGE_NAME="${BASE_IMAGE_NAME}" bash "${BUILD_BASE_SCRIPT}"
echo

echo "Deploying ${#FUNCTIONS[@]} container Lambda functions..."
echo

for FUNCTION_NAME in "${FUNCTIONS[@]}"; do
  echo "=================================================="
  echo "Deploying function: ${FUNCTION_NAME}"
  echo "=================================================="

  FUNCTION_NAME="${FUNCTION_NAME}" \
  bash "${DEPLOY_SCRIPT}"

  echo
  echo "Finished deploying: ${FUNCTION_NAME}"
  echo
done

echo "All container Lambda functions deployed successfully."
