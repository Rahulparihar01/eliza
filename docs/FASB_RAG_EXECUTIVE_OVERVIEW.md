# FASB Accounting Standards RAG System
## Executive Overview

---

## What It Is

An AI-powered question-answering system for **FASB Accounting Standards Codification (ASC)** - the authoritative source of U.S. Generally Accepted Accounting Principles (GAAP).

Instead of accountants manually searching through thousands of pages of accounting standards, they can **ask questions in plain English** and get accurate, cited answers in seconds.

---

## Business Value

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              BEFORE vs AFTER                                     │
└─────────────────────────────────────────────────────────────────────────────────┘

     BEFORE (Manual Process)                    AFTER (FASB RAG System)
     ─────────────────────────                  ───────────────────────────
     
     Accountant has question                    Accountant has question
            │                                          │
            ▼                                          ▼
     Open FASB Codification                    Type question in chat
            │                                          │
            ▼                                          ▼
     Search by topic/keyword                   AI retrieves relevant passages
            │                                          │
            ▼                                          ▼
     Read multiple sections                    AI synthesizes answer with
     (10-30 minutes)                           citations (10-30 seconds)
            │                                          │
            ▼                                          ▼
     Cross-reference guidance                  Verified citations link to
     (another 10-30 minutes)                   exact page numbers
            │                                          │
            ▼                                          ▼
     Draft response/memo                       Copy authoritative answer
     
     ──────────────────────                    ──────────────────────────
     Total: 30-60+ minutes                     Total: Under 1 minute
```

---

## How It Works (Simplified)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           USER EXPERIENCE FLOW                                   │
└─────────────────────────────────────────────────────────────────────────────────┘


    ┌─────────────────────────────────────────────────────────────────────────┐
    │  ACCOUNTANT ASKS:                                                        │
    │  "When should revenue be recognized under ASC 606?"                      │
    └─────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │                        FASB RAG SYSTEM                                   │
    │  ┌───────────────────────────────────────────────────────────────────┐  │
    │  │                                                                    │  │
    │  │   1. UNDERSTAND    Interpret the question                         │  │
    │  │         │                                                          │  │
    │  │         ▼                                                          │  │
    │  │   2. SEARCH        Find relevant ASC passages from                │  │
    │  │         │          thousands of indexed standards                  │  │
    │  │         ▼                                                          │  │
    │  │   3. RANK          Select the most relevant passages              │  │
    │  │         │          (typically 6-8 sources)                         │  │
    │  │         ▼                                                          │  │
    │  │   4. SYNTHESIZE    Generate clear, accurate answer                │  │
    │  │                    with proper citations                          │  │
    │  │                                                                    │  │
    │  └───────────────────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │  SYSTEM RESPONDS:                                                        │
    │                                                                          │
    │  "Under ASC 606, revenue should be recognized when (or as) a company    │
    │   satisfies a performance obligation by transferring a promised good    │
    │   or service to a customer [1]. The core principle requires an entity  │
    │   to recognize revenue to depict the transfer of goods or services     │
    │   in an amount that reflects the consideration to which the entity     │
    │   expects to be entitled [2]..."                                        │
    │                                                                          │
    │  Sources:                                                                │
    │  [1] ASC 606-10-25-1 (Page 70)                                          │
    │  [2] ASC 606-10-10-2 (Page 12)                                          │
    │  [3] ASC 606-10-25-23 (Page 85)                                         │
    └─────────────────────────────────────────────────────────────────────────┘
```

---

