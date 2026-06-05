from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import boto3


AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_PROFILE = os.environ.get("AWS_PROFILE", "AussieEcoLense")

MEDIA_BUCKET_NAME = os.environ.get("MEDIA_BUCKET_NAME", "aussie-eco-len-bucket-12345")
MEDIA_TABLE_NAME = os.environ.get("MEDIA_TABLE_NAME", "aussie-eco-len-media")

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_IMAGE = Path(
    os.environ.get(
        "TEST_IMAGE",
        str(REPO_ROOT / "test_media" / "Perameles_nasuta_1.JPG"),
    )
)

MEDIA_INGEST_FUNCTION_NAME = os.environ.get(
    "MEDIA_INGEST_FUNCTION_NAME",
    "media_ingest_v2",
)

TEST_OWNER = os.environ.get("TEST_OWNER", "integration-test-user")

SESSION = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
s3 = SESSION.client("s3")
dynamodb = SESSION.client("dynamodb")
lambda_client = SESSION.client("lambda")


def _db_key(owner_id: str, key: str) -> str:
    return f"OWNER#{owner_id}#KEY#{key}"


def _delete_test_artifacts(key: str, checksum: str) -> None:
    db_key = _db_key(TEST_OWNER, key)

    dynamodb.delete_item(
        TableName=MEDIA_TABLE_NAME,
        Key={"key": {"S": db_key}},
    )

    possible_thumbnail_keys = [
        f"thumbnails/{checksum}.jpg",
        f"thumbnails/{checksum}.jpeg",
        f"thumbnails/{checksum}.png",
    ]

    delete_objects = [{"Key": key}]
    delete_objects.extend({"Key": item} for item in possible_thumbnail_keys)

    s3.delete_objects(
        Bucket=MEDIA_BUCKET_NAME,
        Delete={"Objects": delete_objects, "Quiet": True},
    )


def _get_record(key: str) -> dict:
    response = dynamodb.get_item(
        TableName=MEDIA_TABLE_NAME,
        Key={"key": {"S": _db_key(TEST_OWNER, key)}},
    )
    return response.get("Item", {})


def _put_pending_record(key: str, checksum: str, file_name: str) -> None:
    dynamodb.put_item(
        TableName=MEDIA_TABLE_NAME,
        Item={
            "key": {"S": _db_key(TEST_OWNER, key)},
            "owner_id": {"S": TEST_OWNER},
            "file_name": {"S": file_name},
            "checksum": {"S": checksum},
            "full_key": {"S": key},
            "full_url": {"S": f"https://{MEDIA_BUCKET_NAME}.s3.amazonaws.com/{key}"},
            "visibility": {"S": "private"},
            "upload_status": {"S": "processing"},
        },
    )


def _invoke_media_ingest(key: str) -> dict:
    event = {
        "Records": [
            {
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": MEDIA_BUCKET_NAME},
                    "object": {"key": key},
                },
            }
        ]
    }

    response = lambda_client.invoke(
        FunctionName=MEDIA_INGEST_FUNCTION_NAME,
        Payload=json.dumps(event).encode("utf-8"),
    )

    payload = json.loads(response["Payload"].read().decode("utf-8"))
    assert response["StatusCode"] == 200
    assert payload["statusCode"] == 200, payload
    return payload


def test_backend_v2_image_ingest_end_to_end() -> None:
    assert TEST_IMAGE.exists(), f"Missing test image: {TEST_IMAGE}"

    run_id = uuid.uuid4().hex
    checksum = f"v2-it-{run_id}"
    file_name = f"{checksum}.jpg"
    key = f"images-v2/{file_name}"

    try:
        s3.upload_file(
            Filename=str(TEST_IMAGE),
            Bucket=MEDIA_BUCKET_NAME,
            Key=key,
            ExtraArgs={
                "ContentType": "image/jpeg",
                "Metadata": {
                    "owner_id": TEST_OWNER,
                    "checksum": checksum,
                    "file_name": file_name,
                },
            },
        )

        _put_pending_record(key=key, checksum=checksum, file_name=file_name)

        payload = _invoke_media_ingest(key)
        assert payload["statusCode"] == 200

        # DynamoDB update is synchronous because media_ingest_v2 invokes
        # process_ml_result_v2 and waits for the response, but allow a small
        # delay for eventual read consistency around test infrastructure.
        record = {}
        for _ in range(10):
            record = _get_record(key)
            if record.get("upload_status", {}).get("S") == "ready":
                break
            time.sleep(1)

        assert record["upload_status"]["S"] == "ready", record
        assert record["ml_provider"]["S"] == "gcp_cloud_run", record
        assert record["ml_model_name"]["S"] == "gcp_image_tagger", record
        assert "thumbnail_key" in record, record
        assert "thumbnail_url" in record, record

        tags = record.get("tags", {}).get("M", {})
        assert tags, record
        assert any(value.get("N") == "1" for value in tags.values()), record

    finally:
        _delete_test_artifacts(key=key, checksum=checksum)
