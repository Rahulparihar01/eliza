"""
Business Intelligence Celery Tasks

Async tasks for processing business intelligence questions through
task enrichment and data analysis flows.
"""
from datetime import datetime, timezone
from typing import Dict, Any
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from src.celery_app import celery_app
from src.models.business_intelligence import QuestionStatus, AgentStatus, TelemetryEventType
from src.services.business_intelligence_service import BusinessIntelligenceService
from src.services.connectivity_service import check_data_source_connectivity
from src.crewai_flows.task_enrichment_flow import (
    TaskEnrichmentFlow, TaskEnrichmentFlowState, UserContext
)
from src.crewai_flows.data_analysis_flow import (
    DataAnalysisFlow, DataAnalysisFlowState
)
from src.core.logging import get_logger, LogCategory, bind_context

logger = get_logger(__name__, LogCategory.BUSINESS)


class BusinessIntelligenceTask(Task):
    """Base task class for BI tasks with retry logic."""
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 5}
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True


@celery_app.task(base=BusinessIntelligenceTask, bind=True, name="process_bi_question")
def process_bi_question(self, question_id: str, user_id: int, customer_id: str, company_hr_dataset: str) -> Dict[str, Any]:
    """
    Process a business intelligence question through enrichment and analysis flows.
    
    Args:
        question_id: Unique question identifier
        user_id: User ID
        customer_id: Customer ID (user's organization)
        company_hr_dataset: Target company for HR data analysis
        
    Returns:
        Dict with processing results
    """
    bind_context(
        task="process_bi_question",
        question_id=question_id,
        user_id=user_id,
        customer_id=customer_id,
        company_hr_dataset=company_hr_dataset
    )
    
    logger.info(
        "process_bi_question_start",
        question_id=question_id,
        task_id=self.request.id,
        company_hr_dataset=company_hr_dataset
    )
    
    # Import SessionLocal dynamically to avoid None at import time
    from src.models.database import SessionLocal, init_database
    
    # Ensure database is initialized
    if SessionLocal is None:
        logger.info("SessionLocal not initialized, calling init_database()")
        init_database()
        from src.models.database import SessionLocal
        
        if SessionLocal is None:
            raise RuntimeError("SessionLocal is still None after init_database() - check database configuration")
    
    db = SessionLocal()
    try:
        bi_service = BusinessIntelligenceService(db)
        
        # Get the question
        question = bi_service.get_question(question_id)
        if not question:
            logger.error("question_not_found", question_id=question_id)
            return {"success": False, "error": "Question not found"}

        if question.status == QuestionStatus.FAILED:
            logger.warning(
                "question_already_failed", question_id=question_id, error=question.error_message
            )
            return {"success": False, "error": question.error_message or "Question already failed"}

        if not question.original_question:
            error_msg = "Original question text missing"
            logger.error("question_invalid_payload", question_id=question_id)
            bi_service.update_question_status(
                question_id,
                QuestionStatus.FAILED,
                error_message=error_msg
            )
            return {"success": False, "error": error_msg}
        
        # Update status to enriching
        bi_service.update_question_status(question_id, QuestionStatus.ENRICHING)
        
        # Stage 1: Task Enrichment Flow
        logger.info("task_enrichment_flow_start", question_id=question_id)
        
        try:
            enrichment_flow = TaskEnrichmentFlow()
            enrichment_state = TaskEnrichmentFlowState(
                original_question=question.original_question,
                user_context=UserContext(
                    user_id=user_id,
                    customer_id=customer_id,
                    role=None,  # TODO: Get from user profile
                    department=None,  # TODO: Get from user profile
                    previous_queries=None,
                    preferences=None
                )
            )
            
            # Run enrichment flow (CrewAI expects dict, not Pydantic model)
            enrichment_flow.kickoff(enrichment_state.dict())
            
            # Get updated state from flow instance (flow updates its internal state)
            if hasattr(enrichment_flow, 'state'):
                enrichment_state = enrichment_flow.state
            
            if enrichment_state.error:
                logger.error(
                    "task_enrichment_flow_error",
                    question_id=question_id,
                    error=enrichment_state.error
                )
                bi_service.update_question_status(
                    question_id,
                    QuestionStatus.FAILED,
                    error_message=enrichment_state.error
                )
                return {"success": False, "error": enrichment_state.error}
            
            if not enrichment_state.enriched_prompt:
                error_msg = "Enrichment flow did not produce a prompt"
                logger.error("task_enrichment_flow_no_output", question_id=question_id)
                bi_service.update_question_status(
                    question_id,
                    QuestionStatus.FAILED,
                    error_message=error_msg
                )
                return {"success": False, "error": error_msg}
            
            # Save enriched prompt
            enriched_prompt = bi_service.create_enriched_prompt(
                question_id=question.id,
                original_input=enrichment_state.original_question,
                enriched_prompt=enrichment_state.enriched_prompt.enriched_prompt,
                intent_type=enrichment_state.enriched_prompt.task_analysis.intent_type,
                complexity=enrichment_state.enriched_prompt.task_analysis.complexity,
                confidence_score=enrichment_state.enriched_prompt.task_analysis.confidence_score,
                processing_instructions=enrichment_state.enriched_prompt.processing_instructions,
                expected_output_format=enrichment_state.enriched_prompt.expected_output_format,
                validation_criteria=enrichment_state.enriched_prompt.validation_criteria,
                quality_score=enrichment_state.enriched_prompt.quality_score,
                rag_context=enrichment_state.enriched_prompt.rag_context
            )
            
            # Update question with enriched prompt
            question.enriched_prompt_id = enriched_prompt.id
            db.commit()

            # Mark question status transition after enrichment
            bi_service.update_question_status(
                question.question_id,
                QuestionStatus.ANALYZING
            )
            
            logger.info(
                "task_enrichment_flow_complete",
                question_id=question_id,
                prompt_id=enriched_prompt.prompt_id
            )
            
        except Exception as e:
            logger.error(
                "task_enrichment_flow_exception",
                question_id=question_id,
                error=str(e),
                exc_info=True
            )
            bi_service.update_question_status(
                question_id,
                QuestionStatus.FAILED,
                error_message=f"Enrichment failed: {str(e)}"
            )
            return {"success": False, "error": str(e)}
        
        # Data Source Connectivity Checks
        logger.info(
            "data_source_connectivity_check_start",
            question_id=question_id,
            customer_id=customer_id
        )
        
        try:
            # Check connectivity to all data sources before starting analysis
            connectivity_results = check_data_source_connectivity(customer_id, company_hr_dataset)
            
            # Log connectivity results
            for source_name, result in connectivity_results.items():
                logger.info(
                    f"connectivity_check_{source_name}",
                    question_id=question_id,
                    status=result["status"],
                    available=result["available"],
                    status_message=result["message"]
                )
            
            # Check if critical data sources are available
            vector_index_status = connectivity_results.get("vector_index", {})
            hr_database_status = connectivity_results.get("hr_database", {})
            
            # Vector index is marked as ALWAYS REQUIRED - fail if unavailable
            if vector_index_status.get("status") != "healthy":
                error_msg = (
                    f"Vector index connectivity check failed: {vector_index_status.get('message', 'Unknown error')}. "
                    "Document search is required for all queries."
                )
                logger.error(
                    "vector_index_connectivity_failed",
                    question_id=question_id,
                    error=error_msg,
                    details=vector_index_status.get("details", {})
                )
                bi_service.update_question_status(
                    question_id,
                    QuestionStatus.FAILED,
                    error_message=error_msg
                )
                return {"success": False, "error": error_msg}
            
            # HR database connectivity is a warning, not a failure
            # (some questions might not need HR data)
            if hr_database_status.get("status") != "healthy":
                logger.warning(
                    "hr_database_connectivity_warning",
                    question_id=question_id,
                    status_message=hr_database_status.get("message", "Unknown error"),
                    details=hr_database_status.get("details", {})
                )
                # Continue anyway - the query might not need HR data
            
            logger.info(
                "data_source_connectivity_check_complete",
                question_id=question_id,
                all_healthy=all(r["status"] == "healthy" for r in connectivity_results.values())
            )
            
        except Exception as e:
            logger.error(
                "data_source_connectivity_check_exception",
                question_id=question_id,
                error=str(e),
                exc_info=True
            )
            # Connectivity check failure is not fatal - log and continue
            # The actual tools will handle failures when called
            logger.warning(
                "connectivity_check_failed_continuing",
                question_id=question_id,
                reason="Connectivity check failed but continuing with analysis"
            )
        
        # Stage 2: Data Analysis Flow
        logger.info("data_analysis_flow_start", question_id=question_id)
        
        try:
            # Create analysis session
            analysis_session = bi_service.create_analysis_session(
                question_id=question.id,
                enriched_prompt_id=enriched_prompt.id
            )
            
            # Update question with session
            question.analysis_session_id = analysis_session.id
            db.commit()
            
            # Add telemetry: analysis started
            bi_service.add_telemetry_event(
                session_id=analysis_session.id,
                event_type=TelemetryEventType.STAGE_STARTED,
                stage_name="Enrichment",
                user_message="Running task enrichment",
                progress_percentage=10.0,
            )
            
            # Add telemetry: connectivity checks
            bi_service.add_telemetry_event(
                session_id=analysis_session.id,
                event_type=TelemetryEventType.INFO,
                user_message="Verifying data source connectivity...",
                progress_percentage=15.0,
            )
            
            # Add telemetry for each data source based on connectivity results
            if 'connectivity_results' in locals():
                for source_name, result in connectivity_results.items():
                    if result["status"] == "healthy":
                        display_name = "HR Database" if source_name == "hr_database" else "Document Search"
                        data_note = ""
                        
                        # Add note about data availability
                        if not result.get("has_customer_data", True):
                            data_note = " (no data available)"
                        
                        bi_service.add_telemetry_event(
                            session_id=analysis_session.id,
                            event_type=TelemetryEventType.INFO,
                            user_message=f"✓ {display_name} connected{data_note}",
                            progress_percentage=18.0,
                        )
                    else:
                        display_name = "HR Database" if source_name == "hr_database" else "Document Search"
                        bi_service.add_telemetry_event(
                            session_id=analysis_session.id,
                            event_type=TelemetryEventType.WARNING,
                            user_message=f"⚠ {display_name} unavailable: {result.get('message', 'Unknown error')}",
                            progress_percentage=18.0,
                        )
            
            # Run analysis flow
            analysis_flow = DataAnalysisFlow()
            analysis_state = DataAnalysisFlowState(
                enriched_prompt=enriched_prompt.enriched_prompt,
                customer_id=customer_id,
                company_hr_dataset=company_hr_dataset,
                user_id=user_id,
                data_sources_needed=enrichment_state.enriched_prompt.task_analysis.data_sources_needed,
                session_id=analysis_session.id  # Pass session ID for tracking (creates own db sessions)
            )
            
            # Update session status
            bi_service.update_analysis_session(
                analysis_session.session_id,
                status=AgentStatus.RUNNING
            )
            
            # Add telemetry: data retrieval started
            bi_service.add_telemetry_event(
                session_id=analysis_session.id,
                event_type=TelemetryEventType.AGENT_STARTED,
                agent_name="Data Retrieval Agent",
                user_message="Retrieving data from HR database and documents...",
                progress_percentage=25.0
            )
            
            # Execute analysis flow (CrewAI expects dict, not Pydantic model)
            analysis_flow.kickoff(analysis_state.dict())
            
            # Get updated state from flow instance (flow updates its internal state)
            if hasattr(analysis_flow, 'state'):
                analysis_state = analysis_flow.state
            
            # Add telemetry: data retrieval completed
            bi_service.add_telemetry_event(
                session_id=analysis_session.id,
                event_type=TelemetryEventType.AGENT_COMPLETED,
                agent_name="Data Retrieval Agent",
                user_message="Data retrieval completed",
                progress_percentage=50.0
            )
            
            # Add telemetry: analysis started
            bi_service.add_telemetry_event(
                session_id=analysis_session.id,
                event_type=TelemetryEventType.AGENT_STARTED,
                agent_name="Data Analysis Agent",
                user_message="Analyzing data and generating insights...",
                progress_percentage=75.0
            )
            
            if analysis_state.error:
                logger.error(
                    "data_analysis_flow_error",
                    question_id=question_id,
                    error=analysis_state.error
                )
                bi_service.update_analysis_session(
                    analysis_session.session_id,
                    status=AgentStatus.FAILED,
                    error_message=analysis_state.error
                )
                bi_service.update_question_status(
                    question_id,
                    QuestionStatus.FAILED,
                    error_message=analysis_state.error
                )
                return {"success": False, "error": analysis_state.error}
            
            if not analysis_state.analysis_result:
                error_msg = "Analysis flow did not produce results"
                logger.error("data_analysis_flow_no_output", question_id=question_id)
                bi_service.update_analysis_session(
                    analysis_session.session_id,
                    status=AgentStatus.FAILED,
                    error_message=error_msg
                )
                bi_service.update_question_status(
                    question_id,
                    QuestionStatus.FAILED,
                    error_message=error_msg
                )
                return {"success": False, "error": error_msg}
            
            # Save analysis result
            analysis_result = bi_service.create_analysis_result(
                question_id=question.id,
                session_id=analysis_session.id,
                analysis_text=analysis_state.analysis_result.analysis_text,
                executive_summary=analysis_state.analysis_result.executive_summary,
                key_findings=analysis_state.analysis_result.key_findings,
                data_sources_used=analysis_state.analysis_result.data_sources_used,
                confidence_score=analysis_state.analysis_result.confidence_score,
                recommendations=analysis_state.analysis_result.recommendations,
                visualizations=analysis_state.analysis_result.visualizations,
                metadata=analysis_state.analysis_result.metadata
            )
            
            # Update question with result
            question.result_id = analysis_result.id
            db.commit()
            
            # Update session status
            bi_service.update_analysis_session(
                analysis_session.session_id,
                status=AgentStatus.COMPLETED,
                agents_executed={"data_retriever": "completed", "data_analyzer": "completed"},
                tools_used={"hr_database": True, "document_search": True},
                data_sources_queried={"hr_database": True, "documents": True}
            )
            
            # Add telemetry: analysis completed
            bi_service.add_telemetry_event(
                session_id=analysis_session.id,
                event_type=TelemetryEventType.AGENT_COMPLETED,
                agent_name="Data Analysis Agent",
                user_message="Analysis completed successfully",
                progress_percentage=100.0
            )
            
            # Update question status to completed
            completed_question = bi_service.update_question_status(question_id, QuestionStatus.COMPLETED)

            logger.info(
                "data_analysis_flow_complete",
                question_id=question_id,
                result_id=analysis_result.result_id
            )

            return {
                "success": True,
                "question_id": question_id,
                "result_id": analysis_result.result_id,
                "status": completed_question.status.value if completed_question else "completed"
            }
            
        except SoftTimeLimitExceeded:
            logger.error(
                "data_analysis_flow_timeout",
                question_id=question_id,
            )
            if 'analysis_session' in locals():
                bi_service.update_analysis_session(
                    analysis_session.session_id,
                    status=AgentStatus.FAILED,
                    error_message="Data analysis exceeded execution time limit"
                )
            bi_service.update_question_status(
                question_id,
                QuestionStatus.FAILED,
                error_message="Data analysis exceeded execution time limit"
            )
            return {"success": False, "error": "Data analysis timed out"}
        except Exception as e:
            logger.error(
                "data_analysis_flow_exception",
                question_id=question_id,
                error=str(e),
                exc_info=True
            )
            if 'analysis_session' in locals():
                bi_service.update_analysis_session(
                    analysis_session.session_id,
                    status=AgentStatus.FAILED,
                    error_message=str(e)
                )
            bi_service.update_question_status(
                question_id,
                QuestionStatus.FAILED,
                error_message=f"Analysis failed: {str(e)}"
            )
            return {"success": False, "error": str(e)}
        
    except Exception as e:
        logger.error(
            "process_bi_question_exception",
            question_id=question_id,
            error=str(e),
            exc_info=True
        )
        return {"success": False, "error": str(e)}
    
    finally:
        db.close()

