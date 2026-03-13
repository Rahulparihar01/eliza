# ELIZA Accelerate Platform - AWS Fargate Deployment Guide

## Platform Overview

**ELIZA Accelerate** is a multi-tenant AI enablement platform built on a Python/FastAPI backend with a React frontend. The platform uses a modular **applet** system that allows deploying only the features a customer needs, reducing infrastructure costs and attack surface.

This deployment covers the **Adoption Analytics** applet (`APPLETS=adoption`), which provides:

- **ChatGPT Enterprise usage analytics** - Syncs conversation metadata, GPT usage, and user activity from OpenAI's Compliance API
- **Daily metrics dashboard** - Active users, message counts, model breakdowns, top GPTs, and usage trends
- **Cross-tenant data sharing** - Secure sharing of adoption metrics between organizational units
- **Scheduled sync** - Configurable cron-based background sync via Celery Beat
- **Integrity checks** - Pre-sync consistency validation and auto-recovery from partial syncs

The adoption applet connects to the **ChatGPT Enterprise Compliance API** (`https://api.chatgpt.com/v1`) using an API key with `compliance_export` scope to pull conversation metadata (no message content), GPT catalog data, and user activity into PostgreSQL for dashboarding.

---

## Architecture Overview

```
                         ┌─────────────────────────────────────────────────┐
                         │              AWS Cloud (VPC)                    │
                         │                                                │
    Users ──── HTTPS ──▶ │  ┌──────────────────────────────────────────┐  │
                         │  │     Application Load Balancer (ALB)       │  │
                         │  │     - TLS termination                     │  │
                         │  │     - Path-based routing                  │  │
                         │  └──────┬──────────────────────┬────────────┘  │
                         │         │                      │               │
                         │    /* (frontend)         /v1/* (api)           │
                         │         │                      │               │
                         │  ┌──────▼──────┐    ┌──────────▼──────────┐   │
                         │  │  ECS Fargate │    │    ECS Fargate      │   │
                         │  │  Frontend    │    │    App (API)        │   │
                         │  │  (nginx)     │    │    (FastAPI)        │   │
                         │  └─────────────┘    └─────────┬───────────┘   │
                         │                               │               │
                         │         ┌─────────────────────┼──────────┐    │
                         │         │                     │          │    │
                         │  ┌──────▼──────┐    ┌─────────▼────┐     │    │
                         │  │  ECS Fargate │    │  ECS Fargate │     │    │
                         │  │  Celery      │    │  Celery Beat │     │    │
                         │  │  Worker      │    │  (scheduler) │     │    │
                         │  └──────┬───┬──┘    └──────────────┘     │    │
                         │         │   │                             │    │
                         │    ┌────▼┐ ┌▼──────────────┐             │    │
                         │    │ RDS │ │  ElastiCache   │             │    │
                         │    │ PG  │ │  Redis         │             │    │
                         │    └─────┘ └───────────────┘             │    │
                         │                                          │    │
                         │   ┌──────────────────────────────────┐   │    │
                         │   │ AWS Secrets Manager               │   │    │
                         │   │ (API keys, DB creds, encryption) │   │    │
                         │   └──────────────────────────────────┘   │    │
                         └─────────────────────────────────────────────┘
```

### Service Inventory (Adoption-Only)

For the adoption applet, the deployment is streamlined. Several services from the full platform (Neo4j, Elasticsearch, Logstash, Kibana, Langfuse) are **not required**.

| Service | Fargate Task | Purpose | Required? |
|---------|-------------|---------|-----------|
| **Frontend** | `eliza-frontend` | React SPA served by nginx, proxies `/v1/*` to API | Yes |
| **App (API)** | `eliza-app` | FastAPI backend, runs DB migrations on startup | Yes |
| **Celery Worker** | `eliza-celery-worker` | Processes adoption sync tasks | Yes |
| **Celery Beat** | `eliza-celery-beat` | Cron scheduler, dispatches sync jobs every 60s | Yes |
| **PostgreSQL** | AWS RDS | Primary data store | Yes (managed) |
| **Redis** | AWS ElastiCache | Celery broker + result backend | Yes (managed) |
| **Neo4j** | - | Knowledge graph (not used by adoption) | No |
| **Elasticsearch** | - | Search indexing (not used by adoption) | No |
| **Logstash / Kibana** | - | Log pipeline (not used by adoption) | No |
| **Langfuse** | - | LLM observability (optional, no LLM calls in adoption) | No |

---

## AWS Resources Required

### 1. Networking

