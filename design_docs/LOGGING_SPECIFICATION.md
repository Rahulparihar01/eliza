# Logging Specification for AI Enablement Platform

## Executive Summary

This document defines comprehensive logging standards for the AI Enablement Platform, ensuring excellent observability, debugging capabilities, and clean log presentation for both technical teams and end users. The specification covers structured logging, log levels, formatting, user-facing log interfaces, and monitoring integration.

**Key Principles:**
- **Structured Logging**: Machine-readable JSON format with human-readable fallbacks
- **Contextual Information**: Rich context for debugging and monitoring
- **User-Friendly Presentation**: Clean, actionable logs for end users
- **Performance Awareness**: Efficient logging that doesn't impact system performance
- **Security Conscious**: No sensitive data exposure in logs

---

## 1. Log Format Standards

### 1.1 Structured Log Format
*Building on enterprise logging best practices*

```python
# From structured logging patterns - EXAMPLE
import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid
from contextvars import ContextVar

# Context variables for request tracking
request_id_context: ContextVar[str] = ContextVar('request_id', default='')
user_id_context: ContextVar[str] = ContextVar('user_id', default='')
session_id_context: ContextVar[str] = ContextVar('session_id', default='')

class LogLevel(Enum):
    """Standard log levels with numeric values"""
    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50

class LogCategory(Enum):
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

@dataclass
class LogContext:
    """Contextual information for log entries"""
    request_id: str = ""
    user_id: str = ""
    session_id: str = ""
    component: str = ""
    operation: str = ""
    source_id: str = ""
    document_id: str = ""
    chunk_id: str = ""
    agent_name: str = ""
    flow_name: str = ""
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary, excluding empty values"""
        return {k: v for k, v in asdict(self).items() if v}

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
    
    def to_json(self) -> str:
        """Convert to JSON string for structured logging"""
        return json.dumps(asdict(self), default=str, separators=(',', ':'))
    
    def to_human_readable(self) -> str:
        """Convert to human-readable format for console output"""
        timestamp = self.timestamp
        level_icon = self._get_level_icon()
        component = f"[{self.component}]" if self.component else ""
        operation = f"({self.operation})" if self.operation else ""
        
        base_message = f"{timestamp} {level_icon} {component}{operation} {self.message}"
        
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

class EnhancedLogger:
    """Enhanced logger with structured logging and context management"""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(name)
        self._setup_logger()
        
        # Performance tracking
        self.operation_timers: Dict[str, float] = {}
    
    def _setup_logger(self):
        """Setup logger with appropriate handlers"""
        self.logger.setLevel(logging.DEBUG)
        
        # Console handler for development
        if self.config.get('console_logging', True):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(HumanReadableFormatter())
            self.logger.addHandler(console_handler)
        
        # JSON handler for production
        if self.config.get('json_logging', True):
            json_handler = logging.StreamHandler()
            json_handler.setFormatter(JSONFormatter())
            self.logger.addHandler(json_handler)
    
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
        context = LogContext(
            request_id=request_id_context.get(),
            user_id=user_id_context.get(),
            session_id=session_id_context.get(),
            component=self.name,
            operation=operation
        )
        
        # Add any additional context from kwargs
        context_dict = context.to_dict()
        context_dict.update(kwargs.get('context', {}))
        
        return LogEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level,
            category=category.value,
            message=message,
            component=self.name,
            operation=operation,
            context=context_dict,
            **{k: v for k, v in kwargs.items() if k != 'context'}
        )
    
    def trace(self, message: str, **kwargs):
        """Log trace level message"""
        entry = self._create_log_entry("TRACE", message, **kwargs)
        self.logger.log(LogLevel.TRACE.value, entry)
    
    def debug(self, message: str, **kwargs):
        """Log debug level message"""
        entry = self._create_log_entry("DEBUG", message, **kwargs)
        self.logger.debug(entry)
    
    def info(self, message: str, **kwargs):
        """Log info level message"""
        entry = self._create_log_entry("INFO", message, **kwargs)
        self.logger.info(entry)
    
    def warning(self, message: str, **kwargs):
        """Log warning level message"""
        entry = self._create_log_entry("WARNING", message, **kwargs)
        self.logger.warning(entry)
    
    def error(self, message: str, **kwargs):
        """Log error level message"""
        entry = self._create_log_entry("ERROR", message, **kwargs)
        
        # Add stack trace if exception is available
        if 'exception' in kwargs:
            entry.stack_trace = traceback.format_exc()
            entry.error_type = type(kwargs['exception']).__name__
        
        self.logger.error(entry)
    
    def critical(self, message: str, **kwargs):
        """Log critical level message"""
        entry = self._create_log_entry("CRITICAL", message, **kwargs)
        
        # Add stack trace if exception is available
        if 'exception' in kwargs:
            entry.stack_trace = traceback.format_exc()
            entry.error_type = type(kwargs['exception']).__name__
        
        self.logger.critical(entry)
    
    def start_operation(self, operation_name: str, **kwargs) -> str:
        """Start timing an operation"""
        operation_id = f"{operation_name}_{uuid.uuid4().hex[:8]}"
        self.operation_timers[operation_id] = datetime.now(timezone.utc).timestamp()
        
        self.info(
            f"Starting operation: {operation_name}",
            category=LogCategory.PERFORMANCE,
            operation=operation_name,
            operation_id=operation_id,
            user_message=f"Starting {operation_name}...",
            **kwargs
        )
        
        return operation_id
    
    def end_operation(
        self, 
        operation_id: str, 
        operation_name: str, 
        success: bool = True,
        items_processed: int = None,
        **kwargs
    ):
        """End timing an operation"""
        if operation_id not in self.operation_timers:
            self.warning(f"Operation timer not found: {operation_id}")
            return
        
        start_time = self.operation_timers.pop(operation_id)
        duration_ms = (datetime.now(timezone.utc).timestamp() - start_time) * 1000
        
        level = "INFO" if success else "ERROR"
        status = "completed" if success else "failed"
        
        log_method = self.info if success else self.error
        log_method(
            f"Operation {status}: {operation_name}",
            category=LogCategory.PERFORMANCE,
            operation=operation_name,
            operation_id=operation_id,
            duration_ms=duration_ms,
            items_processed=items_processed,
            user_message=f"{operation_name} {status}" + (f" ({items_processed} items)" if items_processed else ""),
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
    
    def log_security_event(self, event_type: str, details: Dict[str, Any], **kwargs):
        """Log security-related events"""
        self.warning(
            f"Security event: {event_type}",
            category=LogCategory.SECURITY,
            operation=event_type,
            metadata=details,
            user_message=f"Security event detected: {event_type}",
            **kwargs
        )

class HumanReadableFormatter(logging.Formatter):
    """Formatter for human-readable console output"""
    
    def format(self, record):
        if isinstance(record.msg, LogEntry):
            return record.msg.to_human_readable()
        return super().format(record)

class JSONFormatter(logging.Formatter):
    """Formatter for structured JSON output"""
    
    def format(self, record):
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
        return log_entry.to_json()
```

