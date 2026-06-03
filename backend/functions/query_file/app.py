from http import HTTPMethod, HTTPStatus

from shared.schemas import QueryFileResponse
from shared.utils import build_response_message


def build_not_implemented_response() -> QueryFileResponse:
    return QueryFileResponse(
        detected_tags={},
        count=0,
        results=[],
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

    response = build_not_implemented_response()

    return build_response_message(
        status_code=HTTPStatus.NOT_IMPLEMENTED,
        body={
            **response.model_dump(mode="json"),
            "message": "query_file upload parsing is not implemented yet",
        },
        allow_http_methods=allow_methods,
    )
