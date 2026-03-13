# Platform Skeleton - Setup Guide

This skeleton provides the foundation for creating a new instance of the Eliza Platform with a different set of features for a new customer.

## 🎯 Purpose

This skeleton includes:
- **Core platform infrastructure** (databases, auth, API structure)
- **Design system components** (navigation, layout, UI patterns)
- **Critical patterns** (database sessions, async tasks, multi-tenancy)
- **Setup instructions** for getting started quickly

## 📋 Prerequisites

Before starting, ensure you have:
- Docker and Docker Compose installed
- Python 3.11+ (for local development)
- Node.js 18+ and npm (for frontend development)
- Basic understanding of FastAPI, React, and Docker

## 🚀 Quick Start

### 1. Copy Skeleton to New Repository

```bash
# Create new repository directory
mkdir your-customer-platform
cd your-customer-platform

# Copy skeleton structure
cp -r path/to/eliza-platform/dev_onboarding/platform_skeleton/* .

# Initialize git repository
git init
git add .
git commit -m "Initial platform skeleton"
```

### 2. Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration
# - Set CUSTOMER_ID and CUSTOMER_NAME
# - Configure database credentials
# - Add API keys (OpenAI, Anthropic, etc.)
# - Set encryption key (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

### 3. Initialize Database

```bash
# Start database services only
docker-compose up -d postgres redis neo4j elasticsearch

# Wait for services to be healthy (30-60 seconds)
docker-compose ps

# Run migrations
docker-compose run --rm app alembic upgrade head

# Initialize RBAC (if needed)
docker-compose run --rm app python scripts/init_rbac.py
```

### 4. Start Development Environment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app celery-worker frontend

# Access application
# - API: http://localhost:5001
# - API Docs: http://localhost:5001/docs
# - Frontend: http://localhost:3000
```

## 📁 Directory Structure

```
your-customer-platform/
├── src/                          # Backend Python code
│   ├── api/                      # API routes
│   │   └── routes/               # Individual route modules
│   ├── core/                     # Core infrastructure
│   │   ├── config.py            # Configuration management
│   │   ├── auth.py              # Authentication
│   │   └── logging.py           # Logging setup
│   ├── models/                   # SQLAlchemy models
│   │   └── database.py          # Database base configuration
│   ├── services/                 # Business logic services
│   ├── tasks/                    # Celery tasks
│   ├── middleware/               # FastAPI middleware
│   └── main.py                  # FastAPI application entry point
│
├── frontend/                      # React frontend
│   ├── src/
│   │   ├── components/           # React components
│   │   │   └── layout/          # Layout components (Navigation, Header, Layout)
│   │   ├── contexts/            # React contexts (AuthContext)
│   │   ├── pages/               # Page components
│   │   ├── services/            # API service clients
│   │   └── App.tsx             # Main app component
│   └── package.json
│
├── docker/                        # Docker configuration
│   ├── Dockerfile               # Backend Dockerfile
│   ├── docker-compose.yml       # Development compose file
│   └── entrypoint.sh           # Container entrypoint
│
├── alembic/                      # Database migrations
│   ├── versions/                # Migration files
│   └── env.py                  # Alembic environment
│
├── config/                       # Configuration files
│   └── customers/              # Customer-specific configs
│
├── scripts/                     # Utility scripts
│   ├── setup-local.sh          # Local setup script
│   └── init_rbac.py            # RBAC initialization
│
├── .env.example                 # Environment variable template
├── requirements.txt            # Python dependencies
├── alembic.ini                 # Alembic configuration
└── README.md                    # This file
```

## 🎨 Design System

### Navigation Structure

The left navigation follows a consistent structure:

```
┌─────────────────────────┐
│  Welcome back           │
│  [Avatar] User Name     │
│  [Role Badge]           │
├─────────────────────────┤
│  INSIGHTS               │
│  • My Insights          │
├─────────────────────────┤
│  DATA                   │
│  • Knowledge Base        │
│  • [Your Data Sources]  │
├─────────────────────────┤
│  [YOUR FEATURES]        │
│  • Feature 1            │
│  • Feature 2            │
├─────────────────────────┤
│  ADMINISTRATION         │
│  • Admin Settings        │
│  • Agent Configuration   │
└─────────────────────────┘
```

### Key Design Elements

1. **Navigation Width**: 
   - Expanded: `w-60` (240px)
   - Collapsed: `w-16` (64px)

2. **Color Scheme**: 
   - Uses Tailwind CSS with custom color tokens
   - Brand colors, surface colors, text colors defined in `tailwind.config.js`

3. **Typography**: 
   - Section headers: `text-xs text-muted-2 uppercase`
   - Navigation items: `text-sm text-text`

4. **Icons**: 
   - Uses Heroicons (`@heroicons/react/24/outline`)
   - Consistent icon sizing and styling

## 🔧 Critical Patterns

### 1. Database Session Management

**CRITICAL**: Never store database sessions in serializable state.

```python
# ✅ CORRECT: Module import, local sessions
from src.models import database

if database.SessionLocal is None:
    database.init_database()
db = database.SessionLocal()
try:
    # Use db
    pass
finally:
    db.close()

# ❌ WRONG: Direct import or storing in state
from src.models.database import SessionLocal  # Creates local binding!
class FlowState(BaseModel):
    db_session: Session  # Breaks Celery pickling!
```

### 2. Multi-Tenancy

All data must be filtered by `customer_id`:

```python
# ✅ CORRECT: Filter by customer_id
db.query(Document).filter(Document.customer_id == current_user.customer_id).all()

