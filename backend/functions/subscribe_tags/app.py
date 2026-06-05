import json
from http import HTTPMethod, HTTPStatus
from typing import Optional

from shared.schemas import SNSSubscribeRequest, SNSSubscribeResponse
from shared.aws_resources import get_sns_and_topic_arn
from shared.utils import build_response_message

sns, topic_arn = get_sns_and_topic_arn()


def parse_request(event: dict) -> SNSSubscribeRequest:
    body = event.get("body")
    return SNSSubscribeRequest(**json.loads(body))


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


def set_subscription_filter_policy(
    subscription_arn: str,
    tags: list[str],
    sns_client,
):
    filter_policy = {
        "tag": tags
    }

    sns_client.set_subscription_attributes(
        SubscriptionArn=subscription_arn,
        AttributeName="FilterPolicy",
        AttributeValue=json.dumps(filter_policy),
    )

    sns_client.set_subscription_attributes(
        SubscriptionArn=subscription_arn,
        AttributeName="FilterPolicyScope",
        AttributeValue="MessageAttributes",
    )


def is_confirmed_subscription_arn(subscription_arn: str | None) -> bool:
    if not subscription_arn:
        return False

    subscription_arn = subscription_arn.strip()

    if subscription_arn.lower() in {
        "pendingconfirmation",
        "deleted",
    }:
        return False

    return (
        subscription_arn.startswith("arn:aws:sns:")
        and len(subscription_arn.split(":")) >= 6
    )


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


def subscribe_email_to_tags(
    email: str,
    tags: list[str],
    sns_client,
    topic_arn: str,
):
    email = email.strip().lower()
    tags = [
        tag.strip().lower()
        for tag in tags
        if tag and tag.strip()
    ]

    existing_sub = find_subscription_by_email(
        email=email,
        sns_client=sns_client,
        topic_arn=topic_arn,
    )

    if existing_sub is not None:
        subscription_arn = existing_sub.get("SubscriptionArn")
        state = subscription_state(subscription_arn)

        if state == "pending":
            return SNSSubscribeResponse(
                email=email,
                tags=tags,
                subscription_arn=None,
                message=(
                    "A confirmation email has already been sent. "
                    "AWS SNS does not allow this pending subscription to be updated yet. "
                    "Please confirm the email first, then try changing the tags again."
                ),
            )

        if state == "deleted":
            return SNSSubscribeResponse(
                email=email,
                tags=tags,
                subscription_arn=None,
                message=(
                    "This SNS subscription was recently deleted. "
                    "AWS may take some time to fully remove the deleted subscription. "
                    "Please wait for AWS SNS to finish processing, then try subscribing again."
                ),
            )

        if state == "confirmed":
            set_subscription_filter_policy(
                subscription_arn=subscription_arn,
                tags=tags,
                sns_client=sns_client,
            )

            return SNSSubscribeResponse(
                email=email,
                tags=tags,
                subscription_arn=subscription_arn,
                message="Subscription tags updated.",
            )

        return SNSSubscribeResponse(
            email=email,
            tags=tags,
            subscription_arn=None,
            message=(
                "This SNS subscription is in an unknown state. "
                "Please wait and try again later."
            ),
        )

    response = sns_client.subscribe(
        TopicArn=topic_arn,
        Protocol="email",
        Endpoint=email,
        ReturnSubscriptionArn=True,
        Attributes={
            "FilterPolicy": json.dumps({"tag": tags}),
            "FilterPolicyScope": "MessageAttributes",
        },
    )

    return SNSSubscribeResponse(
        email=email,
        tags=tags,
        subscription_arn=response.get("SubscriptionArn"),
        message="Confirmation email sent. Please confirm it before receiving notifications.",
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

    res = subscribe_email_to_tags(
        email=request.email,
        tags=request.tags,
        sns_client=sns,
        topic_arn=topic_arn,
    )

    return build_response_message(
        status_code=HTTPStatus.OK,
        body=res.model_dump(mode="json"),
        allow_http_methods=[HTTPMethod.POST],
    )
