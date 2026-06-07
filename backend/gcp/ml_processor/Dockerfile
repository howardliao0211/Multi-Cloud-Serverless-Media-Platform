ARG BASE_IMAGE=ml-processor-base:gpu
FROM ${BASE_IMAGE}

WORKDIR /app

RUN mkdir -p /app/shared /models

COPY backend/layers/python/shared/model.py /app/shared/model.py
COPY backend/layers/python/shared/species.py /app/shared/species.py
RUN touch /app/shared/__init__.py

COPY backend/gcp/ml_processor/server.py /app/server.py
COPY backend/gcp/ml_processor/models/model.pt /models/model.pt
COPY backend/gcp/ml_processor/models/mdv5a.pt /models/mdv5a.pt

CMD ["/app/.venv/bin/python", "server.py"]
