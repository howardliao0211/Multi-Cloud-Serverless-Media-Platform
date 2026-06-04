from __future__ import annotations

import io
from pathlib import Path

import boto3
from PIL import Image, ImageOps


DEFAULT_THUMBNAIL_SIZE = (512, 512)


def build_thumbnail_key(media_key: str, output_extension: str = ".jpg") -> str:
    stem = Path(media_key).stem
    return f"thumbnails/{stem}{output_extension}"


def create_image_thumbnail_bytes(
    image_bytes: bytes,
    size: tuple[int, int] = DEFAULT_THUMBNAIL_SIZE,
    output_format: str = "JPEG",
) -> bytes:
    with Image.open(io.BytesIO(image_bytes)) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail(size)

        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")

        output = io.BytesIO()
        image.save(output, format=output_format, quality=85, optimize=True)
        return output.getvalue()


def upload_thumbnail_bytes(
    bucket: str,
    thumbnail_key: str,
    thumbnail_bytes: bytes,
    content_type: str = "image/jpeg",
) -> str:
    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=bucket,
        Key=thumbnail_key,
        Body=thumbnail_bytes,
        ContentType=content_type,
    )

    return f"https://{bucket}.s3.amazonaws.com/{thumbnail_key}"


def create_and_upload_image_thumbnail(
    bucket: str,
    media_key: str,
    image_bytes: bytes,
) -> tuple[str, str]:
    thumbnail_key = build_thumbnail_key(media_key)
    thumbnail_bytes = create_image_thumbnail_bytes(image_bytes)
    thumbnail_url = upload_thumbnail_bytes(bucket, thumbnail_key, thumbnail_bytes)
    return thumbnail_key, thumbnail_url
