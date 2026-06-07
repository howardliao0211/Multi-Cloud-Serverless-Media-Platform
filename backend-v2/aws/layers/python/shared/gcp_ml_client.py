from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import boto3

try:
    import google.auth as google_auth
    from google.auth import impersonated_credentials
    from google.auth.transport.requests import Request as GoogleAuthRequest
except Exception as exc:
    print(f"GCP auth import failed: {type(exc).__name__}: {exc!r}")
    google_auth = None
    impersonated_credentials = None
    GoogleAuthRequest = None

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


_cached_google_id_token: str | None = None


def get_google_id_token() -> str | None:
    """
    Return a Google-signed ID token for Cloud Run IAM.

    This mirrors the v1 tag_image path:
    AWS Lambda -> WIF credentials file -> impersonate GCP service account
    -> mint ID token with Cloud Run URL as audience.
    """
    global _cached_google_id_token

    if _cached_google_id_token:
        return _cached_google_id_token

    if google_auth is None or impersonated_credentials is None or GoogleAuthRequest is None:
        print("GCP auth disabled: google-auth imports unavailable")
        return None

    credentials_file = os.environ.get(
        "GCP_WIF_CREDENTIALS_FILE",
        "/var/task/auth/gcp_wif_credentials.json",
    )
    invoker_service_account = os.environ.get("GCP_INVOKER_SERVICE_ACCOUNT", "")
    audience = os.environ.get("GCP_CLOUD_RUN_AUDIENCE") or os.environ.get("GCP_ML_PROCESSOR_URL", "")

    if not invoker_service_account:
        print("GCP auth disabled: GCP_INVOKER_SERVICE_ACCOUNT is not configured")
        return None

    if not audience:
        print("GCP auth disabled: GCP_CLOUD_RUN_AUDIENCE/GCP_ML_PROCESSOR_URL is not configured")
        return None

    if not Path(credentials_file).exists():
        print(f"GCP auth disabled: WIF credentials file not found: {credentials_file}")
        return None

    source_credentials, _ = google_auth.load_credentials_from_file(
        credentials_file,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    impersonated = impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=invoker_service_account,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )

    target_credentials = impersonated_credentials.IDTokenCredentials(
        target_credentials=impersonated,
        target_audience=audience.rstrip("/"),
        include_email=True,
    )

    target_credentials.refresh(GoogleAuthRequest())
    _cached_google_id_token = target_credentials.token
    print("GCP auth enabled: minted Google ID token for Cloud Run")
    return _cached_google_id_token



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
        "X-Timestamp": timestamp,
        "X-Signature": signature,
    }


def call_gcp_ml_processor(
    request: GcpMlRequest,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    endpoint = os.environ.get("GCP_ML_PROCESSOR_URL")
    if not endpoint:
        raise RuntimeError("Missing GCP_ML_PROCESSOR_URL")

    url = endpoint.rstrip("/") + "/process-media"
    payload = {
        "request_id": request.request_id,
        "media_type": request.media_type,
        "input_url": str(request.input_url),
        "model_urls": request.model_urls.model_dump(),
        "model_version": request.model_version,
    }

    if request.sample_every_n_frames is not None:
        payload["sample_every_n_frames"] = request.sample_every_n_frames

    if request.max_frame is not None:
        payload["max_frame"] = request.max_frame

    body = _canonical_body(payload)

    headers = sign_request(payload)

    google_id_token = get_google_id_token()
    if google_id_token:
        headers["Authorization"] = f"Bearer {google_id_token}"
    else:
        print("Calling GCP ML processor without Google Authorization header")

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
