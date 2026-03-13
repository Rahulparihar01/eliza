"""
AI Enablement Platform - Enhanced Logging System

Implements structured logging with:
- Context propagation (request_id, user_id, task_id, etc.)
- Operation timing and tracking
- ELK stack integration (Logstash)
- Development and production formatters
- Celery task logging support
"""

import logging
import logging.handlers
import sys
import json
import uuid
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum
from contextvars import ContextVar
from pathlib import Path


# ============================================================================
# Context Variables for Request/Task Tracking
# ============================================================================

request_id_context: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_context: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
session_id_context: ContextVar[Optional[str]] = ContextVar('session_id', default=None)
trace_id_context: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)
task_id_context: ContextVar[Optional[str]] = ContextVar('task_id', default=None)
document_id_context: ContextVar[Optional[str]] = ContextVar('document_id', default=None)
customer_id_context: ContextVar[Optional[str]] = ContextVar('customer_id', default=None)


# ============================================================================
# Enums
# ============================================================================

class LogLevel(str, Enum):
    """Standard log levels"""
    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(str, Enum):
    """Log categories for filtering and routing"""
    SYSTEM = "system"
    SECURITY = "security"
    PERFORMANCE = "performance"
    BUSINESS = "business"
    USER_ACTION = "user_action"
    DATA_PROCESSING = "data_processing"
    API = "api"
    INTEGRATION = "integration"
    QA_RAG = "qa_rag"
    CHUNKING = "chunking"
    INGESTION = "ingestion"
    ANALYSIS = "analysis"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class LogContext:
    """Contextual information for log entries"""
    request_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    task_id: Optional[str] = None
    document_id: Optional[str] = None
    customer_id: Optional[str] = None
    component: Optional[str] = None
    operation: Optional[str] = None
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary, excluding None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}
    
    @classmethod
    def from_context_vars(cls, component: str = None, operation: str = None) -> 'LogContext':
        """Create from current context variables"""
        return cls(
            request_id=request_id_context.get(),
            user_id=user_id_context.get(),
            session_id=session_id_context.get(),
            trace_id=trace_id_context.get(),
            task_id=task_id_context.get(),
            document_id=document_id_context.get(),
            customer_id=customer_id_context.get(),
            component=component,
            operation=operation
        )


@dataclass
class LogEntry:
    """Structured log entry format"""
    timestamp: str
    level: str
    category: str
    message: str
    component: str
    operation: str = ""
    
    # Context information
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Performance metrics
    duration_ms: Optional[float] = None
    memory_mb: Optional[float] = None
    
    # Error information
    error_type: Optional[str] = None
    error_code: Optional[str] = None
    stack_trace: Optional[str] = None
    
    # Business metrics
    items_processed: Optional[int] = None
    success_count: Optional[int] = None
    error_count: Optional[int] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # User-friendly information
    user_message: Optional[str] = None
    user_action: Optional[str] = None
    progress_percent: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {k: v for k, v in asdict(self).items() if v is not None and v != {} and v != ""}
    
    def to_json(self) -> str:
        """Convert to JSON string for structured logging"""
        return json.dumps(self.to_dict(), default=str, separators=(',', ':'))
    
    def to_human_readable(self) -> str:
        """Convert to human-readable format for console output"""
        level_icon = self._get_level_icon()
        component_str = f"[{self.component}]" if self.component else ""
        operation_str = f"({self.operation})" if self.operation else ""
        
        base_message = f"{self.timestamp} {level_icon} {component_str}{operation_str} {self.message}"
        
        # Add performance info if available
        if self.duration_ms is not None:
            base_message += f" [took: {self.duration_ms:.2f}ms]"
        
        # Add progress if available
        if self.progress_percent is not None:
            base_message += f" [progress: {self.progress_percent:.1f}%]"
        
        # Add items processed if available
        if self.items_processed is not None:
            base_message += f" [items: {self.items_processed}]"
        
        return base_message
    
    def _get_level_icon(self) -> str:
        """Get emoji icon for log level"""
        icons = {
            "TRACE": "🔍",
            "DEBUG": "🐛",
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🚨"
        }
        return icons.get(self.level, "📝")


# ============================================================================
# Formatters
# ============================================================================

