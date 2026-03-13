"""
Content Writer Flow

CrewAI flow for the Research-First Content Writer product.
Orchestrates the complete content generation workflow:
1. Research Phase - Gather evidence from selected sources
2. POV Generation - Generate distinct POV options
3. Hook Generation - Create compelling opening hooks
4. Outline Generation - Structure long-form content
5. Draft Generation - Create full content draft (with parallel section generation)
6. Section Refinement - Surgical edits with POV transformation

This flow uses AI agents to:
- Analyze research and generate takeaways
- Create distinct POV approaches
- Craft engaging hooks
- Structure content outlines
- Generate drafts with skills/voice applied (sections in parallel for speed)
- Refine sections with user feedback
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import uuid

from crewai import Agent, Task, Crew, LLM
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory
from src.services.langfuse_service import get_langfuse_service

logger = get_logger(__name__, LogCategory.BUSINESS)
settings = get_settings()


# Pydantic models for structured responses
class ResearchExcerpt(BaseModel):
    """A research excerpt."""
    id: int
    text: str
    source_url: Optional[str] = None
    source_type: str
    metadata: Optional[Dict[str, Any]] = None


class KeyTakeaway(BaseModel):
    """A key takeaway from research."""
    text: str
    theme: Optional[str] = None
    source: Optional[str] = None


class ContestedItem(BaseModel):
    """A contested/debatable claim."""
    claim: str
    pro_evidence: List[str] = []
    con_evidence: List[str] = []


class POVPointer(BaseModel):
    """A POV concept/approach suggestion."""
    index: int
    label: str
    description: str
    key_concepts: List[str]
    research_refs: Optional[List[int]] = None


class HookOption(BaseModel):
    """A hook option using the Alec Paul framework."""
    index: int
    title: Optional[str] = None  # For blog/twitter article (null for LinkedIn)
    lede: str  # Full hook - Line 1 + Line 2
    line1: Optional[str] = None  # Standalone first line (mobile test)
    pattern: Optional[str] = None  # Hook pattern used
    why_it_works: Optional[str] = None  # Why this hook is effective


class OutlineSection(BaseModel):
    """A section in an outline."""
    title: str
    summary: str


class OutlineOption(BaseModel):
    """An outline option."""
    index: int
    sections: List[OutlineSection]


class ContentWriterFlow:
    """
    Content Writer Flow for AI-powered content generation.
    
    This is a simplified flow class that orchestrates agents for each phase.
    Unlike CrewAI's Flow class, this uses direct agent execution for more control.
    """
    
    def __init__(
        self,
        run_id: str,
        customer_id: str,
        user_id: int,
        topic: str,
        format: str,
        selected_sources: List[str],
        pasted_text: Optional[str] = None,
        constraints: Optional[Dict[str, Any]] = None,
        selected_pov: Optional[Dict[str, Any]] = None,
        selected_hook: Optional[Dict[str, Any]] = None,
        selected_outline: Optional[Dict[str, Any]] = None,
        research_pack: Optional[List[Dict[str, Any]]] = None,
        user_skills: Optional[List[Dict[str, Any]]] = None,
    ):
        self.run_id = run_id
        self.customer_id = customer_id
        self.user_id = user_id
        self.topic = topic
        self.format = format
        self.selected_sources = selected_sources
        self.pasted_text = pasted_text
        self.constraints = constraints or {}
        self.selected_pov = selected_pov
        self.selected_hook = selected_hook
        self.selected_outline = selected_outline
        self.research_pack = research_pack or []
        self.user_skills = user_skills or []
        self.langfuse_service = get_langfuse_service()
        self.trace_id = self.langfuse_service.current_trace_id
        
        # Initialize LLMs - gpt-4o for quality, gpt-4o-mini for speed
        self.llm = self._create_llm(fast=False)  # gpt-4o for main tasks
        self.fast_llm = self._create_llm(fast=True)  # gpt-4o-mini for parallel section generation
    
    def _create_llm(self, fast: bool = False) -> LLM:
        """Create the LLM instance for agents.
        
        Args:
            fast: If True, use gpt-4o-mini for speed. If False, use gpt-4o for quality.
        """
        # Always use gpt-4o for quality, gpt-4o-mini only when speed is critical
        model = "gpt-4o-mini" if fast else "gpt-4o"
        api_key = settings.openai_api_key
        
        return LLM(
            model=f"openai/{model}",
            api_key=api_key,
            temperature=0.7,
        )

    def _kickoff_with_trace(
        self,
        *,
        crew: Crew,
        span_name: str,
        input_data: Dict[str, Any],
    ):
        """Execute a Crew kickoff and attach it as a Langfuse span."""
        with self.langfuse_service.span_scope(
            name=span_name,
            input_data=input_data,
            metadata={
                "component": "agentmesh",
                "flow": "content_writer_flow",
                "run_id": self.run_id,
                "customer_id": self.customer_id,
                "user_id": self.user_id,
                "format": str(self.format),
                "topic": self.topic,
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
    
    # ==================== Research Phase ====================
    
    def _create_research_agent(self) -> Agent:
        """Create research analyst agent."""
        return Agent(
            role="Research Analyst",
            goal="Gather comprehensive evidence and insights on the given topic from multiple sources",
            backstory="""You are an expert research analyst who excels at finding 
            high-quality evidence, data, and perspectives on any topic. You organize 
            research into clear takeaways and identify areas of debate or controversy.""",
            llm=self.llm,
            verbose=False,
        )
    
    def conduct_research(self) -> Dict[str, Any]:
        """
        Conduct research phase.
        
        For MVP: Uses pasted text and generates synthetic research.
        In production: Would call actual source APIs.
        
        Returns:
            {
                "key_takeaways": [...],
                "excerpts": [...],
                "contested_items": [...],
                "best_counterargument": str
            }
        """
        logger.info(f"Conducting research for run {self.run_id}")
        
        agent = self._create_research_agent()
        
        # Build research context
        context = f"""
        Topic: {self.topic}
        Format: {self.format}
        Selected Sources: {', '.join(self.selected_sources)}
        """
        
        if self.pasted_text:
            context += f"\n\nUser-provided text:\n{self.pasted_text[:5000]}"
        
        if self.constraints:
            context += f"\n\nConstraints: {json.dumps(self.constraints)}"
        
        task = Task(
            description=f"""Analyze the following content and extract key research for a {self.format} article.

