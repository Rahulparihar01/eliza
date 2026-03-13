# Prompt Tracking & Feedback System Specification

## Executive Summary

This document defines a comprehensive prompt tracking system for the AI Enablement Platform that leverages **CrewAI's native logging and tracking capabilities** while adding user feedback and frontend integration layers. The system provides clean, accessible logging with task-based organization for easy frontend integration and analytics.

**Key Features:**
- **CrewAI Native Integration**: Leverages built-in execution traces, observability, and logging
- **Task-Based Organization**: All prompts linked to user tasks with unique IDs
- **Real-Time Tracking**: Complete prompt lifecycle from generation to execution via CrewAI traces
- **User Feedback Layer**: Rating, corrections, and improvement suggestions on top of CrewAI data
- **Frontend Accessibility**: Clean APIs for prompt retrieval and display
- **Performance Analytics**: Agent improvement metrics using CrewAI's comprehensive traces
- **Simple Implementation**: Minimal custom code by leveraging CrewAI's built-in functionality

---

## 1. CrewAI Native Integration Architecture

### 1.1 CrewAI Logging and Traces Overview

CrewAI provides comprehensive built-in logging and execution traces that capture:

- **Agent thoughts and reasoning**
- **Task execution details** 
- **Tool usage and outputs**
- **Token consumption metrics**
- **Execution times**
- **Cost estimates**
- **Complete prompt lifecycle**

### 1.2 Enhanced Data Model (User Feedback Layer)

```python
# From prompt_tracking/models.py - EXAMPLE
# We'll primarily use CrewAI's native data structures and add minimal custom models for user feedback

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import uuid

class FeedbackRating(Enum):
    """User feedback ratings"""
    EXCELLENT = 5
    GOOD = 4
    SATISFACTORY = 3
    POOR = 2
    VERY_POOR = 1

@dataclass
class TaskMetadata:
    """Additional metadata to link with CrewAI execution results"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    session_id: str = ""
    department: Optional[str] = None
    priority: int = 1
    original_input: str = ""
    tags: List[str] = field(default_factory=list)

@dataclass
class UserFeedback:
    """User feedback on CrewAI execution results"""
    feedback_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""  # Links to CrewAI execution
    crew_execution_id: str = ""  # CrewAI's internal execution ID
    user_id: str = ""
    
    # Feedback details
    rating: FeedbackRating = FeedbackRating.SATISFACTORY
    feedback_text: str = ""
    suggested_improvement: str = ""
    
    # Specific feedback categories
    accuracy_rating: Optional[int] = None  # 1-5
    relevance_rating: Optional[int] = None  # 1-5
    clarity_rating: Optional[int] = None  # 1-5
    completeness_rating: Optional[int] = None  # 1-5
    
    # Feedback metadata
    feedback_type: str = "general"  # general, correction, suggestion
    is_correction: bool = False
    corrected_response: str = ""
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None
```

## 2. CrewAI Integration Implementation

### 2.1 CrewAI Logging Configuration

