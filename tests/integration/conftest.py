import os
import uuid

import boto3
import pytest

from botocore.config import Config


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: tests that call deployed AWS resources",
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
        "test_user_id": "integration-test-user",
        "test_video_path": "./integration/test_video.mp4"
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
