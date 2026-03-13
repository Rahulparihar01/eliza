"""Add RAGFlow domain, document, conversation, and message tables

Revision ID: zz17_add_ragflow_tables
Revises: zz16_add_eval_sets
Create Date: 2026-01-21

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'zz17_add_ragflow_tables'
down_revision = 'zz16_add_eval_sets'
branch_labels = None
depends_on = None
tags = ["core"]


def upgrade() -> None:
    # Create ragflow_parser_type enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE ragflow_parser_type AS ENUM ('naive', 'deepdoc', 'gpt-4o', 'docling');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create ragflow_domain_status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE ragflow_domain_status AS ENUM ('active', 'inactive', 'syncing', 'error');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create ragflow_document_status enum
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE ragflow_document_status AS ENUM ('pending', 'parsing', 'completed', 'failed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create ragflow_domains table
    op.execute("""
        CREATE TABLE IF NOT EXISTS ragflow_domains (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            
            -- Identification
            customer_id VARCHAR(100) NOT NULL REFERENCES customers(customer_id),
            name VARCHAR(255) NOT NULL,
            display_name VARCHAR(255) NOT NULL,
            description TEXT,
            
            -- RAGFlow dataset mapping
            ragflow_dataset_id VARCHAR(100) UNIQUE,
            ragflow_dataset_name VARCHAR(255),
            
            -- Status
            status ragflow_domain_status NOT NULL DEFAULT 'active',
            last_sync_at TIMESTAMPTZ,
            last_sync_error TEXT,
            
            -- Parser configuration
            parser_type ragflow_parser_type NOT NULL DEFAULT 'naive',
            parser_config JSONB,
            
            -- Embedding configuration
            embedding_model VARCHAR(100) NOT NULL DEFAULT 'text-embedding-3-large@OpenAI',
            chunk_token_count INTEGER NOT NULL DEFAULT 512,
            
            -- Retrieval configuration
            similarity_threshold INTEGER NOT NULL DEFAULT 20,
            top_k INTEGER NOT NULL DEFAULT 5,
            
            -- Statistics
            document_count INTEGER NOT NULL DEFAULT 0,
            chunk_count INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            
            -- Feature flags
            is_active BOOLEAN NOT NULL DEFAULT true,
            
            -- Audit
            created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            
            -- Constraints
            CONSTRAINT uq_ragflow_domain_name UNIQUE (customer_id, name)
        );
    """)
    
    # Create indexes for ragflow_domains
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ragflow_domains_customer_id ON ragflow_domains (customer_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ragflow_domains_customer_status ON ragflow_domains (customer_id, status);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ragflow_domains_ragflow_dataset_id ON ragflow_domains (ragflow_dataset_id);
    """)
    
    # Create ragflow_documents table
    op.execute("""
        CREATE TABLE IF NOT EXISTS ragflow_documents (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            
            -- Domain relationship
            domain_id INTEGER NOT NULL REFERENCES ragflow_domains(id) ON DELETE CASCADE,
            customer_id VARCHAR(100) NOT NULL REFERENCES customers(customer_id),
            
            -- File information
            original_filename VARCHAR(500) NOT NULL,
            file_size INTEGER NOT NULL,
            mime_type VARCHAR(100) NOT NULL,
            
            -- RAGFlow mapping
            ragflow_document_id VARCHAR(100) UNIQUE,
            ragflow_run_id VARCHAR(100),
            
            -- Status
            status ragflow_document_status NOT NULL DEFAULT 'pending',
            progress INTEGER NOT NULL DEFAULT 0,
            processing_error TEXT,
            
            -- Processing results
            chunk_count INTEGER NOT NULL DEFAULT 0,
            token_count INTEGER NOT NULL DEFAULT 0,
            processing_started_at TIMESTAMPTZ,
            processing_completed_at TIMESTAMPTZ,
            
            -- Metadata
            document_metadata JSONB,
            
            -- Audit
            uploaded_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
        );
    """)
    
    # Create indexes for ragflow_documents
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ragflow_documents_domain_id ON ragflow_documents (domain_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ragflow_documents_customer_id ON ragflow_documents (customer_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ragflow_documents_domain_status ON ragflow_documents (domain_id, status);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ragflow_documents_ragflow_document_id ON ragflow_documents (ragflow_document_id);
    """)
    
    # Create ragflow_conversations table
    op.execute("""
        CREATE TABLE IF NOT EXISTS ragflow_conversations (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            
            -- Relationships
            domain_id INTEGER NOT NULL REFERENCES ragflow_domains(id) ON DELETE CASCADE,
            customer_id VARCHAR(100) NOT NULL REFERENCES customers(customer_id),
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            
            -- Conversation info
            title VARCHAR(255),
            
            -- Statistics
            message_count INTEGER NOT NULL DEFAULT 0,
            last_message_at TIMESTAMPTZ,
            
            -- Status
            is_active BOOLEAN NOT NULL DEFAULT true
        );
    """)
    
    # Create indexes for ragflow_conversations
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ragflow_conversations_domain_id ON ragflow_conversations (domain_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ragflow_conversations_customer_id ON ragflow_conversations (customer_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ragflow_conversations_user_id ON ragflow_conversations (user_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ragflow_conversations_user_domain ON ragflow_conversations (user_id, domain_id);
    """)
    
    # Create ragflow_messages table
    op.execute("""
        CREATE TABLE IF NOT EXISTS ragflow_messages (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            
            -- Conversation relationship
            conversation_id INTEGER NOT NULL REFERENCES ragflow_conversations(id) ON DELETE CASCADE,
            
            -- Message content
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            
            -- RAG retrieval context (for assistant messages)
            retrieved_chunks JSONB,
            chunk_count INTEGER,
            
            -- Token usage
            prompt_tokens INTEGER,
            completion_tokens INTEGER
        );
    """)
    
    # Create indexes for ragflow_messages
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_ragflow_messages_conversation_id ON ragflow_messages (conversation_id);
    """)


def downgrade() -> None:
    # Drop tables in reverse order (due to foreign keys)
    op.execute("DROP TABLE IF EXISTS ragflow_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS ragflow_conversations CASCADE")
    op.execute("DROP TABLE IF EXISTS ragflow_documents CASCADE")
    op.execute("DROP TABLE IF EXISTS ragflow_domains CASCADE")
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS ragflow_document_status")
    op.execute("DROP TYPE IF EXISTS ragflow_domain_status")
    op.execute("DROP TYPE IF EXISTS ragflow_parser_type")