```python
# From prompt_tracking/crewai_integration.py - EXAMPLE
from crewai import Crew, Agent, Task
from typing import Dict, Any, Optional
import json
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TrackedCrew(Crew):
    """Enhanced Crew with integrated tracking and user feedback"""
    
    def __init__(self, *args, task_metadata: TaskMetadata = None, **kwargs):
        # Enable CrewAI's native logging
        kwargs['output_log_file'] = True  # Enable JSON logging
        kwargs['verbose'] = True  # Enable detailed logging
        
        super().__init__(*args, **kwargs)
        
        self.task_metadata = task_metadata or TaskMetadata()
        self.execution_id = None
        self.execution_result = None
        
        # Initialize feedback storage (simple SQLite for user feedback layer)
        self.feedback_manager = FeedbackManager()
    
    async def kickoff(self, inputs: Dict[str, Any]) -> Any:
        """Execute crew with enhanced tracking"""
        
        # Update task metadata with inputs
        self.task_metadata.original_input = inputs.get('user_input', '')
        self.task_metadata.user_id = inputs.get('user_id', '')
        self.task_metadata.session_id = inputs.get('session_id', '')
        
        logger.info(f"Starting crew execution for task: {self.task_metadata.task_id}")
        
        try:
            # Execute the crew (CrewAI handles all the logging internally)
            result = super().kickoff(inputs)
            
            # CrewAI automatically generates execution traces and logs
            # We just need to store our task metadata and prepare for user feedback
            
            self.execution_result = result
            self.execution_id = self._extract_execution_id_from_logs()
            
            # Store task metadata for frontend access
            await self.feedback_manager.store_task_metadata(
                self.task_metadata, 
                self.execution_id,
                result
            )
            
            logger.info(f"Crew execution completed for task: {self.task_metadata.task_id}")
            
            return {
                'result': result,
                'task_id': self.task_metadata.task_id,
                'execution_id': self.execution_id,
                'logs_available': True
            }
            
        except Exception as e:
            logger.error(f"Crew execution failed for task {self.task_metadata.task_id}: {e}")
            
            # Still store metadata for error analysis
            await self.feedback_manager.store_task_metadata(
                self.task_metadata, 
                None,
                None,
                error=str(e)
            )
            
            raise
    
    def _extract_execution_id_from_logs(self) -> str:
        """Extract execution ID from CrewAI logs if available"""
        # CrewAI may provide execution IDs in logs or traces
        # This would be implementation-specific based on CrewAI's actual log format
        return str(uuid.uuid4())  # Fallback to generated ID
    
    def get_execution_logs(self) -> Dict[str, Any]:
        """Get CrewAI's execution logs and traces"""
        # Access CrewAI's logged data
        # This would read from the JSON log files CrewAI generates
        
        log_file = f"logs_{self.execution_id}.json"  # CrewAI's log file
        
        try:
            with open(log_file, 'r') as f:
                logs = json.load(f)
            
            return {
                'task_id': self.task_metadata.task_id,
                'execution_id': self.execution_id,
                'logs': logs,
                'metadata': self.task_metadata.__dict__
            }
            
        except FileNotFoundError:
            # Fallback to basic information
            return {
                'task_id': self.task_metadata.task_id,
                'execution_id': self.execution_id,
                'result': self.execution_result,
                'metadata': self.task_metadata.__dict__
            }

class FeedbackManager:
    """Lightweight manager for user feedback on CrewAI executions"""
    
    def __init__(self, db_path: str = "user_feedback.db"):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._init_feedback_database()
    
    def _init_feedback_database(self):
        """Initialize lightweight database for user feedback only"""
        
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            # Simple tasks table (metadata only, CrewAI handles execution data)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_metadata (
                    task_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    original_input TEXT NOT NULL,
                    department TEXT,
                    priority INTEGER DEFAULT 1,
                    crew_execution_id TEXT,
                    final_result TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    tags TEXT
                )
            """)
            
            # User feedback table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_feedback (
                    feedback_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    crew_execution_id TEXT,
                    user_id TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    feedback_text TEXT,
                    suggested_improvement TEXT,
                    accuracy_rating INTEGER,
                    relevance_rating INTEGER,
                    clarity_rating INTEGER,
                    completeness_rating INTEGER,
                    feedback_type TEXT DEFAULT 'general',
                    is_correction BOOLEAN DEFAULT 0,
                    corrected_response TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES task_metadata (task_id)
                )
            """)
            
            conn.commit()
    
    async def store_task_metadata(
        self, 
        metadata: TaskMetadata, 
        execution_id: str, 
        result: Any,
        error: str = None
    ):
        """Store task metadata for frontend access"""
        
        import sqlite3
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO task_metadata (
                        task_id, user_id, session_id, original_input,
                        department, priority, crew_execution_id, final_result,
                        error_message, completed_at, tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (
                    metadata.task_id,
                    metadata.user_id,
                    metadata.session_id,
                    metadata.original_input,
                    metadata.department,
                    metadata.priority,
                    execution_id,
                    str(result) if result else None,
                    error,
                    json.dumps(metadata.tags)
                ))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to store task metadata: {e}")
    
    async def add_user_feedback(self, feedback: UserFeedback) -> str:
        """Add user feedback for a CrewAI execution"""
        
        import sqlite3
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO user_feedback (
                        feedback_id, task_id, crew_execution_id, user_id, rating,
                        feedback_text, suggested_improvement, accuracy_rating,
                        relevance_rating, clarity_rating, completeness_rating,
                        feedback_type, is_correction, corrected_response
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    feedback.feedback_id,
                    feedback.task_id,
                    feedback.crew_execution_id,
                    feedback.user_id,
                    feedback.rating.value,
                    feedback.feedback_text,
                    feedback.suggested_improvement,
                    feedback.accuracy_rating,
                    feedback.relevance_rating,
                    feedback.clarity_rating,
                    feedback.completeness_rating,
                    feedback.feedback_type,
                    feedback.is_correction,
                    feedback.corrected_response
                ))
                conn.commit()
            
            self.logger.info(f"Added user feedback: {feedback.feedback_id}")
            return feedback.feedback_id
            
        except Exception as e:
            self.logger.error(f"Failed to add user feedback: {e}")
            raise
```

