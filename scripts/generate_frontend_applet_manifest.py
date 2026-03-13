#!/usr/bin/env python3
"""Generate frontend applet/page manifest from applet YAML files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_applet_pages(applets_dir: Path) -> dict[str, list[str]]:
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
        normalized_pages = [p for p in pages if isinstance(p, str) and p.strip()]
        applet_to_pages[applet.strip()] = normalized_pages
    return applet_to_pages


def main() -> int:
    root = _repo_root()
    applets_dir = root / "applets"
    output_path = root / "frontend" / "src" / "shared" / "lib" / "applet-manifest.generated.json"

    payload: dict[str, Any] = {
        "generated_from": "applets/*.yaml",
        "applet_to_pages": _load_applet_pages(applets_dir),
    }

    output_path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")
    print(f"Generated {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
