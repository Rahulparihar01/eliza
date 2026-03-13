# ELIZA Accelerate - Helm Deployment Guide

## Platform Overview

ELIZA Accelerate is a multi-tenant AI enablement platform. This Helm chart deploys the **Adoption Analytics** applet, which provides a dashboard for monitoring ChatGPT Enterprise usage across your organization. It syncs conversation metadata, GPT catalog data, and user activity from the OpenAI Compliance API and presents it through an interactive dashboard with usage trends, top GPTs, top users, model breakdowns, and cross-team sharing.

No message content is stored -- only metadata (conversation counts, timestamps, user emails, GPT names).

---

## Prerequisites

- Kubernetes 1.25+
- Helm 3.10+
- A container registry accessible from your cluster (to host the built images)
- `kubectl` configured to access your cluster

---

## What's in the Chart

```
docs/deployment/kubernetes/adoption/
├── README.md                               # This file
└── eliza-adoption/                         # Helm chart
    ├── Chart.yaml                          # Chart metadata
    ├── values.yaml                         # Default configuration
    └── templates/
        ├── _helpers.tpl                    # Template helpers
        ├── app-deployment.yaml             # FastAPI API server
        ├── celery-worker-deployment.yaml   # Background task processor
        ├── celery-beat-deployment.yaml     # Cron scheduler (singleton)
        ├── frontend-deployment.yaml        # React UI (nginx)
        ├── services.yaml                   # ClusterIP services
        ├── ingress.yaml                    # Ingress with path-based routing
        ├── configmap.yaml                  # Non-sensitive config
        ├── secret.yaml                     # Sensitive values
        ├── postgres.yaml                   # Internal PostgreSQL (optional)
        ├── redis.yaml                      # Internal Redis (optional)
        ├── hpa.yaml                        # Horizontal Pod Autoscalers (optional)
        └── NOTES.txt                       # Post-install instructions
```

### Kubernetes Resources Created

| Resource | Name | Purpose |
|----------|------|---------|
| Deployment | `*-app` | FastAPI API server (runs DB migrations on startup) |
| Deployment | `*-celery-worker` | Processes adoption sync background tasks |
| Deployment | `*-celery-beat` | Cron scheduler, dispatches sync jobs (always 1 replica) |
| Deployment | `*-frontend` | React SPA served by nginx |
| Service | `*-app` | ClusterIP for the API (port 5001) |
| Service | `*-frontend` | ClusterIP for the frontend (port 80) |
| Ingress | `*` | Path-based routing: `/v1/*` to app, `/*` to frontend |
| ConfigMap | `*-config` | Non-sensitive environment variables |
| Secret | `*-secrets` | API keys, passwords, encryption key |
| StatefulSet | `*-postgres` | Internal PostgreSQL (if enabled) |
| Deployment | `*-redis` | Internal Redis (if enabled) |
| HPA | `*-app`, `*-celery-worker`, `*-frontend` | Autoscaling (if enabled) |

---

## Step 1: Build and Push Images

Since you have the full source code, build the two Docker images and push them to your container registry.

```bash
# Set your registry
export REGISTRY=your-registry.example.com/eliza

# Build backend (API + workers + beat -- all use the same image)
docker build -f docker/Dockerfile \
  --build-arg APPLETS=adoption \
  --platform linux/amd64 \
  -t $REGISTRY/eliza-backend:1.0.0 .

# Build frontend
docker build \
  --build-arg REACT_APP_APPLETS=adoption \
  --platform linux/amd64 \
  -t $REGISTRY/eliza-frontend:1.0.0 \
  frontend/

# Push both
docker push $REGISTRY/eliza-backend:1.0.0
docker push $REGISTRY/eliza-frontend:1.0.0
```

If your registry requires authentication from within the cluster, create an image pull secret:

```bash
kubectl create secret docker-registry eliza-registry \
  --docker-server=your-registry.example.com \
  --docker-username=YOUR_USER \
  --docker-password=YOUR_TOKEN \
  -n eliza
```

