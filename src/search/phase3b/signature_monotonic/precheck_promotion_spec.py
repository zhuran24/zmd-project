from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso
from src.search.phase3b.signature_monotonic.precheck_candidate import (
    SIGNATURE_MONOTONIC_PRECHECK_CANDIDATE_SOURCE,
)

SIGNATURE_MONOTONIC_PRECHECK_PROMOTION_SPEC_SOURCE = (
    "phase3b_signature_monotonic_precheck_promotion_spec_v1"
)
DEFAULT_PRECHECK_CANDIDATE_PATH = Path(
    ".artifacts/phase3b_signature_monotonic_precheck_candidate/precheck_candidate.json"
)


def build_phase3b_signature_monotonic_precheck_promotion_spec(
    project_root: Path,
    *,
    precheck_candidate_path: Optional[Path] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    input_path = _resolve_path(
        project_root,
        precheck_candidate_path
        if precheck_candidate_path is not None
        else DEFAULT_PRECHECK_CANDIDATE_PATH,
    )
    candidate_summary, load_error = _load_json_mapping(input_path)
    metadata = _mapping(candidate_summary.get("metadata")) if candidate_summary else {}
    candidate = _mapping(candidate_summary.get("candidate")) if candidate_summary else {}
    gate = _mapping(candidate_summary.get("gate")) if candidate_summary else {}
    evidence = _mapping(candidate_summary.get("evidence")) if candidate_summary else {}
    source_supported = metadata.get("source") == SIGNATURE_MONOTONIC_PRECHECK_CANDIDATE_SOURCE
    design_gate_passed = bool(gate.get("design_gate_passed", False))
    input_runtime_ready = bool(gate.get("runtime_promotion_ready", False))
    failed_input_checks = [
        str(check.get("check_id"))
        for check in list(candidate_summary.get("checks", []) if candidate_summary else [])
        if isinstance(check, Mapping) and str(check.get("status")) == "fail"
    ]
    runtime_guard_present = (
        not input_runtime_ready and "runtime_promotion_guard" in failed_input_checks
    )
    infeasible_count = int(evidence.get("monotonic_infeasible_count", 0))
    feasible_control_count = int(evidence.get("monotonic_feasible_control_count", 0))
    evidence_present = bool(infeasible_count >= 3 and feasible_control_count >= 1)
    blocked_by = _promotion_blockers(
        candidate_summary_present=candidate_summary is not None and load_error is None,
        source_supported=source_supported,
        design_gate_passed=design_gate_passed,
        runtime_guard_present=runtime_guard_present,
        evidence_present=evidence_present,
        input_runtime_ready=input_runtime_ready,
    )
    spec_ready_for_runtime_slice = bool(
        candidate_summary is not None
        and load_error is None
        and source_supported
        and design_gate_passed
        and runtime_guard_present
        and evidence_present
    )
    checks = [
        _check(
            "precheck_candidate_present",
            "pass" if candidate_summary is not None and load_error is None else "fail",
            "precheck candidate summary loaded"
            if candidate_summary is not None and load_error is None
            else load_error or f"missing:{_display_path(project_root, input_path)}",
        ),
        _check(
            "precheck_candidate_schema",
            "pass" if source_supported else "fail",
            "supported signature-monotonic precheck candidate schema"
            if source_supported
            else f"unsupported source:{metadata.get('source')}",
        ),
        _check(
            "design_gate_passed",
            "pass" if design_gate_passed else "fail",
            "diagnostic design gate is passed"
            if design_gate_passed
            else "diagnostic design gate is not passed",
        ),
        _check(
            "runtime_promotion_guard_present",
            "pass" if runtime_guard_present else "fail",
            "runtime promotion remains explicitly guarded"
            if runtime_guard_present
            else "expected runtime_promotion_guard failed check is missing",
        ),
        _check(
            "monotonic_evidence_present",
            "pass" if evidence_present else "fail",
            f"infeasible={infeasible_count}; feasible_controls={feasible_control_count}",
        ),
        _check(
            "proof_semantics_unchanged",
            "pass",
            "promotion spec is report-only and does not alter terminal proof sources",
        ),
        _check(
            "runtime_slice_guarded_default",
            "pass",
            "runtime implementation must be guarded/default-off until an explicit code slice",
        ),
    ]
    return {
        "metadata": {
            "source": SIGNATURE_MONOTONIC_PRECHECK_PROMOTION_SPEC_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
            "precheck_candidate": _display_path(project_root, input_path),
        },
        "candidate": dict(candidate),
        "promotion_status": {
            "spec_ready_for_runtime_slice": bool(spec_ready_for_runtime_slice),
            "design_gate_passed": bool(design_gate_passed),
            "runtime_slice_implemented": True,
            "runtime_promotion_ready": False,
            "runtime_promotion_guarded": bool(runtime_guard_present),
            "input_runtime_promotion_ready": bool(input_runtime_ready),
            "promotion_blocked_by": blocked_by,
            "recommendation": _recommendation(spec_ready_for_runtime_slice, blocked_by),
        },
        "evidence_summary": dict(evidence),
        "proposed_precheck_contract": _proposed_precheck_contract(),
        "required_runtime_tests": _required_runtime_tests(),
        "required_safety_gates": _required_safety_gates(),
        "checks": checks,
    }


def render_phase3b_signature_monotonic_precheck_promotion_spec_markdown(spec: Mapping[str, Any]) -> str:
    candidate = _mapping(spec.get("candidate"))
    status = _mapping(spec.get("promotion_status"))
    evidence = _mapping(spec.get("evidence_summary"))
    contract = _mapping(spec.get("proposed_precheck_contract"))
    lines = [
        "# Phase 3B Signature-Monotonic Precheck Promotion Spec",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Spec ready for runtime slice: {bool(status.get('spec_ready_for_runtime_slice', False))}",
        f"- Runtime slice implemented: {bool(status.get('runtime_slice_implemented', False))}",
        f"- Runtime promotion ready: {bool(status.get('runtime_promotion_ready', False))}",
        f"- Runtime promotion guarded: {bool(status.get('runtime_promotion_guarded', False))}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Evidence",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| monotonic_infeasible_count | {_markdown_cell(evidence.get('monotonic_infeasible_count'))} |",
        f"| monotonic_feasible_control_count | {_markdown_cell(evidence.get('monotonic_feasible_control_count'))} |",
        "",
        "## Contract",
        "",
        f"- Precheck reason: {contract.get('precheck_reason')}",
        f"- Trigger condition: {contract.get('trigger_condition')}",
        f"- Runtime default: {contract.get('runtime_default')}",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in list(spec.get("checks", [])):
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


def render_phase3b_signature_monotonic_precheck_promotion_spec_text(spec: Mapping[str, Any]) -> str:
    status = _mapping(spec.get("promotion_status"))
    evidence = _mapping(spec.get("evidence_summary"))
    return "\n".join(
        [
            "Phase 3B signature-monotonic precheck promotion spec",
            f"spec_ready_for_runtime_slice={bool(status.get('spec_ready_for_runtime_slice', False))}",
            f"runtime_slice_implemented={bool(status.get('runtime_slice_implemented', False))}",
            f"runtime_promotion_ready={bool(status.get('runtime_promotion_ready', False))}",
            f"monotonic_infeasible_count={evidence.get('monotonic_infeasible_count')}",
            f"monotonic_feasible_control_count={evidence.get('monotonic_feasible_control_count')}",
            f"recommendation={status.get('recommendation')}",
        ]
    ) + "\n"


def write_phase3b_signature_monotonic_precheck_promotion_spec(
    spec: Mapping[str, Any],
    output_dir: Path,
) -> Dict[str, str]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "promotion_spec.json"
    md_path = output_dir / "promotion_spec.md"
    txt_path = output_dir / "promotion_spec.txt"
    _atomic_write_json(json_path, spec)
    _atomic_write_text(md_path, render_phase3b_signature_monotonic_precheck_promotion_spec_markdown(spec))
    _atomic_write_text(txt_path, render_phase3b_signature_monotonic_precheck_promotion_spec_text(spec))
    return {"json": str(json_path), "md": str(md_path), "txt": str(txt_path)}


def _proposed_precheck_contract() -> Dict[str, Any]:
    return {
        "precheck_reason": "signature_monotonic_forced_label_infeasible",
        "trigger_condition": (
            "Forced coordinate labels for a mandatory compact-signature group imply "
            "per-slot signature domains with no nondecreasing sequence."
        ),
        "runtime_default": "guarded/default-off",
        "parallel_path_behavior": "unchanged until a separate explicit runtime slice",
        "proof_source": False,
        "terminal_proof_unchanged": True,
        "expected_payload_fields": [
            "signature_monotonic_precheck.evaluated",
            "signature_monotonic_precheck.triggered",
            "signature_monotonic_precheck.group_id",
            "signature_monotonic_precheck.failure.slot_index",
            "signature_monotonic_precheck.constrained_slots[]",
        ],
    }


def _required_runtime_tests() -> list[Dict[str, str]]:
    return [
        {
            "test_id": "monotonic_infeasible_for_m6x4_source_sweep",
            "assertion": "source_sweep forced labels trigger without invoking CP-SAT Solve.",
        },
        {
            "test_id": "monotonic_infeasible_for_exchange_combo",
            "assertion": "combo_006 forced labels trigger via the same monotonic DP failure.",
        },
        {
            "test_id": "monotonic_feasible_control_not_eliminated",
            "assertion": "a subset with slot16 y=65 only remains non-triggering.",
        },
        {
            "test_id": "default_off_runtime_behavior",
            "assertion": "serial/parallel pre-master paths are unchanged unless explicitly enabled.",
        },
    ]


def _required_safety_gates() -> list[str]:
    return [
        "No final 168h long run before B5A retry.",
        "No release/viewer/frontdoor status promotion.",
        "No workspace checkpoint import-back.",
        "Runtime precheck evidence remains non-proof until terminal exact evidence exists.",
    ]


def _promotion_blockers(
    *,
    candidate_summary_present: bool,
    source_supported: bool,
    design_gate_passed: bool,
    runtime_guard_present: bool,
    evidence_present: bool,
    input_runtime_ready: bool,
) -> list[str]:
    blockers: list[str] = []
    if not candidate_summary_present:
        blockers.append("precheck_candidate_missing")
    if not source_supported:
        blockers.append("unsupported_precheck_candidate_schema")
    if not design_gate_passed:
        blockers.append("design_gate_not_passed")
    if not runtime_guard_present:
        blockers.append("runtime_guard_missing")
    if not evidence_present:
        blockers.append("monotonic_evidence_insufficient")
    if input_runtime_ready:
        blockers.append("candidate_should_not_be_runtime_ready_yet")
    return blockers


def _recommendation(ready: bool, blockers: list[str]) -> str:
    if ready:
        return "Spec is ready for a guarded/default-off runtime slice; keep proof semantics unchanged."
    return "Runtime slice is not ready; resolve blockers: " + ", ".join(blockers)


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
