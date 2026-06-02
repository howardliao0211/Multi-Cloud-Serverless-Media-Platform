import json
from http import HTTPMethod, HTTPStatus
from typing import List

from pydantic import ValidationError

from shared.aws_resources import get_table, scan_media_record
from shared.query_utils import (
    infer_media_type,
    normalize_tag_counts,
    parse_json_request,
)
from shared.schemas import (
    MediaRecord,
    MediaRecordStatus,
    QuerySpeciesRequest,
    QuerySpeciesResponse,
    QuerySpeciesResult,
)
from shared.utils import build_response_message


table = get_table()


def parse_request(event: dict) -> QuerySpeciesRequest:
    return parse_json_request(event, QuerySpeciesRequest)


def media_contains_species(media_record: MediaRecord, species: str) -> bool:
    tag_counts = normalize_tag_counts(media_record.tags)
    return tag_counts.get(species, 0) >= 1


def shape_query_result(media_record: MediaRecord) -> QuerySpeciesResult:
    media_type = infer_media_type(media_record)
    thumbnail_url = media_record.thumbnail_url if media_type == "image" else None

    return QuerySpeciesResult(
        checksum=media_record.checksum,
        file_name=media_record.file_name,
        media_type=media_type,
        url=media_record.full_url,
        thumbnail_url=thumbnail_url,
        tags=normalize_tag_counts(media_record.tags),
    )


def query_species(request: QuerySpeciesRequest) -> QuerySpeciesResponse:
    results: List[QuerySpeciesResult] = []

    filters = {"upload_status": MediaRecordStatus.ready}

    for media_record in scan_media_record(table, filters):
        if media_contains_species(media_record, request.species):
            results.append(shape_query_result(media_record))

    return QuerySpeciesResponse(
        count=len(results),
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
        response = query_species(request)

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
