#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
FUNCTION_NAME="${FUNCTION_NAME:-tag_image}"
REPOSITORY_NAME="${ECR_REPOSITORY_NAME:-aussie_eco_len}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ARCHITECTURE="${ARCHITECTURE:-x86_64}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-900}"
MEMORY_SIZE_MB="${MEMORY_SIZE_MB:-3000}"

# For creating the Lambda if it does not exist.
# Prefer LAMBDA_ROLE_ARN. If it is not set, resolve LAMBDA_ROLE_NAME.
LAMBDA_ROLE_NAME="${LAMBDA_ROLE_NAME:-aussie-eco-len-lambda-role}"
LAMBDA_ROLE_ARN="${LAMBDA_ROLE_ARN:-}"

# Optional environment variables passed to the Lambda container.
BUCKET_NAME="${BUCKET_NAME:-}"
TABLE_NAME="${TABLE_NAME:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DOCKER_CONTEXT="${DOCKER_CONTEXT:-${BACKEND_ROOT}/container_functions/${FUNCTION_NAME}}"
DOCKERFILE="${DOCKERFILE:-${DOCKER_CONTEXT}/Dockerfile}"
LOCAL_IMAGE="${LOCAL_IMAGE:-${REPOSITORY_NAME}:${IMAGE_TAG}}"

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

command -v aws >/dev/null 2>&1 || {
  echo "Error: aws CLI is not installed or not on PATH." >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || {
  echo "Error: docker is not installed or not on PATH." >&2
  exit 1
}

if [[ ! -d "${DOCKER_CONTEXT}" ]]; then
  echo "Error: Docker context does not exist: ${DOCKER_CONTEXT}" >&2
  exit 1
fi

if [[ ! -f "${DOCKERFILE}" ]]; then
  echo "Error: Dockerfile does not exist: ${DOCKERFILE}" >&2
  exit 1
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
REMOTE_IMAGE="${ECR_REGISTRY}/${REPOSITORY_NAME}:${IMAGE_TAG}"

if [[ -z "${LAMBDA_ROLE_ARN}" ]]; then
  LAMBDA_ROLE_ARN="$(aws iam get-role \
    --role-name "${LAMBDA_ROLE_NAME}" \
    --query 'Role.Arn' \
    --output text)"
fi

if [[ "${LAMBDA_ROLE_ARN}" != arn:aws:iam::*:role/* && "${LAMBDA_ROLE_ARN}" != arn:aws-us-gov:iam::*:role/* ]]; then
  echo "Error: LAMBDA_ROLE_ARN must be an IAM role ARN, not a user ARN." >&2
  echo "Current value: ${LAMBDA_ROLE_ARN}" >&2
  exit 1
fi

ENV_VARS=""
if [[ -n "${BUCKET_NAME}" || -n "${TABLE_NAME}" ]]; then
  ENV_VARS="Variables={"
  if [[ -n "${BUCKET_NAME}" ]]; then
    ENV_VARS+="BUCKET_NAME=${BUCKET_NAME}"
  fi
  if [[ -n "${TABLE_NAME}" ]]; then
    if [[ "${ENV_VARS}" != "Variables={" ]]; then
      ENV_VARS+=","
    fi
    ENV_VARS+="TABLE_NAME=${TABLE_NAME}"
  fi
  ENV_VARS+="}"
fi

echo "Deploying container Lambda: ${FUNCTION_NAME}"
echo "Region: ${AWS_REGION}"
echo "Architecture: ${ARCHITECTURE}"
echo "Docker context: ${DOCKER_CONTEXT}"
echo "Dockerfile: ${DOCKERFILE}"
echo "ECR image: ${REMOTE_IMAGE}"

aws ecr describe-repositories \
  --repository-names "${REPOSITORY_NAME}" \
  --region "${AWS_REGION}" >/dev/null 2>&1 || \
aws ecr create-repository \
  --repository-name "${REPOSITORY_NAME}" \
  --region "${AWS_REGION}" \
  --image-scanning-configuration scanOnPush=true \
  --image-tag-mutability MUTABLE >/dev/null

echo "Logging in to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" | \
  docker login --username AWS --password-stdin "${ECR_REGISTRY}"

echo "Building Docker image..."
docker buildx build \
  --platform "${DOCKER_PLATFORM}" \
  --provenance=false \
  --no-cache \
  -t "${LOCAL_IMAGE}" \
  -f "${DOCKERFILE}" \
  "${DOCKER_CONTEXT}"

echo "Pushing Docker image..."
docker tag "${LOCAL_IMAGE}" "${REMOTE_IMAGE}"
docker push "${REMOTE_IMAGE}"

echo "Published image: ${REMOTE_IMAGE}"

if aws lambda get-function \
  --region "${AWS_REGION}" \
  --function-name "${FUNCTION_NAME}" >/dev/null 2>&1; then

  echo "Updating existing Lambda function ${FUNCTION_NAME}..."
  aws lambda update-function-code \
    --region "${AWS_REGION}" \
    --function-name "${FUNCTION_NAME}" \
    --image-uri "${REMOTE_IMAGE}" >/dev/null

  aws lambda wait function-updated \
    --region "${AWS_REGION}" \
    --function-name "${FUNCTION_NAME}"

  if [[ -n "${ENV_VARS}" ]]; then
    aws lambda update-function-configuration \
      --region "${AWS_REGION}" \
      --function-name "${FUNCTION_NAME}" \
      --timeout "${TIMEOUT_SECONDS}" \
      --memory-size "${MEMORY_SIZE_MB}" \
      --environment "${ENV_VARS}" >/dev/null
  else
    aws lambda update-function-configuration \
      --region "${AWS_REGION}" \
      --function-name "${FUNCTION_NAME}" \
      --timeout "${TIMEOUT_SECONDS}" \
      --memory-size "${MEMORY_SIZE_MB}" >/dev/null
  fi

else
  echo "Creating Lambda function ${FUNCTION_NAME}..."

  if [[ -n "${ENV_VARS}" ]]; then
    aws lambda create-function \
      --region "${AWS_REGION}" \
      --function-name "${FUNCTION_NAME}" \
      --package-type Image \
      --code ImageUri="${REMOTE_IMAGE}" \
      --role "${LAMBDA_ROLE_ARN}" \
      --architectures "${ARCHITECTURE}" \
      --timeout "${TIMEOUT_SECONDS}" \
      --memory-size "${MEMORY_SIZE_MB}" \
      --environment "${ENV_VARS}" >/dev/null
  else
    aws lambda create-function \
      --region "${AWS_REGION}" \
      --function-name "${FUNCTION_NAME}" \
      --package-type Image \
      --code ImageUri="${REMOTE_IMAGE}" \
      --role "${LAMBDA_ROLE_ARN}" \
      --architectures "${ARCHITECTURE}" \
      --timeout "${TIMEOUT_SECONDS}" \
      --memory-size "${MEMORY_SIZE_MB}" >/dev/null
  fi
fi

aws lambda wait function-updated \
  --region "${AWS_REGION}" \
  --function-name "${FUNCTION_NAME}" 2>/dev/null || true

echo "Deployment complete."
echo "Function: ${FUNCTION_NAME}"
echo "Image: ${REMOTE_IMAGE}"
