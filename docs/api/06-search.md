# Search API

**Base Path:** `/search`

**Required Permission:** Inherited from authentication

## Overview

The Search API provides advanced search capabilities across person data using multiple data stores:
- **Elasticsearch**: Full-text search with fuzzy matching
- **Neo4j**: Graph-based relationship queries
- **PostgreSQL**: Fallback for basic queries

## Key Features

- **Full-Text Search**: Semantic search across multiple fields
- **Skill Matching**: Find people with specific skill combinations
- **Career Path Analysis**: Track transitions between companies
- **Company Networks**: Discover company relationships through people
- **Skill Co-occurrence**: Identify commonly paired skills
- **Aggregations**: Analytics on person data distribution

---

## Endpoints

### POST /search/persons

Full-text search for persons across all fields.

**Request:**
```json
{
  "query": "machine learning engineer python",
  "filters": {
    "location_country": "united states",
    "experience_years_min": 5,
    "skills": ["python"]
  },
  "size": 20,
  "from_": 0
}
```

**Parameters:**
- `query` (string, required) - Search query
- `filters` (object, optional) - Additional filters
  - `location_country` (string)
  - `location_region` (string)
  - `job_company_name` (string)
  - `job_title_role` (string)
  - `skills` (array of strings)
  - `experience_years_min` (integer)
  - `experience_years_max` (integer)
- `size` (integer, default: 10, max: 100) - Number of results
- `from_` (integer, default: 0) - Pagination offset

**Response:** `200 OK`
```json
{
  "total": 150,
  "hits": [
    {
      "pdl_id": "qEnOZ5Oh0poWnQ1luFBfVw_0000",
      "full_name": "Jane Doe",
      "job_title": "Senior Machine Learning Engineer",
      "job_company_name": "Tech Corp",
      "job_company_website": "techcorp.com",
      "location_country": "united states",
      "location_locality": "San Francisco",
      "location_region": "California",
      "skills": ["python", "tensorflow", "machine learning"],
      "experience_years": 8,
      "score": 12.5,
      "linkedin_url": "https://linkedin.com/in/janedoe"
    },
    ...
  ],
  "took": 85,
  "max_score": 12.5,
  "fallback": false
}
```

**Search Fields & Weights:**

The search algorithm searches across multiple fields with different weights:

| Field | Weight | Example |
|-------|--------|---------|
| `full_name` | 3.0 | "Jane Doe" |
| `job_title` | 2.0 | "Machine Learning Engineer" |
| `skills` | 1.5 | ["python", "tensorflow"] |
| `job_company_name` | 1.0 | "Tech Corp" |
| `location_locality` | 0.5 | "San Francisco" |

**Query Syntax:**
- **Simple**: `"python engineer"` - Searches all fields
- **Phrase**: `"machine learning"` - Exact phrase match
- **Boolean**: `"python AND (tensorflow OR pytorch)"` - Boolean operators
- **Fuzzy**: `"enginer~"` - Handles typos (1-2 character difference)

**Fallback Mode:**

If Elasticsearch is unavailable, the system falls back to PostgreSQL with basic text search. Response includes `"fallback": true` to indicate degraded search quality.

---

### POST /search/persons/by-skills

Find persons with specific skill combinations.

**Request:**
```json
{
  "skills": ["python", "tensorflow", "aws"],
  "min_match": 2,
  "size": 50
}
```

**Parameters:**
- `skills` (array, required) - List of skills to match
- `min_match` (integer, default: 1) - Minimum number of skills required
- `size` (integer, default: 10, max: 100) - Results limit

**Response:** `200 OK`
```json
{
  "total": 85,
  "hits": [
    {
      "pdl_id": "...",
      "full_name": "Jane Doe",
      "job_title": "ML Engineer",
      "matched_skills": ["python", "tensorflow", "aws"],
      "match_count": 3,
      "total_skills": 15,
      "skills": ["python", "tensorflow", "aws", "docker", "kubernetes", ...],
      "score": 3.0
    },
    ...
  ]
}
```

