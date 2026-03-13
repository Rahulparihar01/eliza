"""S3 helper functions for Airflow DAGs."""

from __future__ import annotations

import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)


def get_s3_client() -> Any:
    return boto3.client(
        "s3",
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )


def get_raw_bucket() -> str:
    return os.environ.get("S3_RAW_BUCKET", "eliza-raw-documents")


def get_processed_bucket() -> str:
    return os.environ.get("S3_PROCESSED_BUCKET", "eliza-processed-documents")


def upload_bytes(bucket: str, key: str, data: bytes, metadata: dict[str, str] | None = None) -> str:
    """Upload bytes to S3 and return the full s3:// URI."""
    s3 = get_s3_client()
    extra: dict[str, Any] = {}
    if metadata:
        extra["Metadata"] = metadata
    s3.put_object(Bucket=bucket, Key=key, Body=data, **extra)
    return f"s3://{bucket}/{key}"


def download_bytes(bucket: str, key: str) -> bytes:
    s3 = get_s3_client()
    resp = s3.get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()


def download_head_bytes(bucket: str, key: str, size: int = 1024) -> bytes:
    """Download only the first *size* bytes of an object."""
    s3 = get_s3_client()
    end = max(0, size - 1)
    resp = s3.get_object(Bucket=bucket, Key=key, Range=f"bytes=0-{end}")
    return resp["Body"].read()


def tag_object(bucket: str, key: str, tags: dict[str, str]) -> None:
    """Apply S3 object tags."""
    s3 = get_s3_client()
    tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]
    s3.put_object_tagging(
        Bucket=bucket,
        Key=key,
        Tagging={"TagSet": tag_set},
    )


def list_objects(bucket: str, prefix: str = "") -> list[dict[str, Any]]:
    """List all objects under a prefix (handles pagination)."""
    s3 = get_s3_client()
    objects: list[dict[str, Any]] = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            objects.append(obj)
    return objects
