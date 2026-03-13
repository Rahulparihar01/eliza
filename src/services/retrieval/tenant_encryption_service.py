"""
Tenant-scoped encryption service.

Derives a unique Fernet key per customer_id from a master secret using HKDF,
so each tenant's tokens are encrypted with a distinct key.
"""

import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src.core.config import get_settings

logger = logging.getLogger(__name__)


class TenantEncryptionService:
    """Encrypt / decrypt values using a per-tenant derived key."""

    @staticmethod
    def _derive_key(customer_id: str) -> bytes:
        settings = get_settings()
        master = settings.master_encryption_key
        if not master:
            raise ValueError("MASTER_ENCRYPTION_KEY is not configured")
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=customer_id.encode(),
        )
        return base64.urlsafe_b64encode(hkdf.derive(master.encode()))

    @classmethod
    def encrypt(cls, customer_id: str, value: str) -> str:
        f = Fernet(cls._derive_key(customer_id))
        return f.encrypt(value.encode()).decode()

    @classmethod
    def decrypt(cls, customer_id: str, value: str) -> str:
        f = Fernet(cls._derive_key(customer_id))
        return f.decrypt(value.encode()).decode()