### 1.2 Component-Specific Logging

```python
# From component-specific logging patterns - EXAMPLE

class DataIngestionLogger(EnhancedLogger):
    """Specialized logger for data ingestion operations"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("data_ingestion", config)
    
    def log_source_discovery(self, source_id: str, source_type: str, file_count: int):
        """Log data source discovery"""
        self.info(
            f"Discovered data source: {source_id}",
            category=LogCategory.INGESTION,
            operation="source_discovery",
            source_id=source_id,
            metadata={
                "source_type": source_type,
                "file_count": file_count
            },
            user_message=f"Found {file_count} files in {source_id}",
            items_processed=file_count
        )
    
    def log_document_processing_start(self, document_path: str, document_id: str):
        """Log start of document processing"""
        return self.start_operation(
            "document_processing",
            category=LogCategory.DATA_PROCESSING,
            document_id=document_id,
            metadata={"document_path": document_path},
            user_message=f"Processing document: {document_path}"
        )
    
    def log_document_processing_end(
        self, 
        operation_id: str, 
        document_id: str, 
        success: bool,
        chunks_created: int = None,
        qa_pairs_generated: int = None
    ):
        """Log end of document processing"""
        metadata = {"chunks_created": chunks_created}
        if qa_pairs_generated:
            metadata["qa_pairs_generated"] = qa_pairs_generated
        
        user_message = f"Document processed successfully"
        if chunks_created:
            user_message += f" ({chunks_created} chunks created"
            if qa_pairs_generated:
                user_message += f", {qa_pairs_generated} Q&A pairs generated"
            user_message += ")"
        
        self.end_operation(
            operation_id,
            "document_processing",
            success=success,
            items_processed=chunks_created,
            category=LogCategory.DATA_PROCESSING,
            document_id=document_id,
            metadata=metadata,
            user_message=user_message if success else "Document processing failed"
        )
    
    def log_chunking_strategy(self, strategy: str, config: Dict[str, Any]):
        """Log chunking strategy selection"""
        self.info(
            f"Using chunking strategy: {strategy}",
            category=LogCategory.CHUNKING,
            operation="strategy_selection",
            metadata={"strategy": strategy, "config": config},
            user_message=f"Chunking documents using {strategy} strategy"
        )
    
    def log_qa_rag_processing(
        self, 
        source_id: str, 
        chunks_count: int, 
        questions_generated: int,
        avg_quality_score: float
    ):
        """Log QA RAG processing results"""
        self.info(
            f"QA RAG processing completed for {source_id}",
            category=LogCategory.QA_RAG,
            operation="qa_generation",
            source_id=source_id,
            metadata={
                "chunks_processed": chunks_count,
                "questions_generated": questions_generated,
                "avg_quality_score": avg_quality_score
            },
            user_message=f"Generated {questions_generated} Q&A pairs with {avg_quality_score:.1%} quality",
            items_processed=questions_generated
        )

class CrewAILogger(EnhancedLogger):
    """Specialized logger for CrewAI operations"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("crewai", config)
    
    def log_flow_start(self, flow_name: str, agents: List[str]) -> str:
        """Log start of CrewAI flow"""
        return self.start_operation(
            f"flow_{flow_name}",
            category=LogCategory.SYSTEM,
            flow_name=flow_name,
            metadata={"agents": agents},
            user_message=f"Starting {flow_name} workflow with {len(agents)} agents"
        )
    
    def log_agent_task_start(self, agent_name: str, task_description: str) -> str:
        """Log start of agent task"""
        return self.start_operation(
            f"agent_task",
            category=LogCategory.SYSTEM,
            agent_name=agent_name,
            metadata={"task_description": task_description},
            user_message=f"{agent_name} starting task"
        )
    
    def log_agent_task_end(
        self, 
        operation_id: str, 
        agent_name: str, 
        success: bool,
        result_summary: str = None
    ):
        """Log end of agent task"""
        self.end_operation(
            operation_id,
            "agent_task",
            success=success,
            category=LogCategory.SYSTEM,
            agent_name=agent_name,
            metadata={"result_summary": result_summary},
            user_message=f"{agent_name} {'completed' if success else 'failed'} task"
        )

class APILogger(EnhancedLogger):
    """Specialized logger for API operations"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__("api", config)
    
    def log_request_start(
        self, 
        method: str, 
        endpoint: str, 
        user_id: str = None,
        request_size: int = None
    ) -> str:
        """Log API request start"""
        return self.start_operation(
            f"api_request",
            category=LogCategory.API,
            metadata={
                "method": method,
                "endpoint": endpoint,
                "user_id": user_id,
                "request_size": request_size
            },
            user_message=f"Processing {method} {endpoint}"
        )
    
    def log_request_end(
        self,
        operation_id: str,
        status_code: int,
        response_size: int = None,
        error_message: str = None
    ):
        """Log API request end"""
        success = 200 <= status_code < 400
        
        metadata = {
            "status_code": status_code,
            "response_size": response_size
        }
        
        if error_message:
            metadata["error_message"] = error_message
        
        self.end_operation(
            operation_id,
            "api_request",
            success=success,
            category=LogCategory.API,
            metadata=metadata,
            user_message=f"Request {'completed' if success else 'failed'} with status {status_code}"
        )
```