{context}

Your task:
1. Identify 5-7 key takeaways from the content
2. Extract 8-10 notable excerpts with context
3. Identify any contested/debatable claims with pro/con evidence
4. Determine the strongest counterargument to the main thesis

Return a JSON object with this structure:
{{
    "key_takeaways": [
        {{"text": "...", "theme": "...", "source": "..."}}
    ],
    "excerpts": [
        {{"id": 0, "text": "...", "source_url": null, "source_type": "pasted_text", "metadata": {{}}}}
    ],
    "contested_items": [
        {{"claim": "...", "pro_evidence": ["..."], "con_evidence": ["..."]}}
    ],
    "best_counterargument": "..."
}}""",
            expected_output="A JSON object containing research analysis",
            agent=agent,
        )
        
        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=False,
        )
        
        try:
            result = self._kickoff_with_trace(
                crew=crew,
                span_name="agentmesh.content_writer.conduct_research",
                input_data={
                    "run_id": self.run_id,
                    "topic": self.topic,
                    "format": str(self.format),
                    "selected_sources": self.selected_sources,
                    "has_pasted_text": bool(self.pasted_text),
                },
            )
            
            # Parse result
            result_text = str(result)
            
            # Extract JSON from response
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(result_text)
            
            # Ensure IDs on excerpts
            for i, exc in enumerate(data.get("excerpts", [])):
                if "id" not in exc:
                    exc["id"] = i
            
            logger.info(f"Research complete: {len(data.get('key_takeaways', []))} takeaways, {len(data.get('excerpts', []))} excerpts")
            return data
            
        except Exception as e:
            logger.error(f"Research failed: {e}")
            # Return minimal research from pasted text
            return {
                "key_takeaways": [{"text": self.topic, "theme": "Main topic", "source": "user"}],
                "excerpts": [{"id": 0, "text": self.pasted_text[:500] if self.pasted_text else self.topic, "source_type": "pasted_text"}],
                "contested_items": [],
                "best_counterargument": None,
            }
    
    # ==================== POV Generation ====================
    
    def _create_pov_agent(self) -> Agent:
        """Create POV analysis agent."""
        return Agent(
            role="POV Strategist",
            goal="Generate diverse, compelling points of view for content creation",
            backstory="""You are an expert content strategist who can see topics from 
            multiple angles. You create distinct POV approaches that resonate with 
            different audience segments while maintaining intellectual honesty.""",
            llm=self.llm,
            verbose=False,
        )
    
    def generate_povs(self, research: Dict[str, Any], num_povs: int = 5) -> Dict[str, Any]:
        """
        Generate POV options based on research.
        
        Args:
            research: Research pack data
            num_povs: Number of POV options to generate
            
        Returns:
            {"pov_options": [...]}
        """
        logger.info(f"Generating {num_povs} POV options for run {self.run_id}")
        
        agent = self._create_pov_agent()
        
        # Build context from research
        takeaways = research.get("key_takeaways", [])
        excerpts = research.get("excerpts", [])
        contested = research.get("contested_items", [])
        
        context = f"""
Topic: {self.topic}
Format: {self.format}

Key Takeaways:
{json.dumps(takeaways[:5], indent=2)}

