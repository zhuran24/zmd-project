from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    MasterPlacementModel,
)
from src.search.benders_loop import create_exact_search_session
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso

COORDINATE_VALIDATION_PROFILE_PROBE_SOURCE = (
    "phase3b_coordinate_validation_profile_probe_v1"
)

DEFAULT_COORDINATE_VALIDATION_PROFILES = (
    {
        "profile_id": "validation_default_2s",
        "time_limit_seconds": 2.0,
        "worker_count": 1,
    },
    {
        "profile_id": "validation_fixed_presolve_on_30s",
        "time_limit_seconds": 30.0,
        "search_branching": "fixed",
        "worker_count": 1,
        "random_seed": 1,
        "randomize_search": False,
        "cp_model_presolve": True,
    },
    {
        "profile_id": "validation_fixed_presolve_off_30s",
        "time_limit_seconds": 30.0,
        "search_branching": "fixed",
        "worker_count": 1,
        "random_seed": 1,
        "randomize_search": False,
        "cp_model_presolve": False,
        "cp_model_probing_level": 0,
        "symmetry_level": 0,
        "hint_conflict_limit": 0,
    },
    {
        "profile_id": "validation_fixed_presolve_off_120s",
        "time_limit_seconds": 120.0,
        "search_branching": "fixed",
        "worker_count": 1,
        "random_seed": 1,
        "randomize_search": False,
        "cp_model_presolve": False,
        "cp_model_probing_level": 0,
        "symmetry_level": 0,
        "hint_conflict_limit": 0,
    },
)


def build_phase3b_coordinate_validation_profile_probe(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_idx: int = 119,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    profiles: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    normalized_profiles = _normalize_profiles(
        profiles or DEFAULT_COORDINATE_VALIDATION_PROFILES
    )
    started = time.perf_counter()
    model_error: Optional[str] = None
    entries: list[Dict[str, Any]] = []
    context: Dict[str, Any] = {}
    try:
        artifact_hashes = compute_exact_artifact_hashes(project_root)
        artifact_hash_error = None
    except Exception as exc:
        artifact_hashes = {}
        artifact_hash_error = f"{type(exc).__name__}: {exc}"

    try:
        context = _build_coordinate_validation_context(
            project_root,
            candidate=str(candidate),
            anchor_idx=int(anchor_idx),
            master_search_profile=str(master_search_profile),
        )
        model = context["model"]
        greedy = model._run_mandatory_greedy_pass(
            ordered_groups=context["ordered_groups"],
            candidates_by_group=context["candidates_by_group"],
            blocked_cells=set(context["blocked_cells"]),
            stop_on_first_failure=True,
        )
        context["greedy"] = _compact_greedy(greedy)
        if bool(greedy.get("complete", False)):
            for profile in normalized_profiles:
                validation = model._validate_coordinate_forced_hint(
                    solution_hint=dict(greedy.get("solution_hint", {})),
                    ghost_anchor_hint_idx=int(anchor_idx),
                    time_limit_seconds=float(profile["time_limit_seconds"]),
                    solver_parameter_profile=profile,
                )
                entries.append(
                    {
                        "candidate": str(candidate),
                        "anchor_idx": int(anchor_idx),
                        "profile_id": str(profile["profile_id"]),
                        "evaluated": True,
                        **_compact_validation(validation),
                    }
                )
        else:
            for profile in normalized_profiles:
                entries.append(
                    {
                        "candidate": str(candidate),
                        "anchor_idx": int(anchor_idx),
                        "profile_id": str(profile["profile_id"]),
                        "evaluated": False,
                        "status": "SKIPPED",
                        "accepted": False,
                        "reason": "mandatory_greedy_incomplete",
                    }
                )
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"

    status = _status_from_entries(entries, model_error=model_error)
    return {
        "metadata": {
            "source": COORDINATE_VALIDATION_PROFILE_PROBE_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "coordinate_validation_profile_probe_not_proof_source",
        },
        "paths": {"project_root": str(project_root)},
        "candidate": {
            "key": str(candidate),
            "ghost_rect": _candidate_rect(str(candidate)),
            "anchor_idx": int(anchor_idx),
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "profiles": normalized_profiles,
        },
        "artifact_hashes": dict(artifact_hashes),
        "artifact_hash_error": artifact_hash_error,
        "context": _compact_context(context),
        "status": status,
        "probe": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "status_counts_by_profile": _status_counts_by_key(entries, "profile_id"),
            "unknown_diagnostics": _unknown_diagnostics(entries),
            "best_terminal_entry": _best_terminal_entry(entries),
        },
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(status, context, model_error),
    }


