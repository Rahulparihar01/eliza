# Platform Skeleton Directory Structure

This document describes the complete directory structure for the platform skeleton.

## Root Directory

```
your-customer-platform/
├── .env                          # Environment variables (gitignored)
├── .env.example                  # Environment variable template
├── .gitignore                    # Git ignore rules
├── README.md                     # Project README
├── requirements.txt              # Python dependencies
├── alembic.ini                   # Alembic configuration
├── Makefile                      # Common commands (optional)
│
├── src/                          # Backend Python code
├── frontend/                     # React frontend
├── docker/                       # Docker configuration
├── alembic/                      # Database migrations
├── config/                       # Configuration files
├── scripts/                      # Utility scripts
└── tests/                        # Test files
```

## Backend Structure (`src/`)

```
src/
├── __init__.py
├── main.py                       # FastAPI application entry point
├── celery_app.py                 # Celery application configuration
│
├── api/                          # API layer
│   ├── __init__.py
│   ├── routes/                   # Route modules
│   │   ├── __init__.py
│   │   ├── health.py            # Health check endpoints
│   │   ├── auth.py              # Authentication endpoints
│   │   ├── documents.py         # Document management
│   │   └── your_feature.py      # Your custom routes
│   │
│   └── schemas/                  # Pydantic request/response models
│       ├── __init__.py
│       ├── auth.py
│       ├── documents.py
│       └── your_feature.py
│
├── core/                         # Core infrastructure
│   ├── __init__.py
│   ├── config.py                # Configuration management
│   ├── auth.py                  # Authentication logic
│   ├── logging.py               # Logging setup
│   ├── exceptions.py            # Custom exceptions
│   └── auth_context.py          # Auth context helpers
│
├── models/                       # SQLAlchemy database models
│   ├── __init__.py
│   ├── database.py              # Database base configuration
│   ├── auth.py                  # User, Role, Permission models
│   ├── customer.py              # Customer models
│   ├── document.py              # Document models
│   └── your_feature.py          # Your custom models
│
├── services/                     # Business logic services
│   ├── __init__.py
│   ├── base_service.py          # Base service class
│   ├── auth_service.py          # Authentication service
│   ├── document_service.py      # Document service
│   └── your_feature_service.py  # Your custom services
│
├── tasks/                        # Celery tasks
│   ├── __init__.py
│   ├── documents.py             # Document processing tasks
│   └── your_feature_tasks.py    # Your custom tasks
│
├── middleware/                   # FastAPI middleware
│   ├── __init__.py
│   ├── authorization.py         # RBAC middleware
│   └── logging.py               # Request logging middleware
│
├── utils/                        # Utility functions
│   ├── __init__.py
│   └── encryption.py           # Encryption utilities
│
└── crewai_custom_tools/          # CrewAI tools (if using)
    ├── __init__.py
    └── document_search_tool.py
```

## Frontend Structure (`frontend/`)

```
frontend/
├── public/                       # Static assets
│   ├── index.html
│   ├── favicon.ico
│   └── manifest.json
│
├── src/
│   ├── index.tsx                 # Entry point
│   ├── App.tsx                   # Main app component with routes
│   │
│   ├── components/               # React components
│   │   ├── layout/              # Layout components
│   │   │   ├── Layout.tsx       # Main layout wrapper
│   │   │   ├── Navigation.tsx   # Left navigation (CRITICAL)
│   │   │   ├── Header.tsx       # Top header
│   │   │   └── NavItem.tsx      # Navigation item component
│   │   │
│   │   ├── common/              # Common reusable components
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   └── Modal.tsx
│   │   │
│   │   └── your-feature/        # Your feature components
│   │       └── YourComponent.tsx
│   │
│   ├── pages/                    # Page components
│   │   ├── HomePage.tsx
│   │   ├── KnowledgeBasePage.tsx
│   │   └── YourFeaturePage.tsx
│   │
│   ├── contexts/                 # React contexts
│   │   └── AuthContext.tsx      # Authentication context
│   │
│   ├── services/                 # API service clients
│   │   └── api/                 # Generated API clients (Orval)
│   │
│   ├── hooks/                    # Custom React hooks
│   │   └── useAuth.ts
│   │
│   └── utils/                    # Utility functions
│       └── constants.ts
│
├── package.json                  # Node dependencies
├── tsconfig.json                 # TypeScript configuration
├── tailwind.config.js            # Tailwind CSS configuration
├── orval.config.ts               # API client generation config
└── Dockerfile                    # Frontend Dockerfile
```

