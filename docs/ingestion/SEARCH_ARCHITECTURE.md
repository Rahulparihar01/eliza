# Search Infrastructure Architecture

**Date:** October 9, 2025  
**Status:** Design Document  
**Purpose:** Enable look-alike candidate search and employee pattern analysis

---

## Use Case: Finding Look-Alike Candidates

### Business Goal
Enable clients to:
1. **Identify ideal employee profiles** based on successful hires
2. **Find similar candidates** across large datasets
3. **Understand career patterns** (what paths lead to success)
4. **Discover skill clusters** (what skills co-occur)

### Example Queries

**"Find people like our best data engineer"**
```
Input: John Doe (Senior Data Engineer at Netflix)
Skills: Python, Spark, Kafka, AWS, SQL
Education: Stanford CS
Career: Microsoft → Uber → Netflix

Output: Similar candidates with:
- Similar skill combinations (weighted)
- Similar career progression patterns
- Same education tier
- Companies of similar scale/prestige
```

**"Who typically becomes a VP of Engineering?"**
```
Query career paths that lead to VP Engineering:
- Common previous roles
- Company progression patterns
- Typical years of experience
- Required skill evolution
```

---

## Architecture Overview

### Three-Tier Search Strategy

```
┌─────────────────────────────────────────────────────────────────────┐
│                     APPLICATION LAYER                                │
│                   PersonSearchService (Unified)                      │
│         • Routes queries to appropriate search engine                │
│         • Combines results from multiple sources                     │
│         • Caches frequent queries                                    │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
        ┌───────────────────────┴───────────────────────┐
        ↓                                               ↓
┌─────────────────────────┐                ┌─────────────────────────┐
│   ELASTICSEARCH          │                │       NEO4J             │
│   (Full-Text Search)     │                │   (Graph Analysis)      │
├─────────────────────────┤                ├─────────────────────────┤
│ • Keyword search         │                │ • Career paths          │
│ • Skills matching        │                │ • Company networks      │
│ • Faceted filtering      │                │ • Skill co-occurrence   │
│ • Aggregations           │                │ • Shortest paths        │
│ • Auto-complete          │                │ • Community detection   │
│ • Fuzzy matching         │                │ • Centrality metrics    │
└─────────────────────────┘                └─────────────────────────┘
        ↑                                               ↑
        └───────────────────────┬───────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        SOURCE OF TRUTH                               │
│                    PostgreSQL - PDLPerson                            │
│              • Normalized, typed, transactional                      │
│              • Sync triggers after transform                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Elasticsearch Design

### Index Schema: `pdl_persons`

**Optimized for:** Text search, filtering, aggregations, look-alike matching

```json
{
  "settings": {
    "number_of_shards": 2,
    "number_of_replicas": 1,
    "analysis": {
      "analyzer": {
        "skill_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "skill_synonyms"]
        },
        "name_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "asciifolding"]
        }
      },
      "filter": {
        "skill_synonyms": {
          "type": "synonym",
          "synonyms": [
            "js, javascript",
            "py, python",
            "k8s, kubernetes",
            "aws, amazon web services"
          ]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "pdl_id": {"type": "keyword"},
      "customer_id": {"type": "keyword"},
      
      "full_name": {
        "type": "text",
        "analyzer": "name_analyzer",
        "fields": {
          "keyword": {"type": "keyword"},
          "suggest": {
            "type": "completion",
            "analyzer": "name_analyzer"
          }
        }
      },
      
      "job_title": {
        "type": "text",
        "analyzer": "standard",
        "fields": {
          "keyword": {"type": "keyword"},
          "suggest": {"type": "completion"}
        }
      },
      "job_title_role": {"type": "keyword"},
      "job_title_levels": {"type": "keyword"},
      
      "job_company_name": {
        "type": "text",
        "fields": {
          "keyword": {"type": "keyword"},
          "suggest": {"type": "completion"}
        }
      },
      "job_company_size": {"type": "keyword"},
      "job_company_industry": {"type": "keyword"},
      
      "skills": {
        "type": "text",
        "analyzer": "skill_analyzer",
        "fields": {
          "keyword": {"type": "keyword"}
        }
      },
      
      "location_name": {"type": "text"},
      "location_country": {"type": "keyword"},
      "location_region": {"type": "keyword"},
      "location_metro": {"type": "keyword"},
      
      "inferred_years_experience": {"type": "integer"},
      "pdl_likelihood": {"type": "float"},
      
      "emails": {"type": "keyword"},
      "linkedin_url": {"type": "keyword"},
      
      "created_at": {"type": "date"},
      "updated_at": {"type": "date"}
    }
  }
}
```

### Key Search Patterns

#### 1. Skills-Based Search
```python
# Find people with specific skill combinations
{
  "query": {
    "bool": {
      "must": [
        {"match": {"skills": "Python"}},
        {"match": {"skills": "Machine Learning"}}
      ],
      "should": [
        {"match": {"skills": "TensorFlow"}},
        {"match": {"skills": "PyTorch"}}
      ]
    }
  }
}
```

#### 2. Look-Alike Search (More Like This)
```python
# Find people similar to a given person
{
  "query": {
    "more_like_this": {
      "fields": ["skills", "job_title", "job_company_name"],
      "like": [
        {
          "_id": "PDL123456"
        }
      ],
      "min_term_freq": 1,
      "max_query_terms": 25
    }
  }
}
```

#### 3. Aggregations (Pattern Discovery)
```python
# What skills do successful data engineers have?
{
  "query": {"match": {"job_title": "Data Engineer"}},
  "aggs": {
    "top_skills": {
      "terms": {"field": "skills.keyword", "size": 20}
    },
    "companies": {
      "terms": {"field": "job_company_name.keyword", "size": 10}
    },
    "experience_distribution": {
      "histogram": {
        "field": "inferred_years_experience",
        "interval": 2
      }
    }
  }
}
```

---

## Neo4j Design

### Graph Model

**Optimized for:** Relationship queries, path finding, network analysis

```
┌─────────────┐     WORKS_AT      ┌─────────────┐
│   Person    │──────────────────→│   Company   │
│             │                    │             │
│ - pdl_id    │                    │ - name      │
│ - name      │                    │ - size      │
│ - title     │                    │ - industry  │
└─────────────┘                    └─────────────┘
       │                                  ↑
       │ HAS_SKILL                        │
       ↓                                  │
