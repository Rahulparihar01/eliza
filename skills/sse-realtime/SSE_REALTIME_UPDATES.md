# SSE Real-Time Updates Guide

> **Purpose:** This skill ensures Server-Sent Events (SSE) are implemented correctly for streaming progress updates from async operations to the frontend.

---

## Quick Reference

```python
# ✅ CORRECT SSE Endpoint Pattern
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse
import asyncio
import json

@router.get("/{entity_id}/stream")
async def stream_updates(
    request: Request,
    entity_id: str,
    token: str = Query(..., description="JWT token (EventSource doesn't support headers)")
):
    """Stream real-time updates using Server-Sent Events."""
    
    # 1. Verify token (EventSource can't send Authorization header)
    current_user = await verify_token(token)
    
    # 2. Verify access to entity
    entity = get_entity(entity_id)
    if entity.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    async def event_generator():
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break
            
            # Get latest events
            events = get_new_events(entity_id, last_event_id)
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"
            
            # Check for completion
            if is_complete(entity_id):
                yield f"data: {json.dumps({'event_type': 'completed'})}\n\n"
                break
            
            await asyncio.sleep(1)  # Poll interval
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
```

---

## Overview

SSE provides a unidirectional stream from server to client for real-time progress updates during long-running async operations. The Eliza Platform uses a database-polling pattern where Celery workers write telemetry events to the database and the SSE endpoint reads and streams them to the frontend.

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React)                        │
│  EventSource → onmessage → updateState                      │
└─────────────────────────────────────────────────────────────┘
                              ↑ SSE Stream
                              │ data: {...}\n\n
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI SSE Endpoint                      │
│  StreamingResponse(event_generator())                       │
└─────────────────────────────────────────────────────────────┘
                              ↑ Polls Database
┌─────────────────────────────────────────────────────────────┐
│                     Telemetry Table                          │
│  Celery tasks write events → SSE endpoint reads events      │
└─────────────────────────────────────────────────────────────┘
                              ↑ Writes Events
┌─────────────────────────────────────────────────────────────┐
│                      Celery Worker                           │
│  Task execution → add_telemetry_event()                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Critical Rules

### Rule 1: Pass Token as Query Parameter

**Context:** The browser `EventSource` API does not support custom headers. JWT tokens cannot be sent via the `Authorization` header, so they must be passed as a query parameter.

```python
# ❌ WRONG: Expecting Authorization header (EventSource can't send it)
@router.get("/{entity_id}/stream")
async def stream_updates(
    entity_id: str,
    current_user = Depends(require_permission(["feature:read"]))  # Header-based auth
):
    ...

# ✅ CORRECT: Accept token as query parameter
@router.get("/{entity_id}/stream")
async def stream_updates(
    entity_id: str,
    token: str = Query(..., description="JWT access token")
):
    payload = await auth_service.verify_token(token)
    ...
```

### Rule 2: Always Check for Client Disconnect

**Context:** Without disconnect detection, the server continues generating events after the client closes the connection, wasting resources and potentially causing memory leaks.

```python
# ❌ WRONG: No disconnect check — runs forever if client leaves
async def event_generator():
    while True:
        events = get_new_events(entity_id)
        for event in events:
            yield f"data: {json.dumps(event)}\n\n"
        await asyncio.sleep(1)

# ✅ CORRECT: Check for disconnect on every iteration
async def event_generator():
    while True:
        if await request.is_disconnected():
            break
        events = get_new_events(entity_id)
        for event in events:
            yield f"data: {json.dumps(event)}\n\n"
        await asyncio.sleep(1)
```

### Rule 3: Send Terminal Events and Close the Stream

**Context:** The stream must explicitly send a terminal event (`completed` or `failed`) and then `break` out of the generator. Without this, the client never knows the operation finished and the connection stays open indefinitely.

```python
# ❌ WRONG: No terminal event — client polls forever
if current_status == YourStatus.COMPLETED:
    break  # Client never receives a completion signal

# ✅ CORRECT: Send terminal event, then close
if current_status in [YourStatus.COMPLETED, YourStatus.FAILED]:
    terminal_event = {
        "event_type": "completed" if current_status == YourStatus.COMPLETED else "failed",
        "status": current_status.value,
        "progress_percentage": 100.0 if current_status == YourStatus.COMPLETED else None,
        "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    }
    yield f"data: {json.dumps(terminal_event)}\n\n"
    break
```

