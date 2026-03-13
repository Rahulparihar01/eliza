# Platform Skeleton Copy Checklist

This checklist helps you identify what files to copy from the main eliza-platform repository to create your new platform instance.

## 📋 Overview

The platform skeleton provides **documentation and guidance**. You'll need to copy actual code files from the eliza-platform repository to create a working instance.

## ✅ Files to Copy from eliza-platform

### Core Infrastructure (REQUIRED)

```
src/core/
├── config.py                    # Configuration management
├── auth.py                      # Authentication logic
├── logging.py                   # Logging setup
├── exceptions.py                # Custom exceptions
└── auth_context.py              # Auth context helpers

src/models/
├── database.py                   # Database base (CRITICAL)
├── auth.py                      # User, Role, Permission models
└── customer.py                  # Customer models

src/middleware/
├── authorization.py              # RBAC middleware
└── logging.py                   # Request logging middleware

src/utils/
└── encryption.py                # Encryption utilities
```

### API Infrastructure (REQUIRED)

```
src/api/routes/
├── __init__.py
├── health.py                    # Health check endpoints
└── auth.py                      # Authentication endpoints

src/api/schemas/
├── __init__.py
├── auth.py                      # Auth request/response models
└── users.py                     # User models

src/main.py                      # FastAPI application entry point
src/celery_app.py                # Celery configuration
```

### Frontend Infrastructure (REQUIRED)

```
frontend/src/components/layout/
├── Layout.tsx                   # Main layout wrapper
├── Navigation.tsx                # Left navigation (CRITICAL - customize this)
├── Header.tsx                    # Top header
└── NavItem.tsx                  # Navigation item component

frontend/src/contexts/
└── AuthContext.tsx              # Authentication context

frontend/src/App.tsx              # Main app with routes
frontend/src/index.tsx            # Entry point

frontend/tailwind.config.js      # Design system configuration
frontend/orval.config.ts          # API client generation
frontend/package.json             # Dependencies
frontend/tsconfig.json            # TypeScript config
```

### Docker Configuration (REQUIRED)

```
docker/
├── Dockerfile                   # Backend Dockerfile
├── docker-compose.yml           # Development compose file
├── entrypoint.sh                # Container entrypoint
└── config/                      # Docker configs (if using logstash)
```

### Database (REQUIRED)

```
alembic/
├── env.py                       # Alembic environment
├── script.py.mako                # Migration template
└── versions/
    ├── 001_initial_schema.py    # Initial schema
    └── 002_add_auth_tables.py   # Auth tables

alembic.ini                      # Alembic configuration
```

### Configuration (REQUIRED)

```
config/
├── customer_config.py           # Customer config loader
└── customers/
    └── customer-template/
        └── config.yml           # Template config
```

### Scripts (RECOMMENDED)

```
scripts/
├── setup-local.sh               # Local setup script
├── init_rbac.py                 # RBAC initialization
└── seed_admin_user.py           # Admin user creation
```

### Optional (Add as Needed)

```
src/services/
├── base_service.py              # Base service class
├── auth_service.py              # Auth service
└── document_service.py          # Document service (if using documents)

src/tasks/
└── documents.py                 # Document tasks (if using documents)

src/api/routes/
├── documents.py                # Document routes (if using documents)
└── business_intelligence.py     # BI routes (if using BI)

frontend/src/pages/
├── HomePage.tsx                # Home page
└── KnowledgeBasePage.tsx       # Knowledge base (if using documents)
```

## 🎯 Customization Points

After copying, you'll customize:

### 1. Navigation (CRITICAL)
**File**: `frontend/src/components/layout/Navigation.tsx`
- Update `navigationConfig` array with your features
- Group features into sections
- Set permissions

### 2. Routes
**File**: `frontend/src/App.tsx`
- Add routes for your features
- Import page components

### 3. Environment
**File**: `.env`
- Set `CUSTOMER_ID` and `CUSTOMER_NAME`
- Configure database credentials
- Add API keys

### 4. API Routes
**Files**: `src/api/routes/your_feature.py`
- Create route modules for your features
- Register in `src/main.py`

### 5. Database Models
**Files**: `src/models/your_feature.py`
- Create models for your features
- Create migrations in `alembic/versions/`

## 📝 Copy Process

### Step 1: Create Directory Structure

