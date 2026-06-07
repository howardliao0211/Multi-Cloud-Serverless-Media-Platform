#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_V2_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${BACKEND_V2_DIR}/.." && pwd)"

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load_env.sh" "${BACKEND_V2_DIR}/.env"

usage() {
  echo "Usage: $0 <function-name> <function-dir>"
  echo "Example: $0 process_ml_result_v2 backend-v2/aws/functions/process_ml_result"
}

if [[ $# -ne 2 ]]; then
  usage
  exit 2
fi

FUNCTION_NAME="$1"
FUNCTION_DIR_INPUT="$2"

if [[ "${FUNCTION_DIR_INPUT}" = /* ]]; then
  FUNCTION_DIR="${FUNCTION_DIR_INPUT}"
else
  FUNCTION_DIR="${REPO_ROOT}/${FUNCTION_DIR_INPUT}"
fi

if [[ ! -d "${FUNCTION_DIR}" ]]; then
  echo "Missing function directory: ${FUNCTION_DIR}" >&2
  exit 1
fi

if [[ ! -f "${FUNCTION_DIR}/app.py" ]]; then
  echo "Missing app.py in function directory: ${FUNCTION_DIR}" >&2
  exit 1
fi

: "${AWS_REGION:?Missing AWS_REGION}"
: "${AWS_PROFILE:?Missing AWS_PROFILE}"

BUILD_ROOT="${BACKEND_V2_DIR}/.build"
BUILD_DIR="${BUILD_ROOT}/${FUNCTION_NAME}"
ZIP_PATH="${BUILD_ROOT}/${FUNCTION_NAME}.zip"
SHARED_DIR="${BACKEND_V2_DIR}/aws/layers/python/shared"

echo "== Deploy backend v2 zip Lambda =="
echo "FUNCTION_NAME=${FUNCTION_NAME}"
echo "FUNCTION_DIR=${FUNCTION_DIR}"
echo "SHARED_DIR=${SHARED_DIR}"

if [[ ! -d "${SHARED_DIR}" ]]; then
  echo "Missing shared layer directory: ${SHARED_DIR}" >&2
  exit 1
fi

rm -rf "${BUILD_DIR}" "${ZIP_PATH}"
mkdir -p "${BUILD_DIR}"

cp "${FUNCTION_DIR}/app.py" "${BUILD_DIR}/app.py"
cp -R "${SHARED_DIR}" "${BUILD_DIR}/shared"

if [[ -f "${FUNCTION_DIR}/requirements.txt" ]]; then
  python3 -m pip install \
    --no-cache-dir \
    --platform manylinux2014_x86_64 \
    --implementation cp \
    --python-version 3.12 \
    --only-binary=:all: \
    -r "${FUNCTION_DIR}/requirements.txt" \
    -t "${BUILD_DIR}"
fi

(cd "${BUILD_DIR}" && zip -qr "${ZIP_PATH}" .)

aws lambda update-function-code \
  --function-name "${FUNCTION_NAME}" \
  --zip-file "fileb://${ZIP_PATH}" \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}" >/dev/null

echo "Waiting for Lambda code update..."
aws lambda wait function-updated \
  --function-name "${FUNCTION_NAME}" \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}"

echo "Deployed ${FUNCTION_NAME} from ${ZIP_PATH}"
