"""
Docling Resume Parser

Uses Docling document conversion toolkit to parse resumes/CVs.
Extracts structured data: skills, experience, education, contact info.

Two extraction modes:
1. **OpenAI (default)**: Docling converts PDF → Markdown, then GPT-4o-mini
   extracts structured data via structured output. Highly accurate.
2. **Local**: Docling converts PDF → Markdown, then regex heuristics extract
   data. Fast and free but brittle on non-standard layouts.

Docling: https://github.com/docling-project/docling
- Layout fidelity for multi-column resumes
- Export to Markdown/JSON
- Handles tables (skills matrices)
- Headers/footers extraction
"""
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from pathlib import Path
import io
import json
import re
from pydantic import BaseModel

import structlog

logger = structlog.get_logger(__name__)


class ParsedEducation(BaseModel):
    """Parsed education entry"""
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    school: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ParsedExperience(BaseModel):
    """Parsed work experience entry"""
    title: Optional[str] = None
    company: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    description: Optional[str] = None
    location: Optional[str] = None


class ParsedResume(BaseModel):
    """
    Structured resume data extracted by Docling.
    
    Normalized to be compatible with PDL person format
    for consistent matching algorithms.
    """
    # Contact information
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    location: Optional[str] = None
    
    # Professional summary
    summary: Optional[str] = None
    headline: Optional[str] = None  # Current title
    
    # Skills
    skills: List[str] = []
    
    # Work experience
    experience: List[ParsedExperience] = []
    
    # Education
    education: List[ParsedEducation] = []
    
    # Additional fields
    certifications: List[str] = []
    languages: List[str] = []
    
    # Source tracking
    greenhouse_id: Optional[int] = None  # Greenhouse candidate ID for applicants
    candidate_id: Optional[str] = None  # Internal candidate identifier
    
    # Metadata
    parsed_at: datetime = datetime.now()
    raw_text: Optional[str] = None  # Full resume text
    docling_output: Optional[Dict[str, Any]] = None  # Raw Docling output


