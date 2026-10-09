# Backend image. Two targets:
#   dev  -> dev dependencies, code mounted as a volume, auto-reload
#   prod -> runtime dependencies only, code copied into the image (default)
FROM python:3.13-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
WORKDIR /app
# Unprivileged user; /data holds the SQLite database (mounted volume).
RUN useradd --create-home --uid 1000 jarvis && mkdir /data && chown jarvis /data
COPY pyproject.toml uv.lock ./

FROM base AS dev
RUN uv sync --frozen
USER jarvis
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS prod
RUN uv sync --frozen --no-dev
COPY app ./app
COPY modules ./modules
USER jarvis
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