# ✅ CORRECT: Use company_hr_dataset for company-specific data
doc_tool = DocumentSearchTool(
    customer_id=user.customer_id,
    company_hr_dataset=target_company,  # Critical!
    limit=10
)
```

### 3. API Route Pattern

```python
from fastapi import APIRouter, Depends
from src.api.schemas import YourRequest, YourResponse
from src.middleware.authorization import require_permission
from src.models.database import get_db
from sqlalchemy.orm import Session

router = APIRouter(prefix="/v1/your-feature", tags=["Your Feature"])

@router.post("/endpoint", response_model=YourResponse)
async def your_endpoint(
    request: YourRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("your-feature:write"))
):
    # Implementation
    pass
```

### 4. Celery Task Pattern

```python
from src.celery_app import celery_app
from src.models import database

@celery_app.task(bind=True, max_retries=3)
def your_task(self, task_data: dict):
    # Initialize database
    if database.SessionLocal is None:
        database.init_database()
    db = database.SessionLocal()
    try:
        # Task implementation
        pass
    finally:
        db.close()
```

### 5. Frontend Component Pattern

```typescript
import React from 'react';
import { Layout } from '../components/layout/Layout';

export function YourFeaturePage() {
  return (
    <Layout pageTitle="Your Feature">
      <div className="p-6">
        {/* Your content */}
      </div>
    </Layout>
  );
}
```

## 📝 Customization Checklist

### Phase 1: Core Setup
- [ ] Update `CUSTOMER_ID` and `CUSTOMER_NAME` in `.env`
- [ ] Configure database credentials
- [ ] Add API keys (OpenAI, Anthropic, etc.)
- [ ] Generate and set encryption key
- [ ] Run database migrations
- [ ] Initialize RBAC (if needed)

### Phase 2: Navigation & Features
- [ ] Update `frontend/src/components/layout/Navigation.tsx` with your features
- [ ] Add route definitions in `frontend/src/App.tsx`
- [ ] Create page components in `frontend/src/pages/`
- [ ] Update navigation permissions as needed

### Phase 3: API Endpoints
- [ ] Create route modules in `src/api/routes/`
- [ ] Define Pydantic schemas in `src/api/schemas/`
- [ ] Implement service logic in `src/services/`
- [ ] Add database models in `src/models/` (if needed)
- [ ] Register routes in `src/main.py`

### Phase 4: Features & Products
- [ ] Build your specific features using platform patterns
- [ ] Add Celery tasks for async processing (if needed)
- [ ] Implement frontend components
- [ ] Add tests

### Phase 5: Polish
- [ ] Update branding (colors, logos)
- [ ] Customize navigation labels
- [ ] Add customer-specific documentation
- [ ] Configure production settings

## 🔍 Key Files to Customize

### Backend
- `src/core/config.py` - Application configuration
- `src/main.py` - FastAPI app setup and route registration
- `src/api/routes/` - Add your route modules here
- `src/models/` - Add database models here
- `src/services/` - Add business logic here

### Frontend
- `frontend/src/components/layout/Navigation.tsx` - **CRITICAL**: Navigation structure
- `frontend/src/App.tsx` - Route definitions
- `frontend/src/pages/` - Your page components
- `frontend/tailwind.config.js` - Design system colors

### Configuration
- `.env` - Environment variables
- `docker/docker-compose.yml` - Docker services
- `alembic/versions/` - Database migrations

## ⚠️ Critical Rules

1. **Always rebuild containers after code changes**:
   ```bash
   docker-compose build app celery-worker frontend
   docker-compose up -d app celery-worker frontend
   ```

2. **Never store database sessions in flow state** (breaks Celery)

3. **Always use module imports** for database (`from src.models import database`)

4. **Filter all queries by `customer_id`** for multi-tenancy

5. **Use `company_hr_dataset`** for company-specific document searches

6. **Only one container runs migrations** (`RUN_MIGRATIONS=true` only on `app`)

## 📚 Reference Documentation

- **[Main Onboarding Guide](../README.md)** - Comprehensive platform overview
- **[Engineering Tasks](../ENGINEERING_TASKS.md)** - Task breakdown for engineers
- **[Cookbook](../../cookbook/README.md)** - CrewAI and architecture patterns
- **[Repository Rules](../../.cursorrules)** - Critical development rules

## 🆘 Troubleshooting

### Database Connection Errors
- Wait 30-60 seconds after starting services
- Check `docker-compose ps` for service health
- Verify `DATABASE_URL` in `.env`

### Container Has Old Code
- Always rebuild: `docker-compose build --no-cache app`
- Restart: `docker-compose up -d app`

### Migration Errors
- Check only `app` container has `RUN_MIGRATIONS=true`
- Verify migration files are in `alembic/versions/`
- Check database connection

### Frontend Not Updating
- Rebuild frontend: `docker-compose build --no-cache frontend`
- Clear browser cache
- Check API URL in `frontend/orval.config.ts`

## ✅ Success Criteria

You'll know the skeleton is set up correctly when:

1. ✅ All Docker services start successfully
2. ✅ Database migrations run without errors
3. ✅ API docs accessible at `http://localhost:5001/docs`
4. ✅ Frontend loads at `http://localhost:3000`
5. ✅ Navigation displays correctly
6. ✅ Authentication flow works
7. ✅ You can add new routes and they appear in navigation

## 🎯 Next Steps

1. **Review the skeleton structure** - Understand what's included
2. **Follow Quick Start** - Get it running locally
3. **Customize navigation** - Add your features to the nav
4. **Build your first feature** - Use platform patterns
5. **Iterate and improve** - Validate patterns through usage

---

**Remember**: This skeleton provides the foundation. Build your features on top using established patterns. The goal is to validate and improve platform patterns through real usage.

