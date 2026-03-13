# Critical Patterns - Platform Skeleton

These patterns are **mandatory** for maintaining platform consistency and avoiding common pitfalls.

## 1. Database Session Management

### The Problem
SQLAlchemy sessions cannot be pickled. Storing them in flow state breaks Celery tasks.

### ✅ CORRECT Pattern

```python
# Always use module import
from src.models import database

# Check initialization before use
if database.SessionLocal is None:
    database.init_database()

# Create session locally
db = database.SessionLocal()
try:
    # Use db here
    result = db.query(YourModel).filter(...).all()
finally:
    db.close()
```

### ❌ WRONG Patterns

```python
# WRONG: Direct import creates local binding
from src.models.database import SessionLocal
db = SessionLocal()  # May be None if not initialized!

# WRONG: Storing session in state
class FlowState(BaseModel):
    db_session: Session  # Breaks Celery pickling!

# WRONG: Assuming SessionLocal exists
db = SessionLocal()  # May fail if not initialized
```

### When to Use

- **Celery tasks**: Always use this pattern
- **CrewAI flows**: Always use this pattern
- **API routes**: Can use `Depends(get_db)` dependency injection
- **Services**: Use this pattern or dependency injection

## 2. Multi-Tenancy Data Isolation

### The Problem
All data must be filtered by `customer_id` to prevent cross-tenant data access.

### ✅ CORRECT Pattern

```python
# Always filter by customer_id
def get_user_documents(db: Session, customer_id: str):
    return db.query(Document).filter(
        Document.customer_id == customer_id
    ).all()

# In API routes, use current_user
@router.get("/documents")
async def get_documents(
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("documents:read"))
):
    return db.query(Document).filter(
        Document.customer_id == current_user.customer_id
    ).all()
```

### Company-Specific Data

For company-specific data (like HR datasets), use `company_hr_dataset`:

```python
# ✅ CORRECT: Filter by both customer_id and company_hr_dataset
results = await vector_service.search_similar_chunks(
    query=query,
    company_hr_dataset="target_company",  # Critical!
    limit=10
)

# ✅ CORRECT: Document search tool
doc_tool = DocumentSearchTool(
    customer_id=user.customer_id,
    company_hr_dataset=target_company,  # Critical!
    limit=10
)
```

### ❌ WRONG Patterns

```python
# WRONG: No customer_id filter
def get_all_documents(db: Session):
    return db.query(Document).all()  # Returns ALL customers' data!

# WRONG: Using customer_id for company-specific searches
results = await vector_service.search_similar_chunks(
    query=query,
    customer_id="eliza",  # Wrong! Should use company_hr_dataset
    limit=10
)
```

## 3. API Route Pattern

### Standard Pattern

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.models.database import get_db
from src.middleware.authorization import require_permission
from src.api.schemas import YourRequest, YourResponse
from src.services.your_service import YourService

router = APIRouter(prefix="/v1/your-feature", tags=["Your Feature"])

@router.post("/endpoint", response_model=YourResponse)
async def your_endpoint(
    request: YourRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("your-feature:write"))
):
    """
    Endpoint description.
    
    Requires permission: your-feature:write
    """
    try:
        service = YourService(db)
        result = service.process(request, current_user.customer_id)
        return YourResponse(**result)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
```

### Key Elements

1. **Router prefix**: `/v1/your-feature`
2. **Tags**: For API documentation grouping
3. **Dependency injection**: `get_db` for database, `require_permission` for auth
4. **Response model**: Pydantic model for validation
5. **Error handling**: Proper HTTP exceptions

## 4. Celery Task Pattern

### Standard Pattern

```python
from src.celery_app import celery_app
from src.models import database
from src.services.your_service import YourService
import structlog

logger = structlog.get_logger(__name__)

@celery_app.task(bind=True, max_retries=3)
def your_task(self, task_data: dict):
    """
    Async task description.
    
    Args:
        task_data: Dictionary with task parameters
    """
    # Initialize database
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    try:
        logger.info("task_started", task_id=self.request.id)
        
        service = YourService(db)
        result = service.process(task_data)
        
        logger.info("task_completed", task_id=self.request.id)
        return {"success": True, "result": result}
        
    except Exception as e:
        logger.error("task_failed", task_id=self.request.id, error=str(e))
        # Retry logic handled by Celery
        raise
    finally:
        db.close()
```

### Key Elements

1. **Database initialization**: Check and initialize before use
2. **Try-finally**: Always close database session
3. **Logging**: Log start, completion, and errors
4. **Return value**: Serializable dictionary
5. **Error handling**: Let Celery handle retries

## 5. Service Layer Pattern

### Standard Pattern

```python
from sqlalchemy.orm import Session
from src.services.base_service import BaseService
from src.models.your_model import YourModel
import structlog

