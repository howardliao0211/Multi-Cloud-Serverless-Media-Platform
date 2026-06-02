from enum import Enum
from optparse import Option
from typing import Dict, Optional, Literal
from pydantic import BaseModel, Field


class MediaType(str, Enum):
    image = "image"
    video = "video"


class MediaVisibility(str, Enum):
    private = "private"
    public = "public"


class MediaRecordStatus(str, Enum):
    pending = "pending"
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class MediaRecord(BaseModel):
    file_name: str
    checksum: str
    full_key: str
    visibility: MediaVisibility

    full_url: Optional[str] = None
    file_type: Optional[str] = None
    thumbnail_key: Optional[str] = None
    thumbnail_url: Optional[str] = None

    tags: Dict[str, int] = Field(default_factory=dict)

    upload_status: MediaRecordStatus = MediaRecordStatus.pending
    error_message: Optional[str] = None


class UploadUrlRequest(BaseModel):
    filename: str
    checksum: str
    media_type: MediaType
    visibility: MediaVisibility


class UploadUrlResponse(BaseModel):
    duplicate: bool
    upload_url: Optional[str] = None
    expires_in: Optional[int] = None
