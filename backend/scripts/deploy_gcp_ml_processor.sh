#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_V2_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${BACKEND_V2_DIR}/.." && pwd)"

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load_env.sh" "${BACKEND_V2_DIR}/.env"

: "${GCP_PROJECT_ID:?Missing GCP_PROJECT_ID}"
: "${GCP_REGION:?Missing GCP_REGION}"
: "${GCP_SERVICE_NAME:?Missing GCP_SERVICE_NAME}"
GCP_ARTIFACT_REPOSITORY="${GCP_ARTIFACT_REPOSITORY:-ml-processors}"

BASE_DOCKERFILE="${BACKEND_V2_DIR}/gcp/base_images/ml_processor_base/Dockerfile"
APP_DOCKERFILE="${BACKEND_V2_DIR}/gcp/ml_processor/Dockerfile"

if [[ ! -f "${BASE_DOCKERFILE}" ]]; then
  echo "Missing base Dockerfile: ${BASE_DOCKERFILE}" >&2
  exit 1
fi

if [[ ! -f "${APP_DOCKERFILE}" ]]; then
  echo "Missing app Dockerfile: ${APP_DOCKERFILE}" >&2
  exit 1
fi

IMAGE_TAG="${IMAGE_TAG:-v2-$(date -u +%Y%m%d%H%M%S)}"
BASE_IMAGE="gcr.io/${GCP_PROJECT_ID}/aussie-ecolens-ml-processor-base:${IMAGE_TAG}"
LOCAL_BASE_IMAGE_TAG="aussie-ecolens-ml-processor-base:latest"
IMAGE_URI="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_ARTIFACT_REPOSITORY}/ml-processor:${IMAGE_TAG}"

echo "== Deploy backend v2 GCP ML processor =="
echo "BASE_DOCKERFILE=${BASE_DOCKERFILE}"
echo "APP_DOCKERFILE=${APP_DOCKERFILE}"
echo "BASE_IMAGE=${BASE_IMAGE}"
echo "LOCAL_BASE_IMAGE_TAG=${LOCAL_BASE_IMAGE_TAG}"
echo "IMAGE_URI=${IMAGE_URI}"

HMAC_DEPLOY_ARGS=()
if [[ -n "${GCP_HMAC_SECRET:-}" ]]; then
  HMAC_DEPLOY_ARGS+=(--set-secrets "INTERNAL_HMAC_SECRET=${GCP_HMAC_SECRET}:latest")
elif [[ -n "${INTERNAL_HMAC_SECRET:-}" ]]; then
  HMAC_DEPLOY_ARGS+=(--set-env-vars "INTERNAL_HMAC_SECRET=${INTERNAL_HMAC_SECRET}")
else
  echo "Missing GCP_HMAC_SECRET or INTERNAL_HMAC_SECRET" >&2
  echo "Set GCP_HMAC_SECRET to a GCP Secret Manager secret name, or set INTERNAL_HMAC_SECRET in backend-v2/.env." >&2
  exit 1
fi


gcloud artifacts repositories describe "${GCP_ARTIFACT_REPOSITORY}" \
  --project "${GCP_PROJECT_ID}" \
  --location "${GCP_REGION}" >/dev/null 2>&1 || \
gcloud artifacts repositories create "${GCP_ARTIFACT_REPOSITORY}" \
  --project "${GCP_PROJECT_ID}" \
  --location "${GCP_REGION}" \
  --repository-format docker \
  --description "Aussie EcoLens backend v2 ML processor images" \
  --quiet

gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet

docker build \
  --platform linux/amd64 \
  -f "${BASE_DOCKERFILE}" \
  -t "${BASE_IMAGE}" \
  -t "${LOCAL_BASE_IMAGE_TAG}" \
  "${REPO_ROOT}"

docker build \
  --platform linux/amd64 \
  -f "${APP_DOCKERFILE}" \
  -t "${IMAGE_URI}" \
  "${REPO_ROOT}"

docker push "${IMAGE_URI}"

gcloud run deploy "${GCP_SERVICE_NAME}" \
  --project "${GCP_PROJECT_ID}" \
  --region "${GCP_REGION}" \
  --image "${IMAGE_URI}" \
  --no-allow-unauthenticated \
  --execution-environment gen2 \
  --cpu "${GCP_CLOUD_RUN_CPU:-4}" \
  --memory "${GCP_CLOUD_RUN_MEMORY:-16Gi}" \
  --gpu "${GCP_CLOUD_RUN_GPU_COUNT:-1}" \
  --gpu-type "${GCP_CLOUD_RUN_GPU_TYPE:-nvidia-l4}" \
  --no-gpu-zonal-redundancy \
  --min-instances "${GCP_CLOUD_RUN_MIN_INSTANCES:-0}" \
  --max-instances "${GCP_CLOUD_RUN_MAX_INSTANCES:-1}" \
  --no-cpu-throttling \
  --set-env-vars "ENVIRONMENT=${ENVIRONMENT:-us-demo},GCP_MODEL_CACHE_DIR=${GCP_MODEL_CACHE_DIR:-/tmp/aussie-ecolens-models},MAX_TIME_SKEW_SECONDS=${MAX_TIME_SKEW_SECONDS:-300},GCP_MODEL_VERSION=${GCP_MODEL_VERSION:-request-presigned-models-v1}" \
  "${HMAC_DEPLOY_ARGS[@]}"

echo "Deployed Cloud Run service ${GCP_SERVICE_NAME} -> ${IMAGE_URI}"
