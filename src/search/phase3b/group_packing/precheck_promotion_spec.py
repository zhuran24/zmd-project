from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso


GROUP_PACKING_PRECHECK_PROMOTION_SPEC_SOURCE = (
    "phase3b_group_packing_precheck_promotion_spec_v1"
)
GROUP_PACKING_PRECHECK_CANDIDATE_SOURCE = (
    "phase3b_group_packing_precheck_candidate_v1"
)
DEFAULT_PRECHECK_CANDIDATE_PATH = Path(
    ".artifacts/phase3b_group_packing_precheck_candidate/precheck_candidate.json"
)
DEFAULT_MIN_SAMPLE_COUNT = 51


def build_phase3b_group_packing_precheck_promotion_spec(
    project_root: Path,
    *,
    precheck_candidate_path: Optional[Path] = None,
    min_sample_count: int = DEFAULT_MIN_SAMPLE_COUNT,
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
    group_packing_probe = (
        _mapping(candidate_summary.get("group_packing_probe"))
        if candidate_summary
        else {}
    )
    group_packing_blockers = (
        _mapping(candidate_summary.get("group_packing_blockers"))
        if candidate_summary
        else {}
    )
    blockers = [
        dict(entry)
        for entry in list(group_packing_blockers.get("blockers", []))
        if isinstance(entry, Mapping)
    ]

    source_supported = metadata.get("source") == GROUP_PACKING_PRECHECK_CANDIDATE_SOURCE
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
    sample_count = int(group_packing_probe.get("sample_count", 0))
    feasible_count = int(group_packing_probe.get("feasible_count", 0))
    unknown_count = int(group_packing_probe.get("unknown_count", 0))
    skipped_count = int(group_packing_probe.get("skipped_count", 0))
    infeasible_count = int(group_packing_probe.get("infeasible_count", 0))
    blocker_count = int(group_packing_blockers.get("blocker_count", len(blockers)))
    full_sample_coverage_present = bool(
        sample_count >= int(min_sample_count)
        and sample_count > 0
        and infeasible_count == sample_count
        and feasible_count == 0
        and unknown_count == 0
        and skipped_count == 0
    )
    blocker_inventory_present = bool(blocker_count >= 1 and blockers)

    promotion_blocked_by = _promotion_blockers(
        candidate_summary_present=candidate_summary is not None and load_error is None,
        source_supported=source_supported,
        design_gate_passed=design_gate_passed,
        runtime_guard_present=runtime_guard_present,
        full_sample_coverage_present=full_sample_coverage_present,
        blocker_inventory_present=blocker_inventory_present,
        input_runtime_ready=input_runtime_ready,
    )
    spec_ready_for_runtime_slice = bool(
        candidate_summary is not None
        and load_error is None
        and source_supported
        and design_gate_passed
        and runtime_guard_present
        and full_sample_coverage_present
        and blocker_inventory_present
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
            "supported precheck candidate schema"
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
            "full_sample_coverage_present",
            "pass" if full_sample_coverage_present else "fail",
            (
                f"samples={sample_count}; infeasible={infeasible_count}; "
                f"feasible={feasible_count}; unknown={unknown_count}; skipped={skipped_count}; "
                f"required>={int(min_sample_count)}"
            ),
        ),
        _check(
            "blocker_inventory_present",
            "pass" if blocker_inventory_present else "fail",
            f"blocker_count={blocker_count}",
        ),
        _check(
            "proof_semantics_unchanged",
            "pass",
            "promotion spec is report-only and does not alter proof sources",
        ),
        _check(
            "promotion_spec_not_runtime_change",
            "pass",
            "runtime implementation remains blocked until a separate code slice",
        ),
    ]

    return {
        "metadata": {
            "source": GROUP_PACKING_PRECHECK_PROMOTION_SPEC_SOURCE,
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
            "runtime_promotion_ready": False,
            "runtime_promotion_guarded": bool(runtime_guard_present),
            "input_runtime_promotion_ready": bool(input_runtime_ready),
            "promotion_blocked_by": promotion_blocked_by,
            "recommendation": _recommendation(
                spec_ready_for_runtime_slice=spec_ready_for_runtime_slice,
                promotion_blocked_by=promotion_blocked_by,
            ),
        },
        "evidence_summary": {
            "min_sample_count": int(min_sample_count),
            "sample_count": sample_count,
            "infeasible_count": infeasible_count,
            "feasible_count": feasible_count,
            "unknown_count": unknown_count,
            "skipped_count": skipped_count,
            "blocker_count": blocker_count,
            "blockers": blockers,
        },
        "proposed_precheck_contract": _proposed_precheck_contract(),
        "required_runtime_tests": _required_runtime_tests(),
        "required_safety_gates": _required_safety_gates(),
        "checks": checks,
    }


