# Celery Task Development Guide

> **Purpose:** This skill ensures Celery async tasks are built correctly the first time, avoiding common pitfalls with database sessions, serialization, and error handling.

---

## Quick Reference

```python
# ✅ CORRECT Celery Task Pattern
from src.celery_app import celery_app
from src.models import database
from src.core.logging import get_logger, LogCategory, bind_context

logger = get_logger(__name__, LogCategory.BUSINESS)

class MyTask(Task):
    """Base task class with retry logic."""
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 5}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True

@celery_app.task(base=MyTask, bind=True, name="my_task_name")
def my_task(self, entity_id: str, user_id: int, customer_id: str) -> Dict[str, Any]:
    """Process something asynchronously."""
    bind_context(task="my_task_name", entity_id=entity_id, user_id=user_id)
    logger.info("task_start", entity_id=entity_id)
    
    # ✅ CRITICAL: Module-level import + check + initialize
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    try:
        # Your business logic here
        service = MyService(db)
        result = service.process(entity_id)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error("task_failed", error=str(e), exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()  # ✅ ALWAYS close in finally
```

---

## Critical Rules

### Rule 1: Database Session Management

**Context:** SQLAlchemy sessions cannot be serialized. `SessionLocal` is `None` at module load time. Direct imports (`from x import y`) create a local binding to the value at import time. Module imports (`from x import module`) always reference the actual global variable. Celery workers may not have the database initialized when they first load.

```python
# ❌ WRONG: Passing session
@celery_app.task
def process_item(db: Session, item_id: int):  # Session not serializable!
    ...

# ❌ WRONG: Direct import creates stale binding
from src.models.database import SessionLocal  # SessionLocal is None at import!

@celery_app.task
def process_item(item_id: int):
    db = SessionLocal()  # ❌ FAILS! Still references None

# ✅ CORRECT: Module import maintains reference to actual global
from src.models import database

@celery_app.task
def process_item(item_id: int):
    if database.SessionLocal is None:
        database.init_database()
    db = database.SessionLocal()  # ✅ Works!
    try:
        ...
    finally:
        db.close()
```

### Rule 2: Task Arguments Must Be Serializable

**Context:** Celery serializes task arguments to send them to workers via the message broker. Only primitive types survive serialization.

```python
# ❌ WRONG: Passing Pydantic models or SQLAlchemy objects
@celery_app.task
def process_question(question: BIQuestion):  # Not serializable!
    ...

# ✅ CORRECT: Pass IDs and lookup in task
@celery_app.task
def process_question(question_id: str, user_id: int, customer_id: str):
    db = get_session()
    question = db.query(BIQuestion).filter_by(question_id=question_id).first()
    ...
```

### Rule 3: Use Base Task Class for Retry Logic

**Context:** Without a base task class, tasks have no retry behavior and fail permanently on transient errors.

```python
from celery import Task

class RetryableTask(Task):
    """Base task with automatic retry on failure."""
    autoretry_for = (Exception,)           # Retry on any exception
    retry_kwargs = {
        'max_retries': 3,                   # Maximum retry attempts
        'countdown': 5                       # Seconds between retries
    }
    retry_backoff = True                    # Exponential backoff
    retry_backoff_max = 600                 # Max backoff: 10 minutes
    retry_jitter = True                     # Add randomness to prevent thundering herd

class CriticalTask(Task):
    """For tasks that should not auto-retry (e.g., payment processing)."""
    max_retries = 0                         # No automatic retries

@celery_app.task(base=RetryableTask, bind=True)
def my_retryable_task(self, item_id: str):
    ...
```

### Rule 4: Handle Timeouts Gracefully

**Context:** Long-running tasks without timeout handling can hang indefinitely, consuming worker slots.

```python
from celery.exceptions import SoftTimeLimitExceeded

@celery_app.task(
    bind=True,
    soft_time_limit=300,   # 5 minute soft limit (raises exception)
    time_limit=360         # 6 minute hard limit (kills task)
)
def long_running_task(self, analysis_id: str):
    try:
        # Long-running work
        ...
    except SoftTimeLimitExceeded:
        logger.error("task_timeout", analysis_id=analysis_id)
        # Save partial progress, update status to failed
        update_status(analysis_id, "failed", "Task exceeded time limit")
        return {"success": False, "error": "Task timed out"}
```

---

## Complete Template

