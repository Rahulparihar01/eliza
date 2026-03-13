# AI Assistant - Analytics Domain Onboarding Specification

## Overview

This document specifies the conversational onboarding flow for adding new Analytics Domains to the AI Assistant. An Analytics Domain is a pre-configured, tuned data environment that enables users to query structured data using natural language.

## Architecture

### Three-Layer Model

| Layer | Who | Where | What |
|-------|-----|-------|------|
| **Connection** | Admin | Administration → Data Connections | Secure database credentials, firewall rules |
| **Domain Onboarding** | Power User | AI Assistant → Analytics Domains | Schema selection, metadata, context, sample queries |
| **Usage** | Regular User | AI Assistant → Chat | Select domain, ask questions |

### Permissions

```
# Static Permissions (always exist)
connections:manage                    → Admin: create/edit DB connections

assistant:access                      → User: access AI Assistant
assistant:documents:upload            → User: upload documents
assistant:documents:read              → User: view/query documents
assistant:documents:delete            → User: delete documents

assistant:domains:onboard             → Power User: start onboarding wizard
assistant:domains:publish             → Power User: publish new domains
assistant:domains:configure           → Power User: edit existing domain configs
assistant:domains:delete              → Power User: remove domains

# Dynamic Permissions (created per domain when published)
assistant:domains:<domain_slug>:access → User: can query this domain in chat
```

## User Flow

### Step 1: Select Connection (Form-based)

User selects from available database connections (configured by admin in Data Connections).

```
┌─────────────────────────────────────────┐
│  Choose a database connection           │
│                                         │
│  ○ PostgreSQL - Insurance DB            │
│  ○ MySQL - HR Database                  │
│  ○ Snowflake - Analytics Warehouse      │
│                                         │
│  (Only connections you have access to)  │
│                                         │
│                        [Start Setup →]  │
└─────────────────────────────────────────┘
```

**Requirements:**
- Only show connections the user has permission to use
- Show connection type icon and name
- Show connection status (healthy/unhealthy)

### Steps 2-3: Conversational Onboarding

A chat-style exchange where the AI guides the user through configuration.

**Information to Collect:**

| Data | Required | How Collected |
|------|----------|---------------|
| Domain name | ✓ | Direct question |
| Domain description/purpose | ✓ | Conversation |
| Tables to include | ✓ | AI shows discovered tables, user confirms |
| Tables to exclude | Optional | AI asks which to skip |
| Column meanings/mappings | As needed | AI asks about ambiguous columns |
| Business glossary terms | Optional | User provides context |
| **Sample queries (3-5)** | **✓ Required** | User provides question + expected SQL |
| Relationships/joins | Optional | AI can infer, user validates |

**Sample Conversation Flow:**

```
🤖 AI: I've connected to the HR Database and found 12 tables. 
       What would you like to call this domain?

👤 User: HR Analytics

🤖 AI: Great! What's the main purpose of this domain? 
       What kinds of questions will users ask?

👤 User: Headcount reporting, salary analysis, org structure

🤖 AI: I see tables like `employees`, `departments`, `salaries`. 
       Are there any tables I should exclude?

👤 User: Yes, exclude audit_logs and _temp tables

🤖 AI: I notice the `status` column in `employees` has values A, T, L. 
       What do these mean?

👤 User: A = Active, T = Terminated, L = On Leave

🤖 AI: Now I need some sample queries. These help me understand 
       how your team thinks about this data.
       
       Please provide 3-5 example questions WITH the expected SQL.
       This is required to ensure quality answers.

👤 User: "How many active employees per department?"
         
         SELECT d.name, COUNT(*) 
         FROM employees e
         JOIN departments d ON e.dept_id = d.id
         WHERE e.status = 'A' 
         GROUP BY d.name

🤖 AI: Perfect! Can you provide 2-3 more sample queries?

👤 User: [provides more examples]

🤖 AI: I have enough context to get started. Ready to test?
```

**AI Behavior Guidelines:**
- Ask one question at a time
- Acknowledge and confirm each answer
- Probe for clarification on ambiguous data
- Validate sample SQL syntax before accepting
- Summarize collected information before proceeding

### Step 4: Test & Publish

