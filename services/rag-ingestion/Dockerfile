FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Build context is always the repo root (works from both main compose and standalone)
COPY services/rag-ingestion/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY packages/eliza-rag-ingestion /app/packages/eliza-rag-ingestion
RUN pip install --no-cache-dir /app/packages/eliza-rag-ingestion

COPY services/rag-ingestion/app.py /app/app.py

EXPOSE 8100

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8100/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8100", "--workers", "2"]
