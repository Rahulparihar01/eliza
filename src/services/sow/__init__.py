"""
SOW (Statement of Work) Generation Service

Provides AI-powered extraction of SOW fields from meeting transcripts
and generation of professional SOW documents.
"""

from .sow_service import SowService, ExtractedAnswer
from .template_parser import TemplateParser, TemplateField
from .transcript_parser import TranscriptParser, Meeting, Utterance
from .mermaid_renderer import MermaidRenderer

__all__ = [
    "SowService",
    "ExtractedAnswer",
    "TemplateParser",
    "TemplateField", 
    "TranscriptParser",
    "Meeting",
    "Utterance",
    "MermaidRenderer",
]
