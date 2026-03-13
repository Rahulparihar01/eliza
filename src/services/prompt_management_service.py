"""
Prompt Management Service - Centralized prompt storage, versioning, and retrieval.

This service provides:
- CRUD operations for prompt templates
- Version control for prompts
- Activation/deactivation of prompt versions
- Integration with GEPA for optimized prompts
- Change logging for audit trails
- Auto-discovery of domains from DataSourceType
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc

from src.models.prompt_template import (
    PromptTemplate,
    PromptChangeLog,
    DomainPromptConfig,
    DomainPromptFeedback,
    PromptType,
    PromptStatus,
)
from src.models.data_analyst import DataSourceType
from src.core.logging import get_logger
from src.services.workspace_rag_backend import refresh_workspace_prompt_templates_for_domain

logger = get_logger(__name__)


# Default prompts for each domain
DEFAULT_DOMAIN_PROMPTS = {
    "fasb": {
        "display_name": "FASB Accounting Standards",
        "description": "FASB Accounting Standards Codification RAG system",
        "prompts": {
            PromptType.SYSTEM: {
                "name": "FASB System Prompt",
                "content": """You are an assistant that answers questions about FASB Accounting Standards Codification (ASC).
Use ONLY the provided context. If the answer isn't in the context, say "I don't know."
When you state facts, cite sources like [1], [2] referring to the numbered context items.

FORMATTING RULES:
- Use **bold** for key terms and requirements (e.g., **no preference**, **consistently**)
- Use bullet points (- ) when listing multiple requirements or items
- Keep answers clear, structured, and authoritative
- Cite sources inline where relevant [1], [2], etc.""",
            },
            PromptType.QUERY_REWRITE: {
                "name": "FASB Query Rewrite",
                "content": """Rewrite the user's question to be more specific for searching FASB Accounting Standards.
Focus on:
- Identifying specific ASC topics or codification numbers mentioned
- Extracting key accounting terms and concepts
- Clarifying the type of guidance needed (recognition, measurement, disclosure, etc.)

Original question: {question}
Rewritten query:""",
            },
            PromptType.SYNTHESIS: {
                "name": "FASB Answer Synthesis",
                "content": """Based on the retrieved FASB context, provide a clear and authoritative answer.

Question: {question}

Context:
{context}

Provide a well-structured answer with proper citations [1], [2], etc.""",
            },
        },
    },
    "insurance": {
        "display_name": "Insurance Domain",
        "description": "Insurance industry data analysis and RAG system",
        "prompts": {
            PromptType.SYSTEM: {
                "name": "Insurance System Prompt",
                "content": """You are an expert insurance data analyst assistant.
You help users understand insurance data, policies, claims, and industry metrics.
Use the provided context and data to give accurate, helpful answers.
Always cite your sources when making factual claims.""",
            },
            PromptType.QUERY_REWRITE: {
                "name": "Insurance Query Rewrite",
                "content": """Rewrite the user's question for insurance data analysis.
Focus on:
- Identifying specific insurance products, coverage types, or policy elements
- Extracting key metrics (premiums, claims, loss ratios, etc.)
- Clarifying the time period or scope of the analysis

Original question: {question}
Rewritten query:""",
            },
            PromptType.SYNTHESIS: {
                "name": "Insurance Answer Synthesis",
                "content": """Based on the retrieved insurance data and context, provide a helpful analysis.

Question: {question}

Context/Data:
{context}

Provide a clear answer with relevant insights:""",
            },
        },
    },
    "knowledge_base": {
        "display_name": "Knowledge Base",
        "description": "RAGFlow-powered customer knowledge bases",
        "prompts": {
            PromptType.SYSTEM: {
                "name": "Knowledge Base System Prompt",
                "content": """You are a retrieval-augmented assistant for a customer knowledge base.
Use ONLY the provided context. If the answer is not in the context, say "I don't know."
When you state facts, cite sources like [1], [2] referring to the numbered context items.