logger = structlog.get_logger(__name__)

class YourService(BaseService):
    """Service for your feature business logic."""
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.db = db
    
    def create_item(self, data: dict, customer_id: str) -> YourModel:
        """Create a new item."""
        logger.info("creating_item", customer_id=customer_id)
        
        item = YourModel(
            customer_id=customer_id,
            **data
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        
        logger.info("item_created", item_id=item.id, customer_id=customer_id)
        return item
    
    def get_items(self, customer_id: str) -> list[YourModel]:
        """Get all items for customer."""
        return self.db.query(YourModel).filter(
            YourModel.customer_id == customer_id
        ).all()
```

### Key Elements

1. **Inherit BaseService**: Provides common functionality
2. **Database session**: Passed in constructor
3. **Customer filtering**: Always filter by `customer_id`
4. **Logging**: Log important operations
5. **Error handling**: Let exceptions bubble up

## 6. Frontend Component Pattern

### Page Component Pattern

```typescript
import React, { useState, useEffect } from 'react';
import { Layout } from '../components/layout/Layout';
import { useYourFeatureApi } from '../services/api';

export function YourFeaturePage() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const api = useYourFeatureApi();

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const result = await api.getItems();
        setData(result);
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <Layout pageTitle="Your Feature">
      <div className="p-6">
        {loading ? (
          <div>Loading...</div>
        ) : (
          <div>
            {/* Your content */}
          </div>
        )}
      </div>
    </Layout>
  );
}
```

### Key Elements

1. **Use Layout component**: Provides navigation and structure
2. **State management**: useState for local state
3. **API hooks**: Use generated API clients
4. **Loading states**: Show loading indicators
5. **Error handling**: Try-catch for API calls

## 7. Pydantic Schema Pattern

### Request/Response Schemas

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class YourItemRequest(BaseModel):
    """Request schema for creating/updating items."""
    name: str = Field(..., description="Item name", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="Item description")
    metadata: Optional[dict] = Field(None, description="Additional metadata")

class YourItemResponse(BaseModel):
    """Response schema for items."""
    id: int
    name: str
    description: Optional[str]
    customer_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # For SQLAlchemy model conversion
```

### Key Elements

1. **Field validation**: Use Field for constraints
2. **Optional fields**: Use Optional for nullable fields
3. **Response models**: Include all relevant fields
4. **Config**: Use `from_attributes = True` for SQLAlchemy

## 8. Container Rebuild Pattern

### The Problem
Docker containers cache layers. Code changes require rebuild.

### ✅ CORRECT Pattern

```bash
# After code changes
docker-compose build app celery-worker frontend
docker-compose up -d app celery-worker frontend

# For troubleshooting
docker-compose build --no-cache app celery-worker frontend
```

### ❌ WRONG Pattern

```bash
# WRONG: Restart doesn't rebuild
docker-compose restart celery-worker  # Uses old image!
```

## 9. Migration Pattern

### Creating Migrations

```bash
# Create migration
docker-compose run --rm app alembic revision -m "add_your_feature_table"

# Edit migration file in alembic/versions/
# Add upgrade() and downgrade() functions

# Run migration
docker-compose run --rm app alembic upgrade head
```

### Migration File Pattern

```python
"""add_your_feature_table

Revision ID: abc123
Revises: def456
Create Date: 2024-01-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'abc123'
down_revision = 'def456'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'your_table',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_your_table_customer_id', 'your_table', ['customer_id'])

def downgrade():
    op.drop_index('ix_your_table_customer_id', 'your_table')
    op.drop_table('your_table')
```

## 10. Environment Configuration Pattern

### .env File Structure

```bash
# Application
CUSTOMER_ID=your_customer
CUSTOMER_NAME=Your Customer Name
ENVIRONMENT=development

# Database
DATABASE_URL=postgresql://user:password@postgres:5432/ai_platform
REDIS_URL=redis://redis:6379

# Security
JWT_SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-encryption-key-here

# AI Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_LLM_MODEL=gpt-4o-mini
```

### Configuration Access

```python
from src.core.config import get_settings

settings = get_settings()
customer_id = settings.customer_id
database_url = settings.database_url
```

---

## Summary Checklist

When building features, ensure:

- [ ] Database sessions created locally, never in state
- [ ] All queries filtered by `customer_id`
- [ ] Company-specific data uses `company_hr_dataset`
- [ ] API routes use dependency injection
- [ ] Celery tasks initialize database properly
- [ ] Services filter by customer_id
- [ ] Frontend uses Layout component
- [ ] Pydantic schemas validate inputs
- [ ] Containers rebuilt after code changes
- [ ] Migrations follow naming conventions

---

**Remember**: These patterns prevent common bugs and maintain platform consistency. Follow them religiously.