---

## Step 2: Choose a Deployment Option

The chart supports three deployment patterns. Pick the one that matches your environment.

### Option A: Quick Evaluation (all-in-one)

PostgreSQL and Redis run as pods inside the cluster. Simplest to get started, not recommended for production.

```bash
helm install eliza ./docs/deployment/kubernetes/adoption/eliza-adoption \
  --namespace eliza --create-namespace \
  --set image.registry=your-registry.example.com/eliza/ \
  --set image.backend.tag=1.0.0 \
  --set image.frontend.tag=1.0.0 \
  --set config.customerId=yourcompany \
  --set config.customerName="Your Company" \
  --set secrets.adminEmail=admin@yourcompany.com \
  --set secrets.adminPassword=StrongPassword123 \
  --set secrets.openaiApiKey=sk-proj-... \
  --set secrets.encryptionKey=YOUR_FERNET_KEY \
  --set postgresql.internal.password=dbpassword123 \
  --set ingress.hosts[0].host=adoption.yourcompany.com
```

### Option B: Production (external data stores)

Use your existing managed PostgreSQL and Redis (RDS, ElastiCache, Cloud SQL, Memorystore, etc.).

Create a `values-prod.yaml`:

```yaml
image:
  registry: your-registry.example.com/eliza/
  backend:
    tag: "1.0.0"
  frontend:
    tag: "1.0.0"

config:
  customerId: yourcompany
  customerName: "Your Company"
  frontendUrl: "https://adoption.yourcompany.com"
  allowedOrigins: "https://adoption.yourcompany.com"

secrets:
  adminEmail: admin@yourcompany.com
  adminPassword: StrongPassword123
  openaiApiKey: sk-proj-...
  encryptionKey: YOUR_FERNET_KEY

postgresql:
  external:
    enabled: true
    host: your-rds-instance.abcdef.us-east-1.rds.amazonaws.com
    port: 5432
    database: ai_enablement
    username: eliza
    password: your-db-password
  internal:
    enabled: false

redis:
  external:
    enabled: true
    host: your-elasticache.abcdef.0001.use1.cache.amazonaws.com
    port: 6379
  internal:
    enabled: false

app:
  replicaCount: 2
  initTenant: true   # Set to false after first deploy

ingress:
  enabled: true
  className: nginx    # Or alb, traefik, etc.
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: 50m
  hosts:
    - host: adoption.yourcompany.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: eliza-adoption-tls
      hosts:
        - adoption.yourcompany.com

autoscaling:
  enabled: true
```

```bash
helm install eliza ./docs/deployment/kubernetes/adoption/eliza-adoption \
  --namespace eliza --create-namespace \
  -f values-prod.yaml
```

### Option C: Bring Your Own Secrets

If your team manages secrets through an external system (Vault, AWS Secrets Manager with External Secrets Operator, etc.), create the Kubernetes Secret yourself and reference it:

```bash
kubectl create secret generic eliza-secrets -n eliza \
  --from-literal=ADMIN_EMAIL=admin@yourcompany.com \
  --from-literal=ADMIN_PASSWORD=StrongPassword123 \
  --from-literal=OPENAI_API_KEY=sk-proj-... \
  --from-literal=ENCRYPTION_KEY=YOUR_FERNET_KEY \
  --from-literal=DB_PASSWORD=your-db-password
```

Then install with:

```bash
helm install eliza ./docs/deployment/kubernetes/adoption/eliza-adoption \
  --namespace eliza \
  --set secrets.existingSecret=eliza-secrets \
  --set image.registry=your-registry.example.com/eliza/ \
  ...
```

---

## Step 3: Verify the Deployment

```bash
# Watch pods come up (app takes 1-2 min for migrations)
kubectl get pods -n eliza -w

# Check app logs for migration output
kubectl logs -n eliza -l app.kubernetes.io/component=app -f

# Verify all pods are Running/Ready
kubectl get pods -n eliza

# Test the API health endpoint
kubectl port-forward -n eliza svc/eliza-app 5001:5001
curl http://localhost:5001/health/ready
```

