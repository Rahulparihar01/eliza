# Data Connections & Talent Intelligence UI - Implementation Plan

**Created:** October 10, 2025  
**Branch:** `feature/data-connections-ui`  
**Status:** Planning Phase

---

## Executive Summary

Build a comprehensive UI for managing data connections (PDL, future sources) and analyzing talent intelligence through AI-powered look-alike persona matching. The system will leverage CrewAI flows and agents with Elasticsearch/Neo4j for deep talent analysis.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐    ┌─────────────────────────────┐  │
│  │  Data Connections    │    │  Talent Intelligence        │  │
│  │  Page                │    │  Page                       │  │
│  ├──────────────────────┤    ├─────────────────────────────┤  │
│  │ • API Configuration  │    │ • Job Description Upload    │  │
│  │ • Sync Management    │    │ • Ideal Candidate Profile   │  │
│  │ • Health Monitoring  │    │ • Look-Alike Search         │  │
│  │ • Cost Tracking      │    │ • AI Analysis Results       │  │
│  └──────────────────────┘    └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐    ┌─────────────────────────────┐  │
│  │  Connector Service   │    │  Talent Intelligence Flow   │  │
│  │  (Existing)          │    │  (New CrewAI)              │  │
│  └──────────────────────┘    └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer                                 │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL  │  Elasticsearch  │  Neo4j  │  Redis (Celery)    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Data Connections Page

### Page: `/data-connections`

**Purpose:** Manage API integrations (PDL, future sources) for ingesting talent data.

### Components Needed

#### 1. **ConnectionsListView**
```typescript
interface Connection {
  id: string;
  name: string;
  type: 'people_data_labs' | 'linkedin' | 'github' | 'custom';
  status: 'healthy' | 'unhealthy' | 'inactive';
  lastSync: Date;
  recordCount: number;
  costToDate: number;
  isEnabled: boolean;
}
```

**Features:**
- Table/card view of all connections
- Status indicators (green/yellow/red)
- Quick actions: Enable/Disable, Sync Now, Edit, Delete
- Cost tracking per connection
- Filter by status, type

**Existing Reference:** `src/pages/document-management/DocumentManagementPage.tsx`

---

#### 2. **CreateConnectionModal**

**Form Fields:**
- Connection Name (text)
- Connection Type (dropdown: PDL, LinkedIn, GitHub, Custom)
- API Key (password field, encrypted)
- Search Query (JSON editor with validation)
  - Job Title
  - Company
  - Location
  - Skills
  - Experience Level
- Sync Mode (Full Refresh / Incremental)
- Schedule (Manual / Daily / Weekly / Monthly)
- Max Records Per Sync (number)
- Cost Limit (number, optional)

**Features:**
- Query builder UI (no-code option)
- Test Connection button
- Cost Estimation preview
- Query templates for common searches

**Existing Reference:** Modal patterns from `src/components/` + form validation

---

#### 3. **ConnectionDetailView**

**Tabs:**
1. **Overview**
   - Connection info
   - Health status
   - Quick stats (records, cost, last sync)

2. **Sync History**
   - Table of past syncs
   - Status, duration, records fetched
   - Error logs
   - Cost per sync

3. **Configuration**
   - Edit connection settings
   - Update API key
   - Modify search query

4. **Data Preview**
   - Sample of fetched records
   - Field mapping visualization

**Features:**
- Real-time sync progress (SSE)
- Manual sync trigger
- Export sync logs
- Telemetry charts

**Existing Reference:** Document viewer patterns + SSE from existing flows

---

#### 4. **SyncProgressWidget**

**Real-time updates via SSE:**
- Progress bar (0-100%)
- Current stage (Initializing → Fetching → Transforming → Complete)
- Records processed
- Estimated time remaining
- Cost so far
- Errors/warnings

**WebSocket/SSE Connection:**
```typescript
const { data: telemetry } = useSSE(`/api/v1/connectors/${id}/telemetry`);
```

---

### API Endpoints (Existing - Ready to Use)

