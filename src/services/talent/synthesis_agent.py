"""
Synthesis Agent for Talent Intelligence System.

This agent takes scored candidates and analysis results, then synthesizes
a high-quality report with rankings, explanations, and recommendations.

Strategic LLM Usage: Uses claude-3-5-sonnet for high-quality synthesis and writing.
Outputs: Structured SynthesisReport Pydantic model.
"""

from typing import List, Dict, Any, Optional
from crewai import Agent, Task, Crew, LLM
from pydantic import BaseModel, Field
import json

from src.models.talent_analysis import (
    SynthesisReport, CandidateScore, DiagnosticReport,
    PatternInsight, CandidateSource
)
from src.core.logging import get_logger, LogCategory
from src.core.config import get_settings
from src.services.langfuse_service import get_langfuse_service

logger = get_logger(__name__, component="talent.synthesis_agent")
settings = get_settings()


class SynthesisInput(BaseModel):
    """Input for synthesis analysis"""
    diagnostic_report: DiagnosticReport = Field(description="Diagnostic analysis results")
    applicant_scores: List[CandidateScore] = Field(description="Scored applicants")
    market_scores: List[CandidateScore] = Field(description="Scored market candidates")
    top_overall_count: int = Field(default=3, description="Number of top overall candidates")


class SynthesisAgentService:
    """
    Service for running the Synthesis Agent.
    
    The agent synthesizes all analysis results into a cohesive report
    with clear explanations, rankings, and actionable recommendations.
    """
    
    def __init__(
        self,
        customer_id: str,
        user_id: int,
        llm_provider: str = "openai",
        llm_model: str = "gpt-4o"
    ):
        """
        Initialize the synthesis agent service.
        
        Args:
            customer_id: Customer ID for the analysis
            user_id: User ID requesting the analysis
            llm_provider: LLM provider (default: openai)
            llm_model: LLM model (default: gpt-4o for quality synthesis)
        """
        self.customer_id = customer_id
        self.user_id = user_id
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.llm = self._build_llm()
        self.langfuse_service = get_langfuse_service()
        self.trace_id = self.langfuse_service.current_trace_id
        
        logger.info(
            "synthesis_agent_initialized",
            customer_id=customer_id,
            user_id=user_id,
            llm_provider=llm_provider,
            llm_model=llm_model
        )
    
    def _build_llm(self) -> LLM:
        """Build LLM client from configuration."""
        if self.llm_provider == "anthropic":
            return LLM(
                model=f"anthropic/{self.llm_model}",
                api_key=settings.anthropic_api_key,
                temperature=0.7  # Moderate temp for natural writing
            )
        elif self.llm_provider == "openai":
            return LLM(
                model=f"openai/{self.llm_model}",
                api_key=settings.openai_api_key,
                temperature=0.7
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")
    
    def _create_synthesis_agent(self) -> Agent:
        """Create the synthesis agent with proper configuration."""
        return Agent(
            role="Talent Intelligence Report Synthesizer",
            goal=(
                "Synthesize candidate analysis into clear, actionable reports that "
                "help hiring managers make confident decisions for any role type. "
                "Provide compelling explanations for why each top candidate was selected."
            ),
            backstory=(
                "You are an expert at synthesizing complex talent data into clear, "
                "compelling narratives for any role type. You understand that hiring "
                "managers need more than just scores - they need stories that explain "
                "WHY each candidate is a good fit. You excel at identifying patterns "
                "across candidates, highlighting unique strengths, and providing "
                "actionable recommendations. You write with clarity and confidence, "
                "backing every claim with specific evidence from the candidate's "
                "background. Your reports combine quantitative rigor with qualitative "
                "insight, making hiring decisions accessible to both technical and "
                "non-technical stakeholders."
            ),
            llm=self.llm,
            verbose=True,
            allow_delegation=False,
            max_iter=3
        )
    
    def _format_candidate_context(
        self,
        candidates: List[CandidateScore],
        source: str,
        limit: int = 10
    ) -> str:
        """Format candidate scores into readable context."""
        if not candidates:
            return f"No {source} candidates available."
        
        context = f"\n**{source.upper()} CANDIDATES (Top {min(limit, len(candidates))}):**\n"
        
        for i, candidate in enumerate(candidates[:limit], 1):
            context += f"\n{i}. Candidate {candidate.candidate_id} (Score: {candidate.overall_score:.3f})\n"
            context += f"   Source: {candidate.source.value}\n"
            
            # Add dimension highlights
            top_dimensions = sorted(
                candidate.dimensions,
                key=lambda x: x.score,
                reverse=True
            )[:3]
            
            context += "   Top dimensions:\n"
            for dim in top_dimensions:
                context += f"     - {dim.dimension}: {dim.score:.3f} ({dim.explanation})\n"
        
        return context
    
    def _format_diagnostic_context(self, diagnostic: DiagnosticReport) -> str:
        """Format diagnostic report into readable context."""
        context = "\n**DIAGNOSTIC ANALYSIS:**\n"
        context += f"\nRole: {diagnostic.role_type}\n"
        context += f"Seniority: {diagnostic.seniority_level}\n"
        context += f"Confidence: {diagnostic.confidence:.2f}\n"
        
        # Role competency priorities
        context += "\nRole Competency Priorities:\n"
        context += f"  - Research/Innovation Focus: {diagnostic.ml_competencies.research_focus:.2f}\n"
        context += f"  - Production/Delivery Focus: {diagnostic.ml_competencies.production_focus:.2f}\n"
        context += f"  - Operations/Infrastructure Focus: {diagnostic.ml_competencies.mlops_focus:.2f}\n"
        context += f"  - Leadership Potential: {diagnostic.ml_competencies.leadership_potential:.2f}\n"
        
        # Attribute weights
        context += f"\nAttribute Weights ({len(diagnostic.attribute_weights)}):\n"
        for attr in diagnostic.attribute_weights:
            context += f"  - {attr.attribute} (weight: {attr.weight:.2f}): {attr.reason}\n"
        
        # Skills
        context += f"\nRequired Skills: {', '.join(diagnostic.required_skills)}\n"
        context += f"Preferred Skills: {', '.join(diagnostic.preferred_skills)}\n"
        
        # Key hypotheses
        context += f"\nKey Hypotheses ({len(diagnostic.key_hypotheses)}):\n"
        for hypothesis in diagnostic.key_hypotheses:
            context += f"  - {hypothesis}\n"
        
        return context
    
    def _create_synthesis_task(
        self,
        agent: Agent,
        synthesis_input: SynthesisInput
    ) -> Task:
        """Create the synthesis task with structured output format."""
        
        # Build comprehensive context
        diagnostic_context = self._format_diagnostic_context(synthesis_input.diagnostic_report)
        applicant_context = self._format_candidate_context(
            synthesis_input.applicant_scores,
            "Applicant",
            limit=10
        )
        market_context = self._format_candidate_context(
            synthesis_input.market_scores,
            "Market",
            limit=10
        )
        
        task_description = f"""
Synthesize the talent analysis into a comprehensive, actionable report for the hiring manager.

{diagnostic_context}
{applicant_context}
{market_context}

**YOUR TASK:**
1. Write an executive summary of the analysis findings (2-3 paragraphs)
2. Extract 5-7 key insights about the candidate pool and top performers
3. Identify 3-5 recurring patterns in top candidates (skills, career paths, companies, experience levels)
4. Provide actionable recommendations for the hiring process
5. Note any concerns or caveats about the analysis
6. Assess overall confidence in the analysis quality

**OUTPUT FORMAT:**
You MUST respond with a valid JSON object matching this EXACT schema:
{{
    "executive_summary": "string (2-3 paragraphs synthesizing key findings, candidate quality, and hiring recommendations)",
    "key_insights": [
        "insight 1 (specific, evidence-based observation about candidates)",
        "insight 2 (e.g., '80% of top candidates have 5-7 years experience')",
        "insight 3",
        "insight 4",
        "insight 5"
    ],
    "pattern_highlights": [
        {{
            "pattern_type": "career_path|skill_combo|company_cluster|experience_level",
            "description": "string (detailed description of the pattern)",
            "frequency": int (number of top candidates showing this pattern),
            "baseline_comparison": "string (how this compares to baseline employees)",
            "examples": ["candidate_id_1", "candidate_id_2"]
        }}
    ],
    "recommendations": [
        "recommendation 1 (specific, actionable advice for hiring manager)",
        "recommendation 2 (e.g., 'Prioritize candidates with PyTorch + production ML experience')",
        "recommendation 3"
    ],
    "concerns": [
        "concern 1 (optional - any caveats or limitations)",
        "concern 2 (e.g., 'Limited baseline data may affect accuracy')"
    ],
    "confidence_assessment": "string (overall confidence: High/Medium/Low with brief explanation)"
}}

**GUIDELINES:**
- **Executive Summary**: Synthesize findings into hiring manager-friendly narrative
  * Overall candidate quality across both pools
  * Key differentiators of top candidates
  * Confidence in recommendations
  * Suggested next steps
  
- **Key Insights**: Specific, data-driven observations
  * Cite actual percentages, skills, companies
  * Highlight surprising or important findings
  * Compare applicant vs market pools if relevant
  
- **Pattern Highlights**: Actionable patterns to look for
  * Pattern type must be one of: career_path, skill_combo, company_cluster, experience_level
  * Description should explain WHY this pattern matters
  * Frequency = count of top candidates showing this pattern
  * Baseline comparison = how this differs from baseline employees
  * Examples = list of 2-3 candidate IDs showing this pattern
  
- **Recommendations**: Specific actions for hiring manager
  * Prioritize by impact (most important first)
  * Make them actionable (e.g., "Interview candidates X and Y first")
  * Explain sourcing strategies if applicable
  
- **Concerns**: Be honest about limitations
  * Data quality issues
  * Small sample sizes
  * Baseline limitations
  * Market conditions
  
- **Confidence Assessment**: Overall quality assessment
  * State confidence level (High/Medium/Low)
  * Explain key factors affecting confidence
  * Be calibrated and honest

Write in clear, professional language. Be specific with evidence (skills, companies, years experience).
"""
        
        return Task(
            description=task_description,
            agent=agent,
            expected_output="A valid JSON object containing the structured synthesis report"
        )
    
    def _parse_synthesis_output(self, raw_output: str) -> SynthesisReport:
        """
        Parse the agent's raw output into a SynthesisReport.
        
        The agent should output valid JSON. We parse and validate it.
        """
        try:
            # Try to find JSON in the output
            json_start = raw_output.find('{')
            json_end = raw_output.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON object found in agent output")
            
            json_str = raw_output[json_start:json_end]
            data = json.loads(json_str)
            
            # Convert to Pydantic model
            synthesis_report = SynthesisReport(**data)
            
            logger.info(
                "synthesis_report_parsed",
                insight_count=len(synthesis_report.key_insights),
                pattern_count=len(synthesis_report.pattern_highlights),
                recommendation_count=len(synthesis_report.recommendations)
            )
            
            return synthesis_report
            
        except Exception as e:
            logger.error(
                "synthesis_parsing_failed",
                error=str(e),
                raw_output=raw_output[:500],
                exc_info=True
            )
            raise ValueError(f"Failed to parse synthesis output: {str(e)}")
    
    def synthesize(self, synthesis_input: SynthesisInput) -> SynthesisReport:
        """
        Run synthesis analysis.
        
        Args:
            synthesis_input: Diagnostic report and scored candidates
            
        Returns:
            SynthesisReport with comprehensive analysis
            
        Raises:
            ValueError: If output parsing fails
        """
        logger.info(
            "synthesis_analysis_start",
            customer_id=self.customer_id,
            user_id=self.user_id,
            applicant_count=len(synthesis_input.applicant_scores),
            market_count=len(synthesis_input.market_scores)
        )
        
        try:
            # Create agent and task
            agent = self._create_synthesis_agent()
            task = self._create_synthesis_task(agent, synthesis_input)
            
            # Create crew and execute
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=True
            )
            
            logger.debug("synthesis_crew_executing")
            with self.langfuse_service.span_scope(
                name="agentmesh.talent.synthesis_agent.synthesize",
                input_data={
                    "applicant_count": len(synthesis_input.applicant_scores),
                    "market_count": len(synthesis_input.market_scores),
                    "top_overall_count": synthesis_input.top_overall_count,
                    "diagnostic_confidence": synthesis_input.diagnostic_report.confidence,
                },
                metadata={
                    "component": "agentmesh",
                    "flow": "talent_orchestrator",
                    "service": "synthesis_agent",
                    "customer_id": self.customer_id,
                    "user_id": self.user_id,
                    "llm_provider": self.llm_provider,
                    "llm_model": self.llm_model,
                },
                trace_id=self.trace_id,
            ) as span_info:
                result = crew.kickoff()
                
                # Parse output
                synthesis_report = self._parse_synthesis_output(result.raw)
                
                observation = span_info.get("observation")
                if observation is not None:
                    try:
                        observation.update(
                            output={
                                "insight_count": len(synthesis_report.key_insights),
                                "pattern_count": len(synthesis_report.pattern_highlights),
                                "recommendation_count": len(synthesis_report.recommendations),
                                "concern_count": len(synthesis_report.concerns),
                            }
                        )
                    except Exception:
                        pass
            
            logger.info(
                "synthesis_analysis_complete",
                customer_id=self.customer_id,
                user_id=self.user_id,
                insight_count=len(synthesis_report.key_insights),
                recommendation_count=len(synthesis_report.recommendations)
            )
            
            return synthesis_report
            
        except Exception as e:
            logger.error(
                "synthesis_analysis_failed",
                customer_id=self.customer_id,
                user_id=self.user_id,
                error=str(e),
                exc_info=True
            )
            raise
