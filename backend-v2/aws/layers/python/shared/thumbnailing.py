from __future__ import annotations

import io
import tempfile
from pathlib import Path

import boto3
import cv2
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


def create_video_thumbnail_bytes(
    video_path: str,
    max_width: int = 768,
) -> bytes:
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    try:
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        # Prefer a frame around one third into the video, falling back to the first frame.
        target_frame = max(frame_count // 3, 0)
        if target_frame:
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)

        success, frame = cap.read()

        if not success or frame is None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            success, frame = cap.read()

        if not success or frame is None:
            raise ValueError("Could not extract thumbnail frame from video")

        height, width = frame.shape[:2]
        if width > max_width:
            scale = max_width / width
            frame = cv2.resize(
                frame,
                (max_width, int(height * scale)),
                interpolation=cv2.INTER_AREA,
            )

        success, encoded = cv2.imencode(".jpg", frame)
        if not success:
            raise ValueError("Failed to encode video thumbnail as JPEG")

        return encoded.tobytes()
    finally:
        cap.release()


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


def create_and_upload_video_thumbnail(
    bucket: str,
    media_key: str,
    video_bytes: bytes,
) -> tuple[str, str]:
    thumbnail_key = build_thumbnail_key(media_key)

    suffix = Path(media_key).suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        tmp.write(video_bytes)
        tmp.flush()

        thumbnail_bytes = create_video_thumbnail_bytes(tmp.name)

    thumbnail_url = upload_thumbnail_bytes(bucket, thumbnail_key, thumbnail_bytes)
    return thumbnail_key, thumbnail_url
