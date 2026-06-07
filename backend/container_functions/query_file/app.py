import traceback
import uuid
import cv2
import os

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Dict
from typing import Iterator
from typing import List

from shared.aws_resources import (
    delete_s3_object_if_exists,
    download_s3_file,
    get_bucket_and_name,
    get_table,
    scan_media_record,
)
from shared.query_utils import (
    can_query_media,
    infer_media_type,
    normalize_tag_counts,
)
from shared.schemas import (
    MediaRecord,
    MediaType,
    MediaRecordStatus,
    QueryFileResponse,
    QueryFileResult,
    MediaRecordResponse,
    QueryFileJobStatus,
)
from shared.gcp_ml_contracts import GcpMlRequest, GcpModelUrls
from shared.gcp_ml_client import call_gcp_ml_processor, generate_presigned_get_url

s3, bucket_name = get_bucket_and_name()
table = get_table()

CLASSIFIER_MODEL_KEY = "models/model.pt"
DETECTOR_MODEL_KEY = "models/mdv5a.pt"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
QUERY_UPLOAD_PREFIX = "query_uploads"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_job_key(job_id: str) -> str:
    return f"QUERY_JOB#{job_id}"


def update_query_job(job_id: str, updates: dict) -> None:
    if not updates:
        return

    updates = {
        **updates,
        "updated_at": utc_now(),
    }

    update_expression_parts = []
    expression_attribute_names = {}
    expression_attribute_values = {}

    for index, (field, value) in enumerate(updates.items()):
        field_name = f"#field_{index}"
        field_value = f":value_{index}"
        update_expression_parts.append(f"{field_name} = {field_value}")
        expression_attribute_names[field_name] = field
        expression_attribute_values[field_value] = value

    table.update_item(
        Key={"key": build_job_key(job_id)},
        UpdateExpression="SET " + ", ".join(update_expression_parts),
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values,
    )


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


def cleanup_query_upload(query_key: str) -> None:
    try:
        delete_s3_object_if_exists(s3, bucket_name, query_key)
    except Exception as error:
        print(f"Failed to clean query upload {query_key}: {error}")


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
    presigned = MediaRecordResponse.from_media_record(
        media_record,
        s3,
        bucket_name,
        300,
    )

    return QueryFileResult(
        owner_id=media_record.owner_id,
        checksum=media_record.checksum,
        file_name=media_record.file_name,
        visibility=media_record.visibility,
        media_type=media_type,
        url=media_record.full_url,
        thumbnail_url=thumbnail_url,
        full_presigned_url=presigned.full_presigned_url,
        thumbnail_presigned_url=presigned.thumbnail_presigned_url,
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


def detect_image_query_tags(s3_key) -> Dict[str, int]:
    # ImageTagger returns the animal tags found in the temporary query image.
    input_url = generate_presigned_get_url(bucket_name, s3_key)
    model_urls = GcpModelUrls(
        classifier=generate_presigned_get_url(bucket_name, CLASSIFIER_MODEL_KEY),
        detector=generate_presigned_get_url(bucket_name, DETECTOR_MODEL_KEY),
    )
    gcp_request = GcpMlRequest(
        request_id=str(uuid.uuid4()),
        media_type=MediaType.image.value,
        input_url=input_url,
        model_urls=model_urls,
        model_version=os.getenv("GCP_MODEL_VERSION", "model_presigned_url"),
    )
    gcp_result = call_gcp_ml_processor(gcp_request)
    return normalize_tag_counts(gcp_result.tag_counts)


def detect_video_query_tags(s3_key, temp_path: Path) -> Dict[str, int]:
    cap = cv2.VideoCapture(str(temp_path))

    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {temp_path}")

    try:
        fps = cap.get(cv2.CAP_PROP_FPS)

        if fps is None or fps <= 0:
            fps = 30

        frame_interval = max(int(round(fps)), 1)

    finally:
        cap.release()

    input_url = generate_presigned_get_url(bucket_name, s3_key)

    model_urls = GcpModelUrls(
        classifier=generate_presigned_get_url(bucket_name, CLASSIFIER_MODEL_KEY),
        detector=generate_presigned_get_url(bucket_name, DETECTOR_MODEL_KEY),
    )

    gcp_request = GcpMlRequest(
        request_id=str(uuid.uuid4()),
        media_type=MediaType.video.value,
        input_url=input_url,
        model_urls=model_urls,
        model_version=os.getenv("GCP_MODEL_VERSION", "model_presigned_url"),
        sample_every_n_frames=frame_interval,
        max_frame=None,
    )

    gcp_result = call_gcp_ml_processor(gcp_request)
    detected_tags: Dict[str, int] = {}

    assert gcp_result.frames is not None

    for frame in gcp_result.frames:
        current_tags = frame.tag_counts
        frame_tags = normalize_tag_counts(current_tags)

        for tag, count in frame_tags.items():
            detected_tags[tag] = max(detected_tags.get(tag, 0), count)

    return detected_tags


def detect_query_file_tags(
    s3_key: str,
    temp_path: Path,
    file_name: str,
    content_type: str,
) -> Dict[str, int]:
    media_type = infer_uploaded_media_type(file_name, content_type)

    if media_type == "image":
        return detect_image_query_tags(s3_key, temp_path)

    return detect_video_query_tags(s3_key, temp_path)


def lambda_handler(event, context):
    job_id = event["job_id"]
    current_user = event["owner_id"]
    query_key = event["query_key"]

    try:
        update_query_job(
            job_id,
            {
                "status": QueryFileJobStatus.processing.value,
                "error_message": None,
            },
        )
        validate_query_key_owner(query_key, current_user)
        file_name, content_type = get_query_object_metadata(
            query_key,
            current_user,
        )

        with temporary_s3_query_file(query_key) as temp_path:
            detected_tags = detect_query_file_tags(
                query_key, temp_path, file_name, content_type
            )
            response = query_matching_media(detected_tags, current_user)

            update_query_job(
                job_id,
                {
                    "status": QueryFileJobStatus.completed.value,
                    "detected_tags": response.detected_tags,
                    "count": response.count,
                    "results": [
                        result.model_dump(mode="json") for result in response.results
                    ],
                    "error_message": None,
                },
            )

            return {
                "job_id": job_id,
                "status": QueryFileJobStatus.completed.value,
            }

    except Exception as error:
        print("Unhandled query_file error")
        print(traceback.format_exc())

        update_query_job(
            job_id,
            {
                "status": QueryFileJobStatus.failed.value,
                "error_message": str(error),
            },
        )
        raise

    finally:
        cleanup_query_upload(query_key)
