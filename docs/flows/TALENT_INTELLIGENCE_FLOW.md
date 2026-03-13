# Talent Intelligence Flow - CrewAI Architecture

**Purpose:** Analyze job descriptions and find ideal candidate personas using ingested people data

---

## 🎯 Flow Overview

**Input:** Job description (text or file) OR manual persona definition  
**Output:** AI-generated ideal persona + ranked look-alike candidates  
**Processing:** 3-agent CrewAI flow with specialized search tools  

---

## 🤖 Agent Architecture

### 1. **Job Analyst Agent**
**Role:** Senior Talent Acquisition Specialist  
**Goal:** Extract key requirements, skills, and attributes from job descriptions  

**Tasks:**
- Parse job description text
- Identify required skills, experience levels, and qualifications
- Extract company culture indicators
- Determine ideal candidate attributes
- Output structured persona definition

**Tools:**
- None (pure LLM analysis)

**Prompt Template:**
```
You are a Senior Talent Acquisition Specialist with 15+ years of experience in recruiting 
top talent across technology companies. Your expertise lies in understanding job requirements 
deeply and translating them into actionable candidate profiles.

Given the following job description:
{job_description}

Analyze and extract:

1. CORE REQUIREMENTS
   - Required technical skills (list each with proficiency level needed)
   - Years of experience required (minimum and ideal)
   - Educational requirements
   - Certifications or licenses

2. ROLE CHARACTERISTICS
   - Seniority level (entry/mid/senior/executive)
   - Role type (IC/manager/director/VP/C-level)
   - Team size they'd manage (if applicable)
   - Key responsibilities

3. IDEAL BACKGROUND
   - Previous role titles that would be great fits
   - Types of companies (startups, enterprise, specific industries)
   - Company sizes (early-stage, growth, enterprise)
   - Notable companies that produce ideal candidates

4. SKILLS & COMPETENCIES
   - Hard skills (technical, tools, frameworks)
   - Soft skills (leadership, communication, etc.)
   - Domain expertise

5. CULTURAL FIT INDICATORS
   - Work style preferences
   - Team dynamics
   - Company culture attributes

6. CAREER PATH SIGNALS
   - Career progression patterns to look for
   - Red flags to avoid
   - Growth trajectory indicators

Provide your analysis in a structured JSON format that can be used to search for candidates.
Be specific and actionable. Think like a recruiter who knows exactly what success looks like.
```

---

### 2. **Talent Scout Agent**
**Role:** Expert People Search Specialist  
**Goal:** Find candidates matching the ideal persona using Elasticsearch and Neo4j  

**Tasks:**
- Transform persona into search queries
- Execute searches across Elasticsearch (skills, titles, companies)
- Execute graph queries in Neo4j (career paths, networks)
- Rank candidates by fit score
- Enrich candidate profiles with additional context

**Tools:**
- `PersonFullTextSearchTool` (Elasticsearch)
- `PersonSkillSearchTool` (Elasticsearch)
- `PersonCareerPathTool` (Neo4j)
- `PersonCompanyNetworkTool` (Neo4j)
- `PersonLookAlikeSearchTool` (Hybrid)

**Prompt Template:**
```
You are an Expert People Search Specialist with deep knowledge of talent databases and 
search strategies. You excel at finding hidden gems and understanding candidate fit beyond 
just keywords.

Given the ideal candidate persona:
{persona_json}

Your mission: Find the TOP candidates who match this profile using your search tools.

SEARCH STRATEGY:

1. MULTI-FACETED SEARCH
   - Use full-text search for job titles and company names
   - Use skill search for technical capabilities
   - Use career path analysis for progression patterns
   - Use company network analysis for ecosystem fit

2. SEARCH ITERATIONS
   - Start broad to understand the candidate landscape
   - Refine based on initial results
   - Look for adjacent roles and transferable skills
   - Don't just match keywords - understand context

3. RANKING CRITERIA
   - Skills match (technical + soft skills)
   - Experience level fit
   - Career trajectory alignment
   - Company background relevance
   - Cultural fit indicators
   - Growth potential

4. ENRICHMENT
   - Pull related career transitions
   - Identify notable projects or achievements
   - Find skill co-occurrences
   - Map professional network strength

Execute your searches systematically. For each search:
- Explain your search strategy
- Show search parameters
- Analyze results quality
- Refine if needed

Return a ranked list of top 20-50 candidates with fit scores and rationale.
```

