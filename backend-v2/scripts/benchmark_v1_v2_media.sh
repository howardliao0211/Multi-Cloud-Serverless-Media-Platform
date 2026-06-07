#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_V2_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${BACKEND_V2_DIR}/.." && pwd)"

# shellcheck source=/dev/null
source "${SCRIPT_DIR}/load_env.sh" "${BACKEND_V2_DIR}/.env"

export AWS_PAGER=""

OWNER_ID="${OWNER_ID:-benchmark-user}"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%d%H%M%S)}"
IMAGE_DIR="${IMAGE_DIR:-${REPO_ROOT}/tests/fixtures/media}"
VIDEO_FILE="${VIDEO_FILE:-${REPO_ROOT}/tests/integration/test_video.mp4}"
OUT_DIR="${OUT_DIR:-${REPO_ROOT}/.benchmark/v1-v2-${RUN_ID}}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-5}"
IMAGE_TIMEOUT_SECONDS="${IMAGE_TIMEOUT_SECONDS:-240}"
VIDEO_TIMEOUT_SECONDS="${VIDEO_TIMEOUT_SECONDS:-900}"
DO_CLEANUP="false"
MEDIA_LIMIT="${MEDIA_LIMIT:-}"

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

mkdir -p "${OUT_DIR}"

CSV_PATH="${OUT_DIR}/benchmark.csv"
JSONL_PATH="${OUT_DIR}/benchmark.jsonl"
SUMMARY_PATH="${OUT_DIR}/summary.txt"

echo "pipeline,media_type,file,s3_key,ddb_key,status,provider,tags_json,thumbnail_key,duration_seconds,error" > "${CSV_PATH}"
: > "${JSONL_PATH}"

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"
}

sha256_file() {
  shasum -a 256 "$1" | awk '{print $1}'
}

now_ms() {
  python3 - <<'PY'
import time
print(int(time.time() * 1000))
PY
}

ddb_get_item_to_file() {
  local ddb_key_raw="$1"
  local out_file="$2"
  local ddb_key_json
  ddb_key_json="$(json_escape "${ddb_key_raw}")"

  aws dynamodb get-item \
    --table-name "${MEDIA_TABLE_NAME}" \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" \
    --key "{\"key\":{\"S\":${ddb_key_json}}}" \
    --output json > "${out_file}"
}

parse_ddb_field() {
  local item_file="$1"
  local field="$2"
  python3 - "$item_file" "$field" <<'PYHELPER'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
field = sys.argv[2]

try:
    text = path.read_text()
    data = json.loads(text) if text.strip() else {}
except Exception:
    print("")
    raise SystemExit(0)

item = data.get("Item") or {}
v = item.get(field) or {}
print(v.get("S") or "")
PYHELPER
}

parse_ddb_tags_json() {
  local item_file="$1"
  python3 - "$item_file" <<'PYHELPER'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])

try:
    text = path.read_text()
    data = json.loads(text) if text.strip() else {}
except Exception:
    print("{}")
    raise SystemExit(0)

item = data.get("Item") or {}
raw = item.get("tags", {}).get("M", {})
tags = {}

for k, v in raw.items():
    if "N" in v:
        try:
            tags[k] = int(v["N"])
        except ValueError:
            tags[k] = v["N"]
    elif "S" in v:
        tags[k] = v["S"]

print(json.dumps(tags, sort_keys=True))
PYHELPER
}

