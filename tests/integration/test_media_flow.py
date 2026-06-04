import hashlib
import json
import time
import urllib.request
import zlib
from pathlib import Path
from struct import pack

import pytest
from boto3.dynamodb.conditions import Key


pytestmark = pytest.mark.integration


def _png_chunk(chunk_type, data):
    return (
        pack(">I", len(data))
        + chunk_type
        + data
        + pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    )


def _solid_png_bytes(width=32, height=32):
    row = b"\x00" + (b"\x35\x8f\xcf" * width)
    raw = row * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )


def _checksum(data):
    return hashlib.sha256(data).hexdigest()


def _api_event(method, body=None, query_params=None, user_id="integration-test-user"):
    event = {
        "httpMethod": method,
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": user_id,
                    }
                }
            }
        },
    }

    if body is not None:
        event["body"] = json.dumps(body)

    if query_params is not None:
        event["queryStringParameters"] = query_params

    return event


def _s3_event(bucket, key):
    return {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": bucket},
                    "object": {"key": key},
                },
            }
        ]
    }


def _invoke_lambda(lambda_client, function_name, event):
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(event).encode("utf-8"),
    )

    payload = json.loads(response["Payload"].read().decode("utf-8"))

    if response.get("FunctionError"):
        pytest.fail(f"{function_name} failed: {payload}")

    return payload


def _body(handler_response):
    return json.loads(handler_response["body"])


def _get_media_record(table, key):
    response = table.get_item(
        Key={
            "key": key,
        },
        ConsistentRead=True,
    )
    return response.get("Item")



def _wait_for_media_status(
    table,
    key: str,
    expected_status: str = "ready",
    timeout_seconds: int = 60 * 5,
    poll_interval_seconds: float = 2.0,
):
    deadline = time.time() + timeout_seconds
    last_item = None
    last_status = None

    while time.time() < deadline:
        item = _get_media_record(table, key)
        last_item = item

        if item is not None:
            last_status = item.get("upload_status")

            if last_status == expected_status:
                return item

            if last_status == "failed":
                raise AssertionError(
                    f"Media processing failed for {key!r}: "
                    f"{item.get('error_message') or item}"
                )

        time.sleep(poll_interval_seconds)

    raise TimeoutError(
        f"Timed out waiting for media record {key!r} "
        f"to become {expected_status!r}. "
        f"Last status: {last_status!r}. "
        f"Last item: {last_item}"
    )