```bash
mkdir your-customer-platform
cd your-customer-platform
mkdir -p src/core src/models src/api/routes src/api/schemas
mkdir -p src/middleware src/services src/tasks src/utils
mkdir -p frontend/src/components/layout frontend/src/pages
mkdir -p frontend/src/contexts frontend/src/services
mkdir -p docker config/customers docker/config
mkdir -p alembic/versions scripts
```

### Step 2: Copy Core Files

```bash
# From eliza-platform repository root

# Core infrastructure
cp -r src/core/* your-customer-platform/src/core/
cp -r src/models/database.py your-customer-platform/src/models/
cp -r src/models/auth.py your-customer-platform/src/models/
cp -r src/models/customer.py your-customer-platform/src/models/
cp -r src/middleware/* your-customer-platform/src/middleware/
cp -r src/utils/* your-customer-platform/src/utils/

# API infrastructure
cp src/main.py your-customer-platform/src/
cp src/celery_app.py your-customer-platform/src/
cp -r src/api/routes/health.py your-customer-platform/src/api/routes/
cp -r src/api/routes/auth.py your-customer-platform/src/api/routes/
cp -r src/api/schemas/auth.py your-customer-platform/src/api/schemas/
cp -r src/api/schemas/users.py your-customer-platform/src/api/schemas/

# Frontend infrastructure
cp -r frontend/src/components/layout/* your-customer-platform/frontend/src/components/layout/
cp -r frontend/src/contexts/AuthContext.tsx your-customer-platform/frontend/src/contexts/
cp frontend/src/App.tsx your-customer-platform/frontend/src/
cp frontend/src/index.tsx your-customer-platform/frontend/src/
cp frontend/tailwind.config.js your-customer-platform/frontend/
cp frontend/orval.config.ts your-customer-platform/frontend/
cp frontend/package.json your-customer-platform/frontend/
cp frontend/tsconfig.json your-customer-platform/frontend/

# Docker
cp -r docker/* your-customer-platform/docker/

# Database
cp -r alembic/* your-customer-platform/alembic/
cp alembic.ini your-customer-platform/

# Configuration
cp -r config/customer_config.py your-customer-platform/config/
cp -r config/customers/customer-template your-customer-platform/config/customers/

# Scripts
cp scripts/setup-local.sh your-customer-platform/scripts/
cp scripts/init_rbac.py your-customer-platform/scripts/
```

### Step 3: Copy Dependencies

```bash
# Python dependencies
cp requirements.txt your-customer-platform/

# Frontend dependencies (package.json already copied)
# Run: cd frontend && npm install
```

### Step 4: Create Environment File

```bash
# Copy template
cp .env.example your-customer-platform/.env

# Edit with your values
nano your-customer-platform/.env
```

### Step 5: Initialize Git

```bash
cd your-customer-platform
git init
git add .
git commit -m "Initial platform skeleton"
```

## ⚠️ Critical Files

These files are **absolutely required** and must be copied correctly:

1. **`src/models/database.py`** - Database session management (CRITICAL)
2. **`frontend/src/components/layout/Navigation.tsx`** - Navigation structure
3. **`src/core/config.py`** - Configuration management
4. **`src/main.py`** - FastAPI app setup
5. **`docker/docker-compose.yml`** - Docker services
6. **`alembic/env.py`** - Migration environment

## 🔍 Verification Checklist

After copying, verify:

- [ ] All core files copied
- [ ] Navigation component exists and is customizable
- [ ] Database models include BaseModel pattern
- [ ] Docker compose file has all required services
- [ ] Environment file template exists
- [ ] Alembic migrations directory exists
- [ ] Frontend dependencies can be installed (`npm install` works)
- [ ] Python dependencies can be installed (`pip install -r requirements.txt` works)

## 🚀 Next Steps

After copying:

1. Follow [SETUP_INSTRUCTIONS.md](./SETUP_INSTRUCTIONS.md)
2. Customize [Navigation](./NAVIGATION_GUIDE.md)
3. Review [Critical Patterns](./CRITICAL_PATTERNS.md)
4. Build your features using platform patterns

## 📚 Reference

- [Main README](./README.md) - Overview
- [Setup Instructions](./SETUP_INSTRUCTIONS.md) - Step-by-step setup
- [Navigation Guide](./NAVIGATION_GUIDE.md) - Customize navigation
- [Critical Patterns](./CRITICAL_PATTERNS.md) - Required patterns
- [Directory Structure](./DIRECTORY_STRUCTURE.md) - Complete structure

---

**Note**: This checklist assumes you have access to the eliza-platform repository. Adjust paths as needed for your environment.

