import json
from http import HTTPMethod, HTTPStatus
from typing import Optional

from pydantic import ValidationError

from shared.aws_resources import get_table, scan_media_record
from shared.query_utils import parse_json_request
from shared.schemas import EditTagsRequest, EditTagsResponse, EditTagsResult, MediaRecord
from shared.utils import build_response_message


table = get_table()


def parse_request(event: dict) -> EditTagsRequest:
    return parse_json_request(event, EditTagsRequest)


def media_matches_url(media_record: MediaRecord, url: str) -> bool:
    return url in {
        media_record.full_url,
        media_record.thumbnail_url,
    }


def find_media_by_url(url: str) -> Optional[MediaRecord]:
    for media_record in scan_media_record(table):
        if media_matches_url(media_record, url):
            return media_record

    return None


def build_lookup_response(request: EditTagsRequest) -> EditTagsResponse:
    results: list[EditTagsResult] = []

    for url in request.urls:
        media_record = find_media_by_url(url)

        if media_record is None:
            results.append(
                EditTagsResult(
                    url=url,
                    updated=False,
                    message="media not found",
                )
            )
            continue

        results.append(
            EditTagsResult(
                url=url,
                updated=False,
                checksum=media_record.checksum,
                file_name=media_record.file_name,
                tags=media_record.tags,
                message="media found; edit_tags update logic is not implemented yet",
            )
        )

    return EditTagsResponse(
        updated_count=0,
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

    if event.get("httpMethod") != "POST":
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Unsupported HTTP method"},
            allow_http_methods=allow_methods,
        )

    try:
        request = parse_request(event)
        response = build_lookup_response(request)

        return build_response_message(
            status_code=HTTPStatus.NOT_IMPLEMENTED,
            body=response.model_dump(mode="json"),
            allow_http_methods=allow_methods,
        )
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Invalid edit tags request", "error": str(error)},
            allow_http_methods=allow_methods,
        )
