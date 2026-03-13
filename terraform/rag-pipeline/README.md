# RAG Pipeline — Standalone Terraform Project

Self-contained infrastructure for the document ingestion and retrieval-augmented
generation (RAG) pipeline.  This project can be extracted and deployed
independently—it has **zero dependencies** on the Eliza Platform Terraform.

For production rollout steps, see `RELEASE.md`.  
To run your own PDFs (e.g. from SharePoint) through the pipeline, see **`docs/TESTING_WITH_PDFS.md`**.

## What It Provisions

| Resource | File | Purpose |
|----------|------|---------|
| VPC + Subnets | `vpc.tf` | Isolated network for all pipeline resources |
| MWAA (Managed Airflow) | `mwaa.tf` | Orchestrates SharePoint → S3 → OpenSearch DAGs |
| S3 Buckets | `s3.tf` | `raw-documents`, `processed-documents`, `airflow-dags` |
| OpenSearch Serverless | `opensearch.tf` | Vector store for document embeddings |
| API Gateway + WAF | `api_gateway.tf` | Public endpoint for MCP server |
| ECS Cluster + MCP Service | `ecs.tf` | Fargate task running the MCP server |
| ECR Repository | `ecr.tf` | Container registry for MCP server image |
| IAM Roles | `iam.tf` | MWAA execution role + ECS task roles |
| Security Groups | `security_groups.tf` | MWAA and ECS network access |
| Secrets Manager | `secrets.tf` | SharePoint OAuth + MCP API key |

## MCP Server (`mcp_server/`)

The MCP server source code lives alongside the Terraform in `mcp_server/`.
It's a standalone FastMCP server that connects directly to OpenSearch + Bedrock
and exposes RAG tools via SSE for ChatGPT Enterprise or any MCP client.

Build and push the image:

```bash
# From the repo root (needs packages/eliza-rag-ingestion in context)
docker build -f terraform/rag-pipeline/mcp_server/Dockerfile -t mcp-server .

# Push to ECR (after terraform apply creates the repo)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker tag mcp-server:latest $(terraform -chdir=terraform/rag-pipeline output -raw mcp_server_ecr_repo):latest
docker push $(terraform -chdir=terraform/rag-pipeline output -raw mcp_server_ecr_repo):latest
```

## Quick Start

```bash
cd terraform/rag-pipeline

terraform init

cat > terraform.tfvars <<'EOF'
sharepoint_tenant_id     = "your-azure-tenant-id"
sharepoint_client_id     = "your-app-client-id"
sharepoint_client_secret = "your-app-client-secret"
sharepoint_site_id       = "your-sharepoint-site-id"
mcp_api_key              = "your-mcp-api-key"
EOF

terraform plan
terraform apply
```

## Deploy MWAA Assets (DAGs + Package)

After infrastructure exists, sync runtime assets into the MWAA DAG bucket:

```bash
terraform/rag-pipeline/scripts/deploy_mwaa_assets.sh \
  --bucket "$(terraform -chdir=terraform/rag-pipeline output -raw s3_dags_bucket)" \
  --region us-east-1
```

This uploads:
- `dags/` -> `s3://<bucket>/dags/`
- `files/requirements-airflow.txt` -> `s3://<bucket>/requirements/requirements.txt`
- built `eliza-rag-ingestion` wheel -> `s3://<bucket>/packages/`
- `plugins.zip` containing the wheel -> `s3://<bucket>/plugins/plugins.zip`

`mwaa.tf` is wired to:
- install dependencies from `requirements/requirements.txt`
- load plugins from `plugins/plugins.zip`

`requirements-airflow.txt` includes:
- `--find-links /usr/local/airflow/plugins`
- `eliza-rag-ingestion`

So MWAA installs the package from the wheel delivered in `plugins.zip`.

## Extracting for Customer Deployment

This directory is designed to be copied as-is into another repo:

```bash
# Copy terraform + MCP server
cp -r terraform/rag-pipeline /path/to/customer-repo/

# Also copy the RAG package dependency
cp -r packages/eliza-rag-ingestion /path/to/customer-repo/packages/

cd /path/to/customer-repo/
terraform -chdir=rag-pipeline init && terraform -chdir=rag-pipeline plan
```

No remote state references, no `data` sources pointing at the platform.

## Variables

See `variables.tf` for all configurable inputs.  Key ones:

- `project` — Resource name prefix (default: `eliza-rag`)
- `aws_region` — Target AWS region (default: `us-east-1`)
- `vpc_cidr` — VPC CIDR (default: `10.1.0.0/16`, avoids conflict with platform `10.0.0.0/16`)
- `mwaa_environment_class` — Airflow sizing (`mw1.small` / `mw1.medium` / `mw1.large`)
- `sharepoint_*` — Azure AD OAuth credentials for SharePoint sync
- `mcp_api_key` — API key for MCP server authentication
- `mcp_server_*` — MCP server sizing and image tag