**Test Phase:**
```
┌─────────────────────────────────────────────────────────────┐
│  ✓ Domain configured                                        │
│                                                             │
│  Test your domain with a question:                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ What's the average salary by department?             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [Run Test]                                                 │
│                                                             │
│  Generated SQL:                                             │
│  SELECT d.name, AVG(s.amount)                               │
│  FROM salaries s                                            │
│  JOIN employees e ON s.emp_id = e.id                        │
│  JOIN departments d ON e.dept_id = d.id                     │
│  GROUP BY d.name                                            │
│                                                             │
│  ✓ Query executed successfully (0.23s)                      │
│  ✓ Results returned: 8 rows                                 │
│                                                             │
│  [Run Another Test]                                         │
│                                                             │
│  [Save as Draft]        [Publish Domain]                    │
└─────────────────────────────────────────────────────────────┘
```

**Publish Actions:**
1. Mark domain status as 'published'
2. Create dynamic permission: `assistant:domains:<slug>:access`
3. Log audit event
4. Notify relevant users (optional)

## Data Model

### AnalyticsDomain Table

```sql
CREATE TABLE analytics_domains (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(100) NOT NULL REFERENCES customers(customer_id),
    connection_id INTEGER NOT NULL REFERENCES connector_configurations(id),
    
    -- Basic Info
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    
    -- Status
    status VARCHAR(50) DEFAULT 'draft', -- draft, published, archived
    
    -- Configuration (JSON)
    schema_config JSONB NOT NULL DEFAULT '{}',
    -- {
    --   "included_tables": ["employees", "departments", "salaries"],
    --   "excluded_tables": ["audit_logs", "_temp"],
    --   "column_mappings": {
    --     "employees.status": {"A": "Active", "T": "Terminated", "L": "On Leave"}
    --   },
    --   "glossary": {"FTE": "Full-Time Equivalent", "HC": "Headcount"}
    -- }
    
    -- Sample Queries (JSON array)
    sample_queries JSONB NOT NULL DEFAULT '[]',
    -- [
    --   {
    --     "question": "How many active employees per department?",
    --     "sql": "SELECT d.name, COUNT(*) FROM employees e JOIN departments d ON e.dept_id = d.id WHERE e.status = 'A' GROUP BY d.name"
    --   }
    -- ]
    
    -- Onboarding transcript (for audit/improvement)
    onboarding_transcript JSONB,
    
    -- Audit
    created_by INTEGER REFERENCES users(id),
    published_by INTEGER REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    published_at TIMESTAMPTZ
);
```

## UI Components

### Domain List View

```
┌─────────────────────────────────────────────────────────────┐
│  Analytics Domains                                          │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  📊 Insurance Analytics                              │   │
│  │  Query insurance policy, claim, and customer data    │   │
│  │  ✓ Published · Last used 2h ago                      │   │
│  │                                    [Configure] [→]   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  👥 HR Analytics                                     │   │
│  │  Employee headcount and salary analysis              │   │
│  │  📝 Draft · Last edited 3d ago                       │   │
│  │                            [Continue Setup] [Delete] │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐   │
│  │  + Onboard New Domain                                │   │
│  │  Connect additional data sources                     │   │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Chat Integration

When domain is published, it appears in the Chat domain selector:

```
┌─────────────────────────────────────────────────────────────┐
│  Chat                                                       │
│                                                             │
│  [Select Domain: Insurance Analytics ▼]                     │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Insurance Analytics    ← Currently selected          │   │
│  │ HR Analytics           (requires permission)         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Ask anything about your data...                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Current State (Implemented)
- [x] Insurance Analytics domain pre-configured
- [x] Chat interface working with single domain
- [x] Basic permission structure

### Phase 2: UI Rename & Permissions (This PR)
- [x] Rename sections and pages
- [x] Add AI Assistant permissions
- [x] Placeholder for domain onboarding

### Phase 3: Domain Management (Future)
- [ ] Analytics Domains list page
- [ ] Domain configuration editing
- [ ] Draft/publish workflow

### Phase 4: Conversational Onboarding (Future)
- [ ] Connection selector
- [ ] Chat-based schema configuration
- [ ] Sample query collection (required)
- [ ] Test & publish flow

### Phase 5: Dynamic Permissions (Future)
- [ ] Auto-create permission on domain publish
- [ ] Role UI shows available domains
- [ ] Domain-scoped access in chat

## Open Questions

1. **Multi-tenant domains:** Can a domain be shared across tenants, or always tenant-specific?
2. **Domain versioning:** When schema changes, how do we handle existing domains?
3. **Query limits:** Should we allow per-domain query complexity limits?
4. **Caching:** How long to cache schema metadata?

---

*Last Updated: December 25, 2025*

