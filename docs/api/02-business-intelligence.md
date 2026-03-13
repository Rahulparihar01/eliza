# Business Intelligence API

**Base Path:** `/api/v1/bi`

**Required Permission:** `bi:read` (for reading), `bi:write` (for creating questions)

## Overview

The Business Intelligence Q&A system allows users to ask natural language questions about business data. The system:
1. Enriches the question using AI task analysis
2. Retrieves relevant data from vector stores and databases
3. Generates comprehensive analysis using CrewAI agents
4. Provides real-time progress updates via Server-Sent Events (SSE)

## Key Concepts

- **Question**: A natural language business question submitted by a user
- **Enriched Prompt**: AI-enhanced version of the question with context and intent analysis
- **Analysis Session**: A CrewAI flow execution that answers the question
- **Telemetry**: Real-time progress events from agent execution
- **Company HR Dataset**: Scopes data to a specific company (multi-company support)

## Endpoints

### POST /api/v1/bi/questions

Submit a business intelligence question.

**Requires Permission:** `bi:write`

**Request:**
```json
{
  "question": "What are the top skills among our machine learning engineers?",
  "company_hr_dataset": "caylent",
  "session_id": "session_123",
  "metadata": {
    "source": "web_app",
    "user_context": "quarterly_review"
  }
}
```

**Parameters:**
- `question` (string, required) - Natural language question
- `company_hr_dataset` (string, optional) - Company to query (defaults to system default)
- `session_id` (string, optional) - Group related questions together
- `metadata` (object, optional) - Additional context

**Response:** `202 Accepted`
```json
{
  "question_id": "bi_q_abc123def456",
  "status": "pending",
  "message": "Question submitted successfully and is being processed",
  "task_id": "celery_task_789xyz"
}
```

**Processing Stages:**
1. `pending` → Question queued
2. `enriching` → AI is analyzing question intent
3. `analyzing` → CrewAI agents are working
4. `completed` → Analysis complete
5. `failed` → Error occurred

**Errors:**
- `400` - Invalid question format
- `403` - No access to specified company dataset
- `503` - Background workers unavailable

---

### GET /api/v1/bi/questions/{question_id}

Get detailed question information with full results.

**Requires Permission:** `bi:read`

**Response:** `200 OK`
```json
{
  "id": 1,
  "question_id": "bi_q_abc123def456",
  "user_id": 1,
  "customer_id": "eliza",
  "session_id": "session_123",
  "original_question": "What are the top skills among our machine learning engineers?",
  "status": "completed",
  "enriched_prompt": {
    "prompt_id": "prompt_xyz789",
    "intent_type": "skill_analysis",
    "complexity": "medium",
    "confidence_score": 0.92
  },
  "analysis_session": {
    "session_id": "analysis_session_456",
    "flow_name": "DataAnalysisFlow",
    "status": "completed"
  },
  "result": {
    "answer": "Based on analysis of 45 ML engineers:\n\nTop Skills:\n1. Python (95%)\n2. TensorFlow (78%)\n3. PyTorch (72%)\n4. Machine Learning (89%)\n5. Deep Learning (67%)\n...",
    "data_sources": ["hr_documents", "resumes", "skills_database"],
    "confidence": 0.88,
    "visualizations": [...],
    "recommendations": [...]
  },
  "error_message": null,
  "question_metadata": {...},
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:02:30Z",
  "completed_at": "2024-01-15T10:02:30Z"
}
```

**Errors:**
- `404` - Question not found
- `403` - Not authorized to access this question

---

### GET /api/v1/bi/questions/{question_id}/status

Get quick status update on question processing.

**Requires Permission:** `bi:read`

**Response:** `200 OK`
```json
{
  "question_id": "bi_q_abc123def456",
  "status": "analyzing",
  "progress_percentage": 50.0,
  "current_stage": "Data Analysis",
  "error_message": null
}
```

**Status to Progress Mapping:**
- `pending`: 0%
- `enriching`: 25%
- `analyzing`: 50%
- `completed`: 100%
- `failed`: 0%

---

### GET /api/v1/bi/questions/{question_id}/telemetry

Stream real-time telemetry events using Server-Sent Events (SSE).

**Requires Permission:** `bi:read`

