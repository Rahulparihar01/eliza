# API Changelog

All notable changes to the Eliza Platform API will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial API documentation
- MCP server integration documentation

---

## [1.0.0] - 2024-01-15

### Added
- **Authentication API** - JWT-based auth with RBAC
- **Business Intelligence API** - AI-powered Q&A system
- **Talent Intelligence API** - ML talent analysis and matching
- **Documents API** - Vector-based document management
- **Connectors API** - Data source integrations (PDL, filesystem)
- **Search API** - Multi-data-store person search
- **Health Check API** - System monitoring endpoints

### Authentication
- User login/logout with JWT tokens
- Token refresh mechanism
- Role-Based Access Control (RBAC)
- Session management with device fingerprinting
- User profile management

### Business Intelligence
- Natural language question submission
- AI-powered task enrichment
- CrewAI-based data analysis
- Real-time progress via Server-Sent Events (SSE)
- Question history and results retrieval
- Execution timeline and telemetry

### Talent Intelligence
- Resume parsing with Docling VLM
- Baseline profile building
- Multi-dimensional candidate scoring
- People Data Labs (PDL) integration
- Market candidate search
- Synthesis report generation
- Real-time analysis progress

### Documents
- Multi-format document upload (PDF, DOCX, TXT, etc.)
- Configurable chunking strategies (semantic, fixed-size, sliding-window)
- Vector embedding and indexing
- Semantic search with similarity scoring
- Document download and management
- Real-time upload progress via SSE
- Document statistics and metrics

### Connectors
- People Data Labs connector
- Filesystem connector
- Connector configuration management
- Manual and scheduled sync triggers
- Sync run monitoring with telemetry
- PDL person data access
- Cost estimation for PDL queries
- Connection testing and validation

### Search
- Full-text person search (Elasticsearch)
- Skill-based search
- Career transition tracking (Neo4j)
- Company network analysis (Neo4j)
- Skill co-occurrence analysis
- Field aggregations for analytics

### Health & Monitoring
- Basic health checks for load balancers
- Readiness probes for Kubernetes
- Detailed component health status
- Service-specific health endpoints
- Performance metrics

### Security
- JWT token-based authentication
- Multi-tenant data isolation
- Permission-based access control
- Encrypted credentials storage
- Audit logging
- Device fingerprinting
- Session management

### Performance
- Sub-second search queries (Elasticsearch)
- Efficient vector similarity search (FAISS)
- Asynchronous processing with Celery
- Real-time updates via SSE
- Connection pooling
- Query result caching

---

## Deprecations

### [1.0.0]
- `GET /api/v1/documents/recent` - Deprecated in favor of `GET /api/v1/documents` with date filtering
  - **Reason**: Redundant functionality, better served by flexible filtering
  - **Migration**: Use `GET /api/v1/documents?created_after=<timestamp>&limit=<n>&sort=-created_at`
  - **Removal**: Planned for v2.0.0

---

## Breaking Changes

None yet. API is in v1.0.0 release.

---

## Migration Guides

### From v0.x to v1.0.0

Not applicable - v1.0.0 is the first public release.

---

## Upcoming Features

### v1.1.0 (Planned)
- GraphQL API alongside REST
- Webhook support for async operations
- Batch operations API
- Advanced filtering DSL
- API versioning in URLs

### v1.2.0 (Planned)
- Additional ATS connectors (Greenhouse, Lever)
- HRIS connectors (Workday, BambooHR)
- Enhanced skill taxonomy
- Multi-language support
- Advanced analytics endpoints

### v2.0.0 (Future)
- Major API restructuring
- Removal of deprecated endpoints
- Enhanced permission system
- GraphQL as primary API

---

## Support Policy

### Active Support
- **Current Version** (1.0.x): Full support, security updates, bug fixes
- **Previous Major** (N/A): Not applicable yet

### Security Updates
- Critical security issues: Immediate patch
- High severity: Within 7 days
- Medium/Low severity: Next minor release

### Deprecation Policy
1. Feature marked as deprecated in current version
2. Deprecated feature supported for at least one major version
3. Removal announced 6 months in advance
4. Migration guide provided before removal

---

## Versioning

We use Semantic Versioning (SemVer):

- **MAJOR** version: Incompatible API changes
- **MINOR** version: Backwards-compatible new features
- **PATCH** version: Backwards-compatible bug fixes

### Version Format
```
MAJOR.MINOR.PATCH
  │     │     │
  │     │     └─ Bug fixes
  │     └─────── New features (backwards-compatible)
  └───────────── Breaking changes
```

---

## API Stability

### Stable APIs (Production-Ready)
✅ Authentication API
✅ Business Intelligence API (core features)
✅ Documents API (core features)
✅ Health Check API

### Beta APIs (May Change)
⚠️ Talent Intelligence API - Active development
⚠️ Connectors API - Adding new connector types
⚠️ Search API - Enhancing graph queries

### Experimental Features
🧪 Q&A RAG generation for documents
🧪 Skill taxonomy auto-tagging
🧪 Advanced career path predictions

---

## Feedback

We welcome feedback on our API!

- **Bug Reports**: GitHub Issues
- **Feature Requests**: GitHub Discussions
- **Security Issues**: security@eliza-platform.com
- **General Questions**: support@eliza-platform.com

---

## Links

- [API Documentation](./README.md)
- [Quick Reference](./QUICK_REFERENCE.md)
- [GitHub Repository](https://github.com/your-org/eliza-platform)
- [Support Portal](https://support.eliza-platform.com)


