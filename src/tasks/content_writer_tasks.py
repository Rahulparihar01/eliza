"""
Content Writer Celery Tasks

Async tasks for the Research-First Content Writer product.
Handles research, POV generation, draft generation, and refinement.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from src.celery_app import celery_app
from src.models import database
from src.models.content_writer import RunStatus
from src.core.logging import get_logger, LogCategory
from src.services.langfuse_service import get_langfuse_service

logger = get_logger(__name__, LogCategory.BUSINESS)


@celery_app.task(bind=True, max_retries=2, time_limit=600)  # 10 min timeout
def process_content_writer_run(
    self,
    run_id: str,
    user_id: int,
    customer_id: str,
) -> Dict[str, Any]:
    """
    Main task to process a content writer run.
    
    Executes the full workflow:
    1. Research Phase - Gather evidence from selected sources
    2. POV Generation - Generate POV options
    
    Note: Draft generation is triggered separately after user selects POV.
    
    Args:
        run_id: Run ID
        user_id: User ID
        customer_id: Customer ID
        
    Returns:
        Result dict with status and any error
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    langfuse_service = get_langfuse_service()
    
    try:
        logger.info(f"Starting content writer run: {run_id}")
        
        from src.services.content_writer import ContentWriterService
        service = ContentWriterService(db)
        
        # Get run
        run = service.get_run(run_id, customer_id)
        if not run:
            return {"success": False, "error": "Run not found"}
        
        # Update status to researching
        service.update_run_status(run_id, RunStatus.RESEARCHING)
        
        # Execute research flow
        from src.flows.content_writer_flow import ContentWriterFlow
        flow = ContentWriterFlow(
            run_id=run_id,
            customer_id=customer_id,
            user_id=user_id,
            topic=run.topic,
            format=run.format,
            selected_sources=run.selected_sources,
            pasted_text=run.pasted_text,
            constraints=run.constraints,
        )
        
        # Run research phase
        logger.info(f"Running research phase for run {run_id}")
        with langfuse_service.span_scope(
            name="agentmesh.content_writer.task.conduct_research",
            input_data={"run_id": run_id, "topic": run.topic, "format": str(run.format)},
            metadata={
                "component": "agentmesh",
                "task": "content_writer.process_content_writer_run",
                "run_id": run_id,
                "customer_id": customer_id,
                "user_id": user_id,
            },
        ):
            research_result = flow.conduct_research()
        
        if not research_result:
            service.update_run_status(
                run_id,
                RunStatus.FAILED,
                error_message="Research phase returned no results",
            )
            return {"success": False, "error": "Research failed"}
        
        # Save research pack
        service.create_research_pack(
            run_id=run_id,
            key_takeaways=research_result.get("key_takeaways", []),
            excerpts=research_result.get("excerpts", []),
            contested_items=research_result.get("contested_items"),
            best_counterargument=research_result.get("best_counterargument"),
        )
        
        # Generate POV options
        logger.info(f"Generating POV options for run {run_id}")
        with langfuse_service.span_scope(
            name="agentmesh.content_writer.task.generate_povs",
            input_data={
                "run_id": run_id,
                "takeaway_count": len(research_result.get("key_takeaways", [])),
                "excerpt_count": len(research_result.get("excerpts", [])),
            },
            metadata={
                "component": "agentmesh",
                "task": "content_writer.process_content_writer_run",
                "run_id": run_id,
                "customer_id": customer_id,
                "user_id": user_id,
            },
        ):
            pov_result = flow.generate_povs(research_result)
        
        if not pov_result or not pov_result.get("pov_options"):
            service.update_run_status(
                run_id,
                RunStatus.FAILED,
                error_message="POV generation returned no results",
            )
            return {"success": False, "error": "POV generation failed"}
        
        # Save POV options and update status
        service.update_run_pov_options(run_id, pov_result["pov_options"])
        
        logger.info(f"Content writer run {run_id} ready for POV selection")
        langfuse_service.trace_event(
            name="agentmesh.content_writer.task.process_content_writer_run.completed",
            input_data={"run_id": run_id},
            output_data={
                "status": "pov_selection",
                "pov_count": len(pov_result["pov_options"]),
            },
            metadata={
                "component": "agentmesh",
                "task": "content_writer.process_content_writer_run",
                "run_id": run_id,
                "customer_id": customer_id,
                "user_id": user_id,
            },
        )
        return {
            "success": True,
            "run_id": run_id,
            "status": "pov_selection",
            "pov_count": len(pov_result["pov_options"]),
        }
        
    except Exception as e:
        logger.error(f"Content writer run failed: {e}", exc_info=True)
        
        try:
            from src.services.content_writer import ContentWriterService
            service = ContentWriterService(db)
            service.update_run_status(
                run_id,
                RunStatus.FAILED,
                error_message=str(e),
            )
        except Exception:
            pass
        
        return {"success": False, "error": str(e)}
    
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, time_limit=600)  # 10 min timeout
def generate_draft_task(
    self,
    run_id: str,
    user_id: int,
    customer_id: str,
    apply_default_skills: bool = True,
    specific_skill_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Generate draft using selected POV (Fast Path).
    
    Args:
        run_id: Run ID
        user_id: User ID
        customer_id: Customer ID
        apply_default_skills: Whether to apply default skills
        specific_skill_ids: Specific skill IDs to apply
        
    Returns:
        Result dict with draft content
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    langfuse_service = get_langfuse_service()
    
    try:
        logger.info(f"Generating draft for run: {run_id}")
        
        from src.services.content_writer import ContentWriterService
        service = ContentWriterService(db)
        
        # Get run
        run = service.get_run(run_id, customer_id)
        if not run:
            return {"success": False, "error": "Run not found"}
        
        if not run.selected_pov:
            return {"success": False, "error": "POV not selected"}
        
        # Get research pack
        research_pack = service.get_research_pack(run_id)
        
        # Get skills
        skills = []
        if apply_default_skills:
            skills = service.get_default_skills(customer_id, user_id)
        if specific_skill_ids:
            for skill in service.list_skills(customer_id, user_id):
                if skill.id in specific_skill_ids and skill not in skills:
                    skills.append(skill)
        
        # Update status
        service.update_run_status(run_id, RunStatus.DRAFTING)
        
        # Execute draft generation flow
        from src.flows.content_writer_flow import ContentWriterFlow
        flow = ContentWriterFlow(
            run_id=run_id,
            customer_id=customer_id,
            user_id=user_id,
            topic=run.topic,
            format=run.format,
            selected_sources=run.selected_sources,
            pasted_text=run.pasted_text,
            constraints=run.constraints,
            selected_pov=run.selected_pov,
            selected_hook=run.selected_hook,
            selected_outline=run.selected_outline,
            research_pack=research_pack.excerpts if research_pack else None,
            user_skills=[s.content for s in skills],
        )
        
        # Generate hooks and outlines IN PARALLEL for speed
        needs_hooks = not run.selected_hook
        needs_outlines = run.format.value in ("blog", "twitter_article") and not run.selected_outline
        
        if needs_hooks or needs_outlines:
            logger.info(f"Generating hooks and outlines in parallel for run {run_id}")
            
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {}
                
                if needs_hooks:
                    futures['hooks'] = executor.submit(flow.generate_hooks)
                
                if needs_outlines:
                    futures['outlines'] = executor.submit(flow.generate_outlines)
                
                # Wait for all to complete and process results
                for key, future in futures.items():
                    try:
                        result = future.result(timeout=120)  # 2 min timeout per task
                        
                        if key == 'hooks' and result and result.get("hook_options"):
                            service.update_run_hook_options(run_id, result["hook_options"])
                            service.select_hook(run_id, 0)  # Auto-select first hook
                            logger.info(f"Generated {len(result['hook_options'])} hooks for run {run_id}")
                        
                        elif key == 'outlines' and result and result.get("outline_options"):
                            service.update_run_outline_options(run_id, result["outline_options"])
                            service.select_outline(run_id, 0)  # Auto-select first outline
                            logger.info(f"Generated {len(result['outline_options'])} outlines for run {run_id}")
                    
                    except Exception as e:
                        logger.warning(f"Failed to generate {key} for run {run_id}: {e}")
        
        # Generate draft
        logger.info(f"Generating full draft for run {run_id}")
        with langfuse_service.span_scope(
            name="agentmesh.content_writer.task.generate_draft",
            input_data={
                "run_id": run_id,
                "format": str(run.format),
                "has_selected_pov": bool(run.selected_pov),
                "has_selected_hook": bool(run.selected_hook),
                "has_selected_outline": bool(run.selected_outline),
            },
            metadata={
                "component": "agentmesh",
                "task": "content_writer.generate_draft_task",
                "run_id": run_id,
                "customer_id": customer_id,
                "user_id": user_id,
            },
        ):
            draft_result = flow.generate_draft()
        
        if not draft_result or not draft_result.get("content"):
            service.update_run_status(
                run_id,
                RunStatus.FAILED,
                error_message="Draft generation returned no content",
            )
            return {"success": False, "error": "Draft generation failed"}
        
        # Save draft
        draft = service.create_draft(
            run_id=run_id,
            content=draft_result["content"],
            refinement_type="full_generation",
        )
        
        # Increment skill usage
        if skills:
            service.increment_skill_usage([s.id for s in skills])
        
        logger.info(f"Draft generated for run {run_id}")
        langfuse_service.trace_event(
            name="agentmesh.content_writer.task.generate_draft_task.completed",
            input_data={"run_id": run_id},
            output_data={
                "draft_id": draft.id if draft else None,
                "version": draft.version if draft else None,
                "word_count": draft.word_count if draft else None,
            },
            metadata={
                "component": "agentmesh",
                "task": "content_writer.generate_draft_task",
                "run_id": run_id,
                "customer_id": customer_id,
                "user_id": user_id,
            },
        )
        return {
            "success": True,
            "run_id": run_id,
            "draft_id": draft.id if draft else None,
            "version": draft.version if draft else None,
            "word_count": draft.word_count if draft else None,
        }
        
    except Exception as e:
        logger.error(f"Draft generation failed: {e}", exc_info=True)
        
        try:
            from src.services.content_writer import ContentWriterService
            service = ContentWriterService(db)
            service.update_run_status(
                run_id,
                RunStatus.FAILED,
                error_message=str(e),
            )
        except Exception:
            pass
        
        return {"success": False, "error": str(e)}
    
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, time_limit=300)  # 5 min timeout
def generate_pov_pointers_task(
    self,
    run_id: str,
    section_text: str,
    document_summary: str,
    context_before: str,
    context_after: str,
    issue_types: List[str],
    issue_explanation: Optional[str],
    num_pointers: int,
    research_pack: Optional[List[Dict[str, Any]]],
    user_id: int,
    customer_id: str,
) -> Dict[str, Any]:
    """
    Generate POV pointers for section refinement (Step 1).
    
    Args:
        run_id: Run ID
        section_text: Text to refine
        document_summary: Brief summary of overall document
        context_before: Paragraphs before section
        context_after: Paragraphs after section
        issue_types: Identified issues
        issue_explanation: Additional context
        num_pointers: Number of POV pointers to generate
        research_pack: Research excerpts
        user_id: User ID
        customer_id: Customer ID
        
    Returns:
        Dict with pov_pointers list
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    langfuse_service = get_langfuse_service()
    
    try:
        logger.info(f"Generating {num_pointers} POV pointers for run {run_id}")
        
        from src.flows.content_writer_flow import ContentWriterFlow
        
        # Get run for context
        from src.services.content_writer import ContentWriterService
        service = ContentWriterService(db)
        run = service.get_run(run_id, customer_id)
        
        flow = ContentWriterFlow(
            run_id=run_id,
            customer_id=customer_id,
            user_id=user_id,
            topic=run.topic if run else "Unknown",
            format=run.format if run else "blog",
            selected_sources=[],
            research_pack=research_pack,
        )
        
        with langfuse_service.span_scope(
            name="agentmesh.content_writer.task.generate_pov_pointers",
            input_data={
                "run_id": run_id,
                "num_pointers": num_pointers,
                "issue_types": issue_types,
                "section_length_chars": len(section_text),
            },
            metadata={
                "component": "agentmesh",
                "task": "content_writer.generate_pov_pointers_task",
                "run_id": run_id,
                "customer_id": customer_id,
                "user_id": user_id,
            },
        ):
            result = flow.generate_pov_pointers(
                section_text=section_text,
                document_summary=document_summary,
                context_before=context_before,
                context_after=context_after,
                issue_types=issue_types,
                issue_explanation=issue_explanation,
                num_pointers=num_pointers,
            )
        
        logger.info(f"Generated {len(result.get('pov_pointers', []))} POV pointers")
        return result
        
    except Exception as e:
        logger.error(f"POV pointer generation failed: {e}", exc_info=True)
        return {"success": False, "error": str(e), "pov_pointers": []}
    
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, time_limit=300)  # 5 min timeout
def refine_draft_section_task(
    self,
    run_id: str,
    section_text: str,
    document_summary: str,
    context_before: str,
    context_after: str,
    issue_types: List[str],
    issue_explanation: Optional[str],
    pov_selection: Dict[str, Any],
    research_pack: Optional[List[Dict[str, Any]]],
    user_skills: List[Dict[str, Any]],
    user_id: int,
    customer_id: str,
) -> Dict[str, Any]:
    """
    Refine section with selected POV (Step 2).
    
    Args:
        run_id: Run ID
        section_text: Text to refine
        document_summary: Brief summary of overall document
        context_before: Paragraphs before section
        context_after: Paragraphs after section
        issue_types: Identified issues
        issue_explanation: Additional context
        pov_selection: Selected POV approach
        research_pack: Research excerpts
        user_skills: User skills content
        user_id: User ID
        customer_id: Customer ID
        
    Returns:
        Dict with refined_text, changes_summary, pov_applied
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    langfuse_service = get_langfuse_service()
    
    try:
        logger.info(f"Refining section for run {run_id}")
        
        from src.flows.content_writer_flow import ContentWriterFlow
        
        # Get run for context
        from src.services.content_writer import ContentWriterService
        service = ContentWriterService(db)
        run = service.get_run(run_id, customer_id)
        
        flow = ContentWriterFlow(
            run_id=run_id,
            customer_id=customer_id,
            user_id=user_id,
            topic=run.topic if run else "Unknown",
            format=run.format if run else "blog",
            selected_sources=[],
            research_pack=research_pack,
            user_skills=user_skills,
        )
        
        with langfuse_service.span_scope(
            name="agentmesh.content_writer.task.refine_draft_section",
            input_data={
                "run_id": run_id,
                "issue_types": issue_types,
                "section_length_chars": len(section_text),
                "pov_label": pov_selection.get("label"),
            },
            metadata={
                "component": "agentmesh",
                "task": "content_writer.refine_draft_section_task",
                "run_id": run_id,
                "customer_id": customer_id,
                "user_id": user_id,
            },
        ):
            result = flow.refine_section_with_pov(
                section_text=section_text,
                document_summary=document_summary,
                context_before=context_before,
                context_after=context_after,
                issue_types=issue_types,
                issue_explanation=issue_explanation,
                pov_selection=pov_selection,
            )
        
        logger.info(f"Section refined for run {run_id}")
        return result
        
    except Exception as e:
        logger.error(f"Section refinement failed: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e),
            "refined_text": section_text,
            "changes_summary": f"Refinement failed: {str(e)}",
            "pov_applied": "None",
        }
    
    finally:
        db.close()