**Query Parameters:**
- `token` (string, required) - JWT access token (EventSource doesn't support headers)

**Example:**
```javascript
const token = localStorage.getItem('auth_token');
const eventSource = new EventSource(
  `http://localhost:5001/api/v1/bi/questions/${questionId}/telemetry?token=${token}`
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.event_type) {
    case 'agent_started':
      console.log(`Agent ${data.agent_name} started`);
      break;
    case 'tool_execution':
      console.log(`Tool: ${data.tool_name} - ${data.user_message}`);
      break;
    case 'stage_completed':
      console.log(`Stage ${data.stage_name} completed`);
      break;
    case 'completed':
      console.log('Analysis complete!');
      eventSource.close();
      break;
    case 'failed':
      console.error('Analysis failed:', data.message);
      eventSource.close();
      break;
  }
};
```

**Event Format:**
```json
{
  "event_id": "telemetry-123",
  "telemetry_id": 123,
  "event_type": "tool_execution",
  "agent_name": "Research Specialist",
  "tool_name": "DocumentSearchTool",
  "stage_name": "data_retrieval",
  "message": "Searching for ML engineer skills data",
  "user_message": "Retrieving relevant documents...",
  "progress_percentage": 35.0,
  "timestamp": "2024-01-15T10:01:15Z"
}
```

**Event Types:**
- `flow_started` - CrewAI flow began
- `agent_started` - Agent began working
- `tool_execution` - Tool was called
- `tool_result` - Tool returned results
- `stage_completed` - Flow stage finished
- `completed` - Analysis complete
- `failed` - Analysis failed
- `heartbeat` - Keep-alive ping (every 15s)

---

### GET /api/v1/bi/questions/{question_id}/result

Get final analysis result for a completed question.

**Requires Permission:** `bi:read`

**Response:** `200 OK`
```json
{
  "answer": "Detailed analysis answer...",
  "data_sources": ["hr_documents", "employee_database"],
  "confidence": 0.88,
  "visualizations": [
    {
      "type": "bar_chart",
      "title": "Top Skills Distribution",
      "data": {...}
    }
  ],
  "recommendations": [
    "Consider upskilling team in PyTorch",
    "Strong Python foundation across team"
  ],
  "related_questions": [
    "What certifications do our ML engineers have?",
    "How do our ML skills compare to industry benchmarks?"
  ]
}
```

**Errors:**
- `404` - Result not yet available or question not found

---

### GET /api/v1/bi/questions

List business intelligence questions with pagination.

**Requires Permission:** `bi:read`

**Query Parameters:**
- `session_id` (string, optional) - Filter by session
- `status` (string, optional) - Filter by status (`pending`, `enriching`, `analyzing`, `completed`, `failed`)
- `page` (integer, default: 1) - Page number (min: 1)
- `page_size` (integer, default: 20) - Items per page (min: 1, max: 100)

**Response:** `200 OK`
```json
{
  "questions": [
    {
      "id": 1,
      "question_id": "bi_q_abc123",
      "original_question": "What are the top skills?",
      "status": "completed",
      "created_at": "2024-01-15T10:00:00Z",
      "completed_at": "2024-01-15T10:02:30Z"
    },
    ...
  ],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```

---

### GET /api/v1/bi/questions/{question_id}/timeline

Get complete execution timeline with all agent activity.

**Requires Permission:** `bi:read`

**Response:** `200 OK`
```json
{
  "question_id": "bi_q_abc123",
  "status": "completed",
  "created_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:02:30Z",
  "enriched_prompt": {
    "prompt_id": "prompt_xyz",
    "original_input": "What are the top skills?",
    "enriched_prompt": "Analyze the distribution of technical skills...",
    "intent_type": "skill_analysis",
    "complexity": "medium",
    "confidence_score": 0.92,
    "quality_score": 0.88
  },
  "tool_executions": [
    {
      "execution_id": "exec_123",
      "tool_name": "DocumentSearchTool",
      "agent_name": "Research Specialist",
      "tool_input": {"query": "machine learning engineers skills"},
      "tool_output": {"results_count": 25, "chunks": [...]},
      "status": "completed",
      "duration_ms": 1250,
      "started_at": "2024-01-15T10:00:30Z",
      "completed_at": "2024-01-15T10:00:31.25Z"
    },
    ...
  ],
  "agent_responses": [
    {
      "response_id": "resp_456",
      "agent_name": "Research Specialist",
      "stage_name": "data_retrieval",
      "input_prompt": "Retrieve ML engineer skills data",
      "response_text": "Found 45 ML engineers with skill data",
      "reasoning": "Searched documents and employee database",
      "confidence_score": 0.9,
      "duration_ms": 2500,
      "created_at": "2024-01-15T10:00:31Z"
    },
    ...
  ],
  "telemetry_events": [...]
}
```

**Use Cases:**
- Debugging failed analyses
- Showing users what the system is doing
- Performance optimization
- Audit trails

---

### GET /api/v1/bi/sessions/{session_id}/tool-executions

Get tool executions for an analysis session.

**Requires Permission:** `bi:read`

**Query Parameters:**
- `tool_name` (string, optional) - Filter by specific tool

**Response:** `200 OK`
```json
{
  "session_id": "analysis_session_456",
  "tool_executions": [...],
  "total": 15
}
```

---

### GET /api/v1/bi/sessions/{session_id}/agent-responses

Get agent responses for an analysis session.

**Requires Permission:** `bi:read`

**Query Parameters:**
- `agent_name` (string, optional) - Filter by agent
- `stage_name` (string, optional) - Filter by stage

**Response:** `200 OK`
```json
{
  "session_id": "analysis_session_456",
  "agent_responses": [...],
  "total": 8
}
```

---

### GET /api/v1/bi/prompts

List enriched prompts (admin only).

**Requires Permission:** `bi:admin`

**Query Parameters:**
- `page` (integer, default: 1)
- `page_size` (integer, default: 20, max: 100)

**Response:** `200 OK`
```json
{
  "prompts": [...],
  "total": 500,
  "page": 1,
  "page_size": 20,
  "total_pages": 25
}
```

---

### GET /api/v1/bi/health

Health check for BI system components.

**No authentication required**

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "components": {
    "database": "healthy",
    "redis": "healthy",
    "celery_workers": "healthy",
    "vector_service": "healthy",
    "crewai": "healthy"
  },
  "details": {
    "redis": {
      "latency_ms": 2.5,
      "queue_depth": 3
    },
    "celery_workers": {
      "workers": ["celery@worker1", "celery@worker2"]
    }
  },
  "timestamp": "2024-01-15T12:00:00Z"
}
```

**Statuses:**
- `healthy` - All components operational
- `degraded` - Some components have issues
- `unhealthy` - Critical components down

---

## Common Workflows

### Submit Question and Poll Status

```python
import requests
import time

# 1. Submit question
response = requests.post(
    'http://localhost:5001/api/v1/bi/questions',
    headers={'Authorization': f'Bearer {token}'},
    json={
        'question': 'What are our top skills?',
        'company_hr_dataset': 'caylent'
    }
)
question_id = response.json()['question_id']

# 2. Poll status until complete
while True:
    status_response = requests.get(
        f'http://localhost:5001/api/v1/bi/questions/{question_id}/status',
        headers={'Authorization': f'Bearer {token}'}
    )
    status_data = status_response.json()
    
    print(f"Status: {status_data['status']} - {status_data['progress_percentage']}%")
    
    if status_data['status'] in ['completed', 'failed']:
        break
    
    time.sleep(2)

# 3. Get results
if status_data['status'] == 'completed':
    result = requests.get(
        f'http://localhost:5001/api/v1/bi/questions/{question_id}/result',
        headers={'Authorization': f'Bearer {token}'}
    )
    print(result.json()['answer'])
```

### Real-Time Progress with SSE

```javascript
async function askQuestion(question) {
  // 1. Submit question
  const response = await fetch('/api/v1/bi/questions', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ question })
  });
  
  const { question_id } = await response.json();
  
  // 2. Listen for real-time updates
  const eventSource = new EventSource(
    `/api/v1/bi/questions/${question_id}/telemetry?token=${token}`
  );
  
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    // Update UI with progress
    updateProgress(data);
    
    if (data.event_type === 'completed') {
      eventSource.close();
      // Fetch final results
      fetchResults(question_id);
    } else if (data.event_type === 'failed') {
      eventSource.close();
      showError(data.message);
    }
  };
  
  eventSource.onerror = (error) => {
    console.error('SSE error:', error);
    eventSource.close();
  };
}
```

## Multi-Company Support

The BI system supports querying data from multiple companies within a single customer organization.

**Setting Default Company:**

System settings define the default `company_hr_dataset`. If not specified in the request, this default is used.

**Querying Specific Company:**

```json
{
  "question": "What are the skill gaps?",
  "company_hr_dataset": "caylent"
}
```

**Access Control:**

Users can only access companies they have permission for. The system checks authorization before processing questions.

## Performance Considerations

- **Typical Processing Time**: 30-120 seconds depending on complexity
- **Concurrent Limit**: No hard limit, but Celery workers scale based on configuration
- **Data Volume**: System can handle millions of documents
- **Real-time Updates**: SSE polls database every 1 second

## Troubleshooting

### Question Stuck in "Pending"

**Cause:** Celery workers not running or queue is full

**Solution:** Check worker health at `/api/v1/bi/health`

### Analysis Failed with "No relevant data found"

**Cause:** No documents match the query or company dataset is empty

**Solution:** Check document count for company, ensure documents are uploaded and indexed

### SSE Connection Drops

**Cause:** Network timeout or proxy closing long connections

**Solution:** Implement reconnection logic with exponential backoff

### Slow Analysis Performance

**Cause:** Large document corpus or complex query

**Solution:** Pre-filter documents, optimize vector index, scale Celery workers


