# CrewAI Implementation Specification for User Task Enrichment

## Executive Summary

This document defines the optimal CrewAI implementation for the User Task Enrichment system, leveraging CrewAI's agent orchestration, flow management, and task execution capabilities to create a robust, scalable enrichment pipeline.

**Key Requirements:**
- **CrewAI Flows**: Orchestrate the multi-stage enrichment pipeline
- **CrewAI Agents**: Specialized agents for each enrichment component
- **CrewAI Tasks**: Structured task definitions with clear inputs/outputs
- **CrewAI Tools**: Custom tools for RAG retrieval, example matching, and quality validation
- **OpenAI Compatibility**: All LLM calls use OpenAI-compatible API format

---

## 1. CrewAI Architecture Overview

### 1.1 Core Components Mapping

```python
# From CrewAI implementation architecture - EXAMPLE
from crewai import Agent, Task, Flow, Tool
from crewai.tools import BaseTool
from typing import Dict, List, Any, Optional
import asyncio
from dataclasses import dataclass

# Map enrichment components to CrewAI constructs:
# UserTaskEnrichmentAgent -> CrewAI Flow (orchestrator)
# IntentAnalyzer -> CrewAI Agent (intent_analysis_agent)
# RAGContextRetriever -> CrewAI Agent (rag_retrieval_agent) 
# ContextEnricher -> CrewAI Agent (context_enrichment_agent)
# PromptGenerator -> CrewAI Agent (prompt_generation_agent)
# QualityValidator -> CrewAI Agent (quality_validation_agent)

@dataclass
class EnrichmentFlowConfig:
    """Configuration for the enrichment flow"""
    api_key: str
    api_base_url: str = "http://localhost:5001/inf"
    max_concurrent_tasks: int = 3
    timeout_seconds: int = 300
    quality_threshold: float = 0.8
    examples_directory: str = "prompt_examples"
    rag_config: Dict[str, Any] = None
    logging_config: Dict[str, Any] = None

class UserTaskEnrichmentFlow(Flow):
    """CrewAI Flow orchestrating the user task enrichment pipeline"""
    
    def __init__(self, config: EnrichmentFlowConfig, model_config_path: str = "model_config.yaml"):
        super().__init__()
        self.config = config
        self.logger = self._initialize_logger()
        
        # Initialize model management system
        from MODEL_CONFIGURATION_SYSTEM import load_model_config_from_file, ModelManager, UnifiedLLMInterface, TaskType
        self.model_config = load_model_config_from_file(model_config_path)
        self.model_manager = ModelManager(self.model_config)
        self.llm_interface = UnifiedLLMInterface(self.model_manager)
        
        # Initialize specialized agents
        self.agents = self._create_enrichment_agents()
        
        # Initialize custom tools
        self.tools = self._create_enrichment_tools()
        
        # Define the enrichment flow structure
        self.flow_structure = self._define_flow_structure()
    
    def _create_enrichment_agents(self) -> Dict[str, Agent]:
        """Create specialized CrewAI agents for each enrichment component"""
        
        agents = {}
        
        # Intent Analysis Agent
        agents['intent_analyzer'] = Agent(
            role="Intent Analysis Specialist",
            goal="Analyze user requests to determine intent, complexity, and requirements",
            backstory="""You are an expert at understanding user intentions and breaking down 
            complex requests into structured, analyzable components. You excel at identifying 
            ambiguities, extracting entities, and determining the appropriate processing approach.""",
            tools=[
                self.tools['intent_classification_tool'],
                self.tools['entity_extraction_tool'],
                self.tools['complexity_assessment_tool']
            ],
            llm_config=self._get_model_config_for_task(TaskType.INTENT_ANALYSIS),
            verbose=True,
            memory=True  # Enable memory for learning from previous analyses
        )
        
        # RAG Retrieval Agent
        agents['rag_retriever'] = Agent(
            role="Knowledge Retrieval Specialist", 
            goal="Find and retrieve relevant information from the knowledge base to enrich user requests",
            backstory="""You are an expert information retrieval specialist with deep knowledge 
            of semantic search, query optimization, and knowledge base navigation. You excel at 
            finding relevant context from diverse sources and synthesizing it into actionable insights.""",
            tools=[
                self.tools['rag_query_generator'],
                self.tools['vector_search_tool'],
                self.tools['qa_database_search'],
                self.tools['context_synthesizer']
            ],
            llm_config=self._get_model_config_for_task(TaskType.RAG_RETRIEVAL),
            verbose=True,
            memory=True
        )
        
        # Context Enrichment Agent
        agents['context_enricher'] = Agent(
            role="Business Context Specialist",
            goal="Enrich user requests with relevant business, organizational, and domain context",
            backstory="""You are a business analyst with deep understanding of organizational 
            structures, business processes, and domain-specific knowledge. You excel at adding 
            relevant context that helps processing agents understand the business implications 
            and constraints of user requests.""",
            tools=[
                self.tools['organizational_context_tool'],
                self.tools['temporal_context_tool'],
                self.tools['domain_context_tool'],
                self.tools['user_context_analyzer']
            ],
            llm_config=self._get_model_config_for_task(TaskType.CONTEXT_ENRICHMENT),
            verbose=True,
            memory=True
        )
        
        # Prompt Generation Agent
        agents['prompt_generator'] = Agent(
            role="Prompt Engineering Expert",
            goal="Generate exceptional prompts that maximize processing agent success rates",
            backstory="""You are a world-class prompt engineering expert with deep knowledge of 
            AI agent psychology, instruction clarity, and task optimization. You excel at creating 
            prompts that are clear, actionable, and perfectly tailored to the intended processing agent.""",
            tools=[
                self.tools['template_selector'],
                self.tools['example_matcher'],
                self.tools['prompt_enhancer'],
                self.tools['best_practices_applier']
            ],
            llm_config=self._get_model_config_for_task(TaskType.PROMPT_GENERATION),
            verbose=True,
            memory=True
        )
        
        # Quality Validation Agent
        agents['quality_validator'] = Agent(
            role="Quality Assurance Specialist",
            goal="Ensure generated prompts meet the highest quality standards before processing",
            backstory="""You are a meticulous quality assurance expert with deep understanding 
            of prompt effectiveness, clarity metrics, and success prediction. You excel at 
            identifying potential issues and suggesting improvements that maximize agent performance.""",
            tools=[
                self.tools['quality_assessor'],
                self.tools['prompt_refiner'],
                self.tools['validation_criteria_checker'],
                self.tools['success_predictor']
            ],
            llm_config=self._get_model_config_for_task(TaskType.QUALITY_VALIDATION),
            verbose=True,
            memory=True
        )
        
        return agents
    
    def _get_model_config_for_task(self, task_type: 'TaskType') -> Dict[str, Any]:
        """Get CrewAI-compatible model configuration for a specific task"""
        model_config = self.model_manager.get_model_for_task(task_type)
        provider_config = self.model_config.provider_configs.get(model_config.provider, {})
        
        # Create CrewAI-compatible configuration
        llm_config = {
            "model": model_config.model_name,
            "temperature": model_config.temperature,
            "max_tokens": model_config.max_tokens,
            "timeout": model_config.timeout
        }
        
        # Add authentication
        if model_config.api_key or provider_config.get("api_key"):
            llm_config["api_key"] = model_config.api_key or provider_config.get("api_key")
        
        # Add base URL
        if model_config.base_url or provider_config.get("base_url"):
            llm_config["base_url"] = model_config.base_url or provider_config.get("base_url")
        
        # Add provider-specific parameters
        if model_config.provider.value == "azure_openai":
            llm_config["api_version"] = provider_config.get("api_version", "2024-02-15-preview")
        elif model_config.provider.value == "openai" and provider_config.get("organization"):
            llm_config["organization"] = provider_config.get("organization")
        
        return llm_config
    
    def _create_enrichment_tools(self) -> Dict[str, BaseTool]:
        """Create custom CrewAI tools for enrichment operations"""
        
        tools = {}
        
        # Intent Analysis Tools
        tools['intent_classification_tool'] = IntentClassificationTool(self.config)
        tools['entity_extraction_tool'] = EntityExtractionTool(self.config)
        tools['complexity_assessment_tool'] = ComplexityAssessmentTool(self.config)
        
        # RAG Retrieval Tools
        tools['rag_query_generator'] = RAGQueryGeneratorTool(self.config)
        tools['vector_search_tool'] = VectorSearchTool(self.config)
        tools['qa_database_search'] = QADatabaseSearchTool(self.config)
        tools['context_synthesizer'] = ContextSynthesizerTool(self.config)
        
        # Context Enrichment Tools
        tools['organizational_context_tool'] = OrganizationalContextTool(self.config)
        tools['temporal_context_tool'] = TemporalContextTool(self.config)
        tools['domain_context_tool'] = DomainContextTool(self.config)
        tools['user_context_analyzer'] = UserContextAnalyzerTool(self.config)
        
        # Prompt Generation Tools
        tools['template_selector'] = TemplateSelectorTool(self.config)
        tools['example_matcher'] = ExampleMatcherTool(self.config)
        tools['prompt_enhancer'] = PromptEnhancerTool(self.config)
        tools['best_practices_applier'] = BestPracticesApplierTool(self.config)
        
        # Quality Validation Tools
        tools['quality_assessor'] = QualityAssessorTool(self.config)
        tools['prompt_refiner'] = PromptRefinerTool(self.config)
        tools['validation_criteria_checker'] = ValidationCriteriaCheckerTool(self.config)
        tools['success_predictor'] = SuccessPredictorTool(self.config)
        
        return tools
    
    def _define_flow_structure(self) -> List[Dict[str, Any]]:
        """Define the CrewAI flow structure with task dependencies"""
        
        return [
            {
                "stage": "intent_analysis",
                "agent": self.agents['intent_analyzer'],
                "dependencies": [],
                "parallel": False,
                "critical": True
            },
            {
                "stage": "rag_retrieval", 
                "agent": self.agents['rag_retriever'],
                "dependencies": ["intent_analysis"],
                "parallel": False,
                "critical": False  # Can continue without RAG if needed
            },
            {
                "stage": "context_enrichment",
                "agent": self.agents['context_enricher'], 
                "dependencies": ["intent_analysis", "rag_retrieval"],
                "parallel": False,
                "critical": True
            },
            {
                "stage": "prompt_generation",
                "agent": self.agents['prompt_generator'],
                "dependencies": ["intent_analysis", "rag_retrieval", "context_enrichment"],
                "parallel": False,
                "critical": True
            },
            {
                "stage": "quality_validation",
                "agent": self.agents['quality_validator'],
                "dependencies": ["prompt_generation"],
                "parallel": False,
                "critical": True
            }
        ]
    
    async def kickoff(self, user_input: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the enrichment flow using CrewAI orchestration"""
        
        flow_start_time = asyncio.get_event_loop().time()
        
        self.logger.info(
            f"Starting user task enrichment flow",
            operation="flow_kickoff",
            user_message="Analyzing and enriching your request..."
        )
        
        try:
            # Create flow context
            flow_context = {
                "user_input": user_input,
                "user_context": user_context,
                "flow_id": f"enrichment_{int(flow_start_time)}",
                "stage_results": {},
                "flow_metadata": {
                    "start_time": flow_start_time,
                    "config": self.config.__dict__
                }
            }
            
            # Execute stages in sequence with dependency management
            for stage_config in self.flow_structure:
                stage_result = await self._execute_stage(stage_config, flow_context)
                flow_context["stage_results"][stage_config["stage"]] = stage_result
                
                # Check if critical stage failed
                if stage_config["critical"] and stage_result.get("status") == "failed":
                    raise Exception(f"Critical stage {stage_config['stage']} failed: {stage_result.get('error')}")
            
            # Compile final result
            final_result = self._compile_enrichment_result(flow_context)
            
            # Log success
            processing_time = asyncio.get_event_loop().time() - flow_start_time
            self.logger.info(
                f"Enrichment flow completed successfully",
                operation="flow_completion",
                duration_ms=processing_time * 1000,
                metadata={
                    "stages_completed": len(flow_context["stage_results"]),
                    "quality_score": final_result.get("quality_score", 0),
                    "prompt_length": len(final_result.get("enriched_prompt", ""))
                },
                user_message="Request analysis complete - ready for processing"
            )
            
            return final_result
            
        except Exception as e:
            self.logger.error(
                f"Enrichment flow failed: {e}",
                operation="flow_error",
                exception=e,
                user_message="Failed to analyze request - please try rephrasing"
            )
            raise
    
    async def _execute_stage(self, stage_config: Dict[str, Any], flow_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single stage of the enrichment flow"""
        
        stage_name = stage_config["stage"]
        agent = stage_config["agent"]
        
        # Create stage-specific task
        task = self._create_stage_task(stage_name, flow_context)
        
        try:
            # Execute task with the assigned agent
            result = await agent.execute(task)
            
            return {
                "status": "success",
                "result": result,
                "agent": agent.role,
                "stage": stage_name,
                "execution_time": task.execution_time if hasattr(task, 'execution_time') else None
            }
            
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e),
                "agent": agent.role,
                "stage": stage_name
            }
    
    def _create_stage_task(self, stage_name: str, flow_context: Dict[str, Any]) -> Task:
        """Create a CrewAI task for a specific enrichment stage"""
        
        task_definitions = {
            "intent_analysis": Task(
                description=f"""
                Analyze the user request to determine intent, complexity, and requirements.
                
                User Input: {flow_context['user_input']}
                User Context: {flow_context['user_context']}
                
                Your analysis should include:
                1. Primary intent classification
                2. Task complexity assessment  
                3. Entity extraction
                4. Sub-objective identification
                5. Success criteria definition
                6. Required data source identification
                
                Provide structured output with confidence scores.
                """,
                expected_output="Structured task analysis with intent, complexity, entities, and requirements",
                agent=self.agents['intent_analyzer']
            ),
            
            "rag_retrieval": Task(
                description=f"""
                Retrieve relevant context from the knowledge base to enrich the user request.
                
                User Input: {flow_context['user_input']}
                Intent Analysis: {flow_context['stage_results'].get('intent_analysis', {}).get('result', {})}
                User Context: {flow_context['user_context']}
                
                Your retrieval should include:
                1. Multi-faceted query generation
                2. Vector similarity search
                3. Q&A pairs retrieval
                4. Result ranking and filtering
                5. Context summarization
                
                Focus on finding information that will help a processing agent understand the business context and requirements.
                """,
                expected_output="Relevant context chunks, Q&A pairs, and synthesized summary",
                agent=self.agents['rag_retriever']
            ),
            
            "context_enrichment": Task(
                description=f"""
                Enrich the user request with comprehensive business, organizational, and domain context.
                
                User Input: {flow_context['user_input']}
                Intent Analysis: {flow_context['stage_results'].get('intent_analysis', {}).get('result', {})}
                RAG Context: {flow_context['stage_results'].get('rag_retrieval', {}).get('result', {})}
                User Context: {flow_context['user_context']}
                
                Your enrichment should include:
                1. Organizational context (roles, permissions, structure)
                2. Temporal context (business cycles, deadlines, historical)
                3. Domain context (industry knowledge, best practices)
                4. User-specific context (expertise level, preferences)
                5. Data availability assessment
                6. Processing constraints identification
                
                Integrate RAG findings with broader contextual knowledge.
                """,
                expected_output="Comprehensive enriched context with organizational, temporal, and domain insights",
                agent=self.agents['context_enricher']
            ),
            
            "prompt_generation": Task(
                description=f"""
                Generate an exceptional prompt that maximizes processing agent success.
                
                User Input: {flow_context['user_input']}
                Intent Analysis: {flow_context['stage_results'].get('intent_analysis', {}).get('result', {})}
                RAG Context: {flow_context['stage_results'].get('rag_retrieval', {}).get('result', {})}
                Enriched Context: {flow_context['stage_results'].get('context_enrichment', {}).get('result', {})}
                User Context: {flow_context['user_context']}
                
                Your prompt generation should include:
                1. Relevant example prompt matching
                2. Template selection and customization
                3. Best practices application
                4. Context integration
                5. Processing instructions definition
                6. Output format specification
                7. Validation criteria creation
                
                Create a prompt that is clear, actionable, and perfectly suited for the intended processing agent.
                """,
                expected_output="Optimized prompt with processing instructions, output format, and validation criteria",
                agent=self.agents['prompt_generator']
            ),
            
            "quality_validation": Task(
                description=f"""
                Validate and refine the generated prompt to ensure maximum quality.
                
                Generated Prompt: {flow_context['stage_results'].get('prompt_generation', {}).get('result', {})}
                Intent Analysis: {flow_context['stage_results'].get('intent_analysis', {}).get('result', {})}
                User Context: {flow_context['user_context']}
                
                Your validation should include:
                1. Multi-dimensional quality assessment
                2. Clarity and actionability evaluation
                3. Completeness verification
                4. Best practices compliance check
                5. Success probability estimation
                6. Refinement recommendations
                
                If quality score is below {self.config.quality_threshold}, provide specific improvements.
                """,
                expected_output="Quality assessment with score and refined prompt if needed",
                agent=self.agents['quality_validator']
            )
        }
        
        return task_definitions.get(stage_name)
    
    def _compile_enrichment_result(self, flow_context: Dict[str, Any]) -> Dict[str, Any]:
        """Compile the final enrichment result from all stages"""
        
        stage_results = flow_context["stage_results"]
        
        # Extract key results from each stage
        intent_analysis = stage_results.get("intent_analysis", {}).get("result", {})
        rag_context = stage_results.get("rag_retrieval", {}).get("result", {})
        enriched_context = stage_results.get("context_enrichment", {}).get("result", {})
        generated_prompt = stage_results.get("prompt_generation", {}).get("result", {})
        quality_validation = stage_results.get("quality_validation", {}).get("result", {})
        
        # Compile final enriched prompt
        final_prompt = quality_validation.get("refined_prompt") or generated_prompt.get("prompt_text", "")
        
        return {
            "enriched_prompt": final_prompt,
            "processing_instructions": generated_prompt.get("processing_instructions", {}),
            "expected_output_format": generated_prompt.get("output_format", {}),
            "validation_criteria": generated_prompt.get("validation_criteria", []),
            "quality_score": quality_validation.get("quality_score", 0.0),
            "metadata": {
                "original_input": flow_context["user_input"],
                "intent_type": intent_analysis.get("intent_type"),
                "complexity": intent_analysis.get("complexity"),
                "confidence_score": intent_analysis.get("confidence_score", 0.0),
                "rag_confidence": rag_context.get("confidence_score", 0.0),
                "sources_used": rag_context.get("sources_used", []),
                "user_context": flow_context["user_context"],
                "processing_time_ms": (asyncio.get_event_loop().time() - flow_context["flow_metadata"]["start_time"]) * 1000,
                "stages_executed": list(stage_results.keys())
            }
        }
```