Notable Excerpts:
{json.dumps(excerpts[:5], indent=2)}

Contested Items:
{json.dumps(contested[:3], indent=2) if contested else "None identified"}
"""
        
        task = Task(
            description=f"""Generate {num_povs} distinct POV approaches for writing about this topic.

{context}

Each POV should be:
- Distinctly different from the others
- Intellectually honest (not strawman)
- Compelling for a specific audience
- Grounded in the research

Return a JSON object:
{{
    "pov_options": [
        {{
            "index": 0,
            "label": "Short label (e.g., 'Contrarian Take')",
            "description": "2-3 sentence description of this POV approach",
            "key_concepts": ["concept1", "concept2", "concept3"],
            "research_refs": [0, 2, 4]
        }}
    ]
}}

Generate exactly {num_povs} POV options.""",
            expected_output="A JSON object with POV options",
            agent=agent,
        )
        
        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=False,
        )
        
        try:
            result = self._kickoff_with_trace(
                crew=crew,
                span_name="agentmesh.content_writer.generate_povs",
                input_data={
                    "run_id": self.run_id,
                    "topic": self.topic,
                    "num_povs": num_povs,
                    "takeaway_count": len(research.get("key_takeaways", [])),
                    "excerpt_count": len(research.get("excerpts", [])),
                },
            )
            result_text = str(result)
            
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(result_text)
            
            logger.info(f"Generated {len(data.get('pov_options', []))} POV options")
            return data
            
        except Exception as e:
            logger.error(f"POV generation failed: {e}")
            return {
                "pov_options": [
                    {
                        "index": 0,
                        "label": "Balanced Analysis",
                        "description": "A balanced, evidence-based analysis of the topic.",
                        "key_concepts": ["evidence", "nuance", "context"],
                        "research_refs": None,
                    }
                ]
            }
    
    # ==================== Hook Generation ====================
    
    # Hook Writing Guide (Alec Paul Framework)
    HOOK_WRITING_GUIDE = """
## The 2-Line Hook Structure

### Line 1: Social Proof + Personal Storytelling
The opening sentence immediately builds credibility and teases a story.
- **Social Proof**: Shows you did something relevant to others (e.g., "I closed 71 deals in 60 days")
- **Personal Storytelling**: Makes it unique - can't find this anywhere else (e.g., "with just AI agents and no SDRs")
- **Combined Example**: "I grew notus to $80k MRR using only LinkedIn"

### Line 2: Expectation Setting
Tells the reader exactly what they'll get - creates curiosity by showing the "what" while hiding the "how."
Example: "If I had to start from 0 again, here are the exact 6 steps I'd follow."

## Hook Patterns That Work

1. **The Unexpected Result**: Specific result + counterintuitive twist
   Example: "$1M to $100M ARR in 12 months - The fastest-growing AI company in history didn't replace a single human."

2. **The Contrarian Confession**: Vulnerability + unexpected framing + curiosity gap
   Example: "I 'cheated' LinkedIn's algorithm and let an AI agent loose on the results. Most would call it a failure."

3. **The Data Revelation**: Specific numbers + scandal/tension + immediate stakes
   Example: "A $700M AI startup just got caught reporting $14M ARR when their real revenue was $3M."

4. **The Scale Proof**: Specific achievement + constraint that makes it impressive
   Example: "I closed 71 deals in the last 60 days – solo. No marketing, no SDRs."

5. **The Pattern Break**: Bold claim + new concept introduction
   Example: "Unicorns are dead. What we're left with are zombicorns."

## Quality Criteria

**Strong hooks have:**
- Information density (every word earns its place)
- Specificity (numbers, names, concrete details)
- Tension or curiosity gap
- Credibility signal within the first line
- Standalone power (works even if reader sees nothing else)

**Avoid these mistakes:**
- Teaching in the hook (removes reason to keep reading)
- Vague claims without specifics
- Buried social proof
- Weak first line that needs the second to make sense
- Generic statements that could apply to anyone

## Mobile Constraint
Mobile users cannot see content after the first line break. Line 1 MUST work standalone to earn the "see more" click.