class DoclingParser:
    """
    Resume parser using Docling document conversion toolkit.
    
    Handles PDF, DOCX, TXT formats.
    Extracts structured data and normalizes to PDL-like format.
    
    Extraction modes (controlled by RESUME_EXTRACTION_MODE env var):
    - "openai": Docling PDF→Markdown, then GPT-4o-mini structured output (default)
    - "local":  Docling PDF→Markdown, then regex heuristics (free, fast, brittle)
    """
    
    # System prompt for OpenAI structured extraction
    _EXTRACTION_SYSTEM_PROMPT = """You are a resume parsing assistant. Given the markdown text of a resume, extract structured data accurately.

Rules:
- Extract the candidate's REAL name. Section headers like "Top Skills", "Experience", "Summary" are NOT names.
- For location, extract the candidate's city/state/country if mentioned anywhere in the resume.
- For skills, include ALL skills mentioned throughout the resume, not just those under a "Skills" header.
- For experience, extract each job with title, company, dates, location, and whether it is the current role.
- For education, extract degree, field of study, school name, and dates.
- For certifications, extract all professional certifications and licenses.
- For languages, extract spoken/written languages if mentioned.
- Dates should be in "YYYY" or "YYYY-MM" format when possible.
- If a field is not present in the resume, leave it null/empty.
- Be precise. Do not hallucinate information that is not in the resume text."""

    def __init__(self):
        """Initialize Docling parser."""
        self.logger = logger.bind(service="docling_parser")
        
        # Lazy import of Docling (only when needed)
        self._docling_converter = None
        self._openai_client = None
    
    def _get_converter(self):
        """
        Lazy initialization of Docling converter.
        
        Import Docling only when first needed to avoid
        startup overhead if not used.
        """
        if self._docling_converter is None:
            try:
                from docling.document_converter import DocumentConverter
                self._docling_converter = DocumentConverter()
                self.logger.info("Docling converter initialized")
            except ImportError as e:
                self.logger.error("Failed to import Docling", error=str(e))
                raise ImportError(
                    "Docling is not installed. "
                    "Install with: pip install docling docling-core"
                )
        
        return self._docling_converter
    
    def _get_openai_client(self):
        """Lazy initialization of OpenAI client."""
        if self._openai_client is None:
            from openai import OpenAI
            from src.core.config import get_settings
            settings = get_settings()
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required for OpenAI resume extraction mode")
            self._openai_client = OpenAI(api_key=settings.openai_api_key)
            self.logger.info("OpenAI client initialized for resume extraction")
        return self._openai_client
    
    def parse_resume(
        self,
        file_bytes: bytes,
        filename: str
    ) -> ParsedResume:
        """
        Parse resume from bytes using Docling.
        
        Args:
            file_bytes: Resume file content
            filename: Original filename (for format detection)
            
        Returns:
            ParsedResume with structured data
        """
        try:
            self.logger.info("Parsing resume", filename=filename)
            
            # Determine file format
            file_ext = Path(filename).suffix.lower()
            
            # Convert document using Docling
            converter = self._get_converter()
            
            # Create a file-like object from bytes
            file_obj = io.BytesIO(file_bytes)
            
            # Convert document to structured format
            result = converter.convert(file_obj)
            
            # Extract text content
            raw_text = result.document.export_to_markdown()
            
            # Extract structured data (OpenAI or local, with fallback)
            parsed_data = self._extract_structured_data(raw_text, result)
            
            # Create ParsedResume
            parsed_resume = ParsedResume(
                **parsed_data,
                raw_text=raw_text,
                docling_output=result.document.export_to_dict() if hasattr(result, 'document') else None
            )
            
            self.logger.info(
                "Resume parsed successfully",
                filename=filename,
                skills_count=len(parsed_resume.skills),
                experience_count=len(parsed_resume.experience),
                education_count=len(parsed_resume.education)
            )
            
            return parsed_resume
            
        except Exception as e:
            self.logger.error("Failed to parse resume", filename=filename, error=str(e))
            
            # Return basic ParsedResume with error info
            return ParsedResume(
                raw_text=f"Error parsing resume: {str(e)}",
                docling_output={"error": str(e)}
            )
    
    def _extract_structured_data(
        self,
        markdown_text: str,
        docling_result: Any
    ) -> Dict[str, Any]:
        """
        Extract structured data from Docling markdown output.
        
        Checks RESUME_EXTRACTION_MODE setting:
        - "openai": Uses GPT model with structured output (accurate)
        - "local":  Uses regex heuristics (fast, free, fallback)
        
        If OpenAI extraction fails, automatically falls back to local.
        """
        from src.core.config import get_settings
        settings = get_settings()
        mode = settings.resume_extraction_mode.lower()
        
        if mode == "openai":
            try:
                data = self._extract_with_openai(markdown_text)
                if data:
                    return data
                self.logger.warning("OpenAI extraction returned empty, falling back to local")
            except Exception as e:
                self.logger.warning(
                    "OpenAI extraction failed, falling back to local heuristics",
                    error=str(e),
                    error_type=type(e).__name__
                )
        
        # Local regex fallback
        return self._extract_with_local_heuristics(markdown_text)
    
    def _extract_with_openai(self, markdown_text: str) -> Optional[Dict[str, Any]]:
        """
        Extract structured resume data using OpenAI structured output.
        
        Sends the Docling markdown to GPT-4o-mini and gets back a JSON
        object matching our ParsedResume schema. Far more accurate than
        regex for name, location, skills, and experience extraction.
        """
        from src.core.config import get_settings
        settings = get_settings()
        model = settings.resume_extraction_model
        
        client = self._get_openai_client()
        
        # Truncate very long resumes to stay within token limits
        max_chars = 15000  # ~4k tokens, well within limits
        text_to_send = markdown_text[:max_chars]
        if len(markdown_text) > max_chars:
            self.logger.info("Truncating resume text for OpenAI extraction",
                           original_length=len(markdown_text),
                           truncated_to=max_chars)
        
        self.logger.info("Extracting resume data with OpenAI",
                        model=model,
                        text_length=len(text_to_send))
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": self._EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract structured data from this resume:\n\n{text_to_send}"}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "parsed_resume",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "full_name": {"type": ["string", "null"], "description": "Candidate's full name"},
                            "first_name": {"type": ["string", "null"], "description": "First/given name"},
                            "last_name": {"type": ["string", "null"], "description": "Last/family name"},
                            "email": {"type": ["string", "null"], "description": "Email address"},
                            "phone": {"type": ["string", "null"], "description": "Phone number"},
                            "linkedin_url": {"type": ["string", "null"], "description": "LinkedIn profile URL"},
                            "github_url": {"type": ["string", "null"], "description": "GitHub profile URL"},
                            "location": {"type": ["string", "null"], "description": "City, State/Region, Country"},
                            "summary": {"type": ["string", "null"], "description": "Professional summary or objective"},
                            "headline": {"type": ["string", "null"], "description": "Current job title or professional headline"},
                            "skills": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "All skills mentioned in the resume"
                            },
                            "experience": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": ["string", "null"]},
                                        "company": {"type": ["string", "null"]},
                                        "start_date": {"type": ["string", "null"], "description": "YYYY or YYYY-MM"},
                                        "end_date": {"type": ["string", "null"], "description": "YYYY or YYYY-MM, null if current"},
                                        "is_current": {"type": "boolean"},
                                        "description": {"type": ["string", "null"]},
                                        "location": {"type": ["string", "null"]}
                                    },
                                    "required": ["title", "company", "start_date", "end_date", "is_current", "description", "location"],
                                    "additionalProperties": False
                                }
                            },
                            "education": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "degree": {"type": ["string", "null"]},
                                        "field_of_study": {"type": ["string", "null"]},
                                        "school": {"type": ["string", "null"]},
                                        "start_date": {"type": ["string", "null"]},
                                        "end_date": {"type": ["string", "null"]}
                                    },
                                    "required": ["degree", "field_of_study", "school", "start_date", "end_date"],
                                    "additionalProperties": False
                                }
                            },
                            "certifications": {
                                "type": "array",
                                "items": {"type": "string"}
                            },
                            "languages": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": [
                            "full_name", "first_name", "last_name", "email", "phone",
                            "linkedin_url", "github_url", "location", "summary", "headline",
                            "skills", "experience", "education", "certifications", "languages"
                        ],
                        "additionalProperties": False
                    }
                }
            },
            temperature=0.0,  # Deterministic extraction
        )
        
        result_text = response.choices[0].message.content
        if not result_text:
            return None
        
        data = json.loads(result_text)
        
        # Log token usage
        usage = response.usage
        if usage:
            self.logger.info("OpenAI resume extraction complete",
                           model=model,
                           prompt_tokens=usage.prompt_tokens,
                           completion_tokens=usage.completion_tokens,
                           total_tokens=usage.total_tokens,
                           extracted_name=data.get("full_name"))
        
        return data
    
    def _extract_with_local_heuristics(self, markdown_text: str) -> Dict[str, Any]:
        """
        Extract structured data using local regex heuristics (no API calls).
        
        Used as:
        - Primary mode when RESUME_EXTRACTION_MODE=local
        - Fallback when OpenAI extraction fails
        """
        data = {}
        
        # Extract contact information
        data.update(self._extract_contact_info(markdown_text))
        
        # Extract skills
        data['skills'] = self._extract_skills(markdown_text)
        
        # Extract experience
        data['experience'] = self._extract_experience(markdown_text)
        
        # Extract education
        data['education'] = self._extract_education(markdown_text)
        
        # Extract certifications
        data['certifications'] = self._extract_certifications(markdown_text)
        
        # Extract summary/headline
        data.update(self._extract_summary(markdown_text))
        
        return data
    
    def _extract_contact_info(self, text: str) -> Dict[str, Optional[str]]:
        """Extract contact information from resume text."""
        contact_info = {}
        
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, text)
        if email_match:
            contact_info['email'] = email_match.group(0)
        
        # Extract phone (US format)
        phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            contact_info['phone'] = phone_match.group(0)
        
        # Extract LinkedIn URL
        linkedin_pattern = r'linkedin\.com/in/[\w-]+'
        linkedin_match = re.search(linkedin_pattern, text, re.IGNORECASE)
        if linkedin_match:
            contact_info['linkedin_url'] = f"https://{linkedin_match.group(0)}"
        
        # Extract GitHub URL
        github_pattern = r'github\.com/[\w-]+'
        github_match = re.search(github_pattern, text, re.IGNORECASE)
        if github_match:
            contact_info['github_url'] = f"https://{github_match.group(0)}"
        
        # Extract name using multi-layer heuristic
        # Layer 1: Blocklist of common section headers (negative matching)
        section_headers = {
            'top skills', 'skills', 'experience', 'education', 'summary',
            'professional summary', 'work experience', 'career summary',
            'technical skills', 'core competencies', 'technologies',
            'certifications', 'projects', 'publications', 'references',
            'contact information', 'contact info', 'personal information',
            'professional experience', 'career objective', 'objective',
            'about me', 'profile summary', 'key skills', 'achievements',
            'work history', 'employment history', 'career history',
        }
        # Layer 2: Common non-name words that appear in resumes (positive filter)
        non_name_words = {
            'skills', 'experience', 'education', 'summary', 'objective',
            'career', 'professional', 'technical', 'core', 'certifications',
            'projects', 'references', 'information', 'contact', 'profile',
            'overview', 'history', 'competencies', 'achievements', 'top',
            'work', 'employment', 'key', 'about', 'personal', 'details',
            'phone', 'email', 'address', 'linkedin', 'github', 'website',
            'http', 'https', 'www', 'resume', 'curriculum', 'vitae', 'cv',
        }
        lines = text.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip('#').strip()
            if line and len(line.split()) >= 2 and len(line) < 50:
                # Layer 1: Skip known section headers
                if line.lower() in section_headers:
                    continue
                words = line.split()
                if 2 <= len(words) <= 4:
                    # Layer 2: Skip if ANY word is a common non-name word
                    lower_words = [w.lower().rstrip('.:,;') for w in words]
                    if any(w in non_name_words for w in lower_words):
                        continue
                    # Layer 3: Positive check - name words should be capitalized
                    # (or all-caps which is common in resumes)
                    if not all(w[0].isupper() or w.isupper() for w in words if w.isalpha()):
                        continue
                    # Layer 4: Name words should be mostly alphabetic
                    alpha_words = [w for w in words if w.replace('-', '').replace("'", '').isalpha()]
                    if len(alpha_words) < 2:
                        continue
                    
                    contact_info['full_name'] = line
                    contact_info['first_name'] = words[0]
                    contact_info['last_name'] = words[-1]
                    break
        
        return contact_info
    
    def _extract_skills(self, text: str) -> List[str]:
        """
        Extract skills from resume.
        
        Looks for common skills section headers.
        """
        skills = []
        
        # Find skills section
        skills_pattern = r'(?i)(skills|technical skills|core competencies|technologies)(.*?)(?=\n\n|\n#|$)'
        skills_match = re.search(skills_pattern, text, re.DOTALL)
        
        if skills_match:
            skills_text = skills_match.group(2)
            
            # Extract individual skills (comma or bullet separated)
            # Remove markdown bullets and extra whitespace
            skills_text = re.sub(r'[•\-\*]', '', skills_text)
            skills_text = re.sub(r'\s+', ' ', skills_text)
            
            # Split by common separators
            potential_skills = re.split(r'[,;|\n]', skills_text)
            
            # Clean and filter skills
            for skill in potential_skills:
                skill = skill.strip()
                if skill and len(skill) < 50:  # Reasonable skill length
                    skills.append(skill)
        
        return skills
    
    def _extract_experience(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract work experience from resume.
        
        Looks for common experience section headers.
        """
        experience = []
        
        # Find experience section
        exp_pattern = r'(?i)(experience|work experience|employment history|professional experience)(.*?)(?=\n#\s*[A-Z]|$)'
        exp_match = re.search(exp_pattern, text, re.DOTALL)
        
        if exp_match:
            exp_text = exp_match.group(2)
            
            # Split into individual job entries (heuristic: ## or bold text)
            job_entries = re.split(r'\n##\s+|\n\*\*', exp_text)
            
            for entry in job_entries:
                if not entry.strip():
                    continue
                
                job_data = {}
                lines = entry.strip().split('\n')
                
                # First line often contains title and company
                if lines:
                    first_line = lines[0].strip('*').strip()
                    # Try to parse "Title at Company" or "Title, Company"
                    if ' at ' in first_line:
                        parts = first_line.split(' at ')
                        job_data['title'] = parts[0].strip()
                        job_data['company'] = parts[1].strip()
                    elif ',' in first_line:
                        parts = first_line.split(',')
                        job_data['title'] = parts[0].strip()
                        job_data['company'] = parts[1].strip() if len(parts) > 1 else None
                    else:
                        job_data['title'] = first_line
                
                # Look for date ranges (e.g., "2020 - 2023" or "Jan 2020 - Present")
                date_pattern = r'(\w+\s+)?(\d{4})\s*[-–]\s*(\w+\s+)?(\d{4}|Present|Current)'
                date_match = re.search(date_pattern, entry, re.IGNORECASE)
                if date_match:
                    job_data['start_date'] = date_match.group(2)
                    end_date = date_match.group(4)
                    if end_date.lower() in ['present', 'current']:
                        job_data['is_current'] = True
                        job_data['end_date'] = None
                    else:
                        job_data['end_date'] = end_date
                
                # Description is the rest of the text
                if len(lines) > 1:
                    job_data['description'] = '\n'.join(lines[1:]).strip()
                
                if job_data:
                    experience.append(job_data)
        
        return experience
    
    def _extract_education(self, text: str) -> List[Dict[str, Any]]:
        """Extract education from resume."""
        education = []
        
        # Find education section
        edu_pattern = r'(?i)(education|academic background)(.*?)(?=\n#\s*[A-Z]|$)'
        edu_match = re.search(edu_pattern, text, re.DOTALL)
        
        if edu_match:
            edu_text = edu_match.group(2)
            
            # Split into individual entries
            edu_entries = re.split(r'\n##\s+|\n\*\*', edu_text)
            
            for entry in edu_entries:
                if not entry.strip():
                    continue
                
                edu_data = {}
                lines = entry.strip().split('\n')
                
                # First line often contains degree and school
                if lines:
                    first_line = lines[0].strip('*').strip()
                    
                    # Common patterns: "Bachelor of Science in Computer Science"
                    if 'bachelor' in first_line.lower() or 'master' in first_line.lower() or 'phd' in first_line.lower():
                        edu_data['degree'] = first_line
                    
                    # Look for school name in subsequent lines
                    if len(lines) > 1:
                        edu_data['school'] = lines[1].strip()
                
                # Look for graduation year
                year_pattern = r'\b(19|20)\d{2}\b'
                year_match = re.search(year_pattern, entry)
                if year_match:
                    edu_data['end_date'] = year_match.group(0)
                
                if edu_data:
                    education.append(edu_data)
        
        return education
    
    def _extract_certifications(self, text: str) -> List[str]:
        """Extract certifications from resume."""
        certifications = []
        
        # Find certifications section
        cert_pattern = r'(?i)(certifications?|licenses?)(.*?)(?=\n\n|\n#|$)'
        cert_match = re.search(cert_pattern, text, re.DOTALL)
        
        if cert_match:
            cert_text = cert_match.group(2)
            
            # Extract individual certifications (bullet or line separated)
            cert_text = re.sub(r'[•\-\*]', '', cert_text)
            cert_lines = cert_text.strip().split('\n')
            
            for line in cert_lines:
                line = line.strip()
                if line and len(line) < 100:
                    certifications.append(line)
        
        return certifications
    
    def _extract_summary(self, text: str) -> Dict[str, Optional[str]]:
        """Extract professional summary or headline."""
        result = {}
        
        # Look for summary section
        summary_pattern = r'(?i)(summary|profile|about|objective)(.*?)(?=\n\n|\n#|$)'
        summary_match = re.search(summary_pattern, text, re.DOTALL)
        
        if summary_match:
            summary_text = summary_match.group(2).strip()
            if summary_text:
                result['summary'] = summary_text
        
        return result
    
    def normalize_to_pdl_format(self, parsed_resume: ParsedResume) -> Dict[str, Any]:
        """
        Convert parsed resume to PDL-like format.
        
        This allows us to use the same scoring algorithms
        for both applicants (from resumes) and market candidates (from PDL).
        
        Args:
            parsed_resume: Parsed resume data
            
        Returns:
            Dictionary in PDL person format
        """
        pdl_format = {
            "id": f"resume_{hash(parsed_resume.email or parsed_resume.full_name or 'unknown')}",
            "full_name": parsed_resume.full_name,
            "first_name": parsed_resume.first_name,
            "last_name": parsed_resume.last_name,
            "emails": [{"address": parsed_resume.email}] if parsed_resume.email else [],
            "phone_numbers": [{"number": parsed_resume.phone}] if parsed_resume.phone else [],
            "linkedin_url": parsed_resume.linkedin_url,
            "github_url": parsed_resume.github_url,
            "location_name": parsed_resume.location,
            "headline": parsed_resume.headline or parsed_resume.summary,
            "summary": parsed_resume.summary,
            
            # Skills
            "skills": [{"name": skill} for skill in parsed_resume.skills],
            
            # Experience
            "experience": [
                {
                    "title": {"name": exp.title} if exp.title else None,
                    "company": {"name": exp.company} if exp.company else None,
                    "start_date": exp.start_date,
                    "end_date": exp.end_date,
                    "is_current": exp.is_current,
                    "description": exp.description,
                    "location": {"name": exp.location} if exp.location else None,
                }
                for exp in parsed_resume.experience
            ],
            
            # Education
            "education": [
                {
                    "school": {"name": edu.school} if edu.school else None,
                    "degrees": [edu.degree] if edu.degree else [],
                    "majors": [edu.field_of_study] if edu.field_of_study else [],
                    "start_date": edu.start_date,
                    "end_date": edu.end_date,
                }
                for edu in parsed_resume.education
            ],
            
            # Certifications
            "certifications": [
                {"name": cert}
                for cert in parsed_resume.certifications
            ],
            
            # Metadata
            "source": "resume_upload",
            "data_source": "docling_parser",
        }
        
        return pdl_format