---

### 3. **Insights Synthesizer Agent**
**Role:** Talent Intelligence Analyst  
**Goal:** Generate actionable insights and recommendations  

**Tasks:**
- Synthesize search results into persona summary
- Identify trends and patterns in the candidate pool
- Generate market intelligence
- Provide sourcing recommendations
- Create executive summary

**Tools:**
- None (synthesis of previous results)

**Prompt Template:**
```
You are a Talent Intelligence Analyst who transforms raw search data into strategic 
insights that hiring managers and recruiters can act on immediately.

Given:
- Original job description: {job_description}
- Ideal persona: {persona_json}
- Search results: {search_results}

Create a comprehensive Talent Intelligence Report with:

1. EXECUTIVE SUMMARY
   - Top 5 candidates (with brief rationale)
   - Key insights about the talent market for this role
   - Recommended sourcing strategies

2. IDEAL PERSONA REFINED
   - Synthesized persona based on actual candidate data
   - Must-have attributes (found in top candidates)
   - Nice-to-have attributes
   - Unique differentiators

3. MARKET ANALYSIS
   - Total candidates found matching criteria
   - Distribution by current companies
   - Distribution by previous companies
   - Common career paths observed
   - Skill availability and scarcity

4. TOP CANDIDATES BREAKDOWN
   For each of the top 10-20 candidates:
   - Name, current title, current company
   - Fit score (0-100) with breakdown:
     * Skills match: X%
     * Experience fit: X%
     * Career trajectory: X%
     * Company background: X%
     * Cultural fit signals: X%
   - Why they're a great fit (2-3 sentences)
   - Potential concerns (if any)
   - Recommended approach for outreach

5. SOURCING RECOMMENDATIONS
   - Where to find more candidates like these
   - Companies to target
   - Job boards and communities
   - Keywords for sourcing
   - Networking strategies

6. COMPETITIVE INTELLIGENCE
   - Companies losing talent in this space
   - Companies attracting top talent
   - Emerging trends in this talent pool

Make your insights actionable. Think like a strategic advisor who's helping 
a company make a critical hire.
```

---

## 🔧 CrewAI Tools for Person Search

### 1. **PersonFullTextSearchTool**
**Purpose:** Elasticsearch full-text search for job titles, companies, skills  
**Input:** Query text, filters (location, experience level)  
**Output:** List of matching persons with scores  

**Implementation:**
```python
from crewai.tools import BaseTool
from src.services.search.person_search_service import PersonSearchService

class PersonFullTextSearchTool(BaseTool):
    name: str = "person_full_text_search"
    description: str = """
    Search for people using full-text search across job titles, companies, and skills.
    
    Use this when you need to:
    - Find people by job title (e.g., "Senior Software Engineer")
    - Find people who worked at specific companies
    - Search for specific skills or expertise
    - Use natural language queries
    
    Input format:
    {
        "query": "software engineer machine learning",
        "location": "United States" (optional),
        "min_years_experience": 5 (optional),
        "current_company": "Google" (optional),
        "limit": 20
    }
    
    Returns: List of persons with relevance scores, ranked by match quality.
    """
    
    def _run(self, query: str, **filters) -> str:
        # Implementation calls PersonSearchService
        pass
```

### 2. **PersonSkillSearchTool**
**Purpose:** Find people with specific skill combinations  
**Input:** List of required skills, optional skill levels  
**Output:** People matching skill criteria  

### 3. **PersonCareerPathTool**
**Purpose:** Neo4j graph query for career transitions  
**Input:** From company/role, to company/role  
**Output:** People who made similar transitions  

### 4. **PersonCompanyNetworkTool**
**Purpose:** Find people connected through companies  
**Input:** Company names  
**Output:** Network graph of shared employees  

