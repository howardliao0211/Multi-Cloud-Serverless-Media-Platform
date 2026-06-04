import json
import os
from typing import Literal
from http import HTTPMethod, HTTPStatus

import boto3
from boto3.dynamodb.conditions import Key

from shared.schemas import (
    MediaRecord,
    GetMediaUploadStatus,
    MediaUploadStatusResponse
)
from shared.aws_resources import (
    get_bucket_and_name,
    get_table,
    scan_media_record,
)
from shared.utils import (
    build_response_message,
    get_current_user
)

s3, bucket_name = get_bucket_and_name()
table = get_table()
URL_EXPIRES_SECONDS = 300


def parse_request(event: dict, ) -> GetMediaUploadStatus | None:
    query_params = event.get("queryStringParameters") or {}
    return GetMediaUploadStatus(**query_params)


def lambda_handler(event, context):

    methods = [
        HTTPMethod.OPTIONS, HTTPMethod.GET
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
    res = MediaUploadStatusResponse(
        upload_status=media.upload_status,
        error_message=media.error_message
    )

    return build_response_message(
        status_code=HTTPStatus.OK,
        body=res.model_dump(mode="json"),
        allow_http_methods=methods
    )
