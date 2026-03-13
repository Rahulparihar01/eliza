# PDL Search Infrastructure - Deployment & Testing Guide

**Date:** October 9, 2025  
**Purpose:** Deploy and validate PDL ingestion + search infrastructure  
**Goal:** Ensure search is working before building agent/flow integrations

---

## Phase 1: Deployment

### Step 1: Build and Deploy Services

```bash
cd /Users/scottgay/Documents/Eliza/eliza-platform

# 1. Build all services
docker-compose -f docker/docker-compose.yml build \
    app \
    celery-worker \
    celery-ingestion-worker

# 2. Start infrastructure (if not already running)
docker-compose -f docker/docker-compose.yml up -d \
    postgres \
    redis \
    elasticsearch \
    neo4j \
    logstash

# Wait for services to be healthy
sleep 60

# 3. Start application services
docker-compose -f docker/docker-compose.yml up -d \
    app \
    celery-worker \
    celery-ingestion-worker \
    flower

# 4. Check service health
docker-compose -f docker/docker-compose.yml ps
```

### Step 2: Verify Service Health

```bash
# Check Elasticsearch
curl http://localhost:9200/_cluster/health | jq

# Check Neo4j
docker exec docker-neo4j-1 cypher-shell -u neo4j -p password \
    "RETURN 'Neo4j is running' as status"

# Check API health
curl http://localhost:5001/health/ready | jq

# Check Celery workers
docker-compose -f docker/docker-compose.yml logs celery-ingestion-worker --tail=50

# Check Flower (Celery UI)
open http://localhost:5555
```

---

## Phase 2: Run PDL Ingestion

### Step 1: Create PDL Connector Configuration

```bash
# Get auth token
TOKEN=$(curl -X POST http://localhost:5001/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "your_password"
  }' | jq -r '.access_token')

# Create PDL connector
curl -X POST http://localhost:5001/v1/connectors/configurations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "PDL People Search",
    "connector_type": "people_data_labs",
    "config": {
      "api_key": "5bc8459782ab4964e99f96cf3638d9d9f96c9c06aac3e1fd92ddf554386cdde7"
    },
    "sync_mode": "full",
    "schedule_enabled": false
  }' | jq
```

### Step 2: Run Initial Sync (Small Test)

```bash
# Trigger sync with limited query
curl -X POST http://localhost:5001/v1/connectors/configurations/{config_id}/trigger \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "job_title": "data engineer",
      "job_company_name": "netflix"
    },
    "max_records": 10
  }' | jq

# Get sync run ID from response
SYNC_RUN_ID="..."
```

### Step 3: Monitor Sync Progress

```bash
# Check sync status
curl -X GET "http://localhost:5001/v1/connectors/sync-runs/${SYNC_RUN_ID}" \
  -H "Authorization: Bearer $TOKEN" | jq

# Watch Celery task in Flower
open "http://localhost:5555/task/${TASK_ID}"

# Monitor logs
docker-compose -f docker/docker-compose.yml logs -f celery-ingestion-worker

# Check database
docker exec docker-postgres-1 psql -U user -d ai_enablement -c "
  SELECT 
    sync_id, 
    status, 
    records_extracted, 
    records_loaded,
    started_at,
    completed_at
  FROM connector_sync_runs 
  ORDER BY started_at DESC 
  LIMIT 5;
"
```

---

## Phase 3: Validate Data Pipeline

### Step 1: Verify PostgreSQL Data

```bash
# Check PDL persons table
docker exec docker-postgres-1 psql -U user -d ai_enablement -c "
  SELECT 
    COUNT(*) as total_persons,
    COUNT(DISTINCT customer_id) as customers,
    COUNT(DISTINCT job_company_name) as companies
  FROM pdl_persons;
"

# Sample person data
docker exec docker-postgres-1 psql -U user -d ai_enablement -c "
  SELECT 
    pdl_id,
    full_name,
    job_title,
    job_company_name,
    array_length(skills, 1) as skill_count
  FROM pdl_persons 
  LIMIT 5;
"
```

### Step 2: Verify Elasticsearch Sync

```bash
# Check if index was created
curl http://localhost:9200/_cat/indices?v | grep pdl

# Check document count
curl http://localhost:9200/test_customer_pdl_persons/_count | jq

# Sample documents
curl -X GET http://localhost:9200/test_customer_pdl_persons/_search \
  -H "Content-Type: application/json" \
  -d '{
    "size": 5,
    "query": {"match_all": {}}
  }' | jq '.hits.hits[]._source | {name: .full_name, title: .job_title, company: .job_company_name}'
```

### Step 3: Verify Neo4j Sync