| Resource | Specification | Notes |
|----------|--------------|-------|
| **VPC** | 1x VPC with DNS support enabled | Dedicated or shared |
| **Subnets** | 2+ public subnets, 2+ private subnets across 2 AZs minimum | Fargate tasks run in private subnets |
| **NAT Gateway** | 1-2 NAT Gateways | Required for Fargate tasks in private subnets to reach ECR, OpenAI API, etc. |
| **Internet Gateway** | 1x IGW | For ALB in public subnets |
| **Security Groups** | 4 (ALB, App, Workers, Data) | See security group rules below |

### 2. Compute (ECS Fargate)

| Resource | Specification | Notes |
|----------|--------------|-------|
| **ECS Cluster** | 1x cluster | `eliza-adoption` |
| **ECR Repositories** | 2 (backend, frontend) | Stores Docker images |
| **Task Definitions** | 4 (frontend, app, worker, beat) | See sizing below |
| **ECS Services** | 4 | One per task definition |

#### Task Sizing

| Task | CPU | Memory | Desired Count | Min/Max (Auto-scale) |
|------|-----|--------|---------------|----------------------|
| `eliza-frontend` | 0.25 vCPU | 512 MB | 2 | 2/4 |
| `eliza-app` | 1 vCPU | 4 GB | 2 | 2/4 |
| `eliza-celery-worker` | 1 vCPU | 4 GB | 1 | 1/3 |
| `eliza-celery-beat` | 0.25 vCPU | 512 MB | 1 | 1/1 (singleton) |

### 3. Data Stores (Managed)

| Resource | Specification | Notes |
|----------|--------------|-------|
| **RDS PostgreSQL** | `db.t3.medium` or `db.r6g.large`, PostgreSQL 15, Multi-AZ | 20 GB gp3 storage, auto-scaling up to 100 GB |
| **ElastiCache Redis** | `cache.t3.small`, Redis 7.x, single-node or cluster mode disabled | Used as Celery broker (`/0`) and result backend (`/1`) |

### 4. Load Balancing & DNS

| Resource | Specification | Notes |
|----------|--------------|-------|
| **Application Load Balancer** | 1x ALB in public subnets | TLS termination with ACM certificate |
| **Target Groups** | 2 (frontend on port 80, app on port 5001) | Health check paths below |
| **ACM Certificate** | 1x for your domain | e.g., `adoption.yourcompany.com` |
| **Route 53** (or external DNS) | A/AAAA alias record to ALB | |

### 5. Security & Secrets

| Resource | Specification | Notes |
|----------|--------------|-------|
| **AWS Secrets Manager** | 1 secret with multiple key-value pairs | API keys, DB credentials, encryption keys |
| **IAM Roles** | Task execution role, task role | ECR pull, Secrets Manager read, CloudWatch logs |
| **KMS Key** (optional) | 1 CMK for encrypting secrets and RDS | |

### 6. Observability

| Resource | Specification | Notes |
|----------|--------------|-------|
| **CloudWatch Log Groups** | 4 (one per service) | `/ecs/eliza-frontend`, `/ecs/eliza-app`, etc. |
| **CloudWatch Alarms** | CPU, memory, unhealthy host count | |
| **CloudWatch Container Insights** | Enable on ECS cluster | |

---

## Container Images

Two Docker images are built from the repository:

### Backend Image (API + Workers + Beat)

All three backend services (app, celery-worker, celery-beat) use the **same Docker image** with different `CMD` overrides.

```
# Build from repo root
docker build -f docker/Dockerfile --build-arg APPLETS=adoption -t eliza-backend .
```

| Service | CMD Override |
|---------|-------------|
| **App** | `python -m uvicorn src.main:app --host 0.0.0.0 --port 5001` (default) |
| **Celery Worker** | `celery -A src.celery_app worker --loglevel=info --concurrency=2 --max-tasks-per-child=50` |
| **Celery Beat** | `celery -A src.celery_app beat --loglevel=info --pidfile=/tmp/celerybeat.pid` |

### Frontend Image

```
# Build from frontend/ directory
docker build --build-arg REACT_APP_API_URL="" --build-arg REACT_APP_APPLETS=adoption -t eliza-frontend frontend/
```

The frontend uses **relative URLs** (`/v1/*`) for API calls. Nginx inside the container proxies these to the backend. In the AWS deployment, the ALB handles this routing instead, so the `REACT_APP_API_URL` should be left empty (the default).

### ECR Push

```bash
# Authenticate with ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag eliza-backend:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/eliza-backend:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/eliza-backend:latest

docker tag eliza-frontend:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/eliza-frontend:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/eliza-frontend:latest
```

