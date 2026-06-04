#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_SCRIPT="${PROJECT_ROOT}/scripts/deploy_function.sh"
FUNCTIONS_DIR="${PROJECT_ROOT}/functions"
BUILD_DIR="${PROJECT_ROOT}/build"

if [[ ! -d "${FUNCTIONS_DIR}" ]]; then
  echo "Error: functions directory not found: ${FUNCTIONS_DIR}" >&2
  exit 1
fi

if [[ ! -f "${DEPLOY_SCRIPT}" ]]; then
  echo "Error: deploy script not found: ${DEPLOY_SCRIPT}" >&2
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

echo "Cleaning build directory: ${BUILD_DIR}"
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

echo "Deploying ${#FUNCTIONS[@]} Lambda functions..."
echo

for FUNCTION_NAME in "${FUNCTIONS[@]}"; do
  echo "=================================================="
  echo "Deploying function: ${FUNCTION_NAME}"
  echo "=================================================="

  BUILD_DIR="${BUILD_DIR}" \
  FUNCTION_NAME="${FUNCTION_NAME}" \
  REBUILD_LAYER=false \
  bash "${DEPLOY_SCRIPT}"

  echo
  echo "Finished deploying: ${FUNCTION_NAME}"
  echo
done

echo "All Lambda functions deployed successfully."