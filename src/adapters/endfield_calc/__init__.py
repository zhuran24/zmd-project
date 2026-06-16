"""Build-time snapshot adapter for JamboChen/endfield-calc inspired data ingestion."""

from src.adapters.endfield_calc.diff_report import (
    build_catalog_diff_report,
    render_catalog_diff_markdown,
)
from src.adapters.endfield_calc.normalize_catalog import build_normalized_catalog_from_snapshot_payload
from src.adapters.endfield_calc.semantic_mapping import (
    CURRENT_REPOSITORY_SEMANTIC_TARGET,
    available_semantic_targets,
    project_catalog_to_current_repository_semantics,
    project_catalog_to_semantic_target,
)
from src.adapters.endfield_calc.snapshot_ingest import (
    detect_snapshot_source_format,
    ingest_snapshot_dir,
    ingest_snapshot_source,
    load_snapshot_dir,
    load_snapshot_source,
    write_snapshot_payload,
)

__all__ = [
    "build_catalog_diff_report",
    "build_normalized_catalog_from_snapshot_payload",
    "CURRENT_REPOSITORY_SEMANTIC_TARGET",
    "available_semantic_targets",
    "detect_snapshot_source_format",
    "ingest_snapshot_dir",
    "ingest_snapshot_source",
    "project_catalog_to_current_repository_semantics",
    "project_catalog_to_semantic_target",
    "load_snapshot_dir",
    "load_snapshot_source",
    "render_catalog_diff_markdown",
    "write_snapshot_payload",
]
