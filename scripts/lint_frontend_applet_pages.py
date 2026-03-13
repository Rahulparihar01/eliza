#!/usr/bin/env python3
"""Validate frontend page-key gating against applet YAML manifests.

Checks:
1) `frontend/src/shared/lib/applet-manifest.generated.json` matches applet YAML pages.
2) `pageKey: "..."` usages map to known manifest page keys.
3) `isFrontendPageEnabled("...")` usages map to known manifest page keys.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml


PAGE_KEY_PATTERN = re.compile(r"pageKey\s*:\s*['\"]([^'\"]+)['\"]")
IS_PAGE_ENABLED_PATTERN = re.compile(r"isFrontendPageEnabled\(\s*['\"]([^'\"]+)['\"]\s*\)")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_yaml_applet_pages(applets_dir: Path) -> dict[str, list[str]]:
    applet_to_pages: dict[str, list[str]] = {}
    for path in sorted(applets_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            continue
        applet = data.get("applet")
        pages = data.get("pages", [])
        if not isinstance(applet, str):
            continue
        if not isinstance(pages, list):
            pages = []
        normalized_pages = [p.strip() for p in pages if isinstance(p, str) and p.strip()]
        applet_to_pages[applet.strip()] = normalized_pages
    return applet_to_pages


def _load_generated_manifest(manifest_path: Path) -> dict[str, list[str]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    applet_to_pages = payload.get("applet_to_pages", {})
    if not isinstance(applet_to_pages, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for applet, pages in applet_to_pages.items():
        if not isinstance(applet, str):
            continue
        if not isinstance(pages, list):
            pages = []
        normalized[applet] = [p.strip() for p in pages if isinstance(p, str) and p.strip()]
    return normalized


def _extract_page_keys(file_path: Path) -> set[str]:
    content = file_path.read_text(encoding="utf-8")
    return set(PAGE_KEY_PATTERN.findall(content))


def _extract_enabled_checks(file_path: Path) -> set[str]:
    content = file_path.read_text(encoding="utf-8")
    return set(IS_PAGE_ENABLED_PATTERN.findall(content))


def _normalize(mapping: dict[str, list[str]]) -> dict[str, list[str]]:
    return {k: sorted(set(v)) for k, v in sorted(mapping.items(), key=lambda x: x[0])}


def main() -> int:
    root = _repo_root()
    applets_dir = root / "applets"
    manifest_path = root / "frontend" / "src" / "shared" / "lib" / "applet-manifest.generated.json"
    section_config = root / "frontend" / "src" / "components" / "navigation" / "sectionConfigs.ts"
    app_tsx = root / "frontend" / "src" / "App.tsx"

    errors: list[str] = []

    yaml_pages = _load_yaml_applet_pages(applets_dir)
    generated_pages = _load_generated_manifest(manifest_path)

    if _normalize(yaml_pages) != _normalize(generated_pages):
        errors.append(
            "Generated applet manifest does not match applet YAML pages. "
            "Run: python3 scripts/generate_frontend_applet_manifest.py"
        )

    known_page_keys = {page for pages in yaml_pages.values() for page in pages}
    section_page_keys = _extract_page_keys(section_config)
    app_enabled_checks = _extract_enabled_checks(app_tsx)

    unknown_section_keys = sorted(section_page_keys - known_page_keys)
    if unknown_section_keys:
        errors.append(
            "Unknown pageKey values in sectionConfigs.ts: " + ", ".join(unknown_section_keys)
        )

    unknown_enabled_checks = sorted(app_enabled_checks - known_page_keys)
    if unknown_enabled_checks:
        errors.append(
            "Unknown isFrontendPageEnabled keys in App.tsx: " + ", ".join(unknown_enabled_checks)
        )

    if errors:
        print("Frontend applet page lint failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Frontend applet page lint passed.")
    print(f"- known manifest page keys: {len(known_page_keys)}")
    print(f"- section pageKey usages: {len(section_page_keys)}")
    print(f"- App.tsx isFrontendPageEnabled checks: {len(app_enabled_checks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
