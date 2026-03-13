"""
Tenant-aware object storage service.

Uploads and deletes raw document files in tenant-configured S3/MinIO backends.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional

from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from src.services.tenant_storage_settings_service import (
    ResolvedTenantObjectStorageConfig,
    TenantStorageSettingsService,
)


class ObjectStorageService:
    """S3-compatible object storage helper for tenant document blobs."""

    def __init__(self, db: Session):
        self.db = db
        self.settings_service = TenantStorageSettingsService(db)

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """Return a safe object-key filename segment."""
        name = filename.strip()
        if not name:
            return "document.bin"
        # Keep key names deterministic and ASCII-safe.
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
        return name[:240] or "document.bin"

    @staticmethod
    def _build_client(config: ResolvedTenantObjectStorageConfig):
        addressing_style = "path" if config.force_path_style else "auto"

        import boto3

        return boto3.client(
            "s3",
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name=config.region or "us-east-1",
            endpoint_url=config.endpoint_url,
            config=BotoConfig(s3={"addressing_style": addressing_style}),
        )

    @staticmethod
    def _ensure_bucket_exists(client, config: ResolvedTenantObjectStorageConfig) -> bool:
        """Ensure the configured bucket exists; create it when missing."""
        try:
            client.head_bucket(Bucket=config.bucket)
            return False
        except ClientError as exc:
            error = exc.response.get("Error", {}) if isinstance(exc.response, dict) else {}
            code = str(error.get("Code", "")).strip()
            status = (
                exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if isinstance(exc.response, dict)
                else None
            )
            missing = code in {"404", "NoSuchBucket", "NotFound"} or status == 404
            if not missing:
                raise

            create_kwargs = {"Bucket": config.bucket}
            region = (config.region or "").strip()
            if region and region != "us-east-1":
                create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
            client.create_bucket(**create_kwargs)
            return True

    @staticmethod
    def build_object_key(
        *,
        customer_id: str,
        workspace_id: int,
        knowledge_base_id: Optional[int],
        document_id: int,
        filename: str,
        path_prefix: Optional[str] = None,
    ) -> str:
        """Build deterministic object key for workspace/KB document blobs."""
        safe_filename = ObjectStorageService._sanitize_filename(filename)
        kb_segment = f"kb_{knowledge_base_id}" if knowledge_base_id else "kb_unassigned"
        key_parts = [
            f"tenant_{customer_id}",
            f"workspace_{workspace_id}",
            kb_segment,
            f"doc_{document_id}",
            safe_filename,
        ]
        key = "/".join(key_parts)
        if path_prefix:
            normalized_prefix = path_prefix.strip().strip("/")
            if normalized_prefix:
                return f"{normalized_prefix}/{key}"
        return key

    async def upload_document_bytes(
        self,
        *,
        customer_id: str,
        workspace_id: int,
        knowledge_base_id: Optional[int],
        document_id: int,
        filename: str,
        content: bytes,
        content_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload document bytes and return persisted storage metadata."""
        resolved = self.settings_service.resolve_storage_config(customer_id)
        if not resolved:
            raise ValueError("Tenant object storage is not configured")

        object_key = self.build_object_key(
            customer_id=customer_id,
            workspace_id=workspace_id,
            knowledge_base_id=knowledge_base_id,
            document_id=document_id,
            filename=filename,
            path_prefix=resolved.path_prefix,
        )

        client = self._build_client(resolved)
        loop = asyncio.get_running_loop()

        def _upload() -> Dict[str, Any]:
            bucket_created = self._ensure_bucket_exists(client, resolved)
            kwargs = {
                "Bucket": resolved.bucket,
                "Key": object_key,
                "Body": content,
            }
            if content_type:
                kwargs["ContentType"] = content_type
            response = client.put_object(**kwargs)
            etag = str(response.get("ETag", "")).strip('"')
            return {
                "backend": resolved.backend.value,
                "bucket": resolved.bucket,
                "object_key": object_key,
                "etag": etag,
                "bucket_created": bucket_created,
                "managed": True,
                "endpoint_url": resolved.endpoint_url or "",
                "region": resolved.region or "",
            }

        return await loop.run_in_executor(None, _upload)

    async def list_objects(
        self,
        *,
        customer_id: str,
        bucket: str,
        prefix: Optional[str] = None,
        continuation_token: Optional[str] = None,
        max_keys: int = 1000,
    ) -> Dict[str, Any]:
        """List objects from a tenant-accessible S3-compatible bucket path."""
        resolved = self.settings_service.resolve_storage_config(customer_id)
        if not resolved:
            raise ValueError("Tenant object storage is not configured")

        client = self._build_client(resolved)
        loop = asyncio.get_running_loop()

        normalized_prefix = (prefix or "").strip().strip("/")
        if normalized_prefix:
            normalized_prefix = f"{normalized_prefix}/"

        def _list() -> Dict[str, Any]:
            kwargs: Dict[str, Any] = {
                "Bucket": bucket,
                "MaxKeys": max(1, min(max_keys, 1000)),
            }
            if normalized_prefix:
                kwargs["Prefix"] = normalized_prefix
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token

            response = client.list_objects_v2(**kwargs)
            contents = response.get("Contents") or []

            objects: List[Dict[str, Any]] = []
            for item in contents:
                key = str(item.get("Key") or "").strip()
                if not key:
                    continue
                etag = str(item.get("ETag") or "").strip().strip('"')
                last_modified = item.get("LastModified")
                objects.append(
                    {
                        "key": key,
                        "size": int(item.get("Size") or 0),
                        "etag": etag,
                        "last_modified": (
                            last_modified.isoformat()
                            if hasattr(last_modified, "isoformat")
                            else None
                        ),
                    }
                )

            return {
                "objects": objects,
                "is_truncated": bool(response.get("IsTruncated", False)),
                "next_token": response.get("NextContinuationToken"),
            }

        return await loop.run_in_executor(None, _list)

    async def get_object_bytes(
        self,
        *,
        customer_id: str,
        bucket: str,
        object_key: str,
    ) -> Dict[str, Any]:
        """Fetch object bytes and metadata from tenant-accessible storage."""
        resolved = self.settings_service.resolve_storage_config(customer_id)
        if not resolved:
            raise ValueError("Tenant object storage is not configured")

        client = self._build_client(resolved)
        loop = asyncio.get_running_loop()

        def _get() -> Dict[str, Any]:
            response = client.get_object(Bucket=bucket, Key=object_key)
            body = response.get("Body")
            content = body.read() if body is not None else b""
            if body is not None:
                body.close()

            last_modified = response.get("LastModified")
            etag = str(response.get("ETag") or "").strip().strip('"')
            return {
                "content": content,
                "content_type": response.get("ContentType"),
                "etag": etag,
                "last_modified": (
                    last_modified.isoformat()
                    if hasattr(last_modified, "isoformat")
                    else None
                ),
                "size": int(response.get("ContentLength") or len(content)),
            }

        return await loop.run_in_executor(None, _get)

    async def delete_object(
        self,
        *,
        customer_id: str,
        bucket: str,
        object_key: str,
    ) -> None:
        """Delete object from tenant-configured storage backend."""
        resolved = self.settings_service.resolve_storage_config(customer_id)
        if not resolved:
            return

        client = self._build_client(resolved)
        loop = asyncio.get_running_loop()

        def _delete() -> None:
            client.delete_object(Bucket=bucket, Key=object_key)

        await loop.run_in_executor(None, _delete)
