# User Task Enrichment - Additional Components

## Prompt Generation Component

```python
# From prompt generation patterns - EXAMPLE

@dataclass
class GeneratedPrompt:
    """Generated prompt with metadata"""
    prompt_text: str
    processing_instructions: Dict[str, Any]
    output_format: Dict[str, Any]
    validation_criteria: List[str]
    quality_score: float
    quality_level: PromptQuality
    generation_metadata: Dict[str, Any]

class PromptGenerator:
    """Generates optimized prompts using templates, best practices, and example prompts"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = openai.OpenAI(
            api_key=config.get('api_key'),
            base_url=config.get('api_base_url', 'http://localhost:5001/inf')
        )
        
        # Load example prompts from prompt_examples directory
        self.prompt_examples = self._load_prompt_examples()
        self.example_matcher = PromptExampleMatcher(self.prompt_examples)
    
    async def generate_prompt(
        self,
        user_input: str,
        task_analysis: TaskAnalysis,
        enriched_context: Dict[str, Any],
        user_context: UserContext,
        rag_context: Optional['RAGRetrievalResult'] = None
    ) -> GeneratedPrompt:
        """Generate optimized prompt for processing agent"""
        
        # Step 1: Find relevant example prompts
        relevant_examples = self.example_matcher.find_relevant_examples(
            user_input, task_analysis, user_context
        )
        
        # Step 2: Select appropriate template
        template_info = self._select_template(task_analysis.intent_type)
        
        # Step 3: Prepare template variables
        template_vars = self._prepare_template_variables(
            user_input, task_analysis, enriched_context, user_context, rag_context
        )
        
        # Step 4: Generate base prompt from template
        base_prompt = template_info['template'].format(**template_vars)
        
        # Step 5: Enhance with example prompts and best practices
        enhanced_prompt = await self._enhance_with_examples_and_best_practices(
            base_prompt, relevant_examples, task_analysis, user_context
        )
        
        # Step 6: Add processing instructions
        processing_instructions = self._generate_processing_instructions(
            task_analysis, enriched_context, user_context
        )
        
        # Step 7: Define output format
        output_format = self._define_output_format(task_analysis, user_context)
        
        # Step 8: Create validation criteria
        validation_criteria = self._create_validation_criteria(task_analysis, user_context)
        
        # Step 9: Calculate initial quality score
        quality_score = self._calculate_quality_score(enhanced_prompt, task_analysis)
        quality_level = self._determine_quality_level(quality_score)
        
        return GeneratedPrompt(
            prompt_text=enhanced_prompt,
            processing_instructions=processing_instructions,
            output_format=output_format,
            validation_criteria=validation_criteria,
            quality_score=quality_score,
            quality_level=quality_level,
            generation_metadata={
                'template_used': task_analysis.intent_type.value,
                'enhancement_applied': True,
                'context_sources': list(enriched_context.keys()),
                'generation_timestamp': datetime.utcnow().isoformat()
            }
        )
    
    async def _enhance_with_best_practices(
        self,
        base_prompt: str,
        task_analysis: TaskAnalysis,
        user_context: UserContext
    ) -> str:
        """Enhance prompt using best practices"""
        
        enhancement_prompt = f"""
        Enhance the following prompt to make it exceptionally clear and actionable for an AI agent.
        Apply these best practices:
        
        1. **Clarity**: Make instructions crystal clear and unambiguous
        2. **Specificity**: Add specific details and examples where helpful
        3. **Structure**: Organize information logically with clear sections
        4. **Context**: Ensure sufficient context for accurate completion
        5. **Constraints**: Clearly state any limitations or requirements
        6. **Success Criteria**: Define what constitutes successful completion
        7. **Output Format**: Specify exactly how the response should be structured
        
        Task Complexity: {task_analysis.complexity.value}
        User Expertise: {user_context.expertise_level}
        
        Original Prompt:
        {base_prompt}
        
        Enhanced Prompt:
        """
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.get('enhancement_model', 'meta-llama/Llama-3.1-70B-Instruct'),
                messages=[
                    {"role": "system", "content": "You are an expert at creating clear, actionable prompts for AI agents. Enhance prompts to maximize success rates."},
                    {"role": "user", "content": enhancement_prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            enhanced = response.choices[0].message.content.strip()
            
            # Validate enhancement
            if len(enhanced) > len(base_prompt) * 0.8:  # Should be substantially enhanced
                return enhanced
            else:
                return base_prompt  # Fallback to original if enhancement failed
                
        except Exception as e:
            # Fallback to base prompt if enhancement fails
            return base_prompt
```

