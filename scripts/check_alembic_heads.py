#!/usr/bin/env python3
"""Check Alembic head topology before/after flatten operations."""

from __future__ import annotations

import argparse
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def run() -> int:
    parser = argparse.ArgumentParser(
        description="Report Alembic heads and enforce optional constraints."
    )
    parser.add_argument(
        "--expect-single-head",
        action="store_true",
        help="Fail if more than one Alembic head is present.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    config = Config(str(repo_root / "alembic.ini"))
    script_dir = ScriptDirectory.from_config(config)

    heads = sorted(script_dir.get_heads())
    print(f"Alembic heads ({len(heads)}): {', '.join(heads) if heads else '(none)'}")

    if args.expect_single_head and len(heads) != 1:
        print("ERROR: expected exactly one Alembic head.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
