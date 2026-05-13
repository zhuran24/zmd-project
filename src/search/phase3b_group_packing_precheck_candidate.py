from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from src.search.exact_campaign import now_iso

GROUP_PACKING_PRECHECK_CANDIDATE_SOURCE = (
    "phase3b_group_packing_precheck_candidate_v1"
)
START_COMPATIBILITY_SOURCE = "phase3b_start_compatibility_diagnostics_v1"
DEFAULT_START_COMPATIBILITY_PATH = Path(
    ".artifacts/phase3b_start_compatibility/start_compatibility_69x19.json"
)


def build_phase3b_group_packing_precheck_candidate_summary(
    project_root: Path,
    *,
    start_compatibility_path: Optional[Path] = None,
    min_sample_count: int = 3,
    min_blocker_count: int = 1,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    input_path = _resolve_path(
        project_root,
        start_compatibility_path
        if start_compatibility_path is not None
        else DEFAULT_START_COMPATIBILITY_PATH,
    )
    diagnostics, load_error = _load_json_mapping(input_path)
    metadata = _mapping(diagnostics.get("metadata")) if diagnostics else {}
    candidate = _mapping(diagnostics.get("candidate")) if diagnostics else {}
    status = _mapping(diagnostics.get("status")) if diagnostics else {}
    diag = _mapping(diagnostics.get("diagnostics")) if diagnostics else {}
    group_packing_probe = _mapping(diag.get("group_packing_probe"))
    group_packing_blockers = _mapping(diag.get("group_packing_blockers"))
    blockers = [
        dict(entry)
        for entry in list(group_packing_blockers.get("blockers", []))
        if isinstance(entry, Mapping)
    ]
    sample_count = int(group_packing_probe.get("sample_count", 0))
    feasible_count = int(group_packing_probe.get("feasible_count", 0))
    unknown_count = int(group_packing_probe.get("unknown_count", 0))
    skipped_count = int(group_packing_probe.get("skipped_count", 0))
    blocker_count = int(group_packing_blockers.get("blocker_count", len(blockers)))
    design_gate_passed = bool(
        diagnostics is not None
        and load_error is None
        and metadata.get("source") == START_COMPATIBILITY_SOURCE
        and bool(group_packing_probe.get("enabled", False))
        and bool(group_packing_blockers.get("precheck_design_candidate", False))
        and sample_count >= int(min_sample_count)
        and blocker_count >= int(min_blocker_count)
        and feasible_count == 0
        and unknown_count == 0
        and skipped_count == 0
    )
    runtime_promotion_ready = False
    checks = [
        _check(
            "start_compatibility_present",
            "pass" if diagnostics is not None and load_error is None else "fail",
            "start-compatibility report loaded"
            if diagnostics is not None and load_error is None
            else load_error or f"missing:{_display_path(project_root, input_path)}",
        ),
        _check(
            "start_compatibility_schema",
            "pass" if metadata.get("source") == START_COMPATIBILITY_SOURCE else "fail",
            "supported start-compatibility schema"
            if metadata.get("source") == START_COMPATIBILITY_SOURCE
            else f"unsupported source:{metadata.get('source')}",
        ),
        _check(
            "group_packing_probe_enabled",
            "pass" if bool(group_packing_probe.get("enabled", False)) else "fail",
            "group packing probe was enabled"
            if bool(group_packing_probe.get("enabled", False))
            else "group packing probe disabled or missing",
        ),
        _check(
            "minimum_sample_count",
            "pass" if sample_count >= int(min_sample_count) else "fail",
            f"sample_count={sample_count}; required>={int(min_sample_count)}",
        ),
        _check(
            "minimum_blocker_count",
            "pass" if blocker_count >= int(min_blocker_count) else "fail",
            f"blocker_count={blocker_count}; required>={int(min_blocker_count)}",
        ),
        _check(
            "no_feasible_group_packing_sample",
            "pass" if feasible_count == 0 else "fail",
            f"feasible_count={feasible_count}",
        ),
        _check(
            "no_unknown_group_packing_sample",
            "pass" if unknown_count == 0 else "fail",
            f"unknown_count={unknown_count}",
        ),
        _check(
            "no_skipped_group_packing_sample",
            "pass" if skipped_count == 0 else "fail",
            f"skipped_count={skipped_count}",
        ),
        _check(
            "diagnostic_precheck_design_candidate",
            "pass"
            if bool(group_packing_blockers.get("precheck_design_candidate", False))
            else "fail",
            "diagnostic blocker evidence is internally consistent"
            if bool(group_packing_blockers.get("precheck_design_candidate", False))
            else "group_packing_blockers did not mark precheck_design_candidate",
        ),
        _check(
            "runtime_promotion_guard",
            "fail",
            (
                "sampled diagnostic evidence is not terminal proof; broaden coverage "
                "and add runtime tests before promoting to pre-master eliminator"
            ),
        ),
    ]
    return {
        "metadata": {
            "source": GROUP_PACKING_PRECHECK_CANDIDATE_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
            "start_compatibility": _display_path(project_root, input_path),
        },
        "candidate": dict(candidate),
        "input_status": dict(status),
        "gate": {
            "design_gate_passed": bool(design_gate_passed),
            "runtime_promotion_ready": bool(runtime_promotion_ready),
            "min_sample_count": int(min_sample_count),
            "min_blocker_count": int(min_blocker_count),
            "recommendation": _recommendation(
                design_gate_passed=design_gate_passed,
                sample_count=sample_count,
                blocker_count=blocker_count,
                feasible_count=feasible_count,
                unknown_count=unknown_count,
                skipped_count=skipped_count,
            ),
            "promotion_requirements": [
                "Broaden sampling beyond the current failed-anchor sample set.",
                "Add deterministic runtime tests before any pre-master eliminator promotion.",
                "Keep terminal proof source unchanged; this report is diagnostic evidence only.",
                "Re-run B5A after any runtime precheck change before production acceptance.",
            ],
        },
        "group_packing_probe": {
            "enabled": bool(group_packing_probe.get("enabled", False)),
            "sample_count": sample_count,
            "feasible_count": feasible_count,
            "infeasible_count": int(group_packing_probe.get("infeasible_count", 0)),
            "unknown_count": unknown_count,
            "skipped_count": skipped_count,
        },
        "group_packing_blockers": {
            "blocker_count": blocker_count,
            "precheck_design_candidate": bool(
                group_packing_blockers.get("precheck_design_candidate", False)
            ),
            "blockers": blockers,
        },
        "checks": checks,
    }


def render_phase3b_group_packing_precheck_candidate_markdown(
    summary: Mapping[str, Any],
) -> str:
    candidate = _mapping(summary.get("candidate"))
    gate = _mapping(summary.get("gate"))
    blockers = [
        entry
        for entry in list(_mapping(summary.get("group_packing_blockers")).get("blockers", []))
        if isinstance(entry, Mapping)
    ]
    lines = [
        "# Phase 3B Group Packing Precheck Candidate Gate",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Design gate passed: {bool(gate.get('design_gate_passed', False))}",
        f"- Runtime promotion ready: {bool(gate.get('runtime_promotion_ready', False))}",
        f"- Recommendation: {gate.get('recommendation')}",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in list(summary.get("checks", [])):
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
    if blockers:
        lines.extend(
            [
                "",
                "## Blockers",
                "",
                "| Group | Status | Samples | Anchors | Required | Surviving | Greedy |",
                "| --- | --- | --- | --- | --- | --- | --- |",
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
                        _markdown_cell(",".join(str(idx) for idx in list(entry.get("anchor_indices", [])))),
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
    requirements = [
        str(item) for item in list(gate.get("promotion_requirements", []))
    ]
    if requirements:
        lines.extend(["", "## Promotion Requirements", ""])
        lines.extend(f"- {item}" for item in requirements)
    return "\n".join(lines) + "\n"


def render_phase3b_group_packing_precheck_candidate_text(
    summary: Mapping[str, Any],
) -> str:
    candidate = _mapping(summary.get("candidate"))
    gate = _mapping(summary.get("gate"))
    blockers = _mapping(summary.get("group_packing_blockers"))
    lines = [
        "Phase 3B group packing precheck candidate gate",
        f"candidate={candidate.get('key')}",
        f"design_gate_passed={bool(gate.get('design_gate_passed', False))}",
        f"runtime_promotion_ready={bool(gate.get('runtime_promotion_ready', False))}",
        f"recommendation={gate.get('recommendation')}",
        f"blocker_count={blockers.get('blocker_count', 0)}",
    ]
    for check in list(summary.get("checks", [])):
        if not isinstance(check, Mapping):
            continue
        lines.append(
            "check "
            f"id={check.get('check_id')} "
            f"status={check.get('status')} "
            f"detail={check.get('detail')}"
        )
    for entry in list(blockers.get("blockers", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "blocker "
            f"group={entry.get('group_id')} "
            f"status={entry.get('solver_status')} "
            f"samples={entry.get('sample_count')} "
            f"anchors={','.join(str(idx) for idx in list(entry.get('anchor_indices', [])))} "
            f"required={entry.get('required_count_min')}..{entry.get('required_count_max')} "
            f"surviving={entry.get('surviving_at_failure_min')}..{entry.get('surviving_at_failure_max')} "
            f"greedy={entry.get('greedy_selected_min')}..{entry.get('greedy_selected_max')}"
        )
    return "\n".join(lines) + "\n"


def _recommendation(
    *,
    design_gate_passed: bool,
    sample_count: int,
    blocker_count: int,
    feasible_count: int,
    unknown_count: int,
    skipped_count: int,
) -> str:
    if not design_gate_passed:
        return (
            "Do not promote: evidence is incomplete "
            f"(samples={sample_count}, blockers={blocker_count}, feasible={feasible_count}, "
            f"unknown={unknown_count}, skipped={skipped_count})."
        )
    return (
        "Design candidate only: sampled group packing is exact-infeasible and internally "
        "consistent, but runtime pre-master promotion remains blocked until broader coverage "
        "and tests exist."
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