## 2. Custom CrewAI Tools Implementation

### 2.1 Intent Analysis Tools

```python
# From CrewAI tools implementation - EXAMPLE
from crewai.tools import BaseTool
from typing import Dict, Any, List
import json
import openai

class IntentClassificationTool(BaseTool):
    """CrewAI tool for intent classification"""
    
    name: str = "Intent Classification"
    description: str = "Classify user intent and determine task complexity"
    
    def __init__(self, config: EnrichmentFlowConfig):
        super().__init__()
        self.config = config
        self.client = openai.OpenAI(
            api_key=config.api_key,
            base_url=config.api_base_url
        )
    
    def _run(self, user_input: str, user_context: Dict[str, Any]) -> str:
        """Execute intent classification"""
        
        classification_prompt = f"""
        Classify the following user request and provide detailed analysis:
        
        User Input: "{user_input}"
        User Context: {json.dumps(user_context, indent=2)}
        
        Analyze and respond with JSON:
        {{
            "primary_intent": "question_answering|data_analysis|report_generation|recommendation|comparison|summarization|calculation|workflow_execution|information_extraction",
            "confidence": 0.0-1.0,
            "complexity": "simple|moderate|complex|expert",
            "main_objective": "clear statement of primary goal",
            "sub_objectives": ["list of sub-goals"],
            "entities_mentioned": ["specific entities referenced"],
            "success_criteria": ["how to measure success"],
            "estimated_effort": "quick|moderate|extensive",
            "recommended_agent_type": "suggested processing agent type"
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="meta-llama/Llama-3.1-8B-Instruct",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing user requests and understanding intent. Always respond with valid JSON."},
                    {"role": "user", "content": classification_prompt}
                ],
                temperature=0.1,
                max_tokens=800
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return json.dumps({
                "primary_intent": "question_answering",
                "confidence": 0.5,
                "complexity": "moderate", 
                "main_objective": user_input,
                "error": str(e)
            })

class EntityExtractionTool(BaseTool):
    """CrewAI tool for extracting entities from user input"""
    
    name: str = "Entity Extraction"
    description: str = "Extract named entities, departments, systems, and key concepts from user input"
    
    def __init__(self, config: EnrichmentFlowConfig):
        super().__init__()
        self.config = config
        self.client = openai.OpenAI(
            api_key=config.api_key,
            base_url=config.api_base_url
        )
    
    def _run(self, user_input: str, user_context: Dict[str, Any]) -> str:
        """Extract entities from user input"""
        
        extraction_prompt = f"""
        Extract all relevant entities from the user request:
        
        User Input: "{user_input}"
        User Context: {json.dumps(user_context, indent=2)}
        
        Extract and categorize entities as JSON:
        {{
            "people": ["names of people mentioned"],
            "departments": ["departments or teams mentioned"], 
            "systems": ["software systems, databases, or tools mentioned"],
            "metrics": ["KPIs, metrics, or measurements mentioned"],
            "time_periods": ["dates, quarters, years, or time ranges mentioned"],
            "products": ["products, services, or offerings mentioned"],
            "locations": ["offices, regions, or geographic areas mentioned"],
            "concepts": ["business concepts, processes, or methodologies mentioned"],
            "organizations": ["companies, vendors, or external organizations mentioned"]
        }}
        """
        
        try:
            response = self.client.chat.completions.create(
                model="meta-llama/Llama-3.1-8B-Instruct",
                messages=[
                    {"role": "system", "content": "You are an expert at extracting and categorizing entities from business text."},
                    {"role": "user", "content": extraction_prompt}
                ],
                temperature=0.1,
                max_tokens=600
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return json.dumps({"error": str(e), "entities": []})

class ComplexityAssessmentTool(BaseTool):
    """CrewAI tool for assessing task complexity"""
    
    name: str = "Complexity Assessment"
    description: str = "Assess the complexity of a user request and determine processing requirements"
    
    def _run(self, user_input: str, intent_analysis: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """Assess task complexity"""
        
        complexity_factors = {
            "multiple_objectives": len(intent_analysis.get("sub_objectives", [])) > 2,
            "cross_functional": len(intent_analysis.get("entities_mentioned", [])) > 3,
            "executive_level": user_context.get("user_role") in ["executive", "director"],
            "time_sensitive": user_context.get("time_constraint") == "urgent",
            "data_intensive": "analysis" in intent_analysis.get("primary_intent", ""),
            "ambiguous_request": intent_analysis.get("confidence", 1.0) < 0.7
        }
        
        complexity_score = sum(complexity_factors.values()) / len(complexity_factors)
        
        if complexity_score >= 0.7:
            complexity_level = "expert"
        elif complexity_score >= 0.5:
            complexity_level = "complex"
        elif complexity_score >= 0.3:
            complexity_level = "moderate"
        else:
            complexity_level = "simple"
        
        return json.dumps({
            "complexity_level": complexity_level,
            "complexity_score": complexity_score,
            "complexity_factors": complexity_factors,
            "processing_recommendations": {
                "requires_expert_agent": complexity_score >= 0.7,
                "needs_human_review": complexity_score >= 0.8,
                "estimated_processing_time": "extensive" if complexity_score >= 0.6 else "moderate",
                "parallel_processing_beneficial": len(intent_analysis.get("sub_objectives", [])) > 1
            }
        })

### 2.2 RAG Retrieval Tools

class RAGQueryGeneratorTool(BaseTool):
    """CrewAI tool for generating RAG queries"""
    
    name: str = "RAG Query Generator"
    description: str = "Generate optimized queries for RAG retrieval based on intent analysis"
    
    def _run(self, user_input: str, intent_analysis: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """Generate RAG queries"""
        
        # Generate different types of queries
        queries = {
            "primary_query": user_input,
            "intent_specific_queries": self._generate_intent_queries(intent_analysis, user_context),
            "entity_queries": self._generate_entity_queries(intent_analysis.get("entities_mentioned", [])),
            "context_queries": self._generate_context_queries(user_context),
            "follow_up_queries": self._generate_follow_up_queries(intent_analysis)
        }
        
        return json.dumps(queries)
    
    def _generate_intent_queries(self, intent_analysis: Dict[str, Any], user_context: Dict[str, Any]) -> List[str]:
        """Generate queries specific to the identified intent"""
        
        intent = intent_analysis.get("primary_intent", "question_answering")
        department = user_context.get("department", "")
        
        intent_query_templates = {
            "data_analysis": [
                f"{department} performance metrics",
                f"{department} trend analysis",
                f"Key performance indicators for {department}"
            ],
            "report_generation": [
                f"{department} status report",
                f"Executive summary for {department}",
                f"{department} quarterly update"
            ],
            "recommendation": [
                f"Best practices for {department}",
                f"{department} improvement strategies",
                f"Strategic recommendations for {department}"
            ]
        }
        
        return intent_query_templates.get(intent, [user_input])

class VectorSearchTool(BaseTool):
    """CrewAI tool for vector similarity search"""
    
    name: str = "Vector Search"
    description: str = "Perform semantic similarity search in vector index"
    
    def __init__(self, config: EnrichmentFlowConfig):
        super().__init__()
        self.config = config
        # Initialize vector index connection
        self.vector_index = self._initialize_vector_index()
    
    def _run(self, queries: List[str], max_results: int = 10, threshold: float = 0.7) -> str:
        """Execute vector search for multiple queries"""
        
        all_results = []
        
        for query in queries:
            try:
                # Generate query embedding
                query_embedding = self._generate_embedding(query)
                
                # Search vector index
                results = self.vector_index.similarity_search(
                    query_embedding,
                    k=max_results,
                    threshold=threshold
                )
                
                all_results.extend(results)
                
            except Exception as e:
                continue  # Skip failed queries
        
        # Deduplicate and rank results
        unique_results = self._deduplicate_results(all_results)
        
        return json.dumps({
            "results": unique_results[:max_results],
            "total_found": len(unique_results),
            "queries_executed": len(queries)
        })

### 2.3 Prompt Generation Tools

class ExampleMatcherTool(BaseTool):
    """CrewAI tool for matching relevant prompt examples"""
    
    name: str = "Example Matcher"
    description: str = "Find relevant prompt examples from the examples directory"
    
    def __init__(self, config: EnrichmentFlowConfig):
        super().__init__()
        self.config = config
        self.example_loader = PromptExampleLoader(config.examples_directory)
        self.examples = self.example_loader.load_all_examples()
    
    def _run(self, user_input: str, intent_analysis: Dict[str, Any], user_context: Dict[str, Any]) -> str:
        """Find relevant prompt examples"""
        
        matcher = PromptExampleMatcher(self.examples)
        
        # Create mock objects for compatibility
        class MockTaskAnalysis:
            def __init__(self, intent_data):
                self.intent_type = type('IntentType', (), {'value': intent_data.get('primary_intent', 'question_answering')})()
                self.complexity = type('Complexity', (), {'value': intent_data.get('complexity', 'moderate')})()
                self.entities_mentioned = intent_data.get('entities_mentioned', [])
        
        class MockUserContext:
            def __init__(self, context_data):
                self.user_role = context_data.get('user_role', 'employee')
                self.department = context_data.get('department', '')
        
        mock_task_analysis = MockTaskAnalysis(intent_analysis)
        mock_user_context = MockUserContext(user_context)
        
        # Find relevant examples
        match_result = matcher.find_relevant_examples(
            user_input, mock_task_analysis, mock_user_context, max_examples=3
        )
        
        # Format results for JSON serialization
        examples_data = []
        for example in match_result.matched_examples:
            examples_data.append({
                "id": example.id,
                "name": example.name,
                "description": example.description,
                "relevance_score": example.relevance_score,
                "example_prompt": example.example_prompt,
                "best_practices": example.best_practices_demonstrated,
                "quality_indicators": example.quality_indicators
            })
        
        return json.dumps({
            "matched_examples": examples_data,
            "match_metadata": match_result.match_metadata,
            "matching_strategy": match_result.matching_strategy_used
        })

class PromptEnhancerTool(BaseTool):
    """CrewAI tool for enhancing prompts with examples and best practices"""
    
    name: str = "Prompt Enhancer"
    description: str = "Enhance base prompts using example patterns and best practices"
    
    def __init__(self, config: EnrichmentFlowConfig):
        super().__init__()
        self.config = config
        self.client = openai.OpenAI(
            api_key=config.api_key,
            base_url=config.api_base_url
        )
    
    def _run(self, base_prompt: str, matched_examples: List[Dict[str, Any]], intent_analysis: Dict[str, Any]) -> str:
        """Enhance prompt using matched examples"""
        
        if not matched_examples:
            return base_prompt
        
        # Prepare example context
        example_context = self._format_examples_for_enhancement(matched_examples)
        
        enhancement_prompt = f"""
        Enhance the following prompt by incorporating the best practices and structural patterns from these proven examples:
        
        **Base Prompt to Enhance:**
        {base_prompt}
        
        **Reference Examples:**
        {example_context}
        
        **Enhancement Guidelines:**
        1. Apply the structural organization patterns from examples
        2. Include specific deliverables and success criteria
        3. Add relevant business context and constraints
        4. Incorporate demonstrated best practices
        5. Maintain clarity and actionability
        
        **Task Context:**
        - Intent: {intent_analysis.get('primary_intent')}
        - Complexity: {intent_analysis.get('complexity')}
        
        Provide the enhanced prompt that maximizes processing agent success.
        """
        
        try:
            response = self.client.chat.completions.create(
                model="meta-llama/Llama-3.1-70B-Instruct",
                messages=[
                    {"role": "system", "content": "You are an expert prompt engineer who creates exceptional prompts by applying proven patterns and best practices."},
                    {"role": "user", "content": enhancement_prompt}
                ],
                temperature=0.3,
                max_tokens=2500
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return base_prompt  # Fallback to original
    
    def _format_examples_for_enhancement(self, examples: List[Dict[str, Any]]) -> str:
        """Format examples for the enhancement prompt"""
        
        formatted_examples = []
        
        for i, example in enumerate(examples, 1):
            formatted = f"""
            **Example {i}: {example['name']}** (Relevance: {example['relevance_score']:.1%})
            
            Best Practices Demonstrated:
            {chr(10).join([f"  • {practice.replace('_', ' ').title()}" for practice in example.get('best_practices', [])])}
            
            Key Structural Elements:
            {self._extract_structure_from_prompt(example.get('example_prompt', ''))}
            """
            formatted_examples.append(formatted)
        
        return '\n'.join(formatted_examples)
    
    def _extract_structure_from_prompt(self, prompt: str) -> str:
        """Extract structural elements from example prompt"""
        
        lines = prompt.split('\n')
        structure_elements = []
        
        for line in lines[:10]:  # Only check first 10 lines
            stripped = line.strip()
            if stripped.startswith('**') and stripped.endswith('**'):
                structure_elements.append(f"  • Section: {stripped}")
            elif stripped.startswith('###'):
                structure_elements.append(f"  • Header: {stripped}")
            elif stripped.startswith('1.') or stripped.startswith('2.'):
                if "Numbered lists used" not in structure_elements:
                    structure_elements.append("  • Numbered lists used")
        
        return '\n'.join(structure_elements[:5])
```

This comprehensive CrewAI implementation provides:

1. **CrewAI Flow Orchestration**: Complete flow management with stage dependencies
2. **Specialized CrewAI Agents**: Each enrichment component as a dedicated agent
3. **Custom CrewAI Tools**: Specialized tools for each operation
4. **OpenAI Compatibility**: All LLM calls use OpenAI-compatible format
5. **Error Handling**: Robust error handling and fallback mechanisms
6. **Performance Monitoring**: Comprehensive logging and metrics
7. **Scalable Architecture**: Easy to extend with new agents and tools

The system leverages CrewAI's strengths in agent coordination, task management, and tool integration while maintaining the sophisticated enrichment capabilities we've designed.
