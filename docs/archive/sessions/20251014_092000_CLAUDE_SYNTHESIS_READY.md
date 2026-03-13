# Claude 3.5 Sonnet - Synthesis Agent Configuration
**Date**: October 14, 2025, 09:20 AM PST

## Model Configuration

### Synthesis Agent
- **Provider**: Anthropic
- **Model**: `claude-3-5-sonnet-20241022`
- **Purpose**: Generate executive summaries and sourcing recommendations
- **API Key**: ✅ Configured and validated

### Diagnostic Agent
- **Provider**: OpenAI
- **Model**: `gpt-4o-mini`
- **Purpose**: Analyze job requirements and prioritize attributes
- **API Key**: ✅ Configured and validated

## Why Claude 3.5 Sonnet?

### Strengths for Synthesis
1. **Superior Writing Quality**: Best-in-class for executive summaries
2. **Deep Analysis**: Excellent at synthesizing complex patterns
3. **Contextual Understanding**: Handles 100+ candidates effectively
4. **Long-form Output**: Produces detailed, nuanced reports
5. **Cost-Effective**: ~$0.05 per analysis (200k context, 2k output)

### Synthesis Tasks
1. **Executive Summary**: High-level analysis of candidate pool
2. **Pattern Recognition**: Identify key trends across candidates
3. **Sourcing Recommendations**: Actionable recruiting advice
4. **Top 3 Selection**: Choose best candidates with detailed reasoning
5. **Comparative Analysis**: Explain why top candidates stand out

## Model Performance

### Expected Output Quality
```markdown
**Executive Summary**
Based on the analysis of 50 applicants and 50 market candidates, we've identified 
three exceptional candidates who demonstrate strong alignment with the ML Engineer 
role requirements. The candidate pool shows a consistent pattern of PyTorch expertise 
combined with startup experience, suggesting these are the most critical attributes...

**Key Patterns**
1. Top candidates universally have 5-7 years of ML experience
2. PyTorch expertise correlates strongly with overall fit scores
3. Startup experience (Series A-C) is a strong predictor of success...

**Sourcing Recommendations**
1. Target candidates with ML roles at Series B/C startups
2. Prioritize PyTorch over TensorFlow in job descriptions...
```

### Typical Response Time
- **Diagnostic** (GPT-4o-mini): 15-20 seconds
- **Synthesis** (Claude Sonnet): 20-30 seconds
- **Total LLM time**: ~40 seconds out of 60-75 second total analysis

## API Configuration

### Environment Variables
```bash
ANTHROPIC_API_KEY=sk-ant-api...  # ✅ Configured
OPENAI_API_KEY=sk-...            # ✅ Configured
```

### Rate Limits
- **Anthropic**: 50 requests/minute (Tier 2+)
- **OpenAI**: 10,000 requests/minute (Tier 3+)
- **Our Usage**: 2 LLM calls per analysis (well within limits)

### Cost Per Analysis
```
GPT-4o-mini Diagnostic:
  - Input: ~5k tokens (job description + baseline)
  - Output: ~1k tokens (diagnostic report)
  - Cost: ~$0.01

Claude Sonnet Synthesis:
  - Input: ~20k tokens (all candidate scores + diagnostic)
  - Output: ~2k tokens (synthesis report)
  - Cost: ~$0.05

Total LLM Cost: ~$0.06 per analysis
(+ $0.50 for PDL API = $0.56 total)
```

## Integration in Orchestrator

### Stage 7: Synthesis
```python
synthesis_agent = SynthesisAgentService(
    customer_id=self.customer_id,
    user_id=self.user_id,
    llm_provider="anthropic",
    llm_model="claude-3-5-sonnet-20241022"
)

synthesis_input = SynthesisInput(
    diagnostic_report=diagnostic,
    applicant_scores=applicant_scores,      # Up to 50
    market_scores=market_scores,            # Up to 50
    top_overall_count=3
)

synthesis_report = await asyncio.to_thread(
    synthesis_agent.synthesize,
    synthesis_input
)
```

### Provenance Tracking
```python
provenance_chains.append(ProvenanceChain(
    step_name="synthesis",
    step_description="Generated executive summary and sourcing recommendations",
    service_used="SynthesisAgentService",
    llm_provider="anthropic",
    llm_model="claude-3-5-sonnet-20241022",
    timestamp=stage7_start,
    duration_seconds=(datetime.now(timezone.utc) - stage7_start).total_seconds()
))
```

## Error Handling

### Retry Logic
- 3 retries with exponential backoff
- Handled by CrewAI framework
- Falls back to structured output on consistent failures

### Timeout
- 60 second timeout per LLM call
- Analysis continues even if synthesis fails (degraded mode)

## Testing Strategy

### Unit Tests
- Mock API responses
- Verify Pydantic model validation
- Test prompt construction

### Integration Tests
- Call real API with test data
- Verify response structure
- Check output quality

### End-to-End Test
- **Best test**: Run full analysis and review synthesis output
- Verify all sections present (summary, patterns, recommendations)
- Check Top 3 selection logic

## Quality Metrics

### What Makes Good Synthesis
1. ✅ **Concise**: 200-500 word executive summary
2. ✅ **Specific**: Mentions actual skills and patterns from data
3. ✅ **Actionable**: Clear sourcing recommendations
4. ✅ **Justified**: Explains why top 3 were selected
5. ✅ **Comparative**: Highlights differences between applicants and market

### What We Avoid
- ❌ Generic boilerplate
- ❌ Hallucinated information
- ❌ Vague recommendations
- ❌ Missing top candidate explanations

## Monitoring

### Log What Matters
```python
logger.info(
    "stage_7_synthesis_complete",
    analysis_id=analysis_id,
    top_candidate_count=len(synthesis_report.top_overall_candidate_ids),
    summary_length=len(synthesis_report.executive_summary),
    pattern_count=len(synthesis_report.key_patterns),
    recommendation_count=len(synthesis_report.sourcing_recommendations)
)
```

### Watch For
- Synthesis duration > 45 seconds (API slow)
- Empty recommendations (model issue)
- Top 3 not including market candidates (bias issue)

## Status

✅ **Claude 3.5 Sonnet is configured and ready**
✅ **API key validated**
✅ **Will be tested in full analysis run**

**Next**: Run complete end-to-end analysis to see Claude in action! 🚀

## Expected First Run Output

When you run your first analysis, look for these log entries:

```
stage_7_synthesis_start
  analysis_id: ml_ta_abc123

calling_claude_api
  model: claude-3-5-sonnet-20241022
  input_tokens: ~20000
  max_output_tokens: 4000

stage_7_synthesis_complete
  duration_seconds: 25.3
  top_candidate_count: 3
  summary_length: 437
```

The synthesis will be the final step before returning results to the frontend!


