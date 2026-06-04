FROM lambda_python_base:latest

WORKDIR ${LAMBDA_TASK_ROOT}

ENV PYTHONPATH="/opt/python:${LAMBDA_TASK_ROOT}" \
    PYTHONDONTWRITEBYTECODE=1

RUN mkdir -p /opt/python/shared

COPY layers/python/shared/__init__.py \
    layers/python/shared/aws_resources.py \
    layers/python/shared/model.py \
    layers/python/shared/query_utils.py \
    layers/python/shared/schemas.py \
    layers/python/shared/species.py \
    layers/python/shared/utils.py \
    /opt/python/shared/

COPY container_functions/query_file/app.py ${LAMBDA_TASK_ROOT}/app.py

CMD ["app.lambda_handler"]
