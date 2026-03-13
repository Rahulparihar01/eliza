"""
Tenant storage settings service.

Stores tenant-level object storage configuration in Customer.config_data and
handles credential encryption/decryption.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from src.api.schemas.tenant_settings import (
    TenantObjectStorageBackend,
    TenantObjectStorageSettingsResponse,
    TenantObjectStorageSettingsUpdateRequest,
)
from src.models.customer import Customer
from src.utils.encryption import EncryptionError, decrypt_value, encrypt_value


@dataclass
class ResolvedTenantObjectStorageConfig:
    """Internal resolved object storage configuration with decrypted credentials."""

    backend: TenantObjectStorageBackend
    bucket: str
    region: Optional[str]
    endpoint_url: Optional[str]
    path_prefix: Optional[str]
    force_path_style: bool
    access_key_id: str
    secret_access_key: str
    default_local_source_path: Optional[str]


class TenantStorageSettingsService:
    """Service for tenant-scoped object storage settings."""

    CONFIG_ROOT_KEY = "storage_settings"
    OBJECT_STORAGE_KEY = "object_storage"
    ACCESS_KEY_ENCRYPTED = "access_key_id_encrypted"
    SECRET_KEY_ENCRYPTED = "secret_access_key_encrypted"

    def __init__(self, db: Session):
        self.db = db

    def _get_customer_or_raise(self, customer_id: str) -> Customer:
        customer = self.db.query(Customer).filter(Customer.customer_id == customer_id).first()
        if not customer:
            raise ValueError(f"Customer '{customer_id}' not found")
        return customer

    def _get_storage_root(self, customer: Customer) -> Dict[str, Any]:
        config_data = customer.config_data if isinstance(customer.config_data, dict) else {}
        storage_root = config_data.get(self.CONFIG_ROOT_KEY)
        if isinstance(storage_root, dict):
            return dict(storage_root)
        return {}

    def _set_storage_root(self, customer: Customer, storage_root: Dict[str, Any]) -> None:
        config_data = dict(customer.config_data or {})
        if storage_root:
            config_data[self.CONFIG_ROOT_KEY] = storage_root
        elif self.CONFIG_ROOT_KEY in config_data:
            config_data.pop(self.CONFIG_ROOT_KEY, None)
        customer.config_data = config_data

    def _get_object_storage_block(self, customer: Customer) -> Dict[str, Any]:
        storage_root = self._get_storage_root(customer)
        object_storage = storage_root.get(self.OBJECT_STORAGE_KEY)
        if isinstance(object_storage, dict):
            return dict(object_storage)
        return {}

    def _set_object_storage_block(self, customer: Customer, payload: Dict[str, Any]) -> None:
        storage_root = self._get_storage_root(customer)
        storage_root[self.OBJECT_STORAGE_KEY] = payload
        self._set_storage_root(customer, storage_root)

    @staticmethod
    def _normalize_optional(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def get_storage_settings(self, customer_id: str) -> TenantObjectStorageSettingsResponse:
        """Return tenant storage settings without exposing decrypted secrets."""
        customer = self._get_customer_or_raise(customer_id)
        object_storage = self._get_object_storage_block(customer)

        backend_raw = object_storage.get("backend")
        backend = None
        if backend_raw in {TenantObjectStorageBackend.S3.value, TenantObjectStorageBackend.MINIO.value}:
            backend = TenantObjectStorageBackend(backend_raw)

        return TenantObjectStorageSettingsResponse(
            backend=backend,
            bucket=self._normalize_optional(object_storage.get("bucket")),
            region=self._normalize_optional(object_storage.get("region")),
            endpoint_url=self._normalize_optional(object_storage.get("endpoint_url")),
            path_prefix=self._normalize_optional(object_storage.get("path_prefix")),
            force_path_style=bool(object_storage.get("force_path_style", False)),
            default_local_source_path=self._normalize_optional(
                object_storage.get("default_local_source_path")
            ),
            has_credentials=bool(
                object_storage.get(self.ACCESS_KEY_ENCRYPTED)
                and object_storage.get(self.SECRET_KEY_ENCRYPTED)
            ),
        )

    def update_storage_settings(
        self,
        customer_id: str,
        request: TenantObjectStorageSettingsUpdateRequest,
    ) -> TenantObjectStorageSettingsResponse:
        """Create or update tenant object storage settings."""
        customer = self._get_customer_or_raise(customer_id)
        existing = self._get_object_storage_block(customer)

        if request.backend == TenantObjectStorageBackend.MINIO and not request.endpoint_url:
            raise ValueError("endpoint_url is required when backend is 'minio'")

        provided_access_key = self._normalize_optional(request.access_key_id)
        provided_secret_key = self._normalize_optional(request.secret_access_key)
        has_existing_creds = bool(
            existing.get(self.ACCESS_KEY_ENCRYPTED) and existing.get(self.SECRET_KEY_ENCRYPTED)
        )
        rotating_creds = bool(provided_access_key or provided_secret_key)

        if rotating_creds and (not provided_access_key or not provided_secret_key):
            raise ValueError("Both access_key_id and secret_access_key are required when rotating credentials")
        if not rotating_creds and not has_existing_creds:
            raise ValueError(
                "Object storage credentials are required for initial setup "
                "(provide access_key_id and secret_access_key)"
            )

        force_path_style = bool(request.force_path_style)
        if request.backend == TenantObjectStorageBackend.MINIO and request.force_path_style is False:
            # MinIO typically requires path-style requests; enforce sane default.
            force_path_style = True

        payload: Dict[str, Any] = {
            "backend": request.backend.value,
            "bucket": request.bucket.strip(),
            "region": self._normalize_optional(request.region),
            "endpoint_url": self._normalize_optional(request.endpoint_url),
            "path_prefix": self._normalize_optional(request.path_prefix),
            "force_path_style": force_path_style,
            "default_local_source_path": self._normalize_optional(request.default_local_source_path),
            self.ACCESS_KEY_ENCRYPTED: existing.get(self.ACCESS_KEY_ENCRYPTED),
            self.SECRET_KEY_ENCRYPTED: existing.get(self.SECRET_KEY_ENCRYPTED),
        }

        if rotating_creds:
            try:
                payload[self.ACCESS_KEY_ENCRYPTED] = encrypt_value(provided_access_key)
                payload[self.SECRET_KEY_ENCRYPTED] = encrypt_value(provided_secret_key)
            except EncryptionError as exc:
                raise ValueError(f"Failed to encrypt storage credentials: {exc}") from exc

        self._set_object_storage_block(customer, payload)
        self.db.commit()
        self.db.refresh(customer)

        return self.get_storage_settings(customer_id)

    def resolve_storage_config(
        self,
        customer_id: str,
    ) -> Optional[ResolvedTenantObjectStorageConfig]:
        """Resolve decrypted tenant storage settings for runtime object operations."""
        customer = self._get_customer_or_raise(customer_id)
        object_storage = self._get_object_storage_block(customer)

        backend_raw = object_storage.get("backend")
        bucket = self._normalize_optional(object_storage.get("bucket"))
        access_key_encrypted = object_storage.get(self.ACCESS_KEY_ENCRYPTED)
        secret_key_encrypted = object_storage.get(self.SECRET_KEY_ENCRYPTED)

        if not backend_raw or not bucket or not access_key_encrypted or not secret_key_encrypted:
            return None

        try:
            backend = TenantObjectStorageBackend(backend_raw)
            access_key = decrypt_value(access_key_encrypted)
            secret_key = decrypt_value(secret_key_encrypted)
        except Exception:
            return None

        endpoint_url = self._normalize_optional(object_storage.get("endpoint_url"))
        if backend == TenantObjectStorageBackend.MINIO and not endpoint_url:
            return None

        return ResolvedTenantObjectStorageConfig(
            backend=backend,
            bucket=bucket,
            region=self._normalize_optional(object_storage.get("region")),
            endpoint_url=endpoint_url,
            path_prefix=self._normalize_optional(object_storage.get("path_prefix")),
            force_path_style=bool(object_storage.get("force_path_style", False)),
            access_key_id=access_key,
            secret_access_key=secret_key,
            default_local_source_path=self._normalize_optional(
                object_storage.get("default_local_source_path")
            ),
        )
