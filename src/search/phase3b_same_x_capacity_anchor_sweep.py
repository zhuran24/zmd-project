from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso
from src.search.phase3b_coordinate_validation_group_delta import (
    _build_delta_context,
    _candidate_rect,
    _check,
    _mapping,
)

PHASE3B_SAME_X_CAPACITY_ANCHOR_SWEEP_SOURCE = (
    "phase3b_same_x_capacity_anchor_sweep_v1"
)

SAME_X_CAPACITY_CONFLICT_REASON = "same_x_strip_fixed_ghost_capacity_conflict"
DEFAULT_SAME_X_CAPACITY_SWEEP_ANCHORS = tuple(range(118, 126))


def build_phase3b_same_x_capacity_anchor_sweep(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_indices: Optional[Sequence[int]] = None,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    time_limit_seconds: float = 2.0,
    worker_count: int = 1,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    anchors = _normalize_anchor_indices(anchor_indices or DEFAULT_SAME_X_CAPACITY_SWEEP_ANCHORS)
    started = time.perf_counter()
    entries: list[Dict[str, Any]] = []
    context: Dict[str, Any] = {}
    model_error: Optional[str] = None

    try:
        artifact_hashes = compute_exact_artifact_hashes(project_root)
        artifact_hash_error = None
    except Exception as exc:
        artifact_hashes = {}
        artifact_hash_error = f"{type(exc).__name__}: {exc}"

    try:
        if not anchors:
            raise ValueError("anchor_indices must not be empty")
        context = _build_delta_context(
            project_root,
            candidate=str(candidate),
            anchor_idx=int(anchors[0]),
            master_search_profile=str(master_search_profile),
        )
        solver_profile = _solver_profile(
            time_limit_seconds=float(time_limit_seconds),
            worker_count=int(worker_count),
        )
        entries = [
            _evaluate_anchor(
                context=context,
                anchor_idx=int(anchor_idx),
                time_limit_seconds=float(time_limit_seconds),
                solver_parameter_profile=solver_profile,
            )
            for anchor_idx in anchors
        ]
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"

    summary = _summary(entries, model_error=model_error)
    return {
        "metadata": {
            "source": PHASE3B_SAME_X_CAPACITY_ANCHOR_SWEEP_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "same_x_capacity_anchor_sweep_not_proof_source",
        },
        "paths": {"project_root": str(project_root)},
        "candidate": {
            "key": str(candidate),
            "ghost_rect": _candidate_rect(str(candidate)),
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "anchor_indices": list(anchors),
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
        },
        "artifact_hashes": dict(artifact_hashes),
        "artifact_hash_error": artifact_hash_error,
        "context": _compact_context(context),
        "sweep": {
            "entries": entries,
            "summary": summary,
            "status_counts": _status_counts(entries),
            "reason_counts": _reason_counts(entries),
            "precheck_rejected_anchors": [
                int(entry["anchor_idx"])
                for entry in entries
                if str(_mapping(entry.get("validation")).get("reason")) == SAME_X_CAPACITY_CONFLICT_REASON
            ],
            "solver_attempted_anchors": [
                int(entry["anchor_idx"])
                for entry in entries
                if bool(_mapping(entry.get("validation")).get("attempted_solver", _mapping(entry.get("validation")).get("attempted", False)))
            ],
        },
        "status": _status(summary, model_error=model_error),
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(entries=entries, summary=summary, model_error=model_error),
    }


def render_phase3b_same_x_capacity_anchor_sweep_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    sweep = _mapping(report.get("sweep"))
    summary = _mapping(sweep.get("summary"))
    lines = [
        "# Phase 3B Same-X Capacity Anchor Sweep",
        "",
        f"- Candidate: {candidate.get('key')}",
        "- Diagnostic semantics: same_x_capacity_anchor_sweep_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Anchor count: {summary.get('anchor_count')}",
        f"- Same-X capacity rejected: {summary.get('same_x_capacity_rejected_count')}",
        f"- Solver attempted: {summary.get('solver_attempted_count')}",
        f"- Anchor119 explained: {summary.get('anchor119_explained')}",
        "",
        "## Anchor Matrix",
        "",
        "| Anchor | Status | Reason | Accepted | Attempted Solver | Forced Count | Capacity | Lower | Upper | Greedy | Wall | Branches | Conflicts |",
        "| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    for entry in list(sweep.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        validation = _mapping(entry.get("validation"))
        capacity = _mapping(validation.get("capacity_conflict"))
        greedy = _mapping(entry.get("greedy"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("anchor_idx")),
                    _markdown_cell(validation.get("status")),
                    _markdown_cell(validation.get("reason")),
                    _markdown_cell(validation.get("accepted")),
                    _markdown_cell(validation.get("attempted_solver")),
                    _markdown_cell(capacity.get("forced_count")),
                    _markdown_cell(capacity.get("capacity")),
                    _markdown_cell(capacity.get("lower_capacity")),
                    _markdown_cell(capacity.get("upper_capacity")),
                    _markdown_cell(greedy.get("complete")),
                    _markdown_cell(validation.get("wall_time")),
                    _markdown_cell(validation.get("branches")),
                    _markdown_cell(validation.get("conflicts")),
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


def render_phase3b_same_x_capacity_anchor_sweep_text(report: Mapping[str, Any]) -> str:
    status = _mapping(report.get("status"))
    sweep = _mapping(report.get("sweep"))
    summary = _mapping(sweep.get("summary"))
    lines = [
        "Phase 3B same-x capacity anchor sweep",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"same_x_capacity_rejected_count={summary.get('same_x_capacity_rejected_count')}",
        f"solver_attempted_count={summary.get('solver_attempted_count')}",
        f"anchor119_explained={summary.get('anchor119_explained')}",
        f"status_counts={sweep.get('status_counts')}",
        f"reason_counts={sweep.get('reason_counts')}",
    ]
    for entry in list(sweep.get("entries", [])):
        if isinstance(entry, Mapping):
            validation = _mapping(entry.get("validation"))
            lines.append(
                "entry "
                f"anchor={entry.get('anchor_idx')} "
                f"status={validation.get('status')} "
                f"reason={validation.get('reason')} "
                f"attempted_solver={validation.get('attempted_solver')} "
                f"accepted={validation.get('accepted')}"
            )
    return "\n".join(lines) + "\n"


def _evaluate_anchor(
    *,
    context: Mapping[str, Any],
    anchor_idx: int,
    time_limit_seconds: float,
    solver_parameter_profile: Mapping[str, Any],
) -> Dict[str, Any]:
    model = context["model"]
    domain = list(getattr(model, "_ghost_domains", []))[int(anchor_idx)]
    blocked_cells = {
        (int(cell[0]), int(cell[1]))
        for cell in list(_mapping(domain).get("cells", []))
    }
    greedy = model._run_mandatory_greedy_pass(
        ordered_groups=list(context.get("ordered_groups", [])),
        candidates_by_group=context.get("candidates_by_group", {}),
        blocked_cells=blocked_cells,
        stop_on_first_failure=True,
    )
    if bool(greedy.get("complete", False)):
        validation = _compact_validation(
            model._validate_coordinate_forced_hint(
                solution_hint=dict(greedy.get("solution_hint", {})),
                ghost_anchor_hint_idx=int(anchor_idx),
                time_limit_seconds=float(time_limit_seconds),
                require_complete=False,
                solver_parameter_profile=solver_parameter_profile,
            )
        )
    else:
        validation = _compact_validation(
            {
                "attempted": False,
                "attempted_solver": False,
                "status": "SKIPPED",
                "accepted": False,
                "reason": "greedy_anchor_incomplete",
                "forced_slot_field_count": 0,
                "forced_ghost_anchor": True,
                "require_complete": False,
            }
        )
    return {
        "anchor_idx": int(anchor_idx),
        "ghost_anchor": dict(_mapping(domain).get("anchor", {})),
        "blocked_cell_count": int(len(blocked_cells)),
        "greedy": _compact_greedy(greedy),
        "validation": validation,
    }


def _compact_validation(payload: Mapping[str, Any]) -> Dict[str, Any]:
    result = {
        "attempted": bool(payload.get("attempted", False)),
        "attempted_solver": bool(
            payload.get("attempted_solver", payload.get("attempted", False))
        ),
        "status": str(payload.get("status", "")),
        "accepted": bool(payload.get("accepted", False)),
        "reason": payload.get("reason"),
        "forced_slot_field_count": int(payload.get("forced_slot_field_count", 0)),
        "forced_ghost_anchor": bool(payload.get("forced_ghost_anchor", False)),
        "require_complete": bool(payload.get("require_complete", False)),
        "wall_time": float(payload.get("wall_time", 0.0)),
        "user_time": float(payload.get("user_time", 0.0)),
        "deterministic_time": float(payload.get("deterministic_time", 0.0)),
        "branches": int(payload.get("branches", 0)),
        "conflicts": int(payload.get("conflicts", 0)),
        "solver_parameters": dict(payload.get("solver_parameters", {})),
    }
    if payload.get("capacity_conflict") is not None:
        result["capacity_conflict"] = dict(payload.get("capacity_conflict", {}))
    return result


def _compact_greedy(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "complete": bool(payload.get("complete", False)),
        "reason": payload.get("reason"),
        "hinted_groups": int(payload.get("hinted_groups", 0)),
        "hinted_instances": int(payload.get("hinted_instances", 0)),
        "first_failed_group_id": payload.get("first_failed_group_id"),
        "first_failed_group_template": payload.get("first_failed_group_template"),
        "first_failure_reason": payload.get("first_failure_reason"),
        "first_failed_group_position": payload.get("first_failed_group_position"),
    }


def _summary(
    entries: Sequence[Mapping[str, Any]],
    *,
    model_error: Optional[str],
) -> Dict[str, Any]:
    same_x = [
        entry
        for entry in entries
        if str(_mapping(entry.get("validation")).get("reason")) == SAME_X_CAPACITY_CONFLICT_REASON
    ]
    solver_attempted = [
        entry
        for entry in entries
        if bool(_mapping(entry.get("validation")).get("attempted_solver", False))
    ]
    unknown = [
        entry
        for entry in entries
        if str(_mapping(entry.get("validation")).get("status")) == "UNKNOWN"
    ]
    other_infeasible = [
        entry
        for entry in entries
        if str(_mapping(entry.get("validation")).get("status")) == "INFEASIBLE"
        and str(_mapping(entry.get("validation")).get("reason")) != SAME_X_CAPACITY_CONFLICT_REASON
    ]
    anchor119 = next((entry for entry in entries if int(entry.get("anchor_idx", -1)) == 119), None)
    return {
        "anchor_count": int(len(entries)),
        "same_x_capacity_rejected_count": int(len(same_x)),
        "same_x_capacity_rejected_anchors": [int(entry["anchor_idx"]) for entry in same_x],
        "solver_attempted_count": int(len(solver_attempted)),
        "solver_attempted_anchors": [int(entry["anchor_idx"]) for entry in solver_attempted],
        "unknown_count": int(len(unknown)),
        "unknown_anchors": [int(entry["anchor_idx"]) for entry in unknown],
        "other_infeasible_count": int(len(other_infeasible)),
        "other_infeasible_anchors": [int(entry["anchor_idx"]) for entry in other_infeasible],
        "anchor119_explained": bool(
            anchor119 is not None
            and str(_mapping(anchor119.get("validation")).get("reason")) == SAME_X_CAPACITY_CONFLICT_REASON
        ),
        "model_error": model_error,
    }


def _status(summary: Mapping[str, Any], *, model_error: Optional[str]) -> Dict[str, Any]:
    if model_error is not None:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "diagnostic_error",
            "recommendation": "Same-x capacity anchor sweep failed; inspect model_error.",
        }
    same_x_count = int(summary.get("same_x_capacity_rejected_count", 0))
    solver_count = int(summary.get("solver_attempted_count", 0))
    if same_x_count and solver_count:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "mixed_precheck_and_solver_anchor_set",
            "recommendation": "Some anchors are explained by the same-x precheck; others still need solver diagnostics before B5A retry.",
        }
    if same_x_count:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "all_evaluated_anchors_explained_by_same_x_capacity",
            "recommendation": "The sweep anchors are explained by the same-x capacity precheck; coordinator can consider a guarded B5A retry after merge.",
        }
    return {
        "completed": True,
        "evaluated": bool(int(summary.get("anchor_count", 0))),
        "outcome": "same_x_capacity_did_not_explain_sweep",
        "recommendation": "The same-x capacity precheck did not explain the sweep; continue diagnostics before B5A retry.",
    }


