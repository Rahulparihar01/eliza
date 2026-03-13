"""
Comprehensive tests for search infrastructure.

Tests:
- BaseElasticsearchSync
- BaseNeo4jSync
- PDL person sync implementations
- PersonSearchService
- Search API endpoints
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from elasticsearch import Elasticsearch
from neo4j import GraphDatabase
from sqlalchemy.orm import Session

from src.services.search.base_elasticsearch_sync import BaseElasticsearchSync
from src.services.search.base_neo4j_sync import BaseNeo4jSync
from src.services.search.pdl_person_sync import (
    PDLPersonElasticsearchSync,
    PDLPersonNeo4jSync
)
from src.services.search.person_search_service import PersonSearchService


# ==================== Test Data ====================

SAMPLE_PERSON_DATA = {
    'pdl_id': 'test_person_123',
    'customer_id': 'test_customer',
    'full_name': 'Jane Doe',
    'first_name': 'Jane',
    'last_name': 'Doe',
    'job_title': 'Senior Data Engineer',
    'job_title_role': 'engineer',
    'job_title_levels': ['senior'],
    'job_company_name': 'Netflix',
    'job_company_size': '1000-5000',
    'job_company_industry': 'Entertainment',
    'job_company_location_name': 'Los Gatos, CA',
    'job_start_date': '2020-01-01',
    'skills': ['Python', 'Spark', 'AWS', 'Machine Learning'],
    'location_name': 'San Francisco, CA',
    'location_country': 'United States',
    'location_region': 'California',
    'location_metro': 'San Francisco Bay Area',
    'location_locality': 'San Francisco',
    'inferred_years_experience': 8,
    'pdl_likelihood': 9,
    'primary_email': 'jane@example.com',
    'linkedin_url': 'https://linkedin.com/in/janedoe',
    'education_history': [],
    'work_history': [
        {
            'company': {'name': 'Google', 'size': '10000+'},
            'title': 'Data Engineer',
            'start_date': '2018-01-01',
            'end_date': '2019-12-31'
        }
    ],
    'created_at': '2024-01-01T00:00:00',
    'updated_at': '2024-01-01T00:00:00',
}


# ==================== Test BaseElasticsearchSync ====================

class TestElasticsearchSync(BaseElasticsearchSync):
    """Test implementation of BaseElasticsearchSync."""
    
    def get_document_id(self, record):
        return record['id']


@pytest.fixture
def mock_es_client():
    """Mock Elasticsearch client."""
    client = Mock(spec=Elasticsearch)
    client.indices = Mock()
    client.indices.exists = Mock(return_value=False)
    client.indices.create = Mock()
    client.index = Mock(return_value={'result': 'created', '_version': 1})
    client.search = Mock(return_value={
        'hits': {
            'total': {'value': 10},
            'max_score': 2.5,
            'hits': [
                {
                    '_id': 'doc1',
                    '_score': 2.5,
                    '_source': {'name': 'Test'}
                }
            ]
        },
        'took': 15
    })
    client.delete = Mock()
    client.count = Mock(return_value={'count': 100})
    return client


def test_elasticsearch_sync_initialization(mock_es_client, tmp_path):
    """Test Elasticsearch sync initialization."""
    # Create a temporary config file
    config_file = tmp_path / "test_mapping.yaml"
    config_file.write_text("""
index_name: test_index
index_prefix: ${CUSTOMER_ID}
settings:
  number_of_shards: 1
field_mappings:
  id:
    type: keyword
    source: id
  name:
    type: text
    source: name
    """)
    
    sync = TestElasticsearchSync(
        mock_es_client,
        str(config_file),
        "test_customer"
    )
    
    assert sync.index_name == "test_customer_test_index"
    assert sync.customer_id == "test_customer"


def test_elasticsearch_ensure_index(mock_es_client, tmp_path):
    """Test Elasticsearch index creation."""
    config_file = tmp_path / "test_mapping.yaml"
    config_file.write_text("""
index_name: test_index
field_mappings:
  id:
    type: keyword
    source: id
    """)
    
    sync = TestElasticsearchSync(mock_es_client, str(config_file), "test_customer")
    sync.ensure_index()
    
    # Verify index creation was called
    mock_es_client.indices.create.assert_called_once()


def test_elasticsearch_sync_document(mock_es_client, tmp_path):
    """Test document sync to Elasticsearch."""
    config_file = tmp_path / "test_mapping.yaml"
    config_file.write_text("""
