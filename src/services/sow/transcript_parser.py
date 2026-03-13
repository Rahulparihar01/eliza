"""
Transcript Parser for SOW Generation

Parses meeting transcripts from various sources (Fathom, plain text)
into a standardized format for SOW extraction.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class Utterance:
    """A single utterance from the transcript."""
    utterance_id: str
    speaker: str
    speaker_email: Optional[str]
    text: str
    timestamp: Optional[str]
    order_index: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "utterance_id": self.utterance_id,
            "speaker": self.speaker,
            "speaker_email": self.speaker_email,
            "text": self.text,
            "timestamp": self.timestamp,
            "order_index": self.order_index,
        }


@dataclass
class ActionItem:
    """An action item from the meeting."""
    description: str
    assignee_name: Optional[str]
    assignee_email: Optional[str]
    completed: bool
    timestamp: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "assignee_name": self.assignee_name,
            "assignee_email": self.assignee_email,
            "completed": self.completed,
            "timestamp": self.timestamp,
        }


@dataclass
class Participant:
    """A meeting participant."""
    name: str
    email: str
    is_external: bool
    team: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "email": self.email,
            "is_external": self.is_external,
            "team": self.team,
        }


@dataclass
class Meeting:
    """Parsed meeting data."""
    title: str
    url: Optional[str]
    created_at: Optional[datetime]
    scheduled_start: Optional[datetime]
    scheduled_end: Optional[datetime]
    recording_start: Optional[datetime]
    recording_end: Optional[datetime]
    participants: List[Participant]
    utterances: List[Utterance]
    action_items: List[ActionItem]
    summary: Optional[str]
    share_url: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "scheduled_start": self.scheduled_start.isoformat() if self.scheduled_start else None,
            "scheduled_end": self.scheduled_end.isoformat() if self.scheduled_end else None,
            "recording_start": self.recording_start.isoformat() if self.recording_start else None,
            "recording_end": self.recording_end.isoformat() if self.recording_end else None,
            "participants": [p.to_dict() for p in self.participants],
            "utterances": [u.to_dict() for u in self.utterances],
            "action_items": [a.to_dict() for a in self.action_items],
            "summary": self.summary,
            "share_url": self.share_url,
        }
    
    def to_transcript_text(self) -> str:
        """Convert to plain text transcript format."""
        lines = [f"Meeting: {self.title}"]
        if self.scheduled_start:
            lines.append(f"Date: {self.scheduled_start.strftime('%Y-%m-%d')}")
        lines.append("")
        
        for utterance in self.utterances:
            lines.append(f"{utterance.speaker}: {utterance.text}")
        
        return "\n".join(lines)
    
    def get_meeting_date(self) -> Optional[datetime]:
        """Get the meeting date."""
        return self.scheduled_start or self.recording_start or self.created_at


class TranscriptParser:
    """Parser for meeting transcripts from various sources."""
    
    @staticmethod
    def parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string."""
        if not value:
            return None
        try:
            # Handle Z suffix
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None
    
    def parse_fathom_json(self, data: Dict[str, Any]) -> List[Meeting]:
        """
        Parse Fathom API JSON response.
        
        Handles both single meeting and multiple meetings (items array) format.
        """
        meetings = []
        
        # Handle items array format
        items = data.get("items", [data] if "transcript" in data else [])
        
        for item in items:
            meeting = self._parse_fathom_meeting(item)
            if meeting:
                meetings.append(meeting)
        
        return meetings
    
    def _parse_fathom_meeting(self, data: Dict[str, Any]) -> Optional[Meeting]:
        """Parse a single meeting from Fathom JSON."""
        
        # Parse participants from calendar_invitees
        participants = []
        raw_invitees = data.get("calendar_invitees") or []
        for invitee in raw_invitees:
            participant = Participant(
                name=invitee.get("name", "Unknown"),
                email=invitee.get("email", ""),
                is_external=invitee.get("is_external", False),
                team=invitee.get("team"),
            )
            participants.append(participant)
        
        # Add recorder if not in invitees
        recorded_by = data.get("recorded_by") or {}
        if recorded_by:
            recorder_email = recorded_by.get("email", "")
            if not any(p.email == recorder_email for p in participants):
                participants.append(Participant(
                    name=recorded_by.get("name", "Unknown"),
                    email=recorder_email,
                    is_external=False,
                    team=recorded_by.get("team"),
                ))
        
        # Parse transcript utterances
        utterances = []
        raw_transcript = data.get("transcript") or []
        for idx, entry in enumerate(raw_transcript, start=1):
            speaker_data = entry.get("speaker", {})
            
            utterance = Utterance(
                utterance_id=f"u_{idx:04d}",
                speaker=speaker_data.get("display_name", "Unknown") if isinstance(speaker_data, dict) else str(speaker_data),
                speaker_email=speaker_data.get("matched_calendar_invitee_email") if isinstance(speaker_data, dict) else None,
                text=entry.get("text", ""),
                timestamp=entry.get("timestamp"),
                order_index=idx,
            )
            utterances.append(utterance)
        
        # Parse action items
        action_items = []
        raw_action_items = data.get("action_items") or []
        for item in raw_action_items:
            assignee = item.get("assignee", {})
            action = ActionItem(
                description=item.get("description", ""),
                assignee_name=assignee.get("name") if assignee else None,
                assignee_email=assignee.get("email") if assignee else None,
                completed=item.get("completed", False),
                timestamp=item.get("recording_timestamp"),
            )
            action_items.append(action)
        
        meeting = Meeting(
            title=data.get("title") or data.get("meeting_title", "Untitled Meeting"),
            url=data.get("url"),
            created_at=self.parse_datetime(data.get("created_at")),
            scheduled_start=self.parse_datetime(data.get("scheduled_start_time")),
            scheduled_end=self.parse_datetime(data.get("scheduled_end_time")),
            recording_start=self.parse_datetime(data.get("recording_start_time")),
            recording_end=self.parse_datetime(data.get("recording_end_time")),
            participants=participants,
            utterances=utterances,
            action_items=action_items,
            summary=data.get("default_summary"),
            share_url=data.get("share_url"),
        )
        
        return meeting
    
    def parse_plain_text(self, content: str) -> Meeting:
        """Parse plain text transcript format."""
        lines = content.strip().split("\n")
        utterances = []
        
        for idx, line in enumerate(lines, start=1):
            speaker = "Unknown"
            text = line.strip()
            
            if ":" in line:
                parts = line.split(":", 1)
                if len(parts[0]) <= 40:  # Reasonable speaker name length
                    speaker = parts[0].strip()
                    text = parts[1].strip()
            
            utterances.append(Utterance(
                utterance_id=f"u_{idx:04d}",
                speaker=speaker,
                speaker_email=None,
                text=text,
                timestamp=None,
                order_index=idx,
            ))
        
        return Meeting(
            title="Uploaded Transcript",
            url=None,
            created_at=datetime.now(),
            scheduled_start=None,
            scheduled_end=None,
            recording_start=None,
            recording_end=None,
            participants=[],
            utterances=utterances,
            action_items=[],
            summary=None,
            share_url=None,
        )
    
    def parse_file(self, file_path: Path) -> List[Meeting]:
        """Parse a transcript file (JSON or plain text)."""
        content = file_path.read_text(encoding="utf-8")
        
        if file_path.suffix.lower() == ".json":
            data = json.loads(content)
            return self.parse_fathom_json(data)
        else:
            return [self.parse_plain_text(content)]
    
    def parse_content(self, content: Union[str, bytes], filename: str = "") -> List[Meeting]:
        """Parse transcript content (auto-detect format)."""
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        
        # Try JSON first
        if filename.endswith(".json") or content.strip().startswith("{"):
            try:
                data = json.loads(content)
                return self.parse_fathom_json(data)
            except json.JSONDecodeError:
                pass
        
        # Fall back to plain text
        return [self.parse_plain_text(content)]
    
    @staticmethod
    def extract_meeting_context(meetings: List[Meeting]) -> Dict[str, Any]:
        """
        Extract context information from meetings for SOW generation.
        """
        all_participants = []
        client_domains = set()
        vendor_domains = set()
        titles = []
        
        for meeting in meetings:
            titles.append(meeting.title)
            
            for p in meeting.participants:
                if "@" in p.email:
                    domain = p.email.split("@")[1]
                    if p.is_external:
                        client_domains.add(domain)
                    else:
                        vendor_domains.add(domain)
                all_participants.append(p.name)
        
        return {
            "title": " + ".join(titles[:3]) + (f" (+{len(titles)-3} more)" if len(titles) > 3 else ""),
            "participants": list(set(all_participants)),
            "client_domains": list(client_domains),
            "vendor_domains": list(vendor_domains),
            "meeting_count": len(meetings),
        }
    
    @staticmethod
    def combine_utterances(meetings: List[Meeting]) -> List[Dict[str, Any]]:
        """Combine utterances from multiple meetings into a single list."""
        all_utterances = []
        
        for meeting in meetings:
            # Add meeting separator if not first
            if all_utterances:
                all_utterances.append({
                    "utterance_id": f"sep_{len(all_utterances)}",
                    "speaker": "[Meeting Separator]",
                    "text": f"--- Meeting: {meeting.title} ---",
                    "order_index": len(all_utterances) + 1,
                })
            
            for u in meeting.utterances:
                u_dict = u.to_dict()
                u_dict["order_index"] = len(all_utterances) + 1
                all_utterances.append(u_dict)
        
        return all_utterances
