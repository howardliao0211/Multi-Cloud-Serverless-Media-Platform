#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${BACKEND_DIR}/.." && pwd)"

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load_env.sh" "${BACKEND_DIR}/.env"

export AWS_PAGER=""

OWNER_ID="${OWNER_ID:-manual-v2-test-user}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%d%H%M%S)}"
IMAGE_FILE="${IMAGE_FILE:-${REPO_ROOT}/tests/fixtures/media/Perameles_nasuta_1.JPG}"
VIDEO_FILE="${VIDEO_FILE:-${REPO_ROOT}/tests/fixtures/media/5214219-hd_1920_1080_25fps.mp4}"
DO_CLEANUP="false"

if [[ "${1:-}" == "--cleanup" ]]; then
  DO_CLEANUP="true"
fi

required_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required env var: ${name}" >&2
    exit 1
  fi
}

required_env AWS_REGION
required_env AWS_PROFILE
required_env MEDIA_BUCKET_NAME
required_env MEDIA_TABLE_NAME

if [[ ! -f "${IMAGE_FILE}" ]]; then
  echo "Missing image fixture: ${IMAGE_FILE}" >&2
  exit 1
fi

if [[ ! -f "${VIDEO_FILE}" ]]; then
  echo "Missing video fixture: ${VIDEO_FILE}" >&2
  exit 1
fi

sha256_file() {
  shasum -a 256 "$1" | awk '{print $1}'
}

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"
}

ddb_get_item() {
  local ddb_key="$1"

  aws dynamodb get-item \
    --table-name "${MEDIA_TABLE_NAME}" \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" \
    --key "{\"key\":{\"S\":${ddb_key}}}" \
    --output json
}

assert_ddb_ready_with_tags() {
  local ddb_key_raw="$1"
  local media_label="$2"
  local ddb_key_json
  ddb_key_json="$(json_escape "${ddb_key_raw}")"

  local item_json="/tmp/manual-e2e-v2-${media_label}-ddb.json"
  ddb_get_item "${ddb_key_json}" > "${item_json}"

  python3 - <<PY
import json
from pathlib import Path

p = Path("${item_json}")
data = json.loads(p.read_text())
item = data.get("Item")
if not item:
    raise SystemExit("No DynamoDB item found for ${media_label}")

status = item.get("upload_status", {}).get("S")
provider = item.get("ml_provider", {}).get("S")
tags = item.get("tags", {}).get("M", {})
thumbnail_key = item.get("thumbnail_key", {}).get("S")

print("${media_label} DynamoDB status:", status)
print("${media_label} provider:", provider)
print("${media_label} tags:", tags)
print("${media_label} thumbnail_key:", thumbnail_key)

if status != "ready":
    raise SystemExit(f"${media_label} upload_status is not ready: {status}")
if provider != "gcp_cloud_run":
    raise SystemExit(f"${media_label} ml_provider is not gcp_cloud_run: {provider}")
if not tags:
    raise SystemExit("${media_label} tags is empty")
if not thumbnail_key:
    raise SystemExit("${media_label} thumbnail_key is missing")
PY
}

invoke_media_ingest() {
  local event_path="$1"
  local response_path="$2"

  aws lambda invoke \
    --function-name media_ingest_v2 \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" \
    --payload "fileb://${event_path}" \
    "${response_path}" >/tmp/manual-e2e-v2-lambda-invoke.json

  cat /tmp/manual-e2e-v2-lambda-invoke.json
  echo
  cat "${response_path}"
  echo

  python3 - <<PY
import json
from pathlib import Path

outer = json.loads(Path("${response_path}").read_text())
status = outer.get("statusCode")
if status != 200:
    raise SystemExit(f"media_ingest_v2 returned statusCode={status}: {outer}")

body = json.loads(outer.get("body") or "{}")
result = body.get("result", {})
if result.get("statusCode") != 200:
    raise SystemExit(f"process_ml_result_v2 returned non-200: {result}")

print("Lambda invoke OK")
PY
}

create_s3_event() {
  local bucket="$1"
  local key="$2"
  local output="$3"

  cat > "${output}" <<EOF
{
  "Records": [
    {
      "eventSource": "aws:s3",
      "eventName": "ObjectCreated:Put",
      "s3": {
        "bucket": {"name": "${bucket}"},
        "object": {"key": "${key}"}
      }
    }
  ]
}
EOF
}

run_media_case() {
  local media_label="$1"
  local local_file="$2"
  local prefix="$3"

  local file_name
  file_name="$(basename "${local_file}")"

  local checksum
  checksum="$(sha256_file "${local_file}")"

  local s3_key="${prefix}/manual-${media_label}-${RUN_ID}-${file_name}"
  local event_path="/tmp/manual-e2e-v2-${media_label}-event.json"
  local response_path="/tmp/manual-e2e-v2-${media_label}-response.json"
  local ddb_key="OWNER#${OWNER_ID}#KEY#${s3_key}"

  echo "== ${media_label} E2E =="
  echo "local_file=${local_file}"
  echo "s3_key=${s3_key}"
  echo "checksum=${checksum}"

  aws s3 cp "${local_file}" "s3://${MEDIA_BUCKET_NAME}/${s3_key}" \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" \
    --metadata "owner_id=${OWNER_ID},checksum=${checksum},file_name=${file_name},visibility=private"

  create_s3_event "${MEDIA_BUCKET_NAME}" "${s3_key}" "${event_path}"
  invoke_media_ingest "${event_path}" "${response_path}"
  assert_ddb_ready_with_tags "${ddb_key}" "${media_label}"

  if [[ "${DO_CLEANUP}" == "true" ]]; then
    echo "Cleaning up ${media_label} artifacts..."

    local thumbnail_key
    thumbnail_key="$(python3 - <<PY
import json
from pathlib import Path

data = json.loads(Path("/tmp/manual-e2e-v2-${media_label}-ddb.json").read_text())
print(data.get("Item", {}).get("thumbnail_key", {}).get("S", ""))
PY
)"

    aws s3 rm "s3://${MEDIA_BUCKET_NAME}/${s3_key}" \
      --region "${AWS_REGION}" \
      --profile "${AWS_PROFILE}" || true

    if [[ -n "${thumbnail_key}" ]]; then
      aws s3 rm "s3://${MEDIA_BUCKET_NAME}/${thumbnail_key}" \
        --region "${AWS_REGION}" \
        --profile "${AWS_PROFILE}" || true
    fi

    aws dynamodb delete-item \
      --table-name "${MEDIA_TABLE_NAME}" \
      --region "${AWS_REGION}" \
      --profile "${AWS_PROFILE}" \
      --key "{\"key\":{\"S\":$(json_escape "${ddb_key}")}}" || true
  fi

  echo "== ${media_label} E2E passed =="
  echo
}