def _upload_to_presigned_url(upload_url, data, content_type, file_name, checksum, owner_id):
    request = urllib.request.Request(
        upload_url,
        data=data,
        method="PUT",
        headers={
            "Content-Type": content_type,
            "x-amz-meta-file_name": file_name,
            "x-amz-meta-checksum": checksum,
            "x-amz-meta-owner_id": owner_id,
        },
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        assert response.status == 200


def _build_db_key(owner_id, full_key):
    return f"OWNER#{owner_id}#KEY#{full_key}"


def _put_media_record(table, **overrides):
    item = {
        "key": "OWNER#integration-test-user#KEY#integration-tests/integration-test.png",
        "owner_id": "integration-test-user",
        "file_name": "integration-test.png",
        "checksum": "integration-test-checksum",
        "full_key": "integration-tests/integration-test.png",
        "visibility": "private",
        "full_url": "https://example.invalid/full",
        "file_type": "image/png",
        "thumbnail_key": "integration-tests/integration-test-thumb.jpg",
        "thumbnail_url": "https://example.invalid/thumb",
        "tags": {},
        "ml_detections": [],
        "upload_status": "pending",
        "error_message": None,
    }

    item.update(overrides)
    item["key"] = _build_db_key(item["owner_id"], item["full_key"])

    table.put_item(Item=item)
    return item


def _delete_media_record(table, item):
    """
    Delete one DynamoDB media record.

    ReturnValues='ALL_OLD' helps us detect whether the key actually matched
    an existing item. DynamoDB delete_item succeeds even when no item matches.
    """
    key = {
        "key": item["key"],
    }

    response = table.delete_item(
        Key=key,
        ReturnValues="ALL_OLD",
    )

    deleted_item = response.get("Attributes")

    if deleted_item is None:
        print(f"No DynamoDB item deleted. Key may not exist: {key}")
    else:
        print(f"Deleted DynamoDB item: {key}")

    return deleted_item


def _delete_s3_objects(s3, bucket, *keys):
    objects = [{"Key": key} for key in keys if key]

    if not objects:
        return

    response = s3.delete_objects(
        Bucket=bucket,
        Delete={
            "Objects": objects,
            "Quiet": False,
        },
    )

    deleted = response.get("Deleted", [])
    errors = response.get("Errors", [])

    print(f"Deleted S3 objects: {deleted}")

    if errors:
        raise RuntimeError(f"Failed to delete S3 objects: {errors}")


def _cleanup_media(table, s3, bucket, record=None, s3_keys=None):
    """
    Cleanup helper that tries DynamoDB and S3 independently.

    This prevents a DynamoDB cleanup failure from stopping S3 cleanup.
    """
    cleanup_errors = []

    try:
        _delete_media_record(table, record)
    except Exception as e:
        cleanup_errors.append(f"DynamoDB cleanup failed: {e}")

    try:
        _delete_s3_objects(s3, bucket, *(s3_keys or []))
    except Exception as e:
        cleanup_errors.append(f"S3 cleanup failed: {e}")

    if cleanup_errors:
        print("\n".join(cleanup_errors))


def test_tag_image(aws_clients, integration_config, unique_id):
    s3 = aws_clients["s3"]
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    bucket = integration_config["bucket"]

    image = _solid_png_bytes()
    checksum = "integration_test_" + _checksum(image)
    file_name = f"{unique_id}.png"

    # Fixed: do not add integration_test_ twice.
    full_key = f"images/{checksum}.png"

    # Include multiple likely thumbnail extensions for safer cleanup.
    thumbnail_keys = [
        f"thumbnails/{checksum}.png",
        f"thumbnails/{checksum}.jpg",
        f"thumbnails/{checksum}.jpeg",
    ]

    record = _put_media_record(
        table,
        owner_id=integration_config["test_user_id"],
        file_name=file_name,
        checksum=checksum,
        full_key=full_key,
        visibility="private",
        file_type="image/png",
    )

    try:
        s3.put_object(
            Bucket=bucket,
            Key=full_key,
            Body=image,
            ContentType="image/png",
            Metadata={
                "file_name": file_name,
                "checksum": checksum,
                "owner_id": integration_config["test_user_id"]
            },
        )

        # Do not invoke tag_image manually here.
        # The S3 bucket notification triggers tag_image for images/.
        # Manually invoking it as well creates duplicate concurrent processing
        # and can race with cleanup, causing intermittent S3 404s in Cloud Run.
        record = _wait_for_media_status(
            table,
            key=record["key"],
            expected_status="ready",
            timeout_seconds=60 * 5,
        )

        item = _get_media_record(table, record["key"])
        assert item is not None
        assert item["upload_status"] == "ready", item.get("error_message")
        assert item["file_type"] == "image/png"

    finally:
        _cleanup_media(
            table=table,
            s3=s3,
            bucket=bucket,
            record=record,
            s3_keys=[
                full_key,
                *thumbnail_keys,
            ],
        )


def test_tag_video(aws_clients, integration_config, unique_id):
    video_path = integration_config["test_video_path"]
    if not video_path:
        pytest.skip("Set AUSSIE_ECOLENS_TEST_VIDEO_PATH to test video tagging.")

    s3 = aws_clients["s3"]
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    bucket = integration_config["bucket"]

    video = Path(video_path).read_bytes()
    checksum = "integration_test_" + _checksum(video)
    file_name = f"{unique_id}.mp4"

    # Fixed: do not add integration_test_ twice.
    full_key = f"videos/{checksum}.mp4"

    # Video thumbnail is usually an image, not mp4.
    # Keep mp4 as a fallback cleanup key in case your backend uses it.
    thumbnail_keys = [
        f"thumbnails/{checksum}.jpg",
        f"thumbnails/{checksum}.jpeg",
        f"thumbnails/{checksum}.png",
        f"thumbnails/{checksum}.mp4",
    ]

    record = _put_media_record(
        table,
        owner_id=integration_config["test_user_id"],
        file_name=file_name,
        checksum=checksum,
        full_key=full_key,
        visibility="private",
        file_type="video/mp4",
    )

    try:
        s3.put_object(
            Bucket=bucket,
            Key=full_key,
            Body=video,
            ContentType="video/mp4",
            Metadata={
                "file_name": file_name,
                "checksum": checksum,
                "owner_id": integration_config["test_user_id"]
            },
        )

        _invoke_lambda(
            lambda_client,
            integration_config["tag_video_function"],
            _s3_event(bucket, full_key),
        )

        item = _get_media_record(table, record["key"])

        assert item is not None
        assert item["upload_status"] == "ready", item.get("error_message")
        assert item["file_type"] == "video/mp4"

    finally:
        _cleanup_media(
            table=table,
            s3=s3,
            bucket=bucket,
            record=record,
            s3_keys=[
                full_key,
                *thumbnail_keys,
            ],
        )


def test_deduplicate_media_in_s3(aws_clients, integration_config, unique_id):
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    user_id = integration_config["test_user_id"]

    checksum = f"{unique_id}-dedupe"
    file_name = f"{unique_id}.png"

    created_record = {
        "checksum": checksum,
        "file_name": file_name,
    }

    try:
        first = _invoke_lambda(
            lambda_client,
            integration_config["get_signed_url_function"],
            _api_event(
                "POST",
                {
                    "file_name": file_name,
                    "checksum": checksum,
                    "media_type": "image",
                    "visibility": "private",
                },
                user_id=user_id,
            ),
        )

        second = _invoke_lambda(
            lambda_client,
            integration_config["get_signed_url_function"],
            _api_event(
                "POST",
                {
                    "file_name": file_name,
                    "checksum": checksum,
                    "media_type": "image",
                    "visibility": "private",
                },
                user_id=user_id,
            ),
        )

        first_body = _body(first)
        second_body = _body(second)

        assert first["statusCode"] == 200
        assert first_body["duplicate"] is False
        assert first_body["upload_url"].startswith("https://")

        assert second["statusCode"] == 200
        assert second_body["duplicate"] is True
        assert second_body["upload_url"] is None

    finally:
        try:
            _delete_media_record(table, created_record)
        except Exception as e:
            print(f"DynamoDB cleanup failed: {e}")


def test_get_private_media(aws_clients, integration_config, unique_id):
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    user_id = integration_config["test_user_id"]

    record = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}.png",
        checksum=f"{unique_id}-private",
        full_key=f"integration-tests/{unique_id}.png",
        thumbnail_key=f"integration-tests/{unique_id}-thumb.jpg",
        visibility="private",
        tags={"koala": 1},
        upload_status="ready",
    )

    try:
        response = _invoke_lambda(
            lambda_client,
            integration_config["get_private_media_function"],
            _api_event("GET", user_id=user_id),
        )

        body = _body(response)
        records = body["media_records"]

        assert response["statusCode"] == 200
        assert any(item["file_name"] == record["file_name"]
                   for item in records)
        assert all(item["owner_id"] == user_id for item in records)

    finally:
        try:
            _delete_media_record(table, record)
        except Exception as e:
            print(f"DynamoDB cleanup failed: {e}")


