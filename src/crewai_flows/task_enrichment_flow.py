"""
Task Enrichment Flow

CrewAI flow that transforms raw user questions into enriched prompts
optimized for the data analysis agents.

Based on USER_TASK_ENRICHMENT_SPECIFICATION.md
"""
from typing import Dict, Any, Optional, List
from crewai import Agent, Task, Crew, Process, LLM
from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel, Field
import json

from src.core.logging import get_logger, LogCategory
from src.core.config import get_settings

logger = get_logger(__name__, LogCategory.BUSINESS)
settings = get_settings()


def normalize_llm_output(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize LLM output to match our Pydantic models.
    
    Claude sometimes returns rich structured data like:
    - entities: [{"type": "department", "value": "Engineering"}]
    - data_sources_needed: [{"specific_tables": ["employees"]}]
    
    This function extracts simple values that match our model expectations.
    """
    normalized = data.copy()
    
    # Normalize entities - extract 'value' from dicts, keep strings as-is
    if "entities" in normalized and isinstance(normalized["entities"], list):
        normalized["entities"] = [
            item["value"] if isinstance(item, dict) and "value" in item else str(item)
            for item in normalized["entities"]
        ]
    
    # Normalize keywords - same approach
    if "keywords" in normalized and isinstance(normalized["keywords"], list):
        normalized["keywords"] = [
            item["value"] if isinstance(item, dict) and "value" in item else str(item)
            for item in normalized["keywords"]
        ]
    
    # Normalize data_sources_needed - extract simple source names
    if "data_sources_needed" in normalized and isinstance(normalized["data_sources_needed"], list):
        sources = []
        for item in normalized["data_sources_needed"]:
            if isinstance(item, dict):
                # Extract primary source name (could be 'source', 'name', or just use 'hr_database')
                if "source" in item:
                    sources.append(item["source"])
                elif "name" in item:
                    sources.append(item["name"])
                else:
                    # Default to extracting from keys
                    sources.append("hr_database" if "specific_tables" in item else "documents")
            else:
                sources.append(str(item))
        normalized["data_sources_needed"] = sources
    
    return normalized


class UserContext(BaseModel):
    """User context information for enrichment."""
    user_id: int
    customer_id: str
    role: Optional[str] = None
    department: Optional[str] = None
    previous_queries: Optional[List[str]] = None
    preferences: Optional[Dict[str, Any]] = None


class TaskAnalysis(BaseModel):
    """Analysis of the user's task/question."""
    intent_type: str = Field(description="Type of intent: question_answering, data_analysis, report_generation, etc.")
    complexity: str = Field(description="Complexity level: simple, moderate, complex, expert")
    confidence_score: float = Field(description="Confidence in the analysis (0-1)")
    entities: List[str] = Field(default_factory=list, description="Extracted entities")
    keywords: List[str] = Field(default_factory=list, description="Key terms")
    data_sources_needed: List[str] = Field(default_factory=list, description="Required data sources")


class EnrichedPrompt(BaseModel):
    """Enriched prompt output."""
    original_input: str
    enriched_prompt: str
    task_analysis: TaskAnalysis
    processing_instructions: Dict[str, Any]
    expected_output_format: Dict[str, Any]
    validation_criteria: Dict[str, Any]
    quality_score: float
    rag_context: Optional[Dict[str, Any]] = None


class TaskEnrichmentFlowState(BaseModel):
    """State for the task enrichment flow."""
    original_question: str = ""
    user_context: Optional[UserContext] = None
    task_analysis: Optional[TaskAnalysis] = None
    rag_context: Optional[Dict[str, Any]] = None
    enriched_prompt: Optional[EnrichedPrompt] = None
    error: Optional[str] = None


class TaskEnrichmentFlow(Flow[TaskEnrichmentFlowState]):
    """
    Task Enrichment Flow using CrewAI.
    
    Transforms raw user questions into enriched prompts through:
    1. Intent Analysis - Understand what the user wants
    2. Context Enrichment - Add relevant business context
    3. Prompt Generation - Create optimized prompt for analysis agents
    
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
                customer_id=self.state.user_context.customer_id,
                flow_identifier="task_enrichment_flow",
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
            llm = LLM(
                model=config.model_id,
                api_key="bedrock",
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
    def analyze_intent(self):
        """
        Stage 1: Analyze the user's intent and extract key information.
        """
        logger.info(
            "task_enrichment_analyze_intent_start",
            question=self.state.original_question
        )
        
        # Load agent configuration at runtime
        agent_config = self._get_complete_agent_config("task_analyzer_agent")
        logger.info(
            f"Loaded config for task_analyzer_agent: model={agent_config.model_id}, "
            f"provider={agent_config.provider_name}, source={agent_config.source}"
        )
        
        # Build LLM from configuration
        llm = self._build_llm_from_config(agent_config)
        
        # Create intent analyzer agent from configuration
        intent_analyzer = Agent(
            role=agent_config.role,
            goal=agent_config.goal,
            backstory=agent_config.backstory,
            llm=llm,
            verbose=True,
        )
        
        # Create analysis task
        analysis_task = Task(
            description=f"""
            Analyze the following user question and extract key information:
            
            Question: {self.state.original_question}
            
            User Context:
            - Customer: {self.state.user_context.customer_id}
            - Role: {self.state.user_context.role or 'Unknown'}
            - Department: {self.state.user_context.department or 'Unknown'}
            
            Provide a detailed analysis including:
            1. Intent type (question_answering, data_analysis, report_generation, recommendation, comparison, trend_analysis, forecasting, anomaly_detection)
            2. Complexity level (simple, moderate, complex, expert)
            3. Confidence score (0-1)
            4. Extracted entities (people, departments, metrics, time periods, etc.)
            5. Key terms and concepts
            6. Required data sources (hr_database, documents, both)
            
            Return your analysis as a JSON object with these fields:
            - intent_type
            - complexity
            - confidence_score
            - entities (list)
            - keywords (list)
            - data_sources_needed (list)
            """,
            expected_output="JSON object with intent analysis",
            agent=intent_analyzer,
        )
        
        # Execute analysis
        crew = Crew(
            agents=[intent_analyzer],
            tasks=[analysis_task],
            process=Process.sequential,
            verbose=True,
        )
        
        try:
            result = crew.kickoff()
            
            # Parse the result
            result_text = str(result)
            
            # Try to extract JSON from the result
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                analysis_data = json.loads(json_match.group())
                # Normalize Claude's rich output to match our simple model
                normalized_data = normalize_llm_output(analysis_data)
                self.state.task_analysis = TaskAnalysis(**normalized_data)
            else:
                # Fallback: create basic analysis
                self.state.task_analysis = TaskAnalysis(
                    intent_type="question_answering",
                    complexity="moderate",
                    confidence_score=0.7,
                    entities=[],
                    keywords=[],
                    data_sources_needed=["hr_database", "documents"]
                )
            
            logger.info(
                "task_enrichment_analyze_intent_complete",
                intent_type=self.state.task_analysis.intent_type,
                complexity=self.state.task_analysis.complexity,
                confidence=self.state.task_analysis.confidence_score
            )
            
        except Exception as e:
            logger.error(
                "task_enrichment_analyze_intent_error",
                error=str(e),
                exc_info=True
            )
            self.state.error = f"Intent analysis failed: {str(e)}"
            # Create fallback analysis
            self.state.task_analysis = TaskAnalysis(
                intent_type="question_answering",
                complexity="moderate",
                confidence_score=0.5,
                entities=[],
                keywords=[],
                data_sources_needed=["hr_database", "documents"]
            )
    
    @listen(analyze_intent)
    def enrich_context(self):
        """
        Stage 2: Enrich the question with relevant context.
        """
        logger.info("task_enrichment_enrich_context_start")
        
        # Load agent configuration at runtime
        agent_config = self._get_complete_agent_config("enrichment_agent")
        logger.info(
            f"Loaded config for enrichment_agent: model={agent_config.model_id}, "
            f"provider={agent_config.provider_name}, source={agent_config.source}"
        )
        
        # Build LLM from configuration
        llm = self._build_llm_from_config(agent_config)
        
        # Create context enricher agent from configuration
        context_enricher = Agent(
            role=agent_config.role,
            goal=agent_config.goal,
            backstory=agent_config.backstory,
            llm=llm,
            verbose=True,
        )
        
        # Create enrichment task
        enrichment_task = Task(
            description=f"""
            Enrich the following question with relevant business context:
            
            Original Question: {self.state.original_question}
            
            Intent Analysis:
            - Type: {self.state.task_analysis.intent_type}
            - Complexity: {self.state.task_analysis.complexity}
            - Data Sources: {', '.join(self.state.task_analysis.data_sources_needed)}
            
            Add context such as:
            1. Relevant business metrics and KPIs
            2. Time periods to consider
            3. Comparison points or benchmarks
            4. Related business processes
            5. Potential data quality considerations
            
            Return a JSON object with:
            - enriched_context: Dict with additional context information
            - suggested_refinements: List of ways to refine the question
            - related_topics: List of related topics to consider
            """,
            expected_output="JSON object with enriched context",
            agent=context_enricher,
        )
        
        # Execute enrichment
        crew = Crew(
            agents=[context_enricher],
            tasks=[enrichment_task],
            process=Process.sequential,
            verbose=True,
        )
        
        try:
            result = crew.kickoff()
            result_text = str(result)
            
            # Try to extract JSON
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                self.state.rag_context = json.loads(json_match.group())
            else:
                self.state.rag_context = {
                    "enriched_context": {},
                    "suggested_refinements": [],
                    "related_topics": []
                }
            
            logger.info("task_enrichment_enrich_context_complete")
            
        except Exception as e:
            logger.error(
                "task_enrichment_enrich_context_error",
                error=str(e),
                exc_info=True
            )
            self.state.rag_context = {
                "enriched_context": {},
                "suggested_refinements": [],
                "related_topics": []
            }
    
    @listen(enrich_context)
    def generate_enriched_prompt(self):
        """
        Stage 3: Generate the final enriched prompt for analysis agents.
        """
        logger.info("task_enrichment_generate_prompt_start")
        
        # Note: prompt_generator is kept simple with code defaults for now
        # Could be configured via database in the future if needed
        # Using task_analyzer_agent config as a reasonable default
        agent_config = self._get_complete_agent_config("task_analyzer_agent")
        llm = self._build_llm_from_config(agent_config)
        
        # Create prompt generator agent
        prompt_generator = Agent(
            role="Prompt Generator",
            goal="Create optimized prompts for data analysis agents",
            backstory=(
                "You are an expert at crafting clear, specific prompts that guide AI agents "
                "to produce high-quality analysis. You know how to structure prompts for "
                "maximum effectiveness."
            ),
            llm=llm,
            verbose=True,
        )
        
        # Create generation task
        generation_task = Task(
            description=f"""
            Create an enriched prompt for data analysis agents based on:
            
            Original Question: {self.state.original_question}
            
            Intent: {self.state.task_analysis.intent_type}
            Complexity: {self.state.task_analysis.complexity}
            Data Sources: {', '.join(self.state.task_analysis.data_sources_needed)}
            
            Context: {json.dumps(self.state.rag_context, indent=2)}
            
            Create a comprehensive prompt that:
            1. Clearly states the analysis objective
            2. Specifies what data to retrieve
            3. Defines the expected output format
            4. Includes relevant context and constraints
            5. Provides guidance on analysis approach
            
            The prompt should be clear, specific, and actionable for data analysis agents.
            """,
            expected_output="Enriched prompt text for analysis agents",
            agent=prompt_generator,
        )
        
        # Execute generation
        crew = Crew(
            agents=[prompt_generator],
            tasks=[generation_task],
            process=Process.sequential,
            verbose=True,
        )
        
        try:
            result = crew.kickoff()
            enriched_prompt_text = str(result)
            
            # Create enriched prompt object
            self.state.enriched_prompt = EnrichedPrompt(
                original_input=self.state.original_question,
                enriched_prompt=enriched_prompt_text,
                task_analysis=self.state.task_analysis,
                processing_instructions={
                    "data_sources": self.state.task_analysis.data_sources_needed,
                    "complexity": self.state.task_analysis.complexity,
                },
                expected_output_format={
                    "type": "structured_analysis",
                    "sections": ["executive_summary", "key_findings", "recommendations"]
                },
                validation_criteria={
                    "completeness": "All requested information provided",
                    "accuracy": "Data is accurate and properly sourced",
                    "clarity": "Analysis is clear and well-structured"
                },
                quality_score=self.state.task_analysis.confidence_score,
                rag_context=self.state.rag_context
            )
            
            logger.info(
                "task_enrichment_generate_prompt_complete",
                quality_score=self.state.enriched_prompt.quality_score
            )
            
        except Exception as e:
            logger.error(
                "task_enrichment_generate_prompt_error",
                error=str(e),
                exc_info=True
            )
            self.state.error = f"Prompt generation failed: {str(e)}"

