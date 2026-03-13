"""
Talent Intelligence Flow

A CrewAI flow that analyzes job descriptions and finds ideal candidate personas 
using ingested people data from Elasticsearch and Neo4j.

DUAL PIPELINE ARCHITECTURE:
1. Applicants Pipeline - Score applicants from HR platform (Greenhouse) against baseline
2. Market Pipeline - Search PDL data for non-applicant candidates
3. Combined Ranking - Merge and rank top 3 overall

This flow consists of multiple specialized agents:
1. Job Analyst - Extracts requirements from job descriptions
2. Talent Scout - Searches for matching candidates using search tools
3. Insights Synthesizer - Generates actionable intelligence and recommendations
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from crewai import Agent, Task, Crew
from crewai.flow.flow import Flow, listen, start
from pydantic import BaseModel
import json
import re
import structlog

from src.crewai_custom_tools.person_search_tools import create_person_search_tools
from src.core.config import get_settings
from src.models import database
from src.models.connector import Applicant, BaselineEmployeeProfile, ApplicantScore
from src.services.talent_scoring import TalentScoringEngine, BaselineProfileBuilder
from src.services.resume_processing import DoclingParser
from src.services.langfuse_service import get_langfuse_service

logger = structlog.get_logger(__name__)
settings = get_settings()


# State models
class TalentAnalysisState(BaseModel):
    """State passed between flow steps"""
    job_description: Optional[str] = None
    ideal_candidate_description: Optional[str] = None  # NEW: Natural language ideal candidate description
    manual_persona: Optional[Dict[str, Any]] = None
    job_posting_id: Optional[int] = None  # NEW: HR platform job posting ID for applicant analysis
    ideal_persona: Optional[Dict[str, Any]] = None
    baseline_profile_id: Optional[int] = None  # NEW: Baseline employee profile for scoring
    applicant_results: Optional[List[Dict[str, Any]]] = None  # NEW: Scored applicants
    market_results: Optional[List[Dict[str, Any]]] = None  # NEW: Market candidates from PDL search
    top_overall: Optional[List[Dict[str, Any]]] = None  # NEW: Top 3 overall
    insights_report: Optional[Dict[str, Any]] = None
    customer_id: str
    analysis_id: str
    # Token usage tracking
    token_usage: Dict[str, Any] = {
        "total_tokens": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "successful_requests": 0,
        "by_step": {}
    }


class TalentIntelligenceFlow(Flow[TalentAnalysisState]):
    """
    Main Talent Intelligence Flow
    
    This flow analyzes job descriptions or manual persona definitions to find
    ideal candidates using AI agents with access to comprehensive people search tools.
    
    DUAL PIPELINE:
    - Pipeline 1: Score applicants from HR platform against baseline employees
    - Pipeline 2: Search market candidates from PDL data
    - Merge: Combine and rank top 3 overall
    """
    
    def __init__(self, customer_id: str, analysis_id: str, job_posting_id: Optional[int] = None):
        super().__init__()
        self.customer_id = customer_id
        self.analysis_id = analysis_id
        self.job_posting_id = job_posting_id
        self.langfuse_service = get_langfuse_service()
        self.trace_id = self.langfuse_service.current_trace_id
        
        # Create search tools for this customer
        self.search_tools = create_person_search_tools(customer_id)
        
        # Initialize database session
        if database.SessionLocal is None:
            database.init_database()
        self.db = database.SessionLocal()
        
        # Initialize scoring engine and parser
        self.scoring_engine = TalentScoringEngine(self.db)
        self.docling_parser = DoclingParser()
        
        # Initialize agents
        self.job_analyst = self._create_job_analyst()
        self.talent_scout = self._create_talent_scout()
        self.insights_synthesizer = self._create_insights_synthesizer()
        
        logger.info("talent_flow_model_config",
                    analysis_id=self.analysis_id,
                    crewai_llm_model=settings.crewai_llm_model)
    
    def _track_token_usage(self, step_name: str, crew_output) -> None:
        """Extract and accumulate token usage from a CrewAI crew output."""
        try:
            usage = getattr(crew_output, 'token_usage', None)
            if usage is None:
                logger.warning("no_token_usage_available", step=step_name)
                return
            
            # CrewAI token_usage can be a dict or UsageMetrics object
            if hasattr(usage, 'total_tokens'):
                step_tokens = {
                    "total_tokens": usage.total_tokens or 0,
                    "prompt_tokens": usage.prompt_tokens or 0,
                    "completion_tokens": usage.completion_tokens or 0,
                    "successful_requests": usage.successful_requests or 0,
                }
            elif isinstance(usage, dict):
                step_tokens = {
                    "total_tokens": usage.get("total_tokens", 0),
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "successful_requests": usage.get("successful_requests", 0),
                }
            else:
                logger.warning("unexpected_token_usage_type", 
                             step=step_name, usage_type=type(usage).__name__)
                return
            
            # Accumulate totals
            self.state.token_usage["total_tokens"] += step_tokens["total_tokens"]
            self.state.token_usage["prompt_tokens"] += step_tokens["prompt_tokens"]
            self.state.token_usage["completion_tokens"] += step_tokens["completion_tokens"]
            self.state.token_usage["successful_requests"] += step_tokens["successful_requests"]
            self.state.token_usage["by_step"][step_name] = step_tokens
            
            logger.info("token_usage_tracked",
                       analysis_id=self.analysis_id,
                       step=step_name,
                       step_tokens=step_tokens,
                       running_total=self.state.token_usage["total_tokens"],
                       model=settings.crewai_llm_model)
        except Exception as e:
            logger.warning("token_tracking_error", step=step_name, error=str(e))

    def _kickoff_with_trace(
        self,
        *,
        crew: Crew,
        span_name: str,
        input_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Execute Crew kickoff while emitting a Langfuse span."""
        span_metadata = {
            "component": "agentmesh",
            "flow": "talent_intelligence_flow",
            "analysis_id": self.analysis_id,
            "customer_id": self.customer_id,
            "job_posting_id": self.job_posting_id,
            "model": settings.crewai_llm_model,
        }
        if metadata:
            span_metadata.update(metadata)

        with self.langfuse_service.span_scope(
            name=span_name,
            input_data=input_data,
            metadata=span_metadata,
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
    
    # ── Location filtering helpers ──────────────────────────────────────
    
    # Bidirectional map: any form → set of canonical names it could mean.
    # Canonical names are full lowercase English country names.
    # ISO 2-letter, 3-letter codes, and common alternate names are all mapped.
    COUNTRY_ALIASES: Dict[str, str] = {
        # Latin America
        "ar": "argentina", "arg": "argentina",
        "br": "brazil", "bra": "brazil", "brasil": "brazil",
        "mx": "mexico", "mex": "mexico", "méxico": "mexico",
        "co": "colombia", "col": "colombia",
        "cl": "chile", "chl": "chile",
        "pe": "peru", "per": "peru", "perú": "peru",
        "uy": "uruguay", "ury": "uruguay",
        "ve": "venezuela", "ven": "venezuela",
        "ec": "ecuador", "ecu": "ecuador",
        "py": "paraguay", "pry": "paraguay",
        "bo": "bolivia", "bol": "bolivia",
        "cr": "costa rica", "cri": "costa rica",
        # North America / Caribbean
        "us": "united states", "usa": "united states",
        "united states of america": "united states",
        "ca": "canada", "can": "canada",
        # Europe
        "uk": "united kingdom", "gb": "united kingdom", "gbr": "united kingdom",
        "great britain": "united kingdom", "england": "united kingdom",
        "de": "germany", "deu": "germany", "deutschland": "germany",
        "fr": "france", "fra": "france",
        "es": "spain", "esp": "spain", "españa": "spain",
        "it": "italy", "ita": "italy", "italia": "italy",
        "pt": "portugal", "prt": "portugal",
        "nl": "netherlands", "nld": "netherlands", "holland": "netherlands",
        "ie": "ireland", "irl": "ireland",
        "pl": "poland", "pol": "poland",
        "se": "sweden", "swe": "sweden",
        "ch": "switzerland", "che": "switzerland",
        "at": "austria", "aut": "austria",
        "ro": "romania", "rou": "romania",
        "ua": "ukraine", "ukr": "ukraine",
        "cz": "czech republic", "cze": "czech republic", "czechia": "czech republic",
        # Asia-Pacific
        "in": "india", "ind": "india",
        "cn": "china", "chn": "china", "prc": "china",
        "jp": "japan", "jpn": "japan",
        "kr": "south korea", "kor": "south korea",
        "republic of korea": "south korea", "korea": "south korea",
        "sg": "singapore", "sgp": "singapore",
        "au": "australia", "aus": "australia",
        "nz": "new zealand", "nzl": "new zealand",
        "ph": "philippines", "phl": "philippines",
        "il": "israel", "isr": "israel",
        "ae": "united arab emirates", "uae": "united arab emirates",
        "sa": "saudi arabia", "sau": "saudi arabia",
        "pk": "pakistan", "pak": "pakistan",
        # Africa
        "za": "south africa", "zaf": "south africa",
        "ng": "nigeria", "nga": "nigeria",
        "ke": "kenya", "ken": "kenya",
        "eg": "egypt", "egy": "egypt",
    }
    
    def _normalize_country(self, name: str) -> str:
        """Lower-case and resolve common aliases / ISO codes to canonical form."""
        lower = name.strip().lower()
        return self.COUNTRY_ALIASES.get(lower, lower)
    
    @staticmethod
    def _tokenize_location(location_str: str) -> List[str]:
        """
        Split a location string into meaningful segments for matching.
        
        "Buenos Aires, Argentina"  → ["buenos aires", "argentina"]
        "São Paulo, BR"            → ["são paulo", "br"]
        "New Mexico, USA"          → ["new mexico", "usa"]
        "Argentina"                → ["argentina"]
        """
        # Split on comma, slash, pipe, semicolon – common location separators
        parts = re.split(r"[,/|;]+", location_str)
        return [p.strip().lower() for p in parts if p.strip()]
    
    def _extract_applicant_location(self, applicant) -> Optional[str]:
        """
        Best-effort extraction of an applicant's location string.
        
        Sources checked (in priority order):
        1. Greenhouse profile_data → addresses[0].value
        2. Parsed resume → contact_info.location  (or top-level location)
        3. Most recent experience entry location
        """
        # 1. Greenhouse profile_data
        if applicant.profile_data and isinstance(applicant.profile_data, dict):
            addresses = applicant.profile_data.get("addresses", [])
            if addresses and isinstance(addresses, list):
                for addr in addresses:
                    val = addr.get("value") if isinstance(addr, dict) else None
                    if val:
                        return val
        
        # 2. Parsed resume location
        if applicant.resume_parsed and isinstance(applicant.resume_parsed, dict):
            # Top-level location on the parsed resume
            loc = applicant.resume_parsed.get("location")
            if loc:
                return loc
            
            # Some parsers nest it under contact_info
            contact = applicant.resume_parsed.get("contact_info", {})
            if isinstance(contact, dict):
                loc = contact.get("location")
                if loc:
                    return loc
            
            # 3. Fall back to most recent experience location
            experience = applicant.resume_parsed.get("experience", [])
            if experience and isinstance(experience, list):
                for exp in experience:
                    if isinstance(exp, dict):
                        exp_loc = exp.get("location")
                        if exp_loc:
                            # Could be a string or {"name": "..."} dict
                            if isinstance(exp_loc, dict):
                                return exp_loc.get("name")
                            return exp_loc
        
        return None
    
    def _location_matches_countries(self, location_str: Optional[str],
                                     required_countries: List[str]) -> bool:
        """
        Return True if *location_str* resolves to a country in *required_countries*.
        
        Strategy: split the location on commas and check each **segment** as a
        whole token against the canonical country names.  This prevents
        "New Mexico, USA" from matching "Mexico" (segment "new mexico" ≠ "mexico")
        while still matching "São Paulo, BR" → segment "br" → canonical "brazil".
        
        An empty / None required_countries list means "no restriction" → always True.
        """
        if not required_countries:
            return True
        if not location_str:
            return False
        
        # Build the set of canonical country names we accept
        accepted = set()
        for country in required_countries:
            accepted.add(self._normalize_country(country))
        
        # Tokenize the location and resolve each segment
        segments = self._tokenize_location(location_str)
        for segment in segments:
            # Resolve the segment through aliases (handles "BR" → "brazil")
            resolved = self._normalize_country(segment)
            if resolved in accepted:
                return True
            # Also check if the raw segment exactly equals any accepted name
            # (handles a location like "Buenos Aires, Argentina" where
            #  "argentina" is already the canonical form)
            if segment in accepted:
                return True
        
        return False
    
    def _filter_applicants_by_location(
        self,
        applicants: list,
        required_countries: List[str],
    ) -> list:
        """
        Hard pre-filter: remove applicants whose location doesn't match
        any of the required countries.  Applicants with *no detectable
        location* are kept (we can't prove they're outside the requirement).
        """
        if not required_countries:
            return applicants
        
        filtered = []
        removed = []
        for applicant in applicants:
            loc = self._extract_applicant_location(applicant)
            if loc is None or self._location_matches_countries(loc, required_countries):
                filtered.append(applicant)
            else:
                removed.append({
                    "id": applicant.id,
                    "name": f"{applicant.first_name} {applicant.last_name}".strip(),
                    "detected_location": loc,
                })
        
        if removed:
            logger.info("applicants_filtered_by_location",
                       analysis_id=self.analysis_id,
                       required_countries=required_countries,
                       removed_count=len(removed),
                       remaining_count=len(filtered),
                       removed_applicants=removed)
        
        return filtered
    
    def _filter_market_candidates_by_location(
        self,
        candidates: List[Dict[str, Any]],
        required_countries: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Hard post-filter: remove market candidates returned by the AI agent
        whose location doesn't match any of the required countries.
        Candidates with no location field are kept.
        """
        if not required_countries:
            return candidates
        
        filtered = []
        removed = []
        for candidate in candidates:
            loc = candidate.get("location") or candidate.get("location_name")
            if loc is None or self._location_matches_countries(loc, required_countries):
                filtered.append(candidate)
            else:
                removed.append({
                    "name": candidate.get("name", "Unknown"),
                    "detected_location": loc,
                })
        
        if removed:
            logger.info("market_candidates_filtered_by_location",
                       analysis_id=self.analysis_id,
                       required_countries=required_countries,
                       removed_count=len(removed),
                       remaining_count=len(filtered),
                       removed_candidates=removed)
        
        return filtered
        
    def _create_job_analyst(self) -> Agent:
        """
        Create the Job Analyst Agent with excellent prompting
        
        Role: Extract requirements and define ideal candidate persona
        """
        return Agent(
            role="Senior Talent Acquisition Specialist",
            goal="Extract key requirements, skills, and attributes from job descriptions to define the ideal candidate persona",
            backstory="""You are a Senior Talent Acquisition Specialist with 15+ years of experience 
            recruiting top talent across technology companies, healthcare, finance, and consulting. 
            
            Your superpower is understanding job requirements deeply and translating them into 
            actionable candidate profiles that recruiters can actually use.
            
            You've placed thousands of candidates and know what makes someone truly successful in a role.
            You think beyond keywords - you understand career paths, skill combinations, cultural fit,
            and the subtle signals that separate good candidates from great ones.
            
            You're known for your ability to read between the lines of job descriptions and identify 
            what companies REALLY need, not just what they say they need.""",
            verbose=True,
            allow_delegation=False,
            llm_config={
                "model": settings.crewai_llm_model,
                "temperature": 0.3,  # Lower temperature for more focused analysis
            }
        )
    
    def _create_talent_scout(self) -> Agent:
        """
        Create the Talent Scout Agent with search tools
        
        Role: Find candidates using Elasticsearch and Neo4j
        """
        return Agent(
            role="Expert People Search Specialist",
            goal="Find top candidates matching the ideal persona using advanced search tools and strategies",
            backstory="""You are an Expert People Search Specialist with deep knowledge of talent 
            databases, search strategies, and sourcing techniques.
            
            You've spent 10+ years mastering the art of finding hidden gems in talent pools. You know 
            how to craft search queries that find the perfect candidates, not just keyword matches.
            
            You understand that the best candidates often have non-obvious backgrounds. You look for:
            - Transferable skills from adjacent roles
            - Career progression patterns that indicate growth potential
            - Company backgrounds that signal relevant experience
            - Skill combinations that create unique value
            
            You're a master at using multiple search approaches:
            - Full-text search for broad discovery
            - Skill-based search for technical matching  
            - Career path analysis for progression patterns
            - Network analysis for ecosystem fit
            
            You always explain your search strategy and refine based on results. You don't just 
            return names - you understand WHY each candidate would be a great fit.""",
            tools=self.search_tools,  # Give agent access to search tools
            verbose=True,
            allow_delegation=False,
            llm_config={
                "model": settings.crewai_llm_model,
                "temperature": 0.4,  # Slightly higher for creative search strategies
            }
        )
    
    def _create_insights_synthesizer(self) -> Agent:
        """
        Create the Insights Synthesizer Agent
        
        Role: Generate actionable intelligence and recommendations
        """
        return Agent(
            role="Talent Intelligence Analyst",
            goal="Transform raw search data into strategic insights and actionable recommendations",
            backstory="""You are a Talent Intelligence Analyst who turns data into decisions.
            
            You've advised hundreds of companies on their talent strategies, from startups to 
            Fortune 500 companies. Your reports have influenced hiring decisions worth millions.
            
            You excel at:
            - Identifying patterns in talent pools
            - Understanding market dynamics and competition for talent
            - Creating candidate profiles that hiring managers immediately understand
            - Generating insights that shape sourcing strategies
            - Explaining complex data in simple, actionable terms
            
            You think like a strategic advisor. You don't just present data - you interpret it,
            contextualize it, and recommend specific actions.
            
            Your reports are known for being:
            - Executive-ready (clear, concise, actionable)
            - Data-driven (backed by evidence)
            - Strategic (forward-looking recommendations)
            - Practical (implementable by recruiting teams)
            
            You always include specific examples and explain your reasoning.""",
            verbose=True,
            allow_delegation=False,
            llm_config={
                "model": settings.crewai_llm_model,
                "temperature": 0.5,  # Higher for creative insights
            }
        )
    
    @start()
    def analyze_job(self):
        """
        Step 1: Analyze job description and ideal candidate description to extract persona
        
        NOTE: Now accepts BOTH job description AND ideal candidate description for richer context
        """
        logger.info("talent_flow_step_1_started", 
                   analysis_id=self.analysis_id,
                   customer_id=self.customer_id)
        
        # Get input
        state = self.state
        job_description = state.job_description
        ideal_candidate_description = state.ideal_candidate_description
        manual_persona = state.manual_persona
        
        # If manual persona provided, skip analysis
        if manual_persona:
            logger.info("using_manual_persona", analysis_id=self.analysis_id)
            self.state.ideal_persona = manual_persona
            return
        
        # Build context for the agent (both JD and ideal candidate description)
        context_parts = []
        
        if job_description:
            context_parts.append(f"""
            JOB DESCRIPTION:
            {job_description}
            """)
        
        if ideal_candidate_description:
            context_parts.append(f"""
            IDEAL CANDIDATE DESCRIPTION (Natural Language Input):
            {ideal_candidate_description}
            
            This is a natural language description of the ideal candidate. Use it to enhance 
            and refine your understanding of what we're looking for. It may include details 
            about personality, culture fit, specific experiences, or attributes that aren't 
            in the formal job description.
            """)
        
        full_context = "\n\n".join(context_parts)
        
        # Create analysis task with excellent prompt
        analysis_task = Task(
            description=f"""
            Analyze the provided inputs and extract the ideal candidate persona.
            
            {full_context}
            
            YOUR TASK:
            Synthesize BOTH the job description (if provided) and the ideal candidate description 
            (if provided) to create a comprehensive ideal candidate persona. Think deeply about what 
            this role really needs and what kind of background would make someone successful.
            
            Use ALL the information provided to build the most complete, actionable persona possible.
            
            Provide your analysis in this exact JSON format:
            {{
                "role_summary": {{
                    "title": "exact role title",
                    "seniority_level": "entry/mid/senior/staff/principal/director/vp/c-level",
                    "role_type": "individual_contributor/manager/director/executive",
                    "key_responsibilities": ["responsibility 1", "responsibility 2", ...]
                }},
                "required_qualifications": {{
                    "technical_skills": [
                        {{"skill": "Python", "proficiency": "expert", "years": 5}},
                        {{"skill": "AWS", "proficiency": "advanced", "years": 3}}
                    ],
                    "soft_skills": ["leadership", "communication", "problem-solving"],
                    "education": ["Bachelor's in Computer Science or related field"],
                    "certifications": ["AWS Certified", "PMP"],
                    "years_experience": {{"minimum": 5, "ideal": 8}}
                }},
                "ideal_background": {{
                    "previous_titles": ["Software Engineer", "Senior Developer"],
                    "target_companies": ["Google", "Amazon", "Microsoft", "high-growth startups"],
                    "company_types": ["enterprise tech", "SaaS", "fintech"],
                    "company_sizes": ["1000-5000", "5000+"],
                    "industries": ["technology", "financial services"]
                }},
                "location_preferences": {{
                    "required_countries": ["list of countries candidates MUST be located in, empty if no restriction"],
                    "preferred_regions": ["list of preferred regions/cities/states"],
                    "remote_ok": true,
                    "relocation_ok": false,
                    "location_notes": "any additional location context from the description"
                }},
                "career_signals": {{
                    "positive_indicators": [
                        "promoted within 2 years",
                        "led team of 5+ engineers",
                        "shipped products to production"
                    ],
                    "red_flags": [
                        "frequent job hopping (< 1 year per role)",
                        "lack of technical depth"
                    ],
                    "growth_trajectory": "steady progression from IC to senior roles"
                }},
                "cultural_fit": {{
                    "work_style": ["collaborative", "autonomous", "data-driven"],
                    "team_dynamics": ["cross-functional", "agile"],
                    "company_values": ["innovation", "customer-focus"]
                }},
                "must_haves": ["skill/attribute that is non-negotiable"],
                "nice_to_haves": ["bonus skills or experiences"]
            }}
            
            Be specific and actionable. Think like a recruiter who will use this to find candidates.
            Focus on realistic, findable attributes.
            """,
            expected_output="JSON object with ideal candidate persona",
            agent=self.job_analyst
        )
        
        # Execute task
        crew = Crew(
            agents=[self.job_analyst],
            tasks=[analysis_task],
            verbose=True
        )
        result = self._kickoff_with_trace(
            crew=crew,
            span_name="agentmesh.talent.analyze_job",
            input_data={
                "analysis_id": self.analysis_id,
                "question_has_manual_persona": bool(self.state.manual_persona),
                "job_description": (self.state.job_description or "")[:2000],
                "ideal_candidate_description": (self.state.ideal_candidate_description or "")[:2000],
            },
        )
        
        # Track token usage
        self._track_token_usage("analyze_job", result)
        
        # Parse result
        try:
            persona = json.loads(str(result))
            self.state.ideal_persona = persona
            logger.info("job_analysis_completed", 
                       analysis_id=self.analysis_id,
                       persona_keys=list(persona.keys()))
        except json.JSONDecodeError as e:
            logger.error("failed_to_parse_persona", 
                        error=str(e),
                        result=str(result))
            # Fallback: store raw result
            self.state.ideal_persona = {"raw": str(result)}
    
    @listen(analyze_job)
    def score_applicants(self):
        """
        Pipeline 1: Score applicants from HR platform against baseline
        
        Steps:
        1. Get or build baseline profile for role
        2. Get all applicants for job posting
        3. Ensure resumes are parsed
        4. Score each applicant against baseline
        5. Return top 5 applicants
        """
        logger.info("applicant_pipeline_started", 
                   analysis_id=self.analysis_id,
                   job_posting_id=self.job_posting_id)
        
        # Skip if no job posting ID (market-only analysis)
        if not self.job_posting_id:
            logger.info("no_job_posting_id_skipping_applicants", analysis_id=self.analysis_id)
            self.state.applicant_results = []
            return
        
        try:
            persona = self.state.ideal_persona
            role_title = persona.get("role_summary", {}).get("title", "Unknown Role")
            
            # Step 1: Get or build baseline profile
            baseline_builder = BaselineProfileBuilder(self.db, self.customer_id)
            baseline = baseline_builder.build_baseline_for_role(role_title)
            
            if not baseline:
                logger.warning("no_baseline_profile_created",
                             role_title=role_title,
                             analysis_id=self.analysis_id)
                self.state.applicant_results = []
                return
            
            self.state.baseline_profile_id = baseline.id
            
            # Step 2: Get applicants for this job posting
            # Exclude hired and rejected candidates - they should not be re-scored
            excluded_statuses = ['hired', 'rejected']
            applicants = self.db.query(Applicant).filter(
                Applicant.job_posting_id == self.job_posting_id,
                Applicant.customer_id == self.customer_id,
                Applicant.status.notin_(excluded_statuses)
            ).all()
            
            logger.info("applicants_filtered_by_status",
                       analysis_id=self.analysis_id,
                       job_posting_id=self.job_posting_id,
                       excluded_statuses=excluded_statuses,
                       applicants_after_status_filter=len(applicants))
            
            # Step 2b: Location pre-filter – drop anyone outside required countries
            required_countries = (
                persona.get("location_preferences", {})
                       .get("required_countries", [])
            )
            # Ignore placeholder values the LLM may leave in the template
            if required_countries and isinstance(required_countries, list):
                required_countries = [
                    c for c in required_countries
                    if isinstance(c, str)
                    and c.strip()
                    and "list of" not in c.lower()
                    and "empty" not in c.lower()
                ]
            
            if required_countries:
                pre_filter_count = len(applicants)
                applicants = self._filter_applicants_by_location(
                    applicants, required_countries
                )
                logger.info("applicants_after_location_filter",
                           analysis_id=self.analysis_id,
                           required_countries=required_countries,
                           before=pre_filter_count,
                           after=len(applicants))
            
            if not applicants:
                logger.warning("no_applicants_found",
                             job_posting_id=self.job_posting_id,
                             analysis_id=self.analysis_id)
                self.state.applicant_results = []
                return
            
            logger.info("scoring_applicants",
                       applicant_count=len(applicants),
                       baseline_id=baseline.id)
            
            # Step 3 & 4: Score each applicant
            scored_applicants = []
            
            for applicant in applicants:
                # Convert parsed resume to PDL format
                if applicant.resume_parsed:
                    from src.services.resume_processing.docling_parser import ParsedResume
                    parsed_resume = ParsedResume(**applicant.resume_parsed)
                    candidate_data = self.docling_parser.normalize_to_pdl_format(parsed_resume)
                    
                    # Score against baseline
                    score_result = self.scoring_engine.score_candidate(
                        candidate_data=candidate_data,
                        baseline_profile=baseline,
                        analysis_id=self.analysis_id
                    )
                    
                    # Save score to database
                    applicant_score = ApplicantScore(
                        applicant_id=applicant.id,
                        analysis_id=self.analysis_id,
                        overall_score=score_result["overall_score"],
                        skills_score=score_result["skills_score"],
                        experience_score=score_result["experience_score"],
                        career_trajectory_score=score_result["career_trajectory_score"],
                        company_fit_score=score_result["company_fit_score"],
                        education_score=score_result["education_score"],
                        embedding_similarity=score_result["embedding_similarity"],
                        matched_employee_ids=score_result["matched_employee_ids"],
                        dimension_scores=score_result["dimension_scores"],
                        reasoning=score_result["reasoning"]
                    )
                    self.db.add(applicant_score)
                    
                    # Add to results
                    scored_applicants.append({
                        "applicant_id": applicant.id,
                        "name": f"{applicant.first_name} {applicant.last_name}".strip(),
                        "email": applicant.email,
                        "overall_score": score_result["overall_score"],
                        "dimension_scores": score_result["dimension_scores"],
                        "reasoning": score_result["reasoning"],
                        "source": "applicant",
                        "resume_parsed": candidate_data
                    })
            
            self.db.commit()
            
            # Step 5: Sort and return top 5
            scored_applicants.sort(key=lambda x: x["overall_score"], reverse=True)
            self.state.applicant_results = scored_applicants[:5]
            
            logger.info("applicant_pipeline_completed",
                       analysis_id=self.analysis_id,
                       scored_count=len(scored_applicants),
                       top_5_count=len(self.state.applicant_results))
            
        except Exception as e:
            logger.error("applicant_pipeline_failed",
                        analysis_id=self.analysis_id,
                        error=str(e),
                        exc_info=True)
            self.state.applicant_results = []
    
    @listen(score_applicants)
    def search_market_candidates(self):
        """
        Step 2: Search for candidates using the ideal persona
        """
        logger.info("talent_flow_step_2_started", analysis_id=self.analysis_id)
        
        persona = self.state.ideal_persona
        
        # Create search task with excellent prompt
        search_task = Task(
            description=f"""
            Use your search tools to find TOP candidates matching this ideal persona:
            
            IDEAL PERSONA:
            {json.dumps(persona, indent=2)}
            
            YOUR MISSION:
            Find 20-50 candidates who best match this profile. Use ALL available search tools 
            strategically and iteratively.
            
            CRITICAL - LOCATION FILTERING:
            Check the persona's "location_preferences" field carefully.
            - If "required_countries" is NOT empty, you MUST only return candidates located in those countries.
            - Use the "location" parameter in your search tool calls to filter by location.
            - If a search tool does not support location filtering, manually exclude candidates 
              outside the required countries from your results.
            - This is a HARD REQUIREMENT - do not include candidates from other locations.
            
            SEARCH STRATEGY:
            
            1. START BROAD - Full-Text Search
               - Search for job titles from the persona
               - Search for target companies
               - ALWAYS include location filter if required_countries is specified
               - Get a sense of the candidate landscape
               - Tool: person_full_text_search
            
            2. REFINE WITH SKILLS - Skill-Based Search
               - Search for required technical skills
               - Look for skill combinations
               - Filter by proficiency if needed
               - Tool: person_skill_search
            
            3. ANALYZE PATTERNS - Career Path Search
               - Look at common career transitions
               - Identify successful progression patterns
               - Find people from target companies
               - Tool: person_career_path_search
            
            4. FIND LOOK-ALIKES - Hybrid Search
               - Use the full persona for comprehensive matching
               - Get ranked results with fit scores
               - Tool: person_lookalike_search
            
            5. ITERATE & REFINE
               - Review initial results
               - Adjust search parameters
               - Try adjacent job titles
               - Consider transferable skills
            
            FOR EACH SEARCH:
            - Explain your search strategy
            - Show the parameters you're using
            - INCLUDE location filter when required_countries is specified
            - Analyze the quality of results
            - Decide if you need to refine
            
            RANKING CRITERIA:
            Score each candidate on:
            - Skills match (0-100)
            - Experience level fit (0-100)
            - Career trajectory alignment (0-100)
            - Company background relevance (0-100)
            - Location match (0-100) - 100 if in required country, 0 if not
            - Cultural fit signals (0-100)
            
            OUTPUT FORMAT:
            Return a JSON array of candidates with:
            {{
                "search_strategy_summary": "explanation of your approach",
                "total_candidates_evaluated": number,
                "top_candidates": [
                    {{
                        "person_id": 123,
                        "name": "Jane Doe",
                        "current_title": "Senior Software Engineer",
                        "current_company": "Google",
                        "location": "Buenos Aires, Argentina",
                        "skills": ["Python", "AWS", "Kubernetes"],
                        "experience_years": 8,
                        "education": [...],
                        "fit_scores": {{
                            "overall": 92,
                            "skills_match": 95,
                            "experience_fit": 90,
                            "career_trajectory": 88,
                            "company_background": 92,
                            "location_match": 100,
                            "cultural_fit": 90
                        }},
                        "why_great_fit": "2-3 sentence explanation",
                        "potential_concerns": "any concerns or gaps",
                        "search_source": "which tool/query found them"
                    }}
                ]
            }}
            
            Be thorough. Use multiple searches. Find the BEST candidates, not just matches.
            """,
            expected_output="JSON object with search results and ranked candidates",
            agent=self.talent_scout
        )
        
        # Execute task
        crew = Crew(
            agents=[self.talent_scout],
            tasks=[search_task],
            verbose=True
        )
        result = self._kickoff_with_trace(
            crew=crew,
            span_name="agentmesh.talent.search_market_candidates",
            input_data={
                "analysis_id": self.analysis_id,
                "persona_summary": (self.state.ideal_persona or {}),
            },
        )
        
        # Track token usage
        self._track_token_usage("search_market_candidates", result)
        
        # Parse result
        try:
            search_results = json.loads(str(result))
            market_candidates = search_results.get('top_candidates', [])
            
            # Add source tag
            for candidate in market_candidates:
                candidate["source"] = "market"
            
            # Location post-filter – hard-drop anyone outside required countries
            persona = self.state.ideal_persona or {}
            required_countries = (
                persona.get("location_preferences", {})
                       .get("required_countries", [])
            )
            if required_countries and isinstance(required_countries, list):
                required_countries = [
                    c for c in required_countries
                    if isinstance(c, str)
                    and c.strip()
                    and "list of" not in c.lower()
                    and "empty" not in c.lower()
                ]
            
            if required_countries:
                pre_filter_count = len(market_candidates)
                market_candidates = self._filter_market_candidates_by_location(
                    market_candidates, required_countries
                )
                logger.info("market_candidates_after_location_filter",
                           analysis_id=self.analysis_id,
                           required_countries=required_countries,
                           before=pre_filter_count,
                           after=len(market_candidates))
            
            self.state.market_results = market_candidates[:10]
            logger.info("market_search_completed",
                       analysis_id=self.analysis_id,
                       candidates_found=len(self.state.market_results))
        except json.JSONDecodeError as e:
            logger.error("failed_to_parse_search_results",
                        error=str(e),
                        result=str(result))
            self.state.market_results = []
    
    @listen(search_market_candidates)
    def combine_and_rank(self):
        """
        Step 3: Combine applicant and market results, compute top 3 overall
        """
        logger.info("combining_results", analysis_id=self.analysis_id)
        
        applicants = self.state.applicant_results or []
        market = self.state.market_results or []
        
        # Combine all candidates
        all_candidates = []
        
        # Add applicants with their scores
        for app in applicants:
            all_candidates.append({
                **app,
                "score": app["overall_score"],  # Normalize score field
                "category": "Applicant"
            })
        
        # Add market candidates with their fit scores
        for mkt in market:
            # Market candidates have fit_scores from AI agents
            fit_score = mkt.get("fit_scores", {}).get("overall", 75)  # Default to 75 if missing
            all_candidates.append({
                **mkt,
                "score": fit_score,
                "category": "Market"
            })
        
        # Sort by score and get top 3 overall
        all_candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        self.state.top_overall = all_candidates[:3]
        
        logger.info("results_combined",
                   analysis_id=self.analysis_id,
                   total_candidates=len(all_candidates),
                   top_3_count=len(self.state.top_overall),
                   top_3_sources=[c.get("category") for c in self.state.top_overall])
    
    @listen(combine_and_rank)
    def synthesize_insights(self):
        """
        Step 3: Generate insights and recommendations
        """
        logger.info("talent_flow_step_3_started", analysis_id=self.analysis_id)
        
        job_description = self.state.job_description or "N/A"
        persona = self.state.ideal_persona
        applicants = self.state.applicant_results or []
        market_candidates = self.state.market_results or []
        top_overall = self.state.top_overall or []
        
        # Create synthesis task
        synthesis_task = Task(
            description=f"""
            Create a comprehensive Talent Intelligence Report.
            
            INPUTS:
            
            Job Description:
            {job_description}
            
            Ideal Persona:
            {json.dumps(persona, indent=2)}
            
            **DUAL PIPELINE RESULTS:**
            
            Applicants ({len(applicants)} scored):
            {json.dumps(applicants, indent=2) if applicants else "No applicants"}
            
            Market Candidates ({len(market_candidates)} found):
            {json.dumps(market_candidates[:5], indent=2) if market_candidates else "No market candidates"}
            
            Top 3 Overall (combined ranking):
            {json.dumps(top_overall, indent=2)}
            
            YOUR TASK:
            Synthesize this information into an executive-ready Talent Intelligence Report.
            
            REPORT STRUCTURE:
            
            {{
                "executive_summary": {{
                    "overview": "2-3 paragraph summary of findings",
                    "top_recommendation": "single best candidate with brief rationale",
                    "key_insights": ["insight 1", "insight 2", "insight 3"],
                    "bottom_line": "clear recommendation for next steps"
                }},
                "ideal_persona_refined": {{
                    "must_have_attributes": ["based on actual top candidates"],
                    "nice_to_have_attributes": ["bonus attributes found"],
                    "unique_differentiators": ["what makes top candidates special"],
                    "persona_summary": "1-paragraph ideal candidate description"
                }},
                "market_analysis": {{
                    "total_qualified_candidates": number,
                    "candidate_distribution": {{
                        "by_current_company": {{"Google": 10, "Amazon": 8}},
                        "by_experience_level": {{"5-7 years": 15, "8-10 years": 12}},
                        "by_location": {{"San Francisco": 20, "New York": 15}}
                    }},
                    "skills_availability": {{
                        "common_skills": ["skills most candidates have"],
                        "rare_skills": ["skills that are scarce"]
                    }},
                    "market_insights": [
                        "trend or pattern observed",
                        "competitive intelligence"
                    ]
                }},
                "top_candidates_analysis": [
                    {{
                        "rank": 1,
                        "name": "Jane Doe",
                        "current_title": "Senior Engineer",
                        "current_company": "Google",
                        "overall_fit_score": 92,
                        "fit_breakdown": {{"skills": 95, "experience": 90, ...}},
                        "why_excellent_fit": "3-4 sentence detailed explanation",
                        "key_strengths": ["strength 1", "strength 2"],
                        "potential_concerns": ["concern if any"],
                        "outreach_recommendation": "suggested approach for contacting"
                    }}
                ],
                "sourcing_recommendations": {{
                    "priority_companies_to_target": ["company names with rationale"],
                    "effective_search_keywords": ["keywords that found top candidates"],
                    "job_boards_and_communities": ["where to find more"],
                    "networking_strategies": ["specific tactics"],
                    "alternative_titles_to_search": ["related job titles"]
                }},
                "competitive_intelligence": {{
                    "companies_losing_talent": ["companies people are leaving"],
                    "companies_attracting_talent": ["companies people are joining"],
                    "emerging_trends": ["trends in this talent pool"],
                    "market_dynamics": "analysis of supply/demand"
                }},
                "next_steps": [
                    "specific actionable step 1",
                    "specific actionable step 2"
                ]
            }}
            
            Make your insights ACTIONABLE. Think like a strategic advisor.
            Be specific with examples. Explain your reasoning.
            Focus on helping the hiring team make great decisions.
            """,
            expected_output="JSON object with comprehensive talent intelligence report",
            agent=self.insights_synthesizer
        )
        
        # Execute task
        crew = Crew(
            agents=[self.insights_synthesizer],
            tasks=[synthesis_task],
            verbose=True
        )
        result = self._kickoff_with_trace(
            crew=crew,
            span_name="agentmesh.talent.synthesize_insights",
            input_data={
                "analysis_id": self.analysis_id,
                "applicant_count": len(self.state.applicant_results or []),
                "market_count": len(self.state.market_results or []),
            },
        )
        
        # Track token usage
        self._track_token_usage("synthesize_insights", result)
        
        # Parse result
        try:
            insights = json.loads(str(result))
            self.state.insights_report = insights
            logger.info("insights_synthesis_completed",
                       analysis_id=self.analysis_id)
        except json.JSONDecodeError as e:
            logger.error("failed_to_parse_insights",
                        error=str(e),
                        result=str(result))
            self.state.insights_report = {"raw": str(result)}
    
    def run(self, 
            job_description: Optional[str] = None,
            ideal_candidate_description: Optional[str] = None,
            manual_persona: Optional[Dict[str, Any]] = None,
            job_posting_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute the talent intelligence flow with DUAL PIPELINE
        
        Args:
            job_description: Job description text (optional if manual_persona provided)
            ideal_candidate_description: Natural language description of ideal candidate (optional)
            manual_persona: Pre-defined persona dict (optional if job_description provided)
            job_posting_id: HR platform job posting ID for applicant scoring (optional)
            
        Returns:
            Complete analysis results with:
            - ideal_persona
            - applicant_results (top 5)
            - market_results (top 10)
            - top_overall (top 3 combined)
            - insights_report
            
        DUAL PIPELINE:
        - Pipeline 1: Score applicants from job_posting_id against baseline
        - Pipeline 2: Search market candidates from PDL
        - Combined: Top 3 overall from both groups
        """
        # Initialize state
        self.state = TalentAnalysisState(
            job_description=job_description,
            ideal_candidate_description=ideal_candidate_description,
            manual_persona=manual_persona,
            job_posting_id=job_posting_id or self.job_posting_id,
            customer_id=self.customer_id,
            analysis_id=self.analysis_id
        )
        
        # Run the flow
        logger.info("talent_flow_started",
                   analysis_id=self.analysis_id,
                   customer_id=self.customer_id,
                   has_job_description=bool(job_description),
                   has_ideal_candidate_description=bool(ideal_candidate_description),
                   has_manual_persona=bool(manual_persona))
        
        try:
            # Flow executes: analyze_job -> search_candidates -> synthesize_insights
            self.kickoff()
            
            # Log final token usage summary
            token_usage = self.state.token_usage
            logger.info("talent_flow_token_usage_summary",
                       analysis_id=self.analysis_id,
                       model=settings.crewai_llm_model,
                       total_tokens=token_usage["total_tokens"],
                       prompt_tokens=token_usage["prompt_tokens"],
                       completion_tokens=token_usage["completion_tokens"],
                       successful_requests=token_usage["successful_requests"],
                       by_step=token_usage["by_step"])
            
            # Return complete dual pipeline results
            return {
                "analysis_id": self.analysis_id,
                "customer_id": self.customer_id,
                "job_description": job_description,
                "ideal_candidate_description": ideal_candidate_description,
                "job_posting_id": job_posting_id or self.job_posting_id,
                "ideal_persona": self.state.ideal_persona,
                "applicant_results": self.state.applicant_results or [],
                "market_results": self.state.market_results or [],
                "top_overall": self.state.top_overall or [],
                "insights_report": self.state.insights_report,
                "status": "completed",
                "token_usage": token_usage,
                "model": settings.crewai_llm_model,
            }
            
        except Exception as e:
            logger.error("talent_flow_failed",
                        analysis_id=self.analysis_id,
                        error=str(e),
                        exc_info=True)
            return {
                "analysis_id": self.analysis_id,
                "status": "failed",
                "error": str(e),
                "token_usage": self.state.token_usage,
                "model": settings.crewai_llm_model,
            }


# Helper function to create and run flow
def run_talent_intelligence_analysis(
    customer_id: str,
    analysis_id: str,
    job_description: Optional[str] = None,
    ideal_candidate_description: Optional[str] = None,
    manual_persona: Optional[Dict[str, Any]] = None,
    job_posting_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run talent intelligence analysis with DUAL PIPELINE
    
    Args:
        customer_id: Customer ID for multi-tenancy
        analysis_id: Unique analysis ID
        job_description: Job description text (optional)
        ideal_candidate_description: Natural language ideal candidate description (optional)
        manual_persona: Pre-defined persona (optional)
        job_posting_id: HR platform job posting ID for applicant scoring (optional)
        
    Returns:
        Complete analysis results with dual pipeline:
        - applicant_results: Top 5 applicants (scored against baseline)
        - market_results: Top 10 market candidates (from PDL search)
        - top_overall: Top 3 overall (combined ranking)
        
    DUAL PIPELINE:
    If job_posting_id provided:
      - Pipeline 1: Score all applicants for that job posting
      - Pipeline 2: Search market candidates
      - Combine: Return top 3 overall
    
    If no job_posting_id:
      - Only Pipeline 2 runs (market search only)
    """
    flow = TalentIntelligenceFlow(
        customer_id=customer_id,
        analysis_id=analysis_id,
        job_posting_id=job_posting_id
    )
    
    return flow.run(
        job_description=job_description,
        ideal_candidate_description=ideal_candidate_description,
        manual_persona=manual_persona,
        job_posting_id=job_posting_id
    )