## Key Principle
Don't optimize for short. Optimize for DENSE. Effective hooks can be long if every word earns its place.
"""
    
    def _create_hook_agent(self) -> Agent:
        """Create hook generation agent with Alec Paul framework."""
        return Agent(
            role="LinkedIn Hook Specialist",
            goal="Create high-performing hooks using the 2-line structure: Social Proof + Personal Story in Line 1, Expectation Setting in Line 2",
            backstory=f"""You are an expert hook writer trained on the Alec Paul framework for LinkedIn content.
            You understand that hooks create curiosity while establishing credibility - but they NEVER teach anything.
            The hook's only job is to earn the next line.
            
            You follow these principles:
            - Line 1 must work standalone (mobile constraint)
            - Social proof + personal storytelling in the opener
            - Expectation setting in the second line
            - Information density over brevity
            - Every word must earn its place
            
            {self.HOOK_WRITING_GUIDE}""",
            llm=self.llm,
            verbose=False,
        )
    
    def generate_hooks(self, num_hooks: int = 5) -> Dict[str, Any]:
        """
        Generate hook options using the Alec Paul framework.
        
        Args:
            num_hooks: Number of hooks to generate
            
        Returns:
            {"hook_options": [...]}
        """
        logger.info(f"Generating {num_hooks} hooks for run {self.run_id}")
        
        agent = self._create_hook_agent()
        
        # Build context
        pov_context = ""
        if self.selected_pov:
            pov_context = f"""
Selected POV: {self.selected_pov.get('label', '')}
POV Description: {self.selected_pov.get('description', '')}
Key Concepts: {', '.join(self.selected_pov.get('key_concepts', []))}"""
        
        # Format-specific guidance
        format_guidance = {
            "linkedin": """
For LinkedIn posts:
- No title needed - focus entirely on the opening lines
- Line 1 MUST work standalone (mobile users only see this before "see more")
- Use the 2-line structure: Social Proof + Story in Line 1, Expectation in Line 2
- Optimize for density, not brevity""",
            "blog": """
For blog posts:
- Create a compelling headline that creates curiosity
- Opening paragraph should hook with social proof and promise value
- Headline + first paragraph work together as the "hook" """,
            "twitter_article": """
For Twitter/X articles:
- Attention-grabbing title that stops the scroll
- Concise opening that delivers on title's promise
- Mobile-first: first line must work alone""",
        }
        
        # Research context for social proof
        research_context = ""
        if self.research_pack:
            takeaways = [e.get('text', '')[:100] for e in self.research_pack[:3]]
            research_context = f"\nKey evidence to potentially reference:\n- " + "\n- ".join(takeaways)
        
        task = Task(
            description=f"""Generate {num_hooks} high-performing hook options for a {self.format} piece.

TOPIC: {self.topic}
{pov_context}
{research_context}

FORMAT REQUIREMENTS:
{format_guidance.get(self.format, 'Create compelling openings.')}

HOOK WRITING FRAMEWORK:
{self.HOOK_WRITING_GUIDE}

YOUR TASK:
Generate {num_hooks} distinct hooks, each using a DIFFERENT pattern from the framework:
1. The Unexpected Result pattern
2. The Contrarian Confession pattern  
3. The Data Revelation pattern
4. The Scale Proof pattern
5. The Pattern Break pattern

For each hook, ensure:
- Line 1 contains social proof OR a credibility signal
- Line 1 works completely standalone (mobile test)
- Line 2 sets clear expectations without teaching the lesson
- Every word earns its place (information density)
- Curiosity is created by showing WHAT, hiding HOW

Return a JSON object:
{{
    "hook_options": [
        {{
            "index": 0,
            "title": "Headline (null for LinkedIn posts)",
            "lede": "The full hook - Line 1 (social proof + story) + Line 2 (expectation)",
            "line1": "Just the first line that must work standalone",
            "pattern": "Which pattern this uses (Unexpected Result, Contrarian Confession, etc.)",
            "why_it_works": "Brief explanation of why this hook is effective"
        }}
    ]
}}

QUALITY CHECK before returning:
- [ ] Does each Line 1 work standalone? (mobile test)
- [ ] Is there a social proof element in each?
- [ ] Does Line 2 set clear expectations?
- [ ] Is curiosity created without teaching the lesson?
- [ ] Would YOU click "see more" on this?

