"""Applet manifest loader for modular route/task selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic import field_validator
import yaml


@dataclass
class AppletSpec:
    """Resolved applet specification merged from base + selected applets."""

    routes: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    flows: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)
    migration_tags: list[str] = field(default_factory=list)


class _ManifestBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    description: str | None = None


class _AppletManifest(_ManifestBase):
    applet: str
    depends_on: list[str] = Field(default_factory=list)
    routes: list[str] = Field(default_factory=list)
    tasks: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    models: list[str] = Field(default_factory=list)
    flows: list[str] = Field(default_factory=list)
    pages: list[str] = Field(default_factory=list)
    migration_tags: list[str] = Field(default_factory=list)

    @field_validator("applet", mode="before")
    @classmethod
    def _normalize_applet(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("applet must be a string")
        normalized = value.strip()
        if not normalized:
            raise ValueError("applet cannot be empty")
        return normalized

    @field_validator(
        "routes",
        "depends_on",
        "tasks",
        "services",
        "models",
        "flows",
        "pages",
        "migration_tags",
        mode="before",
    )
    @classmethod
    def _normalize_string_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("expected a list")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("list items must be strings")
            cleaned = item.strip()
            if cleaned:
                normalized.append(cleaned)
        return normalized

    @field_validator("tasks")
    @classmethod
    def _normalize_task_module_names(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for task in value:
            if task.startswith("src.tasks."):
                normalized.append(task.removeprefix("src.tasks."))
            else:
                normalized.append(task)
        return normalized

    @field_validator("migration_tags")
    @classmethod
    def _normalize_migration_tags(cls, value: list[str]) -> list[str]:
        return [tag.lower().replace("-", "_") for tag in value]


class _ProfileManifest(_ManifestBase):
    profile: str
    applets: list[str]

    @field_validator("profile", mode="before")
    @classmethod
    def _normalize_profile(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("profile must be a string")
        normalized = value.strip()
        if not normalized:
            raise ValueError("profile cannot be empty")
        return normalized

    @field_validator("applets", mode="before")
    @classmethod
    def _normalize_profile_applets(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("applets must be a list")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("applets entries must be strings")
            cleaned = item.strip()
            if cleaned:
                normalized.append(cleaned)
        if not normalized:
            raise ValueError("applets cannot be empty")
        return normalized


def parse_selected_applets(raw_value: str | None) -> list[str]:
    """Parse APPLETS env var into normalized list."""
    if raw_value is None:
        return ["all"]

    values = [item.strip() for item in raw_value.split(",") if item.strip()]
    if not values:
        return ["all"]

    return values


def resolve_applet_spec(selected_applets: list[str]) -> AppletSpec:
    """Resolve applet manifests into a single merged spec."""
    if "all" in selected_applets:
        raise ValueError("Cannot resolve concrete manifest for 'all'")

    manifests_dir = Path(__file__).resolve().parents[2] / "applets"
    merged = AppletSpec()

    # Base is always included for auth/settings/core routes.
    manifest_names = ["_base"] + selected_applets
    resolving_stack: list[str] = []
    for manifest_name in manifest_names:
        _merge_manifest(manifest_name, manifests_dir, merged, resolving_stack)

    _dedupe_spec(merged)
    return merged


def get_enabled_route_keys(raw_applets_value: str | None) -> set[str] | None:
    """Return enabled route keys set, or None when all routes are enabled."""
    selected = parse_selected_applets(raw_applets_value)
    if "all" in selected:
        return None
    return set(resolve_applet_spec(selected).routes)


def get_enabled_task_modules(raw_applets_value: str | None) -> list[str] | None:
    """Return enabled task modules, or None when all task modules are enabled."""
    selected = parse_selected_applets(raw_applets_value)
    if "all" in selected:
        return None
    return resolve_applet_spec(selected).tasks


def get_enabled_migration_tags(raw_applets_value: str | None) -> list[str] | None:
    """Return enabled migration tags, or None when all migrations are enabled."""
    selected = parse_selected_applets(raw_applets_value)
    if "all" in selected:
        return None
    return resolve_applet_spec(selected).migration_tags


def _merge_manifest(
    manifest_name: str,
    manifests_dir: Path,
    merged: AppletSpec,
    resolving_stack: list[str],
) -> None:
    if manifest_name in resolving_stack:
        cycle = " -> ".join([*resolving_stack, manifest_name])
        raise ValueError(f"Circular applet/profile reference detected: {cycle}")

    path = manifests_dir / f"{manifest_name}.yaml"
    if not path.exists():
        path = manifests_dir / "profiles" / f"{manifest_name}.yaml"
    if not path.exists():
        raise ValueError(f"Applet manifest not found: {manifest_name}")

    content = yaml.safe_load(path.read_text()) or {}
    if not isinstance(content, dict):
        raise ValueError(f"Invalid manifest {path}: expected YAML object at top level")

    # Profile manifests compose applets.
    try:
        if "applets" in content:
            profile_manifest = _ProfileManifest.model_validate(content)
            if profile_manifest.profile != manifest_name:
                raise ValueError(
                    f"Profile name mismatch: filename '{manifest_name}' "
                    f"does not match profile '{profile_manifest.profile}'"
                )
            resolving_stack.append(manifest_name)
            for applet_name in profile_manifest.applets:
                _merge_manifest(applet_name, manifests_dir, merged, resolving_stack)
            resolving_stack.pop()
            return

        applet_manifest = _AppletManifest.model_validate(content)
        if applet_manifest.applet != manifest_name:
            raise ValueError(
                f"Applet name mismatch: filename '{manifest_name}' "
                f"does not match applet '{applet_manifest.applet}'"
            )
        resolving_stack.append(manifest_name)
        for dependency_name in applet_manifest.depends_on:
            _merge_manifest(dependency_name, manifests_dir, merged, resolving_stack)
        resolving_stack.pop()
        merged.routes.extend(applet_manifest.routes)
        merged.tasks.extend(applet_manifest.tasks)
        merged.services.extend(applet_manifest.services)
        merged.models.extend(applet_manifest.models)
        merged.flows.extend(applet_manifest.flows)
        merged.pages.extend(applet_manifest.pages)
        merged.migration_tags.extend(applet_manifest.migration_tags)
    except ValidationError as exc:
        raise ValueError(f"Invalid manifest {path}: {exc}") from exc


def _dedupe_spec(spec: AppletSpec) -> None:
    spec.routes = list(dict.fromkeys(spec.routes))
    spec.tasks = list(dict.fromkeys(spec.tasks))
    spec.services = list(dict.fromkeys(spec.services))
    spec.models = list(dict.fromkeys(spec.models))
    spec.flows = list(dict.fromkeys(spec.flows))
    spec.pages = list(dict.fromkeys(spec.pages))
    spec.migration_tags = list(dict.fromkeys(spec.migration_tags))