class JSONFormatter(logging.Formatter):
    """Formatter for structured JSON output (production)"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        if isinstance(record.msg, LogEntry):
            return record.msg.to_json()
        
        # Fallback for non-structured logs
        log_entry = LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=record.levelname,
            category=LogCategory.SYSTEM.value,
            message=record.getMessage(),
            component=record.name
        )
        
        # Add exception info if present
        if record.exc_info:
            log_entry.stack_trace = self.formatException(record.exc_info)
            log_entry.error_type = record.exc_info[0].__name__ if record.exc_info[0] else None
        
        return log_entry.to_json()


class HumanReadableFormatter(logging.Formatter):
    """Formatter for human-readable console output (development)"""
    
    # ANSI color codes
    COLORS = {
        'TRACE': '\033[36m',      # Cyan
        'DEBUG': '\033[34m',      # Blue
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors and human-readable format"""
        if isinstance(record.msg, LogEntry):
            formatted = record.msg.to_human_readable()
            
            # Apply color to the level icon in the message
            color = self.COLORS.get(record.msg.level, self.RESET)
            formatted = formatted.replace(record.msg._get_level_icon(), f"{color}{record.msg._get_level_icon()}{self.RESET}", 1)
            
            # Add exception if present
            if record.exc_info:
                formatted += f"\n{self.formatException(record.exc_info)}"
            
            return formatted
        
        # Fallback for non-structured logs
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        formatted = f"{timestamp} {color}{record.levelname:8}{self.RESET} [{record.name:20}] {record.getMessage()}"
        
        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"
        
        return formatted


# ============================================================================
# Enhanced Logger
# ============================================================================

class EnhancedLogger:
    """Enhanced logger with structured logging and context management"""
    
    def __init__(self, name: str, component: Optional[str] = None, **default_context):
        self.name = name
        self.component = component or name
        self.default_context = default_context
        self.logger = logging.getLogger(name)
        
        # Track active operations
        self._operations: Dict[str, Dict[str, Any]] = {}
    
    def _create_log_entry(
        self,
        level: str,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        operation: str = "",
        **kwargs
    ) -> LogEntry:
        """Create structured log entry with context"""
        
        # Get context from context variables
        log_context = LogContext.from_context_vars(
            component=self.component,
            operation=operation
        )
        
        # Merge with default context
        context_dict = log_context.to_dict()
        context_dict.update(self.default_context)
        
        # Add any additional context from kwargs
        extra_context = kwargs.pop('context', {})
        context_dict.update(extra_context)
        
        # Define known LogEntry fields to extract from kwargs
        known_fields = {
            'duration_ms', 'memory_mb', 'error_type', 'error_code', 'stack_trace',
            'items_processed', 'success_count', 'error_count', 'metadata',
            'user_message', 'user_action', 'progress_percent'
        }
        
        # Separate known fields from unknown fields
        log_entry_kwargs = {}
        metadata = kwargs.pop('metadata', {})
        
        for key in list(kwargs.keys()):
            if key in known_fields:
                log_entry_kwargs[key] = kwargs.pop(key)
            else:
                # Put unknown fields into metadata
                metadata[key] = kwargs.pop(key)
        
        # Merge metadata
        if 'metadata' in log_entry_kwargs:
            log_entry_kwargs['metadata'].update(metadata)
        else:
            log_entry_kwargs['metadata'] = metadata
        
        return LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level,
            category=category.value if isinstance(category, LogCategory) else category,
            message=message,
            component=self.component,
            operation=operation,
            context=context_dict,
            **log_entry_kwargs
        )
    
    def trace(self, message: str, **kwargs):
        """Log trace level message"""
        entry = self._create_log_entry(LogLevel.TRACE.value, message, **kwargs)
        self.logger.debug(entry)  # Map to DEBUG since TRACE doesn't exist in standard logging
    
    def debug(self, message: str, **kwargs):
        """Log debug level message"""
        entry = self._create_log_entry(LogLevel.DEBUG.value, message, **kwargs)
        self.logger.debug(entry)
    
    def info(self, message: str, **kwargs):
        """Log info level message"""
        entry = self._create_log_entry(LogLevel.INFO.value, message, **kwargs)
        self.logger.info(entry)
    
    def warning(self, message: str, **kwargs):
        """Log warning level message"""
        entry = self._create_log_entry(LogLevel.WARNING.value, message, **kwargs)
        self.logger.warning(entry)
    
    def error(self, message: str, exception: Exception = None, **kwargs):
        """Log error level message"""
        # Extract exc_info before passing to LogEntry
        exc_info = exception if exception else kwargs.pop('exc_info', False)
        
        entry = self._create_log_entry(LogLevel.ERROR.value, message, **kwargs)
        
        # Add exception info
        if exception:
            entry.error_type = type(exception).__name__
            entry.error_code = getattr(exception, 'code', None)
        
        # Pass exc_info to logger
        self.logger.error(entry, exc_info=exc_info)
    
    def critical(self, message: str, exception: Exception = None, **kwargs):
        """Log critical level message"""
        # Extract exc_info before passing to LogEntry
        exc_info = exception if exception else kwargs.pop('exc_info', False)
        
        entry = self._create_log_entry(LogLevel.CRITICAL.value, message, **kwargs)
        
        # Add exception info
        if exception:
            entry.error_type = type(exception).__name__
            entry.error_code = getattr(exception, 'code', None)
        
        # Pass exc_info to logger
        self.logger.critical(entry, exc_info=exc_info)
    
    def start_operation(
        self,
        operation_name: str,
        category: LogCategory = LogCategory.PERFORMANCE,
        **kwargs
    ) -> str:
        """Start timing an operation and return operation ID"""
        operation_id = f"{operation_name}_{uuid.uuid4().hex[:8]}"
        
        self._operations[operation_id] = {
            'name': operation_name,
            'start_time': time.time(),
            'category': category
        }
        
        # Merge operation_id into existing metadata if present
        metadata = kwargs.pop('metadata', {})
        metadata['operation_id'] = operation_id
        
        self.info(
            f"Starting operation: {operation_name}",
            category=category,
            operation=operation_name,
            metadata=metadata,
            user_message=kwargs.pop('user_message', f"Starting {operation_name}..."),
            **kwargs
        )
        
        return operation_id
    
    def end_operation(
        self,
        operation_id: str,
        success: bool = True,
        items_processed: Optional[int] = None,
        **kwargs
    ):
        """End timing an operation"""
        if operation_id not in self._operations:
            self.warning(f"Operation timer not found: {operation_id}")
            return
        
        op_info = self._operations.pop(operation_id)
        operation_name = op_info['name']
        duration_ms = (time.time() - op_info['start_time']) * 1000
        category = op_info['category']
        
        status = "completed" if success else "failed"
        log_method = self.info if success else self.error
        
        # Merge operation_id into existing metadata if present
        metadata = kwargs.pop('metadata', {})
        metadata['operation_id'] = operation_id
        
        log_method(
            f"Operation {status}: {operation_name}",
            category=category,
            operation=operation_name,
            duration_ms=duration_ms,
            items_processed=items_processed,
            metadata=metadata,
            user_message=kwargs.pop('user_message', f"{operation_name} {status}" + (f" ({items_processed} items)" if items_processed else "")),
            **kwargs
        )
    
    def log_user_action(self, action: str, details: Dict[str, Any] = None, **kwargs):
        """Log user action for analytics and debugging"""
        self.info(
            f"User action: {action}",
            category=LogCategory.USER_ACTION,
            operation=action,
            user_action=action,
            metadata=details or {},
            user_message=f"Action: {action}",
            **kwargs
        )
    
    def log_business_metric(
        self,
        metric_name: str,
        value: Any,
        unit: str = "",
        **kwargs
    ):
        """Log business metrics"""
        message = f"Metric {metric_name}: {value}"
        if unit:
            message += f" {unit}"
        
        self.info(
            message,
            category=LogCategory.BUSINESS,
            operation="metric_collection",
            metadata={
                "metric_name": metric_name,
                "metric_value": value,
                "metric_unit": unit
            },
            **kwargs
        )


