# User Task Enrichment Agent Specification

## Executive Summary

This document defines the User Task Enrichment Agent system that transforms raw user inputs into exceptionally clear, actionable prompts for processing agents. The system analyzes user intent, enriches context, and generates optimized prompts that maximize the success rate of downstream processing agents.

**Key Objectives:**
- **Intent Clarification**: Transform ambiguous user requests into clear, specific instructions
- **Context Enrichment**: Add relevant business context, constraints, and expectations
- **Prompt Optimization**: Generate prompts following best practices for agent performance
- **Quality Assurance**: Validate and refine prompts before processing
- **Adaptive Learning**: Improve prompt generation based on processing outcomes

---

## 1. System Architecture

### 1.1 Core Components

```python
# From user task enrichment architecture - EXAMPLE
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from datetime import datetime
import json
import re

class UserIntentType(Enum):
    """Categories of user intents"""
    QUESTION_ANSWERING = "question_answering"
    DATA_ANALYSIS = "data_analysis"
    DOCUMENT_SEARCH = "document_search"
    REPORT_GENERATION = "report_generation"
    COMPARISON = "comparison"
    SUMMARIZATION = "summarization"
    RECOMMENDATION = "recommendation"
    CALCULATION = "calculation"
    WORKFLOW_EXECUTION = "workflow_execution"
    INFORMATION_EXTRACTION = "information_extraction"

class TaskComplexity(Enum):
    """Task complexity levels"""
    SIMPLE = "simple"           # Single-step, clear intent
    MODERATE = "moderate"       # Multi-step, some ambiguity
    COMPLEX = "complex"         # Multi-step, requires clarification
    EXPERT = "expert"          # Domain expertise required

class PromptQuality(Enum):
    """Quality levels for generated prompts"""
    EXCELLENT = "excellent"    # Ready for processing
    GOOD = "good"             # Minor refinements needed
    NEEDS_IMPROVEMENT = "needs_improvement"  # Requires enhancement
    INSUFFICIENT = "insufficient"  # Needs major rework

@dataclass
class UserContext:
    """User context information for prompt enrichment"""
    user_id: str
    session_id: str
    user_role: str = "employee"  # employee, manager, executive, analyst
    department: str = ""
    expertise_level: str = "intermediate"  # beginner, intermediate, expert
    previous_queries: List[str] = field(default_factory=list)
    current_project: str = ""
    time_constraint: str = ""  # urgent, normal, flexible
    output_preference: str = "detailed"  # brief, detailed, comprehensive
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_role": self.user_role,
            "department": self.department,
            "expertise_level": self.expertise_level,
            "time_constraint": self.time_constraint,
            "output_preference": self.output_preference,
            "context_available": bool(self.current_project or self.previous_queries)
        }

@dataclass
class TaskAnalysis:
    """Analysis of the user's task"""
    intent_type: UserIntentType
    complexity: TaskComplexity
    confidence_score: float  # 0.0 to 1.0
    
    # Extracted components
    main_objective: str
    sub_objectives: List[str] = field(default_factory=list)
    entities_mentioned: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    
    # Ambiguities and clarifications needed
    ambiguous_terms: List[str] = field(default_factory=list)
    missing_context: List[str] = field(default_factory=list)
    assumptions_made: List[str] = field(default_factory=list)
    
    # Processing requirements
    required_data_sources: List[str] = field(default_factory=list)
    estimated_processing_time: str = ""
    recommended_agent_type: str = ""

@dataclass
class EnrichedPrompt:
    """The final enriched prompt for processing agents"""
    original_user_input: str
    enriched_prompt: str
    
    # Metadata
    task_analysis: TaskAnalysis
    user_context: UserContext
    quality_score: float
    quality_assessment: PromptQuality
    
    # Instructions for processing agent
    processing_instructions: Dict[str, Any]
    expected_output_format: Dict[str, Any]
    validation_criteria: List[str]
    
    # Tracking
    enrichment_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    enrichment_agent_version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enriched_prompt": self.enriched_prompt,
            "processing_instructions": self.processing_instructions,
            "expected_output_format": self.expected_output_format,
            "validation_criteria": self.validation_criteria,
            "metadata": {
                "original_input": self.original_user_input,
                "quality_score": self.quality_score,
                "intent_type": self.task_analysis.intent_type.value,
                "complexity": self.task_analysis.complexity.value,
                "user_context": self.user_context.to_dict()
            }
        }

class UserTaskEnrichmentAgent:
    """Main agent for enriching user tasks into optimized prompts"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = self._initialize_logger()
        
        # Initialize sub-components
        self.intent_analyzer = IntentAnalyzer(config.get('intent_analysis', {}))
        self.context_enricher = ContextEnricher(config.get('context_enrichment', {}))
        self.rag_context_retriever = RAGContextRetriever(config.get('rag_retrieval', {}))
        self.prompt_generator = PromptGenerator(config.get('prompt_generation', {}))
        self.quality_validator = PromptQualityValidator(config.get('quality_validation', {}))
        
        # Load prompt templates and examples
        self.prompt_templates = self._load_prompt_templates()
        self.best_practice_examples = self._load_best_practice_examples()
        
        # Performance tracking
        self.enrichment_metrics = {
            "total_requests": 0,
            "successful_enrichments": 0,
            "quality_scores": [],
            "processing_times": []
        }
    
    def _initialize_logger(self):
        """Initialize specialized logger for task enrichment"""
        from LOGGING_SPECIFICATION import EnhancedLogger, LogCategory
        return EnhancedLogger("task_enrichment", self.config.get('logging', {}))
    
    async def enrich_user_task(
        self, 
        user_input: str, 
        user_context: UserContext
    ) -> EnrichedPrompt:
        """Main method to enrich user task into optimized prompt"""
        
        operation_id = self.logger.start_operation(
            "task_enrichment",
            category=LogCategory.BUSINESS,
            user_id=user_context.user_id,
            user_message="Analyzing your request..."
        )
        
        try:
            start_time = asyncio.get_event_loop().time()
            
            # Step 1: Analyze user intent and task complexity
            self.logger.info(
                "Analyzing user intent and task structure",
                operation="intent_analysis",
                user_message="Understanding your request..."
            )
            task_analysis = await self.intent_analyzer.analyze_task(user_input, user_context)
            
            # Step 2: Retrieve relevant context from RAG indexes
            self.logger.info(
                "Retrieving relevant information from knowledge base",
                operation="rag_retrieval",
                user_message="Searching knowledge base for relevant context..."
            )
            rag_context = await self.rag_context_retriever.retrieve_relevant_context(
                user_input, task_analysis, user_context
            )
            
            # Step 3: Enrich with contextual information
            self.logger.info(
                f"Enriching context for {task_analysis.intent_type.value} task",
                operation="context_enrichment",
                user_message="Adding relevant context..."
            )
            enriched_context = await self.context_enricher.enrich_context(
                user_input, task_analysis, user_context, rag_context
            )
            
            # Step 4: Generate optimized prompt
            self.logger.info(
                "Generating optimized prompt for processing agent",
                operation="prompt_generation",
                user_message="Creating detailed instructions..."
            )
            generated_prompt = await self.prompt_generator.generate_prompt(
                user_input, task_analysis, enriched_context, user_context, rag_context
            )
            
            # Step 5: Validate and refine prompt quality
            self.logger.info(
                "Validating prompt quality and completeness",
                operation="quality_validation",
                user_message="Ensuring optimal prompt quality..."
            )
            validated_prompt = await self.quality_validator.validate_and_refine(
                generated_prompt, task_analysis
            )
            
            # Step 6: Create final enriched prompt
            enriched_prompt = EnrichedPrompt(
                original_user_input=user_input,
                enriched_prompt=validated_prompt.prompt_text,
                task_analysis=task_analysis,
                user_context=user_context,
                quality_score=validated_prompt.quality_score,
                quality_assessment=validated_prompt.quality_level,
                processing_instructions=validated_prompt.processing_instructions,
                expected_output_format=validated_prompt.output_format,
                validation_criteria=validated_prompt.validation_criteria
            )
            
            # Update metrics
            processing_time = asyncio.get_event_loop().time() - start_time
            self._update_metrics(enriched_prompt, processing_time)
            
            # Log successful completion
            self.logger.end_operation(
                operation_id,
                "task_enrichment",
                success=True,
                metadata={
                    "intent_type": task_analysis.intent_type.value,
                    "complexity": task_analysis.complexity.value,
                    "quality_score": enriched_prompt.quality_score,
                    "prompt_length": len(enriched_prompt.enriched_prompt)
                },
                user_message=f"Request analysis complete - ready for processing"
            )
            
            return enriched_prompt
            
        except Exception as e:
            self.logger.end_operation(
                operation_id,
                "task_enrichment",
                success=False,
                metadata={"error": str(e)},
                user_message="Failed to analyze request - please try rephrasing"
            )
            raise
    
    def _load_prompt_templates(self) -> Dict[str, Any]:
        """Load prompt templates for different intent types"""
        return {
            "question_answering": {
                "template": """
                You are an expert assistant tasked with answering a specific question based on available data and context.

                **Primary Objective:** {main_objective}
                
                **Question to Answer:** {user_question}
                
                **Context and Constraints:**
                {context_information}
                
                **Available Data Sources:**
                {data_sources}
                
                **Response Requirements:**
                - Provide a clear, accurate answer based on available information
                - Include relevant supporting evidence or data points
                - If information is incomplete, clearly state what is missing
                - Format response according to user's expertise level: {expertise_level}
                - Expected response length: {response_length}
                
                **Success Criteria:**
                {success_criteria}
                
                **Additional Instructions:**
                {additional_instructions}
                """,
                "required_fields": ["main_objective", "user_question", "context_information", "data_sources"]
            },
            
            "data_analysis": {
                "template": """
                You are a data analysis expert tasked with analyzing data to provide insights and recommendations.

                **Analysis Objective:** {main_objective}
                
                **Data Analysis Request:** {analysis_request}
                
                **Data Sources and Scope:**
                {data_sources_scope}
                
                **Analysis Parameters:**
                - Time period: {time_period}
                - Key metrics to focus on: {key_metrics}
                - Comparison criteria: {comparison_criteria}
                - Statistical methods to use: {statistical_methods}
                
                **Context and Business Rules:**
                {business_context}
                
                **Expected Deliverables:**
                1. Executive summary of key findings
                2. Detailed analysis with supporting data
                3. Visual representations (if applicable): {visualization_requirements}
                4. Actionable recommendations
                5. Confidence levels and limitations
                
                **Output Format Requirements:**
                {output_format}
                
                **Quality Standards:**
                {quality_standards}
                """,
                "required_fields": ["main_objective", "analysis_request", "data_sources_scope"]
            },
            
            "report_generation": {
                "template": """
                You are a professional report writer tasked with creating a comprehensive report.

                **Report Purpose:** {report_purpose}
                
                **Report Request:** {report_request}
                
                **Target Audience:** {target_audience}
                
                **Report Scope and Structure:**
                {report_structure}
                
                **Data Sources and Information:**
                {information_sources}
                
                **Report Requirements:**
                - Executive Summary: {executive_summary_requirements}
                - Main Content Sections: {main_sections}
                - Supporting Data: {data_requirements}
                - Conclusions and Recommendations: {conclusions_requirements}
                
                **Formatting and Style:**
                - Report length: {report_length}
                - Writing style: {writing_style}
                - Technical level: {technical_level}
                - Include charts/graphs: {visual_elements}
                
                **Quality Standards:**
                - Accuracy and factual correctness
                - Clear and logical flow
                - Professional presentation
                - Actionable insights
                
                **Delivery Timeline:** {timeline_requirements}
                """,
                "required_fields": ["report_purpose", "report_request", "target_audience"]
            },
            
            "recommendation": {
                "template": """
                You are a strategic advisor tasked with providing expert recommendations.

                **Recommendation Objective:** {main_objective}
                
                **Decision Context:** {decision_context}
                
                **Current Situation:** {current_situation}
                
                **Available Options:** {available_options}
                
                **Evaluation Criteria:**
                {evaluation_criteria}
                
                **Constraints and Limitations:**
                {constraints}
                
                **Stakeholder Considerations:**
                {stakeholder_impacts}
                
                **Recommendation Framework:**
                1. Situation Analysis
                2. Option Evaluation
                3. Risk Assessment
                4. Primary Recommendation with rationale
                5. Alternative options with trade-offs
                6. Implementation considerations
                7. Success metrics
                
                **Output Requirements:**
                - Clear, actionable recommendations
                - Supporting rationale and evidence
                - Risk mitigation strategies
                - Implementation roadmap
                - Success measurement criteria
                
                **Decision Timeline:** {decision_timeline}
                """,
                "required_fields": ["main_objective", "decision_context", "current_situation"]
            }
        }
    
    def _load_best_practice_examples(self) -> Dict[str, List[Dict[str, str]]]:
        """Load best practice examples for prompt generation"""
        return {
            "clarity_examples": [
                {
                    "poor": "Analyze the sales data",
                    "good": "Analyze Q3 2024 sales data for the North American region, focusing on product category performance and identifying trends that explain the 15% revenue decline compared to Q2 2024"
                },
                {
                    "poor": "Find information about employees",
                    "good": "Extract employee performance metrics from HR records for the Engineering department, focusing on employees hired in the last 18 months, to identify training needs and career development opportunities"
                }
            ],
            
            "context_examples": [
                {
                    "poor": "What's our customer satisfaction?",
                    "good": "Calculate current customer satisfaction scores from recent survey data (last 6 months), compare against industry benchmarks, and identify specific service areas impacting scores for our enterprise software customers"
                }
            ],
            
            "specificity_examples": [
                {
                    "poor": "Create a report about the company",
                    "good": "Generate a quarterly business performance report for Q3 2024, including financial metrics, operational KPIs, market position analysis, and strategic recommendations for the executive leadership team"
                }
            ],
            
            "actionability_examples": [
                {
                    "poor": "Look at the budget",
                    "good": "Review the 2024 marketing budget allocation across digital channels, identify overspend/underspend areas, and provide specific reallocation recommendations to optimize ROI for the remaining quarter"
                }
            ]
        }
    
    def _update_metrics(self, enriched_prompt: EnrichedPrompt, processing_time: float):
        """Update enrichment performance metrics"""
        self.enrichment_metrics["total_requests"] += 1
        
        if enriched_prompt.quality_assessment in [PromptQuality.EXCELLENT, PromptQuality.GOOD]:
            self.enrichment_metrics["successful_enrichments"] += 1
        
        self.enrichment_metrics["quality_scores"].append(enriched_prompt.quality_score)
        self.enrichment_metrics["processing_times"].append(processing_time)
        
        # Log metrics periodically
        if self.enrichment_metrics["total_requests"] % 10 == 0:
            avg_quality = sum(self.enrichment_metrics["quality_scores"]) / len(self.enrichment_metrics["quality_scores"])
            avg_time = sum(self.enrichment_metrics["processing_times"]) / len(self.enrichment_metrics["processing_times"])
            success_rate = self.enrichment_metrics["successful_enrichments"] / self.enrichment_metrics["total_requests"]
            
            self.logger.log_business_metric("enrichment_success_rate", success_rate * 100, "percent")
            self.logger.log_business_metric("avg_quality_score", avg_quality, "score")
            self.logger.log_business_metric("avg_processing_time", avg_time * 1000, "milliseconds")
```