csv_quote() {
  python3 -c 'import csv,sys; w=csv.writer(sys.stdout); w.writerow(sys.argv[1:])' "$@"
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

invoke_v2_lambda() {
  local event_path="$1"
  local response_path="$2"

  aws lambda invoke \
    --function-name media_ingest_v2 \
    --region "${AWS_REGION}" \
    --profile "${AWS_PROFILE}" \
    --payload "fileb://${event_path}" \
    "${response_path}" >/dev/null

  python3 - <<PY
import json
from pathlib import Path
outer = json.loads(Path("${response_path}").read_text())
if outer.get("statusCode") != 200:
    raise SystemExit(f"media_ingest_v2 statusCode={outer.get('statusCode')}: {outer}")
body = json.loads(outer.get("body") or "{}")
result = body.get("result", {})
if result.get("statusCode") != 200:
    raise SystemExit(f"process_ml_result_v2 statusCode={result.get('statusCode')}: {result}")
PY
}

wait_for_ready() {
  local ddb_key="$1"
  local timeout_seconds="$2"
  local item_file="$3"

  local start
  start="$(now_ms)"

  while true; do
    ddb_get_item_to_file "${ddb_key}" "${item_file}"

    if python3 - <<PY
import json
from pathlib import Path
data = json.loads(Path("${item_file}").read_text())
item = data.get("Item")
if not item:
    raise SystemExit(1)
status = item.get("upload_status", {}).get("S")
if status == "ready":
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

    local now elapsed
    now="$(now_ms)"
    elapsed=$(( (now - start) / 1000 ))
    if (( elapsed >= timeout_seconds )); then
      return 1
    fi

    sleep "${POLL_INTERVAL_SECONDS}"
  done
}

cleanup_artifacts() {
  local s3_key="$1"
  local ddb_key="$2"
  local item_file="$3"

  local thumbnail_key=""
  if [[ -f "${item_file}" ]]; then
    thumbnail_key="$(parse_ddb_field "${item_file}" "thumbnail_key" || true)"
  fi

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
}

record_result() {
  local pipeline="$1"
  local media_type="$2"
  local file="$3"
  local s3_key="$4"
  local ddb_key="$5"
  local status="$6"
  local provider="$7"
  local tags_json="$8"
  local thumbnail_key="$9"
  local duration_seconds="${10}"
  local error="${11}"

  csv_quote \
    "${pipeline}" \
    "${media_type}" \
    "${file}" \
    "${s3_key}" \
    "${ddb_key}" \
    "${status}" \
    "${provider}" \
    "${tags_json}" \
    "${thumbnail_key}" \
    "${duration_seconds}" \
    "${error}" >> "${CSV_PATH}"

  python3 - "$pipeline" "$media_type" "$file" "$s3_key" "$ddb_key" "$status" "$provider" "$tags_json" "$thumbnail_key" "$duration_seconds" "$error" <<'PYJSON' >> "${JSONL_PATH}"
import json
import sys

(
    pipeline,
    media_type,
    file,
    s3_key,
    ddb_key,
    status,
    provider,
    tags_json,
    thumbnail_key,
    duration_seconds,
    error,
) = sys.argv[1:]

try:
    tags = json.loads(tags_json) if tags_json else {}
except json.JSONDecodeError:
    tags = {"_parse_error": tags_json}

row = {
    "pipeline": pipeline,
    "media_type": media_type,
    "file": file,
    "s3_key": s3_key,
    "ddb_key": ddb_key,
    "status": status,
    "provider": provider,
    "tags": tags,
    "thumbnail_key": thumbnail_key,
    "duration_seconds": float(duration_seconds) if duration_seconds else None,
    "error": error,
}

print(json.dumps(row, sort_keys=True))
PYJSON
}

run_case() {
  local pipeline="$1"
  local media_type="$2"
  local local_file="$3"

  local file_name checksum prefix s3_key ddb_key timeout item_file start_ms end_ms duration status provider tags_json thumbnail_key error event_path response_path

  file_name="$(basename "${local_file}")"
  checksum="$(sha256_file "${local_file}")"

  if [[ "${pipeline}" == "v1" && "${media_type}" == "image" ]]; then
    prefix="images"
  elif [[ "${pipeline}" == "v1" && "${media_type}" == "video" ]]; then
    prefix="videos"
  elif [[ "${pipeline}" == "v2" && "${media_type}" == "image" ]]; then
    prefix="images-v2"
  elif [[ "${pipeline}" == "v2" && "${media_type}" == "video" ]]; then
    prefix="videos-v2"
  else
    echo "Invalid case: ${pipeline} ${media_type}" >&2
    exit 1
  fi

  s3_key="${prefix}/benchmark-${pipeline}-${media_type}-${RUN_ID}-${file_name}"
  ddb_key="OWNER#${OWNER_ID}#KEY#${s3_key}"
  item_file="${OUT_DIR}/${pipeline}-${media_type}-${file_name}.ddb.json"
  event_path="${OUT_DIR}/${pipeline}-${media_type}-${file_name}.event.json"
  response_path="${OUT_DIR}/${pipeline}-${media_type}-${file_name}.lambda-response.json"

  if [[ "${media_type}" == "video" ]]; then
    timeout="${VIDEO_TIMEOUT_SECONDS}"
  else
    timeout="${IMAGE_TIMEOUT_SECONDS}"
  fi

  echo "== ${pipeline} ${media_type}: ${file_name} =="

  start_ms="$(now_ms)"
  error=""

  if ! aws s3 cp "${local_file}" "s3://${MEDIA_BUCKET_NAME}/${s3_key}" \
      --region "${AWS_REGION}" \
      --profile "${AWS_PROFILE}" \
      --metadata "owner_id=${OWNER_ID},checksum=${checksum},file_name=${file_name},visibility=private" >/dev/null
  then
    end_ms="$(now_ms)"
    duration="$(python3 - <<PY
print(round((${end_ms} - ${start_ms}) / 1000, 3))
PY
)"
    record_result "${pipeline}" "${media_type}" "${local_file}" "${s3_key}" "${ddb_key}" "upload_failed" "" "{}" "" "${duration}" "s3 upload failed"
    return 1
  fi

  if [[ "${pipeline}" == "v2" ]]; then
    create_s3_event "${MEDIA_BUCKET_NAME}" "${s3_key}" "${event_path}"
    if ! invoke_v2_lambda "${event_path}" "${response_path}"; then
      end_ms="$(now_ms)"
      duration="$(python3 - <<PY
print(round((${end_ms} - ${start_ms}) / 1000, 3))
PY
)"
      record_result "${pipeline}" "${media_type}" "${local_file}" "${s3_key}" "${ddb_key}" "lambda_failed" "" "{}" "" "${duration}" "v2 lambda invoke failed"
      return 1
    fi
  fi

  if wait_for_ready "${ddb_key}" "${timeout}" "${item_file}"; then
    end_ms="$(now_ms)"
    duration="$(python3 - <<PY
