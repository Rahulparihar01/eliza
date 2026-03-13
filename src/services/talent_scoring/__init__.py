"""
Talent Scoring Services

Multi-dimensional scoring engine for matching candidates against employee baselines.
"""

from .scoring_engine import TalentScoringEngine
from .baseline_builder import BaselineProfileBuilder

__all__ = [
    'TalentScoringEngine',
    'BaselineProfileBuilder',
]

