"""
Data Analyst Flow

CrewAI flow that orchestrates the complete data analyst conversation flow:
1. Intent Detection - Determine if question is DATA or CONVERSATIONAL
2. Clarification - Clarify ambiguous questions if needed
3. Confirmation - Confirm intent with user
4. Processing - Route to appropriate processing (SQL generation or conversational response)

This flow replaces direct LLM calls in IntentRouterService with CrewAI agents.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import uuid

from crewai import Agent, Task, Crew, LLM
from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory
from src.models.data_analyst import DataSourceType, MessageType
from src.services.langfuse_service import get_langfuse_service

logger = get_logger(__name__, LogCategory.BUSINESS)
settings = get_settings()


# Pydantic models for structured responses
class IntentResult(BaseModel):
    """Result of intent detection."""
    intent: str = Field(description="Intent type: 'data_query' or 'conversational'")
    confidence: str = Field(description="Confidence level: 'high', 'medium', or 'low'")
    clarification_needed: bool = Field(description="Whether clarification is needed")
    clarification_prompt: Optional[str] = Field(None, description="Clarification prompt if needed")
    clarified_question: Optional[str] = Field(None, description="Clarified question if auto-clarified")
    reasoning: Optional[str] = Field(None, description="Reasoning for intent detection")
    suggested_sql_hint: Optional[str] = Field(None, description="Hint for SQL generation if data_query")


class ClarificationResult(BaseModel):
    """Result of question clarification."""
    clarified_question: str = Field(description="The clarified question")
    intent_confirmed: bool = Field(description="Whether user confirmed intent")


class ConfirmationResult(BaseModel):
    """Result of intent confirmation."""
    confirmed: bool = Field(description="Whether user confirmed")
    corrected_question: Optional[str] = Field(None, description="Corrected question if user provided corrections")


# Flow State
class DataAnalystFlowState(BaseModel):
    """State maintained throughout the data analyst flow"""
    
    # Input
    message_id: str
    user_id: int
    customer_id: str
    conversation_id: Optional[str] = None
    original_question: str
    data_source_type: str
    
    # Step 1: Intent Detection
    detected_intent: Optional[str] = None  # "data_query" | "conversational"
    intent_confidence: Optional[str] = None  # "high" | "medium" | "low"
    clarification_needed: bool = False
    clarification_prompt: Optional[str] = None
    clarified_question: Optional[str] = None
    intent_reasoning: Optional[str] = None
    suggested_sql_hint: Optional[str] = None
    
    # Step 2: Clarification (if needed)
    clarification_response: Optional[str] = None
    clarification_complete: bool = False
    
    # Step 3: Confirmation
    confirmation_message: Optional[str] = None
    confirmation_response: Optional[str] = None
    intent_confirmed: bool = False
    
    # Step 4: Processing
    processing_result: Optional[Dict[str, Any]] = None
    message_type: Optional[str] = None  # "data" | "conversational"
    
    # Error handling
    error: Optional[str] = None
    
    # Metadata
    conversation_context: Optional[str] = None  # Previous conversation context


class DataAnalystFlow(Flow[DataAnalystFlowState]):
    """
    CrewAI Flow for Data Analyst conversation orchestration.
    
    Orchestrates:
    1. Intent Detection - Analyze question to determine type
    2. Clarification - Clarify ambiguous questions
    3. Confirmation - Confirm intent with user
    4. Processing - Route to appropriate processing
    """
    
    def __init__(self, initial_state: Optional[DataAnalystFlowState] = None):
        # Store initial_state before calling super().__init__()
        # CrewAI's Flow.__init__() will call _create_initial_state(), so we need to
        # set this before super().__init__() is called
        self._initial_state = initial_state
        
        # Initialize LLM for agents (before super().__init__() so it's available)
        self.llm = LLM(
            model=settings.default_llm_model,
            temperature=0.3,  # Lower for consistent intent detection
            base_url=settings.openai_api_base_url,
            api_key=settings.openai_api_key
        )
        
        # Now call super().__init__() which will call _create_initial_state()
        super().__init__()
        
        # Tools will be initialized lazily when state is available
        self._tools_initialized = False
        self.langfuse_service = get_langfuse_service()
        self.trace_id = self.langfuse_service.current_trace_id
    
    def _create_initial_state(self) -> DataAnalystFlowState:
        """Create initial state - use provided initial_state if available"""
        if hasattr(self, '_initial_state') and self._initial_state:
            return self._initial_state
        # Fallback to default (shouldn't happen in production, but needed for CrewAI initialization)
        return DataAnalystFlowState(
            message_id="",
            user_id=0,
            customer_id="",
            original_question="",
            data_source_type="insurance"
        )
    
    def _init_tools(self):
        """Initialize CrewAI tools (lazy initialization when state is available)"""
        if self._tools_initialized:
            return
        
        from src.crewai_custom_tools.data_analyst_tools import (
            DatabaseMessageTool,
            VannaSQLGenerationTool,
            SQLExecutorTool,
            InsightsGenerationTool,
            ConversationalResponseTool
        )
        
        # Initialize tools with context from state
        self.db_tool = DatabaseMessageTool(
            customer_id=self.state.customer_id,
            user_id=self.state.user_id
        )
        
        self.vanna_tool = VannaSQLGenerationTool(
            data_source_type=self.state.data_source_type
        )
        
        self.sql_executor_tool = SQLExecutorTool(
            data_source_type=self.state.data_source_type
        )
        
        self.insights_tool = InsightsGenerationTool()
        
        self.conversational_tool = ConversationalResponseTool()
        
        self._tools_initialized = True
    
    def _init_agents(self):
        """Initialize CrewAI agents"""
        
        # Initialize tools first (requires state)
        self._init_tools()
        
        # Agent 1: Intent Detection Agent
        self.intent_agent = Agent(
            role="Intent Detection Specialist",
            goal="Analyze user questions to determine if they require SQL/data retrieval (DATA_QUERY) or general conversation (CONVERSATIONAL). Also determine if clarification is needed.",
            backstory="""
            You are an expert at understanding user intent in data analysis contexts.
            You analyze questions to determine:
            1. Whether they need SQL/data retrieval (DATA_QUERY) or conversational response (CONVERSATIONAL)
            2. If the question is clear enough to proceed or needs clarification
            3. What clarification should be asked if needed
            
            You understand that:
            - Questions about numbers, metrics, data breakdowns → DATA_QUERY
            - Questions about processes, SOPs, explanations → CONVERSATIONAL
            - Vague questions like "show me data" → Need clarification
            """,
            tools=[],  # No tools needed - pure LLM analysis
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
        
        # Agent 2: Clarification Agent
        self.clarification_agent = Agent(
            role="Question Clarification Specialist",
            goal="Generate clarification prompts for ambiguous questions and refine questions based on user responses",
            backstory="""
            You help users clarify their questions when they're ambiguous or incomplete.
            You generate clear, specific clarification prompts that help users refine their questions.
            When users respond to clarification, you intelligently combine the original question
            with their clarification to create a clear, actionable question.
            """,
            tools=[],  # No tools needed
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
        
        # Agent 3: Confirmation Agent
        self.confirmation_agent = Agent(
            role="Intent Confirmation Specialist",
            goal="Generate confirmation messages and handle user confirmations or corrections",
            backstory="""
            You help confirm user intent before processing their questions.
            You generate clear confirmation messages that summarize what the system understood.
            You handle user responses (confirmations or corrections) gracefully.
            """,
            tools=[],  # No tools needed
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
        
        # Agent 4: Processing Router Agent
        self.router_agent = Agent(
            role="Data Processing Router",
            goal="Route confirmed questions to appropriate processing (SQL generation for DATA queries, conversational response for CONVERSATIONAL queries)",
            backstory="""
            You route confirmed questions to the right processing path.
            For DATA queries, you use Vanna to generate SQL, execute it, and generate insights.
            For CONVERSATIONAL queries, you generate helpful conversational responses.
            You ensure all results are properly formatted and stored.
            """,
            tools=[
                self.vanna_tool,
                self.sql_executor_tool,
                self.insights_tool,
                self.conversational_tool,
                self.db_tool
            ],
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
    
    def _update_message_status(self, new_status: str):
        """Update message status in database."""
        try:
            # Get message_id from state
            message_id = None
            if hasattr(self, 'state') and self.state:
                message_id = getattr(self.state, 'message_id', None)
            if not message_id and hasattr(self, '_state') and self._state:
                message_id = getattr(self._state, 'message_id', None)
            if not message_id and hasattr(self, '_initial_state') and self._initial_state:
                message_id = getattr(self._initial_state, 'message_id', None)
            
            if not message_id:
                logger.warning("Cannot update message status: message_id is None")
                return
            
            # Ensure tools are initialized
            if not hasattr(self, '_tools_initialized') or not self._tools_initialized:
                self._init_tools()
            
            # Update status via db_tool
            if hasattr(self, 'db_tool') and self.db_tool:
                import json
                update_data = {
                    "operation": "update_message_status",
                    "message_id": message_id,
                    "new_status": new_status
                }
                self.db_tool._run(operation_json=json.dumps(update_data))  # Pass as keyword argument
                logger.info(f"Message status updated to: {new_status} for message {message_id}")
            else:
                logger.warning("Cannot update message status: db_tool not initialized")
        except Exception as e:
            logger.error(f"Failed to update message status: {e}", exc_info=True)
    
    def _emit_telemetry_event(
        self,
        event_type: str,
        stage_name: Optional[str] = None,
        agent_name: Optional[str] = None,
        tool_name: Optional[str] = None,
        message: Optional[str] = None,
        user_message: Optional[str] = None,
        progress_percentage: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
        error_details: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None
    ):
        """Emit a telemetry event via DatabaseMessageTool."""
        try:
            # Get message_id from state - check both state and _state (CrewAI internal)
            message_id = None
            
            # Try to get from state property
            if hasattr(self, 'state') and self.state:
                message_id = getattr(self.state, 'message_id', None)
            
            # Try to get from _state (CrewAI internal)
            if not message_id and hasattr(self, '_state') and self._state:
                message_id = getattr(self._state, 'message_id', None)
            
            # Try to get from _initial_state if state not yet initialized
            if not message_id and hasattr(self, '_initial_state') and self._initial_state:
                message_id = getattr(self._initial_state, 'message_id', None)
            
            # CRITICAL: Return early if message_id is None or empty string
            if not message_id or message_id == "":
                logger.warning(
                    "Cannot emit telemetry event: message_id is None or empty",
                    event_type=event_type,
                    stage_name=stage_name,
                    has_state=hasattr(self, 'state'),
                    has_underscore_state=hasattr(self, '_state'),
                    has_initial_state=hasattr(self, '_initial_state')
                )
                return  # Early return - don't try to insert into database
            
            # Ensure tools are initialized before emitting telemetry
            if not hasattr(self, '_tools_initialized') or not self._tools_initialized:
                self._init_tools()
            
            # Only emit if db_tool is available
            if hasattr(self, 'db_tool') and self.db_tool:
                import json
                event_data = {
                    "operation": "add_telemetry_event",
                    "message_id": message_id,  # Keep as is - validation happens in tool
                    "event_type": event_type,
                    "agent_name": agent_name,
                    "tool_name": tool_name,
                    "stage_name": stage_name,
                    "message": message,
                    "user_message": user_message,
                    "progress_percentage": progress_percentage,
                    "data": data,
                    "error_details": error_details,
                    "duration_ms": duration_ms
                }
                result = self.db_tool._run(operation_json=json.dumps(event_data))  # Pass as keyword argument
                logger.debug(f"Telemetry event emitted: {event_type} for message {message_id}")
                try:
                    self.langfuse_service.trace_event(
                        name=f"agentmesh.data_analyst.{event_type}",
                        input_data={
                            "message_id": message_id,
                            "stage_name": stage_name,
                            "agent_name": agent_name,
                            "tool_name": tool_name,
                            "message": message,
                        },
                        output_data={"result": result},
                        metadata={
                            "component": "agentmesh",
                            "flow": "data_analyst",
                            "event_type": event_type,
                            "stage_name": stage_name,
                            "agent_name": agent_name,
                            "progress_percentage": progress_percentage,
                            "duration_ms": duration_ms,
                        },
                    )
                except Exception:
                    pass
            else:
                logger.warning(
                    "Cannot emit telemetry event: db_tool not initialized",
                    event_type=event_type,
                    message_id=message_id
                )
        except Exception as e:
            logger.error(f"Failed to emit telemetry event: {e}", exc_info=True)
    
    def _validate_domain_relevance(self) -> bool:
        """
        Validate that the question is relevant to the selected domain.
        
        Supports:
        - Insurance: policies, claims, premiums, loss ratios
        - FASB: Accounting Standards Codification, ASC topics, GAAP
        
        Returns:
            True if relevant, False if not (sets error in state)
        """
        try:
            from litellm import completion
            import json
            
            # Get domain-specific validation config
            domain_config = self._get_domain_validation_config()
            
            validation_prompt = f"""You are a domain validator for a {domain_config['domain_name']} system.

