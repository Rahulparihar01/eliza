# BI Pipeline with Connectivity Checks - Flow Diagram

## Complete Flow Visualization

```
┌──────────────────────────────────────────────────────────────────────┐
│                         USER SUBMITS QUESTION                         │
│                    "How many employees do we have?"                   │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     API ENDPOINT VALIDATION                           │
│  • Authentication check                                               │
│  • Create question record                                             │
│  • Enqueue Celery task                                                │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    CELERY TASK: process_bi_question                   │
│  [Status: PENDING → ENRICHING]                                        │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
╔══════════════════════════════════════════════════════════════════════╗
║                 STAGE 1: TASK ENRICHMENT FLOW (CrewAI)               ║
║                                                                       ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Step 1: Intent Analysis                           │  [10%]       ║
║  │  • Classify question type                          │              ║
║  │  • Extract entities and keywords                   │              ║
║  │  • Determine complexity                            │              ║
║  │  • Identify required data sources                  │              ║
║  └────────────────────────────────────────────────────┘              ║
║                          ↓                                            ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Step 2: Context Enrichment                        │              ║
║  │  • Add business context                            │              ║
║  │  • Identify relevant metrics                       │              ║
║  │  • Suggest refinements                             │              ║
║  └────────────────────────────────────────────────────┘              ║
║                          ↓                                            ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Step 3: Prompt Generation                         │              ║
║  │  • Create enriched prompt                          │              ║
║  │  • Define output format                            │              ║
║  │  • Set validation criteria                         │              ║
║  └────────────────────────────────────────────────────┘              ║
║                                                                       ║
║  Output: EnrichedPrompt object saved to database                     ║
╚═══════════════════════════════════════════════════════════════════════╝
                                 │
                                 ▼
                    [Status: ENRICHING → ANALYZING]
                                 │
                                 ▼
╔══════════════════════════════════════════════════════════════════════╗
║           🆕 DATA SOURCE CONNECTIVITY CHECKS                         ║
║                                                                       ║
║  📡 Telemetry: "Verifying data source connectivity..."    [15%]      ║
║                                                                       ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Check 1: HR Database (PostgreSQL)                 │              ║
║  │  ─────────────────────────────────────────────────  │              ║
║  │  • Test database connection                        │              ║
║  │  • Check connection pool health                    │              ║
║  │  • Verify customer has employee data               │              ║
║  │                                                     │              ║
║  │  ✅ Result: healthy                                │              ║
║  │  ✅ Has customer data: True                        │              ║
║  │  ✅ Pool status: 4/5 connections available         │              ║
║  └────────────────────────────────────────────────────┘              ║
║                                                                       ║
║  📡 Telemetry: "✓ HR Database connected"               [18%]         ║
║                                                                       ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Check 2: Vector Index (FAISS)                     │              ║
║  │  ─────────────────────────────────────────────────  │              ║
║  │  • Verify index file exists                        │              ║
║  │  • Verify mapping file exists                      │              ║
║  │  • Load index metadata                             │              ║
║  │  • Verify customer has documents                   │              ║
║  │                                                     │              ║
║  │  ✅ Result: healthy                                │              ║
║  │  ✅ Total vectors: 42                              │              ║
║  │  ✅ Has customer data: True                        │              ║
║  └────────────────────────────────────────────────────┘              ║
║                                                                       ║
║  📡 Telemetry: "✓ Document Search connected"           [18%]         ║
║                                                                       ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Validation: Check Critical Resources              │              ║
║  │  ─────────────────────────────────────────────────  │              ║
║  │  Vector Index Status: ✅ HEALTHY (continue)        │              ║
║  │  HR Database Status:  ✅ HEALTHY (continue)        │              ║
║  └────────────────────────────────────────────────────┘              ║
║                                                                       ║
║  ✅ All checks passed - proceeding to data analysis                  ║
╚═══════════════════════════════════════════════════════════════════════╝
                                 │
                                 ▼
╔══════════════════════════════════════════════════════════════════════╗
║                STAGE 2: DATA ANALYSIS FLOW (CrewAI)                  ║
║                                                                       ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Step 1: Data Retrieval                            │  [25%]       ║
║  │  ───────────────────────────────────────────────    │              ║
║  │  Agent: Data Retrieval Specialist                  │              ║
║  │                                                     │              ║
║  │  Tools Available:                                  │              ║
║  │    • HRDatabaseTool (verified ✅)                  │              ║
║  │    • DocumentSearchTool (verified ✅)              │              ║
║  │                                                     │              ║
║  │  📡 "Retrieving data from HR database and docs..." │              ║
║  │                                                     │              ║
║  │  Actions:                                          │              ║
║  │    1. Call DocumentSearchTool("employees")         │              ║
║  │       → Returns 3 relevant document chunks         │              ║
║  │    2. Call HRDatabaseTool({"query_type":          │              ║
║  │       "employees", "filters": {}})                 │              ║
║  │       → Returns 15 employee records                │              ║
║  │                                                     │              ║
║  │  Output: DataRetrievalResult                       │              ║
║  └────────────────────────────────────────────────────┘              ║
║                                                                       ║
║  📡 Telemetry: "Data retrieval completed"               [50%]        ║
║                          ↓                                            ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Step 2: Data Analysis                             │  [75%]       ║
║  │  ───────────────────────────────────────────────    │              ║
║  │  Agent: Business Intelligence Analyst              │              ║
║  │                                                     │              ║
║  │  📡 "Analyzing data and generating insights..."    │              ║
║  │                                                     │              ║
║  │  Actions:                                          │              ║
║  │    1. Analyze retrieved data                       │              ║
║  │    2. Generate executive summary                   │              ║
║  │    3. Extract key findings                         │              ║
║  │    4. Create recommendations                       │              ║
║  │                                                     │              ║
║  │  Output: AnalysisResult                            │              ║
║  │    • Executive Summary                             │              ║
║  │    • Key Findings (5 items)                        │              ║
║  │    • Recommendations (3 items)                     │              ║
║  │    • Confidence: 0.85                              │              ║
║  └────────────────────────────────────────────────────┘              ║
║                                                                       ║
║  📡 Telemetry: "Analysis completed successfully"        [100%]       ║
╚═══════════════════════════════════════════════════════════════════════╝
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   SAVE RESULTS TO DATABASE                            │
│  • AnalysisResult record created                                     │
│  • Question status updated: ANALYZING → COMPLETED                    │
│  • Response available via API                                        │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       RETURN TO USER                                  │
│  {                                                                    │
│    "success": true,                                                   │
│    "question_id": "q_12345",                                          │
│    "status": "completed",                                             │
│    "analysis": {                                                      │
│      "executive_summary": "Your company has 15 employees...",         │
│      "key_findings": [...],                                           │
│      "recommendations": [...]                                         │
│    }                                                                  │
│  }                                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Failure Scenario: Vector Index Unavailable

```
┌──────────────────────────────────────────────────────────────────────┐
│                    USER SUBMITS QUESTION                              │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
         [ ... Task Enrichment Flow Completes ... ]
                                 │
                                 ▼
