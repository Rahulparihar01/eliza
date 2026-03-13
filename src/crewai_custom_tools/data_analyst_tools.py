"""
CrewAI Tools for Data Analyst Flow

Tools that connect CrewAI agents to:
- Vanna SQL generation
- SQL execution
- Database operations (messages/conversations)
- Insights generation
- Conversational responses
"""
from typing import Any, Optional, Dict, List, Type
from crewai.tools import BaseTool
from pydantic import Field, BaseModel
import json

from src.services.vanna_service import VannaService
from src.services.data_analyst_service import DataAnalystService
from src.services.conversation_service import ConversationService
from src.services.conversation_context_manager import ConversationContextManager
from src.models.data_analyst import DataSourceType, DataAnalystTelemetryEventType
from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__, component="crewai.tools.data_analyst")


class DatabaseMessageToolInput(BaseModel):
    """Input schema for DatabaseMessageTool."""
    operation_json: str = Field(..., description="JSON string with operation and parameters")


class DatabaseMessageTool(BaseTool):
    """
    CrewAI tool for database message and conversation operations.
    
    Handles:
    - Creating/updating messages
    - Retrieving conversation context
    - Saving results
    """
    
    name: str = "Database Message Operations"
    description: str = """
    Save messages, retrieve conversation context, and update message results.
    
    Operations:
    - create_message: Create a new message record
    - get_conversation_context: Get conversation context for SQL generation
    - update_message_results: Update message with processing results
    - get_message: Retrieve a message by ID
    
    Input format: JSON string with operation and parameters.
    Example: '{"operation": "get_conversation_context", "conversation_id": "uuid"}'
    """
    args_schema: Type[BaseModel] = DatabaseMessageToolInput
    
    customer_id: Optional[str] = Field(None, description="Customer ID")
    user_id: Optional[int] = Field(None, description="User ID")
    
    def _get_db_session(self):
        """Get database session (create locally, never store in tool)"""
        from src.models import database
        
        if database.SessionLocal is None:
            database.init_database()
        
        return database.SessionLocal()
    
    def _run(self, **kwargs) -> str:
        """Execute database operation"""
        try:
            # Extract operation_json from kwargs (CrewAI 1.5.0 may pass as direct param)
            operation_json = kwargs.get('operation_json')
            
            if not operation_json:
                return json.dumps({"error": "operation_json parameter is required", "status": "failed"})
            
            operation = json.loads(operation_json) if isinstance(operation_json, str) else operation_json
            op_type = operation.get("operation")
            
            db = self._get_db_session()
            try:
                if op_type == "get_conversation_context":
                    conversation_id = operation.get("conversation_id")
                    if not conversation_id:
                        return json.dumps({"error": "conversation_id required"})
                    
                    conversation_service = ConversationService(db)
                    conversation = conversation_service.get_conversation(
                        conversation_id,
                        self.user_id or 0
                    )
                    
                    if not conversation:
                        return json.dumps({"error": "Conversation not found"})
                    
                    context_manager = ConversationContextManager(get_settings())
                    context = context_manager.get_conversation_context(conversation)
                    
                    return json.dumps({"context": context})
                
                elif op_type == "add_telemetry_event":
                    message_id = operation.get("message_id")
                    event_type = operation.get("event_type")
                    agent_name = operation.get("agent_name")
                    tool_name = operation.get("tool_name")
                    stage_name = operation.get("stage_name")
                    message = operation.get("message")
                    user_message = operation.get("user_message")
                    progress_percentage = operation.get("progress_percentage")
                    data = operation.get("data")
                    error_details = operation.get("error_details")
                    duration_ms = operation.get("duration_ms")
                    
                    # DEBUG: Log what we received
                    logger.info(
                        f"Telemetry event received",
                        message_id=message_id,
                        message_id_type=type(message_id).__name__,
                        message_id_repr=repr(message_id),
                        event_type=event_type,
                        stage_name=stage_name
                    )
                    
                    # Stronger validation: reject None, empty string, or string "None"
                    if not message_id or message_id == "None" or str(message_id).strip() == "":
                        logger.warning(
                            f"Telemetry event REJECTED: invalid message_id",
                            message_id=message_id,
                            message_id_type=type(message_id).__name__,
                            event_type=event_type,
                            stage_name=stage_name
                        )
                        return json.dumps({
                            "success": False, 
                            "skipped": True,
                            "reason": "Invalid message_id (None or empty)"
                        })
                    
                    if not event_type:
                        return json.dumps({"error": "event_type required"})
                    
                    logger.info(f"Telemetry event PASSED validation, inserting", message_id=message_id)
                    
                    service = DataAnalystService(db)
                    try:
                        telemetry = service.add_telemetry_event(
                            message_id=message_id,
                            event_type=DataAnalystTelemetryEventType(event_type),
                            agent_name=agent_name,
                            tool_name=tool_name,
                            stage_name=stage_name,
                            message=message,
                            user_message=user_message,
                            progress_percentage=progress_percentage,
                            data=data,
                            error_details=error_details,
                            duration_ms=duration_ms
                        )
                        return json.dumps({"success": True, "telemetry_id": telemetry.telemetry_id})
                    except Exception as e:
                        logger.error(f"Failed to add telemetry event: {e}", exc_info=True)
                        return json.dumps({"error": str(e)})
                
                elif op_type == "update_message_results":
                    message_id = operation.get("message_id")
                    result_data = operation.get("result_data")
                    result_metadata = operation.get("result_metadata")
                    status = operation.get("status", "completed")
                    generated_sql = operation.get("generated_sql")
                    conversational_response = operation.get("conversational_response")
                    
                    if not message_id:
                        return json.dumps({"error": "message_id required"})
                    
                    from src.models.data_analyst import DataAnalystMessage, DataAnalystQuestionStatus
                    from datetime import datetime
                    
                    message = db.query(DataAnalystMessage).filter(
                        DataAnalystMessage.message_id == message_id
                    ).first()
                    
                    if not message:
                        return json.dumps({"error": "Message not found"})
                    
                    # Update message with results
                    if result_data is not None:
                        message.result_data = result_data
                    if result_metadata is not None:
                        message.result_metadata = result_metadata
                    if generated_sql is not None:
                        message.generated_sql = generated_sql
                    if conversational_response is not None:
                        message.conversational_response = conversational_response
                    if status:
                        message.status = status
                    
                    message.completed_at = datetime.utcnow()
                    
                    # Update conversation last_activity_at if conversation exists
                    if message.conversation_id:
                        from src.models.data_analyst import DataAnalystConversation
                        conversation = db.query(DataAnalystConversation).filter(
                            DataAnalystConversation.conversation_id == message.conversation_id
                        ).first()
                        if conversation:
                            conversation.last_activity_at = datetime.utcnow()
                    
                    db.commit()
                    
                    return json.dumps({
                        "status": "success",
                        "message_id": message_id,
                        "updated_at": datetime.utcnow().isoformat()
                    })
                
                elif op_type == "update_message_status":
                    message_id = operation.get("message_id")
                    new_status = operation.get("new_status")
                    if not message_id or not new_status:
                        return json.dumps({"error": "message_id and new_status required"})
                    
                    from src.models.data_analyst import DataAnalystMessage
                    
                    message = db.query(DataAnalystMessage).filter(
                        DataAnalystMessage.message_id == message_id
                    ).first()
                    
                    if not message:
                        return json.dumps({"error": "Message not found"})
                    
                    old_status = message.status
                    message.status = new_status
                    
                    # Also update clarification_prompt if provided
                    clarification_prompt = operation.get("clarification_prompt")
                    if clarification_prompt:
                        message.clarification_prompt = clarification_prompt
                    
                    # Update detected_intent if provided
                    detected_intent = operation.get("detected_intent")
                    if detected_intent:
                        message.detected_intent = detected_intent
                    
                    # Update intent_confidence if provided  
                    intent_confidence = operation.get("intent_confidence")
                    if intent_confidence:
                        message.intent_confidence = intent_confidence
                    
                    db.commit()
                    
                    return json.dumps({
                        "message_id": message_id,
                        "old_status": old_status,
                        "new_status": new_status,
                        "clarification_prompt": clarification_prompt,
                        "status": "success"
                    })
                
                elif op_type == "get_message":
                    message_id = operation.get("message_id")
                    if not message_id:
                        return json.dumps({"error": "message_id required"})
                    
                    from src.models.data_analyst import DataAnalystMessage
                    
                    message = db.query(DataAnalystMessage).filter(
                        DataAnalystMessage.message_id == message_id
                    ).first()
                    
                    if not message:
                        return json.dumps({"error": "Message not found"})
                    
                    return json.dumps({
                        "message_id": message.message_id,
                        "original_question": message.original_question,
                        "message_type": message.message_type,
                        "status": message.status
                    })
                
                else:
                    return json.dumps({"error": f"Unknown operation: {op_type}"})
            
            finally:
                db.close()
        
        except Exception as e:
            logger.error(
                "database_message_tool_error",
                error=str(e),
                exc_info=True
            )
            return json.dumps({"error": str(e)})


