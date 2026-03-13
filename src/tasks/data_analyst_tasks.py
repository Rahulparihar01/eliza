"""
Data Analyst Celery Tasks

Processes data analyst messages using CrewAI flows.
"""
from celery import Task
from src.celery_app import celery_app
from src.models import database
from src.services.data_analyst_service import DataAnalystService
from src.services.conversation_service import ConversationService
from src.services.conversation_context_manager import ConversationContextManager
from src.flows.data_analyst_flow import DataAnalystFlowState, DataAnalystFlow
from src.core.logging import get_logger
from src.core.config import get_settings
from src.services.langfuse_service import get_langfuse_service

logger = get_logger(__name__, component="data.analyst.tasks")
settings = get_settings()


@celery_app.task(bind=True, name="data_analyst.process_message")
def process_data_analyst_message(self: Task, message_id: str):
    """
    Process a data analyst message using CrewAI flow.
    
    Args:
        message_id: Message ID to process
    """
    # Initialize database if needed
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    langfuse_service = get_langfuse_service()
    try:
        from src.models.data_analyst import DataAnalystMessage
        
        # Get message
        message = db.query(DataAnalystMessage).filter(
            DataAnalystMessage.message_id == message_id
        ).first()
        
        if not message:
            raise ValueError(f"Message {message_id} not found")
        
        # Emit telemetry event: flow received by Celery worker
        try:
            from src.models.data_analyst import DataAnalystTelemetryEventType
            service = DataAnalystService(db)
            service.add_telemetry_event(
                message_id=message_id,
                event_type=DataAnalystTelemetryEventType.FLOW_STARTED,  # Pass enum, not .value
                stage_name="Flow",
                user_message="Flow received by worker - initializing...",
                progress_percentage=1
            )
            logger.info(f"Emitted flow received event for message {message_id}")
        except Exception as e:
            logger.error(f"Failed to emit flow received event: {e}", exc_info=True)
        
        # Get conversation context if available
        conversation_context = None
        if message.conversation_id:
            conversation_service = ConversationService(db)
            conversation = conversation_service.get_conversation(
                message.conversation_id,
                message.user_id
            )
            
            if conversation:
                context_manager = ConversationContextManager(settings)
                conversation_context = context_manager.get_conversation_context(
                    conversation,
                    exclude_message_id=message_id
                )
        
        # Create flow state (include clarification/confirmation responses if available)
        # Explicitly convert enum to string value to ensure proper comparison in flow
        data_source_str = message.data_source_type.value if hasattr(message.data_source_type, 'value') else str(message.data_source_type)
        
        flow_state = DataAnalystFlowState(
            message_id=message_id,
            user_id=message.user_id,
            customer_id=message.customer_id,
            conversation_id=message.conversation_id,
            original_question=message.original_question,
            data_source_type=data_source_str,
            conversation_context=conversation_context,
            clarification_response=message.clarification_response,  # If user provided clarification
            confirmation_response=message.intent_confirmed and "yes" or None  # Simplified - will be improved
        )
        
        # Create flow with initial state (this ensures message_id is available from the start)
        flow = DataAnalystFlow(initial_state=flow_state)
        
        # Run flow
        with langfuse_service.span_scope(
            name="agentmesh.data_analyst.task.process_message",
            input_data={
                "message_id": message_id,
                "customer_id": message.customer_id,
                "user_id": message.user_id,
                "data_source_type": data_source_str,
            },
            metadata={
                "component": "agentmesh",
                "task": "data_analyst.process_message",
                "message_id": message_id,
                "conversation_id": message.conversation_id,
            },
        ) as span_info:
            result = flow.kickoff()
            observation = span_info.get("observation")
            if observation is not None:
                try:
                    observation.update(
                        output={
                            "status": flow.state.processing_result and "completed" or "partial",
                            "detected_intent": flow.state.detected_intent,
                            "clarification_needed": flow.state.clarification_needed,
                        }
                    )
                except Exception:
                    pass
        
        # Update message with flow state results
        # The router agent saves results via DatabaseMessageTool, but we also update here for safety
        
        # Update intent detection fields
        if flow.state.detected_intent:
            message.detected_intent = flow.state.detected_intent
        if flow.state.intent_confidence:
            message.intent_confidence = flow.state.intent_confidence
        if flow.state.clarification_prompt:
            message.clarification_prompt = flow.state.clarification_prompt
        if flow.state.clarified_question:
            message.clarified_question = flow.state.clarified_question
        if flow.state.confirmation_message:
            # Store confirmation message (could be used by frontend)
            pass  # Could add confirmation_message field to message model if needed
        
        # Update status based on flow state
        # Check for clarification_needed FIRST (it uses error as flow control)
        if flow.state.error == "CLARIFICATION_NEEDED" or flow.state.clarification_needed:
            # Clarification needed - this is NOT a failure, it's a normal flow state
            message.status = "clarification_needed"
            logger.info(
                "message_needs_clarification",
                message_id=message_id,
                clarification_prompt=flow.state.clarification_prompt
            )
        elif flow.state.error:
            # Real error (not clarification flow control)
            message.status = "failed"
            message.sql_error = flow.state.error
        elif flow.state.confirmation_message and not flow.state.confirmation_response:
            # Waiting for confirmation
            message.status = "intent_confirmed"
        elif flow.state.processing_result:
            # Processing completed
            message.status = "completed"
        else:
            # Default to completed
            message.status = "completed"
        
        db.commit()
        
        logger.info(
            "message_processed_via_flow",
            message_id=message_id,
            intent=flow.state.detected_intent,
            message_type=flow.state.message_type,
            status=message.status,
            clarification_needed=flow.state.clarification_needed
        )
        
    except Exception as e:
        logger.error(
            "message_processing_failed",
            message_id=message_id,
            error=str(e),
            exc_info=True
        )
        
        # Update message status to failed
        try:
            message = db.query(DataAnalystMessage).filter(
                DataAnalystMessage.message_id == message_id
            ).first()
            if message:
                message.status = "failed"
                message.sql_error = str(e)
                db.commit()
        except:
            pass
        
        raise
    finally:
        db.close()


# Backward compatibility: Keep old task name
@celery_app.task(bind=True, name="data_analyst.process_question")
def process_data_analyst_question(self: Task, question_id: str):
    """
    Process a data analyst question (backward compatibility).
    
    This task is kept for backward compatibility but now uses the message flow.
    """
    # Map question_id to message_id (they might be the same)
    # For now, treat question_id as message_id
    process_data_analyst_message.delay(question_id)
