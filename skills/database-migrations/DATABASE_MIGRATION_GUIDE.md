# Database Migration Guide

> **Purpose:** This skill ensures database migrations are created correctly, with proper schema changes, indexes, rollback support, and multi-tenant considerations.

---

## Quick Reference

```python
# ✅ CORRECT Migration Pattern
"""add_your_feature_tables

Revision ID: abc123def456
Revises: previous_revision_id
Create Date: 2025-01-16 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'abc123def456'
down_revision = 'previous_revision_id'  # ← Must chain correctly!
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create table with proper constraints and defaults
    op.create_table(
        'your_table',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),  # Multi-tenant!
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
    )
    
    # Create indexes for common queries
    op.create_index('ix_your_table_customer_status', 'your_table', ['customer_id', 'status'])


def downgrade() -> None:
    # Drop in reverse order
    op.drop_index('ix_your_table_customer_status', table_name='your_table')
    op.drop_table('your_table')
```

---

## Critical Rules

### Rule 1: SQLAlchemy Model Must Match Database Schema

**Context:** This is the #1 source of "column does not exist" errors. `BaseModel` automatically gives you `id`, `created_at`, and `updated_at` columns. If the actual database table has a different schema, queries will fail.

```python
# src/models/database.py - BaseModel gives you these columns automatically:
class BaseModel(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

# ❌ WRONG: Using BaseModel when table lacks updated_at
class TalentAnalysis(BaseModel):  # Inherits id, created_at, updated_at
    __tablename__ = "talent_analyses"
    # But migration only creates id and created_at!
    # Result: "column talent_analyses.updated_at does not exist"

# ✅ CORRECT: Override missing columns
class TalentAnalysis(BaseModel):
    __tablename__ = "talent_analyses"
    updated_at = None  # Explicitly exclude inherited column
    
    # OR use custom timestamp columns
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

# ✅ CORRECT: Use Base instead of BaseModel for custom schemas
class TalentAnalysisEvent(Base):  # NOT BaseModel
    __tablename__ = "talent_analysis_events"
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, server_default=func.now())
    # Only define columns that actually exist
```

### Rule 2: Always Chain Migrations Correctly

**Context:** Broken migration chains cause Alembic to fail or skip migrations entirely, leaving the database in an inconsistent state.

```python
# ❌ WRONG: Guessing the down_revision
revision = 'new_revision_id'
down_revision = 'some_old_revision'  # Wrong! Skips intermediate migrations

# ✅ CORRECT: Check the current head first
# $ alembic heads

revision = 'new_revision_id'
down_revision = 'actual_previous_revision'  # ← Get this right!
branch_labels = None
depends_on = None
```

**To find the correct down_revision:**

```bash
# List all migrations
alembic history

# Get current head
alembic heads

# If multiple heads (branching), you may need to merge:
alembic merge -m "merge heads" rev1 rev2
```

### Rule 3: Include All Standard Columns for Multi-Tenant Tables

**Context:** Missing `customer_id` breaks tenant isolation. Missing timestamps break `BaseModel` compatibility and audit trails.

```python
def upgrade() -> None:
    op.create_table(
        'your_multi_tenant_table',
        # Primary key
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        
        # ✅ REQUIRED: Multi-tenant isolation
        sa.Column('customer_id', sa.String(100), nullable=False),
        
        # ✅ RECOMMENDED: Audit trail
        sa.Column('user_id', sa.Integer(), nullable=True),
        
        # Your columns
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), server_default='pending'),
        
        # ✅ REQUIRED: Timestamps for BaseModel compatibility
        sa.Column('created_at', sa.DateTime(timezone=True), 
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), 
                  server_default=sa.text('now()'), nullable=True),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
```

### Rule 4: Create Proper Indexes

**Context:** Missing indexes cause slow queries on multi-tenant tables, especially for filtered listings and lookups.