# ============================================================================
# Context Management Functions
# ============================================================================

def bind_context(**context_values) -> Dict[str, Any]:
    """
    Bind context values to current execution context.
    
    Returns tokens that can be used to reset the context.
    
    Example:
        tokens = bind_context(request_id="abc123", user_id="user@example.com")
        try:
            # ... your code ...
        finally:
            reset_context(tokens)
    """
    context_vars_map = {
        'request_id': request_id_context,
        'user_id': user_id_context,
        'session_id': session_id_context,
        'trace_id': trace_id_context,
        'task_id': task_id_context,
        'document_id': document_id_context,
        'customer_id': customer_id_context,
    }
    
    tokens = {}
    for key, value in context_values.items():
        if key in context_vars_map and value is not None:
            tokens[key] = context_vars_map[key].set(str(value))
    
    return tokens


def reset_context(tokens: Dict[str, Any]):
    """Reset context variables using tokens from bind_context"""
    context_vars_map = {
        'request_id': request_id_context,
        'user_id': user_id_context,
        'session_id': session_id_context,
        'trace_id': trace_id_context,
        'task_id': task_id_context,
        'document_id': document_id_context,
        'customer_id': customer_id_context,
    }
    
    # Reset in reverse order
    for key in reversed(list(tokens.keys())):
        if key in context_vars_map:
            context_vars_map[key].reset(tokens[key])


