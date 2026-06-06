import json
import json
from http import HTTPMethod, HTTPStatus
from typing import Literal

from shared.aws_resources import get_sns_and_topic_arn
from shared.utils import build_response_message
from shared.schemas import (
    SNSGetSubscriptionRequest,
    SubscriptionStatus,
    SNSGetSubscriptionResponse,
)

sns, topic_arn = get_sns_and_topic_arn()


def parse_request(
    event: dict,
) -> SNSGetSubscriptionRequest | None:
    query_params = event.get("queryStringParameters")
    return SNSGetSubscriptionRequest(**query_params)


def subscription_state(subscription_arn: str | None) -> SubscriptionStatus:
    if not subscription_arn:
        return SubscriptionStatus.none

    value = subscription_arn.strip().lower()

    if value == "pendingconfirmation":
        return SubscriptionStatus.pending

    if value == "deleted":
        return SubscriptionStatus.deleted

    if (
        subscription_arn.startswith("arn:aws:sns:")
        and len(subscription_arn.split(":")) >= 6
    ):
        return SubscriptionStatus.confirmed

    return SubscriptionStatus.invalid


def get_user_subscription_from_sns(
    email: str,
    sns_client,
    topic_arn: str,
) -> dict | None:
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

            if protocol != "email":
                continue

            if endpoint != email:
                continue

            state = subscription_state(subscription_arn)

            result = SNSGetSubscriptionResponse(email=email, tags=[], state=state)

            # PendingConfirmation and Deleted are not real ARNs.
            # You cannot call get_subscription_attributes on them.
            if state != SubscriptionStatus.confirmed:
                return result

            attributes_response = sns_client.get_subscription_attributes(
                SubscriptionArn=subscription_arn,
            )

            attributes = attributes_response.get("Attributes", {})
            filter_policy_raw = attributes.get("FilterPolicy")

            if filter_policy_raw:
                filter_policy = json.loads(filter_policy_raw)
                result.tags = filter_policy.get("tag", [])

            return result

        next_token = response.get("NextToken")

        if not next_token:
            break

    return SNSGetSubscriptionResponse(
        email=email, tags=[], state=SubscriptionStatus.none
    )


def lambda_handler(event, context):

    allow_methods = [HTTPMethod.OPTIONS, HTTPMethod.GET]

    if event.get("httpMethod") == "OPTIONS":
        return build_response_message(
            status_code=HTTPStatus.OK,
            body={"message": "OK"},
            allow_http_methods=allow_methods,
        )

    request = parse_request(event)
    email = request.email.strip().lower()

    res = get_user_subscription_from_sns(
        email=email,
        sns_client=sns,
        topic_arn=topic_arn,
    )

    return build_response_message(
        status_code=HTTPStatus.OK,
        body=res.model_dump(mode="json"),
        allow_http_methods=allow_methods,
    )
