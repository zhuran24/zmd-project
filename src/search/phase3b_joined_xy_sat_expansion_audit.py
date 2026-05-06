from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from src.search.exact_campaign import now_iso
from src.search.phase3b_forced_anchor_master import _check, _display_path, _mapping
from src.search.phase3b_grouped_xy_sat_expansion_audit import (
    _as_float,
    _cell,
    _metrics,
    _parse_case,
    _ratio,
    _round,
)

JOINED_XY_SAT_EXPANSION_AUDIT_SOURCE = "phase3b_joined_xy_sat_expansion_audit_v1"

DEFAULT_LOG_CASES = (
    {
        "case_id": "active_guard_anchor118_45s",
        "family": "active_guard",
        "anchor_idx": 118,
        "log_path": Path(".codex_test_logs/phase3b/active_guard_anchor118_base_45s_20260423.log"),
    },
    {
        "case_id": "active_guard_anchor119_300s",
        "family": "active_guard",
        "anchor_idx": 119,
        "log_path": Path(
            ".codex_test_logs/phase3b/block_element_presolve_traces/"
            "active_guard_anchor119_300s_20260423.log"
        ),
    },
    {
        "case_id": "grouped_xy_anchor118_120s",
        "family": "grouped_xy",
        "anchor_idx": 118,
        "log_path": Path(".codex_test_logs/phase3b/grouped_xy_probe_anchor118_120s_20260423.log"),
    },
    {
        "case_id": "grouped_xy_anchor119_120s",
        "family": "grouped_xy",
        "anchor_idx": 119,
        "log_path": Path(".codex_test_logs/phase3b/grouped_xy_probe_anchor119_120s_20260423.log"),
    },
    {
        "case_id": "joined_xy_anchor118_60s",
        "family": "joined_xy",
        "anchor_idx": 118,
        "log_path": Path(".codex_test_logs/phase3b/joined_xy_probe_anchor118_60s_20260423.log"),
    },
    {
        "case_id": "joined_xy_anchor118_60s_seed2",
        "family": "joined_xy",
        "anchor_idx": 118,
        "log_path": Path(".codex_test_logs/phase3b/joined_xy_probe_anchor118_60s_seed2_20260423.log"),
    },
    {
        "case_id": "joined_xy_anchor119_120s",
        "family": "joined_xy",
        "anchor_idx": 119,
        "log_path": Path(".codex_test_logs/phase3b/joined_xy_probe_anchor119_120s_20260423.log"),
    },
)


