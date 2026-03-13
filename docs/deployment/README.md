# ELIZA Accelerate - Deployment Guides

This directory contains deployment guides and configuration files for running the ELIZA Accelerate platform, organized by deployment method and applet scope.

## Structure

```
docs/deployment/
├── README.md                          # This file
│
├── aws-fargate/                       # AWS Fargate (ECS)
│   ├── adoption/                      # Adoption applet only
│   └── full/                          # Full platform (planned)
│
├── docker-compose/                    # Docker Compose (single host)
│   ├── adoption/                      # Adoption applet only
│   └── full/                          # Full platform (planned)
│
└── kubernetes/                        # Kubernetes (Helm)
    ├── adoption/                      # Adoption applet only (Helm chart included)
    └── full/                          # Full platform (planned)
```

## Deployment Options

| Method | Best for | Complexity |
|--------|----------|------------|
| [**Docker Compose**](./docker-compose/) | Evaluation, single-host, fastest time to running | Low |
| [**Kubernetes (Helm)**](./kubernetes/) | Production, existing K8s cluster | Medium |
| [**AWS Fargate (ECS)**](./aws-fargate/) | Production, AWS-native, no cluster management | Medium-High |

## Applet Scopes

| Scope | `APPLETS` value | What's included | Infrastructure required |
|-------|----------------|-----------------|----------------------|
| **Adoption** | `adoption` | Adoption Analytics dashboard, ChatGPT Enterprise sync | PostgreSQL, Redis |
| **Full** | `all` | All applets (adoption, talent, BI, connectors, RAG, etc.) | PostgreSQL, Redis, Elasticsearch, Neo4j, Logstash |

## Quick Comparison

| Concern | Docker Compose | Kubernetes (Helm) | AWS Fargate |
|---------|---------------|-------------------|-------------|
| Infrastructure needed | 1 EC2 instance | Existing K8s cluster | VPC + ECS + RDS + ElastiCache |
| Data stores | Bundled (containers) or external | Bundled (pods) or external | AWS managed (RDS, ElastiCache) |
| Scaling | Manual | HPA built in | ECS auto-scaling |
| TLS/HTTPS | Reverse proxy (nginx/Caddy) | Ingress controller | ALB with ACM |
| Secrets | `.env` file | K8s Secrets / Vault | AWS Secrets Manager |
| Time to first deploy | ~10 minutes | ~15 minutes | ~1 hour (infra provisioning) |
| Monthly cost (adoption, estimate) | ~$120 (t3.xlarge) | Depends on cluster | ~$430 |

## Building Images from Source

All deployment methods require two Docker images built from the repository root:

```bash
# Backend (API + all workers use the same image)
docker build -f docker/Dockerfile --build-arg APPLETS=adoption -t eliza-backend .

# Frontend
docker build --build-arg REACT_APP_APPLETS=adoption -t eliza-frontend frontend/
```

For the full platform, change `APPLETS=adoption` to `APPLETS=all` (or omit the build arg -- `all` is the default).