┌─────────────┐                          │
│    Skill    │                          │
│             │                    PREVIOUSLY_AT
│ - name      │                          │
│ - category  │                          │
└─────────────┘                          │
       ↑                                 │
       │                           ┌─────────────┐
       │ REQUIRES_SKILL            │   Person    │
       │                           │ (past job)  │
       └───────────────────────────┘             │
                                   └─────────────┘
```

### Node Types

**Person Node**
```cypher
CREATE (p:Person {
  pdl_id: 'PDL123456',
  name: 'John Doe',
  current_title: 'Senior Data Engineer',
  years_experience: 8,
  linkedin_url: 'https://linkedin.com/in/johndoe'
})
```

**Company Node**
```cypher
CREATE (c:Company {
  name: 'Netflix',
  size: '5000-10000',
  industry: 'Entertainment'
})
```

**Skill Node**
```cypher
CREATE (s:Skill {
  name: 'Python',
  category: 'Programming Language'
})
```

### Relationship Types

**WORKS_AT** (Current Employment)
```cypher
CREATE (p)-[:WORKS_AT {
  title: 'Senior Data Engineer',
  start_date: date('2022-01-01'),
  is_current: true
}]->(c)
```

**PREVIOUSLY_AT** (Past Employment)
```cypher
CREATE (p)-[:PREVIOUSLY_AT {
  title: 'Data Engineer',
  start_date: date('2018-06-01'),
  end_date: date('2021-12-31'),
  duration_months: 42
}]->(c)
```

**HAS_SKILL** (Person → Skill)
```cypher
CREATE (p)-[:HAS_SKILL {
  proficiency: 'expert',
  years: 5
}]->(s)
```

**REQUIRES_SKILL** (Job/Company → Skill)
```cypher
CREATE (c)-[:REQUIRES_SKILL {
  importance: 'required'
}]->(s)
```

### Key Graph Queries

#### 1. Career Path Analysis
```cypher
// What paths lead from junior engineer to VP?
MATCH path = (start:Person {current_title: 'Junior Engineer'})-[:PREVIOUSLY_AT*]->
             (intermediate:Company)-[:PREVIOUSLY_AT*]->
             (end:Person {current_title: 'VP Engineering'})
