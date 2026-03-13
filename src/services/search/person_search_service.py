"""
Unified Person Search Service.

Provides a single interface for searching person data across:
- Elasticsearch (full-text search, aggregations)
- Neo4j (graph queries, relationships)
- PostgreSQL (fallback, direct queries)

Routes queries intelligently based on query type and data needs.
"""
from typing import Dict, Any, List, Optional
from elasticsearch import Elasticsearch
from neo4j import GraphDatabase
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory
from src.services.search.pdl_person_sync import PDLPersonElasticsearchSync, PDLPersonNeo4jSync

logger = get_logger(__name__, LogCategory.BUSINESS)


class PersonSearchService:
    """
    Unified search service for person data.
    
    Routes queries to the best search engine for the task:
    - ES: Full-text search, fuzzy matching, faceted search
    - Neo4j: Career paths, company networks, skill relationships
    - PostgreSQL: Direct queries, complex filters
    """
    
    def __init__(
        self,
        db: Session,
        customer_id: str,
        es_client: Optional[Elasticsearch] = None,
        neo4j_driver: Optional[Any] = None
    ):
        """
        Initialize search service.
        
        Args:
            db: SQLAlchemy database session
            customer_id: Customer ID for multi-tenancy
            es_client: Optional Elasticsearch client (auto-created if None)
            neo4j_driver: Optional Neo4j driver (auto-created if None)
        """
        self.db = db
        self.customer_id = customer_id
        settings = get_settings()
        
        # Initialize Elasticsearch
        if es_client is None:
            self.es_client = Elasticsearch(
                hosts=settings.elasticsearch_hosts,
                verify_certs=False,
                http_compress=True
            )
        else:
            self.es_client = es_client
        
        # Initialize Neo4j
        if neo4j_driver is None:
            self.neo4j_driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password)
            )
        else:
            self.neo4j_driver = neo4j_driver
        
        # Initialize sync services (for index access)
        self.es_sync = PDLPersonElasticsearchSync(self.es_client, customer_id)
        self.neo4j_sync = PDLPersonNeo4jSync(self.neo4j_driver, customer_id)
        
        logger.info(
            "person_search_service_initialized",
            customer_id=customer_id
        )
    
    # ==================== Full-Text Search (Elasticsearch) ====================
    
    def search_persons(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        size: int = 10,
        from_: int = 0
    ) -> Dict[str, Any]:
        """
        Full-text search for persons.
        
        Args:
            query: Search query text
            filters: Optional filters (company, title, location, etc.)
            size: Number of results to return
            from_: Offset for pagination
            
        Returns:
            Search results with hits and metadata
        """
        try:
            # Build Elasticsearch query
            es_query = self._build_search_query(query, filters)
            
            # Execute search
            result = self.es_sync.search(es_query, size=size, from_=from_)
            
            # Transform results
            hits = []
            for hit in result.get('hits', {}).get('hits', []):
                hits.append({
                    'pdl_id': hit['_id'],
                    'score': hit['_score'],
                    **hit['_source']
                })
            
            logger.info(
                "person_search_completed",
                customer_id=self.customer_id,
                query=query,
                total=result.get('hits', {}).get('total', {}).get('value', 0),
                returned=len(hits)
            )
            
            return {
                'total': result.get('hits', {}).get('total', {}).get('value', 0),
                'hits': hits,
                'took': result.get('took'),
                'max_score': result.get('hits', {}).get('max_score')
            }
            
        except Exception as e:
            logger.error(
                "person_search_failed",
                customer_id=self.customer_id,
                query=query,
                error=str(e),
                exc_info=True
            )
            # Fallback to PostgreSQL
            return self._fallback_search(query, filters, size, from_)
    
    def _build_search_query(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build Elasticsearch query DSL."""
        # Multi-field search with boosting
        must = [
            {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "full_name^3",
                        "job_title^2",
                        "skills^2",
                        "job_company_name",
                        "location_name"
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            }
        ]
        
        # Add filters
        filter_clauses = [
            {"term": {"customer_id": self.customer_id}}
        ]
        
        if filters:
            if 'company' in filters:
                filter_clauses.append({
                    "term": {"job_company_name.keyword": filters['company']}
                })
            if 'title' in filters:
                filter_clauses.append({
                    "match": {"job_title": filters['title']}
                })
            if 'skills' in filters:
                for skill in filters['skills']:
                    filter_clauses.append({
                        "match": {"skills": skill}
                    })
            if 'location' in filters:
                filter_clauses.append({
                    "match": {"location_name": filters['location']}
                })
            if 'min_experience' in filters:
                filter_clauses.append({
                    "range": {
                        "inferred_years_experience": {
                            "gte": filters['min_experience']
                        }
                    }
                })
        
        return {
            "query": {
                "bool": {
                    "must": must,
                    "filter": filter_clauses
                }
            }
        }
    
    def search_by_skills(
        self,
        skills: List[str],
        min_match: int = 1,
        size: int = 10
    ) -> Dict[str, Any]:
        """
        Find persons with specific skill combinations.
        
        Args:
            skills: List of required skills
            min_match: Minimum number of skills that must match
            size: Number of results
            
        Returns:
            Matching persons
        """
        try:
            es_query = {
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"customer_id": self.customer_id}}
                        ],
                        "should": [
                            {"match": {"skills": skill}}
                            for skill in skills
                        ],
                        "minimum_should_match": min_match
                    }
                }
            }
            
            result = self.es_sync.search(es_query, size=size)
            
            hits = []
            for hit in result.get('hits', {}).get('hits', []):
                person = hit['_source']
                # Calculate skill match score
                matched_skills = [s for s in skills if s.lower() in str(person.get('skills', '')).lower()]
                hits.append({
                    'pdl_id': hit['_id'],
                    'score': hit['_score'],
                    'matched_skills': matched_skills,
                    'match_count': len(matched_skills),
                    **person
                })
            
            # Sort by match count
            hits.sort(key=lambda x: x['match_count'], reverse=True)
            
            return {
                'total': len(hits),
                'hits': hits
            }
            
        except Exception as e:
            logger.error(
                "skill_search_failed",
                skills=skills,
                error=str(e),
                exc_info=True
            )
            return {'total': 0, 'hits': []}
    
    def aggregate_by_field(
        self,
        field: str,
        size: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get aggregation counts for a field.
        
        Args:
            field: Field to aggregate (e.g., 'job_company_name', 'skills')
            size: Number of top values to return
            filters: Optional filters to apply
            
        Returns:
            Aggregation results
        """
        try:
            # Build query with filters
            query = {
                "bool": {
                    "filter": [
                        {"term": {"customer_id": self.customer_id}}
                    ]
                }
            }
            
            if filters:
                if 'title' in filters:
                    query['bool']['filter'].append({
                        "match": {"job_title": filters['title']}
                    })
            
            # Determine field type for aggregation
            agg_field = f"{field}.keyword" if field not in ['inferred_years_experience'] else field
            
            es_query = {
                "size": 0,  # We only want aggregations
                "query": query,
                "aggs": {
                    field: {
                        "terms": {
                            "field": agg_field,
                            "size": size
                        }
                    }
                }
            }
            
            result = self.es_sync.search(es_query)
            
            buckets = result.get('aggregations', {}).get(field, {}).get('buckets', [])
            
            return {
                'field': field,
                'total_docs': result.get('hits', {}).get('total', {}).get('value', 0),
                'buckets': [
                    {
                        'key': bucket['key'],
                        'count': bucket['doc_count']
                    }
                    for bucket in buckets
                ]
            }
            
        except Exception as e:
            logger.error(
                "aggregation_failed",
                field=field,
                error=str(e),
                exc_info=True
            )
            return {'field': field, 'total_docs': 0, 'buckets': []}
    
    # ==================== Graph Queries (Neo4j) ====================
    
    def find_career_transitions(
        self,
        from_company: str,
        to_company: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Find people who moved from one company to another.
        
        Args:
            from_company: Starting company
            to_company: Destination company
            limit: Maximum number of results
            
        Returns:
            List of persons and their transition details
        """
        try:
            cypher = """
            MATCH (p:Person)-[r1:PREVIOUSLY_AT]->(c1:Company {name: $from_company})
            MATCH (p)-[r2:WORKS_AT]->(c2:Company {name: $to_company})
            WHERE p.customer_id = $customer_id
            RETURN p.pdl_id as pdl_id,
                   p.name as name,
                   p.current_title as current_title,
                   r1.title as previous_title,
                   r1.end_date as transition_date,
                   r2.start_date as current_start_date
            LIMIT $limit
            """
            
            results = self.neo4j_sync.query(cypher, {
                'from_company': from_company,
                'to_company': to_company,
                'customer_id': self.customer_id,
                'limit': limit
            })
            
            logger.info(
                "career_transitions_found",
                from_company=from_company,
                to_company=to_company,
                count=len(results)
            )
            
            return results
            
        except Exception as e:
            logger.error(
                "career_transition_query_failed",
                from_company=from_company,
                to_company=to_company,
                error=str(e),
                exc_info=True
            )
            return []
    
    def get_company_network(
        self,
        company_name: str,
        max_hops: int = 2,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get network of companies connected through people.
        
        Args:
            company_name: Starting company
            max_hops: Maximum relationship depth
            limit: Maximum companies to return
            
        Returns:
            Network of connected companies
        """
        try:
            cypher = """
            MATCH (start:Company {name: $company_name})<-[:WORKS_AT|PREVIOUSLY_AT]-(p:Person)-[:WORKS_AT|PREVIOUSLY_AT]->(other:Company)
            WHERE p.customer_id = $customer_id
              AND other.name <> $company_name
            WITH other, count(DISTINCT p) as shared_people
            ORDER BY shared_people DESC
            LIMIT $limit
            RETURN other.name as company_name,
                   other.industry as industry,
                   shared_people
            """
            
            results = self.neo4j_sync.query(cypher, {
                'company_name': company_name,
                'customer_id': self.customer_id,
                'limit': limit
            })
            
            return {
                'source_company': company_name,
                'connected_companies': results,
                'total': len(results)
            }
            
        except Exception as e:
            logger.error(
                "company_network_query_failed",
                company=company_name,
                error=str(e),
                exc_info=True
            )
            return {
                'source_company': company_name,
                'connected_companies': [],
                'total': 0
            }
    
    def get_skill_cooccurrence(
        self,
        skill: str,
        top_n: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find skills that commonly occur with a given skill.
        
        Args:
            skill: Skill to analyze
            top_n: Number of top co-occurring skills
            
        Returns:
            List of skills and co-occurrence counts
        """
        try:
            cypher = """
            MATCH (p:Person)-[:HAS_SKILL]->(s1:Skill {name: $skill})
            MATCH (p)-[:HAS_SKILL]->(s2:Skill)
            WHERE p.customer_id = $customer_id
              AND s2.name <> $skill
            WITH s2.name as cooccurring_skill, count(DISTINCT p) as count
            ORDER BY count DESC
            LIMIT $top_n
            RETURN cooccurring_skill, count
            """
            
            results = self.neo4j_sync.query(cypher, {
                'skill': skill,
                'customer_id': self.customer_id,
                'top_n': top_n
            })
            
            return results
            
        except Exception as e:
            logger.error(
                "skill_cooccurrence_query_failed",
                skill=skill,
                error=str(e),
                exc_info=True
            )
            return []
    
    # ==================== Fallback (PostgreSQL) ====================
    
    def _fallback_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        size: int,
        from_: int
    ) -> Dict[str, Any]:
        """Fallback to PostgreSQL search when Elasticsearch is unavailable."""
        from src.models.connector import PDLPerson
        
        try:
            # Build PostgreSQL query
            db_query = self.db.query(PDLPerson).filter(
                PDLPerson.customer_id == self.customer_id
            )
            
            # Add text search
            if query:
                db_query = db_query.filter(
                    PDLPerson.full_name.ilike(f"%{query}%") |
                    PDLPerson.job_title.ilike(f"%{query}%") |
                    PDLPerson.job_company_name.ilike(f"%{query}%")
                )
            
            # Add filters
            if filters:
                if 'company' in filters:
                    db_query = db_query.filter(PDLPerson.job_company_name == filters['company'])
                if 'title' in filters:
                    db_query = db_query.filter(PDLPerson.job_title.ilike(f"%{filters['title']}%"))
            
            # Get total count
            total = db_query.count()
            
            # Apply pagination
            persons = db_query.offset(from_).limit(size).all()
            
            # Transform to search result format
            hits = [
                {
                    'pdl_id': p.pdl_id,
                    'full_name': p.full_name,
                    'job_title': p.job_title,
                    'job_company_name': p.job_company_name,
                    'skills': p.skills,
                    'location_name': p.location_name,
                    'score': 1.0  # No scoring in PostgreSQL
                }
                for p in persons
            ]
            
            logger.warning(
                "using_postgresql_fallback_search",
                customer_id=self.customer_id,
                query=query,
                total=total
            )
            
            return {
                'total': total,
                'hits': hits,
                'took': 0,
                'fallback': True
            }
            
        except Exception as e:
            logger.error(
                "fallback_search_failed",
                customer_id=self.customer_id,
                error=str(e),
                exc_info=True
            )
            return {
                'total': 0,
                'hits': [],
                'error': str(e)
            }
    
    def close(self):
        """Close connections."""
        if hasattr(self, 'neo4j_sync'):
            self.neo4j_sync.close()