```
POST   /api/v1/connectors/configure          # Create connection
GET    /api/v1/connectors/list                # List all connections
GET    /api/v1/connectors/{id}                # Get connection details
PUT    /api/v1/connectors/{id}/update         # Update connection
DELETE /api/v1/connectors/{id}/delete         # Delete connection
POST   /api/v1/connectors/{id}/sync           # Trigger sync
GET    /api/v1/connectors/{id}/health         # Health check
GET    /api/v1/connectors/{id}/sync-history   # Sync history
GET    /api/v1/connectors/{id}/statistics     # Stats
```

---

## Phase 2: Talent Intelligence Page

### Page: `/talent-intelligence`

**Purpose:** AI-powered talent analysis, ideal candidate profiling, and look-alike search.

### User Journey

1. **Upload Job Description** (or paste text)
2. **Define Ideal Candidate** (optional additional criteria)
3. **AI Analysis** (CrewAI flow extracts requirements, analyzes talent pool)
4. **View Results** (ranked candidates, insights, recommendations)
5. **Refine & Export** (adjust criteria, export matches)

---

### Components Needed

#### 1. **JobDescriptionInput**

**Upload Options:**
- Text paste (markdown editor)
- File upload (PDF, DOCX, TXT)
- URL import (scrape job posting)

**AI Extraction Preview:**
- Job Title
- Required Skills
- Experience Level
- Industry
- Location preferences
- Company culture indicators

**Features:**
- Auto-save drafts
- Template library (common roles)
- Multi-language support

---

#### 2. **IdealCandidateBuilder**

**Interactive Form:**
- **Must-Have Skills** (chip selector)
- **Nice-to-Have Skills** (chip selector)
- **Experience Range** (slider: 0-20+ years)
- **Education Level** (dropdown)
- **Industry Experience** (multi-select)
- **Company Tier** (Startup / Mid-size / Enterprise)
- **Location Preferences** (geo selector)
- **Career Trajectory** (growth indicators)

**AI Assistance:**
- "Suggest skills based on job description"
- "Show me profiles of top performers in this role"
- "What skills do successful candidates have?"

---

#### 3. **AIAnalysisFlow**

**CrewAI Flow: `TalentIntelligenceFlow`**

**Agents:**
1. **Requirements Analyst Agent**
   - Extracts skills, experience, qualifications from JD
   - Identifies hidden requirements
   - Prioritizes criteria

2. **Market Research Agent**
   - Queries Elasticsearch for skill trends
   - Analyzes salary benchmarks
   - Identifies talent pools

3. **Profile Matcher Agent**
   - Searches Neo4j for career paths
   - Queries Elasticsearch for candidates
   - Ranks by fit score

4. **Insights Generator Agent**
   - Summarizes findings
   - Provides recommendations
   - Highlights red flags

**Tools Available to Agents:**
- `PersonSearchTool` (Elasticsearch full-text)
- `SkillAnalysisTool` (Elasticsearch aggregations)
- `CareerPathTool` (Neo4j graph queries)
- `CompanyNetworkTool` (Neo4j relationships)
- `DocumentSearchTool` (RAG for JD context)

**Flow Output:**
```typescript
interface TalentIntelligenceResult {
  analysisId: string;
  jobDescription: JobDescription;
  idealProfile: IdealCandidate;
  matches: CandidateMatch[];
  insights: {
    marketTrends: string[];
    skillGaps: string[];
    recommendations: string[];
    talentPoolSize: number;
  };
  createdAt: Date;
}
```

---

#### 4. **AnalysisProgressView**

**Real-time Flow Execution (SSE):**
- Current agent working
- Current tool execution
- Progress percentage
- Intermediate results
- Token usage
- Estimated completion time

**Visual:**
- Agent avatars with status
- Tool execution logs
- Result streaming

---

#### 5. **CandidateMatchResults**

**List View:**
- Ranked by fit score (0-100)
- Profile cards with:
  - Name (if available)
  - Current role & company
  - Key skills match
  - Experience level
  - Fit score breakdown
  - LinkedIn/GitHub links