def render_phase3b_coordinate_validation_profile_probe_markdown(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    probe = _mapping(report.get("probe"))
    unknowns = _mapping(probe.get("unknown_diagnostics"))
    lines = [
        "# Phase 3B Coordinate Validation Profile Probe",
        "",
        f"- Candidate: {_mapping(report.get('candidate')).get('key')}",
        f"- Anchor: {_mapping(report.get('candidate')).get('anchor_idx')}",
        "- Diagnostic semantics: coordinate_validation_profile_probe_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Status counts: {probe.get('status_counts', {})}",
        f"- Zero-branch UNKNOWN entries: {unknowns.get('zero_branch_unknown_count', 0)}",
        f"- Search-progress UNKNOWN entries: {unknowns.get('search_progress_unknown_count', 0)}",
        "",
        "## Profile Matrix",
        "",
        "| Profile | Status | Accepted | Reason | Presolve | Seconds | Wall | Branches | Conflicts | Deterministic |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in list(probe.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        params = _mapping(entry.get("solver_parameters"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("profile_id")),
                    _markdown_cell(entry.get("status")),
                    _markdown_cell(entry.get("accepted")),
                    _markdown_cell(entry.get("reason")),
                    _markdown_cell(params.get("cp_model_presolve")),
                    _markdown_cell(params.get("max_time_in_seconds")),
                    _markdown_cell(entry.get("wall_time")),
                    _markdown_cell(entry.get("branches")),
                    _markdown_cell(entry.get("conflicts")),
                    _markdown_cell(entry.get("deterministic_time")),
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


def render_phase3b_coordinate_validation_profile_probe_text(
    report: Mapping[str, Any],
) -> str:
    status = _mapping(report.get("status"))
    probe = _mapping(report.get("probe"))
    unknowns = _mapping(probe.get("unknown_diagnostics"))
    candidate = _mapping(report.get("candidate"))
    lines = [
        "Phase 3B coordinate validation profile probe",
        f"candidate={candidate.get('key')}",
        f"anchor_idx={candidate.get('anchor_idx')}",
        "diagnostic_semantics=coordinate_validation_profile_probe_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"status_counts={probe.get('status_counts', {})}",
        f"zero_branch_unknown_count={unknowns.get('zero_branch_unknown_count', 0)}",
        f"search_progress_unknown_count={unknowns.get('search_progress_unknown_count', 0)}",
    ]
    for entry in list(probe.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        params = _mapping(entry.get("solver_parameters"))
        lines.append(
            "entry "
            f"profile={entry.get('profile_id')} "
            f"status={entry.get('status')} "
            f"accepted={entry.get('accepted')} "
            f"reason={entry.get('reason')} "
            f"presolve={params.get('cp_model_presolve')} "
            f"seconds={params.get('max_time_in_seconds')} "
            f"wall={entry.get('wall_time')} "
            f"branches={entry.get('branches')} "
            f"conflicts={entry.get('conflicts')} "
            f"deterministic={entry.get('deterministic_time')}"
        )
    return "\n".join(lines) + "\n"


def _build_coordinate_validation_context(
    project_root: Path,
    *,
    candidate: str,
    anchor_idx: int,
    master_search_profile: str,
) -> Dict[str, Any]:
    ghost_rect = _candidate_rect(candidate)
    exact_session = create_exact_search_session(
        project_root,
        solve_mode="certified_exact",
        master_search_profile=str(master_search_profile),
    )
    model = MasterPlacementModel.from_exact_core(
        exact_session.core,
        ghost_rect=(int(ghost_rect["w"]), int(ghost_rect["h"])),
        master_search_profile=str(master_search_profile),
    )
    model.build()
    if int(anchor_idx) < 0 or int(anchor_idx) >= len(model._ghost_domains):
        raise ValueError(f"anchor_idx out of range: {anchor_idx}")
    candidates_by_group = {
        str(group["group_id"]): model._candidate_pose_indices_for_group(group)
        for group in model._mandatory_groups
    }
    ordered_groups = model._ordered_mandatory_groups_for_greedy(candidates_by_group)
    domain = model._ghost_domains[int(anchor_idx)]
    blocked_cells = {
        (int(cell[0]), int(cell[1]))
        for cell in list(domain.get("cells", []))
    }
    return {
        "model": model,
        "ordered_groups": ordered_groups,
        "candidates_by_group": candidates_by_group,
        "blocked_cells": blocked_cells,
        "ghost_anchor_count": int(len(model._ghost_domains)),
        "blocked_cell_count": int(len(blocked_cells)),
        "ordered_group_count": int(len(ordered_groups)),
    }


def _normalize_profiles(profiles: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(profiles):
        profile_id = str(raw.get("profile_id") or f"profile_{index}").strip()
        if not profile_id or profile_id in seen:
            continue
        seen.add(profile_id)
        normalized = dict(raw)
        normalized["profile_id"] = profile_id
        normalized["time_limit_seconds"] = max(0.0, float(raw.get("time_limit_seconds", 2.0)))
        normalized["worker_count"] = max(1, int(raw.get("worker_count", 1)))
        result.append(normalized)
    return result or _normalize_profiles(DEFAULT_COORDINATE_VALIDATION_PROFILES)


def _compact_validation(validation: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "status": validation.get("status"),
        "accepted": bool(validation.get("accepted", False)),
        "reason": validation.get("reason"),
        "wall_time": float(validation.get("wall_time", 0.0)),
        "user_time": float(validation.get("user_time", 0.0)),
        "deterministic_time": float(validation.get("deterministic_time", 0.0)),
        "branches": int(validation.get("branches", 0)),
        "conflicts": int(validation.get("conflicts", 0)),
        "binary_propagations": int(validation.get("binary_propagations", 0)),
        "integer_propagations": int(validation.get("integer_propagations", 0)),
        "missing_hint_count": int(validation.get("missing_hint_count", 0)),
        "missing_pose_tuple_count": int(validation.get("missing_pose_tuple_count", 0)),
        "forced_slot_field_count": int(validation.get("forced_slot_field_count", 0)),
        "forced_ghost_anchor": bool(validation.get("forced_ghost_anchor", False)),
        "require_complete": bool(validation.get("require_complete", True)),
        "solver_parameters": dict(validation.get("solver_parameters", {})),
    }


def _compact_greedy(greedy: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "complete": bool(greedy.get("complete", False)),
        "reason": greedy.get("reason"),
        "hinted_instances": int(greedy.get("hinted_instances", 0)),
        "hinted_groups": int(greedy.get("hinted_groups", 0)),
        "first_failure_reason": greedy.get("first_failure_reason"),
        "first_failed_group_id": greedy.get("first_failed_group_id"),
        "first_failed_group_template": greedy.get("first_failed_group_template"),
        "first_failed_group_position": greedy.get("first_failed_group_position"),
    }


def _compact_context(context: Mapping[str, Any]) -> Dict[str, Any]:
    result = {
        "ghost_anchor_count": int(context.get("ghost_anchor_count", 0)),
        "blocked_cell_count": int(context.get("blocked_cell_count", 0)),
        "ordered_group_count": int(context.get("ordered_group_count", 0)),
    }
    if isinstance(context.get("greedy"), Mapping):
        result["greedy"] = dict(context["greedy"])
    return result


def _candidate_rect(candidate: str) -> Dict[str, int]:
    raw = str(candidate).strip().lower()
    if "x" not in raw:
        raise ValueError(f"Unsupported candidate {candidate!r}; expected WxH.")
    w_text, h_text = raw.split("x", 1)
    w = int(w_text)
    h = int(h_text)
    if w <= 0 or h <= 0:
        raise ValueError(f"Unsupported candidate {candidate!r}; dimensions must be positive.")
    return {"w": int(w), "h": int(h), "area": int(w * h)}


def _status_from_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    model_error: Optional[str],
) -> Dict[str, Any]:
    evaluated = [entry for entry in entries if bool(entry.get("evaluated", False))]
    counts = _status_counts(evaluated)
    unknowns = _unknown_diagnostics(evaluated)
    if model_error is not None:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "diagnostic_error",
            "status_counts": counts,
            "recommendation": "Coordinate validation profile probe failed; inspect model_error.",
        }
    if not entries:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "no_validation_entries",
            "status_counts": counts,
            "recommendation": "No coordinate validation profile entries were evaluated.",
        }
    if not evaluated:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "coordinate_validation_not_evaluated",
            "status_counts": _status_counts(entries),
            "recommendation": "Coordinate validation profiles were skipped before solver evaluation; inspect context.greedy.",
        }
    if any(str(entry.get("status")) in {"OPTIMAL", "FEASIBLE"} for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "coordinate_validation_accepted",
            "status_counts": counts,
            "recommendation": "At least one profile accepts the forced coordinate hint; compare against runtime failure.",
        }
    if any(str(entry.get("status")) == "INFEASIBLE" for entry in evaluated):
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "coordinate_validation_infeasible",
            "status_counts": counts,
            "recommendation": "At least one profile proves the forced coordinate hint infeasible; use as shrink target.",
        }
    if int(unknowns.get("search_progress_unknown_count", 0)) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "coordinate_validation_progress_without_terminal",
            "status_counts": counts,
            "recommendation": "Validation remains UNKNOWN but search progresses; compare longer profile or shrink validation model.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "coordinate_validation_zero_branch_unknown",
        "status_counts": counts,
        "recommendation": "Validation profiles remain zero-branch UNKNOWN; inspect validation model build/presolve.",
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
    unknowns = [entry for entry in entries if str(entry.get("status")) == "UNKNOWN"]
    zero_branch = [
        entry
        for entry in unknowns
        if _number_or_zero(entry.get("branches")) == 0
        and _number_or_zero(entry.get("conflicts")) == 0
    ]
    progress = [entry for entry in unknowns if entry not in zero_branch]
    return {
        "unknown_count": int(len(unknowns)),
        "zero_branch_unknown_count": int(len(zero_branch)),
        "search_progress_unknown_count": int(len(progress)),
        "zero_branch_unknown_by_profile": _count_entries_by_key(zero_branch, "profile_id"),
        "search_progress_unknown_by_profile": _count_entries_by_key(progress, "profile_id"),
    }


