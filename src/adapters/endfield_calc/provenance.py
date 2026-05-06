"""Provenance helpers for endfield-calc snapshot ingest."""

from __future__ import annotations

from typing import Any, Mapping

from src.interchange.normalized_catalog import build_catalog_metadata

DEFAULT_SOURCE = "JamboChen/endfield-calc snapshot"
DEFAULT_LICENSE = "MIT"
_EXTENSION_RESERVED_KEYS = {
    "source",
    "generated_at",
    "source_version",
    "version",
    "source_commit",
    "commit",
    "source_license",
    "notes",
    "upstream_repository",
    "tick_interval_seconds",
}


def build_endfield_calc_catalog_metadata(snapshot_metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    snapshot_metadata = dict(snapshot_metadata or {})
    generated_at = snapshot_metadata.get("generated_at")
    extensions: dict[str, Any] = {
        "upstream_repository": snapshot_metadata.get("upstream_repository", "https://github.com/JamboChen/endfield-calc"),
        "tick_interval_seconds": float(snapshot_metadata.get("tick_interval_seconds", 2.0)),
    }
    for key, value in snapshot_metadata.items():
        if key in _EXTENSION_RESERVED_KEYS or value is None:
            continue
        extensions[str(key)] = value
    return build_catalog_metadata(
        source=str(snapshot_metadata.get("source", DEFAULT_SOURCE)),
        generated_at=str(generated_at) if generated_at else None,
        source_version=snapshot_metadata.get("source_version") or snapshot_metadata.get("version"),
        source_commit=snapshot_metadata.get("source_commit") or snapshot_metadata.get("commit"),
        source_license=snapshot_metadata.get("source_license") or DEFAULT_LICENSE,
        notes=snapshot_metadata.get("notes")
        or [
            "Snapshot ingest is build-time only and does not add a runtime dependency on upstream code.",
            "Field aliases are normalized into the neutral catalog contract before downstream use.",
        ],
        extensions=extensions,
    )
