"""
SOW Generation Service

Main service for extracting SOW fields from meeting transcripts
and generating professional SOW documents.
"""
from __future__ import annotations

import json
import logging
import re
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import openai
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.services.provider_service import ProviderService

from .template_parser import TemplateParser, TemplateField
from .transcript_parser import TranscriptParser, Meeting
from .mermaid_renderer import MermaidRenderer

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ExtractedAnswer:
    """An extracted answer for a SOW field."""
    tag: str
    value: Optional[Any] = None
    value_rendered: Optional[str] = None
    citations: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: Optional[str] = None
    followup_question: Optional[str] = None
    needs_review: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag": self.tag,
            "value": self.value,
            "value_rendered": self.value_rendered,
            "citations": self.citations,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "followup_question": self.followup_question,
            "needs_review": self.needs_review,
        }


class SowService:
    """Service for SOW extraction and generation."""
    
    # Field guidance for extraction (matching original sow-eliza)
    FIELD_GUIDANCE = {
        # Identity fields
        "CLIENT_NAME": "\n  GUIDANCE: Extract FULL company name (e.g., 'Acme Corporation' not just 'Acme').",
        "CLIENT_SIGNATORY": "\n  GUIDANCE: Extract full name of main client contact (first + last name).",
        "VENDOR_SIGNATORY": "\n  GUIDANCE: Extract full name of main vendor contact (first + last name).",
        
        # Team fields - distinguish project team from company size
        "VENDOR_TEAM_COUNT": "\n  GUIDANCE: Extract PROJECT team size (e.g., '0.25 FDE', '1-2 people', '10-20 hours/week'). NOT company headcount.",
        "CLIENT_TEAM_COUNT": "\n  GUIDANCE: Extract client-side PROJECT team size. NOT total company employees.",
        "TEAM_COMPOSITION": "\n  GUIDANCE: List team members with: Name, Title, and relevant background/experience.",
        
        # Pricing fields
        "PRICING_MODEL": "\n  GUIDANCE: Extract ALL pricing options mentioned (e.g., 'hourly OR project-based OR retainer').",
        "TOTAL_COST": "\n  GUIDANCE: Include range, qualifiers, and scope (e.g., '$50K-$100K for full implementation').",
        "PRICING_DETAILS": "\n  GUIDANCE: Capture all details: price ranges, typical durations, what's included, maintenance costs, factors affecting price.",
        
        # Timeline fields
        "DURATION": "\n  GUIDANCE: Project duration (e.g., '3-6 months', '8 weeks'). NOT meeting duration.",
        "START_DATE": "\n  GUIDANCE: When PROJECT starts. Meeting date ≠ project start date. Return null if not explicitly stated.",
        "END_DATE": "\n  GUIDANCE: When PROJECT ends. Return null if not explicitly stated.",
        "SOW_EFFECTIVE_DATE": "\n  GUIDANCE: When the SOW agreement becomes effective. Return null if not discussed.",
        "PHASE_BREAKDOWN": "\n  GUIDANCE: Extract project phases with descriptions (e.g., 'Phase 1: Discovery', 'Phase 2: Implementation').",
        
        # Scope fields
        "TECHNICAL_PLAN": "\n  GUIDANCE: Technical approach, tools, methodologies, and implementation steps.",
        
        "PROJECT_PLAN": """\n  GUIDANCE: Generate a comprehensive project plan combining technical approach and phases.
  Format as structured phases with HEADING and DESCRIPTION for each:
  
  Extract from the call:
  1. Overall technical approach (tools, methodologies, AI technologies)
  2. Project phases with details (Discovery, Design, Implementation, etc.)
  3. Key activities and deliverables for each phase
  4. Timeline/duration for each phase if mentioned
  
  Return as a JSON object with this structure:
  {
    "technical_approach": "Brief overview of technical methodology and tools",
    "phases": [
      {
        "name": "Discovery & Analysis",
        "description": "Detailed description of what happens in this phase",
        "duration": "2-3 weeks",
        "deliverables": ["Deliverable 1", "Deliverable 2"]
      },
      ...
    ],
    "summary": "Brief summary of the overall project approach and expected outcomes"
  }
  
  IMPORTANT: Do NOT include "Phase 1:", "Phase 2:" etc. in the phase names.
  Just use the descriptive name like "Discovery & Analysis", "Solution Design", etc.
  
  DO NOT include pricing/cost information in this field.""",
        "OUT_OF_SCOPE": "\n  GUIDANCE: Items explicitly excluded. Look for 'not included', 'out of scope', 'not a fit'.",
        "DELIVERABLES": "\n  GUIDANCE: Concrete outputs to be delivered: documents, software, training, reports, etc.",
        "SUCCESS_CRITERIA": """\n  GUIDANCE: Extract SPECIFIC, MEASURABLE success criteria. Each criterion MUST have:
  - A clear condition (what must happen)
  - A measurable outcome (how we verify it succeeded)
  - A timeline if mentioned (when it should happen)
  
  Examples of GOOD success criteria:
  - "Portfolio company accepts recommendations and begins implementation within 30 days"
  - "Deliver initial analysis within 2-3 weeks of project kickoff"
  - "Achieve 20% reduction in manual processing time within 6 months"
  
  Examples of BAD (too vague) criteria:
  - "Project completed successfully" (not measurable)
  - "Client is satisfied" (subjective)
  - "Good ROI" (not specific)
  
  If criteria are vague in transcript, infer measurable versions.""",
        "RISKS": "\n  GUIDANCE: Concerns from EITHER party: technical risks, business risks, adoption challenges, dependencies.",
        "ASSUMPTIONS": "\n  GUIDANCE: Conditions assumed to be true: budget availability, stakeholder cooperation, system access, timing.",
        
        # Outcome fields
        "EXECUTIVE_SUMMARY": "\n  GUIDANCE: High-level overview: client context, problem statement, proposed solution.",
        "BUSINESS_OUTCOMES": "\n  GUIDANCE: What the client wants to achieve: business goals, expected improvements, strategic objectives.",
        "NEXT_STEPS": "\n  GUIDANCE: Specific action items with owners (who does what) and optional timing.",
        
        # Table fields - structured data extraction
        "TOTAL_HOURS": "\n  GUIDANCE: Extract total project hours and delivery duration (e.g., '200 hours over 8 weeks'). Include both the number of hours AND the timeframe.",
        "PRICING_TABLE": """\n  GUIDANCE: Extract pricing/team structure as a structured list. For each role include:
  - Role name (e.g., Forward Deployed Engineer, AI Engineer, Project Manager)
  - Hourly rate (e.g., $200)
  - Estimated hours
  - Estimated total cost for that role
  Return as a list of objects: [{"Roles": "...", "Hourly Rate": "$XXX", "Estimated Hours": "XX", "Estimated Cost": "$X,XXX"}, ...]""",
        
        "ARCHITECTURE_DIAGRAM": """\n  GUIDANCE: Generate a Mermaid flowchart diagram showing the technical architecture discussed.
  Extract components, systems, data flows, and integrations mentioned in the call.
  Return a valid Mermaid diagram string using flowchart TD (top-down) syntax.
  Include:
  - Main systems/components (e.g., AI Agent, Database, API, Client App)
  - Data flows and integrations
  - External services mentioned
  - Key process steps
  Example format:
  flowchart TD
    A[Client System] --> B[AI Agent]
    B --> C[Database]
    B --> D[External API]""",
    }
    
    def __init__(self, db: Optional[Session] = None, customer_id: Optional[str] = None):
        self.db = db
        self.customer_id = customer_id
        self.template_parser = TemplateParser()
        self.transcript_parser = TranscriptParser()
        self.mermaid_renderer = MermaidRenderer()
        
        # Initialize OpenAI client
        self.openai_client = None
        self.openai_model = settings.default_llm_model or "gpt-4.1"
        self._init_openai()
    
    def _init_openai(self):
        """Initialize OpenAI client."""
        api_key = settings.openai_api_key
        if api_key:
            self.openai_client = openai.OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized for SOW service")
        else:
            logger.warning("No OpenAI API key configured - SOW extraction will be limited")
    
    def extract_from_transcript(
        self,
        transcript_content: str,
        transcript_filename: str,
        template_path: Path,
    ) -> Tuple[str, List[TemplateField], Dict[str, ExtractedAnswer]]:
        """
        Extract SOW fields from a transcript.
        
        Args:
            transcript_content: Raw transcript content (JSON or text)
            transcript_filename: Original filename (for format detection)
            template_path: Path to the SOW template
            
        Returns:
            (session_id, fields, answers) tuple
        """
        # Parse transcript
        meetings = self.transcript_parser.parse_content(transcript_content, transcript_filename)
        if not meetings:
            raise ValueError("No meetings found in transcript")
        
        logger.info(f"Parsed {len(meetings)} meetings from transcript")
        
        # Get meeting context
        meeting_context = TranscriptParser.extract_meeting_context(meetings)
        utterances = TranscriptParser.combine_utterances(meetings)
        
        logger.info(f"Combined: {len(meetings)} meetings, {len(utterances)} utterances")
        
        # Parse template
        doc, fields = self.template_parser.parse_template(template_path)
        logger.info(f"Found {len(fields)} fields in template")
        
        # Extract answers using LLM
        answers = self._extract_all_fields(fields, utterances, meeting_context)
        
        # Always generate architecture diagram (regardless of template)
        logger.info("Generating architecture diagram...")
        mermaid_code = self._generate_architecture_diagram(utterances, meeting_context)
        if mermaid_code:
            answers["ARCHITECTURE_DIAGRAM"] = ExtractedAnswer(
                tag="ARCHITECTURE_DIAGRAM",
                value=mermaid_code,
                value_rendered=mermaid_code,
                confidence=0.8,
                reasoning="Generated from technical discussion in meeting",
            )
            logger.info(f"Architecture diagram generated: {len(mermaid_code)} chars")
            
            # Add diagram field to template if it doesn't exist
            diagram_field = next((f for f in fields if f.tag == "ARCHITECTURE_DIAGRAM"), None)
            if not diagram_field:
                # Create synthetic field for the diagram
                from .template_parser import TemplateField
                diagram_field = TemplateField(
                    tag="ARCHITECTURE_DIAGRAM",
                    instruction="Architecture diagram",
                    sample_answer="",
                    instruction_para_idx=0,  # Will be inserted at start
                    sample_para_indices=[],
                    is_diagram=True,
                )
                fields.insert(0, diagram_field)
                logger.info("Added synthetic ARCHITECTURE_DIAGRAM field to template")
        else:
            logger.warning("Failed to generate architecture diagram")
        
        session_id = str(uuid.uuid4())
        logger.info(f"Extraction complete. Session: {session_id[:8]}...")
        
        return session_id, fields, answers
    
    def _extract_all_fields(
        self,
        fields: List[TemplateField],
        utterances: List[Dict[str, Any]],
        meeting_context: Dict[str, Any],
    ) -> Dict[str, ExtractedAnswer]:
        """Extract answers for all fields from the transcript."""
        if not self.openai_client:
            logger.warning("No OpenAI client - returning empty answers")
            return {}
        
        # Format transcript
        transcript_text = self._format_transcript(utterances)
        context_info = self._format_context(meeting_context)
        
        # Group fields for batch extraction
        field_groups = self._group_fields(fields)
        
        all_answers: Dict[str, ExtractedAnswer] = {}
        
        for group_name, group_fields in field_groups.items():
            logger.info(f"Extracting {group_name} fields ({len(group_fields)} fields)")
            answers = self._extract_field_group(
                group_name, group_fields, utterances, transcript_text, context_info
            )
            all_answers.update(answers)
        
        return all_answers
    
    def _group_fields(self, fields: List[TemplateField]) -> Dict[str, List[TemplateField]]:
        """Group fields by category for better extraction."""
        groups = {
            "scope": [],
            "overview": [],
            "timeline": [],
            "tables": [],
            "project_plan": [],
        }
        
        for f in fields:
            tag = f.tag.upper()
            if tag == "PROJECT_PLAN":
                groups["project_plan"].append(f)
            elif tag == "PRICING_TABLE":
                groups["tables"].append(f)
            elif any(x in tag for x in ["TOTAL_HOURS", "DURATION", "TIMELINE"]):
                groups["timeline"].append(f)
            elif any(x in tag for x in ["SCOPE", "SUCCESS", "ASSUMPTION", "RISK"]):
                groups["scope"].append(f)
            elif tag not in ["HIGHLIGHTED_GREEN_TEXTS", "ARCHITECTURE_DIAGRAM"]:
                groups["overview"].append(f)
        
        return {k: v for k, v in groups.items() if v}
    
    def _extract_field_group(
        self,
        group_name: str,
        fields: List[TemplateField],
        utterances: List[Dict[str, Any]],
        transcript_text: str,
        context_info: str,
    ) -> Dict[str, ExtractedAnswer]:
        """Extract a group of related fields."""
        if not fields:
            return {}
        
        # Build prompt for this group
        field_prompts = []
        for f in fields:
            guidance = self.FIELD_GUIDANCE.get(f.tag, "")
            field_prompts.append(f'"{f.tag}": "QUESTION: {f.question}{guidance}"')
        
        prompt = f"""Extract information from this meeting transcript.

{context_info}

TRANSCRIPT:
{transcript_text[:50000]}

FIELDS TO EXTRACT:
{chr(10).join(field_prompts)}

For each field, provide:
- answer: The extracted answer (be specific and detailed)
- confidence: 0.0-1.0 confidence score
- reasoning: Brief explanation of how you found this

Return as JSON:
{{
    "FIELD_TAG": {{
        "answer": "extracted answer",
        "confidence": 0.85,
        "reasoning": "found in discussion about..."
    }},
    ...
}}
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {"role": "system", "content": "You are an expert at extracting SOW information from meeting transcripts. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4000,
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            data = json.loads(content)
            
            results = {}
            for f in fields:
                field_data = data.get(f.tag, {})
                raw_answer = field_data.get("answer")
                # Render value using proper formatting
                rendered = self._render_value(raw_answer, f.tag)
                
                results[f.tag] = ExtractedAnswer(
                    tag=f.tag,
                    value=raw_answer,
                    value_rendered=rendered,
                    confidence=float(field_data.get("confidence", 0.5)),
                    reasoning=field_data.get("reasoning"),
                    needs_review=float(field_data.get("confidence", 0.5)) < 0.7,
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Field extraction failed for {group_name}: {e}")
            return {f.tag: ExtractedAnswer(tag=f.tag, confidence=0.0) for f in fields}
    
    def _generate_architecture_diagram(
        self,
        utterances: List[Dict[str, Any]],
        meeting_context: Dict[str, Any],
        max_retries: int = 3,
    ) -> Optional[str]:
        """Generate a mermaid architecture diagram from the transcript."""
        if not self.openai_client:
            return None
        
        transcript_text = self._format_transcript(utterances, max_chars=40000)
        
        prompts = [
            self._get_diagram_prompt(transcript_text, max_nodes=10),
            self._get_diagram_prompt(transcript_text, max_nodes=8),
            self._get_diagram_prompt(transcript_text, max_nodes=6, ultra_simple=True),
        ]
        
        for attempt, prompt in enumerate(prompts[:max_retries], 1):
            logger.info(f"Diagram generation attempt {attempt}/{max_retries}")
            
            try:
                response = self.openai_client.chat.completions.create(
                    model=self.openai_model,
                    messages=[
                        {"role": "system", "content": "You are a technical architect creating Mermaid diagrams. Output ONLY valid Mermaid syntax."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2 + (attempt * 0.1),
                    max_tokens=1500,
                )
                
                content = response.choices[0].message.content.strip()
                
                # Clean up response
                if "```mermaid" in content:
                    content = content.split("```mermaid")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                if not content.startswith("flowchart"):
                    continue
                
                # Sanitize
                content = self._sanitize_mermaid(content)
                
                # Validate by test rendering
                if self.mermaid_renderer.validate_mermaid(content):
                    logger.info(f"Attempt {attempt}: Successfully generated diagram ({len(content)} chars)")
                    return content
                else:
                    logger.warning(f"Attempt {attempt}: Diagram failed validation")
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt}: Generation error: {e}")
        
        logger.error(f"All {max_retries} diagram attempts failed")
        return None
    
    def _get_diagram_prompt(self, transcript: str, max_nodes: int = 10, ultra_simple: bool = False) -> str:
        """Generate prompt for mermaid diagram creation."""
        if ultra_simple:
            return f"""Create a VERY SIMPLE Mermaid flowchart for the technical architecture discussed.

