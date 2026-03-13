#!/usr/bin/env python3
"""Applet-aware migration runner with selective execution support."""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from pathlib import Path
from typing import Iterable

from alembic import command
from alembic.config import Config
from alembic.script import Script, ScriptDirectory


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.applets.registry import get_enabled_migration_tags

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
        raw = match.group("value")
        for value in raw.split(","):
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


def _extract_revision_tags(script: Script) -> set[str]:
    source = Path(script.path).read_text(encoding="utf-8")
    module = ast.parse(source)
    docstring = ast.get_docstring(module)
    tags = _extract_docstring_tags(docstring)
    tags.update(_extract_assignment_tags(module))
    return tags


def _parent_revisions(script: Script) -> tuple[str, ...]:
    down_revision = script.down_revision
    if down_revision is None:
        return tuple()
    if isinstance(down_revision, str):
        return (down_revision,)
    return tuple(down_revision)


def _revision_order_map(revisions_ascending: list[Script]) -> dict[str, int]:
    return {script.revision: idx for idx, script in enumerate(revisions_ascending)}


def _collect_ancestors(
    revision_id: str,
    parent_map: dict[str, tuple[str, ...]],
    acc: set[str],
) -> None:
    for parent in parent_map.get(revision_id, tuple()):
        if parent in acc:
            continue
        acc.add(parent)
        _collect_ancestors(parent, parent_map, acc)


def _build_selective_plan(
    revisions_ascending: list[Script],
    desired_tags: set[str],
) -> tuple[set[str], list[str], list[str]]:
    tags_by_revision = {script.revision: _extract_revision_tags(script) for script in revisions_ascending}
    untagged = sorted(
        revision_id for revision_id, tags in tags_by_revision.items() if not tags
    )
    if untagged:
        raise ValueError(
            "Selective execution requires tags on every migration revision. "
            f"Found untagged revisions: {', '.join(untagged[:8])}"
            + ("..." if len(untagged) > 8 else "")
        )

    include = {
        revision_id
        for revision_id, tags in tags_by_revision.items()
        if tags.intersection(desired_tags)
    }
    if not include:
        return set(), [], []

    parent_map = {
        script.revision: _parent_revisions(script) for script in revisions_ascending
    }
    include_closure = set(include)
    for revision_id in tuple(include):
        _collect_ancestors(revision_id, parent_map, include_closure)

    children_map: dict[str, set[str]] = {script.revision: set() for script in revisions_ascending}
    for child, parents in parent_map.items():
        for parent in parents:
            if parent in children_map:
                children_map[parent].add(child)

    target_heads = sorted(
        [
            revision_id
            for revision_id in include_closure
            if not (children_map.get(revision_id, set()) & include_closure)
        ],
        key=_revision_order_map(revisions_ascending).get,
    )

    excluded_tagged = sorted(
        revision_id
        for revision_id, tags in tags_by_revision.items()
        if tags and revision_id not in include_closure
    )

    return include_closure, target_heads, excluded_tagged


def _upgrade_targets(config: Config, targets: Iterable[str]) -> None:
    for target in targets:
        print(f"[migrations] Upgrading to selective target: {target}")
        command.upgrade(config, target)


def _normalize_applets(raw_value: str | None) -> str:
    if raw_value is None:
        return "all"
    value = raw_value.strip()
    return value or "all"


def run() -> int:
    parser = argparse.ArgumentParser(
        description="Run Alembic migrations with applet-aware tag resolution."
    )
    parser.add_argument(
        "--applets",
        default=os.getenv("APPLETS"),
        help="Comma-separated applets/profile (defaults to APPLETS env var).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve and print migration tags without running Alembic.",
    )
    parser.add_argument(
        "--mode",
        choices=["safe", "auto", "selective", "strict"],
        default="auto",
        help=(
            "safe: always run full migration tree; "
            "auto: try selective and fallback to full if not ready; "
            "selective: fail if selective plan cannot be built; "
            "strict: fail on any selective mismatch (no fallback/no-op)."
        ),
    )
    args = parser.parse_args()

    selected_applets = _normalize_applets(args.applets)
    try:
        resolved_tags = get_enabled_migration_tags(selected_applets)
    except ValueError as exc:
        print(f"[migrations] ERROR: invalid APPLETS selection '{selected_applets}': {exc}")
        return 1

    if resolved_tags is None:
        print("[migrations] APPLETS=all -> full migration tree will run.")
    else:
        tag_list = ", ".join(resolved_tags) if resolved_tags else "(none)"
        print(
            f"[migrations] APPLETS={selected_applets} -> resolved migration tags: {tag_list}"
        )
        print(
            "[migrations] Selective mode is enabled with safety guardrails. "
            "If revision tags are incomplete, mode=auto falls back to full tree."
        )

    if resolved_tags is None:
        if args.dry_run:
            return 0
        print("[migrations] Running full migration tree.")
        command.upgrade(Config("alembic.ini"), "heads")
        return 0

    normalized_tags = {_normalize_tag(tag) for tag in resolved_tags}
    revisions_ascending = list(reversed(list(ScriptDirectory.from_config(Config("alembic.ini")).walk_revisions())))

    if args.mode == "safe":
        print("[migrations] Mode=safe -> running full migration tree.")
        if args.dry_run:
            return 0
        command.upgrade(Config("alembic.ini"), "heads")
        return 0

    try:
        include_closure, target_heads, excluded_tagged = _build_selective_plan(
            revisions_ascending,
            normalized_tags,
        )
    except ValueError as exc:
        if args.mode in {"selective", "strict"}:
            print(f"[migrations] ERROR: {exc}")
            return 1
        print(f"[migrations] WARNING: selective plan unavailable: {exc}")
        print("[migrations] WARNING: falling back to full migration tree.")
        if args.dry_run:
            return 0
        command.upgrade(Config("alembic.ini"), "heads")
        return 0

    if not include_closure:
        if args.mode == "strict":
            print("[migrations] ERROR: no revisions matched selected tags in strict mode.")
            return 1
        print("[migrations] No revisions matched selected tags; nothing to run.")
        return 0

    print(
        "[migrations] Selective plan ready: "
        f"apply {len(include_closure)} revisions, "
        f"target heads={target_heads}, "
        f"excluded tagged revisions={len(excluded_tagged)}."
    )
    if args.dry_run:
        return 0

    _upgrade_targets(Config("alembic.ini"), target_heads)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
