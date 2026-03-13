#!/usr/bin/env python3
"""
Resume Parsing Model Evaluation — ParsedResume Schema-Aligned

Evaluates multiple resume-parsing approaches against human-curated ground truth:
  - GPT-5.2  (OpenAI vision, premium)
  - GPT-4o   (OpenAI vision, mid-tier)
  - GPT-4o-mini (OpenAI vision, budget)
  - Docling Granite 258M (local VLM + regex, free — our production parser)

Each model's output is compared field-by-field against the ParsedResume target
schema from src/models/talent_analysis.py.

Target schema:
  ParsedResume:
    full_name, email, phone, location, linkedin_url, github_url,
    current_title, current_company, summary,
    skills: List[str],
    certifications: List[str],
    experience: List[{title, company, start_date, end_date,
                      duration_months, description, achievements[]}],
    education: List[{degree, field_of_study, school, graduation_year}]

Usage:
    python scripts/eval_resume_parsing.py                        # All 4 models, all resumes
    python scripts/eval_resume_parsing.py --model gpt-5.2        # Single model
    python scripts/eval_resume_parsing.py --model docling         # Docling only
    python scripts/eval_resume_parsing.py --limit 5              # First N resumes
    python scripts/eval_resume_parsing.py --greenhouse-only       # Real resumes only
    python scripts/eval_resume_parsing.py --include-greenhouse    # Synthetic + real
    python scripts/eval_resume_parsing.py --output results.json  # Save JSON report
"""
import asyncio
import argparse
import base64
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ============================================================================
# ParsedResume EXTRACTION PROMPT
# ============================================================================

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


# ============================================================================
# DATA MODELS (aligned with ParsedResume)
# ============================================================================

@dataclass
class GroundTruth:
    """Ground truth aligned with ParsedResume schema."""
    filename: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    current_title: Optional[str] = None
    current_company: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    experience: List[Dict[str, Any]] = field(default_factory=list)
    education: List[Dict[str, Any]] = field(default_factory=list)
    # Non-schema metadata
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResumeEvalResult:
    """Per-resume, per-model evaluation result with field-level scores."""
    filename: str
    model: str
    source: str  # "synthetic" or "greenhouse"

    # ── String field scores (0.0 = wrong/missing, 1.0 = correct) ──
    full_name_score: float = 0.0
    email_score: float = 0.0
    phone_score: float = 0.0
    location_score: float = 0.0
    linkedin_url_score: float = 0.0
    github_url_score: float = 0.0
    current_title_score: float = 0.0
    current_company_score: float = 0.0
    summary_score: float = 0.0

    # ── Skills (set overlap) ──
    skills_precision: float = 0.0
    skills_recall: float = 0.0
    skills_f1: float = 0.0
    skills_expected: int = 0
    skills_extracted: int = 0
    skills_matched: int = 0

    # ── Certifications (set overlap) ──
    certs_precision: float = 0.0
    certs_recall: float = 0.0
    certs_f1: float = 0.0
    certs_expected: int = 0
    certs_extracted: int = 0

    # ── Experience (structured list) ──
    exp_count_expected: int = 0
    exp_count_extracted: int = 0
    exp_title_recall: float = 0.0
    exp_company_recall: float = 0.0
    exp_date_recall: float = 0.0
    exp_overall_score: float = 0.0

    # ── Education (structured list) ──
    edu_count_expected: int = 0
    edu_count_extracted: int = 0
    edu_school_recall: float = 0.0
    edu_degree_recall: float = 0.0
    edu_overall_score: float = 0.0

    # ── Aggregate scores ──
    contact_score: float = 0.0      # avg of string field scores
    list_score: float = 0.0         # avg of skills_f1, certs_f1
    structured_score: float = 0.0   # avg of exp_overall, edu_overall
    overall_score: float = 0.0      # weighted composite

    # ── Meta ──
    latency_seconds: float = 0.0
    error: Optional[str] = None
    raw_response_length: int = 0
    parse_json_success: bool = False


@dataclass
class ModelSummary:
    """Aggregate metrics for one model across all resumes."""
    model: str
    total: int = 0
    successful: int = 0
    failed: int = 0

    # Per-field averages
    avg_full_name: float = 0.0
    avg_email: float = 0.0
    avg_phone: float = 0.0
    avg_location: float = 0.0
    avg_linkedin_url: float = 0.0
    avg_github_url: float = 0.0
    avg_current_title: float = 0.0
    avg_current_company: float = 0.0
    avg_summary: float = 0.0

    avg_skills_precision: float = 0.0
    avg_skills_recall: float = 0.0
    avg_skills_f1: float = 0.0
    avg_skills_count: float = 0.0

    avg_certs_f1: float = 0.0

    avg_exp_overall: float = 0.0
    avg_exp_count: float = 0.0
    avg_edu_overall: float = 0.0
    avg_edu_count: float = 0.0

    # Composite
    avg_contact_score: float = 0.0
    avg_list_score: float = 0.0
    avg_structured_score: float = 0.0
    avg_overall_score: float = 0.0

    avg_latency: float = 0.0
    est_cost: float = 0.0


# ============================================================================
# FUZZY MATCHING UTILITIES
# ============================================================================

