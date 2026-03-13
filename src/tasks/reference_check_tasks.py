"""
Reference Check Celery Tasks

Background tasks for:
- Sending SMS reminders
- Initiating scheduled calls
- Processing completed calls
- Syncing with Greenhouse
"""

from datetime import datetime, timezone, timedelta
from celery import shared_task

from src.core.logging import get_logger, LogCategory
from src.models import database

logger = get_logger(__name__, LogCategory.TASK)


@shared_task(name="reference_check.send_reminders")
def send_reminders_task():
    """
    Check for upcoming calls and send reminders.
    Should be run every minute via Celery Beat.
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        from src.models.reference_check import (
            ReferenceScheduledCall,
            ScheduledCallStatus
        )
        from src.services.reference_check import TwilioService
        
        now = datetime.now(timezone.utc)
        twilio_service = TwilioService(db)
        
        # Get scheduled calls that need reminders
        scheduled_calls = db.query(ReferenceScheduledCall).filter(
            ReferenceScheduledCall.status == ScheduledCallStatus.SCHEDULED,
            ReferenceScheduledCall.scheduled_at > now
        ).all()
        
        reminders_sent = 0
        
        for call in scheduled_calls:
            time_until_call = (call.scheduled_at - now).total_seconds()
            reference = call.reference
            request = reference.request
            
            # Check each reminder interval
            for interval_seconds in call.reminder_intervals:
                # Determine which reminder this is
                if interval_seconds >= 86400 and not call.reminder_24h_sent:
                    # 24-hour reminder
                    if time_until_call <= 86400 + 300:  # Within 5 min window
                        try:
                            import asyncio
                            asyncio.run(twilio_service.send_reminder(
                                to=reference.phone_number,
                                reference_name=reference.full_name,
                                candidate_name=request.candidate_name,
                                company_name="the company",  # TODO: Get from customer
                                scheduled_time=call.scheduled_at,
                                reminder_type='24h'
                            ))
                            call.reminder_24h_sent = True
                            reminders_sent += 1
                            logger.info(f"Sent 24h reminder for call {call.id}")
                        except Exception as e:
                            logger.error(f"Failed to send 24h reminder: {e}")
                
                elif interval_seconds >= 7200 and not call.reminder_2h_sent:
                    # 2-hour reminder
                    if time_until_call <= 7200 + 300:
                        try:
                            import asyncio
                            asyncio.run(twilio_service.send_reminder(
                                to=reference.phone_number,
                                reference_name=reference.full_name,
                                candidate_name=request.candidate_name,
                                company_name="the company",
                                scheduled_time=call.scheduled_at,
                                reminder_type='2h'
                            ))
                            call.reminder_2h_sent = True
                            reminders_sent += 1
                            logger.info(f"Sent 2h reminder for call {call.id}")
                        except Exception as e:
                            logger.error(f"Failed to send 2h reminder: {e}")
                
                elif interval_seconds >= 900 and not call.reminder_15m_sent:
                    # 15-minute reminder
                    if time_until_call <= 900 + 300:
                        try:
                            import asyncio
                            asyncio.run(twilio_service.send_reminder(
                                to=reference.phone_number,
                                reference_name=reference.full_name,
                                candidate_name=request.candidate_name,
                                company_name="the company",
                                scheduled_time=call.scheduled_at,
                                reminder_type='15m'
                            ))
                            call.reminder_15m_sent = True
                            reminders_sent += 1
                            logger.info(f"Sent 15m reminder for call {call.id}")
                        except Exception as e:
                            logger.error(f"Failed to send 15m reminder: {e}")
        
        db.commit()
        
        return {
            "checked": len(scheduled_calls),
            "reminders_sent": reminders_sent
        }
        
    except Exception as e:
        logger.error(f"Error in send_reminders_task: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@shared_task(name="reference_check.initiate_scheduled_calls")
def initiate_scheduled_calls_task():
    """
    Initiate calls that are due.
    Should be run every minute via Celery Beat.
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        from src.models.reference_check import (
            ReferenceScheduledCall,
            ScheduledCallStatus
        )
        from src.services.reference_check import TwilioService
        
        now = datetime.now(timezone.utc)
        
        # Get calls that should be initiated (within 1 minute of scheduled time)
        due_calls = db.query(ReferenceScheduledCall).filter(
            ReferenceScheduledCall.status == ScheduledCallStatus.SCHEDULED,
            ReferenceScheduledCall.scheduled_at <= now,
            ReferenceScheduledCall.scheduled_at >= now - timedelta(minutes=5)  # Don't initiate old calls
        ).all()
        
        twilio_service = TwilioService(db)
        calls_initiated = 0
        
        for scheduled_call in due_calls:
            try:
                import asyncio
                result = asyncio.run(twilio_service.initiate_call(
                    scheduled_call_id=scheduled_call.id,
                    from_number=scheduled_call.caller_id
                ))
                calls_initiated += 1
                logger.info(f"Initiated call for scheduled_call {scheduled_call.id}: {result}")
            except Exception as e:
                logger.error(f"Failed to initiate call {scheduled_call.id}: {e}")
                scheduled_call.status = ScheduledCallStatus.CANCELLED
        
        db.commit()
        
        return {
            "due_calls": len(due_calls),
            "initiated": calls_initiated
        }
        
    except Exception as e:
        logger.error(f"Error in initiate_scheduled_calls_task: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@shared_task(name="reference_check.process_completed_call")
def process_completed_call_task(call_id: int, conversation_history: list):
    """
    Process a completed call: create transcript, extract Q&A, generate summary.
    
    Args:
        call_id: ID of the completed call
        conversation_history: List of conversation turns
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        from src.models.reference_check import ReferenceCall, ReferenceTemplateQuestion
        from src.services.reference_check import SynthesisService
        
        call = db.query(ReferenceCall).filter(ReferenceCall.id == call_id).first()
        if not call:
            logger.error(f"Call {call_id} not found")
            return {"error": "Call not found"}
        
        # Get template questions
        template_questions = []
        if call.scheduled_call and call.scheduled_call.template:
            template_questions = call.scheduled_call.template.questions
        
        # Get candidate info
        candidate_name = "Unknown"
        position = "Unknown"
        if call.reference and call.reference.request:
            candidate_name = call.reference.request.candidate_name
            position = call.reference.request.job_title or "the position"
        
        synthesis_service = SynthesisService(db)
        
        import asyncio
        result = asyncio.run(synthesis_service.process_call_completion(
            call_id=call_id,
            conversation_history=conversation_history,
            candidate_name=candidate_name,
            position=position,
            template_questions=template_questions
        ))
        
        logger.info(f"Processed completed call {call_id}: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing completed call {call_id}: {e}")
        raise
    finally:
        db.close()


@shared_task(name="reference_check.create_word_level_mapping")
def create_word_level_mapping_task(call_id: int, recording_url: str):
    """
    Create word-level timestamp mapping for a call recording.
    
    Args:
        call_id: ID of the call
        recording_url: URL to the recording
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        from src.services.reference_check import SynthesisService
        
        synthesis_service = SynthesisService(db)
        
        import asyncio
        result = asyncio.run(synthesis_service.create_word_level_mapping(
            call_id=call_id,
            recording_url=recording_url
        ))
        
        logger.info(f"Created word-level mapping for call {call_id}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error creating word-level mapping for call {call_id}: {e}")
        raise
    finally:
        db.close()


@shared_task(name="reference_check.sync_to_greenhouse")
def sync_to_greenhouse_task(request_id: int):
    """
    Sync reference check results to Greenhouse.
    
    Args:
        request_id: ID of the reference check request
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        from src.models.reference_check import ReferenceCheckRequest, ReferenceCall
        
        request = db.query(ReferenceCheckRequest).filter(
            ReferenceCheckRequest.id == request_id
        ).first()
        
        if not request:
            logger.error(f"Request {request_id} not found")
            return {"error": "Request not found"}
        
        if not request.greenhouse_application_id:
            logger.info(f"Request {request_id} has no Greenhouse application ID")
            return {"skipped": "No Greenhouse integration"}
        
        # Get completed calls
        completed_calls = []
        for reference in request.references:
            for call in reference.calls:
                if call.is_complete and call.summary:
                    completed_calls.append(call)
        
        if not completed_calls:
            logger.info(f"No completed calls for request {request_id}")
            return {"skipped": "No completed calls"}
        
        # TODO: Implement Greenhouse Assessment API integration
        # This would:
        # 1. Update candidate test status
        # 2. Provide link to results
        # 3. Update custom fields with summary data
        
        logger.info(f"Would sync {len(completed_calls)} calls to Greenhouse for request {request_id}")
        
        return {
            "request_id": request_id,
            "greenhouse_application_id": request.greenhouse_application_id,
            "completed_calls": len(completed_calls)
        }
        
    except Exception as e:
        logger.error(f"Error syncing to Greenhouse for request {request_id}: {e}")
        raise
    finally:
        db.close()


@shared_task(name="reference_check.cleanup_expired_verifications")
def cleanup_expired_verifications_task():
    """
    Clean up expired verification tokens.
    Should be run daily via Celery Beat.
    """
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        from src.models.reference_check import ReferenceCheckRequest, ReferenceRequestStatus
        
        now = datetime.now(timezone.utc)
        
        # Find expired unverified requests
        expired = db.query(ReferenceCheckRequest).filter(
            ReferenceCheckRequest.verification_expires_at < now,
            ReferenceCheckRequest.verified_at.is_(None),
            ReferenceCheckRequest.status == ReferenceRequestStatus.PENDING
        ).all()
        
        # Clear verification tokens
        for request in expired:
            request.verification_token = None
            request.verification_expires_at = None
        
        db.commit()
        
        logger.info(f"Cleaned up {len(expired)} expired verifications")
        
        return {"cleaned": len(expired)}
        
    except Exception as e:
        logger.error(f"Error cleaning up expired verifications: {e}")
        db.rollback()
        raise
    finally:
        db.close()

