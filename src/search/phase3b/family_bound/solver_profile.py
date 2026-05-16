from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

FAMILY_BOUND_SOLVER_PROFILE_SOURCE = "phase3b_family_bound_solver_profile_v1"
FORCED_ANCHOR_MODEL_SLICE_SOURCE = "phase3b_forced_anchor_model_slice_diagnostic_v1"
FAMILY_BOUND_SEMANTIC_AUDIT_SOURCE = "phase3b_family_bound_semantic_audit_v1"

DEFAULT_TARGET_FAMILY_SLICE_PATH = Path(
    ".artifacts/phase3b_forced_anchor_model_slice_67x13_family009_protocol/"
    "forced_anchor_model_slice_67x13_anchor119_family009_protocol.json"
)
DEFAULT_FAMILY_BOUND_SEMANTIC_AUDIT_PATH = Path(
    ".artifacts/phase3b_family_bound_semantic_audit/family_bound_semantic_audit.json"
)


def build_phase3b_family_bound_solver_profile(
    project_root: Path,
    *,
    target_family_slice_path: Optional[Path] = None,
    family_bound_semantic_audit_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    slice_path = _resolve_path(
        project_root,
        target_family_slice_path
        if target_family_slice_path is not None
        else DEFAULT_TARGET_FAMILY_SLICE_PATH,
    )
    semantic_path = _resolve_path(
        project_root,
        family_bound_semantic_audit_path
        if family_bound_semantic_audit_path is not None
        else DEFAULT_FAMILY_BOUND_SEMANTIC_AUDIT_PATH,
    )
    slice_report, slice_error = _load_json_mapping(slice_path)
    semantic_report, semantic_error = _load_json_mapping(semantic_path)
    profile = _slice_profile(slice_report, slice_error)
    semantic = _semantic_evidence(semantic_report, semantic_error)
    comparison = _comparison(profile, semantic)
    classification = _classification(comparison, semantic)
    checks = _checks(profile, semantic, comparison)
    return {
        "metadata": {
            "source": FAMILY_BOUND_SOLVER_PROFILE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "solver_profile_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "target_family_slice": _display_path(project_root, slice_path),
            "family_bound_semantic_audit": _display_path(project_root, semantic_path),
        },
        "candidate": {"key": profile.get("candidate_key") or semantic.get("candidate_key")},
        "profile": profile,
        "semantic_audit": semantic,
        "comparison": comparison,
        "classification": classification,
        "recommendation": _recommendation(classification, comparison),
        "checks": checks,
    }


def render_phase3b_family_bound_solver_profile_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    comparison = _mapping(report.get("comparison"))
    profile = _mapping(report.get("profile"))
    lines = [
        "# Phase 3B Family Bound Solver Profile",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: solver_profile_not_proof_source",
        f"- Classification: {report.get('classification')}",
        f"- Wall speedup: {comparison.get('wall_time_speedup')}",
        f"- Deterministic speedup: {comparison.get('deterministic_time_speedup')}",
        f"- Recommendation: {report.get('recommendation')}",
        "",
        "| Variant | Status | Wall | Deterministic | Branches | Conflicts | Count Value | Removed Bounds |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in list(profile.get("entries", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("variant")),
                        _markdown_cell(entry.get("status")),
                        _markdown_cell(entry.get("wall_time")),
                        _markdown_cell(entry.get("deterministic_time")),
                        _markdown_cell(entry.get("branches")),
                        _markdown_cell(entry.get("conflicts")),
                        _markdown_cell(entry.get("relaxed_power_family_count_value")),
                        _markdown_cell(entry.get("removed_constraint_count")),
                    ]
                )
                + " |"
            )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(check.get("check_id")),
                        _markdown_cell(check.get("status")),
                        _markdown_cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_family_bound_solver_profile_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    comparison = _mapping(report.get("comparison"))
    lines = [
        "Phase 3B family bound solver profile",
        f"candidate={candidate.get('key')}",
        "diagnostic_semantics=solver_profile_not_proof_source",
        f"classification={report.get('classification')}",
        f"wall_time_speedup={comparison.get('wall_time_speedup')}",
        f"deterministic_time_speedup={comparison.get('deterministic_time_speedup')}",
        f"recommendation={report.get('recommendation')}",
    ]
    for entry in list(_mapping(report.get("profile")).get("entries", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "entry "
                f"variant={entry.get('variant')} "
                f"status={entry.get('status')} "
                f"wall={entry.get('wall_time')} "
                f"deterministic={entry.get('deterministic_time')} "
                f"branches={entry.get('branches')} "
                f"conflicts={entry.get('conflicts')} "
                f"count_value={entry.get('relaxed_power_family_count_value')} "
                f"removed={entry.get('removed_constraint_count')}"
            )
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _slice_profile(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error, "entries": []}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    matrix = _mapping(payload.get("slice_matrix"))
    entries = [
        _entry_profile(entry)
        for entry in list(matrix.get("entries", []))
        if isinstance(entry, Mapping)
        and str(entry.get("variant"))
        in {
            "base",
            "target_power_family_bound_relaxed",
            "target_power_family_bound_relaxed_protocol_boxes_inactive",
        }
    ]
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FORCED_ANCHOR_MODEL_SLICE_SOURCE,
        "candidate_key": candidate.get("key"),
        "campaign_state_unchanged": bool(payload.get("campaign_state_unchanged", False)),
        "entries": entries,
        "by_variant": {str(entry.get("variant")): entry for entry in entries},
    }


