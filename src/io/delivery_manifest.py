"""Certified delivery manifest helpers."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from src.io.output_schema import blueprint_output_path
from src.io.serializer import (
    build_blueprint_payload_from_certified_result,
    load_candidate_placements,
    load_canonical_blueprint,
    recover_legacy_render_payload_from_blueprint,
)
from src.search.exact_campaign import (
    DEFAULT_CAMPAIGN_FILENAME,
    _path_has_symlink_component,
    atomic_write_json,
    candidate_key,
    certified_terminal_evidence_violation,
    compute_exact_artifact_hashes,
    has_certified_export_surface,
    has_terminal_full_frontier_certified_evidence,
    has_valid_terminal_full_frontier_certified_evidence_for_project,
    terminal_certified_final_result_violation_for_project,
    now_iso,
    validate_exact_campaign_resume_state,
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
    project_root = Path(project_root).resolve()
    if str(campaign_state.get("solve_mode")) != "certified_exact":
        raise ValueError("delivery manifest only supports certified_exact campaign state")

    resolved_campaign_path = _resolve_campaign_path(
        project_root=project_root,
        campaign_path=campaign_path,
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
        terminal_violation = certified_terminal_evidence_violation(campaign_state)
        if terminal_violation is None:
            terminal_violation = terminal_certified_final_result_violation_for_project(
                campaign_state,
                project_root=project_root,
            )
        if terminal_violation is not None:
            raise ValueError(
                "certified delivery manifest requires valid project-bound "
                "terminal final_result evidence: "
                f"{terminal_violation}"
            )
    best_result = _build_best_certified_result_payload(
        project_root=project_root,
        campaign_state=campaign_state,
    )
    if has_certified_surface and best_result is None:
        raise ValueError("certified delivery manifest requires terminal final_result evidence")
    final_solution_path = project_root / "data" / "solutions" / "final_solution.json"
    optimal_blueprint_path = blueprint_output_path(project_root)
    if best_result is not None:
        missing_delivery_artifacts: list[str] = []
        if not _is_regular_file(final_solution_path):
            missing_delivery_artifacts.append("final_solution")
        if not _is_regular_file(optimal_blueprint_path):
            missing_delivery_artifacts.append("optimal_blueprint")
        if missing_delivery_artifacts:
            raise ValueError(
                "certified delivery manifest requires exported delivery artifacts before "
                "best_certified_result: " + ",".join(missing_delivery_artifacts)
            )
        validate_delivery_artifacts_match_campaign(
            project_root=project_root,
            campaign_state=campaign_state,
            final_solution_path=final_solution_path,
            optimal_blueprint_path=optimal_blueprint_path,
        )
    if best_result is not None:
        _validate_campaign_state_matches_disk_authority(
            project_root=project_root,
            campaign_state=campaign_state,
            campaign_path=campaign_path,
        )
        _validate_campaign_resume_compatible_with_current_artifacts(
            project_root=project_root,
            campaign_state=campaign_state,
        )

    payload = {
        "metadata": _manifest_metadata_payload(),
        "campaign": _campaign_manifest_payload(campaign_state),
        "best_certified_result": best_result,
        "artifacts": _manifest_artifacts_payload(
            project_root=project_root,
            campaign_path=resolved_campaign_path,
            final_solution_path=final_solution_path,
            optimal_blueprint_path=optimal_blueprint_path,
        ),
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
    if normalized.get("best_certified_result") is not None:
        raise ValueError(
            "direct certified delivery manifest writes must use "
            "export_certified_delivery_manifest canonical writer"
        )
    atomic_write_json(output_path, normalized)
    return normalized


def export_certified_delivery_manifest(
    *,
    project_root: Path,
    campaign_state: Mapping[str, Any],
    campaign_path: Optional[Path] = None,
    output_path: Optional[Path] = None,
) -> Tuple[Path, Dict[str, Any]]:
    project_root = Path(project_root).resolve()
    target_path = (
        Path(output_path)
        if output_path is not None
        else delivery_manifest_output_path(project_root)
    )
    if not target_path.is_absolute():
        target_path = project_root / target_path
    payload = build_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=campaign_state,
        campaign_path=campaign_path,
    )
    _validate_certified_manifest_output_path(
        project_root=project_root,
        output_path=target_path,
        payload=payload,
    )
    normalized = dict(payload)
    atomic_write_json(target_path, normalized)
    return target_path, normalized


def validate_certified_delivery_manifest_matches_campaign(
    *,
    project_root: Path,
    delivery_manifest: Mapping[str, Any],
    campaign_state: Mapping[str, Any],
    campaign_path: Optional[Path] = None,
) -> None:
    """Fail closed unless a manifest is the current campaign/artifact projection.

    The manifest export timestamp is intentionally freshness metadata, not proof
    evidence; every other manifest field is required to match the payload that
    would be generated from the current checkpoint and delivery artifacts.
    """

    if not isinstance(delivery_manifest, Mapping):
        raise ValueError("certified delivery manifest currentness requires JSON mapping payload")
    expected = build_certified_delivery_manifest(
        project_root=project_root,
        campaign_state=campaign_state,
        campaign_path=campaign_path,
    )
    if not _manifest_metadata_is_compatible(delivery_manifest.get("metadata")):
        raise ValueError("certified delivery manifest metadata does not match current contract")
    actual_comparable = _manifest_payload_for_currentness_compare(delivery_manifest)
    expected_comparable = _manifest_payload_for_currentness_compare(expected)
    if not _json_equivalent(actual_comparable, expected_comparable):
        raise ValueError("certified delivery manifest does not match current campaign artifacts")


def _manifest_metadata_payload() -> Dict[str, Any]:
    return {
        "version": DELIVERY_MANIFEST_VERSION,
        "export_timestamp": now_iso(),
        "source": DELIVERY_MANIFEST_SOURCE,
    }


def _manifest_metadata_is_compatible(metadata: Any) -> bool:
    if not isinstance(metadata, Mapping):
        return False
    if set(metadata.keys()) != {"version", "export_timestamp", "source"}:
        return False
    export_timestamp = metadata.get("export_timestamp")
    if not isinstance(export_timestamp, str) or not export_timestamp.strip():
        return False
    return (
        str(metadata.get("version")) == DELIVERY_MANIFEST_VERSION
        and str(metadata.get("source")) == DELIVERY_MANIFEST_SOURCE
    )


def _manifest_payload_for_currentness_compare(payload: Mapping[str, Any]) -> Dict[str, Any]:
    comparable = dict(payload)
    metadata = comparable.get("metadata")
    if isinstance(metadata, Mapping):
        comparable["metadata"] = {
            "version": metadata.get("version"),
            "source": metadata.get("source"),
        }
    else:
        comparable["metadata"] = None
    return comparable


def _campaign_manifest_payload(campaign_state: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "solve_mode": str(campaign_state.get("solve_mode", "")),
        "final_status": _optional_string(campaign_state.get("final_status")),
        "last_stop_reason": _mapping_or_none(campaign_state.get("last_stop_reason")),
        "declare_mode": str(campaign_state.get("declare_mode", "strict")),
        "campaign_hours": float(campaign_state.get("campaign_hours", 0.0)),
        "schema_version": int(campaign_state.get("schema_version", 0)),
        "proof_summary_schema_version": int(
            campaign_state.get("proof_summary_schema_version", 0)
        ),
        "updated_at": str(campaign_state.get("updated_at", "")),
    }


def _manifest_artifacts_payload(
    *,
    project_root: Path,
    campaign_path: Path,
    final_solution_path: Path,
    optimal_blueprint_path: Path,
) -> Dict[str, Any]:
    return {
        "campaign_state": _artifact_entry(project_root, campaign_path),
        "final_solution": _artifact_entry(
            project_root,
            final_solution_path,
        ),
        "optimal_blueprint": _artifact_entry(project_root, optimal_blueprint_path),
        "candidate_placements": _artifact_entry(
            project_root,
            project_root / "data" / "preprocessed" / "candidate_placements.json",
        ),
        "benders_cuts": _artifact_entry(
            project_root,
            project_root / "data" / "checkpoints" / "benders_cuts.jsonl",
        ),
    }


def _validate_campaign_resume_compatible_with_current_artifacts(
    *,
    project_root: Path,
    campaign_state: Mapping[str, Any],
) -> None:
    try:
        current_hashes = compute_exact_artifact_hashes(project_root)
    except Exception as exc:
        raise ValueError(
            "certified delivery manifest requires current exact artifact hashes"
        ) from exc
    reason = validate_exact_campaign_resume_state(
        campaign_state,
        current_hashes,
        project_root=project_root,
    )
    if reason is not None:
        raise ValueError(
            "certified delivery manifest requires campaign checkpoint to be "
            f"resume-compatible with current exact artifacts: {reason}"
        )


def _campaign_path_for_regular_file_check(
    *,
    project_root: Path,
    campaign_path: Optional[Path],
) -> Path:
    project_root = Path(project_root).resolve()
    if campaign_path is None:
        return project_root / "data" / "checkpoints" / DEFAULT_CAMPAIGN_FILENAME
    path = Path(campaign_path)
    if path.is_absolute():
        return path
    return project_root / path


def _resolve_campaign_path(*, project_root: Path, campaign_path: Optional[Path]) -> Path:
    return _campaign_path_for_regular_file_check(
        project_root=project_root,
        campaign_path=campaign_path,
    ).resolve()


def _validate_campaign_state_matches_disk_authority(
    *,
    project_root: Path,
    campaign_state: Mapping[str, Any],
    campaign_path: Optional[Path],
) -> None:
    """Require certified manifest payloads to use the disk checkpoint as authority."""

    if not isinstance(campaign_state, Mapping):
        raise ValueError("certified delivery manifest requires campaign_state mapping payload")
    project_root = Path(project_root).resolve()
    raw_state_path = _campaign_path_for_regular_file_check(
        project_root=project_root,
        campaign_path=campaign_path,
    )
    state_path = raw_state_path.resolve()
    try:
        state_path.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(
            "certified delivery manifest requires campaign checkpoint inside project"
        ) from exc
    if not _is_regular_file(raw_state_path):
        raise ValueError(
            "certified delivery manifest requires regular campaign checkpoint artifact"
        )
    disk_payload = _load_json_mapping(raw_state_path, "campaign_state")
    try:
        payload_matches_disk = _json_equivalent(disk_payload, campaign_state)
    except Exception as exc:
        raise ValueError(
            "certified delivery manifest requires campaign_state JSON-comparable payload"
        ) from exc
    if not payload_matches_disk:
        raise ValueError(
            "certified delivery manifest requires campaign_state to match disk checkpoint authority"
        )


def _validate_certified_manifest_output_path(
    *,
    project_root: Path,
    output_path: Path,
    payload: Mapping[str, Any],
) -> None:
    """Keep certified manifest writes on the canonical in-project delivery surface."""

    if payload.get("best_certified_result") is None:
        return
    project_root = Path(project_root).resolve()
    raw_output_path = Path(output_path)
    if not raw_output_path.is_absolute():
        raw_output_path = project_root / raw_output_path
    target_path = raw_output_path.resolve()
    canonical_path = delivery_manifest_output_path(project_root).resolve()
    try:
        target_path.relative_to(project_root)
        raw_output_path.parent.resolve().relative_to(project_root)
    except ValueError as exc:
        raise ValueError(
            "certified delivery manifest requires canonical output path inside project"
        ) from exc
    if target_path != canonical_path:
        raise ValueError(
            "certified delivery manifest requires canonical output path for best_certified_result"
        )
    if raw_output_path.exists() and not _is_regular_file(raw_output_path):
        raise ValueError(
            "certified delivery manifest requires regular canonical delivery manifest output"
        )


def _artifact_entry(project_root: Path, path: Path) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "path": path.relative_to(project_root).as_posix(),
        "exists": bool(path.exists()),
        "regular_file": bool(_is_regular_file(path)),
    }
    if entry["regular_file"]:
        try:
            stat = path.stat()
            entry["size_bytes"] = int(stat.st_size)
            entry["sha256"] = _file_sha256(path)
        except OSError as exc:
            entry["sha256_error"] = exc.__class__.__name__
    return entry


def _is_regular_file(path: Path) -> bool:
    return bool(path.is_file() and not _path_has_symlink_component(path))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_delivery_artifacts_match_campaign(
    *,
    project_root: Path,
    campaign_state: Mapping[str, Any],
    final_solution_path: Optional[Path] = None,
    optimal_blueprint_path: Optional[Path] = None,
) -> None:
    final_result = campaign_state.get("final_result")
    if not isinstance(final_result, Mapping):
        raise ValueError("certified delivery manifest requires terminal final_result evidence")

    final_solution_path = final_solution_path or (
        project_root / "data" / "solutions" / "final_solution.json"
    )
    optimal_blueprint_path = optimal_blueprint_path or blueprint_output_path(project_root)
    missing_delivery_artifacts: list[str] = []
    if not _is_regular_file(final_solution_path):
        missing_delivery_artifacts.append("final_solution")
    if not _is_regular_file(optimal_blueprint_path):
        missing_delivery_artifacts.append("optimal_blueprint")
    if missing_delivery_artifacts:
        raise ValueError(
            "certified delivery manifest requires exported delivery artifacts before "
            "best_certified_result: " + ",".join(missing_delivery_artifacts)
        )

    final_solution_payload = _load_json_mapping(final_solution_path, "final_solution")
    if not _json_equivalent(final_solution_payload, final_result):
        raise ValueError(
            "certified delivery manifest requires final_solution artifact to match terminal final_result"
        )

    _validate_optimal_blueprint_matches_final_result(
        project_root=project_root,
        optimal_blueprint_path=optimal_blueprint_path,
        final_result=final_result,
    )


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key, value in pairs:
        if key in payload:
            raise ValueError(f"duplicate JSON key: {key}")
        payload[key] = value
    return payload


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _loads_strict_json_object(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_json_constant,
    )


def _load_json_mapping(path: Path, label: str) -> Dict[str, Any]:
    try:
        payload = _loads_strict_json_object(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"certified delivery manifest requires strict readable JSON {label} artifact") from exc
    if not isinstance(payload, Mapping):
        raise ValueError(f"certified delivery manifest requires JSON mapping {label} artifact")
    return dict(payload)


def _json_equivalent(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return json.dumps(left, sort_keys=True, separators=(",", ":"), ensure_ascii=False) == json.dumps(
        right,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _validate_optimal_blueprint_matches_final_result(
    *,
    project_root: Path,
    optimal_blueprint_path: Path,
    final_result: Mapping[str, Any],
) -> None:
    raw_blueprint_payload = _load_json_mapping(optimal_blueprint_path, "optimal_blueprint")
    try:
        blueprint_payload = load_canonical_blueprint(optimal_blueprint_path)
    except Exception as exc:
        raise ValueError(
            "certified delivery manifest requires optimal_blueprint artifact to match terminal final_result"
        ) from exc

    if _blueprint_ghost_rect_summary(blueprint_payload) != _ghost_rect_summary(
        final_result.get("ghost_rect")
    ):
        raise ValueError(
            "certified delivery manifest requires optimal_blueprint artifact to match terminal final_result"
        )

    expected_solution = final_result.get("placement_solution")
    # V79: a terminal certified final_result whose placement_solution is not
    # instance-shaped cannot be reverse-validated against facility_pools, so the
    # publication must fail closed instead of silently skipping the deep check.
    if not isinstance(expected_solution, Mapping) or not _looks_like_instance_placement_solution(
        expected_solution
    ):
        raise ValueError(
            "certified delivery manifest requires an instance-shaped placement_solution "
            "for terminal final_result"
        )

    try:
        facility_pools = load_candidate_placements(
            project_root / "data" / "preprocessed" / "candidate_placements.json"
        )
        expected_blueprint = build_blueprint_payload_from_certified_result(
            result=final_result,
            facility_pools=facility_pools,
            export_timestamp=_blueprint_export_timestamp(blueprint_payload),
        )
        recovered_result = recover_legacy_render_payload_from_blueprint(
            blueprint_payload=blueprint_payload,
            facility_pools=facility_pools,
        )
    except Exception as exc:
        raise ValueError(
            "certified delivery manifest requires optimal_blueprint artifact to match terminal final_result"
        ) from exc

    if not _json_equivalent(raw_blueprint_payload, expected_blueprint):
        raise ValueError(
            "certified delivery manifest requires optimal_blueprint artifact to match terminal final_result"
        )

    if not _blueprint_solution_matches_final_result(
        recovered_result.get("placement_solution"),
        expected_solution,
    ):
        raise ValueError(
            "certified delivery manifest requires optimal_blueprint artifact to match terminal final_result"
        )


def _ghost_rect_summary(raw_rect: Any) -> Optional[Dict[str, int]]:
    if not isinstance(raw_rect, Mapping):
        return None
    try:
        w = int(raw_rect.get("w"))
        h = int(raw_rect.get("h"))
        area = int(raw_rect.get("area", w * h))
    except Exception:
        return None
    if "anchor_x" not in raw_rect or "anchor_y" not in raw_rect:
        return None
    try:
        anchor_x = int(raw_rect.get("anchor_x"))
        anchor_y = int(raw_rect.get("anchor_y"))
    except Exception:
        return None
    if anchor_x < 0 or anchor_y < 0:
        return None
    return {"w": w, "h": h, "area": area, "anchor_x": anchor_x, "anchor_y": anchor_y}


def _blueprint_export_timestamp(blueprint_payload: Mapping[str, Any]) -> Optional[str]:
    metadata = blueprint_payload.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    export_timestamp = metadata.get("export_timestamp")
    if export_timestamp is None:
        return None
    return str(export_timestamp)


def _blueprint_ghost_rect_summary(blueprint_payload: Mapping[str, Any]) -> Optional[Dict[str, int]]:
    objective = blueprint_payload.get("objective_achieved")
    if not isinstance(objective, Mapping):
        return None
    empty_rect = objective.get("empty_rect")
    if not isinstance(empty_rect, Mapping):
        return None
    try:
        w = int(empty_rect.get("w"))
        h = int(empty_rect.get("h"))
        raw_score = float(empty_rect.get("score", w * h))
    except Exception:
        return None
    if not math.isfinite(raw_score) or not raw_score.is_integer():
        return None
    area = int(raw_score)
    if area != w * h:
        return None
    if "anchor_x" not in empty_rect or "anchor_y" not in empty_rect:
        return None
    try:
        anchor_x = int(empty_rect.get("anchor_x"))
        anchor_y = int(empty_rect.get("anchor_y"))
    except Exception:
        return None
    if anchor_x < 0 or anchor_y < 0:
        return None
    return {"w": w, "h": h, "area": area, "anchor_x": anchor_x, "anchor_y": anchor_y}


_BLUEPRINT_COMPARABLE_SOLUTION_FIELDS = frozenset(
    {"facility_type", "pose_idx", "pose_id", "anchor", "orientation", "port_mode"}
)
_BLUEPRINT_UNREPRESENTED_SOLUTION_FIELDS = frozenset(
    {"instance_id", "operation_type", "is_mandatory", "bound_type", "solve_mode"}
)


def _blueprint_solution_matches_final_result(
    recovered_solution: Any,
    expected_solution: Any,
) -> bool:
    if not isinstance(recovered_solution, Mapping) or not isinstance(expected_solution, Mapping):
        return False
    if not _looks_like_instance_placement_solution(expected_solution):
        return True
    if set(recovered_solution.keys()) != set(expected_solution.keys()):
        return False
    for instance_id, expected_entry in expected_solution.items():
        recovered_entry = recovered_solution.get(instance_id)
        if not isinstance(recovered_entry, Mapping) or not isinstance(expected_entry, Mapping):
            return False
        expected_fields = set(str(field) for field in expected_entry.keys())
        unknown_fields = expected_fields - (
            _BLUEPRINT_COMPARABLE_SOLUTION_FIELDS | _BLUEPRINT_UNREPRESENTED_SOLUTION_FIELDS
        )
        if unknown_fields:
            return False
        comparable_fields = expected_fields & _BLUEPRINT_COMPARABLE_SOLUTION_FIELDS
        if not comparable_fields:
            return False
        for field in comparable_fields:
            if field not in recovered_entry:
                return False
            if not _json_value_equivalent(recovered_entry.get(field), expected_entry.get(field)):
                return False
    return True


def _looks_like_instance_placement_solution(solution: Mapping[str, Any]) -> bool:
    for value in solution.values():
        if not isinstance(value, Mapping):
            return False
        if not any(field in value for field in ("facility_type", "pose_idx", "pose_id", "anchor")):
            return False
    return True


def _json_value_equivalent(left: Any, right: Any) -> bool:
    return json.dumps(left, sort_keys=True, separators=(",", ":"), ensure_ascii=False) == json.dumps(
        right,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _build_best_certified_result_payload(
    *,
    project_root: Path,
    campaign_state: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    if str(campaign_state.get("declare_mode", "strict")) != "strict":
        return None
    if not has_valid_terminal_full_frontier_certified_evidence_for_project(
        campaign_state,
        project_root=project_root,
    ):
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
            "anchor_x": int(ghost_rect.get("anchor_x")),
            "anchor_y": int(ghost_rect.get("anchor_y")),
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