### Rule 4: Set Proper SSE Response Headers

**Context:** Without these headers, nginx/proxies may buffer the entire response (defeating streaming), browsers may cache the response, or connections may drop prematurely.

```python
# ❌ WRONG: Missing critical headers
return StreamingResponse(event_generator(), media_type="text/event-stream")

# ✅ CORRECT: All required SSE headers
return StreamingResponse(
    event_generator(),
    media_type="text/event-stream",
    headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Disable nginx buffering
        "Access-Control-Allow-Origin": "*"  # If needed for CORS
    }
)
```

---

## Patterns

### Event Types Reference

```python
class YourEventType(str, Enum):
    """Standard event types for telemetry."""
    
    # Lifecycle events
    STARTED = "started"           # Processing started
    COMPLETED = "completed"       # Processing completed successfully
    FAILED = "failed"            # Processing failed
    
    # Progress events
    PROGRESS = "progress"         # General progress update
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    
    # Agent events
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_ERROR = "agent_error"
    
    # Tool events
    TOOL_CALLED = "tool_called"
    TOOL_RESULT = "tool_result"
    TOOL_ERROR = "tool_error"
    
    # System events
    INFO = "info"                 # Informational message
    WARNING = "warning"           # Warning message
    ERROR = "error"              # Error occurred
    HEARTBEAT = "heartbeat"      # Keep-alive
```

### SSE Protocol Details

Each SSE message follows a specific wire format:

```
data: {"event_type": "progress", "progress_percentage": 50}\n\n
```

- Each message starts with `data: `
- JSON payload follows
- Double newline `\n\n` terminates the message

Multiple lines:

```
data: {"line1": "value"}\n
data: {"line2": "value"}\n\n
```

Event names (optional):

```
event: custom_event\n
data: {"payload": "here"}\n\n
```

### Writing Telemetry Events from Services

Use this pattern in your service layer to write events that the SSE endpoint will stream.

```python
# src/services/your_service.py
from datetime import datetime, timezone
from src.models.your_feature import YourEvent, YourEventType

class YourService:
    
    def add_telemetry_event(
        self,
        entity_id: str,
        event_type: YourEventType,
        message: str = None,
        user_message: str = None,
        agent_name: str = None,
        tool_name: str = None,
        stage_name: str = None,
        progress_percentage: float = None,
        data: dict = None,
        error_details: dict = None,
        duration_ms: int = None
    ) -> YourEvent:
        """
        Add a telemetry event for streaming to frontend.
        
        Args:
            entity_id: Entity this event belongs to
            event_type: Type of event (started, progress, completed, etc.)
            message: Internal message (for logging)
            user_message: User-friendly message (shown in UI)
            agent_name: Name of agent if applicable
            tool_name: Name of tool if applicable
            stage_name: Current processing stage
            progress_percentage: Progress (0-100)
            data: Additional data payload
            error_details: Error information if failed
            duration_ms: Duration of operation
        """
        event = YourEvent(
            entity_id=entity_id,
            event_type=event_type.value,
            message=message,
            user_message=user_message,
            agent_name=agent_name,
            tool_name=tool_name,
            stage_name=stage_name,
            progress_percentage=progress_percentage,
            data=data,
            error_details=error_details,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc)
        )
        
        self.db.add(event)
        self.db.commit()
        
        return event
```

### Using Telemetry in Celery Tasks

```python
# src/tasks/your_tasks.py

@celery_app.task(bind=True)
def process_your_feature(self, entity_id: str, user_id: int, customer_id: str):
    """Process with telemetry updates."""
    
    db = get_session()
    try:
        service = YourService(db)
        
        # Stage 1: Started
        service.add_telemetry_event(
            entity_id=entity_id,
            event_type=YourEventType.STARTED,
            user_message="Starting processing...",
            stage_name="Initialization",
            progress_percentage=0.0
        )
        
        # Stage 2: Processing
        service.add_telemetry_event(
            entity_id=entity_id,
            event_type=YourEventType.AGENT_STARTED,
            agent_name="Data Analysis Agent",
            user_message="Analyzing data...",
            progress_percentage=25.0
        )
        
        # Do actual work...
        
        # Stage 3: Tool execution
        service.add_telemetry_event(
            entity_id=entity_id,
            event_type=YourEventType.TOOL_CALLED,
            tool_name="DocumentSearchTool",
            user_message="Searching documents...",
            progress_percentage=50.0
        )
        
        # More work...
        
        # Stage 4: Completion
        service.add_telemetry_event(
            entity_id=entity_id,
            event_type=YourEventType.COMPLETED,
            user_message="Processing completed successfully",
            progress_percentage=100.0
        )
        
    finally:
        db.close()
```

