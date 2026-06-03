import base64
import tempfile
import cv2

from http import HTTPMethod, HTTPStatus
from contextlib import contextmanager
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from typing import Dict
from typing import Iterator
from typing import List
from typing import Mapping


from shared.aws_resources import (
    download_s3_file,
    get_bucket_and_name,
    get_table,
    scan_media_record,
)
from shared.model import ImageTagger
from shared.query_utils import can_query_media, infer_media_type, normalize_tag_counts
from shared.schemas import MediaRecord, MediaRecordStatus, QueryFileResponse, QueryFileResult
from shared.utils import build_response_message, get_current_user


s3, bucket_name = get_bucket_and_name()
table = get_table()

CLASSIFIER_MODEL_KEY = "models/model.pt"
DETECTOR_MODEL_KEY = "models/mdv5a.pt"
LOCAL_CLASSIFIER_MODEL_PATH = "/tmp/model.pt"
LOCAL_DETECTOR_MODEL_PATH = "/tmp/mdv5a.pt"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv"}

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


@dataclass
class UploadedQueryFile:
    filename: str
    content_type: str
    content: bytes


@contextmanager
def temporary_query_file(uploaded_file: UploadedQueryFile) -> Iterator[Path]:
    suffix = Path(uploaded_file.filename).suffix
    temp_path = None

    try:
        # ImageTagger expects a local file path, so the uploaded bytes are staged briefly.
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=suffix,
            delete=False,
            dir="/tmp",
        ) as temp_file:
            temp_file.write(uploaded_file.content)
            temp_path = Path(temp_file.name)

        yield temp_path

    finally:
        # query_file is search-only; the uploaded query image is not kept in S3 or DynamoDB.
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def get_header(headers: Mapping[str, str], name: str) -> str | None:
    name_lower = name.lower()

    for key, value in headers.items():
        if key.lower() == name_lower:
            return value

    return None


def get_request_body_bytes(event: dict) -> bytes:
    body = event.get("body") or ""

    if event.get("isBase64Encoded"):
        return base64.b64decode(body)

    return body.encode("utf-8")


def parse_multipart_file(event: dict) -> UploadedQueryFile:
    headers = event.get("headers") or {}
    content_type = get_header(headers, "content-type")

    if not content_type or "multipart/form-data" not in content_type:
        raise ValueError("Content-Type must be multipart/form-data")

    body_bytes = get_request_body_bytes(event)
    # The email parser understands MIME-style multipart boundaries, which match form-data.
    raw_message = (
        f"Content-Type: {content_type}\r\n"
        "MIME-Version: 1.0\r\n"
        "\r\n"
    ).encode("utf-8") + body_bytes

    message = BytesParser(policy=default).parsebytes(raw_message)

    if not message.is_multipart():
        raise ValueError("Request body is not valid multipart data")

    for part in message.iter_parts():
        filename = part.get_filename()

        # Ignore normal form fields and keep the first actual file part.
        if not filename:
            continue

        content = part.get_payload(decode=True) or b""

        if not content:
            raise ValueError("Uploaded query file must not be empty")

        return UploadedQueryFile(
            filename=filename,
            content_type=part.get_content_type(),
            content=content,
        )

    raise ValueError("No uploaded file found in multipart request")


def infer_uploaded_media_type(uploaded_file: UploadedQueryFile) -> str:
    content_family = uploaded_file.content_type.split("/")[0].lower()

    if content_family in {"image", "video"}:
        return content_family

    suffix = Path(uploaded_file.filename).suffix.lower()

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
    uploaded_file: UploadedQueryFile,
) -> Dict[str, int]:
    media_type = infer_uploaded_media_type(uploaded_file)

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
        uploaded_file = parse_multipart_file(event)
    except ValueError as error:
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Invalid query file request", "error": str(error)},
            allow_http_methods=allow_methods,
        )

    try:
        with temporary_query_file(uploaded_file) as temp_path:
            temp_file_size = temp_path.stat().st_size
            current_user = get_current_user(event)
            detected_tags = detect_query_file_tags(temp_path, uploaded_file)
            response = query_matching_media(detected_tags, current_user)

            return build_response_message(
                status_code=HTTPStatus.OK,
                body={
                    **response.model_dump(mode="json"),
                    "message": "query_file processed",
                    "uploaded_file": {
                        "filename": uploaded_file.filename,
                        "content_type": uploaded_file.content_type,
                        "size_bytes": len(uploaded_file.content),
                    },
                    "temporary_file": {
                        "saved": True,
                        "size_bytes": temp_file_size,
                    },
                },
                allow_http_methods=allow_methods,
            )
    except ValueError as error:
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Invalid query file request", "error": str(error)},
            allow_http_methods=allow_methods,
        )
