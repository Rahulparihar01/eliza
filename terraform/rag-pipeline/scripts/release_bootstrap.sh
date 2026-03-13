#!/usr/bin/env bash
set -euo pipefail

# One-command bootstrap for rag-pipeline:
# 1) terraform init/plan/apply
# 2) upload DAG + MWAA assets (requirements + plugins.zip with wheel)
# 3) build/push MCP server image to ECR
#
# Usage:
#   terraform/rag-pipeline/scripts/release_bootstrap.sh \
#     --tfvars terraform/rag-pipeline/terraform.tfvars \
#     --region us-east-1 \
#     --auto-approve

TFVARS_FILE=""
REGION="${AWS_REGION:-us-east-1}"
AUTO_APPROVE=false
MCP_IMAGE_TAG="latest"
SKIP_MCP_IMAGE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tfvars)
      TFVARS_FILE="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --auto-approve)
      AUTO_APPROVE=true
      shift
      ;;
    --mcp-image-tag)
      MCP_IMAGE_TAG="$2"
      shift 2
      ;;
    --skip-mcp-image)
      SKIP_MCP_IMAGE=true
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

require_cmd terraform
require_cmd aws
require_cmd python3
require_cmd git

if [[ "$SKIP_MCP_IMAGE" == "false" ]]; then
  require_cmd docker
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAG_PIPELINE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$RAG_PIPELINE_DIR/../.." && pwd)"

if [[ -n "$TFVARS_FILE" && ! -f "$TFVARS_FILE" ]]; then
  echo "tfvars file not found: $TFVARS_FILE"
  exit 1
fi

echo "Checking AWS credentials..."
aws sts get-caller-identity --region "$REGION" >/dev/null

TF_ARGS=()
if [[ -n "$TFVARS_FILE" ]]; then
  TF_ARGS+=("-var-file=$TFVARS_FILE")
fi

PLAN_FILE="$RAG_PIPELINE_DIR/.tfplan-rag-pipeline"
trap 'rm -f "$PLAN_FILE"' EXIT

echo "=== Terraform init ==="
terraform -chdir="$RAG_PIPELINE_DIR" init

echo "=== Terraform plan ==="
terraform -chdir="$RAG_PIPELINE_DIR" plan "${TF_ARGS[@]}" -out "$PLAN_FILE"

echo "=== Terraform apply ==="
if [[ "$AUTO_APPROVE" == "true" ]]; then
  terraform -chdir="$RAG_PIPELINE_DIR" apply -auto-approve "$PLAN_FILE"
else
  terraform -chdir="$RAG_PIPELINE_DIR" apply "$PLAN_FILE"
fi

DAGS_BUCKET="$(terraform -chdir="$RAG_PIPELINE_DIR" output -raw s3_dags_bucket)"
ECR_REPO="$(terraform -chdir="$RAG_PIPELINE_DIR" output -raw mcp_server_ecr_repo)"

echo "=== Deploy MWAA assets ==="
"$RAG_PIPELINE_DIR/scripts/deploy_mwaa_assets.sh" \
  --bucket "$DAGS_BUCKET" \
  --region "$REGION"

if [[ "$SKIP_MCP_IMAGE" == "false" ]]; then
  echo "=== Build and push MCP server image ==="
  aws ecr get-login-password --region "$REGION" \
    | docker login --username AWS --password-stdin "$(echo "$ECR_REPO" | cut -d/ -f1)"

  docker build \
    -f "$RAG_PIPELINE_DIR/mcp_server/Dockerfile" \
    -t "mcp-server:$MCP_IMAGE_TAG" \
    "$REPO_ROOT"

  docker tag "mcp-server:$MCP_IMAGE_TAG" "$ECR_REPO:$MCP_IMAGE_TAG"
  docker push "$ECR_REPO:$MCP_IMAGE_TAG"
fi

echo
echo "Bootstrap complete."
echo "Region:        $REGION"
echo "DAGs bucket:   $DAGS_BUCKET"
echo "MCP ECR repo:  $ECR_REPO"
echo "MCP image tag: $MCP_IMAGE_TAG"
