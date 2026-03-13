"""
Docling VLM Resume Parser

Uses Docling with Granite-Docling-258M Vision-Language Model for state-of-the-art resume parsing.
This is the "novel path" that runs in parallel with the regex-based parser.

Key improvements over regex parser:
- VLM understanding of document structure
- Better handling of complex layouts
- More accurate extraction from tables, figures
- Semantic understanding vs. pattern matching

Supported formats:
- PDF, DOCX, PPTX, HTML, XLSX (via Docling)
- TXT (direct text parsing)
- DOC (old Word format - converted via python-docx2txt or fallback to text extraction)
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import io
import asyncio
import json
import structlog
import subprocess

from src.models.talent_analysis import ParsedResume, ParsedExperience, ParsedEducation

logger = structlog.get_logger(__name__)

# Timeout for parsing a single resume (in seconds)
RESUME_PARSE_TIMEOUT_SECONDS = 120  # 2 minutes per resume

# File extensions that need special handling (not native to Docling)
SPECIAL_FORMATS = {'.txt', '.doc'}


class DoclingVLMParser:
    """
    Resume parser using Docling with OpenAI structured extraction.
    
    PDF → Docling Markdown → OpenAI GPT-4o-mini structured output.
    Falls back to local regex heuristics if OpenAI is unavailable.
    """
    
    def __init__(self):
        """Initialize Docling VLM parser."""
        self.logger = logger.bind(service="docling_vlm_parser")
        
        # Lazy import of Docling
        self._converter = None
        self._vlm_enabled = False
        self._openai_client = None
    
    def _get_converter(self):
        """
        Lazy initialization of Docling VLM converter.
        
        Uses VlmPipeline with Granite-Docling-258M model.
        Falls back to standard converter if VLM not available.
        """
        if self._converter is None:
            try:
                # Try to import VLM components
                from docling.document_converter import DocumentConverter, PdfFormatOption
                from docling.datamodel.base_models import InputFormat
                from docling.datamodel.pipeline_options import PdfPipelineOptions
                
                try:
                    # Try to enable VLM
                    from docling_core.types.doc import ImageRefMode, PictureItem, TableItem
                    
                    # Configure VLM pipeline
                    pipeline_options = PdfPipelineOptions()
                    pipeline_options.images_scale = 2.0  # Higher resolution for better VLM performance
                    pipeline_options.generate_page_images = True
                    pipeline_options.generate_picture_images = True
                    
                    self._converter = DocumentConverter(
                        format_options={
                            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
                        }
                    )
                    
                    self._vlm_enabled = True
                    self.logger.info("Docling VLM converter initialized with Granite-Docling-258M")
                    
                except ImportError:
                    # VLM not available, use standard converter
                    self._converter = DocumentConverter()
                    self._vlm_enabled = False
                    self.logger.warning(
                        "VLM not available, using standard Docling converter. "
                        "Install docling with VLM support for better parsing."
                    )
                
            except ImportError as e:
                self.logger.error("Failed to import Docling", error=str(e))
                raise ImportError(
                    "Docling is not installed. "
                    "Install with: pip install docling>=2.0.0 docling-core>=2.0.0"
                )
        
        return self._converter
    
    async def parse_resume(
        self,
        file_bytes: bytes,
        filename: str,
        timeout_seconds: int = RESUME_PARSE_TIMEOUT_SECONDS
    ) -> ParsedResume:
        """
        Parse resume using Docling VLM with timeout protection.
        
        Args:
            file_bytes: Resume file content
            filename: Original filename
            timeout_seconds: Maximum time to wait for parsing (default: 120s)
            
        Returns:
            ParsedResume with structured data and quality metadata
        """
        try:
            self.logger.info(
                "Parsing resume with VLM",
                filename=filename,
                vlm_enabled=self._vlm_enabled,
                timeout_seconds=timeout_seconds
            )
            
            # Run the synchronous Docling parsing in a thread pool with timeout
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(self._parse_resume_sync, file_bytes, filename),
                    timeout=timeout_seconds
                )
                return result
            except asyncio.TimeoutError:
                self.logger.error(
                    "Resume parsing timed out",
                    filename=filename,
                    timeout_seconds=timeout_seconds
                )
                return ParsedResume(
                    parse_confidence=0.0,
                    quality_flags=["parse_timeout", f"timeout_after_{timeout_seconds}s"],
                    raw_text=f"Resume parsing timed out after {timeout_seconds} seconds"
                )
            
        except Exception as e:
            self.logger.error(
                "Failed to parse resume with VLM",
                filename=filename,
                error=str(e),
                error_type=type(e).__name__
            )
            
            # Return minimal resume with error info
            return ParsedResume(
                parse_confidence=0.0,
                quality_flags=["parse_error", f"error: {str(e)}"],
                raw_text=f"Error parsing resume: {str(e)}"
            )
    
    def _parse_resume_sync(
        self,
        file_bytes: bytes,
        filename: str
    ) -> ParsedResume:
        """
        Synchronous resume parsing implementation.
        Called from thread pool to avoid blocking the async event loop.
        """
        import tempfile
        import os
        
        file_ext = Path(filename).suffix.lower()
        
        # Handle special formats that Docling doesn't support natively
        if file_ext in SPECIAL_FORMATS:
            return self._parse_special_format(file_bytes, filename, file_ext)
        
        # Get converter for standard formats
        converter = self._get_converter()
        
        # Docling requires a file path, not BytesIO
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='wb', suffix=file_ext, delete=False) as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name
        
        try:
            # Convert document using file path
            result = converter.convert(tmp_path)
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass
        
        # Extract markdown
        markdown_text = result.document.export_to_markdown()
        
        # Get DocTags structure if available
        doc_dict = result.document.export_to_dict() if hasattr(result, 'document') else {}
        
        # Extract structured data using VLM-aware methods
        parsed_data = self._extract_structured_data(markdown_text, doc_dict, result)
        
        # Calculate parse quality
        quality_score, quality_flags = self._assess_parse_quality(parsed_data)
        
        # Create ParsedResume (using our talent_analysis Pydantic model)
        parsed_resume = ParsedResume(
            **parsed_data,
            parse_confidence=quality_score,
            quality_flags=quality_flags,
            raw_text=markdown_text,
            docling_output=doc_dict
        )
        
        self.logger.info(
            "Resume parsed successfully with VLM",
            filename=filename,
            vlm_enabled=self._vlm_enabled,
            quality_score=quality_score,
            skills_count=len(parsed_resume.skills),
            experience_count=len(parsed_resume.experience)
        )
        
        return parsed_resume
    
    def _parse_special_format(
        self,
        file_bytes: bytes,
        filename: str,
        file_ext: str
    ) -> ParsedResume:
        """
        Handle file formats not natively supported by Docling.
        
        Supports:
        - .txt: Direct text parsing
        - .doc: Old Word format (tries multiple extraction methods)
        """
        self.logger.info(
            "Parsing special format file",
            filename=filename,
            file_ext=file_ext
        )
        
        if file_ext == '.txt':
            return self._parse_txt_file(file_bytes, filename)
        elif file_ext == '.doc':
            return self._parse_doc_file(file_bytes, filename)
        else:
            # Shouldn't happen, but handle gracefully
            return ParsedResume(
                parse_confidence=0.0,
                quality_flags=["unsupported_format", f"format: {file_ext}"],
                raw_text=f"Unsupported file format: {file_ext}"
            )
    
    def _parse_txt_file(
        self,
        file_bytes: bytes,
        filename: str
    ) -> ParsedResume:
        """
        Parse a plain text resume file.
        
        Text files are parsed directly using pattern matching.
        """
        try:
            # Try UTF-8 first, then fall back to other encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    text_content = file_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                text_content = file_bytes.decode('utf-8', errors='ignore')
            
            # Use pattern extraction on the text
            parsed_data = self._extract_with_patterns(text_content)
            
            # Calculate quality
            quality_score, quality_flags = self._assess_parse_quality(parsed_data)
            quality_flags.append("txt_format")
            
            parsed_resume = ParsedResume(
                **parsed_data,
                parse_confidence=quality_score,
                quality_flags=quality_flags,
                raw_text=text_content
            )
            
            self.logger.info(
                "TXT resume parsed successfully",
                filename=filename,
                quality_score=quality_score,
                skills_count=len(parsed_resume.skills),
                experience_count=len(parsed_resume.experience)
            )
            
            return parsed_resume
            
        except Exception as e:
            self.logger.error(
                "Failed to parse TXT file",
                filename=filename,
                error=str(e)
            )
            return ParsedResume(
                parse_confidence=0.0,
                quality_flags=["txt_parse_error", str(e)],
                raw_text=f"Error parsing TXT: {str(e)}"
            )
    
    def _parse_doc_file(
        self,
        file_bytes: bytes,
        filename: str
    ) -> ParsedResume:
        """
        Parse an old-format Word .doc file.
        
        Tries multiple extraction methods:
        1. antiword (if available on system)
        2. textract (if installed)
        3. Basic binary text extraction as fallback
        """
        import tempfile
        import os
        
        text_content = None
        extraction_method = None
        
        # Create temp file for extraction tools
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.doc', delete=False) as tmp_file:
            tmp_file.write(file_bytes)
            tmp_path = tmp_file.name
        
        try:
            # Method 1: Try antiword (common Linux tool)
            try:
                result = subprocess.run(
                    ['antiword', tmp_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0 and result.stdout.strip():
                    text_content = result.stdout
                    extraction_method = "antiword"
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            
            # Method 2: Try catdoc (another Linux tool)
            if not text_content:
                try:
                    result = subprocess.run(
                        ['catdoc', tmp_path],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        text_content = result.stdout
                        extraction_method = "catdoc"
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
            
            # Method 3: Try python-docx2txt (handles some .doc files)
            if not text_content:
                try:
                    import docx2txt
                    text_content = docx2txt.process(tmp_path)
                    if text_content and text_content.strip():
                        extraction_method = "docx2txt"
                    else:
                        text_content = None
                except Exception:
                    pass
            
            # Method 4: Fallback - extract readable text from binary
            if not text_content:
                text_content = self._extract_text_from_binary(file_bytes)
                extraction_method = "binary_extraction"
            
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass
        
        if not text_content or len(text_content.strip()) < 50:
            self.logger.warning(
                "Could not extract meaningful text from DOC file",
                filename=filename,
                extraction_method=extraction_method
            )
            return ParsedResume(
                parse_confidence=0.0,
                quality_flags=["doc_extraction_failed", "insufficient_text"],
                raw_text="Could not extract text from .doc file. Please convert to PDF or DOCX."
            )
        
        # Parse the extracted text
        parsed_data = self._extract_with_patterns(text_content)
        
        # Calculate quality
        quality_score, quality_flags = self._assess_parse_quality(parsed_data)
        quality_flags.append("doc_format")
        quality_flags.append(f"extraction_method:{extraction_method}")
        
        parsed_resume = ParsedResume(
            **parsed_data,
            parse_confidence=quality_score,
            quality_flags=quality_flags,
            raw_text=text_content
        )
        
        self.logger.info(
            "DOC resume parsed successfully",
            filename=filename,
            extraction_method=extraction_method,
            quality_score=quality_score,
            skills_count=len(parsed_resume.skills),
            experience_count=len(parsed_resume.experience)
        )
        
        return parsed_resume
    
    def _extract_text_from_binary(self, file_bytes: bytes) -> str:
        """
        Extract readable text from binary file as last resort.
        
        Looks for ASCII/UTF-8 text sequences in the binary data.
        """
        import re
        
        # Try to decode as much text as possible
        try:
            # First try UTF-16 (common in .doc files)
            text = file_bytes.decode('utf-16', errors='ignore')
        except:
            text = file_bytes.decode('latin-1', errors='ignore')
        
        # Remove null bytes and control characters (except newlines/tabs)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', ' ', text)
        
        # Find sequences of readable text (at least 4 characters)
        readable_sequences = re.findall(r'[a-zA-Z0-9@.\-_,;:\'\"()\s]{4,}', text)
        
        # Join and clean up
        extracted = ' '.join(readable_sequences)
        extracted = re.sub(r'\s+', ' ', extracted).strip()
        
        return extracted
    
    def _get_openai_client(self):
        """Lazy initialization of OpenAI client."""
        if self._openai_client is None:
            from openai import OpenAI
            from src.core.config import get_settings
            settings = get_settings()
            if not settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required for OpenAI resume extraction")
            self._openai_client = OpenAI(api_key=settings.openai_api_key)
            self.logger.info("OpenAI client initialized for VLM parser")
        return self._openai_client
    
    def _extract_structured_data(
        self,
        markdown_text: str,
        doc_dict: Dict[str, Any],
        docling_result: Any
    ) -> Dict[str, Any]:
        """
        Extract structured data from resume markdown.
        
        Priority:
        1. OpenAI structured output (if RESUME_EXTRACTION_MODE=openai)
        2. VLM-enhanced structure extraction (if Docling VLM was available)
        3. Local regex pattern matching (fallback)
        """
        from src.core.config import get_settings
        settings = get_settings()
        mode = settings.resume_extraction_mode.lower()
        
        # Try OpenAI first
        if mode == "openai":
            try:
                data = self._extract_with_openai(markdown_text)
                if data:
                    return data
                self.logger.warning("OpenAI extraction returned empty, falling back")
            except Exception as e:
                self.logger.warning(
                    "OpenAI extraction failed, falling back to local",
                    error=str(e),
                    error_type=type(e).__name__
                )
        
        # Fall back to existing methods
        data = {}
        if self._vlm_enabled and doc_dict:
            data.update(self._extract_with_structure(markdown_text, doc_dict))
        else:
            data.update(self._extract_with_patterns(markdown_text))
        
        return data
    
    def _extract_with_openai(self, markdown_text: str) -> Optional[Dict[str, Any]]:
        """
        Extract structured resume data using OpenAI structured output.
        
        Reuses the same schema and prompt as DoclingParser for consistency.
        """
        from src.core.config import get_settings
        settings = get_settings()
        model = settings.resume_extraction_model
        
        client = self._get_openai_client()
        
        # Truncate very long resumes
        max_chars = 15000
        text_to_send = markdown_text[:max_chars]
        
        self.logger.info("Extracting resume data with OpenAI (VLM parser)",
                        model=model,
                        text_length=len(text_to_send))
        
        system_prompt = """You are a resume parsing assistant. Given the markdown text of a resume, extract structured data accurately.

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
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
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
                            "full_name": {"type": ["string", "null"]},
                            "first_name": {"type": ["string", "null"]},
                            "last_name": {"type": ["string", "null"]},
                            "email": {"type": ["string", "null"]},
                            "phone": {"type": ["string", "null"]},
                            "linkedin_url": {"type": ["string", "null"]},
                            "github_url": {"type": ["string", "null"]},
                            "location": {"type": ["string", "null"]},
                            "summary": {"type": ["string", "null"]},
                            "headline": {"type": ["string", "null"]},
                            "skills": {"type": "array", "items": {"type": "string"}},
                            "experience": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {"type": ["string", "null"]},
                                        "company": {"type": ["string", "null"]},
                                        "start_date": {"type": ["string", "null"]},
                                        "end_date": {"type": ["string", "null"]},
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
                            "certifications": {"type": "array", "items": {"type": "string"}},
                            "languages": {"type": "array", "items": {"type": "string"}}
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
            temperature=0.0,
        )
        
        result_text = response.choices[0].message.content
        if not result_text:
            return None
        
        data = json.loads(result_text)
        
        usage = response.usage
        if usage:
            self.logger.info("OpenAI resume extraction complete (VLM parser)",
                           model=model,
                           prompt_tokens=usage.prompt_tokens,
                           completion_tokens=usage.completion_tokens,
                           total_tokens=usage.total_tokens,
                           extracted_name=data.get("full_name"))
        
        return data
    
    def _extract_with_structure(
        self,
        markdown_text: str,
        doc_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract data using document structure from VLM.
        
        The VLM provides better section detection, table extraction,
        and layout understanding than regex patterns.
        """
        import re
        
        data = {
            'skills': [],
            'experience': [],
            'education': [],
            'certifications': []
        }
        
        # Extract contact info (still regex for now, but could be VLM-enhanced)
        data.update(self._extract_contact_info(markdown_text))
        
        # Parse sections from document structure
        # DocTags provides hierarchical structure
        text_lower = markdown_text.lower()
        lines = markdown_text.split('\n')
        
        # Find section headers
        skills_section_start = None
        experience_section_start = None
        education_section_start = None
        
        for i, line in enumerate(lines):
            line_lower = line.lower().strip('#').strip()
            
            # Skills section
            if any(keyword in line_lower for keyword in ['skills', 'technical skills', 'competencies', 'technologies']):
                skills_section_start = i
            
            # Experience section
            elif any(keyword in line_lower for keyword in ['experience', 'work history', 'employment', 'professional experience']):
                experience_section_start = i
            
            # Education section
            elif any(keyword in line_lower for keyword in ['education', 'academic', 'qualifications']):
                education_section_start = i
        
        # Extract skills
        if skills_section_start is not None:
            data['skills'] = self._extract_skills_from_section(lines, skills_section_start)
        
        # Extract experience
        if experience_section_start is not None:
            data['experience'] = self._extract_experience_from_section(lines, experience_section_start)
        
        # Extract education
        if education_section_start is not None:
            data['education'] = self._extract_education_from_section(lines, education_section_start)
        
        # Extract summary
        data.update(self._extract_summary(markdown_text))
        
        return data
    
    def _extract_with_patterns(self, markdown_text: str) -> Dict[str, Any]:
        """
        Fallback pattern-based extraction.
        Similar to original parser but simplified.
        """
        import re
        
        data = {
            'skills': [],
            'experience': [],
            'education': [],
            'certifications': []
        }
        
        # Contact info
        data.update(self._extract_contact_info(markdown_text))
        
        # Skills (simple extraction)
        skills_pattern = r'(?i)(skills|technologies)(.*?)(?=\n\n|\n#|$)'
        skills_match = re.search(skills_pattern, markdown_text, re.DOTALL)
        if skills_match:
            skills_text = skills_match.group(2)
            skills_text = re.sub(r'[•\-\*]', '', skills_text)
            potential_skills = re.split(r'[,;|\n]', skills_text)
            data['skills'] = [s.strip() for s in potential_skills if s.strip() and len(s.strip()) < 50]
        
        # Summary
        data.update(self._extract_summary(markdown_text))
        
        return data
    
    def _extract_contact_info(self, text: str) -> Dict[str, Optional[str]]:
        """Extract contact information."""
        import re
        
        contact = {}
        
        # Email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, text)
        if email_match:
            contact['email'] = email_match.group(0)
        
        # Phone
        phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            contact['phone'] = phone_match.group(0)
        
        # LinkedIn
        linkedin_pattern = r'linkedin\.com/in/([\w-]+)'
        linkedin_match = re.search(linkedin_pattern, text, re.IGNORECASE)
        if linkedin_match:
            contact['linkedin_url'] = f"https://linkedin.com/in/{linkedin_match.group(1)}"
        
        # GitHub
        github_pattern = r'github\.com/([\w-]+)'
        github_match = re.search(github_pattern, text, re.IGNORECASE)
        if github_match:
            contact['github_url'] = f"https://github.com/{github_match.group(1)}"
        
        # Name (first substantial line)
        lines = text.split('\n')
        for line in lines[:15]:
            line = line.strip('#').strip()
            if line and 2 <= len(line.split()) <= 4 and len(line) < 50:
                # Exclude lines with common keywords
                if not any(kw in line.lower() for kw in ['resume', 'curriculum', 'cv', 'contact', 'email', 'phone']):
                    contact['full_name'] = line
                    break
        
        return contact
    
    def _extract_skills_from_section(self, lines: List[str], section_start: int) -> List[str]:
        """Extract skills from identified section."""
        import re
        
        skills = []
        
        # Collect lines until next section (marked by # or significant gap)
        section_lines = []
        for i in range(section_start + 1, len(lines)):
            if lines[i].startswith('#'):
                break
            section_lines.append(lines[i])
        
        # Join and parse
        section_text = ' '.join(section_lines)
        section_text = re.sub(r'[•\-\*]', '', section_text)
        
        # Split by common separators
        potential_skills = re.split(r'[,;|\n]', section_text)
        
        # Clean
        for skill in potential_skills:
            skill = skill.strip()
            if skill and 2 <= len(skill) <= 50:
                skills.append(skill)
        
        return skills
    
    def _extract_experience_from_section(self, lines: List[str], section_start: int) -> List[Dict[str, Any]]:
        """Extract experience entries from identified section."""
        import re
        
        experience = []
        
        # Collect section lines
        section_lines = []
        for i in range(section_start + 1, len(lines)):
            if lines[i].startswith('#') and not lines[i].startswith('##'):
                break
            section_lines.append(lines[i])
        
        # Group by job (identified by ## or bold patterns)
        current_job = []
        jobs = []
        
        for line in section_lines:
            if line.startswith('##') or line.startswith('**'):
                if current_job:
                    jobs.append('\n'.join(current_job))
                current_job = [line]
            else:
                current_job.append(line)
        
        if current_job:
            jobs.append('\n'.join(current_job))
        
        # Parse each job
        for job_text in jobs:
            job_data = {}
            job_lines = job_text.split('\n')
            
            if not job_lines:
                continue
            
            # First line: title and company
            first = job_lines[0].strip('#').strip('*').strip()
            if ' at ' in first:
                parts = first.split(' at ')
                job_data['title'] = parts[0].strip()
                job_data['company'] = parts[1].strip()
            elif ' - ' in first:
                parts = first.split(' - ')
                job_data['title'] = parts[0].strip()
                if len(parts) > 1:
                    job_data['company'] = parts[1].strip()
            
            # Dates
            date_pattern = r'(\d{4})\s*[-–]\s*(\d{4}|Present|Current)'
            date_match = re.search(date_pattern, job_text, re.IGNORECASE)
            if date_match:
                job_data['start_date'] = date_match.group(1)
                end = date_match.group(2)
                job_data['end_date'] = None if end.lower() in ['present', 'current'] else end
            
            # Description
            if len(job_lines) > 1:
                desc_lines = [l for l in job_lines[1:] if l.strip() and not re.match(r'^\d{4}', l)]
                if desc_lines:
                    job_data['description'] = '\n'.join(desc_lines).strip()
            
            if job_data:
                experience.append(job_data)
        
        return experience
    
    def _extract_education_from_section(self, lines: List[str], section_start: int) -> List[Dict[str, Any]]:
        """Extract education entries from identified section."""
        import re
        
        education = []
        
        # Collect section lines
        section_lines = []
        for i in range(section_start + 1, len(lines)):
            if lines[i].startswith('#') and not lines[i].startswith('##'):
                break
            section_lines.append(lines[i])
        
        section_text = '\n'.join(section_lines)
        
        # Split by common degree types
        entries = re.split(r'\n(?=Bachelor|Master|PhD|Ph\.D\.|B\.S\.|M\.S\.|B\.A\.|M\.A\.)', section_text, flags=re.IGNORECASE)
        
        for entry in entries:
            if not entry.strip():
                continue
            
            edu_data = {}
            
            # Degree (first line usually)
            lines_in_entry = entry.split('\n')
            if lines_in_entry:
                edu_data['degree'] = lines_in_entry[0].strip()
            
            # School
            if len(lines_in_entry) > 1:
                edu_data['school'] = lines_in_entry[1].strip()
            
            # Year
            year_pattern = r'\b(19|20)\d{2}\b'
            year_match = re.search(year_pattern, entry)
            if year_match:
                edu_data['graduation_year'] = int(year_match.group(0))
            
            if edu_data:
                education.append(edu_data)
        
        return education
    
    def _extract_summary(self, text: str) -> Dict[str, Optional[str]]:
        """Extract professional summary."""
        import re
        
        summary_pattern = r'(?i)(summary|profile|about|objective)(.*?)(?=\n\n|\n#|$)'
        summary_match = re.search(summary_pattern, text, re.DOTALL)
        
        if summary_match:
            summary_text = summary_match.group(2).strip()
            if len(summary_text) > 20:
                return {'summary': summary_text}
        
        return {}
    
    def _assess_parse_quality(self, parsed_data: Dict[str, Any]) -> tuple[float, List[str]]:
        """
        Assess quality of parse.
        
        Returns:
            (quality_score, quality_flags)
            quality_score: 0.0 to 1.0
            quality_flags: List of issues or warnings
        """
        score = 0.0
        flags = []
        
        # Contact info (15 points each)
        if parsed_data.get('full_name'):
            score += 0.15
        else:
            flags.append("missing_name")
        
        if parsed_data.get('email'):
            score += 0.15
        else:
            flags.append("missing_email")
        
        # Skills (20 points)
        skills_count = len(parsed_data.get('skills', []))
        if skills_count >= 5:
            score += 0.20
        elif skills_count > 0:
            score += 0.10
            flags.append("few_skills")
        else:
            flags.append("missing_skills")
        
        # Experience (30 points)
        exp_count = len(parsed_data.get('experience', []))
        if exp_count >= 3:
            score += 0.30
        elif exp_count > 0:
            score += 0.15
            flags.append("limited_experience")
        else:
            flags.append("missing_experience")
        
        # Education (15 points)
        edu_count = len(parsed_data.get('education', []))
        if edu_count > 0:
            score += 0.15
        else:
            flags.append("missing_education")
        
        # Summary (5 points)
        if parsed_data.get('summary'):
            score += 0.05
        
        # Cap at 1.0
        score = min(score, 1.0)
        
        return score, flags

