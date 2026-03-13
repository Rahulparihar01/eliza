#!/usr/bin/env python3
"""Validate Alembic migration tags for modular selective execution."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re
import sys

import yaml


TAG_LINE_RE = re.compile(r"^\s*tags?\s*:\s*(?P<value>.+?)\s*$", re.IGNORECASE)


def _normalize_tag(tag: str) -> str:
    return tag.strip().lower().replace("-", "_")


def _extract_docstring_tags(docstring: str | None) -> set[str]:
    if not docstring:
        return set()
    tags: set[str] = set()
    for line in docstring.splitlines():
        match = TAG_LINE_RE.match(line)
        if not match:
            continue
        for value in match.group("value").split(","):
            normalized = _normalize_tag(value)
            if normalized:
                tags.add(normalized)
    return tags


def _extract_assignment_tags(module: ast.Module) -> set[str]:
    tags: set[str] = set()
    for node in module.body:
        target: ast.Name | None = None
        value: ast.AST | None = None

        if isinstance(node, ast.Assign):
            if len(node.targets) != 1:
                continue
            if isinstance(node.targets[0], ast.Name):
                target = node.targets[0]
                value = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                target = node.target
                value = node.value
        else:
            continue

        if target is None or value is None:
            continue
        if target.id not in {"tags", "migration_tags"}:
            continue
        if isinstance(value, (ast.List, ast.Tuple)):
            for elt in value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    normalized = _normalize_tag(elt.value)
                    if normalized:
                        tags.add(normalized)
    return tags


def _extract_tags_from_file(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    module = ast.parse(source)
    tags = _extract_docstring_tags(ast.get_docstring(module))
    tags.update(_extract_assignment_tags(module))
    return tags


def _allowed_tags(repo_root: Path) -> set[str]:
    manifests_dir = repo_root / "applets"
    allowed: set[str] = set()
    for manifest_path in manifests_dir.glob("*.yaml"):
        content = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        for tag in content.get("migration_tags", []):
            if isinstance(tag, str):
                normalized = _normalize_tag(tag)
                if normalized:
                    allowed.add(normalized)
    return allowed


def run() -> int:
    parser = argparse.ArgumentParser(
        description="Lint migration tags for applet-aware selective migrations."
    )
    parser.add_argument(
        "--enforce-complete-tagging",
        action="store_true",
        help="Fail if any migration file is missing tags.",
    )
    parser.add_argument(
        "--enforce-known-tags",
        action="store_true",
        help="Fail if a migration uses tags not declared by applet manifests.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    versions_dir = repo_root / "alembic" / "versions"
    allowed = _allowed_tags(repo_root)
    if not allowed:
        print("No allowed migration tags found in applet manifests.")
        return 1

    missing: list[str] = []
    unknown: list[tuple[str, list[str]]] = []
    total = 0

    for migration_path in sorted(versions_dir.glob("*.py")):
        total += 1
        tags = _extract_tags_from_file(migration_path)
        if not tags:
            missing.append(migration_path.name)
            continue
        invalid = sorted(tags - allowed)
        if invalid:
            unknown.append((migration_path.name, invalid))

    print(
        f"Migration tag lint: files={total}, missing_tags={len(missing)}, "
        f"unknown_tag_files={len(unknown)}, allowed_tags={sorted(allowed)}"
    )

    if missing:
        print("Files missing migration tags:")
        for name in missing[:30]:
            print(f"- {name}")
        if len(missing) > 30:
            print(f"... and {len(missing) - 30} more")

    if unknown:
        print("Files using unknown migration tags:")
        for name, invalid in unknown[:30]:
            print(f"- {name}: {', '.join(invalid)}")
        if len(unknown) > 30:
            print(f"... and {len(unknown) - 30} more")

    if args.enforce_complete_tagging and missing:
        return 1
    if args.enforce_known_tags and unknown:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
