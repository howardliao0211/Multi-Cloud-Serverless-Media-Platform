#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Build and push all AussieEcoLens container images.
#
# Expected repo root layout:
# - backend/base_images/ml_base/Dockerfile
# - backend/container_functions/tag_image/Dockerfile
# - backend/container_functions/tag_video/Dockerfile

# - backend/container_functions/query_file/Dockerfile
# - gcp/base_images/ml_processor_base/Dockerfile
# - gcp/ml_processor/Dockerfile
#
# This script builds AWS Lambda images as linux/amd64 by default,
# because current ML deps include intel-openmp, which has Linux x86_64
# wheels but not Linux arm64 wheels.
# ============================================================

# ---------- AWS config ----------
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_PROFILE="${AWS_PROFILE:-AussieEcoLense}"
export AWS_ARCHITECTURE="${AWS_ARCHITECTURE:-x86_64}"

# Lambda repositories / tags
export AWS_BASE_IMAGE_NAME="${AWS_BASE_IMAGE_NAME:-ml_base}"
export TAG_IMAGE_REPO="${TAG_IMAGE_REPO:-aussie-ecolens-tag-image}"
export TAG_VIDEO_REPO="${TAG_VIDEO_REPO:-aussie-ecolens-tag-video}"
export QUERY_FILE_REPO="${QUERY_FILE_REPO:-aussie-ecolens-query-file}"

export TAG_IMAGE_TAG="${TAG_IMAGE_TAG:-gcp-ml-dev}"
export TAG_VIDEO_TAG="${TAG_VIDEO_TAG:-ml-dev}"
export QUERY_FILE_TAG="${QUERY_FILE_TAG:-ml-dev}"

# ---------- GCP config ----------
export GCP_PROJECT_ID="${GCP_PROJECT_ID:-}"
export GCP_REGION="${GCP_REGION:-}"
export GCP_AR_REPO="${GCP_AR_REPO:-aussie-ecolens}"

export GCP_BASE_IMAGE_URL="${GCP_BASE_IMAGE_URL:-${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_AR_REPO}/ml-processor-base:gpu}"
export GCP_APP_IMAGE_TAG="${GCP_APP_IMAGE_TAG:-real-gpu-e2e-$(date +%Y%m%d%H%M%S)}"
export GCP_APP_IMAGE_URL="${GCP_APP_IMAGE_URL:-${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_AR_REPO}/ml-processor:${GCP_APP_IMAGE_TAG}}"

# ---------- Platform mapping ----------
case "${AWS_ARCHITECTURE}" in
  x86_64)
    AWS_DOCKER_PLATFORM="linux/amd64"
    ;;
  arm64)
    AWS_DOCKER_PLATFORM="linux/arm64"
    ;;
  *)
    echo "Error: unsupported AWS_ARCHITECTURE='${AWS_ARCHITECTURE}'. Use x86_64 or arm64." >&2
    exit 1
    ;;
esac

# GCP Cloud Run GPU/L4 image should be linux/amd64.
GCP_DOCKER_PLATFORM="linux/amd64"

# ---------- Paths ----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT="$(cd "${BACKEND_ROOT}/.." && pwd)"

AWS_BASE_DOCKERFILE="${PROJECT_ROOT}/backend/base_images/ml_base/Dockerfile"
AWS_BASE_CONTEXT="${PROJECT_ROOT}/backend/base_images/ml_base"

AWS_LAMBDA_PYTHON_BASE_IMAGE_NAME="${AWS_LAMBDA_PYTHON_BASE_IMAGE_NAME:-lambda_python_base}"
AWS_LAMBDA_PYTHON_BASE_DOCKERFILE="${PROJECT_ROOT}/backend/base_images/lambda_python_base/Dockerfile"
AWS_LAMBDA_PYTHON_BASE_CONTEXT="${PROJECT_ROOT}/backend/base_images/lambda_python_base"

TAG_IMAGE_DOCKERFILE="${PROJECT_ROOT}/backend/container_functions/tag_image/Dockerfile"
TAG_VIDEO_DOCKERFILE="${PROJECT_ROOT}/backend/container_functions/tag_video/Dockerfile"
QUERY_FILE_DOCKERFILE="${PROJECT_ROOT}/backend/container_functions/query_file/Dockerfile"
AWS_FUNCTION_CONTEXT="${PROJECT_ROOT}/backend"

GCP_BASE_DOCKERFILE="${PROJECT_ROOT}/gcp/base_images/ml_processor_base/Dockerfile"
GCP_APP_DOCKERFILE="${PROJECT_ROOT}/gcp/ml_processor/Dockerfile"
GCP_CONTEXT="${PROJECT_ROOT}"

# ---------- Helpers ----------
need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Error: required command not found: $1" >&2
    exit 1
  }
}

require_file() {
  if [[ ! -f "$1" ]]; then
    echo "Error: required file not found: $1" >&2
    exit 1
  fi
}

