from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import now_iso
from src.search.phase3b.forced_anchor.master import (
    DEFAULT_CAMPAIGN_STATE_PATH,
    DEFAULT_CANDIDATE,
    _build_exact_overlay,
    _candidate_ghost_rect,
    _check,
    _display_path,
    _file_hash,
    _load_json_mapping,
    _mapping,
    _resolve_path,
    _selected_anchor_indices,
    _solve_forced_anchor_clone,
)

FORCED_ANCHOR_SOLVER_MATRIX_SOURCE = "phase3b_forced_anchor_solver_matrix_v1"
DEFAULT_SEARCH_BRANCHINGS = ("fixed", "automatic", "portfolio")


def build_phase3b_forced_anchor_solver_matrix(
    project_root: Path,
    *,
    campaign_state_path: Optional[Path] = None,
    candidate: str = DEFAULT_CANDIDATE,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    sample_limit: int = 1,
    anchor_indices: Optional[Sequence[int]] = None,
    time_limit_seconds: float = 20.0,
    worker_count: int = 4,
    search_branchings: Sequence[str] = DEFAULT_SEARCH_BRANCHINGS,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    candidate_key = str(candidate)
    campaign_path = _resolve_path(
        project_root,
        campaign_state_path if campaign_state_path is not None else DEFAULT_CAMPAIGN_STATE_PATH,
    )
    before_hash = _file_hash(campaign_path)
    state, state_error = _load_json_mapping(campaign_path)
    candidates = _mapping(state.get("candidates")) if state else {}
    record = _mapping(candidates.get(candidate_key))
    proof_summary = _mapping(record.get("proof_summary"))
    failure_attribution = _mapping(proof_summary.get("master_start_failure_attribution"))
    failed_anchor_samples = [
        entry
        for entry in list(failure_attribution.get("failed_anchor_samples", []))
        if isinstance(entry, Mapping)
    ]
    selected_anchor_indices = _selected_anchor_indices(
        failed_anchor_samples,
        sample_limit,
        explicit_anchor_indices=anchor_indices,
    )
    normalized_branchings = _normalize_branchings(search_branchings)
    ghost_rect = _candidate_ghost_rect(candidate_key, record)

    status: Dict[str, Any] = {
        "completed": False,
        "evaluated": False,
        "outcome": "not_started",
        "recommendation": "Forced-anchor solver matrix has not run.",
    }
    matrix_entries: list[Dict[str, Any]] = []
    timing: Dict[str, float] = {}
    model_error: Optional[str] = None
    started = time.perf_counter()

    if state is None or state_error is not None:
        status.update(
            {
                "completed": True,
                "outcome": "campaign_state_missing",
                "recommendation": "Campaign state is missing or invalid; run B5A before forced-anchor solver-matrix profiling.",
            }
        )
    elif not record:
        status.update(
            {
                "completed": True,
                "outcome": "candidate_missing",
                "recommendation": "Candidate is not present in campaign state; choose a recorded blocker candidate.",
            }
        )
    elif not selected_anchor_indices:
        status.update(
            {
                "completed": True,
                "outcome": "forced_anchor_samples_missing",
                "recommendation": "Candidate has no failed-anchor samples; rerun B5A with failed-anchor sampling enabled.",
            }
        )
    else:
        try:
            overlay_started = time.perf_counter()
            model, base_proto = _build_exact_overlay(
                project_root,
                ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
                master_search_profile=master_search_profile,
            )
            timing["overlay_build_seconds"] = float(time.perf_counter() - overlay_started)
            solve_started = time.perf_counter()
            for anchor_idx in selected_anchor_indices:
                u_var = model.u_vars.get(int(anchor_idx))
                if u_var is None:
                    for branching in normalized_branchings:
                        matrix_entries.append(
                            {
                                "anchor_idx": int(anchor_idx),
                                "search_branching": str(branching),
                                "evaluated": False,
                                "status": "SKIPPED",
                                "skip_reason": "anchor_not_in_model_u_vars",
                            }
                        )
                    continue
                for branching in normalized_branchings:
                    entry = _solve_forced_anchor_clone(
                        base_proto,
                        u_var_index=int(u_var.Index()),
                        anchor_idx=int(anchor_idx),
                        time_limit_seconds=float(time_limit_seconds),
                        worker_count=int(worker_count),
                        search_branching=str(branching),
                    )
                    entry["search_branching"] = str(branching)
                    matrix_entries.append(entry)
            timing["matrix_solve_seconds"] = float(time.perf_counter() - solve_started)
            status.update(_status_from_entries(matrix_entries))
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
            status.update(
                {
                    "completed": True,
                    "evaluated": False,
                    "outcome": "diagnostic_error",
                    "recommendation": "Forced-anchor solver matrix failed; inspect model_error before using this evidence.",
                }
            )

    timing["total_seconds"] = float(time.perf_counter() - started)
    after_hash = _file_hash(campaign_path)
    campaign_state_unchanged = before_hash == after_hash
    return {
        "metadata": {
            "source": FORCED_ANCHOR_SOLVER_MATRIX_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
            "campaign_state": _display_path(project_root, campaign_path),
        },
        "candidate": {
            "key": candidate_key,
            "ghost_rect": ghost_rect,
            "campaign_status": record.get("status") if record else None,
            "attempts": int(record.get("attempts", 0)) if record else 0,
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "sample_limit": int(sample_limit),
            "selected_anchor_indices": [int(idx) for idx in selected_anchor_indices],
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "search_branchings": list(normalized_branchings),
        },
        "input_evidence": {
            "campaign_present": state is not None and state_error is None,
            "campaign_load_error": state_error,
            "candidate_present": bool(record),
            "failed_anchor_count": int(
                failure_attribution.get("failed_anchor_count", 0)
            )
            if failure_attribution
            else 0,
            "failed_anchor_sample_count": len(failed_anchor_samples),
        },
        "status": status,
        "matrix": {
            "entries": matrix_entries,
            "status_counts": _status_counts(matrix_entries),
            "status_counts_by_branching": _status_counts_by_key(
                matrix_entries,
                "search_branching",
            ),
            "status_counts_by_anchor": _status_counts_by_key(
                matrix_entries,
                "anchor_idx",
            ),
            "unknown_diagnostics": _unknown_diagnostics(matrix_entries),
        },
        "timing": timing,
        "model_error": model_error,
        "campaign_state_unchanged": bool(campaign_state_unchanged),
        "checks": _checks(
            state_present=state is not None and state_error is None,
            candidate_present=bool(record),
            selected_anchor_count=len(selected_anchor_indices),
            status=status,
            campaign_state_unchanged=campaign_state_unchanged,
            model_error=model_error,
        ),
    }


def render_phase3b_forced_anchor_solver_matrix_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    profile = _mapping(report.get("profile"))
    matrix = _mapping(report.get("matrix"))
    lines = [
        "# Phase 3B Forced-Anchor Solver Matrix",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Evaluated: {bool(status.get('evaluated', False))}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Time limit: {profile.get('time_limit_seconds')}s",
        f"- Branchings: {', '.join(str(item) for item in list(profile.get('search_branchings', [])))}",
        f"- Status counts: {matrix.get('status_counts', {})}",
        f"- Zero-branch UNKNOWN entries: {_mapping(matrix.get('unknown_diagnostics')).get('zero_branch_unknown_count', 0)}",
        f"- Campaign state unchanged: {bool(report.get('campaign_state_unchanged', False))}",
        "",
        "## Matrix",
        "",
        "| Anchor | Branching | Status | Wall | Branches | Conflicts |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in list(matrix.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("anchor_idx")),
                    _markdown_cell(entry.get("search_branching")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("wall_time")),
                    _markdown_cell(entry.get("branches")),
                    _markdown_cell(entry.get("conflicts")),
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


def render_phase3b_forced_anchor_solver_matrix_text(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    matrix = _mapping(report.get("matrix"))
    lines = [
        "Phase 3B forced-anchor solver matrix",
        f"candidate={candidate.get('key')}",
        f"evaluated={bool(status.get('evaluated', False))}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"status_counts={matrix.get('status_counts', {})}",
        f"zero_branch_unknown_count={_mapping(matrix.get('unknown_diagnostics')).get('zero_branch_unknown_count', 0)}",
        f"campaign_state_unchanged={bool(report.get('campaign_state_unchanged', False))}",
    ]
    for entry in list(matrix.get("entries", [])):
        if isinstance(entry, Mapping):
            lines.append(
                "entry "
                f"anchor={entry.get('anchor_idx')} "
                f"branching={entry.get('search_branching')} "
                f"status={entry.get('status')} "
                f"wall={entry.get('wall_time')} "
                f"branches={entry.get('branches')} "
                f"conflicts={entry.get('conflicts')}"
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


def _normalize_branchings(search_branchings: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in search_branchings:
        token = str(raw).strip().lower()
        if not token:
            continue
        if token not in {"fixed", "automatic", "portfolio"}:
            raise ValueError(f"Unsupported search branching {raw!r}")
        if token in seen:
            continue
        seen.add(token)
        result.append(token)
    return tuple(result or DEFAULT_SEARCH_BRANCHINGS)


def _status_from_entries(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    evaluated = [entry for entry in entries if bool(entry.get("evaluated", False))]
    counts = _status_counts(evaluated)
    unknown_diagnostics = _unknown_diagnostics(evaluated)
    if not entries:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "no_matrix_entries",
            "status_counts": counts,
            "recommendation": "No solver-matrix entries were evaluated.",
        }
    if any(str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"} for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "matrix_feasible_found",
            "status_counts": counts,
            "recommendation": "At least one solver configuration found a feasible forced anchor; inspect that entry before changing runtime behavior.",
        }
    if evaluated and all(str(entry.get("status")) == "INFEASIBLE" for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "matrix_all_infeasible",
            "status_counts": counts,
            "recommendation": "All evaluated solver-matrix entries are infeasible.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "matrix_unknown_remaining",
        "status_counts": counts,
        "recommendation": (
            "UNKNOWN entries are zero-branch/zero-conflict; triage presolve or "
            "model-building bottlenecks by anchor."
            if int(unknown_diagnostics.get("zero_branch_unknown_count", 0)) > 0
            else "Some solver-matrix entries remain UNKNOWN or skipped; triage by branching mode and anchor."
        ),
    }


def _status_counts(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status", "UNKNOWN"))
        counts[status] = int(counts.get(status, 0)) + 1
    return counts


def _status_counts_by_key(
    entries: Sequence[Mapping[str, Any]],
    key_name: str,
) -> Dict[str, Dict[str, int]]:
    grouped: Dict[str, Dict[str, int]] = {}
    for entry in entries:
        key = str(entry.get(key_name))
        status = str(entry.get("status", "UNKNOWN"))
        bucket = grouped.setdefault(key, {})
        bucket[status] = int(bucket.get(status, 0)) + 1
    return grouped


def _unknown_diagnostics(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    unknown_entries = [
        entry
        for entry in entries
        if bool(entry.get("evaluated", False)) and str(entry.get("status")) == "UNKNOWN"
    ]
    zero_branch_unknowns = [
        entry
        for entry in unknown_entries
        if _number_or_zero(entry.get("branches")) == 0
        and _number_or_zero(entry.get("conflicts")) == 0
    ]
    return {
        "unknown_count": int(len(unknown_entries)),
        "zero_branch_unknown_count": int(len(zero_branch_unknowns)),
        "zero_branch_unknown_by_anchor": _count_entries_by_key(
            zero_branch_unknowns,
            "anchor_idx",
        ),
        "zero_branch_unknown_by_branching": _count_entries_by_key(
            zero_branch_unknowns,
            "search_branching",
        ),
        "zero_branch_unknown_samples": [
            {
                "anchor_idx": entry.get("anchor_idx"),
                "search_branching": entry.get("search_branching"),
                "wall_time": entry.get("wall_time"),
                "branches": entry.get("branches"),
                "conflicts": entry.get("conflicts"),
            }
            for entry in zero_branch_unknowns[:8]
        ],
    }


def _count_entries_by_key(
    entries: Sequence[Mapping[str, Any]],
    key_name: str,
) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        key = str(entry.get(key_name))
        counts[key] = int(counts.get(key, 0)) + 1
    return counts


def _number_or_zero(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _checks(
    *,
    state_present: bool,
    candidate_present: bool,
    selected_anchor_count: int,
    status: Mapping[str, Any],
    campaign_state_unchanged: bool,
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    return [
        _check(
            "campaign_state_present",
            "pass" if state_present else "fail",
            "campaign state loaded" if state_present else "campaign state missing",
        ),
        _check(
            "candidate_present",
            "pass" if candidate_present else "fail",
            "candidate loaded" if candidate_present else "candidate missing",
        ),
        _check(
            "forced_anchor_samples_present",
            "pass" if selected_anchor_count > 0 else "fail",
            f"selected_anchor_count={int(selected_anchor_count)}",
        ),
        _check(
            "solver_matrix_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "campaign_state_unchanged",
            "pass" if campaign_state_unchanged else "fail",
            "campaign state hash unchanged"
            if campaign_state_unchanged
            else "campaign state changed during diagnostic",
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _markdown_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")
