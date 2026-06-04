import json
import os
from typing import Literal
from http import HTTPMethod, HTTPStatus

import boto3
from boto3.dynamodb.conditions import Key

from shared.schemas import (
    ChangeVisibilityRequest,
)
from shared.aws_resources import (
    get_bucket_and_name,
    get_table,
    scan_media_record,
    update_media_record_in_db
)
from shared.utils import (
    build_response_message,
    get_current_user
)

s3, bucket_name = get_bucket_and_name()
table = get_table()
URL_EXPIRES_SECONDS = 300


def parse_request(event: dict, ) -> ChangeVisibilityRequest | None:
    body = event.get("body")
    return ChangeVisibilityRequest(**json.loads(body))


def lambda_handler(event, context):

    methods = [
        HTTPMethod.OPTIONS, HTTPMethod.POST
    ]

    if event.get("httpMethod") == "OPTIONS":
        return build_response_message(
            status_code=HTTPStatus.OK,
            body={"message": "OK"},
            allow_http_methods=methods
        )

    request = parse_request(event)
    current_user = get_current_user(event)

    media = scan_media_record(
        table, filters={
            "owner_id": current_user,
            "file_name": request.file_name,
            "checksum": request.checksum,
        }
    )

    if len(media) != 1:
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={
                "message": f"Number of fetched media is not 1: {len(media)}"},
            allow_http_methods=methods
        )

    media = media[0]
    update_media_record_in_db(
        table, media.key, updates={
            "visibility": request.visibility
        }
    )

    return build_response_message(
        status_code=HTTPStatus.OK,
        body={"message": f"Visibility updated to {request.visibility.value}"},
        allow_http_methods=methods
    )