Generate exactly {num_hooks} hook options, each using a different pattern.""",
            expected_output="A JSON object with hook options following the Alec Paul framework",
            agent=agent,
        )
        
        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=False,
        )
        
        try:
            result = self._kickoff_with_trace(
                crew=crew,
                span_name="agentmesh.content_writer.generate_hooks",
                input_data={
                    "run_id": self.run_id,
                    "topic": self.topic,
                    "num_hooks": num_hooks,
                    "format": str(self.format),
                    "has_selected_pov": bool(self.selected_pov),
                },
            )
            result_text = str(result)
            
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(result_text)
            
            # Add format to each hook
            for hook in data.get("hook_options", []):
                hook["format"] = self.format
            
            logger.info(f"Generated {len(data.get('hook_options', []))} hooks")
            return data
            
        except Exception as e:
            logger.error(f"Hook generation failed: {e}")
            # Fallback with a reasonable hook structure
            return {
                "hook_options": [
                    {
                        "index": 0,
                        "title": self.topic if self.format != "linkedin" else None,
                        "lede": f"I spent months researching {self.topic}. Here's what most people get wrong.",
                        "line1": f"I spent months researching {self.topic}.",
                        "pattern": "Scale Proof",
                        "why_it_works": "Uses time investment as social proof and promises insider knowledge",
                        "format": self.format,
                    }
                ]
            }
    
    # ==================== Outline Generation ====================
    
    def _create_outline_agent(self) -> Agent:
        """Create outline generation agent."""
        return Agent(
            role="Content Architect",
            goal="Create well-structured outlines for long-form content",
            backstory="""You are an expert content architect who designs logical, 
            flowing content structures. You understand how to organize ideas for 
            maximum impact and reader engagement.""",
            llm=self.llm,
            verbose=False,
        )
    
    def generate_outlines(self, num_outlines: int = 3) -> Dict[str, Any]:
        """
        Generate outline options (for blog/twitter_article).
        
        Args:
            num_outlines: Number of outlines to generate
            
        Returns:
            {"outline_options": [...]}
        """
        logger.info(f"Generating {num_outlines} outlines for run {self.run_id}")
        
        agent = self._create_outline_agent()
        
        # Build context
        pov_context = ""
        if self.selected_pov:
            pov_context = f"\nSelected POV: {self.selected_pov.get('label', '')} - {self.selected_pov.get('description', '')}"
            key_concepts = self.selected_pov.get('key_concepts', [])
            if key_concepts:
                pov_context += f"\nKey concepts to incorporate: {', '.join(key_concepts)}"
        
        task = Task(
            description=f"""Generate {num_outlines} outline options for a {self.format} article.

Topic: {self.topic}
{pov_context}

Each outline should have 4-7 sections with clear titles and summaries.

Return a JSON object:
{{
    "outline_options": [
        {{
            "index": 0,
            "sections": [
                {{"title": "Section Title", "summary": "Brief description of section content"}}
            ]
        }}
    ]
}}

Generate exactly {num_outlines} outline options with different structures.""",
            expected_output="A JSON object with outline options",
            agent=agent,
        )
        
        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=False,
        )
        
        try:
            result = self._kickoff_with_trace(
                crew=crew,
                span_name="agentmesh.content_writer.generate_outlines",
                input_data={
                    "run_id": self.run_id,
                    "topic": self.topic,
                    "num_outlines": num_outlines,
                    "format": str(self.format),
                    "has_selected_pov": bool(self.selected_pov),
                },
            )
            result_text = str(result)
            
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(result_text)
            
            logger.info(f"Generated {len(data.get('outline_options', []))} outlines")
            return data
            
        except Exception as e:
            logger.error(f"Outline generation failed: {e}")
            return {
                "outline_options": [
                    {
                        "index": 0,
                        "sections": [
                            {"title": "Introduction", "summary": "Introduce the topic"},
                            {"title": "Main Argument", "summary": "Present the core thesis"},
                            {"title": "Evidence", "summary": "Support with evidence"},
                            {"title": "Conclusion", "summary": "Wrap up and call to action"},
                        ]
                    }
                ]
            }
    
    # ==================== Draft Generation ====================
    
    def _create_writer_agent(self) -> Agent:
        """Create content writer agent."""
        # Build backstory with skills
        backstory = """You are an expert content writer who creates engaging, 
        well-researched content. You maintain a consistent voice and style while 
        adapting to different formats and audiences."""
        
        if self.user_skills:
            backstory += "\n\nYour writing guidelines:\n"
            for skill in self.user_skills:
                if isinstance(skill, dict):
                    backstory += f"- {skill.get('name', '')}: {skill.get('description', '')}\n"
        
        return Agent(
            role="Content Writer",
            goal="Create high-quality, engaging content that resonates with the target audience",
            backstory=backstory,
            llm=self.llm,
            verbose=False,
        )
    
    def _generate_section(self, section: Dict[str, str], section_index: int, total_sections: int) -> str:
        """Generate a single section of the draft (for parallel execution)."""
        # Create agent with fast LLM for parallel section generation
        backstory = """You are an expert content writer who creates engaging, 
        well-researched content. You maintain a consistent voice and style."""
        
        if self.user_skills:
            backstory += "\n\nYour writing guidelines:\n"
            for skill in self.user_skills:
                if isinstance(skill, dict):
                    backstory += f"- {skill.get('name', '')}: {skill.get('description', '')}\n"
        
        agent = Agent(
            role="Section Writer",
            goal="Write one compelling section of a larger article",
            backstory=backstory,
            llm=self.fast_llm,  # Use fast LLM for parallel sections
            verbose=False,
        )
        
        # Build section context
        pov_context = ""
        if self.selected_pov:
            pov_context = f"""
