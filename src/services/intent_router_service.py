"""
Intent Router Service

Smart router that uses LLM-based intent detection to determine:
1. Message type (DATA vs CONVERSATIONAL)
2. Question clarification needs
3. User intent confirmation

This replaces naive keyword matching with intelligent LLM-based routing.
"""
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field
import json

from src.core.config import get_settings
from src.core.logging import get_logger
import litellm

logger = get_logger(__name__, component="intent.router.service")


class MessageIntent(str, Enum):
    """Detected message intent."""
    DATA_QUERY = "data_query"  # Requires SQL generation
    CONVERSATIONAL = "conversational"  # General question, no SQL
    CLARIFICATION_NEEDED = "clarification_needed"  # Need to clarify with user
    AMBIGUOUS = "ambiguous"  # Unclear intent


class IntentConfidence(str, Enum):
    """Confidence level for intent detection."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IntentDetectionResult(BaseModel):
    """Result of intent detection."""
    intent: MessageIntent
    confidence: IntentConfidence
    clarified_question: Optional[str] = None  # Clarified/rephrased question
    clarification_needed: bool = False
    clarification_prompt: Optional[str] = None  # Question to ask user for clarification
    reasoning: Optional[str] = None  # Why this intent was detected
    suggested_sql_hint: Optional[str] = None  # Hint for SQL generation if DATA_QUERY


class IntentRouterService:
    """
    Smart router for message intent detection and clarification.
    
    Uses LLM to:
    1. Detect intent (DATA vs CONVERSATIONAL)
    2. Clarify ambiguous questions
    3. Confirm user intent
    4. Provide hints for SQL generation
    """
    
    def __init__(self):
        """Initialize intent router service."""
        self.settings = get_settings()
        self.model = "gpt-4o-mini"  # Cost-effective model for intent detection
    
    def detect_intent(
        self,
        question: str,
        conversation_context: Optional[str] = None
    ) -> IntentDetectionResult:
        """
        Detect message intent using LLM.
        
        Args:
            question: User's question/message
            conversation_context: Optional conversation context (last N messages)
            
        Returns:
            IntentDetectionResult with detected intent, confidence, and clarification needs
        """
        if not self._can_use_llm():
            # Fallback to keyword-based detection if LLM not available
            logger.warning("LLM not available, using fallback intent detection")
            return self._fallback_intent_detection(question)
        
        try:
            # Build prompt for intent detection
            prompt = self._build_intent_detection_prompt(question, conversation_context)
            
            # Call LLM for structured response
            response = litellm.completion(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an intent detection system for a data analyst agent.
Your job is to analyze user questions and determine:
1. Whether they need SQL/data retrieval (DATA_QUERY) or general conversation (CONVERSATIONAL)
2. If the question is clear or needs clarification
3. Provide a clarified/rephrased version of the question if needed

Respond ONLY with valid JSON matching this schema:
{
    "intent": "data_query" | "conversational" | "clarification_needed" | "ambiguous",
    "confidence": "high" | "medium" | "low",
    "clarified_question": "rephrased question if needed, null otherwise",
    "clarification_needed": true/false,
    "clarification_prompt": "question to ask user if clarification needed, null otherwise",
    "reasoning": "brief explanation of why this intent was detected",
    "suggested_sql_hint": "hint for SQL generation if data_query, null otherwise"
}"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent intent detection
                max_tokens=500,
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            # Parse JSON response
            content = response.choices[0].message.content
            result_dict = json.loads(content)
            
            # Validate and create result
            intent = MessageIntent(result_dict.get("intent", "ambiguous"))
            confidence = IntentConfidence(result_dict.get("confidence", "low"))
            
            result = IntentDetectionResult(
                intent=intent,
                confidence=confidence,
                clarified_question=result_dict.get("clarified_question"),
                clarification_needed=result_dict.get("clarification_needed", False),
                clarification_prompt=result_dict.get("clarification_prompt"),
                reasoning=result_dict.get("reasoning"),
                suggested_sql_hint=result_dict.get("suggested_sql_hint")
            )
            
            logger.info(
                "intent_detected",
                intent=intent.value,
                confidence=confidence.value,
                clarification_needed=result.clarification_needed,
                question_length=len(question)
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "intent_detection_failed",
                error=str(e),
                question_length=len(question),
                exc_info=True
            )
            # Fallback to keyword-based detection
            return self._fallback_intent_detection(question)
    
    def clarify_question(
        self,
        question: str,
        clarification_prompt: str,
        user_response: str
    ) -> str:
        """
        Clarify question based on user's response to clarification prompt.
        
        Args:
            question: Original question
            clarification_prompt: The clarification question asked
            user_response: User's response to clarification
            
        Returns:
            Clarified question combining original and user response
        """
        if not self._can_use_llm():
            # Simple concatenation fallback
            return f"{question} ({user_response})"
        
        try:
            prompt = f"""Original question: {question}