```bash
# Check node counts
docker exec docker-neo4j-1 cypher-shell -u neo4j -p password "
  MATCH (n) 
  RETURN labels(n)[0] as label, count(*) as count 
  ORDER BY count DESC;
"

# Check Person nodes
docker exec docker-neo4j-1 cypher-shell -u neo4j -p password "
  MATCH (p:Person) 
  RETURN p.name, p.current_title 
  LIMIT 5;
"

# Check relationships
docker exec docker-neo4j-1 cypher-shell -u neo4j -p password "
  MATCH (p:Person)-[r]->(n) 
  RETURN type(r) as relationship, count(*) as count 
  GROUP BY type(r);
"

# Sample career path
docker exec docker-neo4j-1 cypher-shell -u neo4j -p password "
  MATCH (p:Person)-[:WORKS_AT]->(c:Company)
  RETURN p.name, c.name, p.current_title
  LIMIT 5;
"
```

---

## Phase 4: Test Search Functionality

### Test 1: Full-Text Search

```bash
# Search for "data engineer"
curl -X POST http://localhost:5001/v1/search/persons \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "data engineer python",
    "size": 10
  }' | jq '.hits[] | {name: .full_name, title: .job_title, score: .score}'
```

**Expected Result:**
- Returns 10 results
- Relevant matches (data engineers with Python skills)
- Scores ranked by relevance
- Response time < 100ms

### Test 2: Filtered Search

```bash
# Search with filters
curl -X POST http://localhost:5001/v1/search/persons \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "engineer",
    "filters": {
      "company": "Netflix",
      "skills": ["Python", "AWS"],
      "min_experience": 5
    },
    "size": 10
  }' | jq
```

**Expected Result:**
- Only Netflix employees
- Must have Python AND AWS skills
- 5+ years experience
- Filtered results

### Test 3: Skill-Based Search

```bash
# Find people with specific skills
curl -X POST http://localhost:5001/v1/search/persons/by-skills \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "skills": ["Python", "Machine Learning", "AWS"],
    "min_match": 2,
    "size": 10
  }' | jq '.hits[] | {name: .full_name, matched: .matched_skills, count: .match_count}'
```

**Expected Result:**
- Ranked by skill match count
- Shows which skills matched
- At least 2 of 3 skills present

### Test 4: Career Transitions (Neo4j)

```bash
# Find people who moved from Microsoft to Netflix
curl -X POST http://localhost:5001/v1/search/persons/career-transitions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "from_company": "Microsoft",
    "to_company": "Netflix",
    "limit": 20
  }' | jq '.transitions[] | {name: .name, from_title: .previous_title, to_title: .current_title}'
```

**Expected Result:**
- List of people who made this transition
- Shows previous and current titles
- Transition dates

### Test 5: Company Network (Neo4j)

```bash
# Find companies connected to Netflix through employees
curl -X POST http://localhost:5001/v1/search/companies/network \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Netflix",
    "max_hops": 2,
    "limit": 20
  }' | jq '.connected_companies[] | {company: .company_name, shared: .shared_people}'
```

**Expected Result:**
- List of companies with shared employees
- Ranked by number of connections
- Shows network strength

### Test 6: Skill Co-occurrence (Neo4j)

```bash
# Find skills that commonly occur with Python
curl -X POST http://localhost:5001/v1/search/skills/cooccurrence \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "skill": "Python",
    "top_n": 10
  }' | jq '.cooccurring_skills[] | {skill: .cooccurring_skill, count: .count}'
```

**Expected Result:**
- List of skills commonly paired with Python
- Ranked by frequency
- Reveals skill stacks

### Test 7: Aggregations

```bash
# Top companies
curl -X POST http://localhost:5001/v1/search/aggregate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "field": "job_company_name",
    "size": 20
  }' | jq '.buckets[] | {company: .key, count: .count}'

# Top skills
curl -X POST http://localhost:5001/v1/search/aggregate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "field": "skills",
    "size": 20
  }' | jq '.buckets[] | {skill: .key, count: .count}'
```

**Expected Result:**
- Distribution of values
- Top N most common
- Useful for analytics

---

## Phase 5: Performance Validation

### Benchmark Search Performance

