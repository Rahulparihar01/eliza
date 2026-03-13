"""
PDL Person-specific search sync implementations.

Minimal code - most logic handled by base classes + YAML config.
"""
from typing import Dict, Any, List, Optional, Union

from src.services.search.base_elasticsearch_sync import BaseElasticsearchSync
from src.services.search.base_neo4j_sync import BaseNeo4jSync
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.BUSINESS)


class PDLPersonElasticsearchSync(BaseElasticsearchSync):
    """
    PDL Person-specific Elasticsearch sync.
    
    Inherits all functionality from BaseElasticsearchSync.
    Only needs to implement document ID extraction.
    """
    
    def __init__(self, es_client, customer_id: str):
        """Initialize with PDL person config."""
        config_path = "config/search/elasticsearch/pdl_person_mapping.yaml"
        super().__init__(es_client, config_path, customer_id)
    
    def get_document_id(self, record: Dict[str, Any]) -> str:
        """Use pdl_id as document ID."""
        return record['pdl_id']


class PDLPersonNeo4jSync(BaseNeo4jSync):
    """
    PDL Person-specific Neo4j sync.
    
    Inherits graph logic from BaseNeo4jSync.
    Implements PDL-specific node and relationship extraction.
    """
    
    def __init__(self, neo4j_driver, customer_id: str):
        """Initialize with PDL person config."""
        config_path = "config/search/neo4j/pdl_person_schema.yaml"
        super().__init__(neo4j_driver, config_path, customer_id)
    
    def extract_node_data(
        self,
        source_data: Dict[str, Any],
        node_type: str,
        node_config: Dict
    ) -> Union[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract node data from PDL person record.
        
        Returns single dict or list of dicts for multiple nodes of same type.
        """
        if node_type == "Person":
            # Create Person node from main record
            return {
                'pdl_id': source_data['pdl_id'],
                'name': source_data.get('full_name'),
                'current_title': source_data.get('job_title'),
                'years_experience': source_data.get('inferred_years_experience'),
                'linkedin_url': source_data.get('linkedin_url')
            }
        
        elif node_type == "Company":
            # Extract companies from current job and work history
            companies = []
            
            # Current company
            if source_data.get('job_company_name'):
                companies.append({
                    'name': source_data['job_company_name'],
                    'size': source_data.get('job_company_size'),
                    'industry': source_data.get('job_company_industry'),
                    'location': source_data.get('job_company_location_name')
                })
            
            # Previous companies from work history
            work_history = source_data.get('work_history', [])
            if isinstance(work_history, list):
                for job in work_history:
                    if isinstance(job, dict) and 'company' in job:
                        company = job['company']
                        if isinstance(company, dict) and 'name' in company:
                            companies.append({
                                'name': company['name'],
                                'size': company.get('size'),
                                'industry': company.get('industry'),
                                'location': company.get('location', {}).get('name') if isinstance(company.get('location'), dict) else None
                            })
            
            return companies if companies else None
        
        elif node_type == "Skill":
            # Extract skills as individual nodes
            skills = source_data.get('skills', [])
            
            if isinstance(skills, list):
                return [
                    {
                        'name': skill,
                        'category': 'technical'  # Could be enhanced with skill categorization
                    }
                    for skill in skills
                    if isinstance(skill, str)
                ]
            
            return None
        
        return None
    
    def extract_relationship_data(
        self,
        source_data: Dict[str, Any],
        rel_type: str,
        rel_config: Dict
    ) -> List[Dict[str, Any]]:
        """
        Extract relationship data from PDL person record.
        
        Returns list of relationships to create.
        """
        relationships = []
        pdl_id = source_data.get('pdl_id')
        
        if not pdl_id:
            return relationships
        
        if rel_type == "WORKS_AT":
            # Current employment
            if source_data.get('job_company_name'):
                relationships.append({
                    'from_id': pdl_id,
                    'to_id': source_data['job_company_name'],
                    'title': source_data.get('job_title'),
                    'start_date': source_data.get('job_start_date'),
                    'is_current': True
                })
        
        elif rel_type == "PREVIOUSLY_AT":
            # Past employment from work history
            work_history = source_data.get('work_history', [])
            
            if isinstance(work_history, list):
                for job in work_history:
                    if isinstance(job, dict) and 'company' in job:
                        company = job['company']
                        if isinstance(company, dict) and 'name' in company:
                            # Calculate duration if dates available
                            duration_months = None
                            if 'start_date' in job and 'end_date' in job:
                                # Simplified duration calculation
                                # In production, use proper date parsing
                                pass
                            
                            relationships.append({
                                'from_id': pdl_id,
                                'to_id': company['name'],
                                'title': job.get('title', {}).get('name') if isinstance(job.get('title'), dict) else job.get('title'),
                                'start_date': job.get('start_date'),
                                'end_date': job.get('end_date'),
                                'duration_months': duration_months
                            })
        
        elif rel_type == "HAS_SKILL":
            # Skills relationships
            skills = source_data.get('skills', [])
            
            if isinstance(skills, list):
                for skill in skills:
                    if isinstance(skill, str):
                        relationships.append({
                            'from_id': pdl_id,
                            'to_id': skill,
                            'proficiency': 'unknown',  # PDL doesn't provide proficiency
                            'years': None  # PDL doesn't provide years per skill
                        })
        
        return relationships


# Convenience function to create both syncs at once
def create_pdl_person_syncs(es_client, neo4j_driver, customer_id: str):
    """
    Create both Elasticsearch and Neo4j sync services for PDL persons.
    
    Args:
        es_client: Elasticsearch client
        neo4j_driver: Neo4j driver
        customer_id: Customer ID
        
    Returns:
        Tuple of (elasticsearch_sync, neo4j_sync)
    """
    es_sync = PDLPersonElasticsearchSync(es_client, customer_id)
    neo4j_sync = PDLPersonNeo4jSync(neo4j_driver, customer_id)
    
    # Ensure schemas exist
    es_sync.ensure_index()
    neo4j_sync.ensure_schema()
    
    logger.info(
        "pdl_person_syncs_created",
        customer_id=customer_id
    )
    
    return es_sync, neo4j_sync

