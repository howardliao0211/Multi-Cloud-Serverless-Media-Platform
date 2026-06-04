FROM ml_base:latest

WORKDIR ${LAMBDA_TASK_ROOT}

ENV PYTHONPATH="/opt/python:${LAMBDA_TASK_ROOT}" \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLCONFIGDIR=/tmp/matplotlib

# Create shared package directory
RUN mkdir -p /opt/python/shared

# Copy only selected shared files
COPY layers/python/shared/__init__.py \
    layers/python/shared/model.py \
    layers/python/shared/aws_resources.py \
    layers/python/shared/schemas.py \
    layers/python/shared/utils.py \
    layers/python/shared/species.py \
    /opt/python/shared/

# Copy this Lambda function's app.py and Workload Identity Federation config
COPY container_functions/tag_image/app.py ${LAMBDA_TASK_ROOT}/app.py
COPY container_functions/tag_image/auth/gcp_wif_credentials.json ${LAMBDA_TASK_ROOT}/auth/gcp_wif_credentials.json

CMD ["app.lambda_handler"]