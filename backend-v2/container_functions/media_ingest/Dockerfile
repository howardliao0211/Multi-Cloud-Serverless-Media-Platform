FROM public.ecr.aws/lambda/python:3.12

WORKDIR ${LAMBDA_TASK_ROOT}

COPY layers/python/shared ./shared
COPY container_functions/media_ingest/app.py ./app.py
COPY container_functions/media_ingest/requirements.txt ./requirements.txt
COPY container_functions/media_ingest/auth/gcp_wif_credentials.json ./auth/gcp_wif_credentials.json

RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt --target "${LAMBDA_TASK_ROOT}" && \
    python -c "import google.auth; print('google-auth installed at', google.auth.__file__)"

CMD ["app.lambda_handler"]
