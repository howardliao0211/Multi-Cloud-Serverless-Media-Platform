FROM gcp_client_base:latest

WORKDIR ${LAMBDA_TASK_ROOT}

ENV PYTHONPATH="/opt/python:${LAMBDA_TASK_ROOT}" \
    PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p /opt/python/shared

# Copy only selected shared files
COPY layers/python/shared/__init__.py \
    layers/python/shared/aws_resources.py \
    layers/python/shared/query_utils.py \
    layers/python/shared/schemas.py \
    layers/python/shared/species.py \
    layers/python/shared/utils.py \
    layers/python/shared/gcp_ml_client.py \
    layers/python/shared/gcp_ml_contracts.py \
    /opt/python/shared/

# Copy this Lambda function's app.py and Workload Identity Federation config
COPY container_functions/query_file/auth/gcp_wif_credentials.json ${LAMBDA_TASK_ROOT}/auth/gcp_wif_credentials.json
COPY container_functions/query_file/app.py ${LAMBDA_TASK_ROOT}/app.py

CMD ["app.lambda_handler"]