**Ranking:**
- Results ranked by number of matched skills (descending)
- Secondary ranking by total skill count
- Persons with more matching skills appear first

**Use Cases:**
- Finding candidates with specific tech stacks
- Identifying skill gaps in talent pools
- Building skill-based candidate shortlists

---

### POST /search/persons/career-transitions

Find people who moved from one company to another.

**Request:**
```json
{
  "from_company": "Google",
  "to_company": "Meta",
  "limit": 100
}
```

**Parameters:**
- `from_company` (string, required) - Previous company name
- `to_company` (string, required) - Current company name
- `limit` (integer, default: 50, max: 200) - Results limit

**Response:** `200 OK`
```json
{
  "from_company": "Google",
  "to_company": "Meta",
  "transitions": [
    {
      "pdl_id": "...",
      "full_name": "John Smith",
      "previous_job_title": "Software Engineer",
      "previous_start_date": "2018-06-01",
      "previous_end_date": "2023-05-31",
      "current_job_title": "Senior Software Engineer",
      "current_start_date": "2023-06-01",
      "transition_gap_months": 0,
      "skills": ["python", "distributed systems"],
      "location": "San Francisco, California"
    },
    ...
  ],
  "total": 15
}
```

**Graph Query:**

Uses Neo4j to traverse person-company relationships:
```cypher
MATCH (p:Person)-[:WORKED_AT]->(from:Company {name: 'Google'})
MATCH (p)-[:WORKS_AT]->(to:Company {name: 'Meta'})
RETURN p
```

**Analysis Insights:**
- **Transition Gap**: Time between jobs (positive = gap, negative = overlap)
- **Common Skills**: Skills carried between companies
- **Title Changes**: Promotions or lateral moves
- **Location Changes**: Geographic mobility

**Use Cases:**
- Talent pipeline analysis
- Competitive intelligence
- Recruitment targeting
- Understanding talent flow

---

### POST /search/companies/network

Get network of companies connected through shared employees.

**Request:**
```json
{
  "company_name": "Google",
  "max_hops": 2,
  "limit": 50
}
```

**Parameters:**
- `company_name` (string, required) - Source company
- `max_hops` (integer, default: 1, max: 3) - Graph traversal depth
- `limit` (integer, default: 20, max: 100) - Results limit

**Response:** `200 OK`
```json
{
  "source_company": "Google",
  "connected_companies": [
    {
      "company_name": "Meta",
      "connection_count": 145,
      "connection_type": "employee_transition",
      "common_roles": ["Software Engineer", "Product Manager"],
      "avg_experience_years": 7.5,
      "distance": 1
    },
    {
      "company_name": "Apple",
      "connection_count": 98,
      "connection_type": "employee_transition",
      "common_roles": ["Engineering Manager", "Senior Engineer"],
      "avg_experience_years": 8.2,
      "distance": 1
    },
    {
      "company_name": "Netflix",
      "connection_count": 23,
      "connection_type": "indirect",
      "distance": 2
    },
    ...
  ],
  "total": 150
}
```

**Graph Traversal:**
```
Google → (people who worked at both) → Meta
       → (people who worked at both) → Apple
       → Meta → (people who worked at both) → Netflix (distance 2)
```

**Connection Types:**
- `employee_transition` - Direct transitions (distance 1)
- `indirect` - Connected through intermediate companies (distance > 1)
- `current_overlap` - People currently at both companies

**Use Cases:**
- Competitive landscape analysis
- Talent sourcing strategy
- Company relationship mapping
- Market intelligence

---

### POST /search/skills/cooccurrence

Analyze skills that commonly occur together.

**Request:**
```json
{
  "skill": "python",
  "top_n": 20
}
```

**Parameters:**
- `skill` (string, required) - Target skill
- `top_n` (integer, default: 10, max: 50) - Number of results