FORMATTING RULES:
- Be concise, clear, and accurate
- Use bullet points (- ) for lists
- Avoid speculation or unstated assumptions
- Cite sources inline where relevant [1], [2], etc.""",
            },
            PromptType.QUERY_REWRITE: {
                "name": "Knowledge Base Query Rewrite",
                "content": """Rewrite the user's question to improve document retrieval.
Focus on:
- Preserving key entities, names, and product terms
- Adding synonyms or alternate phrasing
- Keeping the query short and search-friendly

Original question: {question}
Rewritten query:""",
            },
            PromptType.SYNTHESIS: {
                "name": "Knowledge Base Answer Synthesis",
                "content": """Based on the retrieved context, provide a clear answer.

Question: {question}

Context:
{context}

Provide a concise answer with proper citations [1], [2], etc.""",
            },
        },
    },
}


class PromptManagementService:
    """Service for managing prompt templates across domains."""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== Domain Auto-Discovery ====================
    
    def sync_domains_from_data_sources(self, customer_id: str) -> List[DomainPromptConfig]:
        """
        Auto-discover and create domains from DataSourceType enum.
        This ensures all data source types have corresponding prompt domains.
        """
        created = []
        
        for data_source in DataSourceType:
            domain = data_source.value.lower()
            
            # Check if domain config exists
            existing = self.db.query(DomainPromptConfig).filter(
                and_(
                    DomainPromptConfig.customer_id == customer_id,
                    DomainPromptConfig.domain == domain
                )
            ).first()
            
            if not existing:
                # Get default config for this domain
                default_config = DEFAULT_DOMAIN_PROMPTS.get(domain, {})
                
                config = DomainPromptConfig(
                    customer_id=customer_id,
                    domain=domain,
                    display_name=default_config.get("display_name", domain.upper()),
                    description=default_config.get("description", f"{domain.upper()} domain"),
                    is_active=True,
                )
                self.db.add(config)
                created.append(config)
                
                # Create default prompts for this domain
                if "prompts" in default_config:
                    for prompt_type, prompt_data in default_config["prompts"].items():
                        self._create_default_prompt(
                            customer_id=customer_id,
                            domain=domain,
                            prompt_type=prompt_type,
                            name=prompt_data["name"],
                            content=prompt_data["content"],
                        )
        
        if created:
            self.db.commit()
            logger.info(f"Created {len(created)} domain configs from DataSourceType")
        
        return created
    
    def _create_default_prompt(
        self,
        customer_id: str,
        domain: str,
        prompt_type: PromptType,
        name: str,
        content: str,
    ) -> PromptTemplate:
        """Create a default prompt template."""
        prompt = PromptTemplate(
            customer_id=customer_id,
            domain=domain,
            prompt_type=prompt_type,
            name=name,
            content=content,
            version=1,
            is_active=True,
            status=PromptStatus.ACTIVE,
            created_by_user_id=None,
        )
        self.db.add(prompt)
        return prompt
    
    # ==================== Domain Config Operations ====================
    
    def get_or_create_domain_config(
        self,
        customer_id: str,
        domain: str,
        display_name: Optional[str] = None,
    ) -> DomainPromptConfig:
        """Get or create a domain configuration."""
        config = self.db.query(DomainPromptConfig).filter(
            and_(
                DomainPromptConfig.customer_id == customer_id,
                DomainPromptConfig.domain == domain
            )
        ).first()
        
        if not config:
            # Get default config
            default_config = DEFAULT_DOMAIN_PROMPTS.get(domain, {})
            
            config = DomainPromptConfig(
                customer_id=customer_id,
                domain=domain,
                display_name=display_name or default_config.get("display_name", domain.replace("_", " ").title()),
                description=default_config.get("description"),
            )
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
            
            # Create default prompts if available
            if "prompts" in default_config:
                for prompt_type, prompt_data in default_config["prompts"].items():
                    self._create_default_prompt(
                        customer_id=customer_id,
                        domain=domain,
                        prompt_type=prompt_type,
                        name=prompt_data["name"],
                        content=prompt_data["content"],
                    )
                self.db.commit()
        
        return config
    
    def list_domain_configs(
        self,
        customer_id: str,
        active_only: bool = True,
        auto_sync: bool = True,
    ) -> List[DomainPromptConfig]:
        """
        List all domain configurations for a customer.
        
        If auto_sync is True, will first sync domains from DataSourceType.
        """
        # Auto-sync domains from DataSourceType
        if auto_sync:
            self.sync_domains_from_data_sources(customer_id)
        
        query = self.db.query(DomainPromptConfig).filter(
            DomainPromptConfig.customer_id == customer_id
        )
        
        if active_only:
            query = query.filter(DomainPromptConfig.is_active == True)
        
        return query.order_by(DomainPromptConfig.display_name).all()
    
    def update_domain_config(
        self,
        customer_id: str,
        domain: str,
        **kwargs
    ) -> Optional[DomainPromptConfig]:
        """Update a domain configuration."""
        config = self.db.query(DomainPromptConfig).filter(
            and_(
                DomainPromptConfig.customer_id == customer_id,
                DomainPromptConfig.domain == domain
            )
        ).first()
        
        if not config:
            return None
        
        for key, value in kwargs.items():
            if hasattr(config, key) and value is not None:
                setattr(config, key, value)
        
        self.db.commit()
        self.db.refresh(config)
        return config
    
    # ==================== Prompt Template Operations ====================
    
    def create_prompt(
        self,
        customer_id: str,
        domain: str,
        prompt_type: PromptType,
        name: str,
        content: str,
        user_id: Optional[int] = None,
        description: Optional[str] = None,
        variables: Optional[List[str]] = None,
        status: PromptStatus = PromptStatus.DRAFT,
        is_active: bool = False,
        gepa_variant_id: Optional[int] = None,
        gepa_job_id: Optional[int] = None,
        source: str = "manual",
        source_reference: Optional[str] = None,
    ) -> PromptTemplate:
        """Create a new prompt template."""
        # Ensure domain config exists
        self.get_or_create_domain_config(customer_id, domain)
        
        # Get next version number
        max_version = self.db.query(func.max(PromptTemplate.version)).filter(
            and_(
                PromptTemplate.customer_id == customer_id,
                PromptTemplate.domain == domain,
                PromptTemplate.prompt_type == prompt_type
            )
        ).scalar() or 0
        
        version = max_version + 1
        
        # If setting as active, deactivate others first
        if is_active:
            self._deactivate_prompts(customer_id, domain, prompt_type)
        
        prompt = PromptTemplate(
            customer_id=customer_id,
            domain=domain,
            prompt_type=prompt_type,
            name=name,
            description=description,
            content=content,
            variables=variables,
            version=version,
            is_active=is_active,
            status=status if not is_active else PromptStatus.ACTIVE,
            created_by_user_id=user_id,
            last_modified_by_user_id=user_id,
            gepa_variant_id=gepa_variant_id,
            gepa_job_id=gepa_job_id,
        )
        
        self.db.add(prompt)
        self.db.commit()
        self.db.refresh(prompt)
        
        # Log the creation
        self._log_change(
            prompt_id=prompt.id,
            action="created",
            new_content=content,
            user_id=user_id,
            source=source,
            source_reference=source_reference,
            change_summary=f"Created {prompt_type.value} prompt v{version} for {domain}"
        )

        if is_active:
            self._refresh_workspace_prompt_snapshots(
                customer_id=customer_id,
                domain=domain,
                gepa_variant_id=gepa_variant_id,
                gepa_job_id=gepa_job_id,
            )
        
        logger.info(f"Created prompt template: {domain}/{prompt_type.value} v{version}")
        return prompt
    
    def get_prompt(
        self,
        customer_id: str,
        domain: str,
        prompt_type: PromptType,
        version: Optional[int] = None,
    ) -> Optional[PromptTemplate]:
        """
        Get a prompt template.
        
        If version is not specified, returns the active version.
        """
        query = self.db.query(PromptTemplate).filter(
            and_(
                PromptTemplate.customer_id == customer_id,
                PromptTemplate.domain == domain,
                PromptTemplate.prompt_type == prompt_type
            )
        )
        
        if version:
            query = query.filter(PromptTemplate.version == version)
        else:
            query = query.filter(PromptTemplate.is_active == True)
        
        return query.first()
    
    def get_prompt_by_id(self, prompt_id: int) -> Optional[PromptTemplate]:
        """Get a prompt template by ID."""
        return self.db.query(PromptTemplate).filter(
            PromptTemplate.id == prompt_id
        ).first()
    
    def get_active_prompts(
        self,
        customer_id: str,
        domain: str,
    ) -> Dict[str, PromptTemplate]:
        """Get all active prompts for a domain, keyed by prompt type."""
        prompts = self.db.query(PromptTemplate).filter(
            and_(
                PromptTemplate.customer_id == customer_id,
                PromptTemplate.domain == domain,
                PromptTemplate.is_active == True
            )
        ).all()
        
        return {p.prompt_type.value: p for p in prompts}
    
    def list_prompts(
        self,
        customer_id: str,
        domain: Optional[str] = None,
        prompt_type: Optional[PromptType] = None,
        status: Optional[PromptStatus] = None,
        include_archived: bool = False,
    ) -> List[PromptTemplate]:
        """List prompt templates with optional filters."""
        query = self.db.query(PromptTemplate).filter(
            PromptTemplate.customer_id == customer_id
        )
        
        if domain:
            query = query.filter(PromptTemplate.domain == domain)
        
        if prompt_type:
            query = query.filter(PromptTemplate.prompt_type == prompt_type)
        
        if status:
            query = query.filter(PromptTemplate.status == status)
        elif not include_archived:
            query = query.filter(PromptTemplate.status != PromptStatus.ARCHIVED)
        
        return query.order_by(
            PromptTemplate.domain,
            PromptTemplate.prompt_type,
            desc(PromptTemplate.version)
        ).all()
    
    def list_prompt_versions(
        self,
        customer_id: str,
        domain: str,
        prompt_type: PromptType,
    ) -> List[PromptTemplate]:
        """List all versions of a specific prompt type."""
        return self.db.query(PromptTemplate).filter(
            and_(
                PromptTemplate.customer_id == customer_id,
                PromptTemplate.domain == domain,
                PromptTemplate.prompt_type == prompt_type
            )
        ).order_by(desc(PromptTemplate.version)).all()
    
    def update_prompt(
        self,
        prompt_id: int,
        user_id: Optional[int] = None,
        **kwargs
    ) -> Optional[PromptTemplate]:
        """Update a prompt template (creates new version if content changes)."""
        prompt = self.get_prompt_by_id(prompt_id)
        if not prompt:
            return None
        
        # Check if content is being changed
        content_changed = 'content' in kwargs and kwargs['content'] != prompt.content
        
        if content_changed:
            # Create a new version instead of modifying
            return self.create_prompt(
                customer_id=prompt.customer_id,
                domain=prompt.domain,
                prompt_type=prompt.prompt_type,
                name=kwargs.get('name', prompt.name),
                content=kwargs['content'],
                user_id=user_id,
                description=kwargs.get('description', prompt.description),
                variables=kwargs.get('variables', prompt.variables),
                status=kwargs.get('status', PromptStatus.DRAFT),
                is_active=False,  # New versions start inactive
                source="manual",
            )
        
        # Update non-content fields
        previous_content = prompt.content
        for key, value in kwargs.items():
            if hasattr(prompt, key) and value is not None and key != 'content':
                setattr(prompt, key, value)
        
        prompt.last_modified_by_user_id = user_id
        
        self.db.commit()
        self.db.refresh(prompt)
        
        # Clear prompt cache if this is an active prompt
        if prompt.is_active:
            try:
                from src.utils.prompt_loader import clear_prompt_cache
                clear_prompt_cache()
                logger.info(f"Cleared prompt cache after update")
            except Exception as e:
                logger.warning(f"Could not clear prompt cache: {e}")
        
        self._log_change(
            prompt_id=prompt.id,
            action="updated",
            previous_content=previous_content,
            new_content=prompt.content,
            user_id=user_id,
            change_summary="Updated prompt metadata"
        )

        if prompt.is_active:
            self._refresh_workspace_prompt_snapshots(
                customer_id=prompt.customer_id,
                domain=prompt.domain,
                gepa_variant_id=prompt.gepa_variant_id,
                gepa_job_id=prompt.gepa_job_id,
            )
        
        return prompt
    
    def activate_prompt(
        self,
        prompt_id: int,
        user_id: Optional[int] = None,
    ) -> Optional[PromptTemplate]:
        """Activate a prompt version (deactivates others of same type)."""
        prompt = self.get_prompt_by_id(prompt_id)
        if not prompt:
            return None
        
        # Deactivate other versions
        self._deactivate_prompts(
            prompt.customer_id, 
            prompt.domain, 
            prompt.prompt_type
        )
        
        # Activate this version
        prompt.is_active = True
        prompt.status = PromptStatus.ACTIVE
        prompt.last_modified_by_user_id = user_id
        
        self.db.commit()
        self.db.refresh(prompt)
        
        # Clear prompt cache so changes take effect immediately
        try:
            from src.utils.prompt_loader import clear_prompt_cache
            clear_prompt_cache()
            logger.info(f"Cleared prompt cache after activation")
        except Exception as e:
            logger.warning(f"Could not clear prompt cache: {e}")
        
        self._log_change(
            prompt_id=prompt.id,
            action="activated",
            user_id=user_id,
            change_summary=f"Activated {prompt.prompt_type.value} v{prompt.version}"
        )

        self._refresh_workspace_prompt_snapshots(
            customer_id=prompt.customer_id,
            domain=prompt.domain,
            gepa_variant_id=prompt.gepa_variant_id,
            gepa_job_id=prompt.gepa_job_id,
        )
        
        logger.info(f"Activated prompt: {prompt.domain}/{prompt.prompt_type.value} v{prompt.version}")
        return prompt
    
    def archive_prompt(
        self,
        prompt_id: int,
        user_id: Optional[int] = None,
    ) -> Optional[PromptTemplate]:
        """Archive a prompt version."""
        prompt = self.get_prompt_by_id(prompt_id)
        if not prompt:
            return None
        
        if prompt.is_active:
            raise ValueError("Cannot archive active prompt. Activate another version first.")
        
        prompt.status = PromptStatus.ARCHIVED
        prompt.last_modified_by_user_id = user_id
        
        self.db.commit()
        self.db.refresh(prompt)
        
        self._log_change(
            prompt_id=prompt.id,
            action="archived",
            user_id=user_id,
            change_summary=f"Archived {prompt.prompt_type.value} v{prompt.version}"
        )
        
        return prompt
    
    def delete_prompt(self, prompt_id: int) -> bool:
        """Delete a prompt (only drafts can be deleted)."""
        prompt = self.get_prompt_by_id(prompt_id)
        if not prompt:
            return False
        
        if prompt.status != PromptStatus.DRAFT:
            raise ValueError("Only draft prompts can be deleted. Archive instead.")
        
        self.db.delete(prompt)
        self.db.commit()
        return True
    
    # ==================== GEPA Integration ====================
    
    def promote_from_gepa(
        self,
        customer_id: str,
        domain: str,
        prompt_type: PromptType,
        content: str,
        gepa_job_id: int,
        gepa_variant_id: int,
        user_id: Optional[int] = None,
        quality_score: Optional[int] = None,
        auto_activate: bool = False,
    ) -> PromptTemplate:
        """
        Create a new prompt version from a GEPA optimization result.
        
        This is called when a variant is promoted from GEPA.
        """
        # Get variant info for name
        from src.models.gepa_optimizer import CandidateVariant
        variant = self.db.query(CandidateVariant).filter(
            CandidateVariant.id == gepa_variant_id
        ).first()
        
        variant_name = variant.variant_id if variant else f"gepa_{gepa_variant_id}"
        
        prompt = self.create_prompt(
            customer_id=customer_id,
            domain=domain,
            prompt_type=prompt_type,
            name=f"GEPA Optimized: {variant_name}",
            content=content,
            user_id=user_id,
            description=f"Optimized by GEPA job {gepa_job_id}. Quality score: {quality_score}%",
            status=PromptStatus.ACTIVE if auto_activate else PromptStatus.DRAFT,
            is_active=auto_activate,
            gepa_variant_id=gepa_variant_id,
            gepa_job_id=gepa_job_id,
            source="gepa",
            source_reference=f"job:{gepa_job_id}/variant:{gepa_variant_id}",
        )
        
        if quality_score:
            prompt.avg_quality_score = quality_score
            self.db.commit()
        
        return prompt
    
    # ==================== RAG Integration ====================
    
    def get_rag_prompts(
        self,
        customer_id: str,
        domain: str,
    ) -> Dict[str, str]:
        """
        Get all active prompts for a RAG domain in a format ready for use.
        
        Returns a dict like:
        {
            "system": "You are...",
            "query_rewrite": "Rewrite...",
            "synthesis": "Based on..."
        }
        """
        # Ensure domain exists with defaults
        self.get_or_create_domain_config(customer_id, domain)
        
        prompts = self.get_active_prompts(customer_id, domain)
        
        result = {}
        for prompt_type, prompt in prompts.items():
            result[prompt_type] = prompt.content
            # Increment usage count
            prompt.usage_count += 1
        
        self.db.commit()
        return result
    
    def increment_usage(self, prompt_id: int) -> None:
        """Increment usage count for a prompt."""
        prompt = self.get_prompt_by_id(prompt_id)
        if prompt:
            prompt.usage_count += 1
            self.db.commit()
    
    # ==================== Change Log ====================
    
    def get_change_logs(
        self,
        prompt_id: Optional[int] = None,
        customer_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[PromptChangeLog]:
        """Get change logs for a prompt or customer."""
        query = self.db.query(PromptChangeLog)
        
        if prompt_id:
            query = query.filter(PromptChangeLog.prompt_template_id == prompt_id)
        elif customer_id:
            query = query.join(PromptTemplate).filter(
                PromptTemplate.customer_id == customer_id
            )
        
        return query.order_by(desc(PromptChangeLog.created_at)).limit(limit).all()
    
    # ==================== Private Helpers ====================
    
    def _deactivate_prompts(
        self,
        customer_id: str,
        domain: str,
        prompt_type: PromptType,
    ) -> None:
        """Deactivate all prompts of a specific type."""
        self.db.query(PromptTemplate).filter(
            and_(
                PromptTemplate.customer_id == customer_id,
                PromptTemplate.domain == domain,
                PromptTemplate.prompt_type == prompt_type,
                PromptTemplate.is_active == True
            )
        ).update({"is_active": False, "status": PromptStatus.DRAFT.value})

    def _refresh_workspace_prompt_snapshots(
        self,
        customer_id: str,
        domain: str,
        gepa_variant_id: Optional[int] = None,
        gepa_job_id: Optional[int] = None,
    ) -> None:
        """Refresh workspace prompt snapshots + agent cache after active prompt changes."""
        try:
            refresh_workspace_prompt_templates_for_domain(
                domain=domain,
                customer_id=customer_id,
                db=self.db,
                gepa_variant_id=gepa_variant_id,
                gepa_job_id=gepa_job_id,
            )
        except Exception as exc:
            logger.warning(
                "workspace_prompt_snapshot_refresh_failed",
                customer_id=customer_id,
                domain=domain,
                error=str(exc),
            )
    
    def _log_change(
        self,
        prompt_id: int,
        action: str,
        previous_content: Optional[str] = None,
        new_content: Optional[str] = None,
        user_id: Optional[int] = None,
        source: str = "manual",
        source_reference: Optional[str] = None,
        change_summary: Optional[str] = None,
    ) -> PromptChangeLog:
        """Log a change to a prompt."""
        log = PromptChangeLog(
            prompt_template_id=prompt_id,
            action=action,
            previous_content=previous_content,
            new_content=new_content,
            user_id=user_id,
            source=source,
            source_reference=source_reference,
            change_summary=change_summary,
        )
        self.db.add(log)
        self.db.commit()
        return log
    
    # ==================== Statistics ====================
    
    def get_domain_stats(
        self,
        customer_id: str,
        domain: str,
    ) -> Dict[str, Any]:
        """Get statistics for a domain's prompts."""
        prompts = self.list_prompts(customer_id, domain=domain, include_archived=True)
        
        active_count = sum(1 for p in prompts if p.is_active)
        draft_count = sum(1 for p in prompts if p.status == PromptStatus.DRAFT)
        archived_count = sum(1 for p in prompts if p.status == PromptStatus.ARCHIVED)
        gepa_count = sum(1 for p in prompts if p.gepa_job_id is not None)
        
        total_usage = sum(p.usage_count for p in prompts)
        
        return {
            "domain": domain,
            "total_versions": len(prompts),
            "active_count": active_count,
            "draft_count": draft_count,
            "archived_count": archived_count,
            "gepa_optimized_count": gepa_count,
            "total_usage": total_usage,
            "prompt_types": list(set(p.prompt_type.value for p in prompts)),
        }

    # ==================== Prod Feedback (for GEPA) ====================

    def create_domain_feedback(
        self,
        customer_id: str,
        domain: str,
        comment: str,
        rating_numeric: int = -1,
        environment: str = "prod",
        tags: Optional[List[str]] = None,
        improvement_suggestions: Optional[str] = None,
        target_components: Optional[List[str]] = None,
        created_by_user_id: Optional[int] = None,
    ) -> DomainPromptFeedback:
        """
        Store human/user feedback about the currently active prompt set for a domain.

        We snapshot active prompt versions at write-time so later GEPA runs can import feedback
        that corresponds to a particular deployed prompt set.
        """
        self.get_or_create_domain_config(customer_id, domain)

        active_prompts = self.get_active_prompts(customer_id, domain)  # keyed by prompt_type str
        snapshot = {
            prompt_type: {"id": p.id, "version": p.version, "name": p.name}
            for prompt_type, p in active_prompts.items()
        }

        if not snapshot:
            # Still allow feedback even if prompts are missing; but record empty snapshot explicitly.
            snapshot = {}

        rating_numeric = max(-2, min(2, int(rating_numeric)))

        fb = DomainPromptFeedback(
            customer_id=customer_id,
            domain=domain,
            environment=environment,
            rating_numeric=rating_numeric,
            comment=comment,
            tags=tags,
            improvement_suggestions=improvement_suggestions,
            target_components=target_components,
            prompt_snapshot=snapshot,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(fb)
        self.db.commit()
        self.db.refresh(fb)
        return fb

    def list_domain_feedback(
        self,
        customer_id: str,
        domain: str,
        environment: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[DomainPromptFeedback], int]:
        query = self.db.query(DomainPromptFeedback).filter(
            and_(
                DomainPromptFeedback.customer_id == customer_id,
                DomainPromptFeedback.domain == domain,
            )
        )
        if environment:
            query = query.filter(DomainPromptFeedback.environment == environment)

        total = query.count()
        items = (
            query.order_by(DomainPromptFeedback.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total

    def export_seed_feedback_for_gepa(
        self,
        customer_id: str,
        domain: str,
        environment: str = "prod",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Return feedback in GEPA seed_feedback shape:
          {rating_numeric, comment, tags, improvement_suggestions, target_components}
        """
        items, _ = self.list_domain_feedback(
            customer_id=customer_id,
            domain=domain,
            environment=environment,
            limit=limit,
            offset=0,
        )
        return [
            {
                "rating_numeric": f.rating_numeric,
                "comment": f.comment,
                "tags": f.tags,
                "improvement_suggestions": f.improvement_suggestions,
                "target_components": f.target_components,
            }
            for f in items
        ]
