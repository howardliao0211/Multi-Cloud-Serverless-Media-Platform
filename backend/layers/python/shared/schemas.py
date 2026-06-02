from enum import Enum
from optparse import Option
from typing import Any, Dict, Optional, Literal
from pydantic import BaseModel, Field


class MediaRecordStatus(str, Enum):
    pending = "PENDING_UPLOAD"
    uploaded = "UPLOADED"
    processing = "PROCESSING"
    ready = "READY"
    failed = "FAILED"


class MediaRecord(BaseModel):
    checksum: str
    file_name: str
    full_key: str

    full_url: Optional[str] = None
    file_type: Optional[str] = None
    thumbnail_key: Optional[str] = None
    thumbnail_url: Optional[str] = None

    tags: Dict[str, int] = Field(default_factory=dict)

    ml_provider: Optional[str] = None
    ml_detections: list[dict[str, Any]] = Field(default_factory=list)
    ml_model_name: Optional[str] = None
    ml_model_version: Optional[str] = None

    upload_status: MediaRecordStatus = MediaRecordStatus.pending
    error_message: Optional[str] = None


class UploadUrlRequest(BaseModel):
    filename: str
    media_type: Literal["image", "video"]
    checksum: str


class UploadUrlResponse(BaseModel):
    duplicate: bool
    upload_url: Optional[str] = None
    expires_in: Optional[int] = None