def norm(text: Optional[str]) -> str:
    """Normalize for comparison: lowercase, strip, collapse whitespace."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text.lower().strip())


def string_match(expected: Optional[str], actual: Optional[str]) -> float:
    """Score a string field: 1.0 if match, 0.5 if partial, 0.0 if missing."""
    if not expected:
        # No ground truth — if model extracted something, neutral; score 1.0 (not penalized)
        return 1.0
    if not actual:
        return 0.0
    e, a = norm(expected), norm(actual)
    if e == a:
        return 1.0
    # Substring containment (either direction)
    if e in a or a in e:
        return 0.8
    # Check significant word overlap
    e_words = set(e.split())
    a_words = set(a.split())
    if len(e_words) > 0:
        overlap = len(e_words & a_words) / len(e_words)
        if overlap >= 0.5:
            return 0.6
    return 0.0


def set_overlap(
    expected: List[str], extracted: List[str], fuzzy: bool = True
) -> Tuple[float, float, float, int]:
    """
    Compute precision, recall, F1 for two string lists.
    Returns (precision, recall, f1, matched_count).
    """
    if not expected and not extracted:
        return 1.0, 1.0, 1.0, 0
    if not expected:
        return 1.0, 1.0, 1.0, 0  # Nothing expected; don't penalize extras
    if not extracted:
        return 0.0, 0.0, 0.0, 0

    expected_norm = [norm(s) for s in expected]
    extracted_norm = [norm(s) for s in extracted]

    matched = 0
    used_extracted = set()
    for e in expected_norm:
        for i, a in enumerate(extracted_norm):
            if i in used_extracted:
                continue
            if e == a:
                matched += 1
                used_extracted.add(i)
                break
            elif fuzzy and (e in a or a in e):
                matched += 1
                used_extracted.add(i)
                break
            elif fuzzy and len(e) > 3 and len(a) > 3:
                # Check token overlap for multi-word skills
                e_tokens = set(e.split())
                a_tokens = set(a.split())
                if e_tokens and a_tokens:
                    jaccard = len(e_tokens & a_tokens) / len(e_tokens | a_tokens)
                    if jaccard >= 0.5:
                        matched += 1
                        used_extracted.add(i)
                        break

    precision = matched / len(extracted_norm) if extracted_norm else 0.0
    recall = matched / len(expected_norm) if expected_norm else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1, matched


# ============================================================================
# STRUCTURED LIST COMPARISON
# ============================================================================

def compare_experience(
    expected: List[Dict], extracted: List[Dict]
) -> Tuple[float, float, float, float]:
    """
    Compare experience lists. Returns (title_recall, company_recall, date_recall, overall).
    Matches expected entries to extracted by best title+company overlap.
    """
    if not expected:
        return 1.0, 1.0, 1.0, 1.0
    if not extracted:
        return 0.0, 0.0, 0.0, 0.0

    title_matches = 0
    company_matches = 0
    date_matches = 0

    used = set()
    for exp_entry in expected:
        exp_title = norm(exp_entry.get("title") or "")
        exp_company = norm(exp_entry.get("company") or "")

        best_idx = -1
        best_score = -1.0

        for i, ext_entry in enumerate(extracted):
            if i in used:
                continue
            ext_title = norm(ext_entry.get("title") or "")
            ext_company = norm(ext_entry.get("company") or "")

            score = 0.0
            if exp_title and ext_title:
                if exp_title == ext_title:
                    score += 1.0
                elif exp_title in ext_title or ext_title in exp_title:
                    score += 0.7
            if exp_company and ext_company:
                if exp_company == ext_company:
                    score += 1.0
                elif exp_company in ext_company or ext_company in exp_company:
                    score += 0.7

            if score > best_score:
                best_score = score
                best_idx = i

        if best_idx >= 0 and best_score > 0:
            used.add(best_idx)
            ext = extracted[best_idx]

            # Title
            if exp_title:
                ext_title = norm(ext.get("title") or "")
                if exp_title == ext_title or exp_title in ext_title or ext_title in exp_title:
                    title_matches += 1

            # Company
            if exp_company:
                ext_company = norm(ext.get("company") or "")
                if exp_company == ext_company or exp_company in ext_company or ext_company in exp_company:
                    company_matches += 1

            # Dates
            exp_start = norm(exp_entry.get("start_date") or "")
            ext_start = norm(ext.get("start_date") or "")
            if exp_start and ext_start and (exp_start in ext_start or ext_start in exp_start):
                date_matches += 1

    total_with_title = sum(1 for e in expected if e.get("title"))
    total_with_company = sum(1 for e in expected if e.get("company"))
    total_with_date = sum(1 for e in expected if e.get("start_date"))

    title_recall = title_matches / total_with_title if total_with_title else 1.0
    company_recall = company_matches / total_with_company if total_with_company else 1.0
    date_recall = date_matches / total_with_date if total_with_date else 1.0

    overall = (title_recall * 0.4 + company_recall * 0.4 + date_recall * 0.2)
    return title_recall, company_recall, date_recall, overall


def compare_education(
    expected: List[Dict], extracted: List[Dict]
) -> Tuple[float, float, float]:
    """Compare education lists. Returns (school_recall, degree_recall, overall)."""
    if not expected:
        return 1.0, 1.0, 1.0
    if not extracted:
        return 0.0, 0.0, 0.0

    school_matches = 0
    degree_matches = 0

    used = set()
    for edu_entry in expected:
        exp_school = norm(edu_entry.get("school") or "")
        exp_degree = norm(edu_entry.get("degree") or "")

        best_idx = -1
        best_score = -1.0

        for i, ext_entry in enumerate(extracted):
            if i in used:
                continue
            ext_school = norm(ext_entry.get("school") or "")
            ext_degree = norm(ext_entry.get("degree") or "")

            score = 0.0
            if exp_school and ext_school:
                school_words = set(exp_school.split())
                ext_words = set(ext_school.split())
                if school_words & ext_words:
                    score += len(school_words & ext_words) / max(len(school_words), 1)
            if exp_degree and ext_degree:
                if exp_degree in ext_degree or ext_degree in exp_degree:
                    score += 1.0

            if score > best_score:
                best_score = score
                best_idx = i

        if best_idx >= 0 and best_score > 0:
            used.add(best_idx)
            ext = extracted[best_idx]

            if exp_school:
                ext_school = norm(ext.get("school") or "")
                school_words = set(exp_school.split())
                ext_words = set(ext_school.split())
                significant_words = {w for w in school_words if len(w) > 2}
                if significant_words and significant_words & ext_words:
                    school_matches += 1

            if exp_degree:
                ext_degree = norm(ext.get("degree") or "")
                ext_field = norm(ext.get("field_of_study") or "")
                combined = ext_degree + " " + ext_field
                if exp_degree in combined or any(
                    w in combined for w in exp_degree.split() if len(w) > 2
                ):
                    degree_matches += 1

    total_with_school = sum(1 for e in expected if e.get("school"))
    total_with_degree = sum(1 for e in expected if e.get("degree"))

    school_recall = school_matches / total_with_school if total_with_school else 1.0
    degree_recall = degree_matches / total_with_degree if total_with_degree else 1.0

    overall = (school_recall * 0.5 + degree_recall * 0.5)
    return school_recall, degree_recall, overall


# ============================================================================
# FULL RESUME COMPARISON
# ============================================================================

def evaluate_resume(
    parsed: Dict[str, Any],
    gt: GroundTruth,
    model: str,
    source: str,
    latency: float,
) -> ResumeEvalResult:
    """Compare parsed output against ground truth, scoring every ParsedResume field."""
    result = ResumeEvalResult(
        filename=gt.filename,
        model=model,
        source=source,
        latency_seconds=latency,
        parse_json_success=True,
    )

    # ── String fields ──
    result.full_name_score = string_match(gt.full_name, parsed.get("full_name"))
    result.email_score = string_match(gt.email, parsed.get("email"))
    result.phone_score = string_match(gt.phone, parsed.get("phone"))
    result.location_score = string_match(gt.location, parsed.get("location"))
    result.linkedin_url_score = string_match(gt.linkedin_url, parsed.get("linkedin_url"))
    result.github_url_score = string_match(gt.github_url, parsed.get("github_url"))
    result.current_title_score = string_match(gt.current_title, parsed.get("current_title"))
    result.current_company_score = string_match(gt.current_company, parsed.get("current_company"))
    result.summary_score = string_match(gt.summary, parsed.get("summary"))

    # Contact composite (only count fields that have ground truth)
    contact_fields = []
    if gt.full_name:
        contact_fields.append(result.full_name_score)
    if gt.email:
        contact_fields.append(result.email_score)
    if gt.phone:
        contact_fields.append(result.phone_score)
    if gt.location:
        contact_fields.append(result.location_score)
    if gt.linkedin_url:
        contact_fields.append(result.linkedin_url_score)
    if gt.github_url:
        contact_fields.append(result.github_url_score)
    if gt.current_title:
        contact_fields.append(result.current_title_score)
    if gt.current_company:
        contact_fields.append(result.current_company_score)
    result.contact_score = sum(contact_fields) / len(contact_fields) if contact_fields else 1.0

    # ── Skills ──
    extracted_skills = parsed.get("skills") or []
    result.skills_expected = len(gt.skills)
    result.skills_extracted = len(extracted_skills)
    p, r, f1, matched = set_overlap(gt.skills, extracted_skills, fuzzy=True)
    result.skills_precision = p
    result.skills_recall = r
    result.skills_f1 = f1
    result.skills_matched = matched

    # ── Certifications ──
    extracted_certs = parsed.get("certifications") or []
    result.certs_expected = len(gt.certifications)
    result.certs_extracted = len(extracted_certs)
    cp, cr, cf1, _ = set_overlap(gt.certifications, extracted_certs, fuzzy=True)
    result.certs_precision = cp
    result.certs_recall = cr
    result.certs_f1 = cf1

    result.list_score = (result.skills_f1 + result.certs_f1) / 2.0

    # ── Experience ──
    extracted_exp = parsed.get("experience") or []
    if not isinstance(extracted_exp, list):
        extracted_exp = []
    result.exp_count_expected = len(gt.experience)
    result.exp_count_extracted = len(extracted_exp)
    tr, cr2, dr, eo = compare_experience(gt.experience, extracted_exp)
    result.exp_title_recall = tr
    result.exp_company_recall = cr2
    result.exp_date_recall = dr
    result.exp_overall_score = eo

    # ── Education ──
    extracted_edu = parsed.get("education") or []
    if not isinstance(extracted_edu, list):
        extracted_edu = []
    result.edu_count_expected = len(gt.education)
    result.edu_count_extracted = len(extracted_edu)
    sr, ddr, eduo = compare_education(gt.education, extracted_edu)
    result.edu_school_recall = sr
    result.edu_degree_recall = ddr
    result.edu_overall_score = eduo

    result.structured_score = (result.exp_overall_score + result.edu_overall_score) / 2.0

    # ── Overall composite ──
    # Weighted: contact 25%, skills 30%, experience 25%, education 10%, certs 10%
    result.overall_score = (
        result.contact_score * 0.25
        + result.skills_f1 * 0.30
        + result.exp_overall_score * 0.25
        + result.edu_overall_score * 0.10
        + result.certs_f1 * 0.10
    )

    return result


# ============================================================================
# PARSING ENGINE — send resume to GPT and get ParsedResume JSON
# ============================================================================

def pdf_to_base64_images(file_bytes: bytes) -> List[str]:
    """Convert PDF pages to base64-encoded PNG images for vision API."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF (fitz) is required. Install with: pip install PyMuPDF")

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    images = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        # Render at 2x for quality
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        images.append(b64)
    doc.close()
    return images


