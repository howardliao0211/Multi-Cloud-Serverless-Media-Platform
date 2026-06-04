import json

import pytest
from botocore.exceptions import ClientError


pytestmark = pytest.mark.integration


def _get_media_record(table, item):
    response = table.get_item(
        Key={
            "key": item["key"],
        },
        ConsistentRead=True,
    )
    return response.get("Item")


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


def _s3_object_exists(s3, bucket, key):
    try:
        s3.head_object(
            Bucket=bucket,
            Key=key,
        )
        return True
    except ClientError as error:
        if error.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise


def _delete_s3_object(s3, bucket, key):
    s3.delete_object(
        Bucket=bucket,
        Key=key,
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


def test_query_thumbnail(aws_clients, integration_config, unique_id):
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    user_id = integration_config["test_user_id"]

    matching_record_1 = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}-koala-1.png",
        checksum=f"{unique_id}-query-species-koala-1",
        full_key=f"integration-tests/query-species/{unique_id}-koala-1.png",
        thumbnail_url="https://example.com/matched_thumbnail_url.png",
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
        thumbnail_url="https://example.com/matched_thumbnail_url.png",
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
        thumbnail_url="https://example.com/unmatched_thumbnail_url.png",
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
            "query_thumbnail_url",
            _api_event(
                "POST",
                body={
                    "thumbnail_url": "https://example.com/matched_thumbnail_url.png",
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

        assert matched_record_1 is not None, f"{media_records}"
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


def test_edit_tags_add_by_thumbnail_url(aws_clients, integration_config, unique_id):
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    user_id = integration_config["test_user_id"]

    thumbnail_url = f"https://example.com/{unique_id}/edit-tags-add-thumb.jpg"

    media_record = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}-edit-tags-add.png",
        checksum=f"{unique_id}-edit-tags-add",
        full_key=f"integration-tests/edit-tags/{unique_id}-add.png",
        full_url=f"https://example.com/{unique_id}/edit-tags-add-full.png",
        thumbnail_url=thumbnail_url,
        tags={
            "Canis_familiaris": 1,
            "Vombatus_ursinus": 1,
        },
    )

    try:
        response = _invoke_lambda(
            lambda_client,
            "edit_tags",
            _api_event(
                "POST",
                body={
                    "urls": [thumbnail_url],
                    "tags": [{"Canis_familiaris": 1}],
                },
                user_id=user_id,
            ),
        )

        assert response["statusCode"] == 200

        body = _body(response)
        assert body["updated_count"] == 1
        assert len(body["results"]) == 1

        result = body["results"][0]
        assert result["url"] == thumbnail_url
        assert result["updated"] is True
        assert result["checksum"] == media_record["checksum"]
        assert result["file_name"] == media_record["file_name"]
        assert result["message"] == "tags updated"
        assert result["tags"]["Canis_familiaris"] == 2
        assert result["tags"]["Vombatus_ursinus"] == 1

        stored_record = _get_media_record(table, media_record)
        assert stored_record["tags"]["Canis_familiaris"] == 2
        assert stored_record["tags"]["Vombatus_ursinus"] == 1

    finally:
        _delete_media_record(table, media_record)


