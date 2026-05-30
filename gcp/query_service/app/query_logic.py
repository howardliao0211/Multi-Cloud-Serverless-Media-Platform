from typing import Any, Dict


def media_matches_tags(item: Dict[str, Any], requested_tags: Dict[str, Any]) -> bool:
    # tag_counts is the preferred GCP replica schema. tags is kept as a fallback
    # because the current AWS upload Lambda writes detected counts there.
    tag_counts = item.get("tag_counts") or item.get("tags") or {}

    if not isinstance(tag_counts, dict):
        return False

    for tag, min_count in requested_tags.items():
        # Missing species count as 0, which naturally fails most minimum-count
        # requests and gives the required AND behaviour across all tags.
        actual_count = int(tag_counts.get(tag, 0))

        if actual_count < int(min_count):
            return False

    return True