Clarification asked: {clarification_prompt}
User's response: {user_response}

Based on the user's response, create a clear, clarified version of the original question that incorporates their clarification.
Return ONLY the clarified question, nothing else."""

            response = litellm.completion(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a question clarification assistant. Your job is to combine the original question with the user's clarification response into a single, clear question."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.5,
                max_tokens=200
            )
            
            clarified = response.choices[0].message.content.strip()
            
            logger.info(
                "question_clarified",
                original_length=len(question),
                clarified_length=len(clarified)
            )
            
            return clarified
            
        except Exception as e:
            logger.error(
                "question_clarification_failed",
                error=str(e),
                exc_info=True
            )
            # Fallback to simple concatenation
            return f"{question} ({user_response})"
    
    def confirm_intent(
        self,
        question: str,
        detected_intent: MessageIntent,
        suggested_sql_hint: Optional[str] = None
    ) -> str:
        """
        Generate a confirmation message for the user to confirm their intent.
        
        Args:
            question: User's question
            detected_intent: Detected intent
            suggested_sql_hint: Optional SQL hint if DATA_QUERY
            
        Returns:
            Confirmation message to show user
        """
        if detected_intent == MessageIntent.DATA_QUERY:
            confirmation = f"I understand you want to query data. I'll generate SQL to answer: \"{question}\""
            if suggested_sql_hint:
                confirmation += f"\n\nI'll look for: {suggested_sql_hint}"
            confirmation += "\n\nIs this correct? (Yes/No or provide corrections)"
        elif detected_intent == MessageIntent.CONVERSATIONAL:
            confirmation = f"I understand you have a general question: \"{question}\"\n\nI'll provide a conversational answer. Is this correct? (Yes/No or provide corrections)"
        else:
            confirmation = f"I'm not entirely sure what you're asking. Could you clarify: \"{question}\"?"
        
        return confirmation
    
    def _build_intent_detection_prompt(
        self,
        question: str,
        conversation_context: Optional[str] = None
    ) -> str:
        """Build prompt for intent detection."""
        prompt_parts = []
        
        if conversation_context:
            prompt_parts.append(f"Conversation context:\n{conversation_context}\n")
        
        prompt_parts.append(f"User question: {question}\n")
        prompt_parts.append("""
Analyze this question and determine:
1. Intent: Does this require SQL/data retrieval (DATA_QUERY) or is it a general question (CONVERSATIONAL)?
2. Clarity: Is the question clear enough to proceed, or does it need clarification?
3. If DATA_QUERY: What data/tables might be needed? (suggested_sql_hint)
4. If unclear: What clarification should be asked? (clarification_prompt)

Examples:
- "What is the total premium collected?" → DATA_QUERY, high confidence
- "How do I calculate loss ratio?" → CONVERSATIONAL, high confidence
- "Show me premium data" → DATA_QUERY, low confidence, needs clarification (what time period? which policies?)
- "What's our process?" → CONVERSATIONAL, medium confidence, might need clarification (which process?)

Respond with JSON only.""")
        
        return "\n".join(prompt_parts)
    
    def _fallback_intent_detection(self, question: str) -> IntentDetectionResult:
        """
        Fallback keyword-based intent detection when LLM is not available.
        
        Args:
            question: User's question
            
        Returns:
            IntentDetectionResult using keyword matching
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
        
        data_score = sum(1 for keyword in data_keywords if keyword in question_lower)
        conversational_score = sum(1 for keyword in conversational_keywords if keyword in question_lower)
        
        # Determine intent
        if data_score > conversational_score and data_score > 0:
            intent = MessageIntent.DATA_QUERY
            confidence = IntentConfidence.HIGH if data_score >= 2 else IntentConfidence.MEDIUM
        elif conversational_score > data_score and conversational_score > 0:
            intent = MessageIntent.CONVERSATIONAL
            confidence = IntentConfidence.HIGH if conversational_score >= 2 else IntentConfidence.MEDIUM
        elif data_score == conversational_score and data_score > 0:
            intent = MessageIntent.AMBIGUOUS
            confidence = IntentConfidence.LOW
        else:
            # No clear keywords - default to DATA but with low confidence
            intent = MessageIntent.DATA_QUERY
            confidence = IntentConfidence.LOW
        
        return IntentDetectionResult(
            intent=intent,
            confidence=confidence,
            clarification_needed=(confidence == IntentConfidence.LOW),
            reasoning=f"Keyword-based detection: data_score={data_score}, conversational_score={conversational_score}"
        )
    
    def _can_use_llm(self) -> bool:
        """Check if LLM is available for intent detection."""
        return bool(self.settings.openai_api_key)

