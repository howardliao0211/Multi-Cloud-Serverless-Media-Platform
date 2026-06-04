#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

export AWS_PROFILE="${AWS_PROFILE:-AussieEcoLense}"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_ARCHITECTURE="${AWS_ARCHITECTURE:-x86_64}"

export GCP_PROJECT_ID="${GCP_PROJECT_ID:-hazel-sphinx-490908-u6}"
export GCP_REGION="${GCP_REGION:-us-east4}"
export GCP_AR_REPO="${GCP_AR_REPO:-aussie-ecolens}"
export SERVICE_NAME="${SERVICE_NAME:-aussie-eco-len-us-demo-ml-processor}"

export TF_DIR="${TF_DIR:-terraform}"
export TFVARS="${TFVARS:-envs/us-demo.tfvars}"

export MODEL_BUCKET="${MODEL_BUCKET:-aussie-eco-len-bucket-12345}"
export CLASSIFIER_MODEL_KEY="${CLASSIFIER_MODEL_KEY:-models/model.pt}"
export DETECTOR_MODEL_KEY="${DETECTOR_MODEL_KEY:-models/mdv5a.pt}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Error: required command not found: $1" >&2
    exit 1
  }
}

require_base_tools() {
  require_cmd terraform
  require_cmd aws
  require_cmd gcloud
  require_cmd docker
}

generate_model_urls() {
  export CLASSIFIER_MODEL_URL="$(
    aws s3 presign "s3://${MODEL_BUCKET}/${CLASSIFIER_MODEL_KEY}" \
      --expires-in 604800 \
      --region "$AWS_REGION" \
      --profile "$AWS_PROFILE"
  )"

  export DETECTOR_MODEL_URL="$(
    aws s3 presign "s3://${MODEL_BUCKET}/${DETECTOR_MODEL_KEY}" \
      --expires-in 604800 \
      --region "$AWS_REGION" \
      --profile "$AWS_PROFILE"
  )"

  test -n "$CLASSIFIER_MODEL_URL"
  test -n "$DETECTOR_MODEL_URL"
}

current_gcp_image_uri() {
  local tag="${1:-tf-start-$(date +%Y%m%d%H%M%S)}"
  echo "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${GCP_AR_REPO}/ml-processor:${tag}"
}
