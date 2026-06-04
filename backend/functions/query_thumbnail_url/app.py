import json
from http import HTTPMethod, HTTPStatus
from typing import Optional

from pydantic import ValidationError

from shared.aws_resources import get_table, scan_media_record, get_bucket_and_name
from shared.query_utils import (
    can_query_media,
    parse_json_request,
)
from shared.schemas import (
    MediaRecord,
    MediaRecordStatus,
    MediaRecordResponse,
    QueryThumbnailUrlRequest,
    GetMediaResponse
)
from shared.utils import build_response_message, get_current_user


table = get_table()
s3, bucket_name = get_bucket_and_name()


def parse_request(event: dict) -> QueryThumbnailUrlRequest:
    return parse_json_request(event, QueryThumbnailUrlRequest)


def is_matching_thumbnail(media_record: MediaRecord, thumbnail_url: str) -> bool:
    return media_record.thumbnail_url == thumbnail_url


def find_by_thumbnail_url(
    request: QueryThumbnailUrlRequest,
    current_user: str,
) -> GetMediaResponse:

    results = []

    filters = {
        "upload_status": MediaRecordStatus.ready,
        "thumbnail_url": request.thumbnail_url,
    }

    for media_record in scan_media_record(table, filters):
        if not can_query_media(media_record, current_user):
            continue

        if is_matching_thumbnail(media_record, request.thumbnail_url):
            results.append(
                MediaRecordResponse.from_media_record(
                    media_record, s3, bucket_name
                )
            )

    return GetMediaResponse(
        media_records=results
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
        response = find_by_thumbnail_url(request, current_user)

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
