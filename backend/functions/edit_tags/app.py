import json
from http import HTTPMethod, HTTPStatus

from pydantic import ValidationError

from shared.query_utils import parse_json_request
from shared.schemas import EditTagsRequest, EditTagsResponse, EditTagsResult
from shared.utils import build_response_message


def parse_request(event: dict) -> EditTagsRequest:
    return parse_json_request(event, EditTagsRequest)


def build_not_implemented_response(request: EditTagsRequest) -> EditTagsResponse:
    return EditTagsResponse(
        updated_count=0,
        results=[
            EditTagsResult(
                url=url,
                updated=False,
                message="edit_tags update logic is not implemented yet",
            )
            for url in request.urls
        ],
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
        response = build_not_implemented_response(request)

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