### Deployment Configuration

Nginx must be configured to disable buffering for SSE endpoints:

```nginx
# Disable buffering for SSE endpoints
location /api/v1/your-feature/ {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 86400s;  # 24 hours
}
```

Docker Compose should use a single worker or async workers for SSE:

```yaml
app:
  environment:
    - WORKERS=1  # SSE works best with single worker or async workers
```

---

## Complete Template

```python
"""
Real-time SSE streaming for [Feature Name].
"""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import asyncio
import json
import uuid

from src.models import get_db
from src.models.your_feature import YourEntity, YourStatus, YourEvent
from src.services.your_service import YourService
from src.services.auth_service import auth_service
from src.core.auth_context import CurrentUserContext
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.API)

router = APIRouter(prefix="/v1/your-feature", tags=["Your Feature"])


@router.get(
    "/{entity_id}/stream",
    summary="Stream real-time updates",
    description="Stream telemetry events using Server-Sent Events (SSE)."
)
async def stream_telemetry(
    request: Request,
    entity_id: str,
    token: str = Query(..., description="JWT access token"),
    db: Session = Depends(get_db)
):
    """
    Stream real-time telemetry events using SSE.
    
    Note: Token passed as query param because EventSource doesn't support headers.
    
    Events sent:
    - progress: Progress updates with percentage
    - agent_started/completed: Agent lifecycle events
    - tool_called: Tool execution events
    - heartbeat: Keep-alive every 15 seconds
    - completed/failed: Terminal events (closes stream)
    """
    # ========================================
    # 1. Authentication (token in query param)
    # ========================================
    try:
        payload = await auth_service.verify_token(token)
        user_id = int(payload.get("sub"))
        user = await auth_service.get_user_by_id(user_id)
        
        if not user:
            raise HTTPException(status_code=403, detail="User not found")
        
        current_user = CurrentUserContext(
            user_id=user.id,
            customer_id=user.customer_id,
            is_superuser=user.is_superuser,
            # ... other fields
        )
    except Exception as e:
        logger.error("sse_auth_failed", error=str(e))
        raise HTTPException(status_code=403, detail="Invalid or expired token")
    
    # ========================================
    # 2. Verify Entity Access
    # ========================================
    service = YourService(db)
    entity = service.get(entity_id)
    
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    if entity.user_id != current_user.user_id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # ========================================
    # 3. Event Generator
    # ========================================
    async def event_generator():
        """Generate SSE events from telemetry."""
        last_event_id = 0
        idle_cycles = 0
        poll_interval = 1.0  # seconds
        heartbeat_interval = 15  # cycles (15 seconds)
        
        logger.info(
            "sse_stream_started",
            entity_id=entity_id,
            user_id=current_user.user_id
        )
        
        while True:
            # Check for client disconnect
            if await request.is_disconnected():
                logger.debug("sse_client_disconnected", entity_id=entity_id)
                break
            
            # Fetch new events
            events = service.get_events(
                entity_id=entity_id,
                after_id=last_event_id,
                limit=100
            )
            
            # Send events to client
            for event in events:
                event_data = {
                    "event_id": f"event-{event.id}",
                    "event_type": event.event_type,
                    "agent_name": event.agent_name,
                    "tool_name": event.tool_name,
                    "stage_name": event.stage_name,
                    "message": event.message,
                    "user_message": event.user_message,
                    "progress_percentage": event.progress_percentage,
                    "data": event.data,
                    "timestamp": event.timestamp.isoformat() if event.timestamp else datetime.utcnow().isoformat()
                }
                
                yield f"data: {json.dumps(event_data)}\n\n"
                last_event_id = event.id
                idle_cycles = 0
            
            # Check entity status for completion
            latest_entity = service.get(entity_id)
            if latest_entity:
                current_status = latest_entity.status
                
                # Send terminal event and close stream
                if current_status in [YourStatus.COMPLETED, YourStatus.FAILED]:
                    terminal_event = {
                        "event_id": f"terminal-{uuid.uuid4().hex}",
                        "event_type": "completed" if current_status == YourStatus.COMPLETED else "failed",
                        "status": current_status.value,
                        "message": "Processing completed" if current_status == YourStatus.COMPLETED else latest_entity.error_message,
                        "progress_percentage": 100.0 if current_status == YourStatus.COMPLETED else None,
                        "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                    }
                    yield f"data: {json.dumps(terminal_event)}\n\n"
                    logger.info(
                        "sse_stream_terminal",
                        entity_id=entity_id,
                        status=current_status.value
                    )
                    break
            
            # Send heartbeat to keep connection alive
            idle_cycles += 1
            if idle_cycles >= heartbeat_interval:
                heartbeat = {
                    "event_id": f"heartbeat-{uuid.uuid4().hex}",
                    "event_type": "heartbeat",
                    "status": current_status.value if latest_entity else "unknown",
                    "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
                }
                yield f"data: {json.dumps(heartbeat)}\n\n"
                idle_cycles = 0
            
            # Wait before next poll
            await asyncio.sleep(poll_interval)
    
    # ========================================
    # 4. Return StreamingResponse
    # ========================================
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Access-Control-Allow-Origin": "*"  # If needed for CORS
        }
    )
```

