from typing import List

from pydantic import Base64Str, BaseModel, HttpUrl


class ImageRequest(BaseModel):
    image: Base64Str


class ImageResponse(BaseModel):
    hash_id: str
    full_size_url: HttpUrl
    thumbnail_url: HttpUrl
    tags: List[str]
    counts: List[int]
