from typing import Any, Dict, Optional

from app.config import MEDIA_PUBLIC_BASE_URL


def get_tag_counts(item: Dict[str, Any]) -> Dict[str, int]:
    # tag_counts is the preferred GCP replica schema. tags is kept as a fallback
    # because the current AWS upload Lambda writes detected counts there.
    raw_tag_counts = item.get("tag_counts") or item.get("tags") or {}

    if not isinstance(raw_tag_counts, dict):
        return {}

    tag_counts: Dict[str, int] = {}

    for raw_tag, raw_count in raw_tag_counts.items():
        try:
            tag_counts[str(raw_tag).strip().lower()] = int(raw_count)
        except (TypeError, ValueError):
            continue

    return tag_counts


def media_matches_tags(item: Dict[str, Any], requested_tags: Dict[str, Any]) -> bool:
    tag_counts = get_tag_counts(item)

    for tag, min_count in requested_tags.items():
        # Missing species count as 0, which naturally fails most minimum-count
        # requests and gives the required AND behaviour across all tags.
        actual_count = int(tag_counts.get(tag, 0))

        if actual_count < int(min_count):
            return False

    return True


def build_public_url(s3_key: Optional[str]) -> Optional[str]:
    if not s3_key or not MEDIA_PUBLIC_BASE_URL:
        return None

    return f"{MEDIA_PUBLIC_BASE_URL}/{s3_key.lstrip('/')}"


def get_original_url(item: Dict[str, Any]) -> Optional[str]:
    return item.get("original_url") or build_public_url(item.get("s3_key"))


def get_thumbnail_url(item: Dict[str, Any]) -> Optional[str]:
    return item.get("thumbnail_url") or build_public_url(item.get("thumbnail_s3_key"))


def shape_query_result(item: Dict[str, Any]) -> Dict[str, Any]:
    media_type = item.get("media_type")
    original_url = get_original_url(item)
    thumbnail_url = get_thumbnail_url(item)

    if media_type == "video":
        thumbnail_url = None

    return {
        "hash": item.get("hash"),
        "media_type": media_type,
        # The frontend can display thumbnail_url for image previews and open url on click.
        "url": original_url,
        "thumbnail_url": thumbnail_url,
        "tag_counts": get_tag_counts(item),
    }


def thumbnail_url_matches(item: Dict[str, Any], requested_thumbnail_url: str) -> bool:
    thumbnail_url = get_thumbnail_url(item)

    if not thumbnail_url:
        return False

    return thumbnail_url == requested_thumbnail_url


def shape_thumbnail_lookup_result(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "hash": item.get("hash"),
        "media_type": item.get("media_type"),
        "thumbnail_url": get_thumbnail_url(item),
        "url": get_original_url(item),
    }
