"""
Diagnostic Agent for Talent Intelligence System.

This agent analyzes job descriptions and ideal candidate profiles for ANY role type,
producing structured diagnostic reports with attribute weights and strategic insights.

Role-agnostic: dynamically adapts analysis based on the target role provided.
Strategic LLM Usage: Uses gpt-4o-mini for cost-effective reasoning.
Outputs: Structured DiagnosticReport Pydantic model.
"""

from typing import Dict, Any, Optional
from crewai import Agent, Task, Crew, LLM
from pydantic import BaseModel, Field
import json

from src.models.talent_analysis import (
    DiagnosticReport, AttributePriority, PatternType, BaselineProfile
)
from src.core.logging import get_logger, LogCategory
from src.core.config import get_settings
from src.services.langfuse_service import get_langfuse_service
from src.services.talent.pdl_query_rules import (
    PDL_FIELD_RULES,
    QUERY_STRATEGIES,
    recommend_query_strategy
)

logger = get_logger(__name__, component="talent.diagnostic_agent")
settings = get_settings()


class DiagnosticInput(BaseModel):
    """Input for diagnostic analysis"""
    job_description: str = Field(description="The job description text")
    ideal_candidate_description: str = Field(description="Natural language description of ideal candidate")
    baseline_profile: BaselineProfile = Field(description="Baseline profile from current employees in target role")
    role: str = Field(default="", description="Optional role hint. The diagnostic agent will extract the actual role from the job description.")