def render_phase3b_group_packing_precheck_promotion_spec_markdown(
    spec: Mapping[str, Any],
) -> str:
    candidate = _mapping(spec.get("candidate"))
    status = _mapping(spec.get("promotion_status"))
    evidence = _mapping(spec.get("evidence_summary"))
    contract = _mapping(spec.get("proposed_precheck_contract"))
    lines = [
        "# Phase 3B Group Packing Precheck Promotion Spec",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Spec ready for runtime slice: {bool(status.get('spec_ready_for_runtime_slice', False))}",
        f"- Runtime promotion ready: {bool(status.get('runtime_promotion_ready', False))}",
        f"- Runtime promotion guarded: {bool(status.get('runtime_promotion_guarded', False))}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Evidence",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    for key in [
        "min_sample_count",
        "sample_count",
        "infeasible_count",
        "feasible_count",
        "unknown_count",
        "skipped_count",
        "blocker_count",
    ]:
        lines.append(f"| {_markdown_cell(key)} | {_markdown_cell(evidence.get(key))} |")

    blocked_by = [str(item) for item in list(status.get("promotion_blocked_by", []))]
    if blocked_by:
        lines.extend(["", "## Promotion Blockers", ""])
        lines.extend(f"- {item}" for item in blocked_by)

    blockers = [
        entry
        for entry in list(evidence.get("blockers", []))
        if isinstance(entry, Mapping)
    ]
    if blockers:
        lines.extend(
            [
                "",
                "## Diagnostic Blockers",
                "",
                "| Group | Status | Samples | Required | Surviving | Greedy |",
                "| --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in blockers:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("group_id")),
                        _markdown_cell(entry.get("solver_status")),
                        _markdown_cell(entry.get("sample_count")),
                        _markdown_cell(
                            f"{entry.get('required_count_min')}..{entry.get('required_count_max')}"
                        ),
                        _markdown_cell(
                            f"{entry.get('surviving_at_failure_min')}..{entry.get('surviving_at_failure_max')}"
                        ),
                        _markdown_cell(
                            f"{entry.get('greedy_selected_min')}..{entry.get('greedy_selected_max')}"
                        ),
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Proposed Runtime Contract",
            "",
            f"- Precheck reason: {contract.get('precheck_reason')}",
            f"- Candidate status: {contract.get('candidate_status')}",
            f"- Master solve skipped: {bool(contract.get('master_solve_skipped', False))}",
            f"- Attempt budget consumed: {bool(contract.get('attempt_budget_consumed', False))}",
            f"- Evidence scope: {contract.get('evidence_scope')}",
            "",
            "## Required Proof Summary Fields",
            "",
        ]
    )
    lines.extend(
        f"- {field}"
        for field in list(contract.get("required_proof_summary_fields", []))
    )

    lines.extend(["", "## Required Runtime Tests", ""])
    for test in list(spec.get("required_runtime_tests", [])):
        if not isinstance(test, Mapping):
            continue
        lines.append(
            f"- {test.get('test_id')}: {test.get('assertion')}"
        )

    lines.extend(["", "## Required Safety Gates", ""])
    for gate in list(spec.get("required_safety_gates", [])):
        if not isinstance(gate, Mapping):
            continue
        lines.append(f"- {gate.get('gate_id')}: {gate.get('assertion')}")

    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for check in list(spec.get("checks", [])):
        if not isinstance(check, Mapping):
            continue
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


def render_phase3b_group_packing_precheck_promotion_spec_text(
    spec: Mapping[str, Any],
) -> str:
    candidate = _mapping(spec.get("candidate"))
    status = _mapping(spec.get("promotion_status"))
    evidence = _mapping(spec.get("evidence_summary"))
    contract = _mapping(spec.get("proposed_precheck_contract"))
    lines = [
        "Phase 3B group packing precheck promotion spec",
        f"candidate={candidate.get('key')}",
        f"spec_ready_for_runtime_slice={bool(status.get('spec_ready_for_runtime_slice', False))}",
        f"runtime_promotion_ready={bool(status.get('runtime_promotion_ready', False))}",
        f"runtime_promotion_guarded={bool(status.get('runtime_promotion_guarded', False))}",
        f"promotion_blocked_by={','.join(str(item) for item in list(status.get('promotion_blocked_by', [])))}",
        f"recommendation={status.get('recommendation')}",
        f"samples={evidence.get('sample_count')} infeasible={evidence.get('infeasible_count')} feasible={evidence.get('feasible_count')} unknown={evidence.get('unknown_count')} skipped={evidence.get('skipped_count')}",
        f"blocker_count={evidence.get('blocker_count')}",
        f"precheck_reason={contract.get('precheck_reason')}",
        f"candidate_status={contract.get('candidate_status')}",
        f"attempt_budget_consumed={bool(contract.get('attempt_budget_consumed', False))}",
    ]
    for test in list(spec.get("required_runtime_tests", [])):
        if isinstance(test, Mapping):
            lines.append(
                f"required_test id={test.get('test_id')} assertion={test.get('assertion')}"
            )
    for gate in list(spec.get("required_safety_gates", [])):
        if isinstance(gate, Mapping):
            lines.append(
                f"safety_gate id={gate.get('gate_id')} assertion={gate.get('assertion')}"
            )
    for check in list(spec.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "check "
                f"id={check.get('check_id')} "
                f"status={check.get('status')} "
                f"detail={check.get('detail')}"
            )
    return "\n".join(lines) + "\n"


def _proposed_precheck_contract() -> Dict[str, Any]:
    return {
        "precheck_reason": "group_packing_exact_infeasible",
        "candidate_status": "INFEASIBLE",
        "master_status": "INFEASIBLE",
        "diagnostic_flow_status": "NOT_RUN",
        "master_solve_skipped": True,
        "attempt_budget_consumed": False,
        "campaign_candidate_attempts_incremented": False,
        "evidence_scope": "diagnostic_design_only_until_runtime_slice",
        "terminal_proof_source": "unchanged",
        "parallel_path_behavior": "unchanged_until_explicit_runtime_slice",
        "required_proof_summary_fields": [
            "master_candidate_precheck.triggered",
            "master_candidate_precheck.precheck_reason",
            "master_candidate_precheck.master_solve_skipped",
            "group_packing_precheck.triggered",
            "group_packing_precheck.blocker_count",
            "group_packing_precheck.blockers[].group_id",
            "group_packing_precheck.blockers[].solver_status",
            "group_packing_precheck.blockers[].required_count",
            "group_packing_precheck.blockers[].surviving_count",
            "group_packing_precheck.blockers[].anchor_idx",
            "precheck_lookahead.enabled",
            "precheck_lookahead.slot_index",
            "precheck_lookahead.limit",
            "precheck_lookahead.is_selected_head",
        ],
    }


def _required_runtime_tests() -> list[Dict[str, str]]:
    return [
        {
            "test_id": "triggered_candidate_marked_infeasible_without_solve",
            "assertion": (
                "A triggered group-packing precheck records INFEASIBLE, skips master "
                "solve, and preserves candidate attempts at zero."
            ),
        },
        {
            "test_id": "non_triggered_candidate_writes_no_evidence",
            "assertion": (
                "A non-triggered group-packing scan does not create a campaign "
                "candidate record and does not add telemetry evidence."
            ),
        },
        {
            "test_id": "zero_budget_still_allows_precheck_elimination",
            "assertion": (
                "max_attempts=0 still permits deterministic pre-master elimination "
                "but does not enter solve."
            ),
        },
        {
            "test_id": "lookahead_records_only_triggered_eliminations",
            "assertion": (
                "Serial lookahead writes proof_summary.precheck_lookahead only for "
                "triggered eliminations."
            ),
        },
        {
            "test_id": "parallel_path_remains_unchanged",
            "assertion": (
                "Parallel coordinator precheck behavior is unchanged unless a later "
                "slice explicitly opts in."
            ),
        },
        {
            "test_id": "telemetry_reason_counts_remain_backward_compatible",
            "assertion": (
                "precheck_elimination_count and existing reason counts stay stable "
                "while adding the new group-packing reason."
            ),
        },
    ]


def _required_safety_gates() -> list[Dict[str, str]]:
    return [
        {
            "gate_id": "full_eligible_anchor_coverage",
            "assertion": "All eligible failed-anchor samples are covered with no feasible, unknown, or skipped results.",
        },
        {
            "gate_id": "exact_hash_truth_unchanged",
            "assertion": "The four exact hash truth sources still match the B0 startline manifest.",
        },
        {
            "gate_id": "b5a_rerun_after_runtime_change",
            "assertion": "B5A first-certified-anchor sprint is rerun after any runtime precheck change.",
        },
        {
            "gate_id": "production_acceptance_after_anchor",
            "assertion": "Production acceptance is rerun only after B5A finds an anchor.",
        },
        {
            "gate_id": "release_status_remains_open",
            "assertion": "B6/B7 release, viewer, frontdoor, and health status remain exact-open.",
        },
    ]


def _promotion_blockers(
    *,
    candidate_summary_present: bool,
    source_supported: bool,
    design_gate_passed: bool,
    runtime_guard_present: bool,
    full_sample_coverage_present: bool,
    blocker_inventory_present: bool,
    input_runtime_ready: bool,
) -> list[str]:
    blockers: list[str] = []
    if not candidate_summary_present:
        blockers.append("precheck_candidate_missing")
    if candidate_summary_present and not source_supported:
        blockers.append("precheck_candidate_schema")
    if candidate_summary_present and source_supported and not design_gate_passed:
        blockers.append("design_gate_not_passed")
    if candidate_summary_present and source_supported and not full_sample_coverage_present:
        blockers.append("full_sample_coverage_gate")
    if candidate_summary_present and source_supported and not blocker_inventory_present:
        blockers.append("blocker_inventory_missing")
    if input_runtime_ready:
        blockers.append("unexpected_input_runtime_ready")
    if not runtime_guard_present:
        blockers.append("runtime_promotion_guard_missing")
    else:
        blockers.append("runtime_promotion_guard")
    return blockers


def _recommendation(
    *,
    spec_ready_for_runtime_slice: bool,
    promotion_blocked_by: list[str],
) -> str:
    if spec_ready_for_runtime_slice:
        return (
            "Spec is ready as the next runtime implementation contract, but runtime "
            "promotion remains deliberately guarded until that separate slice lands "
            "with tests and B5A rerun evidence."
        )
    return (
        "Do not implement runtime promotion yet; resolve blockers first: "
        + ", ".join(promotion_blocked_by)
    )


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
    return {"check_id": check_id, "status": status, "detail": detail}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
