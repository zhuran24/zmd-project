from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS,
    EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS_ENV,
    EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS,
    EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS_ENV,
    EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS,
    EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV,
    MasterPlacementModel,
)
from src.search.benders_loop import create_exact_search_session
from src.search.exact_campaign import compute_exact_artifact_hashes, now_iso

POSE_ORDER_VALIDATION_PROBE_SOURCE = "phase3b_pose_order_validation_probe_v1"


def build_phase3b_pose_order_validation_probe(
    project_root: Path,
    *,
    candidate: str = "68x19",
    anchor_idx: Optional[int] = None,
    ordering: str = "y_then_x",
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    boundary_port_precheck_max_anchors: Optional[int] = None,
    mandatory_rectangle_precheck_max_anchors: Optional[int] = None,
    validation_seconds: Optional[float] = None,
    max_prefix_groups: Optional[int] = None,
) -> Dict[str, Any]:
    project_root = Path(project_root).resolve()
    ghost_w, ghost_h = _parse_candidate(candidate)
    ordering = _normalize_ordering(ordering)
    caps = {
        EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS_ENV: boundary_port_precheck_max_anchors,
        EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV: mandatory_rectangle_precheck_max_anchors,
        EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS_ENV: validation_seconds,
    }
    resolved_caps = {
        "boundary_port_precheck_max_anchors": _resolved_int_cap(
            EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS_ENV,
            EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS,
            boundary_port_precheck_max_anchors,
        ),
        "mandatory_rectangle_precheck_max_anchors": _resolved_int_cap(
            EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV,
            EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS,
            mandatory_rectangle_precheck_max_anchors,
        ),
        "validation_seconds": _resolved_float_cap(
            EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS_ENV,
            EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS,
            validation_seconds,
        ),
    }

    started = time.perf_counter()
    hash_error: Optional[str] = None
    try:
        artifact_hashes = compute_exact_artifact_hashes(project_root)
    except Exception as exc:
        artifact_hashes = {}
        hash_error = f"{type(exc).__name__}: {exc}"

    with _temporary_env_caps(caps):
        session_started = time.perf_counter()
        exact_session = create_exact_search_session(
            project_root,
            solve_mode="certified_exact",
            master_search_profile=master_search_profile,
        )
        session_build_seconds = time.perf_counter() - session_started
        model = MasterPlacementModel.from_exact_core(
            exact_session.core,
            ghost_rect=(ghost_w, ghost_h),
            master_search_profile=master_search_profile,
        )
        warm_start: Optional[Mapping[str, Any]] = None
        selected_anchor_idx = anchor_idx
        if selected_anchor_idx is None:
            warm_start = model.build_exact_candidate_warm_start()
            selected_anchor_idx = _first_rejection_anchor(
                warm_start,
                ordering=ordering,
            )
        if selected_anchor_idx is None:
            return _base_report(
                project_root=project_root,
                candidate=f"{ghost_w}x{ghost_h}",
                ghost_w=ghost_w,
                ghost_h=ghost_h,
                ordering=ordering,
                anchor_idx=None,
                master_search_profile=master_search_profile,
                resolved_caps=resolved_caps,
                artifact_hashes=artifact_hashes,
                artifact_hash_error=hash_error,
                session_build_seconds=session_build_seconds,
                total_seconds=time.perf_counter() - started,
                status={
                    "probe_complete": False,
                    "outcome": "missing_rejection_anchor",
                    "recommendation": (
                        "Pass --anchor-index explicitly or run start-compatibility "
                        "first to produce pose-order rejection samples."
                    ),
                },
                diagnostics={"warm_start": _compact_warm_start(warm_start or {})},
            )

        if int(selected_anchor_idx) < 0 or int(selected_anchor_idx) >= len(model._ghost_domains):
            return _base_report(
                project_root=project_root,
                candidate=f"{ghost_w}x{ghost_h}",
                ghost_w=ghost_w,
                ghost_h=ghost_h,
                ordering=ordering,
                anchor_idx=int(selected_anchor_idx),
                master_search_profile=master_search_profile,
                resolved_caps=resolved_caps,
                artifact_hashes=artifact_hashes,
                artifact_hash_error=hash_error,
                session_build_seconds=session_build_seconds,
                total_seconds=time.perf_counter() - started,
                status={
                    "probe_complete": False,
                    "outcome": "anchor_index_out_of_range",
                    "recommendation": "Choose an anchor index from this candidate's ghost domain.",
                },
                diagnostics={"ghost_anchor_count": int(len(model._ghost_domains))},
            )

        candidates_by_group = {
            str(group["group_id"]): model._candidate_pose_indices_for_group(group)
            for group in model._mandatory_groups
        }
        ordered_groups = model._ordered_mandatory_groups_for_greedy(candidates_by_group)
        custom_group_orders = _build_custom_group_orders(
            model,
            ordered_groups=ordered_groups,
            candidates_by_group=candidates_by_group,
            ordering=ordering,
        )
        domain = model._ghost_domains[int(selected_anchor_idx)]
        blocked_cells = {
            (int(cell[0]), int(cell[1]))
            for cell in list(domain.get("cells", []))
        }
        full_greedy = model._run_mandatory_greedy_pass(
            ordered_groups=ordered_groups,
            candidates_by_group=candidates_by_group,
            blocked_cells=set(blocked_cells),
            custom_group_orders=custom_group_orders,
            stop_on_first_failure=True,
        )
        validation_seconds_resolved = float(resolved_caps["validation_seconds"])
        full_validation = _compact_validation(
            model._validate_coordinate_forced_hint(
                solution_hint=dict(full_greedy.get("solution_hint", {})),
                ghost_anchor_hint_idx=int(selected_anchor_idx),
                time_limit_seconds=validation_seconds_resolved,
            )
            if bool(full_greedy.get("complete", False))
            else {
                "attempted": False,
                "status": "SKIPPED",
                "accepted": False,
                "reason": "full_greedy_incomplete",
                "forced_slot_field_count": 0,
                "forced_ghost_anchor": True,
            }
        )
        prefix_probe = _build_prefix_probe(
            model,
            ordered_groups=ordered_groups,
            candidates_by_group=candidates_by_group,
            custom_group_orders=custom_group_orders,
            blocked_cells=blocked_cells,
            anchor_idx=int(selected_anchor_idx),
            validation_seconds=validation_seconds_resolved,
            max_prefix_groups=max_prefix_groups,
        )

    status = _status_from_probe(full_greedy, full_validation, prefix_probe)
    return _base_report(
        project_root=project_root,
        candidate=f"{ghost_w}x{ghost_h}",
        ghost_w=ghost_w,
        ghost_h=ghost_h,
        ordering=ordering,
        anchor_idx=int(selected_anchor_idx),
        master_search_profile=master_search_profile,
        resolved_caps=resolved_caps,
        artifact_hashes=artifact_hashes,
        artifact_hash_error=hash_error,
        session_build_seconds=session_build_seconds,
        total_seconds=time.perf_counter() - started,
        status=status,
        diagnostics={
            "ghost_anchor_count": int(len(model._ghost_domains)),
            "blocked_cell_count": int(len(blocked_cells)),
            "full_greedy": _compact_greedy(full_greedy),
            "full_validation": full_validation,
            "prefix_probe": prefix_probe,
            "warm_start": _compact_warm_start(warm_start or {}),
        },
    )


