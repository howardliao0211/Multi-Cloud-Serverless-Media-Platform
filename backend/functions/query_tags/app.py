import json
from http import HTTPMethod, HTTPStatus
from typing import Dict, List

from pydantic import ValidationError

from shared.aws_resources import get_table, scan_media_record, get_bucket_and_name
from shared.query_utils import (
    can_query_media,
    infer_media_type,
    normalize_tag_counts,
    parse_json_request,
)
from shared.schemas import (
    MediaRecord,
    MediaRecordStatus,
    QueryTagsRequest,
    MediaRecordResponse,
    GetMediaResponse,
)
from shared.utils import build_response_message, get_current_user

s3, bucket_name = get_bucket_and_name()
table = get_table()


def parse_request(event: dict) -> QueryTagsRequest:
    return parse_json_request(event, QueryTagsRequest)


def media_matches_tags(media_record: MediaRecord, requested_tags: Dict[str, int]) -> bool:
    tag_counts = normalize_tag_counts(media_record.tags)

    for tag, min_count in requested_tags.items():
        if tag_counts.get(tag, 0) < min_count:
            return False

    return True


def shape_query_result(media_record: MediaRecord) -> MediaRecordResponse:

    return QueryTagsResult(
        checksum=media_record.checksum,
        file_name=media_record.file_name,
        visibility=media_record.visibility,
        media_type=media_type,
        url=media_record.full_url,
        thumbnail_url=thumbnail_url,
        tags=normalize_tag_counts(media_record.tags),
    )


def query_tags(request: QueryTagsRequest, current_user: str) -> GetMediaResponse:
    results: List[MediaRecordResponse] = []

    filters = {"upload_status": MediaRecordStatus.ready}

    for media_record in scan_media_record(table, filters):
        if not can_query_media(media_record, current_user):
            continue

        if media_matches_tags(media_record, request.tags):
            results.append(
                MediaRecordResponse.from_media_record(
                    media_record,
                    s3, bucket_name, 300
                )
            )

    return GetMediaResponse(
        media_records=results,
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
        current_user = get_current_user(event)
        response = query_tags(request, current_user)

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
