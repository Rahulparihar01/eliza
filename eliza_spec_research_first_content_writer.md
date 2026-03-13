# Content Writer Platform: Research-First Long-Form Writer

## Title and Overview
A research-first content writer product inside the Eliza Platform that helps marketers and founders generate **publish-ready** content with a **novel, intriguing POV**, grounded in a curated **Research Pack** (separate from the draft). Users start from a **single topic**, choose research sources, review evidence, and generate content for:
- **X/Twitter long-form article**
- **LinkedIn post**
- **Blog post**

The product emphasizes **Human+AI collaboration**: fast initial draft generation, then an iterative refinement loop with guided “POV → narrative → structure → execution” tools available when needed.

## Problem Statement / User Need
Most “AI writers” produce fluent output but fail to:
- Create a **fresh POV** instead of generic platitudes
- Ground content in **credible sources** and help users reason through disagreements
- Support fast iteration without “regen roulette”
- Improve over time through reusable, personal writing context (voice, pillars, examples)

Users need a system that behaves more like a **context engine** than a content generator: it gathers evidence, proposes differentiated POVs, and enables rapid, surgical revision.

## Goals and Non-Goals

### Goals
- Produce **research-informed**, high-quality drafts with a **new POV**
- Provide a **Source Picker** so users control where research comes from each run
- Surface a structured **Research Pack** (excerpts, takeaways, counterpoints) **separate from the draft**
- Enable a **Fast Path** (“Generate full draft”) and an optional guided refinement workflow
- Support **personal Skills/Memory** that compound over time (voice, pillars, hooks, examples, proof bank)
- Support safe iteration with claim discipline (e.g., call out weakly supported claims)

### Non-Goals (MVP)
- Team/shared skills libraries (personal-only)
- PDF ingestion (e.g., arXiv PDFs) (explicitly deferred)
- Fully automated multi-platform repurposing (explicitly deferred)
- Full publishing/scheduling integrations (optional future)

## Key Features or Capabilities

### 1) Source Picker (Per-Run)
User explicitly selects research sources each run:
- Web (general)
- Reddit
- Hacker News
- X/Twitter
- Curated blogs/news
- User-pasted text

**Output:** A research job that builds a Research Pack using only the selected sources.

### 2) Research Pack Panel (Separate from Draft)
A structured panel that includes:
- Key takeaways (bulleted)
- Excerpts/snippets (short) with source metadata
- “What’s contested / debated” summary
- “Best counterargument” summary
- One-click actions per excerpt: **Use**, **Ignore**, **Find stronger support**, **Find opposing view**

Drafts do **not** show citations by default (citations stay in the Research Pack).

### 3) POV Engine (Novel Frames)
After research, generate 3–5 distinct POV options that are meaningfully different, such as:
- Contrarian thesis (with evidence)
- New vocabulary/model (“named framework”)
- Myth-busting teardown
- Operator playbook
- Hypothesis + experiments (when evidence is mixed)

User can pick one POV to drive the draft, or choose “Surprise me”.

### 4) Hook Lab (Research-Informed)
Generate multiple hook options aligned with the chosen POV and strongest evidence.
Supports LinkedIn and long-form openers (title + lede for blog / Twitter article).

### 5) Outline-First Generation (Especially for Long-Form)
For blog + Twitter article:
- 2–3 outline options consistent with the chosen POV
- Expand section-by-section (optional), preserving narrative coherence

### 6) Fast Path Draft Generation + Refinement Loop (Chosen: Fast Path)
**Default:** one-click **Generate Full Draft** (end-to-end).
Then users can:
- Enter guided refinement (POV → arc → structure → execution) if desired
- Or do “surgical edits” via highlight → instruction (tighten, add example, more tactical, more contrarian, etc.)

### 7) Skills / Memory (Personal-Only) — MVP
First-class “Skills” that users can create, edit, and reuse:
- Voice profile (tone, cadence, do/don’t)
- Content pillars
- Hook guide
- Example posts (what “good” looks like)
- Proof bank (wins, stats, stories)

Skills are personal-only in MVP, applied automatically based on relevance to the request.

### 8) Claim Discipline (Trust Layer)
Drafting experience includes lightweight guardrails:
- Flag statements that appear weakly supported by the Research Pack
- Suggest rephrasing into opinion/hypothesis when appropriate
- Provide “Add support from Research Pack” action

## User Stories / Flows

