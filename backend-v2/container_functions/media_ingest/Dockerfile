FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

COPY layers/python/shared ./shared
COPY container_functions/media_ingest/app.py ./app.py
COPY container_functions/media_ingest/requirements.txt ./requirements.txt

RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -t .

CMD ["app.lambda_handler"]
