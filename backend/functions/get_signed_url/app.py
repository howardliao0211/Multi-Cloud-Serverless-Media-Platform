import json
import os
from typing import Literal

import boto3
from pydantic import BaseModel, ValidationError

from shared.schemas import MediaRecord, UploadUrlRequest

from botocore.config import Config

s3 = boto3.client(
    "s3",
    region_name="us-east-1",
    config=Config(signature_version="s3v4")
)
dynamodb = boto3.resource("dynamodb")

BUCKET_NAME = "aussie-eco-len-bucket-12345"
TABLE_NAME = "aussie-eco-len-media"
URL_EXPIRES_SECONDS = int(os.environ.get("URL_EXPIRES_SECONDS", "300"))

table = dynamodb.Table(TABLE_NAME)


def response(status_code: int, body: dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "OPTIONS,POST",
        },
        "body": json.dumps(body),
    }


def parse_request(event: dict) -> UploadUrlRequest | None:
    body = event.get("body")
    return UploadUrlRequest(**json.loads(body))


def build_s3_key(media_hash: str, media_type: str) -> str:
    if media_type == "image":
        return f"images/{media_hash}.jpg"
    else:
        return f"videos/{media_hash}.mp4"


def build_thumbnail_s3_key(media_hash: str) -> str:
    return f"thumbnails/{media_hash}.jpg"


def get_existing_media(media_hash: str) -> MediaRecord | None:
    result = table.get_item(
        Key={
            "hash": media_hash,
        }
    )
    item = result.get("Item")

    if item is None:
        return None

    return MediaRecord(**item)


def generate_upload_url(s3_key: str) -> str:
    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": BUCKET_NAME,
            "Key": s3_key,
        },
        ExpiresIn=URL_EXPIRES_SECONDS,
    )


def lambda_handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {"message": "OK"})

    request = parse_request(event)
    existing_media = get_existing_media(request.hash)

    if existing_media:
        return response(200, {
            "duplicate": True,
            "message": "Media already exists.",
            "media": existing_media.model_dump(),
        })

    s3_key = build_s3_key(request.hash, request.media_type)
    upload_url = generate_upload_url(s3_key)

    return response(200, {
        "duplicate": False,
        "upload_url": upload_url,
        "expires_in": URL_EXPIRES_SECONDS,
    })
