import json
from datetime import datetime, timezone
from http import HTTPMethod, HTTPStatus
from pathlib import Path
from uuid import uuid4

import boto3
from pydantic import ValidationError

from shared.aws_resources import get_bucket_and_name, get_table
from shared.query_utils import parse_json_request
from shared.schemas import QueryFileJobResponse, QueryFileJobStatus, QueryFileRequest
from shared.utils import build_response_message, get_current_user, get_http_method


s3, bucket_name = get_bucket_and_name()
table = get_table()
lambda_client = boto3.client("lambda")
WORKER_FUNCTION_NAME = "query_file"
QUERY_UPLOAD_PREFIX = "query_uploads"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_request(event: dict) -> QueryFileRequest:
    return parse_json_request(event, QueryFileRequest)


def validate_query_key_owner(query_key: str, current_user: str) -> None:
    expected_prefix = f"{QUERY_UPLOAD_PREFIX}/{current_user}/"

    if not query_key.startswith(expected_prefix):
        raise ValueError("query_key does not belong to the current user")


def validate_query_object(query_key: str, current_user: str) -> tuple[str, str]:
    head = s3.head_object(Bucket=bucket_name, Key=query_key)
    metadata = head.get("Metadata") or {}

    if metadata.get("owner_id") != current_user:
        raise ValueError("query object owner does not match the current user")

    if metadata.get("purpose") != "query_file":
        raise ValueError("query object was not uploaded for query_file")

    file_name = metadata.get("file_name") or Path(query_key).name
    content_type = head.get("ContentType") or ""

    return file_name, content_type


def build_job_key(job_id: str) -> str:
    return f"QUERY_JOB#{job_id}"


def create_job_record(
    job_id: str,
    owner_id: str,
    query_key: str,
    file_name: str,
    content_type: str,
) -> None:
    now = utc_now()

    table.put_item(
        Item={
            "key": build_job_key(job_id),
            "job_id": job_id,
            "owner_id": owner_id,
            "query_key": query_key,
            "file_name": file_name,
            "content_type": content_type,
            "status": QueryFileJobStatus.pending.value,
            "detected_tags": {},
            "count": 0,
            "results": [],
            "error_message": None,
            "created_at": now,
            "updated_at": now,
        },
        ConditionExpression="attribute_not_exists(#key)",
        ExpressionAttributeNames={"#key": "key"},
    )


def invoke_worker(job_id: str, owner_id: str, query_key: str) -> None:
    lambda_client.invoke(
        FunctionName=WORKER_FUNCTION_NAME,
        InvocationType="Event",
        Payload=json.dumps(
            {
                "job_id": job_id,
                "owner_id": owner_id,
                "query_key": query_key,
            }
        ).encode("utf-8"),
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
        validate_query_key_owner(request.query_key, current_user)
        file_name, content_type = validate_query_object(
            request.query_key,
            current_user,
        )
        job_id = uuid4().hex

        create_job_record(
            job_id,
            current_user,
            request.query_key,
            file_name,
            content_type,
        )
        invoke_worker(job_id, current_user, request.query_key)

        response = QueryFileJobResponse(
            job_id=job_id,
            status=QueryFileJobStatus.pending,
        )

        return build_response_message(
            status_code=HTTPStatus.ACCEPTED,
            body=response.model_dump(mode="json"),
            allow_http_methods=allow_methods,
        )

    except (ValidationError, ValueError) as error:
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Invalid query file job request", "error": str(error)},
            allow_http_methods=allow_methods,
        )
    except Exception as error:
        return build_response_message(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            body={"message": "Failed to create query file job", "error": str(error)},
            allow_http_methods=allow_methods,
        )