def test_edit_tags_remove_by_full_url(aws_clients, integration_config, unique_id):
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    user_id = integration_config["test_user_id"]

    full_url = f"https://example.com/{unique_id}/edit-tags-remove-full.png"

    media_record = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}-edit-tags-remove.png",
        checksum=f"{unique_id}-edit-tags-remove",
        full_key=f"integration-tests/edit-tags/{unique_id}-remove.png",
        full_url=full_url,
        thumbnail_url=f"https://example.com/{unique_id}/edit-tags-remove-thumb.jpg",
        tags={
            "Canis_familiaris": 2,
            "Vombatus_ursinus": 1,
        },
    )

    try:
        response = _invoke_lambda(
            lambda_client,
            "edit_tags",
            _api_event(
                "POST",
                body={
                    "urls": [full_url],
                    "tags": [{"Canis_familiaris": -1}],
                },
                user_id=user_id,
            ),
        )

        assert response["statusCode"] == 200

        body = _body(response)
        assert body["updated_count"] == 1

        result = body["results"][0]
        assert result["url"] == full_url
        assert result["updated"] is True
        assert result["checksum"] == media_record["checksum"]
        assert result["file_name"] == media_record["file_name"]
        assert result["message"] == "tags updated"
        assert result["tags"] == {
            "Canis_familiaris": 1,
            "Vombatus_ursinus": 1,
        }

        stored_record = _get_media_record(table, media_record)
        assert stored_record["tags"] == {
            "Canis_familiaris": 1,
            "Vombatus_ursinus": 1,
        }

    finally:
        _delete_media_record(table, media_record)


def test_edit_tags_remove_deletes_tag_when_count_reaches_zero(
    aws_clients,
    integration_config,
    unique_id,
):
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    user_id = integration_config["test_user_id"]

    thumbnail_url = f"https://example.com/{unique_id}/edit-tags-remove-zero-thumb.jpg"

    media_record = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}-edit-tags-remove-zero.png",
        checksum=f"{unique_id}-edit-tags-remove-zero",
        full_key=f"integration-tests/edit-tags/{unique_id}-remove-zero.png",
        full_url=f"https://example.com/{unique_id}/edit-tags-remove-zero-full.png",
        thumbnail_url=thumbnail_url,
        tags={
            "Canis_familiaris": 1,
            "Vombatus_ursinus": 1,
        },
    )

    try:
        response = _invoke_lambda(
            lambda_client,
            "edit_tags",
            _api_event(
                "POST",
                body={
                    "urls": [thumbnail_url],
                    "tags": [{"Canis_familiaris": -1}],
                },
                user_id=user_id,
            ),
        )

        assert response["statusCode"] == 200

        body = _body(response)
        assert body["updated_count"] == 1

        result = body["results"][0]
        assert result["updated"] is True
        assert result["message"] == "tags updated"
        assert result["tags"] == {
            "Vombatus_ursinus": 1,
        }

        stored_record = _get_media_record(table, media_record)
        assert stored_record["tags"] == {
            "Vombatus_ursinus": 1,
        }

    finally:
        _delete_media_record(table, media_record)


def test_edit_tags_applies_independent_tag_deltas(
    aws_clients,
    integration_config,
    unique_id,
):
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    user_id = integration_config["test_user_id"]

    full_url = f"https://example.com/{unique_id}/edit-tags-deltas-full.png"

    media_record = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}-edit-tags-deltas.png",
        checksum=f"{unique_id}-edit-tags-deltas",
        full_key=f"integration-tests/edit-tags/{unique_id}-deltas.png",
        full_url=full_url,
        thumbnail_url=f"https://example.com/{unique_id}/edit-tags-deltas-thumb.jpg",
        tags={
            "Canis_familiaris": 1,
            "Felis_catus": 3,
            "Vombatus_ursinus": 1,
        },
    )

    try:
        response = _invoke_lambda(
            lambda_client,
            "edit_tags",
            _api_event(
                "POST",
                body={
                    "urls": [full_url],
                    "tags": [
                        {"Canis_familiaris": 2},
                        {"Felis_catus": -3},
                        {"Wallabia_bicolor": 1},
                    ],
                },
                user_id=user_id,
            ),
        )

        assert response["statusCode"] == 200

        body = _body(response)
        assert body["updated_count"] == 1

        result = body["results"][0]
        assert result["url"] == full_url
        assert result["updated"] is True
        assert result["message"] == "tags updated"
        assert result["tags"] == {
            "Canis_familiaris": 3,
            "Vombatus_ursinus": 1,
            "Wallabia_bicolor": 1,
        }

        stored_record = _get_media_record(table, media_record)
        assert stored_record["tags"] == {
            "Canis_familiaris": 3,
            "Vombatus_ursinus": 1,
            "Wallabia_bicolor": 1,
        }

    finally:
        _delete_media_record(table, media_record)


