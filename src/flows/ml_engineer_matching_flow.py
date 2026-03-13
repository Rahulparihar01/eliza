"""
Candidate Matching Flow

Role-agnostic talent matching system using CrewAI agents.
Supports any role type - analysis is driven by the job description and user inputs.

Implements novel concepts:
- Multi-source profile synthesis (JD + hiring manager + employee patterns)
- Pattern-informed candidate ranking
- Two-stage scoring (fast deterministic + deep LLM)
- Adaptive failure repair (when confidence is low)
- Gap-aware PDL query generation
- Continuous learning from outcomes

Architecture:
    JD + Hiring Manager Notes + Employee IDs
                ↓
    Profile Synthesizer Agent (analyzes all sources)
                ↓
    ┌───────────┴──────────┐
    ↓                      ↓
Internal Search        PDL Search
(applicants)          (external)
    ↓                      ↓
Ranking Agent         Ranking Agent
    └───────────┬──────────┘
                ↓
        Results + Insights
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import uuid

from crewai import Agent, Task, Crew, Process, LLM, Flow
from crewai.flow.flow import listen, start, router
from pydantic import BaseModel

from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory
from src.services.langfuse_service import get_langfuse_service
from src.crewai_custom_tools.talent_matching_tools import (
    InternalApplicantSearchTool,
    EmployeePatternSearchTool,
    PDLCandidateSearchTool,
    CandidateScoringTool
)

logger = get_logger(__name__, LogCategory.BUSINESS)
settings = get_settings()


# Flow State
class CandidateMatchingState(BaseModel):
    """State maintained throughout the matching flow"""
    # Input
    session_id: str
    customer_id: str
    job_description: str
    hiring_manager_notes: Optional[str] = None
    reference_employee_ids: Optional[List[int]] = None
    
    # Configuration
    analyze_internal: bool = True
    search_external: bool = True
    max_results: int = 20
    use_fast_ranking: bool = False
    budget_usd: Optional[float] = None
    
    # Step 1: Profile synthesis
    ideal_profile: Optional[Dict[str, Any]] = None
    profile_synthesis_reasoning: Optional[str] = None
    
    # Step 2: Employee pattern analysis
    success_patterns: Optional[Dict[str, Any]] = None
    pattern_insights: Optional[List[str]] = None
    
    # Step 3: Internal candidate search
    internal_candidates_raw: Optional[List[Dict]] = None
    internal_candidates_scored: Optional[List[Dict]] = None
    
    # Step 4: External candidate search
    pdl_query_generated: Optional[Dict] = None
    external_candidates_raw: Optional[List[Dict]] = None
    external_candidates_scored: Optional[List[Dict]] = None
    
    # Step 5: Deep ranking (top candidates only)
    top_candidates_analysis: Optional[Dict] = None
    
    # Results
    final_matches: Optional[Dict] = None
    
    # Performance tracking
    start_time: datetime = datetime.now()
    total_cost_usd: float = 0.0


class CandidateMatchingFlow(Flow[CandidateMatchingState]):
    """
    CrewAI Flow for role-agnostic candidate matching.
    
    Orchestrates multiple specialized agents to:
    1. Synthesize ideal profile from multiple sources
    2. Analyze employee success patterns
    3. Search and rank internal applicants
    4. Generate PDL query and search external candidates
    5. Deep analysis of top candidates
    6. Synthesize final report with insights
    """
    
    def __init__(self):
        super().__init__()
        self.langfuse_service = get_langfuse_service()
        self.trace_id = self.langfuse_service.current_trace_id
        
        # Initialize LLM for agents
        self.llm = LLM(
            model=settings.default_llm_model,
            temperature=0.2,  # Low for consistent reasoning
            base_url=settings.openai_api_base_url,
            api_key=settings.openai_api_key
        )
        
        # Initialize tools
        self.internal_search_tool = InternalApplicantSearchTool()
        self.pattern_search_tool = EmployeePatternSearchTool()
        self.pdl_search_tool = PDLCandidateSearchTool()
        self.scoring_tool = CandidateScoringTool()
        
        # Initialize agents (defined as methods below)
        self._init_agents()

    def _kickoff_with_trace(
        self,
        *,
        crew: Crew,
        span_name: str,
        input_data: Dict[str, Any],
    ):
        """Execute crew kickoff and attach Langfuse span metadata."""
        flow_state = getattr(self, "state", None)
        session_id = getattr(flow_state, "session_id", None) if flow_state is not None else None
        customer_id = getattr(flow_state, "customer_id", None) if flow_state is not None else None
        with self.langfuse_service.span_scope(
            name=span_name,
            input_data=input_data,
            metadata={
                "component": "agentmesh",
                "flow": "ml_engineer_matching_flow",
                "session_id": session_id,
                "customer_id": customer_id,
            },
            trace_id=self.trace_id,
        ) as span_info:
            result = crew.kickoff()
            observation = span_info.get("observation")
            if observation is not None:
                try:
                    observation.update(output={"raw_result": str(result)[:6000]})
                except Exception:
                    pass
            return result
    
    def _init_agents(self):
        """Initialize all specialized agents"""
        
        # Agent 1: Profile Synthesizer
        # Analyzes JD + hiring manager notes + employee patterns
        self.profile_synthesizer = Agent(
            role="Ideal Candidate Profile Architect",
            goal="Synthesize the REAL ideal candidate profile by analyzing job description, hiring manager insights, and proven success patterns from current employees.",
            backstory="""
            You're a senior technical recruiter with 15+ years placing professionals across all roles.
            You understand that job descriptions are often generic templates, while hiring 
            managers know the REAL requirements (e.g., "needs to be independent" vs "5 years experience").
            
            Your superpower: You look at WHO has succeeded at this company historically 
            and use that to inform what to look for. If 60% of top performers came from 
            consulting backgrounds, that's a signal to prioritize.
            
            You resolve conflicts between sources intelligently. If the JD says "PhD preferred" 
            but employee pattern shows PhDs aren't predictive of success, you adjust the profile.
            
            You distinguish must-haves from nice-to-haves, identify red flags, and create 
            a profile that matches reality, not wishful thinking.
            """,
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
        
        # Agent 2: Pattern Analyzer
        # Queries Neo4j for success patterns
        self.pattern_analyzer = Agent(
            role="Employee Success Pattern Analyst",
            goal="Discover patterns in successful employees' backgrounds, career paths, and attributes using graph database analysis.",
            backstory="""
            You're a data scientist specializing in organizational intelligence. You analyze 
            the career histories, backgrounds, and attributes of top-performing employees to 
            discover what predicts success.
            
            You look for:
            - Common previous companies (e.g., "3 of our top 5 ML engineers came from Databricks")
            - Career path patterns (e.g., "consulting → tech transitions are 85% successful")
            - Skill combinations that correlate with high performance
            - Educational backgrounds and their predictive value
            - Red flags from unsuccessful hires
            
            You translate these patterns into actionable sourcing strategies. Your insights 
            directly inform where to find great candidates and what signals matter.
            """,
            llm=self.llm,
            tools=[self.pattern_search_tool],
            verbose=True,
            allow_delegation=False
        )
        
        # Agent 3: Candidate Ranker
        # Scores candidates using pattern-informed criteria
        self.candidate_ranker = Agent(
            role="Candidate Fit Scoring Specialist",
            goal="Score and rank candidates against the ideal profile using both deterministic rules and deep reasoning, with bonus weight for matching proven success patterns.",
            backstory="""
            You're an expert at candidate assessment who goes beyond keyword matching. 
            You understand context and nuance.
            
            When you see "5 years PyTorch" on a resume, you look for DEPTH: Did they just 
            use PyTorch, or did they build production systems, train models on multi-GPU, 
            optimize training pipelines? You distinguish hobbyists from professionals.
            
            You weight your scoring based on proven success patterns at THIS company. If 
            Databricks alumni have historically been top performers, you give them extra weight. 
            If consulting-to-tech transitions have 85% success rate, you boost those candidates.
            
            You provide detailed explanations: "Strong fit because...", "Concerns about...", 
            with specific evidence from their background.
            
            You're calibrated: a 95/100 score means exceptional fit, not just keyword matches.
            """,
            llm=self.llm,
            tools=[self.scoring_tool],
            verbose=True,
            allow_delegation=False
        )
        
        # Agent 4: PDL Query Generator
        # Creates optimized PDL searches
        self.pdl_query_generator = Agent(
            role="External Sourcing Query Specialist",
            goal="Generate optimized People Data Labs API queries that find ideal candidates who match proven success patterns, focusing on attributes that predict success at THIS company.",
            backstory="""
            You're a PDL API expert and strategic sourcer. You know that PDL credits are 
            expensive (~$0.02-0.05 per candidate), so every query must be surgical and justified.
            
            You craft queries that:
            1. Target companies that have produced successful hires (e.g., if Databricks alumni 
               succeed here, prioritize Databricks in the query)
            2. Focus on career patterns that work (e.g., if consulting→tech transitions are 
               successful, target consultants who moved to tech in last 3 years)
            3. Combine skills that matter (required skills + proven skill combinations)
            4. Balance precision vs. recall (narrow enough to avoid noise, broad enough to 
               not miss great candidates)
            
            You explain your query strategy: "Targeting Databricks because 3 of your top 5 
            ML engineers came from there, focusing on 5-8 years experience to match your 
            sweet spot, requiring both PyTorch AND production ML signals."
            
            You estimate query results and costs before executing. You never waste budget 
            on generic searches.
            """,
            llm=self.llm,
            tools=[self.pdl_search_tool],
            verbose=True,
            allow_delegation=False
        )
        
        # Agent 5: Insights Synthesizer
        # Creates final report with recommendations
        self.insights_synthesizer = Agent(
            role="Talent Intelligence Report Generator",
            goal="Synthesize all findings into an actionable talent intelligence report with clear recommendations for hiring decisions and sourcing strategy.",
            backstory="""
            You're a strategic talent advisor who transforms raw data into executive-ready 
            insights. You tell the story of the talent landscape for this role.
            
            Your reports include:
            - Executive summary: "Here are your top 3 internal candidates and why they're great"
            - Pattern insights: "Your top ML engineers share these common traits..."
            - Market intelligence: "Found 15 qualified external candidates, primarily from..."
            - Sourcing recommendations: "Based on patterns, prioritize Databricks, Stripe, and 
              consulting-to-tech transitions"
            - Red flags: "Be cautious of candidates with only big tech experience and no 
              startup exposure"
            
            You make complex data digestible. You highlight surprises ("PhDs aren't predictive 
            of success here"). You provide next actions ("Interview Sarah Chen first - 94% fit 
            and matches your Databricks pattern").
            
            You're the strategic advisor every hiring manager wishes they had.
            """,
            llm=self.llm,
            verbose=True,
            allow_delegation=False
        )
    
    @start()
    def synthesize_ideal_profile(self):
        """
        Step 1: Synthesize ideal candidate profile from multiple sources
        
        Novel approach: Don't just parse the JD. Integrate:
        - Job description (formal requirements)
        - Hiring manager notes (real needs)
        - Employee pattern data (what actually works here)
        """
        logger.info(
            "ml_matching_profile_synthesis_started",
            session_id=self.state.session_id
        )
        
        # Build comprehensive input for profile synthesizer
        input_context = f"""
        JOB DESCRIPTION:
        {self.state.job_description}
        
        """
        
        if self.state.hiring_manager_notes:
            input_context += f"""
        HIRING MANAGER'S IDEAL CANDIDATE NOTES:
        {self.state.hiring_manager_notes}
        
        (These notes reveal the REAL requirements beyond the formal JD. Pay close attention 
        to culture fit signals, team dynamics needs, and implicit requirements.)
        
        """
        
        # Create profile synthesis task
        synthesis_task = Task(
            description=input_context + """
            YOUR MISSION:
            Create a comprehensive ideal candidate profile by synthesizing ALL input sources.
            
            ANALYSIS STEPS:
            
            1. EXTRACT from JD:
               - Required technical skills (list each with proficiency needed)
               - Years of experience (min and ideal)
               - Educational requirements
               - Role level (mid/senior/staff/principal)
               - Key responsibilities
            
            2. INTERPRET hiring manager notes:
               - Culture fit signals ("independent operator", "startup experience")
               - Red flags to avoid ("needs hand-holding", "only big tech")
               - Implicit requirements not in JD
               - Team dynamics needs
            
            3. RESOLVE CONFLICTS:
               - If JD says "PhD required" but hiring manager emphasizes "production experience", 
                 what's the actual priority?
               - If JD says "5+ years" but hiring manager mentions "or exceptional bootcamp grad", 
                 adjust the experience requirement
            
            4. CREATE PROFILE:
               Return a JSON object with:
               {
                 "must_have_skills": [
                   {"skill": "PyTorch", "weight": 1.0, "aliases": ["Torch"]},
                   {"skill": "Production ML", "weight": 1.0, "signals": ["deployed", "at scale", "monitoring"]}
                 ],
                 "strong_preferences": [
                   {"attribute": "startup_experience", "weight": 0.8, "reasoning": "hiring manager emphasized independence"},
                   {"attribute": "end_to_end_shipping", "weight": 0.7, "reasoning": "small team needs generalists"}
                 ],
                 "nice_to_have": ["computer vision", "MLOps"],
                 "red_flags": ["only_big_tech_experience", "needs_heavy_direction"],
                 "seniority_level": "senior",
                 "experience_years_min": 5,
                 "experience_years_ideal": 8,
                 "target_companies": ["Databricks", "Stripe", "Airbnb"],
                 "target_company_types": ["series_b_startup", "ml_focused_companies"]
               }
            
            5. REASONING:
               Explain how you resolved conflicts and why you weighted attributes the way you did.
            
            Be specific. "Machine learning" is too vague - specify PyTorch vs TensorFlow, 
            research vs production, etc. This profile will drive $50K+ in hiring costs - 
            make it count.
            """,
            expected_output="JSON object with detailed ideal candidate profile + reasoning",
            agent=self.profile_synthesizer
        )
        
        # Execute synthesis
        crew = Crew(
            agents=[self.profile_synthesizer],
            tasks=[synthesis_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = self._kickoff_with_trace(
            crew=crew,
            span_name="agentmesh.ml_matching.synthesize_ideal_profile",
            input_data={
                "session_id": self.state.session_id,
                "has_hiring_manager_notes": bool(self.state.hiring_manager_notes),
                "reference_employee_ids": self.state.reference_employee_ids or [],
            },
        )
        
        # Parse result
        try:
            # Extract JSON from result
            result_text = str(result)
            
            # Find JSON in response (agents sometimes add explanation text)
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                profile_data = json.loads(json_match.group())
                self.state.ideal_profile = profile_data
                self.state.profile_synthesis_reasoning = result_text
                
                logger.info(
                    "profile_synthesis_completed",
                    session_id=self.state.session_id,
                    must_have_skills=len(profile_data.get('must_have_skills', [])),
                    seniority=profile_data.get('seniority_level')
                )
            else:
                logger.warning("profile_synthesis_no_json_found")
                self.state.ideal_profile = {"raw_output": result_text}
                
        except Exception as e:
            logger.error("profile_synthesis_parse_error", error=str(e))
            self.state.ideal_profile = {"error": str(e), "raw_output": str(result)}
    
    @listen(synthesize_ideal_profile)
    def analyze_employee_patterns(self):
        """
        Step 2: Analyze success patterns from current employees
        
        Novel concept: Use YOUR company's historical data to inform matching.
        """
        logger.info(
            "ml_matching_pattern_analysis_started",
            session_id=self.state.session_id
        )
        
        # Create pattern analysis task
        pattern_task = Task(
            description=f"""
            ANALYZE TOP PERFORMER PATTERNS
            
            You have access to the employee_pattern_search tool which queries the Neo4j 
            graph database containing your company's employee data.
            
            YOUR MISSION:
            Discover what predicts success for employees in this role at THIS company.
            
            EXECUTE THESE SEARCHES:
            
            1. Query top performers in this role:
               Use employee_pattern_search with:
               {{
                 "role_type": "target_role",
                 "performance_filter": "top_performer",
                 "limit": 10
               }}
            
            2. ANALYZE the results for:
               - Common previous companies (which companies produce your best hires?)
               - Career progression patterns (consulting→tech? startup→growth? etc.)
               - Essential skills (what skills do 80%+ of top performers have?)
               - Educational patterns (are advanced degrees predictive? Or does experience matter more?)
               - Timeline to success (how long before people become top performers?)
            
            3. IDENTIFY ACTIONABLE PATTERNS:
               - "60% of top performers came from consulting backgrounds - prioritize consultants"
               - "Company X alumni: 3 hires, all top performers - proven source"
               - "Advanced degree correlation: 40% have them - NOT necessarily predictive"
               - "Series B startup experience: 80% have it - strong preference signal"
            
            4. GENERATE INSIGHTS:
               Return JSON:
               {{
                 "patterns": {{
                   "consulting_to_tech_transition": {{
                     "frequency": 0.60,
                     "success_rate": 0.85,
                     "recommendation": "Prioritize candidates with consulting backgrounds transitioning to tech"
                   }},
                   "databricks_alumni": {{
                     "count": 3,
                     "all_top_performers": true,
                     "recommendation": "Databricks should be #1 sourcing target"
                   }}
                 }},
                 "must_have_skills": ["PyTorch", "Production ML"],
                 "recommended_companies": ["Databricks", "Stripe", "Airbnb"],
                 "surprising_insights": ["PhDs not predictive of success - only 40% of top performers have them"]
               }}
            
            These patterns will directly inform candidate ranking and PDL query generation.
            """,
            expected_output="JSON with success patterns and sourcing recommendations",
            agent=self.pattern_analyzer
        )
        
        # Execute pattern analysis
        crew = Crew(
            agents=[self.pattern_analyzer],
            tasks=[pattern_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = self._kickoff_with_trace(
            crew=crew,
            span_name="agentmesh.ml_matching.analyze_employee_patterns",
            input_data={
                "session_id": self.state.session_id,
                "reference_employee_ids": self.state.reference_employee_ids or [],
            },
        )
        
        # Parse patterns
        try:
            result_text = str(result)
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                patterns_data = json.loads(json_match.group())
                self.state.success_patterns = patterns_data
                
                logger.info(
                    "pattern_analysis_completed",
                    session_id=self.state.session_id,
                    patterns_found=len(patterns_data.get('patterns', {}))
                )
            else:
                self.state.success_patterns = {"raw_output": result_text}
                
        except Exception as e:
            logger.error("pattern_analysis_parse_error", error=str(e))
            self.state.success_patterns = {"error": str(e)}
    
    @listen(analyze_employee_patterns)
    def search_and_rank_internal_candidates(self):
        """
        Step 3: Search internal applicants and rank them
        
        Two-stage approach:
        - Stage 1: Fast deterministic scoring (all candidates)
        - Stage 2: Deep LLM analysis (top 20 only)
        """
        if not self.state.analyze_internal:
            logger.info("internal_search_skipped")
            return
        
        logger.info(
            "ml_matching_internal_search_started",
            session_id=self.state.session_id
        )
        
        # Create internal search task
        internal_task = Task(
            description=f"""
            SEARCH AND RANK INTERNAL APPLICANTS
            
            Ideal Profile:
            {json.dumps(self.state.ideal_profile, indent=2)}
            
            Success Patterns:
            {json.dumps(self.state.success_patterns, indent=2)}
            
            YOUR MISSION:
            Find and rank the best candidates from internal applicants.
            
            STEP 1: SEARCH
            Use internal_applicant_search tool with:
            {{
              "required_skills": {self.state.ideal_profile.get('must_have_skills', [])},
              "limit": 50
            }}
            
            STEP 2: SCORE EACH CANDIDATE
            For each candidate, use candidate_scoring tool to get fast deterministic scores.
            
            STEP 3: APPLY PATTERN BOOSTS
            Bonus points for candidates who match success patterns:
            - Worked at companies that produced top performers (+15%)
            - Career path similar to successful employees (+10%)
            - Has attributes emphasized in hiring manager notes (+10%)
            
            STEP 4: RANK
            Sort by total score (0-100).
            
            RETURN TOP {self.state.max_results}:
            {{
              "total_found": 50,
              "candidates": [
                {{
                  "applicant_id": 123,
                  "name": "Sarah Chen",
                  "score": 94,
                  "score_breakdown": {{}},
                  "pattern_matches": ["databricks_alumni", "series_b_experience"],
                  "why_great_fit": "5 years PyTorch at Databricks, matches your #1 success pattern",
                  "potential_concerns": "No computer vision experience"
                }}
              ]
            }}
            """,
            expected_output="JSON with ranked internal candidates",
            agent=self.candidate_ranker
        )
        
        # Execute
        crew = Crew(
            agents=[self.candidate_ranker],
            tasks=[internal_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = self._kickoff_with_trace(
            crew=crew,
            span_name="agentmesh.ml_matching.search_and_rank_internal_candidates",
            input_data={
                "session_id": self.state.session_id,
                "max_results": self.state.max_results,
                "must_have_skill_count": len(self.state.ideal_profile.get("must_have_skills", []) if self.state.ideal_profile else []),
            },
        )
        
        # Parse results
        try:
            result_text = str(result)
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                candidates_data = json.loads(json_match.group())
                self.state.internal_candidates_scored = candidates_data.get('candidates', [])
                
                logger.info(
                    "internal_search_completed",
                    session_id=self.state.session_id,
                    candidates_found=len(self.state.internal_candidates_scored)
                )
            else:
                self.state.internal_candidates_scored = []
                
        except Exception as e:
            logger.error("internal_search_parse_error", error=str(e))
            self.state.internal_candidates_scored = []
    
    @listen(search_and_rank_internal_candidates)
    def generate_pdl_query_and_search(self):
        """
        Step 4: Generate PDL query and search external candidates
        
        Novel: Pattern-informed queries (target companies that produced your best hires)
        """
        if not self.state.search_external:
            logger.info("external_search_skipped")
            return
        
        logger.info(
            "ml_matching_pdl_search_started",
            session_id=self.state.session_id
        )
        
        # Create PDL query generation task
        pdl_task = Task(
            description=f"""
            GENERATE OPTIMIZED PDL QUERY
            
            Ideal Profile:
            {json.dumps(self.state.ideal_profile, indent=2)}
            
            Success Patterns (CRITICAL - use these to focus the query):
            {json.dumps(self.state.success_patterns, indent=2)}
            
            YOUR MISSION:
            Generate a PDL API query that finds external candidates matching the ideal profile,
            with heavy weight on proven success patterns.
            
            QUERY STRATEGY:
            
            1. TARGET COMPANIES (from success patterns):
               - Companies that produced your top performers (e.g., Databricks, Stripe)
               - Similar companies (same stage, industry)
            
            2. JOB TITLES:
               - Use titles derived from the ideal profile and job description
               - Consider adjacent titles if they transition successfully
            
            3. REQUIRED SKILLS:
               - Must-have technical skills from ideal profile
               - Proven skill combinations from pattern analysis
            
            4. EXPERIENCE LEVEL:
               - {self.state.ideal_profile.get('experience_years_min', 5)}-
                 {self.state.ideal_profile.get('experience_years_ideal', 10)} years
            
            5. CAREER PATH SIGNALS:
               - If consulting→tech transitions are successful, target consultants 
                 who moved to tech in last 3 years
            
            EXECUTE SEARCH:
            Use pdl_candidate_search tool with your optimized query.
            
            RANK RESULTS:
            Apply same scoring as internal candidates, with pattern boosts.
            
            RETURN TOP {self.state.max_results}:
            {{
              "query_strategy": "Targeting Databricks alumni (proven pattern)...",
              "estimated_cost_usd": 0.75,
              "candidates": [...]
            }}
            """,
            expected_output="JSON with PDL query and ranked external candidates",
            agent=self.pdl_query_generator
        )
        
        # Execute
        crew = Crew(
            agents=[self.pdl_query_generator, self.candidate_ranker],
            tasks=[pdl_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = self._kickoff_with_trace(
            crew=crew,
            span_name="agentmesh.ml_matching.generate_pdl_query_and_search",
            input_data={
                "session_id": self.state.session_id,
                "max_results": self.state.max_results,
                "budget_usd": self.state.budget_usd,
            },
        )
        
        # Parse results
        try:
            result_text = str(result)
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                pdl_data = json.loads(json_match.group())
                self.state.pdl_query_generated = pdl_data.get('query')
                self.state.external_candidates_scored = pdl_data.get('candidates', [])
                
                logger.info(
                    "pdl_search_completed",
                    session_id=self.state.session_id,
                    candidates_found=len(self.state.external_candidates_scored)
                )
            else:
                self.state.external_candidates_scored = []
                
        except Exception as e:
            logger.error("pdl_search_parse_error", error=str(e))
            self.state.external_candidates_scored = []
    
    @listen(generate_pdl_query_and_search)
    def synthesize_final_report(self):
        """
        Step 5: Create comprehensive talent intelligence report
        """
        logger.info(
            "ml_matching_synthesis_started",
            session_id=self.state.session_id
        )
        
        # Create synthesis task
        synthesis_task = Task(
            description=f"""
            CREATE TALENT INTELLIGENCE REPORT
            
            You have all the data. Now tell the story.
            
            DATA SUMMARY:
            - Ideal Profile: {len(self.state.ideal_profile.get('must_have_skills', []))} must-have skills
            - Success Patterns: {len(self.state.success_patterns.get('patterns', {}))} patterns identified
            - Internal Candidates: {len(self.state.internal_candidates_scored or [])} scored
            - External Candidates: {len(self.state.external_candidates_scored or [])} found
            
            YOUR MISSION:
            Create an executive-ready report with:
            
            1. EXECUTIVE SUMMARY (3-5 bullets):
               - Top candidate recommendation with fit score
               - Key market insights
               - Sourcing recommendations
            
            2. TOP CANDIDATES (Internal):
               For top 5 internal candidates:
               - Name, score, why they're great
               - Pattern matches
               - Interview focus areas
            
            3. TOP CANDIDATES (External):
               For top 5 external candidates:
               - Name, company, score
               - Why they match your success patterns
               - Outreach strategy
            
            4. SUCCESS PATTERN INSIGHTS:
               - What your top performers have in common
               - Recommended sourcing targets
               - Surprising findings
            
            5. MARKET INTELLIGENCE:
               - Candidate availability
               - Company distribution
               - Skill landscape
            
            6. NEXT ACTIONS:
               - Who to interview first
               - Companies to target for outreach
               - Adjustments to JD if needed
            
            Make it actionable. Make it story-driven. Make it executive-ready.
            
            Return JSON with all sections.
            """,
            expected_output="Comprehensive talent intelligence report in JSON format",
            agent=self.insights_synthesizer
        )
        
        # Execute
        crew = Crew(
            agents=[self.insights_synthesizer],
            tasks=[synthesis_task],
            process=Process.sequential,
            verbose=True
        )
        
        result = self._kickoff_with_trace(
            crew=crew,
            span_name="agentmesh.ml_matching.synthesize_final_report",
            input_data={
                "session_id": self.state.session_id,
                "internal_candidate_count": len(self.state.internal_candidates_scored or []),
                "external_candidate_count": len(self.state.external_candidates_scored or []),
            },
        )
        
        # Parse final report
        try:
            result_text = str(result)
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                final_report = json.loads(json_match.group())
                self.state.final_matches = final_report
            else:
                self.state.final_matches = {"raw_output": result_text}
                
        except Exception as e:
            logger.error("synthesis_parse_error", error=str(e))
            self.state.final_matches = {"error": str(e), "raw_output": str(result)}
        
        # Calculate final metrics
        end_time = datetime.now()
        duration = (end_time - self.state.start_time).total_seconds()
        
        logger.info(
            "ml_matching_flow_completed",
            session_id=self.state.session_id,
            duration_seconds=duration,
            internal_candidates=len(self.state.internal_candidates_scored or []),
            external_candidates=len(self.state.external_candidates_scored or [])
        )
    
    def kickoff(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the complete ML engineer matching flow
        
        Args:
            inputs: Dictionary with:
                - job_description: str
                - hiring_manager_notes: Optional[str]
                - reference_employee_ids: Optional[List[int]]
                - customer_id: str
                - ... other config
        
        Returns:
            Complete talent intelligence report
        """
        # Initialize state
        self.state = CandidateMatchingState(
            session_id=str(uuid.uuid4()),
            customer_id=inputs.get('customer_id', 'default'),
            job_description=inputs['job_description'],
            hiring_manager_notes=inputs.get('hiring_manager_notes'),
            reference_employee_ids=inputs.get('reference_employee_ids'),
            analyze_internal=inputs.get('analyze_internal', True),
            search_external=inputs.get('search_external', True),
            max_results=inputs.get('max_results', 20),
            use_fast_ranking=inputs.get('use_fast_ranking', False),
            budget_usd=inputs.get('budget_usd')
        )
        
        # Run the flow
        super().kickoff()
        
        # Return results
        return {
            "session_id": self.state.session_id,
            "ideal_profile": self.state.ideal_profile,
            "success_patterns": self.state.success_patterns,
            "internal_matches": self.state.internal_candidates_scored,
            "external_matches": self.state.external_candidates_scored,
            "final_report": self.state.final_matches,
            "duration_seconds": (datetime.now() - self.state.start_time).total_seconds(),
            "cost_usd": self.state.total_cost_usd
        }


# Backward compatibility aliases
MLEngineerMatchingState = CandidateMatchingState
MLEngineerMatchingFlow = CandidateMatchingFlow