print(round((${end_ms} - ${start_ms}) / 1000, 3))
PY
)"
    status="$(parse_ddb_field "${item_file}" "upload_status")"
    provider="$(parse_ddb_field "${item_file}" "ml_provider")"
    tags_json="$(parse_ddb_tags_json "${item_file}")"
    thumbnail_key="$(parse_ddb_field "${item_file}" "thumbnail_key")"

    record_result "${pipeline}" "${media_type}" "${local_file}" "${s3_key}" "${ddb_key}" "${status}" "${provider}" "${tags_json}" "${thumbnail_key}" "${duration}" ""

    echo "PASS ${pipeline} ${media_type} ${file_name}: ${duration}s tags=${tags_json}"
  else
    rc=$?
    end_ms="$(now_ms)"
    duration="$(python3 - <<PY
print(round((${end_ms} - ${start_ms}) / 1000, 3))
PY
)"
    status="$(parse_ddb_field "${item_file}" "upload_status" || true)"
    provider="$(parse_ddb_field "${item_file}" "ml_provider" || true)"
    tags_json="$(parse_ddb_tags_json "${item_file}" || echo '{}')"
    thumbnail_key="$(parse_ddb_field "${item_file}" "thumbnail_key" || true)"
    if [[ "${rc}" == "2" ]]; then
      error="DynamoDB upload_status=failed"
    else
      error="timeout waiting for ready"
    fi

    record_result "${pipeline}" "${media_type}" "${local_file}" "${s3_key}" "${ddb_key}" "${status:-not_ready}" "${provider}" "${tags_json}" "${thumbnail_key}" "${duration}" "${error}"
    echo "FAIL ${pipeline} ${media_type} ${file_name}: ${error}" >&2
  fi

  if [[ "${DO_CLEANUP}" == "true" ]]; then
    cleanup_artifacts "${s3_key}" "${ddb_key}" "${item_file}"
  fi
}

