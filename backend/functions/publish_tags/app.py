from boto3.dynamodb.types import TypeDeserializer
import json
from decimal import Decimal
from typing import Any, List

from shared.schemas import MediaRecordStatus, MediaVisibility
from shared.aws_resources import get_sns_and_topic_arn

sns, topic_arn = get_sns_and_topic_arn()


deserializer = TypeDeserializer()


def ddb_image_to_python(image: dict | None) -> dict:
    if not image:
        return {}

    return {key: deserializer.deserialize(value) for key, value in image.items()}


def get_tags(media_record: dict[str, Any]) -> set[str]:
    """
    Supports tags stored as:
      {"dog": 2, "person": 1}
    """
    tags = media_record.get("tags") or {}

    if not isinstance(tags, dict):
        return set()

    return {str(tag).strip().lower() for tag, count in tags.items() if int(count) > 0}


def publish_tag_notification(
    tag: str,
    media_tags: List[str],
    thumbnail_url: str,
    sns_client,
    topic_arn: str,
):
    tag = tag.strip().lower()

    return sns_client.publish(
        TopicArn=topic_arn,
        Subject=f"New image matched tag: {tag}",
        Message=f"""
A new image was uploaded with a tag you subscribed to.

Matched tag: {tag}
Media Tags: {", ".join(media_tags)}
Thumbnail URL: {thumbnail_url}
""",
        MessageAttributes={
            "tag": {
                "DataType": "String",
                "StringValue": tag,
            }
        },
    )


def publish_image_notifications(
    subscribe_tags: list[str],
    media_tags: str,
    thumbnail_url: str,
    sns_client,
    topic_arn: str,
):
    tags = [tag.strip().lower() for tag in subscribe_tags if tag and tag.strip()]

    results = []

    for tag in tags:
        response = publish_tag_notification(
            tag=tag,
            media_tags=media_tags,
            thumbnail_url=thumbnail_url,
            sns_client=sns_client,
            topic_arn=topic_arn,
        )

        results.append(
            {
                "tag": tag,
                "message_id": response.get("MessageId"),
            }
        )

    return results


def lambda_handler(event, context):
    published = []

    for record in event.get("Records", []):
        event_name = record.get("eventName")

        # DynamoDB Stream events are usually INSERT, MODIFY, REMOVE.
        if event_name not in {"INSERT", "MODIFY"}:
            continue

        dynamodb_data = record.get("dynamodb", {})

        old_image = ddb_image_to_python(dynamodb_data.get("OldImage"))

        new_image = ddb_image_to_python(dynamodb_data.get("NewImage"))

        upload_status = new_image.get("upload_status")
        if upload_status != MediaRecordStatus.ready.value:
            # only ready entries have tags
            continue

        visibility = new_image.get("visibility")
        if visibility != MediaVisibility.public.value:
            # only public entries should notify the users
            continue

        old_tags = get_tags(old_image)
        new_tags = get_tags(new_image)

        if event_name == "INSERT":
            tags_to_publish = new_tags
        else:
            # Only notify for newly added tags.
            tags_to_publish = new_tags - old_tags

        if not tags_to_publish:
            continue

        media_tags = new_image.get("tags")
        thumbnail_url = new_image.get("thumbnail_url")

        results = publish_image_notifications(
            subscribe_tags=list(tags_to_publish),
            media_tags=media_tags,
            thumbnail_url=thumbnail_url,
            sns_client=sns,
            topic_arn=topic_arn,
        )

        published.extend(results)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "published": published,
                "count": len(published),
            }
        ),
    }