### Primary Flow: Research → POV → Draft (Fast Path)
1. User selects **format** (LinkedIn / Blog / Twitter article)
2. User enters **topic** and optional constraints (audience, tone, length)
3. User chooses **sources** via Source Picker
4. System generates **Research Pack**
5. System proposes **POVs** (3–5); user selects one (or “Surprise me”)
6. User clicks **Generate Full Draft**
7. User edits via:
   - Quick transformations (tighten, expand, add example, make more tactical)
   - Highlight-and-instruct editing
8. User exports/copies final content (no citations shown by default)

### Guided Refinement Flow (Optional)
At any time after a draft exists, the user can open “Refine with Workflow”:
1. POV adjustments (choose alternate POV, blend POVs)
2. Narrative arcs (choose the emotional journey)
3. Structural blueprint (choose section flow)
4. Execution (hooks, section refinement, CTA)

### Skills Setup Flow
1. User creates or imports Skills (Voice, Pillars, Hooks, Examples, Proof Bank)
2. User sets which Skills are default-on
3. Draft generation automatically references relevant Skills

### Research Pack Interaction Flow
- User reviews excerpts, selects “Use” to pin into a “Selected Evidence” subset
- User requests “Find opposing view” to balance POV
- User regenerates Research Pack with different source selection if needed

## Technical Alignment
Built as a **Product on the Eliza Platform** using standard patterns:
- API endpoints for create/read/update runs and artifacts
- A long-running execution path using Eliza’s standard async task pattern when needed
- A multi-step **CrewAI Flow** for: research → POV generation → outlining → drafting → revision suggestions
- Custom tools for source retrieval and excerpting; optionally upgradable into first-class connectors later
- Optional server-sent events (SSE) for real-time progress updates in the UI (recommended as a follow-on if needed)

## Dependencies / Edge Cases

### Dependencies
- Source retrieval tools for each selected source type (web, Reddit, HN, X, curated blogs, pasted text)
- Persistent storage for:
  - Runs (inputs, selected sources, timestamps, status)
  - Research Packs (excerpts + metadata)
  - Draft artifacts (per format)
  - Skills (personal-only)

### Edge Cases
- Conflicting sources: Research Pack must summarize disagreement and offer “responsible POV” options
- Low-quality sources (e.g., anecdotal Reddit threads): label as anecdotal and avoid presenting as fact
- X/Twitter access limitations: rate limits and/or API access constraints
- Content safety: avoid disallowed content, and prevent fabricated citations or “fake sources”
- Iteration churn: ensure users can revert to earlier draft versions
- Very broad topics: POV engine should ask for 1–2 constraints (audience/angle) *only if needed*, otherwise propose multiple POVs

## Acceptance Criteria

### Research Pack
- User can select sources for each run and the system only uses selected sources
- Research Pack contains:
  - at least 5–15 excerpts (configurable), clustered by theme
  - a “contested” section when disagreement is detected
  - actions: Use / Ignore / Find opposing view / Find stronger support

### POV + Draft Quality
- System generates 3–5 POVs grounded in the Research Pack
- “Generate Full Draft” produces:
  - LinkedIn post formatted for readability
  - Blog post with headings and coherent arc
  - Twitter article with title, sections, and strong opening

### Skills
- Users can create/edit/delete Skills (voice, pillars, hooks, examples, proof bank)
- Skills are personal-only and automatically applied by relevance
- Users can toggle Skills on/off per run

### Editing / Iteration
- Users can apply at least 6 quick transforms (tighten, expand, more tactical, more contrarian, add example, simplify)
- Users can highlight a section and request a targeted rewrite
- Users can view and restore previous versions of drafts

### Product Reliability
- Long-running operations return a trackable run status and final artifacts
- Errors are surfaced clearly (source failures, rate limiting, empty research results)

## Outstanding Product Decisions
None for MVP scope. (PDF ingestion and team/shared Skills are explicitly deferred.)

## Open Engineering Questions
- **OPEN ENGINEERING QUESTION:** What is the initial approach for X/Twitter retrieval (official API vs alternative), and how do we handle rate limits / auth?
- **OPEN ENGINEERING QUESTION:** Do we treat “curated blogs/news” as a maintained allowlist, or an initial preset list configurable by admins?
- **OPEN ENGINEERING QUESTION:** How should Research Pack excerpts be stored (full text vs snippet only) and what is the retention policy?
- **OPEN ENGINEERING QUESTION:** Should SSE streaming be included in MVP or shipped as a follow-on once async runs are validated in production?
- **OPEN ENGINEERING QUESTION:** How do we implement “Find opposing view” reliably across heterogeneous sources without drifting into irrelevant results?
