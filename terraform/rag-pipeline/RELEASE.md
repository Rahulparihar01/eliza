# RAG Pipeline Release Guide

Operational runbook for deploying the standalone AWS RAG pipeline in one command.

## One-Command Setup

From repo root:

```bash
terraform/rag-pipeline/scripts/release_bootstrap.sh \
  --tfvars terraform/rag-pipeline/terraform.tfvars \
  --region us-east-1 \
  --auto-approve
```

What this does:

1. `terraform init/plan/apply` for `terraform/rag-pipeline/`
2. Uploads DAG assets to MWAA S3 bucket:
   - `dags/`
   - `requirements/requirements.txt`
   - `plugins/plugins.zip` containing `eliza-rag-ingestion` wheel
3. Builds and pushes MCP server image to ECR

If you only want infra + assets (no Docker push):

```bash
terraform/rag-pipeline/scripts/release_bootstrap.sh \
  --tfvars terraform/rag-pipeline/terraform.tfvars \
  --region us-east-1 \
  --skip-mcp-image
```

## Prerequisites

- AWS credentials configured locally (`aws sts get-caller-identity` works)
- Tools installed:
  - `terraform` (>= 1.5)
  - `aws` CLI
  - `python3`
  - `docker` (unless `--skip-mcp-image`)
- Repo contains:
  - `dags/`
  - `packages/eliza-rag-ingestion/`

## Required Configuration Before Plan/Apply

Create `terraform/rag-pipeline/terraform.tfvars`:

```hcl
aws_region               = "us-east-1"
project                  = "eliza-rag"
env                      = "development"

# Recommended for production
mcp_api_key              = "replace-with-strong-random-key"

# Optional until SharePoint integration is ready
sharepoint_tenant_id     = ""
sharepoint_client_id     = ""
sharepoint_client_secret = ""
sharepoint_site_id       = ""

# Optional tuning
mcp_server_image_tag     = "latest"
mcp_server_cpu           = "512"
mcp_server_memory        = "1024"
mcp_server_desired_count = 1
```

### Are SharePoint credentials required now?

No. Infrastructure can be provisioned without them.

But SharePoint sync DAG tasks will fail until valid values are provided.

## How Secrets Work

Terraform writes secrets into AWS Secrets Manager:

- `${project}/${env}/sharepoint-credentials`
- `${project}/${env}/mcp-api-key`

MWAA reads secrets through Airflow Secrets Backend (configured in `mwaa.tf`).
MCP server gets `MCP_API_KEY` from Secrets Manager via ECS task secret injection.

## Package Install Strategy for MWAA (`eliza-rag-ingestion`)

MWAA cannot install from local repo paths directly. This setup uses:

- `requirements/requirements.txt` with:
  - `--find-links /usr/local/airflow/plugins`
  - `eliza-rag-ingestion`
- `plugins/plugins.zip` containing the built wheel

The bootstrap script builds the wheel and uploads `plugins.zip`.

## Caveats

- `release_bootstrap.sh` must be run from this repo (it references `dags/` and `packages/`).
- If `--skip-mcp-image` is used, ECS service may not run if ECR has no matching tag.
- `--auto-approve` skips Terraform confirmation; omit for manual review.
- MWAA startup and environment updates can take several minutes after apply.
- If you change DAGs or package code later, rerun:
  - `scripts/deploy_mwaa_assets.sh` (assets only), or
  - `scripts/release_bootstrap.sh` (full flow)

## Minimal Verification Checklist

1. `terraform -chdir=terraform/rag-pipeline output`
2. Confirm objects in DAG bucket:
   - `dags/`
   - `requirements/requirements.txt`
   - `plugins/plugins.zip`
3. Confirm MWAA environment status is `AVAILABLE`
4. Confirm MCP ECS service has running task
5. Check `/health` via API Gateway route to MCP server