def render_phase3b_pose_order_validation_probe_markdown(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    profile = _mapping(report.get("profile"))
    status = _mapping(report.get("status"))
    diag = _mapping(report.get("diagnostics"))
    prefix = _mapping(diag.get("prefix_probe"))
    lines = [
        "# Phase 3B Pose-Order Validation Probe",
        "",
        f"- Candidate: {candidate.get('key')}",
        f"- Anchor: {candidate.get('anchor_idx')}",
        f"- Ordering: {profile.get('ordering')}",
        f"- Outcome: {status.get('outcome')}",
        f"- Recommendation: {status.get('recommendation')}",
        f"- First infeasible prefix: {prefix.get('first_infeasible_prefix_group_count')}",
        "",
    ]
    first_group = _mapping(prefix.get("first_infeasible_group"))
    if first_group:
        lines.extend(
            [
                "## First Infeasible Prefix",
                "",
                f"- Group: {first_group.get('group_id')}",
                f"- Facility type: {first_group.get('facility_type')}",
                f"- Operation type: {first_group.get('operation_type')}",
                f"- Required count: {first_group.get('required_count')}",
                "",
            ]
        )
    rows = [
        entry
        for entry in list(prefix.get("prefix_results", []))
        if isinstance(entry, Mapping)
    ]
    if rows:
        lines.extend(
            [
                "## Prefix Results",
                "",
                "| Prefix | Last group | Greedy | Status | Accepted | Reason | Forced slots |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for entry in rows:
            group = _mapping(entry.get("last_group"))
            validation = _mapping(entry.get("validation"))
            lines.append(
                "| "
                + " | ".join(
                    [
                        _markdown_cell(entry.get("prefix_group_count")),
                        _markdown_cell(group.get("group_id")),
                        _markdown_cell(entry.get("greedy_complete")),
                        _markdown_cell(validation.get("status")),
                        _markdown_cell(validation.get("accepted")),
                        _markdown_cell(validation.get("reason")),
                        _markdown_cell(validation.get("forced_slot_field_count")),
                    ]
                )
                + " |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def render_phase3b_pose_order_validation_probe_text(report: Mapping[str, Any]) -> str:
    candidate = _mapping(report.get("candidate"))
    profile = _mapping(report.get("profile"))
    status = _mapping(report.get("status"))
    diag = _mapping(report.get("diagnostics"))
    prefix = _mapping(diag.get("prefix_probe"))
    lines = [
        "Phase 3B pose-order validation probe",
        f"candidate={candidate.get('key')}",
        f"anchor_idx={candidate.get('anchor_idx')}",
        f"ordering={profile.get('ordering')}",
        f"outcome={status.get('outcome')}",
        f"recommendation={status.get('recommendation')}",
        f"first_infeasible_prefix_group_count={prefix.get('first_infeasible_prefix_group_count')}",
    ]
    first_group = _mapping(prefix.get("first_infeasible_group"))
    if first_group:
        lines.append(
            "first_infeasible_group="
            f"{first_group.get('group_id')}/"
            f"{first_group.get('facility_type')} "
            f"operation={first_group.get('operation_type')} "
            f"required={first_group.get('required_count')}"
        )
    for entry in list(prefix.get("prefix_results", [])):
        if not isinstance(entry, Mapping):
            continue
        group = _mapping(entry.get("last_group"))
        validation = _mapping(entry.get("validation"))
        lines.append(
            "prefix_result="
            f"prefix={entry.get('prefix_group_count')} "
            f"group={group.get('group_id')} "
            f"greedy_complete={bool(entry.get('greedy_complete', False))} "
            f"status={validation.get('status')} "
            f"accepted={bool(validation.get('accepted', False))} "
            f"reason={validation.get('reason')} "
            f"forced_slots={validation.get('forced_slot_field_count')}"
        )
    return "\n".join(lines) + "\n"


def _build_prefix_probe(
    model: MasterPlacementModel,
    *,
    ordered_groups: Sequence[Mapping[str, Any]],
    candidates_by_group: Mapping[str, Sequence[int]],
    custom_group_orders: Mapping[str, Sequence[int]],
    blocked_cells: set[Tuple[int, int]],
    anchor_idx: int,
    validation_seconds: float,
    max_prefix_groups: Optional[int],
) -> Dict[str, Any]:
    group_count = int(len(ordered_groups))
    limit = group_count if max_prefix_groups is None else max(0, int(max_prefix_groups))
    limit = min(group_count, limit)
    prefix_results: List[Dict[str, Any]] = []
    first_infeasible: Optional[Dict[str, Any]] = None
    for prefix_count in range(1, limit + 1):
        prefix_groups = list(ordered_groups[:prefix_count])
        greedy = model._run_mandatory_greedy_pass(
            ordered_groups=prefix_groups,
            candidates_by_group=candidates_by_group,
            blocked_cells=set(blocked_cells),
            custom_group_orders=custom_group_orders,
            stop_on_first_failure=True,
        )
        if bool(greedy.get("complete", False)):
            validation = _compact_validation(
                model._validate_coordinate_forced_hint(
                    solution_hint=dict(greedy.get("solution_hint", {})),
                    ghost_anchor_hint_idx=int(anchor_idx),
                    time_limit_seconds=float(validation_seconds),
                    require_complete=False,
                )
            )
        else:
            validation = _compact_validation(
                {
                    "attempted": False,
                    "status": "SKIPPED",
                    "accepted": False,
                    "reason": "greedy_prefix_incomplete",
                    "forced_slot_field_count": 0,
                    "forced_ghost_anchor": True,
                }
            )
        entry = {
            "prefix_group_count": int(prefix_count),
            "last_group": _compact_group(prefix_groups[-1]),
            "greedy_complete": bool(greedy.get("complete", False)),
            "greedy": _compact_greedy(greedy),
            "validation": validation,
        }
        prefix_results.append(entry)
        if (
            first_infeasible is None
            and bool(greedy.get("complete", False))
            and str(validation.get("status")) == "INFEASIBLE"
        ):
            first_infeasible = dict(entry)
            break
        if not bool(greedy.get("complete", False)):
            break
    return {
        "evaluated_prefix_count": int(len(prefix_results)),
        "max_prefix_groups": int(limit),
        "first_infeasible_prefix_group_count": None
        if first_infeasible is None
        else int(first_infeasible["prefix_group_count"]),
        "first_infeasible_group": None
        if first_infeasible is None
        else dict(first_infeasible["last_group"]),
        "prefix_results": prefix_results,
    }


def _status_from_probe(
    full_greedy: Mapping[str, Any],
    full_validation: Mapping[str, Any],
    prefix_probe: Mapping[str, Any],
) -> Dict[str, Any]:
    first_prefix = prefix_probe.get("first_infeasible_prefix_group_count")
    if first_prefix is not None:
        return {
            "probe_complete": True,
            "outcome": "prefix_infeasible",
            "recommendation": (
                "Use the first infeasible prefix as B3/B2 repro input; "
                "do not treat it as terminal proof."
            ),
        }
    if not bool(full_greedy.get("complete", False)):
        return {
            "probe_complete": True,
            "outcome": "full_greedy_incomplete",
            "recommendation": "Investigate ordering/group packing before coordinate validation.",
        }
    if str(full_validation.get("status")) == "INFEASIBLE":
        return {
            "probe_complete": True,
            "outcome": "full_hint_infeasible_without_prefix_isolation",
            "recommendation": "Increase --max-prefix-groups or inspect non-prefix interactions.",
        }
    if bool(full_validation.get("accepted", False)):
        return {
            "probe_complete": True,
            "outcome": "full_hint_coordinate_compatible",
            "recommendation": "The selected anchor/order is compatible in this diagnostic run.",
        }
    return {
        "probe_complete": True,
        "outcome": "validation_unknown_or_skipped",
        "recommendation": "Raise validation seconds only in workspace diagnostics if needed.",
    }


def _base_report(
    *,
    project_root: Path,
    candidate: str,
    ghost_w: int,
    ghost_h: int,
    ordering: str,
    anchor_idx: Optional[int],
    master_search_profile: str,
    resolved_caps: Mapping[str, Any],
    artifact_hashes: Mapping[str, str],
    artifact_hash_error: Optional[str],
    session_build_seconds: float,
    total_seconds: float,
    status: Mapping[str, Any],
    diagnostics: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "metadata": {
            "source": POSE_ORDER_VALIDATION_PROBE_SOURCE,
            "generated_at": now_iso(),
        },
        "paths": {
            "project_root": str(project_root),
            "canonical_rules": "rules/canonical_rules.json",
            "candidate_placements": "data/preprocessed/candidate_placements.json",
            "mandatory_exact_instances": "data/preprocessed/mandatory_exact_instances.json",
            "generic_io_requirements": "data/preprocessed/generic_io_requirements.json",
        },
        "candidate": {
            "key": str(candidate),
            "ghost_rect": {"w": int(ghost_w), "h": int(ghost_h), "area": int(ghost_w) * int(ghost_h)},
            "anchor_idx": None if anchor_idx is None else int(anchor_idx),
        },
        "profile": {
            "master_search_profile": str(master_search_profile),
            "ordering": str(ordering),
            "caps": dict(resolved_caps),
        },
        "artifact_hashes": dict(artifact_hashes),
        "artifact_hash_error": artifact_hash_error,
        "status": dict(status),
        "timing": {
            "session_build_seconds": float(session_build_seconds),
            "total_seconds": float(total_seconds),
        },
        "diagnostics": dict(diagnostics),
        "checks": _checks(status),
    }


def _checks(status: Mapping[str, Any]) -> List[Dict[str, str]]:
    outcome = str(status.get("outcome", ""))
    return [
        {
            "check_id": "probe_completed",
            "status": "pass" if bool(status.get("probe_complete", False)) else "fail",
            "detail": outcome or "probe did not complete",
        },
        {
            "check_id": "prefix_infeasible_found",
            "status": "pass" if outcome == "prefix_infeasible" else "skipped",
            "detail": outcome or "no prefix result",
        },
    ]


def _build_custom_group_orders(
    model: MasterPlacementModel,
    *,
    ordered_groups: Sequence[Mapping[str, Any]],
    candidates_by_group: Mapping[str, Sequence[int]],
    ordering: str,
) -> Dict[str, List[int]]:
    return {
        str(group["group_id"]): _ordered_pose_indices(
            model,
            str(group["facility_type"]),
            candidates_by_group.get(str(group["group_id"]), []),
            ordering=ordering,
        )
        for group in ordered_groups
    }


def _ordered_pose_indices(
    model: MasterPlacementModel,
    tpl: str,
    candidate_indices: Sequence[int],
    *,
    ordering: str,
) -> List[int]:
    canonical = [int(pose_idx) for pose_idx in candidate_indices]
    anchors_by_pose = model._pose_anchor_by_template_pose.get(str(tpl), {})

    def anchor_xy(pose_idx: int) -> Tuple[int, int]:
        return anchors_by_pose.get(int(pose_idx), (0, 0))

    if ordering == "canonical":
        return list(canonical)
    if ordering == "reverse_canonical":
        return list(reversed(canonical))
    if ordering == "y_then_x":
        return sorted(
            canonical,
            key=lambda pose_idx: (
                int(anchor_xy(pose_idx)[1]),
                int(anchor_xy(pose_idx)[0]),
                str(model.facility_pools[str(tpl)][int(pose_idx)].get("pose_id", "")),
                int(pose_idx),
            ),
        )
    if ordering == "reverse_y_then_x":
        return list(reversed(_ordered_pose_indices(model, tpl, canonical, ordering="y_then_x")))
    if ordering == "x_then_y":
        return sorted(
            canonical,
            key=lambda pose_idx: (
                int(anchor_xy(pose_idx)[0]),
                int(anchor_xy(pose_idx)[1]),
                str(model.facility_pools[str(tpl)][int(pose_idx)].get("pose_id", "")),
                int(pose_idx),
            ),
        )
    if ordering == "reverse_x_then_y":
        return list(reversed(_ordered_pose_indices(model, tpl, canonical, ordering="x_then_y")))
    raise ValueError(f"Unsupported pose ordering: {ordering}")


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
        "require_complete": bool(payload.get("require_complete", False)),
        "wall_time": float(payload.get("wall_time", 0.0)),
        "branches": int(payload.get("branches", 0)),
        "conflicts": int(payload.get("conflicts", 0)),
    }


def _compact_greedy(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "complete": bool(payload.get("complete", False)),
        "hinted_groups": int(payload.get("hinted_groups", 0)),
        "hinted_instances": int(payload.get("hinted_instances", 0)),
        "first_failed_group_id": payload.get("first_failed_group_id"),
        "first_failed_group_template": payload.get("first_failed_group_template"),
        "first_failure_reason": payload.get("first_failure_reason"),
        "first_failed_group_position": payload.get("first_failed_group_position"),
    }


def _compact_group(group: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "group_id": str(group.get("group_id", "")),
        "facility_type": str(group.get("facility_type", "")),
        "operation_type": str(group.get("operation_type", "")),
        "required_count": int(group.get("count", 0)),
    }


def _compact_warm_start(warm_start: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "ghost_anchor_hint_status": warm_start.get("ghost_anchor_hint_status"),
        "warm_start_strategy": warm_start.get("warm_start_strategy"),
        "ghost_aware_pose_order_validation_rejected_count": int(
            warm_start.get("ghost_aware_pose_order_validation_rejected_count", 0)
        ),
        "ghost_aware_pose_order_validation_rejection_samples": [
            dict(entry)
            for entry in list(
                warm_start.get("ghost_aware_pose_order_validation_rejection_samples", [])
            )
            if isinstance(entry, Mapping)
        ],
    }


def _first_rejection_anchor(
    warm_start: Mapping[str, Any],
    *,
    ordering: str,
) -> Optional[int]:
    for entry in list(warm_start.get("ghost_aware_pose_order_validation_rejection_samples", [])):
        if not isinstance(entry, Mapping):
            continue
        if str(entry.get("ordering", "")) != str(ordering):
            continue
        try:
            return int(entry.get("anchor_idx"))
        except Exception:
            continue
    return None


def _parse_candidate(candidate: str) -> Tuple[int, int]:
    parts = str(candidate).lower().split("x")
    if len(parts) != 2:
        raise ValueError(f"Invalid candidate {candidate!r}; expected WxH.")
    return int(parts[0]), int(parts[1])


def _normalize_ordering(ordering: str) -> str:
    normalized = str(ordering).strip().lower()
    supported = {
        "canonical",
        "reverse_canonical",
        "y_then_x",
        "reverse_y_then_x",
        "x_then_y",
        "reverse_x_then_y",
    }
    if normalized not in supported:
        raise ValueError(
            f"Unsupported ordering {ordering!r}; expected one of {sorted(supported)}."
        )
    return normalized


@contextmanager
def _temporary_env_caps(caps: Mapping[str, Optional[Any]]) -> Iterator[None]:
    previous: Dict[str, Optional[str]] = {
        str(key): os.environ.get(str(key)) for key in caps
    }
    try:
        for key, value in caps.items():
            if value is None:
                continue
            os.environ[str(key)] = str(value)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(str(key), None)
            else:
                os.environ[str(key)] = str(value)


def _resolved_int_cap(env_name: str, default: int, override: Optional[int]) -> int:
    if override is not None:
        return max(0, int(override))
    raw = os.environ.get(str(env_name))
    if raw is None or str(raw).strip() == "":
        return max(0, int(default))
    return max(0, int(str(raw).strip()))


def _resolved_float_cap(env_name: str, default: float, override: Optional[float]) -> float:
    if override is not None:
        return max(0.0, float(override))
    raw = os.environ.get(str(env_name))
    if raw is None or str(raw).strip() == "":
        return max(0.0, float(default))
    return max(0.0, float(str(raw).strip()))


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
