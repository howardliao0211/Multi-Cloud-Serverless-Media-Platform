from typing import Dict, Literal
from pydantic import BaseModel, Field


class MediaRecord(BaseModel):
    hash: str
    media_type: Literal["image", "video"]

    s3_key: str
    thumbnail_s3_key: str

    counts: Dict[str, int]

    upload_status: Literal[
        "PENDING_UPLOAD",
        "UPLOADED",
        "PROCESSING",
        "READY",
        "FAILED",
    ] = "PENDING_UPLOAD"


class UploadUrlRequest(BaseModel):
    hash: str
    media_type: Literal["image", "video"]
