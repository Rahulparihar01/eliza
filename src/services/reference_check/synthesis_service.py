"""
Synthesis Service for Reference Check

Handles:
- Q&A extraction from transcripts
- AI-generated summaries
- Transcript-audio synchronization
"""

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from openai import AsyncOpenAI

from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory
from src.models.reference_check import (
    ReferenceCall,
    ReferenceCallTranscript,
    ReferenceQuestionResponse,
    ReferenceCallSummary,
    ReferenceTemplateQuestion
)

logger = get_logger(__name__, LogCategory.INTEGRATION)


class SynthesisService:
    """
    Service for synthesizing reference check call data.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.openai_client = AsyncOpenAI(api_key=self.settings.openai_api_key)
    
    async def extract_qa_pairs(
        self,
        call_id: int,
        transcript: str,
        template_questions: List[ReferenceTemplateQuestion]
    ) -> List[ReferenceQuestionResponse]:
        """
        Extract question-answer pairs from transcript.
        
        Args:
            call_id: ID of the call
            transcript: Full transcript text
            template_questions: List of template questions to match
        
        Returns:
            List of extracted Q&A pairs
        """
        # Format questions for the prompt
        questions_json = json.dumps([
            {
                "id": q.id,
                "text": q.question_text,
                "type": q.question_type.value,
                "priority": q.priority.value
            }
            for q in template_questions
        ])
        
        prompt = f"""Analyze this reference check transcript and extract question-answer pairs.

TRANSCRIPT:
{transcript}

TEMPLATE QUESTIONS:
{questions_json}

