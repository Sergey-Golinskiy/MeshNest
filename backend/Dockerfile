# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps for trimesh + Pillow + asyncpg + healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libjpeg-dev \
        zlib1g-dev \
        libpng-dev \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- builder layer (installs deps) ---
FROM base AS builder
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install --prefix=/install .

# --- runtime layer ---
FROM base AS runtime
COPY --from=builder /install /usr/local
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

ENV PORT=8000

EXPOSE 8000

# api / worker entrypoint выбирается через docker-compose `command:`
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