build_image() {
  local platform="$1"
  local tag="$2"
  local dockerfile="$3"
  local context="$4"
  shift 4

  echo ""
  echo "============================================================"
  echo "Building image: ${tag}"
  echo "Platform: ${platform}"
  echo "Dockerfile: ${dockerfile}"
  echo "Context: ${context}"
  echo "============================================================"

  docker buildx build \
    --platform "${platform}" \
    --provenance=false \
    --sbom=false \
    --load \
    -t "${tag}" \
    -f "${dockerfile}" \
    "$@" \
    "${context}"
}

push_image() {
  local image="$1"

  echo ""
  echo "============================================================"
  echo "Pushing image: ${image}"
  echo "============================================================"

  docker push "${image}"
}

ensure_ecr_repo() {
  local repo="$1"

  aws ecr describe-repositories \
    --repository-names "${repo}" \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" >/dev/null 2>&1 || \
  aws ecr create-repository \
    --repository-name "${repo}" \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" \
    --image-scanning-configuration scanOnPush=true \
    --image-tag-mutability MUTABLE >/dev/null
}

# ---------- Preflight ----------
need_cmd docker
need_cmd aws
need_cmd gcloud

require_file "${AWS_BASE_DOCKERFILE}"
require_file "${AWS_LAMBDA_PYTHON_BASE_DOCKERFILE}"
require_file "${TAG_IMAGE_DOCKERFILE}"
require_file "${TAG_VIDEO_DOCKERFILE}"
require_file "${QUERY_FILE_DOCKERFILE}"
require_file "${GCP_BASE_DOCKERFILE}"
require_file "${GCP_APP_DOCKERFILE}"

if [[ ! -f "${PROJECT_ROOT}/backend/container_functions/tag_image/auth/gcp_wif_credentials.json" ]]; then
  echo "Warning: tag_image WIF config not found:"
  echo "  backend/container_functions/tag_image/auth/gcp_wif_credentials.json"
  echo "The image can build, but private Cloud Run invocation may fail at runtime."
fi

if [[ ! -f "${PROJECT_ROOT}/gcp/ml_processor/models/model.pt" || ! -f "${PROJECT_ROOT}/gcp/ml_processor/models/mdv5a.pt" ]]; then
  echo "Error: GCP model files are required for gcp/ml_processor image:"
  echo "  gcp/ml_processor/models/model.pt"
  echo "  gcp/ml_processor/models/mdv5a.pt"
  exit 1
fi

echo ""
echo "Repo root: ${PROJECT_ROOT}"
echo "AWS region: ${AWS_REGION}"
echo "AWS profile: ${AWS_PROFILE}"
echo "AWS architecture: ${AWS_ARCHITECTURE}"
echo "AWS Docker platform: ${AWS_DOCKER_PLATFORM}"
echo "GCP project: ${GCP_PROJECT_ID}"
echo "GCP region: ${GCP_REGION}"
echo "GCP Docker platform: ${GCP_DOCKER_PLATFORM}"
echo "GCP base image: ${GCP_BASE_IMAGE_URL}"
echo "GCP app image: ${GCP_APP_IMAGE_URL}"

# ---------- AWS login ----------
echo ""
echo "============================================================"
echo "Logging in to AWS ECR"
echo "============================================================"

AWS_ACCOUNT_ID="$(aws sts get-caller-identity \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}" \
  --query Account \
  --output text)"

AWS_ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

aws ecr get-login-password \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}" | \
docker login \
  --username AWS \
  --password-stdin "${AWS_ECR_REGISTRY}"

# ---------- GCP login ----------
echo ""
echo "============================================================"
echo "Configuring Docker auth for GCP Artifact Registry"
echo "============================================================"

gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet

# ---------- Ensure ECR repos ----------
ensure_ecr_repo "${TAG_IMAGE_REPO}"
ensure_ecr_repo "${TAG_VIDEO_REPO}"
ensure_ecr_repo "${QUERY_FILE_REPO}"

# ---------- AWS base images ----------
# Lightweight Lambda Python base for non-ML container Lambdas.
build_image \
  "${AWS_DOCKER_PLATFORM}" \
  "${AWS_LAMBDA_PYTHON_BASE_IMAGE_NAME}:latest" \
  "${AWS_LAMBDA_PYTHON_BASE_DOCKERFILE}" \
  "${AWS_LAMBDA_PYTHON_BASE_CONTEXT}"

# Heavy ML Lambda base for image/video inference Lambdas.
# This is local-only because child Dockerfiles use FROM ml_base:latest.
# If you later want this pushed too, create an ECR repo for it and change
# child Dockerfiles to FROM <remote-uri>.
build_image \
  "${AWS_DOCKER_PLATFORM}" \
  "${AWS_BASE_IMAGE_NAME}:latest" \
  "${AWS_BASE_DOCKERFILE}" \
  "${AWS_BASE_CONTEXT}"

