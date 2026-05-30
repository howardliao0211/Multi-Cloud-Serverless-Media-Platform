from typing import Any, Dict, Iterable

from google.cloud import firestore

from app.config import DATABASE_ID, PROJECT_ID


def get_db() -> firestore.Client:
    # A fresh client is cheap enough for this assignment-scale service and keeps
    # each repository function independent from FastAPI route state.
    return firestore.Client(project=PROJECT_ID, database=DATABASE_ID)


def save_media_replica(payload: Dict[str, Any]) -> None:
    # The media hash is the stable document id shared with AWS DynamoDB.
    media_hash = payload["hash"]
    db = get_db()
    doc_ref = db.collection("media").document(media_hash)

    # merge=True lets AWS resend partial updates without deleting older fields.
    doc_ref.set(payload, merge=True)


def stream_media() -> Iterable[Dict[str, Any]]:
    db = get_db()

    # Firestore returns document snapshots; the route/query layer works with
    # plain dictionaries so it does not need to know Firestore-specific types.
    docs = db.collection("media").stream()

    for doc in docs:
        yield doc.to_dict() or {}