**Features:**
- Sort by: Fit Score / Experience / Skills Match
- Filter by: Location / Company / Experience
- Save to shortlist
- Export to CSV/PDF
- Schedule interviews (future)

---

#### 6. **InsightsDashboard**

**Visualizations:**
1. **Skills Distribution**
   - Bar chart of required skills in talent pool
   - Gap analysis

2. **Experience Levels**
   - Distribution chart

3. **Career Trajectories**
   - Common paths to this role (Neo4j viz)

4. **Company Networks**
   - Where top talent comes from (Neo4j viz)

5. **Market Intelligence**
   - Talent pool size
   - Competition for talent
   - Salary trends

**AI Insights Panel:**
- Key findings
- Recommendations
- Action items
- Market risks

---

### New API Endpoints (To Build)

```
# Talent Intelligence Flow
POST   /api/v1/talent-intelligence/analyze          # Start analysis
GET    /api/v1/talent-intelligence/{id}/status      # Flow status (SSE)
GET    /api/v1/talent-intelligence/{id}/results     # Get results
POST   /api/v1/talent-intelligence/{id}/refine      # Adjust criteria
DELETE /api/v1/talent-intelligence/{id}             # Delete analysis

# Job Descriptions
POST   /api/v1/job-descriptions/upload              # Upload JD
POST   /api/v1/job-descriptions/extract             # AI extract
GET    /api/v1/job-descriptions/templates           # Get templates

# Candidate Matching
GET    /api/v1/candidates/search                    # Search candidates
POST   /api/v1/candidates/lookalike                 # Look-alike search
GET    /api/v1/candidates/{id}/profile              # Full profile
POST   /api/v1/candidates/shortlist                 # Save to shortlist
```

---

## Phase 3: CrewAI Integration

### New Flow: `TalentIntelligenceFlow`

**File:** `src/flows/talent_intelligence_flow.py`

```python
class TalentIntelligenceFlow(Flow):
    """
    AI-powered talent intelligence and look-alike matching.
    """
    
    @start()
    def analyze_job_description(self):
        """Extract requirements from JD."""
        # Use LLM to parse JD
        # Return structured requirements
        
    @listen(analyze_job_description)
    def search_talent_pool(self, requirements):
        """Query Elasticsearch for candidates."""
        # Use PersonSearchTool
        # Return candidate pool
        
    @listen(search_talent_pool)
    def analyze_career_paths(self, candidates):
        """Analyze career trajectories via Neo4j."""
        # Use CareerPathTool
        # Find common patterns
        
    @listen(analyze_career_paths)
    def rank_candidates(self, candidates, patterns):
        """Rank by fit score."""
        # ML-based scoring
        # Return ranked list
        
    @listen(rank_candidates)
    def generate_insights(self, rankings):
        """Generate market insights."""
        # Aggregations & analysis
        # Return insights
```

---

### New Tools for Agents

**File:** `src/crewai_custom_tools/talent_search_tools.py`

```python
class PersonSearchTool(BaseTool):
    """Full-text search across person database."""
    
class SkillAnalysisTool(BaseTool):
    """Analyze skill distributions and trends."""
    
class CareerPathTool(BaseTool):
    """Query Neo4j for career trajectories."""
    
class CompanyNetworkTool(BaseTool):
    """Analyze company-to-company talent flow."""
    
class LookAlikeSearchTool(BaseTool):
    """Find similar candidates based on profile."""
```

---

## Phase 4: UI Implementation Details

### Design System

