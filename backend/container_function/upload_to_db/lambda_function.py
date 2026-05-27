import os
from pathlib import Path, PurePosixPath
from urllib.parse import unquote_plus

import boto3
import cv2
import numpy as np

from botocore.exceptions import ClientError

from shared.schemas import MediaRecord
from shared.model import ImageTagger


s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

TABLE_NAME = "aussie-eco-len-media"
table = dynamodb.Table(TABLE_NAME)

tagger = ImageTagger()


def parse_s3_key(s3_key: str) -> tuple[str, str, str]:
    """
    images/abc123.jpg -> ("abc123", "image", "jpg")
    videos/abc123.mp4 -> ("abc123", "video", "mp4")
    """
    path = PurePosixPath(s3_key)

    folder = path.parts[0]
    filename = path.name

    media_hash, extension = filename.rsplit(".", 1)

    if folder == "images":
        media_type = "image"
    elif folder == "videos":
        media_type = "video"
    else:
        raise ValueError(f"Unsupported S3 folder: {folder}")

    return media_hash, media_type, extension


def build_thumbnail_s3_key(media_hash: str) -> str:
    return f"thumbnails/{media_hash}.jpg"


def create_uploaded_record(media: MediaRecord) -> bool:
    """
    Create the initial record only if the hash does not already exist.

    Returns:
        True  -> this Lambda owns the processing work
        False -> duplicate record already exists, skip processing
    """
    try:
        table.put_item(
            Item=media.model_dump(),
            ConditionExpression="attribute_not_exists(#hash)",
            ExpressionAttributeNames={
                "#hash": "hash",
            },
        )
        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def update_status(media_hash: str, status: str) -> None:
    table.update_item(
        Key={
            "hash": media_hash,
        },
        UpdateExpression="SET upload_status = :status",
        ExpressionAttributeValues={
            ":status": status,
        },
    )


def update_ready(media_hash: str, tags: dict[str, int]) -> None:
    table.update_item(
        Key={
            "hash": media_hash,
        },
        UpdateExpression="""
            SET tags = :tags,
                upload_status = :status
        """,
        ExpressionAttributeValues={
            ":tags": tags,
            ":status": "READY",
        },
    )


def download_s3_file(bucket: str, s3_key: str, local_path: str) -> None:
    s3.download_file(
        Bucket=bucket,
        Key=s3_key,
        Filename=local_path,
    )


def create_thumbnail(image_path: Path, fx: float = 0.5, fy: float = 0.5):
    image = cv2.imread(image_path)
    resized_scaled = cv2.resize(image, None, fx=fx, fy=fy, interpolation=cv2.INTER_AREA)
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

def process_image(bucket: str, s3_key: str) -> None:
    media_hash, media_type, extension = parse_s3_key(s3_key)

    if media_type != "image":
        print(f"Skipping non-image object: {s3_key}")
        return

    thumbnail_s3_key = build_thumbnail_s3_key(media_hash)

    media = MediaRecord(
        hash=media_hash,
        media_type=media_type,
        s3_key=s3_key,
        thumbnail_s3_key=thumbnail_s3_key,
        tags={},
        upload_status="UPLOADED",
    )

    should_process = create_uploaded_record(media)

    if not should_process:
        print(
            f"Duplicate media already exists, skipping model run: {media_hash}")
        return

    try:
        update_status(media_hash, "PROCESSING")

        local_path = f"/tmp/{media_hash}.{extension}"

        download_s3_file(
            bucket=bucket,
            s3_key=s3_key,
            local_path=local_path,
        )

        thumbnail = create_thumbnail(
            image_path=local_path
        )

        upload_thumbnail_to_s3(thumbnail, thumbnail_s3_key, bucket)

        tagger_result = tagger.tag_image(Path(local_path))
        update_ready(
            media_hash=media_hash,
            tags=tagger_result["tags"],
        )

        print(f"Finished processing media: {media_hash}")

    except Exception as e:
        print(f"Failed to process media {media_hash}:", repr(e))
        update_status(media_hash, "FAILED")
        raise


def lambda_handler(event, context):
    img_file_extensions = [
        "png", "jpg", ""
    ]
    video_file_extensions = [
        "mov", "mp4"
    ]

    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        s3_key = unquote_plus(record["s3"]["object"]["key"])
        file_ext = s3_key.split(".")[-1]

        if file_ext in img_file_extensions:
            process_image(
                bucket=bucket,
                s3_key=s3_key,
            )
        elif file_ext in video_file_extensions:
            raise NotImplementedError()
        else:
            raise ValueError(f"Unhandled file extension: {file_ext}")

    return {
        "statusCode": 200,
        "body": "S3 upload event processed successfully",
    }
