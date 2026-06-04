#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_SCRIPT="${PROJECT_ROOT}/scripts/deploy_function.sh"
DEPLOY_CONTAINER_SCRIPT="${PROJECT_ROOT}/scripts/deploy_container_function.sh"

FUNCTIONS=(
  "get_signed_url"
  "get_upload_status"
  "get_private_media"
  "get_public_media",
  "change_visibility"
)

CONTAINER_FUNCTIONS=(
    "tag_image"
    "tag_video"
)

if [[ ! -f "${DEPLOY_SCRIPT}" ]]; then
  echo "Error: deploy script not found: ${DEPLOY_SCRIPT}" >&2
  exit 1
fi

if [[ ! -f "${DEPLOY_CONTAINER_SCRIPT}" ]]; then
  echo "Error: deploy container script not found: ${DEPLOY_CONTAINER_SCRIPT}" >&2
  exit 1
fi

chmod +x "${DEPLOY_SCRIPT}"
chmod +x "${DEPLOY_CONTAINER_SCRIPT}"

echo "Deploying ${#FUNCTIONS[@]} Lambda functions..."
echo

for FUNCTION_NAME in "${FUNCTIONS[@]}"; do
  echo "=================================================="
  echo "Deploying function: ${FUNCTION_NAME}"
  echo "=================================================="

  FUNCTION_NAME="${FUNCTION_NAME}" "${DEPLOY_SCRIPT}"

  echo
  echo "Finished deploying: ${FUNCTION_NAME}"
  echo
done

echo "Deploying ${#CONTAINER_FUNCTIONS[@]} Lambda container functions..."
echo

for FUNCTION_NAME in "${CONTAINER_FUNCTIONS[@]}"; do
  echo "=================================================="
  echo "Deploying function: ${FUNCTION_NAME}"
  echo "=================================================="

  FUNCTION_NAME="${FUNCTION_NAME}" "${DEPLOY_CONTAINER_SCRIPT}"

  echo
  echo "Finished deploying: ${FUNCTION_NAME}"
  echo
done

echo "All Lambda functions deployed successfully."
