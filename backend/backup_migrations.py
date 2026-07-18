"""Backward-compatible backup manifest migrations."""
from __future__ import annotations

from copy import deepcopy

from utils.storage_manifest import COMPONENT_VERSIONS, DATA_CLASSES, DATA_SCHEMA_VERSION


BACKUP_SCHEMA_VERSION = 2
MIN_SUPPORTED_BACKUP_SCHEMA_VERSION = 1


def migrate_backup_manifest(manifest: dict) -> dict:
    """Return a current in-memory manifest without mutating the archive."""
    if not isinstance(manifest, dict):
        raise ValueError("backup manifest must be an object")
    result = deepcopy(manifest)
    try:
        version = int(result.get("schema_version") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid backup schema version") from exc
    if version < MIN_SUPPORTED_BACKUP_SCHEMA_VERSION or version > BACKUP_SCHEMA_VERSION:
        raise ValueError(f"unsupported backup schema version: {version}")
    original_version = version
    if version == 1:
        result.setdefault("format", "kaoyan-learning-backup")
        result.setdefault("data_schema_version", 0)
        result.setdefault("component_versions", {})
        result.setdefault("data_classes", DATA_CLASSES)
        version = 2
    result["schema_version"] = version
    result["original_schema_version"] = original_version
    result.setdefault("format", "kaoyan-learning-backup")
    result.setdefault("data_schema_version", DATA_SCHEMA_VERSION)
    result.setdefault("component_versions", COMPONENT_VERSIONS)
    result.setdefault("data_classes", DATA_CLASSES)
    return result
