"""Certified delivery manifest helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from src.io.output_schema import blueprint_output_path
from src.search.exact_campaign import (
    DEFAULT_CAMPAIGN_FILENAME,
    atomic_write_json,
    candidate_key,
    has_certified_export_surface,
    has_terminal_full_frontier_certified_evidence,
    now_iso,
)

DELIVERY_MANIFEST_VERSION = "1.0.0"
DELIVERY_MANIFEST_SOURCE = "certified_exact_delivery_manifest_v1"
DELIVERY_MANIFEST_FILENAME = "certified_delivery_manifest.json"


def delivery_manifest_output_path(project_root: Path) -> Path:
    return project_root / "data" / "solutions" / DELIVERY_MANIFEST_FILENAME


def build_certified_delivery_manifest(
    *,
    project_root: Path,
    campaign_state: Mapping[str, Any],
    campaign_path: Optional[Path] = None,
) -> Dict[str, Any]:
    if str(campaign_state.get("solve_mode")) != "certified_exact":
        raise ValueError("delivery manifest only supports certified_exact campaign state")

    resolved_campaign_path = campaign_path or (
        project_root / "data" / "checkpoints" / DEFAULT_CAMPAIGN_FILENAME
    )
    declare_mode = str(campaign_state.get("declare_mode", "strict"))
    final_result = campaign_state.get("final_result")
    final_status = _optional_string(campaign_state.get("final_status"))
    has_certified_surface = has_certified_export_surface(campaign_state)
    if has_certified_surface:
        if declare_mode != "strict":
            raise ValueError("certified delivery manifest requires strict declare_mode")
        if final_status == "CERTIFIED" and not isinstance(final_result, Mapping):
            raise ValueError("certified delivery manifest requires terminal final_result evidence")
        if not has_terminal_full_frontier_certified_evidence(campaign_state):
            raise ValueError(
                "certified delivery manifest requires exhausted strict candidate frontier"
            )
    best_result = _build_best_certified_result_payload(campaign_state)
    if has_certified_surface and best_result is None:
        raise ValueError("certified delivery manifest requires terminal final_result evidence")
    payload = {
        "metadata": {
            "version": DELIVERY_MANIFEST_VERSION,
            "export_timestamp": now_iso(),
            "source": DELIVERY_MANIFEST_SOURCE,
        },
        "campaign": {
            "solve_mode": str(campaign_state.get("solve_mode", "")),
            "final_status": final_status,
            "last_stop_reason": _mapping_or_none(campaign_state.get("last_stop_reason")),
            "declare_mode": declare_mode,
            "campaign_hours": float(campaign_state.get("campaign_hours", 0.0)),
            "schema_version": int(campaign_state.get("schema_version", 0)),
            "proof_summary_schema_version": int(
                campaign_state.get("proof_summary_schema_version", 0)
            ),
            "updated_at": str(campaign_state.get("updated_at", "")),
        },
        "best_certified_result": best_result,
        "artifacts": {
            "campaign_state": _artifact_entry(project_root, resolved_campaign_path),
            "final_solution": _artifact_entry(
                project_root,
                project_root / "data" / "solutions" / "final_solution.json",
            ),
            "optimal_blueprint": _artifact_entry(project_root, blueprint_output_path(project_root)),
            "candidate_placements": _artifact_entry(
                project_root,
                project_root / "data" / "preprocessed" / "candidate_placements.json",
            ),
            "benders_cuts": _artifact_entry(
                project_root,
                project_root / "data" / "checkpoints" / "benders_cuts.jsonl",
            ),
        },
    }
    compatibility_exports = build_compatibility_exports_payload(project_root)
    if compatibility_exports:
        payload["compatibility_exports"] = compatibility_exports
    return payload


def write_certified_delivery_manifest(
    output_path: Path,
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    normalized = dict(payload)
    atomic_write_json(output_path, normalized)
    return normalized


def export_certified_delivery_manifest(
    *,
    project_root: Path,
    campaign_state: Mapping[str, Any],
    campaign_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> Tuple[Path, Dict[str, Any]]:
    target_path = output_path or delivery_manifest_output_path(project_root)
    payload = build_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=campaign_state,
        campaign_path=campaign_path,
    )
    normalized = write_certified_delivery_manifest(target_path, payload)
    return target_path, normalized


def _artifact_entry(project_root: Path, path: Path) -> Dict[str, Any]:
    return {
        "path": path.relative_to(project_root).as_posix(),
        "exists": bool(path.exists()),
    }


def _build_best_certified_result_payload(
    campaign_state: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    if str(campaign_state.get("declare_mode", "strict")) != "strict":
        return None
    if not has_terminal_full_frontier_certified_evidence(campaign_state):
        return None
    final_result = campaign_state.get("final_result")
    if not isinstance(final_result, Mapping):
        return None

    ghost_rect = _mapping_or_none(final_result.get("ghost_rect"))
    if ghost_rect is None:
        return None

    ghost_w = int(ghost_rect.get("w", 0))
    ghost_h = int(ghost_rect.get("h", 0))
    record = _best_certified_candidate_record(campaign_state, ghost_w=ghost_w, ghost_h=ghost_h)
    if record is None:
        return None
    search_stats = final_result.get("search_stats")
    if not isinstance(search_stats, Mapping):
        search_stats = {}

    return {
        "ghost_rect": {
            "w": ghost_w,
            "h": ghost_h,
            "area": int(ghost_rect.get("area", ghost_w * ghost_h)),
        },
        "search_status": "CERTIFIED",
        "search_stats": dict(search_stats),
        "proof_summary": dict(record.get("proof_summary", {})),
        "loaded_exact_safe_cut_count": int(record.get("loaded_exact_safe_cut_count", 0)),
        "generated_exact_safe_cut_count": int(record.get("generated_exact_safe_cut_count", 0)),
    }


def _best_certified_candidate_record(
    campaign_state: Mapping[str, Any],
    *,
    ghost_w: int,
    ghost_h: int,
) -> Optional[Mapping[str, Any]]:
    candidates = campaign_state.get("candidates")
    if not isinstance(candidates, Mapping):
        return None
    record = candidates.get(candidate_key(ghost_w, ghost_h))
    if not isinstance(record, Mapping):
        return None
    if str(record.get("status", "")) != "CERTIFIED":
        return None
    return record


def _mapping_or_none(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, Mapping):
        return None
    return dict(value)


def _optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)



def build_compatibility_exports_payload(project_root: Path) -> Dict[str, Any]:
    exports_root = project_root / "data" / "exports"
    if not exports_root.exists():
        return {}

    payload: Dict[str, Any] = {}
    for target_dir in sorted(path for path in exports_root.iterdir() if path.is_dir()):
        blueprint_path = target_dir / f"{target_dir.name}.blueprint.json"
        manifest_path = target_dir / f"{target_dir.name}.compatibility_manifest.json"
        if not blueprint_path.exists() and not manifest_path.exists():
            continue
        validation_report_path = target_dir / "validation_report.json"
        validation_report_markdown_path = target_dir / "validation_report.md"
        throughput_report_path = target_dir / "throughput_report.json"
        throughput_report_markdown_path = target_dir / "throughput_report.md"
        payload[target_dir.name] = {
            "blueprint": _artifact_entry(project_root, blueprint_path),
            "compatibility_manifest": _artifact_entry(project_root, manifest_path),
            "validation_report": _artifact_entry(project_root, validation_report_path),
            "validation_report_markdown": _artifact_entry(project_root, validation_report_markdown_path),
            "throughput_report": _artifact_entry(project_root, throughput_report_path),
            "throughput_report_markdown": _artifact_entry(project_root, throughput_report_markdown_path),
        }
    return payload