Your task: Determine if the following question is relevant to {domain_config['domain_description']}.

Question: "{self.state.original_question}"

{domain_config['domain_details']}

Respond with ONLY a JSON object:
{{
  "is_relevant": true/false,
  "reason": "Brief explanation",
  "suggested_clarification": "If partially relevant, suggest how to clarify the question"
}}

Examples of RELEVANT questions:
{domain_config['relevant_examples']}

Examples of NOT RELEVANT questions:
- "What's the weather today?"
- "Tell me about quantum physics"
- "How do I cook pasta?"
            """
            
            settings = get_settings()
            
            response = completion(
                model=settings.default_llm_model,
                messages=[{"role": "user", "content": validation_prompt}],
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            
            if not result.get("is_relevant", False):
                # Question is not relevant to domain
                reason = result.get('reason', f'This question does not appear to be about {domain_config["domain_name"]}')
                suggested_clarification = result.get(
                    "suggested_clarification",
                    domain_config['fallback_clarification']
                )
                
                # Create user-friendly error message
                user_friendly_error = f"I'm sorry, but I can only answer questions about {domain_config['domain_name']}. {reason}. {suggested_clarification}"
                
                self.state.error = user_friendly_error
                self.state.clarification_prompt = suggested_clarification
                
                # Save user-friendly error to database (so frontend displays it clearly)
                self._update_message_with_error(user_friendly_error)
                
                # Emit telemetry event for failed validation
                domain_name = domain_config['domain_name']
                rejection_reason = result.get('reason', f'Not relevant to {domain_name}')
                self._emit_telemetry_event(
                    event_type="domain_validation_failed",
                    stage_name="Domain Validation",
                    user_message=f"Question rejected: {rejection_reason}",
                    progress_percentage=5,
                    data={"reason": result.get("reason"), "suggested_clarification": result.get("suggested_clarification")}
                )
                
                logger.warning(
                    "domain_validation_failed",
                    message_id=self.state.message_id,
                    question=self.state.original_question,
                    reason=result.get("reason"),
                    domain=self.state.data_source_type
                )
                
                return False
            
            # Emit telemetry event for successful validation
            self._emit_telemetry_event(
                event_type="domain_validation_passed",
                stage_name="Domain Validation",
                user_message=f"Question validated - relevant to {domain_config['domain_name']}",
                progress_percentage=5
            )
            
            logger.info(
                "domain_validation_passed",
                message_id=self.state.message_id,
                question=self.state.original_question,
                domain=self.state.data_source_type
            )
            return True
            
        except Exception as e:
            logger.error(f"Domain validation failed with error: {e}", exc_info=True)
            # On validation error, REJECT the question (fail closed for safety)
            domain_config = self._get_domain_validation_config()
            user_friendly_error = f"I'm sorry, I can only answer questions about {domain_config['domain_name']}. Please ask a question related to this domain."
            internal_error_msg = f"Domain validation error: {str(e)}"
            
            self.state.error = user_friendly_error
            self.state.clarification_prompt = domain_config['fallback_clarification']
            self._update_message_with_error(internal_error_msg)
            return False
    
    def _get_domain_validation_config(self) -> Dict[str, Any]:
        """Get domain-specific validation configuration."""
        domain = self.state.data_source_type.lower() if self.state.data_source_type else "insurance"
        
        if domain == "fasb":
            return {
                "domain_name": "FASB Accounting Standards",
                "domain_description": "FASB Accounting Standards Codification (ASC) and GAAP",
                "domain_details": """FASB/ASC data includes:
- Accounting Standards Codification (ASC) topics
- GAAP (Generally Accepted Accounting Principles)
- Revenue recognition (ASC 606)
- Lease accounting (ASC 842)
- Financial instruments and fair value
- Consolidation and equity method
- Business combinations
- Income taxes
- Stock compensation
- Presentation and disclosure requirements""",
                "relevant_examples": """- "What are the revenue recognition criteria under ASC 606?"
- "How should we account for operating leases under ASC 842?"
- "What are the disclosure requirements for fair value measurements?"
- "When should we consolidate a variable interest entity?"
- "How do we recognize stock-based compensation expense?"
- "What is the guidance for business combinations under ASC 805?"
- "How do we account for income tax uncertainties?"
- "What are the impairment testing requirements for goodwill?"
- "How do we present discontinued operations?"
- "What is the definition of a contract under ASC 606?"
- "How do we account for modifications to debt arrangements?"
- "What are the hedge accounting requirements?"
- "How do we recognize deferred tax assets and liabilities?"
- "What is the guidance for segment reporting?"
- "How do we account for contingent liabilities?"
""",
                "fallback_clarification": "I can help you with FASB Accounting Standards Codification (ASC) topics, GAAP guidance, revenue recognition, lease accounting, financial instruments, and other accounting standards. Please ask a question related to accounting standards."
            }
        else:
            # Default: Insurance domain
            return {
                "domain_name": "insurance data",
                "domain_description": "insurance data analysis",
                "domain_details": """Insurance data includes:
- Auto and property insurance policies
- Claims, loss ratios, and incurred amounts
- Premiums, coverage, and deductibles
- Policyholders, states, and risk factors
- Policy effective dates, renewals, and terms""",
                "relevant_examples": """- "What is our loss ratio by state?"
