import os
import uuid

import boto3
import pytest

from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: tests that call deployed AWS resources",
    )


@pytest.fixture(scope="session")
def integration_config():
    if os.getenv("AUSSIE_ECOLENS_RUN_INTEGRATION") != "1":
        pytest.skip(
            "Set AUSSIE_ECOLENS_RUN_INTEGRATION=1 to run AWS integration tests.",
            allow_module_level=True,
        )

    return {
        "region": os.getenv("AWS_REGION", "us-east-1"),
        "bucket": os.getenv("AUSSIE_ECOLENS_BUCKET", "aussie-eco-len-bucket-12345"),
        "table": os.getenv("AUSSIE_ECOLENS_TABLE", "aussie-eco-len-media"),
        "get_signed_url_function": os.getenv(
            "AUSSIE_ECOLENS_GET_SIGNED_URL_FUNCTION",
            "get_signed_url",
        ),
        "get_private_media_function": os.getenv(
            "AUSSIE_ECOLENS_GET_PRIVATE_MEDIA_FUNCTION",
            "get_private_media",
        ),
        "get_public_media_function": os.getenv(
            "AUSSIE_ECOLENS_GET_PUBLIC_MEDIA_FUNCTION",
            "get_public_media",
        ),
        "tag_image_function": os.getenv(
            "AUSSIE_ECOLENS_TAG_IMAGE_FUNCTION",
            "tag_image",
        ),
        "tag_video_function": os.getenv(
            "AUSSIE_ECOLENS_TAG_VIDEO_FUNCTION",
            "tag_video",
        ),
        "test_user_id": os.getenv(
            "AUSSIE_ECOLENS_TEST_USER_ID",
            "integration-test-user",
        ),
        "test_video_path": os.getenv("AUSSIE_ECOLENS_TEST_VIDEO_PATH"),
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

    return {
        "s3": boto3.client("s3", region_name=region),
        "lambda": boto3.client("lambda", region_name=region),
        "table": dynamodb.Table(integration_config["table"]),
    }


@pytest.fixture()
def unique_id():
    return f"it-{uuid.uuid4().hex}"