class DiagnosticAgentService:
    """
    Service for running the Diagnostic Agent.
    
    The agent analyzes inputs and produces a structured diagnostic report
    with attribute weights, patterns to look for, and strategic insights.
    """
    
    def __init__(
        self,
        customer_id: str,
        user_id: int,
        llm_provider: str = "openai",
        llm_model: str = "gpt-4o-mini"
    ):
        """
        Initialize the diagnostic agent service.
        
        Args:
            customer_id: Customer ID for the analysis
            user_id: User ID requesting the analysis
            llm_provider: LLM provider (default: openai)
            llm_model: LLM model (default: gpt-4o-mini for cost-effective reasoning)
        """
        self.customer_id = customer_id
        self.user_id = user_id
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.llm = self._build_llm()
        self.langfuse_service = get_langfuse_service()
        self.trace_id = self.langfuse_service.current_trace_id
        
        logger.info(
            "diagnostic_agent_initialized",
            customer_id=customer_id,
            user_id=user_id,
            llm_provider=llm_provider,
            llm_model=llm_model
        )
    
    def _build_llm(self) -> LLM:
        """Build LLM client from configuration."""
        if self.llm_provider == "openai":
            return LLM(
                model=f"openai/{self.llm_model}",
                api_key=settings.openai_api_key,
                temperature=0.3  # Lower temp for more consistent analysis
            )
        else:
            # Add other providers as needed (Anthropic, Bedrock, etc.)
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")
    
    def _create_diagnostic_agent(self) -> Agent:
        """Create the diagnostic agent with proper configuration."""
        return Agent(
            role="Talent Diagnostic Analyst",
            goal=(
                "Analyze job descriptions and ideal candidate profiles to determine "
                "the most important attributes for the target role. "
                "Produce structured, actionable insights with clear prioritization "
                "that are tailored to the specific role being hired for."
            ),
            backstory=(
                "You are an expert talent analyst with deep understanding of "
                "diverse professional roles across engineering, product, design, "
                "data science, sales, and more. You analyze job requirements, "
                "candidate descriptions, and baseline employee data to identify "
                "the key attributes that predict success for ANY role type. "
                "You prioritize attributes based on business impact, technical "
                "complexity, and cultural fit. You think in terms of patterns: "
                "career trajectories, skill combinations, company backgrounds, "
                "and achievement indicators. Your analysis directly informs how "
                "candidates will be scored and ranked."
            ),
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
            max_iter=3
        )
    
    def _create_diagnostic_task(
        self,
        agent: Agent,
        diagnostic_input: DiagnosticInput
    ) -> Task:
        """Create the diagnostic task with structured output format."""
        
        # Build context about baseline
        baseline_context = self._format_baseline_context(diagnostic_input.baseline_profile)
        
        target_role = diagnostic_input.role
        
        if target_role:
            role_instruction = f"""Analyze the following inputs to determine the optimal attribute weights and patterns
for scoring **{target_role}** candidates:

**TARGET ROLE:** {target_role}"""
        else:
            role_instruction = """Analyze the following inputs to determine the optimal attribute weights and patterns
for scoring candidates. First, identify the target role from the job description, then analyze accordingly.

**TARGET ROLE:** (determine from the job description below)"""
        
        task_description = f"""
{role_instruction}

**JOB DESCRIPTION:**
{diagnostic_input.job_description}

**IDEAL CANDIDATE DESCRIPTION:**
{diagnostic_input.ideal_candidate_description}

**BASELINE EMPLOYEE PROFILE:**
{baseline_context}

**YOUR TASK:**
1. Identify the exact role/title from the job description and set it as role_type
2. Determine seniority level (Mid, Senior, Staff, Principal)
3. Assess competency priorities for THIS SPECIFIC ROLE (research vs production vs operations vs leadership)
4. Identify required and preferred skills SPECIFIC TO THE TARGET ROLE
5. Define attribute weights for scoring dimensions
6. Formulate key hypotheses about ideal candidates for THIS ROLE
7. Provide baseline query parameters

IMPORTANT: Your analysis must be driven entirely by the job description, ideal candidate
description, and baseline data provided. Do NOT default to any particular role type's
skill set. Derive all skills, priorities, and weights from the inputs.
The role_type in your output MUST reflect the actual role described in the job description.

**PDL QUERY CONSTRUCTION RULES:**
When identifying skills and query parameters, follow these empirically validated rules:

Field Guidelines:
- job_title_role: Use standardized values only ("engineering", "sales", "marketing", etc.) - NOT specific titles
- job_title: Use for specific job titles with free text (e.g., the role title from the job description, lowercased)
- skills: Use specific technology/skill names in lowercase derived from the job description
- location_country: Always use full country names in lowercase (e.g., "united states")
- job_company_name: Use for targeting candidates from specific companies

Query Strategies:
- Targeted Search: Use job_title + 2-5 skills + location
- Precision Search: Add more skills for niche requirements (10-1K candidates)
- Company Cluster: Target specific companies if baseline shows patterns

Critical Rules:
- Use 2-5 required skills maximum (too many = 0 results)
- All values must be lowercase
- Don't use "minimum_should_match" or complex "should" clauses
- Don't use job_title_levels unless specifically needed (can over-constrain)

**OUTPUT FORMAT:**
You MUST respond with a valid JSON object matching this EXACT schema:
{{
    "role_type": "(the exact role title extracted from the job description)",
    "seniority_level": "Senior",
    "ml_competencies": {{
        "research_focus": float (0.0-1.0, how much this role emphasizes research/innovation),
        "production_focus": float (0.0-1.0, how much this role emphasizes production/delivery),
        "mlops_focus": float (0.0-1.0, how much this role emphasizes operations/infrastructure),
        "leadership_potential": float (0.0-1.0, how much leadership is valued)
    }},
    "required_skills": ["skill1", "skill2", "skill3"],
    "preferred_skills": ["skill1", "skill2"],
    "attribute_weights": [
        {{
            "attribute": "technical_skills",
            "weight": float (0.0-1.0),
            "reason": "explanation"
        }},
        {{
            "attribute": "experience_level",
            "weight": float (0.0-1.0),
            "reason": "explanation"
        }},
        {{
            "attribute": "domain_expertise",
            "weight": float (0.0-1.0),
            "reason": "explanation"
        }},
        {{
            "attribute": "company_background",
            "weight": float (0.0-1.0),
            "reason": "explanation"
        }},
        {{
            "attribute": "education_pedigree",
            "weight": float (0.0-1.0),
            "reason": "explanation"
        }},
        {{
            "attribute": "career_trajectory",
            "weight": float (0.0-1.0),
            "reason": "explanation"
        }}
    ],
    "key_hypotheses": [
        "hypothesis 1 about ideal candidates for this role",
        "hypothesis 2 about success factors"
    ],
    "baseline_query_params": {{
        "min_years_experience": int,
        "required_skills": ["skill1", "skill2"],
        "preferred_companies": ["company1", "company2"]
    }},
    "confidence": float (0.0-1.0)
}}

**GUIDELINES:**
- ml_competencies values should sum to approximately 1.0
- attribute_weights should cover the 6 key scoring dimensions
- Total attribute weights should sum to approximately 1.0
- required_skills: Must-have skills DERIVED FROM THE JOB DESCRIPTION (not assumed)
- preferred_skills: Nice-to-have skills from the job description
- key_hypotheses: 3-5 hypotheses about what makes a great candidate for THIS role
- baseline_query_params: Criteria for finding similar employees

Focus on the skills, experience, and attributes that matter most for the role described in the
job description and ideal candidate description. Do NOT assume skills that are not mentioned
in the inputs.
"""
        
        return Task(
            description=task_description,
            agent=agent,
            expected_output="A valid JSON object containing the structured diagnostic report"
        )
    
    def _format_baseline_context(self, baseline: BaselineProfile) -> str:
        """Format baseline profile into readable context."""
        employee_count = len(baseline.prototype_employee_ids)
        
        # Format skills
        skills_list = list(baseline.skill_distributions.keys())[:10]
        skills_summary = f"Top skills: {', '.join(skills_list)}" if skills_list else "No skill data"
        
        # Format career paths
        paths_summary = "Common career paths:\n"
        if baseline.common_career_paths:
            for path in baseline.common_career_paths[:3]:
                paths_summary += f"  - {path.path_description} (frequency: {path.frequency})\n"
        else:
            paths_summary += "  - No career path data\n"
        
        # Format companies
        companies_summary = f"Common companies: {', '.join(baseline.company_clusters[:5])}" if baseline.company_clusters else "No company data"
        
        return f"""
Employee Count: {employee_count}
Average Experience: {baseline.average_years_experience:.1f} years
{skills_summary}
{paths_summary}
{companies_summary}
Success Patterns: {', '.join(baseline.success_patterns[:3])}
Data Quality Score: {baseline.data_quality_score:.2f}
"""
    
    def _parse_diagnostic_output(self, raw_output: str) -> DiagnosticReport:
        """
        Parse the agent's raw output into a DiagnosticReport.
        
        The agent should output valid JSON. We parse and validate it.
        """
        try:
            # Try to find JSON in the output (agent might add extra text)
            json_start = raw_output.find('{')
            json_end = raw_output.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON object found in agent output")
            
            json_str = raw_output[json_start:json_end]
            data = json.loads(json_str)
            
            # Convert to Pydantic model (this validates the structure)
            diagnostic_report = DiagnosticReport(**data)
            
            logger.info(
                "diagnostic_report_parsed",
                attribute_count=len(diagnostic_report.attribute_weights),
                hypothesis_count=len(diagnostic_report.key_hypotheses),
                confidence=diagnostic_report.confidence
            )
            
            return diagnostic_report
            
        except Exception as e:
            logger.error(
                "diagnostic_parsing_failed",
                error=str(e),
                raw_output=raw_output[:500],  # Log first 500 chars
                exc_info=True
            )
            raise ValueError(f"Failed to parse diagnostic output: {str(e)}")
    
    def analyze(self, diagnostic_input: DiagnosticInput) -> DiagnosticReport:
        """
        Run diagnostic analysis.
        
        Args:
            diagnostic_input: Job description, ideal candidate, and baseline data
            
        Returns:
            DiagnosticReport with structured analysis
            
        Raises:
            ValueError: If output parsing fails
        """
        logger.info(
            "diagnostic_analysis_start",
            customer_id=self.customer_id,
            user_id=self.user_id,
            role=diagnostic_input.role
        )
        
        try:
            # Create agent and task
            agent = self._create_diagnostic_agent()
            task = self._create_diagnostic_task(agent, diagnostic_input)
            
            # Create crew and execute
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=True
            )
            
            logger.debug("diagnostic_crew_executing")
            with self.langfuse_service.span_scope(
                name="agentmesh.talent.diagnostic_agent.analyze",
                input_data={
                    "role": diagnostic_input.role,
                    "job_description": diagnostic_input.job_description[:4000],
                    "ideal_candidate_description": diagnostic_input.ideal_candidate_description[:4000],
                    "baseline_employee_count": len(diagnostic_input.baseline_profile.prototype_employee_ids),
                },
                metadata={
                    "component": "agentmesh",
                    "flow": "talent_orchestrator",
                    "service": "diagnostic_agent",
                    "customer_id": self.customer_id,
                    "user_id": self.user_id,
                    "llm_provider": self.llm_provider,
                    "llm_model": self.llm_model,
                },
                trace_id=self.trace_id,
            ) as span_info:
                result = crew.kickoff()
                
                # Parse output
                diagnostic_report = self._parse_diagnostic_output(result.raw)
                
                observation = span_info.get("observation")
                if observation is not None:
                    try:
                        observation.update(
                            output={
                                "confidence": diagnostic_report.confidence,
                                "attribute_count": len(diagnostic_report.attribute_weights),
                                "required_skill_count": len(diagnostic_report.required_skills),
                                "hypothesis_count": len(diagnostic_report.key_hypotheses),
                            }
                        )
                    except Exception:
                        pass
            
            logger.info(
                "diagnostic_analysis_complete",
                customer_id=self.customer_id,
                user_id=self.user_id,
                confidence=diagnostic_report.confidence,
                attribute_count=len(diagnostic_report.attribute_weights)
            )
            
            return diagnostic_report
            
        except Exception as e:
            logger.error(
                "diagnostic_analysis_failed",
                customer_id=self.customer_id,
                user_id=self.user_id,
                error=str(e),
                exc_info=True
            )
            raise
