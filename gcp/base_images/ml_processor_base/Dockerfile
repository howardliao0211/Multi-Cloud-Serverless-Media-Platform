FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV UV_LINK_MODE=copy
ENV UV_CACHE_DIR=/tmp/uv-cache

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY gcp/ml_processor/pyproject.toml gcp/ml_processor/uv.lock ./
# The classifier checkpoint was saved from a model object that imports onnx2torch.
# Install only that module without dependencies to avoid pulling ONNX, which conflicts
# with MegaDetector's protobuf<=3.20.1 constraint.
RUN uv sync --frozen --no-dev \
    && uv pip install --python .venv/bin/python --no-deps onnx2torch==1.5.15 \
    && rm -rf /tmp/uv-cache /root/.cache/uv