echo "== Manual backend E2E =="
echo "RUN_ID=${RUN_ID}"
echo "OWNER_ID=${OWNER_ID}"
echo "MEDIA_BUCKET_NAME=${MEDIA_BUCKET_NAME}"
echo "MEDIA_TABLE_NAME=${MEDIA_TABLE_NAME}"
echo

aws sts get-caller-identity \
  --profile "${AWS_PROFILE}" \
  --region "${AWS_REGION}" >/tmp/manual-e2e-v2-identity.json

echo "AWS identity:"
cat /tmp/manual-e2e-v2-identity.json
echo

run_media_case "image" "${IMAGE_FILE}" "images-v2"
run_media_case "video" "${VIDEO_FILE}" "videos-v2"

echo "All manual v2 E2E checks passed."
echo
echo "Useful log commands:"
cat <<EOF
aws logs tail /aws/lambda/media_ingest_v2 \\
  --region "${AWS_REGION}" \\
  --profile "${AWS_PROFILE}" \\
  --since 20m \\
  --format short

aws logs tail /aws/lambda/process_ml_result_v2 \\
  --region "${AWS_REGION}" \\
  --profile "${AWS_PROFILE}" \\
  --since 20m \\
  --format short

gcloud logging read \\
  "resource.type=cloud_run_revision AND resource.labels.service_name=\${GCP_SERVICE_NAME}" \\
  --project "\${GCP_PROJECT_ID}" \\
  --limit 120 \\
  --format="value(timestamp,severity,textPayload)"
EOF
