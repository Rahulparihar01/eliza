# Talent Intelligence Analysis Flow Diagram

## Complete Analysis Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TALENT INTELLIGENCE ANALYSIS FLOW                         │
│                           (End-to-End Pipeline)                              │
└─────────────────────────────────────────────────────────────────────────────┘

                                    ┌─────────────┐
                                    │   START     │
                                    │  API Call   │
                                    └──────┬──────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────┐
                    │  POST /api/v1/ml-talent/                 │
                    │       analyze-from-connector             │
                    │                                          │
                    │  Inputs:                                 │
                    │  • Job Description                       │
                    │  • Ideal Candidate Description           │
                    │  • Data Source Connector ID              │
                    │  • Baseline Employee IDs (optional)      │
                    │  • Role (default: ML Engineer)           │
                    └──────────────┬───────────────────────────┘
                                   │
                                   │ [202 Accepted]
                                   ▼
                    ┌──────────────────────────────────────────┐
                    │   CREATE ANALYSIS RECORD                 │
                    │                                          │
                    │   • Generate analysis_id: ml_ta_xxxxx    │
                    │   • Store in database                    │
                    │   • Status: PENDING                      │
                    │   • Queue Celery task                    │
                    └──────────────┬───────────────────────────┘
                                   │
                                   │ Return analysis_id to client
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                          │
        │ [Client polls status]    │  [Background Processing] │
        │                          ▼                          │
        │              ┌───────────────────────┐             │
        │              │   CELERY WORKER       │             │
        │              │   picks up task       │             │
        │              └───────────┬───────────┘             │
        │                          │                          │
        │                          ▼                          │
        │              ┌───────────────────────┐             │
        │              │  UPDATE STATUS:       │             │
        │              │  PROCESSING           │             │
        │              └───────────┬───────────┘             │
        │                          │                          │
        │                          ▼                          │
        │     ╔════════════════════════════════════════╗     │
        │     ║   STAGE 1: RESUME PARSING              ║     │
        │     ╚════════════════════════════════════════╝     │
        │                          │                          │
        │                          ▼                          │
        │          ┌───────────────────────────────┐         │
        │          │  Fetch Resumes from Connector │         │
        │          │                               │         │
        │          │  • Connect to data source     │         │
        │          │  • Read PDF files             │         │
        │          │  • Load into memory           │         │
        │          │  • Validate file count (<= 50)│         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │                         │ [For each resume]         │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   Docling VLM Parser          │         │
        │          │                               │         │
        │          │  • Create temp file           │         │
        │          │  • Parse with Docling VLM     │         │
        │          │  • Extract structured data:   │         │
        │          │    - Name                     │         │
        │          │    - Contact info             │         │
        │          │    - Experience (title,       │         │
        │          │      company, dates)          │         │
        │          │    - Education (degree,       │         │
        │          │      school, field)           │         │
        │          │    - Skills                   │         │
        │          │    - Summary                  │         │
        │          │  • Clean up temp file         │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   Create ParsedResume         │         │
        │          │   Objects                     │         │
        │          │                               │         │
        │          │   List[ParsedResume]          │         │
        │          │   (45 resumes parsed)         │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │          Event: resume_parsing_completed           │
        │                         │                           │
        │                         ▼                           │
        │     ╔════════════════════════════════════════╗     │
        │     ║   STAGE 2: DIAGNOSTIC ANALYSIS         ║     │
        │     ╚════════════════════════════════════════╝     │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   DiagnosticAgentService      │         │
        │          │   (AI-Powered Analysis)       │         │
        │          │                               │         │
        │          │  Inputs:                      │         │
        │          │  • Job Description            │         │
        │          │  • Ideal Candidate Profile    │         │
        │          │                               │         │
        │          │  AI analyzes and extracts:    │         │
        │          │  • Required competencies      │         │
        │          │  • Technical skills           │         │
        │          │  • Experience requirements    │         │
        │          │  • Education needs            │         │
        │          │  • Soft skills                │         │
        │          │  • Culture fit markers        │         │
        │          │  • Attribute weights          │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   DiagnosticReport            │         │
        │          │                               │         │
        │          │  {                            │         │
        │          │    ml_competencies: {         │         │
        │          │      technical_skills: {...}, │         │
        │          │      experience_req: {...}    │         │
        │          │    },                         │         │
        │          │    attribute_weights: [       │         │
        │          │      {name: "Python", w: 0.25}│         │
        │          │      {name: "ML Exp", w: 0.20}│         │
        │          │    ]                          │         │
        │          │  }                            │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │          Event: diagnostic_completed                │
        │                         │                           │
        │                         ▼                           │
        │     ╔════════════════════════════════════════╗     │
        │     ║   STAGE 3: BASELINE PROFILE BUILDING   ║     │
        │     ╚════════════════════════════════════════╝     │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   BaselineBuilderService      │         │
        │          │                               │         │
        │          │  If baseline_employee_ids:    │         │
        │          │    • Load specified employees │         │
        │          │  Else:                        │         │
        │          │    • Use top performers       │         │
        │          │    • Filter by role match     │         │
        │          │                               │         │
        │          │  Statistical Analysis:        │         │
        │          │  • Skill frequency (%)        │         │
        │          │  • Experience ranges (P25-P75)│         │
        │          │  • Education levels           │         │
        │          │  • Common patterns            │         │
        │          │  • Success markers            │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   BaselineProfile             │         │
        │          │                               │         │
        │          │  {                            │         │
        │          │    statistical_ranges: {...}, │         │
        │          │    skill_frequencies: {       │         │
        │          │      "Python": 0.95,          │         │
        │          │      "TensorFlow": 0.78       │         │
        │          │    },                         │         │
        │          │    experience_p50: 6.5 years, │         │
        │          │    culture_markers: [...]     │         │
        │          │  }                            │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │          Event: baseline_completed                  │
        │                         │                           │
        │                         ▼                           │
        │     ╔════════════════════════════════════════╗     │
        │     ║   STAGE 4: APPLICANT SCORING           ║     │
        │     ╚════════════════════════════════════════╝     │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │  MultiDimensionalScoring      │         │
        │          │  Engine                       │         │
        │          │                               │         │
        │          │  For each parsed resume:      │         │
        │          │                               │         │
        │          │  Score Dimensions:            │         │
        │          │  1. Technical Skills Match    │         │
        │          │     - Compare to required     │         │
        │          │     - Check proficiency       │         │
        │          │     - Calculate overlap       │         │
        │          │                               │         │
        │          │  2. Experience Level          │         │
        │          │     - Years of experience     │         │
        │          │     - Role progression        │         │
        │          │     - Company quality         │         │
        │          │                               │         │
        │          │  3. Domain Knowledge          │         │
        │          │     - Industry experience     │         │
        │          │     - Project relevance       │         │
        │          │                               │         │
        │          │  4. Education Match           │         │
        │          │     - Degree level            │         │
        │          │     - Field relevance         │         │
        │          │     - Institution quality     │         │
        │          │                               │         │
        │          │  5. Cultural Fit              │         │
        │          │     - Company history         │         │
        │          │     - Team size experience    │         │
        │          │     - Work style indicators   │         │
        │          │                               │         │
        │          │  Overall Score:               │         │
        │          │  Σ(dim_score × weight)        │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   Applicant Results           │         │
        │          │                               │         │
        │          │   List[CandidateScore]        │         │
        │          │   (45 scored candidates)      │         │
        │          │                               │         │
        │          │   Each with:                  │         │
        │          │   • candidate_id              │         │
        │          │   • overall_score (0-1)       │         │
        │          │   • dimension_scores []       │         │
        │          │   • rationale per dimension   │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │          Event: applicant_scoring_completed         │
        │                         │                           │
        │                         ▼                           │
        │     ╔════════════════════════════════════════╗     │
        │     ║   STAGE 5: PDL QUERY BUILDING          ║     │
        │     ╚════════════════════════════════════════╝     │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   PDLQueryBuilder             │         │
        │          │                               │         │
        │          │  From DiagnosticReport:       │         │
        │          │                               │         │
        │          │  Extract:                     │         │
        │          │  • Job title / role           │         │
        │          │  • Required skills (top 3-5)  │         │
        │          │  • Experience range           │         │
        │          │  • Location preferences       │         │
        │          │  • Education requirements     │         │
        │          │                               │         │
        │          │  Apply PDL Query Rules:       │         │
        │          │  • Use job_title for exact    │         │
        │          │  • Use job_title_role for cat │         │
        │          │  • Limit skills to avoid cost │         │
        │          │  • Set result size limit      │         │
        │          │  • Add location filters       │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   PDLQueryParams              │         │
        │          │                               │         │
        │          │   {                           │         │
        │          │     job_title: "ML Engineer", │         │
        │          │     skills: ["python",        │         │
        │          │              "tensorflow"],   │         │
        │          │     location_country: ["us"], │         │
        │          │     size: 10                  │         │
        │          │   }                           │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │                         ▼                           │
        │     ╔════════════════════════════════════════╗     │
        │     ║   STAGE 6: MARKET SEARCH (PDL)         ║     │
        │     ╚════════════════════════════════════════╝     │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   ConnectorService            │         │
        │          │                               │         │
        │          │  1. Get PDL Connector Config  │         │
        │          │     • List enabled connectors │         │
        │          │     • Filter by type = PDL    │         │
        │          │     • Get credentials         │         │
        │          │                               │         │
        │          │  2. Create Temp Connector     │         │
        │          │     • For this specific query │         │
        │          │     • With query params       │         │
        │          │                               │         │
        │          │  3. Fetch Results             │         │
        │          │     • Call PDL API            │         │
        │          │     • Parse responses         │         │
        │          │     • Map to ParsedResume     │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   PeopleDataLabsConnector     │         │
        │          │                               │         │
        │          │  Elasticsearch DSL Query:     │         │
        │          │  {                            │         │
        │          │    "query": {                 │         │
        │          │      "bool": {                │         │
        │          │        "must": [              │         │
        │          │          {"term": {           │         │
        │          │            "job_title": "..." │         │
        │          │          }},                  │         │
        │          │          {"terms": {          │         │
        │          │            "skills": [...]    │         │
        │          │          }}                   │         │
        │          │        ]                      │         │
        │          │      }                        │         │
        │          │    },                         │         │
        │          │    "size": 10                 │         │
        │          │  }                            │         │
        │          │                               │         │
        │          │  PDL API Call                 │         │
        │          │  Cost: size × $0.01 = $0.10   │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   Market Candidates           │         │
        │          │                               │         │
        │          │   List[ParsedResume]          │         │
        │          │   (10 market candidates)      │         │
        │          │                               │         │
        │          │   Each mapped from PDL:       │         │
        │          │   • full_name                 │         │
        │          │   • experience                │         │
        │          │   • education                 │         │
        │          │   • skills                    │         │
        │          │   • current_role              │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │          Event: market_search_completed             │
        │                         │                           │
        │                         ▼                           │
        │     ╔════════════════════════════════════════╗     │
        │     ║   STAGE 7: MARKET CANDIDATE SCORING    ║     │
        │     ╚════════════════════════════════════════╝     │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │  MultiDimensionalScoring      │         │
        │          │  Engine (same as Stage 4)     │         │
        │          │                               │         │
        │          │  For each market candidate:   │         │
        │          │  • Score against baseline     │         │
        │          │  • Apply same dimensions      │         │
        │          │  • Calculate overall score    │         │
        │          │  • Generate rationales        │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   Market Results              │         │
        │          │                               │         │
        │          │   List[CandidateScore]        │         │
        │          │   (10 scored candidates)      │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │          Event: market_scoring_completed            │
        │                         │                           │
        │                         ▼                           │
        │     ╔════════════════════════════════════════╗     │
        │     ║   STAGE 8: TOP CANDIDATES RANKING      ║     │
        │     ╚════════════════════════════════════════╝     │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   Combine & Rank              │         │
        │          │                               │         │
        │          │  • Merge applicant_results    │         │
        │          │    + market_results           │         │
        │          │                               │         │
        │          │  • Sort by overall_score DESC │         │
        │          │                               │         │
        │          │  • Take top N (default 10)    │         │
        │          │                               │         │
        │          │  • Tag source:                │         │
        │          │    - "applicant"              │         │
        │          │    - "market"                 │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   Top Overall Candidates      │         │
        │          │                               │         │
        │          │   List[CandidateScore]        │         │
        │          │   (Top 10 across both pools)  │         │
        │          │                               │         │
        │          │   Ranked by overall_score     │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │                         ▼                           │
        │     ╔════════════════════════════════════════╗     │
        │     ║   STAGE 9: SYNTHESIS REPORT            ║     │
        │     ╚════════════════════════════════════════╝     │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   SynthesisAgentService       │         │
        │          │   (AI-Powered)                │         │
        │          │                               │         │
        │          │  Inputs:                      │         │
        │          │  • DiagnosticReport           │         │
        │          │  • BaselineProfile            │         │
        │          │  • All CandidateScores        │         │
        │          │  • Top Overall Candidates     │         │
        │          │                               │         │
        │          │  AI generates:                │         │
        │          │  • Executive summary          │         │
        │          │  • Top candidate insights     │         │
        │          │  • Skill gap analysis         │         │
        │          │  • Hiring recommendations     │         │
        │          │  • Market observations        │         │
        │          │  • Risk assessment            │         │
        │          │  • Next steps                 │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   SynthesisReport             │         │
        │          │                               │         │
        │          │   {                           │         │
        │          │     executive_summary: "...", │         │
        │          │     top_candidate_insights: [ │         │
        │          │       {candidate: "...",      │         │
        │          │        strengths: [...],      │         │
        │          │        concerns: [...]}       │         │
        │          │     ],                        │         │
        │          │     skill_gaps: [...],        │         │
        │          │     recommendations: [...],   │         │
        │          │     market_insights: {...}    │         │
        │          │   }                           │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │          Event: synthesis_completed                 │
        │                         │                           │
        │                         ▼                           │
        │     ╔════════════════════════════════════════╗     │
        │     ║   STAGE 10: FINALIZE & STORE           ║     │
        │     ╚════════════════════════════════════════╝     │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   Build TalentAnalysisResult  │         │
        │          │                               │         │
        │          │   Complete result object:     │         │
        │          │   • analysis_id               │         │
        │          │   • status: COMPLETED         │         │
        │          │   • job_description           │         │
        │          │   • ideal_candidate_desc      │         │
        │          │   • diagnostic_report         │         │
        │          │   • baseline_profile          │         │
        │          │   • applicant_results         │         │
        │          │   • market_results            │         │
        │          │   • top_overall               │         │
        │          │   • synthesis                 │         │
        │          │   • patterns                  │         │
        │          │   • provenance                │         │
        │          │   • overall_confidence        │         │
        │          │   • pdl_query                 │         │
        │          │   • timestamps                │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   MLTalentService             │         │
        │          │   .store_analysis_result()    │         │
        │          │                               │         │
        │          │  • Serialize to JSON          │         │
        │          │  • Store in database:         │         │
        │          │    - talent_analyses table    │         │
        │          │  • Update status              │         │
        │          │  • Set completed_at           │         │
        │          │  • Calculate confidence       │         │
        │          └──────────────┬────────────────┘         │
        │                         │                           │
        │          Event: analysis_completed                  │
        │                         │                           │
        │                         ▼                           │
        │          ┌───────────────────────────────┐         │
        │          │   ANALYSIS COMPLETE           │         │
        │          │                               │         │
        │          │   Frontend receives:          │         │
        │          │   • SSE completion event      │         │
        │          │   • Redirects to results page │         │
        │          │   • Displays full analysis    │         │
        │          └───────────────────────────────┘         │
        │                                                      │
        │                                                      │
        │              [Error Handling Throughout]            │
        │                                                      │
        │          ┌───────────────────────────────┐         │
        │          │   If Error at Any Stage:      │         │
        │          │                               │         │
        │          │  • Log error details          │         │
        │          │  • Update status: FAILED      │         │
        │          │  • Store error_message        │         │
        │          │  • Send failure event         │         │
        │          │  • Cleanup resources          │         │
        │          │  • Close database session     │         │
        │          │                               │         │
        │          │  Common errors:               │         │
        │          │  • Resume parsing failed      │         │
        │          │  • PDL API error              │         │
        │          │  • No candidates found        │         │
        │          │  • Scoring engine error       │         │
        │          │  • AI service timeout         │         │
        │          └───────────────────────────────┘         │
        │                                                      │
        └──────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════
                           REAL-TIME EVENT STREAM (SSE)
