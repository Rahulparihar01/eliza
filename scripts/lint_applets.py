"""Validate applet manifests and route key coverage.

Usage:
  python scripts/lint_applets.py
"""

from __future__ import annotations

import ast
import sys
import argparse
from pathlib import Path

from src.applets.registry import resolve_applet_spec


def _extract_route_keys_from_main(main_py: Path) -> set[str]:
    content = main_py.read_text()
    module = ast.parse(content)
    route_keys: set[str] = set()

    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name):
            continue
        if node.func.id != "_include_router_if_enabled":
            continue
        if not node.args:
            continue
        first_arg = node.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            route_keys.add(first_arg.value)

    return route_keys


def _collect_manifest_names(applets_dir: Path, profile: bool) -> list[str]:
    if profile:
        files = sorted((applets_dir / "profiles").glob("*.yaml"))
    else:
        files = sorted(applets_dir.glob("*.yaml"))
    return [path.stem for path in files]


def _parse_csv_values(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint applet manifests.")
    parser.add_argument(
        "--enforce-route-coverage",
        action="store_true",
        help="Fail if any route key in src/main.py is not represented in applet manifests.",
    )
    parser.add_argument(
        "--require-applets",
        default="",
        help="Comma-separated applet names that must exist in applets/.",
    )
    parser.add_argument(
        "--enforce-profile-image-exclusion",
        action="store_true",
        help="Fail if .dockerignore does not exclude customer profile YAML files.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    applets_dir = repo_root / "applets"
    main_py = repo_root / "src" / "main.py"
    dockerignore = repo_root / ".dockerignore"

    if not applets_dir.exists():
        print("ERROR: applets directory not found.")
        return 1
    if not main_py.exists():
        print("ERROR: src/main.py not found.")
        return 1

    route_keys_in_main = _extract_route_keys_from_main(main_py)
    if not route_keys_in_main:
        print("ERROR: no route keys found in src/main.py")
        return 1

    applet_names = _collect_manifest_names(applets_dir, profile=False)
    profile_names = _collect_manifest_names(applets_dir, profile=True)
    applet_name_set = set(applet_names)

    all_manifest_route_keys: set[str] = set()
    errors: list[str] = []

    # Validate every applet and profile resolves.
    for name in applet_names:
        if name == "_base":
            continue
        try:
            spec = resolve_applet_spec([name])
            all_manifest_route_keys.update(spec.routes)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Failed to resolve applet '{name}': {exc}")

    for name in profile_names:
        try:
            spec = resolve_applet_spec([name])
            all_manifest_route_keys.update(spec.routes)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Failed to resolve profile '{name}': {exc}")

    # Include base routes for coverage checks.
    try:
        base_spec = resolve_applet_spec([])
        all_manifest_route_keys.update(base_spec.routes)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Failed to resolve base manifest: {exc}")

    unknown_manifest_routes = sorted(all_manifest_route_keys - route_keys_in_main)
    if unknown_manifest_routes:
        errors.append(
            "Manifest routes not present in src/main.py: " + ", ".join(unknown_manifest_routes)
        )

    orphan_route_keys = sorted(route_keys_in_main - all_manifest_route_keys)
    if orphan_route_keys and args.enforce_route_coverage:
        errors.append(
            "Route keys in src/main.py missing from applet manifests: "
            + ", ".join(orphan_route_keys)
        )

    required_applets = _parse_csv_values(args.require_applets)
    if required_applets:
        missing_required_applets = sorted(required_applets - applet_name_set)
        if missing_required_applets:
            errors.append(
                "Required applets missing from applets/: " + ", ".join(missing_required_applets)
            )

    if args.enforce_profile_image_exclusion:
        if not dockerignore.exists():
            errors.append(".dockerignore not found for profile image exclusion check.")
        else:
            dockerignore_content = dockerignore.read_text()
            if "applets/profiles/*.yaml" not in dockerignore_content:
                errors.append(
                    ".dockerignore must include 'applets/profiles/*.yaml' to exclude customer profiles."
                )
            if "!applets/profiles/full.yaml" not in dockerignore_content:
                errors.append(
                    ".dockerignore must include '!applets/profiles/full.yaml' for generic runtime profile."
                )

    if errors:
        print("Applet lint failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("Applet lint passed.")
    print(f"- applets checked: {len(applet_names)}")
    print(f"- profiles checked: {len(profile_names)}")
    print(f"- route keys covered: {len(all_manifest_route_keys)}")
    if orphan_route_keys:
        print(
            "- route keys currently uncovered (informational): "
            f"{len(orphan_route_keys)} (use --enforce-route-coverage to fail)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
