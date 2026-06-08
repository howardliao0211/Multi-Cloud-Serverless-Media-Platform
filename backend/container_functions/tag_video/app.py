from urllib.parse import unquote_plus
import cv2
import numpy as np
import uuid
import os
from http import HTTPStatus

from shared.schemas import MediaRecordStatus, MediaType
from shared.utils import build_response_message
from shared.aws_resources import (
    get_bucket_and_name,
    get_table,
    download_s3_file,
    update_media_record_in_db,
    get_s3_object_head_and_url,
    is_media_record_processing,
    upload_thumbnail_to_s3,
)
from shared.utils import build_db_key, build_thumbnail_s3_key
from shared.gcp_ml_contracts import GcpMlRequest, GcpModelUrls
from shared.gcp_ml_client import (
    call_gcp_ml_processor,
    generate_presigned_get_url,
    create_thumbnail_bytes,
)

s3, bucket_name = get_bucket_and_name()
table = get_table()

CLASSIFIER_MODEL_KEY = "models/model.pt"
DETECTOR_MODEL_KEY = "models/mdv5a.pt"


def read_video_frame(local_path, frame_index: int):
    cap = cv2.VideoCapture(str(local_path))

    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {local_path}")

    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)

        success, frame = cap.read()

        if not success or frame is None or frame.size == 0:
            raise ValueError(f"Cannot read video frame at index {frame_index}")

        return frame

    finally:
        cap.release()


def process_video_frames(bucket, video_s3_key, local_path):

    input_url = generate_presigned_get_url(bucket, video_s3_key)

    model_urls = GcpModelUrls(
        classifier=generate_presigned_get_url(bucket, CLASSIFIER_MODEL_KEY),
        detector=generate_presigned_get_url(bucket, DETECTOR_MODEL_KEY),
    )

    gcp_request = GcpMlRequest(
        request_id=str(uuid.uuid4()),
        media_type=MediaType.video.value,
        input_url=input_url,
        model_urls=model_urls,
        model_version=os.getenv("GCP_MODEL_VERSION", "model_presigned_url"),
        second_per_frame=1,
    )

    gcp_result = call_gcp_ml_processor(gcp_request)

    final_tags = {}
    best_sampled_frame_index = 0
    max_animal_cnt = 0

    assert gcp_result.frames is not None

    for frame in gcp_result.frames:
        current_tags = frame.tag_counts

        for animal, count in current_tags.items():
            final_tags[animal] = max(final_tags.get(animal, 0), count)

        total_detected_animal = sum(current_tags.values())

        if total_detected_animal > max_animal_cnt:
            max_animal_cnt = total_detected_animal
            best_sampled_frame_index = frame.frame_index

    thumbnail_frame = read_video_frame(local_path, best_sampled_frame_index)

    return final_tags, thumbnail_frame


def process_video(bucket: str, s3_key: str):

    head, full_url = get_s3_object_head_and_url(s3_key)
    file_name = head["Metadata"]["file_name"]
    checksum = head["Metadata"]["checksum"]
    owner_id = head["Metadata"]["owner_id"]
    file_ext = file_name.split(".")[-1]
    file_type = head["ContentType"]

    thumbnail_s3_key = build_thumbnail_s3_key(checksum + f".{file_ext}")
    db_key = build_db_key(owner_id, s3_key)

    update_media_record_in_db(
        table,
        db_key,
        {
            "full_url": full_url,
            "file_type": file_type,
            "upload_status": MediaRecordStatus.uploaded,
        },
    )

    should_process = is_media_record_processing(table, db_key)

    if not should_process:
        print(f"Duplicate media already exists, skipping model run: {file_name}")
        return None

    try:
        update_media_record_in_db(
            table,
            db_key,
            {
                "upload_status": MediaRecordStatus.processing,
            },
        )

        local_path = f"/tmp/{file_name}"

        download_s3_file(
            s3=s3,
            bucket=bucket,
            s3_key=s3_key,
            local_path=local_path,
        )

        final_tags, thumbnail_frame = process_video_frames(
            bucket=bucket, video_s3_key=s3_key, local_path=local_path
        )

        # Use the frame with most animal to create thumbnail
        thumbnail_bytes = create_thumbnail_bytes(thumbnail_frame)

        upload_thumbnail_to_s3(thumbnail_bytes, s3, bucket_name, thumbnail_s3_key)
        _, thumbnail_url = get_s3_object_head_and_url(thumbnail_s3_key)

        db_entry = {
            "thumbnail_key": thumbnail_s3_key,
            "thumbnail_url": thumbnail_url,
            "tags": final_tags,
            "upload_status": MediaRecordStatus.ready,
        }
        update_media_record_in_db(
            table,
            db_key,
            db_entry,
        )

        print(f"Finished processing media: {s3_key}")
        return db_entry

    except Exception as e:
        update_media_record_in_db(
            table,
            db_key,
            {
                "upload_status": MediaRecordStatus.failed,
                "error_message": f"Error: {e}",
            },
        )
        raise


def lambda_handler(event, context):
    video_file_extensions = ["mp4", "mov", "webm"]
    entries = []

    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        s3_key = unquote_plus(record["s3"]["object"]["key"])
        file_ext = s3_key.split(".")[-1]

        if file_ext.lower() not in video_file_extensions:
            raise ValueError(
                f"Unsupported image file type. Only support {video_file_extensions}"
            )

        entry = process_video(
            bucket=bucket,
            s3_key=s3_key,
        )

        if entry is not None:
            entries.append(entry)

    return build_response_message(
        status_code=HTTPStatus.OK, body=entries, allow_http_methods=[]
    )
