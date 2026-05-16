from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

FAMILY_BOUND_SEMANTIC_AUDIT_SOURCE = "phase3b_family_bound_semantic_audit_v1"
FAMILY_BOUND_AUDIT_SOURCE = "phase3b_family_bound_audit_v1"
FORCED_ANCHOR_MODEL_SLICE_SOURCE = "phase3b_forced_anchor_model_slice_diagnostic_v1"

DEFAULT_FAMILY_BOUND_AUDIT_PATH = Path(
    ".artifacts/phase3b_family_bound_audit_67x13_family009/"
    "family_bound_audit_67x13_anchor119_family009.json"
)
DEFAULT_TARGET_FAMILY_SLICE_PATH = Path(
    ".artifacts/phase3b_forced_anchor_model_slice_67x13_family009_protocol/"
    "forced_anchor_model_slice_67x13_anchor119_family009_protocol.json"
)


def build_phase3b_family_bound_semantic_audit(
    project_root: Path,
    *,
    family_bound_audit_path: Optional[Path] = None,
    target_family_slice_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    family_path = _resolve_path(
        project_root,
        family_bound_audit_path
        if family_bound_audit_path is not None
        else DEFAULT_FAMILY_BOUND_AUDIT_PATH,
    )
    slice_path = _resolve_path(
        project_root,
        target_family_slice_path
        if target_family_slice_path is not None
        else DEFAULT_TARGET_FAMILY_SLICE_PATH,
    )
    family_audit, family_error = _load_json_mapping(family_path)
    slice_report, slice_error = _load_json_mapping(slice_path)
    family = _family_evidence(family_audit, family_error)
    relaxed = _relaxed_slice_evidence(slice_report, slice_error)
    classification = _classification(family, relaxed)
    findings = _findings(family, relaxed, classification)
    checks = _checks(family, relaxed)
    return {
        "metadata": {
            "source": FAMILY_BOUND_SEMANTIC_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "artifact_join_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "family_bound_audit": _display_path(project_root, family_path),
            "target_family_slice": _display_path(project_root, slice_path),
        },
        "candidate": {
            "key": family.get("candidate_key") or relaxed.get("candidate_key"),
        },
        "family_bound": family,
        "target_family_slice": relaxed,
        "classification": classification,
        "findings": findings,
        "recommendation": _recommendation(classification),
        "checks": checks,
    }


def render_phase3b_family_bound_semantic_audit_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    family = _mapping(report.get("family_bound"))
    relaxed = _mapping(report.get("target_family_slice"))
    lines = [
        "# Phase 3B Family Bound Semantic Audit",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: artifact_join_not_proof_source",
        f"- Classification: {report.get('classification')}",
        f"- Target family: {family.get('target_power_family')}",
        f"- Derived bound: {family.get('derived_conditioned_upper_bound')}",
        f"- Relaxed count value: {relaxed.get('relaxed_power_family_count_value')}",
        f"- Violation amount: {relaxed.get('relaxed_family_bound_violation')}",
        f"- Recommendation: {report.get('recommendation')}",
        "",
        "## Findings",
        "",
    ]
    findings = [str(item) for item in list(report.get("findings", []))]
    lines.extend(f"- {finding}" for finding in (findings or ["none"]))
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


def render_phase3b_family_bound_semantic_audit_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    family = _mapping(report.get("family_bound"))
    relaxed = _mapping(report.get("target_family_slice"))
    lines = [
        "Phase 3B family bound semantic audit",
        f"candidate={candidate.get('key')}",
        "diagnostic_semantics=artifact_join_not_proof_source",
        f"classification={report.get('classification')}",
        f"target_family={family.get('target_power_family')}",
        f"derived_bound={family.get('derived_conditioned_upper_bound')}",
        f"relaxed_count_value={relaxed.get('relaxed_power_family_count_value')}",
        f"violation_amount={relaxed.get('relaxed_family_bound_violation')}",
        f"recommendation={report.get('recommendation')}",
    ]
    for finding in list(report.get("findings", [])):
        lines.append(f"finding={finding}")
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _family_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    summary = _mapping(payload.get("summary"))
    audits = [entry for entry in list(payload.get("audits", [])) if isinstance(entry, Mapping)]
    first = audits[0] if audits else {}
    derivation = _mapping(first.get("derivation"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FAMILY_BOUND_AUDIT_SOURCE,
        "candidate_key": candidate.get("key"),
        "all_bounds_consistent": bool(summary.get("all_bounds_consistent", False)),
        "anchor_idx": first.get("anchor_idx"),
        "target_power_family": first.get("target_power_family"),
        "family_size": derivation.get("family_size"),
        "blocked_family_pose_count": derivation.get("blocked_family_pose_count"),
        "global_upper_bound": derivation.get("global_upper_bound"),
        "derived_conditioned_upper_bound": derivation.get(
            "derived_conditioned_upper_bound"
        ),
        "bounds_consistent": bool(first.get("bounds_consistent", False)),
    }


def _relaxed_slice_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    matrix = _mapping(payload.get("slice_matrix"))
    entries = [entry for entry in list(matrix.get("entries", [])) if isinstance(entry, Mapping)]
    target = _target_relaxed_entry(entries)
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FORCED_ANCHOR_MODEL_SLICE_SOURCE,
        "candidate_key": candidate.get("key"),
        "campaign_state_unchanged": bool(payload.get("campaign_state_unchanged", False)),
        "diagnostic_findings": [
            str(item) for item in list(matrix.get("diagnostic_findings", []))
        ],
        "target_variant_present": bool(target),
        "target_variant": target.get("variant") if target else None,
        "target_status": target.get("status") if target else None,
        "relaxed_power_family": target.get("relaxed_power_family") if target else None,
        "relaxed_power_family_count_value": target.get(
            "relaxed_power_family_count_value"
        )
        if target
        else None,
        "removed_constraint_count": target.get(
            "relaxed_conditioned_power_family_bound_constraints_removed"
        )
        if target
        else None,
    }


def _target_relaxed_entry(entries: list[Mapping[str, Any]]) -> Mapping[str, Any]:
    for entry in entries:
        if str(entry.get("variant")) == "target_power_family_bound_relaxed":
            return entry
    for entry in entries:
        if str(entry.get("variant")).startswith("target_power_family_bound_relaxed"):
            return entry
    return {}


def _classification(family: Mapping[str, Any], relaxed: Mapping[str, Any]) -> str:
    if not bool(family.get("present", False)) or not bool(relaxed.get("present", False)):
        return "missing_artifacts"
    if not bool(family.get("bounds_consistent", False)):
        return "family_bound_derivation_mismatch"
    if str(relaxed.get("target_status")) not in {"OPTIMAL", "FEASIBLE"}:
        return "relaxation_not_terminal_feasible"
    derived_bound = _optional_int(family.get("derived_conditioned_upper_bound"))
    count_value = _optional_int(relaxed.get("relaxed_power_family_count_value"))
    if derived_bound is None or count_value is None:
        return "relaxed_solution_count_unknown"
    if count_value > derived_bound:
        return "relaxed_solution_violates_conditioned_bound"
    return "solver_sensitivity_without_bound_violation"


def _findings(
    family: Mapping[str, Any],
    relaxed: Mapping[str, Any],
    classification: str,
) -> list[str]:
    findings: list[str] = []
    if bool(family.get("bounds_consistent", False)):
        findings.append("family_bound_derivation_consistent")
    if str(relaxed.get("target_status")) in {"OPTIMAL", "FEASIBLE"}:
        findings.append("target_bound_relaxation_terminal_feasible")
    derived_bound = _optional_int(family.get("derived_conditioned_upper_bound"))
    count_value = _optional_int(relaxed.get("relaxed_power_family_count_value"))
    if derived_bound is not None and count_value is not None:
        violation = int(count_value - derived_bound)
        if violation > 0:
            findings.append("relaxed_solution_exceeds_conditioned_bound")
        else:
            findings.append("relaxed_solution_does_not_exceed_conditioned_bound")
    if classification == "solver_sensitivity_without_bound_violation":
        findings.append("target_bound_is_solver_sensitivity_not_semantic_violation")
    return findings


def _recommendation(classification: str) -> str:
    if classification == "solver_sensitivity_without_bound_violation":
        return (
            "The relaxed feasible slice does not use more target-family poles than "
            "the conditioned bound permits, so the blocker is currently a solver/"
            "propagation sensitivity rather than a demonstrated semantic violation. "
            "Next compare presolve/search behavior with the bound present versus absent."
        )
    if classification == "relaxed_solution_violates_conditioned_bound":
        return (
            "The relaxed feasible slice exceeds the conditioned bound; audit proof "
            "semantics before any promotion."
        )
    if classification == "family_bound_derivation_mismatch":
        return "Repair family-bound derivation mismatch before further diagnosis."
    if classification == "relaxed_solution_count_unknown":
        return "Rerun target relaxed slice with solution count capture enabled."
    return "Rebuild the missing or non-terminal family-bound semantic artifacts."


def _checks(
    family: Mapping[str, Any],
    relaxed: Mapping[str, Any],
) -> list[Dict[str, str]]:
    derived_bound = _optional_int(family.get("derived_conditioned_upper_bound"))
    count_value = _optional_int(relaxed.get("relaxed_power_family_count_value"))
    violation = None if derived_bound is None or count_value is None else count_value - derived_bound
    if isinstance(relaxed, dict):
        relaxed["relaxed_family_bound_violation"] = violation
    return [
        _check(
            "family_bound_audit_present",
            "pass" if bool(family.get("present", False)) else "fail",
            "family-bound audit loaded"
            if bool(family.get("present", False))
            else str(family.get("load_error")),
        ),
        _check(
            "target_family_slice_present",
            "pass" if bool(relaxed.get("present", False)) else "fail",
            "target family slice loaded"
            if bool(relaxed.get("present", False))
            else str(relaxed.get("load_error")),
        ),
        _check(
            "family_bound_derivation_consistent",
            "pass" if bool(family.get("bounds_consistent", False)) else "fail",
            "derivation/domain/proto agree"
            if bool(family.get("bounds_consistent", False))
            else "family bound derivation is not consistent",
        ),
        _check(
            "target_relaxation_terminal_feasible",
            "pass" if str(relaxed.get("target_status")) in {"OPTIMAL", "FEASIBLE"} else "fail",
            f"status={relaxed.get('target_status')}",
        ),
        _check(
            "relaxed_solution_count_captured",
            "pass" if count_value is not None else "fail",
            f"count_value={count_value}",
        ),
        _check(
            "relaxed_solution_violates_bound",
            "fail" if violation is not None and violation > 0 else "pass",
            f"violation={violation}",
        ),
    ]


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
