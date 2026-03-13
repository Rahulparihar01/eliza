# Docker Compose - Full Platform

> **Status:** Planned

This guide will cover deploying the full ELIZA Accelerate platform (`APPLETS=all`) with Docker Compose, including all applets and the complete infrastructure stack (PostgreSQL, Redis, Elasticsearch, Neo4j, Logstash, Langfuse).

For now, the existing `docker/docker-compose.yml` at the repository root serves as the full-platform Docker Compose reference.

For local development, note that the following services are now opt-in via
Compose profiles and do not start by default:

- `airflow` profile - `airflow-init`, `airflow-webserver`, `airflow-scheduler`, `airflow-worker`
- `rag-ingestion` profile - `rag-ingestion`, `celery-rag-worker`

Example:

```bash
cd docker
docker compose --profile airflow --profile rag-ingestion up -d
```
