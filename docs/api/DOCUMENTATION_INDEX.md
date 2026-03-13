# Eliza Platform API Documentation Index

## 📚 Complete Documentation Set

This documentation package contains comprehensive guides for integrating with the Eliza Platform API, specifically designed for MCP server development.

### Total Documentation Stats
- **11 files** covering all aspects of the API
- **6,489 lines** of detailed documentation
- **136 KB** of content
- **100+ API endpoints** documented
- **7 major API categories** covered

---

## 📖 Documentation Files

### Core Documentation

#### [README.md](./README.md) - **START HERE**
- API overview and quick start
- Authentication basics
- Response formats
- Pagination, filtering, and sorting
- Real-time updates (SSE)
- Multi-tenancy concepts
- Error handling best practices

**Read this first** to understand the API structure and basic concepts.

---

#### [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) - **CURL EXAMPLES**
- Ready-to-use curl commands for all endpoints
- Common patterns and workflows
- Environment variable setup
- HTTP status code reference
- Response format examples

**Use this** when you need to quickly test endpoints or find example commands.

---

### API Endpoint Documentation

#### [01-authentication.md](./01-authentication.md) - **Authentication & RBAC**
*518 lines | 10 KB*

Comprehensive authentication documentation:
- Login/logout flows
- JWT token management (access + refresh tokens)
- Session management with device fingerprinting
- Role-Based Access Control (RBAC)
- Permission system
- User profile management
- Multi-session handling

**Key Sections:**
- Authentication flow diagram
- Token lifetimes and refresh logic
- Standard roles and permissions
- Security best practices
- MCP integration example code

---

#### [02-business-intelligence.md](./02-business-intelligence.md) - **AI Q&A System**
*590 lines | 14 KB*

Business Intelligence Q&A system:
- Natural language question submission
- AI task enrichment
- CrewAI-based analysis
- Real-time progress tracking (SSE)
- Results retrieval
- Execution timeline and telemetry

**Key Sections:**
- Submit question workflow
- Status polling vs. SSE streaming
- Telemetry event types
- Multi-company support
- Performance considerations
- Common workflows with code examples

---

#### [03-talent-intelligence.md](./03-talent-intelligence.md) - **ML Talent Analysis**
*479 lines | 11 KB*

> **See also:** [TALENT_INTELLIGENCE_FLOW.md](./TALENT_INTELLIGENCE_FLOW.md) - Visual flow diagram

ML-powered talent intelligence:
- Resume parsing with Docling VLM
- Baseline profile building
- Multi-dimensional candidate scoring
- People Data Labs (PDL) integration
- Market candidate search
- Synthesis report generation

**Key Sections:**
- Analysis workflow (10 stages)
- Real-time progress events
- Multi-dimensional scoring explained
- PDL query format and best practices
- Cost control for PDL searches
- Provenance and audit trails

---

#### [04-documents.md](./04-documents.md) - **Document Management**
*880 lines | 22 KB*

Vector-based document system:
- Multi-format upload (PDF, DOCX, TXT, etc.)
- Chunking strategies (semantic, fixed, sliding-window)
- Vector embedding and indexing
- Semantic search with similarity scores
- Document lifecycle management
- Real-time upload progress (SSE)

**Key Sections:**
- Document lifecycle diagram
- Chunking strategy selection guide
- Search optimization tips
- Upload best practices
- Performance benchmarks
- Troubleshooting guide
- Storage and retention policies

---

#### [05-connectors.md](./05-connectors.md) - **Data Source Integrations**
*978 lines | 21 KB*

Data connector framework:
- People Data Labs connector
- Filesystem connector
- Configuration management
- Sync triggering and monitoring
- Telemetry and real-time progress
- PDL person data access
- Cost estimation

**Key Sections:**
- Supported connector types
- PDL query format and guidelines
- Filesystem connector setup
- Sync management workflows
- Career transition tracking
- Company network analysis
- Cost management best practices

---

#### [06-search.md](./06-search.md) - **Advanced Search**
*705 lines | 16 KB*

Multi-data-store search system:
- Full-text person search (Elasticsearch)
- Skill-based matching
- Career transition analysis (Neo4j)
- Company network discovery (Neo4j)
- Skill co-occurrence analysis
- Field aggregations