def _checks(
    *,
    entries: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    return [
        _check(
            "anchors_evaluated",
            "pass" if entries else "fail",
            f"anchor_count={len(entries)}",
        ),
        _check(
            "same_x_reason_present",
            "pass" if int(summary.get("same_x_capacity_rejected_count", 0)) > 0 else "warn",
            f"count={summary.get('same_x_capacity_rejected_count')}",
        ),
        _check(
            "anchor119_explained",
            "pass" if bool(summary.get("anchor119_explained", False)) else "warn",
            str(summary.get("anchor119_explained", False)),
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _status_counts(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        status = str(_mapping(entry.get("validation")).get("status", "UNKNOWN"))
        counts[status] = int(counts.get(status, 0)) + 1
    return dict(sorted(counts.items()))


def _reason_counts(entries: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        reason = str(_mapping(entry.get("validation")).get("reason", "unknown"))
        counts[reason] = int(counts.get(reason, 0)) + 1
    return dict(sorted(counts.items()))


def _solver_profile(*, time_limit_seconds: float, worker_count: int) -> Dict[str, Any]:
    return {
        "profile_id": "same_x_capacity_anchor_sweep",
        "search_branching": "fixed",
        "worker_count": max(1, int(worker_count)),
        "random_seed": 1,
        "randomize_search": False,
        "time_limit_seconds": max(0.001, float(time_limit_seconds)),
    }


def _compact_context(context: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "ghost_anchor_count": int(context.get("ghost_anchor_count", 0)),
        "blocked_cell_count": int(context.get("blocked_cell_count", 0)),
        "ordered_group_count": int(context.get("ordered_group_count", 0)),
    }


def _normalize_anchor_indices(anchor_indices: Sequence[int]) -> tuple[int, ...]:
    result: list[int] = []
    seen: set[int] = set()
    for raw in anchor_indices:
        idx = int(raw)
        if idx in seen:
            continue
        seen.add(idx)
        result.append(idx)
    return tuple(result)


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
