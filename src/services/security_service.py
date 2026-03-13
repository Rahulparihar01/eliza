"""
AI Enablement Platform - Security Service

Service for managing security policies, password validation, account lockout,
and multi-factor authentication.
"""

import logging
import re
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.models.auth import User, UserSession, PasswordHistory
from src.services.base_service import BaseService
from src.services.audit_service import audit_service, AuditAction, AuditSeverity

logger = logging.getLogger(__name__)


class PasswordPolicy:
    """Password policy configuration."""
    
    MIN_LENGTH = 8
    MAX_LENGTH = 128
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGITS = True
    REQUIRE_SPECIAL_CHARS = True
    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    HISTORY_COUNT = 5  # Number of previous passwords to check
    MAX_AGE_DAYS = 90  # Password expiration
    
    @classmethod
    def validate_password(cls, password: str, user_id: Optional[int] = None) -> Tuple[bool, List[str]]:
        """
        Validate password against policy.
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Length check
        if len(password) < cls.MIN_LENGTH:
            errors.append(f"Password must be at least {cls.MIN_LENGTH} characters long")
        if len(password) > cls.MAX_LENGTH:
            errors.append(f"Password must be no more than {cls.MAX_LENGTH} characters long")
        
        # Character requirements
        if cls.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if cls.REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if cls.REQUIRE_DIGITS and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if cls.REQUIRE_SPECIAL_CHARS and not re.search(f'[{re.escape(cls.SPECIAL_CHARS)}]', password):
            errors.append(f"Password must contain at least one special character: {cls.SPECIAL_CHARS}")
        
        # Common password patterns
        if cls._is_common_password(password):
            errors.append("Password is too common or predictable")
        
        # Password history check (if user_id provided)
        if user_id and cls._is_password_reused(password, user_id):
            errors.append(f"Password cannot be one of the last {cls.HISTORY_COUNT} passwords used")
        
        return len(errors) == 0, errors
    
    @classmethod
    def _is_common_password(cls, password: str) -> bool:
        """Check if password is in common password list."""
        common_passwords = {
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "dragon", "master",
            "password1", "123456789", "12345678", "1234567890"
        }
        return password.lower() in common_passwords
    
    @classmethod
    def _is_password_reused(cls, password: str, user_id: int) -> bool:
        """Check if password was recently used."""
        from src.services.base_service import get_service_db_session
        with get_service_db_session() as db:
            # Get recent password hashes
            recent_passwords = db.query(PasswordHistory).filter(
                PasswordHistory.user_id == user_id
            ).order_by(PasswordHistory.created_at.desc()).limit(cls.HISTORY_COUNT).all()
            
            # Check against each recent password
            for pwd_history in recent_passwords:
                if cls._verify_password_hash(password, pwd_history.password_hash):
                    return True
            
            return False
    
    @classmethod
    def _verify_password_hash(cls, password: str, password_hash: str) -> bool:
        """Verify password against hash (simplified - would use proper bcrypt in production)."""
        # This is a simplified implementation
        # In production, use proper bcrypt verification
        return hashlib.sha256(password.encode()).hexdigest() == password_hash
    
    @classmethod
    def is_password_expired(cls, user: User) -> bool:
        """Check if user's password has expired."""
        if not user.password_changed_at:
            return True  # Force password change if never set
        
        expiry_date = user.password_changed_at + timedelta(days=cls.MAX_AGE_DAYS)
        return datetime.now(timezone.utc) > expiry_date


class AccountLockoutPolicy:
    """Account lockout policy configuration."""
    
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    RESET_WINDOW_MINUTES = 15  # Window to reset failed attempts
    
    @classmethod
    def should_lock_account(cls, user: User) -> bool:
        """Check if account should be locked based on failed attempts."""
        if user.failed_login_attempts >= cls.MAX_FAILED_ATTEMPTS:
            return True
        return False
    
    @classmethod
    def is_account_locked(cls, user: User) -> bool:
        """Check if account is currently locked."""
        if not user.locked_until:
            return False
        
        return datetime.now(timezone.utc) < user.locked_until
    
    @classmethod
    def get_lockout_duration(cls) -> timedelta:
        """Get lockout duration."""
        return timedelta(minutes=cls.LOCKOUT_DURATION_MINUTES)
    
    @classmethod
    def should_reset_failed_attempts(cls, user: User) -> bool:
        """Check if failed attempts should be reset."""
        if not user.last_failed_login:
            return False
        
        reset_window = timedelta(minutes=cls.RESET_WINDOW_MINUTES)
        return datetime.now(timezone.utc) - user.last_failed_login > reset_window


