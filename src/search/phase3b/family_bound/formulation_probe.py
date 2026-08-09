from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

FAMILY_BOUND_FORMULATION_PROBE_SOURCE = "phase3b_family_bound_formulation_probe_v1"
FORCED_ANCHOR_MODEL_SLICE_SOURCE = "phase3b_forced_anchor_model_slice_diagnostic_v1"
FAMILY_BOUND_SEMANTIC_AUDIT_SOURCE = "phase3b_family_bound_semantic_audit_v1"

DEFAULT_DIRECT_BOUND_SLICE_PATH = Path(
    ".artifacts/phase3b_forced_anchor_model_slice_67x13_family009_direct_bound/"
    "forced_anchor_model_slice_67x13_anchor119_family009_direct_bound.json"
)
DEFAULT_ENFORCED_FORMULATION_SLICE_PATH = Path(
    ".artifacts/phase3b_forced_anchor_model_slice_67x13_family009_enforced_formulation/"
    "forced_anchor_model_slice_67x13_anchor119_enforced_formulation.json"
)
DEFAULT_ALL_FAMILY_DIRECT_BOUND_SLICE_PATH = Path(
    ".artifacts/phase3b_forced_anchor_model_slice_67x13_all_family_direct_bounds/"
    "forced_anchor_model_slice_67x13_anchor119_all_family_direct_bounds.json"
)
DEFAULT_FAMILY_BOUND_SEMANTIC_AUDIT_PATH = Path(
    ".artifacts/phase3b_family_bound_semantic_audit/family_bound_semantic_audit.json"
)