```python
# Create performance test script
# tests/search/benchmark_search_performance.py

import time
import requests
from statistics import mean, median

def benchmark_search(token: str, queries: list, iterations: int = 10):
    """Benchmark search performance."""
    results = []
    
    for query in queries:
        times = []
        
        for _ in range(iterations):
            start = time.time()
            
            response = requests.post(
                'http://localhost:5001/v1/search/persons',
                headers={'Authorization': f'Bearer {token}'},
                json={'query': query, 'size': 10}
            )
            
            elapsed = (time.time() - start) * 1000  # ms
            times.append(elapsed)
        
        results.append({
            'query': query,
            'mean': mean(times),
            'median': median(times),
            'min': min(times),
            'max': max(times)
        })
    
    return results

# Run benchmark
queries = [
    'data engineer',
    'machine learning engineer python',
    'senior software engineer netflix',
    'product manager',
    'data scientist aws'
]

results = benchmark_search(TOKEN, queries)

for r in results:
    print(f"Query: {r['query']}")
    print(f"  Mean: {r['mean']:.2f}ms")
    print(f"  Median: {r['median']:.2f}ms")
    print(f"  Min: {r['min']:.2f}ms")
    print(f"  Max: {r['max']:.2f}ms")
    print()
```

**Performance Targets:**
- ✅ Mean latency: < 100ms
- ✅ P95 latency: < 200ms
- ✅ P99 latency: < 500ms

### Load Test

```bash
# Use Apache Bench or wrk
ab -n 1000 -c 10 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -p search_payload.json \
  http://localhost:5001/v1/search/persons
```

**Load Targets:**
- ✅ 100+ requests/second
- ✅ < 1% error rate
- ✅ Consistent latency under load

---

## Phase 6: Data Quality Validation

### Check Data Completeness

```sql
-- Field population rates
SELECT 
  COUNT(*) as total,
  COUNT(full_name) * 100.0 / COUNT(*) as name_pct,
  COUNT(job_title) * 100.0 / COUNT(*) as title_pct,
  COUNT(job_company_name) * 100.0 / COUNT(*) as company_pct,
  COUNT(skills) * 100.0 / COUNT(*) as skills_pct,
  COUNT(primary_email) * 100.0 / COUNT(*) as email_pct,
  COUNT(linkedin_url) * 100.0 / COUNT(*) as linkedin_pct
FROM pdl_persons;
```

**Quality Targets:**
- ✅ Name: 100%
- ✅ Job title: > 90%
- ✅ Company: > 90%
- ✅ Skills: > 80%
- ✅ Email: > 70%
- ✅ LinkedIn: > 50%

### Check for Duplicates

```sql
-- Check for duplicate pdl_ids
SELECT pdl_id, customer_id, COUNT(*) 
FROM pdl_persons 
GROUP BY pdl_id, customer_id 
HAVING COUNT(*) > 1;

-- Should return 0 rows (unique constraint enforced)
```

### Validate Search Sync

```bash
# Compare counts: PostgreSQL vs Elasticsearch
PG_COUNT=$(docker exec docker-postgres-1 psql -U user -d ai_enablement -t -c "SELECT COUNT(*) FROM pdl_persons;")
ES_COUNT=$(curl -s http://localhost:9200/test_customer_pdl_persons/_count | jq '.count')

echo "PostgreSQL: $PG_COUNT"
echo "Elasticsearch: $ES_COUNT"

# Should be equal (or ES slightly behind if syncing)
```

---

## Phase 7: Agent/Flow Integration Planning

### CrewAI Tool Design

Now that search is working, we need to design tools for agents to use:

**Tool 1: PersonSearchTool**
```python
from crewai_tools import BaseTool

class PersonSearchTool(BaseTool):
    name: str = "Search People"
    description: str = """
    Search for people in our database by skills, title, company, location.
    
    Use this when you need to:
    - Find candidates with specific skills
    - Search for people at a company
    - Look for people with certain job titles
    - Find people in a location
    
    Examples:
    - "Find senior data engineers with Python skills"
    - "Search for machine learning experts at Netflix"
    - "Find product managers in San Francisco"
    """
    
    def _run(self, query: str, filters: dict = None, size: int = 10) -> str:
        # Call PersonSearchService
        results = self.search_service.search_persons(query, filters, size)
        
        # Format for LLM consumption
        return self._format_results(results)
```

**Tool 2: SkillAnalysisTool**
```python
class SkillAnalysisTool(BaseTool):
    name: str = "Analyze Skills"
    description: str = """
    Analyze skill patterns and relationships.
    
    Use this when you need to:
    - Find what skills go together
    - Understand skill stacks
    - Identify skill trends
    
    Examples:
    - "What skills commonly appear with Python?"
    - "What's a typical data engineer skill stack?"
    """
    
    def _run(self, skill: str, top_n: int = 10) -> str:
        results = self.search_service.get_skill_cooccurrence(skill, top_n)
        return self._format_skill_analysis(results)
```

