from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header

from app.auth import verify_internal_api_key
from app.config import ENVIRONMENT
from app.firestore_repo import save_media_replica, stream_media
from app.models import MediaReplicaRequest, TagsQueryRequest
from app.query_logic import media_matches_tags, shape_query_result

app = FastAPI(title="Aussie EcoLens GCP Query Service")


@app.get("/")
def root() -> Dict[str, Any]:
    # Lightweight service identity endpoint for browser/curl checks.
    return {
        "service": "aussie-ecolens-query",
        "environment": ENVIRONMENT,
        "status": "ok",
    }


@app.get("/health")
def health() -> Dict[str, str]:
    # Cloud Run/load balancer health checks can use this endpoint.
    return {"status": "healthy"}


@app.post("/internal/replicate-media")
def replicate_media(
    payload: MediaReplicaRequest,
    x_internal_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Internal endpoint called by AWS upload_to_db after media processing.

    For now this uses a simple shared API key check if INTERNAL_REPLICATION_API_KEY is set.
    Later we can improve this with signed service-to-service auth.
    """
    verify_internal_api_key(x_internal_api_key)

    media_hash = payload.hash

    # Convert the validated request model back to a Firestore-ready dict.
    save_media_replica(payload.to_firestore_document())

    return {
        "status": "replicated",
        "hash": media_hash,
    }


@app.post("/query/tags")
def query_by_tags(payload: TagsQueryRequest) -> Dict[str, Any]:
    """
    Query Firestore media records by tag minimum counts.

    Expected request:
    {
      "tags": {
        "koala": 1,
        "wombat": 2
      }
    }

    Behaviour:
    AND logic between tags.
    Each media record must have count >= requested count for every requested tag.
    """
    matches: List[Dict[str, Any]] = []

    # Simple scan approach for assignment/demo scale.
    # Later, optimise with an index collection if needed.
    for item in stream_media():
        if media_matches_tags(item, payload.tags):
            matches.append(shape_query_result(item))

    return {
        "count": len(matches),
        "results": matches,
    }