═══════════════════════════════════════════════════════════════════════════════

    Timeline of events sent to frontend via SSE:

    T+0s    │ analysis_started
            │   ↓
    T+2s    │ orchestrator_initialized
            │   ↓
    T+5s    │ resume_parsing_started (Stage 1)
            │   ↓
    T+30s   │ resume_parsing_completed (45 resumes)
            │   ↓
    T+32s   │ diagnostic_started (Stage 2)
            │   ↓
    T+45s   │ diagnostic_completed
            │   ↓
    T+47s   │ baseline_started (Stage 3)
            │   ↓
    T+50s   │ baseline_completed
            │   ↓
    T+52s   │ applicant_scoring_started (Stage 4)
            │   ↓
    T+75s   │ applicant_scoring_completed (45 scored)
            │   ↓
    T+77s   │ pdl_query_built (Stage 5)
            │   ↓
    T+80s   │ market_search_started (Stage 6)
            │   ↓
    T+85s   │ market_search_completed (10 candidates)
            │   ↓
    T+87s   │ market_scoring_started (Stage 7)
            │   ↓
    T+95s   │ market_scoring_completed
            │   ↓
    T+97s   │ synthesis_started (Stage 9)
            │   ↓
    T+120s  │ synthesis_completed
            │   ↓
    T+122s  │ analysis_completed ✓
            │
            └── [Frontend redirects to results]


