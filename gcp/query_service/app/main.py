import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from google.cloud import firestore

app = FastAPI(title="Aussie EcoLens GCP Query Service")

PROJECT_ID = os.getenv("FIRESTORE_PROJECT_ID")
DATABASE_ID = os.getenv("FIRESTORE_DATABASE", "(default)")
ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
INTERNAL_API_KEY = os.getenv("INTERNAL_REPLICATION_API_KEY", "")

def get_db():
    return firestore.Client(project=PROJECT_ID, database=DATABASE_ID)


@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "service": "aussie-ecolens-query",
        "environment": ENVIRONMENT,
        "status": "ok",
    }


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "healthy"}


@app.post("/internal/replicate-media")
def replicate_media(
    payload: Dict[str, Any],
    x_internal_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """
    Internal endpoint called by AWS upload_to_db after media processing.

    For now this uses a simple shared API key check if INTERNAL_REPLICATION_API_KEY is set.
    Later we can improve this with signed service-to-service auth.
    """
    if INTERNAL_API_KEY:
        if x_internal_api_key != INTERNAL_API_KEY:
            raise HTTPException(status_code=401, detail="Invalid internal API key")

    media_hash = payload.get("hash")
    if not media_hash:
        raise HTTPException(status_code=400, detail="Missing required field: hash")

    db = get_db()
    doc_ref = db.collection("media").document(media_hash)
    doc_ref.set(payload, merge=True)

    return {
        "status": "replicated",
        "hash": media_hash,
    }


@app.post("/query/tags")
def query_by_tags(payload: Dict[str, Any]) -> Dict[str, Any]:
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
    requested_tags = payload.get("tags")

    if not isinstance(requested_tags, dict) or not requested_tags:
        raise HTTPException(status_code=400, detail="Expected non-empty 'tags' object")

    matches: List[Dict[str, Any]] = []

    # Simple scan approach for assignment/demo scale.
    # Later, optimise with an index collection if needed.
    db = get_db()
    docs = db.collection("media").stream()

    for doc in docs:
        item = doc.to_dict() or {}
        tag_counts = item.get("tag_counts", {})

        if not isinstance(tag_counts, dict):
            continue

        matched = True

        for tag, min_count in requested_tags.items():
            try:
                min_count_int = int(min_count)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"Invalid count for tag: {tag}")

            actual_count = int(tag_counts.get(tag, 0))

            if actual_count < min_count_int:
                matched = False
                break

        if matched:
            matches.append(item)

    return {
        "count": len(matches),
        "results": matches,
    }