class SecurityService(BaseService):
    """Service for managing security policies and enforcement."""
    
    def __init__(self):
        self.password_policy = PasswordPolicy()
        self.lockout_policy = AccountLockoutPolicy()
    
    async def validate_password_policy(
        self,
        password: str,
        user_id: Optional[int] = None
    ) -> Tuple[bool, List[str]]:
        """Validate password against security policy."""
        return self.password_policy.validate_password(password, user_id)
    
    async def record_failed_login(
        self,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Record failed login attempt and check if account should be locked.
        
        Returns:
            True if account was locked, False otherwise
        """
        with self.get_db_session() as db:
            # Reset failed attempts if outside reset window
            if self.lockout_policy.should_reset_failed_attempts(user):
                user.failed_login_attempts = 0
            
            # Increment failed attempts
            user.failed_login_attempts += 1
            user.last_failed_login = datetime.now(timezone.utc)
            
            # Check if account should be locked
            should_lock = self.lockout_policy.should_lock_account(user)
            if should_lock:
                user.locked_until = datetime.now(timezone.utc) + self.lockout_policy.get_lockout_duration()
                user.is_active = False  # Temporarily disable account
                
                # Log account lockout
                await audit_service.log_event(
                    AuditAction.ACCOUNT_LOCKED,
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    severity=AuditSeverity.HIGH,
                    additional_context={
                        "failed_attempts": user.failed_login_attempts,
                        "locked_until": user.locked_until.isoformat(),
                        "reason": "max_failed_attempts_exceeded"
                    }
                )
            else:
                # Log failed login attempt
                await audit_service.log_event(
                    AuditAction.LOGIN_FAILED,
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    severity=AuditSeverity.MEDIUM,
                    additional_context={
                        "failed_attempts": user.failed_login_attempts,
                        "max_attempts": self.lockout_policy.MAX_FAILED_ATTEMPTS
                    }
                )
            
            db.commit()
            return should_lock
    
    async def record_successful_login(self, user: User) -> None:
        """Record successful login and reset failed attempts."""
        with self.get_db_session() as db:
            user.failed_login_attempts = 0
            user.last_failed_login = None
            user.last_login_at = datetime.now(timezone.utc)
            
            # Unlock account if it was locked
            if user.locked_until:
                user.locked_until = None
                user.is_active = True
            
            db.commit()
    
    async def is_account_locked(self, user: User) -> Tuple[bool, Optional[datetime]]:
        """
        Check if account is locked.
        
        Returns:
            Tuple of (is_locked, unlock_time)
        """
        is_locked = self.lockout_policy.is_account_locked(user)
        unlock_time = user.locked_until if is_locked else None
        
        return is_locked, unlock_time
    
    async def unlock_account(
        self,
        user_id: int,
        unlocked_by_id: Optional[int] = None
    ) -> bool:
        """Manually unlock a user account."""
        with self.get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            
            user.locked_until = None
            user.failed_login_attempts = 0
            user.last_failed_login = None
            user.is_active = True
            
            # Log account unlock
            await audit_service.log_event(
                AuditAction.ACCOUNT_UNLOCKED,
                user_id=unlocked_by_id,
                resource_type="user",
                resource_id=str(user_id),
                severity=AuditSeverity.MEDIUM,
                additional_context={
                    "target_user_email": user.email,
                    "unlocked_by": "admin" if unlocked_by_id else "system"
                }
            )
            
            db.commit()
            return True
    
    async def force_password_change(
        self,
        user_id: int,
        reason: str = "security_policy",
        changed_by_id: Optional[int] = None
    ) -> bool:
        """Force user to change password on next login."""
        with self.get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            
            user.force_password_change = True
            
            # Log forced password change
            await audit_service.log_event(
                AuditAction.PASSWORD_RESET_FORCED,
                user_id=changed_by_id,
                resource_type="user",
                resource_id=str(user_id),
                severity=AuditSeverity.MEDIUM,
                additional_context={
                    "target_user_email": user.email,
                    "reason": reason
                }
            )
            
            db.commit()
            return True
    
    async def check_password_expiry(self, user: User) -> bool:
        """Check if user's password has expired."""
        return self.password_policy.is_password_expired(user)
    
    async def get_security_summary(self, user_id: int) -> Dict[str, Any]:
        """Get security summary for a user."""
        with self.get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {}
            
            is_locked, unlock_time = await self.is_account_locked(user)
            password_expired = await self.check_password_expiry(user)
            
            return {
                "user_id": user.id,
                "email": user.email,
                "is_active": user.is_active,
                "is_locked": is_locked,
                "unlock_time": unlock_time.isoformat() if unlock_time else None,
                "failed_login_attempts": user.failed_login_attempts,
                "max_failed_attempts": self.lockout_policy.MAX_FAILED_ATTEMPTS,
                "last_failed_login": user.last_failed_login.isoformat() if user.last_failed_login else None,
                "password_expired": password_expired,
                "force_password_change": getattr(user, 'force_password_change', False),
                "password_changed_at": user.password_changed_at.isoformat() if user.password_changed_at else None,
                "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None
            }


# Global security service instance
security_service = SecurityService()