echo "== Benchmark v1 vs v2 media pipelines =="
echo "RUN_ID=${RUN_ID}"
echo "OWNER_ID=${OWNER_ID}"
echo "OUT_DIR=${OUT_DIR}"
echo "IMAGE_DIR=${IMAGE_DIR}"
echo "VIDEO_FILE=${VIDEO_FILE}"
echo "cleanup=${DO_CLEANUP}"
echo

aws sts get-caller-identity \
  --profile "${AWS_PROFILE}" \
  --region "${AWS_REGION}" > "${OUT_DIR}/aws-identity.json"

echo "Checking S3 notifications..."
aws s3api get-bucket-notification-configuration \
  --bucket "${MEDIA_BUCKET_NAME}" \
  --region "${AWS_REGION}" \
  --profile "${AWS_PROFILE}" \
  --output json > "${OUT_DIR}/bucket-notifications.json"

find "${IMAGE_DIR}" -maxdepth 1 -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) | sort > "${OUT_DIR}/images.txt"

if [[ -n "${MEDIA_LIMIT}" ]]; then
  head -n "${MEDIA_LIMIT}" "${OUT_DIR}/images.txt" > "${OUT_DIR}/images.limited.txt"
  mv "${OUT_DIR}/images.limited.txt" "${OUT_DIR}/images.txt"
fi

if [[ ! -s "${OUT_DIR}/images.txt" ]]; then
  echo "No images found in ${IMAGE_DIR}" >&2
  exit 1
fi

if [[ ! -f "${VIDEO_FILE}" ]]; then
  echo "Missing video file: ${VIDEO_FILE}" >&2
  exit 1
fi

while IFS= read -r image_file; do
  run_case "v1" "image" "${image_file}"
  run_case "v2" "image" "${image_file}"
done < "${OUT_DIR}/images.txt"

run_case "v1" "video" "${VIDEO_FILE}"
run_case "v2" "video" "${VIDEO_FILE}"

python3 - <<PY > "${SUMMARY_PATH}"
import csv
import statistics
from collections import defaultdict
from pathlib import Path

csv_path = Path("${CSV_PATH}")
rows = list(csv.DictReader(csv_path.open()))

groups = defaultdict(list)
failures = []

for row in rows:
    key = (row["pipeline"], row["media_type"])
    if row["status"] == "ready" and not row["error"]:
        groups[key].append(float(row["duration_seconds"]))
    else:
        failures.append(row)

print("Benchmark summary")
print("=================")
print(f"CSV: {csv_path}")
print(f"JSONL: ${JSONL_PATH}")
print()

for key in sorted(groups):
    values = groups[key]
    print(f"{key[0]} {key[1]}:")
    print(f"  count: {len(values)}")
    print(f"  avg_seconds: {statistics.mean(values):.3f}")
    print(f"  median_seconds: {statistics.median(values):.3f}")
    print(f"  min_seconds: {min(values):.3f}")
    print(f"  max_seconds: {max(values):.3f}")
    print()

if failures:
    print("Failures:")
    for row in failures:
        print(f"  {row['pipeline']} {row['media_type']} {row['file']}: {row['error']} status={row['status']}")
else:
    print("Failures: none")
PY

cat "${SUMMARY_PATH}"

echo
echo "Wrote:"
echo "  ${CSV_PATH}"
echo "  ${JSONL_PATH}"
echo "  ${SUMMARY_PATH}"

echo
echo "Useful log commands:"
cat <<EOF
aws logs tail /aws/lambda/tag_image --region "${AWS_REGION}" --profile "${AWS_PROFILE}" --since 60m --format short
aws logs tail /aws/lambda/tag_video --region "${AWS_REGION}" --profile "${AWS_PROFILE}" --since 60m --format short
aws logs tail /aws/lambda/media_ingest_v2 --region "${AWS_REGION}" --profile "${AWS_PROFILE}" --since 60m --format short
aws logs tail /aws/lambda/process_ml_result_v2 --region "${AWS_REGION}" --profile "${AWS_PROFILE}" --since 60m --format short
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=\${GCP_SERVICE_NAME}" --project "\${GCP_PROJECT_ID}" --limit 120 --format="value(timestamp,severity,textPayload)"
EOF
