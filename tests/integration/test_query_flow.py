import json

import pytest


pytestmark = pytest.mark.integration


def _api_event(method, body=None, user_id="integration-test-user"):
    event = {
        "httpMethod": method,
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {
                        "sub": user_id,
                    }
                }
            }
        },
    }

    if body is not None:
        event["body"] = json.dumps(body)

    return event


def _invoke_lambda(lambda_client, function_name, event):
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(event).encode("utf-8"),
    )

    payload = json.loads(response["Payload"].read().decode("utf-8"))

    if response.get("FunctionError"):
        pytest.fail(f"{function_name} failed: {payload}")

    return payload


def _body(handler_response):
    return json.loads(handler_response["body"])


def _build_db_key(owner_id, full_key):
    return f"OWNER#{owner_id}#KEY#{full_key}"


def _put_media_record(table, **overrides):
    item = {
        "owner_id": "integration-test-user",
        "file_name": "integration-query-test.png",
        "checksum": "integration-query-test-checksum",
        "full_key": "integration-tests/query/integration-query-test.png",
        "visibility": "private",
        "full_url": "https://example.invalid/full.png",
        "file_type": "image/png",
        "thumbnail_key": "integration-tests/query/integration-query-test-thumb.jpg",
        "thumbnail_url": "https://example.invalid/thumb.jpg",
        "tags": {
            "koala": 2,
            "wombat": 1,
        },
        "ml_detections": [],
        "upload_status": "ready",
        "error_message": None,
    }

    item.update(overrides)
    item["key"] = _build_db_key(item["owner_id"], item["full_key"])

    table.put_item(Item=item)
    return item


def _delete_media_record(table, item):
    table.delete_item(
        Key={
            "key": item["key"],
        }
    )


def test_query_tag(aws_clients, integration_config, unique_id):
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    user_id = integration_config["test_user_id"]

    matching_record_1 = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}-koala-1.png",
        checksum=f"{unique_id}-query-tags-koala-1",
        full_key=f"integration-tests/query/{unique_id}-koala-1.png",
        tags={
            "koala": 2,
            "wombat": 1,
        },
    )

    matching_record_2 = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}-koala-2.png",
        checksum=f"{unique_id}-query-tags-koala-2",
        full_key=f"integration-tests/query/{unique_id}-koala-2.png",
        tags={
            "koala": 1,
            "kangaroo": 3,
        },
    )

    non_matching_record = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}-no-koala.png",
        checksum=f"{unique_id}-query-tags-no-koala",
        full_key=f"integration-tests/query/{unique_id}-no-koala.png",
        tags={
            "wombat": 5,
            "kangaroo": 1,
        },
    )

    records_to_delete = [
        matching_record_1,
        matching_record_2,
        non_matching_record,
    ]

    try:
        response = _invoke_lambda(
            lambda_client,
            integration_config["query_tags_function"],
            _api_event(
                "POST",
                body={
                    "tags": {
                        "koala": 1,
                    }
                },
                user_id=user_id,
            ),
        )

        assert response["statusCode"] == 200

        body = _body(response)
        media_records = body["media_records"]

        records_by_file_name = {
            media["file_name"]: media
            for media in media_records
        }

        matched_record_1 = records_by_file_name.get(
            matching_record_1["file_name"]
        )
        matched_record_2 = records_by_file_name.get(
            matching_record_2["file_name"]
        )
        non_matched_record = records_by_file_name.get(
            non_matching_record["file_name"]
        )

        assert matched_record_1 is not None
        assert matched_record_2 is not None
        assert non_matched_record is None

        assert matched_record_1["owner_id"] == user_id
        assert matched_record_1["visibility"] == "private"
        assert matched_record_1["tags"]["koala"] == 2
        assert matched_record_1["tags"]["wombat"] == 1
        assert matched_record_1["upload_status"] == "ready"

        assert matched_record_2["owner_id"] == user_id
        assert matched_record_2["visibility"] == "private"
        assert matched_record_2["tags"]["koala"] == 1
        assert matched_record_2["tags"]["kangaroo"] == 3
        assert matched_record_2["upload_status"] == "ready"

    finally:
        for record in records_to_delete:
            _delete_media_record(table, record)


def test_query_species(aws_clients, integration_config, unique_id):
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    user_id = integration_config["test_user_id"]

    matching_record_1 = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}-koala-1.png",
        checksum=f"{unique_id}-query-species-koala-1",
        full_key=f"integration-tests/query-species/{unique_id}-koala-1.png",
        tags={
            "koala": 2,
            "wombat": 1,
        },
    )

    matching_record_2 = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}-koala-2.png",
        checksum=f"{unique_id}-query-species-koala-2",
        full_key=f"integration-tests/query-species/{unique_id}-koala-2.png",
        tags={
            "koala": 1,
            "kangaroo": 3,
        },
    )

    non_matching_record = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}-no-koala.png",
        checksum=f"{unique_id}-query-species-no-koala",
        full_key=f"integration-tests/query-species/{unique_id}-no-koala.png",
        tags={
            "wombat": 5,
            "kangaroo": 1,
        },
    )

    records_to_delete = [
        matching_record_1,
        matching_record_2,
        non_matching_record,
    ]

    try:
        response = _invoke_lambda(
            lambda_client,
            "query_species",
            _api_event(
                "POST",
                body={
                    "species": "koala",
                },
                user_id=user_id,
            ),
        )

        assert response["statusCode"] == 200

        body = _body(response)
        media_records = body["media_records"]

        records_by_file_name = {
            media["file_name"]: media
            for media in media_records
        }

        matched_record_1 = records_by_file_name.get(
            matching_record_1["file_name"]
        )
        matched_record_2 = records_by_file_name.get(
            matching_record_2["file_name"]
        )
        non_matched_record = records_by_file_name.get(
            non_matching_record["file_name"]
        )

        assert matched_record_1 is not None
        assert matched_record_2 is not None
        assert non_matched_record is None

        assert matched_record_1["owner_id"] == user_id
        assert matched_record_1["visibility"] == "private"
        assert matched_record_1["tags"]["koala"] == 2
        assert matched_record_1["tags"]["wombat"] == 1
        assert matched_record_1["upload_status"] == "ready"

        assert matched_record_2["owner_id"] == user_id
        assert matched_record_2["visibility"] == "private"
        assert matched_record_2["tags"]["koala"] == 1
        assert matched_record_2["tags"]["kangaroo"] == 3
        assert matched_record_2["upload_status"] == "ready"

    finally:
        for record in records_to_delete:
            _delete_media_record(table, record)
