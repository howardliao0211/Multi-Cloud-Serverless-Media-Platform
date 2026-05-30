import boto3
from botocore.config import Config
from typing import Literal


BUCKET_NAME = "aussie-eco-len-bucket-12345"
TABLE_NAME = "aussie-eco-len-media"
REGION_NAME = "us-east-1"

def get_bucket_and_name():
    s3 = boto3.client(
        "s3",
        region_name="us-east-1",
        config=Config(signature_version="s3v4")
    )
    return s3, BUCKET_NAME

def get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)

def build_s3_key(
    key_name: str,
    media_type: Literal["image", "video"]
) -> str:
    assert media_type in ("images"), "video"
    return f"{media_type}s/{key_name}"

def build_thumbnail_s3_key(
    key_name: str
) -> str:
    return f"thumbnails/{key_name}"
