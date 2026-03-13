"""
AI Enablement Platform - Tenant Settings API Schemas

Pydantic models for tenant-specific settings including theme/branding.
"""

import re
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# THEME PRESETS
# ============================================================================

THEME_PRESETS = {
    'eliza-forge': {
        'primary': '#c9506b',
        'primaryLight': '#e8a598',
        'accent': '#f5c4a1',
        'text': '#5c4a5a',
    },
    'ocean-blue': {
        'primary': '#0369a1',
        'primaryLight': '#38bdf8',
        'accent': '#06b6d4',
        'text': '#334155',
    },
    'forest-green': {
        'primary': '#15803d',
        'primaryLight': '#4ade80',
        'accent': '#84cc16',
        'text': '#374151',
    },
    'royal-purple': {
        'primary': '#7c3aed',
        'primaryLight': '#a78bfa',
        'accent': '#c084fc',
        'text': '#374151',
    },
}

DEFAULT_THEME = THEME_PRESETS['eliza-forge']


# ============================================================================
# THEME SCHEMAS
# ============================================================================

class ThemeResponse(BaseModel):
    """Response containing theme data."""
    primary: str = Field(..., description="Primary brand color (hex)", example="#c9506b")
    primaryLight: str = Field(..., description="Light variant of primary (hex)", example="#e8a598")
    accent: str = Field(..., description="Accent/coral color (hex)", example="#f5c4a1")
    text: str = Field(..., description="Primary text color (hex)", example="#5c4a5a")
    preset: Optional[str] = Field(None, description="Preset name if using preset", example="eliza-forge")
    
    class Config:
        from_attributes = True


class ThemeUpdateRequest(BaseModel):
    """Request to update theme."""
    primary: str = Field(..., description="Primary brand color (hex)", example="#c9506b")
    primaryLight: str = Field(..., description="Light variant of primary (hex)", example="#e8a598")
    accent: str = Field(..., description="Accent/coral color (hex)", example="#f5c4a1")
    text: str = Field(..., description="Primary text color (hex)", example="#5c4a5a")
    preset: Optional[str] = Field(None, description="Preset name if using preset", example="eliza-forge")
    
    @field_validator('primary', 'primaryLight', 'accent', 'text')
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        """Validate hex color format (#RRGGBB)."""
        if not re.match(r'^#[0-9A-Fa-f]{6}$', v):
            raise ValueError(f'Invalid hex color format: {v}. Must be #RRGGBB')
        return v.lower()
    
    @field_validator('preset')
    @classmethod
    def validate_preset(cls, v: Optional[str]) -> Optional[str]:
        """Validate preset name if provided."""
        if v is not None and v not in THEME_PRESETS:
            raise ValueError(f'Invalid preset: {v}. Valid presets: {list(THEME_PRESETS.keys())}')
        return v


# ============================================================================
# OBJECT STORAGE SCHEMAS
# ============================================================================

class TenantObjectStorageBackend(str, Enum):
    """Supported tenant-scoped object storage backends."""

    S3 = "s3"
    MINIO = "minio"


class TenantObjectStorageSettingsResponse(BaseModel):
    """Object storage settings for the current tenant."""

    backend: Optional[TenantObjectStorageBackend] = Field(
        None,
        description="Configured storage backend (s3 or minio)",
    )
    bucket: Optional[str] = Field(None, description="Bucket name used for document objects")
    region: Optional[str] = Field(None, description="AWS region for S3 (optional for MinIO)")
    endpoint_url: Optional[str] = Field(
        None,
        description="Custom endpoint URL (required for MinIO, optional for S3-compatible APIs)",
    )
    path_prefix: Optional[str] = Field(
        None,
        description="Optional key prefix used for tenant/workspace object organization",
    )
    force_path_style: bool = Field(
        default=False,
        description="Use path-style S3 addressing (typically required for MinIO)",
    )
    default_local_source_path: Optional[str] = Field(
        None,
        description="Default virtual local-directory source path for new knowledge bases",
    )
    has_credentials: bool = Field(
        default=False,
        description="Whether access credentials are configured (secret is never returned)",
    )


class TenantObjectStorageSettingsUpdateRequest(BaseModel):
    """Update tenant object storage settings."""

    backend: TenantObjectStorageBackend = Field(
        ...,
        description="Storage backend to use for tenant documents",
    )
    bucket: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Bucket name used for document objects",
    )
    region: Optional[str] = Field(
        None,
        max_length=100,
        description="AWS region for S3 (optional for MinIO)",
    )
    endpoint_url: Optional[str] = Field(
        None,
        max_length=512,
        description="Custom endpoint URL (required for MinIO)",
    )
    path_prefix: Optional[str] = Field(
        None,
        max_length=512,
        description="Optional key prefix used for object keys",
    )
    force_path_style: bool = Field(
        default=False,
        description="Use path-style S3 URLs (recommended for MinIO)",
    )
    access_key_id: Optional[str] = Field(
        None,
        max_length=255,
        description="Access key ID (send to rotate credentials)",
    )
    secret_access_key: Optional[str] = Field(
        None,
        max_length=2048,
        description="Secret access key (send with access_key_id to rotate credentials)",
    )
    default_local_source_path: Optional[str] = Field(
        None,
        max_length=1024,
        description="Default virtual local-directory source path for knowledge bases",
    )

    @field_validator("endpoint_url")
    @classmethod
    def validate_endpoint_url(cls, v: Optional[str]) -> Optional[str]:
        """Normalize empty endpoint URL to None."""
        if v is None:
            return None
        normalized = v.strip()
        return normalized or None

    @field_validator("path_prefix")
    @classmethod
    def normalize_path_prefix(cls, v: Optional[str]) -> Optional[str]:
        """Normalize object key prefix for consistent key generation."""
        if v is None:
            return None
        normalized = v.strip().strip("/")
        return normalized or None
