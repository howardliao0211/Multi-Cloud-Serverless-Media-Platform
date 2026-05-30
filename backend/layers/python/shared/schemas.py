from typing import Dict, Literal
from pydantic import BaseModel, Field
from typing import Optional

class MediaRecord(BaseModel):
    hash: str
    media_type: Literal["image", "video"]

    s3_key: str
    thumbnail_s3_key: str

    tags: Dict[str, int] = Field(default_factory=dict)

    upload_status: Literal[
        "PENDING_UPLOAD",
        "UPLOADED",
        "PROCESSING",
        "READY",
        "FAILED",
    ] = "PENDING_UPLOAD"


class UploadUrlRequest(BaseModel):
    filename: str
    media_type: Literal["image", "video"]
    checksum: str

class UploadUrlResponse(BaseModel):
    duplicate: bool
    upload_url: Optional[str]
    expires_in: Optional[int]