---

## ECS Task Definitions

### Frontend Task Definition

```json
{
  "family": "eliza-frontend",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "frontend",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/eliza-frontend:latest",
      "portMappings": [
        { "containerPort": 80, "protocol": "tcp" }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost/ || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 10
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/eliza-frontend",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "frontend"
        }
      }
    }
  ]
}
```

**Important - Frontend Nginx Config Change:** Since the ALB is routing `/v1/*` directly to the app service, the frontend nginx config needs to proxy to the ALB or the app service's internal DNS. There are two strategies:

- **Option A (recommended):** Use **ALB path-based routing**. The ALB sends `/v1/*` to the app target group and `/*` to the frontend target group. The frontend nginx does not need to proxy API calls at all; the browser makes requests directly to the ALB on `/v1/*`.
- **Option B:** Use ECS **Service Connect** or **Cloud Map** so the frontend container can resolve `app` as a hostname. Update `nginx.conf` to `proxy_pass http://app.eliza.local:5001;`.

Option A is simpler and recommended.

### App (API) Task Definition

```json
{
  "family": "eliza-app",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "4096",
  "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/elizaTaskRole",
  "containerDefinitions": [
    {
      "name": "app",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/eliza-backend:latest",
      "portMappings": [
        { "containerPort": 5001, "protocol": "tcp" }
      ],
      "environment": [
        { "name": "RUN_MIGRATIONS", "value": "true" },
        { "name": "INIT_TENANT", "value": "true" },
        { "name": "APPLETS", "value": "adoption" },
        { "name": "ENVIRONMENT", "value": "production" },
        { "name": "LOG_LEVEL", "value": "INFO" },
        { "name": "PYTHONPATH", "value": "/app" },
        { "name": "ALLOWED_ORIGINS", "value": "https://adoption.yourcompany.com" },
        { "name": "ELASTICSEARCH_SYNC_ENABLED", "value": "false" },
        { "name": "NEO4J_SYNC_ENABLED", "value": "false" },
        { "name": "LOGSTASH_ENABLED", "value": "false" },
        { "name": "LANGFUSE_ENABLED", "value": "false" },
        { "name": "DEFAULT_LLM_MODEL", "value": "gpt-4o-mini" },
        { "name": "LOG_TO_FILE", "value": "false" },
        { "name": "LOG_JSON_FORMAT", "value": "true" }
      ],
      "secrets": [
        { "name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:DATABASE_URL::" },
        { "name": "REDIS_URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:REDIS_URL::" },
        { "name": "CELERY_BROKER_URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:CELERY_BROKER_URL::" },
        { "name": "CELERY_RESULT_BACKEND", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:CELERY_RESULT_BACKEND::" },
        { "name": "OPENAI_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:OPENAI_API_KEY::" },
        { "name": "ENCRYPTION_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:ENCRYPTION_KEY::" },
        { "name": "ADMIN_EMAIL", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:ADMIN_EMAIL::" },
        { "name": "ADMIN_PASSWORD", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:ADMIN_PASSWORD::" },
        { "name": "CUSTOMER_ID", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:CUSTOMER_ID::" },
        { "name": "CUSTOMER_NAME", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:CUSTOMER_NAME::" }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:5001/health/ready || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 5,
        "startPeriod": 120
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/eliza-app",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "app"
        }
      }
    }
  ]
}
```

### Celery Worker Task Definition

Same image as the app, with a command override. Does **not** run migrations.

```json
{
  "family": "eliza-celery-worker",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "4096",
  "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/elizaTaskRole",
  "containerDefinitions": [
    {
      "name": "celery-worker",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/eliza-backend:latest",
      "command": [
        "celery", "-A", "src.celery_app", "worker",
        "--loglevel=info", "--concurrency=2", "--max-tasks-per-child=50"
      ],
      "environment": [
        { "name": "APPLETS", "value": "adoption" },
        { "name": "ENVIRONMENT", "value": "production" },
        { "name": "LOG_LEVEL", "value": "INFO" },
        { "name": "PYTHONPATH", "value": "/app" },
        { "name": "ELASTICSEARCH_SYNC_ENABLED", "value": "false" },
        { "name": "NEO4J_SYNC_ENABLED", "value": "false" },
        { "name": "LOGSTASH_ENABLED", "value": "false" },
        { "name": "LANGFUSE_ENABLED", "value": "false" },
        { "name": "LOG_TO_FILE", "value": "false" },
        { "name": "LOG_JSON_FORMAT", "value": "true" }
      ],
      "secrets": [
        { "name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:DATABASE_URL::" },
        { "name": "REDIS_URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:REDIS_URL::" },
        { "name": "CELERY_BROKER_URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:CELERY_BROKER_URL::" },
        { "name": "CELERY_RESULT_BACKEND", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:CELERY_RESULT_BACKEND::" },
        { "name": "OPENAI_API_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:OPENAI_API_KEY::" },
        { "name": "ENCRYPTION_KEY", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:ENCRYPTION_KEY::" },
        { "name": "CUSTOMER_ID", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:CUSTOMER_ID::" }
      ],
      "healthCheck": {
        "command": ["CMD-SHELL", "celery -A src.celery_app inspect ping -d celery@$HOSTNAME || exit 1"],
        "interval": 30,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 60
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/eliza-celery-worker",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "worker"
        }
      }
    }
  ]
}
```