def build_phase3b_joined_xy_sat_expansion_audit(
    project_root: Path,
    *,
    log_cases: Optional[Sequence[Mapping[str, Any]]] = None,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    started = time.perf_counter()
    cases = [
        _parse_case(project_root, case)
        for case in (log_cases or DEFAULT_LOG_CASES)
    ]
    comparison = _comparison(cases)
    outcome = (
        "joined_xy_sat_expansion_recovered_active_guard_scale"
        if bool(comparison.get("joined_xy_recovered_active_guard_scale", False))
        else (
            "joined_xy_sat_expansion_audit_incomplete"
            if any(not bool(case.get("present", False)) for case in cases)
            else "joined_xy_sat_expansion_needs_followup"
        )
    )
    report: dict[str, Any] = {
        "metadata": {
            "source": JOINED_XY_SAT_EXPANSION_AUDIT_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "presolve_sat_expansion_audit_not_proof",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "paths": {"project_root": _display_path(project_root, project_root)},
        "status": {
            "completed": True,
            "evaluated": all(bool(case.get("present", False)) for case in cases),
            "outcome": outcome,
            "recommendation": _recommendation(comparison),
        },
        "cases": cases,
        "comparison": comparison,
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }
    report["checks"] = _checks(report, cases)
    return report


def render_phase3b_joined_xy_sat_expansion_audit_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    lines = [
        "# Phase 3B Joined-XY SAT Expansion Audit",
        "",
        "- Diagnostic semantics: presolve_sat_expansion_audit_not_proof",
        f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        f"- proof_source: {bool(_mapping(report.get('metadata')).get('proof_source', True))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Cases",
        "",
        "| Case | Status | Initial Vars | Initial Element | Presolved Vars | New Bool Integer | SAT Booleans | Branches | Conflicts | Conflicts / 1k Branches |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in list(report.get("cases", [])):
        if not isinstance(case, Mapping):
            continue
        metrics = _mapping(case.get("metrics"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(case.get("case_id")),
                    _cell(metrics.get("status")),
                    _cell(metrics.get("initial_variables")),
                    _cell(metrics.get("initial_kElement")),
                    _cell(metrics.get("presolved_variables")),
                    _cell(metrics.get("new_bool_integer_encoding")),
                    _cell(metrics.get("sat_booleans")),
                    _cell(metrics.get("branches")),
                    _cell(metrics.get("conflicts")),
                    _cell(_round(metrics.get("conflicts_per_1k_branches"))),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Comparison",
            "",
            f"- Joined/active integer encoding ratio: {comparison.get('joined_to_active_integer_encoding_ratio')}",
            f"- Joined/grouped integer encoding ratio: {comparison.get('joined_to_grouped_integer_encoding_ratio')}",
            f"- Joined/active SAT booleans ratio: {comparison.get('joined_to_active_sat_boolean_ratio')}",
            f"- Joined/grouped SAT booleans ratio: {comparison.get('joined_to_grouped_sat_boolean_ratio')}",
            f"- Anchor118 terminal reproduced: {comparison.get('anchor118_terminal_reproduced')}",
            f"- Anchor119 search progress: {comparison.get('joined_anchor119_search_progress')}",
            f"- Recommended next action: {comparison.get('recommended_next_action')}",
            "",
            "## Checks",
            "",
            "| Check | Status | Detail |",
            "| --- | --- | --- |",
        ]
    )
    for check in list(report.get("checks", [])):
        if isinstance(check, Mapping):
            lines.append(
                "| "
                + " | ".join(
                    [
                        _cell(check.get("check_id")),
                        _cell(check.get("status")),
                        _cell(check.get("detail")),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def render_phase3b_joined_xy_sat_expansion_audit_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    return "\n".join(
        [
            "phase3b joined-xy sat expansion audit",
            "diagnostic_semantics=presolve_sat_expansion_audit_not_proof",
            f"solver_invoked={bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
            f"proof_source={bool(_mapping(report.get('metadata')).get('proof_source', True))}",
            f"outcome={status.get('outcome')}",
            f"joined_xy_recovered_active_guard_scale={comparison.get('joined_xy_recovered_active_guard_scale')}",
            f"joined_to_grouped_integer_encoding_ratio={comparison.get('joined_to_grouped_integer_encoding_ratio')}",
            f"joined_to_grouped_sat_boolean_ratio={comparison.get('joined_to_grouped_sat_boolean_ratio')}",
            f"anchor118_terminal_reproduced={comparison.get('anchor118_terminal_reproduced')}",
        ]
    ) + "\n"


def _comparison(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_case = {str(case.get("case_id")): case for case in cases}
    active118 = _metrics(by_case.get("active_guard_anchor118_45s"))
    active119 = _metrics(by_case.get("active_guard_anchor119_300s"))
    grouped118 = _metrics(by_case.get("grouped_xy_anchor118_120s"))
    grouped119 = _metrics(by_case.get("grouped_xy_anchor119_120s"))
    joined118 = _metrics(by_case.get("joined_xy_anchor118_60s"))
    joined118_seed2 = _metrics(by_case.get("joined_xy_anchor118_60s_seed2"))
    joined119 = _metrics(by_case.get("joined_xy_anchor119_120s"))
    joined_to_active_integer = _ratio(
        _as_float(joined119.get("new_bool_integer_encoding")),
        _as_float(active119.get("new_bool_integer_encoding")),
    )
    joined_to_grouped_integer = _ratio(
        _as_float(joined119.get("new_bool_integer_encoding")),
        _as_float(grouped119.get("new_bool_integer_encoding")),
    )
    joined_to_active_booleans = _ratio(
        _as_float(joined119.get("sat_booleans")),
        _as_float(active119.get("sat_booleans")),
    )
    joined_to_grouped_booleans = _ratio(
        _as_float(joined119.get("sat_booleans")),
        _as_float(grouped119.get("sat_booleans")),
    )
    joined_density = _as_float(joined119.get("conflicts_per_1k_branches"))
    grouped_density = _as_float(grouped119.get("conflicts_per_1k_branches"))
    active118_terminal = active118.get("status") in {"INFEASIBLE", "OPTIMAL", "FEASIBLE"}
    grouped118_terminal = grouped118.get("status") in {"INFEASIBLE", "OPTIMAL", "FEASIBLE"}
    joined118_terminal = joined118.get("status") in {"INFEASIBLE", "OPTIMAL", "FEASIBLE"}
    joined118_seed2_terminal = joined118_seed2.get("status") in {"INFEASIBLE", "OPTIMAL", "FEASIBLE"}
    anchor118_terminal_reproduced = bool(
        active118_terminal
        and joined118_terminal
        and joined118_seed2_terminal
        and not grouped118_terminal
    )
    joined119_progress = bool(
        joined119.get("status") == "UNKNOWN"
        and _as_float(joined119.get("branches")) not in (None, 0)
        and _as_float(joined119.get("conflicts")) not in (None, 0)
    )
    active_like = bool(
        (joined_to_active_integer or 999.0) <= 1.5
        and (joined_to_active_booleans or 999.0) <= 1.5
    )
    grouped_reduced = bool(
        (joined_to_grouped_integer or 999.0) < 0.1
        and (joined_to_grouped_booleans or 999.0) < 0.25
    )
    density_recovered = bool(
        joined_density is not None
        and grouped_density is not None
        and joined_density > grouped_density * 100.0
    )
    recovered = bool(
        active_like
        and grouped_reduced
        and anchor118_terminal_reproduced
        and joined119_progress
        and density_recovered
    )
    return {
        "joined_xy_recovered_active_guard_scale": bool(recovered),
        "joined_to_active_integer_encoding_ratio": joined_to_active_integer,
        "joined_to_grouped_integer_encoding_ratio": joined_to_grouped_integer,
        "joined_to_active_sat_boolean_ratio": joined_to_active_booleans,
        "joined_to_grouped_sat_boolean_ratio": joined_to_grouped_booleans,
        "joined_anchor119_conflicts_per_1k_branches": joined_density,
        "grouped_anchor119_conflicts_per_1k_branches": grouped_density,
        "anchor118_terminal_reproduced": bool(anchor118_terminal_reproduced),
        "anchor118_seed2_terminal_reproduced": bool(joined118_seed2_terminal),
        "joined_anchor119_search_progress": bool(joined119_progress),
        "recommended_next_action": (
            "run_joined_xy_anchor118_seed2_then_control_anchor125_before_broader_claim"
            if recovered
            else "inspect_joined_xy_sat_expansion_gap_before_more_solver_time"
        ),
        "interpretation": (
            "Joined-XY avoids the grouped flattened selector SAT expansion while preserving "
            "ActiveGuard-scale integer encoding and recovering the anchor118 terminal signal."
        )
        if recovered
        else "Joined-XY needs more diagnostic comparison before claiming SAT expansion recovery.",
    }


def _checks(
    report: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    metadata = _mapping(report.get("metadata"))
    comparison = _mapping(report.get("comparison"))
    return [
        _check("solver_not_invoked", "pass" if not bool(metadata.get("solver_invoked", True)) else "fail", "solver_invoked=false"),
        _check("proof_source_false", "pass" if not bool(metadata.get("proof_source", True)) else "fail", "proof_source=false"),
        _check("all_logs_present", "pass" if all(bool(case.get("present", False)) for case in cases) else "fail", f"present={sum(1 for case in cases if bool(case.get('present', False)))}/{len(cases)}"),
        _check("joined_active_like_integer_encoding", "pass" if _as_float(comparison.get("joined_to_active_integer_encoding_ratio")) is not None and _as_float(comparison.get("joined_to_active_integer_encoding_ratio")) <= 1.5 else "fail", str(comparison.get("joined_to_active_integer_encoding_ratio"))),
        _check("joined_reduces_grouped_integer_encoding", "pass" if _as_float(comparison.get("joined_to_grouped_integer_encoding_ratio")) is not None and _as_float(comparison.get("joined_to_grouped_integer_encoding_ratio")) < 0.1 else "fail", str(comparison.get("joined_to_grouped_integer_encoding_ratio"))),
        _check("joined_reduces_grouped_sat_booleans", "pass" if _as_float(comparison.get("joined_to_grouped_sat_boolean_ratio")) is not None and _as_float(comparison.get("joined_to_grouped_sat_boolean_ratio")) < 0.25 else "fail", str(comparison.get("joined_to_grouped_sat_boolean_ratio"))),
        _check("anchor118_terminal_reproduced", "pass" if bool(comparison.get("anchor118_terminal_reproduced", False)) else "fail", str(comparison.get("anchor118_terminal_reproduced"))),
        _check("anchor118_seed2_terminal_reproduced", "pass" if bool(comparison.get("anchor118_seed2_terminal_reproduced", False)) else "fail", str(comparison.get("anchor118_seed2_terminal_reproduced"))),
        _check("joined_anchor119_search_progress", "pass" if bool(comparison.get("joined_anchor119_search_progress", False)) else "fail", str(comparison.get("joined_anchor119_search_progress"))),
    ]


def _recommendation(comparison: Mapping[str, Any]) -> str:
    if bool(comparison.get("joined_xy_recovered_active_guard_scale", False)):
        return (
            "Joined-XY looks like the current best default-off diagnostic formulation; "
            "next reproduce anchor118 with a second seed and run one control anchor before broader claims."
        )
    return "Joined-XY SAT expansion recovery is not fully established; inspect logs before more solver time."
