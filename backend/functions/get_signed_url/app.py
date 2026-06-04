import json
import os
from typing import Literal
from http import HTTPMethod, HTTPStatus

from boto3.dynamodb.conditions import Key

from shared.schemas import (
    MediaRecord,
    UploadUrlRequest,
    UploadUrlResponse
)
from shared.aws_resources import (
    get_bucket_and_name,
    get_table,
    create_new_media_record,
)
from shared.utils import (
    build_response_message,
    get_current_user,
    build_db_key,
    build_s3_key,
)

s3, bucket_name = get_bucket_and_name()
table = get_table()
URL_EXPIRES_SECONDS = 300


def parse_request(event: dict, ) -> UploadUrlRequest | None:
    body = event.get("body")
    return UploadUrlRequest(**json.loads(body))


def generate_upload_url(s3_key: str, file_name: str, checksum: str, owner_id: str) -> str:
    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": bucket_name,
            "Key": s3_key,
            "Metadata": {
                "file_name": file_name,
                "checksum": checksum,
                "owner_id": owner_id
            },
        },
        ExpiresIn=URL_EXPIRES_SECONDS,
    )


def is_duplicated(key: str) -> bool:
    result = table.query(
        KeyConditionExpression=Key("key").eq(key),
        Limit=1,
    )
    return result.get("Count", 0) > 0


def lambda_handler(event, context):

    if event.get("httpMethod") == "OPTIONS":
        return build_response_message(
            status_code=HTTPStatus.OK,
            body={"message": "OK"},
            allow_http_methods=[HTTPMethod.OPTIONS]
        )

    owner_id = get_current_user(event)
    request = parse_request(event)

    file_ext = request.file_name.split(".")[-1]
    s3_filename = f"{request.checksum}.{file_ext}"
    s3_key = build_s3_key(s3_filename, request.media_type.value)
    db_key = build_db_key(owner_id, s3_key)

    duplicate = is_duplicated(db_key)
    upload_url = None
    expires_in = None

    if duplicate:

        res = UploadUrlResponse(
            duplicate=duplicate,
            upload_url=upload_url,
            expires_in=expires_in
        )

        return build_response_message(
            status_code=HTTPStatus.OK,
            body=res.model_dump(mode="json"),
            allow_http_methods=[HTTPMethod.POST]
        )

    upload_url = generate_upload_url(
        s3_key, request.file_name, request.checksum, owner_id)
    expires_in = URL_EXPIRES_SECONDS

    media = MediaRecord(
        owner_id=owner_id,
        checksum=request.checksum,
        file_name=request.file_name,
        full_key=s3_key,
        visibility=request.visibility.value
    )

    create_new_media_record(
        table, media
    )

    res = UploadUrlResponse(
        duplicate=duplicate,
        upload_url=upload_url,
        expires_in=expires_in
    )

    return build_response_message(
        status_code=HTTPStatus.OK,
        body=res.model_dump(mode="json"),
        allow_http_methods=[HTTPMethod.POST]
    )
