#!/bin/bash
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
REPOSITORY_NAME="${ECR_REPOSITORY_NAME:-aussie_eco_len}"
LOCAL_IMAGE="${LOCAL_IMAGE:-howardliao0211:upload_image}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
LAMBDA_FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-file_upload}"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
REMOTE_IMAGE="${ECR_REGISTRY}/${REPOSITORY_NAME}:${IMAGE_TAG}"

aws ecr describe-repositories \
    --repository-names "$REPOSITORY_NAME" \
    --region "$REGION" >/dev/null 2>&1 || \
aws ecr create-repository \
    --repository-name "$REPOSITORY_NAME" \
    --region "$REGION" \
    --image-scanning-configuration scanOnPush=true \
    --image-tag-mutability MUTABLE >/dev/null

aws ecr get-login-password --region "$REGION" | \
docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker tag "$LOCAL_IMAGE" "$REMOTE_IMAGE"
docker push "$REMOTE_IMAGE"

echo "Published image: $REMOTE_IMAGE"

if [[ -n "$LAMBDA_FUNCTION_NAME" ]]; then
    aws lambda update-function-code \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --image-uri "$REMOTE_IMAGE" \
        --region "$REGION" >/dev/null

    aws lambda wait function-updated \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --region "$REGION"

    aws lambda update-function-configuration \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --region "$REGION" \
        --timeout 900 \
        --memory-size 8192 >/dev/null

    aws lambda wait function-updated \
        --function-name "$LAMBDA_FUNCTION_NAME" \
        --region "$REGION"

    echo "Updated Lambda function: $LAMBDA_FUNCTION_NAME"
else
    echo "Set LAMBDA_FUNCTION_NAME to update the Lambda function to this image."
fi
