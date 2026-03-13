#!/usr/bin/env bash
set -euo pipefail

# Export dependencies for legacy tooling (not used by Docker).
uv export --format requirements-txt --output-file requirements.txt --no-hashes "$@"
