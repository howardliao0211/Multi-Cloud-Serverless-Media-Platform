from __future__ import annotations

from typing import Any, Literal, Optional, Dict, List

from pydantic import BaseModel, Field

MediaType = Literal["image", "video"]
MlStatus = Literal["ok", "failed"]


class GcpModelUrls(BaseModel):
    classifier: str
    detector: str


class GcpMlRequest(BaseModel):
    request_id: str
    media_type: MediaType
    input_url: str
    model_urls: GcpModelUrls
    model_version: str
    sample_every_n_frames: int | None = None
    max_frame: int | None = None


class GcpMlFrame(BaseModel):
    frame_index: int
    tag_counts: Dict[str, int] = Field(default_factory=dict)


class GcpMlResponse(BaseModel):
    request_id: str
    tag_counts: Dict[str, int] = Field(default_factory=dict)
    frames: Optional[List[GcpMlFrame]] = None


class GcpDetection(BaseModel):
    species: str | None = None
    label: str | None = None
    count: int | None = None
    confidence: float | None = None
    bbox: list[float] | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class GcpMlResult(BaseModel):
    status: MlStatus
    provider: str = "gcp_cloud_run"
    model_name: str | None = None
    model_version: str | None = None
    media_type: MediaType | None = None
    tags: dict[str, int] = Field(default_factory=dict)
    detections: list[dict[str, Any]] = Field(default_factory=list)
    error_message: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class ProcessMlResultEvent(BaseModel):
    owner_id: str
    checksum: str
    file_name: str
    bucket: str
    key: str
    file_type: str
    visibility: str | None = None
    thumbnail_key: str | None = None
    thumbnail_url: str | None = None
    gcp_result: dict[str, Any]
