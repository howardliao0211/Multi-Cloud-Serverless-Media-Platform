import cv2

from http import HTTPMethod, HTTPStatus
from contextlib import contextmanager
from json import JSONDecodeError
from pathlib import Path
from uuid import uuid4
from typing import Dict
from typing import Iterator
from typing import List

from pydantic import ValidationError

from shared.aws_resources import (
    download_s3_file,
    get_bucket_and_name,
    get_table,
    scan_media_record,
)
from shared.model import ImageTagger
from shared.query_utils import (
    can_query_media,
    infer_media_type,
    normalize_tag_counts,
    parse_json_request,
)
from shared.schemas import (
    MediaRecord,
    MediaRecordStatus,
    QueryFileRequest,
    QueryFileResponse,
    QueryFileResult,
)
from shared.utils import build_response_message, get_current_user


s3, bucket_name = get_bucket_and_name()
table = get_table()

CLASSIFIER_MODEL_KEY = "models/model.pt"
DETECTOR_MODEL_KEY = "models/mdv5a.pt"
LOCAL_CLASSIFIER_MODEL_PATH = "/tmp/model.pt"
LOCAL_DETECTOR_MODEL_PATH = "/tmp/mdv5a.pt"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
QUERY_UPLOAD_PREFIX = "query_uploads"

# Models are copied from S3 into Lambda's writable /tmp folder during cold start.
download_s3_file(
    s3,
    bucket_name,
    CLASSIFIER_MODEL_KEY,
    LOCAL_CLASSIFIER_MODEL_PATH,
)

download_s3_file(
    s3,
    bucket_name,
    DETECTOR_MODEL_KEY,
    LOCAL_DETECTOR_MODEL_PATH,
)

# Keep one tagger instance warm across invocations whenever Lambda reuses the container.
tagger = ImageTagger(
    classifier_model_path=LOCAL_CLASSIFIER_MODEL_PATH,
    detector_model_path=LOCAL_DETECTOR_MODEL_PATH,
)


def parse_request(event: dict) -> QueryFileRequest:
    return parse_json_request(event, QueryFileRequest)


@contextmanager
def temporary_s3_query_file(query_key: str) -> Iterator[Path]:
    suffix = Path(query_key).suffix
    temp_path = Path(f"/tmp/query-{uuid4().hex}{suffix}")

    try:
        # ImageTagger expects a local file path, so the temporary S3 object is staged in /tmp.
        download_s3_file(s3, bucket_name, query_key, str(temp_path))
        yield temp_path

    finally:
        # This is only the local staging copy. S3 cleanup is handled separately.
        temp_path.unlink(missing_ok=True)


def validate_query_key_owner(query_key: str, current_user: str) -> None:
    expected_prefix = f"{QUERY_UPLOAD_PREFIX}/{current_user}/"

    if not query_key.startswith(expected_prefix):
        raise ValueError("query_key does not belong to the current user")


def get_query_object_metadata(query_key: str, current_user: str) -> tuple[str, str]:
    head = s3.head_object(Bucket=bucket_name, Key=query_key)
    metadata = head.get("Metadata") or {}

    if metadata.get("owner_id") != current_user:
        raise ValueError("query object owner does not match the current user")

    if metadata.get("purpose") != "query_file":
        raise ValueError("query object was not uploaded for query_file")

    content_type = head.get("ContentType") or ""
    file_name = metadata.get("file_name") or Path(query_key).name

    return file_name, content_type


def infer_uploaded_media_type(file_name: str, content_type: str) -> str:
    content_family = content_type.split("/")[0].lower()

    if content_family in {"image", "video"}:
        return content_family

    suffix = Path(file_name).suffix.lower()

    if suffix in IMAGE_EXTENSIONS:
        return "image"

    if suffix in VIDEO_EXTENSIONS:
        return "video"

    raise ValueError("Uploaded query file must be an image or video")


def media_matches_detected_tags(
    media_record: MediaRecord,
    detected_tags: Dict[str, int],
) -> bool:
    media_tags = normalize_tag_counts(media_record.tags)

    for tag, min_count in detected_tags.items():
        if media_tags.get(tag, 0) < min_count:
            return False

    return True