class VannaSQLGenerationToolInput(BaseModel):
    """Input schema for VannaSQLGenerationTool."""
    question: str = Field(..., description="Natural language question to convert to SQL")
    conversation_context: Optional[str] = Field(None, description="Previous conversation context")
    message_id: Optional[str] = Field(None, description="Message ID for telemetry")


class VannaSQLGenerationTool(BaseTool):
    """
    CrewAI tool that wraps Vanna service for SQL generation.
    
    This tool connects CrewAI agents to Vanna AI for text-to-SQL generation.
    """
    
    name: str = "Generate SQL Query"
    description: str = """
    Generate SQL from natural language questions using Vanna AI.
    
    Use this tool when the user wants to query data (DATA_QUERY intent).
    
    Input: JSON string with keys: question (required), conversation_context (optional), message_id (optional)
    Output: Generated SQL query.
    
    Example input: {{"question": "What is the total premium collected in the last quarter?", "message_id": "123"}}
    """
    args_schema: Type[BaseModel] = VannaSQLGenerationToolInput
    
    data_source_type: Optional[str] = Field(None, description="Data source type (e.g., 'insurance')")
    
    def _get_vanna_service(self) -> VannaService:
        """Get Vanna service (lazy initialization)"""
        if not hasattr(self, '_vanna_service_instance'):
            settings = get_settings()
            
            if self.data_source_type == "insurance":
                db_url = settings.insurance_demo_db_url
            else:
                raise ValueError(f"Unsupported data source type: {self.data_source_type}")
            
            self._vanna_service_instance = VannaService(
                database_url=db_url,
                model="gpt-4o-mini"
            )
        
        return self._vanna_service_instance
    
    def _emit_sql_generation_event(self, message_id: str, event_type: str, **kwargs):
        """Helper to emit telemetry events via DatabaseMessageTool"""
        try:
            from src.models import database
            if database.SessionLocal is None:
                database.init_database()
            
            db = database.SessionLocal()
            try:
                service = DataAnalystService(db)
                from src.models.data_analyst import DataAnalystTelemetryEventType
                service.add_telemetry_event(
                    message_id=message_id,
                    event_type=DataAnalystTelemetryEventType(event_type),
                    **kwargs
                )
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to emit SQL generation telemetry event: {e}", exc_info=True)
    
    def _run(self, **kwargs) -> str:
        """
        Generate SQL using Vanna.
        
        Args:
            **kwargs: Can include question, conversation_context, message_id, or input_json
        
        Returns:
            JSON string with generated SQL
        """
        try:
            # DEBUG: Log what we actually receive
            logger.info(f"VannaSQLGenerationTool received kwargs: {kwargs}")
            logger.info(f"kwargs keys: {list(kwargs.keys())}")
            logger.info(f"kwargs types: {[(k, type(v).__name__) for k, v in kwargs.items()]}")
            
            # Extract parameters from kwargs
            input_json = kwargs.get('input_json')
            question = kwargs.get('question')
            conversation_context = kwargs.get('conversation_context')
            message_id = kwargs.get('message_id')
            
            # Handle both JSON string input and direct parameters
            # Prioritize direct parameters (CrewAI 1.5.0 behavior)
            if not question and input_json:
                try:
                    input_data = json.loads(input_json) if isinstance(input_json, str) else input_json
                    # Only use if it looks like valid data (has 'question' key)
                    if isinstance(input_data, dict) and 'question' in input_data:
                        question = input_data.get('question')
                        conversation_context = conversation_context or input_data.get('conversation_context')
                        message_id = message_id or input_data.get('message_id')
                except (json.JSONDecodeError, TypeError):
                    pass  # Ignore invalid JSON, use direct parameters
            
            if not question:
                return json.dumps({"error": "question parameter is required", "status": "failed"})
            
            # Emit SQL generation started event if message_id provided
            if message_id:
                self._emit_sql_generation_event(
                    message_id=message_id,
                    event_type="sql_generation_started",
                    tool_name="VannaSQLGenerationTool",
                    stage_name="SQL Generation",
                    user_message="Generating SQL query...",
                    progress_percentage=70
                )
            
            vanna_service = self._get_vanna_service()
            
            # Build enhanced question with context
            enhanced_question = question
            if conversation_context:
                enhanced_question = f"{conversation_context}\n\nQuestion: {question}"
            
            # Generate SQL
            sql = vanna_service.generate_sql(enhanced_question)
            
            # Emit SQL generation completed event if message_id provided
            if message_id:
                self._emit_sql_generation_event(
                    message_id=message_id,
                    event_type="sql_generation_completed",
                    tool_name="VannaSQLGenerationTool",
                    stage_name="SQL Generation",
                    user_message="SQL query generated successfully",
                    progress_percentage=75,
                    data={"sql_preview": sql[:200] + "..." if len(sql) > 200 else sql}
                )
            
            logger.info(
                "vanna_sql_generated",
                question_length=len(question),
                sql_length=len(sql)
            )
            
            return json.dumps({
                "sql": sql,
                "status": "success",
                "question": question
            })
        
        except Exception as e:
            logger.error(
                "vanna_sql_generation_failed",
                error=str(e),
                exc_info=True
            )
            return json.dumps({
                "error": str(e),
                "status": "failed"
            })


