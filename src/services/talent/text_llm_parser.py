"""
Text + LLM Resume Parser

Lightweight, high-accuracy resume parser that:
1. Extracts text from PDFs using PyMuPDF (fast, no ML models, zero memory overhead)
2. Sends plain text to an LLM (GPT-4o by default) for structured extraction

Benchmarked at 0.930 overall accuracy on real Greenhouse resumes — beating
vision-based approaches while being faster and cheaper (no image tokens).

Replaces the DoclingVLMParser which used a local VLM model + regex extraction
and scored 0.28 accuracy with frequent OOM kills and timeouts.

See scripts/eval_resume_parsing.py for full benchmark results.
"""

import json
import re
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path

from src.models.talent_analysis import ParsedResume, ParsedExperience, ParsedEducation
from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__, component="talent.text_llm_parser")

# Timeout for parsing a single resume (in seconds)
RESUME_PARSE_TIMEOUT_SECONDS = 60  # 1 minute — text+LLM is much faster than VLM

# Extraction prompt — identical to the eval-benchmarked prompt
EXTRACTION_PROMPT = """You are an expert resume parser. Your job is to extract ONLY information that is explicitly written in the resume. Output MUST be a faithful representation of what is on the document — nothing more, nothing less.

CRITICAL RULES:
- DO NOT infer, guess, or fabricate any data. If a field is not explicitly stated in the resume, use null.
- DO NOT add skills that are not literally written on the resume. If "Python" is not printed on the page, do not include it — even if the person's experience implies they know it.
- DO NOT generate descriptions, summaries, or achievements that are not actually written in the resume text.
- DO NOT expand abbreviations or add context that is not present (e.g., do not turn "AWS" into "Amazon Web Services" unless both forms appear).
- DO NOT hallucinate company names, dates, degrees, or any other data.
- If information is ambiguous or partially visible, extract what you can see and use null for what you cannot.

Return ONLY valid JSON (no markdown fences, no commentary). Use null for missing fields. Use empty arrays [] when a category exists but has no entries.

{
  "full_name": "string or null — exactly as written on the resume",
  "email": "string or null — exactly as written",
  "phone": "string or null — exactly as written",
  "location": "string or null — exactly as written",
  "linkedin_url": "string or null — exactly as written or shown on the resume",
  "github_url": "string or null — exactly as written or shown on the resume",
  "current_title": "string or null — the most recent job title, exactly as written",
  "current_company": "string or null — the most recent employer, exactly as written",
  "summary": "string or null — only if a summary/objective/profile section exists on the resume, copy its text verbatim",
  "skills": ["only skills explicitly listed or written on the resume, verbatim"],
  "certifications": ["only certifications explicitly listed on the resume, verbatim"],
  "experience": [
    {
      "title": "Job title exactly as written",
      "company": "Company name exactly as written",
      "start_date": "start date exactly as written on the resume (e.g. 'January 2020', '2018', 'Mar 2019')",
      "end_date": "end date exactly as written, or null if 'Present'/'Current'/ongoing",
      "duration_months": null,
      "description": "role description only if explicitly written on the resume, otherwise null",
      "achievements": ["only bullet points or achievements explicitly written under this role"]
    }
  ],
  "education": [
    {
      "degree": "Degree type exactly as written (e.g. B.S., M.S., Ph.D., MBA)",
      "field_of_study": "Major/field exactly as written, or null if not stated",
      "school": "Institution name exactly as written",
      "graduation_year": "integer or null — only if explicitly stated"
    }
  ]
}

ADDITIONAL RULES:
- For skills: ONLY include skills that are explicitly printed on the resume. Do NOT infer skills from job descriptions, tools mentioned in passing, or technologies implied by the role.
- For experience: extract every distinct role listed, from most recent to oldest, exactly as presented.
- For dates: copy verbatim from the resume. Do NOT calculate or estimate duration_months — always set it to null.
- For non-English resumes: extract all fields as-is. Keep the original language for proper nouns, titles, and institution names.
- When in doubt, use null. It is always better to leave a field null than to guess.
"""


