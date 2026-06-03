import base64
from http import HTTPMethod, HTTPStatus
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from typing import Mapping

from shared.schemas import QueryFileResponse
from shared.utils import build_response_message


@dataclass
class UploadedQueryFile:
    filename: str
    content_type: str
    content: bytes


def get_header(headers: Mapping[str, str], name: str) -> str | None:
    name_lower = name.lower()

    for key, value in headers.items():
        if key.lower() == name_lower:
            return value

    return None


def get_request_body_bytes(event: dict) -> bytes:
    body = event.get("body") or ""

    if event.get("isBase64Encoded"):
        return base64.b64decode(body)

    return body.encode("utf-8")


def parse_multipart_file(event: dict) -> UploadedQueryFile:
    headers = event.get("headers") or {}
    content_type = get_header(headers, "content-type")

    if not content_type or "multipart/form-data" not in content_type:
        raise ValueError("Content-Type must be multipart/form-data")

    body_bytes = get_request_body_bytes(event)
    raw_message = (
        f"Content-Type: {content_type}\r\n"
        "MIME-Version: 1.0\r\n"
        "\r\n"
    ).encode("utf-8") + body_bytes

    message = BytesParser(policy=default).parsebytes(raw_message)

    if not message.is_multipart():
        raise ValueError("Request body is not valid multipart data")

    for part in message.iter_parts():
        filename = part.get_filename()

        if not filename:
            continue

        content = part.get_payload(decode=True) or b""

        if not content:
            raise ValueError("Uploaded query file must not be empty")

        return UploadedQueryFile(
            filename=filename,
            content_type=part.get_content_type(),
            content=content,
        )

    raise ValueError("No uploaded file found in multipart request")


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

    try:
        uploaded_file = parse_multipart_file(event)
    except ValueError as error:
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Invalid query file request", "error": str(error)},
            allow_http_methods=allow_methods,
        )

    response = build_not_implemented_response()

    return build_response_message(
        status_code=HTTPStatus.NOT_IMPLEMENTED,
        body={
            **response.model_dump(mode="json"),
            "message": "query_file ML matching is not implemented yet",
            "uploaded_file": {
                "filename": uploaded_file.filename,
                "content_type": uploaded_file.content_type,
                "size_bytes": len(uploaded_file.content),
            },
        },
        allow_http_methods=allow_methods,
    )
