# ML Talent Intelligence Schema Audit & Fixes
**Date**: October 18, 2025, 9:00 PM PST

## Executive Summary

Comprehensive audit of all prompts vs Pydantic schemas across the 7-stage ML Talent Intelligence pipeline. Found **critical mismatches** in Stage 2 (Diagnostic) and Stage 7 (Synthesis) that would prevent successful completion.

## Issues Found

### ❌ Issue 1: Diagnostic Agent (Stage 2) - **FIXED**
**Status**: Already Fixed
**File**: `src/services/talent/diagnostic_agent.py`

**Mismatch**: Prompt asked for schema with `attribute_priorities`, `key_patterns`, `strategic_insights`, but `DiagnosticReport` model expects `seniority_level`, `ml_competencies`, `required_skills`, etc.

**Fix Applied**: Updated prompt to match `DiagnosticReport` schema exactly.

---

### ❌ Issue 2: Synthesis Agent (Stage 7) - **NEEDS FIX**
**Status**: Critical Issue Found
**File**: `src/services/talent/synthesis_agent.py`

#### Prompt Asks For:
```json
{
  "executive_summary": "string",
  "top_overall_candidate_ids": [
    {
      "candidate_id": "string",
      "candidate_name": "string",
      "source": "APPLICANT|MARKET",
      "overall_score": float,
      "rank": int
    }
  ],
  "top_candidate_explanations": {
    "candidate_id_1": "explanation",
    "candidate_id_2": "explanation"
  },
  "pattern_insights": [
    {
      "pattern_type": "...",
      "description": "...",
      "supporting_evidence": [...],
      "strength": "STRONG|MODERATE|WEAK"
    }
  ],
  "comparative_analysis": {
    "applicant_pool_summary": "...",
    "market_pool_summary": "...",
    "key_differences": [...]
  },
  "recommendations": [
    {
      "priority": "HIGH|MEDIUM|LOW",
      "action": "...",
      "rationale": "..."
    }
  ]
}
```

#### SynthesisReport Model Expects:
```python
class SynthesisReport(BaseModel):
    executive_summary: str  # ✅ MATCHES
    key_insights: List[str]  # ❌ MISSING FROM PROMPT
    pattern_highlights: List[PatternInsight]  # ❌ DIFFERENT NAME
    recommendations: List[str]  # ❌ DIFFERENT STRUCTURE (string vs object)
    concerns: List[str]  # ❌ MISSING FROM PROMPT
    confidence_assessment: str  # ❌ MISSING FROM PROMPT
```

#### PatternInsight Model:
```python
class PatternInsight(BaseModel):
    pattern_type: PatternType  # Enum: CAREER_PATH, SKILL_COMBO, etc.
    description: str
    frequency: int
    example_candidate_ids: List[str]
```

**Problem**: Massive mismatch! The prompt's `pattern_insights` has `supporting_evidence` and `strength`, but `PatternInsight` expects `frequency` and `example_candidate_ids`.

---

### ✅ Issue 3: Scoring Engine - **VERIFIED OK**
**Status**: No issues found
**Files**: `src/services/talent/scoring_engine.py`, `src/models/talent_analysis.py`

The `MultiDimensionalScoringEngine.score()` method:
- **Input**: Takes `ParsedResume`, `DiagnosticReport`, `BaselineProfile`
- **Output**: Returns `CandidateScore` with all required fields
- **Verification**: Schema matches perfectly

---

### ✅ Issue 4: Resume Parser - **VERIFIED OK**
**Status**: No issues found
**Files**: `src/services/talent/docling_vlm_parser.py`

The `DoclingVLMParser.parse()` method outputs `ParsedResume` with correct schema.

---

### ⚠️ Issue 5: Orchestrator Usage - **NEEDS VERIFICATION**
**Status**: Need to verify field names in orchestrator

The orchestrator needs to correctly access fields from all models. Will verify after fixing Synthesis Agent.

---

## Fixes Required

### Fix 1: Update Synthesis Agent Prompt ✅ (Priority: CRITICAL)

**Action**: Update `src/services/talent/synthesis_agent.py` prompt to match `SynthesisReport` schema.

**New Prompt Schema**:
```json
{
  "executive_summary": "string (2-3 paragraphs)",
  "key_insights": [
    "insight 1",
    "insight 2",
    "insight 3"
  ],
  "pattern_highlights": [
    {
      "pattern_type": "CAREER_PATH|SKILL_COMBO|COMPANY_CLUSTER|EXPERIENCE_LEVEL",
      "description": "string",
      "frequency": int (how many candidates show this pattern),
      "example_candidate_ids": ["candidate_id_1", "candidate_id_2"]
    }
  ],
  "recommendations": [
    "recommendation 1",
    "recommendation 2"
  ],
  "concerns": [
    "concern 1 (optional)",
    "concern 2"
  ],
  "confidence_assessment": "string (overall confidence in analysis)"
}
```

### Fix 2: Handle Top Candidates Selection

**Problem**: The orchestrator needs to select top overall candidates, but `SynthesisReport` doesn't include this data.

**Options**:
1. **Option A (Recommended)**: Handle top candidate selection in orchestrator BEFORE calling synthesis agent
2. **Option B**: Add `top_candidates` field to `SynthesisReport` model
3. **Option C**: Create separate method for top candidate selection

**Recommendation**: Use Option A - The orchestrator should:
1. Combine `applicant_scores` and `market_scores`
2. Sort by `overall_score`
3. Take top N (e.g., 3)
4. Pass these to synthesis agent as context (not output)
5. Synthesis agent focuses on insights, patterns, and recommendations

---

## Implementation Plan

### Step 1: Fix Synthesis Agent Prompt ✅
- Update prompt schema to match `SynthesisReport`
- Remove `top_overall_candidate_ids` and `top_candidate_explanations`
- Update `pattern_insights` to match `PatternInsight` model
- Change `recommendations` from objects to simple strings
- Add `key_insights`, `concerns`, `confidence_assessment`

### Step 2: Update Orchestrator ✅
- Add logic to select top overall candidates BEFORE synthesis
- Pass top candidates as context to synthesis agent
- Store top candidates separately in `TalentAnalysisResult`

### Step 3: Test Complete Flow ✅
- Submit new analysis
- Verify each stage completes successfully
- Check that all fields are populated correctly

---

## Testing Checklist

- [ ] Stage 1: Baseline building completes
- [ ] Stage 2: Diagnostic agent with fixed prompt
- [ ] Stage 3: Resume parsing (50 resumes)
- [ ] Stage 4: Applicant scoring
- [ ] Stage 5: Market search via PDL
- [ ] Stage 6: Market candidate scoring
- [ ] Stage 7: Synthesis with fixed prompt
- [ ] Final result has all required fields
- [ ] Frontend can display results

---

## Notes

### Why These Mismatches Happened
1. Models were likely designed first
2. Prompts were written later without checking models
3. No automated validation between prompts and schemas
4. Different developers may have worked on different parts

### Prevention for Future
1. Generate prompts FROM Pydantic schemas (code generation)
2. Add schema validation tests
3. Document model-to-prompt mapping
4. Use JSON Schema to validate LLM outputs

---

## Status Summary

| Component | Status | Priority |
|-----------|--------|----------|
| Diagnostic Agent | ✅ Fixed | Critical |
| Synthesis Agent | ❌ Needs Fix | Critical |
| Scoring Engine | ✅ OK | - |
| Resume Parser | ✅ OK | - |
| Orchestrator | ⚠️ Verify | High |

---

**Next Steps**: Fix Synthesis Agent prompt and update orchestrator logic for top candidate selection.


