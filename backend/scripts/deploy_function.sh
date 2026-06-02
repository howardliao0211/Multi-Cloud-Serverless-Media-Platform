#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
FUNCTION_NAME="${FUNCTION_NAME:-get_private_media}"
LAYER_NAME="${LAYER_NAME:-aussie-eco-len-shared}"
RUNTIME="${RUNTIME:-python3.12}"
HANDLER="${HANDLER:-app.lambda_handler}"
ARCHITECTURE="${ARCHITECTURE:-x86_64}"
LAMBDA_ROLE_ARN="${LAMBDA_ROLE_ARN:-arn:aws:iam::539913718279:role/aussie-eco-len-lambda-role}"

URL_EXPIRES_SECONDS="${URL_EXPIRES_SECONDS:-300}"
PYTHON_VERSION="${RUNTIME#python}"

case "${ARCHITECTURE}" in
  x86_64)
    PIP_PLATFORM="manylinux2014_x86_64"
    ;;
  arm64)
    PIP_PLATFORM="manylinux2014_aarch64"
    ;;
  *)
    echo "Error: unsupported ARCHITECTURE '${ARCHITECTURE}'. Use x86_64 or arm64." >&2
    exit 1
    ;;
esac

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${PROJECT_ROOT}/build"
LAYER_BUILD_DIR="${BUILD_DIR}/shared_layer"
FUNCTION_BUILD_DIR="${BUILD_DIR}/${FUNCTION_NAME}"
LAYER_ZIP="${BUILD_DIR}/shared_layer.zip"
FUNCTION_ZIP="${BUILD_DIR}/${FUNCTION_NAME}.zip"

SHARED_SOURCE_DIR="${PROJECT_ROOT}/layers/python/shared"
FUNCTION_SOURCE_DIR="${PROJECT_ROOT}/functions/${FUNCTION_NAME}"

echo "Deploying ${FUNCTION_NAME} to ${AWS_REGION}"

command -v aws >/dev/null 2>&1 || {
  echo "Error: aws CLI is not installed or not on PATH." >&2
  exit 1
}

command -v python3 >/dev/null 2>&1 || {
  echo "Error: python3 is not installed or not on PATH." >&2
  exit 1
}

command -v zip >/dev/null 2>&1 || {
  echo "Error: zip is not installed or not on PATH." >&2
  exit 1
}

rm -rf "${BUILD_DIR}"
mkdir -p "${LAYER_BUILD_DIR}/python" "${FUNCTION_BUILD_DIR}"

echo "Building shared layer..."
python3 -m pip install \
  --requirement "${SHARED_SOURCE_DIR}/requirements.txt" \
  --target "${LAYER_BUILD_DIR}/python" \
  --platform "${PIP_PLATFORM}" \
  --implementation cp \
  --python-version "${PYTHON_VERSION}" \
  --only-binary=:all: \
  --upgrade

cp -R "${SHARED_SOURCE_DIR}" "${LAYER_BUILD_DIR}/python/shared"

(
  cd "${LAYER_BUILD_DIR}"
  zip -qr "${LAYER_ZIP}" python
)

echo "Publishing layer ${LAYER_NAME}..."
LAYER_VERSION_ARN="$(
  aws lambda publish-layer-version \
    --region "${AWS_REGION}" \
    --layer-name "${LAYER_NAME}" \
    --zip-file "fileb://${LAYER_ZIP}" \
    --compatible-runtimes "${RUNTIME}" \
    --compatible-architectures "${ARCHITECTURE}" \
    --query 'LayerVersionArn' \
    --output text
)"

echo "Published layer: ${LAYER_VERSION_ARN}"

echo "Packaging Lambda function..."
cp "${FUNCTION_SOURCE_DIR}/app.py" "${FUNCTION_BUILD_DIR}/app.py"

(
  cd "${FUNCTION_BUILD_DIR}"
  zip -qr "${FUNCTION_ZIP}" app.py
)

if aws lambda get-function --region "${AWS_REGION}" --function-name "${FUNCTION_NAME}" >/dev/null 2>&1; then
  echo "Updating existing Lambda function ${FUNCTION_NAME}..."
  aws lambda update-function-code \
    --region "${AWS_REGION}" \
    --function-name "${FUNCTION_NAME}" \
    --zip-file "fileb://${FUNCTION_ZIP}" >/dev/null

  aws lambda wait function-updated \
    --region "${AWS_REGION}" \
    --function-name "${FUNCTION_NAME}"

  aws lambda update-function-configuration \
    --region "${AWS_REGION}" \
    --function-name "${FUNCTION_NAME}" \
    --runtime "${RUNTIME}" \
    --handler "${HANDLER}" \
    --layers "${LAYER_VERSION_ARN}" \
    --environment "Variables={URL_EXPIRES_SECONDS=${URL_EXPIRES_SECONDS}}" >/dev/null
else
  if [[ -z "${LAMBDA_ROLE_ARN}" ]]; then
    echo "Error: Lambda function does not exist and LAMBDA_ROLE_ARN is not set." >&2
    echo "Set LAMBDA_ROLE_ARN to an IAM role ARN, then rerun this script." >&2
    exit 1
  fi

  echo "Creating Lambda function ${FUNCTION_NAME}..."
  aws lambda create-function \
    --region "${AWS_REGION}" \
    --function-name "${FUNCTION_NAME}" \
    --runtime "${RUNTIME}" \
    --handler "${HANDLER}" \
    --architectures "${ARCHITECTURE}" \
    --role "${LAMBDA_ROLE_ARN}" \
    --zip-file "fileb://${FUNCTION_ZIP}" \
    --layers "${LAYER_VERSION_ARN}" \
    --environment "Variables={URL_EXPIRES_SECONDS=${URL_EXPIRES_SECONDS}}" >/dev/null
fi

aws lambda wait function-updated \
  --region "${AWS_REGION}" \
  --function-name "${FUNCTION_NAME}" 2>/dev/null || true

echo "Deployment complete."
echo "Function: ${FUNCTION_NAME}"
echo "Layer: ${LAYER_VERSION_ARN}"