**Response:** `200 OK`
```json
{
  "skill": "python",
  "cooccurring_skills": [
    {
      "skill": "machine learning",
      "cooccurrence_count": 850,
      "percentage": 85.0,
      "correlation_score": 0.78
    },
    {
      "skill": "tensorflow",
      "cooccurrence_count": 720,
      "percentage": 72.0,
      "correlation_score": 0.65
    },
    {
      "skill": "aws",
      "cooccurrence_count": 680,
      "percentage": 68.0,
      "correlation_score": 0.61
    },
    ...
  ],
  "total": 45,
  "sample_size": 1000
}
```

**Metrics Explained:**
- **Cooccurrence Count**: Number of people with both skills
- **Percentage**: % of people with target skill who also have this skill
- **Correlation Score**: Statistical correlation (0-1, higher = stronger relationship)
- **Sample Size**: Total people with the target skill

**Use Cases:**
- Understanding skill ecosystems
- Building training programs
- Job description optimization
- Skill gap identification

**Example Insight:**
If 85% of people with "python" also have "machine learning", this suggests:
- Python is fundamental to ML roles
- Training Python developers in ML is natural progression
- Job postings for ML roles should require Python

---

### POST /search/aggregate

Get aggregation counts for any field.

**Request:**
```json
{
  "field": "job_company_name",
  "size": 50,
  "filters": {
    "location_country": "united states",
    "skills": ["python"]
  }
}
```

**Parameters:**
- `field` (string, required) - Field to aggregate
  - Options: `job_company_name`, `job_title_role`, `skills`, `location_country`, `location_region`, `education_level`
- `size` (integer, default: 10, max: 100) - Number of buckets
- `filters` (object, optional) - Filter the dataset before aggregation

**Response:** `200 OK`
```json
{
  "field": "job_company_name",
  "total_docs": 5000,
  "buckets": [
    {
      "key": "Google",
      "doc_count": 450,
      "percentage": 9.0
    },
    {
      "key": "Meta",
      "doc_count": 380,
      "percentage": 7.6
    },
    {
      "key": "Amazon",
      "doc_count": 320,
      "percentage": 6.4
    },
    ...
  ]
}
```

**Common Aggregations:**

**Top Companies:**
```json
{"field": "job_company_name", "size": 20}
```

**Top Skills:**
```json
{"field": "skills", "size": 50}
```

**Location Distribution:**
```json
{"field": "location_country", "size": 10}
```

**Education Levels:**
```json
{"field": "education_level", "size": 5}
```

**Use Cases:**
- Dashboard analytics
- Market research
- Talent pool analysis
- Faceted search filters

---

### GET /search/persons/{pdl_id}

Get a single person by their PDL ID.

**Response:** `200 OK`
```json
{
  "pdl_id": "qEnOZ5Oh0poWnQ1luFBfVw_0000",
  "full_name": "Jane Doe",
  "job_title": "Senior ML Engineer",
  "job_company_name": "Tech Corp",
  "skills": ["python", "tensorflow"],
  "experience_years": 8,
  "education": [
    {
      "school": "Stanford University",
      "degree": "Master of Science",
      "field": "Computer Science",
      "start_date": "2012-09-01",
      "end_date": "2014-06-01"
    }
  ],
  "work_history": [
    {
      "company": "Tech Corp",
      "title": "Senior ML Engineer",
      "start_date": "2020-01-01",
      "is_current": true
    },
    ...
  ],
  "location": {
    "country": "united states",
    "region": "California",
    "locality": "San Francisco"
  },
  "contact": {
    "linkedin_url": "https://linkedin.com/in/janedoe",
    "github_url": "https://github.com/janedoe"
  }
}
```

**Errors:**
- `404` - Person not found

---

## Search Performance

### Elasticsearch (Optimal Path)

- **Query Time**: 50-200ms for most queries
- **Capacity**: Scales to millions of records
- **Features**: Full-text search, fuzzy matching, aggregations
- **Availability**: High availability with replication

### Neo4j (Graph Queries)

- **Query Time**: 100-500ms for graph traversals
- **Capacity**: Optimized for relationship queries
- **Features**: Career paths, company networks, skill graphs
- **Depth Limits**: Max 3 hops for performance