def _entry_profile(entry: Mapping[str, Any]) -> Dict[str, Any]:
    parsed = _mapping(entry.get("response_stats_parsed"))
    return {
        "variant": entry.get("variant"),
        "status": entry.get("status"),
        "wall_time": _float_or_none(entry.get("wall_time")),
        "user_time": _float_or_none(entry.get("user_time")),
        "deterministic_time": _float_or_none(parsed.get("deterministic_time")),
        "branches": int(entry.get("branches", 0)),
        "conflicts": int(entry.get("conflicts", 0)),
        "removed_constraint_count": int(
            entry.get("relaxed_conditioned_power_family_bound_constraints_removed", 0)
        ),
        "relaxed_power_family": entry.get("relaxed_power_family"),
        "relaxed_power_family_count_value": entry.get(
            "relaxed_power_family_count_value"
        ),
        "time_limit_seconds": _float_or_none(entry.get("time_limit_seconds")),
        "worker_count": int(entry.get("worker_count", 0)),
        "response_status": parsed.get("status"),
        "response_stats_available": bool(parsed),
    }


def _semantic_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    relaxed = _mapping(payload.get("target_family_slice"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FAMILY_BOUND_SEMANTIC_AUDIT_SOURCE,
        "classification": payload.get("classification"),
        "relaxed_family_bound_violation": relaxed.get(
            "relaxed_family_bound_violation"
        ),
    }


def _comparison(profile: Mapping[str, Any], semantic: Mapping[str, Any]) -> Dict[str, Any]:
    by_variant = _mapping(profile.get("by_variant"))
    base = _mapping(by_variant.get("base"))
    relaxed = _mapping(by_variant.get("target_power_family_bound_relaxed"))
    protocol_relaxed = _mapping(
        by_variant.get("target_power_family_bound_relaxed_protocol_boxes_inactive")
    )
    return {
        "base_status": base.get("status"),
        "relaxed_status": relaxed.get("status"),
        "protocol_relaxed_status": protocol_relaxed.get("status"),
        "base_wall_time": base.get("wall_time"),
        "relaxed_wall_time": relaxed.get("wall_time"),
        "wall_time_speedup": _ratio(base.get("wall_time"), relaxed.get("wall_time")),
        "base_deterministic_time": base.get("deterministic_time"),
        "relaxed_deterministic_time": relaxed.get("deterministic_time"),
        "deterministic_time_speedup": _ratio(
            base.get("deterministic_time"),
            relaxed.get("deterministic_time"),
        ),
        "base_branches": base.get("branches"),
        "relaxed_branches": relaxed.get("branches"),
        "base_conflicts": base.get("conflicts"),
        "relaxed_conflicts": relaxed.get("conflicts"),
        "removed_constraint_count": relaxed.get("removed_constraint_count"),
        "relaxed_family_bound_violation": semantic.get(
            "relaxed_family_bound_violation"
        ),
    }


def _classification(comparison: Mapping[str, Any], semantic: Mapping[str, Any]) -> str:
    if comparison.get("base_status") == "UNKNOWN" and comparison.get("relaxed_status") in {
        "OPTIMAL",
        "FEASIBLE",
    }:
        violation = _float_or_none(semantic.get("relaxed_family_bound_violation"))
        if violation is not None and violation <= 0:
            return "bound_present_unknown_bound_absent_terminal_without_violation"
        return "bound_present_unknown_bound_absent_terminal"
    return "solver_profile_inconclusive"


def _recommendation(classification: str, comparison: Mapping[str, Any]) -> str:
    if classification == "bound_present_unknown_bound_absent_terminal_without_violation":
        return (
            "The bound-present slice times out as UNKNOWN without branching, while "
            "removing one conditioned family bound solves quickly and the relaxed "
            "solution does not violate the bound. Treat this as a presolve/search "
            "sensitivity; next test bound-present search parameters or a redundant "
            "but solver-friendlier formulation."
        )
    if classification == "bound_present_unknown_bound_absent_terminal":
        return (
            "Removing the target bound makes the slice terminal; inspect the relaxed "
            "solution and semantic audit before any promotion."
        )
    return "The profile is inconclusive; rerun base/relaxed slices with matched parameters."


def _checks(
    profile: Mapping[str, Any],
    semantic: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> list[Dict[str, str]]:
    return [
        _check(
            "target_family_slice_present",
            "pass" if bool(profile.get("present", False)) else "fail",
            "target family slice loaded"
            if bool(profile.get("present", False))
            else str(profile.get("load_error")),
        ),
        _check(
            "semantic_audit_present",
            "pass" if bool(semantic.get("present", False)) else "fail",
            "semantic audit loaded"
            if bool(semantic.get("present", False))
            else str(semantic.get("load_error")),
        ),
        _check(
            "base_unknown",
            "pass" if comparison.get("base_status") == "UNKNOWN" else "fail",
            f"base_status={comparison.get('base_status')}",
        ),
        _check(
            "relaxed_terminal",
            "pass"
            if comparison.get("relaxed_status") in {"OPTIMAL", "FEASIBLE"}
            else "fail",
            f"relaxed_status={comparison.get('relaxed_status')}",
        ),
        _check(
            "removed_one_conditioned_bound",
            "pass" if int(comparison.get("removed_constraint_count") or 0) == 1 else "fail",
            f"removed={comparison.get('removed_constraint_count')}",
        ),
        _check(
            "relaxed_solution_does_not_violate_bound",
            "pass"
            if _float_or_none(comparison.get("relaxed_family_bound_violation")) is not None
            and float(comparison.get("relaxed_family_bound_violation")) <= 0
            else "fail",
            f"violation={comparison.get('relaxed_family_bound_violation')}",
        ),
    ]


def _ratio(numerator: Any, denominator: Any) -> Optional[float]:
    numerator_value = _float_or_none(numerator)
    denominator_value = _float_or_none(denominator)
    if numerator_value is None or denominator_value is None or denominator_value <= 0:
        return None
    return float(numerator_value / denominator_value)


def _float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    if not path.exists():
        return None, None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"json_load_error:{type(exc).__name__}:{exc}"
    if not isinstance(payload, Mapping):
        return None, "json_payload_not_object"
    return dict(payload), None


def _resolve_path(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