## Quality Validation Component

```python
# From quality validation patterns - EXAMPLE

class PromptQualityValidator:
    """Validates and refines prompt quality before processing"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = openai.OpenAI(
            api_key=config.get('api_key'),
            base_url=config.get('api_base_url', 'http://localhost:5001/inf')
        )
        
        # Quality assessment criteria
        self.quality_criteria = {
            'clarity': {
                'weight': 0.25,
                'indicators': ['clear_objective', 'unambiguous_language', 'logical_structure']
            },
            'completeness': {
                'weight': 0.20,
                'indicators': ['all_requirements_specified', 'context_provided', 'constraints_defined']
            },
            'actionability': {
                'weight': 0.20,
                'indicators': ['specific_instructions', 'clear_success_criteria', 'defined_output_format']
            },
            'context_richness': {
                'weight': 0.15,
                'indicators': ['business_context', 'user_context', 'domain_knowledge']
            },
            'optimization': {
                'weight': 0.20,
                'indicators': ['best_practices_applied', 'agent_specific_guidance', 'error_handling']
            }
        }
    
    async def validate_and_refine(
        self,
        generated_prompt: GeneratedPrompt,
        task_analysis: TaskAnalysis
    ) -> GeneratedPrompt:
        """Validate prompt quality and refine if necessary"""
        
        # Step 1: Assess current quality
        quality_assessment = await self._assess_prompt_quality(
            generated_prompt.prompt_text, task_analysis
        )
        
        # Step 2: Identify improvement areas
        improvement_areas = self._identify_improvement_areas(quality_assessment)
        
        # Step 3: Refine if needed
        if quality_assessment['overall_score'] < 0.8 or improvement_areas:
            refined_prompt = await self._refine_prompt(
                generated_prompt, improvement_areas, task_analysis
            )
            
            # Re-assess quality
            refined_assessment = await self._assess_prompt_quality(
                refined_prompt, task_analysis
            )
            
            # Update with refined version if better
            if refined_assessment['overall_score'] > quality_assessment['overall_score']:
                generated_prompt.prompt_text = refined_prompt
                generated_prompt.quality_score = refined_assessment['overall_score']
                generated_prompt.quality_level = self._determine_quality_level(refined_assessment['overall_score'])
        
        return generated_prompt
    
    async def _assess_prompt_quality(
        self,
        prompt_text: str,
        task_analysis: TaskAnalysis
    ) -> Dict[str, Any]:
        """Assess prompt quality across multiple dimensions"""
        
        assessment_prompt = f"""
        Assess the quality of the following prompt for an AI agent. Rate each dimension from 0.0 to 1.0:

        PROMPT TO ASSESS:
        {prompt_text}

        TASK CONTEXT:
        - Intent: {task_analysis.intent_type.value}
        - Complexity: {task_analysis.complexity.value}
        - Main Objective: {task_analysis.main_objective}

        Please assess and respond with JSON:
        {{
            "clarity": {{
                "score": 0.0-1.0,
                "reasoning": "explanation",
                "improvements": ["specific suggestions"]
            }},
            "completeness": {{
                "score": 0.0-1.0,
                "reasoning": "explanation", 
                "improvements": ["specific suggestions"]
            }},
            "actionability": {{
                "score": 0.0-1.0,
                "reasoning": "explanation",
                "improvements": ["specific suggestions"]
            }},
            "context_richness": {{
                "score": 0.0-1.0,
                "reasoning": "explanation",
                "improvements": ["specific suggestions"]
            }},
            "optimization": {{
                "score": 0.0-1.0,
                "reasoning": "explanation",
                "improvements": ["specific suggestions"]
            }},
            "overall_assessment": "summary of strengths and weaknesses",
            "critical_issues": ["issues that must be addressed"]
        }}
        """
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.get('validation_model', 'meta-llama/Llama-3.1-70B-Instruct'),
                messages=[
                    {"role": "system", "content": "You are an expert at evaluating prompt quality for AI agents. Provide detailed, constructive assessments."},
                    {"role": "user", "content": assessment_prompt}
                ],
                temperature=0.1,
                max_tokens=1500
            )
            
            assessment_text = response.choices[0].message.content.strip()
            
            # Clean and parse JSON
            if assessment_text.startswith('```json'):
                assessment_text = assessment_text[7:-3]
            elif assessment_text.startswith('```'):
                assessment_text = assessment_text[3:-3]
            
            assessment = json.loads(assessment_text)
            
            # Calculate weighted overall score
            overall_score = 0.0
            for criterion, config in self.quality_criteria.items():
                if criterion in assessment:
                    overall_score += assessment[criterion]['score'] * config['weight']
            
            assessment['overall_score'] = overall_score
            return assessment
            
        except Exception as e:
            # Fallback assessment
            return {
                'clarity': {'score': 0.7, 'improvements': []},
                'completeness': {'score': 0.7, 'improvements': []},
                'actionability': {'score': 0.7, 'improvements': []},
                'context_richness': {'score': 0.7, 'improvements': []},
                'optimization': {'score': 0.7, 'improvements': []},
                'overall_score': 0.7,
                'overall_assessment': 'Assessment unavailable',
                'critical_issues': []
            }