async def parse_resume_with_model(
    file_bytes: bytes,
    filename: str,
    model: str,
    openai_api_key: str,
) -> Tuple[Dict[str, Any], float]:
    """
    Send resume to GPT model with ParsedResume schema prompt.
    Returns (parsed_dict, latency_seconds).
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=openai_api_key)

    # Convert PDF to images
    page_images = pdf_to_base64_images(file_bytes)

    # Build message content with all pages
    content: List[Dict[str, Any]] = [
        {"type": "text", "text": EXTRACTION_PROMPT}
    ]
    for b64_img in page_images:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64_img}",
                "detail": "high",
            }
        })

    start = time.time()
    try:
        # GPT-5.x uses max_completion_tokens; GPT-4o uses max_tokens
        token_kwargs = {}
        if model.startswith("gpt-5"):
            token_kwargs["max_completion_tokens"] = 16384
        else:
            token_kwargs["max_tokens"] = 8192

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            temperature=0.0,
            **token_kwargs,
        )
        latency = time.time() - start

        raw_text = response.choices[0].message.content or ""

        # Strip markdown code fences if present
        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            # Remove opening fence (```json or ```)
            raw_text = re.sub(r'^```\w*\n?', '', raw_text)
            raw_text = re.sub(r'\n?```$', '', raw_text)

        parsed = json.loads(raw_text)
        return parsed, latency

    except json.JSONDecodeError as e:
        latency = time.time() - start
        return {"_error": f"JSON parse error: {e}", "_raw": raw_text[:500]}, latency
    except Exception as e:
        latency = time.time() - start
        return {"_error": str(e)}, latency


# ============================================================================
# DOCLING GRANITE PARSER (local VLM + regex — our production parser)
# ============================================================================

_docling_parser = None  # Lazy singleton


def _get_docling_parser():
    """Lazy-init the DoclingVLMParser singleton."""
    global _docling_parser
    if _docling_parser is None:
        from src.services.talent.docling_vlm_parser import DoclingVLMParser
        _docling_parser = DoclingVLMParser()
    return _docling_parser


async def parse_resume_with_docling(
    file_bytes: bytes,
    filename: str,
) -> Tuple[Dict[str, Any], float]:
    """
    Run resume through our production Docling Granite 258M parser.

    Returns (parsed_dict, latency_seconds) — same interface as
    parse_resume_with_model so the evaluation loop stays uniform.
    """
    parser = _get_docling_parser()

    start = time.time()
    try:
        parsed_resume = await parser.parse_resume(file_bytes, filename)
        latency = time.time() - start

        # Convert ParsedResume pydantic model → dict for eval comparison
        result_dict = {}
        result_dict["full_name"] = parsed_resume.full_name
        result_dict["email"] = parsed_resume.email
        result_dict["phone"] = parsed_resume.phone
        result_dict["location"] = parsed_resume.location
        result_dict["linkedin_url"] = parsed_resume.linkedin_url
        result_dict["github_url"] = parsed_resume.github_url
        result_dict["current_title"] = parsed_resume.current_title
        result_dict["current_company"] = parsed_resume.current_company
        result_dict["summary"] = parsed_resume.summary
        result_dict["skills"] = parsed_resume.skills or []
        result_dict["certifications"] = parsed_resume.certifications or []
        result_dict["experience"] = [
            {
                "title": exp.title,
                "company": exp.company,
                "start_date": exp.start_date,
                "end_date": exp.end_date,
                "duration_months": exp.duration_months,
                "description": exp.description,
                "achievements": exp.achievements or [],
            }
            for exp in (parsed_resume.experience or [])
        ]
        result_dict["education"] = [
            {
                "degree": edu.degree,
                "field_of_study": edu.field_of_study,
                "school": edu.school,
                "graduation_year": edu.graduation_year,
            }
            for edu in (parsed_resume.education or [])
        ]

        # Flag if docling reported low confidence
        if parsed_resume.parse_confidence < 0.3:
            result_dict["_quality_flags"] = parsed_resume.quality_flags

        return result_dict, latency

    except Exception as e:
        latency = time.time() - start
        return {"_error": f"Docling error: {e}"}, latency


# ============================================================================
# HYBRID: PDF text extraction (PyMuPDF) + LLM structured extraction
# ============================================================================

def pdf_to_text(file_bytes: bytes) -> str:
    """
    Extract plain text from PDF using PyMuPDF.
    Lightweight — no ML models, no VLM, no memory overhead.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF (fitz) is required. Install with: pip install PyMuPDF")

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        pages.append(page.get_text())
    doc.close()
    return "\n\n".join(pages)


