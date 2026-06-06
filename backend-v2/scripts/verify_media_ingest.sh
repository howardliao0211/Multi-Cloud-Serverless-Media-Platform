#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-backend-v2/.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

source backend-v2/scripts/load_env.sh "$ENV_FILE"

export AWS_PAGER="${AWS_PAGER:-}"
export GCP_PROJECT_ID="${GCP_PROJECT_ID:-hazel-sphinx-490908-u6}"
export GCP_REGION="${GCP_REGION:-us-east4}"
export SERVICE_NAME="${GCP_SERVICE_NAME:-aussie-eco-len-us-demo-ml-processor}"

TEST_FILE="tests/integration/test_media_flow_v2.py"
EVIDENCE_DIR="evidence"

echo "== Backend v2 media ingest verification =="
echo "ROOT_DIR=$ROOT_DIR"
echo "TEST_FILE=$TEST_FILE"
echo "GCP_PROJECT_ID=$GCP_PROJECT_ID"
echo "GCP_REGION=$GCP_REGION"
echo "SERVICE_NAME=$SERVICE_NAME"
echo

if [ ! -f "$TEST_FILE" ]; then
  echo "Missing test file: $TEST_FILE"
  exit 1
fi

echo "== Checking whether video test already exists =="
if grep -q "test_backend_v2_video_ingest_end_to_end" "$TEST_FILE"; then
  echo "Video integration test already exists. Skipping patch."
else
  echo "Adding video integration test to $TEST_FILE"

  cat >> "$TEST_FILE" <<'PY'

def test_backend_v2_video_ingest_end_to_end() -> None:
    test_video = Path("integration/test_video.mp4")
    assert test_video.exists(), f"Missing test video: {test_video}"

    run_id = uuid.uuid4().hex
    checksum = f"v2-video-it-{run_id}"
    file_name = f"{checksum}.mp4"
    key = f"videos-v2/{file_name}"

    try:
        s3.upload_file(
            Filename=str(test_video),
            Bucket=MEDIA_BUCKET_NAME,
            Key=key,
            ExtraArgs={
                "ContentType": "video/mp4",
                "Metadata": {
                    "owner_id": TEST_OWNER,
                    "checksum": checksum,
                    "file_name": file_name,
                },
            },
        )

        _put_pending_record(key=key, checksum=checksum, file_name=file_name)

        payload = _invoke_media_ingest(key)
        assert payload["statusCode"] == 200, payload

        record = _get_media_record(key)

        assert record["upload_status"] == "ready"
        assert record["file_type"] == "video/mp4"
        assert record["ml_provider"] == "gcp_cloud_run"
        assert record.get("thumbnail_key")
        assert record.get("thumbnail_url")
        assert record.get("tags")
        assert "error_message" not in record or record["error_message"] is None

        detections = record.get("ml_detections", [])
        assert isinstance(detections, list)

        if detections:
            assert any("timestamp_sec" in detection for detection in detections)
            assert all(detection.get("source") == "original" for detection in detections)

    finally:
        _cleanup_media_record(key)
        _delete_s3_object(key)
        _delete_s3_object(f"thumbnails/{Path(key).stem}.jpg")
PY
fi

echo
echo "== Running integration tests =="
mkdir -p "$EVIDENCE_DIR"

(
  cd tests
  uv run pytest -s integration/test_media_flow_v2.py
) | tee "$EVIDENCE_DIR/backend-v2-media-ingest-final.txt"

echo
echo "== Capturing Cloud Run evidence =="
gcloud run services describe "$SERVICE_NAME" \
  --project "$GCP_PROJECT_ID" \
  --region "$GCP_REGION" \
  --format="yaml(status.url,status.latestReadyRevisionName,status.traffic,spec.template.spec.containers[0].image,spec.template.spec.containers[0].env)" \
  > "$EVIDENCE_DIR/gcp-cloud-run-v2-final.yaml"

echo
echo "== Checking debug endpoint =="
GCP_ML_PROCESSOR_URL="$(gcloud run services describe "$SERVICE_NAME" \
  --project "$GCP_PROJECT_ID" \
  --region "$GCP_REGION" \
  --format='value(status.url)')"

curl -s \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${GCP_ML_PROCESSOR_URL}/debug-version" \
  | tee "$EVIDENCE_DIR/gcp-cloud-run-debug-version.json"

echo
echo

echo "== Git status =="
git status --short

echo
echo "Done."
echo "Evidence written to:"
echo "  $EVIDENCE_DIR/backend-v2-media-ingest-final.txt"
echo "  $EVIDENCE_DIR/gcp-cloud-run-v2-final.yaml"
echo "  $EVIDENCE_DIR/gcp-cloud-run-debug-version.json"
