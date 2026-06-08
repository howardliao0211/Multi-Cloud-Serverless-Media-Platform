FROM aussie-ecolens-ml-processor-base:latest

WORKDIR /app

RUN mkdir -p /app/shared

COPY backend/layers/python/shared/model.py /app/shared/model.py
COPY backend/layers/python/shared/species.py /app/shared/species.py
RUN touch /app/shared/__init__.py

COPY backend/gcp/ml_processor/server.py /app/server.py

CMD ["/app/.venv/bin/python", "server.py"]