def test_get_public_media(aws_clients, integration_config, unique_id):
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]

    record = _put_media_record(
        table,
        owner_id=integration_config["test_user_id"],
        file_name=f"{unique_id}.png",
        checksum=f"{unique_id}-public",
        full_key=f"integration-tests/{unique_id}.png",
        thumbnail_key=f"integration-tests/{unique_id}-thumb.jpg",
        visibility="public",
        tags={"wombat": 1},
        upload_status="ready",
    )

    try:
        response = _invoke_lambda(
            lambda_client,
            integration_config["get_public_media_function"],
            _api_event("GET"),
        )

        body = _body(response)
        records = body["media_records"]

        assert response["statusCode"] == 200
        assert any(item["file_name"] == record["file_name"]
                   for item in records)
        assert all(item["visibility"] == "public" for item in records)

    finally:
        try:
            _delete_media_record(table, record)
        except Exception as e:
            print(f"DynamoDB cleanup failed: {e}")


def test_get_upload_status(aws_clients, integration_config, unique_id):
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]

    record = _put_media_record(
        table,
        owner_id=integration_config["test_user_id"],
        file_name=f"{unique_id}.png",
        checksum=f"{unique_id}-public",
        full_key=f"integration-tests/{unique_id}.png",
        thumbnail_key=f"integration-tests/{unique_id}-thumb.jpg",
        visibility="public",
        tags={"wombat": 1},
        upload_status="ready",
        error_message="fake error message"
    )

    try:
        response = _invoke_lambda(
            lambda_client,
            integration_config["get_upload_status_function"],
            _api_event(
                "GET",
                query_params={
                    "file_name": f"{unique_id}.png",
                    "checksum": f"{unique_id}-public",
                },
                user_id=integration_config["test_user_id"],
            ),
        )

        body = _body(response)
        status = body["upload_status"]
        error_message = body["error_message"]

        assert response["statusCode"] == 200
        assert status == "ready"
        assert error_message == "fake error message"

    finally:
        try:
            _delete_media_record(table, record)
        except Exception as e:
            print(f"DynamoDB cleanup failed: {e}")


