from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

import boto3

from shared.ml_contracts import GcpMlRequest


DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_PRESIGNED_URL_SECONDS = 600


def generate_presigned_get_url(
    bucket: str,
    key: str,
    expires_in: int = DEFAULT_PRESIGNED_URL_SECONDS,
) -> str:
    s3 = boto3.client("s3")
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def get_hmac_secret() -> str:
    direct = os.environ.get("INTERNAL_HMAC_SECRET")
    if direct:
        return direct

    secret_name = os.environ.get("INTERNAL_HMAC_SECRET_NAME") or os.environ.get("GCP_ML_HMAC_SECRET_NAME")
    if not secret_name:
        raise RuntimeError(
            "Missing INTERNAL_HMAC_SECRET or INTERNAL_HMAC_SECRET_NAME/GCP_ML_HMAC_SECRET_NAME"
        )

    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)

    if "SecretString" in response:
        return response["SecretString"]

    return base64.b64decode(response["SecretBinary"]).decode("utf-8")


def _canonical_body(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sign_request(payload: dict[str, Any], secret: str | None = None) -> dict[str, str]:
    timestamp = str(int(time.time()))
    body = _canonical_body(payload)
    secret_value = secret or get_hmac_secret()

    signed = timestamp.encode("utf-8") + b"." + body
    signature = hmac.new(
        secret_value.encode("utf-8"),
        signed,
        hashlib.sha256,
    ).hexdigest()

    return {
        "Content-Type": "application/json",
        "X-AEL-Timestamp": timestamp,
        "X-AEL-Signature": signature,
    }


def call_gcp_ml_processor(
    request: GcpMlRequest,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    endpoint = os.environ.get("GCP_ML_PROCESSOR_URL")
    if not endpoint:
        raise RuntimeError("Missing GCP_ML_PROCESSOR_URL")

    url = endpoint.rstrip("/") + "/process-media"
    payload = request.model_dump()
    body = _canonical_body(payload)

    headers = sign_request(payload)

    req = urllib.request.Request(
        url=url,
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body) if response_body else {}
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GCP ML processor HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GCP ML processor request failed: {exc}") from exc
