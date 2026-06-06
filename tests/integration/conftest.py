import os
import uuid

import boto3
import pytest

from botocore.config import Config
from boto3.dynamodb.conditions import Attr


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: tests that call deployed AWS resources",
    )


def _delete_media_record_by_key(table, key: str):
    response = table.delete_item(
        Key={
            "key": key,
        },
        ReturnValues="ALL_OLD",
    )

    deleted_item = response.get("Attributes")

    if deleted_item is None:
        print(f"No DynamoDB item deleted. Key may not exist: {key}")
    else:
        print(f"Deleted DynamoDB item: {key}")

    return deleted_item


def _scan_integration_test_media_records(table, test_user_id: str):
    """
    Find all media records that belong to integration tests.

    This scans by:
    - owner_id == integration-test-user
    """

    filter_expression = (
        Attr("owner_id").eq(test_user_id)
    )

    items = []
    last_evaluated_key = None

    while True:
        scan_kwargs = {
            "FilterExpression": filter_expression,
        }

        if last_evaluated_key:
            scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))

        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break

    return items


def _cleanup_integration_test_media_records(table, test_user_id: str):
    items = _scan_integration_test_media_records(table, test_user_id)

    print(f"Found {len(items)} integration-test media record(s) to delete.")

    deleted_count = 0
    skipped_count = 0

    for item in items:
        key = item.get("key")

        if not key:
            print(f"Skipping item without 'key': {item}")
            skipped_count += 1
            continue

        deleted_item = _delete_media_record_by_key(table, key)

        if deleted_item is not None:
            deleted_count += 1

    print(
        f"Integration-test media cleanup complete. "
        f"Deleted={deleted_count}, skipped={skipped_count}"
    )


@pytest.fixture(scope="session")
def integration_config():
    return {
        "region": "us-east-1",
        "bucket": "aussie-eco-len-bucket-12345",
        "table": "aussie-eco-len-media",
        "get_signed_url_function": "get_signed_url",
        "get_private_media_function": "get_private_media",
        "get_public_media_function": "get_public_media",
        "tag_image_function": "tag_image",
        "tag_video_function": "tag_video",
        "get_upload_status_function": "get_upload_status",
        "query_tags_function": "query_tags",
        "delete_file_function": "delete_file",
        "test_user_id": "integration-test-user",
        "test_video_path": os.getenv("TEST_VIDEO_PATH", "./integration/test_video.mp4")
    }


@pytest.fixture(scope="session")
def aws_clients(integration_config):
    region = integration_config["region"]

    dynamodb = boto3.resource("dynamodb", region_name=region)

    lambda_config = Config(
        read_timeout=900,
        connect_timeout=10,
        retries={"max_attempts": 1},
    )

    return {
        "s3": boto3.client("s3", region_name=region),
        "lambda": boto3.client(
            "lambda",
            region_name=region,
            config=lambda_config,
        ),
        "table": dynamodb.Table(integration_config["table"]),
    }


@pytest.fixture()
def unique_id():
    return f"it-{uuid.uuid4().hex}"


@pytest.fixture(scope="session", autouse=True)
def cleanup_integration_test_media_records(aws_clients, integration_config):
    table = aws_clients["table"]
    test_user_id = integration_config["test_user_id"]

    # Cleanup stale records from previous failed test runs.
    _cleanup_integration_test_media_records(table, test_user_id)

    yield

    # Cleanup records created by this test run.
    _cleanup_integration_test_media_records(table, test_user_id)
