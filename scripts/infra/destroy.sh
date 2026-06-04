#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"
require_base_tools

cat <<MSG
This will destroy Terraform-managed resources for ${TFVARS}.
Existing data-source-only AWS resources such as the S3 bucket, DynamoDB table,
Cognito user pool, and API Gateway are not destroyed unless you later import
or convert them to Terraform resources.
MSG
read -r -p "Type destroy to continue: " confirm
if [[ "$confirm" != "destroy" ]]; then
  echo "Cancelled."
  exit 0
fi

cd "$REPO_ROOT/$TF_DIR"
terraform init
terraform destroy \
  -var-file="$TFVARS" \
  -var "cloud_run_deletion_protection=false"
