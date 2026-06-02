import json
from http import HTTPMethod, HTTPStatus
from typing import Any, Dict, Optional

from pydantic import ValidationError

from shared.aws_resources import get_table
from shared.query_utils import (
    infer_media_type,
    is_ready_media,
    parse_json_request,
    scan_media,
)
from shared.schemas import QueryThumbnailUrlRequest, QueryThumbnailUrlResponse
from shared.utils import build_response_message


table = get_table()


def parse_request(event: dict) -> QueryThumbnailUrlRequest:
    return parse_json_request(event, QueryThumbnailUrlRequest)


def is_matching_thumbnail(item: Dict[str, Any], thumbnail_url: str) -> bool:
    if not is_ready_media(item):
        return False

    if infer_media_type(item) != "image":
        return False

    return item.get("thumbnail_url") == thumbnail_url


def shape_query_response(item: Dict[str, Any]) -> QueryThumbnailUrlResponse:
    return QueryThumbnailUrlResponse(
        checksum=item["checksum"],
        file_name=item["file_name"],
        url=item["full_url"],
        thumbnail_url=item["thumbnail_url"],
    )


def find_by_thumbnail_url(request: QueryThumbnailUrlRequest) -> Optional[QueryThumbnailUrlResponse]:
    for item in scan_media(table):
        if is_matching_thumbnail(item, request.thumbnail_url):
            return shape_query_response(item)

    return None


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
        response = find_by_thumbnail_url(request)

        if response is None:
            return build_response_message(
                status_code=HTTPStatus.NOT_FOUND,
                body={"message": "No media found for thumbnail_url"},
                allow_http_methods=allow_methods,
            )

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