def test_edit_tags_not_found(aws_clients, integration_config, unique_id):
    lambda_client = aws_clients["lambda"]
    user_id = integration_config["test_user_id"]

    missing_url = f"https://example.com/{unique_id}/edit-tags-missing.png"

    response = _invoke_lambda(
        lambda_client,
        "edit_tags",
        _api_event(
            "POST",
            body={
                "urls": [missing_url],
                "tags": [{"Canis_familiaris": 1}],
            },
            user_id=user_id,
        ),
    )

    assert response["statusCode"] == 200

    body = _body(response)
    assert body["updated_count"] == 0
    assert len(body["results"]) == 1

    result = body["results"][0]
    assert result["url"] == missing_url
    assert result["updated"] is False
    assert result["checksum"] is None
    assert result["file_name"] is None
    assert result["tags"] == {}
    assert result["message"] == "media not found"


def test_edit_tags_forbidden_when_url_belongs_to_another_user(
    aws_clients,
    integration_config,
    unique_id,
):
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    user_id = integration_config["test_user_id"]
    other_user_id = f"{user_id}-other"

    thumbnail_url = f"https://example.com/{unique_id}/edit-tags-forbidden-thumb.jpg"

    other_user_record = _put_media_record(
        table,
        owner_id=other_user_id,
        file_name=f"{unique_id}-edit-tags-forbidden.png",
        checksum=f"{unique_id}-edit-tags-forbidden",
        full_key=f"integration-tests/edit-tags/{unique_id}-forbidden.png",
        full_url=f"https://example.com/{unique_id}/edit-tags-forbidden-full.png",
        thumbnail_url=thumbnail_url,
        tags={
            "Canis_familiaris": 1,
        },
    )

    try:
        response = _invoke_lambda(
            lambda_client,
            "edit_tags",
            _api_event(
                "POST",
                body={
                    "urls": [thumbnail_url],
                    "tags": [{"Canis_familiaris": 1}],
                },
                user_id=user_id,
            ),
        )

        assert response["statusCode"] == 200

        body = _body(response)
        assert body["updated_count"] == 0
        assert len(body["results"]) == 1

        result = body["results"][0]
        assert result["url"] == thumbnail_url
        assert result["updated"] is False
        assert result["checksum"] is None
        assert result["file_name"] is None
        assert result["tags"] == {}
        assert result["message"] == "media not found"

        stored_record = _get_media_record(table, other_user_record)
        assert stored_record["tags"] == {
            "Canis_familiaris": 1,
        }

    finally:
        _delete_media_record(table, other_user_record)


def test_delete_file_removes_owned_record_and_unshared_s3_objects(
    aws_clients,
    integration_config,
    unique_id,
):
    s3 = aws_clients["s3"]
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    bucket = integration_config["bucket"]
    user_id = integration_config["test_user_id"]

    full_key = f"images/{unique_id}-delete-file.png"
    thumbnail_key = f"thumbnails/{unique_id}-delete-file-thumb.jpg"
    full_url = f"https://example.com/{unique_id}/delete-file-full.png"
    thumbnail_url = f"https://example.com/{unique_id}/delete-file-thumb.jpg"

    media_record = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}-delete-file.png",
        checksum=f"{unique_id}-delete-file",
        full_key=full_key,
        full_url=full_url,
        thumbnail_key=thumbnail_key,
        thumbnail_url=thumbnail_url,
        tags={
            "koala": 1,
        },
    )

    try:
        s3.put_object(
            Bucket=bucket,
            Key=full_key,
            Body=b"integration-test-full-object",
            ContentType="image/png",
        )
        s3.put_object(
            Bucket=bucket,
            Key=thumbnail_key,
            Body=b"integration-test-thumbnail-object",
            ContentType="image/jpeg",
        )

        response = _invoke_lambda(
            lambda_client,
            integration_config["delete_file_function"],
            _api_event(
                "POST",
                body={
                    "urls": [full_url],
                },
                user_id=user_id,
            ),
        )

        assert response["statusCode"] == 200

        body = _body(response)
        assert body["deleted_count"] == 1
        assert len(body["results"]) == 1

        result = body["results"][0]
        assert result["url"] == full_url
        assert result["deleted"] is True
        assert result["checksum"] == media_record["checksum"]
        assert result["file_name"] == media_record["file_name"]
        assert result["removed_db_entry"] is True
        assert result["removed_full_object"] is True
        assert result["removed_thumbnail_object"] is True
        assert result["message"] == "media deleted"

        assert _get_media_record(table, media_record) is None
        assert _s3_object_exists(s3, bucket, full_key) is False
        assert _s3_object_exists(s3, bucket, thumbnail_key) is False

    finally:
        _delete_media_record(table, media_record)
        _delete_s3_object(s3, bucket, full_key)
        _delete_s3_object(s3, bucket, thumbnail_key)


