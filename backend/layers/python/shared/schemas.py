from enum import Enum
from typing import Any, Dict, List, Literal, Optional

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
    owner_id: str
    file_name: str
    checksum: str
    full_key: str
    visibility: MediaVisibility

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


class MediaRecordResponse(BaseModel):
    owner_id: str
    file_name: str
    visibility: MediaVisibility
    full_presigned_url: str
    thumbnail_presigned_url: str
    tags: Dict[str, int]
    upload_status: MediaRecordStatus
    error_message: Optional[str]


class UploadUrlRequest(BaseModel):
    file_name: str
    checksum: str
    media_type: MediaType
    visibility: MediaVisibility


class UploadUrlResponse(BaseModel):
    duplicate: bool
    upload_url: Optional[str] = None
    expires_in: Optional[int] = None


class GetMediaResponse(BaseModel):
    media_records: List[MediaRecordResponse]


class GetMediaUploadStatus(BaseModel):
    file_name: str
    checksum: str