---

## 2. User-Facing Log Interface

### 2.1 Clean Log Presentation System

```python
# From user-facing logging patterns - EXAMPLE
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import re

@dataclass
class UserLogEntry:
    """User-friendly log entry for UI presentation"""
    timestamp: str
    level: str
    message: str
    category: str
    progress: Optional[float] = None
    details: Optional[Dict[str, Any]] = None
    action_required: bool = False
    can_retry: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "category": self.category,
            "progress": self.progress,
            "details": self.details,
            "action_required": self.action_required,
            "can_retry": self.can_retry
        }

class UserLogFormatter:
    """Formats technical logs into user-friendly messages"""
    
    # Message templates for common operations
    MESSAGE_TEMPLATES = {
        "document_processing_start": "Processing document: {document_name}",
        "document_processing_end": "Finished processing {document_name} ({chunks_created} chunks created)",
        "qa_rag_processing": "Generated {questions_count} questions and answers with {quality:.0%} quality",
        "chunking_strategy": "Using {strategy} chunking strategy for optimal content organization",
        "source_discovery": "Found {file_count} files to process in {source_name}",
        "flow_start": "Starting {flow_name} analysis with {agent_count} AI agents",
        "agent_task_start": "{agent_name} is analyzing the data",
        "agent_task_end": "{agent_name} completed analysis",
        "api_request": "Processing your request...",
        "indexing_start": "Building searchable index from processed content",
        "indexing_end": "Index created successfully with {item_count} items"
    }
    
    # Progress messages for long-running operations
    PROGRESS_MESSAGES = {
        "document_processing": [
            "Extracting content from documents...",
            "Breaking content into manageable chunks...",
            "Generating questions and answers...",
            "Validating content quality...",
            "Building searchable index..."
        ],
        "analysis_flow": [
            "Analyzing document structure...",
            "Identifying key information...",
            "Calculating insights...",
            "Generating recommendations...",
            "Finalizing results..."
        ]
    }
    
    def __init__(self):
        self.current_operations: Dict[str, Dict[str, Any]] = {}
    
    def format_log_for_user(self, log_entry: LogEntry) -> Optional[UserLogEntry]:
        """Convert technical log entry to user-friendly format"""
        
        # Skip trace and debug logs for users
        if log_entry.level in ["TRACE", "DEBUG"]:
            return None
        
        # Extract user message if available
        if log_entry.user_message:
            message = log_entry.user_message
        else:
            message = self._generate_user_message(log_entry)
        
        # Determine if action is required
        action_required = log_entry.level in ["ERROR", "CRITICAL"]
        can_retry = log_entry.level == "ERROR" and "timeout" in log_entry.message.lower()
        
        # Extract progress information
        progress = log_entry.progress_percent
        if not progress and log_entry.operation in self.current_operations:
            progress = self._calculate_progress(log_entry)
        
        # Prepare details for expandable UI
        details = self._prepare_user_details(log_entry)
        
        return UserLogEntry(
            timestamp=self._format_timestamp_for_user(log_entry.timestamp),
            level=self._map_level_for_user(log_entry.level),
            message=message,
            category=self._map_category_for_user(log_entry.category),
            progress=progress,
            details=details,
            action_required=action_required,
            can_retry=can_retry
        )
    
    def _generate_user_message(self, log_entry: LogEntry) -> str:
        """Generate user-friendly message from technical log"""
        
        operation = log_entry.operation
        message = log_entry.message
        
        # Use templates if available
        if operation in self.MESSAGE_TEMPLATES:
            template = self.MESSAGE_TEMPLATES[operation]
            try:
                return template.format(**log_entry.metadata, **log_entry.context)
            except KeyError:
                pass  # Fall back to original message
        
        # Clean up technical message
        cleaned_message = self._clean_technical_message(message)
        return cleaned_message
    
    def _clean_technical_message(self, message: str) -> str:
        """Clean up technical message for user consumption"""
        
        # Remove technical prefixes
        message = re.sub(r'^(Processing|Executing|Running|Starting|Ending)\s+', '', message)
        
        # Replace technical terms
        replacements = {
            "chunk": "section",
            "embedding": "content analysis",
            "vector": "search index",
            "RAG": "question-answer generation",
            "API": "service",
            "HTTP": "web",
            "JSON": "data",
            "async": "background",
            "pipeline": "workflow"
        }
        
        for tech_term, user_term in replacements.items():
            message = re.sub(rf'\b{tech_term}\b', user_term, message, flags=re.IGNORECASE)
        
        # Capitalize first letter
        if message:
            message = message[0].upper() + message[1:]
        
        return message
    
    def _format_timestamp_for_user(self, timestamp: str) -> str:
        """Format timestamp for user display"""
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return dt.strftime("%H:%M:%S")  # Just show time for recent logs
        except:
            return timestamp
    
    def _map_level_for_user(self, level: str) -> str:
        """Map technical log level to user-friendly level"""
        mapping = {
            "TRACE": "info",
            "DEBUG": "info", 
            "INFO": "info",
            "WARNING": "warning",
            "ERROR": "error",
            "CRITICAL": "error"
        }
        return mapping.get(level, "info")
    
    def _map_category_for_user(self, category: str) -> str:
        """Map technical category to user-friendly category"""
        mapping = {
            "system": "System",
            "security": "Security",
            "performance": "Performance",
            "business": "Analysis",
            "user_action": "Action",
            "data_processing": "Processing",
            "api": "Service",
            "integration": "Integration",
            "qa_rag": "Q&A Generation",
            "chunking": "Content Organization",
            "ingestion": "Data Import",
            "analysis": "Analysis"
        }
        return mapping.get(category, "System")
    
    def _prepare_user_details(self, log_entry: LogEntry) -> Optional[Dict[str, Any]]:
        """Prepare expandable details for user interface"""
        
        details = {}
        
        # Add performance information
        if log_entry.duration_ms:
            details["Processing Time"] = f"{log_entry.duration_ms:.0f}ms"
        
        if log_entry.items_processed:
            details["Items Processed"] = log_entry.items_processed
        
        # Add relevant metadata
        if log_entry.metadata:
            user_friendly_metadata = {}
            for key, value in log_entry.metadata.items():
                friendly_key = self._make_key_friendly(key)
                user_friendly_metadata[friendly_key] = value
            
            if user_friendly_metadata:
                details.update(user_friendly_metadata)
        
        # Add error information for failed operations
        if log_entry.level in ["ERROR", "CRITICAL"]:
            if log_entry.error_type:
                details["Error Type"] = log_entry.error_type
            
            if log_entry.error_code:
                details["Error Code"] = log_entry.error_code
        
        return details if details else None
    
    def _make_key_friendly(self, key: str) -> str:
        """Convert technical key to user-friendly format"""
        # Convert snake_case to Title Case
        friendly = key.replace('_', ' ').title()
        
        # Handle common abbreviations
        abbreviations = {
            'Id': 'ID',
            'Url': 'URL',
            'Api': 'API',
            'Qa': 'Q&A',
            'Rag': 'RAG'
        }
        
        for abbrev, replacement in abbreviations.items():
            friendly = friendly.replace(abbrev, replacement)
        
        return friendly
    
    def _calculate_progress(self, log_entry: LogEntry) -> Optional[float]:
        """Calculate progress for ongoing operations"""
        
        operation = log_entry.operation
        if operation not in self.current_operations:
            return None
        
        op_info = self.current_operations[operation]
        
        # Simple progress calculation based on operation type
        if "document_processing" in operation:
            # Estimate based on processing stages
            stages = ["discovery", "extraction", "chunking", "qa_rag", "indexing"]
            current_stage = log_entry.metadata.get("stage", "")
            
            if current_stage in stages:
                stage_index = stages.index(current_stage)
                return (stage_index / len(stages)) * 100
        
        return None

class LogStreamManager:
    """Manages real-time log streaming to UI clients"""
    
    def __init__(self):
        self.subscribers: Dict[str, List[Any]] = {}  # session_id -> list of websocket connections
        self.log_formatter = UserLogFormatter()
        self.log_buffer: Dict[str, List[UserLogEntry]] = {}  # session_id -> recent logs
        self.max_buffer_size = 1000
    
    def subscribe(self, session_id: str, websocket_connection: Any):
        """Subscribe a client to log updates"""
        if session_id not in self.subscribers:
            self.subscribers[session_id] = []
        self.subscribers[session_id].append(websocket_connection)
        
        # Send recent logs to new subscriber
        if session_id in self.log_buffer:
            for log_entry in self.log_buffer[session_id][-50:]:  # Last 50 entries
                self._send_to_connection(websocket_connection, log_entry)
    
    def unsubscribe(self, session_id: str, websocket_connection: Any):
        """Unsubscribe a client from log updates"""
        if session_id in self.subscribers:
            try:
                self.subscribers[session_id].remove(websocket_connection)
                if not self.subscribers[session_id]:
                    del self.subscribers[session_id]
            except ValueError:
                pass  # Connection not in list
    
    def broadcast_log(self, log_entry: LogEntry, session_id: str = None):
        """Broadcast log entry to subscribed clients"""
        
        # Format for user consumption
        user_log = self.log_formatter.format_log_for_user(log_entry)
        if not user_log:
            return  # Skip logs not relevant to users
        
        # Determine target sessions
        target_sessions = [session_id] if session_id else list(self.subscribers.keys())
        
        for target_session in target_sessions:
            if target_session in self.subscribers:
                # Add to buffer
                if target_session not in self.log_buffer:
                    self.log_buffer[target_session] = []
                
                self.log_buffer[target_session].append(user_log)
                
                # Trim buffer if too large
                if len(self.log_buffer[target_session]) > self.max_buffer_size:
                    self.log_buffer[target_session] = self.log_buffer[target_session][-self.max_buffer_size:]
                
                # Send to all connections for this session
                for connection in self.subscribers[target_session][:]:  # Copy list to avoid modification during iteration
                    try:
                        self._send_to_connection(connection, user_log)
                    except Exception as e:
                        # Remove broken connection
                        self.subscribers[target_session].remove(connection)
    
    def _send_to_connection(self, connection: Any, user_log: UserLogEntry):
        """Send log entry to a specific connection"""
        try:
            # Assume connection has a send_json method (WebSocket)
            connection.send_json({
                "type": "log_entry",
                "data": user_log.to_dict()
            })
        except Exception as e:
            # Log the error but don't let it break the logging system
            print(f"Failed to send log to connection: {e}")
```