```

## Integration Examples

### FastAPI Integration

```python
# From FastAPI integration patterns - TESTED
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class TaskEnrichmentRequest(BaseModel):
    user_input: str
    user_id: str
    session_id: str
    user_role: str = "employee"
    department: str = ""
    expertise_level: str = "intermediate"
    time_constraint: str = "normal"
    output_preference: str = "detailed"
    current_project: Optional[str] = None

class TaskEnrichmentResponse(BaseModel):
    enriched_prompt: str
    processing_instructions: Dict[str, Any]
    expected_output_format: Dict[str, Any]
    validation_criteria: List[str]
    metadata: Dict[str, Any]

app = FastAPI()
enrichment_agent = UserTaskEnrichmentAgent(config={
    'api_key': 'your-api-key',
    'api_base_url': 'http://localhost:5001/inf'
})

@app.post("/enrich-task", response_model=TaskEnrichmentResponse)
async def enrich_user_task(request: TaskEnrichmentRequest):
    """Enrich user task into optimized prompt"""
    
    try:
        # Create user context
        user_context = UserContext(
            user_id=request.user_id,
            session_id=request.session_id,
            user_role=request.user_role,
            department=request.department,
            expertise_level=request.expertise_level,
            time_constraint=request.time_constraint,
            output_preference=request.output_preference,
            current_project=request.current_project or ""
        )
        
        # Enrich the task
        enriched_prompt = await enrichment_agent.enrich_user_task(
            request.user_input, user_context
        )
        
        return TaskEnrichmentResponse(**enriched_prompt.to_dict())
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task enrichment failed: {str(e)}")

@app.get("/enrichment-metrics")
async def get_enrichment_metrics():
    """Get enrichment performance metrics"""
    return enrichment_agent.enrichment_metrics
```

### CrewAI Flow Integration

```python
# From CrewAI flow integration patterns - EXAMPLE
from crewai import Flow, Agent, Task

