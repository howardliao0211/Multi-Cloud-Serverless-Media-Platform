from http import HTTPMethod, HTTPStatus
from typing import Iterable, Literal
import json

FRONTEND_ORIGIN = "https://dqgriz8bwuql1.cloudfront.net"


def get_current_user(event):
    return event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]


def get_current_user_email(event):
    return event["requestContext"]["authorizer"]["jwt"]["claims"]["email"]


def get_http_method(event) -> str | None:
    return event.get("httpMethod") or event.get("requestContext", {}).get(
        "http", {}
    ).get("method")


def build_s3_key(key_name: str, media_type: Literal["image", "video"]) -> str:
    assert media_type in ("image", "video")
    return f"{media_type}s/{key_name}"


def build_thumbnail_s3_key(key_name: str) -> str:
    return f"thumbnails/{key_name}"


def build_db_key(owner_id: str, s3_key: str):
    return f"OWNER#{owner_id}#KEY#{s3_key}"


def build_response_message(
    status_code: HTTPStatus | int,
    body: dict,
    allow_http_methods: Iterable[HTTPMethod],
) -> dict:

    return {
        "statusCode": int(status_code),
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": ",".join(allow_http_methods),
        },
        "body": json.dumps(body),
    }


if __name__ == "__main__":
    print(
        build_response_message(
            HTTPStatus.OK,
            {"message": "Hello World"},
            [HTTPMethod.POST, HTTPMethod.OPTIONS],
        )
    )
