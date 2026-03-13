"""
Generic Elasticsearch sync service.

Provides reusable infrastructure for syncing any dataset to Elasticsearch
through YAML configuration.
"""
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import yaml
import os
from pathlib import Path

from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.BUSINESS)


class BaseElasticsearchSync(ABC):
    """
    Generic Elasticsearch sync service.
    Works with any dataset through configuration.
    
    Usage:
        class MyDataSync(BaseElasticsearchSync):
            def get_document_id(self, record):
                return record['id']
        
        sync = MyDataSync(es_client, 'config/my_data.yaml', 'customer_123')
        sync.ensure_index()
        sync.sync_document(my_data, 'doc_id_123')
    """
    
    def __init__(
        self,
        es_client,
        config_path: str,
        customer_id: str
    ):
        """
        Initialize sync service.
        
        Args:
            es_client: Elasticsearch client instance
            config_path: Path to YAML configuration file
            customer_id: Customer ID for multi-tenancy
        """
        self.es = es_client
        self.customer_id = customer_id
        
        # Load configuration
        config_full_path = self._resolve_config_path(config_path)
        with open(config_full_path) as f:
            self.config = yaml.safe_load(f)
        
        self.index_name = self._get_index_name()
        
        logger.info(
            "elasticsearch_sync_initialized",
            index=self.index_name,
            customer_id=customer_id,
            config=config_path
        )
    
    def _resolve_config_path(self, config_path: str) -> str:
        """Resolve config path relative to project root."""
        if os.path.isabs(config_path):
            return config_path
        
        # Try relative to project root
        project_root = Path(__file__).parent.parent.parent.parent
        full_path = project_root / config_path
        
        if full_path.exists():
            return str(full_path)
        
        # Try as-is
        if os.path.exists(config_path):
            return config_path
        
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
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
        try:
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
                
                logger.info(
                    "elasticsearch_index_created",
                    index=self.index_name,
                    customer_id=self.customer_id
                )
            else:
                logger.debug(
                    "elasticsearch_index_exists",
                    index=self.index_name
                )
        except Exception as e:
            logger.error(
                "elasticsearch_index_creation_failed",
                index=self.index_name,
                error=str(e),
                exc_info=True
            )
            raise
    
    def _build_mappings(self) -> Dict[str, Any]:
        """Build Elasticsearch mappings from config."""
        properties = {}
        
        for field_name, field_config in self.config.get('field_mappings', {}).items():
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
        if 'index' in config:
            mapping['index'] = config['index']
            
        return mapping
    
    def sync_document(
        self, 
        source_data: Dict[str, Any],
        document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sync a single document to Elasticsearch.
        
        Args:
            source_data: Raw data (any structure)
            document_id: Optional explicit document ID (otherwise extracted)
            
        Returns:
            Sync result with success status
        """
        try:
            # Get document ID
            if document_id is None:
                document_id = self.get_document_id(source_data)
            
            # Transform source data to ES document
            es_document = self.transform_to_document(source_data)
            
            # Add customer_id for multi-tenancy
            es_document['customer_id'] = self.customer_id
            
            # Index document
            result = self.es.index(
                index=self.index_name,
                id=document_id,
                body=es_document
            )
            
            logger.info(
                "elasticsearch_document_synced",
                index=self.index_name,
                document_id=document_id,
                result=result.get('result')
            )
            
            return {
                'success': result['result'] in ['created', 'updated'],
                'index': self.index_name,
                'id': document_id,
                'version': result.get('_version'),
                'result': result.get('result')
            }
            
        except Exception as e:
            logger.error(
                "elasticsearch_sync_failed",
                index=self.index_name,
                document_id=document_id,
                error=str(e),
                exc_info=True
            )
            return {
                'success': False,
                'index': self.index_name,
                'id': document_id,
                'error': str(e)
            }
    
    def transform_to_document(self, source_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform source data to ES document using config.
        Can be overridden for custom transformation logic.
        
        Args:
            source_data: Raw source data
            
        Returns:
            Transformed document ready for indexing
        """
        document = {}
        
        # Map fields according to configuration
        for field_name, field_config in self.config.get('field_mappings', {}).items():
            source_field = field_config.get('source', field_name)
            
            if source_field and source_field != 'null':
                # Extract value from source
                value = self._extract_value(source_data, source_field)
                if value is not None:
                    document[field_name] = value
        
        # Apply transformers
        document = self._apply_transformers(document, source_data)
        
        return document
    
    def _extract_value(self, data: Dict, path: str) -> Any:
        """
        Extract nested value using dot notation.
        
        Example: 'job.company.name' -> data['job']['company']['name']
        """
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
                try:
                    document = transformer.transform(
                        document, 
                        source_data, 
                        transformer_config
                    )
                except Exception as e:
                    logger.warning(
                        "transformer_failed",
                        transformer=transformer_name,
                        error=str(e)
                    )
        
        return document
    
    def get_transformer(self, name: str):
        """
        Get transformer by name.
        Override to add custom transformers.
        """
        from src.services.search.transformers import get_transformer
        return get_transformer(name)
    
    def bulk_sync(
        self, 
        records: List[Dict[str, Any]],
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Bulk sync multiple documents.
        
        Args:
            records: List of source records
            batch_size: Number of docs per batch
            
        Returns:
            Summary of sync results
        """
        from elasticsearch.helpers import bulk
        
        actions = []
        errors = []
        
        for record in records:
            try:
                doc_id = self.get_document_id(record)
                es_doc = self.transform_to_document(record)
                es_doc['customer_id'] = self.customer_id
                
                actions.append({
                    '_index': self.index_name,
                    '_id': doc_id,
                    '_source': es_doc
                })
            except Exception as e:
                errors.append({
                    'record': record,
                    'error': str(e)
                })
        
        # Execute bulk operation
        try:
            success, failed = bulk(
                self.es, 
                actions, 
                chunk_size=batch_size,
                raise_on_error=False
            )
            
            logger.info(
                "elasticsearch_bulk_sync_completed",
                index=self.index_name,
                total=len(records),
                success=success,
                failed=len(failed) if failed else 0,
                transform_errors=len(errors)
            )
            
            return {
                'success': success,
                'failed': failed,
                'transform_errors': errors,
                'total': len(records)
            }
            
        except Exception as e:
            logger.error(
                "elasticsearch_bulk_sync_failed",
                index=self.index_name,
                error=str(e),
                exc_info=True
            )
            return {
                'success': 0,
                'failed': len(records),
                'error': str(e),
                'total': len(records)
            }
    
    @abstractmethod
    def get_document_id(self, record: Dict[str, Any]) -> str:
        """
        Extract document ID from record.
        Must implement per dataset.
        
        Args:
            record: Source record
            
        Returns:
            Unique document ID
        """
        pass
    
    def delete_document(self, document_id: str) -> bool:
        """
        Delete document from index.
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            True if successful
        """
        try:
            self.es.delete(index=self.index_name, id=document_id)
            logger.info(
                "elasticsearch_document_deleted",
                index=self.index_name,
                document_id=document_id
            )
            return True
        except Exception as e:
            logger.warning(
                "elasticsearch_delete_failed",
                index=self.index_name,
                document_id=document_id,
                error=str(e)
            )
            return False
    
    def search(
        self, 
        query: Dict[str, Any],
        size: int = 10,
        from_: int = 0
    ) -> Dict[str, Any]:
        """
        Execute search query.
        
        Args:
            query: Elasticsearch query DSL
            size: Number of results
            from_: Offset for pagination
            
        Returns:
            Search results
        """
        try:
            return self.es.search(
                index=self.index_name,
                body=query,
                size=size,
                from_=from_
            )
        except Exception as e:
            logger.error(
                "elasticsearch_search_failed",
                index=self.index_name,
                error=str(e),
                exc_info=True
            )
            raise
    
    def count(self, query: Optional[Dict[str, Any]] = None) -> int:
        """
        Count documents matching query.
        
        Args:
            query: Optional query filter
            
        Returns:
            Number of matching documents
        """
        try:
            body = {'query': query} if query else None
            result = self.es.count(index=self.index_name, body=body)
            return result.get('count', 0)
        except Exception as e:
            logger.error(
                "elasticsearch_count_failed",
                index=self.index_name,
                error=str(e)
            )
            return 0

