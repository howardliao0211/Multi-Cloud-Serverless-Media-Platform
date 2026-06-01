import base64
import json
from http import HTTPMethod, HTTPStatus
from typing import Any, Dict, Iterable, List

from pydantic import ValidationError

from shared.aws_resources import get_table
from shared.schemas import (
    MediaRecordStatus,
    QueryTagsRequest,
    QueryTagsResponse,
    QueryTagsResult,
)
from shared.utils import build_response_message


table = get_table()


def parse_request(event: dict) -> QueryTagsRequest:
    body = event.get("body") or "{}"

    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")

    return QueryTagsRequest(**json.loads(body))


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


def media_matches_tags(item: Dict[str, Any], requested_tags: Dict[str, int]) -> bool:
    tag_counts = normalize_tag_counts(item.get("tags"))

    for tag, min_count in requested_tags.items():
        if tag_counts.get(tag, 0) < min_count:
            return False

    return True


def is_ready_media(item: Dict[str, Any]) -> bool:
    return item.get("upload_status") == MediaRecordStatus.ready.value


def infer_media_type(item: Dict[str, Any]) -> str | None:
    file_type = item.get("file_type")

    if not isinstance(file_type, str) or "/" not in file_type:
        return None

    return file_type.split("/", 1)[0]


def shape_query_result(item: Dict[str, Any]) -> QueryTagsResult:
    media_type = infer_media_type(item)
    thumbnail_url = item.get("thumbnail_url") if media_type == "image" else None

    return QueryTagsResult(
        checksum=item["checksum"],
        file_name=item["file_name"],
        media_type=media_type,
        url=item.get("full_url"),
        thumbnail_url=thumbnail_url,
        tags=normalize_tag_counts(item.get("tags")),
    )


def scan_media() -> Iterable[Dict[str, Any]]:
    response = table.scan()

    while True:
        for item in response.get("Items", []):
            yield item

        last_key = response.get("LastEvaluatedKey")

        if not last_key:
            break

        response = table.scan(ExclusiveStartKey=last_key)


def query_tags(request: QueryTagsRequest) -> QueryTagsResponse:
    results: List[QueryTagsResult] = []

    for item in scan_media():
        if not is_ready_media(item):
            continue

        if media_matches_tags(item, request.tags):
            results.append(shape_query_result(item))

    return QueryTagsResponse(
        count=len(results),
        results=results,
    )


def lambda_handler(event, context):
    allow_methods = [HTTPMethod.POST, HTTPMethod.OPTIONS]

    if event.get("httpMethod") == "OPTIONS":
        return build_response_message(
            status_code=HTTPStatus.OK,
            body={"message": "OK"},
            allow_http_methods=allow_methods,
        )

    try:
        request = parse_request(event)
        response = query_tags(request)

        return build_response_message(
            status_code=HTTPStatus.OK,
            body=response.model_dump(mode="json"),
            allow_http_methods=allow_methods,
        )
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Invalid query request", "error": str(error)},
            allow_http_methods=allow_methods,
        )