def build_phase3b_family_bound_formulation_probe(
    project_root: Path,
    *,
    direct_bound_slice_path: Optional[Path] = None,
    enforced_formulation_slice_path: Optional[Path] = None,
    all_family_direct_bound_slice_path: Optional[Path] = None,
    family_bound_semantic_audit_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    slice_path = _resolve_path(
        project_root,
        direct_bound_slice_path
        if direct_bound_slice_path is not None
        else DEFAULT_DIRECT_BOUND_SLICE_PATH,
    )
    semantic_path = _resolve_path(
        project_root,
        family_bound_semantic_audit_path
        if family_bound_semantic_audit_path is not None
        else DEFAULT_FAMILY_BOUND_SEMANTIC_AUDIT_PATH,
    )
    enforced_path = _resolve_path(
        project_root,
        enforced_formulation_slice_path
        if enforced_formulation_slice_path is not None
        else DEFAULT_ENFORCED_FORMULATION_SLICE_PATH,
    )
    all_family_path = _resolve_path(
        project_root,
        all_family_direct_bound_slice_path
        if all_family_direct_bound_slice_path is not None
        else DEFAULT_ALL_FAMILY_DIRECT_BOUND_SLICE_PATH,
    )
    slice_report, slice_error = _load_json_mapping(slice_path)
    enforced_report, enforced_error = _load_json_mapping(enforced_path)
    all_family_report, all_family_error = _load_json_mapping(all_family_path)
    semantic_report, semantic_error = _load_json_mapping(semantic_path)
    direct = _direct_slice_evidence(slice_report, slice_error)
    enforced = _enforced_slice_evidence(enforced_report, enforced_error)
    all_family = _all_family_direct_slice_evidence(all_family_report, all_family_error)
    semantic = _semantic_evidence(semantic_report, semantic_error)
    comparison = _comparison(direct, enforced, all_family, semantic)
    classification = _classification(comparison)
    checks = _checks(direct, enforced, all_family, semantic, comparison)
    return {
        "metadata": {
            "source": FAMILY_BOUND_FORMULATION_PROBE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "formulation_probe_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "direct_bound_slice": _display_path(project_root, slice_path),
            "enforced_formulation_slice": _display_path(project_root, enforced_path),
            "all_family_direct_bound_slice": _display_path(project_root, all_family_path),
            "family_bound_semantic_audit": _display_path(project_root, semantic_path),
        },
        "candidate": {"key": direct.get("candidate_key") or semantic.get("candidate_key")},
        "direct_bound_slice": direct,
        "enforced_formulation_slice": enforced,
        "all_family_direct_bound_slice": all_family,
        "semantic_audit": semantic,
        "comparison": comparison,
        "classification": classification,
        "recommendation": _recommendation(classification),
        "checks": checks,
    }


def render_phase3b_family_bound_formulation_probe_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    comparison = _mapping(report.get("comparison"))
    direct = _mapping(report.get("direct_bound_slice"))
    lines = [
        "# Phase 3B Family Bound Formulation Probe",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: formulation_probe_not_proof_source",
        f"- Classification: {report.get('classification')}",
        f"- Direct bound status: {comparison.get('direct_status')}",
        f"- Enforced formulation status: {comparison.get('enforced_status')}",
        f"- All-family direct status: {comparison.get('all_family_status')}",
        f"- Direct bound value: {direct.get('replacement_conditioned_power_family_bound')}",
        f"- Direct count value: {direct.get('relaxed_power_family_count_value')}",
        f"- Wall speedup: {comparison.get('wall_time_speedup')}",
        f"- Recommendation: {report.get('recommendation')}",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
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


def render_phase3b_family_bound_formulation_probe_text(report: Mapping[str, Any]) -> str:
    comparison = _mapping(report.get("comparison"))
    direct = _mapping(report.get("direct_bound_slice"))
    lines = [
        "Phase 3B family bound formulation probe",
        f"classification={report.get('classification')}",
        "diagnostic_semantics=formulation_probe_not_proof_source",
        f"direct_status={comparison.get('direct_status')}",
        f"enforced_status={comparison.get('enforced_status')}",
        f"all_family_status={comparison.get('all_family_status')}",
        f"direct_bound={direct.get('replacement_conditioned_power_family_bound')}",
        f"direct_count={direct.get('relaxed_power_family_count_value')}",
        f"wall_time_speedup={comparison.get('wall_time_speedup')}",
        f"recommendation={report.get('recommendation')}",
    ]
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _direct_slice_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    matrix = _mapping(payload.get("slice_matrix"))
    entries = [entry for entry in list(matrix.get("entries", [])) if isinstance(entry, Mapping)]
    base = _entry_by_variant(entries, "base")
    direct = _entry_by_variant(entries, "target_power_family_bound_direct_after_force")
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FORCED_ANCHOR_MODEL_SLICE_SOURCE,
        "candidate_key": candidate.get("key"),
        "campaign_state_unchanged": bool(payload.get("campaign_state_unchanged", False)),
        "base_status": base.get("status"),
        "base_wall_time": base.get("wall_time"),
        "base_deterministic_time": _mapping(base.get("response_stats_parsed")).get(
            "deterministic_time"
        ),
        "direct_variant_present": bool(direct),
        "direct_status": direct.get("status"),
        "direct_wall_time": direct.get("wall_time"),
        "direct_deterministic_time": _mapping(direct.get("response_stats_parsed")).get(
            "deterministic_time"
        ),
        "replacement_bound_mode": direct.get("replacement_bound_mode"),
        "replacement_conditioned_power_family_bound": direct.get(
            "replacement_conditioned_power_family_bound"
        ),
        "relaxed_power_family_count_value": direct.get(
            "relaxed_power_family_count_value"
        ),
        "removed_constraint_count": direct.get(
            "relaxed_conditioned_power_family_bound_constraints_removed"
        ),
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


def _enforced_slice_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    matrix = _mapping(payload.get("slice_matrix"))
    entries = [entry for entry in list(matrix.get("entries", [])) if isinstance(entry, Mapping)]
    base = _entry_by_variant(entries, "base")
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FORCED_ANCHOR_MODEL_SLICE_SOURCE,
        "candidate_key": candidate.get("key"),
        "campaign_state_unchanged": bool(payload.get("campaign_state_unchanged", False)),
        "status": base.get("status"),
        "wall_time": base.get("wall_time"),
        "deterministic_time": _mapping(base.get("response_stats_parsed")).get(
            "deterministic_time"
        ),
        "branches": base.get("branches"),
        "conflicts": base.get("conflicts"),
    }


def _all_family_direct_slice_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    matrix = _mapping(payload.get("slice_matrix"))
    entries = [entry for entry in list(matrix.get("entries", [])) if isinstance(entry, Mapping)]
    entry = _entry_by_variant(entries, "all_conditioned_family_bounds_direct_after_force")
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FORCED_ANCHOR_MODEL_SLICE_SOURCE,
        "candidate_key": candidate.get("key"),
        "campaign_state_unchanged": bool(payload.get("campaign_state_unchanged", False)),
        "status": entry.get("status"),
        "wall_time": entry.get("wall_time"),
        "replacement_count": entry.get("direct_power_family_bound_replacement_count"),
    }


