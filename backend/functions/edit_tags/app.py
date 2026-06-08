from typing import TypedDict
import json
from http import HTTPMethod, HTTPStatus
from typing import Optional

from pydantic import ValidationError

from shared.aws_resources import get_table, scan_media_record, update_media_record_in_db
from shared.query_utils import parse_json_request
from shared.schemas import EditTagsRequest, EditTagsResponse, EditTagsResult, MediaRecord
from shared.utils import build_response_message, get_current_user


table = get_table()


class TagDelta(TypedDict):
    raw_tag: str
    delta: int


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


def build_requested_tag_deltas(
    request: EditTagsRequest,
) -> dict[str, TagDelta]:
    tag_deltas: dict[str, TagDelta] = {}
    direction = 1 if request.operation_key == 1 else -1

    for tag_count in request.tags:
        raw_tag, count = next(iter(tag_count.items()))

        cleaned_tag = raw_tag.strip()
        normalized_tag = cleaned_tag.lower()
        delta = count * direction

        existing = tag_deltas.get(
            normalized_tag,
            {
                "raw_tag": cleaned_tag,
                "delta": 0,
            },
        )

        tag_deltas[normalized_tag] = {
            # Internal lookup is normalized, but raw request casing is preserved.
            # If duplicate tags appear, this keeps the latest raw casing.
            "raw_tag": cleaned_tag,
            "delta": existing["delta"] + delta,
        }

    return {
        normalized_tag: tag_delta
        for normalized_tag, tag_delta in tag_deltas.items()
        if tag_delta["delta"] != 0
    }


def apply_tag_deltas_to_media(
    media_record: MediaRecord,
    tag_deltas: dict[str, TagDelta],
) -> dict[str, int]:
    updated_tags = dict(media_record.tags)

    existing_tag_lookup: dict[str, str] = {
        existing_tag.strip().lower(): existing_tag
        for existing_tag in updated_tags
    }

    for normalized_tag, tag_delta in tag_deltas.items():
        requested_raw_tag = tag_delta["raw_tag"]
        delta = tag_delta["delta"]

        # Existing tag: preserve casing from media_record.tags.
        # New tag: preserve casing from request.
        tag_key = existing_tag_lookup.get(
            normalized_tag,
            requested_raw_tag,
        )

        next_count = updated_tags.get(tag_key, 0) + delta

        if next_count <= 0:
            updated_tags.pop(tag_key, None)
            existing_tag_lookup.pop(normalized_tag, None)
            continue

        updated_tags[tag_key] = next_count
        existing_tag_lookup[normalized_tag] = tag_key

    return updated_tags


def apply_edit_tags(request: EditTagsRequest, current_user: str) -> EditTagsResponse:
    results: list[EditTagsResult] = []
    updated_count = 0
    tag_deltas = build_requested_tag_deltas(request)
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

        if not tag_deltas:
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

        updated_tags = apply_tag_deltas_to_media(media_record, tag_deltas)
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
