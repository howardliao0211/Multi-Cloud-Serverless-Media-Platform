from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException

from app.auth import verify_internal_api_key
from app.config import ENVIRONMENT
from app.firestore_repo import save_media_replica, stream_media
from app.models import MediaReplicaRequest, SpeciesQueryRequest, TagsQueryRequest, ThumbnailQueryRequest
from app.query_logic import (
    media_matches_tags,
    shape_query_result,
    shape_thumbnail_lookup_result,
    thumbnail_url_matches,
)

app = FastAPI(title="Aussie EcoLens GCP Query Service")


def find_matching_media(requested_tags: Dict[str, int]) -> List[Dict[str, Any]]:
    matches = []

    # Simple scan approach for assignment/demo scale.
    # Later, optimise with an index collection if needed.
    for item in stream_media():
        if media_matches_tags(item, requested_tags):
            matches.append(shape_query_result(item))

    return matches


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
    matches = find_matching_media(payload.tags)

    return {
        "count": len(matches),
        "results": matches,
    }


@app.post("/query/species")
def query_by_species(payload: SpeciesQueryRequest) -> Dict[str, Any]:
    """
    Query Firestore media records containing at least one detected species.

    Expected request:
    {
      "species": "dingo"
    }

    Behaviour:
    Equivalent to a tag-count query with { "dingo": 1 }.
    """
    matches = find_matching_media({payload.species: 1})

    return {
        "count": len(matches),
        "results": matches,
    }


@app.post("/query/thumbnail")
def query_by_thumbnail_url(payload: ThumbnailQueryRequest) -> Dict[str, Any]:
    """
    Resolve a thumbnail URL back to its corresponding full-size image URL.

    Expected request:
    {
      "thumbnail_url": "https://.../thumbnails/hash.jpg"
    }
    """
    for item in stream_media():
        if thumbnail_url_matches(item, payload.thumbnail_url):
            return shape_thumbnail_lookup_result(item)

    raise HTTPException(status_code=404, detail="Thumbnail URL not found")