def _comparison(
    direct: Mapping[str, Any],
    enforced: Mapping[str, Any],
    all_family: Mapping[str, Any],
    semantic: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "base_status": direct.get("base_status"),
        "direct_status": direct.get("direct_status"),
        "enforced_status": enforced.get("status"),
        "all_family_status": all_family.get("status"),
        "base_wall_time": direct.get("base_wall_time"),
        "direct_wall_time": direct.get("direct_wall_time"),
        "enforced_wall_time": enforced.get("wall_time"),
        "all_family_wall_time": all_family.get("wall_time"),
        "wall_time_speedup": _ratio(direct.get("base_wall_time"), direct.get("direct_wall_time")),
        "base_deterministic_time": direct.get("base_deterministic_time"),
        "direct_deterministic_time": direct.get("direct_deterministic_time"),
        "enforced_deterministic_time": enforced.get("deterministic_time"),
        "deterministic_time_speedup": _ratio(
            direct.get("base_deterministic_time"),
            direct.get("direct_deterministic_time"),
        ),
        "removed_constraint_count": direct.get("removed_constraint_count"),
        "direct_bound_value": direct.get("replacement_conditioned_power_family_bound"),
        "direct_count_value": direct.get("relaxed_power_family_count_value"),
        "all_family_replacement_count": all_family.get("replacement_count"),
        "relaxed_family_bound_violation": semantic.get(
            "relaxed_family_bound_violation"
        ),
    }


def _classification(comparison: Mapping[str, Any]) -> str:
    if (
        comparison.get("base_status") == "UNKNOWN"
        and comparison.get("direct_status") == "INFEASIBLE"
        and int(comparison.get("removed_constraint_count") or 0) == 1
        and comparison.get("direct_bound_value") is not None
    ):
        return "direct_bound_replacement_infeasible"
    if (
        comparison.get("base_status") == "UNKNOWN"
        and comparison.get("direct_status") in {"OPTIMAL", "FEASIBLE"}
        and int(comparison.get("removed_constraint_count") or 0) == 1
        and comparison.get("direct_bound_value") is not None
    ):
        if (
            comparison.get("enforced_status") == "UNKNOWN"
            and comparison.get("all_family_status") == "INFEASIBLE"
        ):
            return "target_direct_terminal_enforced_unknown_all_family_direct_infeasible"
        if comparison.get("enforced_status") == "UNKNOWN":
            return "direct_after_force_terminal_enforced_formulation_still_unknown"
        return "direct_bound_replacement_terminal_without_relaxing_semantics"
    return "formulation_probe_inconclusive"


