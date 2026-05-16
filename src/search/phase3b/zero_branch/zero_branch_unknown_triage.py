from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

ZERO_BRANCH_UNKNOWN_TRIAGE_SOURCE = "phase3b_zero_branch_unknown_triage_v1"
FORCED_ANCHOR_SOLVER_MATRIX_SOURCE = "phase3b_forced_anchor_solver_matrix_v1"
FORCED_ANCHOR_MODEL_SLICE_SOURCE = "phase3b_forced_anchor_model_slice_diagnostic_v1"
FAILED_ANCHOR_INVENTORY_SOURCE = "phase3b_failed_anchor_inventory_v1"

DEFAULT_SOLVER_MATRIX_PATH = Path(
    ".artifacts/phase3b_forced_anchor_solver_matrix_67x13_cap112_v3_full/"
    "forced_anchor_solver_matrix_67x13_anchors118_125.json"
)
DEFAULT_MODEL_SLICE_DIR = Path(".artifacts/phase3b_forced_anchor_model_slice_67x13_cap112_v3")
DEFAULT_FAILED_ANCHOR_INVENTORY_PATH = Path(
    ".artifacts/phase3b_failed_anchor_inventory_67x13_cap112_v3/failed_anchor_inventory.json"
)
DEFAULT_POWER_COVERAGE_ANCHOR_DELTA_PATH = Path(
    ".artifacts/phase3b_power_coverage_anchor_delta/power_coverage_anchor_delta.json"
)