async def parse_resume_with_text_llm(
    file_bytes: bytes,
    filename: str,
    openai_api_key: str,
    llm_model: str = "gpt-4o-mini",
) -> Tuple[Dict[str, Any], float]:
    """
    Hybrid approach: PyMuPDF extracts text from PDF, then an LLM
    extracts structured data from that plain text (no images needed).

    This tests whether the LLM needs to SEE page images, or if
    plain extracted text is sufficient for accurate parsing.

    Returns (parsed_dict, total_latency_seconds).
    """
    from openai import AsyncOpenAI

    total_start = time.time()

    # Step 1: Extract text from PDF (lightweight, instant)
    try:
        resume_text = pdf_to_text(file_bytes)
    except Exception as e:
        return {"_error": f"PDF text extraction failed: {e}"}, time.time() - total_start

    if not resume_text or len(resume_text.strip()) < 50:
        return {"_error": "PDF text extraction produced empty/minimal text"}, time.time() - total_start

    # Step 2: Send plain text to LLM for structured extraction
    client = AsyncOpenAI(api_key=openai_api_key)

    llm_prompt = (
        EXTRACTION_PROMPT
        + "\n\n--- RESUME TEXT (extracted from PDF) ---\n\n"
        + resume_text
    )

    try:
        token_kwargs = {}
        if llm_model.startswith("gpt-5"):
            token_kwargs["max_completion_tokens"] = 16384
        else:
            token_kwargs["max_tokens"] = 8192

        response = await client.chat.completions.create(
            model=llm_model,
            messages=[{"role": "user", "content": llm_prompt}],
            temperature=0.0,
            **token_kwargs,
        )
        total_latency = time.time() - total_start

        raw_text = response.choices[0].message.content or ""
        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            raw_text = re.sub(r'^```\w*\n?', '', raw_text)
            raw_text = re.sub(r'\n?```$', '', raw_text)

        parsed = json.loads(raw_text)
        return parsed, total_latency

    except json.JSONDecodeError as e:
        return {"_error": f"JSON parse error: {e}", "_raw": raw_text[:500]}, time.time() - total_start
    except Exception as e:
        return {"_error": str(e)}, time.time() - total_start


