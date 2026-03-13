"""Applet registry package."""

from src.applets.registry import (
    get_enabled_migration_tags,
    get_enabled_route_keys,
    get_enabled_task_modules,
    parse_selected_applets,
)

__all__ = [
    "get_enabled_migration_tags",
    "get_enabled_route_keys",
    "get_enabled_task_modules",
    "parse_selected_applets",
]
