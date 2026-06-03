from urllib.parse import unquote_plus
import cv2
import numpy as np

from shared.schemas import MediaRecordStatus
from shared.model import ImageTagger
from shared.aws_resources import (
    get_bucket_and_name,
    get_table,
    build_thumbnail_s3_key,
    download_s3_file,
    update_media_record_in_db,
    get_s3_object_head_and_url,
    is_media_record_processing
)
from shared.utils import build_db_key

s3, bucket_name = get_bucket_and_name()
table = get_table()

CLASSIFIER_MODEL_KEY = "models/model.pt"
DETECTOR_MODEL_KEY = "models/mdv5a.pt"

LOCAL_CLASSIFIER_MODEL_PATH = "/tmp/model.pt"
LOCAL_DETECTOR_MODEL_PATH = "/tmp/mdv5a.pt"

download_s3_file(
    s3, bucket_name, CLASSIFIER_MODEL_KEY, LOCAL_CLASSIFIER_MODEL_PATH
)

download_s3_file(
    s3, bucket_name, DETECTOR_MODEL_KEY, LOCAL_DETECTOR_MODEL_PATH
)


tagger = ImageTagger(
    classifier_model_path=LOCAL_CLASSIFIER_MODEL_PATH,
    detector_model_path=LOCAL_DETECTOR_MODEL_PATH,
)


def process_video_frames_one_by_one(local_path: str):
    cap = cv2.VideoCapture(str(local_path))

    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {local_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps <= 0:
        cap.release()
        raise ValueError("Could not read FPS from video.")

    frame_interval = int(round(fps))
    frame_count = 0
    sampled_idx = 0

    final_tags = {}
    best_thumbnail_frame = None
    max_animal_cnt = 0

    try:
        while True:
            success, frame = cap.read()

            if not success:
                break

            if frame_count % frame_interval == 0:
                tagger_result = tagger.tag_image(frame)
                current_tags = tagger_result["tags"]

                for animal, count in current_tags.items():
                    final_tags[animal] = max(final_tags.get(animal, 0), count)

                if len(current_tags) > max_animal_cnt:
                    max_animal_cnt = len(current_tags)
                    best_thumbnail_frame = frame.copy()

                sampled_idx += 1

            frame_count += 1

    finally:
        cap.release()

    if best_thumbnail_frame is None:
        raise ValueError("No frames were extracted from video.")

    return final_tags, best_thumbnail_frame


def create_thumbnail(image: np.ndarray, fx: float = 0.5, fy: float = 0.5):
    resized_scaled = cv2.resize(
        image, None, fx=fx, fy=fy, interpolation=cv2.INTER_AREA
    )
    return resized_scaled


def upload_thumbnail_to_s3(
    image_array: np.ndarray,
    s3_key: str,
    bucket: str,
) -> None:
    success, encoded_image = cv2.imencode(".jpg", image_array)

    if not success:
        raise ValueError("Failed to encode thumbnail image as JPEG.")

    image_bytes = encoded_image.tobytes()

    s3.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=image_bytes,
        ContentType="image/jpeg",
    )


def process_video(bucket: str, s3_key: str):

    head, full_url = get_s3_object_head_and_url(s3_key)
    file_name = head["Metadata"]["file_name"]
    checksum = head["Metadata"]["checksum"]
    owner_id = head["Metadata"]["owner_id"]
    file_ext = file_name.split(".")[-1]
    file_type = head["ContentType"]

    thumbnail_s3_key = build_thumbnail_s3_key(checksum + f".{file_ext}")
    db_key = build_db_key(
        owner_id, s3_key
    )

    update_media_record_in_db(
        table, db_key, {
            "full_url": full_url,
            "file_type": file_type,
            "upload_status": MediaRecordStatus.uploaded,
        }
    )

    should_process = is_media_record_processing(
        table, db_key
    )

    if not should_process:
        print(
            f"Duplicate media already exists, skipping model run: {file_name}")
        return

    try:
        update_media_record_in_db(
            table, db_key, {
                "upload_status": MediaRecordStatus.processing,
            }
        )

        local_path = f"/tmp/{file_name}"

        download_s3_file(
            s3=s3,
            bucket=bucket,
            s3_key=s3_key,
            local_path=local_path,
        )

        final_tags, thumbnail_frame = process_video_frames_one_by_one(
            local_path
        )

        # Use the frame with most animal to create thumbnail
        thumbnail = create_thumbnail(
            thumbnail_frame
        )

        upload_thumbnail_to_s3(thumbnail, thumbnail_s3_key, bucket)
        _, thumbnail_url = get_s3_object_head_and_url(thumbnail_s3_key)

        update_media_record_in_db(
            table, db_key, {
                "thumbnail_key": thumbnail_s3_key,
                "thumbnail_url": thumbnail_url,
                "tags": final_tags,
                "upload_status": MediaRecordStatus.ready,
            }
        )

        print(f"Finished processing media: {s3_key}")
    except Exception as e:
        update_media_record_in_db(
            table, db_key, {
                "upload_status": MediaRecordStatus.failed,
                "error_message": f"Error: {e}",
            }
        )
        raise


def lambda_handler(event, context):
    video_file_extensions = [
        "mp4", "mov", "mkv"
    ]

    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        s3_key = unquote_plus(record["s3"]["object"]["key"])
        file_ext = s3_key.split(".")[-1]

        if file_ext not in video_file_extensions:
            raise ValueError(
                f"Unsupported image file type. Only support {video_file_extensions}"
            )

        process_video(
            bucket=bucket,
            s3_key=s3_key,
        )