class SQLExecutorTool(BaseTool):
    """
    CrewAI tool for executing SQL queries safely.
    
    Executes SQL queries using Vanna service and returns results.
    """
    
    name: str = "Execute SQL Query"
    description: str = """
    Execute SQL queries and return results.
    
    Input: SQL query string (from VannaSQLGenerationTool)
    Output: Query results as JSON
    
    Example: "SELECT SUM(premium_amount) FROM auto_insurance.premium_transaction_auto WHERE transaction_date >= '2024-01-01'"
    """
    
    data_source_type: Optional[str] = Field(None, description="Data source type")
    
    def _get_vanna_service(self) -> VannaService:
        """Get Vanna service (lazy initialization)"""
        if not hasattr(self, '_vanna_service_instance'):
            settings = get_settings()
            
            if self.data_source_type == "insurance":
                db_url = settings.insurance_demo_db_url
            else:
                raise ValueError(f"Unsupported data source type: {self.data_source_type}")
            
            self._vanna_service_instance = VannaService(
                database_url=db_url,
                model="gpt-4o-mini"
            )
        
        return self._vanna_service_instance
    
    def _run(self, sql: str) -> str:
        """Execute SQL using Vanna"""
        try:
            vanna_service = self._get_vanna_service()
            
            # Execute SQL
            results = vanna_service.run_sql(sql)
            
            logger.info(
                "sql_executed",
                sql_length=len(sql),
                result_count=len(results) if results else 0
            )
            
            # Convert results to JSON-serializable format (handle datetime objects)
            def serialize_value(val):
                """Convert non-JSON-serializable values to strings."""
                from datetime import datetime, date
                from decimal import Decimal
                if isinstance(val, (datetime, date)):
                    return val.isoformat()
                elif isinstance(val, Decimal):
                    return float(val)
                return val
            
            serializable_results = []
            if results:
                for row in results:
                    if isinstance(row, dict):
                        serializable_results.append({k: serialize_value(v) for k, v in row.items()})
                    else:
                        serializable_results.append(row)
            
            # Return results as JSON
            return json.dumps({
                "results": serializable_results,
                "row_count": len(serializable_results) if serializable_results else 0,
                "status": "success"
            })
        
        except Exception as e:
            logger.error(
                "sql_execution_failed",
                error=str(e),
                exc_info=True
            )
            return json.dumps({
                "error": str(e),
                "status": "failed"
            })