def build_phase3b_zero_branch_unknown_triage(
    project_root: Path,
    *,
    solver_matrix_path: Optional[Path] = None,
    model_slice_dir: Optional[Path] = None,
    failed_anchor_inventory_path: Optional[Path] = None,
    power_coverage_anchor_delta_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    matrix_path = _resolve_path(
        project_root,
        solver_matrix_path if solver_matrix_path is not None else DEFAULT_SOLVER_MATRIX_PATH,
    )
    slice_dir = _resolve_path(
        project_root,
        model_slice_dir if model_slice_dir is not None else DEFAULT_MODEL_SLICE_DIR,
    )
    inventory_path = _resolve_path(
        project_root,
        failed_anchor_inventory_path
        if failed_anchor_inventory_path is not None
        else DEFAULT_FAILED_ANCHOR_INVENTORY_PATH,
    )
    power_delta_path = _resolve_path(
        project_root,
        power_coverage_anchor_delta_path
        if power_coverage_anchor_delta_path is not None
        else DEFAULT_POWER_COVERAGE_ANCHOR_DELTA_PATH,
    )
    matrix, matrix_error = _load_json_mapping(matrix_path)
    inventory, inventory_error = _load_json_mapping(inventory_path)
    power_delta, power_delta_error = _load_json_mapping(power_delta_path)
    slice_reports = _load_model_slice_reports(slice_dir)

    matrix_evidence = _matrix_evidence(matrix, matrix_error)
    inventory_evidence = _inventory_evidence(inventory, inventory_error)
    power_delta_evidence = _power_delta_evidence(power_delta, power_delta_error)
    slice_evidence = _slice_evidence(slice_reports)
    findings = _findings(
        matrix_evidence,
        inventory_evidence,
        power_delta_evidence,
        slice_evidence,
    )
    checks = _checks(matrix_evidence, inventory_evidence, power_delta_evidence, slice_evidence)
    return {
        "metadata": {
            "source": ZERO_BRANCH_UNKNOWN_TRIAGE_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
            "solver_matrix": _display_path(project_root, matrix_path),
            "model_slice_dir": _display_path(project_root, slice_dir),
            "failed_anchor_inventory": _display_path(project_root, inventory_path),
            "power_coverage_anchor_delta": _display_path(project_root, power_delta_path),
        },
        "candidate": _candidate(matrix_evidence, inventory_evidence),
        "matrix": matrix_evidence,
        "failed_anchor_inventory": inventory_evidence,
        "power_coverage_anchor_delta": power_delta_evidence,
        "model_slice": slice_evidence,
        "findings": findings,
        "recommendation": _recommendation(findings, matrix_evidence, slice_evidence),
        "checks": checks,
    }


def render_phase3b_zero_branch_unknown_triage_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    matrix = _mapping(report.get("matrix"))
    power_delta = _mapping(report.get("power_coverage_anchor_delta"))
    model_slice = _mapping(report.get("model_slice"))
    lines = [
        "# Phase 3B Zero-Branch UNKNOWN Triage",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Zero-branch UNKNOWN count: {matrix.get('zero_branch_unknown_count', 0)}",
        f"- Power-family changed count: {power_delta.get('power_family_changed_count', 0)}",
        f"- Model-slice findings: {model_slice.get('diagnostic_findings', [])}",
        f"- Recommendation: {report.get('recommendation')}",
        "",
        "## Findings",
        "",
    ]
    findings = [str(item) for item in list(report.get("findings", []))]
    lines.extend(f"- {item}" for item in (findings or ["none"]))
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


def render_phase3b_zero_branch_unknown_triage_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    matrix = _mapping(report.get("matrix"))
    power_delta = _mapping(report.get("power_coverage_anchor_delta"))
    model_slice = _mapping(report.get("model_slice"))
    lines = [
        "Phase 3B zero-branch UNKNOWN triage",
        f"candidate={candidate.get('key')}",
        f"zero_branch_unknown_count={matrix.get('zero_branch_unknown_count', 0)}",
        f"power_family_changed_count={power_delta.get('power_family_changed_count', 0)}",
        f"model_slice_findings={model_slice.get('diagnostic_findings', [])}",
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


def _matrix_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    matrix = _mapping(payload.get("matrix"))
    unknown = _mapping(matrix.get("unknown_diagnostics"))
    candidate = _mapping(payload.get("candidate"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FORCED_ANCHOR_SOLVER_MATRIX_SOURCE,
        "candidate_key": candidate.get("key"),
        "status_counts": dict(_mapping(matrix.get("status_counts"))),
        "zero_branch_unknown_count": int(unknown.get("zero_branch_unknown_count", 0)),
        "zero_branch_unknown_by_anchor": dict(
            _mapping(unknown.get("zero_branch_unknown_by_anchor"))
        ),
        "zero_branch_unknown_by_branching": dict(
            _mapping(unknown.get("zero_branch_unknown_by_branching"))
        ),
        "zero_branch_unknown_samples": [
            dict(entry)
            for entry in list(unknown.get("zero_branch_unknown_samples", []))
            if isinstance(entry, Mapping)
        ],
    }


def _inventory_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    metadata = _mapping(payload.get("metadata"))
    candidate = _mapping(payload.get("candidate"))
    summary = _mapping(payload.get("summary"))
    return {
        "present": True,
        "load_error": load_error,
        "source_supported": metadata.get("source") == FAILED_ANCHOR_INVENTORY_SOURCE,
        "candidate_key": candidate.get("key"),
        "classification_counts": dict(_mapping(summary.get("classification_counts"))),
        "forced_status_counts": dict(_mapping(summary.get("forced_status_counts"))),
        "forced_zero_branch_unknown_count": int(
            summary.get("forced_zero_branch_unknown_count", 0)
        ),
    }


def _power_delta_evidence(
    payload: Optional[Mapping[str, Any]],
    load_error: Optional[str],
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"present": False, "load_error": load_error}
    candidate = _mapping(payload.get("candidate"))
    delta = _mapping(payload.get("delta"))
    return {
        "present": True,
        "load_error": load_error,
        "candidate_key": candidate.get("key"),
        "power_family_changed_count": int(delta.get("power_family_changed_count", 0)),
        "power_family_positive_delta_sum": int(
            delta.get("power_family_positive_delta_sum", 0)
        ),
        "power_family_negative_delta_sum": int(
            delta.get("power_family_negative_delta_sum", 0)
        ),
        "mandatory_surviving_delta": int(delta.get("mandatory_surviving_delta", 0)),
        "optional_surviving_delta": int(delta.get("optional_surviving_delta", 0)),
        "top_power_family_deltas": [
            dict(entry)
            for entry in list(delta.get("top_power_family_deltas", []))
            if isinstance(entry, Mapping)
        ],
        "top_mandatory_group_deltas": [
            dict(entry)
            for entry in list(delta.get("top_mandatory_group_deltas", []))
            if isinstance(entry, Mapping)
        ],
        "optional_template_deltas": [
            dict(entry)
            for entry in list(delta.get("optional_template_deltas", []))
            if isinstance(entry, Mapping)
        ],
        "diagnostic_findings": [
            str(item) for item in list(delta.get("diagnostic_findings", []))
        ],
    }


def _load_model_slice_reports(slice_dir: Path) -> list[Dict[str, Any]]:
    reports: list[Dict[str, Any]] = []
    if not slice_dir.exists() or not slice_dir.is_dir():
        return reports
    for path in sorted(slice_dir.glob("*.json")):
        payload, error = _load_json_mapping(path)
        if not isinstance(payload, Mapping):
            continue
        reports.append({"path": path, "payload": payload, "load_error": error})
    return reports


def _slice_evidence(reports: list[Mapping[str, Any]]) -> Dict[str, Any]:
    findings: list[str] = []
    status_counts: Dict[str, int] = {}
    loaded_reports: list[Dict[str, Any]] = []
    for report in reports:
        payload = _mapping(report.get("payload"))
        metadata = _mapping(payload.get("metadata"))
        if metadata.get("source") != FORCED_ANCHOR_MODEL_SLICE_SOURCE:
            continue
        matrix = _mapping(payload.get("slice_matrix"))
        report_findings = [str(item) for item in list(matrix.get("diagnostic_findings", []))]
        findings.extend(report_findings)
        for status, count in _mapping(matrix.get("status_counts")).items():
            status_counts[str(status)] = int(status_counts.get(str(status), 0)) + int(count)
        loaded_reports.append(
            {
                "path": str(report.get("path")),
                "diagnostic_findings": report_findings,
                "status_counts": dict(_mapping(matrix.get("status_counts"))),
            }
        )
    return {
        "present": bool(loaded_reports),
        "report_count": int(len(loaded_reports)),
        "diagnostic_findings": _dedupe(findings),
        "status_counts": status_counts,
        "reports": loaded_reports,
    }


def _findings(
    matrix: Mapping[str, Any],
    inventory: Mapping[str, Any],
    power_delta: Mapping[str, Any],
    model_slice: Mapping[str, Any],
) -> list[str]:
    findings: list[str] = []
    if int(matrix.get("zero_branch_unknown_count", 0)) > 0:
        findings.append("forced_anchor_matrix_has_zero_branch_unknown")
    if int(inventory.get("forced_zero_branch_unknown_count", 0)) > 0:
        findings.append("failed_anchor_inventory_confirms_zero_branch_unknown")
    for finding in list(model_slice.get("diagnostic_findings", [])):
        findings.append(str(finding))
    for finding in list(power_delta.get("diagnostic_findings", [])):
        findings.append(str(finding))
    if int(power_delta.get("power_family_changed_count", 0)) > 0:
        findings.append("adjacent_anchor_power_family_bounds_shift")
    if int(power_delta.get("power_family_positive_delta_sum", 0)) > 0:
        findings.append("comparison_anchor_has_looser_power_family_bounds")
    if any("power_coverage" in finding for finding in findings):
        findings.append("power_coverage_core_is_primary_suspect")
    if any("residual_optionals" in finding for finding in findings):
        findings.append("residual_optionals_are_involved")
    return _dedupe(findings)


def _recommendation(
    findings: list[str],
    matrix: Mapping[str, Any],
    model_slice: Mapping[str, Any],
) -> str:
    if int(matrix.get("zero_branch_unknown_count", 0)) <= 0:
        return "No zero-branch UNKNOWN evidence is present; continue ordinary solver-matrix triage."
    if not bool(model_slice.get("present", False)):
        return "Zero-branch UNKNOWN is present; run model-slice diagnostics for the affected anchors."
    if "power_coverage_core_is_primary_suspect" in findings:
        return (
            "Zero-branch UNKNOWN is reproduced in the base forced-anchor model; "
            "model-slice and anchor-delta findings point at power coverage core/residual optional interactions."
        )
    return "Zero-branch UNKNOWN is present; inspect model-slice findings before changing proof semantics."


def _checks(
    matrix: Mapping[str, Any],
    inventory: Mapping[str, Any],
    power_delta: Mapping[str, Any],
    model_slice: Mapping[str, Any],
) -> list[Dict[str, str]]:
    return [
        _check(
            "solver_matrix_present",
            "pass" if bool(matrix.get("present", False)) else "fail",
            "solver matrix loaded" if bool(matrix.get("present", False)) else str(matrix.get("load_error")),
        ),
        _check(
            "solver_matrix_zero_branch_unknown_present",
            "pass" if int(matrix.get("zero_branch_unknown_count", 0)) > 0 else "fail",
            f"zero_branch_unknown_count={int(matrix.get('zero_branch_unknown_count', 0))}",
        ),
        _check(
            "failed_anchor_inventory_present",
            "pass" if bool(inventory.get("present", False)) else "fail",
            "failed-anchor inventory loaded"
            if bool(inventory.get("present", False))
            else str(inventory.get("load_error")),
        ),
        _check(
            "model_slice_findings_present",
            "pass" if list(model_slice.get("diagnostic_findings", [])) else "fail",
            f"findings={list(model_slice.get('diagnostic_findings', []))}",
        ),
        _check(
            "power_coverage_anchor_delta_present",
            "pass" if bool(power_delta.get("present", False)) else "fail",
            "power coverage anchor delta loaded"
            if bool(power_delta.get("present", False))
            else str(power_delta.get("load_error")),
        ),
        _check(
            "power_family_bounds_shift_present",
            "pass" if int(power_delta.get("power_family_changed_count", 0)) > 0 else "fail",
            f"changed_count={int(power_delta.get('power_family_changed_count', 0))}",
        ),
    ]


def _candidate(matrix: Mapping[str, Any], inventory: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "key": matrix.get("candidate_key") or inventory.get("candidate_key"),
    }


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


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
