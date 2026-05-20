from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from src.search.exact_campaign import now_iso
from src.search.phase3b.forced_anchor.master import _check, _display_path, _mapping

GROUPED_XY_PROBE_SYNTHESIS_SOURCE = "phase3b_grouped_xy_probe_synthesis_v1"
DEFAULT_PROFILE_AUDIT_PATH = Path(
    ".artifacts/phase3b_grouped_block_xy_profile_audit_20260423/"
    "grouped_block_xy_profile_audit.json"
)
DEFAULT_GROUPED_PROBE_PATHS = (
    Path(
        ".artifacts/phase3b_grouped_xy_probe_anchor118_120s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    Path(
        ".artifacts/phase3b_grouped_xy_probe_anchor119_120s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
)
DEFAULT_COMPARATOR_PROBE_PATHS = (
    Path(
        ".artifacts/phase3b_active_guard_anchor118_base_45s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    Path(
        ".artifacts/phase3b_active_guard_probe_anchor119_300s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
    Path(
        ".artifacts/phase3b_active_guard_anchor125_base_300s_20260423/"
        "forced_anchor_proto_reduction.json"
    ),
)


def build_phase3b_grouped_xy_probe_synthesis(
    project_root: Path,
    *,
    profile_audit_path: Optional[Path] = None,
    grouped_probe_paths: Optional[Sequence[Path]] = None,
    comparator_probe_paths: Optional[Sequence[Path]] = None,
) -> dict[str, Any]:
    project_root = Path(project_root).resolve()
    started = time.perf_counter()
    profile_path = _resolve(project_root, profile_audit_path or DEFAULT_PROFILE_AUDIT_PATH)
    grouped_paths = [
        _resolve(project_root, path)
        for path in (grouped_probe_paths or DEFAULT_GROUPED_PROBE_PATHS)
    ]
    comparator_paths = [
        _resolve(project_root, path)
        for path in (comparator_probe_paths or DEFAULT_COMPARATOR_PROBE_PATHS)
    ]
    profile = _load_json(profile_path)
    grouped_payloads = [_load_json(path) for path in grouped_paths]
    comparator_payloads = [_load_json(path) for path in comparator_paths]
    grouped_entries = _entries(grouped_payloads, grouped_paths, project_root, "grouped_xy")
    comparator_entries = _entries(
        comparator_payloads, comparator_paths, project_root, "active_guard"
    )
    comparison = _comparison(profile, grouped_entries, comparator_entries)
    ready = bool(comparison.get("profile_valid")) and bool(
        comparison.get("grouped_has_search_progress")
    )
    terminal_regression = bool(comparison.get("anchor118_terminal_not_reproduced"))
    outcome = (
        "grouped_xy_search_progress_but_anchor118_terminal_not_reproduced"
        if ready and terminal_regression
        else (
            "grouped_xy_search_progress_ready_for_stability_probe"
            if ready
            else "grouped_xy_probe_synthesis_incomplete_or_blocked"
        )
    )
    report: dict[str, Any] = {
        "metadata": {
            "source": GROUPED_XY_PROBE_SYNTHESIS_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "forced_anchor_diagnostic_synthesis_not_proof",
            "solver_invoked": False,
            "proof_source": False,
            "candidate_elimination_claim": False,
        },
        "paths": {
            "project_root": _display_path(project_root, project_root),
            "profile_audit": _display_path(project_root, profile_path),
            "grouped_probe_paths": [_display_path(project_root, path) for path in grouped_paths],
            "comparator_probe_paths": [
                _display_path(project_root, path) for path in comparator_paths
            ],
        },
        "status": {
            "completed": True,
            "evaluated": bool(profile and grouped_entries and comparator_entries),
            "outcome": outcome,
            "recommendation": _recommendation(comparison),
        },
        "profile_summary": _profile_summary(profile),
        "grouped_entries": grouped_entries,
        "comparator_entries": comparator_entries,
        "comparison": comparison,
        "timing": {"total_seconds": float(time.perf_counter() - started)},
    }
    report["checks"] = _checks(report, profile, grouped_entries, comparator_entries)
    return report


def render_phase3b_grouped_xy_probe_synthesis_markdown(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    lines = [
        "# Phase 3B Grouped XY Probe Synthesis",
        "",
        "- Diagnostic semantics: forced_anchor_diagnostic_synthesis_not_proof",
        f"- solver_invoked: {bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
        f"- proof_source: {bool(_mapping(report.get('metadata')).get('proof_source', True))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Profile",
        "",
        f"- Profile valid: {comparison.get('profile_valid')}",
        f"- Block x/y target delta: {_mapping(report.get('profile_summary')).get('block_xy_target_delta')}",
        f"- Block element delta: {_mapping(report.get('profile_summary')).get('block_element_constraint_delta')}",
        "",
        "## Probe Entries",
        "",
        "| Family | Anchor | Status | Branches | Conflicts | Booleans | Wall | Deterministic | Classification |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in list(report.get("grouped_entries", [])) + list(report.get("comparator_entries", [])):
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(row.get("family")),
                    _cell(row.get("anchor_idx")),
                    _cell(row.get("status")),
                    _cell(row.get("branches")),
                    _cell(row.get("conflicts")),
                    _cell(row.get("booleans")),
                    _cell(row.get("wall_time")),
                    _cell(row.get("deterministic_time")),
                    _cell(row.get("classification")),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Comparison",
            "",
            f"- Grouped has search progress: {comparison.get('grouped_has_search_progress')}",
            f"- Grouped terminal count: {comparison.get('grouped_terminal_count')}",
            f"- Comparator terminal count: {comparison.get('comparator_terminal_count')}",
            f"- Anchor118 terminal not reproduced: {comparison.get('anchor118_terminal_not_reproduced')}",
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


def render_phase3b_grouped_xy_probe_synthesis_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    return "\n".join(
        [
            "phase3b grouped xy probe synthesis",
            "diagnostic_semantics=forced_anchor_diagnostic_synthesis_not_proof",
            f"solver_invoked={bool(_mapping(report.get('metadata')).get('solver_invoked', True))}",
            f"proof_source={bool(_mapping(report.get('metadata')).get('proof_source', True))}",
            f"outcome={status.get('outcome')}",
            f"grouped_has_search_progress={comparison.get('grouped_has_search_progress')}",
            f"anchor118_terminal_not_reproduced={comparison.get('anchor118_terminal_not_reproduced')}",
            f"recommended_next_action={comparison.get('recommended_next_action')}",
        ]
    ) + "\n"


def _entries(
    payloads: Sequence[Mapping[str, Any]],
    paths: Sequence[Path],
    project_root: Path,
    family: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for payload, path in zip(payloads, paths):
        for entry in list(_mapping(payload.get("reduction")).get("entries", [])):
            if not isinstance(entry, Mapping):
                continue
            stats = _mapping(entry.get("response_stats_parsed"))
            branches = _int(entry.get("branches"))
            conflicts = _int(entry.get("conflicts"))
            status = str(entry.get("status") or "")
            terminal = status in {"INFEASIBLE", "OPTIMAL", "FEASIBLE"}
            search_progress = bool(branches > 0 or conflicts > 0)
            rows.append(
                {
                    "family": str(family),
                    "source_path": _display_path(project_root, path),
                    "anchor_idx": entry.get("anchor_idx"),
                    "status": status,
                    "branches": branches,
                    "conflicts": conflicts,
                    "booleans": _int(stats.get("booleans")),
                    "propagations": _int(stats.get("propagations")),
                    "integer_propagations": _int(stats.get("integer_propagations")),
                    "wall_time": entry.get("wall_time"),
                    "deterministic_time": entry.get("deterministic_time"),
                    "terminal": terminal,
                    "search_progress": search_progress,
                    "classification": (
                        "terminal"
                        if terminal
                        else ("search_progress_unknown" if search_progress else "zero_branch_unknown")
                    ),
                    "model_error": entry.get("model_error"),
                }
            )
    return rows


def _comparison(
    profile: Mapping[str, Any],
    grouped_entries: Sequence[Mapping[str, Any]],
    comparator_entries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    profile_summary = _profile_summary(profile)
    grouped_terminal = [row for row in grouped_entries if bool(row.get("terminal"))]
    comparator_terminal = [row for row in comparator_entries if bool(row.get("terminal"))]
    grouped_progress = [
        row for row in grouped_entries if bool(row.get("search_progress"))
    ]
    grouped_anchor118 = [
        row for row in grouped_entries if str(row.get("anchor_idx")) == "118"
    ]
    comparator_anchor118_terminal = [
        row
        for row in comparator_entries
        if str(row.get("anchor_idx")) == "118" and bool(row.get("terminal"))
    ]
    anchor118_terminal_not_reproduced = bool(
        comparator_anchor118_terminal
        and grouped_anchor118
        and not any(bool(row.get("terminal")) for row in grouped_anchor118)
    )
    recommended = (
        "inspect_grouped_xy_sat_boolean_expansion_before_more_solver_time"
        if anchor118_terminal_not_reproduced
        else (
            "run_grouped_xy_anchor119_seed_stability_probe"
            if grouped_progress
            else "refresh_grouped_xy_profile_or_reduce_presolve_surface"
        )
    )
    return {
        "profile_valid": bool(profile_summary.get("grouped_xy_profile_valid", False)),
        "grouped_probe_count": int(len(grouped_entries)),
        "comparator_probe_count": int(len(comparator_entries)),
        "grouped_has_search_progress": bool(grouped_progress),
        "grouped_terminal_count": int(len(grouped_terminal)),
        "comparator_terminal_count": int(len(comparator_terminal)),
        "anchor118_terminal_not_reproduced": bool(anchor118_terminal_not_reproduced),
        "recommended_next_action": recommended,
    }


def _profile_summary(profile: Mapping[str, Any]) -> dict[str, Any]:
    comparison = _mapping(profile.get("comparison"))
    return {
        "grouped_xy_profile_valid": bool(
            comparison.get("grouped_xy_profile_valid", False)
        ),
        "block_xy_target_delta": comparison.get("block_xy_target_delta"),
        "block_element_constraint_delta": comparison.get("block_element_constraint_delta"),
        "selected_geometry_constraint_delta": comparison.get(
            "selected_geometry_constraint_delta"
        ),
        "no_pairwise_cover_literals": comparison.get("no_pairwise_cover_literals"),
    }


def _recommendation(comparison: Mapping[str, Any]) -> str:
    if bool(comparison.get("anchor118_terminal_not_reproduced", False)):
        return (
            "Stop adding grouped-XY solver time for now; inspect SAT boolean expansion "
            "and compare grouped vs active-guard presolved shapes."
        )
    if bool(comparison.get("grouped_has_search_progress", False)):
        return "Grouped-XY has search progress; run a small stability probe only if anchor gates pass."
    return "Grouped-XY evidence is incomplete; refresh probes before acting."


def _checks(
    report: Mapping[str, Any],
    profile: Mapping[str, Any],
    grouped_entries: Sequence[Mapping[str, Any]],
    comparator_entries: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    metadata = _mapping(report.get("metadata"))
    comparison = _mapping(report.get("comparison"))
    return [
        _check("solver_not_invoked_by_synthesis", "pass" if not bool(metadata.get("solver_invoked", True)) else "fail", "solver_invoked=false"),
        _check("proof_source_false", "pass" if not bool(metadata.get("proof_source", True)) else "fail", "proof_source=false"),
        _check("profile_present", "pass" if bool(profile) else "fail", f"present={bool(profile)}"),
        _check("grouped_entries_present", "pass" if bool(grouped_entries) else "fail", f"count={len(grouped_entries)}"),
        _check("comparator_entries_present", "pass" if bool(comparator_entries) else "fail", f"count={len(comparator_entries)}"),
        _check("grouped_search_progress", "pass" if bool(comparison.get("grouped_has_search_progress", False)) else "fail", str(comparison.get("grouped_has_search_progress"))),
        _check("anchor118_terminal_regression_recorded", "pass" if bool(comparison.get("anchor118_terminal_not_reproduced", False)) else "skipped", str(comparison.get("anchor118_terminal_not_reproduced"))),
    ]


def _resolve(project_root: Path, path: Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return project_root / path


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
