"""MCP tool: fetch full document content from S3."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)


async def fetch_document(
    bucket: str,
    key: str,
    *,
    aws_region: str | None = None,
) -> dict[str, Any]:
    """Download a document from S3 and return its content + metadata."""
    region = aws_region or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    s3 = boto3.client("s3", region_name=region)

    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
        body = resp["Body"].read()
        content_type = resp.get("ContentType", "application/octet-stream")
        metadata = resp.get("Metadata", {})

        if content_type.startswith("text/") or key.endswith(".json"):
            text = body.decode("utf-8", errors="replace")
        else:
            text = f"[Binary document: {key}, {len(body)} bytes]"

        return {
            "key": key,
            "bucket": bucket,
            "content_type": content_type,
            "size": len(body),
            "text": text,
            "metadata": metadata,
        }
    except Exception:
        logger.exception(f"Failed to fetch s3://{bucket}/{key}")
        return {"key": key, "bucket": bucket, "error": "Failed to fetch document"}