╔══════════════════════════════════════════════════════════════════════╗
║           🆕 DATA SOURCE CONNECTIVITY CHECKS                         ║
║                                                                       ║
║  📡 "Verifying data source connectivity..."                [15%]     ║
║                                                                       ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Check 1: HR Database                              │              ║
║  │  ✅ Result: healthy                                │              ║
║  └────────────────────────────────────────────────────┘              ║
║  📡 "✓ HR Database connected"                          [18%]         ║
║                                                                       ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Check 2: Vector Index                             │              ║
║  │  ❌ Result: unhealthy                              │              ║
║  │  ❌ Error: Index file not found                    │              ║
║  └────────────────────────────────────────────────────┘              ║
║                                                                       ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Validation: CRITICAL FAILURE DETECTED             │              ║
║  │  ─────────────────────────────────────────────────  │              ║
║  │  Vector Index is REQUIRED for all queries          │              ║
║  │  ❌ FAIL FAST - Do not proceed to analysis         │              ║
║  └────────────────────────────────────────────────────┘              ║
║                                                                       ║
║  ❌ Connectivity check failed - aborting pipeline                    ║
╚═══════════════════════════════════════════════════════════════════════╝
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     UPDATE QUESTION STATUS                            │
│  Status: ANALYZING → FAILED                                           │
│  Error: "Vector index connectivity check failed: Index file not       │
│         found. Document search is required for all queries."          │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       RETURN ERROR TO USER                            │
│  {                                                                    │
│    "success": false,                                                  │
│    "error": "Vector index connectivity check failed: Index file not   │
│              found. Document search is required for all queries."     │
│  }                                                                    │
│                                                                       │
│  💡 User Action: Contact administrator to restore vector index       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Failure Scenario: HR Database Unavailable (Non-Critical)