```python
"""
[Feature Name] Celery Tasks

Async tasks for processing [describe what this processes].
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from src.celery_app import celery_app
from src.models import database
from src.models.your_model import YourStatus
from src.services.your_service import YourService
from src.core.logging import get_logger, LogCategory, bind_context

logger = get_logger(__name__, LogCategory.BUSINESS)


class YourFeatureTask(Task):
    """Base task class for [Feature] tasks with retry logic."""
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 5}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True


@celery_app.task(
    base=YourFeatureTask,
    bind=True,
    name="process_your_feature",
    soft_time_limit=300,
    time_limit=360
)
def process_your_feature(
    self,
    entity_id: str,
    user_id: int,
    customer_id: str,
    company_hr_dataset: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process [describe what this task does].
    
    Args:
        entity_id: Unique identifier for the entity being processed
        user_id: User ID who initiated the request
        customer_id: Customer ID (user's organization)
        company_hr_dataset: Target company for data filtering (if applicable)
        
    Returns:
        Dict with processing results including success status
    """
    # Bind logging context for all log messages in this task
    bind_context(
        task="process_your_feature",
        entity_id=entity_id,
        user_id=user_id,
        customer_id=customer_id
    )
    
    logger.info(
        "task_start",
        entity_id=entity_id,
        task_id=self.request.id
    )
    
    # ========================================
    # Database Session Setup (CRITICAL!)
    # ========================================
    if database.SessionLocal is None:
        logger.info("initializing_database", reason="SessionLocal is None")
        database.init_database()
    
    if database.SessionLocal is None:
        raise RuntimeError(
            "SessionLocal is still None after init_database() - "
            "check database configuration"
        )
    
    db = database.SessionLocal()
    
    try:
        service = YourService(db)
        
        # ========================================
        # 1. Validate Entity Exists
        # ========================================
        entity = service.get_entity(entity_id)
        if not entity:
            logger.error("entity_not_found", entity_id=entity_id)
            return {"success": False, "error": "Entity not found"}
        
        # Check if already failed
        if entity.status == YourStatus.FAILED:
            logger.warning(
                "entity_already_failed",
                entity_id=entity_id,
                error=entity.error_message
            )
            return {"success": False, "error": entity.error_message}
        
        # ========================================
        # 2. Update Status to Processing
        # ========================================
        service.update_status(entity_id, YourStatus.PROCESSING)
        
        # ========================================
        # 3. Main Processing Logic
        # ========================================
        logger.info("processing_start", entity_id=entity_id)
        
        try:
            # Your main processing logic here
            result = service.do_processing(entity)
            
            if result.error:
                logger.error(
                    "processing_error",
                    entity_id=entity_id,
                    error=result.error
                )
                service.update_status(
                    entity_id,
                    YourStatus.FAILED,
                    error_message=result.error
                )
                return {"success": False, "error": result.error}
            
            # ========================================
            # 4. Save Results
            # ========================================
            service.save_result(entity_id, result)
            
            # ========================================
            # 5. Update Status to Completed
            # ========================================
            service.update_status(entity_id, YourStatus.COMPLETED)
            
            logger.info(
                "task_complete",
                entity_id=entity_id,
                result_id=result.id
            )
            
            return {
                "success": True,
                "entity_id": entity_id,
                "result_id": result.id,
                "status": "completed"
            }
            
        except SoftTimeLimitExceeded:
            logger.error("task_timeout", entity_id=entity_id)
            service.update_status(
                entity_id,
                YourStatus.FAILED,
                error_message="Processing exceeded time limit"
            )
            return {"success": False, "error": "Task timed out"}
            
    except Exception as e:
        logger.error(
            "task_exception",
            entity_id=entity_id,
            error=str(e),
            exc_info=True
        )
        # Try to update status if we can
        try:
            service.update_status(
                entity_id,
                YourStatus.FAILED,
                error_message=f"Processing failed: {str(e)}"
            )
        except:
            pass  # Don't mask the original exception
        return {"success": False, "error": str(e)}
    
    finally:
        db.close()  # ✅ ALWAYS close the session
```

---

## Integration

### Step 1: Triggering Tasks from API Endpoints

Use HTTP 202 Accepted for async processing. Create the database record first, then queue the task.

