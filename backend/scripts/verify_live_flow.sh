#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${BACKEND_DIR}/.." && pwd)"

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load_env.sh" "${BACKEND_DIR}/.env"

export AWS_PAGER=""

OWNER_ID="${OWNER_ID:-verify-live-flow-user}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%d%H%M%S)}"
IMAGE_FILE="${IMAGE_FILE:-${REPO_ROOT}/tests/fixtures/media/Perameles_nasuta_1.JPG}"
VIDEO_FILE="${VIDEO_FILE:-${REPO_ROOT}/tests/fixtures/media/5214219-hd_1920_1080_25fps.mp4}"
OUT_DIR="${OUT_DIR:-${REPO_ROOT}/.verify-live-flow/${RUN_ID}}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-5}"
IMAGE_TIMEOUT_SECONDS="${IMAGE_TIMEOUT_SECONDS:-300}"
VIDEO_TIMEOUT_SECONDS="${VIDEO_TIMEOUT_SECONDS:-900}"
DO_CLEANUP="${DO_CLEANUP:-false}"

if [[ "${1:-}" == "--cleanup" ]]; then
  DO_CLEANUP="true"
fi

mkdir -p "${OUT_DIR}"

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

sha256_file() {
  shasum -a 256 "$1" | awk '{print $1}'
}

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"
}

now_ms() {
  python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
}

