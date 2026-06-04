#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common.sh"

mkdir -p "$REPO_ROOT/evidence"
cd "$REPO_ROOT/tests"
AWS_PROFILE="$AWS_PROFILE" AWS_REGION="$AWS_REGION" \
  uv run pytest -s integration/test_media_flow.py | tee "$REPO_ROOT/evidence/e2e-test-final.txt"

cd "$REPO_ROOT"
aws logs tail /aws/lambda/tag_image \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE" \
  --since 15m | tee evidence/tag-image-final-logs.txt || true

gcloud run services logs read "$SERVICE_NAME" \
  --region "$GCP_REGION" \
  --project "$GCP_PROJECT_ID" \
  --limit 150 | tee evidence/cloud-run-final-logs.txt || true