# ============================================================================
# Setup Functions
# ============================================================================

def setup_logging(settings) -> None:
    """
    Set up logging configuration with handlers for console, file, and optionally Logstash.
    
    Args:
        settings: Settings object with logging configuration
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Determine if we're in development mode
    is_development = settings.environment.lower() == "development"
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))
    
    if is_development:
        # Use human-readable formatter for development
        console_handler.setFormatter(HumanReadableFormatter())
    else:
        # Use JSON formatter for production
        console_handler.setFormatter(JSONFormatter())
    
    root_logger.addHandler(console_handler)
    
    # File handler (if enabled)
    if settings.log_to_file:
        log_dir = Path(settings.logs_path) / settings.customer_id
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "app.log"
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, settings.log_level.upper()))
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)
    
    # Logstash handler (if enabled) for ELK stack integration
    if settings.logstash_enabled:
        try:
            import logstash
            
            logstash_handler = logstash.TCPLogstashHandler(
                host=settings.logstash_host,
                port=settings.logstash_port,
                version=1,
                message_type='python-logstash',
                tags=['ai-platform', settings.environment, settings.customer_id]
            )
            logstash_handler.setLevel(getattr(logging, settings.log_level.upper()))
            root_logger.addHandler(logstash_handler)
            
            logger = logging.getLogger(__name__)
            logger.info(f"✅ Logstash handler enabled: {settings.logstash_host}:{settings.logstash_port}")
        except ImportError:
            logger = logging.getLogger(__name__)
            logger.warning("⚠️ python-logstash not installed, skipping Logstash handler")
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"❌ Failed to setup Logstash handler: {e}")
    
    # Configure third-party loggers
    configure_third_party_loggers()
    
    # Log the logging setup
    logger = get_logger(__name__)
    logger.info(
        f"Logging configured - Level: {settings.log_level}, Environment: {settings.environment}",
        category=LogCategory.SYSTEM,
        metadata={
            'log_level': settings.log_level,
            'environment': settings.environment,
            'logstash_enabled': settings.logstash_enabled,
            'log_to_file': settings.log_to_file
        }
    )


def configure_third_party_loggers() -> None:
    """Configure third-party library loggers to reduce noise"""
    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    
    # Keep important logs at INFO level
    logging.getLogger("crewai").setLevel(logging.INFO)
    logging.getLogger("langchain").setLevel(logging.INFO)


def get_logger(name: str, component: Optional[str] = None, **default_context) -> EnhancedLogger:
    """
    Get an enhanced logger with structured logging capabilities.
    
    Args:
        name: Logger name (usually __name__)
        component: Optional component name for grouping
        **default_context: Default context to include in all logs
    
    Returns:
        EnhancedLogger instance
    
    Example:
        logger = get_logger(__name__, component="documents.processor")
        logger.info("Processing document", document_id=doc.id)
        
        # With operation tracking
        op_id = logger.start_operation("extract_text")
        # ... do work ...
        logger.end_operation(op_id, success=True, items_processed=100)
    """
    return EnhancedLogger(name, component=component, **default_context)


# ============================================================================
# Convenience Functions
# ============================================================================

def log_request(method: str, path: str, status_code: int, duration_ms: float, **kwargs):
    """Convenience function to log HTTP requests"""
    logger = get_logger("http")
    level_method = logger.info if 200 <= status_code < 400 else logger.error
    
    level_method(
        f"{method} {path} -> {status_code}",
        category=LogCategory.API,
        operation="http_request",
        duration_ms=duration_ms,
        metadata={
            'method': method,
            'path': path,
            'status_code': status_code
        },
        **kwargs
    )


def log_task_start(task_name: str, task_id: str, **kwargs):
    """Convenience function to log Celery task start"""
    logger = get_logger("celery")
    logger.info(
        f"Task started: {task_name}",
        category=LogCategory.PERFORMANCE,
        operation=task_name,
        metadata={'task_id': task_id, 'task_name': task_name},
        **kwargs
    )


def log_task_end(task_name: str, task_id: str, success: bool, duration_ms: float, **kwargs):
    """Convenience function to log Celery task end"""
    logger = get_logger("celery")
    level_method = logger.info if success else logger.error
    
    level_method(
        f"Task {'completed' if success else 'failed'}: {task_name}",
        category=LogCategory.PERFORMANCE,
        operation=task_name,
        duration_ms=duration_ms,
        metadata={'task_id': task_id, 'task_name': task_name, 'success': success},
        **kwargs
    )