def test_delete_file_not_found(aws_clients, integration_config, unique_id):
    lambda_client = aws_clients["lambda"]
    user_id = integration_config["test_user_id"]
    missing_url = f"https://example.com/{unique_id}/delete-file-missing.png"

    response = _invoke_lambda(
        lambda_client,
        integration_config["delete_file_function"],
        _api_event(
            "POST",
            body={
                "urls": [missing_url],
            },
            user_id=user_id,
        ),
    )

    assert response["statusCode"] == 200

    body = _body(response)
    assert body["deleted_count"] == 0
    assert len(body["results"]) == 1

    result = body["results"][0]
    assert result["url"] == missing_url
    assert result["deleted"] is False
    assert result["checksum"] is None
    assert result["file_name"] is None
    assert result["removed_db_entry"] is False
    assert result["removed_full_object"] is False
    assert result["removed_thumbnail_object"] is False
    assert result["message"] == "media not found"


def test_delete_file_forbidden_when_url_belongs_to_another_user(
    aws_clients,
    integration_config,
    unique_id,
):
    s3 = aws_clients["s3"]
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    bucket = integration_config["bucket"]
    user_id = integration_config["test_user_id"]
    other_user_id = f"{user_id}-other"

    full_key = f"images/{unique_id}-delete-file-forbidden.png"
    thumbnail_key = f"thumbnails/{unique_id}-delete-file-forbidden-thumb.jpg"
    full_url = f"https://example.com/{unique_id}/delete-file-forbidden-full.png"
    thumbnail_url = f"https://example.com/{unique_id}/delete-file-forbidden-thumb.jpg"

    other_user_record = _put_media_record(
        table,
        owner_id=other_user_id,
        file_name=f"{unique_id}-delete-file-forbidden.png",
        checksum=f"{unique_id}-delete-file-forbidden",
        full_key=full_key,
        full_url=full_url,
        thumbnail_key=thumbnail_key,
        thumbnail_url=thumbnail_url,
        tags={
            "koala": 1,
        },
    )

    try:
        s3.put_object(
            Bucket=bucket,
            Key=full_key,
            Body=b"integration-test-forbidden-full-object",
            ContentType="image/png",
        )
        s3.put_object(
            Bucket=bucket,
            Key=thumbnail_key,
            Body=b"integration-test-forbidden-thumbnail-object",
            ContentType="image/jpeg",
        )

        response = _invoke_lambda(
            lambda_client,
            integration_config["delete_file_function"],
            _api_event(
                "POST",
                body={
                    "urls": [full_url],
                },
                user_id=user_id,
            ),
        )

        assert response["statusCode"] == 200

        body = _body(response)
        assert body["deleted_count"] == 0
        assert len(body["results"]) == 1

        result = body["results"][0]
        assert result["url"] == full_url
        assert result["deleted"] is False
        assert result["checksum"] is None
        assert result["file_name"] is None
        assert result["removed_db_entry"] is False
        assert result["removed_full_object"] is False
        assert result["removed_thumbnail_object"] is False
        assert result["message"] == "forbidden: media is owned by another user"

        assert _get_media_record(table, other_user_record) is not None
        assert _s3_object_exists(s3, bucket, full_key) is True
        assert _s3_object_exists(s3, bucket, thumbnail_key) is True

    finally:
        _delete_media_record(table, other_user_record)
        _delete_s3_object(s3, bucket, full_key)
        _delete_s3_object(s3, bucket, thumbnail_key)