### 2.2 Console Log Interface

```python
# From console logging patterns - EXAMPLE
import sys
from typing import TextIO
import colorama
from colorama import Fore, Back, Style

colorama.init()  # Initialize colorama for Windows compatibility

class ConsoleLogHandler:
    """Enhanced console log handler with colors and formatting"""
    
    def __init__(self, output_stream: TextIO = sys.stdout, use_colors: bool = True):
        self.output_stream = output_stream
        self.use_colors = use_colors
        self.log_formatter = UserLogFormatter()
        
        # Color mapping for different log levels
        self.level_colors = {
            "info": Fore.BLUE,
            "warning": Fore.YELLOW,
            "error": Fore.RED,
            "success": Fore.GREEN
        }
        
        # Category icons
        self.category_icons = {
            "Processing": "⚙️",
            "Q&A Generation": "❓",
            "Content Organization": "📑",
            "Data Import": "📥",
            "Analysis": "🔍",
            "System": "🖥️",
            "Security": "🔒",
            "Performance": "⚡"
        }
    
    def handle_log(self, log_entry: LogEntry):
        """Handle a log entry for console output"""
        
        # Convert to user-friendly format
        user_log = self.log_formatter.format_log_for_user(log_entry)
        if not user_log:
            return
        
        # Format for console
        formatted_line = self._format_for_console(user_log)
        
        # Write to output stream
        self.output_stream.write(formatted_line + "\n")
        self.output_stream.flush()
    
    def _format_for_console(self, user_log: UserLogEntry) -> str:
        """Format user log for console output"""
        
        # Get color for level
        color = self.level_colors.get(user_log.level, "")
        reset = Style.RESET_ALL if self.use_colors else ""
        
        # Get icon for category
        icon = self.category_icons.get(user_log.category, "📝")
        
        # Build formatted line
        parts = []
        
        # Timestamp
        parts.append(f"[{user_log.timestamp}]")
        
        # Level and icon
        if self.use_colors and color:
            parts.append(f"{color}{icon} {user_log.level.upper()}{reset}")
        else:
            parts.append(f"{icon} {user_log.level.upper()}")
        
        # Category
        parts.append(f"[{user_log.category}]")
        
        # Message
        parts.append(user_log.message)
        
        # Progress bar if available
        if user_log.progress is not None:
            progress_bar = self._create_progress_bar(user_log.progress)
            parts.append(progress_bar)
        
        return " ".join(parts)
    
    def _create_progress_bar(self, progress: float, width: int = 20) -> str:
        """Create a simple ASCII progress bar"""
        filled = int((progress / 100) * width)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {progress:.1f}%"
    
    def print_summary(self, operation: str, metrics: Dict[str, Any]):
        """Print operation summary"""
        
        color = Fore.GREEN if self.use_colors else ""
        reset = Style.RESET_ALL if self.use_colors else ""
        
        self.output_stream.write(f"\n{color}✅ {operation} Summary{reset}\n")
        self.output_stream.write("=" * 50 + "\n")
        
        for key, value in metrics.items():
            friendly_key = key.replace('_', ' ').title()
            self.output_stream.write(f"{friendly_key}: {value}\n")
        
        self.output_stream.write("\n")
        self.output_stream.flush()
    
    def print_error_details(self, error_message: str, details: Dict[str, Any] = None):
        """Print detailed error information"""
        
        color = Fore.RED if self.use_colors else ""
        reset = Style.RESET_ALL if self.use_colors else ""
        
        self.output_stream.write(f"\n{color}❌ Error Details{reset}\n")
        self.output_stream.write("=" * 50 + "\n")
        self.output_stream.write(f"Message: {error_message}\n")
        
        if details:
            for key, value in details.items():
                friendly_key = key.replace('_', ' ').title()
                self.output_stream.write(f"{friendly_key}: {value}\n")
        
        self.output_stream.write("\n")
        self.output_stream.flush()
```