# ---------- AWS Lambda function images ----------
TAG_IMAGE_LOCAL="${TAG_IMAGE_REPO}:${TAG_IMAGE_TAG}"
TAG_VIDEO_LOCAL="${TAG_VIDEO_REPO}:${TAG_VIDEO_TAG}"
QUERY_FILE_LOCAL="${QUERY_FILE_REPO}:${QUERY_FILE_TAG}"

TAG_IMAGE_REMOTE="${AWS_ECR_REGISTRY}/${TAG_IMAGE_REPO}:${TAG_IMAGE_TAG}"
TAG_VIDEO_REMOTE="${AWS_ECR_REGISTRY}/${TAG_VIDEO_REPO}:${TAG_VIDEO_TAG}"
QUERY_FILE_REMOTE="${AWS_ECR_REGISTRY}/${QUERY_FILE_REPO}:${QUERY_FILE_TAG}"

build_image \
  "${AWS_DOCKER_PLATFORM}" \
  "${TAG_IMAGE_LOCAL}" \
  "${TAG_IMAGE_DOCKERFILE}" \
  "${AWS_FUNCTION_CONTEXT}"

docker tag "${TAG_IMAGE_LOCAL}" "${TAG_IMAGE_REMOTE}"
push_image "${TAG_IMAGE_REMOTE}"

build_image \
  "${AWS_DOCKER_PLATFORM}" \
  "${TAG_VIDEO_LOCAL}" \
  "${TAG_VIDEO_DOCKERFILE}" \
  "${AWS_FUNCTION_CONTEXT}"

docker tag "${TAG_VIDEO_LOCAL}" "${TAG_VIDEO_REMOTE}"
push_image "${TAG_VIDEO_REMOTE}"

build_image \
  "${AWS_DOCKER_PLATFORM}" \
  "${QUERY_FILE_LOCAL}" \
  "${QUERY_FILE_DOCKERFILE}" \
  "${AWS_FUNCTION_CONTEXT}"

docker tag "${QUERY_FILE_LOCAL}" "${QUERY_FILE_REMOTE}"
push_image "${QUERY_FILE_REMOTE}"

# ---------- GCP base image ----------
build_image \
  "${GCP_DOCKER_PLATFORM}" \
  "${GCP_BASE_IMAGE_URL}" \
  "${GCP_BASE_DOCKERFILE}" \
  "${GCP_CONTEXT}"

push_image "${GCP_BASE_IMAGE_URL}"

# ---------- GCP app image ----------
build_image \
  "${GCP_DOCKER_PLATFORM}" \
  "${GCP_APP_IMAGE_URL}" \
  "${GCP_APP_DOCKERFILE}" \
  "${GCP_CONTEXT}" \
  --build-arg "BASE_IMAGE=${GCP_BASE_IMAGE_URL}"

push_image "${GCP_APP_IMAGE_URL}"

# ---------- Summary ----------
echo ""
echo "============================================================"
echo "Build and push complete"
echo "============================================================"
echo "AWS Lambda images:"
echo "  tag_image:  ${TAG_IMAGE_REMOTE}"
echo "  tag_video:  ${TAG_VIDEO_REMOTE}"
echo "  query_file: ${QUERY_FILE_REMOTE}"
echo ""
echo "GCP images:"
echo "  base: ${GCP_BASE_IMAGE_URL}"
echo "  app:  ${GCP_APP_IMAGE_URL}"
echo ""
echo "Next deploy commands:"
echo ""
echo "AWS:"
echo "  FUNCTION_NAME=tag_image IMAGE_TAG=${TAG_IMAGE_TAG} AWS_REGION=${AWS_REGION} bash backend/scripts/deploy_container_function.sh"
echo "  FUNCTION_NAME=tag_video IMAGE_TAG=${TAG_VIDEO_TAG} AWS_REGION=${AWS_REGION} bash backend/scripts/deploy_container_function.sh"
echo "  FUNCTION_NAME=query_file IMAGE_TAG=${QUERY_FILE_TAG} AWS_REGION=${AWS_REGION} bash backend/scripts/deploy_container_function.sh"
echo ""
echo "GCP:"
echo "  gcloud run deploy aussie-eco-len-us-demo-ml-processor \\"
echo "    --image ${GCP_APP_IMAGE_URL} \\"
echo "    --region ${GCP_REGION} \\"
echo "    --project ${GCP_PROJECT_ID} \\"
echo "    --gpu=1 \\"
echo "    --gpu-type=nvidia-l4 \\"
echo "    --no-gpu-zonal-redundancy \\"
echo "    --cpu=4 \\"
echo "    --memory=16Gi \\"
echo "    --no-cpu-throttling \\"
echo "    --concurrency=2 \\"
echo "    --min=0 \\"
echo "    --max=2"
