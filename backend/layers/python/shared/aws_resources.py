from pathlib import Path

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.config import Config
from typing import Literal, Tuple, Any, Optional, List
from enum import Enum
from urllib.parse import quote
from shared.schemas import MediaRecord, MediaRecordStatus

BUCKET_NAME = "aussie-eco-len-bucket-12345"
TABLE_NAME = "aussie-eco-len-media"
REGION_NAME = "us-east-1"


def get_bucket_and_name():
    s3 = boto3.client(
        "s3",
        region_name="us-east-1",
        config=Config(signature_version="s3v4")
    )
    return s3, BUCKET_NAME


def get_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


def get_s3_object_head_and_url(s3_key: str) -> Tuple[dict, str]:
    """
    Return the S3 object's head and permanent object URL.

    Head = 
    {
        "ContentLength": 123456,
        "ContentType": "image/jpeg",
        "LastModified": datetime(...),
        "ETag": '"abc123..."',
        "Metadata": {
            "filename": "filename"
        },
        "StorageClass": "STANDARD",
        "ServerSideEncryption": "AES256",
        "ChecksumSHA256": "...",
        "VersionId": "...",
    }
    """

    s3, bucket_name = get_bucket_and_name()

    head = s3.head_object(
        Bucket=bucket_name,
        Key=s3_key,
    )

    encoded_key = quote(s3_key, safe="/")

    object_url = (
        f"https://{bucket_name}.s3.{REGION_NAME}.amazonaws.com/{encoded_key}"
    )

    return head, object_url


def update_media_record_in_db(table, key: str, updates: dict[str, Any]) -> None:
    """
    Dynamically update fields of a MediaRecord in DynamoDB.

    Example:
        update_media_record(
            checksum="abc123",
            updates={
                "upload_status": "ready",
                "tags": {"tree": 2, "kangaroo": 1},
            },
        )
    """

    if not updates:
        return

    allowed_fields = set(MediaRecord.model_fields.keys())
    non_updatable_fields = {"key", "owner_id", "full_key", "checksum"}

    invalid_fields = set(updates.keys()) - allowed_fields
    if invalid_fields:
        raise ValueError(f"Invalid update fields: {invalid_fields}")

    blocked_fields = set(updates.keys()) & non_updatable_fields
    if blocked_fields:
        raise ValueError(f"Cannot update primary key fields: {blocked_fields}")

    update_expression_parts = []
    expression_attribute_names = {}
    expression_attribute_values = {}

    for index, (field, value) in enumerate(updates.items()):
        field_name = f"#field_{index}"
        field_value = f":value_{index}"

        update_expression_parts.append(f"{field_name} = {field_value}")
        expression_attribute_names[field_name] = field
        expression_attribute_values[field_value] = value

    table.update_item(
        Key={
            "key": key,
        },
        UpdateExpression="SET " + ", ".join(update_expression_parts),
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values,
    )


def download_s3_file(s3, bucket: str, s3_key: str, local_path: str) -> None:

    if Path(local_path).exists():
        return

    s3.download_file(
        Bucket=bucket,
        Key=s3_key,
        Filename=local_path,
    )


def create_new_media_record(table, media: MediaRecord):
    table.put_item(
        Item=media.model_dump(mode="json"),
        ConditionExpression=(
            "attribute_not_exists(#key) "
        ),
        ExpressionAttributeNames={
            "#key": "key",
        },
    )


def is_media_record_processing(
    table,
    key
) -> bool:
    """
    Check whether this media record should be processed.

    Returns:
        True  -> record does not exist, or previous processing failed
        False -> record exists and is not failed
    """
    response = table.get_item(
        Key={
            "key": key,
        },
        ConsistentRead=True,
    )

    item = response.get("Item")

    if item is None:
        return True

    upload_status = item["upload_status"]
    return upload_status not in (
        MediaRecordStatus.pending,
        MediaRecordStatus.failed,
    )


def scan_media_record(
    table,
    filters: Optional[dict[str, Any]] = None,
) -> List[MediaRecord]:
    """
    Scan media records using optional equality filters.

    Example:
        scan_media_record({
            "owner_id": "user123",
            "visibility": MediaVisibility.private,
        })

    Returns:
        List[MediaRecord]
    """

    def to_filter_value(value: Any) -> Any:
        """
        Convert Python values to DynamoDB filter-compatible values.
        """
        if isinstance(value, Enum):
            return value.value

        return value

    filters = filters or {}

    allowed_fields = set(MediaRecord.model_fields.keys())

    invalid_fields = set(filters.keys()) - allowed_fields
    if invalid_fields:
        raise ValueError(f"Invalid filter fields: {invalid_fields}")

    filter_expression = None

    for field, value in filters.items():
        condition = Attr(field).eq(to_filter_value(value))

        if filter_expression is None:
            filter_expression = condition
        else:
            filter_expression = filter_expression & condition

    items = []
    last_evaluated_key = None

    while True:
        scan_kwargs = {}

        if filter_expression is not None:
            scan_kwargs["FilterExpression"] = filter_expression

        if last_evaluated_key:
            scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

        response = table.scan(**scan_kwargs)

        items.extend(response.get("Items", []))

        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break

    return [
        MediaRecord.model_validate(item)
        for item in items
    ]