RETURN path
LIMIT 10
```

#### 2. Company Transition Network
```cypher
// Where do people go after working at Google?
MATCH (p:Person)-[:PREVIOUSLY_AT]->(google:Company {name: 'Google'}),
      (p)-[:WORKS_AT]->(next:Company)
RETURN next.name, COUNT(p) as transitions
ORDER BY transitions DESC
LIMIT 10
```

#### 3. Skill Co-occurrence
```cypher
// What skills are commonly paired with Python?
MATCH (p:Person)-[:HAS_SKILL]->(python:Skill {name: 'Python'}),
      (p)-[:HAS_SKILL]->(other:Skill)
WHERE other.name <> 'Python'
RETURN other.name, COUNT(p) as co_occurrences
ORDER BY co_occurrences DESC
LIMIT 20
```

#### 4. Find Look-Alikes (Graph-Based)
```cypher
// Find people with similar career paths
MATCH (target:Person {pdl_id: 'PDL123456'})-[:PREVIOUSLY_AT]->(c1:Company),
      (similar:Person)-[:PREVIOUSLY_AT]->(c1),
      (similar)-[:PREVIOUSLY_AT]->(c2:Company),
      (target)-[:PREVIOUSLY_AT]->(c2)
WHERE target <> similar
WITH similar, COUNT(DISTINCT c1) as shared_companies
WHERE shared_companies >= 2
RETURN similar.name, similar.current_title, shared_companies
ORDER BY shared_companies DESC
LIMIT 10
```

#### 5. Shortest Career Path
```cypher
// What's the shortest path from Amazon to Netflix?
MATCH (start:Company {name: 'Amazon'}),
      (end:Company {name: 'Netflix'}),
      path = shortestPath((start)-[:PREVIOUSLY_AT|WORKS_AT*]-(end))
RETURN path
```

---

## Unified Search Service

### PersonSearchService API

```python
class PersonSearchService:
    """Unified search service routing queries to ES or Neo4j."""
    
    def __init__(self, es_client, neo4j_driver, pg_session):
        self.es = es_client
        self.neo4j = neo4j_driver
        self.pg = pg_session
        
    # === Elasticsearch Queries ===
    
    def search_by_skills(self, skills: List[str], filters: dict):
        """Find people with specific skills."""
        # Route to Elasticsearch
        
    def search_by_text(self, query: str):
        """Full-text search across all fields."""
        # Route to Elasticsearch
        
    def find_similar(self, pdl_id: str, limit: int = 10):
        """Find look-alike candidates (More Like This)."""
        # Route to Elasticsearch
        
    def aggregate_skills(self, job_title: str):
        """Get top skills for a job title."""
        # Route to Elasticsearch aggregations
        
    # === Neo4j Queries ===
    
    def find_career_paths(self, from_title: str, to_title: str):
        """Find common career progression paths."""
        # Route to Neo4j graph query
        
    def company_transitions(self, company_name: str):
        """Where do people go after this company?"""
        # Route to Neo4j
        
    def skill_clusters(self, skill: str):
        """What skills commonly appear with this skill?"""
        # Route to Neo4j
        
    # === Hybrid Queries ===
    
    def find_best_matches(self, target_profile: dict):
        """
        Find best candidate matches using both ES and Neo4j.
        1. ES: Filter by skills, location, experience
        2. Neo4j: Rank by career path similarity
        3. Combine scores
        """
        # Use both engines