POV to maintain: {self.selected_pov.get('label', '')} - {self.selected_pov.get('description', '')}
Key concepts: {', '.join(self.selected_pov.get('key_concepts', []))}"""
        
        research_context = ""
        if self.research_pack:
            research_context = f"\nResearch to potentially incorporate:\n{json.dumps(self.research_pack[:3], indent=2)}"
        
        position_hint = ""
        if section_index == 0:
            position_hint = "This is the FIRST section - set the stage and hook the reader."
        elif section_index == total_sections - 1:
            position_hint = "This is the FINAL section - wrap up with a strong conclusion and call to action."
        else:
            position_hint = f"This is section {section_index + 1} of {total_sections} - maintain flow from previous sections."
        
        task = Task(
            description=f"""Write the following section for a {self.format} article about "{self.topic}":

Section Title: {section.get('title', 'Untitled')}
Section Summary: {section.get('summary', '')}
{pov_context}
{research_context}

{position_hint}

Write 200-400 words for this section. Be engaging and informative.
Output ONLY the section content (with the section title as a heading). No JSON, no extra formatting.""",
            expected_output="Section content in plain text with heading",
            agent=agent,
        )
        
        crew = Crew(agents=[agent], tasks=[task], verbose=False)
        result = self._kickoff_with_trace(
            crew=crew,
            span_name="agentmesh.content_writer.generate_section",
            input_data={
                "run_id": self.run_id,
                "topic": self.topic,
                "section_index": section_index,
                "total_sections": total_sections,
                "section_title": section.get("title", "Untitled"),
            },
        )
        return str(result).strip()
    
    def _polish_draft(self, sections_content: str) -> str:
        """Final coherence pass to smooth transitions between sections."""
        agent = Agent(
            role="Editor",
            goal="Polish and ensure coherence across all sections",
            backstory="You are an expert editor who ensures content flows smoothly and maintains consistent voice.",
            llm=self.llm,  # Use main LLM (gpt-4o) for quality polish
            verbose=False,
        )
        
        hook_context = ""
        if self.selected_hook:
            hook_context = f"""
The article should start with this hook:
Title: {self.selected_hook.get('title', '')}
Opening: {self.selected_hook.get('lede', '')}
"""
        
        task = Task(
            description=f"""Polish this draft to ensure smooth transitions and consistent voice:

{hook_context}

DRAFT TO POLISH:
{sections_content}

Your task:
1. Add the hook/opening at the start (if provided above)
2. Smooth transitions between sections
3. Ensure consistent tone and voice throughout
4. Fix any awkward phrasing
5. Keep the same structure and content - just polish it

Output the polished article directly. No JSON, no explanations.""",
            expected_output="Polished article in plain text",
            agent=agent,
        )
        
        crew = Crew(agents=[agent], tasks=[task], verbose=False)
        result = self._kickoff_with_trace(
            crew=crew,
            span_name="agentmesh.content_writer.polish_draft",
            input_data={
                "run_id": self.run_id,
                "topic": self.topic,
                "format": str(self.format),
                "has_hook": bool(self.selected_hook),
                "draft_length_chars": len(sections_content),
            },
        )
        return str(result).strip()
    
    def generate_draft(self) -> Dict[str, Any]:
        """
        Generate full draft using selected POV, hook, and outline.
        
        For long-form content with outlines: generates sections in PARALLEL for speed,
        then does a final coherence pass.
        
        Returns:
            {"content": str}
        """
        logger.info(f"Generating draft for run {self.run_id}")
        
        # Check if we can use parallel section generation (need outline with 2+ sections)
        sections = []
        if self.selected_outline:
            sections = self.selected_outline.get('sections', [])
        
        use_parallel = len(sections) >= 2 and self.format in ("blog", "twitter_article")
        
        if use_parallel:
            # PARALLEL GENERATION: Generate each section concurrently, then polish
            logger.info(f"Using parallel generation for {len(sections)} sections")
            
            section_contents = [""] * len(sections)
            
            with ThreadPoolExecutor(max_workers=min(len(sections), 4)) as executor:
                futures = {
                    executor.submit(self._generate_section, section, i, len(sections)): i
                    for i, section in enumerate(sections)
                }
                
                for future in as_completed(futures):
                    idx = futures[future]
                    try:
                        section_contents[idx] = future.result(timeout=60)
                        logger.info(f"Generated section {idx + 1}/{len(sections)}")
                    except Exception as e:
                        logger.error(f"Section {idx + 1} generation failed: {e}")
                        section_contents[idx] = f"## Section {idx + 1}\n\n[Content generation failed]"
            
            # Combine sections
            combined_draft = "\n\n".join(section_contents)
            
            # Final coherence pass with gpt-4o
            logger.info("Running coherence pass...")
            try:
                content = self._polish_draft(combined_draft)
            except Exception as e:
                logger.warning(f"Polish pass failed, using raw sections: {e}")
                content = combined_draft
        else:
            # SINGLE GENERATION: For LinkedIn or short content without outline
            logger.info("Using single-pass generation")
            agent = self._create_writer_agent()
            
            # Build context
            context = f"""