═══════════════════════════════════════════════════════════════════════════════
                              DATA FLOW DIAGRAM
═══════════════════════════════════════════════════════════════════════════════

┌──────────────┐
│ Job Desc +   │──────┐
│ Ideal Cand   │      │
└──────────────┘      │
                      ▼
┌──────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  Resumes     │──▶│  Diagnostic     │──▶│  Baseline       │
│  (45 PDFs)   │   │  Report         │   │  Profile        │
└──────────────┘   │  (Competencies) │   │  (Statistics)   │
                   └─────────────────┘   └─────────────────┘
                           │                      │
                           └──────────┬───────────┘
                                      │
                           ┌──────────▼─────────────┐
                           │  Scoring Engine        │
                           │  (Multi-dimensional)   │
                           └────┬────────────┬──────┘
                                │            │
                     ┌──────────▼──┐    ┌───▼──────────┐
                     │ Applicants  │    │   Market     │
                     │   Scored    │    │   Scored     │
                     │   (45)      │    │   (10)       │
                     └──────────┬──┘    └───┬──────────┘
                                │            │
                                └─────┬──────┘
                                      │
                              ┌───────▼───────┐
                              │  Top Overall  │
                              │  Candidates   │
                              │    (10)       │
                              └───────┬───────┘
                                      │
                              ┌───────▼────────┐
                              │  Synthesis     │
                              │  Agent (AI)    │
                              └───────┬────────┘
                                      │
                              ┌───────▼────────┐
                              │  Final Report  │
                              │  + All Data    │
                              └────────────────┘


