import json
from http import HTTPMethod, HTTPStatus
from typing import Any, Dict, List

from pydantic import ValidationError

from shared.aws_resources import get_table
from shared.query_utils import (
    infer_media_type,
    is_ready_media,
    normalize_tag_counts,
    parse_json_request,
    scan_media,
)
from shared.schemas import (
    QuerySpeciesRequest,
    QuerySpeciesResponse,
    QuerySpeciesResult,
)
from shared.utils import build_response_message


table = get_table()


def parse_request(event: dict) -> QuerySpeciesRequest:
    return parse_json_request(event, QuerySpeciesRequest)


def media_contains_species(item: Dict[str, Any], species: str) -> bool:
    tag_counts = normalize_tag_counts(item.get("tags"))
    return tag_counts.get(species, 0) >= 1


def shape_query_result(item: Dict[str, Any]) -> QuerySpeciesResult:
    media_type = infer_media_type(item)
    thumbnail_url = item.get("thumbnail_url") if media_type == "image" else None

    return QuerySpeciesResult(
        checksum=item["checksum"],
        file_name=item["file_name"],
        media_type=media_type,
        url=item.get("full_url"),
        thumbnail_url=thumbnail_url,
        tags=normalize_tag_counts(item.get("tags")),
    )


def query_species(request: QuerySpeciesRequest) -> QuerySpeciesResponse:
    results: List[QuerySpeciesResult] = []

    for item in scan_media(table):
        if not is_ready_media(item):
            continue

        if media_contains_species(item, request.species):
            results.append(shape_query_result(item))

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
