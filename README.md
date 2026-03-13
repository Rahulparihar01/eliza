# Eliza Platform

The Eliza Platform (Eliza Accelerate) makes it extremely easy for AI coding agents to ship production-ready software by validating design principles through real products. This platform is a place for all agentic applets to live and shared the same infrastructure, while respecting enterprise controls like multi-tenancy, RBAC etc. The platform can be deployed in any cloud env. Currently hosted at [app.elizaplatform.com](https://app.elizaplatform.com).

## Quick Links

- `AGENTS.md` - Feature development guide and critical rules
- `skills/README.md` - Skills library (read before implementing)
- `dev_onboarding/README.md` - Engineer onboarding guide
- `docs/CODEBASE_MAP.md` - Module relationships and navigation map
- `features/README.md` - Feature workflow (PRD → Tech Spec → Implementation Plan)

## Architecture (High Level)

Frontend (React + TypeScript) → FastAPI API layer → Celery workers → CrewAI flows → Data layer (Postgres, Elasticsearch, Neo4j, FAISS, Redis)

## Quick Start (Local Dev)

### Prerequisites

- Docker + Docker Compose
- Node.js + npm (for local frontend)
- API keys (OpenAI required; Anthropic/Groq optional)

### 1) Configure environment

`./dev-start.sh` runs Docker Compose from `docker/`, so it reads `docker/.env`.

```bash
cp .env.template docker/.env
```

Update `docker/.env` with your API keys and local settings.

### 2) Start the dev environment (recommended)

This starts the backend in Docker and the frontend locally with hot reload.

```bash
./dev-start.sh
```

### 3) Stop everything

```bash
./dev-stop.sh
```

### 4) Access services

- API: http://localhost:5001
- API docs: http://localhost:5001/docs
- Frontend: http://localhost:3000
- Flower: http://localhost:5555
- Kibana: http://localhost:5601
- Neo4j: http://localhost:7474
- Elasticsearch: http://localhost:9200

## Common Development Commands

```bash
# Rebuild after backend code changes (critical)
docker-compose -f docker/docker-compose.yml build app celery-worker

docker-compose -f docker/docker-compose.yml up -d app celery-worker

# Run database migrations
docker-compose -f docker/docker-compose.yml exec app alembic upgrade head

# View logs
docker-compose -f docker/docker-compose.yml logs -f app celery-worker
```

## Local Dev Alternatives

If you prefer the full Docker stack (including the frontend container), you can use:

```bash
./scripts/setup-local.sh
```

This script creates a default `.env`, initializes local directories, and brings up `docker/docker-compose.yml`.

## Project Structure (Top Level)

```
ElizaPlatform/
├── AGENTS.md                # Feature dev guide + rules
├── skills/                  # Skills library (check first)
├── features/                # PRD → Tech Spec → Implementation Plan
├── agent_runs/              # Agent run logs + templates
├── dev_onboarding/          # Engineer onboarding
├── docs/                    # Architecture + API docs
├── cookbook/                # CrewAI patterns
├── docker/                  # Compose + Dockerfiles
├── src/                     # Backend (FastAPI, Celery, CrewAI)
├── frontend/                # React app
├── scripts/                 # Utility scripts
└── tests/                   # Tests
```

## Documentation & Workflow

- Start with `dev_onboarding/README.md` if you are new to the repo.
- Always check `skills/README.md` and the relevant skill before implementing.
- Use the feature workflow in `features/README.md` for new work.
- Validate before PR: `python scripts/validate_feature.py [feature_name]`.

## Customer Instance Deployment (Optional)

If you need to deploy a customer instance:

```bash
./scripts/deploy-customer.sh customer-id "Customer Name"
```

Logs and management commands are documented in the scripts and `skills/common-actions/`.

## Troubleshooting

- Check `skills/troubleshooting/ERROR_RECOVERY_PLAYBOOK.md` for common errors.
- Verify `.env` values and Docker health if services fail to start.
- Rebuild containers after backend code changes.

## License

[Add license]

## Contributing

[Add contributing guidelines]