```python
from fastapi import APIRouter, Depends, HTTPException, status
from celery.exceptions import CeleryError

from src.tasks.your_tasks import process_your_feature
from src.services.your_service import YourService

router = APIRouter(prefix="/v1/your-feature", tags=["Your Feature"])

@router.post(
    "/",
    response_model=YourSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,  # 202 for async processing
)
async def submit_request(
    request: YourSubmitRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("your-feature:write"))
):
    """Submit a request for async processing."""
    service = YourService(db)
    
    # 1. Create database record with PENDING status
    entity = service.create_entity(
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        **request.dict()
    )
    
    # 2. Queue the Celery task
    try:
        async_result = process_your_feature.delay(
            entity_id=entity.entity_id,
            user_id=current_user.user_id,
            customer_id=current_user.customer_id
        )
    except CeleryError as celery_error:
        # Handle broker unavailable
        logger.error(
            "task_enqueue_failed",
            entity_id=entity.entity_id,
            error=str(celery_error)
        )
        service.update_status(
            entity.entity_id,
            YourStatus.FAILED,
            error_message="Background workers unavailable"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to queue task for processing"
        )
    
    # 3. Return immediately with entity ID
    return YourSubmitResponse(
        entity_id=entity.entity_id,
        status=entity.status,
        message="Request submitted and is being processed",
        task_id=async_result.id
    )
```

### Step 2: Container Deployment

After modifying Celery tasks, you MUST rebuild the celery-worker container:

```bash
# ✅ CORRECT: Rebuild AND restart
docker-compose build celery-worker
docker-compose up -d celery-worker

# ❌ WRONG: Restart uses old image!
docker-compose restart celery-worker
```

---

## File Locations

```
src/
├── celery_app.py                # Celery application configuration
├── tasks/
│   └── your_tasks.py            # Celery task definitions
├── models/
│   ├── database.py              # SessionLocal, init_database, BaseModel
│   └── your_model.py            # SQLAlchemy models and status enums
├── services/
│   └── your_service.py          # Business logic layer
└── core/
    └── logging.py               # Structured logging (get_logger, bind_context)
```

---

## Testing

### Unit Tests

```python
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.tasks.your_tasks import process_your_feature


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    return db


@pytest.fixture
def mock_service(mock_db):
    """Create a mock service."""
    with patch('src.tasks.your_tasks.YourService') as MockService:
        service = Mock()
        MockService.return_value = service
        yield service


def test_task_success(mock_db, mock_service):
    """Test successful task execution."""
    # Setup
    mock_entity = Mock(status='pending', error_message=None)
    mock_service.get_entity.return_value = mock_entity
    mock_service.do_processing.return_value = Mock(error=None, id='result-123')
    
    with patch('src.tasks.your_tasks.database') as mock_database:
        mock_database.SessionLocal.return_value = mock_db
        
        # Execute
        result = process_your_feature(
            'entity-123', 1, 'customer-123'
        )
    
    # Assert
    assert result['success'] is True
    assert result['entity_id'] == 'entity-123'
    mock_service.update_status.assert_called()
    mock_db.close.assert_called_once()


def test_task_entity_not_found(mock_db, mock_service):
    """Test task when entity doesn't exist."""
    mock_service.get_entity.return_value = None
    
    with patch('src.tasks.your_tasks.database') as mock_database:
        mock_database.SessionLocal.return_value = mock_db
        
        result = process_your_feature(
            'nonexistent', 1, 'customer-123'
        )
    
    assert result['success'] is False
    assert 'not found' in result['error'].lower()
```

### Integration Tests

```python
@pytest.mark.integration
def test_task_integration():
    """Test task with real database and Celery."""
    from src.tasks.your_tasks import process_your_feature
    
    # Create test entity in database
    # ...
    
    # Run task synchronously for testing
    result = process_your_feature.apply(
        args=['test-entity-id', 1, 'test-customer']
    ).get(timeout=30)
    
    assert result['success'] is True
```

---

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| `SessionLocal is None` | Use module import: `from src.models import database` |
| Task silently fails | Check Celery logs: `docker-compose logs celery-worker` |
| Task arguments not passed | Ensure all args are JSON-serializable primitives |
| Database connection errors | Always check & init in task, use try/finally |
| Tasks not retrying | Inherit from custom Task class with retry config |
| Changes not taking effect | Rebuild container: `docker-compose build celery-worker` |

---

## Checklist

- [ ] Task uses module-level database import
- [ ] SessionLocal check and initialization present
- [ ] All arguments are serializable (str, int, dict, list)
- [ ] Status updates at each stage (pending → processing → completed/failed)
- [ ] Error handling with proper status updates
- [ ] Timeout handling for long-running tasks
- [ ] Logging at key state transitions
- [ ] try/finally ensures db.close()
- [ ] Unit tests written
- [ ] Container rebuilt: `docker-compose build celery-worker`

---

## References

- `src/celery_app.py` — Celery application configuration
- `src/models/database.py` — Database session management (SessionLocal, init_database)
- `src/tasks/` — Existing Celery task implementations
- `src/core/logging.py` — Structured logging utilities
- `skills/fastapi-endpoints/` — API endpoint patterns for triggering tasks
- [Celery Documentation](https://docs.celeryq.dev/) — Official Celery docs
