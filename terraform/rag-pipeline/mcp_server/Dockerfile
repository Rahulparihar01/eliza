# Build from repo root:
#   docker build -f terraform/rag-pipeline/mcp_server/Dockerfile .
#
# Build from extracted rag-pipeline directory (customer deployment):
#   docker build -f mcp_server/Dockerfile .
#   (requires packages/eliza-rag-ingestion/ alongside mcp_server/)

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY terraform/rag-pipeline/mcp_server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY packages/eliza-rag-ingestion /app/packages/eliza-rag-ingestion
RUN pip install --no-cache-dir --no-deps /app/packages/eliza-rag-ingestion

COPY terraform/rag-pipeline/mcp_server/ /app/mcp_server/

ENV PYTHONPATH=/app
ENV MCP_TRANSPORT=sse
EXPOSE 8888

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8888/health')" || exit 1

CMD ["python", "-m", "mcp_server.server"]
