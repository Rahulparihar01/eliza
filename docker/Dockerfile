# syntax=docker/dockerfile:1.4
# ============================================
# OPTIMIZED MULTI-STAGE BUILD
# ============================================

# Stage 1: Base with system dependencies + SQLite build (cached heavily)
FROM python:3.12-slim AS base

# Install system dependencies needed ONLY for SQLite build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Build and install SQLite from source for a newer runtime
RUN wget -q https://www.sqlite.org/2023/sqlite-autoconf-3430000.tar.gz \
    && tar xzf sqlite-autoconf-3430000.tar.gz \
    && cd sqlite-autoconf-3430000 \
    && ./configure --prefix=/usr/local \
    && make -j"$(nproc)" \
    && make install \
    && cd .. \
    && rm -rf sqlite-autoconf-3430000 sqlite-autoconf-3430000.tar.gz

# Stage 2: Python dependencies (rebuilds only when pyproject.toml/uv.lock changes)
FROM python:3.12-slim AS deps

WORKDIR /app

# Install uv (pinned version for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install build dependencies needed by some Python packages (e.g. psycopg2-binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency metadata first (cache layer)
COPY pyproject.toml uv.lock ./
COPY packages/eliza-rag-ingestion ./packages/eliza-rag-ingestion

# Install Python dependencies from the lockfile
# --no-install-project: don't install the project itself
# --compile-bytecode: pre-compile .pyc for faster cold starts
# --link-mode=copy: required for Docker multi-stage COPY compatibility
# NOTE: No cache mount - Northflank has limited ephemeral storage (21GB)
RUN uv sync --locked --no-install-project --compile-bytecode --link-mode=copy \
    && rm -rf /tmp/* /var/tmp/* ~/.cache

# Stage 3: Final runtime image
FROM python:3.12-slim AS runtime

WORKDIR /app

# Applet selection for modular deployments (default keeps current behavior).
ARG APPLETS=all

# Install minimal runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    postgresql-client \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Copy SQLite runtime artifacts from base stage
COPY --from=base /usr/local/lib/libsqlite3.so* /usr/local/lib/
COPY --from=base /usr/local/bin/sqlite3 /usr/local/bin/sqlite3
RUN ldconfig

# Copy virtual environment from deps stage
COPY --from=deps /app/.venv /app/.venv

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && mkdir -p /app/data /app/logs /app/cache /home/appuser/.cache \
    && chown -R appuser:appuser /app /home/appuser

# Set environment variables
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV APPLETS=$APPLETS
ENV TRANSFORMERS_CACHE=/app/cache/transformers
ENV HF_HOME=/app/cache/huggingface

# Copy application code (this layer changes most frequently - keep it last!)
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser applets/*.yaml ./applets/
COPY --chown=appuser:appuser applets/profiles/full.yaml ./applets/profiles/full.yaml
COPY --chown=appuser:appuser config/ ./config/
COPY --chown=appuser:appuser alembic/ ./alembic/
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser scripts/ ./scripts/

# Copy entrypoint script
COPY --chown=appuser:appuser docker/entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/ || exit 1

USER appuser

ENTRYPOINT ["entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5001"]