### 5. **PersonLookAlikeSearchTool**
**Purpose:** Hybrid search combining all signals  
**Input:** Reference person ID or ideal attributes  
**Output:** Similar people ranked by composite score  

---

## 🔄 Flow Execution

```
User Input (Job Description or Manual Persona)
  ↓
┌─────────────────────────────────────────────┐
│ AGENT 1: Job Analyst                       │
│ - Parse job description                    │
│ - Extract requirements                     │
│ - Define ideal persona                     │
│ Output: Structured persona JSON            │
└─────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────┐
│ AGENT 2: Talent Scout                      │
│ - Transform persona to search queries      │
│ - Execute Elasticsearch searches           │
│ - Execute Neo4j graph queries              │
│ - Rank and score candidates                │
│ Output: Ranked candidate list              │
└─────────────────────────────────────────────┘
  ↓
┌─────────────────────────────────────────────┐
│ AGENT 3: Insights Synthesizer              │
│ - Analyze candidate pool                   │
│ - Generate market intelligence             │
│ - Create executive summary                 │
│ Output: Talent Intelligence Report         │
└─────────────────────────────────────────────┘
  ↓
Frontend UI Display
```

---

## 📊 Output Schema

### Talent Analysis Result
```json
{
  "analysis_id": "uuid",
  "created_at": "timestamp",
  "job_description": "original text",
  "ideal_persona": {
    "required_skills": [...],
    "experience_years": {"min": 5, "ideal": 8},
    "education": [...],
    "role_level": "senior",
    "previous_titles": [...],
    "target_companies": [...],
    "key_attributes": [...]
  },
  "candidates": [
    {
      "person_id": 123,
      "pdl_id": "...",
      "name": "Jane Doe",
      "current_title": "Senior Engineer",
      "current_company": "Google",
      "fit_score": 92,
      "fit_breakdown": {
        "skills_match": 95,
        "experience_fit": 90,
        "career_trajectory": 88,
        "company_background": 92,
        "cultural_fit": 90
      },
      "why_great_fit": "...",
      "concerns": "...",
      "recommendation": "..."
    }
  ],
  "market_insights": {
    "total_candidates_found": 156,
    "companies_distribution": {...},
    "skills_availability": {...},
    "common_career_paths": [...]
  },
  "sourcing_recommendations": [...],
  "executive_summary": "..."
}
```

---

## 🎨 Frontend Integration

### API Endpoint
```
POST /api/talent/analyze
Body: { job_description: string } OR { persona: object }
Response: { analysis_id: string, status: "processing" }

GET /api/talent/analysis/{analysis_id}
Response: TalentAnalysisResult

GET /api/talent/analysis/{analysis_id}/stream (SSE)
Response: Stream of progress events
```

### SSE Events
- `analysis_started`
- `agent_1_started` (Job Analyst)
- `agent_1_completed`
- `agent_2_started` (Talent Scout)
- `agent_2_progress` (search results)
- `agent_2_completed`
- `agent_3_started` (Insights Synthesizer)
- `agent_3_completed`
- `analysis_completed`
- `analysis_failed`

---

## 🚀 Implementation Priority

1. ✅ Phase 2: Data Connections (Ingest people data) - COMPLETE
2. 🔄 Phase 3a: Create CrewAI tools for search (Backend)
3. 🔄 Phase 3b: Implement Talent Intelligence Flow (Backend)
4. 🔄 Phase 3c: Create API endpoints with SSE (Backend)
5. 🔄 Phase 3d: Build UI components (Frontend)

---

## 💡 Key Success Factors

1. **Excellent Prompts:** Detailed, role-specific prompts that guide agents to think like experts
2. **Search Tool Integration:** Agents must effectively use Elasticsearch and Neo4j
3. **Iterative Search:** Agents should refine searches based on results
4. **Actionable Insights:** Output must be immediately useful for recruiters
5. **Real-time Feedback:** SSE streaming keeps users engaged during processing

---

This architecture ensures our AI agents leverage the full power of the ingested people data 
while providing immense value to talent management users.

