from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MediaReplicaRequest(BaseModel):
    """
    Metadata document sent from AWS after S3/Lambda processing.

    Extra fields are allowed because the AWS media schema may grow over time
    without requiring this GCP endpoint to change immediately.
    """
    model_config = ConfigDict(extra="allow")

    hash: str
    media_type: Optional[Literal["image", "video"]] = None
    s3_key: Optional[str] = None
    thumbnail_s3_key: Optional[str] = None
    tag_counts: Dict[str, int] = Field(default_factory=dict)
    tags: Dict[str, int] = Field(default_factory=dict)
    upload_status: Optional[str] = None

    def to_firestore_document(self) -> Dict[str, Any]:
        # model_dump includes allowed extra fields, so Firestore keeps any
        # metadata that AWS sends but this model does not explicitly list yet.
        return self.model_dump(exclude_none=True)


class TagsQueryRequest(BaseModel):
    """
    Body for POST /query/tags.

    Example:
    {
      "tags": {
        "koala": 1,
        "wombat": 2
      }
    }
    """
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

            if int(raw_count) < 1:
                raise ValueError("tag counts must be at least 1")

            normalized_tags[tag] = int(raw_count)

        return normalized_tags


class SpeciesQueryRequest(BaseModel):
    """
    Body for POST /query/species.

    Example:
    {
      "species": "dingo"
    }
    """
    species: str

    @field_validator("species")
    @classmethod
    def validate_species(cls, species: str) -> str:
        normalized_species = species.strip().lower()

        if not normalized_species:
            raise ValueError("species must not be empty")

        return normalized_species


class ThumbnailQueryRequest(BaseModel):
    """
    Body for POST /query/thumbnail.

    Example:
    {
      "thumbnail_url": "https://.../thumbnails/hash.jpg"
    }
    """
    thumbnail_url: str

    @field_validator("thumbnail_url")
    @classmethod
    def validate_thumbnail_url(cls, thumbnail_url: str) -> str:
        normalized_thumbnail_url = thumbnail_url.strip()

        if not normalized_thumbnail_url:
            raise ValueError("thumbnail_url must not be empty")

        return normalized_thumbnail_url
