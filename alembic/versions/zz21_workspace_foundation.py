"""Workspace Foundation - Unify domains into workspaces

This migration:
1. Seeds ragflow_domains (workspaces) with existing domain configs
2. Adds workspace_id foreign key columns to related tables
3. Backfills workspace_id based on domain string matching
4. Creates indexes for efficient queries

Revision ID: zz21_workspace_foundation
Revises: zz20_add_conversation_uuid, zz10_greenhouse_bigint, zza_tenant_themes
Create Date: 2026-01-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'zz21_workspace_foundation'
down_revision = ('zz20_add_conversation_uuid', 'zz10_greenhouse_bigint', 'zza_tenant_themes')
branch_labels = None
depends_on = None
tags = ["core", "tenancy"]


def upgrade() -> None:
    # Get connection for raw SQL operations
    conn = op.get_bind()
    
    # =========================================================================
    # Step 1: Seed ragflow_domains (workspaces) from domain_prompt_configs
    # =========================================================================
    # Only insert if not already exists (idempotent)
    conn.execute(sa.text("""
        INSERT INTO ragflow_domains (
            customer_id, name, display_name, description, 
            icon, color, status, parser_type, embedding_model,
            chunk_token_count, similarity_threshold, top_k,
            document_count, chunk_count, total_tokens, is_active,
            created_at, updated_at
        )
        SELECT 
            dpc.customer_id,
            dpc.domain as name,
            dpc.display_name,
            dpc.description,
            'folder' as icon,
            CASE 
                WHEN dpc.domain = 'fasb' THEN 'blue'
                WHEN dpc.domain = 'insurance' THEN 'emerald'
                ELSE 'violet'
            END as color,
            'ready' as status,
            'naive' as parser_type,
            'text-embedding-3-large@OpenAI' as embedding_model,
            512 as chunk_token_count,
            COALESCE(dpc.similarity_threshold, 70) as similarity_threshold,
            COALESCE(dpc.retrieval_top_k, 10) as top_k,
            0 as document_count,
            0 as chunk_count,
            0 as total_tokens,
            dpc.is_active,
            NOW() as created_at,
            NOW() as updated_at
        FROM domain_prompt_configs dpc
        WHERE NOT EXISTS (
            SELECT 1 FROM ragflow_domains rd 
            WHERE rd.customer_id = dpc.customer_id AND rd.name = dpc.domain
        )
    """))
    
    # =========================================================================
    # Step 2: Add workspace_id columns to related tables
    # =========================================================================
    
    # Add workspace_id to rag_eval_runs
    op.add_column('rag_eval_runs', 
        sa.Column('workspace_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_rag_eval_runs_workspace_id',
        'rag_eval_runs', 'ragflow_domains',
        ['workspace_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_rag_eval_runs_workspace_id', 'rag_eval_runs', ['workspace_id'])
    
    # Add workspace_id to eval_sets
    op.add_column('eval_sets',
        sa.Column('workspace_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_eval_sets_workspace_id',
        'eval_sets', 'ragflow_domains',
        ['workspace_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_eval_sets_workspace_id', 'eval_sets', ['workspace_id'])
    
    # Add workspace_id to gepa_optimizer_jobs
    op.add_column('gepa_optimizer_jobs',
        sa.Column('workspace_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_gepa_optimizer_jobs_workspace_id',
        'gepa_optimizer_jobs', 'ragflow_domains',
        ['workspace_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_gepa_optimizer_jobs_workspace_id', 'gepa_optimizer_jobs', ['workspace_id'])
    
    # Add workspace_id to prompt_templates
    op.add_column('prompt_templates',
        sa.Column('workspace_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_prompt_templates_workspace_id',
        'prompt_templates', 'ragflow_domains',
        ['workspace_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_prompt_templates_workspace_id', 'prompt_templates', ['workspace_id'])
    
    # Add workspace_id to domain_prompt_configs (link to master workspace)
    op.add_column('domain_prompt_configs',
        sa.Column('workspace_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_domain_prompt_configs_workspace_id',
        'domain_prompt_configs', 'ragflow_domains',
        ['workspace_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_domain_prompt_configs_workspace_id', 'domain_prompt_configs', ['workspace_id'])
    
    # =========================================================================
    # Step 3: Backfill workspace_id based on domain string matching
    # =========================================================================
    
    # Backfill rag_eval_runs
    conn.execute(sa.text("""
        UPDATE rag_eval_runs rer
        SET workspace_id = rd.id
        FROM ragflow_domains rd
        WHERE rer.domain = rd.name 
          AND rer.customer_id = rd.customer_id
          AND rer.workspace_id IS NULL
    """))
    
    # Backfill eval_sets
    conn.execute(sa.text("""
        UPDATE eval_sets es
        SET workspace_id = rd.id
        FROM ragflow_domains rd
        WHERE es.domain = rd.name 
          AND es.customer_id = rd.customer_id
          AND es.workspace_id IS NULL
    """))
    
    # Backfill gepa_optimizer_jobs
    conn.execute(sa.text("""
        UPDATE gepa_optimizer_jobs goj
        SET workspace_id = rd.id
        FROM ragflow_domains rd
        WHERE goj.domain = rd.name 
          AND goj.customer_id = rd.customer_id
          AND goj.workspace_id IS NULL
    """))
    
    # Backfill prompt_templates
    conn.execute(sa.text("""
        UPDATE prompt_templates pt
        SET workspace_id = rd.id
        FROM ragflow_domains rd
        WHERE pt.domain = rd.name 
          AND pt.customer_id = rd.customer_id
          AND pt.workspace_id IS NULL
    """))
    
    # Backfill domain_prompt_configs
    conn.execute(sa.text("""
        UPDATE domain_prompt_configs dpc
        SET workspace_id = rd.id
        FROM ragflow_domains rd
        WHERE dpc.domain = rd.name 
          AND dpc.customer_id = rd.customer_id
          AND dpc.workspace_id IS NULL
    """))


def downgrade() -> None:
    # Remove foreign keys and columns in reverse order
    
    # domain_prompt_configs
    op.drop_index('ix_domain_prompt_configs_workspace_id', table_name='domain_prompt_configs')
    op.drop_constraint('fk_domain_prompt_configs_workspace_id', 'domain_prompt_configs', type_='foreignkey')
    op.drop_column('domain_prompt_configs', 'workspace_id')
    
    # prompt_templates
    op.drop_index('ix_prompt_templates_workspace_id', table_name='prompt_templates')
    op.drop_constraint('fk_prompt_templates_workspace_id', 'prompt_templates', type_='foreignkey')
    op.drop_column('prompt_templates', 'workspace_id')
    
    # gepa_optimizer_jobs
    op.drop_index('ix_gepa_optimizer_jobs_workspace_id', table_name='gepa_optimizer_jobs')
    op.drop_constraint('fk_gepa_optimizer_jobs_workspace_id', 'gepa_optimizer_jobs', type_='foreignkey')
    op.drop_column('gepa_optimizer_jobs', 'workspace_id')
    
    # eval_sets
    op.drop_index('ix_eval_sets_workspace_id', table_name='eval_sets')
    op.drop_constraint('fk_eval_sets_workspace_id', 'eval_sets', type_='foreignkey')
    op.drop_column('eval_sets', 'workspace_id')
    
    # rag_eval_runs
    op.drop_index('ix_rag_eval_runs_workspace_id', table_name='rag_eval_runs')
    op.drop_constraint('fk_rag_eval_runs_workspace_id', 'rag_eval_runs', type_='foreignkey')
    op.drop_column('rag_eval_runs', 'workspace_id')
    
    # Note: We don't delete the seeded workspace records on downgrade
    # to avoid data loss. They can be manually cleaned up if needed.
