import base64
import json
from typing import Any, Dict, Type, TypeVar

from pydantic import BaseModel

from shared.schemas import MediaRecord, MediaVisibility


RequestModel = TypeVar("RequestModel", bound=BaseModel)


def parse_json_request(event: dict, model_cls: Type[RequestModel]) -> RequestModel:
    body = event.get("body") or "{}"

    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")

    return model_cls(**json.loads(body))


def normalize_tag_counts(raw_tags: Any) -> Dict[str, int]:
    if not isinstance(raw_tags, dict):
        return {}

    tag_counts: Dict[str, int] = {}

    for raw_tag, raw_count in raw_tags.items():
        tag = str(raw_tag).strip().lower()

        if not tag:
            continue

        try:
            tag_counts[tag] = int(raw_count)
        except (TypeError, ValueError):
            continue

    return tag_counts


def infer_media_type(media_record: MediaRecord) -> str | None:
    file_type = media_record.file_type

    if not isinstance(file_type, str) or "/" not in file_type:
        return None

    return file_type.split("/", 1)[0]


def can_query_media(media_record: MediaRecord, current_user: str) -> bool:
    if media_record.visibility == MediaVisibility.public:
        return True

    return media_record.owner_id == current_user