def test_delete_file_keeps_shared_s3_objects_when_other_entry_references_them(
    aws_clients,
    integration_config,
    unique_id,
):
    s3 = aws_clients["s3"]
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    bucket = integration_config["bucket"]
    user_id = integration_config["test_user_id"]
    other_user_id = f"{user_id}-other"

    full_key = f"images/{unique_id}-delete-file-shared.png"
    thumbnail_key = f"thumbnails/{unique_id}-delete-file-shared-thumb.jpg"
    user_full_url = f"https://example.com/{unique_id}/delete-file-shared-user-full.png"
    user_thumbnail_url = f"https://example.com/{unique_id}/delete-file-shared-user-thumb.jpg"
    other_full_url = f"https://example.com/{unique_id}/delete-file-shared-other-full.png"
    other_thumbnail_url = f"https://example.com/{unique_id}/delete-file-shared-other-thumb.jpg"

    user_record = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}-delete-file-shared-user.png",
        checksum=f"{unique_id}-delete-file-shared",
        full_key=full_key,
        full_url=user_full_url,
        thumbnail_key=thumbnail_key,
        thumbnail_url=user_thumbnail_url,
        tags={
            "koala": 1,
        },
    )
    other_user_record = _put_media_record(
        table,
        owner_id=other_user_id,
        file_name=f"{unique_id}-delete-file-shared-other.png",
        checksum=f"{unique_id}-delete-file-shared",
        full_key=full_key,
        full_url=other_full_url,
        thumbnail_key=thumbnail_key,
        thumbnail_url=other_thumbnail_url,
        tags={
            "koala": 1,
        },
    )

    try:
        s3.put_object(
            Bucket=bucket,
            Key=full_key,
            Body=b"integration-test-shared-full-object",
            ContentType="image/png",
        )
        s3.put_object(
            Bucket=bucket,
            Key=thumbnail_key,
            Body=b"integration-test-shared-thumbnail-object",
            ContentType="image/jpeg",
        )

        response = _invoke_lambda(
            lambda_client,
            integration_config["delete_file_function"],
            _api_event(
                "POST",
                body={
                    "urls": [user_full_url],
                },
                user_id=user_id,
            ),
        )

        assert response["statusCode"] == 200

        body = _body(response)
        assert body["deleted_count"] == 1
        assert len(body["results"]) == 1

        result = body["results"][0]
        assert result["url"] == user_full_url
        assert result["deleted"] is True
        assert result["checksum"] == user_record["checksum"]
        assert result["file_name"] == user_record["file_name"]
        assert result["removed_db_entry"] is True
        assert result["removed_full_object"] is False
        assert result["removed_thumbnail_object"] is False
        assert result["message"] == "media deleted"

        assert _get_media_record(table, user_record) is None
        assert _get_media_record(table, other_user_record) is not None
        assert _s3_object_exists(s3, bucket, full_key) is True
        assert _s3_object_exists(s3, bucket, thumbnail_key) is True

    finally:
        _delete_media_record(table, user_record)
        _delete_media_record(table, other_user_record)
        _delete_s3_object(s3, bucket, full_key)
        _delete_s3_object(s3, bucket, thumbnail_key)


