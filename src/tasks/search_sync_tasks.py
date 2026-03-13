"""
Celery tasks for syncing data to search engines (Elasticsearch, Neo4j).

These tasks run asynchronously after data is saved to PostgreSQL.
"""
from celery import shared_task
from elasticsearch import Elasticsearch
from neo4j import GraphDatabase

from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory
from src.models import database
from src.models.connector import PDLPerson
from src.services.search.pdl_person_sync import (
    PDLPersonElasticsearchSync,
    PDLPersonNeo4jSync
)

logger = get_logger(__name__, LogCategory.BUSINESS)


def get_elasticsearch_client():
    """Get Elasticsearch client."""
    # Get hosts from settings
    settings = get_settings()
    hosts = settings.elasticsearch_hosts if hasattr(settings, 'elasticsearch_hosts') else ["http://elasticsearch:9200"]
    
    return Elasticsearch(
        hosts=hosts,
        verify_certs=False,
        http_compress=True
    )


def get_neo4j_driver():
    """Get Neo4j driver."""
    settings = get_settings()
    uri = settings.neo4j_uri if hasattr(settings, 'neo4j_uri') else "bolt://neo4j:7687"
    user = settings.neo4j_user if hasattr(settings, 'neo4j_user') else "neo4j"
    password = settings.neo4j_password if hasattr(settings, 'neo4j_password') else "password"
    
    return GraphDatabase.driver(uri, auth=(user, password))


@shared_task(
    name="sync_person_to_elasticsearch",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def sync_person_to_elasticsearch(self, person_id: int, customer_id: str):
    """
    Sync a PDLPerson record to Elasticsearch.
    
    Args:
        person_id: PDLPerson database ID
        customer_id: Customer ID for multi-tenancy
    """
    try:
        # Initialize database session
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        
        try:
            # Fetch person from database
            person = db.query(PDLPerson).filter(PDLPerson.id == person_id).first()
            
            if not person:
                logger.warning(
                    "person_not_found_for_es_sync",
                    person_id=person_id,
                    customer_id=customer_id
                )
                return {'success': False, 'error': 'Person not found'}
            
            # Convert to dict for sync
            person_data = {
                'pdl_id': person.pdl_id,
                'customer_id': person.customer_id,
                'full_name': person.full_name,
                'first_name': person.first_name,
                'last_name': person.last_name,
                'job_title': person.job_title,
                'job_title_role': person.job_title_role,
                'job_title_levels': person.job_title_levels,
                'job_company_name': person.job_company_name,
                'job_company_size': person.job_company_size,
                'job_company_industry': person.job_company_industry,
                'job_company_location_name': person.job_company_location_name,
                'skills': person.skills,
                'location_name': person.location_name,
                'location_country': person.location_country,
                'location_region': person.location_region,
                'location_metro': person.location_metro,
                'location_locality': person.location_locality,
                'inferred_years_experience': person.inferred_years_experience,
                'pdl_likelihood': person.pdl_likelihood,
                'primary_email': person.primary_email,
                'linkedin_url': person.linkedin_url,
                'education_history': person.education_history,
                'work_history': person.work_history,
                'created_at': person.created_at.isoformat() if person.created_at else None,
                'updated_at': person.updated_at.isoformat() if person.updated_at else None,
            }
            
            # Create Elasticsearch sync service
            es_client = get_elasticsearch_client()
            es_sync = PDLPersonElasticsearchSync(es_client, customer_id)
            
            # Ensure index exists
            es_sync.ensure_index()
            
            # Sync document
            result = es_sync.sync_document(person_data, person.pdl_id)
            
            logger.info(
                "person_synced_to_elasticsearch",
                person_id=person_id,
                pdl_id=person.pdl_id,
                customer_id=customer_id,
                result=result.get('result')
            )
            
            return result
            
        finally:
            db.close()
    
    except Exception as exc:
        logger.error(
            "elasticsearch_sync_task_failed",
            person_id=person_id,
            customer_id=customer_id,
            error=str(exc),
            exc_info=True
        )
        
        # Retry the task
        raise self.retry(exc=exc)


@shared_task(
    name="sync_person_to_neo4j",
    bind=True,
    max_retries=3,
    default_retry_delay=60
)
def sync_person_to_neo4j(self, person_id: int, customer_id: str):
    """
    Sync a PDLPerson record to Neo4j graph database.
    
    Args:
        person_id: PDLPerson database ID
        customer_id: Customer ID for multi-tenancy
    """
    try:
        # Initialize database session
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        
        try:
            # Fetch person from database
            person = db.query(PDLPerson).filter(PDLPerson.id == person_id).first()
            
            if not person:
                logger.warning(
                    "person_not_found_for_neo4j_sync",
                    person_id=person_id,
                    customer_id=customer_id
                )
                return {'success': False, 'error': 'Person not found'}
            
            # Convert to dict for sync
            person_data = {
                'pdl_id': person.pdl_id,
                'customer_id': person.customer_id,
                'full_name': person.full_name,
                'job_title': person.job_title,
                'job_company_name': person.job_company_name,
                'job_company_size': person.job_company_size,
                'job_company_industry': person.job_company_industry,
                'job_company_location_name': person.job_company_location_name,
                'job_start_date': person.job_start_date,
                'skills': person.skills,
                'inferred_years_experience': person.inferred_years_experience,
                'linkedin_url': person.linkedin_url,
                'work_history': person.work_history,
            }
            
            # Create Neo4j sync service
            neo4j_driver = get_neo4j_driver()
            neo4j_sync = PDLPersonNeo4jSync(neo4j_driver, customer_id)
            
            # Ensure schema exists
            neo4j_sync.ensure_schema()
            
            # Sync record
            result = neo4j_sync.sync_record(person_data, person.pdl_id)
            
            # Close driver
            neo4j_sync.close()
            
            logger.info(
                "person_synced_to_neo4j",
                person_id=person_id,
                pdl_id=person.pdl_id,
                customer_id=customer_id,
                nodes=result.get('nodes_created'),
                relationships=result.get('relationships_created')
            )
            
            return result
            
        finally:
            db.close()
    
    except Exception as exc:
        logger.error(
            "neo4j_sync_task_failed",
            person_id=person_id,
            customer_id=customer_id,
            error=str(exc),
            exc_info=True
        )
        
        # Retry the task
        raise self.retry(exc=exc)


@shared_task(name="sync_person_to_search_stores")
def sync_person_to_search_stores(person_id: int, customer_id: str):
    """
    Sync a PDLPerson to both Elasticsearch and Neo4j.
    
    Triggers both sync tasks in parallel.
    
    Args:
        person_id: PDLPerson database ID
        customer_id: Customer ID for multi-tenancy
    """
    # Check if sync is enabled
    settings = get_settings()
    es_enabled = getattr(settings, 'elasticsearch_sync_enabled', True)
    neo4j_enabled = getattr(settings, 'neo4j_sync_enabled', True)
    
    results = {}
    
    if es_enabled:
        # Trigger Elasticsearch sync
        sync_person_to_elasticsearch.delay(person_id, customer_id)
        results['elasticsearch'] = 'queued'
    
    if neo4j_enabled:
        # Trigger Neo4j sync
        sync_person_to_neo4j.delay(person_id, customer_id)
        results['neo4j'] = 'queued'
    
    logger.info(
        "person_search_sync_triggered",
        person_id=person_id,
        customer_id=customer_id,
        syncs=results
    )
    
    return results

