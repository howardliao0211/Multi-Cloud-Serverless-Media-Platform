from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from shared.utils import build_db_key
from pydantic import BaseModel, Field, field_validator, model_validator


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


class QueryFileJobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class MediaRecord(BaseModel):
    key: str
    owner_id: str
    owner_email: str
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

    @model_validator(mode="before")
    @classmethod
    def set_key_before_validation(cls, data: dict):

        assert isinstance(data, dict)
        assert "owner_id" in data
        assert "full_key" in data

        owner_id = data.get("owner_id")
        full_key = data.get("full_key")

        if owner_id and full_key:
            data["key"] = build_db_key(owner_id, full_key)

        return data


class MediaRecordResponse(BaseModel):
    owner_id: str
    owner_email: str
    file_name: str
    visibility: MediaVisibility

    full_url: Optional[str]
    thumbnail_url: Optional[str]

    full_presigned_url: Optional[str]
    thumbnail_presigned_url: Optional[str]

    tags: Dict[str, int]
    upload_status: MediaRecordStatus
    error_message: Optional[str]

    @classmethod
    def from_media_record(
        cls, media_record: MediaRecord, s3, bucket_name, expires_seconds=300
    ):
        full_presigned_url = s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={
                "Bucket": bucket_name,
                "Key": media_record.full_key,
            },
            ExpiresIn=expires_seconds,
        )

        thumbnail_presigned_url = None

        if media_record.thumbnail_key:
            thumbnail_presigned_url = s3.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": bucket_name,
                    "Key": media_record.thumbnail_key,
                },
                ExpiresIn=expires_seconds,
            )

        return cls(
            owner_id=media_record.owner_id,
            owner_email=media_record.owner_email,
            file_name=media_record.file_name,
            visibility=media_record.visibility,
            full_url=media_record.full_url,
            thumbnail_url=media_record.thumbnail_url,
            full_presigned_url=full_presigned_url,
            thumbnail_presigned_url=thumbnail_presigned_url,
            tags=media_record.tags or {},
            upload_status=media_record.upload_status,
            error_message=media_record.error_message,
        )


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


class QuerySpeciesRequest(BaseModel):
    species: str

    @field_validator("species")
    @classmethod
    def validate_species(cls, species: str) -> str:
        normalized_species = species.strip().lower()

        if not normalized_species:
            raise ValueError("species must not be empty")

        return normalized_species


class QueryThumbnailUrlRequest(BaseModel):
    thumbnail_url: str


class QueryFileUploadUrlRequest(BaseModel):
    file_name: str
    media_type: MediaType
    content_type: str

    @field_validator("file_name", "content_type")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized_value = value.strip()

        if not normalized_value:
            raise ValueError("value must not be empty")

        return normalized_value


class QueryFileUploadUrlResponse(BaseModel):
    upload_url: str
    query_key: str
    expires_in: int
    upload_headers: Dict[str, str] = Field(default_factory=dict)


class QueryFileRequest(BaseModel):
    query_key: str

    @field_validator("query_key")
    @classmethod
    def validate_query_key(cls, query_key: str) -> str:
        normalized_query_key = query_key.strip()

        if not normalized_query_key:
            raise ValueError("query_key must not be empty")

        return normalized_query_key


class QueryFileResult(BaseModel):
    owner_id: str
    owner_email: str
    checksum: str
    file_name: str
    visibility: MediaVisibility
    media_type: MediaType
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    full_presigned_url: Optional[str] = None
    thumbnail_presigned_url: Optional[str] = None
    tags: Dict[str, int] = Field(default_factory=dict)


class QueryFileResponse(BaseModel):
    detected_tags: Dict[str, int] = Field(default_factory=dict)
    count: int
    results: List[QueryFileResult] = Field(default_factory=list)


class QueryFileJobResponse(BaseModel):
    job_id: str
    status: QueryFileJobStatus


class QueryFileJobStatusResponse(BaseModel):
    job_id: str
    status: QueryFileJobStatus
    detected_tags: Dict[str, int] = Field(default_factory=dict)
    count: int = 0
    results: List[QueryFileResult] = Field(default_factory=list)
    error_message: Optional[str] = None


class GetMediaResponse(BaseModel):
    media_records: List[MediaRecordResponse]


class GetMediaUploadStatus(BaseModel):
    file_name: str
    checksum: str


class ChangeVisibilityRequest(BaseModel):
    url: str
    visibility: MediaVisibility


class EditTagsRequest(BaseModel):
    urls: List[str]
    tags: List[Dict[str, int]]
    operation_key: Literal[0, 1]

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, urls: List[str]) -> List[str]:
        normalized_urls = [url.strip() for url in urls if url.strip()]

        if not normalized_urls:
            raise ValueError("urls must not be empty")

        return normalized_urls


class EditTagsResult(BaseModel):
    url: str
    updated: bool
    checksum: Optional[str] = None
    file_name: Optional[str] = None
    tags: Dict[str, int] = Field(default_factory=dict)
    message: Optional[str] = None


class EditTagsResponse(BaseModel):
    updated_count: int
    results: List[EditTagsResult] = Field(default_factory=list)


class DeleteFileRequest(BaseModel):
    urls: List[str]

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, urls: List[str]) -> List[str]:
        normalized_urls = [url.strip() for url in urls if url.strip()]

        if not normalized_urls:
            raise ValueError("urls must not be empty")

        return list(dict.fromkeys(normalized_urls))


class DeleteFileResult(BaseModel):
    url: str
    deleted: bool
    checksum: Optional[str] = None
    file_name: Optional[str] = None
    removed_db_entry: bool = False
    removed_full_object: bool = False
    removed_thumbnail_object: bool = False
    message: Optional[str] = None


class DeleteFileResponse(BaseModel):
    deleted_count: int
    results: List[DeleteFileResult] = Field(default_factory=list)


class MediaUploadStatusResponse(BaseModel):
    upload_status: MediaRecordStatus
    error_message: Optional[str]


class SNSSubscribeRequest(BaseModel):
    email: str
    tags: List[str]


class SNSSubscribeResponse(BaseModel):
    email: str
    tags: List[str]
    subscription_arn: Optional[str]
    message: str


class SNSUnsubscribeRequest(BaseModel):
    email: str


class SNSGetSubscriptionRequest(BaseModel):
    email: str


class SubscriptionStatus(str, Enum):
    none = "none"
    pending = "pending"
    deleted = "deleted"
    confirmed = "confirmed"
    invalid = "invalid"


class SNSGetSubscriptionResponse(BaseModel):
    email: str
    tags: List[str]
    state: SubscriptionStatus
