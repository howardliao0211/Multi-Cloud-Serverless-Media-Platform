import json
from http import HTTPMethod, HTTPStatus
from typing import Optional

from pydantic import ValidationError

from shared.aws_resources import get_table, scan_media_record, update_media_record_in_db
from shared.query_utils import parse_json_request
from shared.schemas import EditTagsRequest, EditTagsResponse, EditTagsResult, MediaRecord
from shared.species import normalize_species_tag
from shared.utils import build_response_message, get_current_user


table = get_table()


def parse_request(event: dict) -> EditTagsRequest:
    return parse_json_request(event, EditTagsRequest)


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


def normalize_requested_species(tags: list[str]) -> tuple[list[str], list[str]]:
    valid_tags: list[str] = []
    invalid_tags: list[str] = []

    for tag in tags:
        normalized_tag = normalize_species_tag(tag)

        if normalized_tag is None:
            invalid_tags.append(tag)
            continue

        valid_tags.append(normalized_tag)

    return list(dict.fromkeys(valid_tags)), invalid_tags


def add_tags_to_media(media_record: MediaRecord, tags: list[str]) -> dict[str, int]:
    updated_tags = dict(media_record.tags)

    for tag in tags:
        updated_tags[tag] = updated_tags.get(tag, 0) + 1

    return updated_tags


def remove_tags_from_media(media_record: MediaRecord, tags: list[str]) -> dict[str, int]:
    updated_tags = dict(media_record.tags)

    for tag in tags:
        if tag not in updated_tags:
            continue

        updated_tags[tag] -= 1

        if updated_tags[tag] <= 0:
            updated_tags.pop(tag)

    return updated_tags


def build_add_tags_result(
    url: str,
    media_record: MediaRecord,
    tags: dict[str, int],
) -> EditTagsResult:
    return EditTagsResult(
        url=url,
        updated=True,
        checksum=media_record.checksum,
        file_name=media_record.file_name,
        tags=tags,
        message="tags added",
    )


def build_remove_tags_result(
    url: str,
    media_record: MediaRecord,
    tags: dict[str, int],
) -> EditTagsResult:
    return EditTagsResult(
        url=url,
        updated=True,
        checksum=media_record.checksum,
        file_name=media_record.file_name,
        tags=tags,
        message="tags removed",
    )


def apply_edit_tags(request: EditTagsRequest, current_user: str) -> EditTagsResponse:
    results: list[EditTagsResult] = []
    updated_count = 0
    valid_tags, invalid_tags = normalize_requested_species(request.tags)
    media_records = scan_media_record(table)

    for url in request.urls:
        media_record, media_exists = find_user_media_by_url(
            media_records,
            url,
            current_user,
        )

        if not media_exists:
            results.append(
                EditTagsResult(
                    url=url,
                    updated=False,
                    message="media not found",
                )
            )
            continue

        if media_record is None:
            results.append(
                EditTagsResult(
                    url=url,
                    updated=False,
                    message="forbidden: media is owned by another user",
                )
            )
            continue

        if invalid_tags:
            results.append(
                EditTagsResult(
                    url=url,
                    updated=False,
                    checksum=media_record.checksum,
                    file_name=media_record.file_name,
                    tags=media_record.tags,
                    message=f"invalid species tags: {', '.join(invalid_tags)}",
                )
            )
            continue

        if request.operation == 1:
            updated_tags = add_tags_to_media(media_record, valid_tags)
            result = build_add_tags_result(url, media_record, updated_tags)
        else:
            updated_tags = remove_tags_from_media(media_record, valid_tags)
            result = build_remove_tags_result(url, media_record, updated_tags)

        update_media_record_in_db(
            table,
            media_record.file_name,
            media_record.checksum,
            {"tags": updated_tags},
        )

        updated_count += 1
        results.append(result)

    return EditTagsResponse(
        updated_count=updated_count,
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
        response = apply_edit_tags(request, current_user)

        return build_response_message(
            status_code=HTTPStatus.OK,
            body=response.model_dump(mode="json"),
            allow_http_methods=allow_methods,
        )
    except (json.JSONDecodeError, ValidationError, ValueError) as error:
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Invalid edit tags request", "error": str(error)},
            allow_http_methods=allow_methods,
        )