```python
def upgrade() -> None:
    # After creating table...
    
    # ✅ Composite index for common multi-tenant queries
    op.create_index(
        'ix_your_table_customer_status',
        'your_table',
        ['customer_id', 'status']
    )
    
    # ✅ Index for unique lookups
    op.create_index(
        op.f('ix_your_table_entity_id'),
        'your_table',
        ['entity_id'],
        unique=True
    )
    
    # ✅ Index for time-based queries
    op.create_index(
        'ix_your_table_created_at',
        'your_table',
        ['created_at']
    )
    
    # ✅ Index for foreign key lookups
    op.create_index(
        op.f('ix_your_table_user_id'),
        'your_table',
        ['user_id']
    )
```

---

## Patterns

### SQLAlchemy Model Template

Create the matching model in `src/models/your_feature.py`:

```python
"""
[Feature] Database Models

SQLAlchemy models for [feature description].
"""
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum

from src.models.database import BaseModel, Base


class YourStatus(str, Enum):
    """Status values for YourEntity."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class YourEventType(str, Enum):
    """Event types for telemetry."""
    STARTED = "started"
    PROGRESS = "progress"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    TOOL_CALLED = "tool_called"
    ERROR = "error"
    COMPLETED = "completed"


class YourEntity(BaseModel):
    """Main entity model."""
    __tablename__ = "your_main_table"
    
    # Note: id, created_at, updated_at inherited from BaseModel
    
    entity_id = Column(String(100), unique=True, nullable=False, index=True)
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), 
                         nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Input fields
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    config = Column(JSON, nullable=True)
    
    # Status
    status = Column(String(50), nullable=False, default=YourStatus.PENDING.value)
    error_message = Column(Text, nullable=True)
    
    # Results
    result = Column(JSON, nullable=True)
    entity_metadata = Column("metadata", JSON, nullable=True)  # Renamed to avoid SQLAlchemy conflict
    
    # Metrics
    progress_percentage = Column(Float, default=0)
    items_processed = Column(Integer, default=0)
    
    # Timing (custom columns, not from BaseModel)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Task tracking
    task_id = Column(String(100), nullable=True, index=True)
    
    # Relationships
    events = relationship(
        "YourEvent",
        back_populates="entity",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    customer = relationship("Customer", back_populates="your_entities")
    user = relationship("User")


class YourEvent(Base):  # Note: Using Base, not BaseModel
    """Event/telemetry model for tracking progress."""
    __tablename__ = "your_events_table"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(
        String(100),
        ForeignKey("your_main_table.entity_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Event details
    event_type = Column(String(50), nullable=False)
    agent_name = Column(String(100), nullable=True)
    tool_name = Column(String(100), nullable=True)
    stage_name = Column(String(100), nullable=True)
    
    # Messages
    message = Column(Text, nullable=True)
    user_message = Column(Text, nullable=True)
    
    # Progress
    progress_percentage = Column(Float, nullable=True)
    
    # Data
    data = Column(JSON, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Timing
    duration_ms = Column(Integer, nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # Relationship
    entity = relationship("YourEntity", back_populates="events")
```

### Adding a Column to Existing Table

```python
def upgrade() -> None:
    op.add_column(
        'existing_table',
        sa.Column('new_column', sa.String(100), nullable=True)
    )
    
    # If column should have default for existing rows:
    op.execute("UPDATE existing_table SET new_column = 'default_value' WHERE new_column IS NULL")
    
    # Then make non-nullable if needed:
    op.alter_column('existing_table', 'new_column', nullable=False)

def downgrade() -> None:
    op.drop_column('existing_table', 'new_column')
```

### Adding an Index

```python
def upgrade() -> None:
    op.create_index(
        'ix_table_column',
        'table_name',
        ['column_name'],
        unique=False
    )

def downgrade() -> None:
    op.drop_index('ix_table_column', table_name='table_name')
```

### Renaming a Column

