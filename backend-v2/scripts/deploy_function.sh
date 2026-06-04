#!/usr/bin/env bash
set -euo pipefail

FUNCTION_NAME="${1:?Usage: deploy_function.sh <function-name> <source-dir>}"
SOURCE_DIR="${2:?Usage: deploy_function.sh <function-name> <source-dir>}"

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_PROFILE="${AWS_PROFILE:-AussieEcoLense}"
LAMBDA_ROLE_ARN="${LAMBDA_ROLE_ARN:-arn:aws:iam::539913718279:role/aussie-eco-len-lambda-role}"
PYTHON_RUNTIME="${PYTHON_RUNTIME:-python3.12}"
ARCHITECTURE="${LAMBDA_ARCHITECTURE:-arm64}"
TIMEOUT="${LAMBDA_TIMEOUT:-60}"
MEMORY="${LAMBDA_MEMORY:-1024}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_V2_DIR="${ROOT_DIR}/backend-v2"
BUILD_DIR="${BACKEND_V2_DIR}/.build/${FUNCTION_NAME}"
ZIP_PATH="${BACKEND_V2_DIR}/.build/${FUNCTION_NAME}.zip"

rm -rf "$BUILD_DIR" "$ZIP_PATH"
mkdir -p "$BUILD_DIR"

echo "Packaging ${FUNCTION_NAME} from ${SOURCE_DIR}"

cp -R "${BACKEND_V2_DIR}/layers/python/shared" "${BUILD_DIR}/shared"
cp "${SOURCE_DIR}/app.py" "${BUILD_DIR}/app.py"

if [ -f "${SOURCE_DIR}/requirements.txt" ] && [ -s "${SOURCE_DIR}/requirements.txt" ]; then
  echo "Installing dependencies with uv"
  uv pip install \
    --target "$BUILD_DIR" \
    --python-platform "aarch64-manylinux2014" \
    --python-version "3.12" \
    -r "${SOURCE_DIR}/requirements.txt"
fi

(
  cd "$BUILD_DIR"
  zip -qr "$ZIP_PATH" .
)

if aws lambda get-function \
  --function-name "$FUNCTION_NAME" \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE" >/dev/null 2>&1
then
  echo "Updating existing Lambda ${FUNCTION_NAME}"
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://${ZIP_PATH}" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" >/dev/null

  aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE"

  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --runtime "$PYTHON_RUNTIME" \
    --handler "app.lambda_handler" \
    --timeout "$TIMEOUT" \
    --memory-size "$MEMORY" \
    --architectures "$ARCHITECTURE" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" >/dev/null
else
  echo "Creating Lambda ${FUNCTION_NAME}"
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime "$PYTHON_RUNTIME" \
    --handler "app.lambda_handler" \
    --role "$LAMBDA_ROLE_ARN" \
    --zip-file "fileb://${ZIP_PATH}" \
    --timeout "$TIMEOUT" \
    --memory-size "$MEMORY" \
    --architectures "$ARCHITECTURE" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" >/dev/null
fi

echo "Deployed ${FUNCTION_NAME}"