### Celery Beat Task Definition

The Beat scheduler must run as a **singleton** (exactly 1 task). It dispatches adoption sync jobs every 60 seconds.

```json
{
  "family": "eliza-celery-beat",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/elizaTaskRole",
  "containerDefinitions": [
    {
      "name": "celery-beat",
      "image": "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/eliza-backend:latest",
      "command": [
        "celery", "-A", "src.celery_app", "beat",
        "--loglevel=info", "--pidfile=/tmp/celerybeat.pid"
      ],
      "environment": [
        { "name": "APPLETS", "value": "adoption" },
        { "name": "ENVIRONMENT", "value": "production" },
        { "name": "LOG_LEVEL", "value": "INFO" },
        { "name": "PYTHONPATH", "value": "/app" }
      ],
      "secrets": [
        { "name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:DATABASE_URL::" },
        { "name": "REDIS_URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:REDIS_URL::" },
        { "name": "CELERY_BROKER_URL", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:CELERY_BROKER_URL::" },
        { "name": "CELERY_RESULT_BACKEND", "valueFrom": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption:CELERY_RESULT_BACKEND::" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/eliza-celery-beat",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "beat"
        }
      }
    }
  ]
}
```

---

## ALB Configuration

### Listener Rules

| Priority | Condition | Target Group | Notes |
|----------|-----------|-------------|-------|
| 1 | Path pattern: `/v1/*` | `eliza-app-tg` (port 5001) | API requests |
| 2 | Path pattern: `/api/*` | `eliza-app-tg` (port 5001) | Legacy API routes |
| 3 | Path pattern: `/health/ready` | `eliza-app-tg` (port 5001) | Backend health |
| 4 | Path pattern: `/docs`, `/redoc`, `/openapi.json` | `eliza-app-tg` (port 5001) | API documentation |
| Default | All other paths | `eliza-frontend-tg` (port 80) | React SPA |

### Target Group Health Checks

| Target Group | Path | Port | Interval | Healthy Threshold | Unhealthy Threshold |
|-------------|------|------|----------|-------------------|---------------------|
| `eliza-app-tg` | `/health/ready` | 5001 | 30s | 2 | 5 |
| `eliza-frontend-tg` | `/health` | 80 | 30s | 2 | 3 |

### HTTPS Configuration

- Listener on port 443 with ACM certificate
- HTTP (port 80) listener with redirect to HTTPS
- SSL policy: `ELBSecurityPolicy-TLS13-1-2-2021-06` or newer

---

## Security Group Rules

### ALB Security Group (`sg-alb`)

| Direction | Port | Source/Dest | Purpose |
|-----------|------|-------------|---------|
| Inbound | 443 | `0.0.0.0/0` | HTTPS from internet |
| Inbound | 80 | `0.0.0.0/0` | HTTP redirect |
| Outbound | All | `sg-app` | To app tasks |
| Outbound | All | `sg-frontend` | To frontend tasks |

### App/Frontend Security Group (`sg-app`)

| Direction | Port | Source/Dest | Purpose |
|-----------|------|-------------|---------|
| Inbound | 5001 | `sg-alb` | API traffic from ALB |
| Inbound | 80 | `sg-alb` | Frontend traffic from ALB |
| Outbound | 5432 | `sg-data` | To RDS PostgreSQL |
| Outbound | 6379 | `sg-data` | To ElastiCache Redis |
| Outbound | 443 | `0.0.0.0/0` | OpenAI API, ECR, Secrets Manager |

### Worker Security Group (`sg-workers`)

