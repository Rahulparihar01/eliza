# Technical Specification
## [Feature Name]

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | Draft / Reviewed / Approved |
| **Last Updated** | [Date] |
| **PRD Reference** | [Link to 01_PRODUCT_SPEC.md] |
| **Author** | [Engineering Lead / Development Agent] |

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Data Model](#data-model)
4. [API Design](#api-design)
5. [Integration Points](#integration-points)
6. [Security Considerations](#security-considerations)
7. [Error Handling](#error-handling)
8. [Performance Considerations](#performance-considerations)
9. [Testing Strategy](#testing-strategy)
10. [Migration Strategy](#migration-strategy)
11. [Agent Review Notes](#agent-review-notes)

---

## Overview

[Summary of technical approach based on PRD requirements. 2-3 paragraphs explaining the high-level solution.]

### Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| [Decision 1] | [Why this approach was chosen] |
| [Decision 2] | [Why this approach was chosen] |

---

## Architecture

### System Context

[How this feature fits into the existing Eliza Platform architecture]

```
┌─────────────────────────────────────────────────────────────────┐
│                         [Diagram]                                │
│  Show how this feature connects to existing systems              │
└─────────────────────────────────────────────────────────────────┘
```

### Component Diagram

```
[ASCII or description of component relationships]
```

### Data Flow

[How data moves through the system for key user flows]

1. User initiates [action]
2. Frontend calls [API endpoint]
3. Backend [processes/validates]
4. Data stored in [database/service]
5. Response returned to user

---

## Data Model

### New Tables

```sql
CREATE TABLE [table_name] (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(100) NOT NULL,  -- Multi-tenant (REQUIRED)
    
    -- Business fields
    [field_name] [TYPE] [CONSTRAINTS],
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_[table]_customer ON [table_name](customer_id);
CREATE INDEX idx_[table]_[field] ON [table_name]([field]);
```

### Modified Tables

| Table | Change | Migration Notes |
|-------|--------|-----------------|
| [table_name] | Add column [X] | [Any special considerations] |

### Entity Relationships

```
[Entity A] 1──────* [Entity B]
     │
     └──────1 [Entity C]
```

---

## API Design

### New Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/[resource]` | Create [resource] | `[permission]:write` |
| GET | `/api/v1/[resource]` | List [resources] | `[permission]:read` |
| GET | `/api/v1/[resource]/{id}` | Get [resource] | `[permission]:read` |
| PUT | `/api/v1/[resource]/{id}` | Update [resource] | `[permission]:write` |
| DELETE | `/api/v1/[resource]/{id}` | Delete [resource] | `[permission]:write` |

### Request/Response Models

```python
# src/api/schemas/[feature].py

class [Resource]CreateRequest(BaseModel):
    """Request to create a new [resource]."""
    name: str = Field(..., description="Name of the resource")
    # Add other fields...

class [Resource]Response(BaseModel):
    """Response containing [resource] data."""
    id: int
    customer_id: str
    name: str
    created_at: datetime
    updated_at: datetime

class [Resource]ListResponse(BaseModel):
    """Paginated list of [resources]."""
    items: List[[Resource]Response]
    total: int
    page: int
    page_size: int
```

### API Examples

```bash
# Create resource
curl -X POST /api/v1/[resource] \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "Example"}'

# Response
{
  "id": 1,
  "customer_id": "tenant-123",
  "name": "Example",
  "created_at": "2026-01-16T12:00:00Z"
}
```

---

## Integration Points

### Existing Services

| Service | Usage | Location |
|---------|-------|----------|
| [Service name] | [How it's used] | `src/services/[file].py` |

### External APIs

| API | Purpose | Auth Method |
|-----|---------|-------------|
| [API name] | [What it provides] | [API key / OAuth / etc.] |

### Celery Tasks

| Task | Purpose | Queue |
|------|---------|-------|
| `[task_name]` | [What it does] | `default` |

---

## Security Considerations

### Authentication & Authorization

- **Required Permission:** `[resource]:read`, `[resource]:write`
- **Multi-tenant:** All queries MUST filter by `customer_id`

### Row Level Security

Reference: `skills/row-level-security/RLS_IMPLEMENTATION_GUIDE.md`

```python
# Ensure RLS is applied
@router.get("/[resource]")
async def list_resources(
    current_user = Depends(require_permission(["[resource]:read"])),
    db: Session = Depends(get_db)
):
    # RLS automatically filters by customer_id
    return db.query([Resource]).all()
```

### Data Validation

| Input | Validation |
|-------|------------|
| [Field] | [Validation rules] |

---

## Error Handling

| Error Case | HTTP Code | Response | Handling |
|------------|-----------|----------|----------|
| Resource not found | 404 | `{"detail": "Resource not found"}` | Return early |
| Invalid input | 422 | Pydantic validation error | Automatic |
| Unauthorized | 401 | `{"detail": "Not authenticated"}` | Middleware |
| Forbidden | 403 | `{"detail": "Permission denied"}` | Decorator |

---

## Performance Considerations

### Caching Strategy

- [ ] Cache [X] with TTL of [Y] seconds
- [ ] Invalidate on [events]

### Query Optimization

- [ ] Add index on [fields]
- [ ] Use pagination for list endpoints
- [ ] Limit results to [N] by default

### Rate Limiting

- [ ] [N] requests per [time period] per user

---

## Testing Strategy

### Unit Tests

```python
# tests/test_[feature].py

def test_create_[resource]():
    """Test creating a new [resource]."""
    # Arrange
    # Act
    # Assert

def test_list_[resources]_filtered_by_tenant():
    """Verify multi-tenant isolation."""
    # Ensure user A cannot see user B's data
```

### Integration Tests

- [ ] API endpoint returns correct response
- [ ] Database records created correctly
- [ ] Multi-tenant isolation verified
- [ ] Permissions enforced

### E2E Tests

- [ ] User can complete [workflow]
- [ ] Error states handled gracefully

---

## Migration Strategy

### Database Migration

```python
# alembic/versions/[hash]_[description].py

def upgrade():
    op.create_table(
        '[table_name]',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('customer_id', sa.String(100), nullable=False),
        # ...
    )

def downgrade():
    op.drop_table('[table_name]')
```

### Deployment Order

1. Run database migration
2. Deploy backend changes
3. Deploy frontend changes
4. Verify health checks

### Rollback Plan

1. Revert frontend deployment
2. Revert backend deployment
3. Run `alembic downgrade -1`

---

## Agent Review Notes

### Questions Asked During Review

| Question | Resolution |
|----------|------------|
| [Question from agent] | [Decision made] |

### Edge Cases Identified

| Edge Case | Handling |
|-----------|----------|
| [Edge case 1] | [How it's handled] |

### Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| [Risk 1] | Low/Med/High | Low/Med/High | [Mitigation strategy] |

---

## Open Technical Questions

- [ ] [Question that needs resolution]
- [ ] [Question that needs resolution]