def test_change_visibility_to_private(aws_clients, integration_config, unique_id):
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]

    record = _put_media_record(
        table,
        owner_id=integration_config["test_user_id"],
        file_name=f"{unique_id}.png",
        checksum=f"{unique_id}-public",
        full_key=f"integration-tests/{unique_id}.png",
        thumbnail_key=f"integration-tests/{unique_id}-thumb.jpg",
        visibility="public",
        tags={"wombat": 1},
        upload_status="ready",
        error_message="fake error message"
    )

    try:
        response = _invoke_lambda(
            lambda_client,
            "change_visibility",
            _api_event(
                "PATCH",
                body={
                    "file_name": f"{unique_id}.png",
                    "checksum": f"{unique_id}-public",
                    "visibility": "private",
                },
                user_id=integration_config["test_user_id"],
            ),
        )

        body = _body(response)
        message = body["message"]

        assert response["statusCode"] == 200
        assert message == f"Visibility updated to private"

        updated_record = _get_media_record(
            table, record["key"]
        )

        assert updated_record["visibility"] == "private"

    finally:
        try:
            _delete_media_record(table, record)
        except Exception as e:
            print(f"DynamoDB cleanup failed: {e}")


def test_change_visibility_to_public(aws_clients, integration_config, unique_id):
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]

    record = _put_media_record(
        table,
        owner_id=integration_config["test_user_id"],
        file_name=f"{unique_id}.png",
        checksum=f"{unique_id}-private",
        full_key=f"integration-tests/{unique_id}.png",
        thumbnail_key=f"integration-tests/{unique_id}-thumb.jpg",
        visibility="private",
        tags={"wombat": 1},
        upload_status="ready",
        error_message="fake error message"
    )

    try:
        response = _invoke_lambda(
            lambda_client,
            "change_visibility",
            _api_event(
                "PATCH",
                body={
                    "file_name": f"{unique_id}.png",
                    "checksum": f"{unique_id}-private",
                    "visibility": "public",
                },
                user_id=integration_config["test_user_id"],
            ),
        )

        body = _body(response)
        message = body["message"]

        assert response["statusCode"] == 200
        assert message == f"Visibility updated to public"

        updated_record = _get_media_record(
            table, record["key"]
        )

        assert updated_record["visibility"] == "public"

    finally:
        try:
            _delete_media_record(table, updated_record)
        except Exception as e:
            print(f"DynamoDB cleanup failed: {e}")
