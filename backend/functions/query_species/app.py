import json
from http import HTTPMethod, HTTPStatus
from typing import List

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
    QuerySpeciesRequest,
    MediaRecordResponse,
    GetMediaResponse
)
from shared.utils import build_response_message, get_current_user


s3, bucket_name = get_bucket_and_name()
table = get_table()


def parse_request(event: dict) -> QuerySpeciesRequest:
    return parse_json_request(event, QuerySpeciesRequest)


def media_contains_species(media_record: MediaRecord, species: str) -> bool:
    tag_counts = normalize_tag_counts(media_record.tags)
    return tag_counts.get(species, 0) >= 1


def query_species(request: QuerySpeciesRequest, current_user: str) -> GetMediaResponse:
    results: List[MediaRecordResponse] = []

    filters = {"upload_status": MediaRecordStatus.ready}

    for media_record in scan_media_record(table, filters):
        if not can_query_media(media_record, current_user):
            continue

        if media_contains_species(media_record, request.species):
            results.append(
                MediaRecordResponse.from_media_record(
                    media_record, s3, bucket_name, 300
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
        response = query_species(request, current_user)

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
