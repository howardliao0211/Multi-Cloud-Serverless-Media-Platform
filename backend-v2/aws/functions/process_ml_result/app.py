from __future__ import annotations

import json
from typing import Any

from shared.ml_result_processor import process_ml_result_payload


def _response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
        },
        "body": json.dumps(body, default=str),
    }


def lambda_handler(event, context):
    try:
        if isinstance(event, dict) and "body" in event:
            body = event.get("body") or "{}"
            payload = json.loads(body) if isinstance(body, str) else body
        else:
            payload = event

        result = process_ml_result_payload(payload)
        return _response(200, result)

    except Exception as exc:
        return _response(
            500,
            {
                "message": "Failed to process ML result",
                "error": str(exc),
            },
        )