```python
def upgrade() -> None:
    op.alter_column(
        'table_name',
        'old_column_name',
        new_column_name='new_column_name'
    )

def downgrade() -> None:
    op.alter_column(
        'table_name',
        'new_column_name',
        new_column_name='old_column_name'
    )
```

### Changing Column Type

```python
def upgrade() -> None:
    # For PostgreSQL, may need USING clause for type conversion
    op.alter_column(
        'table_name',
        'column_name',
        type_=sa.Text(),
        postgresql_using='column_name::text'
    )

def downgrade() -> None:
    op.alter_column(
        'table_name',
        'column_name',
        type_=sa.String(255),
        postgresql_using='column_name::varchar(255)'
    )
```

---

## Complete Template

```python
"""add_[feature]_tables

Create tables for [feature description].

Revision ID: [auto-generated]
Revises: [previous revision]
Create Date: [auto-generated]
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'abc123def456'
down_revision = 'previous_revision_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create [feature] tables.
    
    Tables created:
    - your_main_table: Main entity table
    - your_events_table: Events/audit log for main entity
    """
    
    # ================================================================
    # Table 1: Main entity table
    # ================================================================
    op.create_table(
        'your_main_table',
        # Primary key
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_id', sa.String(100), nullable=False),
        
        # Multi-tenant isolation
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        
        # Input fields
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        # Status tracking
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        
        # Results (JSON for flexibility)
        sa.Column('result', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        # Metrics
        sa.Column('progress_percentage', sa.Float(), server_default='0'),
        sa.Column('items_processed', sa.Integer(), server_default='0'),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), 
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), 
                  server_default=sa.text('now()'), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        
        # Task tracking (for Celery integration)
        sa.Column('task_id', sa.String(100), nullable=True),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.UniqueConstraint('entity_id'),
    )
    
    # Indexes for main table
    op.create_index(
        'ix_your_main_table_customer_status',
        'your_main_table',
        ['customer_id', 'status']
    )
    op.create_index(
        'ix_your_main_table_created_at',
        'your_main_table',
        ['created_at']
    )
    op.create_index(
        op.f('ix_your_main_table_entity_id'),
        'your_main_table',
        ['entity_id'],
        unique=True
    )
    op.create_index(
        op.f('ix_your_main_table_task_id'),
        'your_main_table',
        ['task_id']
    )
    
    # ================================================================
    # Table 2: Events table (for telemetry/audit)
    # ================================================================
    op.create_table(
        'your_events_table',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_id', sa.String(100), nullable=False),
        
        # Event details
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('agent_name', sa.String(100), nullable=True),
        sa.Column('tool_name', sa.String(100), nullable=True),
        sa.Column('stage_name', sa.String(100), nullable=True),
        
        # Messages
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('user_message', sa.Text(), nullable=True),  # User-friendly message
        
        # Progress
        sa.Column('progress_percentage', sa.Float(), nullable=True),
        
        # Data payload
        sa.Column('data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        # Timing
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), 
                  server_default=sa.text('now()'), nullable=False),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(
            ['entity_id'],
            ['your_main_table.entity_id'],
            ondelete='CASCADE'  # Delete events when entity is deleted
        ),
    )
    
    # Indexes for events table
    op.create_index(
        'ix_your_events_entity_timestamp',
        'your_events_table',
        ['entity_id', 'timestamp']
    )
    op.create_index(
        op.f('ix_your_events_table_entity_id'),
        'your_events_table',
        ['entity_id']
    )
    op.create_index(
        op.f('ix_your_events_table_timestamp'),
        'your_events_table',
        ['timestamp']
    )


def downgrade() -> None:
    """
    Drop [feature] tables in reverse order.
    
    Events table first (has FK to main), then main table.
    """
    # Drop events table indexes
    op.drop_index(op.f('ix_your_events_table_timestamp'), table_name='your_events_table')
    op.drop_index(op.f('ix_your_events_table_entity_id'), table_name='your_events_table')
    op.drop_index('ix_your_events_entity_timestamp', table_name='your_events_table')
    
    # Drop main table indexes
    op.drop_index(op.f('ix_your_main_table_task_id'), table_name='your_main_table')
    op.drop_index(op.f('ix_your_main_table_entity_id'), table_name='your_main_table')
    op.drop_index('ix_your_main_table_created_at', table_name='your_main_table')
    op.drop_index('ix_your_main_table_customer_status', table_name='your_main_table')
    
    # Drop tables (FK constraint requires events first)
    op.drop_table('your_events_table')
    op.drop_table('your_main_table')
```

