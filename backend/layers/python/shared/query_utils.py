import base64
import json
from typing import Any, Dict, Iterable, Type, TypeVar

from pydantic import BaseModel

from shared.schemas import MediaRecordStatus


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


def is_ready_media(item: Dict[str, Any]) -> bool:
    return item.get("upload_status") == MediaRecordStatus.ready.value


def infer_media_type(item: Dict[str, Any]) -> str | None:
    file_type = item.get("file_type")

    if not isinstance(file_type, str) or "/" not in file_type:
        return None

    return file_type.split("/", 1)[0]


def scan_media(table) -> Iterable[Dict[str, Any]]:
    response = table.scan()

    while True:
        for item in response.get("Items", []):
            yield item

        last_key = response.get("LastEvaluatedKey")

        if not last_key:
            break

        response = table.scan(ExclusiveStartKey=last_key)
