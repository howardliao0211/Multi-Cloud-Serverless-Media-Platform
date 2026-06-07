#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_V2_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${BACKEND_V2_DIR}/.." && pwd)"

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load_env.sh" "${BACKEND_V2_DIR}/.env"

usage() {
  echo "Usage: $0 <function-name> <context-dir>"
  echo "Example: $0 media_ingest_v2 backend-v2/aws/container_functions/media_ingest"
}

if [[ $# -ne 2 ]]; then
  usage
  exit 2
fi

FUNCTION_NAME="$1"
CONTEXT_DIR_INPUT="$2"

if [[ "${CONTEXT_DIR_INPUT}" = /* ]]; then
  CONTEXT_DIR="${CONTEXT_DIR_INPUT}"
else
  CONTEXT_DIR="${REPO_ROOT}/${CONTEXT_DIR_INPUT}"
fi

if [[ ! -d "${CONTEXT_DIR}" ]]; then
  echo "Missing context directory: ${CONTEXT_DIR}" >&2
  exit 1
fi

DOCKERFILE="${CONTEXT_DIR}/Dockerfile"
if [[ ! -f "${DOCKERFILE}" ]]; then
  echo "Missing Dockerfile: ${DOCKERFILE}" >&2
  exit 1
fi

: "${AWS_REGION:?Missing AWS_REGION}"
if [[ -z "${AWS_ACCOUNT_ID:-}" ]]; then
  AWS_ACCOUNT_ID="$(aws sts get-caller-identity \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" \
    --query Account \
    --output text)"
fi
: "${AWS_PROFILE:?Missing AWS_PROFILE}"

IMAGE_TAG="${IMAGE_TAG:-$(date -u +%Y%m%d%H%M%S)}"
ECR_REPOSITORY="${ECR_REPOSITORY:-${FUNCTION_NAME}}"
IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPOSITORY}:${IMAGE_TAG}"

echo "== Deploy backend v2 container Lambda =="
echo "FUNCTION_NAME=${FUNCTION_NAME}"
echo "CONTEXT_DIR=${CONTEXT_DIR}"
echo "DOCKERFILE=${DOCKERFILE}"
echo "IMAGE_URI=${IMAGE_URI}"

aws ecr describe-repositories \
  --repository-names "${ECR_REPOSITORY}" \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}" >/dev/null 2>&1 || \
aws ecr create-repository \
  --repository-name "${ECR_REPOSITORY}" \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}" >/dev/null

aws ecr get-login-password \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}" | \
docker login \
  --username AWS \
  --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  --load \
  -f "${DOCKERFILE}" \
  -t "${IMAGE_URI}" \
  "${REPO_ROOT}"

docker push "${IMAGE_URI}"

aws lambda update-function-code \
  --function-name "${FUNCTION_NAME}" \
  --image-uri "${IMAGE_URI}" \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}" >/dev/null

echo "Waiting for Lambda code update..."
aws lambda wait function-updated \
  --function-name "${FUNCTION_NAME}" \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}"

echo "Deployed ${FUNCTION_NAME} -> ${IMAGE_URI}"