class InsightsGenerationToolInput(BaseModel):
    """Input schema for InsightsGenerationTool."""
    results_json: str = Field(..., description="Query results as JSON string")
    question: str = Field(..., description="Original question asked by the user")


class InsightsGenerationTool(BaseTool):
    """
    CrewAI tool for generating insights from query results.
    
    Uses LLM to generate structured insights from data.
    """
    
    name: str = "Generate Insights"
    description: str = """
    Generate rich insights from SQL query results.
    
    Input: JSON string with keys: results_json (query results), question (original question)
    Output: Structured insights including executive summary, key findings, anomalies, recommendations
    
    Example input: {{"results_json": "{...}", "question": "What is the loss ratio?"}}
    """
    args_schema: Type[BaseModel] = InsightsGenerationToolInput
    
    def _run(self, **kwargs) -> str:
        """
        Generate insights from results.
        
        Args:
            **kwargs: Can include results_json, question, or input_json
        
        Returns:
            JSON string with insights
        """
        try:
            # Extract parameters from kwargs
            input_json = kwargs.get('input_json')
            results_json = kwargs.get('results_json')
            question = kwargs.get('question')
            
            # Handle both JSON string input and direct parameters
            # Prioritize direct parameters (CrewAI 1.5.0 behavior)
            if (not results_json or not question) and input_json:
                try:
                    input_data = json.loads(input_json) if isinstance(input_json, str) else input_json
                    # Only use if it looks like valid data
                    if isinstance(input_data, dict):
                        results_json = results_json or input_data.get('results_json')
                        question = question or input_data.get('question')
                except (json.JSONDecodeError, TypeError):
                    pass  # Ignore invalid JSON, use direct parameters
            
            if not results_json or not question:
                return json.dumps({
                    "error": "results_json and question are required",
                    "executive_summary": "Invalid input parameters."
                })
            
            results_data = json.loads(results_json) if isinstance(results_json, str) else results_json
            results = results_data.get("results", [])
            
            if not results:
                return json.dumps({
                    "executive_summary": "No data returned from query.",
                    "key_findings": [],
                    "anomalies": [],
                    "recommendations": []
                })
            
            # Use DataAnalystService for insights generation
            from src.models import database
            
            if database.SessionLocal is None:
                database.init_database()
            
            db = database.SessionLocal()
            try:
                service = DataAnalystService(db)
                insights = service._generate_insights(question, results)
                
                return json.dumps(insights)
            finally:
                db.close()
        
        except Exception as e:
            logger.error(
                "insights_generation_failed",
                error=str(e),
                exc_info=True
            )
            # Return error without fallback text - let the flow handle this properly
            return json.dumps({
                "status": "error",
                "error": f"Insights generation failed: {str(e)}"
            })


