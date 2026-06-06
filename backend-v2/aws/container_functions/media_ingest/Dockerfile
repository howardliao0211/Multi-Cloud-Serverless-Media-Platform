FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

COPY backend-v2/aws/layers/python/shared ./shared
COPY backend-v2/aws/container_functions/media_ingest/app.py ./app.py
COPY backend-v2/aws/container_functions/media_ingest/requirements.txt ./requirements.txt
COPY backend-v2/aws/container_functions/media_ingest/auth/gcp_wif_credentials.json ./auth/gcp_wif_credentials.json

RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt --target "${LAMBDA_TASK_ROOT}" && \
    python -c "import google.auth; print('google-auth installed at', google.auth.__file__)"

CMD ["app.lambda_handler"]
