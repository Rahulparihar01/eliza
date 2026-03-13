"""Workspace Templates and Knowledge Bases

Add workspace templates for different workspace types (RAG Retrieval, Data Analytics).
Add knowledge_bases table to support multiple KBs per workspace.
Add knowledge_base_permissions for KB-level access control.

Revision ID: zz22_workspace_templates_kb
Revises: zz21_workspace_foundation
Create Date: 2026-02-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'zz22_workspace_templates_kb'
down_revision = 'zz21_workspace_foundation'
branch_labels = None
depends_on = None
tags = ["core"]


def upgrade() -> None:
    """
    Create workspace architecture tables.
    
    Tables:
    - workspace_templates: Available workspace types (RAG Retrieval, Data Analytics)
    - knowledge_bases: Knowledge bases within workspaces (1:N)
    - knowledge_base_permissions: User/role access to knowledge bases
    """
    conn = op.get_bind()
    
    # =========================================================================
    # Table 1: Workspace Templates
    # =========================================================================
    op.create_table(
        'workspace_templates',
        
        # Primary key
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        
        # Template identification
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        
        # UI
        sa.Column('icon', sa.String(50), nullable=False, server_default='folder'),
        
        # Availability
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default='true'),
        
        # Configuration schema (JSON Schema for template options)
        sa.Column('config_schema', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('default_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), 
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), 
                  server_default=sa.text('now()'), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
    )
    
    op.create_index('ix_workspace_templates_name', 'workspace_templates', ['name'], unique=True)
    op.create_index('ix_workspace_templates_is_available', 'workspace_templates', ['is_available'])
    
    # =========================================================================
    # Seed Workspace Templates
    # =========================================================================
    conn.execute(sa.text("""
        INSERT INTO workspace_templates (name, display_name, description, icon, is_available, config_schema, default_config)
        VALUES 
        (
            'rag_retrieval',
            'RAG Retrieval',
            'Create a knowledge base from your documents for intelligent Q&A. Upload PDFs, documents, and files to enable AI-powered search and chat.',
            'document-search',
            true,
            '{"type": "object", "properties": {"knowledge_bases": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "parser_type": {"type": "string", "enum": ["naive", "deepdoc", "gpt-4o", "custom-vlm"]}, "parser_config": {"type": "object"}}}}}}',
            '{"knowledge_bases": []}'
        ),
        (
            'data_analytics',
            'Multi Source / Data Analytics',
            'Connect to databases and data sources for analytics queries. Run SQL queries, create reports, and analyze data from multiple sources.',
            'chart-bar',
            false,
            '{"type": "object", "properties": {"data_sources": {"type": "array", "items": {"type": "object", "properties": {"type": {"type": "string"}, "connection_string": {"type": "string"}}}}}}',
            '{"data_sources": []}'
        )
        ON CONFLICT (name) DO NOTHING
    """))
    
    # =========================================================================
    # Update ragflow_domains (Workspaces) - Add template_id
    # =========================================================================
    op.add_column('ragflow_domains',
        sa.Column('template_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_ragflow_domains_template_id',
        'ragflow_domains', 'workspace_templates',
        ['template_id'], ['id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_ragflow_domains_template_id', 'ragflow_domains', ['template_id'])
    
    # Add workspace-level config column
    op.add_column('ragflow_domains',
        sa.Column('workspace_config', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )
    
    # Backfill existing domains to use rag_retrieval template
    conn.execute(sa.text("""
        UPDATE ragflow_domains 
        SET template_id = (SELECT id FROM workspace_templates WHERE name = 'rag_retrieval')
        WHERE template_id IS NULL
    """))
    
    # =========================================================================
    # Table 2: Knowledge Bases
    # =========================================================================
    op.create_table(
        'knowledge_bases',
        
        # Primary key
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        
        # Workspace relationship
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        
        # Multi-tenant isolation (denormalized for RLS)
        sa.Column('customer_id', sa.String(100), nullable=False),
        
        # Knowledge base identification
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        
        # RAGFlow integration
        sa.Column('ragflow_dataset_id', sa.String(100), nullable=True, unique=True),
        
        # Parser configuration
        sa.Column('parser_type', sa.String(50), nullable=False, server_default='naive'),
        sa.Column('parser_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        # Embedding configuration
        sa.Column('embedding_model', sa.String(100), nullable=False, 
                  server_default='text-embedding-3-large@OpenAI'),
        sa.Column('chunk_token_count', sa.Integer(), nullable=False, server_default='512'),
        
        # Retrieval configuration
        sa.Column('similarity_threshold', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('top_k', sa.Integer(), nullable=False, server_default='5'),
        
        # Statistics (synced from RAGFlow)
        sa.Column('document_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        
        # Status
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        
        # Flags
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        
        # Audit
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), 
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), 
                  server_default=sa.text('now()'), nullable=True),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['workspace_id'], ['ragflow_domains.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.UniqueConstraint('workspace_id', 'name', name='uq_knowledge_base_workspace_name'),
    )
    
    # Indexes for knowledge_bases
    op.create_index('ix_knowledge_bases_workspace_id', 'knowledge_bases', ['workspace_id'])
    op.create_index('ix_knowledge_bases_customer_id', 'knowledge_bases', ['customer_id'])
    op.create_index('ix_knowledge_bases_status', 'knowledge_bases', ['status'])
    op.create_index('ix_knowledge_bases_ragflow_dataset_id', 'knowledge_bases', 
                    ['ragflow_dataset_id'], unique=True)
    
    # =========================================================================
    # Table 3: Knowledge Base Documents (link existing docs to KBs)
    # =========================================================================
    # Add knowledge_base_id to ragflow_documents
    op.add_column('ragflow_documents',
        sa.Column('knowledge_base_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_ragflow_documents_knowledge_base_id',
        'ragflow_documents', 'knowledge_bases',
        ['knowledge_base_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_index('ix_ragflow_documents_knowledge_base_id', 'ragflow_documents', ['knowledge_base_id'])
    
    # =========================================================================
    # Table 4: Knowledge Base Permissions
    # =========================================================================
    op.create_table(
        'knowledge_base_permissions',
        
        # Primary key
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        
        # Knowledge base relationship
        sa.Column('knowledge_base_id', sa.Integer(), nullable=False),
        
        # Permission target (user OR role, not both)
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('role_id', sa.Integer(), nullable=True),
        
        # Permission type
        sa.Column('permission_type', sa.String(50), nullable=False),  # read, write, admin
        
        # Audit
        sa.Column('granted_by_user_id', sa.Integer(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), 
                  server_default=sa.text('now()'), nullable=False),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledge_bases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['granted_by_user_id'], ['users.id']),
        sa.CheckConstraint(
            "(user_id IS NOT NULL AND role_id IS NULL) OR (user_id IS NULL AND role_id IS NOT NULL)",
            name='kb_perm_user_or_role'
        ),
        sa.UniqueConstraint('knowledge_base_id', 'user_id', name='uq_kb_perm_user'),
        sa.UniqueConstraint('knowledge_base_id', 'role_id', name='uq_kb_perm_role'),
    )
    
    # Indexes for knowledge_base_permissions
    op.create_index('ix_kb_permissions_knowledge_base_id', 'knowledge_base_permissions', 
                    ['knowledge_base_id'])
    op.create_index('ix_kb_permissions_user_id', 'knowledge_base_permissions', ['user_id'])
    op.create_index('ix_kb_permissions_role_id', 'knowledge_base_permissions', ['role_id'])
    
    # =========================================================================
    # Migrate Existing Data: Create default KB for each existing workspace
    # =========================================================================
    # For each existing ragflow_domain, create a knowledge_base entry
    conn.execute(sa.text("""
        INSERT INTO knowledge_bases (
            workspace_id, customer_id, name, description,
            ragflow_dataset_id, parser_type, parser_config,
            embedding_model, chunk_token_count, similarity_threshold, top_k,
            document_count, chunk_count, total_tokens,
            status, last_sync_at, last_error, is_active,
            created_by_user_id, created_at, updated_at
        )
        SELECT 
            rd.id as workspace_id,
            rd.customer_id,
            'Default' as name,
            'Default knowledge base for ' || rd.display_name as description,
            rd.ragflow_dataset_id,
            COALESCE(rd.parser_type::text, 'naive') as parser_type,
            rd.parser_config,
            rd.embedding_model,
            rd.chunk_token_count,
            rd.similarity_threshold,
            rd.top_k,
            rd.document_count,
            rd.chunk_count,
            rd.total_tokens,
            rd.status::text as status,
            rd.last_sync_at,
            rd.last_error,
            rd.is_active,
            rd.created_by_user_id,
            rd.created_at,
            rd.updated_at
        FROM ragflow_domains rd
        WHERE NOT EXISTS (
            SELECT 1 FROM knowledge_bases kb WHERE kb.workspace_id = rd.id
        )
    """))
    
    # Update ragflow_documents to link to knowledge_bases
    conn.execute(sa.text("""
        UPDATE ragflow_documents rd
        SET knowledge_base_id = kb.id
        FROM knowledge_bases kb
        WHERE rd.domain_id = kb.workspace_id
          AND rd.knowledge_base_id IS NULL
    """))


def downgrade() -> None:
    """
    Drop workspace architecture tables in reverse order.
    """
    # Remove knowledge_base_id from ragflow_documents
    op.drop_index('ix_ragflow_documents_knowledge_base_id', table_name='ragflow_documents')
    op.drop_constraint('fk_ragflow_documents_knowledge_base_id', 'ragflow_documents', type_='foreignkey')
    op.drop_column('ragflow_documents', 'knowledge_base_id')
    
    # Drop knowledge_base_permissions
    op.drop_index('ix_kb_permissions_role_id', table_name='knowledge_base_permissions')
    op.drop_index('ix_kb_permissions_user_id', table_name='knowledge_base_permissions')
    op.drop_index('ix_kb_permissions_knowledge_base_id', table_name='knowledge_base_permissions')
    op.drop_table('knowledge_base_permissions')
    
    # Drop knowledge_bases
    op.drop_index('ix_knowledge_bases_ragflow_dataset_id', table_name='knowledge_bases')
    op.drop_index('ix_knowledge_bases_status', table_name='knowledge_bases')
    op.drop_index('ix_knowledge_bases_customer_id', table_name='knowledge_bases')
    op.drop_index('ix_knowledge_bases_workspace_id', table_name='knowledge_bases')
    op.drop_table('knowledge_bases')
    
    # Remove template columns from ragflow_domains
    op.drop_column('ragflow_domains', 'workspace_config')
    op.drop_index('ix_ragflow_domains_template_id', table_name='ragflow_domains')
    op.drop_constraint('fk_ragflow_domains_template_id', 'ragflow_domains', type_='foreignkey')
    op.drop_column('ragflow_domains', 'template_id')
    
    # Drop workspace_templates
    op.drop_index('ix_workspace_templates_is_available', table_name='workspace_templates')
    op.drop_index('ix_workspace_templates_name', table_name='workspace_templates')
    op.drop_table('workspace_templates')
