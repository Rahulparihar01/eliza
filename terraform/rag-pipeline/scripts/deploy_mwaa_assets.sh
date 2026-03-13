#!/usr/bin/env bash
set -euo pipefail

# Deploy MWAA runtime assets from this repo to an existing DAG bucket:
# - DAG files -> dags/
# - Airflow requirements -> requirements/requirements.txt
# - eliza-rag-ingestion wheel + plugins.zip -> packages/ and plugins/plugins.zip
#
# Usage:
#   terraform/rag-pipeline/scripts/deploy_mwaa_assets.sh --bucket <bucket> [--region us-east-1]

BUCKET=""
REGION="${AWS_REGION:-us-east-1}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket)
      BUCKET="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1"
      exit 1
      ;;
  esac
done

if [[ -z "$BUCKET" ]]; then
  echo "Missing required --bucket argument"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAG_PIPELINE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$RAG_PIPELINE_DIR/../.." && pwd)"

REQ_FILE="$RAG_PIPELINE_DIR/files/requirements-airflow.txt"
DAGS_DIR="$REPO_ROOT/dags"
PKG_DIR="$REPO_ROOT/packages/eliza-rag-ingestion"

if [[ ! -d "$DAGS_DIR" ]]; then
  echo "DAGs directory not found: $DAGS_DIR"
  exit 1
fi

if [[ ! -d "$PKG_DIR" ]]; then
  echo "Package directory not found: $PKG_DIR"
  exit 1
fi

if [[ ! -f "$REQ_FILE" ]]; then
  echo "Requirements file not found: $REQ_FILE"
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

WHEEL_DIR="$TMP_DIR/wheels"
mkdir -p "$WHEEL_DIR"

echo "Building eliza-rag-ingestion wheel..."
python3 -m pip wheel --no-deps --wheel-dir "$WHEEL_DIR" "$PKG_DIR"

WHEEL_PATH="$(ls "$WHEEL_DIR"/*.whl)"
WHEEL_NAME="$(basename "$WHEEL_PATH")"
PLUGINS_ZIP="$TMP_DIR/plugins.zip"

echo "Creating plugins.zip containing wheel: $WHEEL_NAME"
python3 - <<PY
import zipfile
zip_path = r"$PLUGINS_ZIP"
wheel_path = r"$WHEEL_PATH"
wheel_name = r"$WHEEL_NAME"
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    zf.write(wheel_path, arcname=wheel_name)
PY

echo "Syncing DAGs..."
aws s3 sync "$DAGS_DIR/" "s3://$BUCKET/dags/" --delete --region "$REGION" \
  --exclude "__pycache__/*" \
  --exclude "*.pyc"

echo "Uploading requirements..."
aws s3 cp "$REQ_FILE" "s3://$BUCKET/requirements/requirements.txt" --region "$REGION"

echo "Uploading wheel + plugins.zip..."
aws s3 cp "$WHEEL_PATH" "s3://$BUCKET/packages/$WHEEL_NAME" --region "$REGION"
aws s3 cp "$PLUGINS_ZIP" "s3://$BUCKET/plugins/plugins.zip" --region "$REGION"

echo
echo "Done."
echo "Uploaded to bucket: $BUCKET"
echo "  - dags/"
echo "  - requirements/requirements.txt"
echo "  - packages/$WHEEL_NAME"
echo "  - plugins/plugins.zip"
