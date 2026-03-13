# Generic Search Sync Architecture

**Date:** October 9, 2025  
**Purpose:** Reusable, schema-agnostic sync infrastructure for Elasticsearch and Neo4j  
**Design Goal:** Add new datasets without rewriting foundation code

---

## Design Principles

### 1. **Generic Over Specific**
- Base services work with any data model
- No hardcoded schema assumptions
- Configuration-driven, not code-driven

### 2. **Schema Mapping via Configuration**
- Define mappings in YAML/JSON
- Field transformations declarative
- Easy to add new datasets

### 3. **Extensibility Through Inheritance**
- Base classes handle common logic
- Subclasses override only dataset-specific behavior
- Minimal code per new dataset

### 4. **Zero Coupling**
- Sync services don't depend on specific models
- Work with dictionaries/dataclasses
- No SQLAlchemy model dependencies in sync layer

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────┐
│                    Configuration Layer                          │
│          (YAML/JSON - Define once per dataset)                  │
├────────────────────────────────────────────────────────────────┤
│  • elasticsearch_mappings.yaml                                  │
│  • neo4j_schema.yaml                                            │
│  • field_transformers.yaml                                      │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│                     Generic Base Services                       │
│                (Write once, use for all datasets)               │
├────────────────────────────────────────────────────────────────┤
│  • BaseElasticsearchSync                                        │
│  • BaseNeo4jSync                                                │
│  • BaseSyncCoordinator                                          │
└────────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────────┐
│               Dataset-Specific Implementations                  │
│             (Minimal code, mostly configuration)                │
├────────────────────────────────────────────────────────────────┤
│  • PDLPersonSync (inherits from base)                           │
│  • CompanySync (inherits from base)                             │
│  • JobPostingSync (inherits from base)                          │
│  • ... future datasets                                          │
└────────────────────────────────────────────────────────────────┘
```

---

## Configuration-Driven Approach

### Elasticsearch Index Configuration

**File:** `config/search/elasticsearch/pdl_person_mapping.yaml`

```yaml
# Generic structure - works for any dataset
index_name: pdl_persons
index_prefix: ${CUSTOMER_ID}  # Multi-tenant support

settings:
  number_of_shards: 2
  number_of_replicas: 1
  analysis:
    analyzer:
      text_analyzer:
        type: custom
        tokenizer: standard
        filter: [lowercase, asciifolding]

# Field mapping: source_field → elasticsearch_field
field_mappings:
  # Simple 1:1 mappings
  pdl_id:
    type: keyword
    source: pdl_id
    
  full_name:
    type: text
    source: full_name
    analyzer: text_analyzer
    fields:
      keyword: {type: keyword}
      suggest: {type: completion}
      
  # Nested object mapping
  skills:
    type: text
    source: skills  # JSON array in source
    analyzer: skill_analyzer
    fields:
      keyword: {type: keyword}
    
  # Computed fields
  search_vector:
    type: dense_vector
    source: null  # Computed by transformer
    dimensions: 384
    
# Transformation pipeline
transformers:
  - name: flatten_nested_fields
    apply_to: [education_history, work_history]
    
  - name: extract_keywords
    apply_to: [job_title, skills]
    
  - name: generate_embeddings
    apply_to: [full_name, job_title]
    output_field: search_vector

# Query boosting
search_config:
  default_fields: [full_name^3, job_title^2, skills, job_company_name]
  boost:
    exact_match: 5.0
    fuzzy_match: 1.0
```

### Neo4j Graph Configuration

**File:** `config/search/neo4j/pdl_person_schema.yaml`

```yaml
# Generic structure - works for any dataset
graph_name: person_network

# Node definitions
nodes:
  Person:
    primary_key: pdl_id
    properties:
      pdl_id: {type: string, indexed: true}
      name: {type: string, indexed: true}
      current_title: {type: string, indexed: true}
      years_experience: {type: integer}
    labels: [Person, Profile]
    
  Company:
    primary_key: name
    properties:
      name: {type: string, indexed: true}
      size: {type: string}
      industry: {type: string, indexed: true}
    labels: [Company, Organization]
    
  Skill:
    primary_key: name
    properties:
      name: {type: string, indexed: true}
      category: {type: string}
    labels: [Skill, Capability]

