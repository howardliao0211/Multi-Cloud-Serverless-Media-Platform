import json
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


def subscription_state(subscription_arn: str | None) -> str:
    if not subscription_arn:
        return "none"

    value = subscription_arn.strip().lower()

    if value == "pendingconfirmation":
        return "pending"

    if value == "deleted":
        return "deleted"

    if subscription_arn.startswith("arn:aws:sns:") and len(subscription_arn.split(":")) >= 6:
        return "confirmed"

    return "invalid"


def find_subscription_by_email(
    email: str,
    sns_client,
    topic_arn: str,
) -> Optional[dict]:
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

            if protocol == "email" and endpoint == email:
                return sub

        next_token = response.get("NextToken")

        if not next_token:
            break

    return None


def unsubscribe_email_from_tags(
    email: str,
    sns_client,
    topic_arn: str,
) -> str:
    email = email.strip().lower()

    subscription = find_subscription_by_email(
        email=email,
        sns_client=sns_client,
        topic_arn=topic_arn,
    )

    if subscription is None:
        return (
            False,
            f"{email} does not have any subscription.",
        )

    subscription_arn = subscription.get("SubscriptionArn")
    state = subscription_state(subscription_arn)

    print(f"subscription_arn: {subscription_arn}")
    print(f"subscription_state: {state}")

    if state == "pending":
        return (
            f"{email} has a pending SNS subscription. "
            "AWS SNS does not allow pending email subscriptions to be unsubscribed from the app. "
            "Please confirm the email first, or wait for AWS SNS to remove the pending subscription."
        )

    if state == "deleted":
        return (
            f"{email} has a recently deleted SNS subscription. "
            "AWS SNS may take some time to fully remove it. "
            "Please wait for AWS SNS to finish processing, then try again."
        )

    if state != "confirmed":
        return (
            f"{email} has an SNS subscription in an invalid state: {subscription_arn}. "
            "Please wait and try again later."
        )

    sns_client.unsubscribe(
        SubscriptionArn=subscription_arn,
    )

    return f"Unsubscribed tags for {email}",


def lambda_handler(event, context):

    allow_methods = [HTTPMethod.OPTIONS, HTTPMethod.POST]

    if event.get("httpMethod") == "OPTIONS":
        return build_response_message(
            status_code=HTTPStatus.OK,
            body={"message": "OK"},
            allow_http_methods=allow_methods,
        )

    request = parse_request(event)
    email = request.email.strip().lower()

    message = unsubscribe_email_from_tags(
        email=email,
        sns_client=sns,
        topic_arn=topic_arn,
    )

    return build_response_message(
        status_code=HTTPStatus.OK,
        body={"message": message},
        allow_http_methods=[HTTPMethod.POST],
    )
