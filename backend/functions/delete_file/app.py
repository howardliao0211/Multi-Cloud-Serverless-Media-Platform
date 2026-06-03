import json
from http import HTTPMethod, HTTPStatus
from typing import Optional

from pydantic import ValidationError

from shared.aws_resources import get_table, scan_media_record
from shared.query_utils import parse_json_request
from shared.schemas import DeleteFileRequest, DeleteFileResponse, DeleteFileResult, MediaRecord
from shared.utils import build_response_message, get_current_user


table = get_table()


def parse_request(event: dict) -> DeleteFileRequest:
    return parse_json_request(event, DeleteFileRequest)


def media_matches_url(media_record: MediaRecord, url: str) -> bool:
    return url in {
        media_record.full_url,
        media_record.thumbnail_url,
    }


def find_media_records_by_url(
    media_records: list[MediaRecord],
    url: str,
) -> list[MediaRecord]:
    return [
        media_record
        for media_record in media_records
        if media_matches_url(media_record, url)
    ]


def find_user_media_by_url(
    media_records: list[MediaRecord],
    url: str,
    current_user: str,
) -> tuple[Optional[MediaRecord], bool]:
    matching_records = find_media_records_by_url(media_records, url)

    for media_record in matching_records:
        if media_record.owner_id == current_user:
            return media_record, True

    return None, bool(matching_records)


def plan_delete_file(request: DeleteFileRequest, current_user: str) -> DeleteFileResponse:
    results: list[DeleteFileResult] = []
    media_records = scan_media_record(table)

    for url in request.urls:
        media_record, media_exists = find_user_media_by_url(
            media_records,
            url,
            current_user,
        )

        if not media_exists:
            results.append(
                DeleteFileResult(
                    url=url,
                    deleted=False,
                    message="media not found",
                )
            )
            continue

        if media_record is None:
            results.append(
                DeleteFileResult(
                    url=url,
                    deleted=False,
                    message="forbidden: media is owned by another user",
                )
            )
            continue

        results.append(
            DeleteFileResult(
                url=url,
                deleted=False,
                checksum=media_record.checksum,
                file_name=media_record.file_name,
                message="delete target resolved",
            )
        )

    return DeleteFileResponse(
        deleted_count=0,
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
        current_user = get_current_user(event)
        response = plan_delete_file(request, current_user)

        return build_response_message(
            status_code=HTTPStatus.OK,
            body=response.model_dump(mode="json"),
            allow_http_methods=allow_methods,
        )
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Invalid delete file request", "error": str(error)},
            allow_http_methods=allow_methods,
        )