def _best_terminal_entry(entries: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    terminal = [
        entry
        for entry in entries
        if str(entry.get("status")) in {"OPTIMAL", "FEASIBLE", "INFEASIBLE"}
    ]
    if not terminal:
        return None
    return dict(
        sorted(
            terminal,
            key=lambda entry: (
                float(entry.get("wall_time", 10**9)),
                str(entry.get("profile_id")),
            ),
        )[0]
    )


def _count_entries_by_key(
    entries: Sequence[Mapping[str, Any]],
    key_name: str,
) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        key = str(entry.get(key_name))
        counts[key] = int(counts.get(key, 0)) + 1
    return counts


def _checks(
    status: Mapping[str, Any],
    context: Mapping[str, Any],
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    return [
        _check(
            "context_built",
            "pass" if context else "fail",
            f"blocked_cell_count={int(context.get('blocked_cell_count', 0))}"
            if context
            else "context missing",
        ),
        _check(
            "validation_probe_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
        ),
        _check(
            "model_error_absent",
            "pass" if model_error is None else "fail",
            "no model error" if model_error is None else str(model_error),
        ),
    ]


def _check(check_id: str, status: str, detail: str) -> Dict[str, str]:
    return {"check_id": str(check_id), "status": str(status), "detail": str(detail)}


def _number_or_zero(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _markdown_cell(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("|", "\\|").replace("\n", " ")
