import json
import os
from typing import Literal
from http import HTTPMethod, HTTPStatus

from shared.schemas import UnsubscribeRequest, SubscriptionResponse
from shared.aws_resources import subscribe_email_to_tags, get_sub_table
from shared.utils import build_response_message

sub_table = get_sub_table()


def parse_request(
    event: dict,
) -> UnsubscribeRequest | None:
    body = event.get("body")
    return UnsubscribeRequest(**json.loads(body))


def unsubscribe_email(
    email: str,
    subscription_table,
) -> SubscriptionResponse:
    email = email.strip().lower()

    deleted_tags = []
    last_evaluated_key = None

    while True:
        scan_kwargs = {"FilterExpression": Attr("email").eq(email)}

        if last_evaluated_key:
            scan_kwargs["ExclusiveStartKey"] = last_evaluated_key

        response = subscription_table.scan(**scan_kwargs)

        items = response.get("Items", [])

        for item in items:
            tag = item["tag"]

            subscription_table.delete_item(
                Key={
                    "tag": tag,
                    "email": email,
                }
            )

            deleted_tags.append(tag)

        last_evaluated_key = response.get("LastEvaluatedKey")

        if not last_evaluated_key:
            break

    return SubscriptionResponse(
        email=email,
        tags=deleted_tags,
    )


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
    res = unsubscribe_email(email, sub_table)

    return build_response_message(
        status_code=HTTPStatus.OK,
        body={res.model_dump("json")},
        allow_http_methods=[HTTPMethod.POST],
    )
