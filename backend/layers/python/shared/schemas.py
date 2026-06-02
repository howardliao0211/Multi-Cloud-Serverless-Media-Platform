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


class QueryTagsRequest(BaseModel):
    tags: Dict[str, int]

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: Dict[str, int]) -> Dict[str, int]:
        if not tags:
            raise ValueError("tags must not be empty")

        normalized_tags: Dict[str, int] = {}

        for raw_tag, raw_count in tags.items():
            tag = raw_tag.strip().lower()

            if not tag:
                raise ValueError("tag names must not be empty")

            count = int(raw_count)

            if count < 1:
                raise ValueError("tag counts must be at least 1")

            normalized_tags[tag] = count

        return normalized_tags


class QueryTagsResult(BaseModel):
    checksum: str
    file_name: str
    media_type: Optional[str] = None
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    tags: Dict[str, int] = Field(default_factory=dict)


class QueryTagsResponse(BaseModel):
    count: int
    results: List[QueryTagsResult] = Field(default_factory=list)


class QuerySpeciesRequest(BaseModel):
    species: str

    @field_validator("species")
    @classmethod
    def validate_species(cls, species: str) -> str:
        normalized_species = species.strip().lower()

        if not normalized_species:
            raise ValueError("species must not be empty")

        return normalized_species


class QuerySpeciesResult(BaseModel):
    checksum: str
    file_name: str
    media_type: Optional[str] = None
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    tags: Dict[str, int] = Field(default_factory=dict)


class QuerySpeciesResponse(BaseModel):
    count: int
    results: List[QuerySpeciesResult] = Field(default_factory=list)


class QueryThumbnailUrlRequest(BaseModel):
    thumbnail_url: str

    @field_validator("thumbnail_url")
    @classmethod
    def validate_thumbnail_url(cls, thumbnail_url: str) -> str:
        normalized_thumbnail_url = thumbnail_url.strip()

        if not normalized_thumbnail_url:
            raise ValueError("thumbnail_url must not be empty")

        return normalized_thumbnail_url


class QueryThumbnailUrlResponse(BaseModel):
    checksum: str
    file_name: str
    url: str
    thumbnail_url: str

    
class GetPrivateMediaRequest(BaseModel):
    owner_id: str


class GetMediaResponse(BaseModel):
    media_records: List[MediaRecordResponse]


class GetMediaUploadStatus(BaseModel):
    file_name: str
    checksum: str
