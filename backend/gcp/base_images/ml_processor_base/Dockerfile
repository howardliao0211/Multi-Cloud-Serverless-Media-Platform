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

COPY backend/gcp/ml_processor/pyproject.toml backend/gcp/ml_processor/uv.lock ./
# The classifier checkpoint was saved from a model object that imports onnx2torch.
# onnx2torch is required when torch.load unpickles the classifier model.
# Install it without dependencies, while explicitly installing the ONNX runtime
# packages needed by the serialized classifier.
RUN uv sync --frozen --no-dev \
    && uv pip install --python .venv/bin/python --no-deps onnx2torch==1.5.15 'onnx>=1.16,<2' ml_dtypes \
    && rm -rf /tmp/uv-cache /root/.cache/uv