### 2.2 Usage Example

```python
# From user_task_enrichment_flow.py - EXAMPLE
from prompt_tracking.crewai_integration import TrackedCrew, TaskMetadata
from crewai import Agent, Task

# Create agents
intent_analyzer = Agent(
    role="Intent Analyzer",
    goal="Analyze user intent and extract key information",
    backstory="Expert at understanding user requests and categorizing them"
)

context_enricher = Agent(
    role="Context Enricher", 
    goal="Enrich user requests with relevant context and information",
    backstory="Specialist in gathering and organizing relevant information"
)

# Create tasks
analyze_task = Task(
    description="Analyze the user's intent: {user_input}",
    agent=intent_analyzer
)

enrich_task = Task(
    description="Enrich the analyzed intent with relevant context",
    agent=context_enricher,
    depends_on=[analyze_task]
)

# Create tracked crew
task_metadata = TaskMetadata(
    user_id="user_123",
    session_id="session_456", 
    department="sales",
    tags=["intent_analysis", "context_enrichment"]
)

crew = TrackedCrew(
    agents=[intent_analyzer, context_enricher],
    tasks=[analyze_task, enrich_task],
    task_metadata=task_metadata,
    verbose=True
)

# Execute with automatic tracking
result = await crew.kickoff({
    'user_input': 'Help me analyze our Q3 sales performance',
    'user_id': 'user_123',
    'session_id': 'session_456'
})

# Result includes tracking information
print(f"Task ID: {result['task_id']}")
print(f"Execution ID: {result['execution_id']}")
print(f"Logs available: {result['logs_available']}")

# Access detailed logs and traces (CrewAI's native data)
execution_logs = crew.get_execution_logs()
```

## 3. Frontend API Integration

### 3.1 Simplified API Endpoints

```python
# From api/crewai_tracking_api.py - EXAMPLE
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer
from typing import Dict, Any
import json
import os

app = FastAPI()
security = HTTPBearer()

@app.get("/api/tasks/{task_id}/execution")
async def get_task_execution(
    task_id: str,
    token: str = Depends(security)
) -> Dict[str, Any]:
    """Get complete execution details including CrewAI logs and user feedback"""
    
    user_id = await get_user_from_token(token.credentials)
    
    # Get task metadata
    feedback_manager = FeedbackManager()
    task_data = await feedback_manager.get_task_metadata(task_id)
    
    if not task_data or task_data['user_id'] != user_id:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get CrewAI execution logs
    crew_logs = await get_crewai_logs(task_data['crew_execution_id'])
    
    # Get user feedback
    user_feedback = await feedback_manager.get_task_feedback(task_id)
    
    return {
        'task_id': task_id,
        'metadata': task_data,
        'execution_logs': crew_logs,  # CrewAI's detailed traces
        'user_feedback': user_feedback,
        'summary': {
            'agents_used': len(crew_logs.get('agents', [])),
            'tasks_completed': len(crew_logs.get('tasks', [])),
            'total_tokens': crew_logs.get('total_tokens', 0),
            'total_cost': crew_logs.get('total_cost', 0.0),
            'execution_time': crew_logs.get('execution_time', 0.0)
        }
    }

@app.get("/api/users/{user_id}/tasks")
async def get_user_tasks(
    user_id: str,
    limit: int = 50,
    token: str = Depends(security)
) -> Dict[str, Any]:
    """Get user's recent tasks with basic info"""
    
    request_user_id = await get_user_from_token(token.credentials)
    if request_user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    feedback_manager = FeedbackManager()
    tasks = await feedback_manager.get_user_tasks(user_id, limit)
    
    return {
        'user_id': user_id,
        'tasks': tasks
    }

@app.post("/api/tasks/{task_id}/feedback")
async def add_task_feedback(
    task_id: str,
    feedback_data: Dict[str, Any],
    token: str = Depends(security)
) -> Dict[str, str]:
    """Add user feedback for a CrewAI execution"""
    
    user_id = await get_user_from_token(token.credentials)
    
    feedback = UserFeedback(
        task_id=task_id,
        crew_execution_id=feedback_data.get('crew_execution_id', ''),
        user_id=user_id,
        rating=FeedbackRating(feedback_data.get('rating', 3)),
        feedback_text=feedback_data.get('feedback_text', ''),
        suggested_improvement=feedback_data.get('suggested_improvement', ''),
        accuracy_rating=feedback_data.get('accuracy_rating'),
        relevance_rating=feedback_data.get('relevance_rating'),
        clarity_rating=feedback_data.get('clarity_rating'),
        completeness_rating=feedback_data.get('completeness_rating'),
        feedback_type=feedback_data.get('feedback_type', 'general'),
        is_correction=feedback_data.get('is_correction', False),
        corrected_response=feedback_data.get('corrected_response', '')
    )
    
    feedback_manager = FeedbackManager()
    feedback_id = await feedback_manager.add_user_feedback(feedback)
    
    return {'feedback_id': feedback_id, 'message': 'Feedback added successfully'}

async def get_crewai_logs(execution_id: str) -> Dict[str, Any]:
    """Get CrewAI execution logs from log files"""
    
    # CrewAI saves logs to files, we read them
    log_file = f"logs_{execution_id}.json"
    
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            return json.load(f)
    
    # Fallback - check default log file
    if os.path.exists('logs.json'):
        with open('logs.json', 'r') as f:
            all_logs = json.load(f)
            # Filter for specific execution if possible
            return all_logs
    
    return {'error': 'Logs not found'}

async def get_user_from_token(token: str) -> str:
    """Extract user ID from authentication token"""
    return "user_123"  # Placeholder
```

