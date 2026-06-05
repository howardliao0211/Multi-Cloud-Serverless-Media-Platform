import json
import os
from typing import Literal
from http import HTTPMethod, HTTPStatus

from shared.schemas import SNSSubscribeRequest, Subscription, SubscriptionResponse
from shared.aws_resources import subscribe_email_to_tags, get_sub_table
from shared.utils import build_response_message

sub_table = get_sub_table()


def parse_request(
    event: dict,
) -> SNSSubscribeRequest | None:
    body = event.get("body")
    return SNSSubscribeRequest(**json.loads(body))


def subscribe_email_to_tags(
    email: str,
    tags: list[str],
    subscription_table,
) -> SubscriptionResponse:

    email = email.strip().lower()
    tags = [tag.lower().strip() for tag in tags]

    for tag in tags:
        sub = Subscription(tag=tag, email=email)
        subscription_table.put_item(Item=sub.model_dump("json"))

    return SubscriptionResponse(email=email, tags=tags)


def lambda_handler(event, context):

    allow_methods = [HTTPMethod.OPTIONS, HTTPMethod.POST]

    if event.get("httpMethod") == "OPTIONS":
        return build_response_message(
            status_code=HTTPStatus.OK,
            body={"message": "OK"},
            allow_http_methods=allow_methods,
        )

    request = parse_request(event)
    email = request.email
    tags = request.tags
    res = subscribe_email_to_tags(email, tags, sub_table)

    return build_response_message(
        status_code=HTTPStatus.OK,
        body={res.model_dump("json")},
        allow_http_methods=[HTTPMethod.POST],
    )
