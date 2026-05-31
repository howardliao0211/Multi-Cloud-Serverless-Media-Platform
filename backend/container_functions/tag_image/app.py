import os
from pathlib import Path, PurePosixPath
from urllib.parse import unquote_plus
from typing import Dict, Tuple
from http import HTTPStatus, HTTPMethod

import boto3
import cv2
import numpy as np

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


def process_image(bucket: str, s3_key: str):

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

        tagger_result = tagger.tag_image(Path(local_path))

        update_media_record_in_db(
            table, file_name, checksum, {
                "thumbnail_key": thumbnail_s3_key,
                "thumbnail_url": thumbnail_url,
                "tags": tagger_result["tags"],
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
        )
