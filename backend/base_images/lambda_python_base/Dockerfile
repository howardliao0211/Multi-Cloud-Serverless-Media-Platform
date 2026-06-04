FROM public.ecr.aws/lambda/python:3.12 AS builder
FROM ghcr.io/astral-sh/uv:0.11.17 AS uv

FROM builder

WORKDIR ${LAMBDA_TASK_ROOT}

ENV PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

RUN --mount=from=uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv pip install \
      boto3>=1.43.9 \
      pydantic>=2.13.4 \
      requests>=2.32.3 \
      --target "${LAMBDA_TASK_ROOT}" \
      --index-url https://pypi.org/simple \
    && python - <<'PY_CLEAN'
from pathlib import Path
import shutil

root = Path("/var/task")

for name in ("tests", "test", "__pycache__"):
    for path in root.rglob(name):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)

for pattern in ("*.pyc", "*.pyo"):
    for path in root.rglob(pattern):
        if path.is_file():
            path.unlink(missing_ok=True)
PY_CLEAN
