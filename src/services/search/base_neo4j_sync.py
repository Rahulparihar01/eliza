"""
Generic Neo4j sync service.

Provides reusable infrastructure for syncing any dataset to Neo4j graph database
through YAML configuration.
"""
from typing import Dict, Any, List, Optional, Union
from abc import ABC, abstractmethod
import yaml
import os
from pathlib import Path

from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.BUSINESS)


class BaseNeo4jSync(ABC):
    """
    Generic Neo4j sync service.
    Works with any dataset through configuration.
    
    Usage:
        class MyDataSync(BaseNeo4jSync):
            def extract_node_data(self, source_data, node_type, node_config):
                # Extract node data from source
                return {...}
            
            def extract_relationship_data(self, source_data, rel_type, rel_config):
                # Extract relationships from source
                return [...]
        
        sync = MyDataSync(driver, 'config/my_data.yaml', 'customer_123')
        sync.ensure_schema()
        sync.sync_record(my_data, 'record_id_123')
    """
    
    def __init__(
        self,
        neo4j_driver,
        config_path: str,
        customer_id: str
    ):
        """
        Initialize sync service.
        
        Args:
            neo4j_driver: Neo4j driver instance
            config_path: Path to YAML configuration file
            customer_id: Customer ID for multi-tenancy
        """
        self.driver = neo4j_driver
        self.customer_id = customer_id
        
        # Load configuration
        config_full_path = self._resolve_config_path(config_path)
        with open(config_full_path) as f:
            self.config = yaml.safe_load(f)
        
        logger.info(
            "neo4j_sync_initialized",
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
    
    def ensure_schema(self) -> None:
        """Create indexes and constraints from config."""
        with self.driver.session() as session:
            try:
                # Create constraints
                for constraint in self.config.get('constraints', []):
                    self._create_constraint(session, constraint)
                
                # Create indexes
                for index in self.config.get('indexes', []):
                    self._create_index(session, index)
                
                logger.info(
                    "neo4j_schema_ensured",
                    customer_id=self.customer_id,
                    constraints=len(self.config.get('constraints', [])),
                    indexes=len(self.config.get('indexes', []))
                )
                
            except Exception as e:
                logger.error(
                    "neo4j_schema_creation_failed",
                    error=str(e),
                    exc_info=True
                )
                raise
    
    def _create_constraint(self, session, config: Dict) -> None:
        """Create uniqueness constraint."""
        try:
            if config['type'] == 'unique':
                label = config['label']
                props = config['properties']
                
                # Neo4j constraint syntax
                constraint_name = f"constraint_{label}_{'_'.join(props)}".lower()
                prop_str = ', '.join([f'n.{p}' for p in props])
                
                query = f"""
                CREATE CONSTRAINT {constraint_name} IF NOT EXISTS
                FOR (n:{label})
                REQUIRE ({prop_str}) IS UNIQUE
                """
                session.run(query)
                
                logger.debug(
                    "neo4j_constraint_created",
                    constraint=constraint_name,
                    label=label
                )
                
        except Exception as e:
            # Constraint may already exist
            logger.debug(
                "neo4j_constraint_exists_or_failed",
                constraint=config.get('label'),
                error=str(e)
            )
    
    def _create_index(self, session, config: Dict) -> None:
        """Create index."""
        try:
            label = config['label']
            props = config['properties']
            index_type = config['type']
            
            if index_type == 'range':
                # Range index for lookups
                for prop in props:
                    index_name = f"index_{label}_{prop}".lower()
                    query = f"""
                    CREATE INDEX {index_name} IF NOT EXISTS
                    FOR (n:{label})
                    ON (n.{prop})
                    """
                    session.run(query)
                    
            elif index_type == 'fulltext':
                # Full-text index for search
                name = config['name']
                props_list = ', '.join([f"'{p}'" for p in props])
                
                # Check if index exists
                check_query = f"SHOW INDEXES YIELD name WHERE name = '{name}' RETURN count(*) as cnt"
                result = session.run(check_query)
                count = result.single()['cnt']
                
                if count == 0:
                    query = f"""
                    CREATE FULLTEXT INDEX {name} IF NOT EXISTS
                    FOR (n:{label})
                    ON EACH [{props_list}]
                    """
                    session.run(query)
            
            logger.debug(
                "neo4j_index_created",
                label=label,
                type=index_type
            )
            
        except Exception as e:
            # Index may already exist
            logger.debug(
                "neo4j_index_exists_or_failed",
                label=config.get('label'),
                error=str(e)
            )
    
    def sync_record(
        self,
        source_data: Dict[str, Any],
        record_id: str
    ) -> Dict[str, Any]:
        """
        Sync a single record to Neo4j graph.
        
        Creates nodes and relationships based on config.
        
        Args:
            source_data: Raw source data
            record_id: Unique record identifier
            
        Returns:
            Sync result with statistics
        """
        try:
            with self.driver.session() as session:
                # Create/update nodes
                nodes_created = self._sync_nodes(session, source_data, record_id)
                
                # Create relationships
                rels_created = self._sync_relationships(session, source_data, record_id)
                
                logger.info(
                    "neo4j_record_synced",
                    record_id=record_id,
                    customer_id=self.customer_id,
                    nodes=nodes_created,
                    relationships=rels_created
                )
                
                return {
                    'success': True,
                    'record_id': record_id,
                    'nodes_created': nodes_created,
                    'relationships_created': rels_created
                }
                
        except Exception as e:
            logger.error(
                "neo4j_sync_failed",
                record_id=record_id,
                customer_id=self.customer_id,
                error=str(e),
                exc_info=True
            )
            return {
                'success': False,
                'record_id': record_id,
                'error': str(e)
            }
    
    def _sync_nodes(
        self, 
        session, 
        source_data: Dict[str, Any],
        record_id: str
    ) -> int:
        """Create/update nodes from source data."""
        nodes_created = 0
        
        for node_type, node_config in self.config.get('nodes', {}).items():
            # Extract node data from source
            node_data_list = self.extract_node_data(
                source_data, 
                node_type, 
                node_config
            )
            
            # Handle both single dict and list of dicts
            if not node_data_list:
                continue
            
            if isinstance(node_data_list, dict):
                node_data_list = [node_data_list]
            
            for node_data in node_data_list:
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
        
        # Build property assignments
        set_props = []
        for key in node_data.keys():
            if key != primary_key:
                set_props.append(f"n.{key} = ${key}")
        
        set_clause = ", ".join(set_props) if set_props else ""
        
        # Build query
        query = f"""
        MERGE (n:{labels} {{{primary_key}: ${primary_key}}})
        """
        
        if set_clause:
            query += f"SET {set_clause}"
        
        query += """
        SET n.customer_id = $customer_id,
            n.updated_at = datetime()
        ON CREATE SET n.created_at = datetime()
        RETURN n
        """
        
        # Execute
        session.run(query, **node_data, customer_id=self.customer_id)
    
    def _sync_relationships(
        self,
        session,
        source_data: Dict[str, Any],
        record_id: str
    ) -> int:
        """Create relationships from source data."""
        rels_created = 0
        
        for rel_type, rel_config in self.config.get('relationships', {}).items():
            # Extract relationship data
            rel_data_list = self.extract_relationship_data(
                source_data,
                rel_type,
                rel_config
            )
            
            for rel_data in rel_data_list:
                if rel_data:
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
        """Create a relationship between nodes."""
        from_label = rel_config['from']
        to_label = rel_config['to']
        
        # Get node configs
        from_node_config = self.config['nodes'][from_label]
        to_node_config = self.config['nodes'][to_label]
        
        from_key = from_node_config['primary_key']
        to_key = to_node_config['primary_key']
        
        # Build property assignments for relationship
        rel_props = []
        for key, value in rel_data.items():
            if key not in ['from_id', 'to_id']:
                rel_props.append(f"r.{key} = ${key}")
        
        props_clause = ", ".join(rel_props) if rel_props else ""
        
        # Build query
        query = f"""
        MATCH (from:{from_label} {{{from_key}: $from_id}})
        MATCH (to:{to_label} {{{to_key}: $to_id}})
        MERGE (from)-[r:{rel_type}]->(to)
        """
        
        if props_clause:
            query += f"SET {props_clause}"
        
        query += """
        SET r.customer_id = $customer_id,
            r.updated_at = datetime()
        ON CREATE SET r.created_at = datetime()
        RETURN r
        """
        
        # Execute
        try:
            session.run(query, **rel_data, customer_id=self.customer_id)
        except Exception as e:
            logger.warning(
                "neo4j_relationship_creation_failed",
                rel_type=rel_type,
                from_id=rel_data.get('from_id'),
                to_id=rel_data.get('to_id'),
                error=str(e)
            )
    
    @abstractmethod
    def extract_node_data(
        self,
        source_data: Dict[str, Any],
        node_type: str,
        node_config: Dict
    ) -> Union[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract node data from source.
        Must implement per dataset.
        
        Args:
            source_data: Raw source data
            node_type: Type of node (from config)
            node_config: Node configuration
            
        Returns:
            Dict with node properties or List of dicts, or None if not applicable
        """
        pass
    
    @abstractmethod
    def extract_relationship_data(
        self,
        source_data: Dict[str, Any],
        rel_type: str,
        rel_config: Dict
    ) -> List[Dict[str, Any]]:
        """
        Extract relationship data from source.
        Must implement per dataset.
        
        Args:
            source_data: Raw source data
            rel_type: Type of relationship (from config)
            rel_config: Relationship configuration
            
        Returns:
            List of dicts with 'from_id', 'to_id', and properties
        """
        pass
    
    def delete_record(self, record_id: str) -> bool:
        """
        Delete all nodes/relationships for a record.
        
        Args:
            record_id: Record ID to delete
            
        Returns:
            True if successful
        """
        try:
            with self.driver.session() as session:
                # Find and delete all related nodes
                # This is a generic approach - may need customization per dataset
                query = """
                MATCH (n {customer_id: $customer_id})
                WHERE n.record_id = $record_id 
                   OR n.pdl_id = $record_id
                   OR n.id = $record_id
                DETACH DELETE n
                """
                session.run(query, customer_id=self.customer_id, record_id=record_id)
                
                logger.info(
                    "neo4j_record_deleted",
                    record_id=record_id,
                    customer_id=self.customer_id
                )
                return True
                
        except Exception as e:
            logger.error(
                "neo4j_delete_failed",
                record_id=record_id,
                error=str(e)
            )
            return False
    
    def query(self, cypher: str, parameters: Optional[Dict] = None) -> List[Dict]:
        """
        Execute Cypher query.
        
        Args:
            cypher: Cypher query string
            parameters: Query parameters
            
        Returns:
            List of result records
        """
        try:
            with self.driver.session() as session:
                result = session.run(cypher, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(
                "neo4j_query_failed",
                error=str(e),
                exc_info=True
            )
            raise
    
    def close(self):
        """Close driver connection."""
        self.driver.close()

