"""
Celery application configuration for document processing.
Optimized for mixed I/O and CPU workloads.
"""
import os
from typing import Any, Dict, Optional

from celery import Celery, signals

from src.applets.registry import get_enabled_task_modules
from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory

settings = get_settings()
logger = get_logger(__name__)
_task_trace_handles: Dict[str, Dict[str, Any]] = {}

ALL_TASK_MODULES = [
    "src.tasks.documents",
    "src.tasks.business_intelligence_tasks",
    "src.tasks.ingestion_tasks",
    "src.tasks.talent_tasks",
    "src.tasks.data_analyst_tasks",
    "src.tasks.adoption_sync_tasks",
    "src.tasks.rag_eval_tasks",
    "src.tasks.gepa_optimizer_tasks",
    "src.tasks.retrieval_tasks",
    "src.tasks.content_writer_tasks",
    "src.tasks.ragflow_tasks",
    "src.tasks.ragflow_source_sync_tasks",
]


def _summarize_for_trace(value: Any, *, max_length: int = 800, depth: int = 0) -> Any:
    """Convert arbitrary task inputs into compact trace-safe payloads."""
    if depth > 3:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= max_length else f"{value[:max_length]}...[truncated]"
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if isinstance(value, (list, tuple)):
        return [_summarize_for_trace(item, max_length=max_length, depth=depth + 1) for item in value[:20]]
    if isinstance(value, dict):
        summarized: Dict[str, Any] = {}
        for key in list(value.keys())[:30]:
            summarized[str(key)] = _summarize_for_trace(
                value[key],
                max_length=max_length,
                depth=depth + 1,
            )
        return summarized
    return str(value)


def _extract_retrieval_query(task_kwargs: Dict[str, Any], args: Any) -> Optional[str]:
    """Return the retrieval query from kwargs/args when available."""
    query = task_kwargs.get("query")
    if isinstance(query, str) and query.strip():
        return query.strip()
    if args and len(args) >= 2 and isinstance(args[1], str) and args[1].strip():
        return args[1].strip()
    return None

enabled_task_modules = get_enabled_task_modules(os.getenv("APPLETS"))
if enabled_task_modules is None:
    task_modules = ALL_TASK_MODULES
else:
    task_modules = []
    for task_name in enabled_task_modules:
        if task_name.startswith("src.tasks."):
            task_modules.append(task_name)
        else:
            task_modules.append(f"src.tasks.{task_name}")
    if not task_modules:
        logger.warning(
            "No task modules resolved for selected applets; worker will start with no applet-specific tasks.",
            category=LogCategory.SYSTEM,
            metadata={"applets": os.getenv("APPLETS", "all")},
        )

celery_app = Celery(
    "eliza",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=task_modules,
)

beat_schedule = {}

if settings.rag_kb_s3_sync_enabled and "src.tasks.ragflow_source_sync_tasks" in task_modules:
    beat_schedule["ragflow-s3-kb-sync-dispatch"] = {
        "task": "ragflow.schedule_s3_kb_syncs",
        "schedule": max(30, int(settings.rag_kb_s3_sync_interval_seconds)),
        "options": {"queue": "rag_ingestion"},
    }

celery_app.conf.update(
    # Serialization (security: never use pickle)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    
    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Use Redis-backed dynamic scheduler so tenant schedule changes apply
    # without restarting celery-beat.
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.celery_broker_url,
    redbeat_key_prefix="eliza-beat:",
    
    # Task execution
    task_track_started=True,
    task_acks_late=True,              # Only acknowledge after completion
    worker_prefetch_multiplier=1,      # Fetch one task at a time
    worker_max_tasks_per_child=100,    # Restart worker after 100 tasks
    
    # Result backend
    task_ignore_result=False,          # Keep results for debugging
    result_expires=259200,             # 72 hour TTL (3 days)
    result_backend_transport_options={
        'socket_keepalive': True,
        'socket_connect_timeout': 5,
        'retry_on_timeout': True,
    },
    
    # Retry configuration
    task_autoretry_for=(Exception,),
    task_retry_kwargs={'max_retries': 3},
    task_default_retry_delay=120,     # 2 minutes between retries
    
    # Performance
    worker_disable_rate_limits=True,
    
    # Logging format
    worker_log_format='[%(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
    
    # Queue routing - route tasks to dedicated queues
    task_routes={
        'src.tasks.ingestion_tasks.*': {'queue': 'ingestion'},
        'run_connector_sync': {'queue': 'ingestion'},
        'ragflow.process_s3_document': {'queue': 'rag_ingestion'},
        'ragflow.sync_s3_knowledge_base': {'queue': 'rag_ingestion'},
        'ragflow.schedule_s3_kb_syncs': {'queue': 'rag_ingestion'},
    },
    task_default_queue='celery',  # Default queue for other tasks
    
    # Beat schedule for periodic tasks
    beat_schedule=beat_schedule,
)

