# Product Requirements Document
## Clearhaven Portfolio Intelligence Platform

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | Draft |
| **Last Updated** | January 15, 2026 |
| **Product Owner** | TBD |
| **Engineering Lead** | TBD |

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Goals and Non-Goals](#goals-and-non-goals)
4. [Target Users](#target-users)
5. [Product Overview](#product-overview)
6. [Feature 1: Portfolio Intelligence](#feature-1-portfolio-intelligence-holdco-analytics)
7. [Feature 2: Quarterly Metrics Reimagined](#feature-2-quarterly-metrics-reimagined)
8. [User Stories and Flows](#user-stories-and-flows)
9. [Technical Requirements](#technical-requirements)
10. [Dependencies](#dependencies)
11. [Edge Cases and Risk Mitigation](#edge-cases-and-risk-mitigation)
12. [Acceptance Criteria](#acceptance-criteria)
13. [Success Metrics](#success-metrics)
14. [Open Questions](#open-questions)
15. [Appendix](#appendix)

---

## Executive Summary

This document defines the product requirements for **Clearhaven Portfolio Intelligence**, a comprehensive platform enabling private equity holding companies (HoldCos) to unify, query, and analyze data across their critical operational systems—specifically **DealCloud** (deal pipeline and relationships) and **Chronograph** (portfolio monitoring and KPIs).

The platform consists of two interconnected features:

1. **Portfolio Intelligence (HoldCo Analytics)** — An AI-powered chat and query experience that connects DealCloud and Chronograph, enabling natural language queries across previously siloed data sources.

2. **Quarterly Metrics Reimagined** — A modernized submission and context-sharing workflow allowing Portfolio Companies (PortCos) to submit standardized metrics with narrative context, complete with versioning and status management.

Together, these features transform how private equity firms analyze portfolio performance, prepare for board meetings, and maintain alignment between HoldCo and PortCo stakeholders across the entire investment lifecycle.

---

## Problem Statement

### Current State Challenges

Private equity HoldCo teams face significant friction in comprehensively managing and understanding portfolio company performance:

| Challenge | Impact |
|-----------|--------|
| **Disparate Systems** | Data lives in multiple disconnected tools (DealCloud, Chronograph, Excel files, emails), requiring manual aggregation |
| **Inconsistent Data Definitions** | Each PortCo may define KPIs differently (e.g., "ARR" varies by industry), making comparison difficult |
| **Lost Granularity** | Normalization tools "flatten" underlying drivers—product-line detail is lost when rolled up into aggregate metrics |
| **Manual Reconciliation** | Analyst-heavy drilldowns and slow feedback loops, especially during board meeting preparation |
| **Low Adoption** | Existing "insight portals" see poor adoption unless insights appear in familiar workflows with automatic updates |
| **Version Confusion** | No single source of truth for quarterly submissions; email threads and file versions create alignment issues |

### The Opportunity

HoldCo teams need a **single unified experience** to:
- Ask questions across all data sources using natural language
- Drill into underlying drivers without losing context
- Maintain consistent narratives across the investment lifecycle (origination → performance → exit)
- Share a cohesive, versioned view with PortCo stakeholders

---

## Goals and Non-Goals

### Goals

| Priority | Goal |
|----------|------|
| **P0** | Provide an in-app Eliza chat and query experience for HoldCo users to ask cross-source questions spanning DealCloud + Chronograph |
| **P0** | Enable saved queries and templated insights that can be re-run on demand and scheduled for automatic portfolio updates |
| **P0** | Establish a scalable, permissioned foundation supporting quarterly PortCo submissions with narrative context |
| **P1** | Support versioning and clear status tags on submissions (Draft, Shared, Final) without requiring hard approval gates |
| **P1** | Synthesize quarterly submissions with DealCloud and Chronograph data for comprehensive board/LP-ready insights |
| **P2** | Enable scheduled query execution with results delivered in-app |

### Non-Goals (Out of Scope for MVP)

| Item | Rationale |
|------|-----------|
| External MCP connector usage (Claude Desktop, ChatGPT) | Connectors may be reused later; not required for initial value delivery |
| Full automation of PortCo accounting integrations (QuickBooks) | Optional extension; not required for core value proposition |
| Replacement of Chronograph or DealCloud | We enable cross-source intelligence, not system replacement |
| Email/Slack notifications for scheduled insights | Default is in-app; notifications are an optional future enhancement |

---

## Target Users

### Primary Users

#### 1. HoldCo Investment Professionals
- **Role**: Partners, Principals, Associates at the holding company
- **Primary Needs**: 
  - Quick answers to portfolio performance questions
  - Board meeting preparation materials
  - Cross-portfolio trend analysis
  - Deal pipeline correlation with portfolio outcomes
- **Usage Frequency**: Daily to weekly

#### 2. HoldCo Operations Team
- **Role**: Operations partners, CFO office, portfolio management
- **Primary Needs**:
  - Standardized metric collection across PortCos
  - Performance benchmarking
  - LP reporting data aggregation
- **Usage Frequency**: Weekly to monthly (higher during reporting periods)

#### 3. PortCo Operators
- **Role**: CFOs, Controllers, Finance leads at portfolio companies
- **Primary Needs**:
  - Simple, Excel-based metric submission
  - Ability to provide narrative context
  - Clear status visibility with HoldCo
- **Usage Frequency**: Quarterly (submission periods)

### Secondary Users

#### 4. System Administrators
- **Role**: IT/Operations staff responsible for system configuration
- **Primary Needs**: 
  - Connector configuration and monitoring
  - Permission management
  - Data quality oversight

---

## Product Overview

### System Architecture (Conceptual)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ELIZA PLATFORM                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────┐ │
│  │  DealCloud  │    │ Chronograph │    │   Quarterly Submissions     │ │
│  │  Connector  │    │  Connector  │    │  (Excel + Context Upload)   │ │
│  └──────┬──────┘    └──────┬──────┘    └─────────────┬───────────────┘ │
│         │                  │                         │                  │
│         └──────────────────┼─────────────────────────┘                  │
│                            ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              Unified Data Layer + Identity Resolution            │   │
│  │         (PortCo mapping, KPI normalization, lineage tracking)    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                            │                                            │
│         ┌──────────────────┼──────────────────┐                        │
│         ▼                  ▼                  ▼                        │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│  │ Eliza Chat  │    │   Dynamic   │    │  Portfolio  │                │
│  │   (NL Q&A)  │    │ Query Tool  │    │  Explorer   │                │
│  └─────────────┘    └─────────────┘    └─────────────┘                │
│         │                  │                  │                        │
│         └──────────────────┼──────────────────┘                        │
│                            ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │         Saved Queries / Templates / Scheduled Reports            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Feature 1: Portfolio Intelligence (HoldCo Analytics)

### Overview

Portfolio Intelligence enables HoldCo users to connect DealCloud and Chronograph, then query across both systems using natural language chat, guided query builders, and saved templates—all within the Eliza application.

### User-Facing Components

#### 1.1 Eliza Chat (Natural Language Q&A)

**Description**: AI-powered conversational interface for portfolio questions

**Capabilities**:
- Natural language query input with follow-up prompts
- Cross-source data synthesis (DealCloud + Chronograph)
- Source attribution showing which systems/fields contributed to answers
- Drill-down capability into underlying data
- Contextual suggestions based on query history

**Example Interactions**:
```
User: "Which deal origination sources produce the best long-term returns?"

Eliza: "Based on analysis of 47 closed deals from DealCloud and their 
       subsequent performance in Chronograph:
       
       Top Performing Sources by MOIC:
       1. Proprietary Outreach: 2.8x average (12 deals)
       2. Industry Conferences: 2.4x average (8 deals)
       3. Investment Bank Referrals: 2.1x average (15 deals)
       
       [Sources: DealCloud deal_source field, Chronograph portfolio_returns]
       
       Would you like to drill into a specific source or time period?"
```

#### 1.2 Dynamic Query Tool

**Description**: Guided query builder with filters and parameters

**Capabilities**:
- Filter by: Fund, PortCo, Time Period, Sector, Geography, Deal Team
- Visual query construction for non-technical users
- Preview results before saving
- Export to common formats (Excel, PDF)

**UI Components**:
- Multi-select dropdowns for entity selection
- Date range pickers with presets (QTD, YTD, LTM, Custom)
- Metric selector with definitions on hover
- Result preview panel

#### 1.3 Saved Queries and Templates

**Description**: Reusable query configurations for repeated analysis

**Capabilities**:
- Save any query with custom name and description
- Organize by category (Board Prep, LP Reporting, Portfolio Review)
- Schedule execution (daily, weekly, monthly, quarterly)
- Share templates with team members (permission-based)
- View execution history and compare results over time

**Pre-built Templates** (Examples):
| Template Name | Purpose | Frequency |
|--------------|---------|-----------|
| Weekly Portfolio Risks | Flag underperforming metrics across all PortCos | Weekly |
| Board Prep Summary | Comprehensive single-PortCo performance package | Ad-hoc |
| LP Quarterly Report | Aggregate fund performance for LP communications | Quarterly |
| Pipeline-to-Performance Correlation | Link deal sources to outcomes | Monthly |

#### 1.4 Portfolio Explorer

**Description**: Browsable interface for PortCos, deals, and key metrics

**Capabilities**:
- Hierarchical navigation: Fund → PortCo → Metrics
- Key KPI summary cards with trend indicators
- Quick links to related entities and chat queries
- Search and filter across all portfolio entities
- Visual indicators for data freshness and completeness

### Core Analytical Questions Enabled

The platform must support answering these eight cross-source analytical questions:

| # | Question | Data Sources |
|---|----------|--------------|
| 1 | Which deal origination sources produce the best long-term returns? | DealCloud (sources) + Chronograph (returns) |
| 2 | What are the leading indicators in pipeline that forecast future portfolio KPI trends? | DealCloud (pipeline) + Chronograph (KPIs) |
| 3 | Which relationship networks lead to faster value creation after close? | DealCloud (relationships) + Chronograph (value metrics) |
| 4 | Are investments sourced from certain sectors/geographies more operationally efficient? | DealCloud (deal attributes) + Chronograph (operational KPIs) |
| 5 | What patterns predict portfolio under-performance early in the investment lifecycle? | DealCloud (deal characteristics) + Chronograph (performance trends) |
| 6 | How do deal team activities/engagement levels correlate with portfolio outcomes? | DealCloud (activities) + Chronograph (outcomes) |
| 7 | What are the hidden bottlenecks in closing deals that most impact long-term value creation? | DealCloud (process metrics) + Chronograph (value creation) |
| 8 | Can we automate quarterly LP reporting by pulling integrated data directly? | All sources synthesized |

---

## Feature 2: Quarterly Metrics Reimagined

### Overview

This feature modernizes how PortCos submit quarterly metrics and narrative context to HoldCos, replacing fragmented email/spreadsheet workflows with a versioned, status-tracked, and searchable submission system that integrates with Portfolio Intelligence.

### User-Facing Components

#### 2.1 PortCo Submission Workflow

**Description**: Streamlined metric submission with Excel as the primary input method

**Submission Mechanisms** (Priority Order):
| Method | Priority | Description |
|--------|----------|-------------|
| Excel Upload | Primary | Standardized template upload with validation |
| Portal UI | Optional | Web form for structured context and attachments |
| API/Connectors | Future | Direct system integration (e.g., QuickBooks) |

**Excel Template Features**:
- Pre-defined metric categories with clear definitions
- Validation rules to catch common errors
- Support for product-line/segment breakdowns
- Version identification in file metadata

#### 2.2 Narrative Context Capture

**Description**: Lightweight interface for operators to provide qualitative context alongside quantitative metrics

**Context Fields**:
- **Executive Summary**: High-level quarter overview
- **Metric Explanations**: Why specific metrics changed (e.g., "Gross margin dipped due to one-time inventory adjustment")
- **KPI Definitions**: PortCo-specific interpretations where they differ from standard
- **Supporting Materials**: Attachments (board decks, operational reports)
- **Forward Outlook**: Known factors affecting next quarter

**UI Design Principles**:
- Mirror familiar formats (similar to what would be in a board deck)
- Optional fields—don't block submission for incomplete context
- Rich text support for explanations
- Drag-and-drop attachment handling

#### 2.3 Versioning and Status Model

**Description**: Clear tracking of submission state and history

**Status Tags**:
| Status | Description | Visibility |
|--------|-------------|------------|
| **Draft** | Work in progress; not ready for HoldCo review | PortCo only |
| **Shared** | Ready for HoldCo review; may still be revised | PortCo + HoldCo |
| **Final** | Locked version; official record for the period | PortCo + HoldCo |

**Versioning Rules**:
- Every save creates a new version
- Numeric metrics: Minimal versioning expected (typically 1-2 versions)
- Narrative/Context: Robust versioning supported (multiple iterations common)
- Each version records: timestamp, user, change summary
- Any version can be referenced in queries and reports

**Version History UI**:
```
┌─────────────────────────────────────────────────────────────┐
│  Q4 2025 Submission - Acme Corp                             │
├─────────────────────────────────────────────────────────────┤
│  Current: v3 (Final) - Jan 12, 2026 by J. Smith             │
│  ─────────────────────────────────────────────────────────  │
│  Version History:                                           │
│  • v3 - Final    - Jan 12, 2026 - "Finalized after review"  │
│  • v2 - Shared   - Jan 10, 2026 - "Updated gross margin"    │
│  • v1 - Draft    - Jan 8, 2026  - "Initial submission"      │
└─────────────────────────────────────────────────────────────┘
```

#### 2.4 Synthesis with Portfolio Intelligence

**Description**: Submitted metrics and context are queryable alongside DealCloud and Chronograph data

**Integration Points**:
- Quarterly metrics appear in Portfolio Explorer
- Chat can reference submission data with version citations
- Saved queries can incorporate submission fields
- Board prep templates auto-pull latest Final submissions

**Example Synthesized Query**:
```
User: "Summarize Acme Corp's Q4 performance with context from their submission"

Eliza: "Acme Corp Q4 2025 Performance Summary:
       
       From Chronograph:
       - Revenue: $12.4M (+8% QoQ)
       - ARR: $48.2M (+12% YoY)
       
       From Q4 Submission (v3 - Final, Jan 12):
       - Gross Margin: 62% (down from 68%)
       - Context: 'One-time inventory write-down of $400K; 
         normalized margin would be 66%'
       
       From DealCloud:
       - Original Investment: Series B, Q2 2023
       - Lead Partner: M. Johnson
       
       [View full submission | Compare to Q3]"
```

---

## User Stories and Flows

### Feature 1 User Flows

#### Flow 1.1: System Connection Setup (Admin)

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Admin opens Eliza Settings → Connectors                          │
│    ↓                                                                │
│ 2. Selects "Add Connection" → Chooses DealCloud                     │
│    ↓                                                                │
│ 3. Enters API credentials and configuration                         │
│    ↓                                                                │
│ 4. System runs connectivity test                                    │
│    ↓                                                                │
│ 5. On success: Initial data sync begins                             │
│    ↓                                                                │
│ 6. Repeat for Chronograph                                           │
│    ↓                                                                │
│ 7. Configure PortCo identity mapping between systems                │
│    ↓                                                                │
│ 8. Verify cross-source queries work                                 │
└─────────────────────────────────────────────────────────────────────┘
```

#### Flow 1.2: Cross-Source Analysis (Investment Professional)

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. User opens Eliza Chat                                            │
│    ↓                                                                │
│ 2. Types: "Which deals from 2023 are outperforming expectations?"   │
│    ↓                                                                │
│ 3. Eliza synthesizes DealCloud (2023 closed deals) +                │
│    Chronograph (current vs. projected performance)                  │
│    ↓                                                                │
│ 4. Results displayed with source attribution                        │
│    ↓                                                                │
│ 5. User clicks "Drill into TechCo performance"                      │
│    ↓                                                                │
│ 6. Detailed KPI breakdown with product-line splits shown            │
│    ↓                                                                │
│ 7. User: "Save this as 'Board Prep - TechCo'"                       │
│    ↓                                                                │
│ 8. Query saved; user schedules weekly refresh                       │
└─────────────────────────────────────────────────────────────────────┘
```

#### Flow 1.3: Portfolio Exploration (Operations Team)

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. User opens Portfolio Explorer                                    │
│    ↓                                                                │
│ 2. Selects Fund III from fund list                                  │
│    ↓                                                                │
│ 3. Views PortCo cards with key metrics and trend indicators         │
│    ↓                                                                │
│ 4. Clicks PortCo "HealthTech Inc" for detail view                   │
│    ↓                                                                │
│ 5. Sees unified view: DealCloud deal info + Chronograph KPIs        │
│    ↓                                                                │
│ 6. Clicks "Ask about this company" → Opens chat with context        │
│    ↓                                                                │
│ 7. Types follow-up questions with PortCo pre-selected               │
└─────────────────────────────────────────────────────────────────────┘
```

### Feature 2 User Flows

#### Flow 2.1: PortCo Quarterly Submission

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. PortCo operator receives quarterly submission reminder           │
│    ↓                                                                │
│ 2. Downloads standardized Excel template from Eliza                 │
│    ↓                                                                │
│ 3. Fills in quarterly metrics in familiar spreadsheet format        │
│    ↓                                                                │
│ 4. Uploads completed Excel to Eliza                                 │
│    ↓                                                                │
│ 5. System validates and parses; shows preview                       │
│    ↓                                                                │
│ 6. Operator adds narrative context:                                 │
│    - "Gross margin impacted by one-time adjustment"                 │
│    - Attaches supporting memo                                       │
│    ↓                                                                │
│ 7. Saves as Draft → Reviews → Updates to "Shared"                   │
│    ↓                                                                │
│ 8. HoldCo notified of new submission                                │
└─────────────────────────────────────────────────────────────────────┘
```

#### Flow 2.2: HoldCo Board Preparation

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. HoldCo user opens saved template "Q4 Board Deck - Fund III"      │
│    ↓                                                                │
│ 2. System checks for latest submissions from each PortCo           │
│    - Shows: 8/10 PortCos have "Shared" or "Final" submissions       │
│    - Flags: 2 PortCos still in "Draft" status                       │
│    ↓                                                                │
│ 3. User runs template; results aggregated with version citations    │
│    ↓                                                                │
│ 4. For flagged PortCos, user sends reminder via Eliza               │
│    ↓                                                                │
│ 5. Once all Final, user generates board-ready export                │
│    ↓                                                                │
│ 6. Export includes: metrics, context excerpts, version references   │
└─────────────────────────────────────────────────────────────────────┘
```

#### Flow 2.3: Iterative Context Refinement

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. HoldCo reviews PortCo submission in chat                         │
│    ↓                                                                │
│ 2. Asks: "Why did customer acquisition cost increase 40%?"          │
│    ↓                                                                │
│ 3. Eliza shows: No specific context provided for CAC                │
│    ↓                                                                │
│ 4. HoldCo requests clarification (flag/comment in system)           │
│    ↓                                                                │
│ 5. PortCo operator adds context: "Expanded to 3 new markets;        │
│    CAC normalizes after initial market entry investment"            │
│    ↓                                                                │
│ 6. Submission updated to v2 (Shared); HoldCo notified               │
│    ↓                                                                │
│ 7. Both parties reference same versioned record                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Technical Requirements

### Platform Integration

| Requirement | Implementation Approach |
|-------------|------------------------|
| Platform/Product Separation | Connectors, RBAC, and patterns remain platform-level; Portfolio Intelligence and Quarterly Metrics are products built on top |
| Connector Framework | Build DealCloud and Chronograph connectors using `BaseConnector` pattern |
| Permission Model | Use `resource:action` style checks (e.g., `portfolio:read`, `submissions:write`) |
| Async Processing | Long-running ingestion/synthesis via Celery tasks and flows |
| Real-time Updates | Streaming update patterns for ingest/synthesis progress |

### Data Layer Requirements

#### Identity Resolution
- Consistent PortCo identifiers across DealCloud, Chronograph, and submissions
- Mapping table with manual override capability
- Fuzzy matching for initial suggestions

#### Data Normalization
- Minimal shared concept set: PortCo, Fund, Time Period, KPI labels
- Preserve raw source data for drilldown (no lossy normalization)
- Track data lineage for audit and attribution

#### Storage Strategy
- Raw uploads stored with original format preserved
- Parsed structures for query performance
- Derived normalized entities with source references

### API Requirements

| Endpoint Category | Key Operations |
|-------------------|----------------|
| Connectors | Create, test, sync, status |
| Portfolio | List PortCos, get details, search |
| Queries | Execute, save, schedule, history |
| Submissions | Upload, update status, version history |
| Chat | Send message, stream response, get context |

### Security and Permissions

| Permission | Description |
|------------|-------------|
| `portfolio:read` | View portfolio data and run queries |
| `portfolio:write` | Save queries, create templates |
| `submissions:read` | View PortCo submissions |
| `submissions:write` | Upload and update submissions |
| `connectors:admin` | Configure and manage connectors |

**Multi-tenancy Rules**:
- HoldCo users cannot access PortCo internal-only context unless explicitly shared
- PortCos cannot see other PortCos' data
- All queries filtered by tenant and permission scope

---

## Dependencies

### External System Dependencies

| System | Required Access | Priority |
|--------|-----------------|----------|
| **DealCloud** | API access, entity model documentation (deals, companies, activities, relationships, pipeline stages) | P0 |
| **Chronograph** | GraphQL schema access, KPI structures, portfolio identifiers | P0 |
| **Excel Templates** | Sample quarterly templates and representative KPI definitions | P0 |

### Internal Dependencies

| Dependency | Description |
|------------|-------------|
| Eliza Connector Framework | BaseConnector implementation pattern |
| Eliza RBAC | Permission model and enforcement |
| Eliza Chat Infrastructure | NL query processing and response generation |
| Eliza Task System | Async processing for ingestion and synthesis |

### Data Dependencies

| Data | Source | Notes |
|------|--------|-------|
| PortCo master list | DealCloud or Chronograph | Canonical source TBD |
| KPI definitions | Chronograph + PortCo submissions | May vary by company |
| Historical metrics | Chronograph | Time series preservation critical |
| Deal attributes | DealCloud | Full entity model needed |

---

## Edge Cases and Risk Mitigation

### Edge Case Handling

| Edge Case | Handling Approach |
|-----------|-------------------|
| **Inconsistent KPI definitions** ("ARR" varies by PortCo) | Allow PortCo-specific definitions in submissions; show definition on hover; flag when comparing across PortCos |
| **Lossy source normalization** | Store raw data alongside normalized; always enable drill-down to source |
| **Duplicate uploads** | Detect similar files; prompt user to confirm intent (new version vs. duplicate) |
| **Partial data submissions** | Accept partial; clearly indicate completeness in UI; don't block queries |
| **System sync failures** | Retry with backoff; alert admin; show data freshness indicators |
| **Identity mapping conflicts** | Surface for manual resolution; don't auto-merge ambiguous matches |

### Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| DealCloud API limitations | Medium | High | Early API review; design for rate limits; cache aggressively |
| Chronograph schema complexity | Medium | Medium | Dedicated schema analysis phase; incremental KPI support |
| PortCo adoption friction | Medium | High | Excel-first approach; minimal required fields; clear value demonstration |
| Data quality issues | High | Medium | Validation rules; quality indicators; context for anomalies |
| Cross-source join performance | Medium | Medium | Pre-compute common joins; async processing for complex queries |

---

## Acceptance Criteria

### Feature 1: Portfolio Intelligence

| ID | Criterion | Verification Method |
|----|-----------|---------------------|
| F1-1 | HoldCo admin can connect DealCloud and verify connectivity | Manual test: Add connection, run test, view success |
| F1-2 | HoldCo admin can connect Chronograph and verify connectivity | Manual test: Add connection, run test, view success |
| F1-3 | User can answer each of the 8 example questions in chat | Manual test: Ask each question, verify relevant response |
| F1-4 | Answers include clear source attribution | Verify response shows which systems/fields contributed |
| F1-5 | User can drill down into underlying data | Click drill-down, verify detail view loads |
| F1-6 | User can save a query as a named template | Save query, verify appears in saved list |
| F1-7 | User can schedule a saved query | Schedule query, verify execution at scheduled time |
| F1-8 | Portfolio Explorer shows navigable PortCo list with key metrics | Browse list, verify metrics display and navigation works |
| F1-9 | Portfolio Explorer links to chat and saved queries | Click link, verify context carries through |

### Feature 2: Quarterly Metrics Reimagined

| ID | Criterion | Verification Method |
|----|-----------|---------------------|
| F2-1 | PortCo operator can upload standardized Excel | Upload file, verify parsing success |
| F2-2 | PortCo operator can enter narrative context | Add context, verify saved and displayed |
| F2-3 | PortCo operator can attach supporting materials | Attach file, verify accessible |
| F2-4 | Submissions support version history | Create multiple versions, verify history shows all |
| F2-5 | Submissions support status tags (Draft/Shared/Final) | Change status, verify displayed correctly |
| F2-6 | Version metadata includes timestamp and user | Check version detail, verify metadata present |
| F2-7 | HoldCo can view latest Shared/Final submissions | Log in as HoldCo, verify visibility |
| F2-8 | HoldCo can query submission data in chat | Ask about submission, verify data returned |
| F2-9 | Saved queries can reference specific submission versions | Run query with version param, verify correct data |
| F2-10 | Narrative/context versioning is robust | Create multiple context versions, verify all preserved |

---

## Success Metrics

### Quantitative Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Time to answer portfolio question** | <30 seconds (vs. hours manual) | Average query response time |
| **Board prep time reduction** | 50% reduction | User-reported time comparison |
| **Cross-source query adoption** | 80% of HoldCo users weekly | Usage analytics |
| **PortCo submission compliance** | 95% on-time submissions | Submission timestamps |
| **Version alignment** | 100% HoldCo/PortCo same-version reference | Audit of cited versions |

### Qualitative Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **User satisfaction** | NPS > 50 | Quarterly survey |
| **Data trust** | "High confidence" rating | User feedback |
| **Workflow adoption** | Replaces email/manual processes | User interviews |

---

## Open Questions

### Product Decisions Needed

| Question | Options | Recommendation |
|----------|---------|----------------|
| Scheduled insight notifications | In-app only vs. Email/Slack | Start in-app; add notifications later |
| KPI dictionary UI for PortCos | Include in MVP vs. Phase 2 | Phase 2 (valuable but not blocking) |
| Submission reminder automation | Manual vs. Automated | Automated with manual override |

### Engineering Questions to Resolve

| Question | Owner | Timeline |
|----------|-------|----------|
| Chronograph ingestion approach for KPI time series with product-level splits | Engineering | Pre-development |
| DealCloud entity mapping (deals, companies, activities, relationships, stages) | Engineering | Pre-development |
| Identity resolution strategy for PortCos across systems | Engineering + Product | Design phase |
| Storage strategy for raw uploads + parsed + normalized | Engineering | Design phase |
| Scheduling implementation within Eliza patterns | Engineering | Development |
| QuickBooks connector scope (if pursued) | Product + Engineering | Phase 2 planning |

---

## Appendix

### A. Glossary

| Term | Definition |
|------|------------|
| **HoldCo** | Holding Company - the private equity firm managing the portfolio |
| **PortCo** | Portfolio Company - a company in which the PE firm has invested |
| **DealCloud** | CRM and deal management platform for PE firms |
| **Chronograph** | Portfolio monitoring and KPI tracking platform |
| **ARR** | Annual Recurring Revenue |
| **MOIC** | Multiple on Invested Capital |
| **LP** | Limited Partner - investors in the PE fund |
| **KPI** | Key Performance Indicator |

### B. Related Documents

- Eliza Platform Architecture Documentation
- Connector Development Guide
- RBAC and Permissions Specification
- API Design Standards

### C. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | January 15, 2026 | — | Initial PRD based on feature specification |

---

*This document is a living artifact and will be updated as product decisions are made and engineering questions are resolved.*
