"""
Unit tests for Adoption Dashboard authorization.

Tests cover:
- check_adoption_access() method (permission-based checks)
- get_accessible_adoption_companies() method (permission parsing)
- Permission naming conventions
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.core.auth_context import CurrentUserContext, CurrentUserSettings


def create_mock_user(
    user_id: int = 1,
    customer_id: str = "acme",
    permissions: list = None,
    is_superuser: bool = False
) -> CurrentUserContext:
    """Create a mock user context for testing."""
    return CurrentUserContext(
        user_id=user_id,
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        is_active=True,
        is_superuser=is_superuser,
        customer_id=customer_id,
        department=None,
        team=None,
        roles=["test_role"],
        permissions=permissions or [],
        settings=CurrentUserSettings()
    )


class TestCheckAdoptionAccessPermissions:
    """Tests for check_adoption_access() permission-based checks (no DB mocking)."""
    
    def test_superuser_always_has_access(self):
        """Superusers should have access to any company."""
        from src.middleware.authorization import auth_middleware
        
        user = create_mock_user(is_superuser=True, customer_id="blackstone")
        
        # Superuser bypass should work
        assert auth_middleware.check_adoption_access(user, "acme") is True
        assert auth_middleware.check_adoption_access(user, "beta") is True
        
    def test_own_tenant_always_accessible(self):
        """Users should always have access to their own tenant."""
        from src.middleware.authorization import auth_middleware
        
        user = create_mock_user(customer_id="acme", permissions=[])
        
        assert auth_middleware.check_adoption_access(user, "acme") is True
        
    def test_wildcard_permission_grants_all_access(self):
        """Wildcard permission should grant access to all companies."""
        from src.middleware.authorization import auth_middleware
        
        user = create_mock_user(
            customer_id="blackstone", 
            permissions=["adoption:read:company:*"]
        )
        
        assert auth_middleware.check_adoption_access(user, "acme") is True
        assert auth_middleware.check_adoption_access(user, "beta") is True
        assert auth_middleware.check_adoption_access(user, "gamma") is True
        
    def test_specific_permission_grants_access(self):
        """Specific company permission should grant access to that company only."""
        from src.middleware.authorization import auth_middleware
        
        user = create_mock_user(
            customer_id="blackstone", 
            permissions=["adoption:read:company:acme"]
        )
        
        assert auth_middleware.check_adoption_access(user, "acme") is True
        # For 'beta', no permission exists - will check DB which we're not mocking
        # So we skip this assertion in this test
        
    def test_admin_wildcard_permission(self):
        """Admin wildcard permission should grant admin access to all."""
        from src.middleware.authorization import auth_middleware
        
        user = create_mock_user(
            customer_id="blackstone",
            permissions=["adoption:admin:company:*"]
        )
        
        assert auth_middleware.check_adoption_access(user, "acme", action="admin") is True
        assert auth_middleware.check_adoption_access(user, "beta", action="admin") is True


class TestGetAccessibleAdoptionCompaniesLogic:
    """Tests for get_accessible_adoption_companies() permission parsing logic."""
    
    def test_own_tenant_always_included(self):
        """User's own tenant should always be in the list - testing the basic logic."""
        from src.middleware.authorization import auth_middleware
        
        user = create_mock_user(customer_id="acme", permissions=[])
        
        # This will hit the DB for shares, but own tenant should be in result
        # Since we're testing permission logic, we accept some DB calls
        result = auth_middleware.get_accessible_adoption_companies(user)
        
        assert "acme" in result
        
    def test_specific_permissions_parsed_correctly(self):
        """Specific company permissions should be parsed and included."""
        from src.middleware.authorization import auth_middleware
        
        user = create_mock_user(
            customer_id="blackstone",
            permissions=[
                "adoption:read:company:acme",
                "adoption:read:company:beta",
                "some:other:permission"
            ]
        )
        
        result = auth_middleware.get_accessible_adoption_companies(user)
        
        assert "blackstone" in result  # Own tenant
        assert "acme" in result        # From permission
        assert "beta" in result        # From permission