class TextLLMParser:
    """
    Resume parser using PDF text extraction + LLM structured extraction.

    Much faster, lighter, and more accurate than the VLM + regex approach.
    No local ML models loaded — uses PyMuPDF for text and OpenAI API for extraction.
    """

    def __init__(self, model: Optional[str] = None):
        """
        Initialize the text+LLM parser.

        Args:
            model: LLM model name (default: from settings or 'gpt-4o')
        """
        settings = get_settings()

        self.model = model or getattr(settings, 'resume_parsing_model', 'gpt-4o')
        self.api_key = settings.openai_api_key

        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY is required for TextLLMParser. "
                "Set it in .env or environment variables."
            )

        self._client = None
        logger.info(
            "text_llm_parser_initialized",
            model=self.model
        )

    def _get_client(self):
        """Lazy-init the AsyncOpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    def _extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """
        Extract text from PDF using PyMuPDF.
        Fast, lightweight, no ML models.
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError(
                "PyMuPDF (fitz) is required for TextLLMParser. "
                "Install with: pip install PyMuPDF"
            )

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            pages.append(page.get_text())
        doc.close()
        return "\n\n".join(pages)

    def _extract_text_from_file(self, file_bytes: bytes, filename: str) -> str:
        """Extract text from various file formats."""
        ext = Path(filename).suffix.lower()

        if ext == '.pdf':
            return self._extract_text_from_pdf(file_bytes)
        elif ext == '.txt':
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    return file_bytes.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return file_bytes.decode('utf-8', errors='ignore')
        elif ext in ('.doc', '.docx'):
            try:
                import docx2txt
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = tmp.name
                try:
                    return docx2txt.process(tmp_path) or ""
                finally:
                    os.unlink(tmp_path)
            except ImportError:
                logger.warning("docx2txt not installed, falling back to raw decode")
                return file_bytes.decode('utf-8', errors='ignore')
        else:
            return file_bytes.decode('utf-8', errors='ignore')

    async def parse_resume(
        self,
        file_bytes: bytes,
        filename: str,
        timeout_seconds: int = RESUME_PARSE_TIMEOUT_SECONDS,
    ) -> ParsedResume:
        """
        Parse resume using text extraction + LLM.

        Same interface as DoclingVLMParser.parse_resume() for drop-in replacement.

        Args:
            file_bytes: Resume file content
            filename: Original filename
            timeout_seconds: Maximum time for the entire operation

        Returns:
            ParsedResume with structured data and quality metadata
        """
        logger.info(
            "parsing_resume",
            filename=filename,
            model=self.model,
            timeout_seconds=timeout_seconds,
        )

        try:
            result = await asyncio.wait_for(
                self._parse_resume_impl(file_bytes, filename),
                timeout=timeout_seconds,
            )
            return result
        except asyncio.TimeoutError:
            logger.error(
                "resume_parsing_timed_out",
                filename=filename,
                timeout_seconds=timeout_seconds,
            )
            return ParsedResume(
                parse_confidence=0.0,
                quality_flags=["parse_timeout", f"timeout_after_{timeout_seconds}s"],
                raw_text=f"Resume parsing timed out after {timeout_seconds} seconds",
            )
        except Exception as e:
            logger.error(
                "resume_parsing_failed",
                filename=filename,
                error=str(e),
                error_type=type(e).__name__,
            )
            return ParsedResume(
                parse_confidence=0.0,
                quality_flags=["parse_error", f"error: {str(e)}"],
                raw_text=f"Error parsing resume: {str(e)}",
            )

    async def _parse_resume_impl(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> ParsedResume:
        """Internal implementation — text extraction + LLM call."""

        # Step 1: Extract text from file
        resume_text = await asyncio.to_thread(
            self._extract_text_from_file, file_bytes, filename
        )

        if not resume_text or len(resume_text.strip()) < 30:
            logger.warning(
                "empty_text_extraction",
                filename=filename,
                text_length=len(resume_text) if resume_text else 0,
            )
            return ParsedResume(
                parse_confidence=0.0,
                quality_flags=["empty_text", "extraction_failed"],
                raw_text=resume_text or "",
            )

        # Step 2: Send to LLM for structured extraction
        client = self._get_client()

        prompt = (
            EXTRACTION_PROMPT
            + "\n\n--- RESUME TEXT (extracted from PDF) ---\n\n"
            + resume_text
        )

        token_kwargs = {}
        if self.model.startswith("gpt-5"):
            token_kwargs["max_completion_tokens"] = 16384
        else:
            token_kwargs["max_tokens"] = 8192

        response = await client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"},
            **token_kwargs,
        )

        raw_response = response.choices[0].message.content or ""

        # Strip markdown fences if present
        clean = raw_response.strip()
        if clean.startswith("```"):
            clean = re.sub(r'^```\w*\n?', '', clean)
            clean = re.sub(r'\n?```$', '', clean)

        parsed = json.loads(clean)

        # Build ParsedResume from the LLM output
        experience = []
        for exp_data in (parsed.get("experience") or []):
            if isinstance(exp_data, dict):
                experience.append(ParsedExperience(
                    title=exp_data.get("title"),
                    company=exp_data.get("company"),
                    start_date=exp_data.get("start_date"),
                    end_date=exp_data.get("end_date"),
                    duration_months=exp_data.get("duration_months"),
                    description=exp_data.get("description"),
                    achievements=exp_data.get("achievements", []),
                ))

        education = []
        for edu_data in (parsed.get("education") or []):
            if isinstance(edu_data, dict):
                education.append(ParsedEducation(
                    degree=edu_data.get("degree"),
                    field_of_study=edu_data.get("field_of_study"),
                    school=edu_data.get("school"),
                    graduation_year=edu_data.get("graduation_year"),
                ))

        # Assess quality
        quality_score, quality_flags = self._assess_quality(parsed)

        resume = ParsedResume(
            full_name=parsed.get("full_name"),
            email=parsed.get("email"),
            phone=parsed.get("phone"),
            location=parsed.get("location"),
            linkedin_url=parsed.get("linkedin_url"),
            github_url=parsed.get("github_url"),
            current_title=parsed.get("current_title"),
            current_company=parsed.get("current_company"),
            summary=parsed.get("summary"),
            skills=parsed.get("skills") or [],
            certifications=parsed.get("certifications") or [],
            experience=experience,
            education=education,
            parse_confidence=quality_score,
            quality_flags=quality_flags,
            raw_text=resume_text,
        )

        logger.info(
            "resume_parsed_successfully",
            filename=filename,
            model=self.model,
            quality_score=quality_score,
            skills_count=len(resume.skills),
            experience_count=len(resume.experience),
            education_count=len(resume.education),
        )

        return resume

    def _assess_quality(self, parsed: Dict[str, Any]) -> tuple[float, List[str]]:
        """Assess parse quality based on field completeness."""
        score = 0.0
        flags = []

        if parsed.get("full_name"):
            score += 0.15
        else:
            flags.append("missing_name")

        if parsed.get("email"):
            score += 0.15
        else:
            flags.append("missing_email")

        skills_count = len(parsed.get("skills") or [])
        if skills_count >= 5:
            score += 0.20
        elif skills_count > 0:
            score += 0.10
            flags.append("few_skills")
        else:
            flags.append("missing_skills")

        exp_count = len(parsed.get("experience") or [])
        if exp_count >= 3:
            score += 0.30
        elif exp_count > 0:
            score += 0.15
            flags.append("limited_experience")
        else:
            flags.append("missing_experience")

        edu_count = len(parsed.get("education") or [])
        if edu_count > 0:
            score += 0.15
        else:
            flags.append("missing_education")

        if parsed.get("summary"):
            score += 0.05

        return min(score, 1.0), flags
