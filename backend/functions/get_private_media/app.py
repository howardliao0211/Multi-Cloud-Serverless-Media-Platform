from typing import List, Optional
import json
import os
from typing import Literal, List
from http import HTTPMethod, HTTPStatus

import boto3
from boto3.dynamodb.conditions import Key

from shared.schemas import (
    MediaRecord,
    MediaVisibility,
    GetMediaResponse,
)
from shared.aws_resources import (
    get_bucket_and_name,
    get_table,
    scan_media_record
)
from shared.utils import (
    build_response_message,
    build_media_record_response,
    get_current_user
)

s3, bucket_name = get_bucket_and_name()
table = get_table()
URL_EXPIRES_SECONDS = 300


def get_private_media(
    owner_id: str,
) -> List[MediaRecord]:
    filters = {
        "owner_id": owner_id,
        "visibility": MediaVisibility.private
    }

    return scan_media_record(table, filters)


def lambda_handler(event, context):

    allow_methods = [HTTPMethod.OPTIONS, HTTPMethod.GET]

    if event.get("httpMethod") == "OPTIONS":
        return build_response_message(
            status_code=HTTPStatus.OK,
            body={"message": "OK"},
            allow_http_methods=allow_methods
        )

    owner_id = get_current_user(event)
    media = get_private_media(owner_id)
    media_response = [
        build_media_record_response(
            item,
            s3,
            bucket_name,
            URL_EXPIRES_SECONDS
        )
        for item in media
    ]
    res = GetMediaResponse(
        media_records=media_response
    )
    return build_response_message(
        status_code=HTTPStatus.OK,
        body=res.model_dump(),
        allow_http_methods=allow_methods
    )