---

## 3. Integration Examples

### 3.1 FastAPI Integration

```python
# From FastAPI logging integration - EXAMPLE
from fastapi import FastAPI, Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
import time

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests and responses"""
    
    def __init__(self, app, logger: APILogger):
        super().__init__(app)
        self.logger = logger
    
    async def dispatch(self, request: Request, call_next):
        # Set request context
        request_id = str(uuid.uuid4())
        request_id_context.set(request_id)
        
        # Extract user ID if available
        user_id = request.headers.get("X-User-ID", "anonymous")
        user_id_context.set(user_id)
        
        # Log request start
        operation_id = self.logger.log_request_start(
            method=request.method,
            endpoint=str(request.url),
            user_id=user_id,
            request_size=request.headers.get("content-length")
        )
        
        # Process request
        start_time = time.time()
        try:
            response = await call_next(request)
            
            # Log successful response
            self.logger.log_request_end(
                operation_id=operation_id,
                status_code=response.status_code,
                response_size=response.headers.get("content-length")
            )
            
            return response
            
        except Exception as e:
            # Log error response
            self.logger.log_request_end(
                operation_id=operation_id,
                status_code=500,
                error_message=str(e)
            )
            raise

app = FastAPI()
api_logger = APILogger()
app.add_middleware(LoggingMiddleware, logger=api_logger)
```