**Key Sections:**
- Search algorithm and field weights
- Query syntax (boolean, fuzzy, phrase)
- Multi-data-store architecture
- Search patterns for common use cases
- Performance optimization tips
- Fallback behavior

---

#### [07-health.md](./07-health.md) - **Health & Monitoring**
*770 lines | 17 KB*

System health and monitoring:
- Basic health checks
- Readiness probes (Kubernetes)
- Detailed component status
- Service-specific health endpoints
- Performance metrics

**Key Sections:**
- Kubernetes probe configurations
- Load balancer health check setup
- Monitoring tool integration (Prometheus, Datadog, New Relic)
- Alerting rule examples
- Health check best practices
- Troubleshooting guide
- Security considerations

---

### Supplementary Documentation

#### [TALENT_INTELLIGENCE_FLOW.md](./TALENT_INTELLIGENCE_FLOW.md) - **Visual Flow Diagram**
*950+ lines | 28 KB*

Comprehensive visual flow diagram for Talent Intelligence:
- Complete 10-stage analysis pipeline
- Real-time event stream (SSE) timeline
- Data flow diagram
- Scoring dimension breakdown
- Processing time benchmarks
- Success metrics

**Includes:**
- ASCII art diagrams for each stage
- Event timeline with timestamps
- Scoring calculation examples
- Error handling flows
- Performance metrics

---

#### [CHANGELOG.md](./CHANGELOG.md) - **Version History**
*227 lines | 5.7 KB*

API version history and changes:
- Current version (1.0.0)
- Deprecation notices
- Breaking changes
- Migration guides
- Upcoming features roadmap
- Support policy
- Versioning strategy

---

#### [MCP_INTEGRATION_GUIDE.md](./MCP_INTEGRATION_GUIDE.md) - **MCP Server Guide**
*805 lines | 19 KB*

Complete MCP server integration guide:
- MCP server architecture diagram
- Recommended tool implementations
- Authentication manager code
- Error handling patterns
- Rate limiting and retries
- Configuration examples
- Testing strategies
- Best practices

**Includes:**
- 14 recommended MCP tools with full implementations
- Complete authentication manager class
- Error handling utilities
- Retry logic with exponential backoff
- Environment variable configuration
- Testing examples with Jest
- Security best practices

**MCP Tools Covered:**
1. `ask_business_question` - BI Q&A
2. `get_question_status` - Status checking
3. `analyze_talent_pool` - Talent analysis
4. `search_documents` - Semantic search
5. `upload_documents` - Document ingestion
6. `find_candidates` - Candidate search
7. `find_skill_cooccurrence` - Skill analysis
8. `analyze_career_transitions` - Career paths
9. `list_connectors` - Connector management
10. `trigger_connector_sync` - Sync operations
11. And more...

---

## 🎯 Quick Navigation by Use Case

### For MCP Server Developers
1. Start with [README.md](./README.md) - Understand the API basics
2. Review [MCP_INTEGRATION_GUIDE.md](./MCP_INTEGRATION_GUIDE.md) - Implementation patterns
3. Reference [01-authentication.md](./01-authentication.md) - Auth implementation
4. Use [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) - Test endpoints

### For Business Intelligence Integration
1. [02-business-intelligence.md](./02-business-intelligence.md) - Complete BI API
2. [04-documents.md](./04-documents.md) - Document management
3. [06-search.md](./06-search.md) - Search capabilities

### For Talent/Recruitment Features
1. [03-talent-intelligence.md](./03-talent-intelligence.md) - Talent analysis
2. [05-connectors.md](./05-connectors.md) - Data connectors (PDL)
3. [06-search.md](./06-search.md) - Candidate search

### For Production Deployment
1. [07-health.md](./07-health.md) - Monitoring setup
2. [01-authentication.md](./01-authentication.md) - Security
3. [CHANGELOG.md](./CHANGELOG.md) - Version policy

---

## 📊 API Coverage

### By Category

| Category | Endpoints | Documentation |
|----------|-----------|---------------|
| Authentication | 12 | [01-authentication.md](./01-authentication.md) |
| Business Intelligence | 15 | [02-business-intelligence.md](./02-business-intelligence.md) |
| Talent Intelligence | 6 | [03-talent-intelligence.md](./03-talent-intelligence.md) |
| Documents | 15 | [04-documents.md](./04-documents.md) |
| Connectors | 20+ | [05-connectors.md](./05-connectors.md) |
| Search | 7 | [06-search.md](./06-search.md) |
| Health & Monitoring | 6 | [07-health.md](./07-health.md) |

