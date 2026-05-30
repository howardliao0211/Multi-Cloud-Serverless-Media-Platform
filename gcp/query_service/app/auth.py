from typing import Optional

from fastapi import HTTPException

from app.config import INTERNAL_API_KEY


def verify_internal_api_key(x_internal_api_key: Optional[str]) -> None:
    """
    Validate service-to-service calls from AWS.

    If no internal API key is configured, local/demo calls are allowed.
    """
    # This protects the replication endpoint from arbitrary public writes when
    # the Cloud Run service is exposed to the frontend.
    if INTERNAL_API_KEY and x_internal_api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid internal API key")
