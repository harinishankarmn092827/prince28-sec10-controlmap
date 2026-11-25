# Stage 1: Build dependencies
FROM python:3.13-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project


# Stage 2: Production runtime
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app/src:/app" \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

RUN groupadd --system appgroup \
    && useradd --system \
       --gid appgroup \
       --home-dir /app \
       appuser

COPY --from=builder --chown=appuser:appgroup /app/.venv /app/.venv

COPY --chown=appuser:appgroup app/ /app/app/
COPY --chown=appuser:appgroup src/ /app/src/
COPY --chown=appuser:appgroup scripts/ /app/scripts/
COPY --chown=appuser:appgroup migrations/ /app/migrations/
COPY --chown=appuser:appgroup prompts/ /app/prompts/
COPY --chown=appuser:appgroup alembic.ini /app/alembic.ini

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]