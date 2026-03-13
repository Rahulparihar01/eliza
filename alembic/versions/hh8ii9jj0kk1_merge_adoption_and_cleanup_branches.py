"""Merge adoption and cleanup branches

Revision ID: hh8ii9jj0kk1
Revises: gg7hh8ii9jj0, zz2_scott_tenant_admin
Create Date: 2026-01-02

This migration merges the two parallel branches:
- Adoption dashboard branch (ending at gg7hh8ii9jj0)
- Permission cleanup branch (ending at zz2_scott_tenant_admin)
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = 'hh8ii9jj0kk1'
down_revision = ('gg7hh8ii9jj0', 'zz2_scott_tenant_admin')
branch_labels = None
depends_on = None
tags = ["adoption", "auth", "tenancy"]


def upgrade():
    # This is a merge migration - no schema changes needed
    pass


def downgrade():
    # This is a merge migration - no schema changes needed
    pass