get_ddb_item() {
  local key_raw="$1"
  local out="$2"
  aws dynamodb get-item \
    --table-name "${MEDIA_TABLE_NAME}" \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" \
    --key "{\"key\":{\"S\":$(json_escape "${key_raw}")}}" \
    --output json > "${out}"
}

extract_ddb_summary() {
  local item_file="$1"
  python3 - "$item_file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    text = path.read_text()
    data = json.loads(text) if text.strip() else {}
except Exception as exc:
    print(f"invalid_json={exc}")
    raise SystemExit(0)

item = data.get("Item") or {}
if not item:
    print("item_missing=true")
    raise SystemExit(0)

def s(name):
    return (item.get(name) or {}).get("S")

def tags():
    raw = (item.get("tags") or {}).get("M") or {}
    out = {}
    for k, v in raw.items():
        if "N" in v:
            out[k] = v["N"]
        elif "S" in v:
            out[k] = v["S"]
    return out

print("upload_status=" + str(s("upload_status")))
print("ml_provider=" + str(s("ml_provider")))
print("ml_model_name=" + str(s("ml_model_name")))
print("ml_model_version=" + str(s("ml_model_version")))
print("file_type=" + str(s("file_type")))
print("thumbnail_key=" + str(s("thumbnail_key")))
print("tags=" + json.dumps(tags(), sort_keys=True))
PY
}

wait_for_ready() {
  local ddb_key="$1"
  local timeout_seconds="$2"
  local item_file="$3"

  local start_ms
  start_ms="$(now_ms)"

  while true; do
    get_ddb_item "${ddb_key}" "${item_file}" || true

    if python3 - "$item_file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    text = path.read_text()
    data = json.loads(text) if text.strip() else {}
except Exception:
    raise SystemExit(1)

item = data.get("Item")
if not item:
    raise SystemExit(1)

status = (item.get("upload_status") or {}).get("S")
tags = (item.get("tags") or {}).get("M") or {}

if status == "ready" and tags:
    raise SystemExit(0)
if status == "failed":
    raise SystemExit(2)
raise SystemExit(1)
PY
    then
      return 0
    else
      rc=$?
      if [[ "${rc}" == "2" ]]; then
        return 2
      fi
    fi

    local elapsed_ms elapsed_s
    elapsed_ms=$(( $(now_ms) - start_ms ))
    elapsed_s=$(( elapsed_ms / 1000 ))

    if (( elapsed_s >= timeout_seconds )); then
      return 1
    fi

    sleep "${POLL_INTERVAL_SECONDS}"
  done
}

check_lambda_config() {
  local fn="$1"
  local out="${OUT_DIR}/lambda-${fn}.json"

  if aws lambda get-function-configuration \
      --function-name "${fn}" \
      --region "${AWS_REGION}" \
      --profile "${AWS_PROFILE}" \
      --output json > "${out}" 2>/dev/null
  then
    python3 - "$out" "$fn" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
fn = sys.argv[2]
data = json.loads(path.read_text())
env = data.get("Environment", {}).get("Variables", {}) or {}
print(f"{fn}: package={data.get('PackageType')} timeout={data.get('Timeout')} memory={data.get('MemorySize')} last_update={data.get('LastUpdateStatus')}")
print(f"{fn}: env_keys={','.join(sorted(env.keys()))}")
PY
  else
    echo "${fn}: not found or not accessible"
  fi
}

run_production_prefix_case() {
  local media_type="$1"
  local local_file="$2"
  local prefix="$3"
  local timeout="$4"

  local file_name checksum s3_key ddb_key item_file start_ms duration_s
  file_name="$(basename "${local_file}")"
  checksum="$(sha256_file "${local_file}")"
  s3_key="${prefix}/verify-live-${media_type}-${RUN_ID}-${file_name}"
  ddb_key="OWNER#${OWNER_ID}#KEY#${s3_key}"
  item_file="${OUT_DIR}/${media_type}.ddb.json"

  echo
  echo "== ${media_type} production-prefix test =="
  echo "local_file=${local_file}"
  echo "s3_key=${s3_key}"
  echo "ddb_key=${ddb_key}"

  start_ms="$(now_ms)"

  aws s3 cp "${local_file}" "s3://${MEDIA_BUCKET_NAME}/${s3_key}" \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" \
    --metadata "owner_id=${OWNER_ID},checksum=${checksum},file_name=${file_name},visibility=private"

  if wait_for_ready "${ddb_key}" "${timeout}" "${item_file}"; then
    duration_s="$(python3 - <<PY
print(round(($(now_ms) - ${start_ms}) / 1000, 3))
PY
)"
    echo "${media_type}: PASS duration_seconds=${duration_s}"
    extract_ddb_summary "${item_file}"
  else
    rc=$?
    duration_s="$(python3 - <<PY
print(round(($(now_ms) - ${start_ms}) / 1000, 3))
PY
)"
    echo "${media_type}: FAIL duration_seconds=${duration_s} rc=${rc}"
    extract_ddb_summary "${item_file}"
    echo "DDB raw file: ${item_file}"
    return 1
  fi

  if [[ "${DO_CLEANUP}" == "true" ]]; then
    local thumbnail_key
    thumbnail_key="$(python3 - "$item_file" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text())
print(((data.get("Item") or {}).get("thumbnail_key") or {}).get("S") or "")
PY
)"
    aws s3 rm "s3://${MEDIA_BUCKET_NAME}/${s3_key}" \
      --region "${AWS_REGION}" \
      --profile "${AWS_PROFILE}" >/dev/null 2>&1 || true

    if [[ -n "${thumbnail_key}" ]]; then
      aws s3 rm "s3://${MEDIA_BUCKET_NAME}/${thumbnail_key}" \
        --region "${AWS_REGION}" \
        --profile "${AWS_PROFILE}" >/dev/null 2>&1 || true
    fi

    aws dynamodb delete-item \
      --table-name "${MEDIA_TABLE_NAME}" \
      --region "${AWS_REGION}" \
      --profile "${AWS_PROFILE}" \
      --key "{\"key\":{\"S\":$(json_escape "${ddb_key}")}}" >/dev/null 2>&1 || true
  fi
}

echo "== Verify live production flow =="
echo "RUN_ID=${RUN_ID}"
echo "OWNER_ID=${OWNER_ID}"
echo "OUT_DIR=${OUT_DIR}"
echo "MEDIA_BUCKET_NAME=${MEDIA_BUCKET_NAME}"
echo "MEDIA_TABLE_NAME=${MEDIA_TABLE_NAME}"
echo