**Tool 3: CareerPathTool**
```python
class CareerPathTool(BaseTool):
    name: str = "Analyze Career Paths"
    description: str = """
    Analyze career transitions and patterns.
    
    Use this when you need to:
    - Find people who moved between companies
    - Understand typical career progressions
    - Identify talent flow patterns
    
    Examples:
    - "Who moved from Microsoft to Netflix?"
    - "What's a typical path to senior engineer?"
    """
    
    def _run(self, from_company: str, to_company: str) -> str:
        results = self.search_service.find_career_transitions(
            from_company, to_company
        )
        return self._format_career_paths(results)
```

**Tool 4: LookAlikeCandidateTool**
```python
class LookAlikeCandidateTool(BaseTool):
    name: str = "Find Look-Alike Candidates"
    description: str = """
    Find candidates similar to a reference person.
    
    Use this when you need to:
    - Find people like a top performer
    - Build a candidate pipeline
    - Identify similar profiles
    
    Inputs: person_id or profile description
    """
    
    def _run(self, reference_person_id: str = None, profile: dict = None) -> str:
        # 1. Get reference person's profile
        if reference_person_id:
            ref = self.search_service.get_person_by_id(reference_person_id)
        else:
            ref = profile
        
        # 2. Search by skills
        skill_matches = self.search_service.search_by_skills(
            ref['skills'], 
            min_match=len(ref['skills']) // 2
        )
        
        # 3. Filter by career progression (Neo4j)
        # 4. Rank by similarity score
        # 5. Return top candidates
        
        return self._format_candidates(candidates)
```

### Agent Flow Example

```python
# Example: Recruitment agent using search tools

from crewai import Agent, Task, Crew

search_agent = Agent(
    role="Talent Researcher",
    goal="Find the best candidates for open positions",
    backstory="Expert at finding and qualifying candidates",
    tools=[
        PersonSearchTool(search_service),
        SkillAnalysisTool(search_service),
        CareerPathTool(search_service),
        LookAlikeCandidateTool(search_service)
    ]
)

task = Task(
    description="""
    Find 10 senior data engineer candidates similar to our top performer.
    
    Our top performer:
    - Skills: Python, Spark, AWS, Machine Learning
    - Career: Startup → Big Tech → Current company
    - Location: SF Bay Area
    - Experience: 8 years
    
    Find similar candidates with:
    1. Similar skill stack (at least 3/4 skills)
    2. Similar career progression
    3. Currently at target companies (Netflix, Airbnb, Uber)
    """,
    agent=search_agent,
    expected_output="List of 10 qualified candidates with justification"
)

crew = Crew(agents=[search_agent], tasks=[task])
result = crew.kickoff()
```

---

## Validation Checklist

### ✅ Infrastructure
- [ ] All Docker services running
- [ ] Elasticsearch healthy
- [ ] Neo4j healthy
- [ ] Celery workers active
- [ ] No errors in logs

### ✅ Data Pipeline
- [ ] PDL connector configured
- [ ] Sync completes successfully
- [ ] Data in PostgreSQL (pdl_persons)
- [ ] Data in Elasticsearch (index created)
- [ ] Data in Neo4j (nodes + relationships)
- [ ] Counts match across stores

### ✅ Search Functionality
- [ ] Full-text search works
- [ ] Filtered search works
- [ ] Skill search works
- [ ] Career transitions work (Neo4j)
- [ ] Company network works (Neo4j)
- [ ] Skill co-occurrence works (Neo4j)
- [ ] Aggregations work
- [ ] Response times < 100ms

### ✅ Data Quality
- [ ] > 90% field completeness
- [ ] No duplicates
- [ ] Valid data formats
- [ ] Skills populated
- [ ] Work history present

### ✅ Performance
- [ ] Search latency < 100ms
- [ ] Can handle 100+ req/sec
- [ ] No memory leaks
- [ ] Celery queue draining

### ✅ Ready for Agent Integration
- [ ] Search API stable
- [ ] Results format consistent
- [ ] Error handling robust
- [ ] Tool interfaces designed

---

## Next Steps

Once all validation passes:

1. **Build CrewAI Tools** (1-2 days)
   - Implement PersonSearchTool
   - Implement SkillAnalysisTool
   - Implement CareerPathTool
   - Implement LookAlikeCandidateTool

2. **Create Agent Flow** (2-3 days)
   - Design recruitment agent
   - Test with real queries
   - Refine prompts
   - Validate output quality

3. **User Testing** (1 week)
   - Run real recruitment searches
   - Gather feedback
   - Measure search quality
   - Iterate on relevance

4. **Production Deployment**
   - Deploy to production
   - Monitor metrics
   - Set up alerts
   - Document for users

---

**Ready to start testing!** 🚀

Run through this guide step-by-step, and we'll catch any issues before building agent integrations.

