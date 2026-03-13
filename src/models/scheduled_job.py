"""
Scheduled Job Configuration Model

Stores configuration and execution history for Celery scheduled tasks.
This allows dynamic management of job schedules via the admin UI.
"""
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from src.models.database import BaseModel
import enum


class JobStatus(str, enum.Enum):
    """Status of a scheduled job's last execution."""
    IDLE = "idle"           # Never run
    RUNNING = "running"     # Currently executing
    SUCCESS = "success"     # Last run succeeded
    FAILED = "failed"       # Last run failed
    CANCELLED = "cancelled" # Run was cancelled


class ScheduledJobConfig(BaseModel):
    """
    Configuration for a scheduled Celery task.
    
    This table stores:
    - Schedule configuration (cron/interval)
    - Enabled/disabled state
    - Last execution status and timing
    - Error information for debugging
    """
    __tablename__ = "scheduled_job_configs"
    
    # Job identification
    job_name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    task_name = Column(String(255), nullable=False)  # Celery task name
    
    # Schedule configuration
    schedule_type = Column(String(20), default="interval", nullable=False)  # 'interval', 'cron'
    schedule_value = Column(String(100), nullable=False)  # e.g., "21600" (seconds) or "0 6 * * *" (cron)
    
    # State
    is_enabled = Column(Boolean, default=True, nullable=False)
    
    # Execution tracking
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_status = Column(String(20), default="idle", nullable=False)
    last_run_duration_seconds = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)
    last_task_id = Column(String(100), nullable=True)  # Celery task ID
    
    # Next scheduled run (calculated)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    
    # Audit
    updated_by_user_id = Column(Integer, nullable=True)
    
    def __repr__(self):
        return f"<ScheduledJobConfig(name='{self.job_name}', enabled={self.is_enabled}, status='{self.last_run_status}')>"
    
    def to_dict(self):
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "job_name": self.job_name,
            "display_name": self.display_name,
            "description": self.description,
            "task_name": self.task_name,
            "schedule_type": self.schedule_type,
            "schedule_value": self.schedule_value,
            "is_enabled": self.is_enabled,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_run_status": self.last_run_status,
            "last_run_duration_seconds": self.last_run_duration_seconds,
            "last_error": self.last_error,
            "last_task_id": self.last_task_id,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ScheduledJobExecution(BaseModel):
    """
    Execution history for scheduled jobs.
    
    Keeps a log of recent executions for debugging and monitoring.
    """
    __tablename__ = "scheduled_job_executions"
    
    job_name = Column(String(100), nullable=False, index=True)
    task_id = Column(String(100), nullable=False, index=True)  # Celery task ID
    
    # Timing
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Result
    status = Column(String(20), default="running", nullable=False)  # running, success, failed, cancelled
    error_message = Column(Text, nullable=True)
    error_traceback = Column(Text, nullable=True)
    
    # Metadata
    triggered_by = Column(String(50), default="scheduler", nullable=False)  # scheduler, manual, api
    triggered_by_user_id = Column(Integer, nullable=True)
    result_summary = Column(Text, nullable=True)  # JSON string with execution results
    
    def __repr__(self):
        return f"<ScheduledJobExecution(job='{self.job_name}', task='{self.task_id}', status='{self.status}')>"