Topic: {self.topic}
Format: {self.format}
"""
            
            if self.selected_pov:
                context += f"""
POV: {self.selected_pov.get('label', '')}
Description: {self.selected_pov.get('description', '')}
Key concepts: {', '.join(self.selected_pov.get('key_concepts', []))}
"""
            
            if self.selected_hook:
                context += f"""
Opening:
Title: {self.selected_hook.get('title', '')}
Lede: {self.selected_hook.get('lede', '')}
"""
            
            if sections:
                context += f"""
Outline:
{json.dumps(sections, indent=2)}
"""
            
            if self.research_pack:
                context += f"""
Research excerpts to incorporate:
{json.dumps(self.research_pack[:5], indent=2)}
"""
            
            if self.constraints:
                context += f"""
Constraints: {json.dumps(self.constraints)}
"""
            
            format_instructions = {
                "linkedin": "Write a LinkedIn post (800-1200 words). Use short paragraphs, include hooks, and end with engagement question.",
                "blog": "Write a blog post (1500-2500 words). Include introduction, sections per outline, and conclusion.",
                "twitter_article": "Write a Twitter/X article (1000-1500 words). Punchy, scannable, with clear takeaways.",
            }
            
            task = Task(
                description=f"""Write a {self.format} article based on the following:

{context}

Instructions: {format_instructions.get(self.format, 'Write engaging content.')}

Write the complete article now. Do not include any JSON wrapping - just output the article text directly.""",
                expected_output="A complete article in plain text",
                agent=agent,
            )
            
            crew = Crew(agents=[agent], tasks=[task], verbose=False)
            
            try:
                result = self._kickoff_with_trace(
                    crew=crew,
                    span_name="agentmesh.content_writer.generate_draft_single_pass",
                    input_data={
                        "run_id": self.run_id,
                        "topic": self.topic,
                        "format": str(self.format),
                        "has_outline": bool(self.selected_outline),
                        "has_hook": bool(self.selected_hook),
                        "has_pov": bool(self.selected_pov),
                    },
                )
                content = str(result)
                
                # Clean up any markdown code blocks
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("markdown") or content.startswith("text"):
                        content = "\n".join(content.split("\n")[1:])
                content = content.strip()
            except Exception as e:
                logger.error(f"Draft generation failed: {e}")
                return {"content": f"# {self.topic}\n\nContent generation failed. Please try again."}
        
        logger.info(f"Generated draft: {len(content.split())} words")
        return {"content": content}
    
    # ==================== Section Refinement ====================
    
    def _create_pov_pointer_agent(self) -> Agent:
        """Create POV pointer generation agent."""
        return Agent(
            role="POV Analyst",
            goal="Generate diverse POV approaches for content refinement",
            backstory="""You are an expert at analyzing content and suggesting 
            alternative perspectives. You understand how different angles can 
            strengthen or transform content.""",
            llm=self.llm,
            verbose=False,
        )
    
    def _create_section_critique_agent(self) -> Agent:
        """Create section critique/rewrite agent."""
        backstory = """You are an expert editor who can surgically rewrite 
        content to address specific issues while maintaining voice and flow."""
        
        if self.user_skills:
            backstory += "\n\nWriting guidelines:\n"
            for skill in self.user_skills:
                if isinstance(skill, dict):
                    backstory += f"- {skill.get('name', '')}: {skill.get('description', '')}\n"
        
        return Agent(
            role="Section Editor",
            goal="Refine content sections while addressing issues and applying selected POV",
            backstory=backstory,
            llm=self.llm,
            verbose=False,
        )
    
    def generate_pov_pointers(
        self,
        section_text: str,
        document_summary: str,
        context_before: str,
        context_after: str,
        issue_types: List[str],
        issue_explanation: Optional[str],
        num_pointers: int = 5,
    ) -> Dict[str, Any]:
        """
        Generate POV pointers for section refinement (Step 1).
        
        Args:
            section_text: Text to refine
            document_summary: Overall document context
            context_before: Paragraphs before section
            context_after: Paragraphs after section
            issue_types: Identified issues
            issue_explanation: Additional context
            num_pointers: Number of POV pointers to generate
            
        Returns:
            {"pov_pointers": [...]}
        """
        logger.info(f"Generating {num_pointers} POV pointers for section refinement")
        
        agent = self._create_pov_pointer_agent()
        
        # Build context
        context = f"""
Document Summary: {document_summary}

Section to refine:
{section_text}

Context before:
{context_before}

Context after:
{context_after}

Issues identified: {', '.join(issue_types) if issue_types else 'None specified'}
{f'Additional context: {issue_explanation}' if issue_explanation else ''}
"""
        
        if self.research_pack:
            context += f"""