class EnrichedTaskFlow(Flow):
    """Flow that uses task enrichment before processing"""
    
    def __init__(self, enrichment_agent: UserTaskEnrichmentAgent):
        super().__init__()
        self.enrichment_agent = enrichment_agent
        self.processing_agents = self._create_processing_agents()
    
    async def execute_enriched_task(
        self,
        user_input: str,
        user_context: UserContext
    ) -> Dict[str, Any]:
        """Execute task with enrichment preprocessing"""
        
        # Step 1: Enrich the user task
        enriched_prompt = await self.enrichment_agent.enrich_user_task(
            user_input, user_context
        )
        
        # Step 2: Select appropriate processing agent
        agent_type = enriched_prompt.task_analysis.recommended_agent_type
        processing_agent = self.processing_agents.get(agent_type, self.processing_agents['general_agent'])
        
        # Step 3: Create task with enriched prompt
        task = Task(
            description=enriched_prompt.enriched_prompt,
            expected_output=enriched_prompt.expected_output_format,
            agent=processing_agent
        )
        
        # Step 4: Execute the task
        result = await processing_agent.execute(task)
        
        # Step 5: Validate result against criteria
        validation_result = self._validate_result(result, enriched_prompt.validation_criteria)
        
        return {
            'result': result,
            'validation': validation_result,
            'enrichment_metadata': enriched_prompt.to_dict()['metadata']
        }
    
    def _create_processing_agents(self) -> Dict[str, Agent]:
        """Create specialized processing agents"""
        return {
            'research_agent': Agent(
                role="Research Specialist",
                goal="Find and analyze information to answer questions accurately",
                backstory="Expert researcher with access to comprehensive data sources"
            ),
            'analyst_agent': Agent(
                role="Data Analyst",
                goal="Analyze data and provide insights with statistical rigor",
                backstory="Experienced data analyst skilled in quantitative analysis"
            ),
            'writer_agent': Agent(
                role="Professional Writer",
                goal="Create well-structured, professional reports and documents",
                backstory="Expert writer with business communication expertise"
            ),
            'advisor_agent': Agent(
                role="Strategic Advisor",
                goal="Provide strategic recommendations based on analysis",
                backstory="Senior consultant with expertise in strategic planning"
            ),
            'general_agent': Agent(
                role="General Assistant",
                goal="Handle diverse tasks with adaptability and accuracy",
                backstory="Versatile assistant capable of handling various requests"
            )
        }
    
    def _validate_result(self, result: Any, validation_criteria: List[str]) -> Dict[str, Any]:
        """Validate result against enrichment criteria"""
        
        validation_results = {
            'criteria_met': [],
            'criteria_failed': [],
            'overall_score': 0.0,
            'recommendations': []
        }
        
        # Simple validation logic (could be enhanced with LLM validation)
        for criterion in validation_criteria:
            # Basic heuristic validation
            if self._check_criterion(result, criterion):
                validation_results['criteria_met'].append(criterion)
            else:
                validation_results['criteria_failed'].append(criterion)
        
        # Calculate overall score
        total_criteria = len(validation_criteria)
        met_criteria = len(validation_results['criteria_met'])
        validation_results['overall_score'] = met_criteria / total_criteria if total_criteria > 0 else 1.0
        
        # Add recommendations for failed criteria
        if validation_results['criteria_failed']:
            validation_results['recommendations'] = [
                f"Address criterion: {criterion}" for criterion in validation_results['criteria_failed']
            ]
        
        return validation_results
    
    def _check_criterion(self, result: Any, criterion: str) -> bool:
        """Basic criterion checking (could be enhanced)"""
        result_str = str(result).lower()
        criterion_lower = criterion.lower()
        
        # Simple keyword-based validation
        if 'addresses' in criterion_lower and 'objective' in criterion_lower:
            return len(result_str) > 50  # Has substantial content
        elif 'accurate' in criterion_lower:
            return 'error' not in result_str and 'unknown' not in result_str
        elif 'format' in criterion_lower:
            return len(result_str) > 20  # Has some structure
        else:
            return True  # Default to pass for unknown criteria
