import hashlib
import hmac
import json
import os
import time
from decimal import Decimal
from pathlib import Path, PurePosixPath
from urllib.parse import unquote_plus
from typing import Dict, Tuple
from http import HTTPStatus, HTTPMethod

import boto3
import cv2
import numpy as np
import requests

from botocore.exceptions import ClientError

from shared.schemas import MediaRecord, MediaRecordStatus
from shared.model import ImageTagger
from shared.aws_resources import (
    get_bucket_and_name,
    get_table,
    build_thumbnail_s3_key,
    download_s3_file,
    update_media_record_in_db,
    get_s3_object_head_and_url,
    is_media_record_processing
)


s3, bucket_name = get_bucket_and_name()
table = get_table()

CLASSIFIER_MODEL_KEY = "models/model.pt"
DETECTOR_MODEL_KEY = "models/mdv5a.pt"

LOCAL_CLASSIFIER_MODEL_PATH = "/tmp/model.pt"
LOCAL_DETECTOR_MODEL_PATH = "/tmp/mdv5a.pt"

GCP_ML_ENABLED = os.getenv("GCP_ML_ENABLED", "false").lower() == "true"
GCP_ML_PROCESSOR_URL = os.getenv("GCP_ML_PROCESSOR_URL", "").rstrip("/")
GCP_ML_HMAC_SECRET = os.getenv("GCP_ML_HMAC_SECRET", "")
GCP_ML_PRESIGNED_URL_EXPIRY_SECONDS = int(
    os.getenv("GCP_ML_PRESIGNED_URL_EXPIRY_SECONDS", "600")
)

download_s3_file(
    s3, bucket_name, CLASSIFIER_MODEL_KEY, LOCAL_CLASSIFIER_MODEL_PATH
)

download_s3_file(
    s3, bucket_name, DETECTOR_MODEL_KEY, LOCAL_DETECTOR_MODEL_PATH
)


tagger = ImageTagger(
    classifier_model_path=LOCAL_CLASSIFIER_MODEL_PATH,
    detector_model_path=LOCAL_DETECTOR_MODEL_PATH,
)


def convert_floats_for_dynamodb(value):
    """
    DynamoDB does not accept Python float values through boto3 resources.
    Convert nested float values to Decimal before update_item.
    """
    if isinstance(value, float):
        return Decimal(str(value))

    if isinstance(value, list):
        return [convert_floats_for_dynamodb(item) for item in value]

    if isinstance(value, dict):
        return {
            key: convert_floats_for_dynamodb(item)
            for key, item in value.items()
        }

    return value


def sign_gcp_ml_request(body: bytes, timestamp: str) -> str:
    message = timestamp.encode("utf-8") + b"." + body

    return hmac.new(
        GCP_ML_HMAC_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def call_gcp_ml_processor(
    *,
    bucket: str,
    s3_key: str,
    checksum: str,
    file_type: str,
    request_id: str,
) -> dict:
    if not GCP_ML_PROCESSOR_URL:
        raise ValueError("GCP_ML_PROCESSOR_URL is not configured")

    if not GCP_ML_HMAC_SECRET:
        raise ValueError("GCP_ML_HMAC_SECRET is not configured")

    media_type = file_type.split("/")[0]

    presigned_url = s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": s3_key,
        },
        ExpiresIn=GCP_ML_PRESIGNED_URL_EXPIRY_SECONDS,
    )

    payload = {
        "request_id": request_id,
        "hash": checksum,
        "media_type": media_type,
        "inputs": [
            {
                "source": "original",
                "url": presigned_url,
                "timestamp_sec": None,
            }
        ],
    }

    body = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    timestamp = str(int(time.time()))
    signature = sign_gcp_ml_request(body, timestamp)

    response = requests.post(
        f"{GCP_ML_PROCESSOR_URL}/process-media",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Timestamp": timestamp,
            "X-Signature": signature,
        },
        timeout=60,
    )

    response.raise_for_status()

    result = response.json()

    if result.get("hash") != checksum:
        raise ValueError(
            f"GCP ML response hash mismatch: expected {checksum}, got {result.get('hash')}"
        )

    if result.get("status") != "success":
        raise ValueError(f"GCP ML returned non-success status: {result}")

    return result


