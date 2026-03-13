"""
Content Writer Service

Main service for the Research-First Content Writer product.
Handles runs, research packs, drafts, skills, and section refinement.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.core.config import get_settings
from src.models.content_writer import (
    ContentWriterRun,
    ResearchPack,
    DraftArtifact,
    ContentWriterSkill,
    RunStatus,
    ContentFormat,
    SourceType,
    SkillType,
    IssueType,
)
from src.api.schemas.content_writer import (
    RunCreateRequest,
    POVPointerResponse,
    HookOptionResponse,
    OutlineOptionResponse,
    SectionIdentifier,
    POVSelection,
    ResearchPackExcerptResponse,
)

logger = logging.getLogger(__name__)
settings = get_settings()


class ContentWriterService:
    """Service for Content Writer operations."""
    
    def __init__(self, db: Session, customer_id: Optional[str] = None, user_id: Optional[int] = None):
        self.db = db
        self.customer_id = customer_id
        self.user_id = user_id
    
    # ==================== Run Management ====================
    
    def create_run(
        self,
        request: RunCreateRequest,
        customer_id: str,
        user_id: int,
    ) -> ContentWriterRun:
        """
        Create a new content writer run.
        
        Args:
            request: Run creation request
            customer_id: Customer ID
            user_id: User ID
            
        Returns:
            Created run
        """
        run_id = f"cw_{uuid.uuid4().hex[:16]}"
        
        run = ContentWriterRun(
            run_id=run_id,
            customer_id=customer_id,
            user_id=user_id,
            topic=request.topic,
            format=request.format,
            selected_sources=[s.value for s in request.selected_sources],
            pasted_text=request.pasted_text,
            constraints=request.constraints,
            status=RunStatus.PENDING,
        )
        
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        
        logger.info(f"Created content writer run: {run_id}")
        return run
    
    def get_run(
        self,
        run_id: str,
        customer_id: str,
        user_id: Optional[int] = None,
    ) -> Optional[ContentWriterRun]:
        """
        Get a run by ID with ownership validation.
        
        Args:
            run_id: Run ID
            customer_id: Customer ID for validation
            user_id: Optional user ID for stricter validation
            
        Returns:
            Run or None
        """
        query = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id,
            ContentWriterRun.customer_id == customer_id,
        )
        
        if user_id:
            query = query.filter(ContentWriterRun.user_id == user_id)
        
        return query.first()
    
    def list_runs(
        self,
        customer_id: str,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        status: Optional[RunStatus] = None,
    ) -> Tuple[List[ContentWriterRun], int]:
        """
        List runs for a user.
        
        Args:
            customer_id: Customer ID
            user_id: User ID
            page: Page number (1-indexed)
            page_size: Items per page
            status: Optional status filter
            
        Returns:
            (runs, total_count)
        """
        query = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.customer_id == customer_id,
            ContentWriterRun.user_id == user_id,
        )
        
        if status:
            query = query.filter(ContentWriterRun.status == status)
        
        total = query.count()
        
        runs = query.order_by(desc(ContentWriterRun.created_at)).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        
        return runs, total
    
    def update_run_status(
        self,
        run_id: str,
        status: RunStatus,
        error_message: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Optional[ContentWriterRun]:
        """Update run status."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run:
            return None
        
        run.status = status
        if error_message:
            run.error_message = error_message
        if task_id:
            run.task_id = task_id
        
        if status == RunStatus.RESEARCHING and not run.started_at:
            run.started_at = datetime.utcnow()
        elif status in (RunStatus.COMPLETED, RunStatus.FAILED):
            run.completed_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(run)
        
        logger.info(f"Updated run {run_id} status to {status}")
        return run
    
    def update_run_pov_options(
        self,
        run_id: str,
        pov_options: List[Dict[str, Any]],
    ) -> Optional[ContentWriterRun]:
        """Store generated POV options."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run:
            return None
        
        run.pov_options = pov_options
        run.status = RunStatus.POV_SELECTION
        self.db.commit()
        self.db.refresh(run)
        
        return run
    
    def select_pov(
        self,
        run_id: str,
        pov_index: Optional[int] = None,
        custom_pov: Optional[str] = None,
    ) -> Optional[ContentWriterRun]:
        """Select a POV for the run."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run:
            return None
        
        if custom_pov:
            run.selected_pov = {
                "type": "custom",
                "instruction": custom_pov,
            }
        elif pov_index is not None and run.pov_options:
            if 0 <= pov_index < len(run.pov_options):
                run.selected_pov = run.pov_options[pov_index]
        
        self.db.commit()
        self.db.refresh(run)
        
        return run
    
    def update_run_hook_options(
        self,
        run_id: str,
        hook_options: List[Dict[str, Any]],
    ) -> Optional[ContentWriterRun]:
        """Store generated hook options."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run:
            return None
        
        run.hook_options = hook_options
        run.status = RunStatus.HOOK_SELECTION
        self.db.commit()
        self.db.refresh(run)
        
        return run
    
    def select_hook(
        self,
        run_id: str,
        hook_index: int,
    ) -> Optional[ContentWriterRun]:
        """Select a hook for the run."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run or not run.hook_options:
            return None
        
        if 0 <= hook_index < len(run.hook_options):
            run.selected_hook = run.hook_options[hook_index]
        
        self.db.commit()
        self.db.refresh(run)
        
        return run
    
    def update_run_outline_options(
        self,
        run_id: str,
        outline_options: List[Dict[str, Any]],
    ) -> Optional[ContentWriterRun]:
        """Store generated outline options."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run:
            return None
        
        run.outline_options = outline_options
        run.status = RunStatus.OUTLINE_SELECTION
        self.db.commit()
        self.db.refresh(run)
        
        return run
    
    def select_outline(
        self,
        run_id: str,
        outline_index: int,
    ) -> Optional[ContentWriterRun]:
        """Select an outline for the run."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run or not run.outline_options:
            return None
        
        if 0 <= outline_index < len(run.outline_options):
            run.selected_outline = run.outline_options[outline_index]
        
        self.db.commit()
        self.db.refresh(run)
        
        return run
    
    # ==================== Research Pack Management ====================
    
    def create_research_pack(
        self,
        run_id: str,
        key_takeaways: List[Dict[str, Any]],
        excerpts: List[Dict[str, Any]],
        contested_items: Optional[List[Dict[str, Any]]] = None,
        best_counterargument: Optional[str] = None,
    ) -> Optional[ResearchPack]:
        """Create research pack for a run."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run:
            return None
        
        # Add IDs to excerpts if not present
        for i, excerpt in enumerate(excerpts):
            if 'id' not in excerpt:
                excerpt['id'] = i
        
        research_pack = ResearchPack(
            run_id=run.id,
            key_takeaways=key_takeaways,
            excerpts=excerpts,
            contested_items=contested_items,
            best_counterargument=best_counterargument,
        )
        
        self.db.add(research_pack)
        self.db.commit()
        self.db.refresh(research_pack)
        
        logger.info(f"Created research pack for run {run_id}")
        return research_pack
    
    def get_research_pack(self, run_id: str) -> Optional[ResearchPack]:
        """Get research pack for a run."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run:
            return None
        
        return run.research_pack
    
    def update_research_pack_selections(
        self,
        run_id: str,
        selected_excerpt_ids: List[int],
    ) -> Optional[ResearchPack]:
        """Update selected excerpts in research pack."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run or not run.research_pack:
            return None
        
        run.research_pack.selected_excerpt_ids = selected_excerpt_ids
        self.db.commit()
        self.db.refresh(run.research_pack)
        
        return run.research_pack
    
    # ==================== Draft Management ====================
    
    def create_draft(
        self,
        run_id: str,
        content: str,
        refinement_type: str = "full_generation",
        refinement_instruction: Optional[str] = None,
        parent_version_id: Optional[int] = None,
    ) -> Optional[DraftArtifact]:
        """Create a new draft artifact."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run:
            return None
        
        # Determine version number
        latest_draft = self.get_latest_draft(run_id)
        version = 1 if not latest_draft else latest_draft.version + 1
        
        draft = DraftArtifact(
            run_id=run.id,
            version=version,
            format=run.format,
            content=content,
            word_count=len(content.split()),
            character_count=len(content),
            refinement_type=refinement_type,
            refinement_instruction=refinement_instruction,
            parent_version_id=parent_version_id,
        )
        
        self.db.add(draft)
        
        # Update run status
        run.status = RunStatus.COMPLETED
        run.completed_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(draft)
        
        logger.info(f"Created draft v{version} for run {run_id}")
        return draft
    
    def get_latest_draft(self, run_id: str) -> Optional[DraftArtifact]:
        """Get the latest draft for a run."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run:
            return None
        
        return self.db.query(DraftArtifact).filter(
            DraftArtifact.run_id == run.id
        ).order_by(desc(DraftArtifact.version)).first()
    
    def get_draft_version(self, run_id: str, version: int) -> Optional[DraftArtifact]:
        """Get a specific draft version."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run:
            return None
        
        return self.db.query(DraftArtifact).filter(
            DraftArtifact.run_id == run.id,
            DraftArtifact.version == version,
        ).first()
    
    def list_draft_versions(self, run_id: str) -> List[DraftArtifact]:
        """List all draft versions for a run."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run:
            return []
        
        return self.db.query(DraftArtifact).filter(
            DraftArtifact.run_id == run.id
        ).order_by(desc(DraftArtifact.version)).all()
    
    def create_draft_version(
        self,
        run_id: str,
        content: str,
        parent_version_id: int,
        refinement_type: str,
        refinement_instruction: str,
    ) -> Optional[DraftArtifact]:
        """Create a new draft version after refinement."""
        run = self.db.query(ContentWriterRun).filter(
            ContentWriterRun.run_id == run_id
        ).first()
        
        if not run:
            return None
        
        parent = self.db.query(DraftArtifact).filter(
            DraftArtifact.id == parent_version_id
        ).first()
        
        if not parent:
            return None
        
        draft = DraftArtifact(
            run_id=run.id,
            version=parent.version + 1,
            format=run.format,
            content=content,
            word_count=len(content.split()),
            character_count=len(content),
            parent_version_id=parent_version_id,
            refinement_type=refinement_type,
            refinement_instruction=refinement_instruction,
        )
        
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        
        logger.info(f"Created draft v{draft.version} for run {run_id}")
        return draft
    
    # ==================== Section Refinement ====================
    
    def extract_section_context(
        self,
        draft: DraftArtifact,
        section: SectionIdentifier,
        context_paragraphs: int = 2,
        include_summary: bool = True,
    ) -> Dict[str, str]:
        """
        Extract context around a section for refinement.
        
        Args:
            draft: Draft artifact containing full content
            section: Section identifier (highlighted text + location)
            context_paragraphs: Number of paragraphs before/after (default 2)
            include_summary: Include document summary (default True)
        
        Returns:
            {
                "document_summary": str,
                "before": str,
                "after": str,
                "section_index": int
            }
        """
        content = draft.content
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        
        # Find section location
        section_index = None
        for i, para in enumerate(paragraphs):
            if section.highlighted_text.strip() in para:
                section_index = i
                break
        
        if section_index is None:
            # Fallback: search by character position if provided
            if section.start_char is not None:
                char_count = 0
                for i, para in enumerate(paragraphs):
                    if char_count <= section.start_char < char_count + len(para):
                        section_index = i
                        break
                    char_count += len(para) + 2  # +2 for \n\n
        
        if section_index is None:
            raise ValueError("Section not found in draft")
        
        # Extract context
        start_idx = max(0, section_index - context_paragraphs)
        end_idx = min(len(paragraphs), section_index + context_paragraphs + 1)
        
        context_before = "\n\n".join(paragraphs[start_idx:section_index])
        context_after = "\n\n".join(paragraphs[section_index + 1:end_idx])
        
        # Generate document summary
        document_summary = ""
        if include_summary:
            document_summary = self._generate_document_summary(content, draft.format)
        
        return {
            "document_summary": document_summary,
            "before": context_before,
            "after": context_after,
            "section_index": section_index,
        }
    
    def _generate_document_summary(self, content: str, format: ContentFormat) -> str:
        """
        Generate a brief summary of the overall document.
        
        For MVP, extracts first paragraph + metadata.
        In production, use LLM to generate actual summary.
        """
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        
        if not paragraphs:
            return "Document is empty."
        
        # Simple heuristic: first paragraph + word count
        first_para = paragraphs[0][:300]
        word_count = len(content.split())
        
        format_name = format.value if isinstance(format, ContentFormat) else format
        return f"{first_para}... (Total: {word_count} words, Format: {format_name})"
    
    def replace_section(
        self,
        content: str,
        section: SectionIdentifier,
        new_text: str,
    ) -> str:
        """
        Replace a section in the content with new text.
        
        Args:
            content: Full draft content
            section: Section identifier with highlighted text
            new_text: Replacement text
        
        Returns:
            Updated content with section replaced
        """
        if section.highlighted_text not in content:
            raise ValueError("Section not found in content")
        
        # Replace first occurrence
        updated_content = content.replace(section.highlighted_text, new_text, 1)
        return updated_content
    
    # ==================== Skills Management ====================
    
    def create_skill(
        self,
        customer_id: str,
        user_id: int,
        skill_type: SkillType,
        name: str,
        content: Dict[str, Any],
        description: Optional[str] = None,
        is_default: bool = False,
    ) -> ContentWriterSkill:
        """Create a new skill."""
        skill_id = f"sk_{uuid.uuid4().hex[:16]}"
        
        skill = ContentWriterSkill(
            skill_id=skill_id,
            customer_id=customer_id,
            user_id=user_id,
            skill_type=skill_type,
            name=name,
            description=description,
            content=content,
            is_default=is_default,
        )
        
        self.db.add(skill)
        self.db.commit()
        self.db.refresh(skill)
        
        logger.info(f"Created skill: {skill_id} ({skill_type})")
        return skill
    
    def get_skill(
        self,
        skill_id: str,
        customer_id: str,
        user_id: int,
    ) -> Optional[ContentWriterSkill]:
        """Get a skill by ID with ownership validation."""
        return self.db.query(ContentWriterSkill).filter(
            ContentWriterSkill.skill_id == skill_id,
            ContentWriterSkill.customer_id == customer_id,
            ContentWriterSkill.user_id == user_id,
        ).first()
    
    def list_skills(
        self,
        customer_id: str,
        user_id: int,
        skill_types: Optional[List[SkillType]] = None,
    ) -> List[ContentWriterSkill]:
        """List skills for a user."""
        query = self.db.query(ContentWriterSkill).filter(
            ContentWriterSkill.customer_id == customer_id,
            ContentWriterSkill.user_id == user_id,
        )
        
        if skill_types:
            query = query.filter(ContentWriterSkill.skill_type.in_(skill_types))
        
        return query.order_by(ContentWriterSkill.name).all()
    
    def get_default_skills(
        self,
        customer_id: str,
        user_id: int,
    ) -> List[ContentWriterSkill]:
        """Get default skills for a user."""
        return self.db.query(ContentWriterSkill).filter(
            ContentWriterSkill.customer_id == customer_id,
            ContentWriterSkill.user_id == user_id,
            ContentWriterSkill.is_default == True,
        ).all()
    
    def update_skill(
        self,
        skill_id: str,
        customer_id: str,
        user_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        content: Optional[Dict[str, Any]] = None,
        is_default: Optional[bool] = None,
    ) -> Optional[ContentWriterSkill]:
        """Update a skill."""
        skill = self.get_skill(skill_id, customer_id, user_id)
        
        if not skill:
            return None
        
        if name is not None:
            skill.name = name
        if description is not None:
            skill.description = description
        if content is not None:
            skill.content = content
        if is_default is not None:
            skill.is_default = is_default
        
        self.db.commit()
        self.db.refresh(skill)
        
        return skill
    
    def delete_skill(
        self,
        skill_id: str,
        customer_id: str,
        user_id: int,
    ) -> bool:
        """Delete a skill."""
        skill = self.get_skill(skill_id, customer_id, user_id)
        
        if not skill:
            return False
        
        self.db.delete(skill)
        self.db.commit()
        
        logger.info(f"Deleted skill: {skill_id}")
        return True
    
    def increment_skill_usage(
        self,
        skill_ids: List[int],
    ) -> None:
        """Increment usage count for skills."""
        self.db.query(ContentWriterSkill).filter(
            ContentWriterSkill.id.in_(skill_ids)
        ).update(
            {
                ContentWriterSkill.usage_count: ContentWriterSkill.usage_count + 1,
                ContentWriterSkill.last_used_at: datetime.utcnow(),
            },
            synchronize_session=False,
        )
        self.db.commit()
    
    def get_user_skills(
        self,
        customer_id: str,
        user_id: int,
        skill_types: Optional[List[str]] = None,
    ) -> List[ContentWriterSkill]:
        """Get user skills, optionally filtered by type."""
        query = self.db.query(ContentWriterSkill).filter(
            ContentWriterSkill.customer_id == customer_id,
            ContentWriterSkill.user_id == user_id,
        )
        
        if skill_types:
            query = query.filter(ContentWriterSkill.skill_type.in_(skill_types))
        
        return query.all()
