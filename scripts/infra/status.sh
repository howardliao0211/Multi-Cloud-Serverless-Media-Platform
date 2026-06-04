#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"
require_base_tools

cd "$REPO_ROOT"

echo "=== git ==="
git status --short || true

echo ""
echo "=== Terraform outputs ==="
cd "$REPO_ROOT/$TF_DIR"
terraform output || true

echo ""
echo "=== Cloud Run ==="
gcloud run services describe "$SERVICE_NAME" \
  --region "$GCP_REGION" \
  --project "$GCP_PROJECT_ID" \
  --format="yaml(status.latestReadyRevisionName,status.url,spec.template.spec.containers[0].image,spec.template.spec.containers[0].env)" || true

echo ""
echo "=== Lambda images ==="
for fn in tag_image tag_video query_file; do
  aws lambda get-function-configuration \
    --function-name "$fn" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" \
    --query '{FunctionName:FunctionName,LastModified:LastModified,Image:Code.ImageUri}' \
    --output table || true
done