For each question that was asked (whether from template or as a follow-up):
1. Identify the exact question asked
2. Extract the complete response
3. Match to template question ID if applicable (null if it's a follow-up or off-template question)
4. Note any follow-up questions and responses
5. Assess sentiment (positive/neutral/negative/mixed)
6. Provide approximate timestamp ranges (seconds from start, estimate based on position in transcript)

Return as JSON array:
{{
  "questions": [
    {{
      "template_question_id": <id or null>,
      "question_asked": "<exact question>",
      "response_text": "<complete response>",
      "sentiment": "<sentiment>",
      "start_time": <seconds>,
      "end_time": <seconds>,
      "follow_ups": [
        {{"question": "...", "response": "...", "timestamp": <seconds>}}
      ]
    }}
  ]
}}
"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing interview transcripts. Extract information accurately and completely."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            qa_list = result.get("questions", [])
            
            # Create database records
            qa_records = []
            for qa in qa_list:
                record = ReferenceQuestionResponse(
                    call_id=call_id,
                    template_question_id=qa.get("template_question_id"),
                    question_asked=qa.get("question_asked", ""),
                    response_text=qa.get("response_text", ""),
                    response_sentiment=qa.get("sentiment"),
                    transcript_start_time=qa.get("start_time"),
                    transcript_end_time=qa.get("end_time"),
                    follow_up_questions=qa.get("follow_ups")
                )
                self.db.add(record)
                qa_records.append(record)
            
            self.db.commit()
            
            logger.info(
                "Q&A pairs extracted",
                extra={
                    "call_id": call_id,
                    "qa_count": len(qa_records)
                }
            )
            
            return qa_records
            
        except Exception as e:
            logger.error(f"Failed to extract Q&A pairs: {e}")
            raise
    
    async def generate_summary(
        self,
        call_id: int,
        transcript: str,
        qa_pairs: List[ReferenceQuestionResponse],
        candidate_name: str,
        position: str
    ) -> ReferenceCallSummary:
        """
        Generate executive summary from reference check.
        
        Args:
            call_id: ID of the call
            transcript: Full transcript text
            qa_pairs: Extracted Q&A pairs
            candidate_name: Name of the candidate
            position: Position being applied for
        
        Returns:
            Generated summary record
        """
        # Format Q&A for prompt
        qa_json = json.dumps([
            {
                "question": qa.question_asked,
                "response": qa.response_text,
                "sentiment": qa.response_sentiment,
                "follow_ups": qa.follow_up_questions
            }
            for qa in qa_pairs
        ])
        
        prompt = f"""Generate a comprehensive summary of this reference check.

CANDIDATE: {candidate_name}
POSITION: {position}

TRANSCRIPT:
{transcript}

EXTRACTED Q&A:
{qa_json}

Provide a thorough analysis including:
1. Executive summary (2-3 paragraphs covering the overall reference feedback)
2. Key strengths mentioned by the reference (specific examples when possible)
3. Areas of concern or development needs (be specific but fair)
4. Notable direct quotes with context (include approximate timestamps)
5. Overall sentiment assessment
6. Recommendation score (1-10) with clear justification

Return as JSON:
{{
  "executive_summary": "...",
  "key_strengths": ["strength 1 with example", "strength 2 with example", ...],
  "areas_of_concern": ["concern 1", "concern 2", ...],
  "notable_quotes": [
    {{"quote": "exact quote", "context": "what prompted this", "timestamp": <seconds>}}
  ],
  "overall_sentiment": "positive|neutral|negative|mixed",
  "recommendation_score": <1-10>,
  "recommendation_notes": "justification for the score"
}}
"""
        
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert HR analyst specializing in reference check evaluation. Provide balanced, insightful analysis."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Create summary record
            summary = ReferenceCallSummary(
                call_id=call_id,
                executive_summary=result.get("executive_summary", ""),
                key_strengths=result.get("key_strengths", []),
                areas_of_concern=result.get("areas_of_concern", []),
                notable_quotes=result.get("notable_quotes", []),
                overall_sentiment=result.get("overall_sentiment"),
                recommendation_score=result.get("recommendation_score"),
                recommendation_notes=result.get("recommendation_notes")
            )
            
            self.db.add(summary)
            self.db.commit()
            self.db.refresh(summary)
            
            logger.info(
                "Call summary generated",
                extra={
                    "call_id": call_id,
                    "recommendation_score": summary.recommendation_score
                }
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            raise
    
    async def create_transcript(
        self,
        call_id: int,
        conversation_history: List[Dict[str, Any]]
    ) -> ReferenceCallTranscript:
        """
        Create transcript record from conversation history.
        
        Args:
            call_id: ID of the call
            conversation_history: List of conversation turns
        
        Returns:
            Transcript record
        """
        # Build full transcript text
        full_transcript = ""
        segments = []
        current_time = 0.0
        
        for turn in conversation_history:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            
            # Estimate timing (rough approximation)
            # Average speaking rate is ~150 words per minute
            word_count = len(content.split())
            duration = (word_count / 150) * 60  # seconds
            
            speaker_label = "Agent" if role == "agent" else "Reference"
            full_transcript += f"{speaker_label}: {content}\n\n"
            
            segments.append({
                "speaker": role,
                "text": content,
                "start_time": current_time,
                "end_time": current_time + duration
            })
            
            current_time += duration
        
        # Create transcript record
        transcript = ReferenceCallTranscript(
            call_id=call_id,
            full_transcript=full_transcript.strip(),
            transcript_segments=segments,
            language="en"
        )
        
        self.db.add(transcript)
        self.db.commit()
        self.db.refresh(transcript)
        
        logger.info(
            "Transcript created",
            extra={
                "call_id": call_id,
                "segment_count": len(segments)
            }
        )
        
        return transcript
    
    async def create_word_level_mapping(
        self,
        call_id: int,
        recording_url: str
    ) -> Dict[str, Any]:
        """
        Create word-level timestamp mapping for audio sync.
        Uses OpenAI Whisper for precise transcription.
        
        Args:
            call_id: ID of the call
            recording_url: URL to the call recording
        
        Returns:
            Word mapping data
        """
        import aiohttp
        import tempfile
        import os
        
        try:
            # Download recording
            async with aiohttp.ClientSession() as session:
                async with session.get(recording_url) as response:
                    if response.status != 200:
                        raise ValueError(f"Failed to download recording: {response.status}")
                    
                    audio_data = await response.read()
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name
            
            try:
                # Transcribe with word timestamps
                with open(tmp_path, "rb") as audio_file:
                    response = await self.openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format="verbose_json",
                        timestamp_granularities=["word", "segment"]
                    )
                
                # Build word map
                word_map = []
                for word in response.words:
                    word_map.append({
                        "word": word.word,
                        "start": word.start,
                        "end": word.end
                    })
                
                # Update transcript with word timestamps
                transcript = self.db.query(ReferenceCallTranscript).filter(
                    ReferenceCallTranscript.call_id == call_id
                ).first()
                
                if transcript:
                    transcript.word_timestamps = word_map
                    transcript.confidence_score = getattr(response, 'confidence', None)
                    self.db.commit()
                
                logger.info(
                    "Word-level mapping created",
                    extra={
                        "call_id": call_id,
                        "word_count": len(word_map)
                    }
                )
                
                return {
                    "segments": response.segments,
                    "words": word_map,
                    "duration": response.duration
                }
                
            finally:
                # Clean up temp file
                os.unlink(tmp_path)
                
        except Exception as e:
            logger.error(f"Failed to create word-level mapping: {e}")
            raise
    
    def get_timestamp_for_text(
        self,
        search_text: str,
        word_map: List[Dict[str, Any]]
    ) -> float:
        """
        Find timestamp for specific text in the recording.
        
        Args:
            search_text: Text to find
            word_map: Word-level timestamp mapping
        
        Returns:
            Timestamp in seconds, or 0.0 if not found
        """
        search_words = search_text.lower().split()
        
        for i in range(len(word_map) - len(search_words) + 1):
            match = True
            for j, search_word in enumerate(search_words):
                word_in_map = word_map[i + j]['word'].lower().strip('.,!?')
                if word_in_map != search_word.strip('.,!?'):
                    match = False
                    break
            
            if match:
                return word_map[i]['start']
        
        return 0.0
    
    async def process_call_completion(
        self,
        call_id: int,
        conversation_history: List[Dict[str, Any]],
        candidate_name: str,
        position: str,
        template_questions: List[ReferenceTemplateQuestion]
    ) -> Dict[str, Any]:
        """
        Process a completed call: create transcript, extract Q&A, generate summary.
        
        Args:
            call_id: ID of the call
            conversation_history: Conversation history from voice agent
            candidate_name: Name of the candidate
            position: Position being applied for
            template_questions: Template questions used
        
        Returns:
            Processing results
        """
        # Create transcript
        transcript = await self.create_transcript(call_id, conversation_history)
        
        # Extract Q&A pairs
        qa_pairs = await self.extract_qa_pairs(
            call_id=call_id,
            transcript=transcript.full_transcript,
            template_questions=template_questions
        )
        
        # Generate summary
        summary = await self.generate_summary(
            call_id=call_id,
            transcript=transcript.full_transcript,
            qa_pairs=qa_pairs,
            candidate_name=candidate_name,
            position=position
        )
        
        # Update call record
        call = self.db.query(ReferenceCall).filter(ReferenceCall.id == call_id).first()
        if call:
            call.is_complete = True
            self.db.commit()
        
        return {
            "call_id": call_id,
            "transcript_id": transcript.id,
            "qa_count": len(qa_pairs),
            "summary_id": summary.id,
            "recommendation_score": summary.recommendation_score
        }