Expected output when everything is healthy:

```
NAME                                    READY   STATUS    AGE
eliza-app-xxxxx-yyyyy                   1/1     Running   3m
eliza-app-xxxxx-zzzzz                   1/1     Running   3m
eliza-celery-beat-xxxxx-yyyyy           1/1     Running   3m
eliza-celery-worker-xxxxx-yyyyy         1/1     Running   3m
eliza-frontend-xxxxx-yyyyy              1/1     Running   3m
eliza-frontend-xxxxx-zzzzz              1/1     Running   3m
eliza-postgres-0                        1/1     Running   3m   (if internal)
eliza-redis-xxxxx-yyyyy                 1/1     Running   3m   (if internal)
```

---

## Step 4: Post-Deployment Configuration

### Disable tenant initialization

After the first successful boot, turn off `INIT_TENANT` so it doesn't re-run:

```bash
helm upgrade eliza ./docs/deployment/kubernetes/adoption/eliza-adoption \
  --namespace eliza --reuse-values \
  --set app.initTenant=false
```

### Configure adoption sync

1. Open `https://adoption.yourcompany.com` (or `kubectl port-forward` to the frontend)
2. Log in with your admin credentials
3. Go to **Admin Settings** > **AI Providers**
4. Add an **OpenAI** provider:
   - Paste your ChatGPT Enterprise **Compliance API key** (needs `compliance_export` scope)
   - Enter your **ChatGPT Workspace ID**
   - Enable the provider as an adoption data source
5. Go to **Adoption Settings**:
   - Set the **sync start date** (how far back to pull historical data)
   - Enable the **scheduled sync**
6. Click **Sync Now** to verify connectivity

---

## Resource Requirements

### Per-component

| Component | CPU request | CPU limit | Memory request | Memory limit |
|-----------|-------------|-----------|----------------|--------------|
| App (x2) | 1 core | 2 cores | 2 GB | 4 GB |
| Celery Worker (x1) | 1 core | 2 cores | 2 GB | 4 GB |
| Celery Beat (x1) | 250m | 500m | 512 MB | 1 GB |
| Frontend (x2) | 100m | 500m | 128 MB | 512 MB |
| PostgreSQL (x1, if internal) | 500m | 1 core | 512 MB | 2 GB |
| Redis (x1, if internal) | 100m | 500m | 128 MB | 512 MB |

### Cluster total (with internal data stores)

| Resource | Minimum | With headroom |
|----------|---------|---------------|
| **CPU** | ~5 cores | 8 cores |
| **Memory** | ~9 GB | 16 GB |
| **Storage** | 20 GB PVC (PostgreSQL) | 50 GB |

All values are configurable in `values.yaml`.

---

## Network Requirements

### Ingress routing

The Ingress routes traffic by path:

| Path | Backend Service | Port |
|------|----------------|------|
| `/v1/*` | `*-app` | 5001 |
| `/api/*` | `*-app` | 5001 |
| `/docs`, `/redoc`, `/openapi.json` | `*-app` | 5001 |
| `/health/*` | `*-app` | 5001 |
| `/*` (default) | `*-frontend` | 80 |

### Outbound access

Pods need outbound HTTPS (443) to:

| Destination | Which pod | Purpose |
|-------------|-----------|---------|
| `api.chatgpt.com` | celery-worker | OpenAI Compliance API (adoption data sync) |
| Your container registry | All (at pull time) | Image pulls |

No other outbound access is required. If you have NetworkPolicies, allow egress to `api.chatgpt.com:443` from the celery-worker pods.

### Internal communication

All inter-service traffic uses ClusterIP services within the cluster:

```
Ingress ──▶ frontend:80 (static assets)
        ──▶ app:5001    (API)
                │
                ├──▶ postgres:5432
                └──▶ redis:6379

celery-worker ──▶ postgres:5432
              ──▶ redis:6379
              ──▶ api.chatgpt.com:443

celery-beat   ──▶ redis:6379
```