Research excerpts available:
{json.dumps(self.research_pack[:5], indent=2)}
"""
        
        task = Task(
            description=f"""Generate {num_pointers} distinct POV approaches for rewriting this section.

{context}

Each POV should:
- Address the identified issues
- Offer a distinct perspective
- Maintain coherence with surrounding content
- Be grounded in available research

Return a JSON object:
{{
    "pov_pointers": [
        {{
            "index": 0,
            "label": "Short label (e.g., 'Data-Driven')",
            "description": "2-3 sentence description of this approach",
            "key_concepts": ["concept1", "concept2", "concept3"],
            "research_refs": [0, 2]
        }}
    ]
}}

Generate exactly {num_pointers} POV pointers.""",
            expected_output="A JSON object with POV pointers",
            agent=agent,
        )
        
        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=False,
        )
        
        try:
            result = self._kickoff_with_trace(
                crew=crew,
                span_name="agentmesh.content_writer.generate_pov_pointers",
                input_data={
                    "run_id": self.run_id,
                    "num_pointers": num_pointers,
                    "issue_types": issue_types,
                    "section_length_chars": len(section_text),
                },
            )
            result_text = str(result)
            
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(result_text)
            
            logger.info(f"Generated {len(data.get('pov_pointers', []))} POV pointers")
            return data
            
        except Exception as e:
            logger.error(f"POV pointer generation failed: {e}")
            return {
                "pov_pointers": [
                    {
                        "index": 0,
                        "label": "Direct Improvement",
                        "description": "Address the identified issues directly while maintaining voice.",
                        "key_concepts": ["clarity", "evidence", "flow"],
                        "research_refs": None,
                    }
                ]
            }
    
    def refine_section_with_pov(
        self,
        section_text: str,
        document_summary: str,
        context_before: str,
        context_after: str,
        issue_types: List[str],
        issue_explanation: Optional[str],
        pov_selection: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Refine section with selected POV (Step 2).
        
        Args:
            section_text: Text to refine
            document_summary: Overall document context
            context_before: Paragraphs before section
            context_after: Paragraphs after section
            issue_types: Identified issues
            issue_explanation: Additional context
            pov_selection: Selected POV approach
            
        Returns:
            {"refined_text": str, "changes_summary": str, "pov_applied": str}
        """
        logger.info(f"Refining section with POV")
        
        agent = self._create_section_critique_agent()
        
        # Determine POV instruction
        pov_instruction = pov_selection.get("custom_pov", "")
        if not pov_instruction and pov_selection.get("selected_index") is not None:
            pov_instruction = f"Apply POV pointer #{pov_selection['selected_index']}"
        
        preserve_facts = pov_selection.get("preserve_facts", True)
        maintain_flow = pov_selection.get("maintain_flow", True)
        
        # Build context
        context = f"""
Document Summary: {document_summary}

Section to refine:
{section_text}

Context before:
{context_before}

Context after:
{context_after}

Issues to address: {', '.join(issue_types) if issue_types else 'None specified'}
{f'Additional context: {issue_explanation}' if issue_explanation else ''}

POV instruction: {pov_instruction}
Preserve factual claims: {preserve_facts}
Maintain transitions: {maintain_flow}
"""
        
        if self.research_pack:
            context += f"""
Research excerpts to support claims:
{json.dumps(self.research_pack[:5], indent=2)}
"""
        
        task = Task(
            description=f"""Rewrite the section following these guidelines:

{context}

Requirements:
1. Address all identified issues
2. Apply the specified POV transformation
3. Maintain coherence with surrounding paragraphs
4. Use research to support claims if available
5. Keep the same approximate length

Return a JSON object:
{{
    "refined_text": "The rewritten section text",
    "changes_summary": "Brief explanation of what changed and why",
    "pov_applied": "Description of POV transformation applied",
    "research_pack_refs": [0, 2]
}}""",
            expected_output="A JSON object with refined text and metadata",
            agent=agent,
        )
        
        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=False,
        )
        
        try:
            result = self._kickoff_with_trace(
                crew=crew,
                span_name="agentmesh.content_writer.refine_section_with_pov",
                input_data={
                    "run_id": self.run_id,
                    "issue_types": issue_types,
                    "section_length_chars": len(section_text),
                    "pov_label": pov_selection.get("label"),
                },
            )
            result_text = str(result)
            
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(result_text)
            
            logger.info(f"Section refined: {len(data.get('refined_text', '').split())} words")
            return data
            
        except Exception as e:
            logger.error(f"Section refinement failed: {e}")
            return {
                "refined_text": section_text,
                "changes_summary": f"Refinement failed: {str(e)}",
                "pov_applied": "None - error occurred",
                "research_pack_refs": None,
            }