- "How many auto policies do we have?"
- "Show me high-risk policyholders"
- "What's the total premium by line of business?"
- "Show me claims trends over time"
""",
                "fallback_clarification": "I can help you analyze insurance data including policies, claims, premiums, loss ratios, and policyholders. Please ask a question related to insurance data."
            }
    
    def _update_message_with_error(self, error_msg: str):
        """Save error message to database."""
        try:
            # Ensure tools are initialized
            if not hasattr(self, '_tools_initialized') or not self._tools_initialized:
                self._init_tools()
            
            if hasattr(self, 'db_tool') and self.db_tool:
                import json
                update_data = {
                    "operation": "update_message_status",
                    "message_id": self.state.message_id,
                    "new_status": "failed",
                    "sql_error": error_msg
                }
                # Add clarification if available
                if hasattr(self.state, 'clarification_question') and self.state.clarification_question:
                    update_data["clarification_question"] = self.state.clarification_question
                
                self.db_tool._run(operation_json=json.dumps(update_data))  # Pass as keyword argument
                logger.info(f"Error saved to database for message {self.state.message_id}")
        except Exception as e:
            logger.error(f"Failed to save error to database: {e}", exc_info=True)
    
    def _extract_and_save_results(self, crew, crew_result) -> bool:
        """
        Extract tool outputs from crew execution and FORCE SAVE to database.
        
        This is critical - we NEVER rely on agents to call database save tools.
        Instead, we parse the crew's execution results and extract:
        - Generated SQL
        - Query results (columns, rows, row_count)
        - Insights metadata
        
        Then we directly call the database save operation via Python code.
        
        Returns:
            True if results were successfully extracted and saved, False otherwise
        """
        try:
            import json
            
            # Initialize variables to collect from crew execution
            generated_sql = None
            result_data = None
            result_metadata = None
            conversational_response = None
            
            # Try to extract tool outputs from crew tasks
            if hasattr(crew_result, 'tasks_output') and crew_result.tasks_output:
                for task_output in crew_result.tasks_output:
                    # Look for tool outputs in the task
                    if hasattr(task_output, 'agent') and hasattr(task_output.agent, 'tools'):
                        # Check if any tools were called
                        logger.debug(f"Task output has {len(task_output.agent.tools)} tools available")
            
            # FALLBACK: Parse crew logs/output for tool results
            # CrewAI logs tool inputs and outputs - we can parse these
            crew_output_str = str(crew_result.raw)
            
            # Try to extract JSON-like patterns from output
            # Look for SQL generation tool output
            if '"sql"' in crew_output_str or '"generated_sql"' in crew_output_str:
                # Try to find SQL in the output
                import re
                sql_patterns = [
                    r'"sql":\s*"([^"]+)"',
                    r'"generated_sql":\s*"([^"]+)"',
                    r'WITH\s+\w+\s+AS\s+\([^)]+\)',  # CTE pattern
                    r'SELECT\s+.+?FROM\s+\w+',  # Basic SELECT pattern
                ]
                for pattern in sql_patterns:
                    match = re.search(pattern, crew_output_str, re.IGNORECASE | re.DOTALL)
                    if match:
                        if pattern.startswith('"'):
                            generated_sql = match.group(1)
                        else:
                            generated_sql = match.group(0)
                        logger.info(f"Extracted SQL from crew output (pattern: {pattern[:20]}...)")
                        break
            
            # For DATA queries, we need SQL and results
            if self.state.message_type == "data":
                if not generated_sql:
                    logger.warning("No SQL found in crew output for DATA query")
                    # Try to re-generate SQL directly as fallback
                    generated_sql = self._fallback_generate_sql()
                
                if generated_sql:
                    # Execute SQL directly to get results
                    result_data, result_metadata = self._execute_sql_and_generate_insights(generated_sql)
                
                if not result_data or not result_metadata:
                    logger.error("Failed to get results and insights for DATA query")
                    return False
                    
            else:  # CONVERSATIONAL query
                # For conversational queries, the result is the response text
                conversational_response = crew_result.raw
                result_data = {"response": conversational_response}
                result_metadata = {}
            
            # NOW FORCE SAVE TO DATABASE using direct Python code (not relying on agent)
            logger.info(f"Force-saving results to database for message_id={self.state.message_id}")
            
            if not hasattr(self, '_tools_initialized') or not self._tools_initialized:
                self._init_tools()
            
            if hasattr(self, 'db_tool') and self.db_tool:
                save_data = {
                    "operation": "update_message_results",
                    "message_id": self.state.message_id,
                    "result_data": result_data,
                    "result_metadata": result_metadata,
                    "status": "completed"
                }
                
                if generated_sql:
                    save_data["generated_sql"] = generated_sql
                if conversational_response:
                    save_data["conversational_response"] = conversational_response
                
                save_result = self.db_tool._run(operation_json=json.dumps(save_data))  # Pass as keyword argument
                logger.info(f"Database save completed: {save_result[:200] if save_result else 'success'}")
                
                # Verify the save worked
                return self._verify_save_success()
            else:
                logger.error("Cannot save: db_tool not initialized")
                return False
                
        except Exception as e:
            logger.error(f"Failed to extract and save results: {e}", exc_info=True)
            return False
    
    def _fallback_generate_sql(self) -> Optional[str]:
        """Fallback: Generate SQL directly if crew didn't produce it."""
        try:
            logger.info("Attempting fallback SQL generation")
            if hasattr(self, 'vanna_tool') and self.vanna_tool:
                import json
                result = self.vanna_tool._run(
                    question=self.state.original_question,
                    conversation_context=self.state.conversation_context or "",
                    message_id=self.state.message_id
                )
                result_data = json.loads(result)
                if result_data.get("status") == "success":
                    return result_data.get("sql")
        except Exception as e:
            logger.error(f"Fallback SQL generation failed: {e}", exc_info=True)
        return None
    
    def _execute_sql_and_generate_insights(self, sql: str) -> tuple:
        """Execute SQL and generate insights directly."""
        try:
            import json
            
            # Execute SQL
            if not hasattr(self, 'sql_executor_tool'):
                logger.error("SQL executor tool not available")
                return None, None
            
            exec_result = self.sql_executor_tool._run(sql=sql)
            exec_data = json.loads(exec_result)
            
            if exec_data.get("status") != "success":
                logger.error(f"SQL execution failed: {exec_data.get('error')}")
                return None, None
            
            # Extract results (array of dicts from ExecuteSQLQueryTool)
            results = exec_data.get("results", [])
            
            # Convert dict results to columns + rows format for frontend
            columns = []
            rows = []
            if results:
                # Extract column names from first result dict
                if isinstance(results[0], dict):
                    columns = list(results[0].keys())
                    # Convert each dict to array of values in same order as columns
                    for result_dict in results:
                        row = [result_dict.get(col) for col in columns]
                        rows.append(row)
                else:
                    # If results are already arrays, use them directly
                    rows = results
            
            # Format result_data with proper structure
            result_data = {
                "columns": columns,
                "rows": rows,
                "row_count": len(rows)
            }
            
            logger.info(
                f"Formatted SQL results: {len(columns)} columns, {len(rows)} rows",
                columns=columns,
                sample_row=rows[0] if rows else None
            )
            
            # If no results, generate helpful guidance about available data
            if len(rows) == 0:
                logger.info("Query returned 0 rows - generating guidance about available data")
                return self._generate_no_data_guidance(sql, self.state.original_question)
            
            # Generate insights
            if hasattr(self, 'insights_tool') and self.insights_tool:
                insights_result = self.insights_tool._run(
                    results_json=json.dumps(exec_data),
                    question=self.state.original_question
                )
                insights_data = json.loads(insights_result)
                
                # Check if insights generation failed
                if insights_data.get("status") == "error":
                    error_msg = insights_data.get("error", "Unknown error during insights generation")
                    logger.error(
                        "Insights generation tool returned error",
                        error=error_msg,
                        insights_data=insights_data
                    )
                    raise ValueError(error_msg)
                
                # InsightsGenerationTool returns the insights dict directly
                # Expected fields: summary, key_findings, statistics, chart_suggestions, anomalies, recommendations
                if "summary" in insights_data or "executive_summary" in insights_data:
                    # Valid insights returned
                    result_metadata = insights_data
                    result_metadata["sql"] = sql  # Add SQL to metadata
                    
                    # Handle both old "executive_summary" and new "summary" fields
                    summary_text = insights_data.get("summary") or insights_data.get("executive_summary")
                    
                    logger.info(
                        "Generated insights with summary",
                        summary_length=len(summary_text) if summary_text else 0,
                        has_findings=bool(insights_data.get("key_findings")),
                        has_charts=bool(insights_data.get("chart_suggestions"))
                    )
                else:
                    # Insights generation failed - this should not happen with our improved prompt
                    # Log error and raise to trigger proper error handling
                    logger.error(
                        "Insights generation returned unexpected format - missing summary field",
                        insights_keys=list(insights_data.keys()),
                        insights_data=insights_data
                    )
                    raise ValueError("Insights generation failed: missing summary field")
            else:
                # No insights tool available - this should not happen in production
                logger.error("Insights tool not available")
                raise ValueError("Insights tool not initialized")
            
            return result_data, result_metadata
            
        except Exception as e:
            logger.error(f"Failed to execute SQL and generate insights: {e}", exc_info=True)
            return None, None
    
    def _generate_no_data_guidance(self, sql: str, question: str) -> tuple:
        """Generate helpful guidance when query returns no data."""
        try:
            import json
            from litellm import completion
            
            settings = get_settings()
            
            # Query database for available data ranges
            logger.info("Querying database for available data ranges")
            
            # Get date ranges from auto_insurance policies
            auto_date_query = """
            SELECT 
                MIN(effective_date) as min_date,
                MAX(effective_date) as max_date,
                COUNT(*) as policy_count
            FROM auto_insurance.policy_auto
            """
            
            # Get date ranges from property_insurance policies
            property_date_query = """
            SELECT 
                MIN(effective_date) as min_date,
                MAX(effective_date) as max_date,
                COUNT(*) as policy_count
            FROM property_insurance.policy_property
            """
            
            # Execute queries to get available data info
            available_data = {}
            
            if hasattr(self, 'sql_executor_tool'):
                try:
                    auto_result = self.sql_executor_tool._run(sql=auto_date_query)
                    auto_data = json.loads(auto_result)
                    if auto_data.get("status") == "success" and auto_data.get("results"):
                        auto_info = auto_data["results"][0]
                        available_data["auto_insurance"] = {
                            "min_date": auto_info.get("min_date"),
                            "max_date": auto_info.get("max_date"),
                            "policy_count": auto_info.get("policy_count")
                        }
                    
                    property_result = self.sql_executor_tool._run(sql=property_date_query)
                    property_data = json.loads(property_result)
                    if property_data.get("status") == "success" and property_data.get("results"):
                        prop_info = property_data["results"][0]
                        available_data["property_insurance"] = {
                            "min_date": prop_info.get("min_date"),
                            "max_date": prop_info.get("max_date"),
                            "policy_count": prop_info.get("policy_count")
                        }
                except Exception as e:
                    logger.warning(f"Could not fetch available data ranges: {e}")
            
            # Use LLM to generate helpful guidance
            guidance_prompt = f"""You are helping a user who asked a question about insurance data, but the query returned no results.

User's Question: "{question}"

Generated SQL Query:
{sql}

Available Data in System:
{json.dumps(available_data, indent=2, default=str)}

Your task: Generate a helpful, conversational response that:
1. Acknowledges their question
2. Explains why no data was found (e.g., no data for that time period, no matching criteria)
3. Clearly states what data IS available in the system (date ranges, policy counts)
4. Suggests alternative questions or asks for clarification if their intent was different
5. Be specific about date ranges if that's the issue

Keep the tone friendly and helpful. Use clear formatting with line breaks.

Respond with ONLY a JSON object:
{{
  "summary": "Your full conversational response explaining the situation and offering guidance",
  "key_findings": ["List of specific findings about what data exists"],
  "recommendations": ["Suggestions for alternative questions the user could ask"],
  "statistics": {{"available_auto_policies": count, "available_property_policies": count, "date_range": "YYYY-MM-DD to YYYY-MM-DD"}}
}}
"""
            
            response = completion(
                model=settings.default_llm_model,
                messages=[{"role": "user", "content": guidance_prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            guidance_text = response.choices[0].message.content
            guidance_data = json.loads(guidance_text)
            
            # Format as result_data (empty results) and result_metadata (with guidance)
            result_data = {
                "columns": [],
                "rows": [],
                "row_count": 0
            }
            
            result_metadata = {
                "sql": sql,
                "summary": guidance_data.get("summary", "No data found for this query."),
                "key_findings": guidance_data.get("key_findings", []),
                "recommendations": guidance_data.get("recommendations", []),
                "statistics": guidance_data.get("statistics", {}),
                "chart_suggestions": [],  # No charts for empty data
                "anomalies": [],
                "no_data": True  # Flag to indicate this is a no-data response
            }
            
            logger.info(
                "Generated no-data guidance",
                summary_length=len(result_metadata["summary"]),
                has_recommendations=len(result_metadata["recommendations"]) > 0
            )
            
            return result_data, result_metadata
            
        except Exception as e:
            logger.error(f"Failed to generate no-data guidance: {e}", exc_info=True)
            
            # Fallback response if guidance generation fails
            result_data = {
                "columns": [],
                "rows": [],
                "row_count": 0
            }
            
            result_metadata = {
                "sql": sql,
                "summary": (
                    "I couldn't find any data matching your question. This might be because:\n\n"
                    "• The time period you asked about doesn't have data yet\n"
                    "• The specific criteria didn't match any records\n"
                    "• The combination of filters was too restrictive\n\n"
                    "Could you try rephrasing your question or asking about a different time period?"
                ),
                "key_findings": [],
                "recommendations": ["Try asking about a different time period", "Simplify your question"],
                "statistics": {},
                "chart_suggestions": [],
                "anomalies": [],
                "no_data": True
            }
            
            return result_data, result_metadata
    
    
    def _verify_save_success(self) -> bool:
        """Verify that results were actually saved to database."""
        try:
            from src.models import database
            if database.SessionLocal is None:
                database.init_database()
            db = database.SessionLocal()
            try:
                from src.models.data_analyst import DataAnalystMessage
                msg = db.query(DataAnalystMessage).filter(
                    DataAnalystMessage.message_id == self.state.message_id
                ).first()
                
                if not msg:
                    logger.error(f"Message not found in database: {self.state.message_id}")
                    return False
                
                if msg.status != 'completed':
                    logger.error(f"Message status is '{msg.status}', not 'completed'")
                    return False
                
                if not msg.result_data:
                    logger.error(f"Message result_data is empty")
                    return False
                
                logger.info(f"Verified: Results successfully saved for message {self.state.message_id}")
                return True
                
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to verify save: {e}", exc_info=True)
            return False
    
    @start()
    def detect_intent(self):
        """
        Step 1: Validate domain relevance and detect intent.
        
        First validates the question is relevant to the selected domain, then analyzes:
        - Intent type (DATA_QUERY vs CONVERSATIONAL)
        - Confidence level
        - Whether clarification is needed
        
        For FASB domain: Skip intent detection and go straight to RAG processing.
        """
        # Update message status to "processing" so frontend shows real-time updates
        self._update_message_status("processing")
        
        # FASB domain: Skip ALL validation and intent detection - go straight to RAG
        # Handle both enum value ("fasb") and potential enum string representation
        # MUST be before domain validation to avoid SQL clarification prompt
        data_source_lower = (self.state.data_source_type or "").lower()
        is_fasb = data_source_lower == "fasb" or data_source_lower.endswith(".fasb") or "fasb" in data_source_lower
        
        if is_fasb:
            logger.info(
                "fasb_domain_skip_all_validation",
                message_id=self.state.message_id,
                data_source_type=self.state.data_source_type,
                reason="FASB uses RAG, not SQL - skip all validation and intent detection"
            )
            # Set state for direct RAG processing
            self.state.detected_intent = "data_query"
            self.state.intent_confidence = "high"
            self.state.clarification_needed = False
            self.state.message_type = "data"  # Will be routed to FASB RAG in process_question
            return self.state
        
        # STEP 1A: Domain validation - Ensure question is relevant to selected domain (non-FASB only)
        if not self._validate_domain_relevance():
            return  # Error set in state, flow will stop
        
        # Initialize agents (which will initialize tools)
        self._init_agents()
        
        # Emit flow started event
        self._emit_telemetry_event(
            event_type="flow_started",
            stage_name="Flow",
            user_message="Starting data analyst flow...",
            progress_percentage=0
        )
        
        # Emit intent detection started event
        self._emit_telemetry_event(
            event_type="intent_detection_started",
            stage_name="Intent Detection",
            agent_name="Intent Detection Specialist",
            user_message="Analyzing question to determine intent...",
            progress_percentage=10
        )
        
        logger.info(
            "data_analyst_flow_intent_detection_started",
            message_id=self.state.message_id,
            question_length=len(self.state.original_question)
        )
        
        try:
            # Build conversation context if available
            context_prompt = ""
            if self.state.conversation_context:
                context_prompt = f"\n\nConversation Context:\n{self.state.conversation_context}"
            
            # Create intent detection task
            intent_task = Task(
                description=f"""
                Analyze this user question and determine:
                1. Intent: Does this require SQL/data retrieval (DATA_QUERY) or is it a general question (CONVERSATIONAL)?
                2. Clarity: Is the question clear enough to proceed, or does it need clarification?
                3. If DATA_QUERY: What data/tables might be needed? (suggested_sql_hint)
                4. If unclear: What clarification should be asked? (clarification_prompt)
                
                User Question: {self.state.original_question}
                {context_prompt}
                
                Respond with structured JSON matching IntentResult schema:
                {{
                    "intent": "data_query" | "conversational",
                    "confidence": "high" | "medium" | "low",
                    "clarification_needed": true/false,
                    "clarification_prompt": "question to ask user if clarification needed, null otherwise",
                    "clarified_question": "rephrased question if auto-clarified, null otherwise",
                    "reasoning": "brief explanation of why this intent was detected",
                    "suggested_sql_hint": "hint for SQL generation if data_query, null otherwise"
                }}
                """,
                agent=self.intent_agent,
                expected_output="Structured JSON with intent detection results"
            )
            
            # Create crew and execute
            crew = Crew(
                agents=[self.intent_agent],
                tasks=[intent_task],
                verbose=True
            )
            with self.langfuse_service.span_scope(
                name="agentmesh.data_analyst.intent_detection",
                input_data={
                    "message_id": self.state.message_id,
                    "question": self.state.original_question,
                },
                metadata={
                    "component": "agentmesh",
                    "flow": "data_analyst",
                    "stage": "intent_detection",
                    "customer_id": self.state.customer_id,
                },
                trace_id=self.trace_id,
            ) as span_info:
                result = crew.kickoff()
                observation = span_info.get("observation")
                if observation is not None:
                    try:
                        observation.update(
                            output={"raw_result": getattr(result, "raw", str(result))}
                        )
                    except Exception:
                        pass
            
            # Parse result (crew returns text, need to extract JSON)
            intent_result = self._parse_intent_result(result.raw)
            
            # Update state
            self.state.detected_intent = intent_result.intent
            self.state.intent_confidence = intent_result.confidence
            self.state.clarification_needed = intent_result.clarification_needed
            self.state.clarification_prompt = intent_result.clarification_prompt
            self.state.clarified_question = intent_result.clarified_question
            self.state.intent_reasoning = intent_result.reasoning
            self.state.suggested_sql_hint = intent_result.suggested_sql_hint
            
            # Map intent to message type
            if intent_result.intent == "data_query":
                self.state.message_type = MessageType.DATA.value
            else:
                self.state.message_type = MessageType.CONVERSATIONAL.value
            
            # Emit intent detection completed event
            self._emit_telemetry_event(
                event_type="intent_detection_completed",
                stage_name="Intent Detection",
                agent_name="Intent Detection Specialist",
                user_message=f"Intent detected: {intent_result.intent} ({intent_result.confidence} confidence)",
                progress_percentage=25,
                data={
                    "intent": intent_result.intent,
                    "confidence": intent_result.confidence,
                    "clarification_needed": intent_result.clarification_needed,
                    "message_type": self.state.message_type
                }
            )
            
            logger.info(
                "data_analyst_flow_intent_detected",
                message_id=self.state.message_id,
                intent=intent_result.intent,
                confidence=intent_result.confidence,
                clarification_needed=intent_result.clarification_needed
            )
            
            return self.state
            
        except Exception as e:
            logger.error(
                "data_analyst_flow_intent_detection_failed",
                message_id=self.state.message_id,
                error=str(e),
                exc_info=True
            )
            self.state.error = f"Intent detection failed: {str(e)}"
            return self.state
    
    @listen(detect_intent)
    def check_clarification(self, state):
        """
        Step 2: Check if clarification is needed and STOP EARLY if so.
        
        If clarification is needed:
        - Update message status to 'clarification_needed'
        - Store clarification prompt in database
        - STOP the flow (don't continue to processing)
        
        The user will respond with clarification, which creates a NEW message
        with the original context + clarification combined.
        """
        # Skip if there was an error in previous step (e.g., domain validation failed)
        if self.state.error:
            logger.info(
                "data_analyst_flow_clarification_check_skipped",
                message_id=self.state.message_id,
                reason="error_in_previous_step"
            )
            return self.state
        
        # If no clarification needed, continue to next step
        if not self.state.clarification_needed:
            logger.info(
                "data_analyst_flow_clarification_not_needed",
                message_id=self.state.message_id,
                reason="question_is_clear"
            )
            return self.state
        
        # CLARIFICATION IS NEEDED - Stop the flow here
        logger.info(
            "data_analyst_flow_clarification_needed",
            message_id=self.state.message_id,
            clarification_prompt=self.state.clarification_prompt
        )
        
        # Emit clarification needed event
        self._emit_telemetry_event(
            event_type="clarification_needed",
            stage_name="Clarification Check",
            agent_name="Intent Detection Specialist",
            user_message="Question needs clarification before processing",
            progress_percentage=25,
            data={
                "clarification_prompt": self.state.clarification_prompt,
                "original_question": self.state.original_question
            }
        )
        
        # Update message status to 'clarification_needed' and save the prompt
        self._save_clarification_needed()
        
        # Set error to stop flow progression (not a real error, just flow control)
        # This prevents the flow from continuing to confirm_intent and process_question
        self.state.error = "CLARIFICATION_NEEDED"
        
        logger.info(
            "data_analyst_flow_stopped_for_clarification",
            message_id=self.state.message_id,
            clarification_prompt=self.state.clarification_prompt
        )
        
        return self.state
    
    def _save_clarification_needed(self):
        """Save clarification_needed status and prompt to database."""
        try:
            # Ensure tools are initialized
            if not hasattr(self, '_tools_initialized') or not self._tools_initialized:
                self._init_tools()
            
            if hasattr(self, 'db_tool') and self.db_tool:
                import json
                update_data = {
                    "operation": "update_message_status",
                    "message_id": self.state.message_id,
                    "new_status": "clarification_needed",
                    "clarification_prompt": self.state.clarification_prompt,
                    "detected_intent": self.state.detected_intent,
                    "intent_confidence": self.state.intent_confidence
                }
                self.db_tool._run(operation_json=json.dumps(update_data))
                logger.info(
                    "clarification_needed_saved",
                    message_id=self.state.message_id,
                    clarification_prompt=self.state.clarification_prompt
                )
            else:
                logger.warning("Cannot save clarification_needed: db_tool not initialized")
        except Exception as e:
            logger.error(f"Failed to save clarification_needed status: {e}", exc_info=True)
    
    @listen(check_clarification)
    def process_question(self, state):
        """
        Step 3: Process the question.
        
        Routes to appropriate processing:
        - DATA queries → Vanna SQL generation → Execution → Insights
        - CONVERSATIONAL queries → Conversational response
        
        This step is SKIPPED if clarification was needed (error == "CLARIFICATION_NEEDED").
        """
        # Skip if clarification was needed - flow stops here
        if self.state.error == "CLARIFICATION_NEEDED":
            logger.info(
                "data_analyst_flow_stopped_for_clarification",
                message_id=self.state.message_id,
                clarification_prompt=self.state.clarification_prompt
            )
            return self.state
        
        # Skip if there was a real error in previous step
        if self.state.error:
            logger.warning(
                "data_analyst_flow_skipping_processing",
                message_id=self.state.message_id,
                reason="error_in_previous_step",
                error=self.state.error
            )
            return self.state
        
        # Build question to process
        question_to_process = self.state.clarified_question or self.state.original_question
        
        # Check if this is a FASB domain query - use RAG instead of CrewAI SQL flow
        if self.state.data_source_type.lower() == "fasb":
            return self._process_fasb_rag(question_to_process)
        
        # Emit processing started event
        self._emit_telemetry_event(
            event_type="processing_started",
            stage_name="Processing",
            agent_name="Data Processing Router",
            user_message=f"Processing {self.state.message_type} query...",
            progress_percentage=65
        )
        
        logger.info(
            "data_analyst_flow_processing_started",
            message_id=self.state.message_id,
            message_type=self.state.message_type,
            question=question_to_process
        )
        
        try:
            if self.state.message_type == MessageType.DATA.value:
                # DATA query path
                processing_task = Task(
                    description=f"""
                    Process this DATA query using the available tools:
                    
                    Question: {question_to_process}
                    Conversation Context: {self.state.conversation_context or 'None'}
                    SQL Hint: {self.state.suggested_sql_hint or 'None'}
                    Message ID: {self.state.message_id}
                    
                    EXECUTION STEPS (follow in order):
                    
                    1. Generate SQL:
                       Call VannaSQLGenerationTool with:
                       - question: "{question_to_process}"
                       - conversation_context: "{self.state.conversation_context or ''}"
                       This returns JSON with "sql" field.
                       
                    2. Execute SQL:
                       Call SQLExecutorTool with the SQL string from step 1.
                       This returns JSON with "results" array and "row_count".
                       
                    3. Generate Insights:
                       Call InsightsGenerationTool with:
                       - results_json: The full JSON output from SQLExecutorTool (step 2)
                       - question: "{question_to_process}"
                       - message_id: "{self.state.message_id}"
                       This returns structured insights JSON.
                       
                    4. Format Results:
                       Prepare result_data from SQLExecutorTool results:
                       - columns: Extract from first result row keys
                       - rows: Convert results to list of lists
                       - row_count: From SQLExecutorTool output
                       
                    5. Save to Database:
                       IMPORTANT: Add the SQL from step 1 to the insights JSON as a "sql" field.
                       The result_metadata MUST include the SQL query for the frontend to display it.
                       
                       Call DatabaseMessageTool with operation:
                       {{
                         "operation": "update_message_results",
                         "message_id": "{self.state.message_id}",
                         "result_data": <formatted result_data from step 4>,
                         "result_metadata": {{...insights from step 3..., "sql": "<SQL string from step 1>"}},
                         "generated_sql": <SQL string from step 1>,
                         "status": "completed"
                       }}
                       
                    CRITICAL: You MUST include the "sql" field in result_metadata.
                    CRITICAL: You MUST call DatabaseMessageTool.update_message_results to save results.
                    Do not return until you have saved the results.
                    
                    After saving, return a brief summary confirming all steps completed.
                    """,
                    agent=self.router_agent,
                    expected_output="Confirmation that SQL was generated, executed, insights created, and results saved to database"
                )
            else:
                # CONVERSATIONAL query path
                processing_task = Task(
                    description=f"""
                    Process this CONVERSATIONAL query using the available tools:
                    
                    Question: {question_to_process}
                    Conversation Context: {self.state.conversation_context or 'None'}
                    Message ID: {self.state.message_id}
                    
                    EXECUTION STEPS (follow in order):
                    
                    1. Generate Response:
                       Call ConversationalResponseTool with:
                       - question: "{question_to_process}"
                       - conversation_context: "{self.state.conversation_context or ''}"
                       This returns JSON with "response" field.
                       
                    2. Save to Database:
                       Call DatabaseMessageTool with operation:
                       {{
                         "operation": "update_message_results",
                         "message_id": "{self.state.message_id}",
                         "result_data": {{"response": <response from step 1>}},
                         "result_metadata": {{}},
                         "conversational_response": <response text from step 1>,
                         "status": "completed"
                       }}
                       
                    CRITICAL: You MUST call DatabaseMessageTool.update_message_results to save the response.
                    Do not return until you have saved the response.
                    
                    After saving, return the conversational response text.
                    """,
                    agent=self.router_agent,
                    expected_output="Helpful conversational response and confirmation it was saved to database"
                )
            
            crew = Crew(
                agents=[self.router_agent],
                tasks=[processing_task],
                verbose=True
            )
            with self.langfuse_service.span_scope(
                name="agentmesh.data_analyst.process_question",
                input_data={
                    "message_id": self.state.message_id,
                    "intent": self.state.detected_intent,
                    "question": question_to_process,
                },
                metadata={
                    "component": "agentmesh",
                    "flow": "data_analyst",
                    "stage": "processing",
                    "customer_id": self.state.customer_id,
                },
                trace_id=self.trace_id,
            ) as span_info:
                result = crew.kickoff()
                observation = span_info.get("observation")
                if observation is not None:
                    try:
                        observation.update(
                            output={"raw_result": getattr(result, "raw", str(result))}
                        )
                    except Exception:
                        pass
            
            # Store processing result
            self.state.processing_result = {
                "result": result.raw,
                "message_type": self.state.message_type,
                "completed_at": datetime.utcnow().isoformat()
            }
            
            # ⚠️ CRITICAL: Parse crew execution and FORCE SAVE to database
            # NEVER rely on the agent to call database tools - they hallucinate this frequently
            # Instead, extract tool outputs from crew execution and save directly via Python code
            success = self._extract_and_save_results(crew, result)
            
            if not success:
                error_msg = "Failed to extract or save results from crew execution"
                self.state.error = error_msg
                self._update_message_with_error(error_msg)
                logger.error(
                    "crew_result_extraction_failed",
                    message_id=self.state.message_id,
                    crew_result=str(result.raw)[:500]  # Log first 500 chars
                )
                return
            
            # Emit processing completed event
            self._emit_telemetry_event(
                event_type="processing_completed",
                stage_name="Processing",
                agent_name="Data Processing Router",
                user_message="Processing completed successfully",
                progress_percentage=100,
                data={"message_type": self.state.message_type}
            )
            
            # Emit flow completed event
            self._emit_telemetry_event(
                event_type="flow_completed",
                stage_name="Flow",
                user_message="Flow completed successfully",
                progress_percentage=100
            )
            
            logger.info(
                "data_analyst_flow_processing_completed",
                message_id=self.state.message_id,
                message_type=self.state.message_type
            )
            
        except Exception as e:
            error_msg = f"Processing failed: {str(e)}"
            self.state.error = error_msg
            
            # Emit error event
            self._emit_telemetry_event(
                event_type="error",
                stage_name="Processing",
                agent_name="Data Processing Router",
                user_message="Processing failed",
                error_details={"error": str(e)},
                progress_percentage=65
            )
            
            # Emit flow failed event
            self._emit_telemetry_event(
                event_type="flow_failed",
                stage_name="Flow",
                user_message="Flow failed",
                error_details={"error": str(e)},
                progress_percentage=0
            )
            
            logger.error(
                "data_analyst_flow_processing_failed",
                message_id=self.state.message_id,
                error=str(e),
                exc_info=True
            )
        
        return self.state
    
    def _process_fasb_rag(self, question: str):
        """
        Process FASB domain query using RAG instead of SQL.
        
        FASB uses OpenSearch Serverless for vector search and OpenAI for answers,
        completely different from the Insurance SQL-based flow.
        """
        # Emit processing started event
        self._emit_telemetry_event(
            event_type="processing_started",
            stage_name="Processing",
            agent_name="FASB RAG Service",
            user_message="Retrieving relevant FASB standards...",
            progress_percentage=65
        )
        
        logger.info(
            "fasb_rag_processing_started",
            message_id=self.state.message_id,
            question=question
        )
        
        try:
            # Import FASB service
            from src.services.fasb_service import get_fasb_service
            
            fasb_service = get_fasb_service()
            
            # Process using RAG - pass customer_id for prompt management
            result = fasb_service.process_message(
                question=question,
                conversation_context=self.state.conversation_context,
                customer_id=self.state.customer_id
            )
            
            # Save results to database
            if not hasattr(self, '_tools_initialized') or not self._tools_initialized:
                self._init_tools()
            
            if hasattr(self, 'db_tool') and self.db_tool:
                import json
                save_data = {
                    "operation": "update_message_results",
                    "message_id": self.state.message_id,
                    "result_data": result["result_data"],
                    "result_metadata": result["result_metadata"],
                    "status": "completed"
                }
                self.db_tool._run(operation_json=json.dumps(save_data))
                logger.info(f"FASB results saved for message {self.state.message_id}")
            
            # Store processing result in state
            self.state.processing_result = {
                "result": result,
                "message_type": "fasb_rag",
                "completed_at": datetime.utcnow().isoformat()
            }
            
            # Emit processing completed event
            self._emit_telemetry_event(
                event_type="processing_completed",
                stage_name="Processing",
                agent_name="FASB RAG Service",
                user_message="FASB answer generated with sources",
                progress_percentage=100,
                data={
                    "sources_count": len(result["result_metadata"].get("sources", [])),
                    "domain": "fasb"
                }
            )
            
            # Emit flow completed event
            self._emit_telemetry_event(
                event_type="flow_completed",
                stage_name="Flow",
                user_message="Flow completed successfully",
                progress_percentage=100
            )
            
            logger.info(
                "fasb_rag_processing_completed",
                message_id=self.state.message_id,
                sources_count=len(result["result_metadata"].get("sources", []))
            )
            
            return self.state
            
        except Exception as e:
            error_msg = f"FASB RAG processing failed: {str(e)}"
            self.state.error = error_msg
            
            # Emit error event
            self._emit_telemetry_event(
                event_type="error",
                stage_name="Processing",
                agent_name="FASB RAG Service",
                user_message="FASB processing failed",
                error_details={"error": str(e)},
                progress_percentage=65
            )
            
            # Emit flow failed event
            self._emit_telemetry_event(
                event_type="flow_failed",
                stage_name="Flow",
                user_message="Flow failed",
                error_details={"error": str(e)},
                progress_percentage=0
            )
            
            # Save error to database
            self._update_message_with_error(error_msg)
            
            logger.error(
                "fasb_rag_processing_failed",
                message_id=self.state.message_id,
                error=str(e),
                exc_info=True
            )
            
            return self.state
    
    def _parse_intent_result(self, raw_output: str) -> IntentResult:
        """Parse intent detection result from agent output"""
        try:
            # Try to extract JSON from output
            json_str = self._extract_json(raw_output)
            result_dict = json.loads(json_str)
            
            return IntentResult(**result_dict)
        except Exception as e:
            logger.warning(
                "failed_to_parse_intent_result",
                error=str(e),
                raw_output=raw_output[:200]
            )
            # Fallback to default
            return IntentResult(
                intent="data_query",
                confidence="low",
                clarification_needed=True,
                reasoning="Failed to parse intent result, defaulting to data_query"
            )
    
    def _parse_confirmation_response(self, response: str) -> Dict[str, Any]:
        """Parse user confirmation response"""
        response_lower = response.lower().strip()
        
        # Check for confirmation
        if any(word in response_lower for word in ["yes", "y", "correct", "confirm", "proceed"]):
            return {"confirmed": True}
        
        # Check for corrections
        if any(word in response_lower for word in ["no", "n", "wrong", "incorrect", "change"]):
            # Try to extract corrected question
            # Simple heuristic: if response is longer than 10 chars, treat as correction
            if len(response) > 10:
                return {
                    "confirmed": False,
                    "corrected_question": response
                }
            return {"confirmed": False}
        
        # Default to confirmed
        return {"confirmed": True}
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from text that may contain markdown or other formatting"""
        # Remove markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            return text[start:end].strip()
        
        # Try to find JSON object
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return text[start:end]
        
        return text
