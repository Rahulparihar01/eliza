#!/usr/bin/env bash
set -euo pipefail

# Ensure a lockfile exists, then sync the environment to it.
if [ ! -f uv.lock ]; then
  uv lock
fi

uv sync "$@"