## System Architecture (High Level)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          FASB RAG ARCHITECTURE                                   │
└─────────────────────────────────────────────────────────────────────────────────┘


                         ┌──────────────────────────┐
                         │      USER INTERFACE      │
                         │    (Web Application)     │
                         └────────────┬─────────────┘
                                      │
                                      ▼
                         ┌──────────────────────────┐
                         │     ELIZA PLATFORM       │
                         │    (Backend Service)     │
                         └────────────┬─────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
         ┌──────────────────┐ ┌──────────────┐ ┌──────────────────┐
         │   AWS OPENSEARCH │ │   OPENAI     │ │  PDF DOCUMENTS   │
         │   (Knowledge     │ │   (AI Brain) │ │  (Verification)  │
         │    Base)         │ │              │ │                  │
         └──────────────────┘ └──────────────┘ └──────────────────┘
                 │                   │                   │
                 │                   │                   │
         ┌───────┴───────┐   ┌──────┴──────┐   ┌───────┴───────┐
         │ All FASB      │   │ Understands │   │ Original PDFs │
         │ standards     │   │ questions & │   │ for citation  │
         │ pre-indexed   │   │ generates   │   │ validation    │
         │ & searchable  │   │ answers     │   │               │
         └───────────────┘   └─────────────┘   └───────────────┘
```

---

## Quality Assurance: Citation Validation

Every answer includes citations that can be **automatically verified**:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CITATION VALIDATION                                      │
└─────────────────────────────────────────────────────────────────────────────────┘

    Answer includes: "Revenue is recognized when performance obligation 
                      is satisfied [1]"
    
    Citation [1] = ASC 606-10-25-1, Page 70
                           │
                           ▼
    ┌─────────────────────────────────────────────────────────────────────────┐
    │  VALIDATION PROCESS:                                                     │
    │                                                                          │
    │  1. System retrieves PDF page 70 from ASC 606 document                  │
    │                                                                          │
    │  2. AI visually scans the page                                          │
    │                                                                          │
    │  3. Confirms: "Yes, this text appears on page 70"                       │
    │                                                                          │
    │  4. Result: ✅ CITATION VERIFIED                                         │
    │                                                                          │
    └─────────────────────────────────────────────────────────────────────────┘
    
    This ensures answers are TRACEABLE and AUDITABLE
```

---

## Key Metrics & Evaluation

The system includes built-in evaluation to measure quality:

| Metric | What It Measures | Target |
|--------|------------------|--------|
| **Answer Accuracy** | Is the answer factually correct? | > 90% |
| **Faithfulness** | Does the answer only use information from sources? | > 95% |
| **Citation Accuracy** | Do citations point to correct pages? | > 90% |
| **Response Time** | How fast are answers generated? | < 10 seconds |

---

## Use Cases

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            WHO BENEFITS                                          │
└─────────────────────────────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────────────────────┐
    │  ACCOUNTANTS & AUDITORS                                                  │
    │  • Quick answers to technical accounting questions                       │
    │  • Reduced research time from hours to minutes                          │
    │  • Consistent, authoritative responses                                  │
    └─────────────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────────────┐
    │  FINANCE TEAMS                                                           │
    │  • Revenue recognition guidance                                          │
    │  • Lease accounting questions                                           │
    │  • New standard implementation support                                  │
    └─────────────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────────────┐
    │  TRAINING & ONBOARDING                                                   │
    │  • Junior staff can get instant guidance                                │
    │  • Reduces senior staff interruptions                                   │
    │  • Accelerates learning curve                                           │
    └─────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack Summary

| Component | Technology | Purpose |
|-----------|------------|---------|
| Knowledge Base | AWS OpenSearch Serverless | Stores & searches all FASB standards |
| AI Engine | OpenAI GPT-4 | Understands questions, generates answers |
| Embeddings | OpenAI text-embedding-3-large | Enables semantic search |
| Validation | GPT-4 Vision | Verifies citations against source PDFs |
| Backend | Python / FastAPI | Orchestrates the system |
| Tracking | Langfuse | Monitors quality metrics and LLM observability |

---

## Summary

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           VALUE PROPOSITION                                      │
└─────────────────────────────────────────────────────────────────────────────────┘

    ✅  FASTER      Research reduced from 30-60 minutes to under 1 minute
    
    ✅  ACCURATE    AI-generated answers with verifiable citations
    
    ✅  AUDITABLE   Every answer links to exact page numbers in source docs
    
    ✅  SCALABLE    Works for any accounting question across all ASC topics
    
    ✅  MEASURABLE  Built-in evaluation tracks accuracy and quality
```

---

*For technical details, see: `docs/FASB_DATA_INGESTION_FLOW.md`*
