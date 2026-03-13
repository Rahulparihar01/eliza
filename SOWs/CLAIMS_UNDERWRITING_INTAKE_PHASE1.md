# Statement of Work: Claims Underwriting Intake System
## Phase 1: Document Intake & Broker Communication

---

## Application Overview

The Eliza Platform is an AI-native enterprise application framework built on modern, scalable architecture. The platform provides:

- **Backend**: FastAPI application with REST API endpoints and async task processing via Celery
- **Frontend**: React-based user interface with real-time event streaming
- **AI Orchestration**: CrewAI framework for multi-agent workflows and intelligent automation
- **Data Layer**: PostgreSQL for relational data, Elasticsearch for search, Neo4j for graph relationships
- **Infrastructure**: Docker Compose deployment with multi-tenant isolation, RBAC security, and comprehensive monitoring

The platform is designed as a skeleton application that can be adapted for specific business workflows. This SOW covers the adaptation for Claims Underwriting, focusing on the document intake and broker communication process.

---

## Scope of Work: Phase 1

Phase 1 focuses on building the core infrastructure and agents necessary to manage the underwriting intake process, including document receipt, parsing, validation, and broker communication.

---

## Section 1: Application Schema for Intake Data Elements

### Description
Design and implement the database schema and data models required to support the claims underwriting intake workflow. This includes structured storage for intake checklists, parsed document data, broker communications, and quality validation results.

### Work Items
- Define database schema for underwriting intake records with support for multi-tenant isolation
- Create models for intake checklists with configurable required items per underwriting type
- Design document storage schema with metadata tracking (source, parsing status, validation results)
- Implement data models for parsed document elements (extracted fields, key-value pairs, structured data)
- Create broker communication tracking schema (email threads, checklist progress, interaction history)
- Design data quality validation schema to store validation rules, results, and remediation tracking
- Implement Pydantic models for API request/response validation
- Create database migrations with proper versioning and rollback support

### Deliverables
- Complete database schema documentation
- SQLAlchemy ORM models for all intake-related entities
- Pydantic response models for API endpoints
- Database migration files with upgrade/downgrade paths
- API endpoint specifications for CRUD operations
- Data model unit tests

---

## Section 2: Agent 1 - Document Intake Management Agent

### Description
Build an intelligent agent responsible for managing the complete document intake lifecycle. The agent processes incoming documents, orchestrates parsing with external and internal tools, validates data quality, and updates intake checklists accordingly.

### Work Items
- Implement document receipt handler for multiple input sources (email, upload, API)
- Integrate external document parsing services (configure provider endpoints and authentication)
- Integrate internal Docling-based document parsing as fallback/alternative parsing method
- Build intake checklist management system (required items definition, status tracking, completion rules)
- Implement email body parsing component to extract structured data from email content
- Create data extraction mapping engine that maps parsed document elements to checklist items
- Build checklist auto-completion logic that checks off items based on extracted data
- Design data quality validation framework with configurable rules and thresholds
- Implement quality check workflow that validates extracted data before checklist approval
- Build context builder that generates comprehensive intake status summaries for Agent 2
- Create error handling and retry logic for parsing failures
- Implement audit logging for all intake operations

### Deliverables
- CrewAI agent implementation with defined role, goal, and backstory
- Custom tools for document parsing (external and internal)
- Custom tool for checklist management and status updates
- Custom tool for data quality validation
- Agent flow orchestration logic
- Integration tests for document parsing workflows
- Agent execution unit tests
- Documentation for agent capabilities and configuration

---

## Section 3: Agent 2 - Email Writing Agent

### Description
Develop an intelligent email composition agent that communicates with brokers to collect missing intake information. The agent understands the current checklist status, crafts contextually appropriate emails, and manages the communication thread until all required items are collected.

### Work Items
- Design email composition system with template management and dynamic content generation
- Implement checklist-aware email generation that identifies missing items
- Build broker communication context tracker (email thread history, previous requests, responses)
- Create prompt engineering for email tone, clarity, and compliance with communication guidelines
- Implement response parsing to extract broker-provided information from email replies
- Build feedback loop that sends parsed responses back to Agent 1 for checklist updates
- Design email sending infrastructure with delivery tracking and error handling
- Implement conversation state management to maintain context across multiple email exchanges
- Create completion detection logic that recognizes when checklist is fully satisfied
- Build transition workflow that flags complete intake packages for underwriting team submission

### Deliverables
- CrewAI agent implementation for email composition
- Custom tool for email generation with checklist context
- Custom tool for email sending and delivery tracking
- Custom tool for parsing broker email responses
- Integration with Agent 1 for checklist updates
- Email template system with customization options
- Unit tests for email generation logic
- Integration tests for complete broker communication workflow
- Documentation for email agent capabilities and configuration

---

## Technical Requirements

### Common Infrastructure
- Multi-tenant data isolation
- RBAC security model
- Comprehensive audit logging
- Error handling and retry mechanisms
- Performance monitoring and observability

### Integration Points
- Email service provider (SMTP/API)
- External document parsing services (API-based)
- Internal Docling parsing service
- Database layer (PostgreSQL)
- Task queue (Celery)
- Frontend API endpoints

### Testing Requirements
- Unit tests for all core components
- Integration tests for end-to-end workflows
- Agent execution tests with mocked services
- API endpoint tests
- Data validation tests

---

## Exclusions

This phase explicitly excludes:
- Underwriting team submission workflow (future phase)
- Advanced analytics and reporting dashboards
- Workflow customization UI for non-technical users
- Integration with external underwriting systems
- Document storage optimization and archival processes

---

## Success Criteria

Phase 1 will be considered complete when:
1. All database schemas are implemented and tested
2. Agent 1 can successfully receive, parse, validate, and update checklists for incoming documents
3. Agent 2 can generate contextually appropriate emails and manage broker communication threads
4. Both agents integrate seamlessly, with Agent 2 successfully collecting missing information identified by Agent 1
5. Complete intake packages can be flagged as ready for underwriting team review
6. All deliverables meet code quality standards and include comprehensive test coverage

