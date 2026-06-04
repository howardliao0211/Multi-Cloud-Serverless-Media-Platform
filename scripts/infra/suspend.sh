#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"
require_base_tools

cd "$REPO_ROOT/$TF_DIR"
terraform init
terraform apply \
  -var-file="$TFVARS" \
  -var "deploy_enabled=false" \
  -var "enable_s3_notifications=false" \
  -var "cloud_run_min_instances=0" \
  -var "cloud_run_max_instances=1" \
  -var "cloud_run_deletion_protection=false"