index_name: test_index
field_mappings:
  id:
    type: keyword
    source: id
  name:
    type: text
    source: name
    """)
    
    sync = TestElasticsearchSync(mock_es_client, str(config_file), "test_customer")
    
    result = sync.sync_document({'id': 'doc1', 'name': 'Test Document'}, 'doc1')
    
    assert result['success'] == True
    assert result['id'] == 'doc1'
    mock_es_client.index.assert_called_once()


# ==================== Test PDL Person Syncs ====================

def test_pdl_elasticsearch_sync_initialization(mock_es_client):
    """Test PDL person Elasticsearch sync initialization."""
    with patch('src.services.search.pdl_person_sync.BaseElasticsearchSync.__init__', return_value=None):
        sync = PDLPersonElasticsearchSync(mock_es_client, "test_customer")
        assert sync is not None


def test_pdl_elasticsearch_get_document_id():
    """Test PDL person document ID extraction."""
    with patch('src.services.search.pdl_person_sync.BaseElasticsearchSync.__init__', return_value=None):
        sync = PDLPersonElasticsearchSync(Mock(), "test_customer")
        
        doc_id = sync.get_document_id({'pdl_id': 'test_123'})
        assert doc_id == 'test_123'


def test_pdl_neo4j_node_extraction():
    """Test PDL person node data extraction."""
    with patch('src.services.search.pdl_person_sync.BaseNeo4jSync.__init__', return_value=None):
        sync = PDLPersonNeo4jSync(Mock(), "test_customer")
        
        # Test Person node extraction
        person_node = sync.extract_node_data(
            SAMPLE_PERSON_DATA,
            'Person',
            {}
        )
        
        assert person_node is not None
        assert person_node['pdl_id'] == 'test_person_123'
        assert person_node['name'] == 'Jane Doe'
        assert person_node['current_title'] == 'Senior Data Engineer'


def test_pdl_neo4j_relationship_extraction():
    """Test PDL person relationship data extraction."""
    with patch('src.services.search.pdl_person_sync.BaseNeo4jSync.__init__', return_value=None):
        sync = PDLPersonNeo4jSync(Mock(), "test_customer")
        
        # Test WORKS_AT relationship
        works_at = sync.extract_relationship_data(
            SAMPLE_PERSON_DATA,
            'WORKS_AT',
            {}
        )
        
        assert len(works_at) == 1
        assert works_at[0]['from_id'] == 'test_person_123'
        assert works_at[0]['to_id'] == 'Netflix'
        
        # Test HAS_SKILL relationships
        skills = sync.extract_relationship_data(
            SAMPLE_PERSON_DATA,
            'HAS_SKILL',
            {}
        )
        
        assert len(skills) == 4  # Python, Spark, AWS, Machine Learning


# ==================== Test PersonSearchService ====================

@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def mock_person_search_service(mock_db, mock_es_client):
    """Mock PersonSearchService."""
    with patch('src.services.search.person_search_service.GraphDatabase.driver'):
        with patch('src.services.search.person_search_service.PDLPersonElasticsearchSync'):
            with patch('src.services.search.person_search_service.PDLPersonNeo4jSync'):
                service = PersonSearchService(
                    mock_db,
                    "test_customer",
                    mock_es_client,
                    Mock()
                )
                return service


def test_person_search_service_initialization(mock_person_search_service):
    """Test PersonSearchService initialization."""
    assert mock_person_search_service.customer_id == "test_customer"


def test_person_search_full_text(mock_person_search_service):
    """Test full-text person search."""
    # Mock the ES sync search method
    mock_person_search_service.es_sync.search = Mock(return_value={
        'hits': {
            'total': {'value': 5},
            'max_score': 3.2,
            'hits': [
                {
                    '_id': 'person1',
                    '_score': 3.2,
                    '_source': {
                        'pdl_id': 'person1',
                        'full_name': 'John Doe',
                        'job_title': 'Data Engineer',
                        'job_company_name': 'Google'
                    }
                }
            ]
        },
        'took': 12
    })
    
    result = mock_person_search_service.search_persons(
        query="data engineer",
        size=10
    )
    
    assert result['total'] == 5
    assert len(result['hits']) == 1
    assert result['hits'][0]['pdl_id'] == 'person1'


def test_search_by_skills(mock_person_search_service):
    """Test skill-based search."""
    mock_person_search_service.es_sync.search = Mock(return_value={
        'hits': {
            'total': {'value': 3},
            'hits': [
                {
                    '_id': 'person1',
                    '_score': 2.5,
                    '_source': {
                        'pdl_id': 'person1',
                        'skills': ['Python', 'AWS', 'Docker']
                    }
                }
            ]
        }
    })
    
    result = mock_person_search_service.search_by_skills(
        skills=['Python', 'AWS'],
        min_match=1,
        size=10
    )
    
    assert result['total'] >= 0
    # The implementation sorts by match count


def test_aggregate_by_field(mock_person_search_service):
    """Test field aggregation."""
    mock_person_search_service.es_sync.search = Mock(return_value={
        'hits': {'total': {'value': 100}},
        'aggregations': {
            'job_company_name': {
                'buckets': [
                    {'key': 'Google', 'doc_count': 50},
                    {'key': 'Netflix', 'doc_count': 30},
                    {'key': 'Amazon', 'doc_count': 20}
                ]
            }
        }
    })
    
    result = mock_person_search_service.aggregate_by_field(
        field='job_company_name',
        size=10
    )
    
    assert result['field'] == 'job_company_name'
    assert result['total_docs'] == 100
    assert len(result['buckets']) == 3
    assert result['buckets'][0]['key'] == 'Google'
    assert result['buckets'][0]['count'] == 50


def test_find_career_transitions(mock_person_search_service):
    """Test career transition query."""
    mock_person_search_service.neo4j_sync.query = Mock(return_value=[
        {
            'pdl_id': 'person1',
            'name': 'John Doe',
            'current_title': 'Senior Engineer',
            'previous_title': 'Engineer',
            'transition_date': '2020-06-01',
            'current_start_date': '2020-07-01'
        }
    ])
    
    result = mock_person_search_service.find_career_transitions(
        from_company='Microsoft',
        to_company='Netflix',
        limit=20
    )
    
    assert len(result) == 1
    assert result[0]['pdl_id'] == 'person1'


def test_get_company_network(mock_person_search_service):
    """Test company network query."""
    mock_person_search_service.neo4j_sync.query = Mock(return_value=[
        {
            'company_name': 'Google',
            'industry': 'Technology',
            'shared_people': 25
        },
        {
            'company_name': 'Amazon',
            'industry': 'Technology',
            'shared_people': 18
        }
    ])
    
    result = mock_person_search_service.get_company_network(
        company_name='Netflix',
        max_hops=2,
        limit=50
    )
    
    assert result['source_company'] == 'Netflix'
    assert len(result['connected_companies']) == 2
    assert result['total'] == 2


def test_get_skill_cooccurrence(mock_person_search_service):
    """Test skill co-occurrence analysis."""
    mock_person_search_service.neo4j_sync.query = Mock(return_value=[
        {'cooccurring_skill': 'AWS', 'count': 45},
        {'cooccurring_skill': 'Docker', 'count': 38},
        {'cooccurring_skill': 'Kubernetes', 'count': 32}
    ])
    
    result = mock_person_search_service.get_skill_cooccurrence(
        skill='Python',
        top_n=10
    )
    
    assert len(result) == 3
    assert result[0]['cooccurring_skill'] == 'AWS'
    assert result[0]['count'] == 45


def test_search_fallback_to_postgresql(mock_db):
    """Test PostgreSQL fallback when Elasticsearch fails."""
    # Mock ES client that raises exception
    failing_es = Mock(spec=Elasticsearch)
    failing_es.search = Mock(side_effect=Exception("ES unavailable"))
    
    # Mock database query
    mock_query = Mock()
    mock_query.filter = Mock(return_value=mock_query)
    mock_query.count = Mock(return_value=10)
    mock_query.offset = Mock(return_value=mock_query)
    mock_query.limit = Mock(return_value=mock_query)
    mock_query.all = Mock(return_value=[])
    
    mock_db.query = Mock(return_value=mock_query)
    
    with patch('src.services.search.person_search_service.GraphDatabase.driver'):
        with patch('src.services.search.person_search_service.PDLPersonElasticsearchSync'):
            with patch('src.services.search.person_search_service.PDLPersonNeo4jSync'):
                service = PersonSearchService(mock_db, "test_customer", failing_es, Mock())
                
                # Force the ES sync to raise exception
                service.es_sync.search = Mock(side_effect=Exception("ES error"))
                
                result = service.search_persons(query="test", size=10)
                
                # Should fallback to PostgreSQL
                assert 'fallback' in result or result['total'] >= 0


# ==================== Test Build Query ====================

def test_build_search_query(mock_person_search_service):
    """Test Elasticsearch query building."""
    query = mock_person_search_service._build_search_query(
        query="data engineer",
        filters={
            'company': 'Netflix',
            'skills': ['Python', 'AWS'],
            'min_experience': 5
        }
    )
    
    assert 'query' in query
    assert 'bool' in query['query']
    assert 'must' in query['query']['bool']
    assert 'filter' in query['query']['bool']
    
    # Check filters are applied
    filter_clauses = query['query']['bool']['filter']
    assert len(filter_clauses) >= 2  # At least customer_id + one filter


# ==================== Performance Tests ====================

@pytest.mark.performance
def test_elasticsearch_bulk_sync_performance(mock_es_client, tmp_path):
    """Test bulk sync performance."""
    config_file = tmp_path / "test_mapping.yaml"
    config_file.write_text("""