TRANSCRIPT (summary):
{transcript[:15000]}

CRITICAL RULES:
- Start with: flowchart TD
- Maximum {max_nodes} nodes total
- Maximum 3 subgraphs
- ONE WORD subgraph names only (e.g., subgraph Sources)
- Simple labels only: A[Simple Label]
- NO quotes, NO parentheses, NO special characters
- Simple arrows: A --> B

Output ONLY mermaid code:

flowchart TD
    subgraph Input
        A[Data Sources]
    end
    subgraph Process
        B[Processing]
        C[AI Engine]
    end
    subgraph Output
        D[Results]
    end
    A --> B
    B --> C
    C --> D
"""
        
        return f"""Analyze this meeting transcript and generate a SIMPLE Mermaid flowchart showing the proposed technical architecture.

TRANSCRIPT:
{transcript}

Generate a simple architecture diagram. Follow these rules EXACTLY:

SYNTAX RULES - MUST FOLLOW:
1. Start with: flowchart TD
2. Subgraph names must be ONE WORD only: subgraph Sources NOT subgraph "Data Sources"
3. Node labels use square brackets with simple text: A[Customer Data]
4. NO quotes anywhere in the diagram
5. NO parentheses in labels
6. NO special characters like / or &
7. Simple arrows only: A --> B
8. Maximum {max_nodes} nodes total
9. Maximum 3 subgraphs

