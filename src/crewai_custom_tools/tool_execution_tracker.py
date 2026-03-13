"""
Tool Execution Tracker

Wraps CrewAI tools to automatically capture execution details including
inputs, outputs, and timing information for display in the UI.
"""
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from crewai.tools import BaseTool

from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.BUSINESS)


class ToolExecutionTracker:
    """
    Tracks tool executions for a session and stores them in the database.
    
    This class provides a context for tracking all tool calls during
    an agent's execution, automatically capturing inputs, outputs, and timing.
    """
    
    def __init__(self, session_id: int, db_session, agent_name: Optional[str] = None):
        """
        Initialize the tool execution tracker.
        
        Args:
            session_id: Database ID of the analysis session
            db_session: SQLAlchemy database session
            agent_name: Name of the agent using the tools
        """
        self.session_id = session_id
        self.db = db_session
        self.agent_name = agent_name
        self.executions = []
    
    def wrap_tool(self, tool: BaseTool) -> BaseTool:
        """
        Wrap a tool to track its executions.
        
        Args:
            tool: The CrewAI tool to wrap
            
        Returns:
            A wrapped version of the tool that captures execution details
        """
        original_run = tool._run
        tracker = self
        
        def tracked_run(*args, **kwargs):
            """Wrapped _run method that captures execution details."""
            from src.services.business_intelligence_service import BusinessIntelligenceService
            
            # Capture input
            tool_input = {
                "args": [str(arg) for arg in args],
                "kwargs": {k: str(v) for k, v in kwargs.items()}
            }
            
            started_at = datetime.now(timezone.utc)
            start_time = time.time()
            
            try:
                # Execute the original tool
                result = original_run(*args, **kwargs)
                
                # Calculate duration
                duration_ms = int((time.time() - start_time) * 1000)
                completed_at = datetime.now(timezone.utc)
                
                # Parse result if it's JSON
                tool_output = None
                results_count = 0
                try:
                    parsed_result = json.loads(result) if isinstance(result, str) else result
                    tool_output = parsed_result
                    
                    # Try to extract results count
                    if isinstance(parsed_result, dict):
                        if "results_count" in parsed_result:
                            results_count = parsed_result["results_count"]
                        elif "results" in parsed_result and isinstance(parsed_result["results"], list):
                            results_count = len(parsed_result["results"])
                        elif "data" in parsed_result and isinstance(parsed_result["data"], list):
                            results_count = len(parsed_result["data"])
                except (json.JSONDecodeError, TypeError):
                    tool_output = {"raw_output": str(result)[:1000]}  # Limit output size
                
                # Store execution in database
                bi_service = BusinessIntelligenceService(tracker.db)
                execution = bi_service.create_tool_execution(
                    session_id=tracker.session_id,
                    tool_name=tool.name,
                    tool_input=tool_input,
                    tool_output=tool_output,
                    agent_name=tracker.agent_name,
                    status="success",
                    duration_ms=duration_ms,
                    results_count=results_count,
                    started_at=started_at,
                    completed_at=completed_at
                )
                
                tracker.executions.append(execution)
                
                logger.info(
                    "tool_execution_tracked",
                    tool_name=tool.name,
                    duration_ms=duration_ms,
                    results_count=results_count,
                    status="success"
                )
                
                return result
                
            except Exception as e:
                # Calculate duration even on failure
                duration_ms = int((time.time() - start_time) * 1000)
                completed_at = datetime.now(timezone.utc)
                
                # Store failed execution
                bi_service = BusinessIntelligenceService(tracker.db)
                execution = bi_service.create_tool_execution(
                    session_id=tracker.session_id,
                    tool_name=tool.name,
                    tool_input=tool_input,
                    tool_output=None,
                    agent_name=tracker.agent_name,
                    status="failed",
                    error_message=str(e),
                    duration_ms=duration_ms,
                    started_at=started_at,
                    completed_at=completed_at
                )
                
                tracker.executions.append(execution)
                
                logger.error(
                    "tool_execution_failed",
                    tool_name=tool.name,
                    error=str(e),
                    duration_ms=duration_ms
                )
                
                # Re-raise the exception
                raise
        
        # Replace the _run method
        tool._run = tracked_run
        return tool
    
    def get_executions(self):
        """Get all tracked executions."""
        return self.executions
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of tool executions.
        
        Returns:
            Dictionary with execution statistics
        """
        total = len(self.executions)
        successful = sum(1 for e in self.executions if e.status == "success")
        failed = sum(1 for e in self.executions if e.status == "failed")
        total_duration = sum(e.duration_ms or 0 for e in self.executions)
        
        tools_used = {}
        for execution in self.executions:
            tool_name = execution.tool_name
            if tool_name not in tools_used:
                tools_used[tool_name] = {
                    "count": 0,
                    "successful": 0,
                    "failed": 0,
                    "total_results": 0
                }
            tools_used[tool_name]["count"] += 1
            if execution.status == "success":
                tools_used[tool_name]["successful"] += 1
                tools_used[tool_name]["total_results"] += execution.results_count or 0
            else:
                tools_used[tool_name]["failed"] += 1
        
        return {
            "total_executions": total,
            "successful": successful,
            "failed": failed,
            "total_duration_ms": total_duration,
            "tools_used": tools_used
        }

