from http import HTTPMethod, HTTPStatus
from typing import Iterable
from shared.schemas import MediaRecord, MediaRecordResponse
import json


FRONTEND_ORIGIN = "https://dqgriz8bwuql1.cloudfront.net"


def get_current_user(event):
    return event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]

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


def build_media_record_response(
    media_record: MediaRecord,
    s3,
    bucket_name: str,
    expires_seconds
):
    full_presigned_url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": bucket_name,
            "Key": media_record.full_key,
        },
        ExpiresIn=expires_seconds,
    )

    thumbnail_presigned_url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": bucket_name,
            "Key": media_record.thumbnail_key,
        },
        ExpiresIn=expires_seconds,
    )

    return MediaRecordResponse(
        owner_id=media_record.owner_id,
        file_name=media_record.file_name,
        visibility=media_record.visibility,
        full_presigned_url=full_presigned_url,
        thumbnail_presigned_url=thumbnail_presigned_url,
        tags=media_record.tags,
        upload_status=media_record.upload_status,
        error_message=media_record.error_message,
    )

if __name__ == "__main__":
    print(
        build_response_message(
            HTTPStatus.OK, {"message": "Hello World"}, [
                HTTPMethod.POST, HTTPMethod.OPTIONS]
        )
    )