echo "== AWS caller identity =="
aws sts get-caller-identity \
  --profile "${AWS_PROFILE}" \
  --region "${AWS_REGION}" \
  --output json | tee "${OUT_DIR}/aws-identity.json"

echo
echo "== S3 bucket notifications =="
aws s3api get-bucket-notification-configuration \
  --bucket "${MEDIA_BUCKET_NAME}" \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}" \
  --output json | tee "${OUT_DIR}/bucket-notifications.json"

echo
echo "== Notification routing summary =="
python3 - "${OUT_DIR}/bucket-notifications.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
configs = data.get("LambdaFunctionConfigurations", []) or []

for c in configs:
    arn = c.get("LambdaFunctionArn", "")
    events = ",".join(c.get("Events", []))
    rules = c.get("Filter", {}).get("Key", {}).get("FilterRules", []) or []
    filters = ",".join(f"{r.get('Name')}={r.get('Value')}" for r in rules)
    print(f"lambda={arn} events={events} filters={filters}")

if not configs:
    print("No LambdaFunctionConfigurations found")
PY

echo
echo "== Lambda configs =="
for fn in \
  tag_image \
  tag_video \
  media_ingest_v2 \
  process_ml_result_v2 \
  get_signed_url \
  get_upload_status \
  query_tags \
  query_species \
  query_file
do
  check_lambda_config "${fn}"
done

echo
echo "== API upload URL behavior check =="
if [[ -n "${API_BASE_URL:-}" ]]; then
  echo "API_BASE_URL=${API_BASE_URL}"
  echo "Skipping authenticated API call by default because Cognito token may be required."
  echo "Set AUTH_TOKEN and re-run if you want API /get_signed_url checked."
  if [[ -n "${AUTH_TOKEN:-}" ]]; then
    curl -sS -X POST "${API_BASE_URL%/}/get_signed_url" \
      -H "Authorization: Bearer ${AUTH_TOKEN}" \
      -H "Content-Type: application/json" \
      -d '{"file_name":"verify-live.jpg","file_type":"image/jpeg","visibility":"private"}' \
      | tee "${OUT_DIR}/get-signed-url-response.json"
  fi
else
  echo "API_BASE_URL not set; skipping API Gateway endpoint call."
fi

if [[ ! -f "${IMAGE_FILE}" ]]; then
  echo "Missing image file: ${IMAGE_FILE}" >&2
  exit 1
fi

if [[ ! -f "${VIDEO_FILE}" ]]; then
  echo "Missing video file: ${VIDEO_FILE}" >&2
  exit 1
fi

# Current production prefixes. If v1 was replaced, these should now route to new flow.
run_production_prefix_case "image" "${IMAGE_FILE}" "images" "${IMAGE_TIMEOUT_SECONDS}"
run_production_prefix_case "video" "${VIDEO_FILE}" "videos" "${VIDEO_TIMEOUT_SECONDS}"

echo
echo "== Recent log commands =="
cat <<EOF
aws logs tail /aws/lambda/tag_image --region "${AWS_REGION}" --profile "${AWS_PROFILE}" --since 30m --format short
aws logs tail /aws/lambda/tag_video --region "${AWS_REGION}" --profile "${AWS_PROFILE}" --since 30m --format short
aws logs tail /aws/lambda/media_ingest_v2 --region "${AWS_REGION}" --profile "${AWS_PROFILE}" --since 30m --format short
aws logs tail /aws/lambda/process_ml_result_v2 --region "${AWS_REGION}" --profile "${AWS_PROFILE}" --since 30m --format short
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=\${GCP_SERVICE_NAME}" --project "\${GCP_PROJECT_ID}" --limit 80 --format="value(timestamp,severity,textPayload)"
EOF

echo
echo "Verification completed. Artifacts in ${OUT_DIR}"
