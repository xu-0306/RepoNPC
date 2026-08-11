# syntax=docker/dockerfile:1
FROM node:24.14.0-bookworm-slim AS web-build

WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN corepack enable && corepack prepare pnpm@11.16.0 --activate && pnpm install --frozen-lockfile
COPY apps/web apps/web
RUN pnpm --dir apps/web run build

FROM python:3.14.7-slim-bookworm AS python-build
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src src
RUN uv sync --locked --no-dev

FROM python:3.14.7-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TMPDIR=/tmp/reponpc
WORKDIR /app
RUN groupadd --system --gid 10001 reponpc \
    && useradd --system --uid 10001 --gid reponpc --home-dir /nonexistent --shell /usr/sbin/nologin reponpc \
    && mkdir --parents /var/lib/reponpc /tmp/reponpc \
    && chown --recursive reponpc:reponpc /var/lib/reponpc /tmp/reponpc
COPY --from=python-build /app/.venv /app/.venv
COPY --from=python-build /app/src /app/src
COPY --from=web-build /app/apps/web/dist /app/apps/web/dist

USER reponpc:reponpc
EXPOSE 8000
VOLUME ["/var/lib/reponpc"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "from urllib.request import urlopen; assert urlopen('http://127.0.0.1:8000/healthz', timeout=3).status == 200"]
CMD ["reponpc"]
