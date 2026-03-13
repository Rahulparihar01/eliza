# Platform Skeleton Setup Instructions

Step-by-step instructions for setting up a new platform instance from the skeleton.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11+ (for local development)
- Node.js 18+ and npm (for frontend development)
- Git

## Step 1: Initialize Repository

```bash
# Create new directory
mkdir your-customer-platform
cd your-customer-platform

# Initialize git
git init

# Copy skeleton files (adjust path as needed)
# Note: You'll need to copy from the actual eliza-platform repository
```

## Step 2: Configure Environment

### 2.1 Create .env File

```bash
# Copy template
cp .env.example .env

# Edit .env with your values
nano .env  # or use your preferred editor
```

### 2.2 Required Environment Variables

```bash
# Application Identity
CUSTOMER_ID=your_customer_id          # Lowercase, no spaces
CUSTOMER_NAME=Your Customer Name      # Display name
ENVIRONMENT=development               # development | production

# Database Configuration
DATABASE_URL=postgresql://user:password@postgres:5432/ai_platform
REDIS_URL=redis://redis:6379

# Neo4j Configuration
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# Security
JWT_SECRET_KEY=your-jwt-secret-key-here-min-32-chars
ENCRYPTION_KEY=your-encryption-key-here

# Generate encryption key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# AI Provider API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=...
DEFAULT_LLM_MODEL=gpt-4o-mini

# Celery Configuration
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
```

## Step 3: Start Infrastructure Services

```bash
# Start only infrastructure services first
docker-compose up -d postgres redis neo4j elasticsearch

# Wait for services to be healthy (check status)
docker-compose ps

# Check logs if needed
docker-compose logs postgres
```

**Wait 30-60 seconds** for services to fully initialize.

## Step 4: Initialize Database

### 4.1 Run Migrations

```bash
# Run all migrations
docker-compose run --rm app alembic upgrade head

# Verify migrations
docker-compose exec postgres psql -U user -d ai_platform -c "\dt"
```

### 4.2 Initialize RBAC (Optional)

```bash
# Initialize roles and permissions
docker-compose run --rm app python scripts/init_rbac.py

# Create admin user (if script exists)
docker-compose run --rm app python scripts/seed_admin_user.py
```

## Step 5: Start Application Services

```bash
# Start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f app celery-worker frontend
```

## Step 6: Verify Installation

### 6.1 Check API Health

```bash
# Health check
curl http://localhost:5001/health

# API documentation
open http://localhost:5001/docs
```

### 6.2 Check Frontend

```bash
# Open frontend
open http://localhost:3000
```

### 6.3 Verify Database Connection

```bash
# Connect to database
docker-compose exec postgres psql -U user -d ai_platform

# Check tables
\dt

# Exit
\q
```

## Step 7: Customize Navigation

### 7.1 Edit Navigation Component

Edit `frontend/src/components/layout/Navigation.tsx`:

```typescript
// Add your features to navigationConfig array
const navigationConfig: NavigationItem[] = [
  // ... existing items ...
  
  // Add your features
  {
    label: 'Your Feature',
    path: '/your-feature',
    icon: 'briefcase',
    requiredPermissions: ['your-feature:read'],
  },
];
```

### 7.2 Add Routes

Edit `frontend/src/App.tsx`:

```typescript
import { YourFeaturePage } from './pages/YourFeaturePage';

// Add route
<Route path="/your-feature" element={<YourFeaturePage />} />
```

### 7.3 Rebuild Frontend

```bash
docker-compose build frontend
docker-compose up -d frontend
```

## Step 8: Create Your First Feature

### 8.1 Backend: Create API Route

Create `src/api/routes/your_feature.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.models.database import get_db
from src.middleware.authorization import require_permission

router = APIRouter(prefix="/v1/your-feature", tags=["Your Feature"])

@router.get("/")
async def get_items(
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("your-feature:read"))
):
    return {"message": "Your feature works!"}
```

### 8.2 Register Route

Edit `src/main.py`:

```python
from api.routes import your_feature

# Register router
app.include_router(your_feature.router, prefix="/api")
```

### 8.3 Frontend: Create Page

Create `frontend/src/pages/YourFeaturePage.tsx`:

```typescript
import React from 'react';
import { Layout } from '../components/layout/Layout';

export function YourFeaturePage() {
  return (
    <Layout pageTitle="Your Feature">
      <div className="p-6">
        <h1>Your Feature</h1>
        <p>This is your feature page.</p>
      </div>
    </Layout>
  );
}
```

### 8.4 Rebuild Services

```bash
# Rebuild backend
docker-compose build app
docker-compose up -d app

# Rebuild frontend
docker-compose build frontend
docker-compose up -d frontend
```

## Step 9: Verify Everything Works

### 9.1 Test API Endpoint

```bash
# Get auth token first (login)
curl -X POST http://localhost:5001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "password"}'

# Use token in request
curl http://localhost:5001/api/v1/your-feature \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 9.2 Test Frontend

1. Navigate to `http://localhost:3000`
2. Login with admin credentials
3. Click on "Your Feature" in navigation
4. Verify page loads correctly

## Common Issues & Solutions

### Issue: Services Won't Start

**Solution**: Check logs
```bash
docker-compose logs app
docker-compose logs postgres
```

### Issue: Database Connection Failed

**Solution**: 
1. Verify services are healthy: `docker-compose ps`
2. Check DATABASE_URL in .env
3. Wait longer for postgres to initialize (60+ seconds)

### Issue: Migration Errors

**Solution**:
1. Check only `app` container has `RUN_MIGRATIONS=true`
2. Verify migration files exist in `alembic/versions/`
3. Check database connection

### Issue: Frontend Shows Old Code

**Solution**: Rebuild frontend
```bash
docker-compose build --no-cache frontend
docker-compose up -d frontend
```

### Issue: API Returns 401 Unauthorized

**Solution**:
1. Check JWT_SECRET_KEY is set
2. Verify token is valid
3. Check user has required permissions

## Next Steps

1. **Customize branding**: Update colors, logos, company name
2. **Add features**: Build your specific features using platform patterns
3. **Configure permissions**: Set up RBAC for your use case
4. **Add tests**: Write tests for your features
5. **Documentation**: Document your custom features

## Production Deployment

When ready for production:

1. **Update environment**: Set `ENVIRONMENT=production`
2. **Secure secrets**: Use proper secret management
3. **Configure domains**: Update CORS and allowed hosts
4. **Set resource limits**: Configure Docker resource limits
5. **Enable monitoring**: Set up logging and monitoring
6. **Backup strategy**: Configure database backups

---

**Remember**: Always rebuild containers after code changes. The skeleton provides the foundation - build your features on top using established patterns.

