ARG BASE_IMAGE=ml-processor-base:gpu
FROM ${BASE_IMAGE}

WORKDIR /app

RUN mkdir -p /app/shared /models

COPY backend/layers/python/shared/model.py /app/shared/model.py
COPY backend/layers/python/shared/species.py /app/shared/species.py
RUN touch /app/shared/__init__.py

COPY backend-v2/gcp/ml_processor/server.py /app/server.py

CMD ["/app/.venv/bin/python", "server.py"]
