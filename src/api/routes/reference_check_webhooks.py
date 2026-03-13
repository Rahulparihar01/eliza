"""
Reference Check Webhook Handlers

Twilio webhook endpoints for:
- Voice call TwiML generation
- Call status updates
- Recording completion
- Inbound call handling
- Media streaming (WebSocket)
"""

from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from src.models import get_db
from src.core.logging import get_logger, LogCategory
from src.core.config import get_settings
from src.services.reference_check import TwilioService, VoiceAgentService, SynthesisService

logger = get_logger(__name__, LogCategory.API)
settings = get_settings()

router = APIRouter(prefix="/reference-checks/webhooks", tags=["Reference Check Webhooks"])


# ============================================================================
# Voice Call Webhooks
# ============================================================================

@router.post("/voice/{scheduled_call_id}")
async def voice_webhook(
    scheduled_call_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle outbound call connection.
    Returns TwiML to connect to media stream for OpenAI Realtime.
    """
    form_data = await request.form()
    call_status = form_data.get("CallStatus")
    answered_by = form_data.get("AnsweredBy")
    
    logger.info(
        "Voice webhook received",
        extra={
            "scheduled_call_id": scheduled_call_id,
            "call_status": call_status,
            "answered_by": answered_by
        }
    )
    
    twilio_service = TwilioService(db)
    voice_agent_service = VoiceAgentService(db)
    
    # Check if voicemail
    if answered_by == "machine_end_beep" or answered_by == "machine_end_silence":
        # Get reference info for voicemail message
        from src.models.reference_check import ReferenceScheduledCall
        scheduled_call = db.query(ReferenceScheduledCall).filter(
            ReferenceScheduledCall.id == scheduled_call_id
        ).first()
        
        if scheduled_call:
            reference = scheduled_call.reference
            request_obj = reference.request
            
            twiml = twilio_service.generate_voicemail_twiml(
                reference_name=reference.full_name,
                company_name="the company",  # TODO: Get from customer
                candidate_name=request_obj.candidate_name,
                callback_number=settings.twilio_phone_number or ""
            )
            
            return PlainTextResponse(content=twiml, media_type="application/xml")
    
    # Human answered - connect to media stream
    websocket_url = f"wss://{request.headers.get('host')}/api/v1/reference-checks/webhooks/media-stream/{scheduled_call_id}"
    
    twiml = twilio_service.generate_voice_twiml(
        scheduled_call_id=scheduled_call_id,
        websocket_url=websocket_url
    )
    
    return PlainTextResponse(content=twiml, media_type="application/xml")


@router.post("/status/{scheduled_call_id}")
async def status_webhook(
    scheduled_call_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle call status updates from Twilio.
    """
    form_data = await request.form()
    
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    call_duration = form_data.get("CallDuration")
    answered_by = form_data.get("AnsweredBy")
    
    logger.info(
        "Status webhook received",
        extra={
            "scheduled_call_id": scheduled_call_id,
            "call_sid": call_sid,
            "call_status": call_status,
            "call_duration": call_duration,
            "answered_by": answered_by
        }
    )
    
    twilio_service = TwilioService(db)
    
    import asyncio
    await twilio_service.update_call_status(
        call_sid=call_sid,
        status=call_status,
        duration=int(call_duration) if call_duration else None,
        answered_by=answered_by
    )
    
    return Response(status_code=200)


@router.post("/recording/{scheduled_call_id}")
async def recording_webhook(
    scheduled_call_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle recording completion from Twilio.
    """
    form_data = await request.form()
    
    call_sid = form_data.get("CallSid")
    recording_url = form_data.get("RecordingUrl")
    recording_sid = form_data.get("RecordingSid")
    recording_duration = form_data.get("RecordingDuration")
    
    logger.info(
        "Recording webhook received",
        extra={
            "scheduled_call_id": scheduled_call_id,
            "call_sid": call_sid,
            "recording_sid": recording_sid,
            "recording_duration": recording_duration
        }
    )
    
    twilio_service = TwilioService(db)
    
    # Update call with recording info
    call = await twilio_service.update_recording(
        call_sid=call_sid,
        recording_url=recording_url,
        recording_sid=recording_sid,
        recording_duration=int(recording_duration) if recording_duration else 0
    )
    
    # Trigger word-level mapping task
    if call and recording_url:
        from src.tasks.reference_check_tasks import create_word_level_mapping_task
        create_word_level_mapping_task.delay(call.id, recording_url)
    
    return Response(status_code=200)


@router.post("/inbound")
async def inbound_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handle inbound calls (callbacks from references).
    """
    form_data = await request.form()
    
    from_number = form_data.get("From")
    to_number = form_data.get("To")
    call_sid = form_data.get("CallSid")
    
    logger.info(
        "Inbound call received",
        extra={
            "from": from_number,
            "to": to_number,
            "call_sid": call_sid
        }
    )
    
    twilio_service = TwilioService(db)
    
    # Try to match to a pending reference
    result = await twilio_service.handle_inbound_call(from_number)
    
    if result.get("found"):
        # Resume reference check
        scheduled_call_id = result["scheduled_call_id"]
        websocket_url = f"wss://{request.headers.get('host')}/api/v1/reference-checks/webhooks/media-stream/{scheduled_call_id}"
        
        twiml = twilio_service.generate_voice_twiml(
            scheduled_call_id=scheduled_call_id,
            websocket_url=websocket_url
        )
        
        return PlainTextResponse(content=twiml, media_type="application/xml")
    else:
        # Unknown caller - play message and hang up
        from twilio.twiml.voice_response import VoiceResponse
        
        response = VoiceResponse()
        response.say(
            "Thank you for calling. We don't have a pending reference check for this number. "
            "If you received a voicemail from us, please ensure you're calling from the same number. "
            "Goodbye.",
            voice='Polly.Joanna'
        )
        response.hangup()
        
        return PlainTextResponse(content=str(response), media_type="application/xml")


# ============================================================================
# Media Stream WebSocket
# ============================================================================

@router.websocket("/media-stream/{scheduled_call_id}")
async def media_stream_websocket(
    websocket: WebSocket,
    scheduled_call_id: int,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for Twilio media streaming.
    Bridges Twilio audio to OpenAI Realtime API.
    """
    await websocket.accept()
    
    logger.info(f"Media stream connected for scheduled_call {scheduled_call_id}")
    
    voice_agent_service = VoiceAgentService(db)
    synthesis_service = SynthesisService(db)
    
    session_data = None
    
    try:
        # Create voice agent session
        session_data = await voice_agent_service.create_session(
            scheduled_call_id=scheduled_call_id,
            is_test=False
        )
        session_id = session_data["session_id"]
        
        # Audio buffers
        twilio_audio_buffer = []
        openai_audio_buffer = []
        
        async def audio_input_callback():
            """Generator that yields audio from Twilio."""
            while True:
                if twilio_audio_buffer:
                    yield twilio_audio_buffer.pop(0)
                else:
                    import asyncio
                    await asyncio.sleep(0.01)
        
        async def audio_output_callback(audio_data):
            """Callback to send audio to Twilio."""
            import json
            await websocket.send_json({
                "event": "media",
                "media": {
                    "payload": audio_data
                }
            })
        
        # Start OpenAI Realtime connection in background
        import asyncio
        realtime_task = asyncio.create_task(
            voice_agent_service.connect_realtime(
                session_id=session_id,
                audio_input_callback=audio_input_callback,
                audio_output_callback=audio_output_callback
            )
        )
        
        # Handle messages from Twilio
        while True:
            try:
                message = await websocket.receive_json()
                event = message.get("event")
                
                if event == "media":
                    # Audio from caller
                    audio_data = message.get("media", {}).get("payload")
                    if audio_data:
                        twilio_audio_buffer.append(audio_data)
                
                elif event == "start":
                    # Call started
                    stream_sid = message.get("start", {}).get("streamSid")
                    logger.info(f"Media stream started: {stream_sid}")
                
                elif event == "stop":
                    # Call ended
                    logger.info("Media stream stopped")
                    break
                    
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected")
                break
        
        # Cancel realtime task
        realtime_task.cancel()
        
        # End session and get results
        if session_id:
            results = await voice_agent_service.end_session(session_id)
            
            # Process completed call
            if results.get("conversation_history"):
                from src.models.reference_check import ReferenceScheduledCall, ReferenceCall
                
                scheduled_call = db.query(ReferenceScheduledCall).filter(
                    ReferenceScheduledCall.id == scheduled_call_id
                ).first()
                
                if scheduled_call:
                    # Find the call record
                    call = db.query(ReferenceCall).filter(
                        ReferenceCall.scheduled_call_id == scheduled_call_id
                    ).order_by(ReferenceCall.created_at.desc()).first()
                    
                    if call:
                        # Trigger processing task
                        from src.tasks.reference_check_tasks import process_completed_call_task
                        process_completed_call_task.delay(
                            call.id,
                            results["conversation_history"]
                        )
        
    except Exception as e:
        logger.error(f"Error in media stream: {e}")
    finally:
        logger.info(f"Media stream ended for scheduled_call {scheduled_call_id}")


# ============================================================================
# Playground WebSocket
# ============================================================================

@router.websocket("/playground/{session_id}")
async def playground_websocket(
    websocket: WebSocket,
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for voice playground testing.
    Allows testing the voice agent without making actual calls.
    """
    await websocket.accept()
    
    logger.info(f"Playground session connected: {session_id}")
    
    voice_agent_service = VoiceAgentService(db)
    
    try:
        # Verify session exists
        status = voice_agent_service.get_session_status(session_id)
        if not status:
            await websocket.send_json({"error": "Session not found"})
            await websocket.close()
            return
        
        # Audio buffers
        browser_audio_buffer = []
        
        async def audio_input_callback():
            """Generator that yields audio from browser."""
            while True:
                if browser_audio_buffer:
                    yield browser_audio_buffer.pop(0)
                else:
                    import asyncio
                    await asyncio.sleep(0.01)
        
        async def audio_output_callback(audio_data):
            """Callback to send audio to browser."""
            await websocket.send_json({
                "type": "audio",
                "audio": audio_data
            })
        
        # Start OpenAI Realtime connection in background
        import asyncio
        realtime_task = asyncio.create_task(
            voice_agent_service.connect_realtime(
                session_id=session_id,
                audio_input_callback=audio_input_callback,
                audio_output_callback=audio_output_callback
            )
        )
        
        # Handle messages from browser
        while True:
            try:
                message = await websocket.receive_json()
                msg_type = message.get("type")
                
                if msg_type == "audio":
                    # Audio from browser
                    audio_data = message.get("audio")
                    if audio_data:
                        browser_audio_buffer.append(audio_data)
                
                elif msg_type == "end":
                    # User ended session
                    logger.info(f"Playground session ended by user: {session_id}")
                    break
                    
            except WebSocketDisconnect:
                logger.info(f"Playground WebSocket disconnected: {session_id}")
                break
        
        # Cancel realtime task
        realtime_task.cancel()
        
        # End session and get results
        results = await voice_agent_service.end_session(session_id)
        
        # Send results to browser
        await websocket.send_json({
            "type": "session_ended",
            "results": results
        })
        
    except Exception as e:
        logger.error(f"Error in playground session: {e}")
        await websocket.send_json({"error": str(e)})
    finally:
        logger.info(f"Playground session closed: {session_id}")

