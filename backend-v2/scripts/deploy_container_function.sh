#!/usr/bin/env bash
set -euo pipefail

FUNCTION_NAME="${1:?Usage: deploy_container_function.sh <function-name> <context-dir>}"
CONTEXT_DIR="${2:?Usage: deploy_container_function.sh <context-dir>}"

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_PROFILE="${AWS_PROFILE:-AussieEcoLense}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-539913718279}"
LAMBDA_ROLE_ARN="${LAMBDA_ROLE_ARN:-arn:aws:iam::539913718279:role/aussie-eco-len-lambda-role}"
PLATFORM="${DOCKER_PLATFORM:-linux/amd64}"
NO_CACHE_FLAG="${DOCKER_NO_CACHE:+--no-cache}"
TIMEOUT="${LAMBDA_TIMEOUT:-120}"
MEMORY="${LAMBDA_MEMORY:-2048}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_V2_DIR="${ROOT_DIR}/backend-v2"
REPO_NAME="${FUNCTION_NAME}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${REPO_NAME}:${IMAGE_TAG}"

aws ecr describe-repositories \
  --repository-names "$REPO_NAME" \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE" >/dev/null 2>&1 || \
aws ecr create-repository \
  --repository-name "$REPO_NAME" \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE" >/dev/null

aws ecr get-login-password \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE" | docker login \
    --username AWS \
    --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

docker buildx build \
  $NO_CACHE_FLAG \
  --platform "$PLATFORM" \
  --provenance=false \
  --sbom=false \
  --output "type=image,push=true,oci-mediatypes=false" \
  -t "$IMAGE_URI" \
  -f "${BACKEND_V2_DIR}/container_functions/media_ingest/Dockerfile" \
  "$BACKEND_V2_DIR"

if aws lambda get-function \
  --function-name "$FUNCTION_NAME" \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE" >/dev/null 2>&1
then
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --image-uri "$IMAGE_URI" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" >/dev/null
else
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --package-type Image \
    --code ImageUri="$IMAGE_URI" \
    --role "$LAMBDA_ROLE_ARN" \
    --timeout "$TIMEOUT" \
    --memory-size "$MEMORY" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" >/dev/null
fi

aws lambda wait function-updated \
  --function-name "$FUNCTION_NAME" \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE"

echo "Deployed container Lambda ${FUNCTION_NAME}: ${IMAGE_URI}"