| Direction | Port | Source/Dest | Purpose |
|-----------|------|-------------|---------|
| Outbound | 5432 | `sg-data` | To RDS PostgreSQL |
| Outbound | 6379 | `sg-data` | To ElastiCache Redis |
| Outbound | 443 | `0.0.0.0/0` | OpenAI Compliance API, ECR |

### Data Security Group (`sg-data`)

| Direction | Port | Source/Dest | Purpose |
|-----------|------|-------------|---------|
| Inbound | 5432 | `sg-app`, `sg-workers` | PostgreSQL from app + workers |
| Inbound | 6379 | `sg-app`, `sg-workers` | Redis from app + workers |

---

## AWS Secrets Manager

Create a secret named `eliza/adoption` with the following key-value pairs:

```json
{
  "DATABASE_URL": "postgresql://<DB_USER>:<DB_PASSWORD>@<RDS_ENDPOINT>:5432/ai_enablement",
  "REDIS_URL": "redis://<ELASTICACHE_ENDPOINT>:6379",
  "CELERY_BROKER_URL": "redis://<ELASTICACHE_ENDPOINT>:6379/0",
  "CELERY_RESULT_BACKEND": "redis://<ELASTICACHE_ENDPOINT>:6379/1",
  "OPENAI_API_KEY": "<your-openai-api-key>",
  "ENCRYPTION_KEY": "<generate-with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'>",
  "ADMIN_EMAIL": "admin@yourcompany.com",
  "ADMIN_PASSWORD": "<strong-admin-password>",
  "CUSTOMER_ID": "<your-customer-id>",
  "CUSTOMER_NAME": "<Your Company Name>",
  "FRONTEND_URL": "https://adoption.yourcompany.com"
}
```

### IAM Policy for Task Execution Role

The ECS task execution role needs permission to pull secrets:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:<ACCOUNT_ID>:secret:eliza/adoption-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:us-east-1:<ACCOUNT_ID>:log-group:/ecs/eliza-*:*"
    }
  ]
}
```

---

## RDS PostgreSQL Setup

### Instance Configuration

| Setting | Value |
|---------|-------|
| Engine | PostgreSQL 15 |
| Instance class | `db.t3.medium` (prod: `db.r6g.large`) |
| Storage | 20 GB gp3, auto-scaling to 100 GB |
| Multi-AZ | Yes (production) |
| Database name | `ai_enablement` |
| Master username | `eliza_admin` |
| Backup retention | 7 days |
| Encryption | Yes (KMS) |
| VPC | Same VPC as ECS |
| Subnet group | Private subnets only |
| Security group | `sg-data` |
| Parameter group | Default PostgreSQL 15 |

### Database Initialization

The app container handles this automatically on first boot when `INIT_TENANT=true`:

1. **Entrypoint script** waits for PostgreSQL to be ready (up to 60s)
2. **Alembic migrations** run with `--applets adoption` to only apply adoption-tagged migrations
3. **Tenant initialization** creates the platform tenant and admin user

After the first successful startup, set `INIT_TENANT=false` in the app task definition to avoid re-running tenant initialization on every deployment.

---

## ElastiCache Redis Setup

### Instance Configuration

| Setting | Value |
|---------|-------|
| Engine | Redis 7.x |
| Node type | `cache.t3.small` (prod: `cache.r6g.large`) |
| Number of nodes | 1 (or 2 for Multi-AZ with automatic failover) |
| Cluster mode | Disabled |
| Encryption in transit | Yes (TLS) |
| Encryption at rest | Yes |
| VPC | Same VPC as ECS |
| Subnet group | Private subnets only |
| Security group | `sg-data` |

### Redis URL Format

- If TLS is enabled: `rediss://<ENDPOINT>:6379`
- If TLS is disabled: `redis://<ENDPOINT>:6379`

The Celery broker uses database `0` and the result backend uses database `1`:
- `CELERY_BROKER_URL=redis://<ENDPOINT>:6379/0`
- `CELERY_RESULT_BACKEND=redis://<ENDPOINT>:6379/1`

---

## Environment Variables Reference

### Required for All Backend Services

| Variable | Value | Notes |
|----------|-------|-------|
| `APPLETS` | `adoption` | Only load adoption routes, tasks, and migrations |
| `DATABASE_URL` | `postgresql://...` | From Secrets Manager |
| `REDIS_URL` | `redis://...` | From Secrets Manager |
| `CELERY_BROKER_URL` | `redis://.../0` | From Secrets Manager |
| `CELERY_RESULT_BACKEND` | `redis://.../1` | From Secrets Manager |
| `ENCRYPTION_KEY` | Fernet key | From Secrets Manager, used to encrypt provider API keys at rest |
| `ENVIRONMENT` | `production` | |
| `LOG_LEVEL` | `INFO` | |
| `PYTHONPATH` | `/app` | |

