"""
Data Analysis Flow

CrewAI flow that retrieves data and performs analysis based on enriched prompts.
Uses custom tools to query HR database and search document embeddings.
"""
from typing import Dict, Any, Optional, List
from crewai import Agent, Task, Crew, Process, LLM
from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel, Field
import json
import time
from datetime import datetime, timezone

from src.crewai_custom_tools import HRDatabaseTool, DocumentSearchTool
from src.crewai_custom_tools.tool_execution_tracker import ToolExecutionTracker
from src.core.logging import get_logger, LogCategory
from src.core.config import get_settings
from src.models import database
from src.services.business_intelligence_service import BusinessIntelligenceService

logger = get_logger(__name__, LogCategory.BUSINESS)
settings = get_settings()


class DataRetrievalResult(BaseModel):
    """Result from data retrieval stage."""
    hr_data: Optional[Dict[str, Any]] = None
    document_data: Optional[Dict[str, Any]] = None
    data_sources_used: List[str] = Field(default_factory=list)
    total_records: int = 0
    retrieval_notes: Optional[str] = None


class AnalysisResult(BaseModel):
    """Final analysis result."""
    analysis_text: str
    executive_summary: Optional[str] = None
    key_findings: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    data_sources_used: List[str] = Field(default_factory=list)
    confidence_score: float = 0.8
    visualizations: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class DataAnalysisFlowState(BaseModel):
    """State for the data analysis flow."""
    enriched_prompt: str = ""
    customer_id: str = ""  # User's organization
    company_hr_dataset: str = ""  # Target company for HR data
    user_id: int = 0
    data_sources_needed: List[str] = Field(default_factory=lambda: ["hr_database", "documents"])
    retrieval_result: Optional[DataRetrievalResult] = None
    analysis_result: Optional[AnalysisResult] = None
    error: Optional[str] = None
    # Tracking fields (not passed in initial state)
    session_id: Optional[int] = None
    # Note: db_session is NOT stored in state to avoid pickle errors
    # Each method creates its own session when needed