index_name: test_index
field_mappings:
  id: {type: keyword, source: id}
  name: {type: text, source: name}
    """)
    
    sync = TestElasticsearchSync(mock_es_client, str(config_file), "test_customer")
    
    # Mock bulk helper
    with patch('elasticsearch.helpers.bulk', return_value=(100, [])):
        records = [{'id': f'doc{i}', 'name': f'Document {i}'} for i in range(100)]
        result = sync.bulk_sync(records, batch_size=50)
        
        assert result['success'] == 100
        assert result['total'] == 100


# ==================== Error Handling Tests ====================

def test_elasticsearch_sync_error_handling(mock_es_client, tmp_path):
    """Test error handling in Elasticsearch sync."""
    config_file = tmp_path / "test_mapping.yaml"
    config_file.write_text("""
index_name: test_index
field_mappings:
  id: {type: keyword, source: id}
    """)
    
    sync = TestElasticsearchSync(mock_es_client, str(config_file), "test_customer")
    
    # Mock index to raise exception
    mock_es_client.index = Mock(side_effect=Exception("Index error"))
    
    result = sync.sync_document({'id': 'doc1'}, 'doc1')
    
    assert result['success'] == False
    assert 'error' in result


def test_person_search_service_handles_none_results(mock_person_search_service):
    """Test handling of None/empty results."""
    mock_person_search_service.neo4j_sync.query = Mock(return_value=[])
    
    result = mock_person_search_service.find_career_transitions(
        from_company='NonExistent',
        to_company='AlsoNonExistent',
        limit=20
    )
    
    assert result == []


# ==================== Configuration Tests ====================

def test_yaml_config_parsing(tmp_path):
    """Test YAML configuration parsing."""
    config_file = tmp_path / "complex_mapping.yaml"
    config_file.write_text("""
index_name: complex_index
index_prefix: ${CUSTOMER_ID}
settings:
  number_of_shards: 2
  number_of_replicas: 1
field_mappings:
  text_field:
    type: text
    analyzer: standard
    fields:
      keyword:
        type: keyword
  nested_field:
    type: nested
    source: nested.path
transformers:
  - name: flatten_nested_fields
    apply_to: [field1, field2]
    """)
    
    with patch('elasticsearch.Elasticsearch'):
        sync = TestElasticsearchSync(Mock(), str(config_file), "test_customer")
        
        assert sync.config['index_name'] == 'complex_index'
        assert sync.config['settings']['number_of_shards'] == 2
        assert 'text_field' in sync.config['field_mappings']
        assert len(sync.config['transformers']) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