### Required for App Service Only

| Variable | Value | Notes |
|----------|-------|-------|
| `RUN_MIGRATIONS` | `true` | Only the app service runs migrations |
| `INIT_TENANT` | `true` (first deploy), then `false` | Creates platform tenant + admin |
| `ADMIN_EMAIL` | From Secrets Manager | Initial admin login |
| `ADMIN_PASSWORD` | From Secrets Manager | Initial admin password |
| `CUSTOMER_ID` | From Secrets Manager | Tenant identifier |
| `CUSTOMER_NAME` | From Secrets Manager | Display name |
| `FRONTEND_URL` | `https://adoption.yourcompany.com` | Used in invite links |
| `ALLOWED_ORIGINS` | `https://adoption.yourcompany.com` | CORS origins |

### Required for Celery Worker

| Variable | Value | Notes |
|----------|-------|-------|
| `OPENAI_API_KEY` | From Secrets Manager | Used by the adoption sync service to call the Compliance API |
| `CUSTOMER_ID` | From Secrets Manager | |

### Disabled Features (Adoption-Only)

These should be explicitly disabled since their backing services are not deployed:

| Variable | Value | Why |
|----------|-------|-----|
| `ELASTICSEARCH_SYNC_ENABLED` | `false` | No Elasticsearch deployed |
| `NEO4J_SYNC_ENABLED` | `false` | No Neo4j deployed |
| `LOGSTASH_ENABLED` | `false` | No Logstash deployed |
| `LANGFUSE_ENABLED` | `false` | No Langfuse deployed (optional, can enable if desired) |
| `LOG_TO_FILE` | `false` | Use CloudWatch instead of file logging |

### Frontend Build Args

| Variable | Value | Notes |
|----------|-------|-------|
| `REACT_APP_API_URL` | `""` (empty) | Uses relative URLs; ALB routes `/v1/*` to backend |
| `REACT_APP_APPLETS` | `adoption` | Only builds adoption UI pages |

---

## Deployment Procedure

### Phase 1: Infrastructure Provisioning

1. **Create VPC** with public and private subnets across 2+ AZs
2. **Create NAT Gateway(s)** in public subnet(s)
3. **Create Security Groups** as defined above
4. **Provision RDS PostgreSQL** in private subnets
5. **Provision ElastiCache Redis** in private subnets
6. **Create ACM Certificate** for your domain
7. **Create ALB** in public subnets with HTTPS listener
8. **Create Target Groups** for frontend and app
9. **Configure ALB listener rules** (path-based routing)
10. **Create Secrets Manager secret** with all credentials
11. **Create ECR repositories** (`eliza-backend`, `eliza-frontend`)
12. **Create CloudWatch log groups**
13. **Create ECS cluster** with Container Insights enabled
14. **Create IAM roles** (task execution role, task role)

### Phase 2: Build and Push Images

```bash
# Clone the repository
git clone <repo-url> && cd ElizaPlatform

# Build backend image (adoption-only)
docker build -f docker/Dockerfile \
  --build-arg APPLETS=adoption \
  --platform linux/amd64 \
  -t <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/eliza-backend:latest .

# Build frontend image (adoption-only)
docker build \
  --build-arg REACT_APP_API_URL="" \
  --build-arg REACT_APP_APPLETS=adoption \
  --platform linux/amd64 \
  -t <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/eliza-frontend:latest \
  frontend/

# Authenticate and push
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/eliza-backend:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/eliza-frontend:latest
```

### Phase 3: Deploy ECS Services

Deploy in this order (respecting dependencies):

1. **`eliza-app`** - Must start first; runs migrations and tenant initialization
2. **Wait** for app to become healthy (health check at `/health/ready`, can take up to 2 minutes for migrations)
3. **`eliza-celery-worker`** - Processes background tasks
4. **`eliza-celery-beat`** - Starts the adoption sync scheduler
5. **`eliza-frontend`** - Serves the UI

### Phase 4: Post-Deployment Verification

```bash
# 1. Check app health
curl https://adoption.yourcompany.com/health/ready

# 2. Check API docs are accessible
curl https://adoption.yourcompany.com/docs

# 3. Log in with admin credentials
curl -X POST https://adoption.yourcompany.com/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "<ADMIN_EMAIL>", "password": "<ADMIN_PASSWORD>"}'

# 4. Verify adoption routes are loaded
curl https://adoption.yourcompany.com/v1/adoption/overview \
  -H "Authorization: Bearer <token>"

# 5. Check CloudWatch logs for each service
aws logs tail /ecs/eliza-app --follow
aws logs tail /ecs/eliza-celery-worker --follow
aws logs tail /ecs/eliza-celery-beat --follow
```

