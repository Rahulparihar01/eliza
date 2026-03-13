"""Add adoption:manage_jobs permission for tenant job scheduler access.

Revision ID: zz29_adoption_manage_jobs
Revises: zz28_adoption_daily_default, 07b7688bf8c2
Create Date: 2026-03-02

Adds:
- adoption:manage_jobs permission to the permissions table
- Links it to the adoption_dashboard feature in feature_permissions
- Also links adoption:manage_sync (was missing from feature_permissions)
- Assigns adoption:manage_jobs to adoption_admin, admin, super_admin roles
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy.sql import text


revision: str = "zz29_adoption_manage_jobs"
down_revision: Union[str, Sequence[str], None] = (
    "zz28_adoption_daily_default",
    "07b7688bf8c2",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["adoption"]


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Add adoption:manage_jobs permission
    existing = conn.execute(
        text("SELECT id FROM permissions WHERE name = 'adoption:manage_jobs'")
    ).fetchone()

    if not existing:
        conn.execute(text("""
            INSERT INTO permissions (name, resource, action, description, scope, created_at)
            VALUES (
                'adoption:manage_jobs',
                'adoption',
                'manage_jobs',
                'View, trigger, and edit scheduled jobs from the Job Scheduler',
                'all',
                now()
            )
        """))

    # 2. Link new permission to adoption_dashboard feature in feature_permissions
    feature_row = conn.execute(
        text("SELECT id FROM platform_features WHERE feature_key = 'adoption_dashboard'")
    ).fetchone()

    if feature_row:
        feature_id = feature_row[0]

        # adoption:manage_jobs
        exists = conn.execute(text(
            "SELECT id FROM feature_permissions "
            "WHERE feature_id = :fid AND permission_key = 'adoption:manage_jobs'"
        ), {"fid": feature_id}).fetchone()

        if not exists:
            max_sort = conn.execute(text(
                "SELECT COALESCE(MAX(sort_order), 0) FROM feature_permissions WHERE feature_id = :fid"
            ), {"fid": feature_id}).scalar()

            conn.execute(text("""
                INSERT INTO feature_permissions
                    (feature_id, permission_key, display_name, description, sort_order, created_at, updated_at)
                VALUES
                    (:fid, 'adoption:manage_jobs', 'Manage Jobs',
                     'View, trigger, and edit scheduled jobs from the Job Scheduler',
                     :sort, now(), now())
            """), {"fid": feature_id, "sort": max_sort + 1})

        # adoption:manage_sync (was missing from feature_permissions)
        exists_sync = conn.execute(text(
            "SELECT id FROM feature_permissions "
            "WHERE feature_id = :fid AND permission_key = 'adoption:manage_sync'"
        ), {"fid": feature_id}).fetchone()

        if not exists_sync:
            max_sort = conn.execute(text(
                "SELECT COALESCE(MAX(sort_order), 0) FROM feature_permissions WHERE feature_id = :fid"
            ), {"fid": feature_id}).scalar()

            conn.execute(text("""
                INSERT INTO feature_permissions
                    (feature_id, permission_key, display_name, description, sort_order, created_at, updated_at)
                VALUES
                    (:fid, 'adoption:manage_sync', 'Manage Sync',
                     'Trigger manual adoption data syncs and configure sync settings',
                     :sort, now(), now())
            """), {"fid": feature_id, "sort": max_sort + 1})

    # 3. Assign adoption:manage_jobs to adoption_admin, admin, super_admin
    for role_name in ("adoption_admin", "admin", "super_admin"):
        conn.execute(text("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r, permissions p
            WHERE r.name = :role_name
              AND r.customer_id IS NULL
              AND p.name = 'adoption:manage_jobs'
              AND NOT EXISTS (
                  SELECT 1 FROM role_permissions rp
                  WHERE rp.role_id = r.id AND rp.permission_id = p.id
              )
        """), {"role_name": role_name})


def downgrade() -> None:
    conn = op.get_bind()

    # Remove role_permissions
    conn.execute(text("""
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE name = 'adoption:manage_jobs'
        )
    """))

    # Remove feature_permissions entries
    conn.execute(text("""
        DELETE FROM feature_permissions
        WHERE permission_key IN ('adoption:manage_jobs', 'adoption:manage_sync')
    """))

    # Remove permission
    conn.execute(text("""
        DELETE FROM permissions WHERE name = 'adoption:manage_jobs'
    """))
