"""
Data Analyst Service
Handles question processing, SQL generation, and result formatting.
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
import json
import statistics
from decimal import Decimal

from src.models.data_analyst import (
    DataAnalystQuestion,
    DataAnalystMessage,
    DataAnalystTelemetry,
    DataAnalystTelemetryEventType,
    DataSourceType,
    DataAnalystQuestionStatus,
    MessageType,
    ConversationType
)
from src.services.vanna_service import VannaService
from src.services.fasb_service import get_fasb_service, FASBService
from src.services.conversation_service import ConversationService
from src.services.conversation_context_manager import ConversationContextManager
from src.services.intent_router_service import IntentRouterService, MessageIntent
from src.core.config import get_settings
from src.core.logging import get_logger
import litellm
import uuid
from datetime import datetime, date

logger = get_logger(__name__, component="data.analyst.service")

class DataAnalystService:
    """Service for data analyst agent operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        
        # Initialize Vanna service for each data source (lazy loading)
        self._vanna_services: Dict[str, VannaService] = {}
        
        # FASB service (lazy initialization)
        self._fasb_service: Optional[FASBService] = None
        
        # Initialize conversation services
        self.conversation_service = ConversationService(db)
        self.context_manager = ConversationContextManager(self.settings)
        self.intent_router = IntentRouterService()
        
        # LLM configuration for insights generation
        self._llm_initialized = False
    
    def _get_vanna_service(self, data_source_type: DataSourceType) -> VannaService:
        """Get or create Vanna service for data source."""
        if data_source_type.value not in self._vanna_services:
            # Get appropriate database URL based on data source
            if data_source_type == DataSourceType.INSURANCE:
                db_url = self.settings.insurance_demo_db_url
            elif data_source_type == DataSourceType.FASB:
                # FASB uses RAG, not Vanna - this shouldn't be called for FASB
                raise ValueError("FASB domain uses RAG, not Vanna SQL generation")
            else:
                raise ValueError(f"Unsupported data source type: {data_source_type}")
            
            # Use OpenAI model for Vanna (LocalContext_OpenAI requires OpenAI-compatible model)
            # Override default_llm_model if it's not OpenAI-compatible
            vanna_model = "gpt-4o-mini"  # Cost-effective OpenAI model for SQL generation
            
            self._vanna_services[data_source_type.value] = VannaService(
                database_url=db_url,
                model=vanna_model
            )
        
        return self._vanna_services[data_source_type.value]
    
    def _get_fasb_service(self) -> FASBService:
        """Get or create FASB RAG service."""
        if self._fasb_service is None:
            self._fasb_service = get_fasb_service()
        return self._fasb_service
    
    def create_question(
        self,
        user_id: int,
        customer_id: str,
        data_source_type: DataSourceType,
        question: str
    ) -> DataAnalystQuestion:
        """Create a new question record."""
        question_id = str(uuid.uuid4())
        
        question_record = DataAnalystQuestion(
            question_id=question_id,
            user_id=user_id,
            customer_id=customer_id,
            data_source_type=data_source_type,
            original_question=question,
            status=DataAnalystQuestionStatus.PENDING
        )
        
        self.db.add(question_record)
        self.db.commit()
        self.db.refresh(question_record)
        
        logger.info(
            "question_created",
            question_id=question_id,
            user_id=user_id,
            data_source_type=data_source_type.value
        )
        
        return question_record
    
    def add_telemetry_event(
        self,
        message_id: str,
        event_type: DataAnalystTelemetryEventType,
        agent_name: Optional[str] = None,
        tool_name: Optional[str] = None,
        stage_name: Optional[str] = None,
        message: Optional[str] = None,
        user_message: Optional[str] = None,
        progress_percentage: Optional[int] = None,
        data: Optional[Dict[str, Any]] = None,
        error_details: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[int] = None
    ) -> DataAnalystTelemetry:
        """
        Add a telemetry event for a message.
        
        Uses Pydantic validation to catch type errors before database insertion.
        """
        from src.api.schemas.data_analyst import TelemetryEventCreate
        from pydantic import ValidationError
        
        # Validate with Pydantic FIRST - this catches type errors early
        try:
            validated_event = TelemetryEventCreate(
                message_id=message_id,
                event_type=event_type,
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
        except (ValueError, ValidationError) as e:
            logger.error(
                f"Telemetry validation failed",
                message_id=message_id,
                message_id_type=type(message_id).__name__,
                event_type=event_type,
                error=str(e),
                exc_info=True
            )
            raise ValueError(f"Invalid telemetry data: {e}")
        
        # Now create SQLAlchemy model with validated data
        telemetry_id = f"dat_{uuid.uuid4().hex[:12]}"
        
        telemetry = DataAnalystTelemetry(
            telemetry_id=telemetry_id,
            message_id=validated_event.message_id,  # Use validated data
            event_type=validated_event.event_type.value,  # Enum to string for DB
            agent_name=validated_event.agent_name,
            tool_name=validated_event.tool_name,
            stage_name=validated_event.stage_name,
            message=validated_event.message,
            user_message=validated_event.user_message,
            progress_percentage=validated_event.progress_percentage,
            data=validated_event.data,
            error_details=validated_event.error_details,
            duration_ms=validated_event.duration_ms
        )
        
        # DEBUG: Log telemetry object state before adding to session
        logger.info(
            f"Telemetry object created, about to add to session",
            telemetry_id=telemetry.telemetry_id,
            telemetry_message_id=telemetry.message_id,
            telemetry_message_id_type=type(telemetry.message_id).__name__,
            validated_message_id=validated_event.message_id,
            event_type=telemetry.event_type
        )
        
        self.db.add(telemetry)
        
        # DEBUG: Log telemetry object state after adding to session
        logger.info(
            f"Telemetry added to session, about to commit",
            telemetry_id=telemetry.telemetry_id,
            telemetry_message_id=telemetry.message_id,
            telemetry_message_id_type=type(telemetry.message_id).__name__
        )
        
        self.db.commit()
        self.db.refresh(telemetry)
        
        logger.debug(
            "telemetry_event_added",
            message_id=message_id,
            event_type=event_type.value,
            stage_name=stage_name
        )
        
        return telemetry
    
    def get_telemetry_events(
        self,
        message_id: str,
        limit: int = 100,
        after_id: Optional[int] = None
    ) -> List[DataAnalystTelemetry]:
        """Get telemetry events for a message."""
        query = self.db.query(DataAnalystTelemetry).filter(
            DataAnalystTelemetry.message_id == message_id
        )
        
        if after_id is not None:
            query = query.filter(DataAnalystTelemetry.id > after_id)
        
        return query.order_by(DataAnalystTelemetry.id.asc()).limit(limit).all()
    
    def process_question(self, question_id: str) -> Dict[str, Any]:
        """
        Process a question: generate SQL, execute, format results.
        
        Returns:
            Dict with result_data and result_metadata
        """
        question = self.db.query(DataAnalystQuestion).filter(
            DataAnalystQuestion.question_id == question_id
        ).first()
        
        if not question:
            raise ValueError(f"Question {question_id} not found")
        
        # Update status
        question.status = DataAnalystQuestionStatus.PROCESSING
        self.db.commit()
        
        try:
            # Get Vanna service for data source
            vanna_service = self._get_vanna_service(question.data_source_type)
            
            # Generate SQL
            generated_sql = vanna_service.generate_sql(question.original_question)
            question.generated_sql = generated_sql
            self.db.commit()
            
            # Execute SQL
            results = vanna_service.run_sql(generated_sql)
            
            # Format results
            result_data = self._format_results(results)
            result_metadata = self._generate_metadata(
                question.original_question,
                generated_sql,
                results
            )
            
            # Update question with results
            question.result_data = result_data
            question.result_metadata = result_metadata
            question.status = DataAnalystQuestionStatus.COMPLETED
            question.completed_at = datetime.utcnow()
            self.db.commit()
            
            logger.info(
                "question_processed",
                question_id=question_id,
                result_count=len(results) if results else 0
            )
            
            return {
                "result_data": result_data,
                "result_metadata": result_metadata
            }
            
        except Exception as e:
            question.status = DataAnalystQuestionStatus.FAILED
            question.sql_error = str(e)
            self.db.commit()
            
            logger.error(
                "question_processing_failed",
                question_id=question_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    def create_message(
        self,
        user_id: int,
        customer_id: str,
        data_source_type: DataSourceType,
        question: str,
        conversation_id: Optional[str] = None,
        message_type: Optional[MessageType] = None,
        skip_intent_detection: bool = False
    ) -> DataAnalystMessage:
        """
        Create message with smart intent detection and clarification.
        
        If conversation_id is None:
        - Auto-create new conversation
        - Auto-generate title from first question
        
        If message_type is None:
        - Use smart intent detection (LLM-based)
        - May set status to CLARIFICATION_NEEDED if question is ambiguous
        
        Args:
            user_id: User ID
            customer_id: Customer/organization ID
            data_source_type: Data source type
            question: The question/message text
            conversation_id: Optional conversation ID (auto-creates if None)
            message_type: Optional message type (skips detection if provided)
            skip_intent_detection: Skip intent detection and use fallback
            
        Returns:
            Created message (may have status CLARIFICATION_NEEDED)
        """
        message_id = str(uuid.uuid4())
        question_id = str(uuid.uuid4())  # Keep for backward compatibility
        
        # Get conversation context for intent detection
        conversation = None
        conversation_context = None
        if conversation_id:
            conversation = self.conversation_service.get_conversation(conversation_id, user_id)
            if conversation:
                conversation_context = self.context_manager.get_conversation_context(conversation)
        
        # Smart intent detection (unless skipped or message_type provided)
        detected_intent = None
        intent_confidence = None
        clarification_prompt = None
        clarified_question = None
        status = DataAnalystQuestionStatus.PENDING
        
        # FASB uses RAG - skip intent detection entirely, go straight to processing
        is_fasb = data_source_type and data_source_type.value.lower() == "fasb" if hasattr(data_source_type, 'value') else str(data_source_type).lower() == "fasb"
        if is_fasb:
            message_type = MessageType.DATA
            detected_intent = "data_query"
            intent_confidence = "high"
            skip_intent_detection = True  # Ensure we skip the intent router below
        
        if message_type is None and not skip_intent_detection:
            # Use smart intent router
            intent_result = self.intent_router.detect_intent(question, conversation_context)
            detected_intent = intent_result.intent.value
            intent_confidence = intent_result.confidence.value
            
            # Map intent to message type
            if intent_result.intent == MessageIntent.DATA_QUERY:
                message_type = MessageType.DATA
            elif intent_result.intent == MessageIntent.CONVERSATIONAL:
                message_type = MessageType.CONVERSATIONAL
            else:
                # Ambiguous or clarification needed
                message_type = MessageType.DATA  # Default, but will need clarification
                status = DataAnalystQuestionStatus.CLARIFICATION_NEEDED
                clarification_prompt = intent_result.clarification_prompt or intent_result.reasoning
            
            # Use clarified question if available
            if intent_result.clarified_question:
                clarified_question = intent_result.clarified_question
            
            # If clarification needed, set status
            if intent_result.clarification_needed and not clarified_question:
                status = DataAnalystQuestionStatus.CLARIFICATION_NEEDED
                clarification_prompt = intent_result.clarification_prompt or self.intent_router.confirm_intent(
                    question,
                    intent_result.intent,
                    intent_result.suggested_sql_hint
                )
        elif message_type is None:
            # Fallback to keyword-based detection
            message_type = self._determine_message_type(question)
        
        # Auto-create conversation if not provided
        if conversation_id is None:
            conversation = self.conversation_service.create_conversation(
                user_id=user_id,
                customer_id=customer_id,
                data_source_type=data_source_type,
                conversation_type=ConversationType.USER,
                title=question[:100] if len(question) > 100 else question  # Use question as title
            )
            conversation_id = conversation.conversation_id
        
        # Get conversation to determine message order
        if not conversation:
            conversation = self.conversation_service.get_conversation(conversation_id, user_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found or access denied")
        
        # Determine message order (next in sequence)
        existing_messages = conversation.messages or []
        max_order = max([m.message_order or 0 for m in existing_messages], default=0)
        message_order = max_order + 1
        
        # Check conversation limits
        if message_order > self.settings.data_analyst_max_messages_per_conversation:
            raise ValueError(
                f"Conversation has reached maximum message limit "
                f"({self.settings.data_analyst_max_messages_per_conversation})"
            )
        
        message = DataAnalystMessage(
            question_id=question_id,  # Backward compatibility
            message_id=message_id,
            user_id=user_id,
            customer_id=customer_id,
            data_source_type=data_source_type,
            original_question=question,
            conversation_id=conversation_id,
            message_order=message_order,
            message_type=message_type.value,
            status=status if message_type == MessageType.DATA else None,
            detected_intent=detected_intent,
            intent_confidence=intent_confidence,
            clarification_prompt=clarification_prompt,
            clarified_question=clarified_question or question,  # Use clarified or original
            intent_confirmed=(status != DataAnalystQuestionStatus.CLARIFICATION_NEEDED)
        )
        
        self.db.add(message)
        
        # Update conversation last_activity_at
        conversation.last_activity_at = datetime.utcnow()
        
        logger.info(
            f"About to commit message",
            message_id=message.message_id,
            message_id_type=type(message.message_id).__name__
        )
        
        self.db.commit()
        self.db.refresh(message)
        
        logger.info(
            f"Message committed and refreshed",
            message_id=message.message_id,
            message_id_type=type(message.message_id).__name__
        )
        
        logger.info(
            "message_created",
            message_id=message_id,
            conversation_id=conversation_id,
            message_type=message_type.value,
            message_order=message_order,
            status=status.value if hasattr(status, 'value') else str(status),
            clarification_needed=(status == DataAnalystQuestionStatus.CLARIFICATION_NEEDED),
            user_id=user_id
        )
        
        return message
    
    def clarify_message(
        self,
        message_id: str,
        clarification_response: str,
        confirm_intent: bool = True
    ) -> DataAnalystMessage:
        """
        Handle user's clarification response and update message.
        
        Args:
            message_id: Message ID
            clarification_response: User's response to clarification prompt
            confirm_intent: Whether user confirmed intent (True) or provided corrections (False)
            
        Returns:
            Updated message
        """
        message = self.db.query(DataAnalystMessage).filter(
            DataAnalystMessage.message_id == message_id
        ).first()
        
        if not message:
            raise ValueError(f"Message {message_id} not found")
        
        if message.status != DataAnalystQuestionStatus.CLARIFICATION_NEEDED:
            raise ValueError(f"Message {message_id} does not need clarification")
        
        # Clarify question using intent router
        clarified_question = self.intent_router.clarify_question(
            message.original_question,
            message.clarification_prompt or "",
            clarification_response
        )
        
        # Update message
        message.clarification_response = clarification_response
        message.clarified_question = clarified_question
        message.intent_confirmed = confirm_intent
        
        # Re-detect intent with clarified question if user provided corrections
        if not confirm_intent:
            conversation = None
            if message.conversation_id:
                conversation = self.conversation_service.get_conversation(
                    message.conversation_id,
                    message.user_id
                )
            
            conversation_context = None
            if conversation:
                conversation_context = self.context_manager.get_conversation_context(
                    conversation,
                    exclude_message_id=message.message_id
                )
            
            intent_result = self.intent_router.detect_intent(clarified_question, conversation_context)
            message.detected_intent = intent_result.intent.value
            message.intent_confidence = intent_result.confidence.value
            
            # Update message type if changed
            if intent_result.intent == MessageIntent.DATA_QUERY:
                message.message_type = MessageType.DATA.value
            elif intent_result.intent == MessageIntent.CONVERSATIONAL:
                message.message_type = MessageType.CONVERSATIONAL.value
        
        # Update status to ready for processing
        if message.message_type == MessageType.DATA.value:
            message.status = DataAnalystQuestionStatus.INTENT_CONFIRMED
        else:
            message.status = None  # Conversational messages don't have processing status
        
        self.db.commit()
        self.db.refresh(message)
        
        logger.info(
            "message_clarified",
            message_id=message_id,
            clarified_question=clarified_question,
            intent_confirmed=confirm_intent
        )
        
        return message
    
    def process_message(
        self,
        message_id: str,
        use_conversation_context: bool = True
    ) -> Dict[str, Any]:
        """
        Process message (data or conversational).
        
        For DATA messages:
        - Use conversation context if available (last 10 messages)
        - Generate SQL with Vanna (enhanced question with context)
        - Execute and return results
        
        For CONVERSATIONAL messages:
        - Use conversation context
        - Generate LLM response (no SQL)
        - Return conversational response
        
        Args:
            message_id: Message ID to process
            use_conversation_context: Whether to use conversation context
            
        Returns:
            Dict with result_data/result_metadata (DATA) or conversational_response (CONVERSATIONAL)
        """
        message = self.db.query(DataAnalystMessage).filter(
            DataAnalystMessage.message_id == message_id
        ).first()
        
        if not message:
            raise ValueError(f"Message {message_id} not found")
        
        # Check if clarification is needed
        if message.status == DataAnalystQuestionStatus.CLARIFICATION_NEEDED:
            raise ValueError(
                f"Message {message_id} requires clarification. "
                f"Use clarify_message() first or provide clarification_response."
            )
        
        # Use clarified question if available, otherwise original
        question_to_process = message.clarified_question or message.original_question
        
        # Get conversation if available
        conversation = None
        if message.conversation_id and use_conversation_context:
            conversation = self.conversation_service.get_conversation(
                message.conversation_id,
                message.user_id
            )
        
        if message.message_type == MessageType.DATA.value:
            return self._process_data_message(message, conversation, question_to_process)
        elif message.message_type == MessageType.CONVERSATIONAL.value:
            return self._process_conversational_message(message, conversation, question_to_process)
        else:
            raise ValueError(f"Unknown message type: {message.message_type}")
    
    def _process_data_message(
        self,
        message: DataAnalystMessage,
        conversation: Optional[Any] = None,
        question_to_process: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a DATA message (SQL generation or RAG depending on domain)."""
        # Update status
        if message.status == DataAnalystQuestionStatus.INTENT_CONFIRMED:
            message.status = DataAnalystQuestionStatus.PROCESSING
        else:
            message.status = DataAnalystQuestionStatus.PROCESSING
        self.db.commit()
        
        try:
            # Use provided question or fall back to message's clarified/original question
            question = question_to_process or message.clarified_question or message.original_question
            
            # Build enhanced question with conversation context
            conversation_context = None
            if conversation:
                enhanced_question = self.context_manager.build_enhanced_question(
                    conversation=conversation,
                    current_question=question,
                    exclude_message_id=message.message_id
                )
                conversation_context = self.context_manager.get_conversation_context(
                    conversation,
                    exclude_message_id=message.message_id
                )
            else:
                enhanced_question = question
            
            # Route based on data source type
            if message.data_source_type == DataSourceType.FASB:
                # FASB uses RAG instead of SQL
                return self._process_fasb_message(message, conversation, question, conversation_context)
            
            # Default: SQL-based processing (Insurance, etc.)
            # Get Vanna service
            vanna_service = self._get_vanna_service(message.data_source_type)
            
            # Generate SQL
            generated_sql = vanna_service.generate_sql(enhanced_question)
            message.generated_sql = generated_sql
            self.db.commit()
            
            # Execute SQL
            results = vanna_service.run_sql(generated_sql)
            
            # Format results
            result_data = self._format_results(results)
            result_metadata = self._generate_metadata(
                message.original_question,
                generated_sql,
                results
            )
            
            # Update message with results
            message.result_data = result_data
            message.result_metadata = result_metadata
            message.status = DataAnalystQuestionStatus.COMPLETED
            message.completed_at = datetime.utcnow()
            
            # Update conversation last_activity_at
            if conversation:
                conversation.last_activity_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(
                "data_message_processed",
                message_id=message.message_id,
                conversation_id=message.conversation_id,
                result_count=len(results) if results else 0
            )
            
            return {
                "result_data": result_data,
                "result_metadata": result_metadata
            }
            
        except Exception as e:
            message.status = DataAnalystQuestionStatus.FAILED
            message.sql_error = str(e)
            self.db.commit()
            
            logger.error(
                "data_message_processing_failed",
                message_id=message.message_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    def _process_fasb_message(
        self,
        message: DataAnalystMessage,
        conversation: Optional[Any],
        question: str,
        conversation_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a FASB RAG message."""
        try:
            # Get FASB service
            fasb_service = self._get_fasb_service()
            
            # Process using RAG - pass customer_id for prompt management
            result = fasb_service.process_message(
                question, 
                conversation_context,
                customer_id=message.customer_id
            )
            
            # Update message with results
            message.result_data = result["result_data"]
            message.result_metadata = result["result_metadata"]
            message.status = DataAnalystQuestionStatus.COMPLETED
            message.completed_at = datetime.utcnow()
            # FASB doesn't generate SQL
            message.generated_sql = None
            
            # Update conversation last_activity_at
            if conversation:
                conversation.last_activity_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(
                "fasb_message_processed",
                message_id=message.message_id,
                conversation_id=message.conversation_id,
                sources_count=len(result["result_metadata"].get("sources", []))
            )
            
            return result
            
        except Exception as e:
            message.status = DataAnalystQuestionStatus.FAILED
            message.sql_error = f"FASB RAG failed: {str(e)}"
            self.db.commit()
            
            logger.error(
                "fasb_message_processing_failed",
                message_id=message.message_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    def _process_conversational_message(
        self,
        message: DataAnalystMessage,
        conversation: Optional[Any] = None,
        question_to_process: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a CONVERSATIONAL message (LLM response, no SQL)."""
        if not self._can_use_llm():
            raise ValueError("LLM not available for conversational messages")
        
        try:
            # Use provided question or fall back to message's clarified/original question
            question = question_to_process or message.clarified_question or message.original_question
            
            # Build enhanced question with conversation context
            if conversation:
                enhanced_question = self.context_manager.build_enhanced_question(
                    conversation=conversation,
                    current_question=question,
                    exclude_message_id=message.message_id
                )
            else:
                enhanced_question = question
            
            # Generate LLM response
            response = litellm.completion(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful data analyst assistant. Answer questions about processes, SOPs, and provide general guidance."
                    },
                    {
                        "role": "user",
                        "content": enhanced_question
                    }
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            conversational_response = response.choices[0].message.content
            
            # Update message
            message.conversational_response = conversational_response
            message.completed_at = datetime.utcnow()
            
            # Update conversation last_activity_at
            if conversation:
                conversation.last_activity_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(
                "conversational_message_processed",
                message_id=message.message_id,
                conversation_id=message.conversation_id
            )
            
            return {
                "conversational_response": conversational_response
            }
            
        except Exception as e:
            logger.error(
                "conversational_message_processing_failed",
                message_id=message.message_id,
                error=str(e),
                exc_info=True
            )
            raise
    
    def _determine_message_type(self, question: str) -> MessageType:
        """
        Determine if question is DATA or CONVERSATIONAL.
        
        Heuristics:
        - Contains data-related keywords (premium, claim, loss ratio, etc.) → DATA
        - Asks about processes, SOPs, documentation → CONVERSATIONAL
        - Can be enhanced with LLM classification later
        
        Args:
            question: The question text
            
        Returns:
            MessageType (DATA or CONVERSATIONAL)
        """
        question_lower = question.lower()
        
        # Data-related keywords
        data_keywords = [
            "premium", "claim", "loss", "ratio", "policy", "customer",
            "revenue", "cost", "amount", "total", "average", "sum",
            "count", "how many", "what is the", "show me", "list",
            "breakdown", "by state", "by month", "by year", "group by"
        ]
        
        # Conversational keywords
        conversational_keywords = [
            "what is", "how do", "explain", "sop", "process", "procedure",
            "documentation", "guide", "help", "tell me about", "describe"
        ]
        
        # Check for data keywords
        data_score = sum(1 for keyword in data_keywords if keyword in question_lower)
        
        # Check for conversational keywords
        conversational_score = sum(1 for keyword in conversational_keywords if keyword in question_lower)
        
        # Default to DATA if it has data keywords or asks for numbers/data
        if data_score > 0 or any(word in question_lower for word in ["how many", "what is the", "show me"]):
            return MessageType.DATA
        
        # Default to CONVERSATIONAL if it has conversational keywords
        if conversational_score > 0:
            return MessageType.CONVERSATIONAL
        
        # Default to DATA (most questions are data-related)
        return MessageType.DATA
    
    def _format_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Format SQL results for frontend display.
        
        Converts Decimal values to float for JSON serialization.
        Handles other non-JSON-serializable types (datetime, etc.).
        """
        if not results:
            return {"rows": [], "columns": [], "row_count": 0}
        
        # Extract column names from first row
        columns = list(results[0].keys()) if results else []
        
        def serialize_value(value: Any) -> Any:
            """Convert non-JSON-serializable values to serializable types."""
            if isinstance(value, Decimal):
                return float(value)
            elif isinstance(value, (datetime, date)):
                return value.isoformat()
            elif isinstance(value, bytes):
                return value.decode('utf-8', errors='replace')
            elif value is None:
                return None
            else:
                # Try to return as-is (int, float, str, bool, list, dict)
                return value
        
        # Convert to list of lists for table display, serializing values
        rows = [[serialize_value(row[col]) for col in columns] for row in results]
        
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows)
        }
    
    def _generate_metadata(
        self,
        question: str,
        sql: str,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate metadata for results: charts, insights, summaries.
        
        Uses LLM to generate rich insights from the data.
        """
        insights_data = self._generate_insights(question, results)
        
        metadata = {
            "sql": sql,
            "chart_suggestions": self._suggest_charts(results),
            "insights": insights_data,  # Now a dict with structured insights
            "summary": insights_data.get("executive_summary", self._generate_summary(results)),
            "statistics": insights_data.get("statistical_summary", {}),
            "key_findings": insights_data.get("key_findings", []),
            "anomalies": insights_data.get("anomalies", []),
            "recommendations": insights_data.get("recommendations", [])
        }
        
        return metadata
    
    def _suggest_charts(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Suggest appropriate chart types based on data structure."""
        if not results:
            return []
        
        suggestions = []
        columns = list(results[0].keys()) if results else []
        
        # Simple heuristics for chart suggestions
        # Could be enhanced with ML-based detection
        numeric_cols = [col for col in columns if self._is_numeric(results, col)]
        categorical_cols = [col for col in columns if not self._is_numeric(results, col)]
        
        if len(numeric_cols) >= 2:
            suggestions.append({
                "type": "line",
                "x": categorical_cols[0] if categorical_cols else None,
                "y": numeric_cols[:2]  # First two numeric columns
            })
        
        if len(categorical_cols) >= 1 and len(numeric_cols) >= 1:
            suggestions.append({
                "type": "bar",
                "x": categorical_cols[0],
                "y": numeric_cols[0]
            })
        
        # Pie chart for single categorical + single numeric
        if len(categorical_cols) == 1 and len(numeric_cols) == 1:
            suggestions.append({
                "type": "pie",
                "label": categorical_cols[0],
                "value": numeric_cols[0]
            })
        
        return suggestions
    
    def _is_numeric(self, results: List[Dict[str, Any]], column: str) -> bool:
        """Check if column contains numeric data."""
        if not results:
            return False
        
        # Sample first 10 rows to check
        sample_size = min(10, len(results))
        for row in results[:sample_size]:
            value = row.get(column)
            if value is None:
                continue
            if not isinstance(value, (int, float)):
                # Try to convert string numbers
                try:
                    float(str(value).replace(',', '').replace('$', ''))
                except (ValueError, AttributeError):
                    return False
        
        return True
    
    def _can_use_llm(self) -> bool:
        """Check if LLM is available for insights generation."""
        return bool(self.settings.openai_api_key)
    
    def _generate_insights(self, question: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate rich insights from results using LLM and statistical analysis.
        
        This method is critical for user experience - it generates the natural language
        response that Eliza provides. If insights cannot be generated, we raise an
        exception rather than returning fallback text.
        
        Raises:
            ValueError: If insights cannot be generated (no LLM API, invalid results, etc.)
        """
        if not results:
            # For empty results, we can provide a clear message
            return {
                "summary": "I didn't find any data matching your query. This could mean the time period had no transactions, or the filters didn't match any records.",
                "key_findings": [],
                "statistics": {},
                "chart_suggestions": [],
                "anomalies": [],
                "recommendations": [
                    "Try adjusting the time period or filters",
                    "Verify that data exists for the specified criteria"
                ]
            }
        
        # Generate statistical summary
        stats = self._calculate_statistics(results)
        
        # Generate LLM insights (this will retry internally and raise if it fails)
        llm_insights = self._generate_llm_insights(question, results, stats)
        
        # Combine LLM insights with our statistical calculations
        # Note: LLM provides "summary" field, we keep "statistics" for compatibility
        insights = {
            "summary": llm_insights.get("summary"),  # Primary natural language response
            "key_findings": llm_insights.get("key_findings", []),
            "statistics": llm_insights.get("statistics", {}),
            "chart_suggestions": llm_insights.get("chart_suggestions", []),
            "anomalies": llm_insights.get("anomalies", []),
            "recommendations": llm_insights.get("recommendations", [])
        }
        
        # Validate that we have the critical summary field
        if not insights.get("summary"):
            raise ValueError("Failed to generate natural language summary")
        
        logger.info(
            "insights_generated",
            question_length=len(question),
            result_count=len(results),
            summary_length=len(insights["summary"]),
            findings_count=len(insights["key_findings"])
        )
        
        return insights
    
    def _calculate_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistical summary for numeric columns."""
        if not results:
            return {}
        
        stats = {}
        columns = list(results[0].keys()) if results else []
        
        for col in columns:
            values = [row.get(col) for row in results if row.get(col) is not None]
            
            if not values:
                continue
            
            # Try to convert to numeric
            numeric_values = []
            for val in values:
                try:
                    if isinstance(val, (int, float, Decimal)):
                        numeric_values.append(float(val))
                    elif isinstance(val, str):
                        # Try to parse string numbers
                        cleaned = val.replace(',', '').replace('$', '').replace('%', '').strip()
                        numeric_values.append(float(cleaned))
                except (ValueError, AttributeError):
                    pass
            
            if numeric_values:
                stats[col] = {
                    "type": "numeric",
                    "count": len(numeric_values),
                    "min": min(numeric_values),
                    "max": max(numeric_values),
                    "mean": statistics.mean(numeric_values),
                    "median": statistics.median(numeric_values),
                    "sum": sum(numeric_values)
                }
                if len(numeric_values) > 1:
                    stats[col]["std_dev"] = statistics.stdev(numeric_values)
            else:
                # Categorical statistics
                unique_values = len(set(str(v) for v in values))
                stats[col] = {
                    "type": "categorical",
                    "count": len(values),
                    "unique_count": unique_values,
                    "most_common": self._get_most_common(values, 5)
                }
        
        return stats
    
    def _get_most_common(self, values: List[Any], n: int = 5) -> List[Dict[str, Any]]:
        """Get most common values."""
        from collections import Counter
        counter = Counter(str(v) for v in values)
        return [{"value": val, "count": count} for val, count in counter.most_common(n)]
    
    def _generate_llm_insights(self, question: str, results: List[Dict[str, Any]], stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate high-quality insights using LLM with retry logic.
        
        This is a critical path - insights must be generated successfully.
        We retry up to 3 times if the LLM fails to produce valid JSON.
        """
        if not self._can_use_llm():
            raise ValueError("LLM API key not configured - cannot generate insights")
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Format sample data for LLM (limit to first 10 rows to avoid token limits)
                sample_data = results[:10]
                data_preview = json.dumps(sample_data, default=str, indent=2)
                
                # Format statistics
                stats_summary = json.dumps(stats, default=str, indent=2)
                
                # Enhanced prompt for conversational, insurance-focused insights
                prompt = f"""You are Eliza, an AI data analyst assistant specializing in insurance analytics.
Analyze the following insurance data query result and provide a natural, conversational response with structured insights.

**User's Question:** {question}

**Query Results:** {len(results)} row(s) returned

**Data Sample (first 10 rows):**
```json
{data_preview}
```

**Statistical Summary:**
```json
{stats_summary}
```

**Your Task:**
Provide a comprehensive yet conversational analysis in JSON format. Write as if you're speaking directly to the user.

**Required JSON Structure:**
{{
  "summary": "A natural, conversational 2-3 sentence response directly answering the user's question. Speak in first person as Eliza. Example: 'Based on the data, I found that the total premium collected last month was $2.5M across 1,247 policies. This represents a 15% increase compared to the previous month, driven primarily by auto insurance renewals.'",
  
  "key_findings": [
    "Specific insight with actual numbers from the data (e.g., 'Auto insurance accounts for 65% of total premium with $1.6M')",
    "Trend or pattern observed (e.g., 'California leads with $850K, followed by Texas at $520K')",
    "Notable comparison or relationship (e.g., 'Commercial policies have 2.3x higher average premium than personal lines')"
  ],
  
  "statistics": {{
    "Primary metric name": {{
      "value": <actual number from data>,
      "formatted": "Human-readable format (e.g., '$2.5M', '1,247 policies', '15.3%')",
      "label": "Clear label for display"
    }},
    "Secondary metric": {{
      "value": <number>,
      "formatted": "formatted value",
      "label": "label"
    }}
  }},
  
  "chart_suggestions": [
    {{
      "chart_type": "bar|line|pie|area|scatter",
      "title": "Descriptive chart title",
      "x_axis": "column_name_from_data",
      "y_axis": "column_name_from_data",
      "description": "Why this visualization is useful"
    }}
  ],
  
  "anomalies": [
    "Any unusual patterns, outliers, or unexpected findings (leave empty array if none)"
  ],
  
  "recommendations": [
    "Actionable recommendation for stakeholders based on the insights",
    "Follow-up analysis suggestion if relevant"
  ]
}}

**Guidelines:**
1. **Summary (CRITICAL)**: Write naturally as Eliza speaking to the user. Use "I" and "you". Directly answer their question with specific numbers. Example: "I found 3 high-risk customers..." NOT "The analysis shows..."

2. **Key Findings**: Include 3-5 specific, data-driven insights. Use actual numbers from the results. Focus on insurance-relevant metrics (premiums, claims, loss ratios, customer counts, policy types, etc.).

3. **Statistics**: Extract 2-4 key metrics that matter most for this query. Format them nicely (use $, %, K/M/B notation).

4. **Chart Suggestions**: Recommend 1-2 visualizations that would best represent this data. **IMPORTANT: Do NOT suggest any charts if there is only 1 row of data - a single data point cannot be meaningfully visualized. Return an empty array [] for chart_suggestions in this case.** Only suggest charts when there are multiple rows/data points to compare or show trends.

5. **Anomalies**: Only include if there are genuinely unusual patterns. Don't force it.

6. **Recommendations**: Provide 1-2 actionable next steps or insights for decision-making.

**Important:**
- Use actual column names and values from the data
- Be specific with numbers (don't say "many" - say "1,247")
- Speak naturally and conversationally
- Focus on insurance domain relevance (premiums, claims, loss ratios, risk, customer value)
- Return ONLY valid JSON, no markdown code blocks, no explanatory text

**CRITICAL:** The "summary" field is your natural language response to the user. Make it conversational, specific, and helpful."""

                # Use litellm to generate insights
                response = litellm.completion(
                    model=self.settings.default_llm_model,  # Use configured model
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are Eliza, an expert insurance data analyst. You provide clear, conversational insights in perfect JSON format. You always include a natural 'summary' field that directly answers the user's question with specific numbers and context."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2000,  # Increased for comprehensive insights
                    response_format={"type": "json_object"}  # Force JSON response
                )
                
                # Extract response text
                response_text = response.choices[0].message.content if response.choices else ""
                
                if not response_text:
                    if attempt < max_retries - 1:
                        logger.warning(f"Empty LLM response, retrying (attempt {attempt + 1}/{max_retries})")
                        continue
                    raise ValueError("LLM returned empty response after retries")
            
                # Parse JSON response
                response_text = response_text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                response_text = response_text.strip()
                
                # Try to parse JSON
                try:
                    insights = json.loads(response_text)
                    
                    # Validate required fields
                    if "summary" not in insights:
                        if attempt < max_retries - 1:
                            logger.warning(f"LLM response missing 'summary' field, retrying (attempt {attempt + 1}/{max_retries})")
                            continue
                        raise ValueError("LLM response missing required 'summary' field")
                    
                    logger.info(
                        "insights_generated_successfully",
                        summary_length=len(insights.get("summary", "")),
                        has_key_findings=bool(insights.get("key_findings")),
                        has_chart_suggestions=bool(insights.get("chart_suggestions"))
                    )
                    
                    return insights
                    
                except json.JSONDecodeError as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"Failed to parse LLM JSON, retrying (attempt {attempt + 1}/{max_retries}): {e}")
                        continue
                    raise ValueError(f"LLM returned invalid JSON after {max_retries} attempts: {e}")
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"LLM insights generation failed, retrying (attempt {attempt + 1}/{max_retries}): {e}")
                    continue
                # Final attempt failed
                logger.error(f"Failed to generate LLM insights after {max_retries} attempts: {e}", exc_info=True)
                raise ValueError(f"Insights generation failed: {str(e)}")
    
    def _generate_basic_summary(self, results: List[Dict[str, Any]]) -> str:
        """Generate basic summary without LLM."""
        row_count = len(results)
        col_count = len(results[0].keys()) if results else 0
        return f"Query returned {row_count} row{'s' if row_count != 1 else ''} with {col_count} column{'s' if col_count != 1 else ''}."
    
    def _generate_basic_findings(self, results: List[Dict[str, Any]], stats: Dict[str, Any]) -> List[str]:
        """Generate basic findings without LLM."""
        findings = []
        
        row_count = len(results)
        findings.append(f"Query returned {row_count} result{'s' if row_count != 1 else ''}.")
        
        # Add findings from statistics
        for col, stat in stats.items():
            if stat.get("type") == "numeric":
                mean_val = stat.get("mean", 0)
                max_val = stat.get("max", 0)
                min_val = stat.get("min", 0)
                findings.append(f"{col}: Average {mean_val:.2f}, Range {min_val:.2f} - {max_val:.2f}")
        
        return findings[:5]  # Limit to 5 findings
    
    def _detect_anomalies(self, results: List[Dict[str, Any]], stats: Dict[str, Any]) -> List[str]:
        """Detect anomalies in the data."""
        anomalies = []
        
        for col, stat in stats.items():
            if stat.get("type") == "numeric" and stat.get("std_dev"):
                mean = stat.get("mean", 0)
                std_dev = stat.get("std_dev", 0)
                
                # Check for outliers (more than 2 standard deviations)
                for row in results:
                    val = row.get(col)
                    if val is not None:
                        try:
                            num_val = float(str(val).replace(',', '').replace('$', ''))
                            if abs(num_val - mean) > 2 * std_dev:
                                anomalies.append(f"{col} value {num_val:.2f} is significantly different from mean {mean:.2f}")
                                break  # Only report once per column
                        except (ValueError, TypeError):
                            pass
        
        return anomalies[:3]  # Limit to 3 anomalies
    
    def _generate_summary(self, results: List[Dict[str, Any]]) -> str:
        """Generate summary statistics."""
        if not results:
            return "No data returned."
        
        row_count = len(results)
        col_count = len(results[0].keys()) if results else 0
        
        return f"Query returned {row_count} row{'s' if row_count != 1 else ''} with {col_count} column{'s' if col_count != 1 else ''}."
    
    def _format_data_for_llm(self, results: List[Dict[str, Any]]) -> str:
        """Format data summary for LLM consumption."""
        if not results:
            return "No data available."
        
        # Sample first 5 rows
        sample = results[:5]
        return json.dumps(sample, default=str, indent=2)
    
    def get_question(self, question_id: str) -> Optional[DataAnalystQuestion]:
        """Get question by ID."""
        return self.db.query(DataAnalystQuestion).filter(
            DataAnalystQuestion.question_id == question_id
        ).first()
    
    def list_questions(
        self,
        user_id: Optional[int] = None,
        customer_id: Optional[str] = None,
        data_source_type: Optional[DataSourceType] = None,
        conversation_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> tuple[List[DataAnalystQuestion], int]:
        """List questions with filters."""
        query = self.db.query(DataAnalystQuestion)
        
        if user_id:
            query = query.filter(DataAnalystQuestion.user_id == user_id)
        
        if customer_id:
            query = query.filter(DataAnalystQuestion.customer_id == customer_id)
        
        if data_source_type:
            query = query.filter(DataAnalystQuestion.data_source_type == data_source_type)
        
        if conversation_id:
            query = query.filter(DataAnalystQuestion.conversation_id == conversation_id)
        
        total = query.count()
        questions = query.order_by(
            DataAnalystQuestion.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        return questions, total

