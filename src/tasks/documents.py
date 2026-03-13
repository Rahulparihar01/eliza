"""
Celery tasks for document processing.

These tasks are executed by Celery workers and handle:
- Document text extraction
- Content chunking
- Embedding generation
- Quality scoring
"""

import time
from celery import Task

from src.celery_app import celery_app
from src.services.document_processor import DocumentProcessor
from src.models import DocumentStatus
# Import SessionLocal dynamically in functions to avoid None at import time
from src.core.logging import get_logger, bind_context, reset_context, LogCategory

logger = get_logger(__name__, component="tasks.documents")


class DocumentProcessingTask(Task):
    """
    Base task class for document processing with automatic resource management.
    
    Features:
    - Automatic retry on failure (configured in celery_app)
    - Lazy initialization of processor
    - Resource cleanup on worker shutdown
    """
    
    _processor = None
    
    @property
    def processor(self) -> DocumentProcessor:
        """Lazy load processor instance (shared across tasks in same worker)"""
        if self._processor is None:
            self._processor = DocumentProcessor()
        return self._processor


@celery_app.task(
    base=DocumentProcessingTask,
    name='tasks.process_document',
    bind=True,
    max_retries=3,
    default_retry_delay=120,  # 2 minutes between retries
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,  # Max 10 minutes
    retry_jitter=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_document_task(self: DocumentProcessingTask, document_id: int, force: bool = False) -> dict:
    """
    Process a document asynchronously via Celery.
    
    This task:
    1. Extracts text from the uploaded document
    2. Chunks the content using the specified strategy
    3. Generates embeddings for each chunk
    4. Calculates quality metrics
    5. Updates document status
    
    Args:
        document_id: ID of the document to process
        force: If True, reprocess even if already completed
    
    Returns:
        dict: Task result with document_id and status
        
    Raises:
        Exception: Any processing errors (will trigger retry)
    """
    start_time = time.time()
    
    # Bind context for task execution
    context_tokens = bind_context(
        task_id=self.request.id,
        document_id=str(document_id)
    )
    
    try:
        # Start operation tracking
        op_id = logger.start_operation(
            "document_processing",
            category=LogCategory.DATA_PROCESSING,
            user_message=f"Processing document {document_id}...",
            metadata={
                'document_id': document_id,
                'force': force,
                'retry_count': self.request.retries
            }
        )
        
        # Process the document
        self.processor.process_document_sync(document_id, force=force)
        
        # End operation tracking
        duration_ms = (time.time() - start_time) * 1000
        logger.end_operation(
            op_id,
            success=True,
            items_processed=1,
            user_message=f"Document {document_id} processed successfully"
        )
        
        result = {
            'task_id': self.request.id,
            'document_id': document_id,
            'status': 'completed',
            'retry_count': self.request.retries,
            'duration_ms': duration_ms
        }
        
        return result
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        
        logger.error(
            f"Document {document_id} processing failed",
            exception=e,
            category=LogCategory.DATA_PROCESSING,
            operation="document_processing",
            duration_ms=duration_ms,
            error_type=type(e).__name__,
            metadata={
                'document_id': document_id,
                'retry_count': self.request.retries,
                'max_retries': self.max_retries
            },
            user_message=f"Failed to process document {document_id}: {str(e)}"
        )
        
        # Update document status to failed if max retries exceeded
        if self.request.retries >= self.max_retries:
            logger.critical(
                f"Max retries exceeded for document {document_id}",
                category=LogCategory.DATA_PROCESSING,
                metadata={'document_id': document_id}
            )
            _mark_document_failed(document_id, str(e))
        
        # Re-raise to trigger Celery retry mechanism
        raise
    
    finally:
        # Always reset context
        reset_context(context_tokens)


@celery_app.task(
    base=DocumentProcessingTask,
    name='tasks.retry_failed_document',
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    acks_late=True,
    reject_on_worker_lost=True,
)
def retry_failed_document_task(self: DocumentProcessingTask, document_id: int) -> dict:
    """
    Retry processing a previously failed document.
    
    This task resets the document status to UPLOADED and reprocesses it.
    Used when users click the retry button in the UI.
    
    Args:
        document_id: ID of the failed document to retry
    
    Returns:
        dict: Task result with document_id and status
        
    Raises:
        Exception: Any processing errors (will trigger retry)
    """
    start_time = time.time()
    
    # Bind context for task execution
    context_tokens = bind_context(
        task_id=self.request.id,
        document_id=str(document_id)
    )
    
    try:
        logger.info(
            f"Retrying failed document {document_id}",
            category=LogCategory.DATA_PROCESSING,
            operation="document_retry",
            user_message=f"Retrying document {document_id}..."
        )
        
        # Reset document status to UPLOADED before reprocessing
        _reset_document_status(document_id)
        
        # Process with force=True to bypass idempotency check
        self.processor.process_document_sync(document_id, force=True)
        
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info(
            f"Document {document_id} retry successful",
            category=LogCategory.DATA_PROCESSING,
            operation="document_retry",
            duration_ms=duration_ms,
            user_message=f"Document {document_id} retry completed successfully"
        )
        
        result = {
            'task_id': self.request.id,
            'document_id': document_id,
            'status': 'completed',
            'retry_count': self.request.retries,
            'duration_ms': duration_ms
        }
        
        return result
        
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        
        logger.error(
            f"Document {document_id} retry failed",
            exception=e,
            category=LogCategory.DATA_PROCESSING,
            operation="document_retry",
            duration_ms=duration_ms,
            error_type=type(e).__name__,
            metadata={'document_id': document_id, 'retry_count': self.request.retries}
        )
        
        # Update document status to failed if max retries exceeded
        if self.request.retries >= self.max_retries:
            logger.critical(
                f"Max retries exceeded for document {document_id} retry",
                category=LogCategory.DATA_PROCESSING,
                metadata={'document_id': document_id}
            )
            _mark_document_failed(document_id, str(e))
        
        # Re-raise to trigger Celery retry mechanism
        raise
    
    finally:
        # Always reset context
        reset_context(context_tokens)


# ============================================================================
# Helper Functions
# ============================================================================

def _reset_document_status(document_id: int):
    """Reset document status to UPLOADED for retry"""
    from src.models import Document
    from src.models.database import SessionLocal
    
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.status = DocumentStatus.UPLOADED
            document.processing_error = None
            document.processing_started_at = None
            document.processing_completed_at = None
            db.commit()
            
            logger.info(
                f"Reset document {document_id} status to UPLOADED",
                category=LogCategory.DATA_PROCESSING,
                operation="reset_status",
                metadata={'document_id': document_id}
            )
    except Exception as e:
        logger.error(
            f"Failed to reset document {document_id} status",
            exception=e,
            category=LogCategory.DATA_PROCESSING,
            metadata={'document_id': document_id}
        )
        db.rollback()
    finally:
        db.close()


def _mark_document_failed(document_id: int, error_message: str):
    """Mark document as failed in database"""
    from src.models import Document
    from src.models.database import SessionLocal
    from datetime import datetime
    
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.status = DocumentStatus.FAILED
            document.processing_error = f"Max retries exceeded: {error_message}"
            document.processing_completed_at = datetime.utcnow()
            db.commit()
            
            logger.warning(
                f"Marked document {document_id} as FAILED",
                category=LogCategory.DATA_PROCESSING,
                operation="mark_failed",
                metadata={
                    'document_id': document_id,
                    'error_message': error_message
                },
                user_message=f"Document {document_id} processing failed after max retries"
            )
    except Exception as e:
        logger.error(
            f"Failed to mark document {document_id} as failed",
            exception=e,
            category=LogCategory.DATA_PROCESSING,
            metadata={'document_id': document_id}
        )
        db.rollback()
    finally:
        db.close()

