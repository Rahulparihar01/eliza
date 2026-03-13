#!/usr/bin/env python3
"""
Smoke test for reference architecture: Bedrock embeddings and (optional) generation.

Usage:
  uv run python scripts/reference_architecture_bedrock_test.py --list-models [--region REGION]
  uv run python scripts/reference_architecture_bedrock_test.py --embed
  uv run python scripts/reference_architecture_bedrock_test.py --generate [--region REGION] [--model MODEL_ID]
  uv run python scripts/reference_architecture_bedrock_test.py --embed --generate

Credentials (for Bedrock / AWS):
  Put credentials in a .env file in the project root (recommended; .env is gitignored).

  For --generate (native Bedrock invoke_model): boto3-style credentials (same as --embed and --list-models):
    AWS_ACCESS_KEY_ID=...
    AWS_SECRET_ACCESS_KEY=...
    AWS_SESSION_TOKEN=...   # optional
  Or BEDROCK_ACCESS_KEY_ID, BEDROCK_SECRET_ACCESS_KEY, BEDROCK_SESSION_TOKEN.

  For --embed (Titan embeddings): boto3-style credentials:
    BEDROCK_ACCESS_KEY_ID=AKIA...
    BEDROCK_SECRET_ACCESS_KEY=...
    BEDROCK_SESSION_TOKEN=...   # optional
  Or: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN.

Requires:
  - --embed: RAG_EMBEDDING_PROVIDER=bedrock, model/region env vars, and boto3 credentials.
  - --generate: boto3 bedrock-runtime invoke_model (e.g. Amazon Titan Text); uses AWS_* or BEDROCK_* credentials.
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Optional

# Ensure project root is on sys.path when run as script (e.g. python scripts/... or uv run)
_SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Load .env from project root so credentials can live in .env (gitignored)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))
except ImportError:
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def run_embed() -> bool:
    """Call Bedrock Titan embed_texts and check result. Returns True on success."""
    from src.services.rag.embeddings import EmbeddingService, EmbeddingProvider

    provider = _env("RAG_EMBEDDING_PROVIDER", "bedrock").lower()
    if provider != "bedrock":
        print("Set RAG_EMBEDDING_PROVIDER=bedrock to run Bedrock embedding smoke test.")
        return False

    model = _env("RAGFLOW_DEFAULT_EMBEDDING_MODEL") or "amazon.titan-embed-text-v1"
    region = _env("RAG_BEDROCK_EMBEDDING_REGION") or "us-east-1"
    # Prefer BEDROCK_* env vars, then fall back to default chain (AWS_* from env, IAM, etc.)
    aws_access_key = _env("AWS_ACCESS_KEY_ID")
    aws_secret_key = _env("AWS_SECRET_ACCESS_KEY")

    svc = EmbeddingService(
        provider=EmbeddingProvider.BEDROCK,
        model=model,
        aws_region=region,
        aws_access_key_id=aws_access_key or None,
        aws_secret_access_key=aws_secret_key or None,
    )
    print(f"EmbeddingService: provider=bedrock, model={model}, region={region}, dimensions={svc.dimensions}")

    async def _embed():
        texts = ["Hello world"]
        vectors = await svc.embed_texts(texts)
        return vectors

    try:
        vectors = asyncio.run(_embed())
    except Exception as e:
        print(f"Embedding failed: {e}")
        return False

    if not vectors or len(vectors) != 1:
        print("Expected one embedding vector.")
        return False
    vec = vectors[0]
    if not isinstance(vec, list) or len(vec) != svc.dimensions:
        print(f"Expected vector of length {svc.dimensions}, got {len(vec) if isinstance(vec, list) else type(vec)}")
        return False
    print(f"OK: got embedding of dimension {len(vec)}")
    return True


def run_list_models(region: str) -> bool:
    """List Bedrock foundation models in the given region (control-plane API; uses AWS credentials)."""
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError as e:
        print(f"boto3 required for --list-models: {e}")
        return False

    aws_access_key_id = _env("BEDROCK_ACCESS_KEY_ID") or _env("AWS_ACCESS_KEY_ID") or None
    aws_secret_access_key = _env("BEDROCK_SECRET_ACCESS_KEY") or _env("AWS_SECRET_ACCESS_KEY") or None
    aws_session_token = _env("BEDROCK_SESSION_TOKEN") or _env("AWS_SESSION_TOKEN") or None

    try:
        kwargs = {"region_name": region}
        if aws_access_key_id and aws_secret_access_key:
            kwargs["aws_access_key_id"] = aws_access_key_id
            kwargs["aws_secret_access_key"] = aws_secret_access_key
            if aws_session_token:
                kwargs["aws_session_token"] = aws_session_token
        client = boto3.client("bedrock", **kwargs)
        # List models; optional filter for text output (chat-compatible)
        response = client.list_foundation_models(byOutputModality="TEXT")
    except NoCredentialsError:
        print("No AWS credentials. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY (or BEDROCK_*) in .env")
        return False
    except ClientError as e:
        print(f"Bedrock list_foundation_models failed: {e.response.get('Error', {}).get('Message', e)}")
        return False

    summaries = response.get("modelSummaries", [])
    if not summaries:
        print(f"No TEXT foundation models found in {region}.")
        return True

    print(f"Bedrock foundation models (TEXT output) in {region}: {len(summaries)} total\n")
    print(f"{'modelId':<55} {'providerName':<15} modelName")
    print("-" * 100)
    for m in sorted(summaries, key=lambda x: (x.get("providerName", ""), x.get("modelId", ""))):
        model_id = m.get("modelId", "")
        provider = m.get("providerName", "")
        name = (m.get("modelName") or "")[:40]
        print(f"{model_id:<55} {provider:<15} {name}")
    print("\nUse any modelId above with --generate (set region via RAG_BEDROCK_EMBEDDING_REGION or --region).")
    return True


def run_generate(
    config_id: Optional[int] = None,
    region: Optional[str] = None,
    model_id: Optional[str] = None,
) -> bool:
    """Test Bedrock text generation via boto3 bedrock-runtime invoke_model (Amazon Titan Text style)."""
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
    except ImportError as e:
        print(f"boto3 required for --generate: {e}")
        return False

    aws_region = region or _env("RAG_BEDROCK_EMBEDDING_REGION") or "us-east-1"
    model_id = model_id or _env("BEDROCK_GENERATE_MODEL_ID") or "qwen.qwen3-32b-v1:0"
    aws_access_key_id = _env("BEDROCK_ACCESS_KEY_ID") or _env("AWS_ACCESS_KEY_ID") or None
    aws_secret_access_key = _env("BEDROCK_SECRET_ACCESS_KEY") or _env("AWS_SECRET_ACCESS_KEY") or None
    aws_session_token = _env("BEDROCK_SESSION_TOKEN") or _env("AWS_SESSION_TOKEN") or None

    kwargs = {"service_name": "bedrock-runtime", "region_name": aws_region}
    if aws_access_key_id and aws_secret_access_key:
        kwargs["aws_access_key_id"] = aws_access_key_id
        kwargs["aws_secret_access_key"] = aws_secret_access_key
        if aws_session_token:
            kwargs["aws_session_token"] = aws_session_token

    try:
        bedrock_runtime = boto3.client(**kwargs)
    except NoCredentialsError:
        print("No AWS credentials. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY (or BEDROCK_*) in .env")
        return False

    # Request body per AWS docs: Submit a single prompt with InvokeModel (Titan Text Premier)
    # https://docs.aws.amazon.com/bedrock/latest/userguide/inference-invoke.html
    prompt_text = "Describe the purpose of a 'hello world' program in one line."
    native_request = {
        "messages": [{"role": "user", "content": prompt_text}],
        "textGenerationConfig": {
            "maxTokenCount": 512,
            "temperature": 0.5,
        },
    }
    body = json.dumps(native_request)

    try:
        response = bedrock_runtime.invoke_model(modelId=model_id, body=body)
        response_body = json.loads(response["body"].read())

        # Bedrock models can return different response shapes:
        # - Titan/Claude Converse: {"results": [{"outputText": "..."}]}
        # - Chat completion (e.g. Qwen): {"choices": [{"message": {"content": "..."}}]}
        if "results" in response_body and response_body["results"]:
            generated_text = response_body["results"][0].get("outputText", "")
        elif "choices" in response_body and response_body["choices"]:
            msg = response_body["choices"][0].get("message") or {}
            generated_text = msg.get("content") or ""
        else:
            print(f"Unexpected response shape. Keys: {list(response_body.keys())}")
            return False

        if not generated_text:
            print("No generated text in response.")
            return False

        print(f"Model: {model_id}")
        print(f"Response: {generated_text[:200]}{'...' if len(generated_text) > 200 else ''}")
        return True
    except ClientError as e:
        print(f"Bedrock invoke_model failed: {e.response.get('Error', {}).get('Message', e)}")
        return False
    except (KeyError, IndexError, TypeError) as e:
        print(f"Unexpected response shape: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Reference architecture smoke test (Bedrock embeddings / generation)")
    parser.add_argument("--list-models", action="store_true", help="List Bedrock foundation model IDs in a region (uses AWS credentials)")
    parser.add_argument("--embed", action="store_true", help="Test Bedrock Titan embeddings")
    parser.add_argument("--generate", action="store_true", help="Test Bedrock text generation (boto3 invoke_model, e.g. Titan Text)")
    parser.add_argument("--region", type=str, default=None, help="AWS region (e.g. us-east-1). Used by --list-models and --generate.")
    parser.add_argument("--model", type=str, default=None, help="Bedrock model ID for --generate (default: amazon.titan-text-premier-v1:0). Must support Titan InvokeModel body: inputText + textGenerationConfig.")
    parser.add_argument("--config-id", type=int, default=None, help="Ignored (kept for CLI compatibility)")
    args = parser.parse_args()

    if args.list_models:
        region = args.region or _env("RAG_BEDROCK_EMBEDDING_REGION") or "us-east-1"
        sys.exit(0 if run_list_models(region) else 1)

    if not args.embed and not args.generate:
        parser.print_help()
        print("\nProvide at least one of --list-models, --embed, or --generate.")
        sys.exit(1)

    failed = False
    if args.embed:
        if not run_embed():
            failed = True
    if args.generate:
        if not run_generate(args.config_id, region=args.region, model_id=args.model):
            failed = True
            print(
                "Hint: ensure BEDROCK_* or AWS_* credentials and region are set (e.g. in .env). "
                "See script docstring for required env vars."
            )

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