```
┌──────────────────────────────────────────────────────────────────────┐
│                    USER SUBMITS QUESTION                              │
│              "What's in our latest benefits document?"                │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
         [ ... Task Enrichment Flow Completes ... ]
                                 │
                                 ▼
╔══════════════════════════════════════════════════════════════════════╗
║           🆕 DATA SOURCE CONNECTIVITY CHECKS                         ║
║                                                                       ║
║  📡 "Verifying data source connectivity..."                [15%]     ║
║                                                                       ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Check 1: HR Database                              │              ║
║  │  ❌ Result: unhealthy                              │              ║
║  │  ⚠️  Error: Connection timeout                     │              ║
║  └────────────────────────────────────────────────────┘              ║
║  📡 "⚠ HR Database unavailable: Connection timeout"   [18%]         ║
║                                                                       ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Check 2: Vector Index                             │              ║
║  │  ✅ Result: healthy                                │              ║
║  └────────────────────────────────────────────────────┘              ║
║  📡 "✓ Document Search connected"                      [18%]         ║
║                                                                       ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Validation: NON-CRITICAL WARNING                  │              ║
║  │  ─────────────────────────────────────────────────  │              ║
║  │  HR Database is optional for document queries      │              ║
║  │  ✅ CONTINUE with degraded functionality           │              ║
║  └────────────────────────────────────────────────────┘              ║
║                                                                       ║
║  ⚠️  Warning logged - continuing with documents only                 ║
╚═══════════════════════════════════════════════════════════════════════╝
                                 │
                                 ▼
╔══════════════════════════════════════════════════════════════════════╗
║                  DATA ANALYSIS FLOW (Degraded Mode)                  ║
║                                                                       ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Data Retrieval Agent                              │              ║
║  │  • DocumentSearchTool: ✅ Available                │              ║
║  │  • HRDatabaseTool: ⚠️  Unavailable (will fail)    │              ║
║  │                                                     │              ║
║  │  Action: Use DocumentSearchTool only               │              ║
║  │  Result: 5 relevant document chunks found          │              ║
║  └────────────────────────────────────────────────────┘              ║
║                          ↓                                            ║
║  ┌────────────────────────────────────────────────────┐              ║
║  │  Data Analysis Agent                               │              ║
║  │  • Analyzes document data only                     │              ║
║  │  • Notes: "Analysis based on documents only"       │              ║
║  └────────────────────────────────────────────────────┘              ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       SUCCESS (Partial)                               │
│  Status: COMPLETED                                                    │
│  Note: "Analysis based on documents only (HR database unavailable)"  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Legend

```
┌────┐   Regular process step
└────┘

╔════╗   New connectivity check stage (highlighted)
╚════╝

│      Flow direction
↓

✅     Success / Healthy
❌     Failure / Error
⚠️      Warning / Degraded
📡     Telemetry event sent to user
[50%]  Progress percentage
```

---

## Key Observations

### Before Connectivity Checks

- ❌ Failures discovered 30-60 seconds into execution
- ❌ Cryptic error messages
- ❌ No early warning system
- ❌ Poor user experience

### After Connectivity Checks

- ✅ Failures discovered in 0.3 seconds
- ✅ Clear, actionable error messages
- ✅ Real-time connectivity status
- ✅ Excellent user experience
- ✅ Graceful degradation when possible

---

**Version**: 1.0  
**Last Updated**: October 4, 2025

