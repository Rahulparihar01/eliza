from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class CurrentUserSettings:
    preferred_language: Optional[str] = None
    timezone: Optional[str] = None


@dataclass
class CurrentUserSessionInfo:
    session_token: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    device_fingerprint: Optional[str]
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    is_current: bool = False


@dataclass
class CurrentUserContext:
    user_id: int
    email: str
    username: Optional[str]
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    customer_id: str
    department: Optional[str]
    team: Optional[str]
    roles: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    primary_role: Optional[str] = None
    last_login_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    settings: CurrentUserSettings = field(default_factory=CurrentUserSettings)
    active_sessions: List[CurrentUserSessionInfo] = field(default_factory=list)

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def has_any_permission(self, permissions: List[str]) -> bool:
        return any(p in self.permissions for p in permissions)

    def has_all_permissions(self, permissions: List[str]) -> bool:
        return all(p in self.permissions for p in permissions)

    def has_role(self, role_name: str) -> bool:
        return role_name in self.roles
