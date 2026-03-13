#!/usr/bin/env python3
"""Validate Alembic flatten readiness for modular deployments."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run_step(command: list[str], label: str, cwd: Path) -> None:
    print(f"[flatten-readiness] {label}")
    print(f"[flatten-readiness] $ {' '.join(command)}")
    subprocess.run(command, cwd=str(cwd), check=True)


def run() -> int:
    parser = argparse.ArgumentParser(
        description="Run flatten-readiness checks for applet-aware migrations."
    )
    parser.add_argument(
        "--applets",
        nargs="+",
        default=["full", "adoption"],
        help="Applet selections to validate with selective dry-run.",
    )
    parser.add_argument(
        "--require-single-head",
        action="store_true",
        help="Fail unless exactly one Alembic head exists.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    python = sys.executable

    head_command = [python, "scripts/check_alembic_heads.py"]
    if args.require_single_head:
        head_command.append("--expect-single-head")
    _run_step(head_command, "Checking Alembic head topology", repo_root)

    _run_step(
        [
            python,
            "scripts/lint_migration_tags.py",
            "--enforce-known-tags",
            "--enforce-complete-tagging",
        ],
        "Checking strict migration tag coverage",
        repo_root,
    )

    for applet_selection in args.applets:
        _run_step(
            [
                python,
                "scripts/run_migrations.py",
                "--applets",
                applet_selection,
                "--mode",
                "selective",
                "--dry-run",
            ],
            f"Building selective migration plan for APPLETS={applet_selection}",
            repo_root,
        )

    print("[flatten-readiness] All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