Focus on:
- Main data sources (customer systems, databases)
- Processing/AI components
- Output/results

Output ONLY the mermaid code. No explanations.

CORRECT EXAMPLE:
flowchart TD
    subgraph Sources
        A[Customer Files]
        B[Salesforce Data]
    end
    subgraph Processing
        C[Data Ingestion]
        D[AI Matching]
    end
    subgraph Outputs
        E[Clean Data]
        F[Dashboard]
    end
    A --> C
    B --> C
    C --> D
    D --> E
    D --> F
"""
    
    def _sanitize_mermaid(self, content: str) -> str:
        """Sanitize mermaid code for rendering."""
        lines = content.split('\n')
        sanitized = []
        
        for line in lines:
            if line.strip().startswith('%%'):
                continue
            
            # Fix subgraph names with quotes
            line = re.sub(r'subgraph\s+(\w+)\s*\[.*?\]', r'subgraph \1', line)
            
            # Remove quotes from labels
            line = re.sub(r'\["([^"]+)"\]', r'[\1]', line)
            
            # Clean label content
            if '[' in line and ']' in line:
                match = re.search(r'\[([^\]]+)\]', line)
                if match:
                    label = match.group(1)
                    clean = label.replace('/', ' ').replace('&', 'and').replace('(', '').replace(')', '')
                    line = line.replace(f'[{label}]', f'[{clean}]')
            
            # Remove arrow labels
            line = re.sub(r'-->\s*\|[^|]*\|\s*', '--> ', line)
            
            sanitized.append(line)
        
        return '\n'.join(sanitized)
    
    def _format_transcript(self, utterances: List[Dict[str, Any]], max_chars: int = 60000) -> str:
        """Format utterances into a readable transcript."""
        lines = []
        total_chars = 0
        
        for u in utterances:
            line = f"[{u.get('speaker', 'Unknown')}]: {u.get('text', '')}"
            if total_chars + len(line) > max_chars:
                break
            lines.append(line)
            total_chars += len(line)
        
        return "\n".join(lines)
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format meeting context for prompts."""
        parts = [f"Meeting: {context.get('title', 'Unknown')}"]
        if context.get('participants'):
            parts.append(f"Participants: {', '.join(context['participants'][:10])}")
        if context.get('client_domains'):
            parts.append(f"Client: {', '.join(context['client_domains'])}")
        return "\n".join(parts)
    
    def _render_value(self, value: Any, tag: str) -> Optional[str]:
        """Render a value as a string for display.
        
        IMPORTANT: This function outputs CLEAN TEXT without bullet prefixes.
        Bullet formatting is added ONLY in the document generation step.
        """
        if value is None:
            return None
        
        # Special handling for PROJECT_PLAN - format as heading + text
        if tag == "PROJECT_PLAN":
            return self._render_project_plan(value)
        
        if isinstance(value, list):
            # Check if this is table data (list of dicts)
            if value and isinstance(value[0], dict):
                # Format table data in a readable way
                lines = []
                for row in value:
                    parts = []
                    for k, v in row.items():
                        if v is not None and str(v).strip() and str(v) != "None":
                            parts.append(f"{k}: {v}")
                    if parts:
                        lines.append(" | ".join(parts))
                return "\n".join(lines) if lines else None
            
            # Regular list - clean up items (NO bullet prefix added here)
            items = []
            for item in value:
                clean_item = self._clean_list_item(str(item))
                if clean_item:
                    items.append(clean_item)
            # Return newline-separated CLEAN text (no bullets)
            return "\n".join(items)
        
        if isinstance(value, dict):
            # For non-PROJECT_PLAN dicts, format as key: value lines
            lines = []
            for k, v in value.items():
                if v is not None and str(v).strip():
                    lines.append(f"{k}: {v}")
            return "\n".join(lines) if lines else None
        
        # For strings, clean up any existing bullet/numbering
        return self._clean_list_item(str(value))
    
    def _render_project_plan(self, value: Any) -> Optional[str]:
        """Render PROJECT_PLAN in heading + text format.
        
        Output format:
        HEADING:Technical Approach
        Brief technical overview...
        
        HEADING:Discovery & Analysis
        Description of phase...
        Duration: X weeks
        Deliverables: item1, item2
        
        Uses HEADING: prefix to mark bold text (converted in document generation).
        """
        if value is None:
            return None
        
        # Parse if it's a string (JSON)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                # Not JSON, return as-is but cleaned
                return self._clean_list_item(value)
        
        if not isinstance(value, dict):
            return str(value)
        
        lines = []
        
        # Technical Approach section
        tech_approach = value.get("technical_approach", "")
        if tech_approach:
            lines.append("HEADING:Technical Approach")
            lines.append(tech_approach)
            lines.append("")
        
        # Phases section
        phases = value.get("phases", [])
        for phase in phases:
            if isinstance(phase, dict):
                name = phase.get("name", "")
                description = phase.get("description", "")
                duration = phase.get("duration", "")
                deliverables = phase.get("deliverables", [])
                
                # Clean up the phase name - remove "Phase X:" prefix
                clean_name = re.sub(r'^Phase\s*\d*[:\s]*', '', name, flags=re.IGNORECASE).strip()
                if not clean_name:
                    clean_name = name  # Fallback to original if nothing left
                
                # Phase heading (marked for bold conversion)
                lines.append(f"HEADING:{clean_name}")
                
                # Description - this is the main content
                if description:
                    lines.append(description)
                
                # Duration on its own line, formatted nicely
                if duration:
                    lines.append(f"Duration: {duration}")
                
                # Deliverables as a list
                if deliverables:
                    if isinstance(deliverables, list) and deliverables:
                        lines.append(f"Deliverables: {', '.join(str(d) for d in deliverables)}")
                    elif deliverables:
                        lines.append(f"Deliverables: {deliverables}")
                
                lines.append("")  # Blank line between phases
        
        # Summary section
        summary = value.get("summary", "")
        if summary:
            lines.append("HEADING:Summary")
            lines.append(summary)
        
        return "\n".join(lines)
    
    def _clean_list_item(self, text: str) -> str:
        """Remove ALL leading numbers/bullets/arrows from a list item."""
        if not text:
            return text
        
        text = text.strip()
        
        # Keep stripping until no more changes (max 10 iterations)
        for _ in range(10):
            prev = text
            # Remove numbered patterns: "1)", "1.", "(1)", "1:", "1-", etc.
            text = re.sub(r'^[\(\[]?\d+[\)\].:\-]\s*', '', text)
            # Remove lettered patterns: "a)", "a.", "(a)", "a:", "A.", etc.
            text = re.sub(r'^[\(\[]?[a-zA-Z][\)\].:\-]\s*', '', text)
            # Remove bullet/arrow markers
            text = re.sub(r'^[•→➔➜➝➞➡➢➣➤\-▪○►◦>»›·∙⁃‣⁌⁍]+\s*', '', text)
            text = text.strip()
            if prev == text:
                break
        
        return text
    
    def generate_document(
        self,
        template_path: Path,
        answers: Dict[str, ExtractedAnswer],
        output_path: Path,
    ) -> Path:
        """Generate a SOW document from extracted answers."""
        return self.template_parser.generate_document(template_path, answers, output_path)
