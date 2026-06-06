from http import HTTPMethod, HTTPStatus
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from shared.aws_resources import get_bucket_and_name
from shared.query_utils import parse_json_request
from shared.schemas import (
    MediaType,
    QueryFileUploadUrlRequest,
    QueryFileUploadUrlResponse,
)
from shared.utils import build_response_message, get_current_user, get_http_method


s3, bucket_name = get_bucket_and_name()
URL_EXPIRES_SECONDS = 300
QUERY_UPLOAD_PREFIX = "query_uploads"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}


def parse_request(event: dict) -> QueryFileUploadUrlRequest:
    return parse_json_request(event, QueryFileUploadUrlRequest)


def validate_query_media(request: QueryFileUploadUrlRequest) -> str:
    suffix = Path(request.file_name).suffix.lower()

    if not suffix:
        raise ValueError("file_name must include an extension")

    if request.media_type == MediaType.image and suffix not in IMAGE_EXTENSIONS:
        raise ValueError("query image must be JPG, JPEG, PNG, or WEBP")

    if request.media_type == MediaType.video and suffix not in VIDEO_EXTENSIONS:
        raise ValueError("query video must be MP4, MOV, MKV, or WEBM")

    content_family = request.content_type.split("/", 1)[0].lower()

    if content_family != request.media_type.value:
        raise ValueError("content_type must match media_type")

    return suffix


def build_query_upload_key(owner_id: str, suffix: str) -> str:
    return f"{QUERY_UPLOAD_PREFIX}/{owner_id}/{uuid4().hex}{suffix}"


def build_upload_headers(
    request: QueryFileUploadUrlRequest,
    owner_id: str,
) -> dict[str, str]:
    return {
        "Content-Type": request.content_type,
        "x-amz-meta-owner_id": owner_id,
        "x-amz-meta-file_name": request.file_name,
        "x-amz-meta-media_type": request.media_type.value,
        "x-amz-meta-purpose": "query_file",
    }


def generate_query_upload_url(
    query_key: str,
    request: QueryFileUploadUrlRequest,
    owner_id: str,
) -> str:
    return s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": bucket_name,
            "Key": query_key,
            "ContentType": request.content_type,
            "Metadata": {
                "owner_id": owner_id,
                "file_name": request.file_name,
                "media_type": request.media_type.value,
                "purpose": "query_file",
            },
        },
        ExpiresIn=URL_EXPIRES_SECONDS,
    )


def lambda_handler(event, context):
    allow_methods = [HTTPMethod.POST, HTTPMethod.OPTIONS]
    http_method = get_http_method(event)

    if http_method == "OPTIONS":
        return build_response_message(
            status_code=HTTPStatus.OK,
            body={"message": "OK"},
            allow_http_methods=allow_methods,
        )

    if http_method != "POST":
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Unsupported HTTP method"},
            allow_http_methods=allow_methods,
        )

    try:
        current_user = get_current_user(event)
        request = parse_request(event)
        suffix = validate_query_media(request)
        query_key = build_query_upload_key(current_user, suffix)
        upload_url = generate_query_upload_url(query_key, request, current_user)
        upload_headers = build_upload_headers(request, current_user)

        response = QueryFileUploadUrlResponse(
            upload_url=upload_url,
            query_key=query_key,
            expires_in=URL_EXPIRES_SECONDS,
            upload_headers=upload_headers,
        )

        return build_response_message(
            status_code=HTTPStatus.OK,
            body=response.model_dump(mode="json"),
            allow_http_methods=allow_methods,
        )

    except (ValidationError, ValueError) as error:
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Invalid query upload URL request", "error": str(error)},
            allow_http_methods=allow_methods,
        )