---

## Frontend Implementation

### React Hook for SSE

```typescript
// hooks/useSSEStream.ts
import { useEffect, useRef, useState, useCallback } from 'react';

interface SSEEvent {
  event_id: string;
  event_type: string;
  message?: string;
  user_message?: string;
  progress_percentage?: number;
  agent_name?: string;
  tool_name?: string;
  stage_name?: string;
  timestamp: string;
  data?: any;
}

interface UseSSEStreamOptions {
  entityId: string;
  token: string;
  onEvent?: (event: SSEEvent) => void;
  onComplete?: () => void;
  onError?: (error: Error) => void;
  enabled?: boolean;
}

export function useSSEStream({
  entityId,
  token,
  onEvent,
  onComplete,
  onError,
  enabled = true,
}: UseSSEStreamOptions) {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const connect = useCallback(() => {
    if (!enabled || !entityId || !token) return;

    // Build SSE URL with token in query param
    const url = `${import.meta.env.VITE_API_URL}/v1/your-feature/${entityId}/stream?token=${encodeURIComponent(token)}`;
    
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsConnected(true);
      console.log('SSE connected', entityId);
    };

    eventSource.onmessage = (event) => {
      try {
        const data: SSEEvent = JSON.parse(event.data);
        
        // Update events list
        setEvents((prev) => [...prev, data]);
        
        // Update progress
        if (data.progress_percentage !== undefined) {
          setProgress(data.progress_percentage);
        }
        
        // Update stage
        if (data.stage_name) {
          setCurrentStage(data.stage_name);
        }
        
        // Call event handler
        onEvent?.(data);
        
        // Handle terminal events
        if (data.event_type === 'completed' || data.event_type === 'failed') {
          eventSource.close();
          setIsConnected(false);
          onComplete?.();
        }
      } catch (e) {
        console.error('Failed to parse SSE event', e);
      }
    };

    eventSource.onerror = (error) => {
      console.error('SSE error', error);
      setIsConnected(false);
      onError?.(new Error('SSE connection failed'));
      eventSource.close();
    };

    return () => {
      eventSource.close();
      setIsConnected(false);
    };
  }, [entityId, token, enabled, onEvent, onComplete, onError]);

  useEffect(() => {
    const cleanup = connect();
    return cleanup;
  }, [connect]);

  // Disconnect function
  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      setIsConnected(false);
    }
  }, []);

  return {
    events,
    isConnected,
    progress,
    currentStage,
    disconnect,
  };
}
```

### Usage in Component

