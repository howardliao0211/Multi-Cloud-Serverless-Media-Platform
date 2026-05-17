import json
import os
import base64
import uuid
from datetime import datetime, timezone

import boto3


s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BUCKET_NAME = "aussie-eco-len-bucket-444177708053-us-east-1-an"
TABLE_NAME = "aussie-eco-len-table"

table = dynamodb.Table(TABLE_NAME)
tagger = None


def get_tagger():
    global tagger

    if tagger is None:
        from shared.model import ImageTagger

        tagger = ImageTagger()

    return tagger


def lambda_handler(event, context):
    try:
        body = parse_body(event)

        user_id = body["user_id"]
        image_name = body["image_name"]
        image_base64 = body["image_base64"]
        image_bytes = base64.b64decode(image_base64)

        image_id = str(uuid.uuid4())
        s3_key = f"uploads/{user_id}/{image_id}-{image_name}"
        tagger = get_tagger()

        # 1. Upload image to S3
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=image_bytes,
            ContentType=guess_content_type(image_name)
        )

        object_url = f"https://{BUCKET_NAME}.s3.us-east-1.amazonaws.com/{s3_key}"

        result = tagger.tag_image(image_base64)
        tags = list(result["tags"].keys())
        counts = list(result["tags"].values())

        # 2. Store metadata in DynamoDB
        item = {
            "uuid": image_id,
            "user_id": user_id,
            "image_name": image_name,
            "s3_bucket": BUCKET_NAME,
            "s3_key": s3_key,
            "full_url": object_url,
            "tags": tags,
            "counts": counts,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

        table.put_item(Item=item)

        return {
            "statusCode": 201,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "message": "Image uploaded successfully",
                "image_id": image_id,
                "s3_key": s3_key
            })
        }

    except KeyError as e:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": f"Missing required field: {str(e)}"
            })
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Internal server error"
            })
        }


def parse_body(event):
    """
    Supports both direct Lambda test events and API Gateway events.
    """
    if "body" in event:
        if isinstance(event["body"], str):
            return json.loads(event["body"])
        return event["body"]

    return event


def guess_content_type(filename):
    filename = filename.lower()

    if filename.endswith(".png"):
        return "image/png"
    if filename.endswith(".jpg") or filename.endswith(".jpeg"):
        return "image/jpeg"
    if filename.endswith(".webp"):
        return "image/webp"

    return "application/octet-stream"
