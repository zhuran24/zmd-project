"""IndustrialPlanner compatibility exports.

Phase 2 keeps the canonical blueprint unchanged and adds a one-way exporter into
IndustrialPlanner-readable JSON plus additive sidecar diagnostics.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "DEFAULT_BASE_ID",
    "INDUSTRIAL_PLANNER_BLUEPRINT_FILENAME",
    "INDUSTRIAL_PLANNER_MANIFEST_FILENAME",
    "INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_FILENAME",
    "INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_MARKDOWN_FILENAME",
    "INDUSTRIAL_PLANNER_VALIDATION_REPORT_FILENAME",
    "INDUSTRIAL_PLANNER_VALIDATION_REPORT_MARKDOWN_FILENAME",
    "INDUSTRIAL_PLANNER_TARGET",
    "build_industrial_planner_export_bundle",
    "build_industrial_planner_throughput_audit",
    "clear_industrial_planner_export_bundle",
    "industrial_planner_target_capabilities",
    "register_industrial_planner_exporter",
    "write_industrial_planner_export_bundle",
]


_EXPORT_BLUEPRINT_EXPORTS = {
    "INDUSTRIAL_PLANNER_BLUEPRINT_FILENAME",
    "INDUSTRIAL_PLANNER_MANIFEST_FILENAME",
    "INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_FILENAME",
    "INDUSTRIAL_PLANNER_THROUGHPUT_REPORT_MARKDOWN_FILENAME",
    "INDUSTRIAL_PLANNER_VALIDATION_REPORT_FILENAME",
    "INDUSTRIAL_PLANNER_VALIDATION_REPORT_MARKDOWN_FILENAME",
    "build_industrial_planner_export_bundle",
    "clear_industrial_planner_export_bundle",
    "register_industrial_planner_exporter",
    "write_industrial_planner_export_bundle",
}

_MAPPING_REGISTRY_EXPORTS = {
    "DEFAULT_BASE_ID",
    "INDUSTRIAL_PLANNER_TARGET",
    "industrial_planner_target_capabilities",
}



def __getattr__(name: str) -> Any:
    if name in _EXPORT_BLUEPRINT_EXPORTS:
        from src.adapters.industrial_planner import export_blueprint as _export_blueprint

        return getattr(_export_blueprint, name)
    if name in _MAPPING_REGISTRY_EXPORTS:
        from src.adapters.industrial_planner import mapping_registry as _mapping_registry

        return getattr(_mapping_registry, name)
    if name == "build_industrial_planner_throughput_audit":
        from src.adapters.industrial_planner.throughput_audit import build_industrial_planner_throughput_audit

        return build_industrial_planner_throughput_audit
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")



def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
