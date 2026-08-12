# syntax=docker/dockerfile:1
FROM python:3.14.7-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/reponpc-model-cache

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --extra indexer --no-install-project
COPY src src
RUN uv sync --locked --no-dev --extra indexer
RUN /app/.venv/bin/python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small', device='cpu', trust_remote_code=False)"
COPY candidate_runner.py /app/candidate_runner.py

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

ENTRYPOINT ["/app/.venv/bin/python", "/app/candidate_runner.py"]