### 3.2 CrewAI Flow Integration

```python
# From CrewAI logging integration - EXAMPLE
from crewai import Flow, Agent, Task

class LoggedFlow(Flow):
    """Flow with integrated logging"""
    
    def __init__(self, name: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self.logger = CrewAILogger()
        self.flow_operation_id = None
    
    async def kickoff(self, *args, **kwargs):
        """Override kickoff to add logging"""
        
        # Log flow start
        agent_names = [agent.role for agent in self.agents] if hasattr(self, 'agents') else []
        self.flow_operation_id = self.logger.log_flow_start(self.name, agent_names)
        
        try:
            # Execute original kickoff
            result = await super().kickoff(*args, **kwargs)
            
            # Log flow success
            self.logger.end_operation(
                self.flow_operation_id,
                f"flow_{self.name}",
                success=True,
                metadata={"result_summary": str(result)[:200]}
            )
            
            return result
            
        except Exception as e:
            # Log flow failure
            self.logger.end_operation(
                self.flow_operation_id,
                f"flow_{self.name}",
                success=False,
                metadata={"error": str(e)}
            )
            raise

class LoggedAgent(Agent):
    """Agent with integrated logging"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = CrewAILogger()
    
    async def execute(self, task: Task):
        """Override execute to add logging"""
        
        # Log task start
        operation_id = self.logger.log_agent_task_start(
            self.role,
            task.description[:100] + "..." if len(task.description) > 100 else task.description
        )
        
        try:
            # Execute original task
            result = await super().execute(task)
            
            # Log task success
            self.logger.log_agent_task_end(
                operation_id,
                self.role,
                success=True,
                result_summary=str(result)[:200] if result else "No result"
            )
            
            return result
            
        except Exception as e:
            # Log task failure
            self.logger.log_agent_task_end(
                operation_id,
                self.role,
                success=False,
                result_summary=str(e)
            )
            raise
```

