from io import BytesIO
from PIL import Image
import uuid
from pathlib import Path
from http import HTTPMethod, HTTPStatus

from urllib.parse import unquote_plus

import cv2
import numpy as np

import google.auth
from google.auth import impersonated_credentials
from google.auth.transport.requests import Request as GoogleAuthRequest


from shared.schemas import MediaRecordStatus, MediaType
from shared.aws_resources import (
    get_bucket_and_name,
    get_table,
    download_s3_file,
    update_media_record_in_db,
    get_s3_object_head_and_url,
    is_media_record_processing,
    upload_thumbnail_to_s3,
)
from shared.gcp_ml_contracts import GcpMlRequest, GcpModelUrls
from shared.gcp_ml_client import (
    call_gcp_ml_processor,
    generate_presigned_get_url,
    create_thumbnail_bytes,
)
from shared.utils import build_db_key, build_thumbnail_s3_key, build_response_message

s3, bucket_name = get_bucket_and_name()
CLASSIFIER_MODEL_KEY = "models/model.pt"
DETECTOR_MODEL_KEY = "models/mdv5a.pt"
table = get_table()


def process_image(bucket: str, s3_key: str, request_id: str):

    head, full_url = get_s3_object_head_and_url(s3_key)
    file_name = head["Metadata"]["file_name"]
    checksum = head["Metadata"]["checksum"]
    owner_id = head["Metadata"]["owner_id"]
    file_ext = file_name.split(".")[-1]
    file_type = head["ContentType"]

    thumbnail_s3_key = build_thumbnail_s3_key(checksum + f".{file_ext}")
    db_key = build_db_key(owner_id, s3_key)

    update_media_record_in_db(
        table,
        db_key,
        {
            "full_url": full_url,
            "file_type": file_type,
            "upload_status": MediaRecordStatus.uploaded,
        },
    )

    should_process = is_media_record_processing(table, db_key)

    if not should_process:
        print(f"Duplicate media already exists, skipping model run: {file_name}")
        return

    try:
        update_media_record_in_db(
            table,
            db_key,
            {
                "upload_status": MediaRecordStatus.processing,
            },
        )

        local_path = f"/tmp/{file_name}"

        download_s3_file(
            s3=s3,
            bucket=bucket,
            s3_key=s3_key,
            local_path=local_path,
        )

        thumbnail_bytes = create_thumbnail_bytes(Path(local_path))

        upload_thumbnail_to_s3(thumbnail_bytes, s3, bucket, thumbnail_s3_key)
        _, thumbnail_url = get_s3_object_head_and_url(thumbnail_s3_key)

        input_url = generate_presigned_get_url(bucket, s3_key)
        model_urls = GcpModelUrls(
            classifier=generate_presigned_get_url(bucket, CLASSIFIER_MODEL_KEY),
            detector=generate_presigned_get_url(bucket, DETECTOR_MODEL_KEY),
        )

        gcp_request = GcpMlRequest(
            request_id=str(uuid.uuid4()),
            media_type=MediaType.image.value,
            input_url=input_url,
            model_urls=model_urls,
            model_version="model_presigned_v1",
        )

        gcp_result = call_gcp_ml_processor(gcp_request)

        db_entry = {
            "thumbnail_key": thumbnail_s3_key,
            "thumbnail_url": thumbnail_url,
            "tags": gcp_result.tag_counts,
            "error_message": None,
            "upload_status": MediaRecordStatus.ready,
        }

        update_media_record_in_db(
            table,
            db_key,
            db_entry,
        )

        print(f"Finished processing media: {s3_key}")
        return db_entry

    except Exception as e:
        update_media_record_in_db(
            table,
            db_key,
            {
                "upload_status": MediaRecordStatus.failed,
                "error_message": f"Error: {e}",
            },
        )
        raise


def lambda_handler(event, context):
    img_file_extensions = ["jpg", "jpeg", "png", "webp"]
    entries = []

    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        s3_key = unquote_plus(record["s3"]["object"]["key"])
        file_ext = s3_key.split(".")[-1]

        if file_ext.lower() not in img_file_extensions:
            raise ValueError(
                f"Unsupported image file type. Only support {img_file_extensions}"
            )

        db_entry = process_image(
            bucket=bucket,
            s3_key=s3_key,
            request_id=context.aws_request_id,
        )

        entries.append(db_entry)

    return build_response_message(
        status_code=HTTPStatus.OK, body=entries, allow_http_methods=[]
    )
