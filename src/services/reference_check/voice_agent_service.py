"""
Voice Agent Service for Reference Check

Handles OpenAI Realtime API integration for conversational AI voice agent.
Manages the voice agent's behavior, prompts, and conversation flow.
"""

import json
import asyncio
import websockets
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from openai import AsyncOpenAI

from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory
from src.models.reference_check import (
    ReferenceCallTemplate,
    ReferenceTemplateQuestion,
    ReferenceVoicePersona,
    ReferenceConsentTemplate,
    ReferenceScheduledCall,
    ReferenceCall,
    CandidateReference,
    QuestionType,
    QuestionPriority
)

logger = get_logger(__name__, LogCategory.INTEGRATION)


@dataclass
class ConversationTurn:
    """Represents a single turn in the conversation."""
    role: str  # 'agent' or 'reference'
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    audio_start_time: Optional[float] = None
    audio_end_time: Optional[float] = None


@dataclass
class QuestionTracker:
    """Tracks which questions have been asked and answered."""
    question_id: int
    question_text: str
    question_type: QuestionType
    priority: QuestionPriority
    asked: bool = False
    answered: bool = False
    response_text: Optional[str] = None
    follow_ups: List[Dict[str, str]] = field(default_factory=list)


class VoiceAgentService:
    """
    Service for managing the AI voice agent using OpenAI Realtime API.
    """
    
    # Two-party consent states that require explicit consent
    TWO_PARTY_CONSENT_STATES = {
        'CA', 'CT', 'DE', 'FL', 'IL', 'MD', 'MA', 'MT', 'NV', 'NH', 'PA', 'WA'
    }
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.openai_client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        
        # Active sessions
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
    
    def _build_system_prompt(
        self,
        persona: ReferenceVoicePersona,
        template: ReferenceCallTemplate,
        reference_info: Dict[str, Any],
        candidate_info: Dict[str, Any],
        company_info: Dict[str, Any]
    ) -> str:
        """
        Build the system prompt for the voice agent.
        
        Args:
            persona: Voice persona configuration
            template: Call template with questions
            reference_info: Information about the reference
            candidate_info: Information about the candidate
            company_info: Information about the hiring company
        
        Returns:
            System prompt string
        """
        # Format questions
        questions_text = self._format_questions(template.questions)
        
        # Build personality description
        personality = ""
        if persona.personality_traits:
            traits = persona.personality_traits
            personality = f"""
PERSONALITY TRAITS:
- Warmth: {traits.get('warmth', 0.7)}/1.0
- Directness: {traits.get('directness', 0.6)}/1.0
- Formality: {traits.get('formality', 0.8)}/1.0
- Patience: {traits.get('patience', 0.9)}/1.0
"""
        
        prompt = f"""You are {persona.name}, a professional reference check specialist conducting a reference call on behalf of {company_info.get('name', 'the company')}.

PERSONA:
- Name: {persona.name}
- Tone: {persona.tone}
- Speaking Style: Professional but conversational
{personality}

CONTEXT:
- Candidate: {candidate_info.get('name', 'the candidate')}
- Position: {candidate_info.get('position', 'the position')}
- Reference: {reference_info.get('name', 'the reference')}
- Relationship: {reference_info.get('relationship', 'professional colleague')}
- Company: {reference_info.get('company', 'their company')}

QUESTIONS TO ASK:
{questions_text}

INSTRUCTIONS:
1. After obtaining recording consent, proceed with the reference check
2. Ask REQUIRED questions first, in a natural conversational flow
3. For 'VERBATIM' questions, ask exactly as written
4. For 'CONCEPT' questions, phrase naturally while covering the key concept
5. Ask thoughtful follow-up questions when responses are vague or particularly interesting
6. Be professional but warm - this is a conversation, not an interrogation
7. If the reference seems uncomfortable with a question, acknowledge and offer to move on
8. Keep your responses concise - you're conducting an interview, not lecturing
9. End gracefully when all required questions are covered or if time is running short
10. Thank them sincerely for their time

HANDLING DIFFICULT SITUATIONS:
- If asked about being an AI: "I'm an AI assistant helping {company_info.get('name', 'the company')} conduct reference checks. I ensure consistency and accuracy in our process while respecting everyone's time."
- If reference declines to answer a question: "I understand. Let's move on to the next topic."
- If conversation goes off-topic: Gently redirect back to the reference check purpose
- If reference is very brief: Ask thoughtful follow-up questions to get more detail

INTRODUCTION SCRIPT:
{persona.introduction_script or f"Hi {{reference_name}}, this is {persona.name} calling on behalf of {company_info.get('name', 'the company')}. Thank you for taking the time to speak with me today about {candidate_info.get('name', 'the candidate')}. Your insights are incredibly valuable in helping us make the right hiring decision."}

CLOSING SCRIPT:
{persona.closing_script or f"Thank you so much for your time today, {{reference_name}}. Your feedback has been incredibly helpful. If you think of anything else you'd like to share, please don't hesitate to reach out. Have a wonderful day!"}
"""
        return prompt
    
    def _format_questions(self, questions: List[ReferenceTemplateQuestion]) -> str:
        """Format questions for the system prompt."""
        formatted = []
        
        # Sort by priority (required first) then by order_index
        sorted_questions = sorted(
            questions,
            key=lambda q: (0 if q.priority == QuestionPriority.REQUIRED else 1, q.order_index)
        )
        
        for i, q in enumerate(sorted_questions, 1):
            priority_marker = "🔴 REQUIRED" if q.priority == QuestionPriority.REQUIRED else "🟡 OPTIONAL"
            type_marker = "[VERBATIM]" if q.question_type == QuestionType.VERBATIM else "[CONCEPT]"
            
            follow_up_note = ""
            if q.follow_up_enabled:
                follow_up_note = f" (up to {q.max_follow_ups} follow-ups allowed)"
            
            formatted.append(f"{i}. {priority_marker} {type_marker}: {q.question_text}{follow_up_note}")
        
        return "\n".join(formatted)
    
    def get_consent_template(
        self,
        jurisdiction: str
    ) -> Optional[ReferenceConsentTemplate]:
        """
        Get the appropriate consent template for a jurisdiction.
        
        Args:
            jurisdiction: State code or jurisdiction identifier
        
        Returns:
            Consent template or None
        """
        # Try exact match first
        template = self.db.query(ReferenceConsentTemplate).filter(
            ReferenceConsentTemplate.jurisdiction == jurisdiction.lower(),
            ReferenceConsentTemplate.is_active == True
        ).first()
        
        if template:
            return template
        
        # Fall back to category-based template
        if jurisdiction.upper() in self.TWO_PARTY_CONSENT_STATES:
            template = self.db.query(ReferenceConsentTemplate).filter(
                ReferenceConsentTemplate.jurisdiction == 'us_two_party',
                ReferenceConsentTemplate.is_active == True
            ).first()
        else:
            template = self.db.query(ReferenceConsentTemplate).filter(
                ReferenceConsentTemplate.jurisdiction == 'us_one_party',
                ReferenceConsentTemplate.is_active == True
            ).first()
        
        # Ultimate fallback to strict compliance
        if not template:
            template = self.db.query(ReferenceConsentTemplate).filter(
                ReferenceConsentTemplate.jurisdiction == 'strict_compliance',
                ReferenceConsentTemplate.is_active == True
            ).first()
        
        return template
    
    def format_consent_script(
        self,
        template: ReferenceConsentTemplate,
        reference_name: str,
        agent_name: str,
        company_name: str,
        candidate_name: str
    ) -> str:
        """
        Format consent script with variables.
        
        Args:
            template: Consent template
            reference_name: Name of the reference
            agent_name: Name of the AI agent
            company_name: Name of the hiring company
            candidate_name: Name of the candidate
        
        Returns:
            Formatted consent script
        """
        script = template.consent_script
        script = script.replace('{reference_name}', reference_name)
        script = script.replace('{agent_name}', agent_name)
        script = script.replace('{company_name}', company_name)
        script = script.replace('{candidate_name}', candidate_name)
        return script
    
    async def create_session(
        self,
        scheduled_call_id: int,
        is_test: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new voice agent session for a scheduled call.
        
        Args:
            scheduled_call_id: ID of the scheduled call
            is_test: Whether this is a test/playground session
        
        Returns:
            Session info including session_id
        """
        # Load scheduled call with related data
        scheduled_call = self.db.query(ReferenceScheduledCall).filter(
            ReferenceScheduledCall.id == scheduled_call_id
        ).first()
        
        if not scheduled_call:
            raise ValueError(f"Scheduled call {scheduled_call_id} not found")
        
        reference = scheduled_call.reference
        request = reference.request
        template = scheduled_call.template
        persona = scheduled_call.persona
        
        if not template:
            # Get default template for customer
            template = self.db.query(ReferenceCallTemplate).filter(
                ReferenceCallTemplate.customer_id == request.customer_id,
                ReferenceCallTemplate.is_default == True,
                ReferenceCallTemplate.is_active == True
            ).first()
        
        if not template:
            raise ValueError("No call template configured")
        
        if not persona:
            # Get default persona for customer
            persona = self.db.query(ReferenceVoicePersona).filter(
                ReferenceVoicePersona.customer_id == request.customer_id,
                ReferenceVoicePersona.is_default == True
            ).first()
        
        if not persona:
            # Create a default persona
            persona = ReferenceVoicePersona(
                customer_id=request.customer_id,
                name="Alex",
                voice_model="alloy",
                tone="professional",
                is_default=True
            )
        
        # Build context
        reference_info = {
            "name": reference.full_name,
            "relationship": reference.relationship.value if reference.relationship else "colleague",
            "company": reference.company,
            "title": reference.title
        }
        
        candidate_info = {
            "name": request.candidate_name,
            "position": request.job_title or "the position"
        }
        
        company_info = {
            "name": "the company"  # TODO: Get from customer settings
        }
        
        # Build system prompt
        system_prompt = self._build_system_prompt(
            persona=persona,
            template=template,
            reference_info=reference_info,
            candidate_info=candidate_info,
            company_info=company_info
        )
        
        # Initialize question tracker
        question_tracker = [
            QuestionTracker(
                question_id=q.id,
                question_text=q.question_text,
                question_type=q.question_type,
                priority=q.priority
            )
            for q in template.questions
        ]
        
        # Generate session ID
        import uuid
        session_id = str(uuid.uuid4())
        
        # Store session
        self.active_sessions[session_id] = {
            "scheduled_call_id": scheduled_call_id,
            "reference_id": reference.id,
            "template_id": template.id,
            "persona_id": persona.id if persona.id else None,
            "system_prompt": system_prompt,
            "persona": persona,
            "reference_info": reference_info,
            "candidate_info": candidate_info,
            "company_info": company_info,
            "question_tracker": question_tracker,
            "conversation_history": [],
            "consent_obtained": False,
            "is_test": is_test,
            "created_at": datetime.now(timezone.utc)
        }
        
        logger.info(
            "Voice agent session created",
            extra={
                "session_id": session_id,
                "scheduled_call_id": scheduled_call_id,
                "is_test": is_test
            }
        )
        
        return {
            "session_id": session_id,
            "scheduled_call_id": scheduled_call_id,
            "persona_name": persona.name,
            "template_name": template.name,
            "question_count": len(template.questions)
        }
    
    async def connect_realtime(
        self,
        session_id: str,
        audio_input_callback: Callable,
        audio_output_callback: Callable
    ):
        """
        Connect to OpenAI Realtime API for a session.
        
        Args:
            session_id: Session ID
            audio_input_callback: Callback to receive audio input from caller
            audio_output_callback: Callback to send audio output to caller
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        try:
            async with websockets.connect(
                "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01",
                extra_headers={
                    "Authorization": f"Bearer {self.settings.openai_api_key}",
                    "OpenAI-Beta": "realtime=v1"
                }
            ) as ws:
                # Initialize session
                await ws.send(json.dumps({
                    "type": "session.update",
                    "session": {
                        "modalities": ["text", "audio"],
                        "instructions": session["system_prompt"],
                        "voice": session["persona"].voice_model,
                        "input_audio_format": "pcm16",
                        "output_audio_format": "pcm16",
                        "input_audio_transcription": {
                            "model": "whisper-1"
                        },
                        "turn_detection": {
                            "type": "server_vad",
                            "threshold": 0.5,
                            "prefix_padding_ms": 300,
                            "silence_duration_ms": 500
                        }
                    }
                }))
                
                # Store websocket reference
                session["websocket"] = ws
                
                # Run bidirectional audio streaming
                await asyncio.gather(
                    self._forward_audio_to_openai(session_id, ws, audio_input_callback),
                    self._forward_audio_from_openai(session_id, ws, audio_output_callback),
                    self._process_events(session_id, ws)
                )
                
        except Exception as e:
            logger.error(f"Error in realtime connection: {e}")
            raise
        finally:
            # Clean up session
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]["websocket"]
    
    async def _forward_audio_to_openai(
        self,
        session_id: str,
        ws,
        audio_input_callback: Callable
    ):
        """Forward audio from caller to OpenAI."""
        try:
            async for audio_data in audio_input_callback():
                if session_id not in self.active_sessions:
                    break
                
                await ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": audio_data
                }))
        except Exception as e:
            logger.error(f"Error forwarding audio to OpenAI: {e}")
    
    async def _forward_audio_from_openai(
        self,
        session_id: str,
        ws,
        audio_output_callback: Callable
    ):
        """Forward audio from OpenAI to caller."""
        try:
            async for message in ws:
                if session_id not in self.active_sessions:
                    break
                
                data = json.loads(message)
                
                if data.get("type") == "response.audio.delta":
                    await audio_output_callback(data.get("delta"))
                    
        except Exception as e:
            logger.error(f"Error forwarding audio from OpenAI: {e}")
    
    async def _process_events(self, session_id: str, ws):
        """Process conversation events for logging and tracking."""
        session = self.active_sessions.get(session_id)
        if not session:
            return
        
        try:
            async for message in ws:
                if session_id not in self.active_sessions:
                    break
                
                data = json.loads(message)
                event_type = data.get("type")
                
                if event_type == "conversation.item.created":
                    # Log conversation turn
                    item = data.get("item", {})
                    role = "agent" if item.get("role") == "assistant" else "reference"
                    content = ""
                    
                    for part in item.get("content", []):
                        if part.get("type") == "text":
                            content = part.get("text", "")
                        elif part.get("type") == "audio":
                            content = part.get("transcript", "")
                    
                    if content:
                        turn = ConversationTurn(
                            role=role,
                            content=content
                        )
                        session["conversation_history"].append(turn)
                        
                        # Check for consent
                        if not session["consent_obtained"] and role == "reference":
                            content_lower = content.lower()
                            if any(word in content_lower for word in ["yes", "i consent", "i agree", "that's fine", "okay", "sure"]):
                                session["consent_obtained"] = True
                                logger.info(f"Consent obtained for session {session_id}")
                
                elif event_type == "response.done":
                    # Track question coverage
                    await self._track_question_coverage(session_id, data)
                
                elif event_type == "error":
                    logger.error(f"OpenAI Realtime error: {data}")
                    
        except Exception as e:
            logger.error(f"Error processing events: {e}")
    
    async def _track_question_coverage(self, session_id: str, response_data: Dict):
        """Track which questions have been asked and answered."""
        session = self.active_sessions.get(session_id)
        if not session:
            return
        
        # This would involve analyzing the conversation to match questions
        # For now, this is a placeholder - actual implementation would use
        # NLP to match conversation content to template questions
        pass
    
    async def end_session(self, session_id: str) -> Dict[str, Any]:
        """
        End a voice agent session and return conversation data.
        
        Args:
            session_id: Session ID
        
        Returns:
            Session data including conversation history
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Close websocket if open
        if "websocket" in session:
            try:
                await session["websocket"].close()
            except:
                pass
        
        # Compile results
        results = {
            "session_id": session_id,
            "scheduled_call_id": session["scheduled_call_id"],
            "consent_obtained": session["consent_obtained"],
            "conversation_history": [
                {
                    "role": turn.role,
                    "content": turn.content,
                    "timestamp": turn.timestamp.isoformat()
                }
                for turn in session["conversation_history"]
            ],
            "question_tracker": [
                {
                    "question_id": q.question_id,
                    "question_text": q.question_text,
                    "asked": q.asked,
                    "answered": q.answered,
                    "response_text": q.response_text
                }
                for q in session["question_tracker"]
            ],
            "is_test": session["is_test"],
            "duration": (datetime.now(timezone.utc) - session["created_at"]).total_seconds()
        }
        
        # Remove session
        del self.active_sessions[session_id]
        
        logger.info(
            "Voice agent session ended",
            extra={
                "session_id": session_id,
                "duration": results["duration"],
                "consent_obtained": results["consent_obtained"]
            }
        )
        
        return results
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a session."""
        session = self.active_sessions.get(session_id)
        if not session:
            return None
        
        return {
            "session_id": session_id,
            "scheduled_call_id": session["scheduled_call_id"],
            "consent_obtained": session["consent_obtained"],
            "turn_count": len(session["conversation_history"]),
            "is_test": session["is_test"],
            "duration": (datetime.now(timezone.utc) - session["created_at"]).total_seconds()
        }

