"""
AI Enablement Platform - MFA Management API Routes

FastAPI routes for managing multi-factor authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

from src.services.mfa_service import mfa_service
from src.models.auth import User
from src.middleware.authorization import (
    authorization_middleware,
    get_current_user,
    ResourceScope
)
from src.core.auth_context import CurrentUserContext

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models for request/response
class MFASetupResponse(BaseModel):
    secret: str
    qr_code: str
    backup_codes: List[str]
    manual_entry_key: str


class MFAVerificationRequest(BaseModel):
    verification_code: str


class MFAStatusResponse(BaseModel):
    enabled: bool
    setup: bool
    backup_codes_remaining: int
    last_used_at: Optional[str]


class MFACodeVerificationRequest(BaseModel):
    code: str


@router.post("/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Set up TOTP MFA for the current user.
    Returns QR code and backup codes.
    """
    try:
        setup_data = await mfa_service.setup_totp(current_user.user_id)
        
        return MFASetupResponse(
            secret=setup_data["secret"],
            qr_code=setup_data["qr_code"],
            backup_codes=setup_data["backup_codes"],
            manual_entry_key=setup_data["manual_entry_key"]
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error setting up MFA: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set up MFA"
        )


@router.post("/verify-setup")
async def verify_mfa_setup(
    request: MFAVerificationRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Verify TOTP code and enable MFA for the user.
    """
    try:
        success = await mfa_service.verify_and_enable_totp(
            current_user.user_id,
            request.verification_code
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code"
            )
        
        return {"message": "MFA enabled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying MFA setup: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify MFA setup"
        )


@router.post("/verify")
async def verify_mfa_code(
    request: MFACodeVerificationRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Verify MFA code (TOTP or backup code).
    """
    try:
        success = await mfa_service.verify_totp_code(
            current_user.user_id,
            request.code
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid MFA code"
            )
        
        return {"message": "MFA code verified successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying MFA code: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify MFA code"
        )


@router.get("/status", response_model=MFAStatusResponse)
async def get_mfa_status(
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Get MFA status for the current user.
    """
    try:
        status_data = await mfa_service.get_mfa_status(current_user.user_id)
        
        return MFAStatusResponse(
            enabled=status_data["enabled"],
            setup=status_data["setup"],
            backup_codes_remaining=status_data["backup_codes_remaining"],
            last_used_at=status_data["last_used_at"]
        )
        
    except Exception as e:
        logger.error(f"Error getting MFA status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get MFA status"
        )


@router.post("/disable")
async def disable_mfa(
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Disable MFA for the current user.
    """
    try:
        success = await mfa_service.disable_mfa(current_user.user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA not set up for user"
            )
        
        return {"message": "MFA disabled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling MFA: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable MFA"
        )


@router.post("/regenerate-backup-codes", response_model=List[str])
async def regenerate_backup_codes(
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Regenerate backup codes for the current user.
    """
    try:
        backup_codes = await mfa_service.regenerate_backup_codes(current_user.user_id)
        return backup_codes
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error regenerating backup codes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate backup codes"
        )


# Admin routes for managing other users' MFA
@router.post("/admin/disable/{user_id}")
async def admin_disable_mfa(
    user_id: int,
    current_user: CurrentUserContext = Depends(authorization_middleware.require_permission("users:update", resource_type="user"))
):
    """
    Admin endpoint to disable MFA for a specific user.
    Requires 'users:update' permission.
    """
    try:
        success = await mfa_service.disable_mfa(user_id, current_user.user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA not set up for user"
            )
        
        return {"message": f"MFA disabled for user {user_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling MFA for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to disable MFA"
        )


@router.get("/admin/status/{user_id}", response_model=MFAStatusResponse)
async def admin_get_mfa_status(
    user_id: int,
    current_user: CurrentUserContext = Depends(authorization_middleware.require_permission("users:read", resource_type="user"))
):
    """
    Admin endpoint to get MFA status for a specific user.
    Requires 'users:read' permission.
    """
    try:
        status_data = await mfa_service.get_mfa_status(user_id)
        
        return MFAStatusResponse(
            enabled=status_data["enabled"],
            setup=status_data["setup"],
            backup_codes_remaining=status_data["backup_codes_remaining"],
            last_used_at=status_data["last_used_at"]
        )
        
    except Exception as e:
        logger.error(f"Error getting MFA status for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get MFA status"
        )


@router.get("/admin/required/{user_id}")
async def check_mfa_required(
    user_id: int,
    current_user: CurrentUserContext = Depends(authorization_middleware.require_permission("users:read", resource_type="user"))
):
    """
    Check if MFA is required for a specific user based on their roles.
    Requires 'users:read' permission.
    """
    try:
        from src.services.auth_service import auth_service
        
        user = await auth_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        required = await mfa_service.is_mfa_required_for_user(user)
        
        return {
            "user_id": user_id,
            "mfa_required": required,
            "reason": "admin_role" if required else "standard_user"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking MFA requirement for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check MFA requirement"
        )
