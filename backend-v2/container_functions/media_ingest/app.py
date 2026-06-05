from __future__ import annotations

import json
import os
import uuid
from typing import Any
from urllib.parse import unquote_plus

import boto3

from shared.gcp_ml_client import call_gcp_ml_processor, generate_presigned_get_url
from shared.media_type import infer_media_type_from_content_type, infer_media_type_from_key
from shared.ml_contracts import GcpMlRequest, ProcessMlResultEvent
from shared.ml_result_processor import process_ml_result_payload
from shared.thumbnailing import create_and_upload_image_thumbnail
from shared.utils import build_db_key


s3 = boto3.client("s3")
lambda_client = boto3.client("lambda")


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(body, default=str),
    }


def _get_first_s3_record(event: dict[str, Any]) -> tuple[str, str]:
    records = event.get("Records") or []
    if not records:
        raise ValueError("Missing S3 Records in event")

    record = records[0]
    bucket = record["s3"]["bucket"]["name"]
    key = unquote_plus(record["s3"]["object"]["key"])
    return bucket, key


def _head_object(bucket: str, key: str) -> dict[str, Any]:
    return s3.head_object(Bucket=bucket, Key=key)


def _read_s3_object_bytes(bucket: str, key: str) -> bytes:
    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def _extract_metadata(head: dict[str, Any], key: str) -> dict[str, str]:
    metadata = head.get("Metadata") or {}

    owner_id = metadata.get("owner_id") or metadata.get("owner-id")
    checksum = metadata.get("checksum")
    file_name = metadata.get("file_name") or metadata.get("file-name") or key.rsplit("/", 1)[-1]

    if not owner_id:
        raise ValueError(f"Missing owner_id metadata for {key}")

    if not checksum:
        raise ValueError(f"Missing checksum metadata for {key}")

    return {
        "owner_id": owner_id,
        "checksum": checksum,
        "file_name": file_name,
    }


def _infer_file_type(head: dict[str, Any], key: str) -> tuple[str, str]:
    content_type = head.get("ContentType")

    try:
        media_type = infer_media_type_from_content_type(content_type, key)
    except ValueError:
        media_type = infer_media_type_from_key(key)

    if content_type:
        file_type = content_type
    elif media_type == "image":
        file_type = "image/jpeg"
    else:
        file_type = "video/mp4"

    return media_type, file_type


def _create_thumbnail_if_supported(bucket: str, key: str, media_type: str) -> tuple[str | None, str | None]:
    if media_type != "image":
        return None, None

    image_bytes = _read_s3_object_bytes(bucket, key)
    return create_and_upload_image_thumbnail(bucket, key, image_bytes)


def _invoke_process_ml_result(payload: dict[str, Any]) -> dict[str, Any]:
    function_name = os.environ.get("PROCESS_ML_RESULT_FUNCTION_NAME")

    if not function_name:
        # Local/direct mode for early testing and simpler rollback.
        return process_ml_result_payload(payload)

    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload, default=str).encode("utf-8"),
    )

    response_payload = json.loads(response["Payload"].read().decode("utf-8"))

    if response.get("FunctionError"):
        raise RuntimeError(f"process_ml_result failed: {response_payload}")

    status_code = int(response_payload.get("statusCode", 200))
    if status_code >= 400:
        raise RuntimeError(f"process_ml_result returned {status_code}: {response_payload}")

    body = response_payload.get("body")
    if isinstance(body, str):
        try:
            response_payload["parsed_body"] = json.loads(body)
        except json.JSONDecodeError:
            response_payload["parsed_body"] = body

    return response_payload


def _mark_failed(
    bucket: str,
    key: str,
    metadata: dict[str, str],
    file_type: str,
    error: Exception,
) -> dict[str, Any]:
    payload = ProcessMlResultEvent(
        owner_id=metadata["owner_id"],
        checksum=metadata["checksum"],
        file_name=metadata["file_name"],
        bucket=bucket,
        key=key,
        file_type=file_type,
        gcp_result={
            "status": "failed",
            "provider": "gcp_cloud_run",
            "error_message": str(error),
        },
    ).model_dump()

    return _invoke_process_ml_result(payload)


def handle_s3_object(bucket: str, key: str) -> dict[str, Any]:
    head = _head_object(bucket, key)
    metadata = _extract_metadata(head, key)
    media_type, file_type = _infer_file_type(head, key)

    thumbnail_key = None
    thumbnail_url = None

    try:
        thumbnail_key, thumbnail_url = _create_thumbnail_if_supported(bucket, key, media_type)

        input_url = generate_presigned_get_url(bucket, key)

        gcp_request = GcpMlRequest(
            request_id=str(uuid.uuid4()),
            checksum=metadata["checksum"],
            bucket=bucket,
            key=key,
            media_type=media_type,
            input_url=input_url,
            source="media_ingest",
        )

        gcp_result = call_gcp_ml_processor(gcp_request)

        process_event = ProcessMlResultEvent(
            owner_id=metadata["owner_id"],
            checksum=metadata["checksum"],
            file_name=metadata["file_name"],
            bucket=bucket,
            key=key,
            file_type=file_type,
            thumbnail_key=thumbnail_key,
            thumbnail_url=thumbnail_url,
            gcp_result=gcp_result,
        )

        return _invoke_process_ml_result(process_event.model_dump())

    except Exception as exc:
        _mark_failed(bucket, key, metadata, file_type, exc)
        raise


def lambda_handler(event, context):
    try:
        bucket, key = _get_first_s3_record(event)
        result = handle_s3_object(bucket, key)
        return _response(
            200,
            {
                "message": "Media ingested",
                "bucket": bucket,
                "key": key,
                "result": result,
            },
        )

    except Exception as exc:
        return _response(
            500,
            {
                "message": "Failed to ingest media",
                "error": str(exc),
            },
        )
