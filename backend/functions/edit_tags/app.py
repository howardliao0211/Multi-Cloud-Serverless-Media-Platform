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
) -> Optional[MediaRecord]:
    matching_records = find_media_records_by_url(media_records, url)

    for media_record in matching_records:
        if media_record.owner_id == current_user:
            return media_record

    return None


def normalize_requested_tag_deltas(
    tag_deltas: list[dict[str, int]],
) -> tuple[dict[str, int], list[str]]:
    valid_tag_deltas: dict[str, int] = {}
    invalid_tags: list[str] = []

    for tag_delta in tag_deltas:
        raw_tag, delta = next(iter(tag_delta.items()))
        normalized_tag = normalize_species_tag(raw_tag)

        if normalized_tag is None:
            invalid_tags.append(raw_tag)
            continue

        valid_tag_deltas[normalized_tag] = (
            valid_tag_deltas.get(normalized_tag, 0) + delta
        )

    return {
        tag: delta
        for tag, delta in valid_tag_deltas.items()
        if delta != 0
    }, invalid_tags


def apply_tag_deltas_to_media(
    media_record: MediaRecord,
    tag_deltas: dict[str, int],
) -> dict[str, int]:
    updated_tags = dict(media_record.tags)

    for tag, delta in tag_deltas.items():
        next_count = updated_tags.get(tag, 0) + delta

        if next_count <= 0:
            updated_tags.pop(tag, None)
            continue

        updated_tags[tag] = next_count

    return updated_tags


def apply_edit_tags(request: EditTagsRequest, current_user: str) -> EditTagsResponse:
    results: list[EditTagsResult] = []
    updated_count = 0
    valid_tag_deltas, invalid_tags = normalize_requested_tag_deltas(request.tags)
    media_records = scan_media_record(table)

    for url in request.urls:
        media_record = find_user_media_by_url(
            media_records,
            url,
            current_user,
        )

        if media_record is None:
            results.append(
                EditTagsResult(
                    url=url,
                    updated=False,
                    message="media not found",
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

        if not valid_tag_deltas:
            results.append(
                EditTagsResult(
                    url=url,
                    updated=False,
                    checksum=media_record.checksum,
                    file_name=media_record.file_name,
                    tags=media_record.tags,
                    message="no tag changes requested",
                )
            )
            continue

        updated_tags = apply_tag_deltas_to_media(media_record, valid_tag_deltas)
        result = EditTagsResult(
            url=url,
            updated=True,
            checksum=media_record.checksum,
            file_name=media_record.file_name,
            tags=updated_tags,
            message="tags updated",
        )

        update_media_record_in_db(
            table,
            media_record.key,
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
