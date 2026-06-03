ARG BASE_IMAGE=ml-processor-base:gpu
FROM ${BASE_IMAGE}

WORKDIR /app

RUN mkdir -p /app/shared /models

COPY backend/layers/python/shared/model.py /app/shared/model.py
RUN touch /app/shared/__init__.py

COPY gcp/ml_processor/server.py /app/server.py
COPY gcp/ml_processor/models/model.pt /models/model.pt
COPY gcp/ml_processor/models/mdv5a.pt /models/mdv5a.pt

CMD ["uv", "run", "--frozen", "python", "server.py"]