---

## Integration

### Step 1: Create a New Migration

```bash
# Create a new migration
alembic revision -m "add_your_feature_tables"
```

### Step 2: Apply Migrations (Development)

```bash
# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade abc123def456

# Show current revision
alembic current

# Show migration history
alembic history
```

### Step 3: Apply Migrations (Docker)

```bash
# Run migration inside container
docker-compose exec app alembic upgrade head

# Or rebuild container (if RUN_MIGRATIONS=true in env)
docker-compose build app
docker-compose up -d app
```

### Step 4: Production Considerations

```bash
# Generate SQL without running (for review)
alembic upgrade head --sql > migration.sql

# Run migration with transaction
alembic upgrade head

# Note: Only ONE container should run migrations
# Set RUN_MIGRATIONS=true only on the app container, not celery-worker
```

---

## File Locations

```
alembic/
├── versions/
│   └── abc123_add_feature.py    # Migration files
├── env.py                       # Alembic environment config
└── alembic.ini                  # Alembic settings

src/models/
├── database.py                  # BaseModel, Base, SessionLocal, init_database
└── your_feature.py              # SQLAlchemy model definitions
```

---

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| "Column does not exist" error | Check SQLAlchemy model matches migration: `docker exec docker-postgres-1 psql -U user -d ai_enablement -c "\d table_name"`. Override missing columns with `updated_at = None` or use `Base` instead of `BaseModel`. |
| Multiple heads | Check with `alembic heads`, merge if needed: `alembic merge -m "merge heads" rev1 rev2` |
| Migration not applied | Check with `alembic current`. Verify migration file exists in container: `docker exec docker-app-1 ls -la /app/alembic/versions/`. Rebuild with `docker-compose build app --no-cache` if missing. |
| Missing `customer_id` on new table | Always include `customer_id` column for multi-tenant tables with a foreign key to `customers.customer_id` |
| No indexes on filtered columns | Add composite indexes for `(customer_id, status)` and individual indexes for lookup columns |
| `downgrade()` doesn't reverse `upgrade()` | Drop indexes before tables, drop child tables before parents, mirror every `upgrade()` operation |

---

## Checklist

- [ ] down_revision chains correctly to previous migration
- [ ] All columns include proper types and constraints
- [ ] customer_id column included for multi-tenant tables
- [ ] Timestamps (created_at, updated_at) match BaseModel expectations
- [ ] Indexes created for common query patterns
- [ ] Foreign keys have appropriate ON DELETE behavior
- [ ] downgrade() reverses all upgrade() operations
- [ ] SQLAlchemy model created/updated to match schema
- [ ] Model uses correct base class (BaseModel vs Base)
- [ ] Container rebuilt: `docker-compose build app`
- [ ] Migration tested: `alembic upgrade head` and `alembic downgrade -1`

---

## References

- `alembic/versions/` — Migration files
- `src/models/database.py` — Base model classes (BaseModel, Base, SessionLocal)
- `src/models/` — SQLAlchemy model definitions
- `alembic.ini` — Alembic configuration
- `skills/fastapi-endpoints/` — API patterns that depend on database models
- `skills/celery-tasks/` — Task patterns that use database sessions
- [Alembic Documentation](https://alembic.sqlalchemy.org/) — Official Alembic docs
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/) — Official SQLAlchemy docs