def _recommendation(classification: str) -> str:
    if classification == "direct_bound_replacement_terminal_without_relaxing_semantics":
        return (
            "A diagnostic forced-anchor clone becomes terminal when the original "
            "reified family bound is replaced by the equivalent direct bound after "
            "forcing the anchor. Prototype a guarded solver-friendly formulation "
            "for this constraint family before any runtime or proof promotion."
        )
    if classification == "direct_after_force_terminal_enforced_formulation_still_unknown":
        return (
            "The direct-after-force diagnostic is terminal, but the general guarded "
            "enforced formulation remains UNKNOWN. This points to an anchor-specialized "
            "solve-time direct-bound injection or a deeper formulation change, not "
            "a ready runtime formulation switch."
        )
    if classification == "target_direct_terminal_enforced_unknown_all_family_direct_infeasible":
        return (
            "The target-family direct-after-force diagnostic is terminal, while the "
            "general enforced formulation remains UNKNOWN and replacing all conditioned "
            "family bounds is INFEASIBLE. This narrows the experiment to a target-family "
            "anchor-specialized injection, not a broad all-family substitution."
        )
    if classification == "direct_bound_replacement_infeasible":
        return (
            "The refreshed target-family direct-bound replacement is INFEASIBLE, "
            "so older terminal direct-bound evidence must be treated as stale. Keep "
            "anchor-specialized injection blocked and audit the model-slice mutation "
            "path before any B5A rerun."
        )
    return "Formulation probe is inconclusive; rerun the direct-bound slice before changing runtime behavior."


def _checks(
    direct: Mapping[str, Any],
    enforced: Mapping[str, Any],
    all_family: Mapping[str, Any],
    semantic: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> list[Dict[str, str]]:
    count_value = _optional_int(comparison.get("direct_count_value"))
    bound_value = _optional_int(comparison.get("direct_bound_value"))
    return [
        _check(
            "direct_bound_slice_present",
            "pass" if bool(direct.get("present", False)) else "fail",
            "direct-bound slice loaded"
            if bool(direct.get("present", False))
            else str(direct.get("load_error")),
        ),
        _check(
            "semantic_audit_present",
            "pass" if bool(semantic.get("present", False)) else "fail",
            "semantic audit loaded"
            if bool(semantic.get("present", False))
            else str(semantic.get("load_error")),
        ),
        _check(
            "enforced_formulation_slice_present",
            "pass" if bool(enforced.get("present", False)) else "skipped",
            f"status={enforced.get('status')}"
            if bool(enforced.get("present", False))
            else "enforced formulation slice not present",
        ),
        _check(
            "all_family_direct_slice_present",
            "pass" if bool(all_family.get("present", False)) else "skipped",
            f"status={all_family.get('status')} replacement_count={all_family.get('replacement_count')}"
            if bool(all_family.get("present", False))
            else "all-family direct-bound slice not present",
        ),
        _check(
            "base_unknown",
            "pass" if comparison.get("base_status") == "UNKNOWN" else "fail",
            f"base_status={comparison.get('base_status')}",
        ),
        _check(
            "direct_bound_terminal",
            "pass"
            if comparison.get("direct_status") in {"OPTIMAL", "FEASIBLE"}
            else "fail",
            f"direct_status={comparison.get('direct_status')}",
        ),
        _check(
            "direct_bound_value_present",
            "pass" if bound_value is not None else "fail",
            f"direct_bound={bound_value}",
        ),
        _check(
            "direct_solution_respects_bound",
            "pass"
            if count_value is not None and bound_value is not None and count_value <= bound_value
            else "fail",
            f"count={count_value} bound={bound_value}",
        ),
    ]


def _entry_by_variant(entries: list[Mapping[str, Any]], variant: str) -> Mapping[str, Any]:
    for entry in entries:
        if str(entry.get("variant")) == str(variant):
            return entry
    return {}


def _ratio(numerator: Any, denominator: Any) -> Optional[float]:
    numerator_value = _optional_float(numerator)
    denominator_value = _optional_float(denominator)
    if numerator_value is None or denominator_value is None or denominator_value <= 0:
        return None
    return float(numerator_value / denominator_value)


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
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
