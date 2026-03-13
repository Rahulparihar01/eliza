"""
Talent Intelligence Services

Core services for role-agnostic talent analysis:
- TextLLMParser: Resume parsing via text extraction + LLM (production default)
- DoclingVLMParser: Legacy resume parsing with VLM + regex (deprecated)
- RoleBaselineBuilder: Build baseline profiles from Neo4j for any role type
- MultiDimensionalScoringEngine: Score candidates across dimensions (diagnostic-driven)
- DiagnosticAgentService: LLM agent for analyzing role requirements and prioritizing attributes
- SynthesisAgentService: LLM agent for synthesizing results into comprehensive reports
- PDLQueryBuilder: Build and refine PDL queries
- TalentIntelligenceOrchestrator: Main orchestration flow tying everything together
- PatternExtractor: Extract patterns from top candidates
- ProvenanceGenerator: Generate complete audit trails
"""

from src.services.talent.text_llm_parser import TextLLMParser
from src.services.talent.docling_vlm_parser import DoclingVLMParser
from src.services.talent.ml_engineer_baseline_builder import RoleBaselineBuilder, MLEngineerBaselineBuilder
from src.services.talent.scoring_engine import MultiDimensionalScoringEngine
from src.services.talent.diagnostic_agent import DiagnosticAgentService, DiagnosticInput
from src.services.talent.synthesis_agent import SynthesisAgentService, SynthesisInput
from src.services.talent.pdl_query_builder import (
    PDLQueryBuilder, PDLQueryParams, QueryRefinementFeedback
)
from src.services.talent.orchestrator import (
    TalentIntelligenceOrchestrator, TalentAnalysisRequest
)

__all__ = [
    "TextLLMParser",
    "DoclingVLMParser",
    "RoleBaselineBuilder",
    "MLEngineerBaselineBuilder",  # Backward compat alias
    "MultiDimensionalScoringEngine",
    "DiagnosticAgentService",
    "DiagnosticInput",
    "SynthesisAgentService",
    "SynthesisInput",
    "PDLQueryBuilder",
    "PDLQueryParams",
    "QueryRefinementFeedback",
    "TalentIntelligenceOrchestrator",
    "TalentAnalysisRequest",
]