# Relationship definitions
relationships:
  WORKS_AT:
    from: Person
    to: Company
    properties:
      title: {type: string}
      start_date: {type: date}
      is_current: {type: boolean}
    source_path: current_job  # Path in source data
    
  PREVIOUSLY_AT:
    from: Person
    to: Company
    properties:
      title: {type: string}
      start_date: {type: date}
      end_date: {type: date}
      duration_months: {type: integer}
    source_path: work_history[]  # Array in source
    
  HAS_SKILL:
    from: Person
    to: Skill
    properties:
      proficiency: {type: string}
      years: {type: integer}
    source_path: skills[]

# Index creation
indexes:
  - type: range
    label: Person
    properties: [pdl_id, name]
    
  - type: fulltext
    label: Person
    properties: [name, current_title]
    name: person_search
    
  - type: range
    label: Company
    properties: [name, industry]

# Constraints
constraints:
  - type: unique
    label: Person
    properties: [pdl_id]
    
  - type: unique
    label: Company
    properties: [name]
```

---

## Generic Base Services

### 1. BaseElasticsearchSync

**File:** `src/services/search/base_elasticsearch_sync.py`

```python
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from elasticsearch import Elasticsearch
import yaml

class BaseElasticsearchSync(ABC):
    """
    Generic Elasticsearch sync service.
    Works with any dataset through configuration.
    """
    
    def __init__(
        self,
        es_client: Elasticsearch,
        config_path: str,
        customer_id: str
    ):
        self.es = es_client
        self.customer_id = customer_id
        
        # Load configuration
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        self.index_name = self._get_index_name()
        
    def _get_index_name(self) -> str:
        """Generate index name with customer prefix."""
        base_name = self.config['index_name']
        prefix = self.config.get('index_prefix', '').replace(
            '${CUSTOMER_ID}', 
            self.customer_id
        )
        return f"{prefix}_{base_name}" if prefix else base_name
    
    def ensure_index(self) -> None:
        """Create index if it doesn't exist."""
        if not self.es.indices.exists(index=self.index_name):
            # Build mappings from config
            mappings = self._build_mappings()
            settings = self.config.get('settings', {})
            
            self.es.indices.create(
                index=self.index_name,
                body={
                    'settings': settings,
                    'mappings': mappings
                }
            )
    
    def _build_mappings(self) -> Dict[str, Any]:
        """Build Elasticsearch mappings from config."""
        properties = {}
        
        for field_name, field_config in self.config['field_mappings'].items():
            properties[field_name] = self._build_field_mapping(field_config)
        
        return {'properties': properties}
    
    def _build_field_mapping(self, config: Dict) -> Dict:
        """Build single field mapping."""
        mapping = {'type': config['type']}
        
        # Add optional properties
        if 'analyzer' in config:
            mapping['analyzer'] = config['analyzer']
        if 'fields' in config:
            mapping['fields'] = config['fields']
        if 'dimensions' in config:  # For vectors
            mapping['dimensions'] = config['dimensions']
            
        return mapping
    
    def sync_document(
        self, 
        source_data: Dict[str, Any],
        document_id: str
    ) -> Dict[str, Any]:
        """
        Sync a single document to Elasticsearch.
        
        Args:
            source_data: Raw data (any structure)
            document_id: Unique identifier
            
        Returns:
            Sync result
        """
        # Transform source data to ES document
        es_document = self.transform_to_document(source_data)
        
        # Index document
        result = self.es.index(
            index=self.index_name,
            id=document_id,
            body=es_document
        )
        
        return {
            'success': result['result'] in ['created', 'updated'],
            'index': self.index_name,
            'id': document_id,
            'version': result.get('_version')
        }
    
    def transform_to_document(self, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform source data to ES document using config.
        Override for custom transformation logic.
        """
        document = {}
        
        for field_name, field_config in self.config['field_mappings'].items():
            source_field = field_config.get('source', field_name)
            
            if source_field:
                # Extract value from source
                value = self._extract_value(source_data, source_field)
                if value is not None:
                    document[field_name] = value
        
        # Apply transformers
        document = self._apply_transformers(document, source_data)
        
        return document
    
    def _extract_value(self, data: Dict, path: str) -> Any:
        """Extract nested value using dot notation."""
        keys = path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
                
        return value
    
    def _apply_transformers(
        self, 
        document: Dict, 
        source_data: Dict
    ) -> Dict:
        """Apply transformation pipeline from config."""
        transformers = self.config.get('transformers', [])
        
        for transformer_config in transformers:
            transformer_name = transformer_config['name']
            transformer = self.get_transformer(transformer_name)
            
            if transformer:
                document = transformer.transform(
                    document, 
                    source_data, 
                    transformer_config
                )
        
        return document
    
    def get_transformer(self, name: str):
        """
        Get transformer by name.
        Override to add custom transformers.
        """
        from src.services.search.transformers import TRANSFORMER_REGISTRY
        return TRANSFORMER_REGISTRY.get(name)
    
    def bulk_sync(
        self, 
        records: List[Dict[str, Any]],
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """Bulk sync multiple documents."""
        from elasticsearch.helpers import bulk
        
        actions = []
        for record in records:
            doc_id = self.get_document_id(record)
            es_doc = self.transform_to_document(record)
            
            actions.append({
                '_index': self.index_name,
                '_id': doc_id,
                '_source': es_doc
            })
        
        success, failed = bulk(self.es, actions, chunk_size=batch_size)
        
        return {
            'success': success,
            'failed': failed,
            'total': len(records)
        }
    
    @abstractmethod
    def get_document_id(self, record: Dict[str, Any]) -> str:
        """Extract document ID from record. Must implement per dataset."""
        pass
    
    def delete_document(self, document_id: str) -> bool:
        """Delete document from index."""
        try:
            self.es.delete(index=self.index_name, id=document_id)
            return True
        except Exception:
            return False
    
    def search(
        self, 
        query: Dict[str, Any],
        size: int = 10,
        from_: int = 0
    ) -> Dict[str, Any]:
        """Execute search query."""
        return self.es.search(
            index=self.index_name,
            body=query,
            size=size,
            from_=from_
        )
```

### 2. BaseNeo4jSync

**File:** `src/services/search/base_neo4j_sync.py`

```python
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from neo4j import GraphDatabase
import yaml

class BaseNeo4jSync(ABC):
    """
    Generic Neo4j sync service.
    Works with any dataset through configuration.
    """
    
    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        config_path: str,
        customer_id: str
    ):
        self.driver = GraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_user, neo4j_password)
        )
        self.customer_id = customer_id
        
        # Load configuration
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
    
    def ensure_schema(self) -> None:
        """Create indexes and constraints from config."""
        with self.driver.session() as session:
            # Create constraints
            for constraint in self.config.get('constraints', []):
                self._create_constraint(session, constraint)
            
            # Create indexes
            for index in self.config.get('indexes', []):
                self._create_index(session, index)
    
    def _create_constraint(self, session, config: Dict) -> None:
        """Create uniqueness constraint."""
        if config['type'] == 'unique':
            label = config['label']
            props = ', '.join([f'n.{p}' for p in config['properties']])
            
            query = f"""
            CREATE CONSTRAINT IF NOT EXISTS 
            FOR (n:{label}) 
            REQUIRE ({props}) IS UNIQUE
            """
            session.run(query)
    
    def _create_index(self, session, config: Dict) -> None:
        """Create index."""
        label = config['label']
        props = ', '.join([f'n.{p}' for p in config['properties']])
        index_type = config['type']
        
        if index_type == 'range':
            query = f"""
            CREATE INDEX IF NOT EXISTS 
            FOR (n:{label}) 
            ON ({props})
            """
        elif index_type == 'fulltext':
            name = config['name']
            props_list = ', '.join([f"'{p}'" for p in config['properties']])
            query = f"""
            CALL db.index.fulltext.createNodeIndex(
                '{name}', 
                ['{label}'], 
                [{props_list}]
            )
            """
        
        try:
            session.run(query)
        except Exception:
            pass  # Index already exists
    
    def sync_record(
        self,
        source_data: Dict[str, Any],
        record_id: str
    ) -> Dict[str, Any]:
        """
        Sync a single record to Neo4j graph.
        
        Creates nodes and relationships based on config.
        """
        with self.driver.session() as session:
            # Create/update nodes
            nodes_created = self._sync_nodes(session, source_data, record_id)
            
            # Create relationships
            rels_created = self._sync_relationships(session, source_data, record_id)
            
            return {
                'success': True,
                'record_id': record_id,
                'nodes_created': nodes_created,
                'relationships_created': rels_created
            }
    
    def _sync_nodes(
        self, 
        session, 
        source_data: Dict[str, Any],
        record_id: str
    ) -> int:
        """Create/update nodes from source data."""
        nodes_created = 0
        
        for node_type, node_config in self.config['nodes'].items():
            # Extract node data from source
            node_data = self.extract_node_data(
                source_data, 
                node_type, 
                node_config
            )
            
            if node_data:
                # Merge node (create or update)
                self._merge_node(session, node_type, node_config, node_data)
                nodes_created += 1
        
        return nodes_created
    
    def _merge_node(
        self, 
        session, 
        node_type: str,
        node_config: Dict,
        node_data: Dict
    ) -> None:
        """Merge (upsert) a node."""
        labels = ':'.join(node_config['labels'])
        primary_key = node_config['primary_key']
        
        # Build MERGE query
        properties_str = ', '.join([
            f"{k}: ${k}" for k in node_data.keys()
        ])
        
        query = f"""
        MERGE (n:{labels} {{{primary_key}: ${primary_key}}})
        SET n += {{{properties_str}}}
        SET n.customer_id = $customer_id
        SET n.updated_at = datetime()
        RETURN n
        """
        
        session.run(query, **node_data, customer_id=self.customer_id)
    
    def _sync_relationships(
        self,
        session,
        source_data: Dict[str, Any],
        record_id: str
    ) -> int:
        """Create relationships from source data."""
        rels_created = 0
        
        for rel_type, rel_config in self.config['relationships'].items():
            # Extract relationship data
            rel_data_list = self.extract_relationship_data(
                source_data,
                rel_type,
                rel_config
            )
            
            for rel_data in rel_data_list:
                self._create_relationship(
                    session, 
                    rel_type, 
                    rel_config, 
                    rel_data
                )
                rels_created += 1
        
        return rels_created
    
    def _create_relationship(
        self,
        session,
        rel_type: str,
        rel_config: Dict,
        rel_data: Dict
    ) -> None:
        """Create a relationship."""
        from_label = rel_config['from']
        to_label = rel_config['to']
        
        # Get node configs
        from_node_config = self.config['nodes'][from_label]
        to_node_config = self.config['nodes'][to_label]
        
        from_key = from_node_config['primary_key']
        to_key = to_node_config['primary_key']
        
        # Build properties
        props_str = ', '.join([
            f"{k}: ${k}" for k, v in rel_data.items()
            if k not in ['from_id', 'to_id']
        ])
        
        query = f"""
        MATCH (from:{from_label} {{{from_key}: $from_id}})
        MATCH (to:{to_label} {{{to_key}: $to_id}})
        MERGE (from)-[r:{rel_type}]->(to)
        SET r += {{{props_str}}}
        RETURN r
        """
        
        session.run(query, **rel_data)
    
    @abstractmethod
    def extract_node_data(
        self,
        source_data: Dict[str, Any],
        node_type: str,
        node_config: Dict
    ) -> Optional[Dict[str, Any]]:
        """Extract node data from source. Must implement per dataset."""
        pass
    
    @abstractmethod
    def extract_relationship_data(
        self,
        source_data: Dict[str, Any],
        rel_type: str,
        rel_config: Dict
    ) -> List[Dict[str, Any]]:
        """Extract relationship data from source. Must implement per dataset."""
        pass
    
    def delete_record(self, record_id: str) -> bool:
        """Delete all nodes/relationships for a record."""
        with self.driver.session() as session:
            # Find and delete all related nodes
            query = """
            MATCH (n {customer_id: $customer_id})
            WHERE n.record_id = $record_id OR n.pdl_id = $record_id
            DETACH DELETE n
            """
            session.run(query, customer_id=self.customer_id, record_id=record_id)
            return True
    
    def close(self):
        """Close driver connection."""
        self.driver.close()
```

### 3. Dataset-Specific Implementation Example

**File:** `src/services/search/pdl_person_sync.py`

```python
from src.services.search.base_elasticsearch_sync import BaseElasticsearchSync
from src.services.search.base_neo4j_sync import BaseNeo4jSync
from typing import Dict, Any, List, Optional

class PDLPersonElasticsearchSync(BaseElasticsearchSync):
    """PDL Person-specific Elasticsearch sync."""
    
    def __init__(self, es_client, customer_id: str):
        config_path = "config/search/elasticsearch/pdl_person_mapping.yaml"
        super().__init__(es_client, config_path, customer_id)
    
    def get_document_id(self, record: Dict[str, Any]) -> str:
        """Use pdl_id as document ID."""
        return record['pdl_id']
    
    # Can override transform_to_document() for custom logic
    # But most logic is handled by base class + config


class PDLPersonNeo4jSync(BaseNeo4jSync):
    """PDL Person-specific Neo4j sync."""
    
    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, customer_id):
        config_path = "config/search/neo4j/pdl_person_schema.yaml"
        super().__init__(neo4j_uri, neo4j_user, neo4j_password, config_path, customer_id)
    
    def extract_node_data(
        self,
        source_data: Dict[str, Any],
        node_type: str,
        node_config: Dict
    ) -> Optional[Dict[str, Any]]:
        """Extract node data for PDL person."""
        if node_type == "Person":
            return {
                'pdl_id': source_data['pdl_id'],
                'name': source_data.get('full_name'),
                'current_title': source_data.get('job_title'),
                'years_experience': source_data.get('inferred_years_experience')
            }
        
        elif node_type == "Company":
            if 'job_company_name' in source_data:
                return {
                    'name': source_data['job_company_name'],
                    'size': source_data.get('job_company_size'),
                    'industry': source_data.get('job_company_industry')
                }
        
        elif node_type == "Skill":
            # Skills are handled in relationships
            return None
        
        return None
    
    def extract_relationship_data(
        self,
        source_data: Dict[str, Any],
        rel_type: str,
        rel_config: Dict
    ) -> List[Dict[str, Any]]:
        """Extract relationship data for PDL person."""
        relationships = []
        
        if rel_type == "WORKS_AT":
            if 'job_company_name' in source_data:
                relationships.append({
                    'from_id': source_data['pdl_id'],
                    'to_id': source_data['job_company_name'],
                    'title': source_data.get('job_title'),
                    'start_date': source_data.get('job_start_date'),
                    'is_current': True
                })
        
        elif rel_type == "HAS_SKILL":
            skills = source_data.get('skills', [])
            if isinstance(skills, list):
                for skill in skills:
                    relationships.append({
                        'from_id': source_data['pdl_id'],
                        'to_id': skill,
                        'proficiency': 'unknown',
                        'years': None
                    })
        
        elif rel_type == "PREVIOUSLY_AT":
            work_history = source_data.get('work_history', [])
            if isinstance(work_history, list):
                for job in work_history:
                    if 'company' in job:
                        relationships.append({
                            'from_id': source_data['pdl_id'],
                            'to_id': job['company']['name'],
                            'title': job.get('title'),
                            'start_date': job.get('start_date'),
                            'end_date': job.get('end_date')
                        })
        
        return relationships
```

---

## Adding a New Dataset (Example: Company Data)

**Step 1:** Create Elasticsearch config

`config/search/elasticsearch/company_mapping.yaml`:
```yaml
index_name: companies
field_mappings:
  company_id: {type: keyword, source: id}
  name: {type: text, fields: {keyword: {type: keyword}}}
  industry: {type: keyword, source: industry}
  size: {type: keyword, source: employee_count}
```

**Step 2:** Create Neo4j config

`config/search/neo4j/company_schema.yaml`:
```yaml
nodes:
  Company:
    primary_key: company_id
    properties:
      company_id: {type: string}
      name: {type: string}
```

**Step 3:** Create sync implementation (minimal code!)

```python
class CompanyElasticsearchSync(BaseElasticsearchSync):
    def __init__(self, es_client, customer_id):
        super().__init__(
            es_client,
            "config/search/elasticsearch/company_mapping.yaml",
            customer_id
        )
    
    def get_document_id(self, record: Dict) -> str:
        return record['company_id']

# Done! Only ~10 lines of code.
```

---

## Benefits of This Architecture

### 1. **Add New Datasets Quickly**
- Write config files (YAML)
- Write 10-20 lines of Python (ID extraction)
- Done!

### 2. **Consistency Across Datasets**
- All datasets use same sync logic
- Same error handling
- Same monitoring
- Same retry strategy

### 3. **Easy to Test**
- Test base classes once
- Mock configuration
- Test-specific implementations minimally

### 4. **Configuration as Documentation**
- YAML files document the schema
- Easy to review
- Version controlled

### 5. **No Code Changes for Schema Updates**
- Modify YAML config
- No Python changes needed
- Restart service

---

## Next Steps

1. ✅ Design generic architecture (this document)
2. 🚧 Implement base sync classes
3. 🚧 Implement PDL-specific sync
4. 🚧 Create transformer registry
5. 🚧 Add comprehensive tests

---

**Design Status:** Complete  
**Ready for Implementation:** ✅  
**Reusable for Future Datasets:** ✅  