### PostgreSQL (Fallback)

- **Query Time**: 200-1000ms for full-text search
- **Capacity**: Works but slower for large datasets
- **Features**: Basic text search, exact matches
- **Limitation**: No fuzzy matching or advanced features

---

## Query Optimization Tips

### 1. Use Specific Queries

❌ **Bad**: `"engineer"`
✅ **Good**: `"machine learning engineer"`

Specific queries reduce result set and improve relevance.

### 2. Apply Filters

```json
{
  "query": "engineer",
  "filters": {
    "location_country": "united states",
    "skills": ["python"]
  }
}
```

Filters reduce search space and improve performance.

### 3. Limit Result Size

```json
{
  "query": "engineer",
  "size": 20  // Don't request 1000 results unless needed
}
```

Smaller result sets are faster to fetch and rank.

### 4. Use Pagination

```json
{
  "query": "engineer",
  "size": 20,
  "from_": 0  // First page
}

// Next page
{
  "from_": 20  // Second page
}
```

Pagination is more efficient than large single queries.

### 5. Cache Common Queries

Frequently used queries (e.g., "top companies") should be cached at the application level.

---

## Search Patterns

### Talent Sourcing

**Find candidates with specific skills in a location:**
```json
{
  "query": "machine learning",
  "filters": {
    "skills": ["python", "tensorflow"],
    "location_country": "united states",
    "experience_years_min": 3
  },
  "size": 50
}
```

### Competitive Intelligence

**Track talent flow between companies:**
```json
{
  "from_company": "Competitor Corp",
  "to_company": "Our Company",
  "limit": 100
}
```

### Market Analysis

**Understand skill distribution:**
```json
{
  "field": "skills",
  "size": 50,
  "filters": {
    "job_title_role": "software engineer",
    "location_country": "united states"
  }
}
```

### Skill Planning

**Find complementary skills:**
```json
{
  "skill": "python",
  "top_n": 20
}
```

---

## Multi-Data-Store Architecture

The Search API intelligently routes queries to appropriate data stores:

```
┌─────────────────────────────────────────┐
│         Search API Request              │
└─────────────┬───────────────────────────┘
              │
              ├──> Full-Text Search → Elasticsearch
              │
              ├──> Career Paths → Neo4j
              │
              ├──> Company Networks → Neo4j
              │
              ├──> Skill Co-occurrence → PostgreSQL + Neo4j
              │
              └──> Aggregations → Elasticsearch
```

**Benefits:**
- Each data store optimized for specific query types
- Automatic failover to PostgreSQL if ES/Neo4j unavailable
- Consistent API regardless of underlying implementation

---

## Troubleshooting

### "Search returned no results"

**Causes:**
1. Query too specific
2. No matching data
3. Typos in query

**Solutions:**
1. Broaden query terms
2. Remove filters
3. Use fuzzy matching (append `~` to terms)
4. Check data availability: `POST /search/aggregate`

### "Fallback: true in response"

**Cause:** Elasticsearch is unavailable

**Impact:** Search quality degraded (no fuzzy matching, slower)

**Solution:** Check Elasticsearch health, restart if needed

### Slow Query Performance

**Causes:**
1. Query too broad
2. No filters
3. Large result set
4. Elasticsearch not optimized

**Solutions:**
1. Add specific terms
2. Apply location/skill filters
3. Reduce `size` parameter
4. Check index health

### Graph Query Timeout

**Cause:** Too many hops or no limit on company network query

**Solution:** Reduce `max_hops` to 1-2, apply stricter `limit`

---

## Best Practices

1. **Always set size limits**: Prevents accidental large queries
2. **Use filters when possible**: Dramatically improves performance
3. **Implement client-side caching**: Cache common queries and aggregations
4. **Handle fallback gracefully**: UI should indicate degraded search
5. **Monitor query performance**: Track slow queries for optimization
6. **Validate inputs**: Sanitize user input to prevent injection
7. **Use pagination**: Better UX and performance than large single queries
8. **Index regularly**: Keep Elasticsearch index up to date


