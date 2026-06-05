import json
from http import HTTPMethod, HTTPStatus
from typing import Optional

from pydantic import ValidationError

from shared.aws_resources import (
    delete_media_record_from_db,
    delete_s3_object_if_exists,
    get_bucket_and_name,
    get_table,
    scan_media_record,
)
from shared.query_utils import parse_json_request
from shared.schemas import (
    DeleteFileRequest,
    DeleteFileResponse,
    DeleteFileResult,
    MediaRecord,
)
from shared.utils import (
    build_response_message,
    get_current_user,
)


s3, bucket_name = get_bucket_and_name()
table = get_table()


def get_http_method(event: dict) -> str:
    """
    Supports both:

    API Gateway REST API v1:
        event["httpMethod"]

    API Gateway HTTP API v2:
        event["requestContext"]["http"]["method"]
    """
    method = event.get("httpMethod")

    if method:
        return str(method).upper()

    method = (
        event
        .get("requestContext", {})
        .get("http", {})
        .get("method", "")
    )

    return str(method).upper()


def parse_request(event: dict) -> DeleteFileRequest:
    return parse_json_request(event, DeleteFileRequest)


def media_matches_url(
    media_record: MediaRecord,
    url: str,
) -> bool:
    return url in {
        str(media_record.full_url) if media_record.full_url else None,
        str(media_record.thumbnail_url) if media_record.thumbnail_url else None,
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
    matching_records = find_media_records_by_url(
        media_records,
        url,
    )

    for media_record in matching_records:
        if media_record.owner_id == current_user:
            return media_record, True

    return None, bool(matching_records)


def is_s3_key_referenced(
    media_records: list[MediaRecord],
    s3_key: str | None,
    field_name: str,
) -> bool:
    if not s3_key:
        return False

    return any(
        getattr(media_record, field_name, None) == s3_key
        for media_record in media_records
    )


def delete_files(
    request: DeleteFileRequest,
    current_user: str,
) -> DeleteFileResponse:
    results: list[DeleteFileResult] = []
    deleted_count = 0

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

        remaining_records = [
            record
            for record in media_records
            if record.key != media_record.key
        ]

        should_delete_full_object = not is_s3_key_referenced(
            remaining_records,
            media_record.full_key,
            "full_key",
        )

        should_delete_thumbnail_object = not is_s3_key_referenced(
            remaining_records,
            media_record.thumbnail_key,
            "thumbnail_key",
        )

        delete_media_record_from_db(
            table,
            media_record.key,
        )

        removed_full_object = False
        removed_thumbnail_object = False

        if should_delete_full_object and media_record.full_key:
            removed_full_object = delete_s3_object_if_exists(
                s3,
                bucket_name,
                media_record.full_key,
            )

        if should_delete_thumbnail_object and media_record.thumbnail_key:
            removed_thumbnail_object = delete_s3_object_if_exists(
                s3,
                bucket_name,
                media_record.thumbnail_key,
            )

        media_records = remaining_records
        deleted_count += 1

        results.append(
            DeleteFileResult(
                url=url,
                deleted=True,
                checksum=media_record.checksum,
                file_name=media_record.file_name,
                removed_db_entry=True,
                removed_full_object=removed_full_object,
                removed_thumbnail_object=removed_thumbnail_object,
                message="media deleted",
            )
        )

    return DeleteFileResponse(
        deleted_count=deleted_count,
        results=results,
    )


def lambda_handler(event, context):
    allow_methods = [
        HTTPMethod.POST,
        HTTPMethod.OPTIONS,
    ]

    http_method = get_http_method(event)

    print(
        json.dumps(
            {
                "http_method": http_method,
                "request_context": event.get("requestContext"),
            },
            default=str,
        )
    )

    if http_method == HTTPMethod.OPTIONS.value:
        return build_response_message(
            status_code=HTTPStatus.OK,
            body={"message": "OK"},
            allow_http_methods=allow_methods,
        )

    if http_method != HTTPMethod.POST.value:
        return build_response_message(
            status_code=HTTPStatus.METHOD_NOT_ALLOWED,
            body={
                "message": "Unsupported HTTP method",
                "received_method": http_method,
            },
            allow_http_methods=allow_methods,
        )

    try:
        request = parse_request(event)
        current_user = get_current_user(event)

        response = delete_files(
            request,
            current_user,
        )

        return build_response_message(
            status_code=HTTPStatus.OK,
            body=response.model_dump(mode="json"),
            allow_http_methods=allow_methods,
        )

    except (
        json.JSONDecodeError,
        ValidationError,
        ValueError,
    ) as error:
        print(f"Invalid delete file request: {error}")

        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={
                "message": "Invalid delete file request",
                "error": str(error),
            },
            allow_http_methods=allow_methods,
        )

    except Exception as error:
        print(f"Unexpected delete file error: {error}")

        return build_response_message(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            body={
                "message": "Failed to delete media",
                "error": str(error),
            },
            allow_http_methods=allow_methods,
        )