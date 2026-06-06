from http import HTTPMethod, HTTPStatus

from shared.aws_resources import get_table
from shared.schemas import QueryFileJobStatusResponse
from shared.utils import build_response_message, get_current_user, get_http_method


table = get_table()


def build_job_key(job_id: str) -> str:
    return f"QUERY_JOB#{job_id}"


def get_job_id(event: dict) -> str:
    path_parameters = event.get("pathParameters") or {}
    job_id = path_parameters.get("job_id") or path_parameters.get("jobId")

    if job_id:
        return job_id.strip()

    raw_path = event.get("rawPath") or event.get("path") or ""
    candidate = raw_path.rstrip("/").split("/")[-1].strip()

    if candidate and candidate != "jobs":
        return candidate

    raise ValueError("job_id is required")


def lambda_handler(event, context):
    allow_methods = [HTTPMethod.GET, HTTPMethod.OPTIONS]
    http_method = get_http_method(event)

    if http_method == "OPTIONS":
        return build_response_message(
            status_code=HTTPStatus.OK,
            body={"message": "OK"},
            allow_http_methods=allow_methods,
        )

    if http_method != "GET":
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Unsupported HTTP method"},
            allow_http_methods=allow_methods,
        )

    try:
        current_user = get_current_user(event)
        job_id = get_job_id(event)
        item = table.get_item(
            Key={"key": build_job_key(job_id)},
            ConsistentRead=True,
        ).get("Item")

        if item is None:
            return build_response_message(
                status_code=HTTPStatus.NOT_FOUND,
                body={"message": "Query file job not found"},
                allow_http_methods=allow_methods,
            )

        if item.get("owner_id") != current_user:
            return build_response_message(
                status_code=HTTPStatus.FORBIDDEN,
                body={"message": "Query file job does not belong to the current user"},
                allow_http_methods=allow_methods,
            )

        response = QueryFileJobStatusResponse(
            job_id=item["job_id"],
            status=item["status"],
            detected_tags=item.get("detected_tags") or {},
            count=int(item.get("count") or 0),
            results=item.get("results") or [],
            error_message=item.get("error_message"),
        )

        return build_response_message(
            status_code=HTTPStatus.OK,
            body=response.model_dump(mode="json"),
            allow_http_methods=allow_methods,
        )

    except ValueError as error:
        return build_response_message(
            status_code=HTTPStatus.BAD_REQUEST,
            body={"message": "Invalid query file job request", "error": str(error)},
            allow_http_methods=allow_methods,
        )