---

## Ingress Controller Notes

The chart creates a standard `networking.k8s.io/v1` Ingress resource. Configure it for your controller:

### NGINX Ingress Controller

```yaml
ingress:
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: 50m
    nginx.ingress.kubernetes.io/proxy-read-timeout: "120"
```

### AWS ALB Ingress Controller

```yaml
ingress:
  className: alb
  annotations:
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:...
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
    alb.ingress.kubernetes.io/ssl-redirect: "443"
```

### Traefik

```yaml
ingress:
  className: traefik
  annotations:
    traefik.ingress.kubernetes.io/router.tls: "true"
```

---

## Updating

To deploy a new version:

```bash
# Build and push new images
docker build -f docker/Dockerfile --build-arg APPLETS=adoption -t $REGISTRY/eliza-backend:1.1.0 .
docker build --build-arg REACT_APP_APPLETS=adoption -t $REGISTRY/eliza-frontend:1.1.0 frontend/
docker push $REGISTRY/eliza-backend:1.1.0
docker push $REGISTRY/eliza-frontend:1.1.0

# Upgrade the release
helm upgrade eliza ./docs/deployment/kubernetes/adoption/eliza-adoption \
  --namespace eliza --reuse-values \
  --set image.backend.tag=1.1.0 \
  --set image.frontend.tag=1.1.0
```

The app pod runs database migrations automatically on startup, so schema changes are applied during the rolling update.

---

## Rollback

```bash
# List release history
helm history eliza -n eliza

# Roll back to a previous revision
helm rollback eliza 1 -n eliza
```

---

## Uninstall

```bash
helm uninstall eliza -n eliza
```

This removes all Kubernetes resources. If using internal PostgreSQL, the PersistentVolumeClaim (`postgres-data`) is **not** deleted automatically (to prevent data loss). Delete it manually if desired:

```bash
kubectl delete pvc -n eliza -l app.kubernetes.io/component=postgres
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| App pod stuck in `Init` / `CrashLoopBackOff` | `kubectl logs -n eliza -l app.kubernetes.io/component=app` -- likely DB connection issue or missing secret values |
| "relation does not exist" errors | Migrations didn't run. Verify `RUN_MIGRATIONS=true` is set (it's hardcoded in the app deployment) |
| Adoption sync fails | `kubectl logs -n eliza -l app.kubernetes.io/component=celery-worker` -- verify `OPENAI_API_KEY` has `compliance_export` scope, verify outbound to `api.chatgpt.com:443` |
| Frontend shows blank page | Check that Ingress paths are routing correctly. Verify `/v1/*` reaches the app service. |
| Can't log in | Verify `app.initTenant=true` was set on first install. Check app logs for tenant initialization output. |
| ImagePullBackOff | Verify `image.registry`, `image.pullSecrets`, and that images exist in your registry |
| Celery Beat running multiple times | Ensure Beat deployment has exactly 1 replica (hardcoded, but verify no HPA targets it) |

---

## Values Reference

All configurable parameters are documented in `values.yaml` with inline comments. Key sections:

| Section | What it controls |
|---------|-----------------|
| `image.*` | Container registry, image names, tags, pull secrets |
| `config.*` | Customer ID, log level, CORS, frontend URL |
| `secrets.*` | Admin credentials, API keys, encryption key (or use `existingSecret`) |
| `postgresql.*` | Internal pod vs external managed database |
| `redis.*` | Internal pod vs external managed Redis |
| `app.*` | API server replicas, resources, health checks, init tenant |
| `celeryWorker.*` | Worker replicas, concurrency, resources |
| `celeryBeat.*` | Scheduler resources (always 1 replica) |
| `frontend.*` | Frontend replicas, resources |
| `ingress.*` | Ingress class, annotations, hosts, TLS |
| `autoscaling.*` | HPA settings for app, worker, frontend |
