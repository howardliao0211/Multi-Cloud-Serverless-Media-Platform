from __future__ import annotations

from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def infer_media_type_from_key(key: str) -> str:
    suffix = Path(key).suffix.lower()

    if suffix in IMAGE_EXTENSIONS:
        return "image"

    if suffix in VIDEO_EXTENSIONS:
        return "video"

    raise ValueError(f"Unsupported media file extension for key: {key}")


def infer_media_type_from_content_type(content_type: str | None, key: str | None = None) -> str:
    if content_type:
        normalized = content_type.lower()

        if normalized.startswith("image/"):
            return "image"

        if normalized.startswith("video/"):
            return "video"

    if key:
        return infer_media_type_from_key(key)

    raise ValueError(f"Unsupported media content type: {content_type!r}")


def is_supported_media_type(media_type: str) -> bool:
    return media_type in {"image", "video"}
