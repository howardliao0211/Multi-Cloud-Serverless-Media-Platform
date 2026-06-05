from __future__ import annotations

from decimal import Decimal
from typing import Any

from shared.aws_resources import get_table
from shared.ml_contracts import GcpMlResult, ProcessMlResultEvent
from shared.utils import build_db_key


def convert_floats_for_dynamodb(value: Any) -> Any:
    """
    DynamoDB boto3 resource does not accept float values.
    Convert nested floats to Decimal while preserving dict/list structure.
    """
    if isinstance(value, float):
        return Decimal(str(value))

    if isinstance(value, dict):
        return {k: convert_floats_for_dynamodb(v) for k, v in value.items()}

    if isinstance(value, list):
        return [convert_floats_for_dynamodb(v) for v in value]

    return value


def normalize_tags(tags: dict[str, Any] | None) -> dict[str, int]:
    if not tags:
        return {}

    normalized: dict[str, int] = {}

    for key, value in tags.items():
        if key is None:
            continue

        tag = str(key).strip()
        if not tag:
            continue

        try:
            normalized[tag] = int(value)
        except (TypeError, ValueError):
            normalized[tag] = 1 if value else 0

    return normalized


def _build_update_expression(values: dict[str, Any]) -> tuple[str, dict[str, str], dict[str, Any]]:
    expression_names: dict[str, str] = {}
    expression_values: dict[str, Any] = {}
    assignments: list[str] = []

    for index, (name, value) in enumerate(values.items()):
        name_key = f"#n{index}"
        value_key = f":v{index}"

        expression_names[name_key] = name
        expression_values[value_key] = convert_floats_for_dynamodb(value)
        assignments.append(f"{name_key} = {value_key}")

    return "SET " + ", ".join(assignments), expression_names, expression_values


def update_media_record_from_ml_result(event: ProcessMlResultEvent) -> dict[str, Any]:
    table = get_table()

    normalized_gcp_result = normalize_gcp_result_shape(event.gcp_result)

    gcp_result = GcpMlResult(
        raw=event.gcp_result,
        **normalized_gcp_result,
    )

    db_key = build_db_key(event.owner_id, event.key)

    if gcp_result.status == "failed":
        updates = {
            "upload_status": "failed",
            "error_message": gcp_result.error_message or "GCP ML processing failed",
            "ml_provider": gcp_result.provider,
            "ml_model_name": gcp_result.model_name,
            "ml_model_version": gcp_result.model_version,
        }
    else:
        updates = {
            "file_type": event.file_type,
            "upload_status": "ready",
            "error_message": None,
            "tags": normalize_tags(gcp_result.tags),
            "ml_provider": gcp_result.provider,
            "ml_model_name": gcp_result.model_name,
            "ml_model_version": gcp_result.model_version,
            "ml_detections": gcp_result.detections,
        }

        if event.thumbnail_key:
            updates["thumbnail_key"] = event.thumbnail_key

        if event.thumbnail_url:
            updates["thumbnail_url"] = event.thumbnail_url

        if event.visibility:
            updates["visibility"] = event.visibility

    update_expression, expression_names, expression_values = _build_update_expression(updates)

    response = table.update_item(
        Key={"key": db_key},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_names,
        ExpressionAttributeValues=expression_values,
        ReturnValues="ALL_NEW",
    )

    return response.get("Attributes", {})



def normalize_gcp_result_shape(result: dict) -> dict:
    """Accept the existing GCP/v1 result shape and normalize it for v2 storage."""
    normalized = dict(result or {})

    if normalized.get("status") == "success":
        normalized["status"] = "ok"

    tags = normalized.get("tags")
    if isinstance(tags, list):
        normalized["tags"] = {str(tag): 1 for tag in tags}

    if normalized.get("provider") is None:
        normalized["provider"] = "gcp_cloud_run"

    if normalized.get("model_name") is None:
        normalized["model_name"] = "gcp_image_tagger"

    return normalized


def process_ml_result_payload(payload: dict[str, Any]) -> dict[str, Any]:
    event = ProcessMlResultEvent(**payload)
    updated_record = update_media_record_from_ml_result(event)

    return {
        "message": "ML result processed",
        "record": updated_record,
    }