## Docker Structure (`docker/`)

```
docker/
├── Dockerfile                    # Backend Dockerfile
├── docker-compose.yml            # Development compose file
├── docker-compose.customer.yml   # Customer instance template
├── entrypoint.sh                 # Container entrypoint script
│
└── config/                       # Docker-specific configs
    └── logstash/                 # Logstash configuration (if using)
```

## Database Migrations (`alembic/`)

```
alembic/
├── env.py                        # Alembic environment configuration
├── script.py.mako                 # Migration template
└── versions/                      # Migration files
    ├── 001_initial_schema.py
    ├── 002_add_auth_tables.py
    └── 003_add_your_feature.py
```

## Configuration (`config/`)

```
config/
├── customers/                     # Customer-specific configs
│   ├── customer-template/
│   │   └── config.yml
│   └── your-customer/
│       └── config.yml
│
└── search/                        # Search configuration
    ├── elasticsearch/
    │   └── mapping.yml
    └── neo4j/
        └── constraints.cypher
```

## Scripts (`scripts/`)

```
scripts/
├── setup-local.sh                # Local development setup
├── deploy-customer.sh            # Customer deployment script
├── init_rbac.py                  # RBAC initialization
└── seed_data.py                  # Seed data script (optional)
```

## Tests (`tests/`)

```
tests/
├── __init__.py
├── conftest.py                   # Pytest configuration
├── test_api/                     # API endpoint tests
│   └── test_auth.py
├── test_services/                # Service layer tests
│   └── test_document_service.py
└── test_models/                  # Model tests
    └── test_user.py
```

## Key Files to Create/Modify

### Backend
- `src/main.py` - FastAPI app setup
- `src/core/config.py` - Configuration
- `src/api/routes/your_feature.py` - Your routes
- `src/models/your_feature.py` - Your models
- `src/services/your_feature_service.py` - Your services

### Frontend
- `frontend/src/components/layout/Navigation.tsx` - **CRITICAL**: Navigation
- `frontend/src/App.tsx` - Routes
- `frontend/src/pages/YourFeaturePage.tsx` - Your pages

### Configuration
- `.env` - Environment variables
- `docker/docker-compose.yml` - Docker services
- `alembic/versions/` - Migrations

## File Naming Conventions

### Python
- **Modules**: `snake_case.py` (e.g., `document_service.py`)
- **Classes**: `PascalCase` (e.g., `DocumentService`)
- **Functions**: `snake_case` (e.g., `get_documents`)

### TypeScript/React
- **Components**: `PascalCase.tsx` (e.g., `DocumentPage.tsx`)
- **Hooks**: `camelCase.ts` starting with `use` (e.g., `useAuth.ts`)
- **Utilities**: `camelCase.ts` (e.g., `formatDate.ts`)

### Database
- **Tables**: `snake_case` (e.g., `document_chunks`)
- **Columns**: `snake_case` (e.g., `created_at`)
- **Indexes**: `ix_table_name_column_name` (e.g., `ix_documents_customer_id`)

## Critical Directories

These directories are **essential** and must exist:

1. **`src/core/`** - Core infrastructure (config, auth, logging)
2. **`src/models/`** - Database models
3. **`src/api/routes/`** - API endpoints
4. **`frontend/src/components/layout/`** - Layout components (especially Navigation)
5. **`alembic/versions/`** - Database migrations
6. **`docker/`** - Docker configuration

## Optional Directories

These can be added as needed:

- `src/crewai_flows/` - CrewAI flow definitions
- `src/crewai_custom_tools/` - CrewAI tools
- `src/flows/` - Custom flow definitions
- `docs/` - Documentation
- `design_docs/` - Design documents

---

**Note**: This structure provides the foundation. Add directories as needed for your specific features, but maintain consistency with these patterns.

