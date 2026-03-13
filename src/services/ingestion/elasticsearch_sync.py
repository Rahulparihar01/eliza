"""
Elasticsearch Sync Service for PDL Persons

Indexes person records in Elasticsearch for:
- Full-text search
- Fuzzy matching
- Faceted filtering
- Real-time search
- Analytics/aggregations

Multi-tenant: One index per customer (pdl_persons_{customer_id})
"""
from typing import Dict, Any, List, Optional
from elasticsearch import Elasticsearch, NotFoundError
from elasticsearch.helpers import bulk
from datetime import datetime

from src.core.logging import get_logger, LogCategory, bind_context
from src.core.config import get_settings
from src.models.connector import PDLPerson

logger = get_logger(__name__, LogCategory.BUSINESS)


class ElasticsearchSyncService:
    """Service for syncing PDL persons to Elasticsearch."""
    
    # Index mapping for PDL persons
    INDEX_MAPPING = {
        "mappings": {
            "properties": {
                # Identity
                "pdl_id": {"type": "keyword"},
                "customer_id": {"type": "keyword"},
                
                # Name (full-text searchable)
                "full_name": {
                    "type": "text",
                    "analyzer": "standard",
                    "fields": {
                        "keyword": {"type": "keyword"},
                        "suggest": {
                            "type": "completion",
                            "analyzer": "simple"
                        }
                    }
                },
                "first_name": {"type": "text"},
                "last_name": {"type": "text"},
                
                # Job information
                "job_title": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword"}}
                },
                "job_title_role": {"type": "keyword"},
                "job_title_sub_role": {"type": "keyword"},
                "job_company_name": {
                    "type": "text",
                    "fields": {
                        "keyword": {"type": "keyword"},
                        "suggest": {"type": "completion"}
                    }
                },
                "job_company_size": {"type": "keyword"},
                "job_company_industry": {"type": "keyword"},
                "job_start_date": {"type": "date"},
                
                # Contact
                "primary_email": {"type": "keyword"},
                "linkedin_url": {"type": "keyword"},
                
                # Location
                "location_name": {"type": "text"},
                "location_locality": {"type": "keyword"},
                "location_region": {"type": "keyword"},
                "location_country": {"type": "keyword"},
                
                # Skills (full-text searchable array)
                "skills": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword"}}
                },
                
                # Metadata
                "pdl_likelihood": {"type": "integer"},
                "pdl_last_updated": {"type": "date"},
                "sync_count": {"type": "integer"},
                
                # Timestamps
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
                "indexed_at": {"type": "date"}
            }
        },
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 1,
            "analysis": {
                "analyzer": {
                    "autocomplete": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "autocomplete_filter"]
                    }
                },
                "filter": {
                    "autocomplete_filter": {
                        "type": "edge_ngram",
                        "min_gram": 2,
                        "max_gram": 20
                    }
                }
            }
        }
    }
    
    def __init__(self, es_client: Optional[Elasticsearch] = None):
        """
        Initialize Elasticsearch sync service.
        
        Args:
            es_client: Optional Elasticsearch client (for testing)
        """
        settings = get_settings()
        
        if es_client:
            self.es = es_client
        else:
            # Connect to Elasticsearch
            es_hosts = settings.elasticsearch_hosts if hasattr(settings, 'elasticsearch_hosts') else ['http://elasticsearch:9200']
            self.es = Elasticsearch(es_hosts)
        
        logger.info("elasticsearch_sync_initialized", hosts=es_hosts if not es_client else "test_client")
    
    def get_index_name(self, customer_id: str) -> str:
        """Get index name for customer."""
        return f"pdl_persons_{customer_id.lower().replace('-', '_')}"
    
    def ensure_index_exists(self, customer_id: str) -> bool:
        """
        Ensure index exists for customer, create if not.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            True if index exists or was created
        """
        index_name = self.get_index_name(customer_id)
        
        try:
            if not self.es.indices.exists(index=index_name):
                logger.info("creating_elasticsearch_index", index=index_name, customer_id=customer_id)
                
                self.es.indices.create(
                    index=index_name,
                    body=self.INDEX_MAPPING
                )
                
                logger.info("elasticsearch_index_created", index=index_name)
                return True
            else:
                return True
                
        except Exception as e:
            logger.error("elasticsearch_index_creation_failed", index=index_name, error=str(e), exc_info=True)
            return False
    
    def index_person(self, person: PDLPerson) -> bool:
        """
        Index a single person record in Elasticsearch.
        
        Args:
            person: PDLPerson model instance
            
        Returns:
            True if successful, False otherwise
        """
        try:
            bind_context(
                operation="index_person",
                pdl_id=person.pdl_id,
                customer_id=person.customer_id
            )
            
            # Ensure index exists
            if not self.ensure_index_exists(person.customer_id):
                return False
            
            index_name = self.get_index_name(person.customer_id)
            
            # Prepare document
            doc = self._person_to_document(person)
            
            # Index document
            self.es.index(
                index=index_name,
                id=person.pdl_id,
                document=doc
            )
            
            logger.info(
                "person_indexed",
                pdl_id=person.pdl_id,
                index=index_name,
                customer_id=person.customer_id
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "person_indexing_failed",
                pdl_id=person.pdl_id if person else None,
                error=str(e),
                exc_info=True
            )
            return False
    
    def bulk_index_persons(self, persons: List[PDLPerson]) -> Dict[str, int]:
        """
        Bulk index multiple persons.
        
        Args:
            persons: List of PDLPerson instances
            
        Returns:
            Dict with success/error counts
        """
        if not persons:
            return {"success": 0, "errors": 0}
        
        try:
            # Group by customer
            by_customer = {}
            for person in persons:
                if person.customer_id not in by_customer:
                    by_customer[person.customer_id] = []
                by_customer[person.customer_id].append(person)
            
            # Ensure indexes exist
            for customer_id in by_customer.keys():
                self.ensure_index_exists(customer_id)
            
            # Prepare bulk actions
            actions = []
            for person in persons:
                actions.append({
                    "_index": self.get_index_name(person.customer_id),
                    "_id": person.pdl_id,
                    "_source": self._person_to_document(person)
                })
            
            # Execute bulk
            success, errors = bulk(self.es, actions, raise_on_error=False)
            
            logger.info(
                "bulk_index_complete",
                total=len(persons),
                success=success,
                errors=len(errors) if errors else 0
            )
            
            return {
                "success": success,
                "errors": len(errors) if errors else 0
            }
            
        except Exception as e:
            logger.error("bulk_index_failed", error=str(e), exc_info=True)
            return {"success": 0, "errors": len(persons)}
    
    def delete_person(self, pdl_id: str, customer_id: str) -> bool:
        """
        Delete a person from the index.
        
        Args:
            pdl_id: PDL person ID
            customer_id: Customer ID
            
        Returns:
            True if successful
        """
        try:
            index_name = self.get_index_name(customer_id)
            
            self.es.delete(
                index=index_name,
                id=pdl_id,
                ignore=[404]  # Ignore if not found
            )
            
            logger.info("person_deleted_from_index", pdl_id=pdl_id, index=index_name)
            return True
            
        except Exception as e:
            logger.error("person_deletion_failed", pdl_id=pdl_id, error=str(e))
            return False
    
    def search_persons(
        self,
        customer_id: str,
        query: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Search persons with full-text and filters.
        
        Args:
            customer_id: Customer ID
            query: Free-text search query
            filters: Dict of filters (company, location, skills, etc.)
            page: Page number (1-indexed)
            page_size: Results per page
            
        Returns:
            Dict with results and metadata
        """
        try:
            index_name = self.get_index_name(customer_id)
            
            # Check if index exists
            if not self.es.indices.exists(index=index_name):
                return {
                    "total": 0,
                    "results": [],
                    "page": page,
                    "page_size": page_size,
                    "total_pages": 0
                }
            
            # Build query
            es_query = self._build_search_query(query, filters)
            
            # Calculate pagination
            from_offset = (page - 1) * page_size
            
            # Execute search
            response = self.es.search(
                index=index_name,
                body={
                    "query": es_query,
                    "from": from_offset,
                    "size": page_size,
                    "sort": [
                        {"_score": "desc"},
                        {"updated_at": "desc"}
                    ]
                }
            )
            
            # Extract results
            hits = response["hits"]["hits"]
            total = response["hits"]["total"]["value"]
            
            results = [hit["_source"] for hit in hits]
            total_pages = (total + page_size - 1) // page_size
            
            logger.info(
                "search_complete",
                customer_id=customer_id,
                query=query,
                total=total,
                returned=len(results)
            )
            
            return {
                "total": total,
                "results": results,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
            
        except Exception as e:
            logger.error("search_failed", customer_id=customer_id, error=str(e), exc_info=True)
            return {
                "total": 0,
                "results": [],
                "page": page,
                "page_size": page_size,
                "total_pages": 0,
                "error": str(e)
            }
    
    def get_aggregations(
        self,
        customer_id: str,
        agg_fields: List[str]
    ) -> Dict[str, Any]:
        """
        Get aggregations for analytics.
        
        Args:
            customer_id: Customer ID
            agg_fields: Fields to aggregate (company, location, skills, etc.)
            
        Returns:
            Dict with aggregation results
        """
        try:
            index_name = self.get_index_name(customer_id)
            
            # Build aggregations
            aggs = {}
            for field in agg_fields:
                aggs[f"{field}_counts"] = {
                    "terms": {
                        "field": f"{field}.keyword" if field not in ["pdl_likelihood", "sync_count"] else field,
                        "size": 50
                    }
                }
            
            # Execute
            response = self.es.search(
                index=index_name,
                body={
                    "size": 0,  # No documents, just aggregations
                    "aggs": aggs
                }
            )
            
            # Extract aggregations
            result = {}
            for field in agg_fields:
                agg_key = f"{field}_counts"
                if agg_key in response["aggregations"]:
                    buckets = response["aggregations"][agg_key]["buckets"]
                    result[field] = [
                        {"value": b["key"], "count": b["doc_count"]}
                        for b in buckets
                    ]
            
            return result
            
        except Exception as e:
            logger.error("aggregation_failed", error=str(e), exc_info=True)
            return {}
    
    def _person_to_document(self, person: PDLPerson) -> Dict[str, Any]:
        """Convert PDLPerson model to Elasticsearch document."""
        # Extract skill names from JSON
        skills = []
        if person.skills:
            if isinstance(person.skills, list):
                skills = [
                    skill.get("name") if isinstance(skill, dict) else str(skill)
                    for skill in person.skills
                ]
        
        return {
            # Identity
            "pdl_id": person.pdl_id,
            "customer_id": person.customer_id,
            
            # Name
            "full_name": person.full_name,
            "first_name": person.first_name,
            "last_name": person.last_name,
            
            # Job
            "job_title": person.job_title,
            "job_title_role": person.job_title_role,
            "job_title_sub_role": person.job_title_sub_role,
            "job_company_name": person.job_company_name,
            "job_company_size": person.job_company_size,
            "job_company_industry": person.job_company_industry,
            "job_start_date": person.job_start_date.isoformat() if person.job_start_date else None,
            
            # Contact
            "primary_email": person.primary_email,
            "linkedin_url": person.linkedin_url,
            
            # Location
            "location_name": person.location_name,
            "location_locality": person.location_locality,
            "location_region": person.location_region,
            "location_country": person.location_country,
            
            # Skills
            "skills": skills,
            
            # Metadata
            "pdl_likelihood": person.pdl_likelihood,
            "pdl_last_updated": person.pdl_last_updated.isoformat() if person.pdl_last_updated else None,
            "sync_count": person.sync_count,
            
            # Timestamps
            "created_at": person.created_at.isoformat() if person.created_at else None,
            "updated_at": person.updated_at.isoformat() if person.updated_at else None,
            "indexed_at": datetime.utcnow().isoformat()
        }
    
    def _build_search_query(
        self,
        query: Optional[str],
        filters: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build Elasticsearch query from search parameters.
        
        Args:
            query: Free-text query
            filters: Field filters
            
        Returns:
            Elasticsearch query DSL
        """
        must_clauses = []
        filter_clauses = []
        
        # Full-text search across multiple fields
        if query:
            must_clauses.append({
                "multi_match": {
                    "query": query,
                    "fields": [
                        "full_name^3",  # Boost name matches
                        "job_title^2",
                        "job_company_name^2",
                        "skills",
                        "location_name"
                    ],
                    "fuzziness": "AUTO",  # Typo tolerance
                    "type": "best_fields"
                }
            })
        
        # Apply filters
        if filters:
            for field, value in filters.items():
                if value:
                    if isinstance(value, list):
                        # Multi-value filter (OR)
                        filter_clauses.append({
                            "terms": {f"{field}.keyword": value}
                        })
                    else:
                        # Single value filter
                        filter_clauses.append({
                            "term": {f"{field}.keyword": value}
                        })
        
        # Build bool query
        if must_clauses or filter_clauses:
            return {
                "bool": {
                    "must": must_clauses if must_clauses else [{"match_all": {}}],
                    "filter": filter_clauses
                }
            }
        else:
            return {"match_all": {}}