class ConversationalResponseToolInput(BaseModel):
    """Input schema for ConversationalResponseTool."""
    question: str = Field(..., description="User's question")
    conversation_context: Optional[str] = Field(None, description="Previous conversation context")


class ConversationalResponseTool(BaseTool):
    """
    CrewAI tool for generating conversational responses.
    
    Generates helpful responses for non-data questions (SOPs, documentation, etc.).
    """
    
    name: str = "Generate Conversational Response"
    description: str = """
    Generate helpful conversational responses for general questions.
    
    Use this for CONVERSATIONAL intent queries (SOPs, documentation, explanations).
    
    Input: JSON string with keys: question (required), conversation_context (optional)
    Output: Helpful conversational response
    
    Example input: {{"question": "What is the claims process?", "conversation_context": "..."}}
    """
    args_schema: Type[BaseModel] = ConversationalResponseToolInput
    
    def _run(self, **kwargs) -> str:
        """
        Generate conversational response.
        
        Args:
            **kwargs: Can include question, conversation_context, or input_json
        
        Returns:
            JSON string with response
        """
        try:
            # Extract parameters from kwargs
            input_json = kwargs.get('input_json')
            question = kwargs.get('question')
            conversation_context = kwargs.get('conversation_context')
            
            # Handle both JSON string input and direct parameters
            # Prioritize direct parameters (CrewAI 1.5.0 behavior)
            if not question and input_json:
                try:
                    input_data = json.loads(input_json) if isinstance(input_json, str) else input_json
                    # Only use if it looks like valid data
                    if isinstance(input_data, dict) and 'question' in input_data:
                        question = input_data.get('question')
                        conversation_context = conversation_context or input_data.get('conversation_context')
                except (json.JSONDecodeError, TypeError):
                    pass  # Ignore invalid JSON, use direct parameters
            
            if not question:
                return json.dumps({
                    "error": "question is required",
                    "response": "Invalid input parameters."
                })
            
            import litellm
            
            settings = get_settings()
            if not settings.openai_api_key:
                return json.dumps({
                    "error": "LLM not available",
                    "response": "I'm sorry, I cannot generate conversational responses at this time."
                })
            
            # Build enhanced question with context
            enhanced_question = question
            if conversation_context:
                enhanced_question = f"{conversation_context}\n\nQuestion: {question}"
            
            # Generate LLM response
            response = litellm.completion(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful data analyst assistant. Answer questions about processes, SOPs, and provide general guidance."
                    },
                    {
                        "role": "user",
                        "content": enhanced_question
                    }
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            conversational_response = response.choices[0].message.content
            
            return json.dumps({
                "response": conversational_response,
                "status": "success"
            })
        
        except Exception as e:
            logger.error(
                "conversational_response_failed",
                error=str(e),
                exc_info=True
            )
            return json.dumps({
                "error": str(e),
                "response": "I'm sorry, I encountered an error generating a response."
            })