```

## Best Practice Examples

### Example Transformations

```python
# From transformation examples - EXAMPLE

class TransformationExamples:
    """Examples of user input transformations"""
    
    @staticmethod
    def get_examples() -> List[Dict[str, str]]:
        return [
            {
                "user_input": "What's our sales performance?",
                "enriched_prompt": """
                You are a business analyst tasked with providing a comprehensive sales performance analysis.

                **Primary Objective:** Analyze current sales performance and provide actionable insights

                **Analysis Requirements:**
                - Time period: Current quarter vs. same quarter last year
                - Key metrics: Revenue, units sold, average deal size, conversion rates
                - Segmentation: By region, product line, and sales team
                - Trend analysis: Monthly progression and seasonal patterns

                **Context Information:**
                - User Role: Manager
                - Department: Sales
                - Expertise Level: Intermediate
                - Time Constraint: Normal priority

                **Available Data Sources:**
                - CRM system (current and historical sales data)
                - Financial reporting system
                - Regional performance databases

                **Expected Output Format:**
                1. Executive Summary (key findings in 3-4 bullet points)
                2. Current Performance Metrics (with YoY comparisons)
                3. Trend Analysis (visual representations preferred)
                4. Performance by Segment (top performers and areas of concern)
                5. Actionable Recommendations (3-5 specific actions)

                **Success Criteria:**
                - Provide accurate data-driven insights
                - Include both positive trends and areas needing attention
                - Offer specific, actionable recommendations
                - Present information appropriate for management review

                **Additional Instructions:**
                - If data is incomplete, clearly state limitations
                - Include confidence levels for projections
                - Highlight any unusual patterns or anomalies
                """
            },
            {
                "user_input": "Create a report about employee satisfaction",
                "enriched_prompt": """
                You are an HR analyst tasked with creating a comprehensive employee satisfaction report.

                **Report Purpose:** Assess current employee satisfaction levels and identify improvement opportunities

                **Target Audience:** HR leadership and executive team

                **Report Scope and Structure:**
                1. Executive Summary
                2. Methodology and Data Sources
                3. Overall Satisfaction Metrics
                4. Satisfaction by Department/Role
                5. Key Satisfaction Drivers
                6. Areas of Concern
                7. Recommendations and Action Plan
                8. Appendices (detailed data tables)

                **Data Sources and Information:**
                - Recent employee satisfaction surveys (last 12 months)
                - Exit interview data
                - Performance review feedback
                - Benefits utilization data
                - Comparative industry benchmarks

                **Report Requirements:**
                - Executive Summary: 1-page overview with key findings and recommendations
                - Main Content: 8-12 pages with detailed analysis
                - Supporting Data: Charts, graphs, and statistical analysis
                - Conclusions: Specific, actionable recommendations with timelines

                **Analysis Framework:**
                - Overall satisfaction scores and trends
                - Satisfaction drivers (compensation, work-life balance, management, growth opportunities)
                - Demographic analysis (tenure, department, role level)
                - Correlation with retention and performance metrics
                - Benchmark comparison with industry standards

                **Formatting and Style:**
                - Professional business report format
                - Include visual elements (charts, graphs, infographics)
                - Executive-level writing style
                - Clear section headings and page numbering

                **Quality Standards:**
                - Data accuracy and statistical validity
                - Clear methodology explanation
                - Actionable insights with business impact
                - Professional presentation ready for executive review

                **Success Criteria:**
                - Provides clear picture of employee satisfaction status
                - Identifies specific areas for improvement
                - Includes benchmarked performance context
                - Offers prioritized action plan with expected outcomes
                """
            }
        ]
```

This comprehensive system transforms basic user requests into detailed, actionable prompts that processing agents can execute with high success rates. The enrichment process adds crucial context, clarifies intent, and provides specific guidance for optimal results.
