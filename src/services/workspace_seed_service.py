"""
Workspace Seed Service

Seeds default workspaces (like FASB) for specific customers on startup.
This ensures built-in workspaces exist without manual creation.
"""

from typing import List
from sqlalchemy.orm import Session

from src.models.ragflow_domain import RAGFlowDomain, RAGFlowDomainStatus
from src.models.workspace import WorkspaceTemplate
from src.core.logging import get_logger

logger = get_logger(__name__, component="workspace.seed")


class WorkspaceSeedService:
    """Service for seeding default workspaces."""
    
    # Only seed for these customer IDs
    SEED_CUSTOMER_IDS = ["eliza"]
    
    # Built-in workspaces to seed
    BUILT_IN_WORKSPACES = [
        {
            "name": "fasb",
            "display_name": "FASB Standards (ASC)",
            "description": "Ask questions about FASB Accounting Standards Codification. Get authoritative answers with cited sources from ASC topics.",
            "icon": "book-open",
            "color": "#10b981",  # emerald
            "template_name": "rag_retrieval",
            "status": RAGFlowDomainStatus.READY,  # Already indexed in OpenSearch
            "workspace_config": {
                "backend_type": "opensearch_fasb",
                "opensearch_index": "fasb-chunks-v4",
            },
            # Document/chunk counts reflecting OpenSearch index
            "document_count": 90,  # ~90 ASC topic PDFs
            "chunk_count": 15000,  # Approximate chunks in OpenSearch
        },
    ]
    
    def __init__(self, db: Session):
        self.db = db
    
    def ensure_default_workspaces_exist(self) -> int:
        """
        Seed default workspaces for allowed customer IDs.
        
        Returns:
            Number of workspaces created.
        """
        created_count = 0
        
        for customer_id in self.SEED_CUSTOMER_IDS:
            count = self._seed_for_customer(customer_id)
            created_count += count
        
        return created_count
    
    def _seed_for_customer(self, customer_id: str) -> int:
        """Seed workspaces for a specific customer."""
        created = 0
        
        for ws_config in self.BUILT_IN_WORKSPACES:
            # Check if workspace already exists
            existing = self.db.query(RAGFlowDomain).filter(
                RAGFlowDomain.customer_id == customer_id,
                RAGFlowDomain.name == ws_config["name"]
            ).first()
            
            if existing:
                logger.info(
                    "workspace_already_exists",
                    customer_id=customer_id,
                    workspace_name=ws_config["name"]
                )
                continue
            
            # Get template ID
            template = self.db.query(WorkspaceTemplate).filter(
                WorkspaceTemplate.name == ws_config["template_name"]
            ).first()
            
            if not template:
                logger.warning(
                    "template_not_found",
                    template_name=ws_config["template_name"]
                )
                continue
            
            # Create workspace
            workspace = RAGFlowDomain(
                customer_id=customer_id,
                name=ws_config["name"],
                display_name=ws_config["display_name"],
                description=ws_config["description"],
                icon=ws_config["icon"],
                color=ws_config["color"],
                template_id=template.id,
                status=ws_config["status"],
                workspace_config=ws_config["workspace_config"],
                document_count=ws_config.get("document_count", 0),
                chunk_count=ws_config.get("chunk_count", 0),
                is_active=True,
            )
            
            self.db.add(workspace)
            created += 1
            
            logger.info(
                "workspace_seeded",
                customer_id=customer_id,
                workspace_name=ws_config["name"],
                template=ws_config["template_name"]
            )
        
        if created > 0:
            self.db.commit()
        
        return created