# Task lifecycle logging for metrics
@signals.task_prerun.connect
def task_prerun_handler(
    sender=None,
    task_id: Optional[str] = None,
    task=None,
    args=None,
    kwargs: Optional[Dict[str, Any]] = None,
    **signal_kwargs,
):
    task_name = getattr(task, "name", None) or getattr(sender, "name", "unknown_task")
    task_kwargs = kwargs or {}
    logger.info(
        "task_started",
        category=LogCategory.PERFORMANCE,
        metadata={
            "task_id": task_id,
            "task_name": task_name,
            "task_args": str(args),
            "task_kwargs": str(task_kwargs),
        }
    )
    try:
        from src.services.langfuse_service import get_langfuse_service

        langfuse_service = get_langfuse_service()
        if langfuse_service.enabled and task_id:
            customer_id = (
                task_kwargs.get("customer_id")
                or (args[0] if args and isinstance(args[0], str) else None)
            )
            session_id = (
                task_kwargs.get("analysis_id")
                or task_kwargs.get("run_id")
                or task_kwargs.get("message_id")
                or task_kwargs.get("question_id")
                or task_kwargs.get("conversation_id")
            )
            user_id = task_kwargs.get("user_id")
            is_retrieval_task = task_name == "run_retrieval"
            trace_name = "agentmesh" if is_retrieval_task else f"celery:{task_name}"
            query = _extract_retrieval_query(task_kwargs, args)
            trace_input: Any
            if is_retrieval_task and query:
                trace_input = query
            else:
                trace_input = {
                    "args": _summarize_for_trace(args or ()),
                    "kwargs": _summarize_for_trace(task_kwargs),
                }
            trace_handle = langfuse_service.begin_trace_scope(
                name=trace_name,
                input_data=trace_input,
                metadata={
                    "component": "celery",
                    "task_id": task_id,
                    "task_name": task_name,
                    "trace_name": trace_name,
                    "customer_id": customer_id,
                    "session_id": session_id,
                    "user_id": user_id,
                },
                session_id=str(session_id) if session_id is not None else None,
                user_id=str(user_id) if user_id is not None else None,
            )
            trace_handle["task_name"] = task_name
            _task_trace_handles[task_id] = trace_handle
    except Exception as exc:
        logger.warning(
            "langfuse_task_trace_start_failed",
            category=LogCategory.PERFORMANCE,
            metadata={"task_id": task_id, "task_name": task_name, "error": str(exc)},
        )

@signals.task_postrun.connect
def task_postrun_handler(
    sender=None,
    task_id: Optional[str] = None,
    task=None,
    state: Optional[str] = None,
    retval: Any = None,
    **signal_kwargs,
):
    task_name = getattr(task, "name", None) or getattr(sender, "name", "unknown_task")
    logger.info(
        "task_finished",
        category=LogCategory.PERFORMANCE,
        metadata={
            "task_id": task_id,
            "task_name": task_name,
            "state": state,
            "runtime": signal_kwargs.get("runtime"),
        }
    )
    try:
        from src.services.langfuse_service import get_langfuse_service

        if task_id and task_id in _task_trace_handles:
            trace_handle = _task_trace_handles.pop(task_id, None)
            output_data: Any = {
                "state": state,
                "result": _summarize_for_trace(retval),
            }
            if task_name == "run_retrieval":
                if isinstance(retval, dict):
                    output_data = _summarize_for_trace(retval)
                elif retval is None:
                    output_data = {"status": state}
                else:
                    output_data = {
                        "status": state,
                        "result": _summarize_for_trace(retval),
                    }
            get_langfuse_service().end_trace_scope(
                trace_handle,
                output_data=output_data,
                metadata={"task_id": task_id, "task_name": task_name},
            )
    except Exception as exc:
        logger.warning(
            "langfuse_task_trace_finish_failed",
            category=LogCategory.PERFORMANCE,
            metadata={"task_id": task_id, "task_name": task_name, "error": str(exc)},
        )

@signals.task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **signal_kwargs):
    task_name = getattr(sender, "name", "unknown_task")
    logger.error(
        "task_failed",
        exception=exception,
        category=LogCategory.PERFORMANCE,
        metadata={
            "task_id": task_id,
            "task_name": task_name,
            "traceback": signal_kwargs.get("traceback"),
        }
    )
    try:
        from src.services.langfuse_service import get_langfuse_service

        if task_id and task_id in _task_trace_handles:
            trace_handle = _task_trace_handles.pop(task_id, None)
            failure_output: Optional[Dict[str, Any]] = None
            if task_name == "run_retrieval":
                failure_output = {
                    "status": "failed",
                    "error": str(exception) if exception is not None else "task_failure",
                }
            get_langfuse_service().end_trace_scope(
                trace_handle,
                output_data=failure_output,
                metadata={"task_id": task_id, "task_name": task_name},
                error=exception,
            )
    except Exception as exc:
        logger.warning(
            "langfuse_task_trace_failure_finalize_failed",
            category=LogCategory.PERFORMANCE,
            metadata={"task_id": task_id, "task_name": task_name, "error": str(exc)},
        )
