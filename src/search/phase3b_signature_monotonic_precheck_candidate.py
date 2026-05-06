from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.search.exact_campaign import now_iso
from src.search.phase3b_signature_monotonic_forced_label_audit import (
    SIGNATURE_MONOTONIC_FORCED_LABEL_AUDIT_SOURCE,
)

SIGNATURE_MONOTONIC_PRECHECK_CANDIDATE_SOURCE = (
    "phase3b_signature_monotonic_precheck_candidate_v1"
)
DEFAULT_AUDIT_DIR = Path(".artifacts/phase3b_signature_monotonic_forced_label_audit_m6x4_anchor119")


def build_phase3b_signature_monotonic_precheck_candidate_summary(
    project_root: Path,
    *,
    audit_dir: Optional[Path] = None,
    control_audit_path: Optional[Path] = None,
    min_infeasible_count: int = 3,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    resolved_audit_dir = _resolve_path(
        project_root,
        audit_dir if audit_dir is not None else DEFAULT_AUDIT_DIR,
    )
    audit_reports = _load_audit_reports(resolved_audit_dir, control_audit_path, project_root)
    evidence_reports = [
        report
        for report in audit_reports
        if not bool(report.get("is_control", False))
    ]
    control_reports = [
        report
        for report in audit_reports
        if bool(report.get("is_control", False))
    ]
    schema_supported = all(
        _mapping(_mapping(report.get("payload")).get("metadata")).get("source")
        == SIGNATURE_MONOTONIC_FORCED_LABEL_AUDIT_SOURCE
        for report in audit_reports
        if report.get("payload") is not None
    )
    missing_count = sum(1 for report in audit_reports if report.get("payload") is None)
    infeasible = [
        _compact_audit(report)
        for report in evidence_reports
        if _audit_outcome(report) == "monotonic_infeasible"
    ]
    non_infeasible = [
        _compact_audit(report)
        for report in evidence_reports
        if _audit_outcome(report) != "monotonic_infeasible"
    ]
    feasible_controls = [
        _compact_audit(report)
        for report in control_reports
        if _audit_outcome(report) == "monotonic_feasible"
    ]
    all_no_solve = all(
        bool(_mapping(_mapping(report.get("payload")).get("metadata")).get("solver_invoked")) is False
        for report in audit_reports
        if report.get("payload") is not None
    )
    all_non_proof = all(
        bool(_mapping(_mapping(report.get("payload")).get("metadata")).get("proof_source")) is False
        for report in audit_reports
        if report.get("payload") is not None
    )
    design_gate_passed = bool(
        audit_reports
        and missing_count == 0
        and schema_supported
        and all_no_solve
        and all_non_proof
        and len(infeasible) >= int(min_infeasible_count)
        and not non_infeasible
        and len(feasible_controls) >= 1
    )
    checks = [
        _check(
            "audit_reports_present",
            "pass" if audit_reports and missing_count == 0 else "fail",
            f"loaded={len(audit_reports) - missing_count}; missing={missing_count}",
        ),
        _check(
            "audit_schema_supported",
            "pass" if schema_supported else "fail",
            f"source={SIGNATURE_MONOTONIC_FORCED_LABEL_AUDIT_SOURCE}",
        ),
        _check(
            "audit_no_solve",
            "pass" if all_no_solve else "fail",
            "all audit reports declare solver_invoked=false",
        ),
        _check(
            "audit_non_proof",
            "pass" if all_non_proof else "fail",
            "all audit reports declare proof_source=false",
        ),
        _check(
            "minimum_monotonic_infeasible_count",
            "pass" if len(infeasible) >= int(min_infeasible_count) else "fail",
            f"infeasible={len(infeasible)}; required>={int(min_infeasible_count)}",
        ),
        _check(
            "no_non_infeasible_evidence_cases",
            "pass" if not non_infeasible else "fail",
            f"non_infeasible={len(non_infeasible)}",
        ),
        _check(
            "monotonic_feasible_control_present",
            "pass" if feasible_controls else "fail",
            f"feasible_controls={len(feasible_controls)}",
        ),
        _check(
            "runtime_promotion_guard",
            "fail",
            "candidate evidence is report-only; add guarded runtime tests before promotion",
        ),
    ]
    first_payload = _mapping(evidence_reports[0].get("payload")) if evidence_reports else {}
    return {
        "metadata": {
            "source": SIGNATURE_MONOTONIC_PRECHECK_CANDIDATE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "signature_monotonic_precheck_candidate_not_proof_source",
        },
        "paths": {
            "project_root": str(project_root),
            "audit_dir": _display_path(project_root, resolved_audit_dir),
            "control_audit": (
                _display_path(project_root, _resolve_path(project_root, control_audit_path))
                if control_audit_path is not None
                else None
            ),
        },
        "candidate": dict(_mapping(first_payload.get("candidate"))),
        "gate": {
            "design_gate_passed": bool(design_gate_passed),
            "runtime_promotion_ready": False,
            "min_infeasible_count": int(min_infeasible_count),
            "recommendation": _recommendation(design_gate_passed, non_infeasible, feasible_controls),
            "promotion_requirements": [
                "Implement the runtime precheck as guarded/default-off before any campaign use.",
                "Test no-solve monotonic-infeasible detection and monotonic-feasible controls.",
                "Keep terminal exact proof source unchanged; this candidate is not proof evidence.",
                "Rerun B5A in a fresh workspace after any runtime precheck change.",
            ],
        },
        "evidence": {
            "audit_count": int(len(evidence_reports)),
            "monotonic_infeasible_count": int(len(infeasible)),
            "non_infeasible_count": int(len(non_infeasible)),
            "control_count": int(len(control_reports)),
            "monotonic_feasible_control_count": int(len(feasible_controls)),
            "infeasible_cases": infeasible,
            "non_infeasible_cases": non_infeasible,
            "control_cases": feasible_controls,
        },
        "proposed_precheck_contract": _proposed_precheck_contract(),
        "checks": checks,
    }


def render_phase3b_signature_monotonic_precheck_candidate_markdown(summary: Mapping[str, Any]) -> str:
    candidate = _mapping(summary.get("candidate"))
    gate = _mapping(summary.get("gate"))
    evidence = _mapping(summary.get("evidence"))
    lines = [
        "# Phase 3B Signature-Monotonic Precheck Candidate Gate",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Design gate passed: {bool(gate.get('design_gate_passed', False))}",
        f"- Runtime promotion ready: {bool(gate.get('runtime_promotion_ready', False))}",
        f"- Monotonic infeasible cases: {evidence.get('monotonic_infeasible_count')}",
        f"- Feasible controls: {evidence.get('monotonic_feasible_control_count')}",
        f"- Recommendation: {gate.get('recommendation')}",
        "- Diagnostic semantics: signature_monotonic_precheck_candidate_not_proof_source",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in list(summary.get("checks", [])):
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
    lines.extend(["", "## Infeasible Cases", "", "| Case | Failure Slot | Previous | Current |", "| --- | ---: | --- | --- |"])
    for entry in list(evidence.get("infeasible_cases", [])):
        if isinstance(entry, Mapping):
            failure = _mapping(entry.get("failure"))
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("name")),
                        _markdown_cell(failure.get("slot_index")),
                        _markdown_cell(failure.get("previous_possible_signature_ids")),
                        _markdown_cell(failure.get("current_allowed_signature_ids")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_signature_monotonic_precheck_candidate_text(summary: Mapping[str, Any]) -> str:
    gate = _mapping(summary.get("gate"))
    evidence = _mapping(summary.get("evidence"))
    return "\n".join(
        [
            "Phase 3B signature-monotonic precheck candidate gate",
            f"design_gate_passed={bool(gate.get('design_gate_passed', False))}",
            f"runtime_promotion_ready={bool(gate.get('runtime_promotion_ready', False))}",
            f"monotonic_infeasible_count={evidence.get('monotonic_infeasible_count')}",
            f"monotonic_feasible_control_count={evidence.get('monotonic_feasible_control_count')}",
            f"recommendation={gate.get('recommendation')}",
        ]
    ) + "\n"


def _load_audit_reports(
    audit_dir: Path,
    control_audit_path: Optional[Path],
    project_root: Path,
) -> list[Dict[str, Any]]:
    reports: list[Dict[str, Any]] = []
    if audit_dir.exists():
        for path in sorted(audit_dir.glob("signature_monotonic_*.json")):
            if control_audit_path is not None and path.resolve() == _resolve_path(project_root, control_audit_path).resolve():
                continue
            payload, error = _load_json_mapping(path)
            reports.append(
                {
                    "name": path.stem.replace("signature_monotonic_", ""),
                    "path": _display_path(project_root, path),
                    "payload": payload,
                    "load_error": error,
                    "is_control": False,
                }
            )
    if control_audit_path is not None:
        path = _resolve_path(project_root, control_audit_path)
        payload, error = _load_json_mapping(path)
        reports.append(
            {
                "name": path.stem.replace("signature_monotonic_", ""),
                "path": _display_path(project_root, path),
                "payload": payload,
                "load_error": error,
                "is_control": True,
            }
        )
    return reports


def _compact_audit(report: Mapping[str, Any]) -> Dict[str, Any]:
    payload = _mapping(report.get("payload"))
    mono = _mapping(payload.get("monotonicity"))
    return {
        "name": report.get("name"),
        "path": report.get("path"),
        "outcome": mono.get("outcome"),
        "label_count": mono.get("label_count"),
        "constrained_slot_count": mono.get("constrained_slot_count"),
        "failure": dict(_mapping(mono.get("failure"))),
    }


def _audit_outcome(report: Mapping[str, Any]) -> str:
    return str(_mapping(_mapping(report.get("payload")).get("monotonicity")).get("outcome"))


def _proposed_precheck_contract() -> Dict[str, Any]:
    return {
        "precheck_reason": "signature_monotonic_forced_label_infeasible",
        "trigger_condition": (
            "For a mandatory group using compact signature-region encoding, forced x/y/mode "
            "labels imply per-slot signature domains with no nondecreasing assignment."
        ),
        "runtime_default": "guarded/default-off until a dedicated runtime slice lands",
        "proof_source": False,
        "terminal_proof_unchanged": True,
        "telemetry_fields": [
            "coordinate_validation_precheck.signature_monotonic.evaluated",
            "coordinate_validation_precheck.signature_monotonic.triggered",
            "coordinate_validation_precheck.signature_monotonic.failure_slot",
            "coordinate_validation_precheck.signature_monotonic.rejected_groups[]",
        ],
    }


def _recommendation(
    design_gate_passed: bool,
    non_infeasible: Sequence[Mapping[str, Any]],
    feasible_controls: Sequence[Mapping[str, Any]],
) -> str:
    if design_gate_passed:
        return "Design gate passed; implement a guarded/default-off runtime precheck slice with focused tests."
    if non_infeasible:
        return "Some evidence audits are not monotonic-infeasible; inspect non_infeasible_cases before runtime work."
    if not feasible_controls:
        return "Add at least one monotonic-feasible control audit before runtime work."
    return "Precheck candidate gate failed; inspect checks before continuing."


def write_phase3b_signature_monotonic_precheck_candidate_summary(
    summary: Mapping[str, Any],
    output_dir: Path,
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "precheck_candidate.json"
    md_path = output_dir / "precheck_candidate.md"
    txt_path = output_dir / "precheck_candidate.txt"
    _atomic_write_json(json_path, summary)
    _atomic_write_text(md_path, render_phase3b_signature_monotonic_precheck_candidate_markdown(summary))
    _atomic_write_text(txt_path, render_phase3b_signature_monotonic_precheck_candidate_text(summary))
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _load_json_mapping(path: Path) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _resolve_path(project_root: Path, path: Optional[Path]) -> Path:
    if path is None:
        return project_root
    path = Path(path)
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(Path(path).resolve().relative_to(project_root)).replace("\\", "/")
    except Exception:
        return str(path)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)
