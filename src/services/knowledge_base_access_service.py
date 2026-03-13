"""
Knowledge base access resolution.

Default behavior keeps KBs open within a workspace unless a KB has explicit
permission grants. When grants exist, user/role permissions are enforced.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from src.core.auth_context import CurrentUserContext
from src.models.auth import user_roles
from src.models.workspace import (
    KnowledgeBase,
    KnowledgeBasePermission,
    KnowledgeBasePermissionType,
)


class KnowledgeBaseAccessService:
    """Resolve effective knowledge base access for a user in a workspace."""

    _PERMISSION_RANK: Dict[str, int] = {
        KnowledgeBasePermissionType.READ.value: 1,
        KnowledgeBasePermissionType.WRITE.value: 2,
        KnowledgeBasePermissionType.ADMIN.value: 3,
    }

    def __init__(self, db: Session):
        self.db = db

    def list_workspace_knowledge_base_ids(self, workspace_id: int, customer_id: str) -> List[int]:
        rows = (
            self.db.query(KnowledgeBase.id)
            .filter(
                KnowledgeBase.workspace_id == workspace_id,
                KnowledgeBase.customer_id == customer_id,
                KnowledgeBase.is_active == True,
            )
            .all()
        )
        return [row[0] for row in rows]

    def _get_user_role_ids(self, user_id: int) -> Set[int]:
        rows = (
            self.db.query(user_roles.c.role_id)
            .filter(
                user_roles.c.user_id == user_id,
                user_roles.c.active == True,
            )
            .all()
        )
        return {row[0] for row in rows}

    def _has_required_permission(
        self,
        granted: Optional[str],
        required: KnowledgeBasePermissionType,
    ) -> bool:
        if not granted:
            return False
        granted_rank = self._PERMISSION_RANK.get(granted, 0)
        required_rank = self._PERMISSION_RANK.get(required.value, 0)
        return granted_rank >= required_rank

    def resolve_accessible_kb_ids(
        self,
        *,
        workspace_id: int,
        user: CurrentUserContext,
        required_permission: KnowledgeBasePermissionType = KnowledgeBasePermissionType.READ,
    ) -> List[int]:
        """
        Resolve KB ids the user can access in a workspace.

        Policy:
        - Superusers can access all active KBs.
        - KB with no explicit grants remains open to workspace users.
        - KB with grants requires matching user/role grant at required level.
        """
        workspace_kb_ids = self.list_workspace_knowledge_base_ids(workspace_id, user.customer_id)
        if not workspace_kb_ids:
            return []
        if user.is_superuser:
            return workspace_kb_ids

        role_ids = self._get_user_role_ids(user.user_id)
        permissions = (
            self.db.query(KnowledgeBasePermission)
            .filter(KnowledgeBasePermission.knowledge_base_id.in_(workspace_kb_ids))
            .all()
        )

        perms_by_kb: Dict[int, List[KnowledgeBasePermission]] = {}
        for permission in permissions:
            perms_by_kb.setdefault(permission.knowledge_base_id, []).append(permission)

        accessible: List[int] = []
        for kb_id in workspace_kb_ids:
            kb_permissions = perms_by_kb.get(kb_id, [])
            if not kb_permissions:
                # Default-open KB behavior until explicit grants are configured.
                accessible.append(kb_id)
                continue

            matched = False
            for permission in kb_permissions:
                if permission.user_id is not None and permission.user_id == user.user_id:
                    if self._has_required_permission(permission.permission_type, required_permission):
                        matched = True
                        break
                if (
                    permission.role_id is not None
                    and permission.role_id in role_ids
                    and self._has_required_permission(permission.permission_type, required_permission)
                ):
                    matched = True
                    break
            if matched:
                accessible.append(kb_id)

        return accessible

    def resolve_effective_kb_scope(
        self,
        *,
        workspace_id: int,
        user: CurrentUserContext,
        requested_kb_ids: Optional[List[int]] = None,
        required_permission: KnowledgeBasePermissionType = KnowledgeBasePermissionType.READ,
    ) -> List[int]:
        """
        Resolve final KB scope for retrieval/upload/chat.

        - If requested_kb_ids is None/empty, returns all accessible KB ids.
        - If requested IDs include missing/unauthorized KBs, raises ValueError/PermissionError.
        """
        workspace_kb_ids = self.list_workspace_knowledge_base_ids(workspace_id, user.customer_id)
        workspace_set = set(workspace_kb_ids)
        accessible = self.resolve_accessible_kb_ids(
            workspace_id=workspace_id,
            user=user,
            required_permission=required_permission,
        )
        accessible_set = set(accessible)

        if not requested_kb_ids:
            return accessible

        requested_set = set(requested_kb_ids)
        missing = requested_set - workspace_set
        if missing:
            raise ValueError(f"Knowledge base(s) not found in workspace: {sorted(missing)}")

        denied = requested_set - accessible_set
        if denied:
            raise PermissionError(f"Access denied for knowledge base(s): {sorted(denied)}")

        return [kb_id for kb_id in requested_kb_ids if kb_id in accessible_set]