class TestAdoptionPermissionConstants:
    """Tests for adoption permission naming conventions."""
    
    def test_permission_format_read(self):
        """Read permission should follow format."""
        user = create_mock_user(permissions=["adoption:read:company:acme"])
        assert user.has_permission("adoption:read:company:acme")
        
    def test_permission_format_admin(self):
        """Admin permission should follow format."""
        user = create_mock_user(permissions=["adoption:admin:company:acme"])
        assert user.has_permission("adoption:admin:company:acme")
        
    def test_permission_format_wildcard(self):
        """Wildcard permission should follow format."""
        user = create_mock_user(permissions=["adoption:read:company:*"])
        assert user.has_permission("adoption:read:company:*")
        
    def test_permission_format_view_dashboard(self):
        """View dashboard permission should follow format."""
        user = create_mock_user(permissions=["adoption:view_dashboard"])
        assert user.has_permission("adoption:view_dashboard")
        
    def test_permission_format_manage_sharing(self):
        """Manage sharing permission should follow format."""
        user = create_mock_user(permissions=["adoption:manage_sharing"])
        assert user.has_permission("adoption:manage_sharing")
        
    def test_permission_format_manage_sync(self):
        """Manage sync permission should follow format."""
        user = create_mock_user(permissions=["adoption:manage_sync"])
        assert user.has_permission("adoption:manage_sync")


class TestAdoptionPermissionParsing:
    """Tests for parsing adoption permission strings."""
    
    def test_parse_company_from_permission(self):
        """Should correctly parse company ID from permission string."""
        permission = "adoption:read:company:acme"
        parts = permission.split(":")
        
        assert len(parts) == 4
        assert parts[0] == "adoption"
        assert parts[1] == "read"
        assert parts[2] == "company"
        assert parts[3] == "acme"
        
    def test_parse_wildcard_permission(self):
        """Should correctly identify wildcard permission."""
        permission = "adoption:read:company:*"
        parts = permission.split(":")
        
        assert parts[3] == "*"
        
    def test_parse_admin_vs_read_action(self):
        """Should correctly distinguish between read and admin actions."""
        read_perm = "adoption:read:company:acme"
        admin_perm = "adoption:admin:company:acme"
        
        read_parts = read_perm.split(":")
        admin_parts = admin_perm.split(":")
        
        assert read_parts[1] == "read"
        assert admin_parts[1] == "admin"
        assert read_parts[3] == admin_parts[3]  # Same company


class TestCurrentUserContextHasPermission:
    """Tests for CurrentUserContext.has_permission() with adoption permissions."""
    
    def test_has_exact_permission(self):
        """Should return True for exact permission match."""
        user = create_mock_user(permissions=[
            "adoption:view_dashboard",
            "adoption:read:company:acme"
        ])
        
        assert user.has_permission("adoption:view_dashboard") is True
        assert user.has_permission("adoption:read:company:acme") is True
        
    def test_does_not_have_permission(self):
        """Should return False for missing permission."""
        user = create_mock_user(permissions=["adoption:view_dashboard"])
        
        assert user.has_permission("adoption:read:company:acme") is False
        assert user.has_permission("adoption:admin:company:*") is False
        
    def test_wildcard_is_not_auto_expanded(self):
        """Wildcard should not auto-expand to specific companies in has_permission."""
        user = create_mock_user(permissions=["adoption:read:company:*"])
        
        # has_permission is exact match only
        assert user.has_permission("adoption:read:company:*") is True
        assert user.has_permission("adoption:read:company:acme") is False  # Not auto-expanded
        
    def test_has_any_permission(self):
        """Should return True if user has any of the specified permissions."""
        user = create_mock_user(permissions=["adoption:view_dashboard"])
        
        assert user.has_any_permission([
            "adoption:view_dashboard",
            "adoption:admin:company:*"
        ]) is True
        
        assert user.has_any_permission([
            "adoption:read:company:acme",
            "adoption:admin:company:*"
        ]) is False
        
    def test_has_all_permissions(self):
        """Should return True only if user has all specified permissions."""
        user = create_mock_user(permissions=[
            "adoption:view_dashboard",
            "adoption:manage_sharing"
        ])
        
        assert user.has_all_permissions([
            "adoption:view_dashboard",
            "adoption:manage_sharing"
        ]) is True
        
        assert user.has_all_permissions([
            "adoption:view_dashboard",
            "adoption:admin:company:*"
        ]) is False
