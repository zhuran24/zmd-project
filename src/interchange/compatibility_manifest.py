"""Compatibility-manifest helpers for additive downstream exports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from src.interchange.target_capabilities import normalize_target_capabilities

COMPATIBILITY_MANIFEST_VERSION = "0.1.0"
_VALID_MAPPING_CLASSES = {"direct", "lossy", "dropped", "derived"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_mapping_entry(
    *,
    classification: str,
    source_path: str,
    target_path: str | None = None,
    reason: str | None = None,
    notes: Sequence[Any] | None = None,
    source_value: Any | None = None,
    target_value: Any | None = None,
) -> dict[str, Any]:
    classification = str(classification).strip().lower()
    if classification not in _VALID_MAPPING_CLASSES:
        raise ValueError(f"unsupported mapping classification: {classification}")
    entry: dict[str, Any] = {
        "classification": classification,
        "source_path": str(source_path),
    }
    if target_path is not None:
        entry["target_path"] = str(target_path)
    if reason is not None:
        entry["reason"] = str(reason)
    if notes is not None:
        entry["notes"] = [str(note) for note in notes]
    if source_value is not None:
        entry["source_value"] = source_value
    if target_value is not None:
        entry["target_value"] = target_value
    return entry


def build_compatibility_manifest(
    *,
    target: str,
    export_mode: str,
    target_capabilities: Mapping[str, Any] | None = None,
    source_blueprint_version: str | None = None,
    mapping_entries: Iterable[Mapping[str, Any]] = (),
    warnings: Sequence[Any] | None = None,
    metadata_extensions: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    buckets = {
        "direct_mappings": [],
        "lossy_mappings": [],
        "dropped_fields": [],
        "derived_mappings": [],
    }

    for raw_entry in mapping_entries:
        if not isinstance(raw_entry, Mapping):
            raise TypeError("mapping entry must be a mapping")
        entry = build_mapping_entry(
            classification=str(raw_entry.get("classification", "")),
            source_path=str(raw_entry.get("source_path", "")),
            target_path=raw_entry.get("target_path"),
            reason=raw_entry.get("reason"),
            notes=raw_entry.get("notes"),
            source_value=raw_entry.get("source_value"),
            target_value=raw_entry.get("target_value"),
        )
        if entry["classification"] == "direct":
            buckets["direct_mappings"].append(entry)
        elif entry["classification"] == "lossy":
            buckets["lossy_mappings"].append(entry)
        elif entry["classification"] == "dropped":
            buckets["dropped_fields"].append(entry)
        else:
            buckets["derived_mappings"].append(entry)

    for key, entries in buckets.items():
        entries.sort(key=lambda entry: (str(entry.get("source_path", "")), str(entry.get("target_path", ""))))
        buckets[key] = entries

    metadata = {
        "version": COMPATIBILITY_MANIFEST_VERSION,
        "target": str(target),
        "export_mode": str(export_mode),
        "generated_at": generated_at or _now_iso(),
    }
    if source_blueprint_version is not None:
        metadata["source_blueprint_version"] = str(source_blueprint_version)
    if metadata_extensions:
        metadata["extensions"] = dict(metadata_extensions)

    normalized_warnings = []
    if warnings is not None:
        normalized_warnings = sorted(str(warning) for warning in warnings)

    return {
        "metadata": metadata,
        "target_capabilities": normalize_target_capabilities(target_capabilities),
        **buckets,
        "warnings": normalized_warnings,
    }
