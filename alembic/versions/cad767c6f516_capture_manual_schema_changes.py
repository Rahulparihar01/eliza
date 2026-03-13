"""Capture manual schema changes

Revision ID: cad767c6f516
Revises: 012_add_hr_schema
Create Date: 2025-10-01 13:03:16.786942

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cad767c6f516'
down_revision: Union[str, Sequence[str], None] = '012_add_hr_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["core"]


def upgrade() -> None:
    """Upgrade schema."""

    # --- user_sessions adjustments ---
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user_sessions' AND column_name = 'device_fingerprint'
            ) THEN
                ALTER TABLE user_sessions ADD COLUMN device_fingerprint VARCHAR(255);
            END IF;
        END;
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user_sessions' AND column_name = 'last_activity'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user_sessions' AND column_name = 'last_activity_at'
            ) THEN
                ALTER TABLE user_sessions RENAME COLUMN last_activity TO last_activity_at;
            END IF;
        END;
        $$;
        """
    )

    # --- user_audit_log adjustments ---
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user_audit_log' AND column_name = 'old_values'
            ) THEN
                ALTER TABLE user_audit_log ADD COLUMN old_values JSON;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user_audit_log' AND column_name = 'new_values'
            ) THEN
                ALTER TABLE user_audit_log ADD COLUMN new_values JSON;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user_audit_log' AND column_name = 'session_id'
            ) THEN
                ALTER TABLE user_audit_log ADD COLUMN session_id VARCHAR(255);
            END IF;
        END;
        $$;
        """
    )

    op.execute("ALTER TABLE user_audit_log ALTER COLUMN status DROP NOT NULL;")
    op.execute("ALTER TABLE user_audit_log ALTER COLUMN user_id DROP NOT NULL;")

    # --- upload_batches adjustments ---
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'upload_batches' AND column_name = 'processed_files'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'upload_batches' AND column_name = 'completed_files'
            ) THEN
                ALTER TABLE upload_batches RENAME COLUMN processed_files TO completed_files;
            END IF;
        END;
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'upload_batches' AND column_name = 'metadata'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'upload_batches' AND column_name = 'batch_metadata'
            ) THEN
                ALTER TABLE upload_batches RENAME COLUMN metadata TO batch_metadata;
            END IF;
        END;
        $$;
        """
    )

    op.execute("ALTER TABLE upload_batches ADD COLUMN IF NOT EXISTS chunking_strategy VARCHAR(20);")
    op.execute("ALTER TABLE upload_batches ADD COLUMN IF NOT EXISTS chunking_config JSON;")
    op.execute("ALTER TABLE upload_batches ADD COLUMN IF NOT EXISTS qa_rag_enabled BOOLEAN DEFAULT FALSE;")
    op.execute("ALTER TABLE upload_batches ADD COLUMN IF NOT EXISTS total_chunks_created INTEGER DEFAULT 0;")
    op.execute("ALTER TABLE upload_batches ADD COLUMN IF NOT EXISTS total_qa_pairs_generated INTEGER DEFAULT 0;")

    # --- documents adjustments ---
    op.execute(
        "ALTER TABLE documents ADD COLUMN IF NOT EXISTS duplicate_chunks_count INTEGER NOT NULL DEFAULT 0;"
    )


def downgrade() -> None:
    """Downgrade schema."""

    # --- documents adjustments ---
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS duplicate_chunks_count;")

    # --- upload_batches adjustments ---
    op.execute("ALTER TABLE upload_batches DROP COLUMN IF EXISTS total_qa_pairs_generated;")
    op.execute("ALTER TABLE upload_batches DROP COLUMN IF EXISTS total_chunks_created;")
    op.execute("ALTER TABLE upload_batches DROP COLUMN IF EXISTS qa_rag_enabled;")
    op.execute("ALTER TABLE upload_batches DROP COLUMN IF EXISTS chunking_config;")
    op.execute("ALTER TABLE upload_batches DROP COLUMN IF EXISTS chunking_strategy;")

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'upload_batches' AND column_name = 'batch_metadata'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'upload_batches' AND column_name = 'metadata'
            ) THEN
                ALTER TABLE upload_batches RENAME COLUMN batch_metadata TO metadata;
            END IF;
        END;
        $$;
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'upload_batches' AND column_name = 'completed_files'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'upload_batches' AND column_name = 'processed_files'
            ) THEN
                ALTER TABLE upload_batches RENAME COLUMN completed_files TO processed_files;
            END IF;
        END;
        $$;
        """
    )

    # --- user_audit_log adjustments ---
    op.execute("ALTER TABLE user_audit_log ALTER COLUMN user_id SET NOT NULL;")
    op.execute("ALTER TABLE user_audit_log ALTER COLUMN status SET NOT NULL;")
    op.execute("ALTER TABLE user_audit_log DROP COLUMN IF EXISTS session_id;")
    op.execute("ALTER TABLE user_audit_log DROP COLUMN IF EXISTS new_values;")
    op.execute("ALTER TABLE user_audit_log DROP COLUMN IF EXISTS old_values;")

    # --- user_sessions adjustments ---
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user_sessions' AND column_name = 'last_activity_at'
            ) AND NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'user_sessions' AND column_name = 'last_activity'
            ) THEN
                ALTER TABLE user_sessions RENAME COLUMN last_activity_at TO last_activity;
            END IF;
        END;
        $$;
        """
    )

    op.execute("ALTER TABLE user_sessions DROP COLUMN IF EXISTS device_fingerprint;")