```typescript
// components/ProcessingStatus.tsx
import { useSSEStream } from '../hooks/useSSEStream';
import { useAuthStore } from '../stores/authStore';

interface ProcessingStatusProps {
  entityId: string;
  onComplete: () => void;
}

export function ProcessingStatus({ entityId, onComplete }: ProcessingStatusProps) {
  const { token } = useAuthStore();
  
  const {
    events,
    isConnected,
    progress,
    currentStage,
  } = useSSEStream({
    entityId,
    token,
    onComplete,
    onError: (error) => {
      console.error('Stream error:', error);
    },
  });

  return (
    <div className="space-y-4">
      {/* Connection Status */}
      <div className="flex items-center gap-2">
        <div 
          className={`w-2 h-2 rounded-full ${
            isConnected ? 'bg-green-500' : 'bg-gray-400'
          }`} 
        />
        <span className="text-sm text-muted">
          {isConnected ? 'Connected' : 'Disconnected'}
        </span>
      </div>

      {/* Progress Bar */}
      <div className="space-y-1">
        <div className="flex justify-between text-sm">
          <span>{currentStage || 'Initializing...'}</span>
          <span>{progress.toFixed(0)}%</span>
        </div>
        <div className="h-2 bg-surface-2 rounded-full overflow-hidden">
          <div 
            className="h-full bg-brand transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Event Log */}
      <div className="max-h-60 overflow-y-auto space-y-2">
        {events.map((event) => (
          <div 
            key={event.event_id}
            className="text-sm p-2 bg-surface-2 rounded"
          >
            <div className="flex items-center gap-2">
              <EventIcon type={event.event_type} />
              <span className="text-text">
                {event.user_message || event.message}
              </span>
            </div>
            <div className="text-xs text-muted mt-1">
              {new Date(event.timestamp).toLocaleTimeString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EventIcon({ type }: { type: string }) {
  switch (type) {
    case 'agent_started':
      return <span>🤖</span>;
    case 'agent_completed':
      return <span>✅</span>;
    case 'tool_called':
      return <span>🔧</span>;
    case 'progress':
      return <span>📊</span>;
    case 'error':
      return <span>❌</span>;
    case 'completed':
      return <span>🎉</span>;
    default:
      return <span>📝</span>;
  }
}
```

---

## Testing

### Manual Testing

```bash
# Get auth token first
TOKEN=$(curl -s -X POST http://localhost:5001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password"}' \
  | jq -r '.access_token')

# Stream events
curl -N "http://localhost:5001/api/v1/your-feature/entity-123/stream?token=$TOKEN"
```

### Unit Tests

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

def test_sse_stream_events():
    """Test SSE endpoint streams events correctly."""
    with patch('src.services.auth_service.verify_token') as mock_auth:
        mock_auth.return_value = {"sub": "1"}
        
        with TestClient(app) as client:
            with client.stream(
                "GET",
                "/v1/your-feature/test-entity/stream?token=test-token"
            ) as response:
                events = []
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        event = json.loads(line[6:])
                        events.append(event)
                        if event["event_type"] in ["completed", "failed"]:
                            break
                
                assert len(events) > 0
                assert events[-1]["event_type"] in ["completed", "failed"]
```

---

## Checklist

- [ ] Token passed as query parameter (EventSource limitation)
- [ ] Token validation before starting stream
- [ ] Entity access authorization checked
- [ ] Client disconnect detection (`request.is_disconnected()`)
- [ ] Heartbeat events sent periodically
- [ ] Terminal events (completed/failed) close the stream
- [ ] Proper SSE headers set (Cache-Control, X-Accel-Buffering)
- [ ] Telemetry events written from Celery tasks
- [ ] Frontend EventSource hook handles reconnection
- [ ] Error handling on both backend and frontend
- [ ] Container rebuilt: `docker-compose build app`

---

## References

- `src/api/routes/` — Existing SSE endpoint implementations
- `src/services/` — Service layer with `add_telemetry_event()` methods
- `src/tasks/` — Celery tasks that write telemetry events
- `frontend/src/hooks/` — Frontend SSE hooks
- `skills/celery-tasks/` — Celery task patterns (telemetry event writing)
- `skills/fastapi-endpoints/` — FastAPI endpoint patterns
- [MDN EventSource API](https://developer.mozilla.org/en-US/docs/Web/API/EventSource) — Browser EventSource reference
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse) — FastAPI streaming docs
