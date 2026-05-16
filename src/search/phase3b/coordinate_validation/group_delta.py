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

COORDINATE_VALIDATION_GROUP_DELTA_SOURCE = (
    "phase3b_coordinate_validation_group_delta_v1"
)

DEFAULT_GROUP_DELTA_VARIANTS = (
    "ghost_plus_all",
    "mandatory_only",
    "ghost_only",
)

EXPANSION_VARIANTS = {
    "ghost_plus_each_group",
    "ghost_plus_all_except_group",
    "ghost_plus_each_family",
    "ghost_plus_all_except_family",
    "mandatory_each_group",
    "mandatory_all_except_group",
    "mandatory_each_family",
    "mandatory_all_except_family",
}

KNOWN_GROUP_DELTA_VARIANTS = (
    "ghost_plus_all",
    "mandatory_only",
    "ghost_only",
    "ghost_plus_each_group",
    "ghost_plus_all_except_group",
    "ghost_plus_each_family",
    "ghost_plus_all_except_family",
    "mandatory_each_group",
    "mandatory_all_except_group",
    "mandatory_each_family",
    "mandatory_all_except_family",
)


def build_phase3b_coordinate_validation_group_delta(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_idx: int = 119,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    variants: Optional[Sequence[str]] = None,
    max_groups: Optional[int] = None,
    max_families: Optional[int] = None,
    time_limit_seconds: float = 2.0,
    worker_count: int = 1,
    solver_parameter_profile: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    normalized_variants = _normalize_variants(variants or DEFAULT_GROUP_DELTA_VARIANTS)
    solver_profile = _normalize_solver_profile(
        solver_parameter_profile,
        time_limit_seconds=float(time_limit_seconds),
        worker_count=int(worker_count),
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
        context = _build_delta_context(
            project_root,
            candidate=str(candidate),
            anchor_idx=int(anchor_idx),
            master_search_profile=str(master_search_profile),
        )
        plans = _build_delta_plans(
            ordered_groups=context["ordered_groups"],
            variants=normalized_variants,
            max_groups=max_groups,
            max_families=max_families,
        )
        entries = [
            _evaluate_delta_plan(
                context=context,
                plan=plan,
                anchor_idx=int(anchor_idx),
                time_limit_seconds=float(time_limit_seconds),
                solver_parameter_profile=solver_profile,
            )
            for plan in plans
        ]
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"

    status = _status_from_entries(entries, model_error=model_error)
    return {
        "metadata": {
            "source": COORDINATE_VALIDATION_GROUP_DELTA_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "coordinate_validation_group_delta_not_proof_source",
        },
        "paths": {"project_root": str(project_root)},
        "candidate": {
            "key": str(candidate),
            "ghost_rect": _candidate_rect(str(candidate)),
            "anchor_idx": int(anchor_idx),
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "variants": list(normalized_variants),
            "max_groups": None if max_groups is None else int(max_groups),
            "max_families": None if max_families is None else int(max_families),
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "solver_parameter_profile": dict(solver_profile),
        },
        "artifact_hashes": dict(artifact_hashes),
        "artifact_hash_error": artifact_hash_error,
        "context": _compact_context(context),
        "status": status,
        "delta": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "status_counts_by_variant": _status_counts_by_key(entries, "variant"),
            "first_infeasible_entry": _first_entry_with_status(entries, "INFEASIBLE"),
            "first_narrower_infeasible_entry": _first_narrower_infeasible_entry(entries),
            "first_accepted_entry": _first_accepted_entry(entries),
            "unknown_diagnostics": _unknown_diagnostics(entries),
        },
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(status, context, entries, model_error),
    }


def render_phase3b_coordinate_validation_group_delta_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    delta = _mapping(report.get("delta"))
    unknowns = _mapping(delta.get("unknown_diagnostics"))
    lines = [
        "# Phase 3B Coordinate Validation Group Delta",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Anchor: {candidate.get('anchor_idx')}",
        "- Diagnostic semantics: coordinate_validation_group_delta_not_proof_source",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- Status counts: {delta.get('status_counts', {})}",
        f"- Zero-branch UNKNOWN entries: {unknowns.get('zero_branch_unknown_count', 0)}",
        f"- Search-progress UNKNOWN entries: {unknowns.get('search_progress_unknown_count', 0)}",
    ]
    first_narrower = _mapping(delta.get("first_narrower_infeasible_entry"))
    if first_narrower:
        lines.append(f"- First non-full infeasible: {first_narrower.get('case_id')}")
    lines.extend(
        [
            "",
            "## Delta Matrix",
            "",
            "| Case | Variant | Status | Accepted | Reason | Ghost | Groups | Missing hints | Missing poses | Forced slots | Wall | Branches | Conflicts | Included | Excluded |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for entry in _entries(report):
        validation = _mapping(entry.get("validation"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("case_id")),
                    _markdown_cell(entry.get("variant")),
                    _markdown_cell(validation.get("status")),
                    _markdown_cell(validation.get("accepted")),
                    _markdown_cell(validation.get("reason")),
                    _markdown_cell(entry.get("include_ghost")),
                    _markdown_cell(entry.get("included_group_count")),
                    _markdown_cell(validation.get("missing_hint_count")),
                    _markdown_cell(validation.get("missing_pose_tuple_count")),
                    _markdown_cell(validation.get("forced_slot_field_count")),
                    _markdown_cell(validation.get("wall_time")),
                    _markdown_cell(validation.get("branches")),
                    _markdown_cell(validation.get("conflicts")),
                    _markdown_cell(",".join(entry.get("included_group_ids", []))),
                    _markdown_cell(",".join(entry.get("excluded_group_ids", []))),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in list(report.get("checks", [])):
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


def render_phase3b_coordinate_validation_group_delta_text(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    status = _mapping(report.get("status"))
    delta = _mapping(report.get("delta"))
    unknowns = _mapping(delta.get("unknown_diagnostics"))
    lines = [
        "Phase 3B coordinate validation group delta",
        f"candidate={candidate.get('key')}",
        f"anchor_idx={candidate.get('anchor_idx')}",
        "diagnostic_semantics=coordinate_validation_group_delta_not_proof_source",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"status_counts={delta.get('status_counts', {})}",
        f"zero_branch_unknown_count={unknowns.get('zero_branch_unknown_count', 0)}",
        f"search_progress_unknown_count={unknowns.get('search_progress_unknown_count', 0)}",
    ]
    for entry in _entries(report):
        validation = _mapping(entry.get("validation"))
        lines.append(
            "entry "
            f"case={entry.get('case_id')} "
            f"variant={entry.get('variant')} "
            f"status={validation.get('status')} "
            f"accepted={validation.get('accepted')} "
            f"reason={validation.get('reason')} "
            f"ghost={entry.get('include_ghost')} "
            f"included_groups={entry.get('included_group_count')} "
            f"missing_hints={validation.get('missing_hint_count')} "
            f"missing_poses={validation.get('missing_pose_tuple_count')} "
            f"forced_slots={validation.get('forced_slot_field_count')} "
            f"wall={validation.get('wall_time')} "
            f"branches={validation.get('branches')} "
            f"conflicts={validation.get('conflicts')}"
        )
    return "\n".join(lines) + "\n"


def _build_delta_context(
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
        "family_count": int(len(_families_from_groups(ordered_groups))),
    }


def _build_delta_plans(
    *,
    ordered_groups: Sequence[Mapping[str, Any]],
    variants: Sequence[str],
    max_groups: Optional[int],
    max_families: Optional[int],
) -> list[Dict[str, Any]]:
    groups = list(ordered_groups)
    selected_groups = _limit_sequence(groups, max_groups)
    families = _limit_sequence(_families_from_groups(groups), max_families)
    plans: list[Dict[str, Any]] = []
    for variant in variants:
        if variant == "ghost_plus_all":
            plans.append(
                _plan(
                    variant=variant,
                    case_id=variant,
                    include_ghost=True,
                    included_groups=groups,
                    require_complete=True,
                )
            )
        elif variant == "mandatory_only":
            plans.append(
                _plan(
                    variant=variant,
                    case_id=variant,
                    include_ghost=False,
                    included_groups=groups,
                    require_complete=True,
                )
            )
        elif variant == "ghost_only":
            plans.append(
                _plan(
                    variant=variant,
                    case_id=variant,
                    include_ghost=True,
                    included_groups=[],
                    require_complete=False,
                )
            )
        elif variant == "ghost_plus_each_group":
            for group in selected_groups:
                group_id = str(group.get("group_id", ""))
                plans.append(
                    _plan(
                        variant=variant,
                        case_id=f"{variant}:{group_id}",
                        include_ghost=True,
                        included_groups=[group],
                        require_complete=False,
                    )
                )
        elif variant == "mandatory_each_group":
            for group in selected_groups:
                group_id = str(group.get("group_id", ""))
                plans.append(
                    _plan(
                        variant=variant,
                        case_id=f"{variant}:{group_id}",
                        include_ghost=False,
                        included_groups=[group],
                        require_complete=False,
                    )
                )
        elif variant == "ghost_plus_all_except_group":
            for group in selected_groups:
                group_id = str(group.get("group_id", ""))
                plans.append(
                    _plan(
                        variant=variant,
                        case_id=f"{variant}:{group_id}",
                        include_ghost=True,
                        included_groups=[g for g in groups if g is not group],
                        excluded_groups=[group],
                        require_complete=False,
                    )
                )
        elif variant == "mandatory_all_except_group":
            for group in selected_groups:
                group_id = str(group.get("group_id", ""))
                plans.append(
                    _plan(
                        variant=variant,
                        case_id=f"{variant}:{group_id}",
                        include_ghost=False,
                        included_groups=[g for g in groups if g is not group],
                        excluded_groups=[group],
                        require_complete=False,
                    )
                )
        elif variant == "ghost_plus_each_family":
            for family in families:
                family_groups = [g for g in groups if _family_key(g) == family]
                plans.append(
                    _plan(
                        variant=variant,
                        case_id=f"{variant}:{family}",
                        include_ghost=True,
                        included_groups=family_groups,
                        require_complete=False,
                        family_key=family,
                    )
                )
        elif variant == "mandatory_each_family":
            for family in families:
                family_groups = [g for g in groups if _family_key(g) == family]
                plans.append(
                    _plan(
                        variant=variant,
                        case_id=f"{variant}:{family}",
                        include_ghost=False,
                        included_groups=family_groups,
                        require_complete=False,
                        family_key=family,
                    )
                )
        elif variant == "ghost_plus_all_except_family":
            for family in families:
                excluded = [g for g in groups if _family_key(g) == family]
                included = [g for g in groups if _family_key(g) != family]
                plans.append(
                    _plan(
                        variant=variant,
                        case_id=f"{variant}:{family}",
                        include_ghost=True,
                        included_groups=included,
                        excluded_groups=excluded,
                        require_complete=False,
                        family_key=family,
                    )
                )
        elif variant == "mandatory_all_except_family":
            for family in families:
                excluded = [g for g in groups if _family_key(g) == family]
                included = [g for g in groups if _family_key(g) != family]
                plans.append(
                    _plan(
                        variant=variant,
                        case_id=f"{variant}:{family}",
                        include_ghost=False,
                        included_groups=included,
                        excluded_groups=excluded,
                        require_complete=False,
                        family_key=family,
                    )
                )
    return plans


def _evaluate_delta_plan(
    *,
    context: Mapping[str, Any],
    plan: Mapping[str, Any],
    anchor_idx: int,
    time_limit_seconds: float,
    solver_parameter_profile: Mapping[str, Any],
) -> Dict[str, Any]:
    model: MasterPlacementModel = context["model"]
    included_groups = [
        group for group in list(plan.get("included_groups", [])) if isinstance(group, Mapping)
    ]
    include_ghost = bool(plan.get("include_ghost", False))
    blocked_cells = set(context.get("blocked_cells", set())) if include_ghost else set()
    greedy = model._run_mandatory_greedy_pass(
        ordered_groups=included_groups,
        candidates_by_group=context["candidates_by_group"],
        blocked_cells=blocked_cells,
        stop_on_first_failure=True,
    )
    if bool(greedy.get("complete", False)):
        validation = _compact_validation(
            model._validate_coordinate_forced_hint(
                solution_hint=dict(greedy.get("solution_hint", {})),
                ghost_anchor_hint_idx=int(anchor_idx) if include_ghost else None,
                time_limit_seconds=float(time_limit_seconds),
                require_complete=bool(plan.get("require_complete", False)),
                solver_parameter_profile=solver_parameter_profile,
            )
        )
    else:
        validation = _compact_validation(
            {
                "attempted": False,
                "status": "SKIPPED",
                "accepted": False,
                "reason": "greedy_variant_incomplete",
                "missing_hint_count": 0,
                "missing_pose_tuple_count": 0,
                "forced_slot_field_count": 0,
                "forced_ghost_anchor": include_ghost,
                "require_complete": bool(plan.get("require_complete", False)),
            }
        )
    included_group_ids = [
        str(group.get("group_id", "")) for group in included_groups if isinstance(group, Mapping)
    ]
    excluded_groups = [
        group for group in list(plan.get("excluded_groups", [])) if isinstance(group, Mapping)
    ]
    return {
        "case_id": str(plan.get("case_id")),
        "variant": str(plan.get("variant")),
        "candidate": str(plan.get("candidate", "")),
        "anchor_idx": int(anchor_idx),
        "include_ghost": include_ghost,
        "require_complete": bool(plan.get("require_complete", False)),
        "family_key": plan.get("family_key"),
        "included_group_count": int(len(included_group_ids)),
        "excluded_group_count": int(len(excluded_groups)),
        "included_group_ids": included_group_ids,
        "excluded_group_ids": [
            str(group.get("group_id", "")) for group in excluded_groups
        ],
        "included_groups": [_compact_group(group) for group in included_groups],
        "excluded_groups": [_compact_group(group) for group in excluded_groups],
        "greedy": _compact_greedy(greedy),
        "validation": validation,
    }


def _plan(
    *,
    variant: str,
    case_id: str,
    include_ghost: bool,
    included_groups: Sequence[Mapping[str, Any]],
    excluded_groups: Sequence[Mapping[str, Any]] = (),
    require_complete: bool,
    family_key: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "variant": str(variant),
        "case_id": str(case_id),
        "include_ghost": bool(include_ghost),
        "included_groups": list(included_groups),
        "excluded_groups": list(excluded_groups),
        "require_complete": bool(require_complete),
        "family_key": family_key,
    }


def _normalize_variants(variants: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in variants:
        variant = str(raw).strip()
        if not variant:
            continue
        if variant not in KNOWN_GROUP_DELTA_VARIANTS:
            raise ValueError(f"Unsupported group delta variant: {variant}")
        if variant in seen:
            continue
        seen.add(variant)
        result.append(variant)
    return tuple(result or DEFAULT_GROUP_DELTA_VARIANTS)


def _normalize_solver_profile(
    profile: Optional[Mapping[str, Any]],
    *,
    time_limit_seconds: float,
    worker_count: int,
) -> Dict[str, Any]:
    normalized = dict(profile or {})
    normalized.setdefault("profile_id", "group_delta_fixed_presolve_on")
    normalized.setdefault("search_branching", "fixed")
    normalized.setdefault("worker_count", int(max(1, worker_count)))
    normalized.setdefault("random_seed", 1)
    normalized.setdefault("randomize_search", False)
    normalized.setdefault("cp_model_presolve", True)
    normalized["time_limit_seconds"] = max(0.0, float(time_limit_seconds))
    normalized["worker_count"] = max(1, int(normalized.get("worker_count", worker_count)))
    return normalized


def _compact_validation(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "attempted": bool(payload.get("attempted", False)),
        "status": str(payload.get("status", "")),
        "accepted": bool(payload.get("accepted", False)),
        "reason": payload.get("reason"),
        "missing_hint_count": int(payload.get("missing_hint_count", 0)),
        "missing_pose_tuple_count": int(payload.get("missing_pose_tuple_count", 0)),
        "forced_slot_field_count": int(payload.get("forced_slot_field_count", 0)),
        "forced_ghost_anchor": bool(payload.get("forced_ghost_anchor", False)),
        "forced_fields": list(payload.get("forced_fields", ["x", "y", "mode"])),
        "use_assumptions": bool(payload.get("use_assumptions", False)),
        "assumption_core_supported": bool(
            payload.get("assumption_core_supported", False)
        ),
        "assumption_count": int(payload.get("assumption_count", 0)),
        "assumption_labels": [
            dict(label)
            for label in list(payload.get("assumption_labels", []))
            if isinstance(label, Mapping)
        ],
        "infeasible_assumption_core": [
            dict(label)
            for label in list(payload.get("infeasible_assumption_core", []))
            if isinstance(label, Mapping)
        ],
        "infeasible_assumption_core_status": payload.get(
            "infeasible_assumption_core_status"
        ),
        "force_equality_filter_active": bool(
            payload.get("force_equality_filter_active", False)
        ),
        "force_equality_labels": [
            dict(label)
            for label in list(payload.get("force_equality_labels", []))
            if isinstance(label, Mapping)
        ],
        "require_complete": bool(payload.get("require_complete", False)),
        "wall_time": float(payload.get("wall_time", 0.0)),
        "user_time": float(payload.get("user_time", 0.0)),
        "deterministic_time": float(payload.get("deterministic_time", 0.0)),
        "branches": int(payload.get("branches", 0)),
        "conflicts": int(payload.get("conflicts", 0)),
        "binary_propagations": int(payload.get("binary_propagations", 0)),
        "integer_propagations": int(payload.get("integer_propagations", 0)),
        "solver_parameters": dict(payload.get("solver_parameters", {})),
    }


def _compact_greedy(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "complete": bool(payload.get("complete", False)),
        "reason": payload.get("reason"),
        "hinted_groups": int(payload.get("hinted_groups", 0)),
        "hinted_instances": int(payload.get("hinted_instances", 0)),
        "first_failed_group_id": payload.get("first_failed_group_id"),
        "first_failed_group_template": payload.get("first_failed_group_template"),
        "first_failed_group_required_count": int(
            payload.get("first_failed_group_required_count", 0)
        ),
        "first_failed_group_candidate_count": int(
            payload.get("first_failed_group_candidate_count", 0)
        ),
        "first_failed_group_surviving_after_blocked_count": int(
            payload.get("first_failed_group_surviving_after_blocked_count", 0)
        ),
        "first_failed_group_surviving_at_failure_count": int(
            payload.get("first_failed_group_surviving_at_failure_count", 0)
        ),
        "first_failure_reason": payload.get("first_failure_reason"),
        "first_failed_group_position": payload.get("first_failed_group_position"),
    }


def _compact_group(group: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "group_id": str(group.get("group_id", "")),
        "facility_type": str(group.get("facility_type", "")),
        "operation_type": str(group.get("operation_type", "")),
        "required_count": int(group.get("count", 0)),
        "family_key": _family_key(group),
    }


def _compact_context(context: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "ghost_anchor_count": int(context.get("ghost_anchor_count", 0)),
        "blocked_cell_count": int(context.get("blocked_cell_count", 0)),
        "ordered_group_count": int(context.get("ordered_group_count", 0)),
        "family_count": int(context.get("family_count", 0)),
    }


def _status_from_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    model_error: Optional[str],
) -> Dict[str, Any]:
    evaluated = [
        entry
        for entry in entries
        if bool(_mapping(entry.get("validation")).get("attempted", False))
    ]
    counts = _status_counts(entries)
    if model_error is not None:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "diagnostic_error",
            "status_counts": counts,
            "recommendation": "Coordinate-validation group delta failed; inspect model_error.",
        }
    if not entries:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "no_delta_entries",
            "status_counts": counts,
            "recommendation": "No delta entries were generated; check variants and caps.",
        }
    if not evaluated:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "coordinate_validation_delta_not_evaluated",
            "status_counts": counts,
            "recommendation": "All delta entries were skipped before solver evaluation.",
        }
    narrower_infeasible = [entry for entry in evaluated if _is_narrower_infeasible(entry)]
    if narrower_infeasible:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "coordinate_validation_delta_infeasible_found",
            "status_counts": counts,
            "recommendation": (
                "A non-full delta/control is infeasible; use the first "
                "non-full infeasible entry as a B2/B3 diagnostic shrink target only."
            ),
        }
    full_infeasible = any(
        str(entry.get("variant")) == "ghost_plus_all"
        and str(_mapping(entry.get("validation")).get("status")) == "INFEASIBLE"
        for entry in evaluated
    )
    if full_infeasible:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "full_hint_infeasible_without_narrower_delta",
            "status_counts": counts,
            "recommendation": (
                "The full forced hint is infeasible but no narrower tested delta "
                "isolated it; expand group/family caps in a workspace."
            ),
        }
    if _first_accepted_entry(evaluated) is not None:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "coordinate_validation_delta_accepted_present",
            "status_counts": counts,
            "recommendation": "At least one delta is coordinate-compatible; compare against failing full hint.",
        }
    unknowns = _unknown_diagnostics(evaluated)
    if int(unknowns.get("search_progress_unknown_count", 0)) > 0:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "coordinate_validation_delta_progress_without_terminal",
            "status_counts": counts,
            "recommendation": "Delta validation remained UNKNOWN with search progress.",
        }
    return {
        "completed": True,
        "evaluated": True,
        "outcome": "coordinate_validation_delta_zero_branch_unknown",
        "status_counts": counts,
        "recommendation": "Delta validation remained zero-branch UNKNOWN.",
    }


