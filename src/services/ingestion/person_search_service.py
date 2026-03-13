"""
Unified Person Search Service

Routes queries to the optimal data store:
- PostgreSQL: Direct lookups, ACID transactions, analytical queries
- Elasticsearch: Full-text search, fuzzy matching, faceted filtering
- Neo4j: Relationship queries, career paths, networks

Provides a single API for frontend to search people regardless of backend store.
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from src.core.logging import get_logger, LogCategory, bind_context
from src.core.config import get_settings
from src.models.connector import PDLPerson
from src.services.ingestion.elasticsearch_sync import ElasticsearchSyncService
from src.services.ingestion.neo4j_sync import Neo4jSyncService

logger = get_logger(__name__, LogCategory.BUSINESS)


class PersonSearchService:
    """
    Unified search service for PDL persons.
    
    Routes queries to the optimal data store based on query type:
    - Text search → Elasticsearch
    - Direct ID lookup → PostgreSQL
    - Relationship queries → Neo4j
    - Aggregations → Elasticsearch
    """
    
    def __init__(self, db: Session):
        """
        Initialize search service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.settings = get_settings()
        
        # Initialize search stores if enabled
        self.es_service = None
        if self.settings.elasticsearch_sync_enabled:
            try:
                self.es_service = ElasticsearchSyncService()
            except Exception as e:
                logger.warning(f"Could not initialize Elasticsearch service: {e}")
        
        self.neo4j_service = None
        if self.settings.neo4j_sync_enabled:
            try:
                self.neo4j_service = Neo4jSyncService()
            except Exception as e:
                logger.warning(f"Could not initialize Neo4j service: {e}")
    
    def search_persons(
        self,
        customer_id: str,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20,
        use_elasticsearch: bool = True
    ) -> Dict[str, Any]:
        """
        Search for persons with text query and filters.
        
        Routes to Elasticsearch for full-text search, falls back to PostgreSQL.
        
        Args:
            customer_id: Customer ID
            query: Free-text search query
            filters: Dict of filters (company, location, skills, etc.)
            page: Page number (1-indexed)
            page_size: Results per page
            use_elasticsearch: Whether to use ES (if available)
            
        Returns:
            Dict with results and pagination metadata
        """
        bind_context(
            operation="search_persons",
            customer_id=customer_id,
            has_query=bool(query),
            has_filters=bool(filters)
        )
        
        # Try Elasticsearch first for text search
        if use_elasticsearch and self.es_service and query:
            try:
                results = self.es_service.search_persons(
                    customer_id=customer_id,
                    query=query,
                    filters=filters,
                    page=page,
                    page_size=page_size
                )
                
                # Hydrate with full details from PostgreSQL if needed
                if results["results"]:
                    results["results"] = self._hydrate_results(results["results"], customer_id)
                
                results["source"] = "elasticsearch"
                
                logger.info(
                    "search_complete",
                    source="elasticsearch",
                    customer_id=customer_id,
                    total=results["total"]
                )
                
                return results
                
            except Exception as e:
                logger.warning(
                    "elasticsearch_search_failed_fallback_postgres",
                    error=str(e)
                )
                # Fall through to PostgreSQL
        
        # Fallback to PostgreSQL
        return self._search_postgres(
            customer_id=customer_id,
            query=query,
            filters=filters,
            page=page,
            page_size=page_size
        )
    
    def get_person_by_id(
        self,
        pdl_id: str,
        customer_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single person by PDL ID.
        
        Routes to PostgreSQL for direct lookups.
        
        Args:
            pdl_id: PDL person ID
            customer_id: Customer ID
            
        Returns:
            Person dict or None if not found
        """
        person = self.db.query(PDLPerson).filter(
            PDLPerson.pdl_id == pdl_id,
            PDLPerson.customer_id == customer_id
        ).first()
        
        if person:
            return self._person_to_dict(person)
        return None
    
    def find_career_transitions(
        self,
        customer_id: str,
        from_company: str,
        to_company: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find people who moved from one company to another.
        
        Routes to Neo4j for relationship queries.
        
        Args:
            customer_id: Customer ID
            from_company: Source company
            to_company: Destination company
            limit: Max results
            
        Returns:
            List of person dicts
        """
        if not self.neo4j_service:
            logger.warning("neo4j_not_available_for_career_transitions")
            return []
        
        try:
            return self.neo4j_service.find_career_transitions(
                customer_id=customer_id,
                from_company=from_company,
                to_company=to_company,
                limit=limit
            )
        except Exception as e:
            logger.error("career_transitions_query_failed", error=str(e), exc_info=True)
            return []
    
    def find_people_with_skills(
        self,
        customer_id: str,
        skills: List[str],
        require_all: bool = True,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find people with specific skill combinations.
        
        Routes to Neo4j for skill relationship queries.
        
        Args:
            customer_id: Customer ID
            skills: List of skill names
            require_all: If True, must have ALL skills
            limit: Max results
            
        Returns:
            List of person dicts
        """
        if not self.neo4j_service:
            logger.warning("neo4j_not_available_for_skills_search")
            # Fallback to Elasticsearch
            if self.es_service:
                try:
                    # Build filter for skills
                    filters = {"skills": skills}
                    results = self.es_service.search_persons(
                        customer_id=customer_id,
                        query=None,
                        filters=filters,
                        page=1,
                        page_size=limit
                    )
                    return results.get("results", [])
                except Exception as e:
                    logger.error("elasticsearch_skills_search_failed", error=str(e))
                    return []
            return []
        
        try:
            return self.neo4j_service.find_people_with_skills(
                customer_id=customer_id,
                skills=skills,
                require_all=require_all,
                limit=limit
            )
        except Exception as e:
            logger.error("skills_search_failed", error=str(e), exc_info=True)
            return []
    
    def get_company_network(
        self,
        customer_id: str,
        company_name: str,
        depth: int = 2
    ) -> Dict[str, Any]:
        """
        Get network of companies connected through people.
        
        Routes to Neo4j for graph traversal.
        
        Args:
            customer_id: Customer ID
            company_name: Center company
            depth: Traversal depth
            
        Returns:
            Dict with company network
        """
        if not self.neo4j_service:
            logger.warning("neo4j_not_available_for_company_network")
            return {"center_company": company_name, "connections": []}
        
        try:
            return self.neo4j_service.get_company_network(
                customer_id=customer_id,
                company_name=company_name,
                depth=depth
            )
        except Exception as e:
            logger.error("company_network_query_failed", error=str(e), exc_info=True)
            return {"center_company": company_name, "connections": []}
    
    def get_aggregations(
        self,
        customer_id: str,
        agg_fields: List[str]
    ) -> Dict[str, Any]:
        """
        Get aggregations for analytics.
        
        Routes to Elasticsearch for fast aggregations.
        
        Args:
            customer_id: Customer ID
            agg_fields: Fields to aggregate
            
        Returns:
            Dict with aggregation results
        """
        if not self.es_service:
            logger.warning("elasticsearch_not_available_for_aggregations")
            return {}
        
        try:
            return self.es_service.get_aggregations(
                customer_id=customer_id,
                agg_fields=agg_fields
            )
        except Exception as e:
            logger.error("aggregations_failed", error=str(e), exc_info=True)
            return {}
    
    def _search_postgres(
        self,
        customer_id: str,
        query: Optional[str],
        filters: Optional[Dict[str, Any]],
        page: int,
        page_size: int
    ) -> Dict[str, Any]:
        """
        Search persons using PostgreSQL.
        
        Fallback when Elasticsearch is not available.
        Limited to simple filters (no full-text search).
        """
        query_builder = self.db.query(PDLPerson).filter(
            PDLPerson.customer_id == customer_id
        )
        
        # Apply filters
        if filters:
            if "job_company_name" in filters:
                query_builder = query_builder.filter(
                    PDLPerson.job_company_name.in_(filters["job_company_name"])
                    if isinstance(filters["job_company_name"], list)
                    else PDLPerson.job_company_name == filters["job_company_name"]
                )
            if "location_country" in filters:
                query_builder = query_builder.filter(
                    PDLPerson.location_country.in_(filters["location_country"])
                    if isinstance(filters["location_country"], list)
                    else PDLPerson.location_country == filters["location_country"]
                )
            if "job_title_role" in filters:
                query_builder = query_builder.filter(
                    PDLPerson.job_title_role.in_(filters["job_title_role"])
                    if isinstance(filters["job_title_role"], list)
                    else PDLPerson.job_title_role == filters["job_title_role"]
                )
        
        # Simple text search on name (if query provided)
        if query:
            query_builder = query_builder.filter(
                PDLPerson.full_name.ilike(f"%{query}%")
            )
        
        # Count total
        total = query_builder.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        persons = query_builder.order_by(PDLPerson.updated_at.desc()).offset(offset).limit(page_size).all()
        
        # Convert to dicts
        results = [self._person_to_dict(p) for p in persons]
        
        total_pages = (total + page_size - 1) // page_size
        
        logger.info(
            "search_complete",
            source="postgresql",
            customer_id=customer_id,
            total=total
        )
        
        return {
            "total": total,
            "results": results,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "source": "postgresql"
        }
    
    def _hydrate_results(
        self,
        es_results: List[Dict[str, Any]],
        customer_id: str
    ) -> List[Dict[str, Any]]:
        """
        Hydrate Elasticsearch results with full PostgreSQL data.
        
        ES results may not have all fields, so we fetch from PostgreSQL.
        """
        # Extract PDL IDs
        pdl_ids = [r.get("pdl_id") for r in es_results if r.get("pdl_id")]
        
        if not pdl_ids:
            return es_results
        
        # Fetch from PostgreSQL
        persons = self.db.query(PDLPerson).filter(
            PDLPerson.pdl_id.in_(pdl_ids),
            PDLPerson.customer_id == customer_id
        ).all()
        
        # Create lookup dict
        person_dict = {p.pdl_id: self._person_to_dict(p) for p in persons}
        
        # Merge ES results with PostgreSQL data
        hydrated = []
        for es_result in es_results:
            pdl_id = es_result.get("pdl_id")
            if pdl_id and pdl_id in person_dict:
                hydrated.append(person_dict[pdl_id])
            else:
                # Use ES data if PostgreSQL data not found
                hydrated.append(es_result)
        
        return hydrated
    
    def _person_to_dict(self, person: PDLPerson) -> Dict[str, Any]:
        """Convert PDLPerson model to dict."""
        return {
            "pdl_id": person.pdl_id,
            "customer_id": person.customer_id,
            "full_name": person.full_name,
            "first_name": person.first_name,
            "last_name": person.last_name,
            "job_title": person.job_title,
            "job_title_role": person.job_title_role,
            "job_company_name": person.job_company_name,
            "job_company_size": person.job_company_size,
            "job_company_industry": person.job_company_industry,
            "primary_email": person.primary_email,
            "linkedin_url": person.linkedin_url,
            "location_name": person.location_name,
            "location_locality": person.location_locality,
            "location_region": person.location_region,
            "location_country": person.location_country,
            "skills": person.skills,
            "pdl_likelihood": person.pdl_likelihood,
            "sync_count": person.sync_count,
            "created_at": person.created_at.isoformat() if person.created_at else None,
            "updated_at": person.updated_at.isoformat() if person.updated_at else None
        }
    
    def close(self):
        """Close connections to search stores."""
        if self.neo4j_service:
            try:
                self.neo4j_service.close()
            except Exception as e:
                logger.warning(f"Error closing Neo4j connection: {e}")

