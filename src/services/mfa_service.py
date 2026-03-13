"""
AI Enablement Platform - Multi-Factor Authentication Service

Service for managing TOTP-based MFA and backup codes.
"""

import logging
import secrets
import pyotp
import qrcode
import io
import base64
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session

from src.models.auth import User, UserMFA
from src.services.base_service import BaseService
from src.services.audit_service import audit_service, AuditAction, AuditSeverity

logger = logging.getLogger(__name__)


class MFAService(BaseService):
    """Service for managing multi-factor authentication."""
    
    def __init__(self):
        self.issuer_name = "AI Enablement Platform"
        self.backup_codes_count = 10
    
    async def setup_totp(self, user_id: int) -> Dict[str, Any]:
        """
        Set up TOTP MFA for a user.
        
        Returns:
            Dictionary with secret, QR code, and backup codes
        """
        with self.get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            # Generate secret key
            secret = pyotp.random_base32()
            
            # Create TOTP object
            totp = pyotp.TOTP(secret)
            
            # Generate provisioning URI for QR code
            provisioning_uri = totp.provisioning_uri(
                name=user.email,
                issuer_name=self.issuer_name
            )
            
            # Generate QR code
            qr_code_data = self._generate_qr_code(provisioning_uri)
            
            # Generate backup codes
            backup_codes = self._generate_backup_codes()
            
            # Check if user already has MFA setup
            existing_mfa = db.query(UserMFA).filter(
                UserMFA.user_id == user_id,
                UserMFA.mfa_type == "totp"
            ).first()
            
            if existing_mfa:
                # Update existing MFA
                existing_mfa.secret_key = secret
                existing_mfa.backup_codes = backup_codes
                existing_mfa.is_enabled = False  # Require verification to enable
                mfa_record = existing_mfa
            else:
                # Create new MFA record
                mfa_record = UserMFA(
                    user_id=user_id,
                    mfa_type="totp",
                    secret_key=secret,
                    backup_codes=backup_codes,
                    is_enabled=False  # Require verification to enable
                )
                db.add(mfa_record)
            
            db.commit()
            
            # Log MFA setup
            await audit_service.log_event(
                AuditAction.MFA_SETUP,
                user_id=user_id,
                severity=AuditSeverity.MEDIUM,
                additional_context={
                    "mfa_type": "totp",
                    "enabled": False
                }
            )
            
            return {
                "secret": secret,
                "qr_code": qr_code_data,
                "backup_codes": backup_codes,
                "manual_entry_key": secret
            }
    
    async def verify_and_enable_totp(
        self,
        user_id: int,
        verification_code: str
    ) -> bool:
        """
        Verify TOTP code and enable MFA for user.
        
        Returns:
            True if verification successful and MFA enabled
        """
        with self.get_db_session() as db:
            mfa_record = db.query(UserMFA).filter(
                UserMFA.user_id == user_id,
                UserMFA.mfa_type == "totp"
            ).first()
            
            if not mfa_record or not mfa_record.secret_key:
                return False
            
            # Verify the code
            totp = pyotp.TOTP(mfa_record.secret_key)
            if totp.verify(verification_code, valid_window=1):
                # Enable MFA
                mfa_record.is_enabled = True
                mfa_record.last_used_at = datetime.now(timezone.utc)
                db.commit()
                
                # Log MFA enabled
                await audit_service.log_event(
                    AuditAction.MFA_ENABLED,
                    user_id=user_id,
                    severity=AuditSeverity.MEDIUM,
                    additional_context={
                        "mfa_type": "totp"
                    }
                )
                
                return True
            
            return False
    
    async def verify_totp_code(
        self,
        user_id: int,
        code: str,
        allow_backup_code: bool = True
    ) -> bool:
        """
        Verify TOTP code or backup code.
        
        Returns:
            True if code is valid
        """
        with self.get_db_session() as db:
            mfa_record = db.query(UserMFA).filter(
                UserMFA.user_id == user_id,
                UserMFA.mfa_type == "totp",
                UserMFA.is_enabled == True
            ).first()
            
            if not mfa_record:
                return False
            
            # Try TOTP code first
            if mfa_record.secret_key:
                totp = pyotp.TOTP(mfa_record.secret_key)
                if totp.verify(code, valid_window=1):
                    mfa_record.last_used_at = datetime.now(timezone.utc)
                    db.commit()
                    
                    await audit_service.log_event(
                        AuditAction.MFA_VERIFIED,
                        user_id=user_id,
                        severity=AuditSeverity.LOW,
                        additional_context={
                            "mfa_type": "totp",
                            "method": "totp_code"
                        }
                    )
                    
                    return True
            
            # Try backup code if allowed
            if allow_backup_code and mfa_record.backup_codes:
                if code in mfa_record.backup_codes:
                    # Remove used backup code
                    mfa_record.backup_codes.remove(code)
                    mfa_record.last_used_at = datetime.now(timezone.utc)
                    db.commit()
                    
                    await audit_service.log_event(
                        AuditAction.MFA_VERIFIED,
                        user_id=user_id,
                        severity=AuditSeverity.MEDIUM,
                        additional_context={
                            "mfa_type": "totp",
                            "method": "backup_code",
                            "remaining_backup_codes": len(mfa_record.backup_codes)
                        }
                    )
                    
                    return True
            
            return False
    
    async def disable_mfa(self, user_id: int, disabled_by_id: Optional[int] = None) -> bool:
        """Disable MFA for a user."""
        with self.get_db_session() as db:
            mfa_record = db.query(UserMFA).filter(
                UserMFA.user_id == user_id,
                UserMFA.mfa_type == "totp"
            ).first()
            
            if not mfa_record:
                return False
            
            mfa_record.is_enabled = False
            db.commit()
            
            # Log MFA disabled
            await audit_service.log_event(
                AuditAction.MFA_DISABLED,
                user_id=disabled_by_id or user_id,
                resource_type="user",
                resource_id=str(user_id),
                severity=AuditSeverity.HIGH,
                additional_context={
                    "mfa_type": "totp",
                    "disabled_by": "admin" if disabled_by_id and disabled_by_id != user_id else "user"
                }
            )
            
            return True
    
    async def regenerate_backup_codes(self, user_id: int) -> List[str]:
        """Regenerate backup codes for a user."""
        with self.get_db_session() as db:
            mfa_record = db.query(UserMFA).filter(
                UserMFA.user_id == user_id,
                UserMFA.mfa_type == "totp"
            ).first()
            
            if not mfa_record:
                raise ValueError("MFA not set up for user")
            
            # Generate new backup codes
            backup_codes = self._generate_backup_codes()
            mfa_record.backup_codes = backup_codes
            db.commit()
            
            # Log backup codes regenerated
            await audit_service.log_event(
                AuditAction.MFA_BACKUP_CODES_REGENERATED,
                user_id=user_id,
                severity=AuditSeverity.MEDIUM,
                additional_context={
                    "mfa_type": "totp"
                }
            )
            
            return backup_codes
    
    async def get_mfa_status(self, user_id: int) -> Dict[str, Any]:
        """Get MFA status for a user."""
        with self.get_db_session() as db:
            mfa_record = db.query(UserMFA).filter(
                UserMFA.user_id == user_id,
                UserMFA.mfa_type == "totp"
            ).first()
            
            if not mfa_record:
                return {
                    "enabled": False,
                    "setup": False,
                    "backup_codes_remaining": 0
                }
            
            return {
                "enabled": mfa_record.is_enabled,
                "setup": True,
                "backup_codes_remaining": len(mfa_record.backup_codes) if mfa_record.backup_codes else 0,
                "last_used_at": mfa_record.last_used_at.isoformat() if mfa_record.last_used_at else None
            }
    
    async def is_mfa_required_for_user(self, user: User) -> bool:
        """Check if MFA is required for a user based on their roles."""
        # MFA required for admin and super admin roles
        admin_roles = ["admin", "super_admin"]
        user_roles = [role.name.lower() for role in user.roles]
        
        return any(role in admin_roles for role in user_roles)
    
    def _generate_qr_code(self, provisioning_uri: str) -> str:
        """Generate QR code as base64 encoded image."""
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return base64.b64encode(buffer.getvalue()).decode()
    
    def _generate_backup_codes(self) -> List[str]:
        """Generate backup codes."""
        codes = []
        for _ in range(self.backup_codes_count):
            # Generate 8-character alphanumeric code
            code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(8))
            codes.append(code)
        
        return codes


# Global MFA service instance
mfa_service = MFAService()