### By HTTP Method

- **GET** - ~60 endpoints (read operations)
- **POST** - ~30 endpoints (create/search operations)
- **PUT** - ~5 endpoints (update operations)
- **DELETE** - ~5 endpoints (delete operations)

---

## 🔑 Key Features Documented

### Real-Time Updates
- Server-Sent Events (SSE) implementation
- Event types and formats
- JavaScript/TypeScript examples
- Heartbeat and keep-alive handling

### Multi-Tenancy
- Customer isolation
- Company-level data scoping
- Permission-based access control
- Secure data segregation

### Asynchronous Processing
- Background task patterns
- Status polling strategies
- Progress tracking
- Error handling

### Vector Search
- Semantic similarity search
- Embedding generation
- Index management
- Performance optimization

### AI/ML Integration
- CrewAI workflows
- LLM-powered analysis
- Resume parsing (Docling VLM)
- Multi-dimensional scoring

---

## 💡 Documentation Highlights

### Code Examples
- ✅ **250+** code examples across all languages
- ✅ **JavaScript/TypeScript** - Full MCP tool implementations
- ✅ **Python** - Service integration examples
- ✅ **Bash/curl** - Quick testing commands

### Diagrams & Visualizations
- API architecture diagrams
- Workflow flowcharts
- Authentication flows
- Multi-data-store architecture

### Best Practices
- Error handling patterns
- Rate limiting strategies
- Caching recommendations
- Security guidelines
- Performance optimization

### Troubleshooting
- Common errors and solutions
- Debugging strategies
- Health check interpretation
- Performance diagnosis

---

## 🚀 Getting Started Checklist

For MCP server developers:

- [ ] Read [README.md](./README.md) for API overview
- [ ] Review [01-authentication.md](./01-authentication.md) for auth setup
- [ ] Study [MCP_INTEGRATION_GUIDE.md](./MCP_INTEGRATION_GUIDE.md) for implementation
- [ ] Test endpoints with [QUICK_REFERENCE.md](./QUICK_REFERENCE.md)
- [ ] Implement core tools (BI, Search, Documents)
- [ ] Add health checks from [07-health.md](./07-health.md)
- [ ] Review [CHANGELOG.md](./CHANGELOG.md) for version policy
- [ ] Test with actual API calls
- [ ] Implement error handling
- [ ] Deploy and monitor

---

## 📞 Support & Resources

### Documentation
- **This Package**: Complete API reference
- **OpenAPI Spec**: http://localhost:5001/docs (Swagger UI)
- **ReDoc**: http://localhost:5001/redoc

### Contact
- **Bug Reports**: GitHub Issues
- **Feature Requests**: GitHub Discussions
- **Security**: security@eliza-platform.com
- **Support**: support@eliza-platform.com

### Additional Resources
- **GitHub**: https://github.com/your-org/eliza-platform
- **Blog**: https://blog.eliza-platform.com
- **Community**: https://community.eliza-platform.com

---

## 📝 Contributing to Documentation

Found an error or want to improve the docs?

1. **Fork** the repository
2. **Edit** the relevant markdown file
3. **Test** your changes
4. **Submit** a pull request

Documentation follows:
- Markdown best practices
- Clear code examples
- Consistent formatting
- Comprehensive coverage

---

## 🔄 Documentation Updates

This documentation is current as of **January 15, 2024** for **API v1.0.0**.

Check [CHANGELOG.md](./CHANGELOG.md) for:
- Latest updates
- Deprecated features
- Breaking changes
- New endpoints

---

## 📈 Documentation Metrics

- **Total Files**: 11
- **Total Lines**: 6,489
- **Total Size**: 136 KB
- **Code Examples**: 250+
- **Endpoints Documented**: 100+
- **Diagrams**: 10+
- **Best Practice Sections**: 50+
- **Troubleshooting Guides**: 7
- **Last Updated**: January 15, 2024

---

**Ready to build your MCP server?** Start with [MCP_INTEGRATION_GUIDE.md](./MCP_INTEGRATION_GUIDE.md)!