```

---

## Data Sync Strategy

### Sync Trigger Points

```
┌─────────────────────────────────────────────────────────────┐
│                    PDL API Ingestion                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              PostgreSQL - IngestedData (Raw)                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│          PDLTransformer → PDLPerson (Normalized)             │
└─────────────────────────────────────────────────────────────┘
                              ↓
              ┌───────────────┴────────────────┐
              ↓                                ↓
┌──────────────────────────┐    ┌──────────────────────────┐
│  Async: Sync to ES       │    │  Async: Sync to Neo4j    │
│  via Celery Task         │    │  via Celery Task         │
└──────────────────────────┘    └──────────────────────────┘
```

### Sync Implementation

**After each PDLPerson save:**
1. Trigger Celery task: `sync_person_to_elasticsearch.delay(person_id)`
2. Trigger Celery task: `sync_person_to_neo4j.delay(person_id)`
3. Tasks run asynchronously (non-blocking)
4. Retry on failure (exponential backoff)

**Bulk Sync (Initial Load):**
```bash
# Sync all existing persons
python manage.py sync_all_to_search --batch-size 1000
```

---

## Performance Targets

### Elasticsearch
- **Index latency:** <1 second per person
- **Search latency:** <100ms for simple queries
- **Aggregation latency:** <500ms
- **Index size:** ~5KB per person

### Neo4j
- **Write latency:** <2 seconds per person (with relationships)
- **Simple query:** <100ms
- **Complex graph traversal:** <1 second
- **Graph size:** ~10KB per person (with relationships)

### Combined
- **Total sync time:** <3 seconds per person
- **Bulk sync:** 1000 persons/minute
- **Search response:** <200ms (99th percentile)

---

## Scaling Considerations

### Elasticsearch
- **Sharding:** 2 shards initially, add more at 10M+ docs
- **Replication:** 1 replica for HA
- **Index lifecycle:** Hot/warm/cold architecture
- **Memory:** 4GB heap minimum, 8GB recommended

### Neo4j
- **Clustering:** Single instance initially, cluster at scale
- **Memory:** 4GB heap minimum, 16GB recommended
- **Indexing:** Create indexes on frequently queried properties
- **Caching:** Enable query cache

### Database
- **PostgreSQL:** Primary source of truth, no scaling needed yet
- **Sync queue:** Use dedicated Celery worker queue
- **Rate limiting:** Prevent overwhelming search engines

---

## Monitoring & Observability

### Metrics to Track

**Sync Health:**
- ES sync success/failure rate
- Neo4j sync success/failure rate
- Average sync latency
- Sync queue depth

**Query Performance:**
- ES query latency (p50, p95, p99)
- Neo4j query latency
- Cache hit rate
- Query volume by type

**Data Quality:**
- Index/graph size
- Missing field rate
- Duplicate detection rate

---

## Implementation Phases

### Phase 1: Foundation (This Sprint) ✅
- [x] Architecture design
- [ ] ElasticsearchService implementation
- [ ] Neo4jService implementation  
- [ ] Sync integration in PDLTransformer
- [ ] Basic tests
- [ ] Docker compose updates

### Phase 2: Search API (Next Sprint)
- [ ] PersonSearchService (unified)
- [ ] REST API endpoints
- [ ] Query validation
- [ ] Response caching
- [ ] Comprehensive tests

### Phase 3: Look-Alike Engine (Sprint 3)
- [ ] Similarity scoring algorithm
- [ ] Hybrid ES + Neo4j ranking
- [ ] ML-based matching (optional)
- [ ] A/B testing framework

### Phase 4: Production Ready (Sprint 4)
- [ ] Performance optimization
- [ ] Monitoring dashboards
- [ ] Alert rules
- [ ] Documentation
- [ ] Load testing

---

## Next Steps

1. ✅ Create architecture document (this file)
2. 🚧 Implement ElasticsearchService
3. 🚧 Implement Neo4jService
4. 🚧 Update PDLTransformer with sync triggers
5. 🚧 Add docker-compose services
6. 🚧 Create comprehensive tests

---

**Document Status:** Complete  
**Ready for Implementation:** ✅  
**Approved By:** Engineering Team  

