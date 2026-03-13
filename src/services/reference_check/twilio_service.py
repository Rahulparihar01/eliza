"""
Twilio Service for Reference Check Voice Agent

Handles all Twilio Voice and SMS operations:
- Outbound call initiation
- Inbound call handling (callbacks)
- SMS reminders
- Caller ID management
- Call recording
"""

import base64
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from twilio.base.exceptions import TwilioRestException

from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory
from src.models.reference_check import (
    CustomerCallerId,
    CustomerCallSettings,
    ReferenceScheduledCall,
    ReferenceCall,
    CandidateReference,
    CallType,
    CallStatus,
    ScheduledCallStatus
)

logger = get_logger(__name__, LogCategory.INTEGRATION)


class TwilioService:
    """
    Service for Twilio Voice and SMS operations.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        
        # Initialize Twilio client
        # Prefer API key authentication over account auth token
        if self.settings.twilio_api_key_sid and self.settings.twilio_api_key_secret:
            self.client = Client(
                self.settings.twilio_api_key_sid,
                self.settings.twilio_api_key_secret,
                self.settings.twilio_account_sid
            )
            logger.info("Twilio client initialized with API key authentication")
        elif self.settings.twilio_account_sid and self.settings.twilio_auth_token:
            self.client = Client(
                self.settings.twilio_account_sid,
                self.settings.twilio_auth_token
            )
            logger.info("Twilio client initialized with account credentials")
        else:
            self.client = None
            logger.warning("Twilio client not initialized - missing credentials")
    
    def _ensure_client(self):
        """Ensure Twilio client is available."""
        if not self.client:
            raise ValueError("Twilio client not configured. Please set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN or TWILIO_API_KEY_SID and TWILIO_API_KEY_SECRET.")
    
    # =========================================================================
    # Caller ID Management
    # =========================================================================
    
    async def add_caller_id(
        self,
        customer_id: str,
        phone_number: str,
        display_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiate verification for a new caller ID.
        Twilio will call the number with a verification code.
        
        Returns:
            Dict with call_sid, phone_number, validation_code, status
        """
        self._ensure_client()
        
        try:
            validation_request = self.client.validation_requests.create(
                phone_number=phone_number,
                friendly_name=display_name or phone_number
            )
            
            # Store in database as pending verification
            caller_id = CustomerCallerId(
                customer_id=customer_id,
                twilio_phone_number=phone_number,
                display_name=display_name,
                is_verified=False,
                verification_sid=validation_request.call_sid
            )
            self.db.add(caller_id)
            self.db.commit()
            self.db.refresh(caller_id)
            
            logger.info(
                "Caller ID verification initiated",
                extra={
                    "customer_id": customer_id,
                    "phone_number": phone_number,
                    "call_sid": validation_request.call_sid
                }
            )
            
            return {
                "id": caller_id.id,
                "call_sid": validation_request.call_sid,
                "phone_number": validation_request.phone_number,
                "validation_code": validation_request.validation_code,
                "status": "pending"
            }
            
        except TwilioRestException as e:
            logger.error(f"Failed to initiate caller ID verification: {e}")
            raise
    
    async def verify_caller_id(
        self,
        customer_id: str,
        caller_id_id: int
    ) -> bool:
        """
        Check if a caller ID has been verified.
        Updates database record if verified.
        """
        self._ensure_client()
        
        caller_id = self.db.query(CustomerCallerId).filter(
            CustomerCallerId.id == caller_id_id,
            CustomerCallerId.customer_id == customer_id
        ).first()
        
        if not caller_id:
            raise ValueError(f"Caller ID {caller_id_id} not found")
        
        # Check Twilio for verification status
        try:
            outgoing_caller_ids = self.client.outgoing_caller_ids.list(
                phone_number=caller_id.twilio_phone_number
            )
            
            if outgoing_caller_ids:
                caller_id.is_verified = True
                self.db.commit()
                logger.info(f"Caller ID {caller_id.twilio_phone_number} verified")
                return True
            
            return False
            
        except TwilioRestException as e:
            logger.error(f"Failed to check caller ID verification: {e}")
            raise
    
    async def list_verified_caller_ids(self, customer_id: str) -> List[Dict[str, Any]]:
        """List all verified caller IDs for a customer."""
        caller_ids = self.db.query(CustomerCallerId).filter(
            CustomerCallerId.customer_id == customer_id,
            CustomerCallerId.is_verified == True
        ).all()
        
        return [
            {
                "id": cid.id,
                "phone_number": cid.twilio_phone_number,
                "display_name": cid.display_name,
                "is_default": cid.is_default,
                "created_at": cid.created_at.isoformat()
            }
            for cid in caller_ids
        ]
    
    async def set_default_caller_id(
        self,
        customer_id: str,
        caller_id_id: int
    ) -> bool:
        """Set a caller ID as the default for a customer."""
        # Clear existing defaults
        self.db.query(CustomerCallerId).filter(
            CustomerCallerId.customer_id == customer_id,
            CustomerCallerId.is_default == True
        ).update({"is_default": False})
        
        # Set new default
        caller_id = self.db.query(CustomerCallerId).filter(
            CustomerCallerId.id == caller_id_id,
            CustomerCallerId.customer_id == customer_id
        ).first()
        
        if not caller_id:
            raise ValueError(f"Caller ID {caller_id_id} not found")
        
        caller_id.is_default = True
        self.db.commit()
        
        return True
    
    async def delete_caller_id(
        self,
        customer_id: str,
        caller_id_id: int
    ) -> bool:
        """Delete a caller ID from database and Twilio."""
        self._ensure_client()
        
        caller_id = self.db.query(CustomerCallerId).filter(
            CustomerCallerId.id == caller_id_id,
            CustomerCallerId.customer_id == customer_id
        ).first()
        
        if not caller_id:
            raise ValueError(f"Caller ID {caller_id_id} not found")
        
        # Try to delete from Twilio
        try:
            outgoing_caller_ids = self.client.outgoing_caller_ids.list(
                phone_number=caller_id.twilio_phone_number
            )
            
            for ocid in outgoing_caller_ids:
                self.client.outgoing_caller_ids(ocid.sid).delete()
                
        except TwilioRestException as e:
            logger.warning(f"Failed to delete caller ID from Twilio: {e}")
        
        # Delete from database
        self.db.delete(caller_id)
        self.db.commit()
        
        return True
    
    # =========================================================================
    # Outbound Calls
    # =========================================================================
    
    async def initiate_call(
        self,
        scheduled_call_id: int,
        from_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Initiate an outbound reference check call.
        
        Args:
            scheduled_call_id: ID of the scheduled call
            from_number: Caller ID to use (optional, uses default if not specified)
        
        Returns:
            Dict with call_sid, status, etc.
        """
        self._ensure_client()
        
        # Get scheduled call with reference
        scheduled_call = self.db.query(ReferenceScheduledCall).filter(
            ReferenceScheduledCall.id == scheduled_call_id
        ).first()
        
        if not scheduled_call:
            raise ValueError(f"Scheduled call {scheduled_call_id} not found")
        
        reference = scheduled_call.reference
        if not reference:
            raise ValueError(f"Reference not found for scheduled call {scheduled_call_id}")
        
        # Determine caller ID
        if not from_number:
            from_number = scheduled_call.caller_id or self.settings.twilio_phone_number
        
        if not from_number:
            raise ValueError("No caller ID configured")
        
        # Build webhook URL
        webhook_base = self.settings.twilio_webhook_base_url
        if not webhook_base:
            raise ValueError("TWILIO_WEBHOOK_BASE_URL not configured")
        
        try:
            # Create the call
            call = self.client.calls.create(
                to=reference.phone_number,
                from_=from_number,
                url=f"{webhook_base}/api/v1/reference-checks/webhooks/voice/{scheduled_call_id}",
                status_callback=f"{webhook_base}/api/v1/reference-checks/webhooks/status/{scheduled_call_id}",
                status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                status_callback_method='POST',
                record=True,
                recording_status_callback=f"{webhook_base}/api/v1/reference-checks/webhooks/recording/{scheduled_call_id}",
                recording_status_callback_event=['completed'],
                timeout=60,  # Ring for 60 seconds before voicemail
                machine_detection='DetectMessageEnd',  # Detect voicemail
                machine_detection_timeout=30
            )
            
            # Update scheduled call status
            scheduled_call.status = ScheduledCallStatus.IN_PROGRESS
            
            # Create call record
            call_record = ReferenceCall(
                scheduled_call_id=scheduled_call_id,
                reference_id=reference.id,
                twilio_call_sid=call.sid,
                call_type=CallType.OUTBOUND,
                call_status=CallStatus.INITIATED,
                started_at=datetime.now(timezone.utc)
            )
            self.db.add(call_record)
            self.db.commit()
            self.db.refresh(call_record)
            
            logger.info(
                "Outbound call initiated",
                extra={
                    "scheduled_call_id": scheduled_call_id,
                    "call_sid": call.sid,
                    "to": reference.phone_number
                }
            )
            
            return {
                "call_id": call_record.id,
                "call_sid": call.sid,
                "status": call.status,
                "direction": call.direction,
                "to": reference.phone_number,
                "from": from_number
            }
            
        except TwilioRestException as e:
            logger.error(f"Failed to initiate call: {e}")
            raise
    
    def generate_voice_twiml(
        self,
        scheduled_call_id: int,
        websocket_url: str
    ) -> str:
        """
        Generate TwiML for connecting call to OpenAI Realtime via WebSocket.
        
        Args:
            scheduled_call_id: ID of the scheduled call
            websocket_url: WebSocket URL for media streaming
        
        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        
        # Connect to WebSocket for bidirectional audio streaming
        connect = Connect()
        stream = Stream(url=websocket_url)
        stream.parameter(name='scheduled_call_id', value=str(scheduled_call_id))
        connect.append(stream)
        response.append(connect)
        
        return str(response)
    
    def generate_voicemail_twiml(
        self,
        reference_name: str,
        company_name: str,
        candidate_name: str,
        callback_number: str
    ) -> str:
        """
        Generate TwiML for leaving a voicemail message.
        
        Returns:
            TwiML XML string
        """
        response = VoiceResponse()
        
        message = (
            f"Hi {reference_name}, this is a call from {company_name} regarding a professional "
            f"reference check for {candidate_name}. Please call us back at your convenience at "
            f"{callback_number}. Thank you and have a great day."
        )
        
        response.say(message, voice='Polly.Joanna')
        response.hangup()
        
        return str(response)
    
    # =========================================================================
    # Inbound Calls (Callbacks)
    # =========================================================================
    
    async def handle_inbound_call(
        self,
        from_number: str
    ) -> Optional[Dict[str, Any]]:
        """
        Handle incoming call from a reference calling back.
        Match by phone number to find pending reference check.
        
        Args:
            from_number: Caller's phone number
        
        Returns:
            Dict with reference info if found, None otherwise
        """
        # Look up reference by phone number with pending callback status
        reference = self.db.query(CandidateReference).filter(
            CandidateReference.phone_number == from_number,
            CandidateReference.status.in_(['voicemail', 'callback_pending'])
        ).first()
        
        if reference:
            # Find the most recent scheduled call
            scheduled_call = self.db.query(ReferenceScheduledCall).filter(
                ReferenceScheduledCall.reference_id == reference.id,
                ReferenceScheduledCall.status.in_([
                    ScheduledCallStatus.VOICEMAIL,
                    ScheduledCallStatus.CALLBACK_PENDING
                ])
            ).order_by(ReferenceScheduledCall.created_at.desc()).first()
            
            if scheduled_call:
                logger.info(
                    "Inbound callback matched to reference",
                    extra={
                        "from_number": from_number,
                        "reference_id": reference.id,
                        "scheduled_call_id": scheduled_call.id
                    }
                )
                
                return {
                    "found": True,
                    "reference_id": reference.id,
                    "scheduled_call_id": scheduled_call.id,
                    "reference_name": reference.full_name,
                    "template_id": scheduled_call.template_id,
                    "persona_id": scheduled_call.persona_id
                }
        
        logger.info(f"No pending reference found for callback from {from_number}")
        return {"found": False}
    
    # =========================================================================
    # SMS Reminders
    # =========================================================================
    
    async def send_reminder(
        self,
        to: str,
        reference_name: str,
        candidate_name: str,
        company_name: str,
        scheduled_time: datetime,
        reminder_type: str  # '24h', '2h', '15m'
    ) -> Dict[str, Any]:
        """
        Send SMS reminder for upcoming reference check call.
        
        Args:
            to: Phone number to send to
            reference_name: Name of the reference
            candidate_name: Name of the candidate
            company_name: Name of the hiring company
            scheduled_time: Scheduled call time
            reminder_type: Type of reminder ('24h', '2h', '15m')
        
        Returns:
            Dict with message_sid and status
        """
        self._ensure_client()
        
        time_str = scheduled_time.strftime("%I:%M %p on %B %d")
        
        messages = {
            '24h': (
                f"Hi {reference_name}, reminder: You have a reference check call "
                f"scheduled for {time_str} regarding {candidate_name}'s application "
                f"at {company_name}. We'll call you at this number."
            ),
            '2h': (
                f"Hi {reference_name}, your reference check call for {candidate_name} "
                f"is in 2 hours ({time_str}). Please ensure you're available."
            ),
            '15m': (
                f"Hi {reference_name}, we'll be calling you in 15 minutes for the "
                f"reference check regarding {candidate_name}. Thank you!"
            )
        }
        
        message_body = messages.get(reminder_type)
        if not message_body:
            raise ValueError(f"Invalid reminder type: {reminder_type}")
        
        try:
            # Use messaging service if configured, otherwise use phone number
            if self.settings.twilio_messaging_service_sid:
                message = self.client.messages.create(
                    body=message_body,
                    messaging_service_sid=self.settings.twilio_messaging_service_sid,
                    to=to
                )
            else:
                message = self.client.messages.create(
                    body=message_body,
                    from_=self.settings.twilio_phone_number,
                    to=to
                )
            
            logger.info(
                "SMS reminder sent",
                extra={
                    "to": to,
                    "reminder_type": reminder_type,
                    "message_sid": message.sid
                }
            )
            
            return {
                "message_sid": message.sid,
                "status": message.status,
                "reminder_type": reminder_type
            }
            
        except TwilioRestException as e:
            logger.error(f"Failed to send SMS reminder: {e}")
            raise
    
    # =========================================================================
    # Call Status Updates
    # =========================================================================
    
    async def update_call_status(
        self,
        call_sid: str,
        status: str,
        duration: Optional[int] = None,
        answered_by: Optional[str] = None
    ) -> ReferenceCall:
        """
        Update call status from Twilio webhook.
        
        Args:
            call_sid: Twilio call SID
            status: Call status from Twilio
            duration: Call duration in seconds
            answered_by: 'human' or 'machine' (voicemail detection)
        
        Returns:
            Updated ReferenceCall record
        """
        call_record = self.db.query(ReferenceCall).filter(
            ReferenceCall.twilio_call_sid == call_sid
        ).first()
        
        if not call_record:
            logger.warning(f"Call record not found for SID {call_sid}")
            return None
        
        # Map Twilio status to our status
        status_map = {
            'initiated': CallStatus.INITIATED,
            'ringing': CallStatus.RINGING,
            'in-progress': CallStatus.IN_PROGRESS,
            'completed': CallStatus.COMPLETED,
            'busy': CallStatus.BUSY,
            'no-answer': CallStatus.NO_ANSWER,
            'failed': CallStatus.FAILED,
            'canceled': CallStatus.FAILED
        }
        
        call_record.call_status = status_map.get(status, CallStatus.FAILED)
        
        if duration:
            call_record.duration_seconds = duration
        
        if status in ['completed', 'busy', 'no-answer', 'failed', 'canceled']:
            call_record.ended_at = datetime.now(timezone.utc)
        
        # Handle voicemail detection
        if answered_by == 'machine':
            call_record.call_status = CallStatus.VOICEMAIL
            call_record.is_complete = False
            call_record.incomplete_reason = 'voicemail'
            
            # Update scheduled call and reference status
            if call_record.scheduled_call:
                call_record.scheduled_call.status = ScheduledCallStatus.VOICEMAIL
            if call_record.reference:
                call_record.reference.status = 'voicemail'
        
        self.db.commit()
        self.db.refresh(call_record)
        
        logger.info(
            "Call status updated",
            extra={
                "call_sid": call_sid,
                "status": status,
                "call_status": call_record.call_status.value
            }
        )
        
        return call_record
    
    async def update_recording(
        self,
        call_sid: str,
        recording_url: str,
        recording_sid: str,
        recording_duration: int
    ) -> ReferenceCall:
        """
        Update call with recording information.
        
        Args:
            call_sid: Twilio call SID
            recording_url: URL to the recording
            recording_sid: Recording SID
            recording_duration: Recording duration in seconds
        
        Returns:
            Updated ReferenceCall record
        """
        call_record = self.db.query(ReferenceCall).filter(
            ReferenceCall.twilio_call_sid == call_sid
        ).first()
        
        if not call_record:
            logger.warning(f"Call record not found for SID {call_sid}")
            return None
        
        call_record.recording_url = recording_url
        call_record.recording_sid = recording_sid
        call_record.recording_duration_seconds = recording_duration
        
        self.db.commit()
        self.db.refresh(call_record)
        
        logger.info(
            "Recording updated",
            extra={
                "call_sid": call_sid,
                "recording_sid": recording_sid,
                "duration": recording_duration
            }
        )
        
        return call_record
    
    # =========================================================================
    # Usage and Metering
    # =========================================================================
    
    async def get_usage_summary(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get usage records for a date range.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
        
        Returns:
            Dict with usage summary
        """
        self._ensure_client()
        
        try:
            records = self.client.usage.records.list(
                start_date=start_date.date(),
                end_date=end_date.date()
            )
            
            usage = {
                "calls": None,
                "sms": None,
                "recordings": None
            }
            
            for record in records:
                if record.category == 'calls':
                    usage["calls"] = {
                        "count": record.count,
                        "usage": record.usage,
                        "price": record.price
                    }
                elif record.category == 'sms':
                    usage["sms"] = {
                        "count": record.count,
                        "usage": record.usage,
                        "price": record.price
                    }
                elif record.category == 'recordings':
                    usage["recordings"] = {
                        "count": record.count,
                        "usage": record.usage,
                        "price": record.price
                    }
            
            return usage
            
        except TwilioRestException as e:
            logger.error(f"Failed to get usage summary: {e}")
            raise
    
    async def get_call_metrics(self, call_sid: str) -> Dict[str, Any]:
        """
        Get detailed metrics for a specific call.
        
        Args:
            call_sid: Twilio call SID
        
        Returns:
            Dict with call metrics
        """
        self._ensure_client()
        
        try:
            call = self.client.calls(call_sid).fetch()
            
            return {
                "sid": call.sid,
                "duration": call.duration,
                "price": call.price,
                "price_unit": call.price_unit,
                "status": call.status,
                "start_time": call.start_time.isoformat() if call.start_time else None,
                "end_time": call.end_time.isoformat() if call.end_time else None,
                "direction": call.direction,
                "answered_by": call.answered_by
            }
            
        except TwilioRestException as e:
            logger.error(f"Failed to get call metrics: {e}")
            raise