def test_delete_file_removes_shared_s3_objects_after_last_owner_deletes(
    aws_clients,
    integration_config,
    unique_id,
):
    s3 = aws_clients["s3"]
    lambda_client = aws_clients["lambda"]
    table = aws_clients["table"]
    bucket = integration_config["bucket"]
    user_id = integration_config["test_user_id"]
    other_user_id = f"{user_id}-other"

    full_key = f"images/{unique_id}-delete-file-last-owner.png"
    thumbnail_key = f"thumbnails/{unique_id}-delete-file-last-owner-thumb.jpg"
    user_full_url = f"https://example.com/{unique_id}/delete-file-last-owner-user-full.png"
    user_thumbnail_url = f"https://example.com/{unique_id}/delete-file-last-owner-user-thumb.jpg"
    other_full_url = f"https://example.com/{unique_id}/delete-file-last-owner-other-full.png"
    other_thumbnail_url = f"https://example.com/{unique_id}/delete-file-last-owner-other-thumb.jpg"

    user_record = _put_media_record(
        table,
        owner_id=user_id,
        file_name=f"{unique_id}-delete-file-last-owner-user.png",
        checksum=f"{unique_id}-delete-file-last-owner",
        full_key=full_key,
        full_url=user_full_url,
        thumbnail_key=thumbnail_key,
        thumbnail_url=user_thumbnail_url,
        tags={
            "koala": 1,
        },
    )
    other_user_record = _put_media_record(
        table,
        owner_id=other_user_id,
        file_name=f"{unique_id}-delete-file-last-owner-other.png",
        checksum=f"{unique_id}-delete-file-last-owner",
        full_key=full_key,
        full_url=other_full_url,
        thumbnail_key=thumbnail_key,
        thumbnail_url=other_thumbnail_url,
        tags={
            "koala": 1,
        },
    )

    try:
        s3.put_object(
            Bucket=bucket,
            Key=full_key,
            Body=b"integration-test-last-owner-full-object",
            ContentType="image/png",
        )
        s3.put_object(
            Bucket=bucket,
            Key=thumbnail_key,
            Body=b"integration-test-last-owner-thumbnail-object",
            ContentType="image/jpeg",
        )

        first_response = _invoke_lambda(
            lambda_client,
            integration_config["delete_file_function"],
            _api_event(
                "POST",
                body={
                    "urls": [user_full_url],
                },
                user_id=user_id,
            ),
        )

        assert first_response["statusCode"] == 200
        first_body = _body(first_response)
        assert first_body["deleted_count"] == 1

        first_result = first_body["results"][0]
        assert first_result["removed_db_entry"] is True
        assert first_result["removed_full_object"] is False
        assert first_result["removed_thumbnail_object"] is False

        assert _get_media_record(table, user_record) is None
        assert _get_media_record(table, other_user_record) is not None
        assert _s3_object_exists(s3, bucket, full_key) is True
        assert _s3_object_exists(s3, bucket, thumbnail_key) is True

        second_response = _invoke_lambda(
            lambda_client,
            integration_config["delete_file_function"],
            _api_event(
                "POST",
                body={
                    "urls": [other_full_url],
                },
                user_id=other_user_id,
            ),
        )

        assert second_response["statusCode"] == 200
        second_body = _body(second_response)
        assert second_body["deleted_count"] == 1

        second_result = second_body["results"][0]
        assert second_result["url"] == other_full_url
        assert second_result["deleted"] is True
        assert second_result["checksum"] == other_user_record["checksum"]
        assert second_result["file_name"] == other_user_record["file_name"]
        assert second_result["removed_db_entry"] is True
        assert second_result["removed_full_object"] is True
        assert second_result["removed_thumbnail_object"] is True
        assert second_result["message"] == "media deleted"

        assert _get_media_record(table, other_user_record) is None
        assert _s3_object_exists(s3, bucket, full_key) is False
        assert _s3_object_exists(s3, bucket, thumbnail_key) is False

    finally:
        _delete_media_record(table, user_record)
        _delete_media_record(table, other_user_record)
        _delete_s3_object(s3, bucket, full_key)
        _delete_s3_object(s3, bucket, thumbnail_key)