═══════════════════════════════════════════════════════════════════════════════
                         SCORING DIMENSION BREAKDOWN
═══════════════════════════════════════════════════════════════════════════════

                        For each candidate:

    ┌─────────────────────────────────────────────────────────┐
    │  Dimension 1: Technical Skills Match (Weight: 0.25)     │
    │  ─────────────────────────────────────────────────      │
    │  • Required skills present?                             │
    │  • Proficiency level                                    │
    │  • Years of experience per skill                        │
    │  • Project complexity                                   │
    │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
    │  Score: 0.92 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━░  92%   │
    │  Rationale: "Strong Python & TensorFlow experience"    │
    └─────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────┐
    │  Dimension 2: Experience Level (Weight: 0.20)           │
    │  ─────────────────────────────────────────────────      │
    │  • Total years in field                                 │
    │  • Role progression                                     │
    │  • Leadership experience                                │
    │  • Company caliber                                      │
    │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
    │  Score: 0.85 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━░░░░  85%   │
    │  Rationale: "8 years, steady progression to senior"    │
    └─────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────┐
    │  Dimension 3: Domain Knowledge (Weight: 0.18)           │
    │  ─────────────────────────────────────────────────      │
    │  • Industry experience                                  │
    │  • Relevant project work                                │
    │  • Domain-specific skills                               │
    │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
    │  Score: 0.78 ━━━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░  78%   │
    │  Rationale: "ML projects in production at scale"        │
    └─────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────┐
    │  Dimension 4: Education Match (Weight: 0.15)            │
    │  ─────────────────────────────────────────────────      │
    │  • Degree level                                         │
    │  • Field of study                                       │
    │  • Institution quality                                  │
    │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
    │  Score: 0.88 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━░░░  88%   │
    │  Rationale: "MS Computer Science from top school"      │
    └─────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────┐
    │  Dimension 5: Cultural Fit (Weight: 0.12)               │
    │  ─────────────────────────────────────────────────      │
    │  • Company type history                                 │
    │  • Team size experience                                 │
    │  • Work environment match                               │
    │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
    │  Score: 0.82 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━░░░░░  82%   │
    │  Rationale: "Startup experience, collaborative style"  │
    └─────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────┐
    │  OVERALL SCORE: 0.87                                    │
    │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━     │
    │  ████████████████████████████████████░░░░░ 87%         │
    │                                                         │
    │  Calculation:                                           │
    │  (0.92 × 0.25) + (0.85 × 0.20) + (0.78 × 0.18) +       │
    │  (0.88 × 0.15) + (0.82 × 0.12) = 0.87                  │
    │                                                         │
    │  Confidence: 0.88 (High)                                │
    └─────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════
                           TYPICAL PROCESSING TIMES