### 1.2 Intent Analysis Component

```python
# From intent analysis patterns - EXAMPLE
import openai
from typing import Dict, List, Any
import json
import re

class IntentAnalyzer:
    """Analyzes user input to determine intent and task complexity"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = openai.OpenAI(
            api_key=config.get('api_key'),
            base_url=config.get('api_base_url', 'http://localhost:5001/inf')
        )
        
        # Intent classification patterns
        self.intent_patterns = {
            UserIntentType.QUESTION_ANSWERING: [
                r'\b(what|who|when|where|why|how|which)\b',
                r'\b(tell me|explain|describe|define)\b',
                r'\?$'
            ],
            UserIntentType.DATA_ANALYSIS: [
                r'\b(analyze|analysis|examine|investigate|study)\b',
                r'\b(trend|pattern|correlation|comparison)\b',
                r'\b(metrics|statistics|performance|data)\b'
            ],
            UserIntentType.REPORT_GENERATION: [
                r'\b(report|summary|overview|document)\b',
                r'\b(create|generate|produce|write)\b',
                r'\b(quarterly|monthly|annual)\b'
            ],
            UserIntentType.RECOMMENDATION: [
                r'\b(recommend|suggest|advise|propose)\b',
                r'\b(should|best|optimal|ideal)\b',
                r'\b(decision|choice|option|alternative)\b'
            ]
        }
        
        # Complexity indicators
        self.complexity_indicators = {
            TaskComplexity.SIMPLE: [
                r'\b(simple|basic|quick|brief)\b',
                r'^.{1,50}$'  # Very short requests
            ],
            TaskComplexity.COMPLEX: [
                r'\b(comprehensive|detailed|thorough|complete)\b',
                r'\b(multiple|various|different|several)\b',
                r'\b(compare|contrast|evaluate|assess)\b'
            ],
            TaskComplexity.EXPERT: [
                r'\b(strategic|executive|advanced|sophisticated)\b',
                r'\b(optimize|maximize|minimize)\b',
                r'\b(roi|kpi|metrics|benchmarks)\b'
            ]
        }
    
    async def analyze_task(self, user_input: str, user_context: UserContext) -> TaskAnalysis:
        """Analyze user task to determine intent and complexity"""
        
        # Step 1: Pattern-based intent classification
        primary_intent = self._classify_intent_by_patterns(user_input)
        
        # Step 2: LLM-based analysis for detailed understanding
        llm_analysis = await self._llm_analyze_task(user_input, user_context)
        
        # Step 3: Determine task complexity
        complexity = self._determine_complexity(user_input, llm_analysis, user_context)
        
        # Step 4: Extract task components
        components = self._extract_task_components(user_input, llm_analysis)
        
        # Step 5: Identify requirements and gaps
        requirements = self._identify_requirements(user_input, llm_analysis, user_context)
        
        return TaskAnalysis(
            intent_type=primary_intent,
            complexity=complexity,
            confidence_score=llm_analysis.get('confidence', 0.8),
            main_objective=components['main_objective'],
            sub_objectives=components['sub_objectives'],
            entities_mentioned=components['entities'],
            constraints=components['constraints'],
            success_criteria=components['success_criteria'],
            ambiguous_terms=requirements['ambiguous_terms'],
            missing_context=requirements['missing_context'],
            assumptions_made=requirements['assumptions'],
            required_data_sources=requirements['data_sources'],
            estimated_processing_time=requirements['processing_time'],
            recommended_agent_type=requirements['agent_type']
        )
    
    def _classify_intent_by_patterns(self, user_input: str) -> UserIntentType:
        """Classify intent using pattern matching"""
        
        input_lower = user_input.lower()
        intent_scores = {}
        
        for intent_type, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, input_lower))
                score += matches
            intent_scores[intent_type] = score
        
        # Return intent with highest score, default to QUESTION_ANSWERING
        if not intent_scores or max(intent_scores.values()) == 0:
            return UserIntentType.QUESTION_ANSWERING
        
        return max(intent_scores.items(), key=lambda x: x[1])[0]
    
    async def _llm_analyze_task(self, user_input: str, user_context: UserContext) -> Dict[str, Any]:
        """Use LLM for detailed task analysis"""
        
        analysis_prompt = f"""
        Analyze the following user request and provide a detailed breakdown:

        User Request: "{user_input}"
        
        User Context:
        - Role: {user_context.user_role}
        - Department: {user_context.department}
        - Expertise Level: {user_context.expertise_level}
        
        Please analyze and respond with a JSON object containing:
        {{
            "primary_intent": "one of: question_answering, data_analysis, document_search, report_generation, comparison, summarization, recommendation, calculation, workflow_execution, information_extraction",
            "confidence": 0.0-1.0,
            "main_objective": "clear statement of what user wants to achieve",
            "sub_objectives": ["list of sub-goals or steps"],
            "entities_mentioned": ["specific entities, departments, products, etc. mentioned"],
            "constraints": ["any limitations or requirements mentioned"],
            "success_criteria": ["how to measure if the task is completed successfully"],
            "ambiguous_terms": ["terms that need clarification"],
            "missing_context": ["information that would help complete the task"],
            "assumptions": ["assumptions that need to be made"],
            "complexity_level": "simple, moderate, complex, or expert",
            "estimated_effort": "quick (< 5 min), moderate (5-30 min), extensive (30+ min)",
            "data_sources_needed": ["types of data or information sources required"],
            "recommended_approach": "suggested approach to fulfill this request"
        }}
        
        Respond only with valid JSON.
        """
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.get('analysis_model', 'meta-llama/Llama-3.1-8B-Instruct'),
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing user requests and understanding intent. Always respond with valid JSON."},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.1,  # Low temperature for consistent analysis
                max_tokens=800
            )
            
            analysis_text = response.choices[0].message.content.strip()
            
            # Clean up response to ensure valid JSON
            if analysis_text.startswith('```json'):
                analysis_text = analysis_text[7:-3]
            elif analysis_text.startswith('```'):
                analysis_text = analysis_text[3:-3]
            
            return json.loads(analysis_text)
            
        except Exception as e:
            # Fallback analysis
            return {
                "primary_intent": "question_answering",
                "confidence": 0.5,
                "main_objective": user_input,
                "sub_objectives": [],
                "entities_mentioned": [],
                "constraints": [],
                "success_criteria": ["Provide helpful response"],
                "ambiguous_terms": [],
                "missing_context": [],
                "assumptions": [],
                "complexity_level": "moderate",
                "estimated_effort": "moderate",
                "data_sources_needed": [],
                "recommended_approach": "Direct response"
            }
    
    def _determine_complexity(
        self, 
        user_input: str, 
        llm_analysis: Dict[str, Any], 
        user_context: UserContext
    ) -> TaskComplexity:
        """Determine task complexity based on multiple factors"""
        
        # Start with LLM assessment
        llm_complexity = llm_analysis.get('complexity_level', 'moderate')
        complexity_map = {
            'simple': TaskComplexity.SIMPLE,
            'moderate': TaskComplexity.MODERATE,
            'complex': TaskComplexity.COMPLEX,
            'expert': TaskComplexity.EXPERT
        }
        base_complexity = complexity_map.get(llm_complexity, TaskComplexity.MODERATE)
        
        # Adjust based on pattern indicators
        input_lower = user_input.lower()
        
        # Check for complexity indicators
        for complexity_level, patterns in self.complexity_indicators.items():
            for pattern in patterns:
                if re.search(pattern, input_lower):
                    if complexity_level.value > base_complexity.value:
                        base_complexity = complexity_level
        
        # Adjust based on user context
        if user_context.user_role in ['executive', 'director']:
            if base_complexity == TaskComplexity.SIMPLE:
                base_complexity = TaskComplexity.MODERATE
        
        # Consider number of sub-objectives
        sub_objectives_count = len(llm_analysis.get('sub_objectives', []))
        if sub_objectives_count > 3 and base_complexity == TaskComplexity.SIMPLE:
            base_complexity = TaskComplexity.MODERATE
        elif sub_objectives_count > 5 and base_complexity == TaskComplexity.MODERATE:
            base_complexity = TaskComplexity.COMPLEX
        
        return base_complexity
    
    def _extract_task_components(self, user_input: str, llm_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured components from task analysis"""
        
        return {
            'main_objective': llm_analysis.get('main_objective', user_input),
            'sub_objectives': llm_analysis.get('sub_objectives', []),
            'entities': llm_analysis.get('entities_mentioned', []),
            'constraints': llm_analysis.get('constraints', []),
            'success_criteria': llm_analysis.get('success_criteria', ['Complete the requested task'])
        }
    
    def _identify_requirements(
        self, 
        user_input: str, 
        llm_analysis: Dict[str, Any], 
        user_context: UserContext
    ) -> Dict[str, Any]:
        """Identify processing requirements and information gaps"""
        
        return {
            'ambiguous_terms': llm_analysis.get('ambiguous_terms', []),
            'missing_context': llm_analysis.get('missing_context', []),
            'assumptions': llm_analysis.get('assumptions', []),
            'data_sources': llm_analysis.get('data_sources_needed', []),
            'processing_time': llm_analysis.get('estimated_effort', 'moderate'),
            'agent_type': self._recommend_agent_type(llm_analysis)
        }
    
    def _recommend_agent_type(self, llm_analysis: Dict[str, Any]) -> str:
        """Recommend the best agent type for processing"""
        
        intent = llm_analysis.get('primary_intent', 'question_answering')
        
        agent_mapping = {
            'question_answering': 'research_agent',
            'data_analysis': 'analyst_agent',
            'report_generation': 'writer_agent',
            'recommendation': 'advisor_agent',
            'calculation': 'calculator_agent',
            'document_search': 'search_agent',
            'summarization': 'summarizer_agent',
            'comparison': 'comparison_agent',
            'workflow_execution': 'workflow_agent',
            'information_extraction': 'extractor_agent'
        }
        
        return agent_mapping.get(intent, 'general_agent')
```

### 1.3 Context Enrichment Component

```python
# From context enrichment patterns - EXAMPLE

class ContextEnricher:
    """Enriches user tasks with relevant business context and constraints"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = openai.OpenAI(
            api_key=config.get('api_key'),
            base_url=config.get('api_base_url', 'http://localhost:5001/inf')
        )
        
        # Business context sources
        self.context_sources = {
            'organizational': self._get_organizational_context,
            'temporal': self._get_temporal_context,
            'domain': self._get_domain_context,
            'regulatory': self._get_regulatory_context,
            'performance': self._get_performance_context
        }
    
    async def enrich_context(
        self, 
        user_input: str, 
        task_analysis: TaskAnalysis, 
        user_context: UserContext,
        rag_context: Optional['RAGRetrievalResult'] = None
    ) -> Dict[str, Any]:
        """Enrich task with comprehensive contextual information"""
        
        enriched_context = {
            'organizational_context': {},
            'temporal_context': {},
            'domain_context': {},
            'regulatory_context': {},
            'performance_context': {},
            'user_specific_context': {},
            'data_availability': {},
            'processing_constraints': {}
        }
        
        # Gather context from various sources
        for context_type, context_getter in self.context_sources.items():
            try:
                context_data = await context_getter(user_input, task_analysis, user_context)
                enriched_context[f'{context_type}_context'] = context_data
            except Exception as e:
                # Log error but continue with other context sources
                enriched_context[f'{context_type}_context'] = {'error': str(e)}
        
        # Add user-specific context
        enriched_context['user_specific_context'] = self._build_user_specific_context(user_context)
        
        # Determine data availability
        enriched_context['data_availability'] = await self._assess_data_availability(
            task_analysis.required_data_sources, user_context
        )
        
        # Add processing constraints
        enriched_context['processing_constraints'] = self._determine_processing_constraints(
            task_analysis, user_context
        )
        
        return enriched_context
    
    async def _get_organizational_context(
        self, 
        user_input: str, 
        task_analysis: TaskAnalysis, 
        user_context: UserContext
    ) -> Dict[str, Any]:
        """Get organizational context relevant to the task"""
        
        return {
            'user_department': user_context.department,
            'user_role_permissions': self._get_role_permissions(user_context.user_role),
            'relevant_departments': self._identify_relevant_departments(task_analysis.entities_mentioned),
            'organizational_priorities': self._get_current_priorities(user_context.department),
            'reporting_structure': self._get_reporting_context(user_context.user_role),
            'cross_functional_impact': self._assess_cross_functional_impact(task_analysis)
        }
    
    async def _get_temporal_context(
        self, 
        user_input: str, 
        task_analysis: TaskAnalysis, 
        user_context: UserContext
    ) -> Dict[str, Any]:
        """Get temporal context for the task"""
        
        current_date = datetime.now()
        
        return {
            'current_quarter': f"Q{((current_date.month - 1) // 3) + 1} {current_date.year}",
            'fiscal_year': self._get_fiscal_year(current_date),
            'business_cycle_phase': self._determine_business_cycle_phase(current_date),
            'recent_events': self._get_recent_business_events(),
            'upcoming_deadlines': self._get_upcoming_deadlines(user_context.department),
            'historical_context': self._get_relevant_historical_context(task_analysis),
            'seasonality_factors': self._get_seasonality_factors(current_date, user_context.department)
        }
    
    async def _get_domain_context(
        self, 
        user_input: str, 
        task_analysis: TaskAnalysis, 
        user_context: UserContext
    ) -> Dict[str, Any]:
        """Get domain-specific context"""
        
        domain_contexts = {
            'hr': self._get_hr_domain_context,
            'finance': self._get_finance_domain_context,
            'sales': self._get_sales_domain_context,
            'marketing': self._get_marketing_domain_context,
            'operations': self._get_operations_domain_context,
            'it': self._get_it_domain_context
        }
        
        department_lower = user_context.department.lower()
        context_getter = domain_contexts.get(department_lower, self._get_general_domain_context)
        
        return await context_getter(task_analysis, user_context)
    
    def _get_role_permissions(self, user_role: str) -> Dict[str, Any]:
        """Get permissions and access levels for user role"""
        
        permission_levels = {
            'employee': {
                'data_access': 'department_only',
                'sensitive_data': False,
                'financial_data': 'limited',
                'personnel_data': 'own_only'
            },
            'manager': {
                'data_access': 'department_full',
                'sensitive_data': 'department',
                'financial_data': 'department_budget',
                'personnel_data': 'team_members'
            },
            'director': {
                'data_access': 'cross_department',
                'sensitive_data': 'authorized',
                'financial_data': 'full_budget',
                'personnel_data': 'department_wide'
            },
            'executive': {
                'data_access': 'company_wide',
                'sensitive_data': 'full_access',
                'financial_data': 'complete',
                'personnel_data': 'company_wide'
            }
        }
        
        return permission_levels.get(user_role, permission_levels['employee'])
    
    def _build_user_specific_context(self, user_context: UserContext) -> Dict[str, Any]:
        """Build user-specific context information"""
        
        return {
            'expertise_level': user_context.expertise_level,
            'preferred_communication_style': self._determine_communication_style(user_context),
            'time_constraints': user_context.time_constraint,
            'output_preferences': user_context.output_preference,
            'previous_interaction_patterns': self._analyze_previous_queries(user_context.previous_queries),
            'current_focus_areas': [user_context.current_project] if user_context.current_project else [],
            'personalization_factors': self._get_personalization_factors(user_context)
        }
    
    def _determine_communication_style(self, user_context: UserContext) -> str:
        """Determine appropriate communication style for user"""
        
        style_mapping = {
            ('executive', 'expert'): 'executive_summary',
            ('executive', 'intermediate'): 'strategic_overview',
            ('manager', 'expert'): 'managerial_detail',
            ('manager', 'intermediate'): 'balanced_approach',
            ('employee', 'expert'): 'technical_focus',
            ('employee', 'intermediate'): 'explanatory',
            ('employee', 'beginner'): 'educational'
        }
        
        key = (user_context.user_role, user_context.expertise_level)
        return style_mapping.get(key, 'balanced_approach')
    
    async def _assess_data_availability(
        self, 
        required_data_sources: List[str], 
        user_context: UserContext
    ) -> Dict[str, Any]:
        """Assess availability of required data sources"""
        
        availability_status = {}
        
        for data_source in required_data_sources:
            # Check if user has access to this data source
            has_access = self._check_data_source_access(data_source, user_context)
            
            # Check if data source is currently available
            is_available = self._check_data_source_status(data_source)
            
            # Estimate data freshness
            freshness = self._get_data_freshness(data_source)
            
            availability_status[data_source] = {
                'accessible': has_access,
                'available': is_available,
                'freshness': freshness,
                'alternative_sources': self._get_alternative_sources(data_source) if not (has_access and is_available) else []
            }
        
        return {
            'source_status': availability_status,
            'overall_availability': all(
                status['accessible'] and status['available'] 
                for status in availability_status.values()
            ),
            'missing_sources': [
                source for source, status in availability_status.items()
                if not (status['accessible'] and status['available'])
            ],
            'data_quality_notes': self._get_data_quality_notes(required_data_sources)
        }
    
    def _determine_processing_constraints(
        self, 
        task_analysis: TaskAnalysis, 
        user_context: UserContext
    ) -> Dict[str, Any]:
        """Determine processing constraints and limitations"""
        
        return {
            'time_constraints': {
                'user_preference': user_context.time_constraint,
                'estimated_processing_time': task_analysis.estimated_processing_time,
                'complexity_factor': task_analysis.complexity.value
            },
            'resource_constraints': {
                'computational_complexity': self._estimate_computational_needs(task_analysis),
                'memory_requirements': self._estimate_memory_needs(task_analysis),
                'external_api_calls': self._estimate_api_calls(task_analysis)
            },
            'quality_constraints': {
                'accuracy_requirements': self._determine_accuracy_requirements(user_context),
                'validation_needs': self._determine_validation_needs(task_analysis),
                'error_tolerance': self._determine_error_tolerance(user_context)
            },
            'security_constraints': {
                'data_sensitivity': self._assess_data_sensitivity(task_analysis),
                'access_controls': self._get_access_controls(user_context),
                'audit_requirements': self._get_audit_requirements(task_analysis, user_context)
            }
        }
```

This specification provides a comprehensive framework for transforming user inputs into exceptionally clear, actionable prompts. The system includes:

1. **Intent Analysis**: Deep understanding of what users actually want to accomplish
2. **Context Enrichment**: Adding relevant business context, constraints, and requirements
3. **Prompt Generation**: Creating optimized prompts following best practices
4. **Quality Validation**: Ensuring prompts meet high standards before processing
5. **Adaptive Learning**: Improving over time based on processing outcomes

The enriched prompts will provide processing agents with clear objectives, comprehensive context, specific constraints, and detailed success criteria, significantly improving their ability to fulfill user requests accurately and efficiently.
