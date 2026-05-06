from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from src.models.master_model import DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso
from src.search.phase3b_coordinate_validation_field_channel_delta import (
    FIELD_CHANNELS_BY_VARIANT,
    FIELD_CHANNEL_VARIANTS,
)
from src.search.phase3b_coordinate_validation_group_delta import (
    _build_delta_context,
    _candidate_rect,
    _check,
    _compact_greedy,
    _compact_validation,
    _mapping,
    _normalize_solver_profile,
)

GREEDY_POSE_ORDER_COMPARISON_SOURCE = "phase3b_greedy_pose_order_comparison_v1"
DEFAULT_TARGET_GROUP_ID = "group::manufacturing_5x5::planter_buckwheat::9"
DEFAULT_FIELD_VARIANT = "x_y"
DEFAULT_STRATEGIES = (
    "single_group_blocked",
    "single_group_unblocked",
    "single_group_y_then_x_blocked",
    "full_blocked",
    "full_unblocked",
    "full_y_then_x_blocked",
)


def build_phase3b_greedy_pose_order_comparison(
    project_root: Path,
    *,
    candidate: str = "67x13",
    anchor_idx: int = 159,
    group_id: str = DEFAULT_TARGET_GROUP_ID,
    field_variant: str = DEFAULT_FIELD_VARIANT,
    strategies: Optional[Sequence[str]] = None,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    time_limit_seconds: float = 10.0,
    worker_count: int = 1,
    solver_parameter_profile: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    normalized_group_id = str(group_id).strip()
    normalized_field_variant = str(field_variant).strip()
    force_fields = _force_fields_for_variant(normalized_field_variant)
    normalized_strategies = _normalize_strategies(strategies or DEFAULT_STRATEGIES)
    solver_profile = _normalize_solver_profile(
        solver_parameter_profile,
        time_limit_seconds=float(time_limit_seconds),
        worker_count=int(worker_count),
    )
    started = time.perf_counter()
    try:
        artifact_hashes = compute_exact_artifact_hashes(project_root)
        artifact_hash_error = None
    except Exception as exc:
        artifact_hashes = {}
        artifact_hash_error = f"{type(exc).__name__}: {exc}"

    context: Dict[str, Any] = {}
    model_error: Optional[str] = None
    entries: list[Dict[str, Any]] = []
    pairwise: list[Dict[str, Any]] = []
    target_group: Dict[str, Any] = {}
    try:
        context = _build_delta_context(
            project_root,
            candidate=str(candidate),
            anchor_idx=int(anchor_idx),
            master_search_profile=str(master_search_profile),
        )
        group_by_id = {
            str(group.get("group_id", "")): group
            for group in list(context["ordered_groups"])
            if isinstance(group, Mapping)
        }
        target_group = dict(group_by_id.get(normalized_group_id) or {})
        if not target_group:
            raise ValueError(f"Unknown target group id: {normalized_group_id}")
        entries = [
            _evaluate_strategy(
                context=context,
                group=target_group,
                strategy=strategy,
                anchor_idx=int(anchor_idx),
                force_fields=force_fields,
                time_limit_seconds=float(time_limit_seconds),
                solver_profile=solver_profile,
            )
            for strategy in normalized_strategies
        ]
        pairwise = _pairwise_overlap(entries)
    except Exception as exc:
        model_error = f"{type(exc).__name__}: {exc}"

    status = _status_from_entries(entries, model_error=model_error)
    return {
        "metadata": {
            "source": GREEDY_POSE_ORDER_COMPARISON_SOURCE,
            "generated_at": now_iso(),
            "diagnostic_semantics": "greedy_pose_order_comparison_not_proof_source",
        },
        "paths": {"project_root": str(project_root)},
        "candidate": {
            "key": str(candidate),
            "ghost_rect": _candidate_rect(str(candidate)),
            "anchor_idx": int(anchor_idx),
        },
        "profile": {
            "group_id": normalized_group_id,
            "field_variant": normalized_field_variant,
            "force_fields": list(force_fields),
            "strategies": list(normalized_strategies),
            "master_search_profile": str(master_search_profile),
            "time_limit_seconds": float(time_limit_seconds),
            "worker_count": int(worker_count),
            "solver_parameter_profile": dict(solver_profile),
        },
        "artifact_hashes": dict(artifact_hashes),
        "artifact_hash_error": artifact_hash_error,
        "context": {
            "ghost_anchor_count": int(context.get("ghost_anchor_count", 0)),
            "blocked_cell_count": int(context.get("blocked_cell_count", 0)),
            "ordered_group_count": int(context.get("ordered_group_count", 0)),
            "target_group": _compact_group(target_group) if target_group else {},
        },
        "status": status,
        "comparison": {
            "entries": entries,
            "status_counts": _status_counts(entries),
            "pairwise_overlap": pairwise,
            "single_group_blocked_vs_full_blocked": _pairwise_named(
                pairwise,
                "single_group_blocked",
                "full_blocked",
            ),
        },
        "timing": {"total_seconds": float(time.perf_counter() - started)},
        "model_error": model_error,
        "checks": _checks(status, entries, model_error),
    }


def render_phase3b_greedy_pose_order_comparison_markdown(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    profile = _mapping(report.get("profile"))
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    lines = [
        "# Phase 3B Greedy Pose Order Comparison",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Anchor: {candidate.get('anchor_idx')}",
        f"- Group: {profile.get('group_id')}",
        f"- Field variant: {profile.get('field_variant')}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        "",
        "## Strategy Matrix",
        "",
        "| Strategy | Complete | Target poses | Validation | Forced labels | Wall | Branches | Conflicts |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in list(comparison.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        validation = _mapping(entry.get("target_validation"))
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(entry.get("strategy")),
                    _markdown_cell(entry.get("target_complete")),
                    _markdown_cell(",".join(str(v) for v in entry.get("target_pose_indices", []))),
                    _markdown_cell(validation.get("status")),
                    _markdown_cell(validation.get("forced_slot_field_count")),
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


def render_phase3b_greedy_pose_order_comparison_text(
    report: Mapping[str, Any],
) -> str:
    candidate = _mapping(report.get("candidate"))
    profile = _mapping(report.get("profile"))
    status = _mapping(report.get("status"))
    comparison = _mapping(report.get("comparison"))
    lines = [
        "Phase 3B greedy pose order comparison",
        f"candidate={candidate.get('key')}",
        f"anchor_idx={candidate.get('anchor_idx')}",
        "diagnostic_semantics=greedy_pose_order_comparison_not_proof_source",
        f"group_id={profile.get('group_id')}",
        f"field_variant={profile.get('field_variant')}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
    ]
    for entry in list(comparison.get("entries", [])):
        if not isinstance(entry, Mapping):
            continue
        validation = _mapping(entry.get("target_validation"))
        lines.append(
            "strategy="
            f"{entry.get('strategy')} "
            f"target_complete={entry.get('target_complete')} "
            f"poses={','.join(str(v) for v in entry.get('target_pose_indices', []))} "
            f"status={validation.get('status')} "
            f"forced_labels={validation.get('forced_slot_field_count')} "
            f"wall={validation.get('wall_time')} "
            f"branches={validation.get('branches')} "
            f"conflicts={validation.get('conflicts')}"
        )
    for overlap in list(comparison.get("pairwise_overlap", [])):
        if isinstance(overlap, Mapping):
            lines.append(
                "overlap="
                f"{overlap.get('left')}:{overlap.get('right')} "
                f"pose_intersection={overlap.get('pose_intersection_count')} "
                f"label_intersection={overlap.get('label_intersection_count')}"
            )
    return "\n".join(lines) + "\n"


def _evaluate_strategy(
    *,
    context: Mapping[str, Any],
    group: Mapping[str, Any],
    strategy: str,
    anchor_idx: int,
    force_fields: Sequence[str],
    time_limit_seconds: float,
    solver_profile: Mapping[str, Any],
) -> Dict[str, Any]:
    model = context["model"]
    group_id = str(group.get("group_id", ""))
    ordered_groups = [group]
    blocked_cells = set(context.get("blocked_cells", set()))
    custom_group_orders: Optional[Dict[str, Sequence[int]]] = None
    if str(strategy).startswith("full_"):
        ordered_groups = [
            item for item in list(context.get("ordered_groups", [])) if isinstance(item, Mapping)
        ]
    if "_unblocked" in str(strategy):
        blocked_cells = set()
    if "y_then_x" in str(strategy):
        custom_group_orders = _y_then_x_orders(
            model=model,
            ordered_groups=ordered_groups,
            candidates_by_group=_mapping(context.get("candidates_by_group")),
        )
    greedy = model._run_mandatory_greedy_pass(
        ordered_groups=ordered_groups,
        candidates_by_group=context["candidates_by_group"],
        blocked_cells=blocked_cells,
        custom_group_orders=custom_group_orders,
        stop_on_first_failure=True,
    )
    target_hint = _target_solution_hint(group=group, greedy=greedy)
    target_validation = _compact_validation(
        model._validate_coordinate_forced_hint(
            solution_hint=target_hint,
            ghost_anchor_hint_idx=int(anchor_idx),
            time_limit_seconds=float(time_limit_seconds),
            require_complete=False,
            solver_parameter_profile=solver_profile,
            force_fields=tuple(force_fields),
            collect_force_equality_labels=True,
        )
    )
    labels = [
        dict(label)
        for label in list(target_validation.get("force_equality_labels", []))
        if isinstance(label, Mapping)
    ]
    return {
        "strategy": str(strategy),
        "ordered_group_count": int(len(ordered_groups)),
        "blocked_cell_count": int(len(blocked_cells)),
        "uses_custom_group_order": custom_group_orders is not None,
        "greedy": _compact_greedy(greedy),
        "target_complete": len(target_hint) == int(group.get("count", 0)),
        "target_pose_indices": [
            int(pose_idx) for pose_idx in list(target_hint.values())
        ],
        "target_xy": _target_pose_xy(model=model, group=group, target_hint=target_hint),
        "target_validation": target_validation,
        "force_equality_labels": labels,
        "stable_keys": [str(label.get("stable_key")) for label in labels],
    }


def _target_solution_hint(
    *,
    group: Mapping[str, Any],
    greedy: Mapping[str, Any],
) -> Dict[str, int]:
    solution_hint = {
        str(key): int(value)
        for key, value in dict(greedy.get("solution_hint", {})).items()
    }
    target_ids = [str(item) for item in list(group.get("instance_ids", []))]
    return {
        instance_id: int(solution_hint[instance_id])
        for instance_id in target_ids
        if instance_id in solution_hint
    }


def _target_pose_xy(
    *,
    model: Any,
    group: Mapping[str, Any],
    target_hint: Mapping[str, int],
) -> list[Dict[str, Any]]:
    tpl = str(group.get("facility_type", ""))
    delegate = getattr(model, "_coordinate_delegate", None)
    tuples = getattr(delegate, "_template_pose_tuple_by_idx", {}).get(tpl, {})
    result: list[Dict[str, Any]] = []
    for slot_index, (solution_id, pose_idx) in enumerate(dict(target_hint).items()):
        pose_tuple = tuples.get(int(pose_idx))
        if pose_tuple is None:
            result.append(
                {
                    "slot_index": int(slot_index),
                    "solution_id": str(solution_id),
                    "pose_index": int(pose_idx),
                    "x": None,
                    "y": None,
                    "mode": None,
                }
            )
            continue
        x_val, y_val, mode_id = pose_tuple
        result.append(
            {
                "slot_index": int(slot_index),
                "solution_id": str(solution_id),
                "pose_index": int(pose_idx),
                "x": int(x_val),
                "y": int(y_val),
                "mode": int(mode_id),
            }
        )
    return result


def _y_then_x_orders(
    *,
    model: Any,
    ordered_groups: Sequence[Mapping[str, Any]],
    candidates_by_group: Mapping[str, Any],
) -> Dict[str, Sequence[int]]:
    result: Dict[str, Sequence[int]] = {}
    for group in ordered_groups:
        group_id = str(group.get("group_id", ""))
        tpl = str(group.get("facility_type", ""))
        candidates = [int(pose_idx) for pose_idx in list(candidates_by_group.get(group_id, []))]
        sorter = getattr(model, "_y_then_x_pose_order", None)
        if callable(sorter):
            result[group_id] = list(sorter(tpl, candidates))
        else:
            result[group_id] = list(candidates)
    return result


def _pairwise_overlap(entries: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    result: list[Dict[str, Any]] = []
    for index, left in enumerate(entries):
        left_poses = {int(value) for value in list(left.get("target_pose_indices", []))}
        left_keys = {str(value) for value in list(left.get("stable_keys", []))}
        for right in list(entries)[index + 1 :]:
            right_poses = {int(value) for value in list(right.get("target_pose_indices", []))}
            right_keys = {str(value) for value in list(right.get("stable_keys", []))}
            result.append(
                {
                    "left": left.get("strategy"),
                    "right": right.get("strategy"),
                    "pose_intersection_count": int(len(left_poses & right_poses)),
                    "label_intersection_count": int(len(left_keys & right_keys)),
                    "left_pose_count": int(len(left_poses)),
                    "right_pose_count": int(len(right_poses)),
                }
            )
    return result


def _pairwise_named(
    pairwise: Sequence[Mapping[str, Any]],
    left: str,
    right: str,
) -> Dict[str, Any]:
    for entry in pairwise:
        names = {str(entry.get("left")), str(entry.get("right"))}
        if names == {str(left), str(right)}:
            return dict(entry)
    return {}


def _status_from_entries(
    entries: Sequence[Mapping[str, Any]],
    *,
    model_error: Optional[str],
) -> Dict[str, Any]:
    if model_error is not None:
        return {
            "completed": True,
            "evaluated": False,
            "outcome": "diagnostic_error",
            "recommendation": "Greedy pose order comparison failed; inspect model_error.",
        }
    statuses = {
        str(_mapping(entry.get("target_validation")).get("status", ""))
        for entry in entries
    }
    if "INFEASIBLE" in statuses and len(statuses) > 1:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "ordering_sensitive_infeasible",
            "recommendation": (
                "INFEASIBLE depends on greedy pose ordering; keep evidence diagnostic "
                "until an exact-safe order-independent condition is found."
            ),
        }
    if "INFEASIBLE" in statuses:
        return {
            "completed": True,
            "evaluated": True,
            "outcome": "all_evaluated_orders_infeasible",
            "recommendation": "All evaluated orderings are infeasible; consider broader exact-safe proof design.",
        }
    return {
        "completed": True,
        "evaluated": bool(entries),
        "outcome": "no_ordering_infeasible_found",
        "recommendation": "No evaluated ordering reproduced INFEASIBLE; inspect diagnostics.",
    }


def _checks(
    status: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
    model_error: Optional[str],
) -> list[Dict[str, str]]:
    statuses = _status_counts(entries)
    return [
        _check(
            "comparison_evaluated",
            "pass" if bool(status.get("evaluated", False)) else "fail",
            str(status.get("outcome")),
        ),
        _check(
            "infeasible_order_present",
            "pass" if int(statuses.get("INFEASIBLE", 0)) > 0 else "fail",
            f"status_counts={statuses}",
        ),
        _check(
            "ordering_sensitivity_recorded",
            "pass"
            if str(status.get("outcome")) == "ordering_sensitive_infeasible"
            else "skipped",
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
        status = str(_mapping(entry.get("target_validation")).get("status", ""))
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _normalize_strategies(strategies: Sequence[str]) -> tuple[str, ...]:
    allowed = set(DEFAULT_STRATEGIES)
    result: list[str] = []
    seen: set[str] = set()
    for raw in strategies:
        for part in str(raw).split(","):
            strategy = part.strip()
            if not strategy:
                continue
            if strategy not in allowed:
                raise ValueError(
                    f"Unsupported strategy: {strategy}; expected one of "
                    + ", ".join(DEFAULT_STRATEGIES)
                )
            if strategy in seen:
                continue
            seen.add(strategy)
            result.append(strategy)
    if not result:
        raise ValueError("At least one strategy is required.")
    return tuple(result)


def _force_fields_for_variant(field_variant: str) -> tuple[str, ...]:
    key = str(field_variant).strip()
    if key not in FIELD_CHANNELS_BY_VARIANT:
        raise ValueError(
            f"Unsupported field variant: {field_variant!r}; expected one of "
            + ", ".join(FIELD_CHANNEL_VARIANTS)
        )
    return tuple(FIELD_CHANNELS_BY_VARIANT[key])


def _compact_group(group: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "group_id": str(group.get("group_id", "")),
        "facility_type": str(group.get("facility_type", "")),
        "operation_type": str(group.get("operation_type", "")),
        "required_count": int(group.get("count", 0)),
    }


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
