import json
import os
from typing import Optional
from http import HTTPMethod, HTTPStatus

from shared.schemas import SNSUnsubscribeRequest
from shared.aws_resources import get_sns_and_topic_arn
from shared.utils import build_response_message

sns, topic_arn = get_sns_and_topic_arn()


def parse_request(
    event: dict,
) -> SNSUnsubscribeRequest | None:
    body = event.get("body")
    return SNSUnsubscribeRequest(**json.loads(body))


def find_subscription_arn_by_email(
    email: str,
    sns_client,
    topic_arn: str,
) -> Optional[str]:
    email = email.strip().lower()
    next_token = None

    while True:
        kwargs = {
            "TopicArn": topic_arn,
        }

        if next_token:
            kwargs["NextToken"] = next_token

        response = sns_client.list_subscriptions_by_topic(**kwargs)

        for sub in response.get("Subscriptions", []):
            protocol = sub.get("Protocol")
            endpoint = sub.get("Endpoint", "").strip().lower()
            subscription_arn = sub.get("SubscriptionArn")

            if (
                protocol == "email"
                and endpoint == email
                and subscription_arn
                and subscription_arn != "PendingConfirmation"
            ):
                return subscription_arn

        next_token = response.get("NextToken")

        if not next_token:
            break

    return None


def unsubscribe_email_from_tags(
    email: str,
    sns_client,
    topic_arn: str,
) -> bool:
    email = email.strip().lower()

    subscription_arn = find_subscription_arn_by_email(
        email=email,
        sns_client=sns_client,
        topic_arn=topic_arn,
    )

    if subscription_arn is None:
        return False

    sns_client.unsubscribe(
        SubscriptionArn=subscription_arn,
    )

    return True


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
    res = unsubscribe_email_from_tags(email, sns, topic_arn)

    if res is not True:
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": f"{email} does not have any subscription"},
            allow_http_methods=[HTTPMethod.POST],
        )
    else:
        return build_response_message(
            status_code=HTTPStatus.OK,
            body={"message": f"Unsubscribe tags for {email}"},
            allow_http_methods=[HTTPMethod.POST],
        )