def shape_query_result(media_record: MediaRecord) -> QueryFileResult:
    media_type = infer_media_type(media_record)
    thumbnail_url = media_record.thumbnail_url if media_type == "image" else None

    return QueryFileResult(
        checksum=media_record.checksum,
        file_name=media_record.file_name,
        visibility=media_record.visibility,
        media_type=media_type,
        url=media_record.full_url,
        thumbnail_url=thumbnail_url,
        tags=normalize_tag_counts(media_record.tags),
    )


def query_matching_media(
    detected_tags: Dict[str, int],
    current_user: str,
) -> QueryFileResponse:
    results: List[QueryFileResult] = []

    if not detected_tags:
        return QueryFileResponse(
            detected_tags=detected_tags,
            count=0,
            results=[],
        )

    filters = {"upload_status": MediaRecordStatus.ready}

    for media_record in scan_media_record(table, filters):
        # Private media is only searchable by its owner; public media is searchable by anyone.
        if not can_query_media(media_record, current_user):
            continue

        # Match all detected tags with at least the detected count.
        if media_matches_detected_tags(media_record, detected_tags):
            results.append(shape_query_result(media_record))

    return QueryFileResponse(
        detected_tags=detected_tags,
        count=len(results),
        results=results,
    )


def detect_image_query_tags(temp_path: Path) -> Dict[str, int]:
    # ImageTagger returns the animal tags found in the temporary query image.
    tagger_result = tagger.tag_image(temp_path)
    return normalize_tag_counts(tagger_result.get("tags"))


def detect_video_query_tags(temp_path: Path) -> Dict[str, int]:
    cap = cv2.VideoCapture(str(temp_path))

    if not cap.isOpened():
        raise ValueError(f"Cannot open uploaded query video: {temp_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps <= 0:
        cap.release()
        raise ValueError("Could not read FPS from uploaded query video")

    frame_interval = max(1, int(round(fps)))
    frame_count = 0
    sampled_frames = 0
    detected_tags: Dict[str, int] = {}

    try:
        while True:
            success, frame = cap.read()

            if not success:
                break

            # Match the upload pipeline: sample one frame per second, not every frame.
            if frame_count % frame_interval == 0:
                tagger_result = tagger.tag_image(frame)
                frame_tags = normalize_tag_counts(tagger_result.get("tags"))

                for tag, count in frame_tags.items():
                    detected_tags[tag] = max(detected_tags.get(tag, 0), count)

                sampled_frames += 1

            frame_count += 1

    finally:
        cap.release()

    if sampled_frames == 0:
        raise ValueError("No frames were extracted from uploaded query video")

    return detected_tags


def detect_query_file_tags(
    temp_path: Path,
    file_name: str,
    content_type: str,
) -> Dict[str, int]:
    media_type = infer_uploaded_media_type(file_name, content_type)

    if media_type == "image":
        return detect_image_query_tags(temp_path)

    return detect_video_query_tags(temp_path)


def lambda_handler(event, context):
    allow_methods = [HTTPMethod.POST, HTTPMethod.OPTIONS]

    if event.get("httpMethod") == "OPTIONS":
        return build_response_message(
            status_code=HTTPStatus.OK,
            body={"message": "OK"},
            allow_http_methods=allow_methods,
        )

    if event.get("httpMethod") != "POST":
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Unsupported HTTP method"},
            allow_http_methods=allow_methods,
        )

    try:
        current_user = get_current_user(event)
        request = parse_request(event)
        validate_query_key_owner(request.query_key, current_user)
        file_name, content_type = get_query_object_metadata(
            request.query_key,
            current_user,
        )

        with temporary_s3_query_file(request.query_key) as temp_path:
            temp_file_size = temp_path.stat().st_size
            detected_tags = detect_query_file_tags(temp_path, file_name, content_type)
            response = query_matching_media(detected_tags, current_user)

            return build_response_message(
                status_code=HTTPStatus.OK,
                body={
                    **response.model_dump(mode="json"),
                    "message": "query_file processed",
                    "query_file": {
                        "query_key": request.query_key,
                        "file_name": file_name,
                        "content_type": content_type,
                    },
                    "temporary_file": {
                        "saved": True,
                        "size_bytes": temp_file_size,
                    },
                },
                allow_http_methods=allow_methods,
            )
    except (JSONDecodeError, ValidationError, ValueError) as error:
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Invalid query file request", "error": str(error)},
            allow_http_methods=allow_methods,
        )