class DataAnalysisFlow(Flow[DataAnalysisFlowState]):
    """
    Data Analysis Flow using CrewAI.
    
    Performs data retrieval and analysis through:
    1. Data Retrieval - Query HR database and search documents
    2. Data Analysis - Analyze retrieved data and generate insights
    
    Agents are configured at runtime from database or code defaults.
    """
    
    def __init__(self):
        # No hardcoded LLM initialization - resolved at runtime per agent
        super().__init__()
    
    def _get_complete_agent_config(self, agent_identifier: str):
        """Load complete agent configuration at runtime (Layer 1 + Layer 2 merged)."""
        from src.models import database
        from src.services.agent_configuration_service import AgentConfigurationService
        
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        try:
            config_service = AgentConfigurationService(db)
            return config_service.get_complete_agent_config(
                customer_id=self.state.customer_id,
                flow_identifier="data_analysis_flow",
                agent_identifier=agent_identifier
            )
        finally:
            db.close()
    
    def _build_llm_from_config(self, config):
        """Build LLM client from complete agent configuration."""
        from crewai import LLM
        
        if config.provider_type == "openai":
            llm = LLM(
                model=config.model_id,
                api_key=config.api_key,
                base_url=config.base_url or "https://api.openai.com/v1",
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
            logger.info(
                f"Built OpenAI LLM for {config.agent_identifier}",
                metadata={
                    "model": config.model_id,
                    "provider": config.provider_name,
                    "temperature": config.temperature,
                    "source": config.source
                }
            )
        elif config.provider_type == "anthropic":
            llm = LLM(
                model=config.model_id,
                api_key=config.api_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
            logger.info(
                f"Built Anthropic LLM for {config.agent_identifier}",
                metadata={
                    "model": config.model_id,
                    "provider": config.provider_name,
                    "temperature": config.temperature,
                    "source": config.source
                }
            )
        elif config.provider_type == "bedrock":
            # Bedrock uses OpenAI-compatible endpoint
            llm = LLM(
                model=config.model_id,
                api_key="bedrock",  # Placeholder, uses AWS credentials
                base_url=config.base_url,
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
            logger.info(
                f"Built Bedrock LLM for {config.agent_identifier}",
                metadata={
                    "model": config.model_id,
                    "provider": config.provider_name,
                    "temperature": config.temperature,
                    "source": config.source
                }
            )
        elif config.provider_type == "groq":
            llm = LLM(
                model=config.model_id,
                api_key=config.api_key,
                base_url=config.base_url or "https://api.groq.com/openai/v1",
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
            logger.info(
                f"Built Groq LLM for {config.agent_identifier}",
                metadata={
                    "model": config.model_id,
                    "provider": config.provider_name,
                    "temperature": config.temperature,
                    "source": config.source
                }
            )
        else:
            # Fallback to OpenAI-compatible
            logger.warning(
                f"Unknown provider type {config.provider_type}, using OpenAI-compatible client",
                metadata={"provider": config.provider_type}
            )
            llm = LLM(
                model=config.model_id,
                api_key=config.api_key,
                base_url=config.base_url,
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
        
        return llm
    
    @start()
    def retrieve_data(self):
        """
        Stage 1: Retrieve relevant data from HR database and documents.
        """
        logger.info(
            "data_analysis_retrieve_data_start",
            metadata={
                "customer_id": self.state.customer_id,
                "company_hr_dataset": self.state.company_hr_dataset,
                "data_sources": self.state.data_sources_needed
            }
        )
        
        # Initialize custom tools with configuration from settings
        # Use company_hr_dataset for HR data queries (not customer_id)
        hr_tool = HRDatabaseTool(customer_id=self.state.company_hr_dataset)
        
        # Get vector search configuration from system settings
        if database.SessionLocal is None:
            database.init_database()
        settings_db = database.SessionLocal()
        try:
            from src.services.settings_service import SettingsService
            settings_service = SettingsService(settings_db)
            vector_threshold = settings_service.get_vector_search_similarity_threshold()
            vector_limit = settings_service.get_vector_search_result_limit()
        finally:
            settings_db.close()
        
        # Document search uses company_hr_dataset to access company-specific FAISS index
        doc_tool = DocumentSearchTool(
            customer_id=self.state.customer_id,
            company_hr_dataset=self.state.company_hr_dataset,  # Company-specific index
            limit=vector_limit,  # Max results per search (from settings)
            similarity_threshold=vector_threshold  # Minimum relevance score (from settings)
        )
        
        # Load agent configuration at runtime
        agent_config = self._get_complete_agent_config("data_retrieval_agent")
        logger.info(
            f"Loaded config for data_retrieval_agent: model={agent_config.model_id}, "
            f"provider={agent_config.provider_name}, source={agent_config.source}"
        )
        
        # Build LLM from configuration
        llm = self._build_llm_from_config(agent_config)
        
        # Wrap tools with execution tracker if session tracking is enabled
        tracker = None
        if self.state.session_id:
            # Ensure database is initialized before creating session
            if database.SessionLocal is None:
                database.init_database()
            db = database.SessionLocal()
            tracker = ToolExecutionTracker(
                session_id=self.state.session_id,
                db_session=db,
                agent_name=agent_config.role  # Use configured role
            )
            hr_tool = tracker.wrap_tool(hr_tool)
            doc_tool = tracker.wrap_tool(doc_tool)
            db.close()  # Close session after wrapping tools
        
        # Create data retrieval agent from configuration
        data_retriever = Agent(
            role=agent_config.role,
            goal=agent_config.goal,
            backstory=agent_config.backstory,
            tools=[hr_tool, doc_tool],
            llm=llm,
            verbose=True,
        )
        
        # Create retrieval task
        retrieval_task = Task(
            description=f"""
            Retrieve data to answer the following question:
            
            {self.state.enriched_prompt}
            
            MANDATORY TOOL USAGE:
            You MUST use BOTH of the following tools for every query:
            
            1. Document Search Tool (ALWAYS REQUIRED)
               - Purpose: Search company documents for relevant context
               - Always use this first to get comprehensive background information
               - Use the full question as the search query
            
            2. HR Database Tool (REQUIRED if HR-related)
               - Purpose: Query structured HR data (employees, departments, performance, skills, training)
               - Use this when the question involves specific employee data, departments, or HR metrics
               - Query format: {{"query_type": "employees|departments|skills|performance|training", "filters": {{}}, "limit": 10}}
            
            EXECUTION STEPS:
            1. ALWAYS start by using the Document Search Tool with the question
            2. If the question is HR-related, use the HR Database Tool with appropriate query_type and filters
            3. Synthesize information from both sources
            4. Return a comprehensive summary including:
               - What documents were found and their relevance
               - What HR data was retrieved (if applicable)
               - Key insights from each source
               - Any gaps or limitations in the data
            
            IMPORTANT: You must actually CALL both tools and report their results. Do not just describe what you would do.
            """,
            expected_output="Comprehensive summary of data retrieved from Document Search (required) and HR Database (if applicable), including actual results from tool calls",
            agent=data_retriever,
        )
        
        # Execute retrieval
        crew = Crew(
            agents=[data_retriever],
            tasks=[retrieval_task],
            process=Process.sequential,
            verbose=True,
        )
        
        try:
            start_time = time.time()
            result = crew.kickoff()
            duration_ms = int((time.time() - start_time) * 1000)
            result_text = str(result)
            
            # Store retrieval result
            self.state.retrieval_result = DataRetrievalResult(
                hr_data={},  # Will be populated by tool calls
                document_data={},  # Will be populated by tool calls
                data_sources_used=self.state.data_sources_needed,
                total_records=0,
                retrieval_notes=result_text
            )
            
            # Capture agent response if session tracking is enabled
            if self.state.session_id:
                # Ensure database is initialized before creating session
                if database.SessionLocal is None:
                    database.init_database()
                db = database.SessionLocal()
                try:
                    bi_service = BusinessIntelligenceService(db)
                    
                    # Get tool execution summary
                    tool_calls_summary = []
                    if tracker:
                        for execution in tracker.get_executions():
                            tool_calls_summary.append({
                                "tool_name": execution.tool_name,
                                "status": execution.status,
                                "results_count": execution.results_count,
                                "duration_ms": execution.duration_ms
                            })
                    
                    bi_service.create_agent_response(
                        session_id=self.state.session_id,
                        agent_name="Data Retrieval Agent",
                        stage_name="retrieval",
                        input_prompt=self.state.enriched_prompt,
                        response_text=result_text,
                        tool_calls=tool_calls_summary,
                        duration_ms=duration_ms,
                        response_metadata={
                            "data_sources": self.state.data_sources_needed,
                            "tool_execution_summary": tracker.get_summary() if tracker else {}
                        }
                    )
                finally:
                    db.close()
            
            logger.info(
                "data_analysis_retrieve_data_complete",
                metadata={
                    "data_sources": self.state.data_sources_needed,
                    "duration_ms": duration_ms
                }
            )
            
        except Exception as e:
            logger.error(
                "data_analysis_retrieve_data_error",
                exception=e
            )
            self.state.error = f"Data retrieval failed: {str(e)}"
            self.state.retrieval_result = DataRetrievalResult(
                retrieval_notes=f"Error: {str(e)}"
            )
    
    @listen(retrieve_data)
    def analyze_data(self):
        """
        Stage 2: Analyze the retrieved data and generate insights.
        """
        logger.info("data_analysis_analyze_data_start")
        
        # Load agent configuration at runtime
        agent_config = self._get_complete_agent_config("bi_analyst_agent")
        logger.info(
            f"Loaded config for bi_analyst_agent: model={agent_config.model_id}, "
            f"provider={agent_config.provider_name}, source={agent_config.source}"
        )
        
        # Build LLM from configuration
        llm = self._build_llm_from_config(agent_config)
        
        # Create data analysis agent from configuration
        data_analyzer = Agent(
            role=agent_config.role,
            goal=agent_config.goal,
            backstory=agent_config.backstory,
            llm=llm,
            verbose=True,
        )
        
        # Create analysis task
        analysis_task = Task(
            description=f"""
            Analyze the retrieved data to answer the following question:
            
            {self.state.enriched_prompt}
            
            Retrieved Data Summary:
            {self.state.retrieval_result.retrieval_notes if self.state.retrieval_result else 'No data retrieved'}
            
            Provide a comprehensive analysis that includes:
            
            1. EXECUTIVE SUMMARY (2-3 sentences)
               - High-level answer to the question
               - Most important insight
            
            2. KEY FINDINGS (3-5 bullet points)
               - Specific insights from the data
               - Quantitative metrics where available
               - Notable patterns or trends
            
            3. DETAILED ANALYSIS (2-3 paragraphs)
               - In-depth explanation of findings
               - Context and implications
               - Supporting evidence from data
            
            4. RECOMMENDATIONS (3-5 bullet points)
               - Actionable next steps
               - Specific suggestions based on findings
               - Prioritized by impact
            
            5. DATA SOURCES
               - List which data sources were used
               - Note any data limitations
            
            Format your response as a structured analysis with clear sections.
            Be specific, data-driven, and actionable.
            """,
            expected_output="Comprehensive structured analysis with executive summary, findings, and recommendations",
            agent=data_analyzer,
        )
        
        # Execute analysis
        crew = Crew(
            agents=[data_analyzer],
            tasks=[analysis_task],
            process=Process.sequential,
            verbose=True,
        )
        
        try:
            start_time = time.time()
            result = crew.kickoff()
            duration_ms = int((time.time() - start_time) * 1000)
            analysis_text = str(result)
            
            # Parse the analysis to extract sections
            executive_summary = self._extract_section(analysis_text, "EXECUTIVE SUMMARY")
            key_findings = self._extract_list_items(analysis_text, "KEY FINDINGS")
            recommendations = self._extract_list_items(analysis_text, "RECOMMENDATIONS")
            
            # Create analysis result
            self.state.analysis_result = AnalysisResult(
                analysis_text=analysis_text,
                executive_summary=executive_summary,
                key_findings=key_findings,
                recommendations=recommendations,
                data_sources_used=self.state.data_sources_needed,
                confidence_score=0.85,
                metadata={
                    "retrieval_notes": self.state.retrieval_result.retrieval_notes if self.state.retrieval_result else None
                }
            )
            
            # Capture agent response if session tracking is enabled
            if self.state.session_id:
                # Ensure database is initialized before creating session
                if database.SessionLocal is None:
                    database.init_database()
                db = database.SessionLocal()
                try:
                    bi_service = BusinessIntelligenceService(db)
                    bi_service.create_agent_response(
                        session_id=self.state.session_id,
                        agent_name="Data Analysis Agent",
                        stage_name="analysis",
                        input_prompt=f"{self.state.enriched_prompt}\n\nRetrieval Data:\n{self.state.retrieval_result.retrieval_notes if self.state.retrieval_result else 'N/A'}",
                        response_text=analysis_text,
                        reasoning=executive_summary,
                        confidence_score=0.85,
                        duration_ms=duration_ms,
                        response_metadata={
                            "findings_count": len(key_findings),
                            "recommendations_count": len(recommendations),
                            "data_sources": self.state.data_sources_needed
                        }
                    )
                finally:
                    db.close()
            
            logger.info(
                "data_analysis_analyze_data_complete",
                metadata={
                    "findings_count": len(key_findings),
                    "recommendations_count": len(recommendations),
                    "duration_ms": duration_ms
                }
            )
            
        except Exception as e:
            logger.error(
                "data_analysis_analyze_data_error",
                exception=e
            )
            self.state.error = f"Data analysis failed: {str(e)}"
            self.state.analysis_result = AnalysisResult(
                analysis_text=f"Analysis failed: {str(e)}",
                confidence_score=0.0
            )
    
    def _extract_section(self, text: str, section_name: str) -> Optional[str]:
        """Extract a specific section from the analysis text."""
        import re
        pattern = rf"{section_name}[:\s]+(.*?)(?=\n\n|\n[A-Z]{{2,}}|$)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
    
    def _extract_list_items(self, text: str, section_name: str) -> List[str]:
        """Extract list items from a section."""
        section_text = self._extract_section(text, section_name)
        if not section_text:
            return []
        
        import re
        # Match bullet points (-, *, •) or numbered lists
        items = re.findall(r'(?:^|\n)[\s]*(?:[-*•]|\d+\.)\s+(.+?)(?=\n[\s]*(?:[-*•]|\d+\.)|$)', section_text, re.DOTALL)
        return [item.strip() for item in items if item.strip()]