def _checks(
    status: Mapping[str, Any],
    context: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    return [
        _check(
            "context_built",
            "pass" if context else "fail",
            f"ordered_group_count={int(context.get('ordered_group_count', 0))}"
            if context
            else "context missing",
        ),
        _check(
            "delta_entries_present",
            "pass" if entries else "fail",
            f"entry_count={len(entries)}",
        ),
        _check(
            "delta_probe_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "skipped",
            str(status.get("outcome")),
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
    return counts


def _status_counts_by_key(
    entries: Sequence[Mapping[str, Any]],
    key_name: str,
) -> Dict[str, Dict[str, int]]:
    grouped: Dict[str, Dict[str, int]] = {}
    for entry in entries:
        key = str(entry.get(key_name))
        status = str(_mapping(entry.get("validation")).get("status", "UNKNOWN"))
        bucket = grouped.setdefault(key, {})
        bucket[status] = int(bucket.get(status, 0)) + 1
    return grouped


def _unknown_diagnostics(entries: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    unknowns = [
        entry
        for entry in entries
        if str(_mapping(entry.get("validation")).get("status")) == "UNKNOWN"
    ]
    zero_branch = [
        entry
        for entry in unknowns
        if _number_or_zero(_mapping(entry.get("validation")).get("branches")) == 0
        and _number_or_zero(_mapping(entry.get("validation")).get("conflicts")) == 0
    ]
    progress = [entry for entry in unknowns if entry not in zero_branch]
    return {
        "unknown_count": int(len(unknowns)),
        "zero_branch_unknown_count": int(len(zero_branch)),
        "search_progress_unknown_count": int(len(progress)),
        "zero_branch_unknown_by_variant": _count_entries_by_key(zero_branch, "variant"),
        "search_progress_unknown_by_variant": _count_entries_by_key(progress, "variant"),
    }


def _first_entry_with_status(
    entries: Sequence[Mapping[str, Any]],
    status: str,
) -> Optional[Dict[str, Any]]:
    for entry in entries:
        if str(_mapping(entry.get("validation")).get("status")) == str(status):
            return dict(entry)
    return None


def _first_narrower_infeasible_entry(
    entries: Sequence[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    for entry in entries:
        if _is_narrower_infeasible(entry):
            return dict(entry)
    return None


def _is_narrower_infeasible(entry: Mapping[str, Any]) -> bool:
    return (
        str(_mapping(entry.get("validation")).get("status")) == "INFEASIBLE"
        and str(entry.get("variant")) != "ghost_plus_all"
    )


def _first_accepted_entry(entries: Sequence[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    for entry in entries:
        if bool(_mapping(entry.get("validation")).get("accepted", False)):
            return dict(entry)
    return None


def _count_entries_by_key(
    entries: Sequence[Mapping[str, Any]],
    key_name: str,
) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for entry in entries:
        key = str(entry.get(key_name))
        counts[key] = int(counts.get(key, 0)) + 1
    return counts


def _families_from_groups(groups: Sequence[Mapping[str, Any]]) -> list[str]:
    seen: set[str] = set()
    families: list[str] = []
    for group in groups:
        family = _family_key(group)
        if family in seen:
            continue
        seen.add(family)
        families.append(family)
    return families


def _family_key(group: Mapping[str, Any]) -> str:
    raw = group.get("family_id")
    if raw is None:
        raw = group.get("facility_family")
    if raw is None:
        raw = group.get("facility_type")
    return str(raw or "")


def _limit_sequence(items: Sequence[Any], limit: Optional[int]) -> list[Any]:
    if limit is None:
        return list(items)
    return list(items)[: max(0, int(limit))]


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


def _entries(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        entry
        for entry in list(_mapping(report.get("delta")).get("entries", []))
        if isinstance(entry, Mapping)
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