**Colors & Themes:**
- Use existing theme from `frontend/src/styles/`
- Connection status colors:
  - Healthy: Green (#10B981)
  - Warning: Yellow (#F59E0B)
  - Error: Red (#EF4444)
  - Inactive: Gray (#6B7280)

**Typography:**
- Use existing font system
- Headings: Inter Bold
- Body: Inter Regular

**Components to Create:**

1. **ConnectionCard** - Display connection status
2. **SyncProgressBar** - Real-time sync progress
3. **CostTracker** - Display API costs
4. **QueryBuilder** - No-code query creation
5. **CandidateCard** - Display candidate profiles
6. **FitScoreIndicator** - Visual fit score (0-100)
7. **SkillsMatchChart** - Skills comparison viz
8. **CareerPathViz** - Neo4j graph visualization
9. **InsightCard** - AI-generated insights
10. **FlowProgressTracker** - CrewAI flow status

---

### Routing

```typescript
// Add to frontend/src/App.tsx
<Route path="/data-connections" element={<DataConnectionsPage />} />
<Route path="/data-connections/:id" element={<ConnectionDetailPage />} />
<Route path="/talent-intelligence" element={<TalentIntelligencePage />} />
<Route path="/talent-intelligence/:id" element={<AnalysisResultsPage />} />
```

---

### State Management

**Use React Query for:**
- Connection list
- Sync status
- Analysis results
- Candidate profiles

**Use SSE for:**
- Real-time sync progress
- Flow execution status
- Telemetry updates

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Merge current branch to main
- [ ] Create `feature/data-connections-ui` branch
- [ ] Set up new page routes
- [ ] Create base components
- [ ] Connect to existing connector APIs

### Phase 2: Data Connections UI (Week 2)
- [ ] Build ConnectionsListView
- [ ] Create CreateConnectionModal
- [ ] Implement ConnectionDetailView
- [ ] Add SyncProgressWidget with SSE
- [ ] Test with PDL integration

### Phase 3: Talent Intelligence Backend (Week 3)
- [ ] Build TalentIntelligenceFlow
- [ ] Create agent tools (Person, Skill, Career, Company)
- [ ] Implement new API endpoints
- [ ] Add SSE for flow progress
- [ ] Write tests

### Phase 4: Talent Intelligence UI (Week 4)
- [ ] Build JobDescriptionInput
- [ ] Create IdealCandidateBuilder
- [ ] Implement AnalysisProgressView
- [ ] Build CandidateMatchResults
- [ ] Add InsightsDashboard
- [ ] Test end-to-end

### Phase 5: Polish & Deploy (Week 5)
- [ ] Add error handling
- [ ] Implement loading states
- [ ] Add analytics tracking
- [ ] Write documentation
- [ ] Deploy to staging
- [ ] User testing

---

## Tech Stack

**Frontend:**
- React 18
- TypeScript
- TailwindCSS
- React Query
- Recharts (visualizations)
- D3.js (Neo4j graph viz)
- react-markdown (JD editor)

**Backend:**
- FastAPI (existing)
- CrewAI (existing)
- Celery (existing)
- SSE (Server-Sent Events)

**Data:**
- PostgreSQL (existing)
- Elasticsearch (existing)
- Neo4j (existing)
- Redis (existing)

---

## Success Metrics

1. **User Experience:**
   - Connection setup < 2 minutes
   - Analysis complete < 30 seconds
   - Page load time < 2 seconds

2. **Functionality:**
   - 100% connector APIs working
   - 95%+ analysis accuracy
   - 99% uptime

3. **Performance:**
   - Support 100+ concurrent analyses
   - Handle 10K+ candidate searches
   - Real-time updates < 500ms latency

---

## Next Steps

1. **Merge to main** ← Do this now
2. **Create UI branch** ← Do this now
3. **Review existing UI components** for reuse
4. **Start with Phase 1** (Foundation)
5. **Iterate with user feedback**

---

## Questions to Clarify

1. Should job descriptions be saved/versioned?
2. Do users need role-based access (who can create connections)?
3. Should we support exporting candidate lists?
4. Do we need integration with ATS (Applicant Tracking System)?
5. Should analysis results be shareable (public links)?

---

**Status:** ✅ Plan Complete - Ready to Implement  
**Estimated Timeline:** 5 weeks  
**Team Size:** 1-2 developers  
**Complexity:** Medium-High

