import json
from http import HTTPMethod, HTTPStatus

from shared.schemas import SNSSubscribeRequest, SNSSubscribeResponse
from shared.aws_resources import get_sns_and_topic_arn
from shared.utils import build_response_message

sns, topic_arn = get_sns_and_topic_arn()


def parse_request(
    event: dict,
) -> SNSSubscribeRequest | None:
    body = event.get("body")
    return SNSSubscribeRequest(**json.loads(body))


def subscribe_email_to_tags(
    email: str,
    tags: list[str],
    sns_client,
    topic_arn: str,
):
    email = email.strip().lower()
    tags = [tag.strip().lower() for tag in tags]

    filter_policy = {
        "tag": tags
    }

    response = sns_client.subscribe(
        TopicArn=topic_arn,
        Protocol="email",
        Endpoint=email,
        ReturnSubscriptionArn=True,
        Attributes={
            "FilterPolicy": json.dumps(filter_policy),
            "FilterPolicyScope": "MessageAttributes",
        },
    )

    return SNSSubscribeResponse(
        email=email,
        tags=tags,
        subscription_arn=response.get("SubscriptionArn")
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
    tags = request.tags
    res = subscribe_email_to_tags(email, tags, sns, topic_arn)

    return build_response_message(
        status_code=HTTPStatus.OK,
        body=res.model_dump(mode="json"),
        allow_http_methods=[HTTPMethod.POST],
    )