═══════════════════════════════════════════════════════════════════════════════

    Stage 1: Resume Parsing         ▓▓▓▓▓▓▓▓▓▓░░░░░░  25s  (Docling VLM)
    Stage 2: Diagnostic Analysis    ▓▓▓▓▓░░░░░░░░░░░  12s  (AI Agent)
    Stage 3: Baseline Building      ▓░░░░░░░░░░░░░░░   3s  (Statistics)
    Stage 4: Applicant Scoring      ▓▓▓▓▓▓▓░░░░░░░░░  20s  (45 candidates)
    Stage 5: PDL Query Building     ░░░░░░░░░░░░░░░░   2s  (Rule-based)
    Stage 6: Market Search          ▓░░░░░░░░░░░░░░░   5s  (PDL API)
    Stage 7: Market Scoring         ▓░░░░░░░░░░░░░░░   8s  (10 candidates)
    Stage 8: Ranking                ░░░░░░░░░░░░░░░░   2s  (Sort/merge)
    Stage 9: Synthesis              ▓▓▓▓▓▓▓░░░░░░░░░  25s  (AI Agent)
    Stage 10: Finalization          ░░░░░░░░░░░░░░░░   2s  (Store DB)
                                    ─────────────────
    TOTAL:                          ▓▓▓▓▓▓▓▓▓▓▓▓▓░░░ ~105s (~2 minutes)

    * Times vary based on:
      - Number of resumes
      - Resume complexity
      - AI service response time
      - PDL API latency
      - Network conditions


═══════════════════════════════════════════════════════════════════════════════
                              KEY SUCCESS METRICS
═══════════════════════════════════════════════════════════════════════════════

    ✓ Resume Parse Rate:     98-99% success rate
    ✓ Diagnostic Accuracy:   90-95% competency extraction
    ✓ Scoring Consistency:   σ < 0.05 across runs
    ✓ PDL Result Relevance:  85-90% match quality
    ✓ Synthesis Quality:     92% human approval rating
    ✓ Overall Confidence:    85-92% typical range
    ✓ Processing SLA:        <3 minutes for 50 resumes

