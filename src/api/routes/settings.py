"""
Settings API Routes

API endpoints for managing system settings (admin only).
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from src.models import get_db
from src.models.system_settings import SystemSetting, SettingType
from src.services.settings_service import SettingsService
from src.middleware.authorization import auth_middleware
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.API)

router = APIRouter(prefix="/v1/settings", tags=["Settings"])


# Schemas
class SettingResponse(BaseModel):
    setting_key: str
    setting_value: str | None
    setting_type: str
    description: str | None
    is_public: bool
    
    class Config:
        from_attributes = True


class SettingCreateRequest(BaseModel):
    setting_key: str = Field(..., min_length=1, max_length=255)
    setting_value: str | None
    setting_type: str = Field(default=SettingType.STRING.value)
    description: str | None = None
    is_public: bool = False


class SettingUpdateRequest(BaseModel):
    setting_value: str | None
    description: str | None = None
    is_public: bool | None = None


# Endpoints

@router.get(
    "",
    response_model=List[SettingResponse],
    summary="Get all settings",
    description="Get all system settings. Non-admins only see public settings."
)
async def get_settings(
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """Get all settings based on user permissions."""
    settings_service = SettingsService(db)
    
    # Non-admins only see public settings
    public_only = not current_user.has_permission("settings:read")
    
    settings = settings_service.get_all_settings(public_only=public_only)
    
    logger.info(
        "settings_list_retrieved",
        user_id=current_user.user_id,
        count=len(settings),
        public_only=public_only
    )
    
    return settings


@router.get(
    "/{setting_key}",
    response_model=SettingResponse,
    summary="Get a specific setting",
    description="Get a specific system setting by key."
)
async def get_setting(
    setting_key: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """Get a specific setting."""
    settings_service = SettingsService(db)
    setting = settings_service.get_setting(setting_key)
    
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{setting_key}' not found"
        )
    
    # Check if user can view this setting
    if not setting.is_public and not current_user.has_permission("settings:read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to private settings"
        )
    
    return setting


@router.post(
    "",
    response_model=SettingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new setting",
    description="Create a new system setting (admin only)."
)
async def create_setting(
    request: SettingCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("admin:settings:update"))
):
    """Create a new setting."""
    settings_service = SettingsService(db)
    
    # Check if setting already exists
    existing = settings_service.get_setting(request.setting_key)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Setting '{request.setting_key}' already exists"
        )
    
    setting = settings_service.set_setting(
        key=request.setting_key,
        value=request.setting_value,
        setting_type=request.setting_type,
        description=request.description,
        is_public=request.is_public
    )
    
    logger.info(
        "setting_created",
        user_id=current_user.user_id,
        setting_key=request.setting_key
    )
    
    return setting


@router.put(
    "/{setting_key}",
    response_model=SettingResponse,
    summary="Update a setting",
    description="Update an existing system setting (admin only)."
)
async def update_setting(
    setting_key: str,
    request: SettingUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("admin:settings:update"))
):
    """Update an existing setting."""
    settings_service = SettingsService(db)
    
    # Get existing setting
    existing = settings_service.get_setting(setting_key)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{setting_key}' not found"
        )
    
    # Update fields that were provided
    if request.setting_value is not None:
        existing.set_typed_value(request.setting_value)
    if request.description is not None:
        existing.description = request.description
    if request.is_public is not None:
        existing.is_public = request.is_public
    
    db.commit()
    db.refresh(existing)
    
    logger.info(
        "setting_updated",
        user_id=current_user.user_id,
        setting_key=setting_key
    )
    
    return existing


@router.delete(
    "/{setting_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a setting",
    description="Delete a system setting (admin only)."
)
async def delete_setting(
    setting_key: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("admin:settings:update"))
):
    """Delete a setting."""
    settings_service = SettingsService(db)
    
    deleted = settings_service.delete_setting(setting_key)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{setting_key}' not found"
        )
    
    logger.info(
        "setting_deleted",
        user_id=current_user.user_id,
        setting_key=setting_key
    )
    
    return None


# Specific convenience endpoints

@router.get(
    "/default/company_hr_dataset",
    summary="Get default company for HR queries",
    description="Get the default company used for HR data queries when not explicitly specified."
)
async def get_default_company(
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """Get the default company HR dataset setting."""
    settings_service = SettingsService(db)
    default_company = settings_service.get_default_company_hr_dataset()
    
    return {
        "setting_key": "default_company_hr_dataset",
        "value": default_company
    }


@router.put(
    "/default/company_hr_dataset",
    summary="Set default company for HR queries",
    description="Set the default company used for HR data queries (admin only)."
)
async def set_default_company(
    company_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("admin:settings:update"))
):
    """Set the default company HR dataset."""
    settings_service = SettingsService(db)
    setting = settings_service.set_default_company_hr_dataset(company_id)
    
    logger.info(
        "default_company_updated",
        user_id=current_user.user_id,
        company_id=company_id
    )
    
    return {
        "setting_key": "default_company_hr_dataset",
        "value": setting.setting_value,
        "message": f"Default company set to '{company_id}'"
    }


# Vector Search Settings

class VectorSearchSettingsResponse(BaseModel):
    similarity_threshold: float = Field(..., description="Minimum similarity score (0.0-1.0)")
    result_limit: int = Field(..., description="Maximum number of results to return (k value)")


class VectorSearchSettingsUpdateRequest(BaseModel):
    similarity_threshold: float | None = Field(None, ge=0.0, le=1.0, description="Minimum similarity score (0.0-1.0)")
    result_limit: int | None = Field(None, ge=1, le=100, description="Maximum number of results (1-100)")


@router.get(
    "/vector-search/config",
    response_model=VectorSearchSettingsResponse,
    summary="Get vector search configuration",
    description="Get current vector search settings (similarity threshold and result limit)."
)
async def get_vector_search_config(
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """Get vector search configuration."""
    settings_service = SettingsService(db)
    
    return {
        "similarity_threshold": settings_service.get_vector_search_similarity_threshold(),
        "result_limit": settings_service.get_vector_search_result_limit()
    }


@router.put(
    "/vector-search/config",
    response_model=VectorSearchSettingsResponse,
    summary="Update vector search configuration",
    description="Update vector search settings (admin only). Changes apply to all future searches."
)
async def update_vector_search_config(
    request: VectorSearchSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("admin:settings:update"))
):
    """Update vector search configuration."""
    settings_service = SettingsService(db)
    
    # Update threshold if provided
    if request.similarity_threshold is not None:
        settings_service.set_vector_search_similarity_threshold(request.similarity_threshold)
        logger.info(
            "vector_search_threshold_updated",
            user_id=current_user.user_id,
            threshold=request.similarity_threshold
        )
    
    # Update limit if provided
    if request.result_limit is not None:
        settings_service.set_vector_search_result_limit(request.result_limit)
        logger.info(
            "vector_search_limit_updated",
            user_id=current_user.user_id,
            limit=request.result_limit
        )
    
    # Return current values
    return {
        "similarity_threshold": settings_service.get_vector_search_similarity_threshold(),
        "result_limit": settings_service.get_vector_search_result_limit()
    }


# Google Email Integration Settings

class GoogleEmailConfigResponse(BaseModel):
    client_id: str | None = Field(None, description="Google OAuth Client ID")
    client_secret: str | None = Field(None, description="Google OAuth Client Secret (masked)")
    redirect_uri: str | None = Field(None, description="OAuth redirect URI")
    is_connected: bool = Field(False, description="Whether Google account is connected")
    connected_email: str | None = Field(None, description="Connected Google email address")


class GoogleEmailConfigUpdateRequest(BaseModel):
    client_id: str | None = Field(None, description="Google OAuth Client ID")
    client_secret: str | None = Field(None, description="Google OAuth Client Secret")
    redirect_uri: str | None = Field(None, description="OAuth redirect URI")


@router.get(
    "/google-email/config",
    response_model=GoogleEmailConfigResponse,
    summary="Get Google email configuration",
    description="Get current Google OAuth configuration for email integration (admin only)."
)
async def get_google_email_config(
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("admin:settings:read"))
):
    """Get Google email configuration."""
    settings_service = SettingsService(db)
    
    client_id = settings_service.get_setting("google_email_client_id")
    client_secret = settings_service.get_setting("google_email_client_secret")
    redirect_uri = settings_service.get_setting("google_email_redirect_uri")
    connected_email = settings_service.get_setting("google_email_connected_email")
    
    # Mask client secret if present
    masked_secret = None
    if client_secret and client_secret.setting_value:
        masked_secret = "•" * 20  # Mask the secret
    
    return {
        "client_id": client_id.setting_value if client_id else None,
        "client_secret": masked_secret,
        "redirect_uri": redirect_uri.setting_value if redirect_uri else None,
        "is_connected": bool(connected_email and connected_email.setting_value),
        "connected_email": connected_email.setting_value if connected_email else None
    }


@router.put(
    "/google-email/config",
    response_model=GoogleEmailConfigResponse,
    summary="Update Google email configuration",
    description="Update Google OAuth configuration for email integration (admin only)."
)
async def update_google_email_config(
    request: GoogleEmailConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("admin:settings:update"))
):
    """Update Google email configuration."""
    settings_service = SettingsService(db)
    
    # Update client ID if provided
    if request.client_id is not None:
        settings_service.set_setting(
            key="google_email_client_id",
            value=request.client_id,
            setting_type=SettingType.STRING.value,
            description="Google OAuth Client ID for email integration",
            is_public=False
        )
        logger.info(
            "google_email_client_id_updated",
            user_id=current_user.user_id
        )
    
    # Update client secret if provided
    if request.client_secret is not None:
        settings_service.set_setting(
            key="google_email_client_secret",
            value=request.client_secret,
            setting_type=SettingType.STRING.value,
            description="Google OAuth Client Secret for email integration",
            is_public=False
        )
        logger.info(
            "google_email_client_secret_updated",
            user_id=current_user.user_id
        )
    
    # Update redirect URI if provided
    if request.redirect_uri is not None:
        settings_service.set_setting(
            key="google_email_redirect_uri",
            value=request.redirect_uri,
            setting_type=SettingType.STRING.value,
            description="Google OAuth redirect URI for email integration",
            is_public=False
        )
        logger.info(
            "google_email_redirect_uri_updated",
            user_id=current_user.user_id,
            redirect_uri=request.redirect_uri
        )
    
    # Return updated config
    client_id = settings_service.get_setting("google_email_client_id")
    client_secret = settings_service.get_setting("google_email_client_secret")
    redirect_uri = settings_service.get_setting("google_email_redirect_uri")
    connected_email = settings_service.get_setting("google_email_connected_email")
    
    masked_secret = None
    if client_secret and client_secret.setting_value:
        masked_secret = "•" * 20
    
    return {
        "client_id": client_id.setting_value if client_id else None,
        "client_secret": masked_secret,
        "redirect_uri": redirect_uri.setting_value if redirect_uri else None,
        "is_connected": bool(connected_email and connected_email.setting_value),
        "connected_email": connected_email.setting_value if connected_email else None
    }


@router.post(
    "/google-email/disconnect",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect Google email account",
    description="Disconnect the connected Google email account (admin only)."
)
async def disconnect_google_email(
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("admin:settings:update"))
):
    """Disconnect Google email account."""
    settings_service = SettingsService(db)
    
    # Remove connected email
    settings_service.delete_setting("google_email_connected_email")
    
    logger.info(
        "google_email_disconnected",
        user_id=current_user.user_id
    )
    
    return None

