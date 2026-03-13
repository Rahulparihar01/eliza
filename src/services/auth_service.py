"""
AI Enablement Platform - Authentication Service

Service layer for user authentication, session management, and RBAC operations.
"""

import jwt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from fastapi import HTTPException, status
import logging
from cachetools import TTLCache
from functools import partial
from starlette.concurrency import run_in_threadpool

from src.models.auth import User, Role, Permission, UserSession, UserAuditLog, PasswordHistory
from src.services.base_service import BaseService
from src.services.audit_service import audit_service, AuditAction, AuditSeverity
from src.services.security_service import security_service
from src.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AuthenticationError(Exception):
    """Custom authentication error."""
    pass


class AuthorizationError(Exception):
    """Custom authorization error."""
    pass


class AuthService(BaseService):
    """Authentication and authorization service."""
    
    def __init__(self):
        self.settings = get_settings()
        self.jwt_secret = self.settings.jwt_secret_key
        self.jwt_algorithm = "HS256"
        self.jwt_expiration_hours = 8
        self.max_failed_attempts = 5
        self.lockout_duration_minutes = 30
        self.max_concurrent_sessions = 3  # Maximum concurrent sessions per user
        self.session_cleanup_interval_hours = 24  # Clean up expired sessions every 24 hours
        
        # Session validation cache: {session_token: (is_valid, expires_at, last_activity)}
        # TTL of 5 minutes - balance between performance and security
        self.session_cache = TTLCache(maxsize=10000, ttl=300)  # 5 minutes
        logger.info("Session cache initialized with 5-minute TTL")
    
    async def authenticate_user(
        self,
        email: str,
        password: str,
        ip_address: str = None,
        user_agent: str = None,
        device_fingerprint: str = None
    ) -> Tuple[User, str, str]:
        """
        Authenticate user and create session.
        
        Returns:
            Tuple of (user, access_token, refresh_token)
        """
        with self.get_db_session() as db:
            # Prevent SQLAlchemy from expiring attributes after commit
            # This allows the User object to be accessed after the session closes
            db.expire_on_commit = False
            
            # Find user by email with roles eagerly loaded (case-insensitive)
            user = db.query(User).options(
                joinedload(User.roles).joinedload(Role.permissions),
                joinedload(User.roles).joinedload(Role.parent_role)
            ).filter(
                and_(func.lower(User.email) == func.lower(email), User.is_active == True)
            ).first()
            
            if not user:
                await self._log_failed_login(email, ip_address, "user_not_found")
                raise AuthenticationError("We couldn't find an account with that email address. Please check your email and try again.")
            
            # Check if account is locked using security service
            is_locked, unlock_time = await security_service.is_account_locked(user)
            if is_locked:
                await audit_service.log_event(
                    AuditAction.LOGIN_FAILED,
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    severity=AuditSeverity.HIGH,
                    additional_context={
                        "reason": "account_locked",
                        "unlock_time": unlock_time.isoformat() if unlock_time else None
                    }
                )
                if unlock_time:
                    raise AuthenticationError(f"Your account has been locked for security reasons. Please try again after {unlock_time.strftime('%I:%M %p on %b %d, %Y')}.")
                else:
                    raise AuthenticationError("Your account has been locked for security reasons. Please contact your administrator.")

            # Verify password
            if not user.verify_password(password):
                # Record failed login attempt using security service
                account_locked = await security_service.record_failed_login(
                    user, ip_address, user_agent
                )

                db.commit()

                if account_locked:
                    raise AuthenticationError("Your account has been locked due to multiple failed login attempts. Please try again in 30 minutes or contact your administrator.")
                else:
                    # Get remaining attempts before lockout
                    remaining_attempts = self.max_failed_attempts - user.failed_login_attempts
                    if remaining_attempts <= 2 and remaining_attempts > 0:
                        raise AuthenticationError(f"The password you entered is incorrect. You have {remaining_attempts} attempt{'s' if remaining_attempts > 1 else ''} remaining before your account is locked.")
                    else:
                        raise AuthenticationError("The password you entered is incorrect. Please check your password and try again.")
            
            # Record successful login using security service
            await security_service.record_successful_login(user)
            user.last_login_ip = ip_address

            # Check and enforce concurrent session limits
            await self._enforce_session_limits(db, user.id)

            # Create session with device fingerprinting
            session_token, refresh_token = UserSession.generate_tokens()
            session = UserSession(
                user_id=user.id,
                session_token=session_token,
                refresh_token=refresh_token,
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=device_fingerprint or self._generate_device_fingerprint(ip_address, user_agent),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=self.jwt_expiration_hours)
            )

            db.add(session)
            db.commit()
            
            # Generate JWT token
            access_token = self._create_access_token(user, session.session_token)
            
            # Log successful login
            await audit_service.log_event(
                AuditAction.LOGIN_SUCCESS,
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session.session_token,
                additional_context={
                    "auth_method": "password",
                    "device_fingerprint": device_fingerprint,
                    "session_expires_at": session.expires_at.isoformat()
                }
            )
            
            return user, access_token, refresh_token
    
    async def create_session_for_user(
        self,
        user: User,
        ip_address: str = None,
        user_agent: str = None,
        device_fingerprint: str = None
    ) -> Tuple[str, str]:
        """
        Create a new session for an existing user (e.g., after tenant switch).
        
        Returns:
            Tuple of (access_token, refresh_token)
        """
        with self.get_db_session() as db:
            db.expire_on_commit = False
            
            # Re-fetch user with roles in this session
            from src.models.auth import User as UserModel
            fresh_user = db.query(UserModel).options(
                joinedload(UserModel.roles).joinedload(Role.permissions),
                joinedload(UserModel.roles).joinedload(Role.parent_role)
            ).filter(UserModel.id == user.id).first()
            
            if not fresh_user:
                raise AuthenticationError("User not found")
            
            # Create new session
            session_token, refresh_token = UserSession.generate_tokens()
            session = UserSession(
                user_id=fresh_user.id,
                session_token=session_token,
                refresh_token=refresh_token,
                ip_address=ip_address,
                user_agent=user_agent,
                device_fingerprint=device_fingerprint or self._generate_device_fingerprint(ip_address, user_agent),
                expires_at=datetime.now(timezone.utc) + timedelta(hours=self.jwt_expiration_hours)
            )
            
            db.add(session)
            db.commit()
            
            # Generate JWT token
            access_token = self._create_access_token(fresh_user, session.session_token)
            
            return access_token, refresh_token
    
    def _create_access_token(self, user: User, session_token: str) -> str:
        """Create JWT access token."""
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "session_token": session_token,
            "permissions": user.get_permissions(),
            "role": user.primary_role.name if user.primary_role else None,
            "customer_id": user.customer_id,  # Use actual user's customer_id
            "iat": now,
            "exp": now + timedelta(hours=self.jwt_expiration_hours),
            "iss": "ai-enablement-platform"
        }

        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def _verify_session_sync(self, session_token: str) -> dict:
        """
        Synchronous session validation — runs in threadpool to avoid blocking the event loop.
        
        Validates session token against database, updates last activity timestamp,
        and returns session data for caching.
        """
        with self.get_db_session() as db:
            session = db.query(UserSession).filter(
                and_(
                    UserSession.session_token == session_token,
                    UserSession.is_active == True
                )
            ).first()
            
            if not session or session.is_expired():
                raise AuthenticationError("Session expired")
            
            # Update last activity (only if not recently updated to avoid excessive DB writes)
            now = datetime.now(timezone.utc)
            # Ensure both datetimes are timezone-aware for comparison
            last_activity = session.last_activity_at
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)
            if (now - last_activity).total_seconds() > 60:  # Only update if > 1 min old
                session.last_activity_at = now
                db.commit()
            
            return {
                "user_id": session.user_id,
                "expires_at": session.expires_at,
                "validated_at": now
            }

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token with session caching."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            session_token = payload.get("session_token")
            
            # Check cache first (fast, non-blocking)
            cached_session = self.session_cache.get(session_token)
            if cached_session:
                # Cache hit - return immediately without DB query
                logger.debug(f"Session cache HIT for token: {session_token[:10]}...")
                return payload
            
            # Cache miss — offload sync DB work to threadpool to avoid blocking the event loop
            logger.debug(f"Session cache MISS for token: {session_token[:10]}...")
            session_data = await run_in_threadpool(self._verify_session_sync, session_token)
            
            # Cache the valid session
            self.session_cache[session_token] = session_data
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token expired")
        except jwt.InvalidTokenError:
            raise AuthenticationError("Invalid token")
    
    async def refresh_token(self, refresh_token: str) -> Tuple[str, str]:
        """Refresh access token using refresh token."""
        with self.get_db_session() as db:
            session = db.query(UserSession).filter(
                and_(
                    UserSession.refresh_token == refresh_token,
                    UserSession.is_active == True
                )
            ).first()
            
            if not session or session.is_expired():
                raise AuthenticationError("Invalid or expired refresh token")
            
            user = session.user
            if not user.is_active:
                raise AuthenticationError("User account is inactive")
            
            # Generate new tokens
            new_session_token, new_refresh_token = UserSession.generate_tokens()
            session.session_token = new_session_token
            session.refresh_token = new_refresh_token
            session.extend_session(self.jwt_expiration_hours)
            
            db.commit()
            
            # Create new access token
            access_token = self._create_access_token(user, new_session_token)
            
            return access_token, new_refresh_token
    
    async def logout(self, session_token: str) -> None:
        """Logout user and invalidate session."""
        with self.get_db_session() as db:
            session = db.query(UserSession).filter(
                UserSession.session_token == session_token
            ).first()
            
            if session:
                session.is_active = False
                db.commit()
                
                # Invalidate session cache
                if session_token in self.session_cache:
                    del self.session_cache[session_token]
                    logger.debug(f"Session cache invalidated for token: {session_token[:10]}...")
                
                await audit_service.log_event(
                    AuditAction.LOGOUT,
                    user_id=session.user_id,
                    session_id=session_token,
                    additional_context={
                        "session_duration_minutes": (
                            datetime.now(timezone.utc) - session.created_at
                        ).total_seconds() / 60
                    }
                )
    
    def get_user_by_id_sync(self, user_id: int) -> Optional[User]:
        """Synchronously get user by ID with all relationships eagerly loaded for DTO conversion."""
        with self.get_db_session() as db:
            user = (
                db.query(User)
                .options(
                    joinedload(User.roles).joinedload(Role.permissions),
                    joinedload(User.roles).joinedload(Role.parent_role),
                    joinedload(User.sessions)
                )
                .filter(and_(User.id == user_id, User.is_active == True))
                .first()
            )

            if user:
                # Force load all lazy attributes while session is active
                # This ensures all data is in memory before the session closes
                _ = user.id
                _ = user.email
                _ = user.username
                _ = user.full_name
                _ = user.customer_id
                _ = user.is_active

                # Load roles, their permissions, and inherited hierarchy
                visited_roles = set()

                def load_role(role: Role):
                    if not role or role.id in visited_roles:
                        return

                    visited_roles.add(role.id)
                    _ = role.id
                    _ = role.name
                    _ = role.description

                    for perm in role.permissions:
                        _ = perm.id
                        _ = perm.name
                        _ = perm.resource
                        _ = perm.action

                    if role.parent_role:
                        _ = role.parent_role.id
                        _ = role.parent_role.name
                        load_role(role.parent_role)

                for role in user.roles:
                    load_role(role)

                # Load sessions
                for session in user.sessions:
                    _ = session.id
                    _ = session.session_token

                # Access the primary_role property to ensure it's computed
                _ = user.primary_role

                # Detach from session but keep all loaded data
                db.expunge_all()

            return user

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Async wrapper to fetch user by ID without blocking the event loop."""
        return await run_in_threadpool(partial(self.get_user_by_id_sync, user_id))
    
    async def check_permission(self, user_id: int, permission: str) -> bool:
        """Check if user has specific permission."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        return user.has_permission(permission)
    
    async def check_any_permission(self, user_id: int, permissions: List[str]) -> bool:
        """Check if user has any of the specified permissions."""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        
        return user.has_any_permission(permissions)
    
    async def require_permission(self, user_id: int, permission: str) -> None:
        """Require user to have specific permission, raise exception if not."""
        if not await self.check_permission(user_id, permission):
            raise AuthorizationError(f"Permission required: {permission}")
    
    async def require_any_permission(self, user_id: int, permissions: List[str]) -> None:
        """Require user to have any of the specified permissions."""
        if not await self.check_any_permission(user_id, permissions):
            raise AuthorizationError(f"One of these permissions required: {', '.join(permissions)}")
    
    async def create_user(
        self, 
        email: str, 
        password: str, 
        first_name: str, 
        last_name: str,
        customer_id: Optional[str] = None,
        role_names: List[str] = None,
        created_by_id: int = None
    ) -> User:
        """Create new user with specified roles."""
        with self.get_db_session() as db:
            is_valid, errors = await security_service.validate_password_policy(password)
            if not is_valid:
                raise ValueError("; ".join(errors))

            # Check if user already exists (case-insensitive)
            existing_user = db.query(User).filter(func.lower(User.email) == func.lower(email)).first()
            if existing_user:
                raise ValueError("User with this email already exists")

            if not customer_id and created_by_id:
                creator = db.query(User).filter(User.id == created_by_id).first()
                if creator:
                    customer_id = creator.customer_id

            if not customer_id:
                raise ValueError("Customer context is required to create a user")

            normalized_email = email.strip().lower()
            base_username = normalized_email.split("@")[0]
            username = base_username
            suffix = 1
            while (
                db.query(User)
                .filter(func.lower(User.username) == func.lower(username))
                .first()
                is not None
            ):
                username = f"{base_username}{suffix}"
                suffix += 1
            
            # Create user
            user = User(
                email=normalized_email,
                username=username,
                full_name=f"{first_name} {last_name}".strip(),
                customer_id=customer_id,
                is_active=True,
                is_superuser=False,
            )
            user.set_password(password)
            
            # Assign roles
            if role_names:
                normalized_roles = [r.strip().lower() for r in role_names if r and r.strip()]
                roles = (
                    db.query(Role)
                    .filter(
                        func.lower(Role.name).in_(normalized_roles),
                        or_(Role.customer_id == customer_id, Role.customer_id.is_(None)),
                        Role.is_active == True,  # noqa: E712
                    )
                    .all()
                )
                user.roles = roles
            
            db.add(user)
            db.commit()
            db.refresh(user)
            
            # Log user creation
            await self._log_audit(
                created_by_id, "user_created",
                resource_type="user", resource_id=str(user.id),
                new_values={"email": email, "roles": role_names}
            )
            
            return user

    async def _enforce_session_limits(self, db: Session, user_id: int) -> None:
        """Enforce concurrent session limits by removing oldest sessions."""
        active_sessions = db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True
            )
        ).order_by(UserSession.last_activity_at.desc()).all()

        # Remove expired sessions first
        for session in active_sessions:
            if session.is_expired():
                session.is_active = False

        # Get remaining active sessions
        active_sessions = [s for s in active_sessions if not s.is_expired()]

        # If we're at or over the limit, deactivate oldest sessions
        if len(active_sessions) >= self.max_concurrent_sessions:
            sessions_to_remove = active_sessions[self.max_concurrent_sessions - 1:]
            for session in sessions_to_remove:
                session.is_active = False
                await self._log_audit(
                    user_id, "session_terminated",
                    session_id=session.session_token,
                    new_values={"reason": "concurrent_session_limit"}
                )

    def _generate_device_fingerprint(self, ip_address: str, user_agent: str) -> str:
        """Generate a simple device fingerprint from IP and user agent."""
        import hashlib
        fingerprint_data = f"{ip_address}:{user_agent}"
        return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:32]

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions. Returns number of sessions cleaned up."""
        with self.get_db_session() as db:
            expired_sessions = db.query(UserSession).filter(
                and_(
                    UserSession.is_active == True,
                    UserSession.expires_at < datetime.now(timezone.utc)
                )
            ).all()

            count = len(expired_sessions)
            for session in expired_sessions:
                session.is_active = False
                await self._log_audit(
                    session.user_id, "session_expired",
                    session_id=session.session_token
                )

            db.commit()
            logger.info(f"Cleaned up {count} expired sessions")
            return count

    async def get_user_active_sessions(self, user_id: int) -> List[UserSession]:
        """Get all active sessions for a user."""
        with self.get_db_session() as db:
            return db.query(UserSession).filter(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.now(timezone.utc)
                )
            ).order_by(UserSession.last_activity_at.desc()).all()

    async def terminate_session(self, session_token: str, terminated_by_user_id: int = None) -> bool:
        """Terminate a specific session."""
        with self.get_db_session() as db:
            session = db.query(UserSession).filter(
                UserSession.session_token == session_token
            ).first()

            if session and session.is_active:
                session.is_active = False
                db.commit()

                await self._log_audit(
                    session.user_id, "session_terminated",
                    session_id=session_token,
                    new_values={
                        "terminated_by": terminated_by_user_id,
                        "reason": "manual_termination"
                    }
                )
                return True
            return False

    async def terminate_all_user_sessions(self, user_id: int, except_session: str = None) -> int:
        """Terminate all sessions for a user except optionally one session."""
        with self.get_db_session() as db:
            query = db.query(UserSession).filter(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True
                )
            )

            if except_session:
                query = query.filter(UserSession.session_token != except_session)

            sessions = query.all()
            count = len(sessions)

            for session in sessions:
                session.is_active = False
                await self._log_audit(
                    user_id, "session_terminated",
                    session_id=session.session_token,
                    new_values={"reason": "terminate_all_sessions"}
                )

            db.commit()
            return count

    async def _log_audit(
        self, 
        user_id: int, 
        action: str, 
        resource_type: str = None,
        resource_id: str = None,
        old_values: Dict = None,
        new_values: Dict = None,
        ip_address: str = None,
        user_agent: str = None,
        session_id: str = None
    ) -> None:
        """Log audit event."""
        with self.get_db_session() as db:
            audit_log = UserAuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                old_values=old_values,
                new_values=new_values,
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id
            )
            db.add(audit_log)
            db.commit()
    
    async def _log_failed_login(self, email: str, ip_address: str, reason: str) -> None:
        """Log failed login attempt."""
        logger.warning(f"Failed login attempt for {email} from {ip_address}: {reason}")

        await audit_service.log_event(
            AuditAction.LOGIN_FAILED,
            user_id=None,
            resource_type="auth",
            ip_address=ip_address,
            severity=AuditSeverity.MEDIUM,
            additional_context={
                "email": email,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


# Global auth service instance
auth_service = AuthService()