### Phase 5: Configure Adoption Sync

After deployment, configure the adoption data source through the UI:

1. Log in to `https://adoption.yourcompany.com` as the admin user
2. Navigate to **Admin Settings** > **AI Providers**
3. Add an **OpenAI** provider with:
   - The **ChatGPT Enterprise Compliance API key** (requires `compliance_export` scope)
   - The **ChatGPT Workspace ID** (`CHATGPT_WORKSPACE_ID`)
   - Enable the provider as an adoption source
4. Navigate to **Adoption Settings**:
   - Set the **initial sync start date** (how far back to pull data)
   - Enable the **scheduled sync** (cron expression, defaults to daily)
5. Trigger a **manual sync** to verify connectivity and data flow

---

## Estimated AWS Costs (Monthly)

These are rough estimates for the adoption-only deployment. Actual costs depend on region, usage, and reserved capacity.

| Resource | Specification | Estimated Cost |
|----------|--------------|----------------|
| ECS Fargate (frontend x2) | 0.25 vCPU, 512 MB | ~$15 |
| ECS Fargate (app x2) | 1 vCPU, 4 GB | ~$120 |
| ECS Fargate (worker x1) | 1 vCPU, 4 GB | ~$60 |
| ECS Fargate (beat x1) | 0.25 vCPU, 512 MB | ~$8 |
| RDS PostgreSQL (Multi-AZ) | db.t3.medium | ~$130 |
| ElastiCache Redis | cache.t3.small | ~$25 |
| ALB | 1 ALB + LCUs | ~$25 |
| NAT Gateway | 1 NAT GW + data | ~$35+ |
| ECR | Storage | ~$1 |
| CloudWatch Logs | Ingestion + storage | ~$10 |
| Secrets Manager | 1 secret | ~$1 |
| **Total** | | **~$430/month** |

For cost savings, consider:
- **Fargate Spot** for the celery worker (tolerant of interruptions)
- **RDS Reserved Instances** for 1-year commitment (~40% savings)
- **Single-AZ RDS** for non-critical deployments
- **Single NAT Gateway** instead of per-AZ

---

## CI/CD Pipeline (Recommended)

A typical GitHub Actions workflow:

```yaml
name: Deploy Adoption

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::<ACCOUNT_ID>:role/github-actions-deploy
          aws-region: us-east-1

      - name: Login to ECR
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and Push Backend
        run: |
          docker build -f docker/Dockerfile \
            --build-arg APPLETS=adoption \
            --platform linux/amd64 \
            -t ${{ env.ECR_REGISTRY }}/eliza-backend:${{ github.sha }} \
            -t ${{ env.ECR_REGISTRY }}/eliza-backend:latest .
          docker push ${{ env.ECR_REGISTRY }}/eliza-backend --all-tags

      - name: Build and Push Frontend
        run: |
          docker build \
            --build-arg REACT_APP_APPLETS=adoption \
            --platform linux/amd64 \
            -t ${{ env.ECR_REGISTRY }}/eliza-frontend:${{ github.sha }} \
            -t ${{ env.ECR_REGISTRY }}/eliza-frontend:latest \
            frontend/
          docker push ${{ env.ECR_REGISTRY }}/eliza-frontend --all-tags

      - name: Deploy to ECS
        run: |
          aws ecs update-service --cluster eliza-adoption --service eliza-app --force-new-deployment
          aws ecs wait services-stable --cluster eliza-adoption --services eliza-app
          aws ecs update-service --cluster eliza-adoption --service eliza-celery-worker --force-new-deployment
          aws ecs update-service --cluster eliza-adoption --service eliza-celery-beat --force-new-deployment
          aws ecs update-service --cluster eliza-adoption --service eliza-frontend --force-new-deployment
```

---

## Monitoring and Alerting

### CloudWatch Alarms

