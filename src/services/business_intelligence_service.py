"""
Business Intelligence Service

Service layer for the Business Intelligence Q&A system.
Orchestrates task enrichment and data analysis flows.
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timezone
import uuid

from src.models.business_intelligence import (
    BIQuestion, BIEnrichedPrompt, BIAnalysisSession,
    BIAgentTelemetry, BIAnalysisResult,
    QuestionStatus, AgentStatus, TelemetryEventType
)
from src.services.base_service import BaseService
from src.core.logging import get_logger, LogCategory, bind_context

logger = get_logger(__name__, component="business_intelligence")


class BusinessIntelligenceService(BaseService):
    """Service for managing business intelligence questions and analysis."""
    
    def __init__(self, db: Session):
        """Initialize the service with a database session."""
        self.db = db
        bind_context(service="business_intelligence")
    
    def create_question(
        self,
        user_id: int,
        customer_id: str,
        question: str,
        company_hr_dataset: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> BIQuestion:
        """
        Create a new business intelligence question.
        
        Args:
            user_id: ID of the user asking the question
            customer_id: Customer ID (user's organization)
            question: The user's question
            company_hr_dataset: Target company for HR data analysis
            session_id: Optional session ID to group related questions
            metadata: Optional metadata
            
        Returns:
            Created BIQuestion instance
        """
        logger.debug(
            "create_bi_question_start", 
            user_id=user_id, 
            customer_id=customer_id,
            company_hr_dataset=company_hr_dataset
        )

        try:
            question_id = f"q_{uuid.uuid4().hex[:12]}"

            initial_status = QuestionStatus.PENDING
            bi_question = BIQuestion(
                question_id=question_id,
                user_id=user_id,
                customer_id=customer_id,
                company_hr_dataset=company_hr_dataset,
                session_id=session_id,
                original_question=question,
                status=initial_status.value,
                question_metadata=metadata or {}
            )

            self.db.add(bi_question)
            self.db.commit()
            self.db.refresh(bi_question)

            logger.info(
                "bi_question_created",
                question_id=question_id,
                user_id=user_id,
                customer_id=customer_id,
                company_hr_dataset=company_hr_dataset
            )

            return bi_question

        except Exception as e:
            self.db.rollback()
            logger.error(
                "bi_question_creation_failed",
                error=str(e),
                exc_info=True
            )
            raise
    
    def get_question(self, question_id: str) -> Optional[BIQuestion]:
        """Get a question by ID."""
        return self.db.query(BIQuestion).filter(
            BIQuestion.question_id == question_id
        ).first()

    def mark_question_failed(self, question_id: str, error_message: str) -> Optional[BIQuestion]:
        """Mark a question as failed with an error message."""
        question = self.get_question(question_id)
        if not question:
            return None

        question.status = QuestionStatus.FAILED.value
        question.error_message = error_message
        question.updated_at = datetime.now(timezone.utc)
        question.completed_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(question)

        logger.error(
            "bi_question_mark_failed",
            question_id=question_id,
            error_message=error_message
        )

        return question
    
    def get_question_by_id(self, id: int) -> Optional[BIQuestion]:
        """Get a question by database ID."""
        return self.db.query(BIQuestion).filter(BIQuestion.id == id).first()
    
    def list_questions(
        self,
        user_id: Optional[int] = None,
        customer_id: Optional[str] = None,
        session_id: Optional[str] = None,
        status: Optional[QuestionStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[BIQuestion], int]:
        """
        List questions with optional filters.
        
        Returns:
            Tuple of (questions list, total count)
        """
        query = self.db.query(BIQuestion)
        
        if user_id:
            query = query.filter(BIQuestion.user_id == user_id)
        if customer_id:
            query = query.filter(BIQuestion.customer_id == customer_id)
        if session_id:
            query = query.filter(BIQuestion.session_id == session_id)
        if status:
            query = query.filter(BIQuestion.status == (status.value if hasattr(status, "value") else status))
        
        total = query.count()
        questions = query.order_by(desc(BIQuestion.created_at)).limit(limit).offset(offset).all()
        
        return questions, total
    
    def update_question_status(
        self,
        question_id: str,
        status: QuestionStatus,
        error_message: Optional[str] = None
    ) -> Optional[BIQuestion]:
        """Update question status."""
        question = self.get_question(question_id)
        if not question:
            return None
        
        question.status = status.value if hasattr(status, "value") else status
        question.updated_at = datetime.now(timezone.utc)
        
        if error_message:
            question.error_message = error_message
        
        if status == QuestionStatus.COMPLETED or status == QuestionStatus.FAILED:
            question.completed_at = datetime.now(timezone.utc)
        
        self.db.commit()
        self.db.refresh(question)
        
        logger.info(
            "bi_question_status_updated",
            question_id=question_id,
            status=status.value
        )
        
        return question
    
    def create_enriched_prompt(
        self,
        question_id: int,
        original_input: str,
        enriched_prompt: str,
        intent_type: Optional[str] = None,
        complexity: Optional[str] = None,
        confidence_score: Optional[float] = None,
        processing_instructions: Optional[Dict[str, Any]] = None,
        expected_output_format: Optional[Dict[str, Any]] = None,
        validation_criteria: Optional[Dict[str, Any]] = None,
        quality_score: Optional[float] = None,
        user_context: Optional[Dict[str, Any]] = None,
        rag_context: Optional[Dict[str, Any]] = None,
        enrichment_metadata: Optional[Dict[str, Any]] = None
    ) -> BIEnrichedPrompt:
        """Create an enriched prompt record."""
        prompt_id = f"p_{uuid.uuid4().hex[:12]}"
        
        enriched = BIEnrichedPrompt(
            prompt_id=prompt_id,
            question_id=question_id,
            original_input=original_input,
            enriched_prompt=enriched_prompt,
            intent_type=intent_type,
            complexity=complexity,
            confidence_score=confidence_score,
            processing_instructions=processing_instructions,
            expected_output_format=expected_output_format,
            validation_criteria=validation_criteria,
            quality_score=quality_score,
            user_context=user_context,
            rag_context=rag_context,
            enrichment_metadata=enrichment_metadata
        )
        
        self.db.add(enriched)
        self.db.commit()
        self.db.refresh(enriched)
        
        logger.info(
            "enriched_prompt_created",
            prompt_id=prompt_id,
            question_id=question_id,
            intent_type=intent_type
        )
        
        return enriched
    
    def list_enriched_prompts(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[BIEnrichedPrompt], int]:
        """List enriched prompts with pagination."""
        query = self.db.query(BIEnrichedPrompt)
        total = query.count()
        prompts = query.order_by(desc(BIEnrichedPrompt.created_at)).limit(limit).offset(offset).all()
        return prompts, total
    
    def create_analysis_session(
        self,
        question_id: int,
        enriched_prompt_id: int
    ) -> BIAnalysisSession:
        """Create an analysis session."""
        session_id = f"s_{uuid.uuid4().hex[:12]}"
        
        session = BIAnalysisSession(
            session_id=session_id,
            question_id=question_id,
            enriched_prompt_id=enriched_prompt_id,
            status=AgentStatus.PENDING,
            started_at=datetime.now(timezone.utc)
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        logger.info(
            "analysis_session_created",
            session_id=session_id,
            question_id=question_id
        )
        
        return session
    
    def update_analysis_session(
        self,
        session_id: str,
        status: Optional[AgentStatus] = None,
        agents_executed: Optional[Dict[str, Any]] = None,
        tools_used: Optional[Dict[str, Any]] = None,
        data_sources_queried: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> Optional[BIAnalysisSession]:
        """Update analysis session."""
        session = self.db.query(BIAnalysisSession).filter(
            BIAnalysisSession.session_id == session_id
        ).first()
        
        if not session:
            return None
        
        if status:
            session.status = status.value if hasattr(status, "value") else status
        if agents_executed:
            session.agents_executed = agents_executed
        if tools_used:
            session.tools_used = tools_used
        if data_sources_queried:
            session.data_sources_queried = data_sources_queried
        if error_message:
            session.error_message = error_message
        
        if status == AgentStatus.COMPLETED or status == AgentStatus.FAILED:
            session.completed_at = datetime.now(timezone.utc)
            if session.started_at:
                duration = (session.completed_at - session.started_at).total_seconds() * 1000
                session.duration_ms = int(duration)
        
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def add_telemetry_event(
        self,
        session_id: int,
        event_type: TelemetryEventType,
        agent_name: Optional[str] = None,
        tool_name: Optional[str] = None,
        stage_name: Optional[str] = None,
        message: Optional[str] = None,
        user_message: Optional[str] = None,
        progress_percentage: Optional[float] = None,
        data: Optional[Dict[str, Any]] = None,
        error_details: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None
    ) -> BIAgentTelemetry:
        """Add a telemetry event."""
        telemetry_id = f"t_{uuid.uuid4().hex[:12]}"
        
        telemetry = BIAgentTelemetry(
            telemetry_id=telemetry_id,
            session_id=session_id,
            event_type=getattr(event_type, 'value', event_type),
            agent_name=agent_name,
            tool_name=tool_name,
            stage_name=stage_name,
            message=message,
            user_message=user_message,
            progress_percentage=progress_percentage,
            data=data,
            error_details=error_details,
            duration_ms=duration_ms
        )
        
        self.db.add(telemetry)
        self.db.commit()
        
        return telemetry
    
    def get_telemetry_events(
        self,
        session_id: int,
        limit: int = 100,
        after_id: Optional[int] = None
    ) -> List[BIAgentTelemetry]:
        """Get telemetry events for a session."""
        query = self.db.query(BIAgentTelemetry).filter(
            BIAgentTelemetry.session_id == session_id
        )

        if after_id is not None:
            query = query.filter(BIAgentTelemetry.id > after_id)

        return query.order_by(BIAgentTelemetry.id).limit(limit).all()
    
    def create_tool_execution(
        self,
        session_id: int,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_output: Optional[Dict[str, Any]] = None,
        agent_name: Optional[str] = None,
        status: str = "pending",
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        results_count: Optional[int] = None,
        execution_metadata: Optional[Dict[str, Any]] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ):
        """Create a tool execution record."""
        from src.models.business_intelligence import BIToolExecution
        
        execution_id = f"te_{uuid.uuid4().hex[:12]}"
        
        if started_at is None:
            started_at = datetime.now(timezone.utc)
        
        tool_execution = BIToolExecution(
            execution_id=execution_id,
            session_id=session_id,
            agent_name=agent_name,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms,
            results_count=results_count,
            execution_metadata=execution_metadata,
            started_at=started_at,
            completed_at=completed_at
        )
        
        self.db.add(tool_execution)
        self.db.commit()
        self.db.refresh(tool_execution)
        
        logger.info(
            "tool_execution_created",
            execution_id=execution_id,
            tool_name=tool_name,
            status=status
        )
        
        return tool_execution
    
    def create_agent_response(
        self,
        session_id: int,
        agent_name: str,
        response_text: str,
        stage_name: Optional[str] = None,
        enriched_prompt_id: Optional[int] = None,
        input_prompt: Optional[str] = None,
        reasoning: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        confidence_score: Optional[float] = None,
        duration_ms: Optional[int] = None,
        response_metadata: Optional[Dict[str, Any]] = None
    ):
        """Create an agent response record."""
        from src.models.business_intelligence import BIAgentResponse
        
        response_id = f"ar_{uuid.uuid4().hex[:12]}"
        
        agent_response = BIAgentResponse(
            response_id=response_id,
            session_id=session_id,
            enriched_prompt_id=enriched_prompt_id,
            agent_name=agent_name,
            stage_name=stage_name,
            input_prompt=input_prompt,
            response_text=response_text,
            reasoning=reasoning,
            tool_calls=tool_calls,
            confidence_score=confidence_score,
            duration_ms=duration_ms,
            response_metadata=response_metadata
        )
        
        self.db.add(agent_response)
        self.db.commit()
        self.db.refresh(agent_response)
        
        logger.info(
            "agent_response_created",
            response_id=response_id,
            agent_name=agent_name,
            stage_name=stage_name
        )
        
        return agent_response
    
    def get_tool_executions(
        self,
        session_id: int,
        tool_name: Optional[str] = None
    ) -> List:
        """Get tool executions for a session."""
        from src.models.business_intelligence import BIToolExecution
        
        query = self.db.query(BIToolExecution).filter(
            BIToolExecution.session_id == session_id
        )
        
        if tool_name:
            query = query.filter(BIToolExecution.tool_name == tool_name)
        
        return query.order_by(BIToolExecution.started_at).all()
    
    def get_agent_responses(
        self,
        session_id: int,
        agent_name: Optional[str] = None,
        stage_name: Optional[str] = None
    ) -> List:
        """Get agent responses for a session."""
        from src.models.business_intelligence import BIAgentResponse
        
        query = self.db.query(BIAgentResponse).filter(
            BIAgentResponse.session_id == session_id
        )
        
        if agent_name:
            query = query.filter(BIAgentResponse.agent_name == agent_name)
        
        if stage_name:
            query = query.filter(BIAgentResponse.stage_name == stage_name)
        
        return query.order_by(BIAgentResponse.created_at).all()
    
    def create_analysis_result(
        self,
        question_id: int,
        session_id: int,
        analysis_text: str,
        executive_summary: Optional[str] = None,
        key_findings: Optional[List[str]] = None,
        data_sources_used: Optional[List[str]] = None,
        hr_data_queried: Optional[Dict[str, Any]] = None,
        documents_referenced: Optional[List[Dict[str, Any]]] = None,
        confidence_score: Optional[float] = None,
        recommendations: Optional[List[str]] = None,
        visualizations: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> BIAnalysisResult:
        """Create an analysis result."""
        result_id = f"r_{uuid.uuid4().hex[:12]}"
        
        result = BIAnalysisResult(
            result_id=result_id,
            question_id=question_id,
            session_id=session_id,
            analysis_text=analysis_text,
            executive_summary=executive_summary,
            key_findings=key_findings,
            data_sources_used=data_sources_used,
            hr_data_queried=hr_data_queried,
            documents_referenced=documents_referenced,
            confidence_score=confidence_score,
            recommendations=recommendations,
            visualizations=visualizations,
            metadata=metadata
        )
        
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        
        logger.info(
            "analysis_result_created",
            result_id=result_id,
            question_id=question_id
        )
        
        return result

