"""Viewer-side report assembly for canonical blueprints."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.adapters.base_planner.report_shapes import build_blueprint_report
from src.adapters.dige.result_view_models import (
    build_result_cards,
    build_result_warnings,
    build_viewer_defaults,
)
from src.io.serializer import (
    load_canonical_blueprint,
    load_candidate_placements,
    load_json_mapping,
)
from src.search.exact_campaign import atomic_write_json

VIEWER_REPORT_FILENAME = "viewer_report.json"
VIEWER_REPORT_VERSION = "0.1.0"


def build_viewer_report_from_blueprint_payload(
    *,
    blueprint_payload: Mapping[str, Any],
    facility_pools: Mapping[str, Any],
    rules_payload: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    summary = build_blueprint_report(
        blueprint_payload=blueprint_payload,
        facility_pools=facility_pools,
        rules_payload=rules_payload,
    )
    return {
        "metadata": {
            "version": VIEWER_REPORT_VERSION,
            "generated_at": generated_at or _now_iso(),
            "source_blueprint_version": str(summary["metadata"]["version"]),
        },
        "summary": summary,
        "cards": build_result_cards(summary),
        "warnings": build_result_warnings(summary),
        "viewer_defaults": build_viewer_defaults(),
    }


def build_viewer_report_from_project_root(project_root: Path) -> dict[str, Any]:
    project_root = Path(project_root)
    blueprint_payload = load_canonical_blueprint(project_root / "data" / "blueprints" / "optimal_blueprint.json")
    facility_pools = load_candidate_placements(project_root / "data" / "preprocessed" / "candidate_placements.json")
    rules_path = project_root / "rules" / "canonical_rules.json"
    rules_payload = load_json_mapping(rules_path) if rules_path.exists() else {}
    return build_viewer_report_from_blueprint_payload(
        blueprint_payload=blueprint_payload,
        facility_pools=facility_pools,
        rules_payload=rules_payload,
    )


def write_viewer_report(output_path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    atomic_write_json(Path(output_path), normalized)
    return normalized


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
