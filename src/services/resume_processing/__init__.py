"""
Resume Processing Services

Handles resume/CV parsing using Docling and Granite models.
"""

from .docling_parser import DoclingParser
from .resume_service import ResumeService

__all__ = [
    'DoclingParser',
    'ResumeService',
]