# ============================================================================
# GROUND TRUTH LOADING
# ============================================================================

def load_ground_truth(gt_path: Path) -> Dict[str, GroundTruth]:
    """Load ground truth JSON (either synthetic or greenhouse format)."""
    if not gt_path.exists():
        print(f"WARNING: Ground truth not found: {gt_path}")
        return {}

    with open(gt_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    ground_truth = {}
    for entry in data:
        meta = entry.get("_meta", {})
        filename = meta.get("filename", entry.get("filename", ""))
        if not filename:
            continue

        gt = GroundTruth(
            filename=filename,
            full_name=entry.get("full_name"),
            email=entry.get("email"),
            phone=entry.get("phone"),
            location=entry.get("location"),
            linkedin_url=entry.get("linkedin_url"),
            github_url=entry.get("github_url"),
            current_title=entry.get("current_title"),
            current_company=entry.get("current_company"),
            summary=entry.get("summary"),
            skills=entry.get("skills", []),
            certifications=entry.get("certifications", []),
            experience=entry.get("experience", []),
            education=entry.get("education", []),
            meta=meta,
        )
        ground_truth[gt.filename] = gt

    return ground_truth


# ============================================================================
# AGGREGATION
# ============================================================================

def compute_summary(model: str, results: List[ResumeEvalResult]) -> ModelSummary:
    """Roll up per-resume results into aggregate model summary."""
    s = ModelSummary(model=model, total=len(results))
    ok = [r for r in results if r.error is None]
    s.successful = len(ok)
    s.failed = s.total - s.successful
    if not ok:
        return s

    n = len(ok)
    s.avg_full_name = sum(r.full_name_score for r in ok) / n
    s.avg_email = sum(r.email_score for r in ok) / n
    s.avg_phone = sum(r.phone_score for r in ok) / n
    s.avg_location = sum(r.location_score for r in ok) / n
    s.avg_linkedin_url = sum(r.linkedin_url_score for r in ok) / n
    s.avg_github_url = sum(r.github_url_score for r in ok) / n
    s.avg_current_title = sum(r.current_title_score for r in ok) / n
    s.avg_current_company = sum(r.current_company_score for r in ok) / n
    s.avg_summary = sum(r.summary_score for r in ok) / n

    s.avg_skills_precision = sum(r.skills_precision for r in ok) / n
    s.avg_skills_recall = sum(r.skills_recall for r in ok) / n
    s.avg_skills_f1 = sum(r.skills_f1 for r in ok) / n
    s.avg_skills_count = sum(r.skills_extracted for r in ok) / n
    s.avg_certs_f1 = sum(r.certs_f1 for r in ok) / n

    s.avg_exp_overall = sum(r.exp_overall_score for r in ok) / n
    s.avg_exp_count = sum(r.exp_count_extracted for r in ok) / n
    s.avg_edu_overall = sum(r.edu_overall_score for r in ok) / n
    s.avg_edu_count = sum(r.edu_count_extracted for r in ok) / n

    s.avg_contact_score = sum(r.contact_score for r in ok) / n
    s.avg_list_score = sum(r.list_score for r in ok) / n
    s.avg_structured_score = sum(r.structured_score for r in ok) / n
    s.avg_overall_score = sum(r.overall_score for r in ok) / n

    s.avg_latency = sum(r.latency_seconds for r in ok) / n

    # Cost estimate
    # Vision models (image tokens): GPT-5.2 ~$1.75/M in, GPT-4o ~$2.50/M in
    # Text-only models: GPT-4o-mini ~$0.15/M in, $0.60/M out
    # Hybrid (docling+LLM): Docling is free, LLM sees text only (much cheaper)
    # Docling alone: free (local)
    output_tokens = n * 600
    if model == "docling":
        s.est_cost = 0.0
    elif model.startswith("text+"):
        # Hybrid: text-only input (avg ~2000 tokens/resume text), no image tokens
        text_input_tokens = n * 2000
        llm_part = model.split("+", 1)[1]
        if llm_part == "gpt-4o-mini":
            s.est_cost = (text_input_tokens / 1e6) * 0.15 + (output_tokens / 1e6) * 0.60
        elif llm_part.startswith("gpt-5"):
            s.est_cost = (text_input_tokens / 1e6) * 1.75 + (output_tokens / 1e6) * 14.0
        else:
            s.est_cost = (text_input_tokens / 1e6) * 2.50 + (output_tokens / 1e6) * 10.0
    elif model.startswith("gpt-5"):
        avg_pages = 2
        input_tokens = n * avg_pages * 800
        s.est_cost = (input_tokens / 1e6) * 1.75 + (output_tokens / 1e6) * 14.0
    elif model == "gpt-4o-mini":
        avg_pages = 2
        input_tokens = n * avg_pages * 800
        s.est_cost = (input_tokens / 1e6) * 0.15 + (output_tokens / 1e6) * 0.60
    else:
        avg_pages = 2
        input_tokens = n * avg_pages * 800
        s.est_cost = (input_tokens / 1e6) * 2.50 + (output_tokens / 1e6) * 10.0

    return s


def build_comparison(summaries: Dict[str, ModelSummary]) -> Dict[str, Any]:
    """Head-to-head comparison between two models."""
    models = list(summaries.keys())
    if len(models) < 2:
        return {"note": "Need 2 models for head-to-head"}
    a, b = summaries[models[0]], summaries[models[1]]

    def winner(val_a, val_b, higher_is_better=True):
        if higher_is_better:
            return models[0] if val_a >= val_b else models[1]
        return models[0] if val_a <= val_b else models[1]

    def delta(va, vb):
        d = va - vb
        return f"{'+' if d >= 0 else ''}{d:.3f}"

    fields = {
        "overall_score": (a.avg_overall_score, b.avg_overall_score, True),
        "contact_score": (a.avg_contact_score, b.avg_contact_score, True),
        "skills_f1": (a.avg_skills_f1, b.avg_skills_f1, True),
        "skills_recall": (a.avg_skills_recall, b.avg_skills_recall, True),
        "certs_f1": (a.avg_certs_f1, b.avg_certs_f1, True),
        "exp_overall": (a.avg_exp_overall, b.avg_exp_overall, True),
        "edu_overall": (a.avg_edu_overall, b.avg_edu_overall, True),
        "latency": (a.avg_latency, b.avg_latency, False),
    }

    comparison = {"models": models}
    for metric, (va, vb, higher) in fields.items():
        comparison[f"winner_{metric}"] = winner(va, vb, higher)
        comparison[f"delta_{metric}"] = delta(va, vb)

    return comparison


# ============================================================================
# EXPERIMENT RUNNER
# ============================================================================

async def run_experiment(
    models: List[str],
    resume_dir: Path,
    ground_truth_path: Path,
    limit: Optional[int] = None,
    openai_api_key: Optional[str] = None,
    include_greenhouse: bool = False,
) -> Dict[str, Any]:
    """Run the full evaluation experiment."""
    api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")

    print(f"\n{'=' * 72}")
    print(f"  RESUME PARSING MODEL EVALUATION")
    print(f"  Target Schema: ParsedResume (src/models/talent_analysis.py)")
    print(f"  Models: {' vs '.join(models)}")
    print(f"{'=' * 72}\n")

    # Load ground truth
    ground_truth = load_ground_truth(ground_truth_path)
    print(f"Loaded {len(ground_truth)} ground truth records from {ground_truth_path.name}")

    # Find matching PDFs
    resume_files: List[Tuple[Path, GroundTruth, str]] = []
    for gt_filename, gt in ground_truth.items():
        pdf_path = resume_dir / gt_filename
        if pdf_path.exists():
            resume_files.append((pdf_path, gt, "synthetic"))

    # Add greenhouse real resumes
    gh_dir = resume_dir / "greenhouse_real"
    if include_greenhouse and gh_dir.exists():
        gh_gt_path = gh_dir / "greenhouse_ground_truth.json"
        if gh_gt_path.exists():
            gh_gt = load_ground_truth(gh_gt_path)
            gh_count = 0
            for gt_filename, gt in gh_gt.items():
                pdf_path = gh_dir / gt_filename
                if pdf_path.exists():
                    resume_files.append((pdf_path, gt, "greenhouse"))
                    gh_count += 1
            print(f"Added {gh_count} real Greenhouse resumes")

    if not resume_files:
        print(f"ERROR: No resume files found matching ground truth in {resume_dir}")
        sys.exit(1)

    if limit:
        resume_files = resume_files[:limit]

    # Source breakdown
    source_counts: Dict[str, int] = {}
    for _, _, src in resume_files:
        source_counts[src] = source_counts.get(src, 0) + 1
    src_str = ", ".join(f"{c} {s}" for s, c in source_counts.items())
    print(f"Eval set: {len(resume_files)} resumes ({src_str})\n")

    # Run evaluations
    all_results: Dict[str, List[ResumeEvalResult]] = {m: [] for m in models}

    # Check if any model needs the OpenAI API
    openai_models = [m for m in models if m != "docling"]
    if openai_models and not api_key:
        print("ERROR: OPENAI_API_KEY required for GPT / text+LLM models")
        sys.exit(1)

    for idx, (pdf_path, gt, source) in enumerate(resume_files, 1):
        tag = f" [{source}]" if source != "synthetic" else ""
        print(f"[{idx}/{len(resume_files)}] {pdf_path.name}{tag}")

        with open(pdf_path, 'rb') as f:
            file_bytes = f.read()

        for model in models:
            try:
                if model == "docling":
                    parsed, latency = await parse_resume_with_docling(
                        file_bytes, pdf_path.name
                    )
                elif model.startswith("text+"):
                    # Hybrid: PDF text extraction → LLM structured extraction
                    llm_part = model.split("+", 1)[1]  # e.g. "gpt-4o-mini"
                    parsed, latency = await parse_resume_with_text_llm(
                        file_bytes, pdf_path.name, api_key, llm_model=llm_part
                    )
                else:
                    parsed, latency = await parse_resume_with_model(
                        file_bytes, pdf_path.name, model, api_key
                    )

                if "_error" in parsed:
                    result = ResumeEvalResult(
                        filename=gt.filename, model=model, source=source,
                        error=parsed["_error"], latency_seconds=latency,
                    )
                    print(f"  {model}: ERROR — {parsed['_error'][:80]}")
                else:
                    result = evaluate_resume(parsed, gt, model, source, latency)
                    print(
                        f"  {model}: overall={result.overall_score:.2f} "
                        f"contact={result.contact_score:.2f} "
                        f"skills_f1={result.skills_f1:.2f}({result.skills_matched}/{result.skills_expected}) "
                        f"exp={result.exp_overall_score:.2f}({result.exp_count_extracted}/{result.exp_count_expected}) "
                        f"edu={result.edu_overall_score:.2f}({result.edu_count_extracted}/{result.edu_count_expected}) "
                        f"{latency:.1f}s"
                    )

            except Exception as e:
                result = ResumeEvalResult(
                    filename=gt.filename, model=model, source=source,
                    error=str(e), latency_seconds=0.0,
                )
                print(f"  {model}: EXCEPTION — {str(e)[:80]}")

            all_results[model].append(result)

    # ── Print summaries ──
    print(f"\n{'=' * 72}")
    print(f"  RESULTS SUMMARY")
    print(f"{'=' * 72}")

    summaries = {}
    for model in models:
        s = compute_summary(model, all_results[model])
        summaries[model] = s

        print(f"\n  ── {model} ──")
        print(f"  Success / Total:         {s.successful} / {s.total}")
        print(f"  ┌─ Contact Fields ────────────────────────")
        print(f"  │  full_name:      {s.avg_full_name:.3f}")
        print(f"  │  email:          {s.avg_email:.3f}")
        print(f"  │  phone:          {s.avg_phone:.3f}")
        print(f"  │  location:       {s.avg_location:.3f}")
        print(f"  │  linkedin_url:   {s.avg_linkedin_url:.3f}")
        print(f"  │  github_url:     {s.avg_github_url:.3f}")
        print(f"  │  current_title:  {s.avg_current_title:.3f}")
        print(f"  │  current_company:{s.avg_current_company:.3f}")
        print(f"  │  summary:        {s.avg_summary:.3f}")
        print(f"  │  AVG CONTACT:    {s.avg_contact_score:.3f}")
        print(f"  ├─ Skills ────────────────────────────────")
        print(f"  │  precision:      {s.avg_skills_precision:.3f}")
        print(f"  │  recall:         {s.avg_skills_recall:.3f}")
        print(f"  │  F1:             {s.avg_skills_f1:.3f}")
        print(f"  │  avg extracted:  {s.avg_skills_count:.1f}")
        print(f"  ├─ Certifications ────────────────────────")
        print(f"  │  F1:             {s.avg_certs_f1:.3f}")
        print(f"  ├─ Experience ────────────────────────────")
        print(f"  │  overall:        {s.avg_exp_overall:.3f}")
        print(f"  │  avg entries:    {s.avg_exp_count:.1f}")
        print(f"  ├─ Education ─────────────────────────────")
        print(f"  │  overall:        {s.avg_edu_overall:.3f}")
        print(f"  │  avg entries:    {s.avg_edu_count:.1f}")
        print(f"  ├─ Composites ────────────────────────────")
        print(f"  │  contact:        {s.avg_contact_score:.3f}")
        print(f"  │  list (skills+certs): {s.avg_list_score:.3f}")
        print(f"  │  structured (exp+edu): {s.avg_structured_score:.3f}")
        print(f"  │  ★ OVERALL:      {s.avg_overall_score:.3f}")
        print(f"  └─ Performance ───────────────────────────")
        print(f"     avg latency:    {s.avg_latency:.1f}s")
        print(f"     est cost:       ${s.est_cost:.4f}")

    # Leaderboard
    if len(models) >= 2:
        print(f"\n  ── LEADERBOARD ──")
        ranked = sorted(summaries.values(), key=lambda s: s.avg_overall_score, reverse=True)
        metrics = [
            ("Overall", "avg_overall_score"),
            ("Contact", "avg_contact_score"),
            ("Skills F1", "avg_skills_f1"),
            ("Certs F1", "avg_certs_f1"),
            ("Experience", "avg_exp_overall"),
            ("Education", "avg_edu_overall"),
        ]
        # Header
        header = f"  {'Metric':<16s}"
        for r in ranked:
            header += f"  {r.model:>14s}"
        print(header)
        print(f"  {'─' * 16}" + f"  {'─' * 14}" * len(ranked))

        for label, attr in metrics:
            row = f"  {label:<16s}"
            values = [getattr(r, attr) for r in ranked]
            best = max(values)
            for r in ranked:
                v = getattr(r, attr)
                marker = " ★" if v == best and len(ranked) > 1 else "  "
                row += f"  {v:>11.3f}{marker}"
            print(row)

        # Latency (lower is better)
        row = f"  {'Latency (s)':<16s}"
        latencies = [r.avg_latency for r in ranked]
        best_lat = min(latencies) if latencies else 0
        for r in ranked:
            marker = " ★" if r.avg_latency == best_lat and len(ranked) > 1 else "  "
            row += f"  {r.avg_latency:>11.1f}{marker}"
        print(row)

        # Cost (lower is better)
        row = f"  {'Est. Cost ($)':<16s}"
        costs = [r.est_cost for r in ranked]
        best_cost = min(costs) if costs else 0
        for r in ranked:
            marker = " ★" if r.est_cost == best_cost and len(ranked) > 1 else "  "
            row += f"  {r.est_cost:>11.4f}{marker}"
        print(row)

    # Head-to-head (if exactly 2 models, also show delta view)
    if len(models) == 2:
        comp = build_comparison(summaries)
        print(f"\n  ── HEAD-TO-HEAD: {models[0]} vs {models[1]} ──")
        for metric in ["overall_score", "contact_score", "skills_f1", "skills_recall",
                        "certs_f1", "exp_overall", "edu_overall", "latency"]:
            w = comp.get(f"winner_{metric}", "?")
            d = comp.get(f"delta_{metric}", "?")
            print(f"  {metric:20s}  winner: {w:12s}  delta: {d}")

    # Build result dict
    experiment = {
        "experiment_id": f"eval_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "schema": "ParsedResume",
        "models": models,
        "resume_count": len(resume_files),
        "source_counts": source_counts,
        "ground_truth_file": str(ground_truth_path),
        "results": {m: [asdict(r) for r in all_results[m]] for m in models},
        "summaries": {m: asdict(summaries[m]) for m in models},
        "comparison": build_comparison(summaries) if len(models) == 2 else {},
    }
    return experiment


# ============================================================================
# CLI
# ============================================================================

ALL_MODELS = ["gpt-5.2", "gpt-4o", "gpt-4o-mini", "docling", "text+gpt-4o-mini"]


def main():
    parser = argparse.ArgumentParser(
        description="Resume Parsing Eval — ParsedResume Schema "
                    "(GPT-5.2 / GPT-4o / GPT-4o-mini / Docling / Text+LLM hybrid)"
    )
    parser.add_argument("--model", type=str, default=None, action="append",
                        help="Model(s) to evaluate. Repeat for multiple: "
                             "--model gpt-5.2 --model text+gpt-4o-mini. "
                             f"Choices: {', '.join(ALL_MODELS)}. "
                             "Also supports text+gpt-5.2, text+gpt-4o, etc. "
                             "Default: all five.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max resumes to evaluate")
    parser.add_argument("--resume-dir", type=str, default=None,
                        help="Resume PDF directory (default: tests/resumes/)")
    parser.add_argument("--ground-truth", type=str, default=None,
                        help="Ground truth JSON path")
    parser.add_argument("--output", type=str, default=None,
                        help="Save results to JSON file")
    parser.add_argument("--include-greenhouse", action="store_true",
                        help="Include real Greenhouse resumes alongside synthetic")
    parser.add_argument("--greenhouse-only", action="store_true",
                        help="Only evaluate Greenhouse resumes (skip synthetic)")
    parser.add_argument("--merge-results", type=str, default=None,
                        help="Path to existing results JSON — merge new model "
                             "results into it instead of starting fresh")

    args = parser.parse_args()

    models = args.model if args.model else ALL_MODELS

    project_root = Path(__file__).parent.parent
    resume_dir = Path(args.resume_dir) if args.resume_dir else project_root / "tests" / "resumes"
    gt_path = (Path(args.ground_truth) if args.ground_truth
               else resume_dir / "eval_ground_truth.json")

    include_greenhouse = args.include_greenhouse or args.greenhouse_only

    if args.greenhouse_only:
        gh_dir = resume_dir / "greenhouse_real"
        if not gh_dir.exists():
            print(f"ERROR: Greenhouse dir not found: {gh_dir}")
            sys.exit(1)
        resume_dir = gh_dir
        gt_path = gh_dir / "greenhouse_ground_truth.json"
        include_greenhouse = False

    if not resume_dir.exists():
        print(f"ERROR: Resume directory not found: {resume_dir}")
        sys.exit(1)

    experiment = asyncio.run(
        run_experiment(
            models=models,
            resume_dir=resume_dir,
            ground_truth_path=gt_path,
            limit=args.limit,
            include_greenhouse=include_greenhouse,
        )
    )

    # Merge with existing results if requested
    if args.merge_results:
        merge_path = Path(args.merge_results)
        if merge_path.exists():
            with open(merge_path, 'r') as f:
                existing = json.load(f)

            # Merge model results and summaries
            for model_name in experiment["results"]:
                existing["results"][model_name] = experiment["results"][model_name]
                existing["summaries"][model_name] = experiment["summaries"][model_name]

            # Update metadata
            existing["models"] = list(existing["results"].keys())
            existing["merged_at"] = datetime.now(timezone.utc).isoformat()
            existing["source_counts"] = experiment.get("source_counts", existing.get("source_counts", {}))

            experiment = existing
            print(f"\nMerged new results into {merge_path.name}")
            print(f"Combined models: {', '.join(existing['models'])}")

    # Save results
    if args.merge_results:
        out_path = Path(args.merge_results)
    elif args.output:
        out_path = Path(args.output)
    else:
        out_dir = project_root / "eval_results"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"{experiment['experiment_id']}.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump(experiment, f, indent=2, default=str)

    print(f"\nResults saved to: {out_path}")
    print(f"Experiment ID: {experiment.get('experiment_id', 'merged')}")


if __name__ == "__main__":
    main()
