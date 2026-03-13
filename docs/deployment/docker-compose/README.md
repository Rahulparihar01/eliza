# Docker Compose Deployments

Guides for deploying ELIZA Accelerate with Docker Compose on a single host.

## Local Development Defaults

The main `docker/docker-compose.yml` now keeps the Airflow and standalone RAG
ingestion stack behind optional Compose profiles so they do not start by
default during local development.

Optional profiles:

- `airflow` - `airflow-init`, `airflow-webserver`, `airflow-scheduler`, `airflow-worker`
- `rag-ingestion` - `rag-ingestion`, `celery-rag-worker`

Examples:

```bash
cd docker
docker compose up -d
docker compose --profile airflow up -d
docker compose --profile rag-ingestion up -d
docker compose --profile airflow --profile rag-ingestion up -d
```

| Applet Scope | Guide | Status |
|-------------|-------|--------|
| [Adoption only](./adoption/) | Adoption Analytics applet, bundled PostgreSQL + Redis | Ready |
| [Full platform](./full/) | All applets with full infrastructure stack | Planned |
