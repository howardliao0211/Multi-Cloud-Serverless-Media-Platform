#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"
require_base_tools
generate_model_urls

cd "$REPO_ROOT/$TF_DIR"
terraform init
terraform apply \
  -var-file="$TFVARS" \
  -var "deploy_enabled=true" \
  -var "enable_s3_notifications=true" \
  -var "cloud_run_min_instances=0" \
  -var "cloud_run_max_instances=2" \
  -var "cloud_run_deletion_protection=false" \
  -var "gcp_classifier_model_url=${CLASSIFIER_MODEL_URL}" \
  -var "gcp_detector_model_url=${DETECTOR_MODEL_URL}"
