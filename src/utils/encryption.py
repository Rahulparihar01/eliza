"""
Encryption utilities for sensitive data.

This module provides encryption/decryption functionality for sensitive fields
like compensation data, using Fernet symmetric encryption.
"""

from typing import Optional
from sqlalchemy import TypeDecorator, String
from cryptography.fernet import Fernet
from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, component="encryption")


class EncryptionError(Exception):
    """Custom exception for encryption-related errors."""
    pass


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy custom type for encrypted string fields.
    
    Automatically encrypts data on write and decrypts on read.
    Uses Fernet symmetric encryption (AES 128 in CBC mode).
    
    Usage:
        class MyModel(Base):
            sensitive_field = Column(EncryptedString(255), nullable=True)
    
    Environment Variable Required:
        ENCRYPTION_KEY: Base64-encoded Fernet key
        Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """
    
    impl = String
    cache_ok = True
    
    def __init__(self, length: int = 255, *args, **kwargs):
        """
        Initialize encrypted string type.
        
        Args:
            length: Maximum length of the encrypted string in database
            *args, **kwargs: Additional arguments passed to String type
        """
        super().__init__(length, *args, **kwargs)
        self._cipher = None
    
    @property
    def cipher(self) -> Fernet:
        """Lazy-load cipher to avoid initialization issues."""
        if self._cipher is None:
            settings = get_settings()
            encryption_key = getattr(settings, 'encryption_key', None)
            
            if not encryption_key:
                logger.error(
                    "Encryption key not configured",
                    category=LogCategory.SECURITY,
                    operation="encryption_init",
                    user_message="System configuration error - encryption not available"
                )
                raise EncryptionError(
                    "ENCRYPTION_KEY environment variable not set. "
                    "Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
                )
            
            try:
                self._cipher = Fernet(encryption_key.encode())
            except Exception as e:
                logger.error(
                    f"Failed to initialize encryption cipher: {str(e)}",
                    category=LogCategory.SECURITY,
                    operation="encryption_init",
                    user_message="System configuration error - invalid encryption key"
                )
                raise EncryptionError(f"Invalid encryption key: {str(e)}")
        
        return self._cipher
    
    def process_bind_param(self, value: Optional[str], dialect) -> Optional[str]:
        """
        Encrypt value before storing in database.
        
        Args:
            value: Plain text value to encrypt
            dialect: SQLAlchemy dialect (unused)
            
        Returns:
            Encrypted string or None if value is None
        """
        if value is None:
            return None
        
        try:
            # Convert to string if not already
            if not isinstance(value, str):
                value = str(value)
            
            # Encrypt and return as string
            encrypted_bytes = self.cipher.encrypt(value.encode('utf-8'))
            encrypted_str = encrypted_bytes.decode('utf-8')
            
            logger.debug(
                "Value encrypted successfully",
                category=LogCategory.SECURITY,
                operation="encrypt",
                metadata={'encrypted_length': len(encrypted_str)}
            )
            
            return encrypted_str
            
        except Exception as e:
            logger.error(
                f"Encryption failed: {str(e)}",
                category=LogCategory.SECURITY,
                operation="encrypt",
                user_message="Failed to encrypt sensitive data"
            )
            raise EncryptionError(f"Encryption failed: {str(e)}")
    
    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        """
        Decrypt value after reading from database.
        
        Args:
            value: Encrypted string from database
            dialect: SQLAlchemy dialect (unused)
            
        Returns:
            Decrypted plain text or None if value is None
        """
        if value is None:
            return None
        
        try:
            # Decrypt and return as string
            decrypted_bytes = self.cipher.decrypt(value.encode('utf-8'))
            decrypted_str = decrypted_bytes.decode('utf-8')
            
            logger.debug(
                "Value decrypted successfully",
                category=LogCategory.SECURITY,
                operation="decrypt"
            )
            
            return decrypted_str
            
        except Exception as e:
            logger.error(
                f"Decryption failed: {str(e)}",
                category=LogCategory.SECURITY,
                operation="decrypt",
                user_message="Failed to decrypt sensitive data"
            )
            raise EncryptionError(f"Decryption failed: {str(e)}")


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.
    
    Returns:
        Base64-encoded encryption key as string
        
    Example:
        >>> key = generate_encryption_key()
        >>> print(f"ENCRYPTION_KEY={key}")
    """
    return Fernet.generate_key().decode('utf-8')


def validate_encryption_key(key: str) -> bool:
    """
    Validate that a string is a valid Fernet encryption key.
    
    Args:
        key: Encryption key to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        Fernet(key.encode('utf-8'))
        return True
    except Exception:
        return False


# Convenience function for manual encryption/decryption
def encrypt_value(value: str) -> str:
    """
    Manually encrypt a value using the configured encryption key.
    
    Args:
        value: Plain text to encrypt
        
    Returns:
        Encrypted string
    """
    settings = get_settings()
    encryption_key = getattr(settings, 'encryption_key', None)
    
    if not encryption_key:
        raise EncryptionError("ENCRYPTION_KEY not configured")
    
    cipher = Fernet(encryption_key.encode())
    return cipher.encrypt(value.encode('utf-8')).decode('utf-8')


def decrypt_value(encrypted_value: str) -> str:
    """
    Manually decrypt a value using the configured encryption key.
    
    Args:
        encrypted_value: Encrypted string to decrypt
        
    Returns:
        Decrypted plain text
    """
    settings = get_settings()
    encryption_key = getattr(settings, 'encryption_key', None)
    
    if not encryption_key:
        raise EncryptionError("ENCRYPTION_KEY not configured")
    
    cipher = Fernet(encryption_key.encode())
    return cipher.decrypt(encrypted_value.encode('utf-8')).decode('utf-8')