## 4. Configuration

### 4.1 CrewAI Logging Configuration

```yaml
# crewai_tracking_config.yaml - EXAMPLE
crewai_tracking:
  # CrewAI native logging settings
  logging:
    enabled: true
    output_format: "json"  # CrewAI supports both txt and json
    verbose: true
    save_logs: true
    log_directory: "./crew_logs"
    
  # User feedback layer settings  
  feedback:
    database_path: "user_feedback.db"
    auto_request_threshold: 3.0  # Request feedback for ratings below 3.0
    retention_days: 365
    
  # Frontend integration
  api:
    enable_real_time: true
    log_access_timeout: 30  # seconds
    max_log_size_mb: 100
    
  # Performance
  cleanup:
    old_logs_days: 90
    compress_logs: true
    backup_interval_hours: 24

# CrewAI specific settings
crewai:
  # Enable comprehensive tracing
  observability:
    enabled: true
    trace_level: "detailed"  # basic, detailed, comprehensive
    
  # Integration with monitoring platforms
  integrations:
    wandb:
      enabled: false  # Set to true if using Weights & Biases
      project: "ai_enablement_platform"
      
    custom_monitoring:
      enabled: true
      webhook_url: "${MONITORING_WEBHOOK_URL}"
```

### 4.2 Environment Variables

```bash
# .env - EXAMPLE

# CrewAI Configuration
CREWAI_LOG_LEVEL=INFO
CREWAI_SAVE_LOGS=true
CREWAI_LOG_FORMAT=json

# User Feedback Database
FEEDBACK_DB_PATH=user_feedback.db

# Monitoring (optional)
MONITORING_WEBHOOK_URL=https://your-monitoring-service.com/webhook
WANDB_API_KEY=your_wandb_key  # If using Weights & Biases

# API Configuration  
FEEDBACK_API_TIMEOUT=30
MAX_LOG_FILE_SIZE_MB=100
```

## 5. Benefits of Using CrewAI Native Tracking

### 5.1 Advantages

✅ **Minimal Custom Code**: Leverage CrewAI's built-in comprehensive logging
✅ **Rich Execution Traces**: Automatic capture of agent thoughts, tool usage, and execution details
✅ **Performance Metrics**: Built-in token usage, cost tracking, and timing
✅ **Observability Integration**: Native support for monitoring platforms
✅ **Maintenance-Free**: CrewAI handles the complex logging infrastructure
✅ **Standardized Format**: Consistent logging format across all executions

### 5.2 Implementation Strategy

1. **Use CrewAI's Native Logging**: Enable `output_log_file=True` and `verbose=True`
2. **Add Thin Feedback Layer**: Simple SQLite database for user feedback only
3. **Frontend Integration**: Read CrewAI logs + user feedback via clean APIs
4. **Monitoring Integration**: Leverage CrewAI's built-in observability features

This approach gives you comprehensive prompt tracking with minimal implementation effort while maintaining all the functionality needed for user feedback and continuous improvement.