| Alarm | Metric | Threshold | Action |
|-------|--------|-----------|--------|
| App CPU High | `CPUUtilization` (app service) | > 80% for 5 min | Scale out / alert |
| App Memory High | `MemoryUtilization` (app service) | > 85% for 5 min | Alert |
| Worker CPU High | `CPUUtilization` (worker) | > 80% for 5 min | Scale out |
| Unhealthy Hosts | `UnHealthyHostCount` (app TG) | > 0 for 3 min | Alert |
| RDS CPU | `CPUUtilization` (RDS) | > 80% for 10 min | Alert |
| RDS Free Storage | `FreeStorageSpace` | < 5 GB | Alert |
| RDS Connections | `DatabaseConnections` | > 80% max | Alert |
| Redis Memory | `DatabaseMemoryUsagePercentage` | > 80% | Alert |
| 5xx Errors | `HTTPCode_Target_5XX_Count` (ALB) | > 10 in 5 min | Alert |

### Key Logs to Monitor

- `/ecs/eliza-app` - API errors, migration output, startup logs
- `/ecs/eliza-celery-worker` - Adoption sync task success/failure
- `/ecs/eliza-celery-beat` - Schedule dispatch logs

### Health Check Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health/ready` | Full readiness check (DB connected, migrations applied) |
| `GET /` | Basic liveness check |
| `GET /docs` | OpenAPI documentation (verifies app is serving) |

---

## Troubleshooting

### App won't start / migration errors

Check CloudWatch logs for `/ecs/eliza-app`. Common causes:
- RDS security group doesn't allow inbound from `sg-app`
- `DATABASE_URL` in Secrets Manager has wrong endpoint/credentials
- RDS is not yet available (takes ~10 min to provision)

### Celery worker not processing tasks

- Verify `CELERY_BROKER_URL` points to the correct ElastiCache endpoint
- Check that the Redis security group allows inbound from `sg-workers`
- Look for `celery inspect ping` failures in worker logs

### Adoption sync fails

- Verify `OPENAI_API_KEY` has `compliance_export` scope
- Check that the worker can reach `https://api.chatgpt.com` (NAT Gateway + security group outbound)
- Look for rate limit errors in worker logs (OpenAI Compliance API has rate limits)

### Frontend shows blank page

- Verify ALB listener rules are correctly routing `/v1/*` to the app target group
- Check the frontend container logs for nginx errors
- Ensure `REACT_APP_APPLETS=adoption` was set at build time

### 502 Bad Gateway

- App container is still starting (health check `start_period` is 120s)
- App container is OOM-killed (check memory limits, increase if needed)
- Target group health checks are failing (check `/health/ready` endpoint)

---

## Appendix A: External Network Dependencies

The platform requires outbound HTTPS (443) access to:

| Endpoint | Purpose | Required? |
|----------|---------|-----------|
| `api.chatgpt.com` | OpenAI Compliance API (adoption sync) | Yes |
| `api.openai.com` | OpenAI API (if LLM features used) | No (adoption-only) |
| `*.dkr.ecr.us-east-1.amazonaws.com` | ECR image pull | Yes (or use VPC endpoint) |
| `secretsmanager.us-east-1.amazonaws.com` | Secrets Manager | Yes (or use VPC endpoint) |
| `logs.us-east-1.amazonaws.com` | CloudWatch Logs | Yes (or use VPC endpoint) |

Consider creating **VPC Endpoints** for ECR, Secrets Manager, and CloudWatch to avoid NAT Gateway data transfer costs and improve security.

## Appendix B: VPC Endpoints (Cost Optimization)

To reduce NAT Gateway data transfer charges and improve security:

| VPC Endpoint | Type | Purpose |
|-------------|------|---------|
| `com.amazonaws.us-east-1.ecr.api` | Interface | ECR API calls |
| `com.amazonaws.us-east-1.ecr.dkr` | Interface | ECR image layers |
| `com.amazonaws.us-east-1.s3` | Gateway | ECR image layer storage (free) |
| `com.amazonaws.us-east-1.secretsmanager` | Interface | Secrets Manager access |
| `com.amazonaws.us-east-1.logs` | Interface | CloudWatch Logs |

A NAT Gateway is still required for outbound access to `api.chatgpt.com`.

## Appendix C: Scaling Considerations

### When to scale horizontally

- **App service**: Scale based on ALB request count or CPU. The app is stateless and can run multiple instances behind the ALB.
- **Celery Worker**: Scale based on Redis queue depth. Monitor the `celery` queue length. For adoption sync, a single worker with concurrency=2 handles most workloads.
- **Celery Beat**: **Never scale beyond 1 instance.** Running multiple Beat instances will cause duplicate task scheduling.
- **Frontend**: Scale based on ALB request count. Nginx serves static files and is very lightweight.

### When to scale vertically

- **RDS**: If query latency increases or CPU stays above 80%, upgrade the instance class.
- **Redis**: If memory usage exceeds 80%, upgrade to a larger node type.