def tag_image_with_fallback(
    *,
    local_path: Path,
    bucket: str,
    s3_key: str,
    checksum: str,
    file_type: str,
    request_id: str,
) -> dict:
    if GCP_ML_ENABLED:
        try:
            print("Calling GCP ML processor")
            gcp_result = call_gcp_ml_processor(
                bucket=bucket,
                s3_key=s3_key,
                checksum=checksum,
                file_type=file_type,
                request_id=request_id,
            )

            return {
                "tags": gcp_result.get("tag_counts", {}),
                "ml_provider": "gcp_cloud_run",
                "ml_detections": convert_floats_for_dynamodb(gcp_result.get("detections", [])),
                "ml_model_name": gcp_result.get("model_name"),
                "ml_model_version": gcp_result.get("model_version"),
            }

        except Exception as exc:
            print(f"GCP ML failed, falling back to local AWS model: {exc}")

    local_result = tagger.tag_image(local_path)

    return {
        "tags": local_result["tags"],
        "ml_provider": "aws_lambda_local",
        "ml_detections": convert_floats_for_dynamodb(local_result.get("detections", [])),
        "ml_model_name": "local_image_tagger",
        "ml_model_version": "current",
    }


def create_thumbnail(image_path: Path, fx: float = 0.5, fy: float = 0.5):
    image = cv2.imread(image_path)
    resized_scaled = cv2.resize(
        image, None, fx=fx, fy=fy, interpolation=cv2.INTER_AREA)
    return resized_scaled


def upload_thumbnail_to_s3(
    image_array: np.ndarray,
    s3_key: str,
    bucket: str,
) -> None:
    success, encoded_image = cv2.imencode(".jpg", image_array)

    if not success:
        raise ValueError("Failed to encode thumbnail image as JPEG.")

    image_bytes = encoded_image.tobytes()

    s3.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=image_bytes,
        ContentType="image/jpeg",
    )


def process_image(bucket: str, s3_key: str, request_id: str):

    head, full_url = get_s3_object_head_and_url(s3_key)
    file_name = head["Metadata"]["file_name"]
    file_ext = file_name.split(".")[-1]
    checksum = head["Metadata"]["checksum"]
    file_type = head["ContentType"]

    if file_type.split("/")[0] != "image":
        print(f"Skipping non-image object: {s3_key}")
        return

    thumbnail_s3_key = build_thumbnail_s3_key(checksum + f".{file_ext}")

    update_media_record_in_db(
        table, file_name, checksum, {
            "full_url": full_url,
            "file_type": file_type,
            "upload_status": MediaRecordStatus.uploaded,
        }
    )

    should_process = is_media_record_processing(
        table, file_name, checksum,
    )

    if not should_process:
        print(
            f"Duplicate media already exists, skipping model run: {file_name}")
        return

    try:
        update_media_record_in_db(
            table, file_name, checksum, {
                "upload_status": MediaRecordStatus.processing,
            }
        )

        local_path = f"/tmp/{file_name}"

        download_s3_file(
            s3=s3,
            bucket=bucket,
            s3_key=s3_key,
            local_path=local_path,
        )

        thumbnail = create_thumbnail(
            image_path=local_path
        )

        upload_thumbnail_to_s3(thumbnail, thumbnail_s3_key, bucket)
        _, thumbnail_url = get_s3_object_head_and_url(thumbnail_s3_key)

        tagger_result = tag_image_with_fallback(
            local_path=Path(local_path),
            bucket=bucket,
            s3_key=s3_key,
            checksum=checksum,
            file_type=file_type,
            request_id=request_id,
        )

        update_media_record_in_db(
            table, file_name, checksum, {
                "thumbnail_key": thumbnail_s3_key,
                "thumbnail_url": thumbnail_url,
                "tags": tagger_result["tags"],
                "ml_provider": tagger_result["ml_provider"],
                "ml_detections": tagger_result["ml_detections"],
                "ml_model_name": tagger_result["ml_model_name"],
                "ml_model_version": tagger_result["ml_model_version"],
                "error_message": None,
                "upload_status": MediaRecordStatus.ready,
            }
        )

        print(f"Finished processing media: {s3_key}")
    except Exception as e:
        update_media_record_in_db(
            table, file_name, checksum, {
                "upload_status": MediaRecordStatus.failed,
                "error_message": f"Error: {e}",
            }
        )
        raise


def lambda_handler(event, context):
    img_file_extensions = [
        "png", "jpg",
    ]

    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        s3_key = unquote_plus(record["s3"]["object"]["key"])
        file_ext = s3_key.split(".")[-1]

        if file_ext not in img_file_extensions:
            raise ValueError(
                f"Unsupported image file type. Only support {img_file_extensions}"
            )

        process_image(
            bucket=bucket,
            s3_key=s3_key,
            request_id=context.aws_request_id,
        )