---

## 4. Monitoring and Alerting Integration

### 4.1 Metrics Collection

```python
# From metrics collection patterns - EXAMPLE
from typing import Counter
import json
import time

class LogMetricsCollector:
    """Collects metrics from log entries for monitoring"""
    
    def __init__(self):
        self.metrics = {
            "log_counts": Counter(),
            "error_counts": Counter(),
            "operation_durations": {},
            "business_metrics": {},
            "performance_metrics": {}
        }
        self.start_time = time.time()
    
    def process_log_entry(self, log_entry: LogEntry):
        """Process log entry to extract metrics"""
        
        # Count logs by level and category
        self.metrics["log_counts"][f"{log_entry.level}_{log_entry.category}"] += 1
        
        # Track errors
        if log_entry.level in ["ERROR", "CRITICAL"]:
            error_key = f"{log_entry.component}_{log_entry.operation}"
            self.metrics["error_counts"][error_key] += 1
        
        # Track operation durations
        if log_entry.duration_ms:
            operation_key = f"{log_entry.component}_{log_entry.operation}"
            if operation_key not in self.metrics["operation_durations"]:
                self.metrics["operation_durations"][operation_key] = []
            self.metrics["operation_durations"][operation_key].append(log_entry.duration_ms)
        
        # Track business metrics
        if log_entry.category == "business":
            metric_name = log_entry.metadata.get("metric_name")
            if metric_name:
                self.metrics["business_metrics"][metric_name] = log_entry.metadata.get("metric_value")
        
        # Track performance metrics
        if log_entry.items_processed:
            self.metrics["performance_metrics"]["total_items_processed"] = (
                self.metrics["performance_metrics"].get("total_items_processed", 0) + 
                log_entry.items_processed
            )
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics"""
        
        current_time = time.time()
        uptime_seconds = current_time - self.start_time
        
        # Calculate average durations
        avg_durations = {}
        for operation, durations in self.metrics["operation_durations"].items():
            if durations:
                avg_durations[operation] = sum(durations) / len(durations)
        
        return {
            "uptime_seconds": uptime_seconds,
            "log_counts": dict(self.metrics["log_counts"]),
            "error_counts": dict(self.metrics["error_counts"]),
            "average_durations_ms": avg_durations,
            "business_metrics": self.metrics["business_metrics"],
            "performance_metrics": self.metrics["performance_metrics"]
        }
    
    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format"""
        
        metrics_lines = []
        
        # Log counts
        for key, count in self.metrics["log_counts"].items():
            level, category = key.split("_", 1)
            metrics_lines.append(
                f'log_entries_total{{level="{level}",category="{category}"}} {count}'
            )
        
        # Error counts
        for key, count in self.metrics["error_counts"].items():
            component, operation = key.split("_", 1)
            metrics_lines.append(
                f'errors_total{{component="{component}",operation="{operation}"}} {count}'
            )
        
        # Operation durations
        for operation, durations in self.metrics["operation_durations"].items():
            if durations:
                avg_duration = sum(durations) / len(durations)
                metrics_lines.append(
                    f'operation_duration_ms{{operation="{operation}"}} {avg_duration}'
                )
        
        return "\n".join(metrics_lines)
```

This comprehensive logging specification provides:

1. **Structured Logging Format** with rich context and metadata
2. **Component-Specific Loggers** for different system parts
3. **User-Friendly Log Interfaces** for both UI and console
4. **Real-Time Log Streaming** for live monitoring
5. **Metrics Collection** for monitoring and alerting
6. **Error Handling** and recovery logging
7. **Security-Conscious** logging without sensitive data exposure

The system ensures that both technical teams and end users have access to appropriate, well-formatted logging information that helps with debugging, monitoring, and understanding system operations.

