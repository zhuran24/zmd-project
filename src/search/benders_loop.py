"""
Benders loop entrypoint（Benders 循环入口）.

职责：
1. certified_exact（严格认证精确）与 exploratory（探索）模式切换。
2. exploratory 路径继续沿用 flow-driven 协同求解。
3. certified_exact 路径改为 flow 仅作诊断，binding/routing 给正式证据。
4. exact 路径只使用 safe static occupied-area lower bound。

文件目录索引 (≈5550 行, 行号大约值, vintage 2026-05-16):
- L1-50     模块 docstring + imports
- L95-510   工具函数 helpers:
    L95     _normalize_solve_mode (certified_exact / exploratory)
    L108-300 anchor119 row domain guard advisory 系列 (Phase 3B)
    L302-385 env resolvers (precheck max anchors, time budgets, log heartbeat lines)
    L386    _resolve_ghost_anchor_filter_from_env
    L445-510 instance solve_mode 归一化
- L803-840  static area lower bound 计算 (safe LB for cuts)
- L842-985  certification blockers 收集
- L986      class ExactSearchSession — 单 candidate 的搜索会话
- L1039     create_exact_search_session (工厂)
- L1057-1700 precheck / proof summary / boundary port 兼容性
- L1917     class LBBDController — Benders 主循环驱动 (主类)
- L3464     LBBDController.run_with_status (公开入口)
- L3558     _run_certified_exact (certified 路径主体, 含 warm-start + community hint)
    L3562    self._greedy_hint = warm_start["solution_hint"]
    L3565    EXACT_COMMUNITY_BLUEPRINT_HINT_PATH env 加载 + 合并 (2026-05-16 land)
    L3766    solve_hint = self._greedy_hint or None  (iteration 1 hint 注入点)
    L3844    self.master.solve(..., solution_hint=solve_hint, ...)
- L5120-5460 run_benders_for_ghost_rect 外部入口
- L5553      文件尾

主要外部 API:
- LBBDController(master, binding_solver, routing_solver, flow_solver,
                 max_iterations=30, master_seconds=600.0, ...)
    .run_with_status(...) -> (status_str, proof_summary)
    内部 dispatch certified_exact vs exploratory.

- create_exact_search_session(candidate_id, ghost_rect, ...) -> ExactSearchSession
- run_benders_for_ghost_rect(...) -> Benders 单 candidate 完整运行

env 变量 (本文件读): 见 docs/env_variable_index.md, 主要 A/B/D/G 组.
"""

from __future__ import annotations

import copy
import json
from collections import defaultdict
from dataclasses import dataclass
import os
from pathlib import Path
import time
from typing import Any, Callable, Dict, FrozenSet, List, Mapping, Optional, Sequence, Set, Tuple, cast

from ortools.sat.python import cp_model

from src.models.binding_subproblem import PortBindingModel
from src.models.power_placement_subproblem import (
    PowerPlacementSubproblem,
    inject_power_poles_into_solution,
)
from src.models.cut_manager import (
    BendersCut,
    CutManager,
    RUN_STATUS_CERTIFIED,
    RUN_STATUS_INFEASIBLE,
    RUN_STATUS_UNKNOWN,
    RUN_STATUS_UNPROVEN,
)
from src.models.flow_subproblem import FlowSubproblem, build_flow_network
from src.models.master_model import (
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT,
    EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT_ENV,
    ExactMasterCore,
    MasterPlacementModel,
    infer_certified_optional_lower_bounds,
    load_generic_io_requirements_artifact,
    load_project_data,
)
from src.models.routing_subproblem import (
    RoutingGrid,
    RoutingPlacementCore,
    RoutingSubproblem,
    run_exact_routing_precheck,
)
from src.search.phase3b.anchor119.guard_controls import (
    PHASE3B_ANCHOR119_ANCHOR_IDX,
    build_phase3b_anchor119_guard_runtime_state,
    build_phase3b_anchor119_guard_runtime_decision,
)
from src.search.phase3b.anchor119.guarded_precheck_runtime import (
    evaluate_phase3b_anchor119_guarded_precheck_advisory,
)
from src.search.exact_campaign import ExactCampaign, compute_exact_artifact_hashes, now_iso

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EXACT_REQUIRED_ARTIFACTS = {
    "mandatory_exact_instances": "data/preprocessed/mandatory_exact_instances.json",
    "candidate_placements": "data/preprocessed/candidate_placements.json",
    "generic_io_requirements": "data/preprocessed/generic_io_requirements.json",
    "canonical_rules": "rules/canonical_rules.json",
}

_EXACT_INTERNAL_STATUS_MASTER_CUT_ADDED_CONTINUE = "master_cut_added_continue"
_CERTIFIED_SOLVE_MODES = {"certified_exact", "exploratory"}
_CampaignHeartbeatCallback = Callable[[Mapping[str, Any]], None]
_PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS = 32
_PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV = (
    "EXACT_PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS"
)
_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS = 0
_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS_ENV = (
    "EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS"
)
_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS = 2.0
_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS_ENV = (
    "EXACT_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS"
)
EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_LINES_ENV = (
    "EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_LINES"
)
EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_MAX_CHARS_ENV = (
    "EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_MAX_CHARS"
)


def _normalize_solve_mode(
    solve_mode: Optional[str] = None,
    certification_mode: Optional[bool] = None,
) -> str:
    if certification_mode is not None:
        return "certified_exact" if certification_mode else "exploratory"
    if solve_mode is None:
        return "certified_exact"
    if solve_mode not in {"certified_exact", "exploratory"}:
        raise ValueError(f"Unsupported solve mode: {solve_mode}")
    return solve_mode


def _maybe_attach_anchor119_row_domain_guard_advisory(
    master_candidate_precheck_payload: Dict[str, Any],
    *,
    project_root: Path,
    ghost_w: int,
    ghost_h: int,
) -> None:
    advisory = evaluate_phase3b_anchor119_guarded_precheck_advisory(
        project_root=project_root,
        ghost_w=int(ghost_w),
        ghost_h=int(ghost_h),
        anchor_idx=PHASE3B_ANCHOR119_ANCHOR_IDX,
    )
    if not bool(advisory.get("enabled", False)):
        return
    proof_summary = advisory.get("proof_summary")
    if not isinstance(proof_summary, Mapping):
        return
    guard_payload = proof_summary.get("anchor119_mixed_lane_guarded_precheck")
    if not isinstance(guard_payload, Mapping):
        return
    runtime_decision = build_phase3b_anchor119_guard_runtime_decision(
        requested_state=guard_payload.get("requested_state"),
        effective_state=guard_payload.get("effective_state"),
        runtime_activation_allowed=bool(
            guard_payload.get("runtime_activation_allowed", False)
        ),
        would_trigger=bool(advisory.get("would_trigger", False)),
        triggered=bool(advisory.get("triggered", False)),
        reason=advisory.get("reason"),
        runtime_enablement_blockers=list(
            guard_payload.get("runtime_enablement_blockers", [])
        )
        if isinstance(guard_payload.get("runtime_enablement_blockers"), list)
        else [],
    )
    master_candidate_precheck_payload["anchor119_row_domain_guard_advisory"] = {
        "enabled": True,
        "would_trigger": bool(advisory.get("would_trigger", False)),
        "triggered": bool(advisory.get("triggered", False)),
        "reason": advisory.get("reason"),
        "runtime_decision": runtime_decision,
        **dict(guard_payload),
    }
    if bool(runtime_decision.get("apply_runtime_elimination", False)):
        master_candidate_precheck_payload.update(
            {
                "triggered": True,
                "precheck_reason": "anchor119_row_domain_runtime_guard",
                "master_solve_skipped": True,
                "supported": True,
                "considered_anchor_count": 1,
                "screened_infeasible_anchor_count": 1,
                "screen_pass_anchor_count": 0,
                "max_packable_min": None,
                "max_packable_max": None,
                "first_infeasible_anchor_idx": int(PHASE3B_ANCHOR119_ANCHOR_IDX),
                "first_infeasible_anchor_max_packable": None,
                "triggered_group_id": None,
                "triggered_group_facility_type": None,
                "triggered_group_operation_type": None,
                "triggered_group_required_count": 0,
            }
        )


def _maybe_attach_anchor119_row_domain_guard_advisory_to_proof_summary(
    proof_summary: Dict[str, Any],
    *,
    project_root: Path,
    ghost_w: int,
    ghost_h: int,
) -> None:
    master_candidate_precheck = proof_summary.get("master_candidate_precheck")
    if isinstance(master_candidate_precheck, Mapping):
        master_candidate_precheck_payload = dict(master_candidate_precheck)
    else:
        master_candidate_precheck_payload = {
            "triggered": False,
            "precheck_reason": None,
            "master_solve_skipped": False,
        }
    _maybe_attach_anchor119_row_domain_guard_advisory(
        master_candidate_precheck_payload,
        project_root=project_root,
        ghost_w=ghost_w,
        ghost_h=ghost_h,
    )
    if "anchor119_row_domain_guard_advisory" in master_candidate_precheck_payload:
        proof_summary["master_candidate_precheck"] = master_candidate_precheck_payload


def _copy_anchor119_row_domain_guard_advisory_from_proof_summary(
    master_candidate_precheck_payload: Dict[str, Any],
    *,
    proof_summary: Mapping[str, Any],
) -> bool:
    source_precheck = proof_summary.get("master_candidate_precheck")
    if not isinstance(source_precheck, Mapping):
        return False
    advisory = source_precheck.get("anchor119_row_domain_guard_advisory")
    if not isinstance(advisory, Mapping):
        return False
    master_candidate_precheck_payload["anchor119_row_domain_guard_advisory"] = dict(advisory)
    return True


def _maybe_build_anchor119_row_domain_runtime_precheck_result(
    *,
    project_root: Path,
    ghost_w: int,
    ghost_h: int,
    master_search_profile: str,
    mandatory_support_diagnostics_summary: Mapping[str, Any],
    default_boundary_port_precheck: Mapping[str, Any],
    exact_session: "ExactSearchSession",
) -> Optional[Dict[str, Any]]:
    runtime_state = build_phase3b_anchor119_guard_runtime_state()
    if not bool(runtime_state.get("runtime_requested", False)):
        return None
    proof_summary = _merge_reuse_metadata(
        {
            "mode": "certified_exact",
            "benders_iterations": 0,
            "master_status": "INFEASIBLE",
            "diagnostic_flow_status": "NOT_RUN",
            "enumerated_bindings": 0,
            "routing_attempts": 0,
            "used_greedy_hint": False,
            "greedy_hint_instances": 0,
            "master_hinted_literals": 0,
            "master_search_profile": str(master_search_profile),
            "master_boundary_port_feasibility": (
                _compact_exact_candidate_boundary_port_feasibility(
                    default_boundary_port_precheck
                )
            ),
            "master_mandatory_group_prechecks": (
                _default_exact_candidate_skipped_mandatory_group_prechecks(
                    skipped_due_to_upstream_precheck=False
                )
            ),
            "master_mandatory_support_diagnostics": dict(
                mandatory_support_diagnostics_summary
            ),
            "master_candidate_precheck": {
                "triggered": False,
                "precheck_reason": None,
                "master_solve_skipped": False,
                "supported": True,
                "considered_anchor_count": 0,
                "screened_infeasible_anchor_count": 0,
                "screen_pass_anchor_count": 0,
                "max_packable_min": None,
                "max_packable_max": None,
                "first_infeasible_anchor_idx": None,
                "first_infeasible_anchor_max_packable": None,
                "triggered_group_id": None,
                "triggered_group_facility_type": None,
                "triggered_group_operation_type": None,
                "triggered_group_required_count": 0,
            },
        },
        used_exact_core_reuse=True,
        core_build_seconds=float(exact_session.core_build_seconds),
        overlay_build_seconds=0.0,
        ghost_constraint_seconds=0.0,
        cut_replay_seconds=0.0,
    )
    _maybe_attach_anchor119_row_domain_guard_advisory_to_proof_summary(
        proof_summary,
        project_root=project_root,
        ghost_w=int(ghost_w),
        ghost_h=int(ghost_h),
    )
    master_candidate_precheck = proof_summary.get("master_candidate_precheck", {})
    if not isinstance(master_candidate_precheck, Mapping):
        return None
    advisory = master_candidate_precheck.get("anchor119_row_domain_guard_advisory")
    if not isinstance(advisory, Mapping):
        return None
    runtime_decision = advisory.get("runtime_decision")
    if not isinstance(runtime_decision, Mapping):
        return None
    if not bool(runtime_decision.get("apply_runtime_elimination", False)):
        return None
    return {
        "triggered": True,
        "status": RUN_STATUS_INFEASIBLE,
        "proof_summary": proof_summary,
        "boundary_port_precheck": dict(default_boundary_port_precheck),
    }


def _pre_master_mandatory_rectangle_precheck_max_anchors() -> int:
    raw_value = os.environ.get(_PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV)
    if raw_value is None or str(raw_value).strip() == "":
        return int(_PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS)
    try:
        return max(0, int(str(raw_value).strip()))
    except ValueError:
        raise ValueError(
            "Unsupported "
            f"{_PRE_MASTER_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV}: "
            f"{raw_value!r}; expected a non-negative integer."
        ) from None


def _pre_master_coordinate_validation_precheck_max_anchors() -> int:
    raw_value = os.environ.get(_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS_ENV)
    if raw_value is None or str(raw_value).strip() == "":
        return int(_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS)
    try:
        return max(0, int(str(raw_value).strip()))
    except ValueError:
        raise ValueError(
            "Unsupported "
            f"{_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_MAX_ANCHORS_ENV}: "
            f"{raw_value!r}; expected a non-negative integer."
        ) from None


def _pre_master_coordinate_validation_precheck_seconds() -> float:
    raw_value = os.environ.get(_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS_ENV)
    if raw_value is None or str(raw_value).strip() == "":
        return max(0.0, float(_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS))
    try:
        return max(0.0, float(str(raw_value).strip()))
    except ValueError:
        raise ValueError(
            "Unsupported "
            f"{_PRE_MASTER_COORDINATE_VALIDATION_PRECHECK_SECONDS_ENV}: "
            f"{raw_value!r}; expected a non-negative number."
        ) from None


def _warm_start_failed_anchor_sample_limit() -> int:
    raw_value = os.environ.get(EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT_ENV)
    if raw_value is None or str(raw_value).strip() == "":
        return max(0, int(EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT))
    try:
        return max(0, int(str(raw_value).strip()))
    except ValueError:
        raise ValueError(
            f"Unsupported {EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT_ENV}: "
            f"{raw_value!r}; expected a non-negative integer."
        ) from None


def _master_cp_sat_log_heartbeat_line_limit() -> int:
    raw_value = os.environ.get(EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_LINES_ENV)
    if raw_value is None or str(raw_value).strip() == "":
        return 0
    try:
        return min(500, max(0, int(str(raw_value).strip())))
    except ValueError:
        raise ValueError(
            f"Unsupported {EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_LINES_ENV}: "
            f"{raw_value!r}; expected a non-negative integer."
        ) from None


def _master_cp_sat_log_heartbeat_max_chars() -> int:
    raw_value = os.environ.get(EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_MAX_CHARS_ENV)
    if raw_value is None or str(raw_value).strip() == "":
        return 1000
    try:
        return min(4000, max(80, int(str(raw_value).strip())))
    except ValueError:
        raise ValueError(
            f"Unsupported {EXACT_MASTER_CP_SAT_LOG_HEARTBEAT_MAX_CHARS_ENV}: "
            f"{raw_value!r}; expected a positive integer."
        ) from None


EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV = "EXACT_MASTER_GHOST_ANCHOR_FILTER"


def _resolve_ghost_anchor_filter_from_env() -> Optional[FrozenSet[Tuple[int, int]]]:
    """A 方案 PoC: env 注入 ghost anchor 白名单, 减 1131 anchor 同时 build 的 RAM.

    Format: "x1,y1;x2,y2;...". 缺省/空 → 不 filter (保留旧 behavior).
    Invalid format → ValueError fail-fast, 不进 production path.
    """

    raw = os.environ.get(EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV, "")
    if not raw.strip():
        return None
    anchors: List[Tuple[int, int]] = []
    for token in raw.split(";"):
        token = token.strip()
        if not token:
            continue
        parts = [p.strip() for p in token.split(",")]
        if len(parts) != 2:
            raise ValueError(
                f"Unsupported {EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV}: "
                f"{raw!r}; expected 'x,y' pairs separated by ';'."
            )
        try:
            anchors.append((int(parts[0]), int(parts[1])))
        except ValueError:
            raise ValueError(
                f"Unsupported {EXACT_MASTER_GHOST_ANCHOR_FILTER_ENV}: "
                f"{raw!r}; non-integer coordinate in token {token!r}."
            ) from None
    return frozenset(anchors)


def _coordinate_validation_failure_sample_fields(entry: Mapping[str, Any]) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    for key in (
        "coordinate_validation_status",
        "coordinate_validation_reason",
        "coordinate_validation_solver_profile_id",
    ):
        if key in entry:
            fields[key] = str(entry.get(key, ""))
    for key in (
        "coordinate_validation_forced_slot_field_count",
        "coordinate_validation_forced_ghost_anchor",
    ):
        if key in entry:
            fields[key] = entry.get(key)
    for key in (
        "capacity_conflict",
        "same_x_strip_capacity_precheck",
        "ghost_overlap_forced_domain_precheck",
        "ghost_y_overlap_precheck",
        "signature_monotonic_precheck",
    ):
        value = entry.get(key)
        if isinstance(value, Mapping):
            fields[key] = dict(value)
    return fields


def _normalize_solve_mode_values(raw_value: Any) -> Tuple[Set[str], Optional[str]]:
    if raw_value is None:
        return set(), "missing"
    if isinstance(raw_value, str):
        raw_items = [raw_value]
    elif isinstance(raw_value, (list, tuple, set)):
        raw_items = list(raw_value)
    else:
        return set(), f"malformed_type:{type(raw_value).__name__}"

    normalized: Set[str] = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, str):
            return set(), f"malformed_member_type:{type(raw_item).__name__}"
        token = str(raw_item).strip()
        if not token:
            continue
        if token not in _CERTIFIED_SOLVE_MODES:
            return set(), f"unknown_mode:{token}"
        normalized.add(token)
    if not normalized:
        return set(), "missing"
    return normalized, None


def _normalize_instance_solve_modes(instance: Mapping[str, Any]) -> Tuple[Set[str], Optional[str]]:
    has_solve_mode = "solve_mode" in instance
    has_solve_modes = "solve_modes" in instance
    if not has_solve_mode and not has_solve_modes:
        return set(), "missing"

    normalized_solve_mode: Optional[Set[str]] = None
    normalized_solve_modes: Optional[Set[str]] = None
    issues: List[str] = []

    if has_solve_mode:
        modes, issue = _normalize_solve_mode_values(instance.get("solve_mode"))
        if issue is not None:
            issues.append(f"solve_mode:{issue}")
        else:
            normalized_solve_mode = modes

    if has_solve_modes:
        modes, issue = _normalize_solve_mode_values(instance.get("solve_modes"))
        if issue is not None:
            issues.append(f"solve_modes:{issue}")
        else:
            normalized_solve_modes = modes

    if issues:
        return set(), ";".join(issues)
    if normalized_solve_mode is not None and normalized_solve_modes is not None:
        if normalized_solve_mode != normalized_solve_modes:
            return set(), (
                "conflicting_mode_metadata:"
                f"solve_mode={sorted(normalized_solve_mode)};"
                f"solve_modes={sorted(normalized_solve_modes)}"
            )
        return set(normalized_solve_mode), None
    if normalized_solve_mode is not None:
        return set(normalized_solve_mode), None
    if normalized_solve_modes is not None:
        return set(normalized_solve_modes), None
    return set(), "missing"


def _reset_last_run_metadata() -> None:
    _publish_last_run_metadata({}, [], loaded_exact_safe_cut_count=0, generated_exact_safe_cut_count=0)


def _publish_last_run_metadata(
    proof_summary: Mapping[str, Any],
    exact_safe_cuts: Sequence[BendersCut],
    *,
    loaded_exact_safe_cut_count: int = 0,
    generated_exact_safe_cut_count: int = 0,
) -> None:
    normalized_proof_summary = dict(proof_summary)
    run_benders_for_ghost_rect.last_run_metadata = {  # type: ignore[attr-defined]
        "proof_summary": normalized_proof_summary,
        "exact_safe_cuts": [cut.to_dict() for cut in exact_safe_cuts],
        "loaded_exact_safe_cut_count": int(loaded_exact_safe_cut_count),
        "generated_exact_safe_cut_count": int(generated_exact_safe_cut_count),
        "fine_grained_exact_safe_cut_count": int(
            normalized_proof_summary.get("fine_grained_exact_safe_cut_count", 0)
        ),
        "binding_domain_empty_cut_count": int(
            normalized_proof_summary.get("binding_domain_empty_cut_count", 0)
        ),
        "routing_front_blocked_cut_count": int(
            normalized_proof_summary.get("routing_front_blocked_cut_count", 0)
        ),
        "routing_precheck_rejections": int(
            normalized_proof_summary.get("routing_precheck_rejections", 0)
        ),
        "routing_precheck_statuses": list(
            normalized_proof_summary.get("routing_precheck_statuses", [])
        ),
        "routing_domain_cells": int(
            normalized_proof_summary.get("routing_domain_cells", 0)
        ),
        "routing_terminal_core_cells": int(
            normalized_proof_summary.get("routing_terminal_core_cells", 0)
        ),
        "routing_state_space_vars": int(
            normalized_proof_summary.get("routing_state_space_vars", 0)
        ),
        "routing_local_pattern_pruned_states": int(
            normalized_proof_summary.get("routing_local_pattern_pruned_states", 0)
        ),
        "used_routing_core_reuse": bool(
            normalized_proof_summary.get("used_routing_core_reuse", False)
        ),
        "routing_core_build_seconds": float(
            normalized_proof_summary.get("routing_core_build_seconds", 0.0)
        ),
        "routing_overlay_build_seconds": float(
            normalized_proof_summary.get("routing_overlay_build_seconds", 0.0)
        ),
        "binding_domain_cache_hits": int(
            normalized_proof_summary.get("binding_domain_cache_hits", 0)
        ),
        "binding_domain_cache_misses": int(
            normalized_proof_summary.get("binding_domain_cache_misses", 0)
        ),
        "binding_domain_reused_instances": list(
            normalized_proof_summary.get("binding_domain_reused_instances", [])
        ),
        "master_search_profile": str(
            normalized_proof_summary.get("master_search_profile", "default_automatic")
        ),
        "power_pole_family_order": list(
            normalized_proof_summary.get("power_pole_family_order", [])
        ),
        "power_pole_family_count_literals": int(
            normalized_proof_summary.get("power_pole_family_count_literals", 0)
        ),
        "residual_optional_family_guided": bool(
            normalized_proof_summary.get("residual_optional_family_guided", False)
        ),
        "binding_search_profile": str(
            normalized_proof_summary.get("binding_search_profile", "exact_binding_guided_branching_v1")
        ),
        "diagnostic_flow_status": str(
            normalized_proof_summary.get("diagnostic_flow_status", "NOT_RUN")
        ),
        "master_status": normalized_proof_summary.get("master_status"),
        "binding_status": normalized_proof_summary.get("binding_status"),
        "routing_status": normalized_proof_summary.get("routing_status"),
        "mode": normalized_proof_summary.get("mode"),
        "used_exact_core_reuse": bool(normalized_proof_summary.get("used_exact_core_reuse", False)),
        "core_build_seconds": float(normalized_proof_summary.get("core_build_seconds", 0.0)),
        "overlay_build_seconds": float(normalized_proof_summary.get("overlay_build_seconds", 0.0)),
        "ghost_constraint_seconds": float(
            normalized_proof_summary.get("ghost_constraint_seconds", 0.0)
        ),
        "cut_replay_seconds": float(normalized_proof_summary.get("cut_replay_seconds", 0.0)),
        "master_representation": str(
            normalized_proof_summary.get("master_representation", "pose_bool_v1")
        ),
        "master_slot_counts": dict(
            normalized_proof_summary.get("master_slot_counts", {})
        ),
        "master_mode_literals": int(
            normalized_proof_summary.get("master_mode_literals", 0)
        ),
        "master_interval_count": int(
            normalized_proof_summary.get("master_interval_count", 0)
        ),
        "master_pose_bool_literals": int(
            normalized_proof_summary.get("master_pose_bool_literals", 0)
        ),
        "master_domain_encoding": str(
            normalized_proof_summary.get("master_domain_encoding", "")
        ),
        "master_domain_table_rows": int(
            normalized_proof_summary.get("master_domain_table_rows", 0)
        ),
        "master_mode_rect_domains": copy.deepcopy(
            normalized_proof_summary.get("master_mode_rect_domains", {})
        ),
        "power_pole_shell_lookup_pairs": copy.deepcopy(
            normalized_proof_summary.get("power_pole_shell_lookup_pairs", {})
        ),
        "power_coverage_representation": str(
            normalized_proof_summary.get("power_coverage_representation", "")
        ),
        "power_coverage_encoding": str(
            normalized_proof_summary.get("power_coverage_encoding", "")
        ),
        "power_coverage_powered_slots": int(
            normalized_proof_summary.get("power_coverage_powered_slots", 0)
        ),
        "power_coverage_pole_slots": int(
            normalized_proof_summary.get("power_coverage_pole_slots", 0)
        ),
        "power_coverage_cover_literals": int(
            normalized_proof_summary.get("power_coverage_cover_literals", 0)
        ),
        "power_coverage_witness_indices": int(
            normalized_proof_summary.get("power_coverage_witness_indices", 0)
        ),
        "power_coverage_element_constraints": int(
            normalized_proof_summary.get("power_coverage_element_constraints", 0)
        ),
        "power_coverage_radius": int(
            normalized_proof_summary.get("power_coverage_radius", 0)
        ),
        "power_capacity_shell_pairs": int(
            normalized_proof_summary.get("power_capacity_shell_pairs", 0)
        ),
        "power_capacity_shell_pair_evaluations": int(
            normalized_proof_summary.get("power_capacity_shell_pair_evaluations", 0)
        ),
        "power_capacity_signature_classes": int(
            normalized_proof_summary.get("power_capacity_signature_classes", 0)
        ),
        "power_capacity_signature_class_evaluations": int(
            normalized_proof_summary.get("power_capacity_signature_class_evaluations", 0)
        ),
        "power_capacity_compact_signature_classes": int(
            normalized_proof_summary.get("power_capacity_compact_signature_classes", 0)
        ),
        "power_capacity_compact_signature_evaluations": int(
            normalized_proof_summary.get(
                "power_capacity_compact_signature_evaluations",
                0,
            )
        ),
        "power_capacity_compact_signature_cache_hits": int(
            normalized_proof_summary.get(
                "power_capacity_compact_signature_cache_hits",
                0,
            )
        ),
        "power_capacity_compact_signature_cache_misses": int(
            normalized_proof_summary.get(
                "power_capacity_compact_signature_cache_misses",
                0,
            )
        ),
        "power_capacity_rect_dp_evaluations": int(
            normalized_proof_summary.get("power_capacity_rect_dp_evaluations", 0)
        ),
        "power_capacity_rect_dp_cache_hits": int(
            normalized_proof_summary.get("power_capacity_rect_dp_cache_hits", 0)
        ),
        "power_capacity_rect_dp_cache_misses": int(
            normalized_proof_summary.get("power_capacity_rect_dp_cache_misses", 0)
        ),
        "power_capacity_rect_dp_state_merges": int(
            normalized_proof_summary.get("power_capacity_rect_dp_state_merges", 0)
        ),
        "power_capacity_rect_dp_peak_line_states": int(
            normalized_proof_summary.get("power_capacity_rect_dp_peak_line_states", 0)
        ),
        "power_capacity_rect_dp_peak_pos_states": int(
            normalized_proof_summary.get("power_capacity_rect_dp_peak_pos_states", 0)
        ),
        "power_capacity_rect_dp_compiled_signatures": int(
            normalized_proof_summary.get("power_capacity_rect_dp_compiled_signatures", 0)
        ),
        "power_capacity_rect_dp_compiled_start_options": int(
            normalized_proof_summary.get("power_capacity_rect_dp_compiled_start_options", 0)
        ),
        "power_capacity_rect_dp_deduped_start_options": int(
            normalized_proof_summary.get("power_capacity_rect_dp_deduped_start_options", 0)
        ),
        "power_capacity_rect_dp_compiled_line_subsets": int(
            normalized_proof_summary.get("power_capacity_rect_dp_compiled_line_subsets", 0)
        ),
        "power_capacity_rect_dp_peak_line_subset_options": int(
            normalized_proof_summary.get("power_capacity_rect_dp_peak_line_subset_options", 0)
        ),
        "power_capacity_rect_dp_v3_fallbacks": int(
            normalized_proof_summary.get("power_capacity_rect_dp_v3_fallbacks", 0)
        ),
        "power_capacity_compact_rect_cpsat_evaluations": int(
            normalized_proof_summary.get("power_capacity_compact_rect_cpsat_evaluations", 0)
        ),
        "power_capacity_compact_rect_cpsat_cache_hits": int(
            normalized_proof_summary.get("power_capacity_compact_rect_cpsat_cache_hits", 0)
        ),
        "power_capacity_compact_rect_cpsat_selected_cases": int(
            normalized_proof_summary.get("power_capacity_compact_rect_cpsat_selected_cases", 0)
        ),
        "power_capacity_compact_rect_cpsat_rect_dp_fallbacks": int(
            normalized_proof_summary.get("power_capacity_compact_rect_cpsat_rect_dp_fallbacks", 0)
        ),
        "power_capacity_normalized_rect_signature_count": int(
            normalized_proof_summary.get("power_capacity_normalized_rect_signature_count", 0)
        ),
        "power_capacity_normalized_rect_cache_hits": int(
            normalized_proof_summary.get("power_capacity_normalized_rect_cache_hits", 0)
        ),
        "power_capacity_normalized_rect_cache_misses": int(
            normalized_proof_summary.get("power_capacity_normalized_rect_cache_misses", 0)
        ),
        "power_capacity_legacy_signature_materializations": int(
            normalized_proof_summary.get("power_capacity_legacy_signature_materializations", 0)
        ),
        "power_capacity_supported_by_pole_materializations": int(
            normalized_proof_summary.get("power_capacity_supported_by_pole_materializations", 0)
        ),
        "power_capacity_m6x4_mixed_cpsat_evaluations": int(
            normalized_proof_summary.get("power_capacity_m6x4_mixed_cpsat_evaluations", 0)
        ),
        "power_capacity_m6x4_mixed_cpsat_cache_hits": int(
            normalized_proof_summary.get("power_capacity_m6x4_mixed_cpsat_cache_hits", 0)
        ),
        "power_capacity_m6x4_mixed_cpsat_selected_cases": int(
            normalized_proof_summary.get("power_capacity_m6x4_mixed_cpsat_selected_cases", 0)
        ),
        "power_capacity_m6x4_mixed_cpsat_v3_fallbacks": int(
            normalized_proof_summary.get("power_capacity_m6x4_mixed_cpsat_v3_fallbacks", 0)
        ),
        "power_capacity_uniform_3x3_cpsat_evaluations": int(
            normalized_proof_summary.get("power_capacity_uniform_3x3_cpsat_evaluations", 0)
        ),
        "power_capacity_uniform_3x3_cpsat_cache_hits": int(
            normalized_proof_summary.get("power_capacity_uniform_3x3_cpsat_cache_hits", 0)
        ),
        "power_capacity_uniform_3x3_cpsat_selected_cases": int(
            normalized_proof_summary.get("power_capacity_uniform_3x3_cpsat_selected_cases", 0)
        ),
        "power_capacity_uniform_3x3_cpsat_v3_fallbacks": int(
            normalized_proof_summary.get("power_capacity_uniform_3x3_cpsat_v3_fallbacks", 0)
        ),
        "power_capacity_bitset_oracle_evaluations": int(
            normalized_proof_summary.get("power_capacity_bitset_oracle_evaluations", 0)
        ),
        "power_capacity_bitset_fallbacks": int(
            normalized_proof_summary.get("power_capacity_bitset_fallbacks", 0)
        ),
        "power_capacity_cpsat_fallbacks": int(
            normalized_proof_summary.get("power_capacity_cpsat_fallbacks", 0)
        ),
        "power_capacity_oracle": str(
            normalized_proof_summary.get("power_capacity_oracle", "")
        ),
        "power_capacity_raw_pole_evaluations": int(
            normalized_proof_summary.get("power_capacity_raw_pole_evaluations", 0)
        ),
        "signature_bucket_cache_hits": int(
            normalized_proof_summary.get("signature_bucket_cache_hits", 0)
        ),
        "signature_bucket_cache_misses": int(
            normalized_proof_summary.get("signature_bucket_cache_misses", 0)
        ),
        "signature_bucket_distinct_keys": int(
            normalized_proof_summary.get("signature_bucket_distinct_keys", 0)
        ),
        "geometry_cache_templates": int(
            normalized_proof_summary.get("geometry_cache_templates", 0)
        ),
    }


def compute_mandatory_area_lower_bound(
    instances: Sequence[Mapping[str, Any]],
    rules: Mapping[str, Any],
) -> int:
    """Compute the exact-safe static occupied-area lower bound from mandatory exact instances."""

    templates = dict(rules.get("facility_templates", {}))
    total = 0
    for instance in instances:
        if not bool(instance.get("is_mandatory")):
            continue
        if str(instance.get("bound_type", "exact")) != "exact":
            continue

        facility_type = str(instance["facility_type"])
        template = templates[facility_type]
        dims = dict(template["dimensions"])
        total += int(dims["w"]) * int(dims["h"])
    return total


def compute_exact_static_area_lower_bound(
    instances: Sequence[Mapping[str, Any]],
    rules: Mapping[str, Any],
    generic_io_requirements: Optional[Mapping[str, Any]] = None,
) -> int:
    total = compute_mandatory_area_lower_bound(instances, rules)
    templates = dict(rules.get("facility_templates", {}))
    optional_lower_bounds = infer_certified_optional_lower_bounds(
        rules,
        generic_io_requirements,
    )
    for facility_type, count in optional_lower_bounds.items():
        template = dict(templates[str(facility_type)])
        dims = dict(template["dimensions"])
        total += int(count) * int(dims["w"]) * int(dims["h"])
    return total


def collect_certification_blockers(
    *,
    instances: Optional[Sequence[Mapping[str, Any]]] = None,
    solve_mode: str = "certified_exact",
    loaded_cuts: Optional[Sequence[BendersCut]] = None,
    current_hashes: Optional[Mapping[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Collect exact-contract blockers without mutating the current solve flow."""

    if solve_mode != "certified_exact":
        return []

    blockers: List[Dict[str, Any]] = []
    for instance in instances or []:
        instance_id = str(instance.get("instance_id", "<unknown>"))
        bound_type = str(instance.get("bound_type", ""))
        if bound_type == "provisional":
            blockers.append(
                {
                    "code": "provisional_instance_forbidden",
                    "instance_id": instance_id,
                    "detail": "provisional instance cannot enter certified_exact",
                }
            )
        if not bool(instance.get("is_mandatory", False)):
            blockers.append(
                {
                    "code": "non_mandatory_instance_forbidden",
                    "instance_id": instance_id,
                    "detail": "non-mandatory instance cannot enter certified_exact",
                }
            )
        instance_modes, mode_issue = _normalize_instance_solve_modes(instance)
        if mode_issue is not None:
            blockers.append(
                {
                    "code": "instance_mode_pollution",
                    "instance_id": instance_id,
                    "detail": (
                        "instance solve-mode metadata is missing or ambiguous for certified_exact: "
                        f"{mode_issue}"
                    ),
                }
            )
            continue
        if "certified_exact" not in instance_modes:
            blockers.append(
                {
                    "code": "instance_mode_pollution",
                    "instance_id": instance_id,
                    "detail": (
                        "instance does not declare certified_exact support: "
                        f"solve_modes={sorted(instance_modes)}"
                    ),
                }
            )

    normalized_hashes = (
        {str(k): str(v) for k, v in current_hashes.items()}
        if current_hashes is not None
        else None
    )
    for cut in loaded_cuts or []:
        if normalized_hashes is not None and dict(cut.artifact_hashes) != normalized_hashes:
            blockers.append(
                {
                    "code": "cut_hash_mismatch",
                    "detail": "loaded cut artifact hashes do not match current artifacts",
                    "cut_type": cut.cut_type,
                }
            )
        if not cut.exact_safe:
            blockers.append(
                {
                    "code": "cut_not_exact_safe",
                    "detail": "loaded cut is not marked exact_safe",
                    "cut_type": cut.cut_type,
                }
            )
        if cut.source_mode != "certified_exact":
            blockers.append(
                {
                    "code": "cut_mode_pollution",
                    "detail": f"loaded cut source_mode={cut.source_mode}",
                    "cut_type": cut.cut_type,
                }
            )

    return blockers


def _resolve_condition_lits_from_condition_set(
    master: Any,
    condition_set: Mapping[str, Any],
) -> Tuple[List[cp_model.IntVar], bool]:
    """把 persisted `BendersCut.condition_set` 反解析回 master 上的 CP-SAT literals.

    返回 (resolved_lits, ok). ok=False → caller 必须 skip cut, 不能退化成无条件.

    支持的 key 类型:
        `ghost_anchor::(x,y)` -> master.u_vars[rect_idx]; 校验 ghost_domains[rect_idx]
        的 anchor 跟 key 里的 (x,y) 一致 (artifact-hash 已拦 ghost 序乱但二次校验
        防止 hash 校验外的边缘场景).

    未知 key 或不匹配 → ok=False. 这是 GPT v4 P0 #1 finding 的 fix:
    persisted cut replay 不能丢 condition; certified mode 下不可解析必 fail-closed.
    """
    if not condition_set:
        return [], True
    u_vars = getattr(master, "u_vars", None) or {}
    ghost_domains = getattr(master, "_ghost_domains", None) or []
    resolved: List[cp_model.IntVar] = []
    for key, raw_value in condition_set.items():
        key_str = str(key)
        if not key_str.startswith("ghost_anchor::"):
            return [], False
        try:
            rect_idx = int(raw_value)
        except Exception:
            return [], False
        try:
            coord_part = key_str.split("::", 1)[1].strip().lstrip("(").rstrip(")")
            xy = coord_part.split(",")
            expected_x = int(xy[0])
            expected_y = int(xy[1])
        except Exception:
            return [], False
        if rect_idx not in u_vars:
            return [], False
        if rect_idx < 0 or rect_idx >= len(ghost_domains):
            return [], False
        anchor = ghost_domains[rect_idx].get("anchor") or {}
        try:
            actual_x = int(anchor.get("x", -1))
            actual_y = int(anchor.get("y", -1))
        except Exception:
            return [], False
        if actual_x != expected_x or actual_y != expected_y:
            return [], False
        resolved.append(u_vars[rect_idx])
    return resolved, True


@dataclass
class ExactSearchSession:
    """Reusable exact-search session carrying one static master core per process."""

    project_root: Path
    solve_mode: str
    instances: List[Dict[str, Any]]
    facility_pools: Dict[str, List[Dict[str, Any]]]
    rules: Dict[str, Any]
    artifact_hashes: Dict[str, str]
    master_search_profile: str
    core: ExactMasterCore
    core_build_seconds: float

    @classmethod
    def create(
        cls,
        project_root: Path,
        *,
        solve_mode: str = "certified_exact",
        master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    ) -> "ExactSearchSession":
        if solve_mode != "certified_exact":
            raise ValueError("ExactSearchSession only supports certified_exact")

        instances, facility_pools, rules = load_project_data(project_root, solve_mode=solve_mode)
        generic_io_requirements = load_generic_io_requirements_artifact(project_root)
        artifact_hashes = compute_exact_artifact_hashes(project_root)
        core_started = time.perf_counter()
        core = MasterPlacementModel.build_exact_core(
            instances,
            facility_pools,
            rules,
            generic_io_requirements=generic_io_requirements,
            master_search_profile=master_search_profile,
        )
        return cls(
            project_root=project_root,
            solve_mode=solve_mode,
            instances=instances,
            facility_pools=facility_pools,
            rules=rules,
            artifact_hashes=artifact_hashes,
            master_search_profile=str(
                dict(core.build_stats.get("search_guidance", {})).get(
                    "profile",
                    master_search_profile,
                )
            ),
            core=core,
            core_build_seconds=time.perf_counter() - core_started,
        )


def create_exact_search_session(
    project_root: Path,
    *,
    solve_mode: str = "certified_exact",
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
) -> ExactSearchSession:
    try:
        return ExactSearchSession.create(
            project_root,
            solve_mode=solve_mode,
            master_search_profile=master_search_profile,
        )
    except TypeError as exc:
        if "master_search_profile" not in str(exc):
            raise
        return ExactSearchSession.create(project_root, solve_mode=solve_mode)


def _merge_reuse_metadata(
    proof_summary: Mapping[str, Any],
    *,
    used_exact_core_reuse: bool,
    core_build_seconds: float,
    overlay_build_seconds: float,
    ghost_constraint_seconds: float,
    cut_replay_seconds: float,
) -> Dict[str, Any]:
    return {
        **dict(proof_summary),
        "used_exact_core_reuse": bool(used_exact_core_reuse),
        "core_build_seconds": float(core_build_seconds),
        "overlay_build_seconds": float(overlay_build_seconds),
        "ghost_constraint_seconds": float(ghost_constraint_seconds),
        "cut_replay_seconds": float(cut_replay_seconds),
    }


def _compact_exact_candidate_mandatory_support_diagnostics(
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "unsupported_group_count": int(payload.get("unsupported_group_count", 0)),
        "empty_candidate_pool_group_count": int(
            payload.get("empty_candidate_pool_group_count", 0)
        ),
        "groups": [
            {
                "group_id": str(entry.get("group_id", "")),
                "facility_type": str(entry.get("facility_type", "")),
                "operation_type": str(entry.get("operation_type", "")),
                "required_count": int(entry.get("required_count", 0)),
                "candidate_pool_count": int(entry.get("candidate_pool_count", 0)),
                "unsupported_reason": entry.get("unsupported_reason"),
            }
            for entry in list(payload.get("groups", []))
        ],
    }


def _compact_exact_candidate_mandatory_group_prechecks(
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    compact = {
        "evaluated": bool(payload.get("evaluated", False)),
        "skipped_due_to_upstream_precheck": bool(
            payload.get("skipped_due_to_upstream_precheck", False)
        ),
        "upstream_anchor_filter_count": int(
            payload.get("upstream_anchor_filter_count", 0)
        ),
        "supported_group_count": int(payload.get("supported_group_count", 0)),
        "groups": [
            {
                "group_id": str(entry.get("group_id", "")),
                "facility_type": str(entry.get("facility_type", "")),
                "operation_type": str(entry.get("operation_type", "")),
                "required_count": int(entry.get("required_count", 0)),
                "oracle_class": entry.get("oracle_class"),
                "oracle_mode": str(entry.get("oracle_mode", "unsupported")),
                "supported": bool(entry.get("supported", False)),
                "unsupported_reason": entry.get("unsupported_reason"),
                "considered_anchor_count": int(
                    entry.get("considered_anchor_count", 0)
                ),
                "screened_infeasible_anchor_count": int(
                    entry.get("screened_infeasible_anchor_count", 0)
                ),
                "screen_pass_anchor_count": int(
                    entry.get("screen_pass_anchor_count", 0)
                ),
                "unsupported_anchor_count": int(
                    entry.get("unsupported_anchor_count", 0)
                ),
                "max_packable_min": entry.get("max_packable_min"),
                "max_packable_max": entry.get("max_packable_max"),
                "first_infeasible_anchor_idx": entry.get(
                    "first_infeasible_anchor_idx"
                ),
                "first_infeasible_anchor_max_packable": entry.get(
                    "first_infeasible_anchor_max_packable"
                ),
                **(
                    {
                        "partial_due_to_time_budget": bool(
                            entry.get("partial_due_to_time_budget", False)
                        )
                    }
                    if "partial_due_to_time_budget" in entry
                    else {}
                ),
                **{
                    str(key): entry.get(str(key))
                    for key in (
                        "witness_pass_anchor_count",
                        "exact_capacity_eval_count",
                        "max_packable_lower_bound_min",
                        "max_packable_lower_bound_max",
                    )
                    if str(key) in entry
                },
            }
            for entry in list(payload.get("groups", []))
        ],
    }
    if "interrupted_due_to_time_budget" in payload:
        compact["interrupted_due_to_time_budget"] = bool(
            payload.get("interrupted_due_to_time_budget", False)
        )
        compact["time_budget_seconds"] = float(payload.get("time_budget_seconds", 0.0))
        compact["elapsed_seconds"] = float(payload.get("elapsed_seconds", 0.0))
    return compact


def _compact_exact_candidate_boundary_port_feasibility(
    payload: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "supported": bool(payload.get("supported", False)),
        "required_count": int(payload.get("required_count", 0)),
        "considered_anchor_count": int(payload.get("considered_anchor_count", 0)),
        "screened_infeasible_anchor_count": int(
            payload.get("screened_infeasible_anchor_count", 0)
        ),
        "screen_pass_anchor_count": int(payload.get("screen_pass_anchor_count", 0)),
        "unsupported_anchor_count": int(
            payload.get("unsupported_anchor_count", 0)
        ),
        "max_packable_min": payload.get("max_packable_min"),
        "max_packable_max": payload.get("max_packable_max"),
        "first_infeasible_anchor_idx": payload.get("first_infeasible_anchor_idx"),
        "first_infeasible_anchor_max_packable": payload.get(
            "first_infeasible_anchor_max_packable"
        ),
    }


def _default_exact_candidate_skipped_mandatory_group_prechecks(
    *,
    skipped_due_to_upstream_precheck: bool,
) -> Dict[str, Any]:
    return {
        "evaluated": False,
        "skipped_due_to_upstream_precheck": bool(
            skipped_due_to_upstream_precheck
        ),
        "upstream_anchor_filter_count": 0,
        "supported_group_count": 0,
        "groups": [],
    }


def _triggered_mandatory_rectangle_precheck_group(
    mandatory_group_prechecks: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    return next(
        (
            dict(entry)
            for entry in list(mandatory_group_prechecks.get("groups", []))
            if isinstance(entry, Mapping)
            and bool(entry.get("supported", False))
            and int(entry.get("considered_anchor_count", 0)) > 0
            and int(entry.get("screen_pass_anchor_count", 0)) == 0
            and int(entry.get("screened_infeasible_anchor_count", 0))
            == int(entry.get("considered_anchor_count", 0))
            and int(entry.get("unsupported_anchor_count", 0)) == 0
        ),
        None,
    )


def _mandatory_rectangle_precheck_proof_summary(
    *,
    master_search_profile: str,
    boundary_port_precheck: Mapping[str, Any],
    mandatory_group_precheck_summary: Mapping[str, Any],
    mandatory_support_diagnostics_summary: Mapping[str, Any],
    triggered_mandatory_group: Mapping[str, Any],
    used_exact_core_reuse: bool,
    core_build_seconds: float,
    overlay_build_seconds: float,
    ghost_constraint_seconds: float,
    cut_replay_seconds: float,
) -> Dict[str, Any]:
    return _merge_reuse_metadata(
        {
            "mode": "certified_exact",
            "benders_iterations": 0,
            "master_status": "INFEASIBLE",
            "diagnostic_flow_status": "NOT_RUN",
            "enumerated_bindings": 0,
            "routing_attempts": 0,
            "used_greedy_hint": False,
            "greedy_hint_instances": 0,
            "master_hinted_literals": 0,
            "master_search_profile": str(master_search_profile),
            "master_boundary_port_feasibility": _compact_exact_candidate_boundary_port_feasibility(
                boundary_port_precheck
            ),
            "master_mandatory_group_prechecks": dict(
                mandatory_group_precheck_summary
            ),
            "master_mandatory_support_diagnostics": dict(
                mandatory_support_diagnostics_summary
            ),
            "master_candidate_precheck": {
                "triggered": True,
                "precheck_reason": "mandatory_rect_group_all_anchors_infeasible",
                "master_solve_skipped": True,
                "supported": bool(triggered_mandatory_group.get("supported", False)),
                "considered_anchor_count": int(
                    triggered_mandatory_group.get("considered_anchor_count", 0)
                ),
                "screened_infeasible_anchor_count": int(
                    triggered_mandatory_group.get(
                        "screened_infeasible_anchor_count",
                        0,
                    )
                ),
                "screen_pass_anchor_count": int(
                    triggered_mandatory_group.get("screen_pass_anchor_count", 0)
                ),
                "max_packable_min": triggered_mandatory_group.get(
                    "max_packable_min"
                ),
                "max_packable_max": triggered_mandatory_group.get(
                    "max_packable_max"
                ),
                "first_infeasible_anchor_idx": triggered_mandatory_group.get(
                    "first_infeasible_anchor_idx"
                ),
                "first_infeasible_anchor_max_packable": triggered_mandatory_group.get(
                    "first_infeasible_anchor_max_packable"
                ),
                "triggered_group_id": triggered_mandatory_group.get("group_id"),
                "triggered_group_facility_type": triggered_mandatory_group.get(
                    "facility_type"
                ),
                "triggered_group_operation_type": triggered_mandatory_group.get(
                    "operation_type"
                ),
                "triggered_group_required_count": int(
                    triggered_mandatory_group.get("required_count", 0)
                ),
            },
        },
        used_exact_core_reuse=used_exact_core_reuse,
        core_build_seconds=core_build_seconds,
        overlay_build_seconds=overlay_build_seconds,
        ghost_constraint_seconds=ghost_constraint_seconds,
        cut_replay_seconds=cut_replay_seconds,
    )


def _evaluate_coordinate_validation_forced_anchor_precheck(
    model: MasterPlacementModel,
    *,
    anchor_indices: Sequence[int],
    time_limit_seconds: float,
    max_anchor_count: int,
) -> Dict[str, Any]:
    normalized_anchor_indices = tuple(int(idx) for idx in anchor_indices)
    payload: Dict[str, Any] = {
        "evaluated": False,
        "triggered": False,
        "skipped_due_to_anchor_limit": False,
        "time_limit_seconds": float(time_limit_seconds),
        "max_anchor_count": int(max_anchor_count),
        "considered_anchor_count": int(len(normalized_anchor_indices)),
        "evaluated_anchor_count": 0,
        "infeasible_anchor_count": 0,
        "accepted_anchor_count": 0,
        "unknown_anchor_count": 0,
        "skipped_anchor_count": 0,
        "short_circuited_after_non_triggering_anchor": False,
        "status_counts": {},
        "rejected_anchors": [],
        "non_triggering_anchors": [],
    }
    if int(max_anchor_count) <= 0 or float(time_limit_seconds) <= 0.0:
        payload["skip_reason"] = "disabled"
        return payload
    if not normalized_anchor_indices:
        payload["skip_reason"] = "empty_anchor_set"
        return payload
    if len(normalized_anchor_indices) > int(max_anchor_count):
        payload["skipped_due_to_anchor_limit"] = True
        payload["skip_reason"] = "anchor_limit_exceeded"
        return payload

    status_counts: Dict[str, int] = {}
    rejected_anchors: List[Dict[str, Any]] = []
    non_triggering_anchors: List[Dict[str, Any]] = []
    for anchor_idx in normalized_anchor_indices:
        validation = model._validate_coordinate_forced_hint(
            solution_hint={},
            ghost_anchor_hint_idx=int(anchor_idx),
            time_limit_seconds=float(time_limit_seconds),
            require_complete=False,
        )
        status = str(validation.get("status", ""))
        status_counts[status] = int(status_counts.get(status, 0)) + 1
        entry = {
            "anchor_idx": int(anchor_idx),
            "status": status,
            "accepted": bool(validation.get("accepted", False)),
            "reason": validation.get("reason"),
            "forced_slot_field_count": int(
                validation.get("forced_slot_field_count", 0)
            ),
            "forced_ghost_anchor": bool(
                validation.get("forced_ghost_anchor", False)
            ),
            "wall_time": float(validation.get("wall_time", 0.0)),
            "branches": int(validation.get("branches", 0)),
            "conflicts": int(validation.get("conflicts", 0)),
        }
        if "attempted_solver" in validation:
            entry["attempted_solver"] = bool(validation.get("attempted_solver", False))
        if validation.get("capacity_conflict") is not None:
            entry["capacity_conflict"] = dict(validation.get("capacity_conflict", {}))
        payload["evaluated_anchor_count"] = int(
            payload.get("evaluated_anchor_count", 0)
        ) + 1
        if status == "INFEASIBLE":
            rejected_anchors.append(entry)
            continue
        non_triggering_anchors.append(entry)
        payload["short_circuited_after_non_triggering_anchor"] = True
        break

    payload["evaluated"] = True
    payload["status_counts"] = dict(sorted(status_counts.items()))
    payload["rejected_anchors"] = rejected_anchors
    payload["non_triggering_anchors"] = non_triggering_anchors
    payload["infeasible_anchor_count"] = int(len(rejected_anchors))
    payload["accepted_anchor_count"] = sum(
        1 for entry in non_triggering_anchors if bool(entry.get("accepted", False))
    )
    payload["unknown_anchor_count"] = sum(
        1 for entry in non_triggering_anchors if str(entry.get("status")) == "UNKNOWN"
    )
    payload["skipped_anchor_count"] = sum(
        1 for entry in non_triggering_anchors if str(entry.get("status")) == "SKIPPED"
    )
    payload["triggered"] = bool(
        normalized_anchor_indices
        and len(rejected_anchors) == len(normalized_anchor_indices)
    )
    return payload


def _compact_coordinate_validation_precheck(payload: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "evaluated": bool(payload.get("evaluated", False)),
        "triggered": bool(payload.get("triggered", False)),
        "skipped_due_to_anchor_limit": bool(
            payload.get("skipped_due_to_anchor_limit", False)
        ),
        "skip_reason": payload.get("skip_reason"),
        "time_limit_seconds": float(payload.get("time_limit_seconds", 0.0)),
        "max_anchor_count": int(payload.get("max_anchor_count", 0)),
        "considered_anchor_count": int(payload.get("considered_anchor_count", 0)),
        "evaluated_anchor_count": int(payload.get("evaluated_anchor_count", 0)),
        "infeasible_anchor_count": int(payload.get("infeasible_anchor_count", 0)),
        "accepted_anchor_count": int(payload.get("accepted_anchor_count", 0)),
        "unknown_anchor_count": int(payload.get("unknown_anchor_count", 0)),
        "skipped_anchor_count": int(payload.get("skipped_anchor_count", 0)),
        "short_circuited_after_non_triggering_anchor": bool(
            payload.get("short_circuited_after_non_triggering_anchor", False)
        ),
        "status_counts": {
            str(key): int(value)
            for key, value in dict(payload.get("status_counts", {})).items()
        },
        "rejected_anchors": [
            dict(entry)
            for entry in list(payload.get("rejected_anchors", []))
            if isinstance(entry, Mapping)
        ],
        "non_triggering_anchors": [
            dict(entry)
            for entry in list(payload.get("non_triggering_anchors", []))
            if isinstance(entry, Mapping)
        ],
    }


def _coordinate_validation_precheck_proof_summary(
    *,
    master_search_profile: str,
    boundary_port_precheck: Mapping[str, Any],
    mandatory_group_precheck_summary: Mapping[str, Any],
    mandatory_support_diagnostics_summary: Mapping[str, Any],
    coordinate_validation_precheck: Mapping[str, Any],
    used_exact_core_reuse: bool,
    core_build_seconds: float,
    overlay_build_seconds: float,
    ghost_constraint_seconds: float,
    cut_replay_seconds: float,
) -> Dict[str, Any]:
    compact_coordinate = _compact_coordinate_validation_precheck(
        coordinate_validation_precheck
    )
    return _merge_reuse_metadata(
        {
            "mode": "certified_exact",
            "benders_iterations": 0,
            "master_status": "INFEASIBLE",
            "diagnostic_flow_status": "NOT_RUN",
            "enumerated_bindings": 0,
            "routing_attempts": 0,
            "used_greedy_hint": False,
            "greedy_hint_instances": 0,
            "master_hinted_literals": 0,
            "master_search_profile": str(master_search_profile),
            "master_boundary_port_feasibility": _compact_exact_candidate_boundary_port_feasibility(
                boundary_port_precheck
            ),
            "master_mandatory_group_prechecks": dict(
                mandatory_group_precheck_summary
            ),
            "master_mandatory_support_diagnostics": dict(
                mandatory_support_diagnostics_summary
            ),
            "coordinate_validation_precheck": compact_coordinate,
            "master_candidate_precheck": {
                "triggered": True,
                "precheck_reason": "coordinate_validation_infeasible",
                "master_solve_skipped": True,
                "supported": True,
                "considered_anchor_count": int(
                    compact_coordinate.get("considered_anchor_count", 0)
                ),
                "screened_infeasible_anchor_count": int(
                    compact_coordinate.get("infeasible_anchor_count", 0)
                ),
                "screen_pass_anchor_count": int(
                    compact_coordinate.get("accepted_anchor_count", 0)
                )
                + int(compact_coordinate.get("unknown_anchor_count", 0))
                + int(compact_coordinate.get("skipped_anchor_count", 0)),
                "max_packable_min": None,
                "max_packable_max": None,
                "first_infeasible_anchor_idx": (
                    compact_coordinate.get("rejected_anchors", [{}])[0].get("anchor_idx")
                    if compact_coordinate.get("rejected_anchors")
                    else None
                ),
                "first_infeasible_anchor_max_packable": None,
                "triggered_group_id": None,
                "triggered_group_facility_type": None,
                "triggered_group_operation_type": None,
                "triggered_group_required_count": 0,
            },
        },
        used_exact_core_reuse=used_exact_core_reuse,
        core_build_seconds=core_build_seconds,
        overlay_build_seconds=overlay_build_seconds,
        ghost_constraint_seconds=ghost_constraint_seconds,
        cut_replay_seconds=cut_replay_seconds,
    )


def evaluate_exact_candidate_pre_master_precheck(
    *,
    ghost_w: int,
    ghost_h: int,
    exact_session: "ExactSearchSession",
    master_search_profile: str,
    include_mandatory_rectangle_precheck: bool = False,
) -> Dict[str, Any]:
    project_root = Path(getattr(exact_session, "project_root", PROJECT_ROOT)).resolve()
    candidate_precheck_artifacts = dict(
        getattr(exact_session.core, "candidate_precheck_artifacts", {})
    )
    mandatory_support_diagnostics = dict(
        candidate_precheck_artifacts.get(
            "mandatory_support_diagnostics",
            exact_session.core.build_stats.get(
                "exact_candidate_mandatory_support_diagnostics",
                {},
            ),
        )
    )
    mandatory_support_diagnostics_summary = (
        _compact_exact_candidate_mandatory_support_diagnostics(
            mandatory_support_diagnostics
        )
    )
    default_boundary_port_precheck = (
        MasterPlacementModel._default_exact_candidate_boundary_port_feasibility_payload()
    )
    anchor119_runtime_precheck = (
        _maybe_build_anchor119_row_domain_runtime_precheck_result(
            project_root=project_root,
            ghost_w=int(ghost_w),
            ghost_h=int(ghost_h),
            master_search_profile=master_search_profile,
            mandatory_support_diagnostics_summary=mandatory_support_diagnostics_summary,
            default_boundary_port_precheck=default_boundary_port_precheck,
            exact_session=exact_session,
        )
    )
    if anchor119_runtime_precheck is not None:
        return anchor119_runtime_precheck
    triggered_empty_pool_group = next(
        (
            dict(entry)
            for entry in list(mandatory_support_diagnostics.get("groups", []))
            if str(entry.get("unsupported_reason", "")) == "empty_candidate_pool"
        ),
        None,
    )
    if triggered_empty_pool_group is not None:
        proof_summary = _merge_reuse_metadata(
            {
                "mode": "certified_exact",
                "benders_iterations": 0,
                "master_status": "INFEASIBLE",
                "diagnostic_flow_status": "NOT_RUN",
                "enumerated_bindings": 0,
                "routing_attempts": 0,
                "used_greedy_hint": False,
                "greedy_hint_instances": 0,
                "master_hinted_literals": 0,
                "master_search_profile": str(master_search_profile),
                "master_boundary_port_feasibility": (
                    _compact_exact_candidate_boundary_port_feasibility(
                        default_boundary_port_precheck
                    )
                ),
                "master_mandatory_group_prechecks": (
                    _default_exact_candidate_skipped_mandatory_group_prechecks(
                        skipped_due_to_upstream_precheck=False
                    )
                ),
                "master_mandatory_support_diagnostics": dict(
                    mandatory_support_diagnostics_summary
                ),
                "master_candidate_precheck": {
                    "triggered": True,
                    "precheck_reason": "mandatory_group_empty_candidate_pool",
                    "master_solve_skipped": True,
                    "supported": False,
                    "considered_anchor_count": 0,
                    "screened_infeasible_anchor_count": 0,
                    "screen_pass_anchor_count": 0,
                    "max_packable_min": None,
                    "max_packable_max": None,
                    "first_infeasible_anchor_idx": None,
                    "first_infeasible_anchor_max_packable": None,
                    "triggered_group_id": triggered_empty_pool_group.get(
                        "group_id"
                    ),
                    "triggered_group_facility_type": triggered_empty_pool_group.get(
                        "facility_type"
                    ),
                    "triggered_group_operation_type": triggered_empty_pool_group.get(
                        "operation_type"
                    ),
                    "triggered_group_required_count": int(
                        triggered_empty_pool_group.get("required_count", 0)
                    ),
                },
            },
            used_exact_core_reuse=True,
            core_build_seconds=float(exact_session.core_build_seconds),
            overlay_build_seconds=0.0,
            ghost_constraint_seconds=0.0,
            cut_replay_seconds=0.0,
        )
        _maybe_attach_anchor119_row_domain_guard_advisory_to_proof_summary(
            proof_summary,
            project_root=project_root,
            ghost_w=int(ghost_w),
            ghost_h=int(ghost_h),
        )
        return {
            "triggered": True,
            "status": RUN_STATUS_INFEASIBLE,
            "proof_summary": proof_summary,
            "boundary_port_precheck": dict(default_boundary_port_precheck),
        }

    boundary_port_screen_spec = dict(
        candidate_precheck_artifacts.get("boundary_port_screen_spec", {})
    )
    if boundary_port_screen_spec:
        boundary_port_precheck = (
            MasterPlacementModel.evaluate_boundary_port_feasibility_from_screen_spec(
                rules=exact_session.core.rules,
                ghost_rect=(int(ghost_w), int(ghost_h)),
                screen_spec=boundary_port_screen_spec,
            )
        )
    else:
        boundary_port_precheck = dict(default_boundary_port_precheck)
    boundary_precheck_triggered = (
        bool(boundary_port_precheck.get("supported", False))
        and int(boundary_port_precheck.get("considered_anchor_count", 0)) > 0
        and int(boundary_port_precheck.get("screen_pass_anchor_count", 0)) == 0
        and int(boundary_port_precheck.get("screened_infeasible_anchor_count", 0))
        == int(boundary_port_precheck.get("considered_anchor_count", 0))
        and int(boundary_port_precheck.get("unsupported_anchor_count", 0)) == 0
    )
    if boundary_precheck_triggered:
        proof_summary = _merge_reuse_metadata(
            {
                "mode": "certified_exact",
                "benders_iterations": 0,
                "master_status": "INFEASIBLE",
                "diagnostic_flow_status": "NOT_RUN",
                "enumerated_bindings": 0,
                "routing_attempts": 0,
                "used_greedy_hint": False,
                "greedy_hint_instances": 0,
                "master_hinted_literals": 0,
                "master_search_profile": str(master_search_profile),
                "master_boundary_port_feasibility": (
                    _compact_exact_candidate_boundary_port_feasibility(
                        boundary_port_precheck
                    )
                ),
                "master_mandatory_group_prechecks": (
                    _default_exact_candidate_skipped_mandatory_group_prechecks(
                        skipped_due_to_upstream_precheck=True
                    )
                ),
                "master_mandatory_support_diagnostics": dict(
                    mandatory_support_diagnostics_summary
                ),
                "master_candidate_precheck": {
                    "triggered": True,
                    "precheck_reason": "boundary_port_all_anchors_infeasible",
                    "master_solve_skipped": True,
                    "supported": bool(boundary_port_precheck.get("supported", False)),
                    "considered_anchor_count": int(
                        boundary_port_precheck.get("considered_anchor_count", 0)
                    ),
                    "screened_infeasible_anchor_count": int(
                        boundary_port_precheck.get(
                            "screened_infeasible_anchor_count",
                            0,
                        )
                    ),
                    "screen_pass_anchor_count": int(
                        boundary_port_precheck.get("screen_pass_anchor_count", 0)
                    ),
                    "max_packable_min": boundary_port_precheck.get(
                        "max_packable_min"
                    ),
                    "max_packable_max": boundary_port_precheck.get(
                        "max_packable_max"
                    ),
                    "first_infeasible_anchor_idx": boundary_port_precheck.get(
                        "first_infeasible_anchor_idx"
                    ),
                    "first_infeasible_anchor_max_packable": boundary_port_precheck.get(
                        "first_infeasible_anchor_max_packable"
                    ),
                    "triggered_group_id": None,
                    "triggered_group_facility_type": None,
                    "triggered_group_operation_type": None,
                    "triggered_group_required_count": 0,
                },
            },
            used_exact_core_reuse=True,
            core_build_seconds=float(exact_session.core_build_seconds),
            overlay_build_seconds=0.0,
            ghost_constraint_seconds=0.0,
            cut_replay_seconds=0.0,
        )
        _maybe_attach_anchor119_row_domain_guard_advisory_to_proof_summary(
            proof_summary,
            project_root=project_root,
            ghost_w=int(ghost_w),
            ghost_h=int(ghost_h),
        )
        return {
            "triggered": True,
            "status": RUN_STATUS_INFEASIBLE,
            "proof_summary": proof_summary,
            "boundary_port_precheck": dict(boundary_port_precheck),
        }

    if bool(include_mandatory_rectangle_precheck):
        boundary_pass_anchor_indices = tuple(
            int(idx)
            for idx in boundary_port_precheck.get("screen_pass_anchor_indices", ())
        )
        model: Optional[MasterPlacementModel] = None
        overlay_build_seconds = 0.0
        mandatory_group_prechecks: Optional[Dict[str, Any]] = None
        mandatory_group_precheck_summary = (
            _default_exact_candidate_skipped_mandatory_group_prechecks(
                skipped_due_to_upstream_precheck=False
            )
        )
        pre_master_mandatory_rectangle_anchor_cap = (
            _pre_master_mandatory_rectangle_precheck_max_anchors()
        )
        if (
            bool(boundary_port_precheck.get("supported", False))
            and boundary_pass_anchor_indices
            and len(boundary_pass_anchor_indices)
            <= int(pre_master_mandatory_rectangle_anchor_cap)
        ):
            overlay_started = time.perf_counter()
            model = MasterPlacementModel.from_exact_core(
                exact_session.core,
                ghost_rect=(int(ghost_w), int(ghost_h)),
                master_search_profile=master_search_profile,
                precomputed_boundary_port_feasibility=boundary_port_precheck,
            )
            overlay_build_seconds = time.perf_counter() - overlay_started
            mandatory_group_prechecks = (
                model.evaluate_exact_candidate_mandatory_rectangle_prechecks(
                    anchor_indices=boundary_pass_anchor_indices
                )
            )
            mandatory_group_precheck_summary = (
                _compact_exact_candidate_mandatory_group_prechecks(
                    mandatory_group_prechecks
                )
            )
            triggered_mandatory_group = (
                _triggered_mandatory_rectangle_precheck_group(
                    mandatory_group_prechecks
                )
            )
            if triggered_mandatory_group is not None:
                proof_summary = _mandatory_rectangle_precheck_proof_summary(
                    master_search_profile=master_search_profile,
                    boundary_port_precheck=boundary_port_precheck,
                    mandatory_group_precheck_summary=mandatory_group_precheck_summary,
                    mandatory_support_diagnostics_summary=mandatory_support_diagnostics_summary,
                    triggered_mandatory_group=triggered_mandatory_group,
                    used_exact_core_reuse=True,
                    core_build_seconds=float(exact_session.core_build_seconds),
                    overlay_build_seconds=float(overlay_build_seconds),
                    ghost_constraint_seconds=0.0,
                    cut_replay_seconds=0.0,
                )
                _maybe_attach_anchor119_row_domain_guard_advisory_to_proof_summary(
                    proof_summary,
                    project_root=project_root,
                    ghost_w=int(ghost_w),
                    ghost_h=int(ghost_h),
                )
                return {
                    "triggered": True,
                    "status": RUN_STATUS_INFEASIBLE,
                    "proof_summary": proof_summary,
                    "boundary_port_precheck": dict(boundary_port_precheck),
                    "mandatory_group_prechecks": dict(mandatory_group_prechecks),
                }

        coordinate_anchor_indices: Tuple[int, ...] = tuple()
        if isinstance(mandatory_group_prechecks, Mapping) and bool(
            mandatory_group_prechecks.get("evaluated", False)
        ):
            coordinate_anchor_indices = tuple(
                int(idx)
                for idx in mandatory_group_prechecks.get(
                    "rebuild_anchor_indices",
                    (),
                )
            )
        if not coordinate_anchor_indices and boundary_pass_anchor_indices:
            coordinate_anchor_indices = tuple(int(idx) for idx in boundary_pass_anchor_indices)
        coordinate_anchor_cap = _pre_master_coordinate_validation_precheck_max_anchors()
        coordinate_time_limit_seconds = _pre_master_coordinate_validation_precheck_seconds()
        if (
            not coordinate_anchor_indices
            and not bool(boundary_port_precheck.get("supported", False))
            and int(coordinate_anchor_cap) > 0
            and float(coordinate_time_limit_seconds) > 0.0
        ):
            if model is None:
                overlay_started = time.perf_counter()
                model = MasterPlacementModel.from_exact_core(
                    exact_session.core,
                    ghost_rect=(int(ghost_w), int(ghost_h)),
                    master_search_profile=master_search_profile,
                    precomputed_boundary_port_feasibility=boundary_port_precheck,
                )
                overlay_build_seconds = time.perf_counter() - overlay_started
            coordinate_anchor_indices = tuple(
                range(len(list(getattr(model, "_ghost_domains", []))))
            )
        if (
            coordinate_anchor_indices
            and int(coordinate_anchor_cap) > 0
            and float(coordinate_time_limit_seconds) > 0.0
            and len(coordinate_anchor_indices) <= int(coordinate_anchor_cap)
        ):
            if model is None:
                overlay_started = time.perf_counter()
                model = MasterPlacementModel.from_exact_core(
                    exact_session.core,
                    ghost_rect=(int(ghost_w), int(ghost_h)),
                    master_search_profile=master_search_profile,
                    precomputed_boundary_port_feasibility=boundary_port_precheck,
                )
                overlay_build_seconds = time.perf_counter() - overlay_started
            coordinate_validation_precheck = (
                _evaluate_coordinate_validation_forced_anchor_precheck(
                    model,
                    anchor_indices=coordinate_anchor_indices,
                    time_limit_seconds=coordinate_time_limit_seconds,
                    max_anchor_count=coordinate_anchor_cap,
                )
            )
            if bool(coordinate_validation_precheck.get("triggered", False)):
                proof_summary = _coordinate_validation_precheck_proof_summary(
                    master_search_profile=master_search_profile,
                    boundary_port_precheck=boundary_port_precheck,
                    mandatory_group_precheck_summary=mandatory_group_precheck_summary,
                    mandatory_support_diagnostics_summary=mandatory_support_diagnostics_summary,
                    coordinate_validation_precheck=coordinate_validation_precheck,
                    used_exact_core_reuse=True,
                    core_build_seconds=float(exact_session.core_build_seconds),
                    overlay_build_seconds=float(overlay_build_seconds),
                    ghost_constraint_seconds=0.0,
                    cut_replay_seconds=0.0,
                )
                _maybe_attach_anchor119_row_domain_guard_advisory_to_proof_summary(
                    proof_summary,
                    project_root=project_root,
                    ghost_w=int(ghost_w),
                    ghost_h=int(ghost_h),
                )
                return {
                    "triggered": True,
                    "status": RUN_STATUS_INFEASIBLE,
                    "proof_summary": proof_summary,
                    "boundary_port_precheck": dict(boundary_port_precheck),
                    "mandatory_group_prechecks": dict(mandatory_group_prechecks or {}),
                    "coordinate_validation_precheck": dict(
                        coordinate_validation_precheck
                    ),
                }

    proof_summary = {}
    _maybe_attach_anchor119_row_domain_guard_advisory_to_proof_summary(
        proof_summary,
        project_root=project_root,
        ghost_w=int(ghost_w),
        ghost_h=int(ghost_h),
    )
    return {
        "triggered": False,
        "status": None,
        "proof_summary": proof_summary,
        "boundary_port_precheck": dict(boundary_port_precheck),
    }


class LBBDController:
    """Orchestrator connecting the master model to exploratory or exact subproblems."""

    def __init__(
        self,
        master: MasterPlacementModel,
        cut_manager: CutManager,
        project_root: Path,
        solve_mode: str,
        *,
        max_iterations: int = 30,
        master_seconds: float = 600.0,
        binding_seconds: float = 600.0,
        routing_seconds: float = 600.0,
        flow_seconds: float = 60.0,
        artifact_hashes: Optional[Mapping[str, str]] = None,
        loaded_exact_safe_cuts: Optional[Sequence[BendersCut]] = None,
        heartbeat_callback: Optional[_CampaignHeartbeatCallback] = None,
        disable_master_warm_start: bool = False,
    ):
        self.master = master
        self.cut_manager = cut_manager
        self.project_root = project_root
        self.solve_mode = solve_mode
        self.max_iterations = max_iterations
        self.master_seconds = master_seconds
        self.binding_seconds = binding_seconds
        self.routing_seconds = routing_seconds
        self.flow_seconds = flow_seconds
        self.artifact_hashes = (
            {str(k): str(v) for k, v in artifact_hashes.items()}
            if artifact_hashes is not None
            else {}
        )
        self._heartbeat_callback = heartbeat_callback
        self.loaded_exact_safe_cuts: List[BendersCut] = list(loaded_exact_safe_cuts or [])
        self.generated_exact_safe_cuts: List[BendersCut] = []
        # P1 #7 main: 当前 wave 的 ε 阶段 (0.05 / 0.01 / 0.0 / None).
        # 由 outer_search 在每次 wave 启动前调 set_epsilon_stage(value) 传入.
        # 影响 _add_exact_persisted_nogood 构造 BendersCut 时的 epsilon_stage tag.
        self.epsilon_stage: Optional[float] = None
        self.last_proof_summary: Dict[str, Any] = {}
        self._master_warm_start_disabled = bool(disable_master_warm_start)
        self._greedy_hint: Dict[str, int] = {}
        self._greedy_hint_instances = 0
        self._used_greedy_hint = False
        self._master_hinted_literals = 0
        self._ghost_anchor_hint_applied = False
        self._ghost_anchor_hint_idx: Optional[int] = None
        self._ghost_anchor_hint_status = "not_used"
        self._residual_optional_zero_hinting_enabled = True
        self._residual_optional_zero_hints = 0
        self._master_start_feasibility: Dict[str, Any] = {
            "ghost_anchor_hint_applied": False,
            "ghost_anchor_hint_idx": None,
            "ghost_anchor_hint_status": "not_used",
            "ghost_anchor_total_count": 0,
            "ghost_anchor_compatible_count": 0,
            "mandatory_hint_pose_count": 0,
            "mandatory_hint_occupied_cell_count": 0,
            "required_optional_positive_hints": 0,
            "residual_optional_positive_hints": 0,
            "residual_optional_zero_hints": 0,
            "warm_start_strategy": "unsupported",
            "ghost_aware_anchor_attempt_count": 0,
            "ghost_aware_anchor_selected_idx": None,
            "ghost_aware_complete_mandatory_hint": False,
            "ghost_aware_hint_instances": 0,
            "ghost_aware_pose_order_portfolio_attempted": False,
            "ghost_aware_pose_order_portfolio_success": False,
            "ghost_aware_pose_order_portfolio_selected_ordering": None,
            "ghost_aware_pose_order_portfolio_attempt_count": 0,
            "ghost_aware_pose_order_portfolio_failed_anchor_count": 0,
            "ghost_aware_pose_order_portfolio_failure_reason_counts": {},
            "ghost_aware_pose_order_portfolio_failure_samples": [],
            "ghost_aware_pose_order_validation_attempt_count": 0,
            "ghost_aware_pose_order_validation_rejected_count": 0,
            "ghost_aware_pose_order_validation_last_status": None,
            "ghost_aware_pose_order_validation_last_reason": None,
        }
        self._master_start_failure_attribution: Dict[str, Any] = {
            "attempted_anchor_count": 0,
            "failed_anchor_count": 0,
            "failure_reason_counts": {},
            "first_failed_anchor_idx": None,
            "first_failed_group_id": None,
            "first_failed_group_template": None,
            "first_failed_group_required_count": 0,
            "first_failed_group_candidate_count": 0,
            "first_failed_group_surviving_after_blocked_count": 0,
            "first_failed_group_surviving_at_failure_count": 0,
            "first_failed_group_position": None,
            "top_failed_groups": [],
            "top_failed_group_failures": [],
            "failed_anchor_samples": [],
        }
        self._master_start_local_repair: Dict[str, Any] = {
            "local_repair_attempted": False,
            "local_repair_success": False,
            "local_repair_trigger_reason": None,
            "local_repair_window_size": 0,
            "local_repair_anchor_idx": None,
            "local_repair_failed_group_id": None,
            "local_repair_failed_group_template": None,
            "local_repair_portfolio_attempt_count": 0,
            "local_repair_selected_group_orderings": [],
            "local_repair_attempt_count": 0,
            "local_repair_success_count": 0,
            "local_repair_intra_group_attempted_count": 0,
            "local_repair_committed_attempted_count": 0,
            "local_repair_window1_count": 0,
            "local_repair_window2_count": 0,
        }
        self._master_boundary_port_feasibility: Dict[str, Any] = {
            "supported": False,
            "required_count": 0,
            "considered_anchor_count": 0,
            "screened_infeasible_anchor_count": 0,
            "screen_pass_anchor_count": 0,
            "unsupported_anchor_count": 0,
            "max_packable_min": None,
            "max_packable_max": None,
            "first_infeasible_anchor_idx": None,
            "first_infeasible_anchor_max_packable": None,
        }
        self._master_mandatory_group_prechecks: Dict[str, Any] = {
            "evaluated": False,
            "skipped_due_to_upstream_precheck": False,
            "upstream_anchor_filter_count": 0,
            "supported_group_count": 0,
            "groups": [],
        }
        self._master_mandatory_support_diagnostics: Dict[str, Any] = {
            "unsupported_group_count": 0,
            "empty_candidate_pool_group_count": 0,
            "groups": [],
        }
        self._master_candidate_precheck: Dict[str, Any] = {
            "triggered": False,
            "precheck_reason": None,
            "master_solve_skipped": False,
            "supported": False,
            "considered_anchor_count": 0,
            "screened_infeasible_anchor_count": 0,
            "screen_pass_anchor_count": 0,
            "max_packable_min": None,
            "max_packable_max": None,
            "first_infeasible_anchor_idx": None,
            "first_infeasible_anchor_max_packable": None,
            "triggered_group_id": None,
            "triggered_group_facility_type": None,
            "triggered_group_operation_type": None,
            "triggered_group_required_count": 0,
            "anchor119_row_domain_guard_advisory": {},
        }
        self._fine_grained_exact_safe_cut_count = 0
        self._binding_domain_empty_cut_count = 0
        self._routing_front_blocked_cut_count = 0
        self._routing_precheck_rejections = 0
        self._routing_precheck_statuses: List[str] = []
        self._routing_domain_cells = 0
        self._routing_terminal_core_cells = 0
        self._routing_state_space_vars = 0
        self._routing_local_pattern_pruned_states = 0
        self._used_routing_core_reuse = False
        self._routing_core_build_seconds = 0.0
        self._routing_overlay_build_seconds = 0.0
        self._binding_domain_cache_hits = 0
        self._binding_domain_cache_misses = 0
        self._binding_domain_reused_instances: List[str] = []

        demands_path = self.project_root / "data" / "preprocessed" / "commodity_demands.json"
        if demands_path.exists():
            with demands_path.open("r", encoding="utf-8") as handle:
                self.commodity_demands = json.load(handle)
        else:
            self.commodity_demands = {}

    def set_epsilon_stage(self, value: Optional[float]) -> None:
        """P1 #7 main: outer_search 每个 wave 调用, 影响新生成 cut 的 ε tag.

        value: 0.05 / 0.01 / 0.0 三阶段, None 表示无 ε 标注 (legacy hard
        nogood, 任何阶段都安全 reuse).
        """
        if value is None:
            self.epsilon_stage = None
        else:
            self.epsilon_stage = float(value)

    def _emit_heartbeat(
        self,
        *,
        stage: str,
        event: str,
        iteration: Optional[int] = None,
        extra: Optional[Mapping[str, Any]] = None,
    ) -> None:
        if self._heartbeat_callback is None:
            return
        payload: Dict[str, Any] = {
            "stage": str(stage),
            "event": str(event),
            "benders_max_iter": int(self.max_iterations),
            "master_seconds": float(self.master_seconds),
            "binding_seconds": float(self.binding_seconds),
            "routing_seconds": float(self.routing_seconds),
            "flow_seconds": float(self.flow_seconds),
        }
        if iteration is not None:
            payload["iteration"] = int(iteration)
        if extra is not None:
            payload.update(dict(extra))
        try:
            self._heartbeat_callback(payload)
        except Exception:
            return

    def _exact_warm_start_summary(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "used_greedy_hint": bool(self._used_greedy_hint),
            "greedy_hint_instances": int(self._greedy_hint_instances),
            "master_hinted_literals": int(self._master_hinted_literals),
            "master_warm_start": {
                "used_greedy_hint": bool(self._used_greedy_hint),
                "greedy_hint_instances": int(self._greedy_hint_instances),
                "master_hinted_literals": int(self._master_hinted_literals),
                "ghost_anchor_hint_applied": bool(self._ghost_anchor_hint_applied),
                "ghost_anchor_hint_idx": None
                if self._ghost_anchor_hint_idx is None
                else int(self._ghost_anchor_hint_idx),
                "ghost_anchor_hint_status": str(self._ghost_anchor_hint_status),
                "residual_optional_zero_hinting_enabled": bool(
                    self._residual_optional_zero_hinting_enabled
                ),
                "residual_optional_zero_hints": int(
                    self._residual_optional_zero_hints
                ),
                "warm_start_strategy": str(
                    self._master_start_feasibility.get(
                        "warm_start_strategy",
                        "unsupported",
                    )
                ),
                "ghost_aware_anchor_attempt_count": int(
                    self._master_start_feasibility.get(
                        "ghost_aware_anchor_attempt_count",
                        0,
                    )
                ),
                "ghost_aware_anchor_selected_idx": self._master_start_feasibility.get(
                    "ghost_aware_anchor_selected_idx"
                ),
                "ghost_aware_complete_mandatory_hint": bool(
                    self._master_start_feasibility.get(
                        "ghost_aware_complete_mandatory_hint",
                        False,
                    )
                ),
                "ghost_aware_hint_instances": int(
                    self._master_start_feasibility.get(
                        "ghost_aware_hint_instances",
                        0,
                    )
                ),
                "ghost_aware_pose_order_portfolio_attempted": bool(
                    self._master_start_feasibility.get(
                        "ghost_aware_pose_order_portfolio_attempted",
                        False,
                    )
                ),
                "ghost_aware_pose_order_portfolio_success": bool(
                    self._master_start_feasibility.get(
                        "ghost_aware_pose_order_portfolio_success",
                        False,
                    )
                ),
                "ghost_aware_pose_order_portfolio_selected_ordering": self._master_start_feasibility.get(
                    "ghost_aware_pose_order_portfolio_selected_ordering"
                ),
                "ghost_aware_pose_order_portfolio_attempt_count": int(
                    self._master_start_feasibility.get(
                        "ghost_aware_pose_order_portfolio_attempt_count",
                        0,
                    )
                ),
                "ghost_aware_pose_order_portfolio_failed_anchor_count": int(
                    self._master_start_feasibility.get(
                        "ghost_aware_pose_order_portfolio_failed_anchor_count",
                        0,
                    )
                ),
                "ghost_aware_pose_order_portfolio_failure_reason_counts": dict(
                    self._master_start_feasibility.get(
                        "ghost_aware_pose_order_portfolio_failure_reason_counts",
                        {},
                    )
                ),
                "ghost_aware_pose_order_portfolio_failure_samples": [
                    dict(entry)
                    for entry in list(
                        self._master_start_feasibility.get(
                            "ghost_aware_pose_order_portfolio_failure_samples",
                            [],
                        )
                    )
                    if isinstance(entry, Mapping)
                ],
                "ghost_aware_pose_order_validation_attempt_count": int(
                    self._master_start_feasibility.get(
                        "ghost_aware_pose_order_validation_attempt_count",
                        0,
                    )
                ),
                "ghost_aware_pose_order_validation_rejected_count": int(
                    self._master_start_feasibility.get(
                        "ghost_aware_pose_order_validation_rejected_count",
                        0,
                    )
                ),
                "ghost_aware_pose_order_validation_last_status": self._master_start_feasibility.get(
                    "ghost_aware_pose_order_validation_last_status"
                ),
                "ghost_aware_pose_order_validation_last_reason": self._master_start_feasibility.get(
                    "ghost_aware_pose_order_validation_last_reason"
                ),
                "local_repair_attempted": bool(
                    self._master_start_local_repair.get(
                        "local_repair_attempted",
                        False,
                    )
                ),
                "local_repair_success": bool(
                    self._master_start_local_repair.get(
                        "local_repair_success",
                        False,
                    )
                ),
                "local_repair_trigger_reason": self._master_start_local_repair.get(
                    "local_repair_trigger_reason"
                ),
                "local_repair_window_size": int(
                    self._master_start_local_repair.get(
                        "local_repair_window_size",
                        0,
                    )
                ),
                "local_repair_anchor_idx": self._master_start_local_repair.get(
                    "local_repair_anchor_idx"
                ),
                "local_repair_failed_group_id": self._master_start_local_repair.get(
                    "local_repair_failed_group_id"
                ),
                "local_repair_failed_group_template": self._master_start_local_repair.get(
                    "local_repair_failed_group_template"
                ),
                "local_repair_portfolio_attempt_count": int(
                    self._master_start_local_repair.get(
                        "local_repair_portfolio_attempt_count",
                        0,
                    )
                ),
                "local_repair_selected_group_orderings": [
                    str(token)
                    for token in list(
                        self._master_start_local_repair.get(
                            "local_repair_selected_group_orderings",
                            [],
                        )
                    )[:2]
                ],
            },
            "master_start_feasibility": {
                "ghost_anchor_hint_applied": bool(
                    self._master_start_feasibility.get(
                        "ghost_anchor_hint_applied",
                        False,
                    )
                ),
                "ghost_anchor_hint_idx": self._master_start_feasibility.get(
                    "ghost_anchor_hint_idx"
                ),
                "ghost_anchor_hint_status": str(
                    self._master_start_feasibility.get(
                        "ghost_anchor_hint_status",
                        "not_used",
                    )
                ),
                "ghost_anchor_total_count": int(
                    self._master_start_feasibility.get("ghost_anchor_total_count", 0)
                ),
                "ghost_anchor_compatible_count": int(
                    self._master_start_feasibility.get(
                        "ghost_anchor_compatible_count",
                        0,
                    )
                ),
                **(
                    {"ghost_anchor_compatibility_skipped": True}
                    if bool(
                        self._master_start_feasibility.get(
                            "ghost_anchor_compatibility_skipped",
                            False,
                        )
                    )
                    else {}
                ),
                "mandatory_hint_pose_count": int(
                    self._master_start_feasibility.get(
                        "mandatory_hint_pose_count",
                        0,
                    )
                ),
                "mandatory_hint_occupied_cell_count": int(
                    self._master_start_feasibility.get(
                        "mandatory_hint_occupied_cell_count",
                        0,
                    )
                ),
                "required_optional_positive_hints": int(
                    self._master_start_feasibility.get(
                        "required_optional_positive_hints",
                        0,
                    )
                ),
                "residual_optional_positive_hints": int(
                    self._master_start_feasibility.get(
                        "residual_optional_positive_hints",
                        0,
                    )
                ),
                "residual_optional_zero_hints": int(
                    self._master_start_feasibility.get(
                        "residual_optional_zero_hints",
                        0,
                    )
                ),
                "warm_start_strategy": str(
                    self._master_start_feasibility.get(
                        "warm_start_strategy",
                        "unsupported",
                    )
                ),
                "ghost_aware_anchor_attempt_count": int(
                    self._master_start_feasibility.get(
                        "ghost_aware_anchor_attempt_count",
                        0,
                    )
                ),
                "ghost_aware_anchor_selected_idx": self._master_start_feasibility.get(
                    "ghost_aware_anchor_selected_idx"
                ),
                "ghost_aware_complete_mandatory_hint": bool(
                    self._master_start_feasibility.get(
                        "ghost_aware_complete_mandatory_hint",
                        False,
                    )
                ),
                "ghost_aware_hint_instances": int(
                    self._master_start_feasibility.get(
                        "ghost_aware_hint_instances",
                        0,
                    )
                ),
                "ghost_aware_pose_order_portfolio_attempted": bool(
                    self._master_start_feasibility.get(
                        "ghost_aware_pose_order_portfolio_attempted",
                        False,
                    )
                ),
                "ghost_aware_pose_order_portfolio_success": bool(
                    self._master_start_feasibility.get(
                        "ghost_aware_pose_order_portfolio_success",
                        False,
                    )
                ),
                "ghost_aware_pose_order_portfolio_selected_ordering": self._master_start_feasibility.get(
                    "ghost_aware_pose_order_portfolio_selected_ordering"
                ),
                "ghost_aware_pose_order_portfolio_attempt_count": int(
                    self._master_start_feasibility.get(
                        "ghost_aware_pose_order_portfolio_attempt_count",
                        0,
                    )
                ),
                "ghost_aware_pose_order_portfolio_failed_anchor_count": int(
                    self._master_start_feasibility.get(
                        "ghost_aware_pose_order_portfolio_failed_anchor_count",
                        0,
                    )
                ),
                "ghost_aware_pose_order_portfolio_failure_reason_counts": dict(
                    self._master_start_feasibility.get(
                        "ghost_aware_pose_order_portfolio_failure_reason_counts",
                        {},
                    )
                ),
                "ghost_aware_pose_order_portfolio_failure_samples": [
                    dict(entry)
                    for entry in list(
                        self._master_start_feasibility.get(
                            "ghost_aware_pose_order_portfolio_failure_samples",
                            [],
                        )
                    )
                    if isinstance(entry, Mapping)
                ],
                "ghost_aware_pose_order_validation_attempt_count": int(
                    self._master_start_feasibility.get(
                        "ghost_aware_pose_order_validation_attempt_count",
                        0,
                    )
                ),
                "ghost_aware_pose_order_validation_rejected_count": int(
                    self._master_start_feasibility.get(
                        "ghost_aware_pose_order_validation_rejected_count",
                        0,
                    )
                ),
                "ghost_aware_pose_order_validation_last_status": self._master_start_feasibility.get(
                    "ghost_aware_pose_order_validation_last_status"
                ),
                "ghost_aware_pose_order_validation_last_reason": self._master_start_feasibility.get(
                    "ghost_aware_pose_order_validation_last_reason"
                ),
                "local_repair_attempted": bool(
                    self._master_start_local_repair.get(
                        "local_repair_attempted",
                        False,
                    )
                ),
                "local_repair_success": bool(
                    self._master_start_local_repair.get(
                        "local_repair_success",
                        False,
                    )
                ),
                "local_repair_trigger_reason": self._master_start_local_repair.get(
                    "local_repair_trigger_reason"
                ),
                "local_repair_window_size": int(
                    self._master_start_local_repair.get(
                        "local_repair_window_size",
                        0,
                    )
                ),
                "local_repair_anchor_idx": self._master_start_local_repair.get(
                    "local_repair_anchor_idx"
                ),
                "local_repair_failed_group_id": self._master_start_local_repair.get(
                    "local_repair_failed_group_id"
                ),
                "local_repair_failed_group_template": self._master_start_local_repair.get(
                    "local_repair_failed_group_template"
                ),
                "local_repair_portfolio_attempt_count": int(
                    self._master_start_local_repair.get(
                        "local_repair_portfolio_attempt_count",
                        0,
                    )
                ),
                "local_repair_selected_group_orderings": [
                    str(token)
                    for token in list(
                        self._master_start_local_repair.get(
                            "local_repair_selected_group_orderings",
                            [],
                        )
                    )[:2]
                ],
            },
            "master_start_failure_attribution": {
                "attempted_anchor_count": int(
                    self._master_start_failure_attribution.get(
                        "attempted_anchor_count",
                        0,
                    )
                ),
                "failed_anchor_count": int(
                    self._master_start_failure_attribution.get(
                        "failed_anchor_count",
                        0,
                    )
                ),
                "failure_reason_counts": {
                    str(key): int(value)
                    for key, value in dict(
                        self._master_start_failure_attribution.get(
                            "failure_reason_counts",
                            {},
                        )
                    ).items()
                    if int(value) > 0
                },
                "first_failed_anchor_idx": self._master_start_failure_attribution.get(
                    "first_failed_anchor_idx"
                ),
                "first_failed_group_id": self._master_start_failure_attribution.get(
                    "first_failed_group_id"
                ),
                "first_failed_group_template": self._master_start_failure_attribution.get(
                    "first_failed_group_template"
                ),
                "first_failed_group_required_count": int(
                    self._master_start_failure_attribution.get(
                        "first_failed_group_required_count",
                        0,
                    )
                ),
                "first_failed_group_candidate_count": int(
                    self._master_start_failure_attribution.get(
                        "first_failed_group_candidate_count",
                        0,
                    )
                ),
                "first_failed_group_surviving_after_blocked_count": int(
                    self._master_start_failure_attribution.get(
                        "first_failed_group_surviving_after_blocked_count",
                        0,
                    )
                ),
                "first_failed_group_surviving_at_failure_count": int(
                    self._master_start_failure_attribution.get(
                        "first_failed_group_surviving_at_failure_count",
                        0,
                    )
                ),
                "first_failed_group_position": self._master_start_failure_attribution.get(
                    "first_failed_group_position"
                ),
                "top_failed_groups": [
                    {
                        "group_id": str(entry.get("group_id", "")),
                        "facility_type": str(entry.get("facility_type", "")),
                        "count": int(entry.get("count", 0)),
                    }
                    for entry in list(
                        self._master_start_failure_attribution.get(
                            "top_failed_groups",
                            [],
                        )
                    )[:5]
                    if int(entry.get("count", 0)) > 0
                ],
                "top_failed_group_failures": [
                    {
                        "group_id": str(entry.get("group_id", "")),
                        "facility_type": str(entry.get("facility_type", "")),
                        "failure_reason": str(entry.get("failure_reason", "")),
                        "count": int(entry.get("count", 0)),
                    }
                    for entry in list(
                        self._master_start_failure_attribution.get(
                            "top_failed_group_failures",
                            [],
                        )
                    )[:8]
                    if int(entry.get("count", 0)) > 0
                ],
                "failed_anchor_samples": [
                    {
                        "anchor_idx": int(entry.get("anchor_idx", 0)),
                        "failure_reason": str(entry.get("failure_reason", "")),
                        "first_failed_group_id": entry.get("first_failed_group_id"),
                        "first_failed_group_template": entry.get(
                            "first_failed_group_template"
                        ),
                        "first_failed_group_position": entry.get(
                            "first_failed_group_position"
                        ),
                        "first_failed_group_required_count": int(
                            entry.get("first_failed_group_required_count", 0)
                        ),
                        "first_failed_group_candidate_count": int(
                            entry.get("first_failed_group_candidate_count", 0)
                        ),
                        "first_failed_group_surviving_after_blocked_count": int(
                            entry.get(
                                "first_failed_group_surviving_after_blocked_count",
                                0,
                            )
                        ),
                        "first_failed_group_surviving_at_failure_count": int(
                            entry.get(
                                "first_failed_group_surviving_at_failure_count",
                                0,
                            )
                        ),
                        "blocked_cell_count": int(entry.get("blocked_cell_count", 0)),
                        "blocked_bbox": entry.get("blocked_bbox"),
                        "local_repair_attempted": bool(
                            entry.get("local_repair_attempted", False)
                        ),
                        "local_repair_success": bool(
                            entry.get("local_repair_success", False)
                        ),
                        "local_repair_attempt_count": int(
                            entry.get("local_repair_attempt_count", 0)
                        ),
                        **_coordinate_validation_failure_sample_fields(entry),
                    }
                    for entry in list(
                        self._master_start_failure_attribution.get(
                            "failed_anchor_samples",
                            [],
                        )
                    )[:_warm_start_failed_anchor_sample_limit()]
                    if isinstance(entry, Mapping)
                ],
            },
            "master_start_local_repair": {
                "local_repair_attempted": bool(
                    self._master_start_local_repair.get(
                        "local_repair_attempted",
                        False,
                    )
                ),
                "local_repair_success": bool(
                    self._master_start_local_repair.get(
                        "local_repair_success",
                        False,
                    )
                ),
                "local_repair_trigger_reason": self._master_start_local_repair.get(
                    "local_repair_trigger_reason"
                ),
                "local_repair_window_size": int(
                    self._master_start_local_repair.get(
                        "local_repair_window_size",
                        0,
                    )
                ),
                "local_repair_anchor_idx": self._master_start_local_repair.get(
                    "local_repair_anchor_idx"
                ),
                "local_repair_failed_group_id": self._master_start_local_repair.get(
                    "local_repair_failed_group_id"
                ),
                "local_repair_failed_group_template": self._master_start_local_repair.get(
                    "local_repair_failed_group_template"
                ),
                "local_repair_portfolio_attempt_count": int(
                    self._master_start_local_repair.get(
                        "local_repair_portfolio_attempt_count",
                        0,
                    )
                ),
                "local_repair_selected_group_orderings": [
                    str(token)
                    for token in list(
                        self._master_start_local_repair.get(
                            "local_repair_selected_group_orderings",
                            [],
                        )
                    )[:2]
                ],
                "local_repair_attempt_count": int(
                    self._master_start_local_repair.get(
                        "local_repair_attempt_count",
                        0,
                    )
                ),
                "local_repair_success_count": int(
                    self._master_start_local_repair.get(
                        "local_repair_success_count",
                        0,
                    )
                ),
                "local_repair_intra_group_attempted_count": int(
                    self._master_start_local_repair.get(
                        "local_repair_intra_group_attempted_count",
                        0,
                    )
                ),
                "local_repair_committed_attempted_count": int(
                    self._master_start_local_repair.get(
                        "local_repair_committed_attempted_count",
                        0,
                    )
                ),
                "local_repair_window1_count": int(
                    self._master_start_local_repair.get(
                        "local_repair_window1_count",
                        0,
                    )
                ),
                "local_repair_window2_count": int(
                    self._master_start_local_repair.get(
                        "local_repair_window2_count",
                        0,
                    )
                ),
            },
            "master_boundary_port_feasibility": {
                "supported": bool(
                    self._master_boundary_port_feasibility.get("supported", False)
                ),
                "required_count": int(
                    self._master_boundary_port_feasibility.get("required_count", 0)
                ),
                "considered_anchor_count": int(
                    self._master_boundary_port_feasibility.get(
                        "considered_anchor_count",
                        0,
                    )
                ),
                "screened_infeasible_anchor_count": int(
                    self._master_boundary_port_feasibility.get(
                        "screened_infeasible_anchor_count",
                        0,
                    )
                ),
                "screen_pass_anchor_count": int(
                    self._master_boundary_port_feasibility.get(
                        "screen_pass_anchor_count",
                        0,
                    )
                ),
                "unsupported_anchor_count": int(
                    self._master_boundary_port_feasibility.get(
                        "unsupported_anchor_count",
                        0,
                    )
                ),
                "max_packable_min": self._master_boundary_port_feasibility.get(
                    "max_packable_min"
                ),
                "max_packable_max": self._master_boundary_port_feasibility.get(
                    "max_packable_max"
                ),
                "first_infeasible_anchor_idx": self._master_boundary_port_feasibility.get(
                    "first_infeasible_anchor_idx"
                ),
                "first_infeasible_anchor_max_packable": self._master_boundary_port_feasibility.get(
                    "first_infeasible_anchor_max_packable"
                ),
            },
            "master_mandatory_group_prechecks": {
                "evaluated": bool(
                    self._master_mandatory_group_prechecks.get("evaluated", False)
                ),
                "skipped_due_to_upstream_precheck": bool(
                    self._master_mandatory_group_prechecks.get(
                        "skipped_due_to_upstream_precheck",
                        False,
                    )
                ),
                "upstream_anchor_filter_count": int(
                    self._master_mandatory_group_prechecks.get(
                        "upstream_anchor_filter_count",
                        0,
                    )
                ),
                "supported_group_count": int(
                    self._master_mandatory_group_prechecks.get(
                        "supported_group_count",
                        0,
                    )
                ),
                "groups": [
                    {
                        "group_id": str(entry.get("group_id", "")),
                        "facility_type": str(entry.get("facility_type", "")),
                        "operation_type": str(entry.get("operation_type", "")),
                        "required_count": int(entry.get("required_count", 0)),
                        "oracle_class": entry.get("oracle_class"),
                        "oracle_mode": str(
                            entry.get("oracle_mode", "unsupported")
                        ),
                        "supported": bool(entry.get("supported", False)),
                        "unsupported_reason": entry.get("unsupported_reason"),
                        "considered_anchor_count": int(
                            entry.get("considered_anchor_count", 0)
                        ),
                        "screened_infeasible_anchor_count": int(
                            entry.get("screened_infeasible_anchor_count", 0)
                        ),
                        "screen_pass_anchor_count": int(
                            entry.get("screen_pass_anchor_count", 0)
                        ),
                        "unsupported_anchor_count": int(
                            entry.get("unsupported_anchor_count", 0)
                        ),
                        "max_packable_min": entry.get("max_packable_min"),
                        "max_packable_max": entry.get("max_packable_max"),
                        "first_infeasible_anchor_idx": entry.get(
                            "first_infeasible_anchor_idx"
                        ),
                        "first_infeasible_anchor_max_packable": entry.get(
                            "first_infeasible_anchor_max_packable"
                        ),
                        **(
                            {
                                "partial_due_to_time_budget": bool(
                                    entry.get("partial_due_to_time_budget", False)
                                )
                            }
                            if "partial_due_to_time_budget" in entry
                            else {}
                        ),
                        **{
                            str(key): entry.get(str(key))
                            for key in (
                                "witness_pass_anchor_count",
                                "exact_capacity_eval_count",
                                "max_packable_lower_bound_min",
                                "max_packable_lower_bound_max",
                            )
                            if str(key) in entry
                        },
                    }
                    for entry in list(
                        self._master_mandatory_group_prechecks.get("groups", [])
                    )
                ],
                **(
                    {
                        "interrupted_due_to_time_budget": bool(
                            self._master_mandatory_group_prechecks.get(
                                "interrupted_due_to_time_budget",
                                False,
                            )
                        ),
                        "time_budget_seconds": float(
                            self._master_mandatory_group_prechecks.get(
                                "time_budget_seconds",
                                0.0,
                            )
                        ),
                        "elapsed_seconds": float(
                            self._master_mandatory_group_prechecks.get(
                                "elapsed_seconds",
                                0.0,
                            )
                        ),
                    }
                    if "interrupted_due_to_time_budget"
                    in self._master_mandatory_group_prechecks
                    else {}
                ),
            },
            "master_mandatory_support_diagnostics": {
                "unsupported_group_count": int(
                    self._master_mandatory_support_diagnostics.get(
                        "unsupported_group_count",
                        0,
                    )
                ),
                "empty_candidate_pool_group_count": int(
                    self._master_mandatory_support_diagnostics.get(
                        "empty_candidate_pool_group_count",
                        0,
                    )
                ),
                "groups": [
                    {
                        "group_id": str(entry.get("group_id", "")),
                        "facility_type": str(entry.get("facility_type", "")),
                        "operation_type": str(entry.get("operation_type", "")),
                        "required_count": int(entry.get("required_count", 0)),
                        "candidate_pool_count": int(
                            entry.get("candidate_pool_count", 0)
                        ),
                        "unsupported_reason": entry.get("unsupported_reason"),
                    }
                    for entry in list(
                        self._master_mandatory_support_diagnostics.get("groups", [])
                    )
                ],
            },
            "master_candidate_precheck": {
                "triggered": bool(
                    self._master_candidate_precheck.get("triggered", False)
                ),
                "precheck_reason": self._master_candidate_precheck.get(
                    "precheck_reason"
                ),
                "master_solve_skipped": bool(
                    self._master_candidate_precheck.get(
                        "master_solve_skipped",
                        False,
                    )
                ),
                "supported": bool(
                    self._master_candidate_precheck.get("supported", False)
                ),
                "considered_anchor_count": int(
                    self._master_candidate_precheck.get(
                        "considered_anchor_count",
                        0,
                    )
                ),
                "screened_infeasible_anchor_count": int(
                    self._master_candidate_precheck.get(
                        "screened_infeasible_anchor_count",
                        0,
                    )
                ),
                "screen_pass_anchor_count": int(
                    self._master_candidate_precheck.get(
                        "screen_pass_anchor_count",
                        0,
                    )
                ),
                "max_packable_min": self._master_candidate_precheck.get(
                    "max_packable_min"
                ),
                "max_packable_max": self._master_candidate_precheck.get(
                    "max_packable_max"
                ),
                "first_infeasible_anchor_idx": self._master_candidate_precheck.get(
                    "first_infeasible_anchor_idx"
                ),
                "first_infeasible_anchor_max_packable": self._master_candidate_precheck.get(
                    "first_infeasible_anchor_max_packable"
                ),
                "triggered_group_id": self._master_candidate_precheck.get(
                    "triggered_group_id"
                ),
                "triggered_group_facility_type": self._master_candidate_precheck.get(
                    "triggered_group_facility_type"
                ),
                "triggered_group_operation_type": self._master_candidate_precheck.get(
                    "triggered_group_operation_type"
                ),
                "triggered_group_required_count": int(
                    self._master_candidate_precheck.get(
                        "triggered_group_required_count",
                        0,
                    )
                ),
                **(
                    {
                        "anchor119_row_domain_guard_advisory": dict(
                            self._master_candidate_precheck.get(
                                "anchor119_row_domain_guard_advisory", {}
                            )
                        )
                    }
                    if isinstance(
                        self._master_candidate_precheck.get(
                            "anchor119_row_domain_guard_advisory"
                        ),
                        Mapping,
                    )
                    and bool(
                        self._master_candidate_precheck.get(
                            "anchor119_row_domain_guard_advisory"
                        )
                    )
                    else {}
                ),
            },
        }
        if self._master_warm_start_disabled:
            summary["master_warm_start_disabled"] = True
            summary["master_warm_start"]["disabled"] = True
        return summary

    def _master_search_summary(self) -> Dict[str, Any]:
        last_solve = dict(self.master.build_stats.get("last_solve", {}))
        search_guidance = dict(self.master.build_stats.get("search_guidance", {}))
        power_coverage = dict(self.master.build_stats.get("power_coverage", {}))
        global_valid_inequalities = dict(
            self.master.build_stats.get("global_valid_inequalities", {})
        )
        ghost_domain_tightening = dict(
            global_valid_inequalities.get("ghost_aware_via_pole_feasibility", {})
        )
        signature_bucket_tightening = dict(
            global_valid_inequalities.get("signature_bucket_capacity_bounds", {})
        )
        residual_signature_bucket_tightening = dict(
            global_valid_inequalities.get("residual_signature_bucket_capacity_bounds", {})
        )
        coordinate_symmetry = dict(
            self.master.build_stats.get("coordinate_symmetry", {})
        )
        domain_activation = dict(self.master.build_stats.get("domain_activation", {}))
        exact_precompute_profile = dict(
            self.master.build_stats.get("exact_precompute_profile", {})
        )
        master_last_solve: Dict[str, Any] = {
            "status": str(last_solve.get("status", "")),
            "wall_time": float(last_solve.get("wall_time", 0.0)),
            "user_time": float(last_solve.get("user_time", 0.0)),
            "deterministic_time": float(last_solve.get("deterministic_time", 0.0)),
            "branches": int(last_solve.get("branches", 0)),
            "conflicts": int(last_solve.get("conflicts", 0)),
            "binary_propagations": int(last_solve.get("binary_propagations", 0)),
            "integer_propagations": int(last_solve.get("integer_propagations", 0)),
            "hinted_literals": int(last_solve.get("hinted_literals", 0)),
            "known_feasible_hint": bool(last_solve.get("known_feasible_hint", False)),
            "search_profile": str(last_solve.get("search_profile", "default_automatic")),
            "search_branching": str(last_solve.get("search_branching", "")),
        }
        requested_search_branching = str(last_solve.get("requested_search_branching", "fixed"))
        if requested_search_branching not in {"", "fixed"}:
            master_last_solve["requested_search_branching"] = requested_search_branching
        solver_parameters = last_solve.get("solver_parameters")
        if isinstance(solver_parameters, Mapping):
            master_last_solve["solver_parameters"] = dict(solver_parameters)
        if (
            str(master_last_solve.get("status")) == "UNKNOWN"
            and int(master_last_solve.get("branches", 0)) == 0
            and int(master_last_solve.get("conflicts", 0)) == 0
        ):
            response_stats = str(last_solve.get("response_stats", ""))
            if response_stats:
                master_last_solve["response_stats"] = response_stats[:4000]
        return {
            "master_search_profile": str(
                last_solve.get(
                    "search_profile",
                    search_guidance.get("profile", "default_automatic"),
                )
            ),
            "master_last_solve": master_last_solve,
            "master_domain_tightening": {
                "ghost_power_capacity_screen_enabled": bool(
                    ghost_domain_tightening.get("enabled", False)
                ),
                "ghost_disabled_placements": int(
                    ghost_domain_tightening.get("disabled_placements", 0)
                ),
                "ghost_surviving_placements": int(
                    ghost_domain_tightening.get("surviving_placements", 0)
                ),
                "ghost_conditioned_family_upper_bound_constraints": int(
                    ghost_domain_tightening.get(
                        "conditioned_family_upper_bound_constraints",
                        0,
                    )
                ),
                "ghost_family_reduction_anchor_count": int(
                    ghost_domain_tightening.get("family_reduction_anchor_count", 0)
                ),
            },
            "master_signature_tightening": {
                "mandatory_bucket_upper_bound_constraints": int(
                    signature_bucket_tightening.get(
                        "mandatory_bucket_upper_bound_constraints",
                        0,
                    )
                ),
                "required_optional_bucket_upper_bound_constraints": int(
                    signature_bucket_tightening.get(
                        "required_optional_bucket_upper_bound_constraints",
                        0,
                    )
                ),
                "ghost_conditioned_mandatory_bucket_constraints": int(
                    signature_bucket_tightening.get(
                        "ghost_conditioned_mandatory_bucket_constraints",
                        0,
                    )
                ),
                "ghost_conditioned_required_optional_bucket_constraints": int(
                    signature_bucket_tightening.get(
                        "ghost_conditioned_required_optional_bucket_constraints",
                        0,
                    )
                ),
                "ghost_signature_reduction_anchor_count": int(
                    signature_bucket_tightening.get(
                        "ghost_signature_reduction_anchor_count",
                        0,
                    )
                ),
            },
            "master_residual_signature_tightening": {
                "bucket_upper_bound_constraints": int(
                    residual_signature_bucket_tightening.get(
                        "bucket_upper_bound_constraints",
                        0,
                    )
                ),
                "ghost_conditioned_bucket_constraints": int(
                    residual_signature_bucket_tightening.get(
                        "ghost_conditioned_residual_bucket_constraints",
                        0,
                    )
                ),
                "ghost_signature_reduction_anchor_count": int(
                    residual_signature_bucket_tightening.get(
                        "ghost_residual_signature_reduction_anchor_count",
                        0,
                    )
                ),
            },
            "master_coordinate_symmetry": {
                "enabled": bool(coordinate_symmetry.get("enabled", False)),
                "mandatory_signature_monotonic_constraints": int(
                    coordinate_symmetry.get(
                        "mandatory_signature_monotonic_constraints",
                        0,
                    )
                ),
                "required_optional_signature_monotonic_constraints": int(
                    coordinate_symmetry.get(
                        "required_optional_signature_monotonic_constraints",
                        0,
                    )
                ),
                "residual_optional_signature_monotonic_constraints": int(
                    coordinate_symmetry.get(
                        "residual_optional_signature_monotonic_constraints",
                        0,
                    )
                ),
            },
            "master_domain_activation": {
                "ghost_anchor_count": int(domain_activation.get("ghost_anchor_count", 0)),
                "mandatory_slot_count": int(
                    domain_activation.get("mandatory_slot_count", 0)
                ),
                "required_optional_slot_count": int(
                    domain_activation.get("required_optional_slot_count", 0)
                ),
                "residual_optional_slot_count": int(
                    domain_activation.get("residual_optional_slot_count", 0)
                ),
                "mandatory_pose_literal_count": int(
                    domain_activation.get("mandatory_pose_literal_count", 0)
                ),
                "required_optional_pose_literal_count": int(
                    domain_activation.get("required_optional_pose_literal_count", 0)
                ),
                "residual_optional_pose_literal_count": int(
                    domain_activation.get("residual_optional_pose_literal_count", 0)
                ),
                "required_optional_active_slot_upper_bound_sum": int(
                    domain_activation.get(
                        "required_optional_active_slot_upper_bound_sum",
                        0,
                    )
                ),
                "residual_optional_active_slot_upper_bound_sum": int(
                    domain_activation.get(
                        "residual_optional_active_slot_upper_bound_sum",
                        0,
                    )
                ),
            },
            "master_search_guidance_applied": bool(search_guidance.get("applied", False)),
            "power_pole_family_order": list(
                search_guidance.get("power_pole_family_order", [])
            ),
            "power_pole_family_count_literals": int(
                search_guidance.get("power_pole_family_count_literals", 0)
            ),
            "residual_optional_family_guided": bool(
                search_guidance.get("residual_optional_family_guided", False)
            ),
            "master_representation": str(
                self.master.build_stats.get("master_representation", "pose_bool_v1")
            ),
            "master_slot_counts": copy.deepcopy(
                self.master.build_stats.get("master_slot_counts", {})
            ),
            "master_mode_literals": int(
                self.master.build_stats.get("master_mode_literals", 0)
            ),
            "master_interval_count": int(
                self.master.build_stats.get("master_interval_count", 0)
            ),
            "master_pose_bool_literals": int(
                self.master.build_stats.get("master_pose_bool_literals", 0)
            ),
            "master_domain_encoding": str(
                self.master.build_stats.get("master_domain_encoding", "")
            ),
            "master_domain_table_rows": int(
                self.master.build_stats.get("master_domain_table_rows", 0)
            ),
            "master_mode_rect_domains": copy.deepcopy(
                self.master.build_stats.get("master_mode_rect_domains", {})
            ),
            "power_pole_shell_lookup_pairs": copy.deepcopy(
                self.master.build_stats.get("power_pole_shell_lookup_pairs", {})
            ),
            "power_coverage_representation": str(
                power_coverage.get("representation", "")
            ),
            "power_coverage_encoding": str(power_coverage.get("encoding", "")),
            "power_coverage_powered_slots": int(
                power_coverage.get("powered_slots", 0)
            ),
            "power_coverage_pole_slots": int(power_coverage.get("pole_slots", 0)),
            "power_coverage_cover_literals": int(
                power_coverage.get("cover_literals", 0)
            ),
            "power_coverage_witness_indices": int(
                power_coverage.get("witness_indices", 0)
            ),
            "power_coverage_element_constraints": int(
                power_coverage.get("element_constraints", 0)
            ),
            "power_coverage_radius": int(power_coverage.get("radius", 0)),
            "power_capacity_shell_pairs": int(
                exact_precompute_profile.get("power_capacity_shell_pairs", 0)
            ),
            "power_capacity_shell_pair_evaluations": int(
                exact_precompute_profile.get("power_capacity_shell_pair_evaluations", 0)
            ),
            "power_capacity_signature_classes": int(
                exact_precompute_profile.get("power_capacity_signature_classes", 0)
            ),
            "power_capacity_signature_class_evaluations": int(
                exact_precompute_profile.get("power_capacity_signature_class_evaluations", 0)
            ),
            "power_capacity_compact_signature_classes": int(
                exact_precompute_profile.get("power_capacity_compact_signature_classes", 0)
            ),
            "power_capacity_compact_signature_evaluations": int(
                exact_precompute_profile.get(
                    "power_capacity_compact_signature_evaluations",
                    0,
                )
            ),
            "power_capacity_compact_signature_cache_hits": int(
                exact_precompute_profile.get(
                    "power_capacity_compact_signature_cache_hits",
                    0,
                )
            ),
            "power_capacity_compact_signature_cache_misses": int(
                exact_precompute_profile.get(
                    "power_capacity_compact_signature_cache_misses",
                    0,
                )
            ),
            "power_capacity_rect_dp_evaluations": int(
                exact_precompute_profile.get("power_capacity_rect_dp_evaluations", 0)
            ),
            "power_capacity_rect_dp_cache_hits": int(
                exact_precompute_profile.get("power_capacity_rect_dp_cache_hits", 0)
            ),
            "power_capacity_rect_dp_cache_misses": int(
                exact_precompute_profile.get("power_capacity_rect_dp_cache_misses", 0)
            ),
            "power_capacity_rect_dp_state_merges": int(
                exact_precompute_profile.get("power_capacity_rect_dp_state_merges", 0)
            ),
            "power_capacity_rect_dp_peak_line_states": int(
                exact_precompute_profile.get("power_capacity_rect_dp_peak_line_states", 0)
            ),
            "power_capacity_rect_dp_peak_pos_states": int(
                exact_precompute_profile.get("power_capacity_rect_dp_peak_pos_states", 0)
            ),
            "power_capacity_rect_dp_compiled_signatures": int(
                exact_precompute_profile.get("power_capacity_rect_dp_compiled_signatures", 0)
            ),
            "power_capacity_rect_dp_compiled_start_options": int(
                exact_precompute_profile.get("power_capacity_rect_dp_compiled_start_options", 0)
            ),
            "power_capacity_rect_dp_deduped_start_options": int(
                exact_precompute_profile.get("power_capacity_rect_dp_deduped_start_options", 0)
            ),
            "power_capacity_rect_dp_compiled_line_subsets": int(
                exact_precompute_profile.get("power_capacity_rect_dp_compiled_line_subsets", 0)
            ),
            "power_capacity_rect_dp_peak_line_subset_options": int(
                exact_precompute_profile.get("power_capacity_rect_dp_peak_line_subset_options", 0)
            ),
            "power_capacity_rect_dp_v3_fallbacks": int(
                exact_precompute_profile.get("power_capacity_rect_dp_v3_fallbacks", 0)
            ),
            "power_capacity_compact_rect_cpsat_evaluations": int(
                exact_precompute_profile.get("power_capacity_compact_rect_cpsat_evaluations", 0)
            ),
            "power_capacity_compact_rect_cpsat_cache_hits": int(
                exact_precompute_profile.get("power_capacity_compact_rect_cpsat_cache_hits", 0)
            ),
            "power_capacity_compact_rect_cpsat_selected_cases": int(
                exact_precompute_profile.get("power_capacity_compact_rect_cpsat_selected_cases", 0)
            ),
            "power_capacity_compact_rect_cpsat_rect_dp_fallbacks": int(
                exact_precompute_profile.get("power_capacity_compact_rect_cpsat_rect_dp_fallbacks", 0)
            ),
            "power_capacity_normalized_rect_signature_count": int(
                exact_precompute_profile.get("power_capacity_normalized_rect_signature_count", 0)
            ),
            "power_capacity_normalized_rect_cache_hits": int(
                exact_precompute_profile.get("power_capacity_normalized_rect_cache_hits", 0)
            ),
            "power_capacity_normalized_rect_cache_misses": int(
                exact_precompute_profile.get("power_capacity_normalized_rect_cache_misses", 0)
            ),
            "power_capacity_legacy_signature_materializations": int(
                exact_precompute_profile.get("power_capacity_legacy_signature_materializations", 0)
            ),
            "power_capacity_supported_by_pole_materializations": int(
                exact_precompute_profile.get("power_capacity_supported_by_pole_materializations", 0)
            ),
            "power_capacity_m6x4_mixed_cpsat_evaluations": int(
                exact_precompute_profile.get("power_capacity_m6x4_mixed_cpsat_evaluations", 0)
            ),
            "power_capacity_m6x4_mixed_cpsat_cache_hits": int(
                exact_precompute_profile.get("power_capacity_m6x4_mixed_cpsat_cache_hits", 0)
            ),
            "power_capacity_m6x4_mixed_cpsat_selected_cases": int(
                exact_precompute_profile.get("power_capacity_m6x4_mixed_cpsat_selected_cases", 0)
            ),
            "power_capacity_m6x4_mixed_cpsat_v3_fallbacks": int(
                exact_precompute_profile.get("power_capacity_m6x4_mixed_cpsat_v3_fallbacks", 0)
            ),
            "power_capacity_uniform_3x3_cpsat_evaluations": int(
                exact_precompute_profile.get("power_capacity_uniform_3x3_cpsat_evaluations", 0)
            ),
            "power_capacity_uniform_3x3_cpsat_cache_hits": int(
                exact_precompute_profile.get("power_capacity_uniform_3x3_cpsat_cache_hits", 0)
            ),
            "power_capacity_uniform_3x3_cpsat_selected_cases": int(
                exact_precompute_profile.get("power_capacity_uniform_3x3_cpsat_selected_cases", 0)
            ),
            "power_capacity_uniform_3x3_cpsat_v3_fallbacks": int(
                exact_precompute_profile.get("power_capacity_uniform_3x3_cpsat_v3_fallbacks", 0)
            ),
            "power_capacity_bitset_oracle_evaluations": int(
                exact_precompute_profile.get("power_capacity_bitset_oracle_evaluations", 0)
            ),
            "power_capacity_bitset_fallbacks": int(
                exact_precompute_profile.get("power_capacity_bitset_fallbacks", 0)
            ),
            "power_capacity_cpsat_fallbacks": int(
                exact_precompute_profile.get("power_capacity_cpsat_fallbacks", 0)
            ),
            "power_capacity_oracle": str(
                exact_precompute_profile.get("power_capacity_oracle", "")
            ),
            "power_capacity_raw_pole_evaluations": int(
                exact_precompute_profile.get("power_capacity_raw_pole_evaluations", 0)
            ),
            "signature_bucket_cache_hits": int(
                exact_precompute_profile.get("signature_bucket_cache_hits", 0)
            ),
            "signature_bucket_cache_misses": int(
                exact_precompute_profile.get("signature_bucket_cache_misses", 0)
            ),
            "signature_bucket_distinct_keys": int(
                exact_precompute_profile.get("signature_bucket_distinct_keys", 0)
            ),
            "geometry_cache_templates": int(
                exact_precompute_profile.get("geometry_cache_templates", 0)
            ),
        }

    def _exact_cut_ladder_summary(self) -> Dict[str, Any]:
        return {
            "fine_grained_exact_safe_cut_count": int(self._fine_grained_exact_safe_cut_count),
            "binding_domain_empty_cut_count": int(self._binding_domain_empty_cut_count),
            "routing_front_blocked_cut_count": int(self._routing_front_blocked_cut_count),
            "routing_precheck_rejections": int(self._routing_precheck_rejections),
            "routing_precheck_statuses": list(self._routing_precheck_statuses),
        }

    def _routing_shrink_summary(self) -> Dict[str, Any]:
        return {
            "routing_domain_cells": int(self._routing_domain_cells),
            "routing_terminal_core_cells": int(self._routing_terminal_core_cells),
            "routing_state_space_vars": int(self._routing_state_space_vars),
            "routing_local_pattern_pruned_states": int(
                self._routing_local_pattern_pruned_states
            ),
        }

    def _routing_reuse_summary(self) -> Dict[str, Any]:
        return {
            "used_routing_core_reuse": bool(self._used_routing_core_reuse),
            "routing_core_build_seconds": float(self._routing_core_build_seconds),
            "routing_overlay_build_seconds": float(self._routing_overlay_build_seconds),
        }

    def _binding_domain_cache_summary(self) -> Dict[str, Any]:
        return {
            "binding_domain_cache_hits": int(self._binding_domain_cache_hits),
            "binding_domain_cache_misses": int(self._binding_domain_cache_misses),
            "binding_domain_reused_instances": list(self._binding_domain_reused_instances),
        }

    def _subproblem_reuse_summary(self) -> Dict[str, Any]:
        return {
            **self._routing_reuse_summary(),
            **self._binding_domain_cache_summary(),
        }

    def _update_routing_shrink_from_domain_stats(
        self,
        domain_stats: Optional[Mapping[str, Any]],
    ) -> None:
        stats = dict(domain_stats or {})
        if "domain_cells" in stats:
            self._routing_domain_cells = int(stats["domain_cells"])
        if "terminal_core_cells" in stats:
            self._routing_terminal_core_cells = int(stats["terminal_core_cells"])

    def _update_routing_shrink_from_build_stats(
        self,
        build_stats: Optional[Mapping[str, Any]],
    ) -> None:
        state_space = dict((build_stats or {}).get("state_space", {}))
        self._update_routing_shrink_from_domain_stats(state_space)
        if "vars" in state_space:
            self._routing_state_space_vars = int(state_space["vars"])
        if "local_pattern_pruned_states" in state_space:
            self._routing_local_pattern_pruned_states = int(
                state_space["local_pattern_pruned_states"]
            )

    def _update_binding_cache_from_summary(
        self,
        binding_summary: Optional[Mapping[str, Any]],
    ) -> None:
        summary = dict(binding_summary or {})
        self._binding_domain_cache_hits = int(summary.get("binding_domain_cache_hits", 0))
        self._binding_domain_cache_misses = int(summary.get("binding_domain_cache_misses", 0))
        self._binding_domain_reused_instances = [
            str(instance_id)
            for instance_id in list(summary.get("binding_domain_reused_instances", []))
        ]

    def _exact_cut_ladder_summary_with_deltas(
        self,
        *,
        fine_grained_delta: int = 0,
        binding_domain_empty_delta: int = 0,
        routing_front_blocked_delta: int = 0,
        routing_precheck_rejections_delta: int = 0,
    ) -> Dict[str, Any]:
        return {
            "fine_grained_exact_safe_cut_count": int(
                self._fine_grained_exact_safe_cut_count + fine_grained_delta
            ),
            "binding_domain_empty_cut_count": int(
                self._binding_domain_empty_cut_count + binding_domain_empty_delta
            ),
            "routing_front_blocked_cut_count": int(
                self._routing_front_blocked_cut_count + routing_front_blocked_delta
            ),
            "routing_precheck_rejections": int(
                self._routing_precheck_rejections + routing_precheck_rejections_delta
            ),
            "routing_precheck_statuses": list(self._routing_precheck_statuses),
        }

    def run_with_status(self) -> Tuple[str, Optional[Dict[str, Any]]]:
        if self.solve_mode == "certified_exact":
            return self._run_certified_exact()
        return self._run_exploratory()

    def _run_exploratory(self) -> Tuple[str, Optional[Dict[str, Any]]]:
        iteration = 0
        while iteration < self.max_iterations:
            print(f"\n--- [LBBD Loop] Iteration {iteration + 1}/{self.max_iterations} ---")
            print("  > Solving Master Problem...")

            master_status = self.master.solve(time_limit_seconds=self.master_seconds)
            if master_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                pass
            elif master_status == cp_model.INFEASIBLE:
                print("  > Master problem is provably infeasible.")
                self.last_proof_summary = {
                    "mode": "exploratory",
                    "benders_iterations": iteration + 1,
                    "master_status": "INFEASIBLE",
                }
                return RUN_STATUS_INFEASIBLE, None
            else:
                print("  > Master problem returned UNKNOWN / timeout.")
                self.last_proof_summary = {
                    "mode": "exploratory",
                    "benders_iterations": iteration + 1,
                    "master_status": "UNKNOWN",
                }
                return RUN_STATUS_UNKNOWN, None

            solution = self.master.extract_solution()
            if not solution:
                self.last_proof_summary = {
                    "mode": "exploratory",
                    "benders_iterations": iteration + 1,
                    "master_status": "EMPTY_SOLUTION",
                }
                return RUN_STATUS_UNKNOWN, None

            print("  > Master solved successfully. Validating with Flow Subproblem...")
            flow_status, bottlenecks = self._run_flow_diagnostic(solution)
            self.last_proof_summary = {
                "mode": "exploratory",
                "benders_iterations": iteration + 1,
                "diagnostic_flow_status": flow_status,
                "bottleneck_count": len(bottlenecks),
            }

            if flow_status == "FEASIBLE":
                print("  > Flow Subproblem FEASIBLE! Layout is validated.")
                return RUN_STATUS_CERTIFIED, solution

            if flow_status == "TIMEOUT":
                print("  > Flow Subproblem timed out.")
                return RUN_STATUS_UNKNOWN, None

            print("  > Flow Subproblem INFEASIBLE. Extracting Bottleneck Cuts...")
            if not bottlenecks:
                print("  > No bottlenecks could be extracted. Terminating.")
                return RUN_STATUS_UNKNOWN, None

            conflict_set: List[Dict[str, str]] = []
            conflict_map_for_master: Dict[str, int] = {}
            for instance_id in bottlenecks:
                if instance_id not in solution:
                    continue
                pose_idx = int(solution[instance_id]["pose_idx"])
                pose_id = str(solution[instance_id]["pose_id"])
                conflict_set.append({"instance_id": instance_id, "pose_id": pose_id})
                conflict_map_for_master[instance_id] = pose_idx

            if not conflict_set:
                return RUN_STATUS_UNKNOWN, None

            is_new = self.cut_manager.add_cut(
                conflict_set,
                reason="macro_flow_bottleneck",
                source="LBBD_Flow",
            )
            if not is_new:
                print("  > Extracted cut already exists! Loop stalling.")
                return RUN_STATUS_UNKNOWN, None

            print(f"  > Added new cut covering {len(conflict_set)} instances. Retrying...")
            self.master.add_benders_cut(conflict_map_for_master)
            iteration += 1

        print("--- [LBBD Loop] Max iterations reached ---")
        self.last_proof_summary = {
            "mode": "exploratory",
            "benders_iterations": self.max_iterations,
            "master_status": "MAX_ITERATIONS",
        }
        return RUN_STATUS_UNPROVEN, None

    def _run_certified_exact(self) -> Tuple[str, Optional[Dict[str, Any]]]:
        diagnostic_flow_status = "NOT_RUN"
        self._emit_heartbeat(stage="master_warm_start", event="start")
        warm_start = self.master.build_exact_candidate_warm_start()
        self._greedy_hint = dict(warm_start.get("solution_hint", {}))
        self._greedy_hint_instances = len(self._greedy_hint)
        self._used_greedy_hint = False
        self._community_hint_path = os.environ.get(
            "EXACT_COMMUNITY_BLUEPRINT_HINT_PATH", ""
        ).strip()
        self._community_hint_overrides = 0
        self._community_hint_additions = 0
        if self._community_hint_path:
            try:
                community_hint_raw = json.loads(
                    Path(self._community_hint_path).read_text()
                )
            except FileNotFoundError:
                print(
                    f"[community-hint] file not found: {self._community_hint_path} — skipping",
                    flush=True,
                )
                community_hint_raw = {}
            except json.JSONDecodeError as exc:
                print(
                    f"[community-hint] JSON parse failed: {self._community_hint_path}: {exc} — skipping",
                    flush=True,
                )
                community_hint_raw = {}
            for inst_id, pose_idx in dict(community_hint_raw or {}).items():
                try:
                    pose_idx_int = int(pose_idx)
                except (TypeError, ValueError):
                    continue
                key = str(inst_id)
                if key in self._greedy_hint:
                    if self._greedy_hint[key] != pose_idx_int:
                        self._community_hint_overrides += 1
                else:
                    self._community_hint_additions += 1
                self._greedy_hint[key] = pose_idx_int
            self._greedy_hint_instances = len(self._greedy_hint)
            print(
                f"[community-hint] loaded {self._community_hint_path}: "
                f"+{self._community_hint_additions} additions, "
                f"{self._community_hint_overrides} overrides, "
                f"total hinted instances now {self._greedy_hint_instances}",
                flush=True,
            )
        self._master_hinted_literals = 0
        self._ghost_anchor_hint_applied = False
        raw_ghost_anchor_hint_idx = warm_start.get("ghost_anchor_hint_idx")
        self._ghost_anchor_hint_idx = (
            None if raw_ghost_anchor_hint_idx is None else int(raw_ghost_anchor_hint_idx)
        )
        self._ghost_anchor_hint_status = str(
            warm_start.get("ghost_anchor_hint_status", "not_used")
        )
        self._residual_optional_zero_hinting_enabled = bool(
            warm_start.get("hint_inactive_residual_optionals", False)
        )
        self._residual_optional_zero_hints = int(
            warm_start.get("residual_optional_zero_hints", 0)
        )
        self._master_start_feasibility = {
            "ghost_anchor_hint_applied": False,
            "ghost_anchor_hint_idx": self._ghost_anchor_hint_idx,
            "ghost_anchor_hint_status": str(self._ghost_anchor_hint_status),
            "ghost_anchor_total_count": int(
                warm_start.get("ghost_anchor_total_count", 0)
            ),
            "ghost_anchor_compatible_count": int(
                warm_start.get("ghost_anchor_compatible_count", 0)
            ),
            **(
                {"ghost_anchor_compatibility_skipped": True}
                if bool(warm_start.get("ghost_anchor_compatibility_skipped", False))
                else {}
            ),
            "mandatory_hint_pose_count": int(
                warm_start.get("mandatory_hint_pose_count", 0)
            ),
            "mandatory_hint_occupied_cell_count": int(
                warm_start.get("mandatory_hint_occupied_cell_count", 0)
            ),
            "required_optional_positive_hints": int(
                warm_start.get("required_optional_positive_hints", 0)
            ),
            "residual_optional_positive_hints": int(
                warm_start.get("residual_optional_positive_hints", 0)
            ),
            "residual_optional_zero_hints": int(
                warm_start.get("residual_optional_zero_hints", 0)
            ),
            "warm_start_strategy": str(
                warm_start.get("warm_start_strategy", "unsupported")
            ),
            "ghost_aware_anchor_attempt_count": int(
                warm_start.get("ghost_aware_anchor_attempt_count", 0)
            ),
            "ghost_aware_anchor_selected_idx": warm_start.get(
                "ghost_aware_anchor_selected_idx"
            ),
            "ghost_aware_complete_mandatory_hint": bool(
                warm_start.get("ghost_aware_complete_mandatory_hint", False)
            ),
            "ghost_aware_hint_instances": int(
                warm_start.get("ghost_aware_hint_instances", 0)
            ),
            "ghost_aware_pose_order_portfolio_attempted": bool(
                warm_start.get("ghost_aware_pose_order_portfolio_attempted", False)
            ),
            "ghost_aware_pose_order_portfolio_success": bool(
                warm_start.get("ghost_aware_pose_order_portfolio_success", False)
            ),
            "ghost_aware_pose_order_portfolio_selected_ordering": warm_start.get(
                "ghost_aware_pose_order_portfolio_selected_ordering"
            ),
            "ghost_aware_pose_order_portfolio_attempt_count": int(
                warm_start.get("ghost_aware_pose_order_portfolio_attempt_count", 0)
            ),
            "ghost_aware_pose_order_portfolio_failed_anchor_count": int(
                warm_start.get(
                    "ghost_aware_pose_order_portfolio_failed_anchor_count",
                    0,
                )
            ),
            "ghost_aware_pose_order_portfolio_failure_reason_counts": dict(
                warm_start.get(
                    "ghost_aware_pose_order_portfolio_failure_reason_counts",
                    {},
                )
            ),
            "ghost_aware_pose_order_portfolio_failure_samples": [
                dict(entry)
                for entry in list(
                    warm_start.get(
                        "ghost_aware_pose_order_portfolio_failure_samples",
                        [],
                    )
                )
                if isinstance(entry, Mapping)
            ],
            "ghost_aware_pose_order_validation_attempt_count": int(
                warm_start.get(
                    "ghost_aware_pose_order_validation_attempt_count",
                    0,
                )
            ),
            "ghost_aware_pose_order_validation_rejected_count": int(
                warm_start.get(
                    "ghost_aware_pose_order_validation_rejected_count",
                    0,
                )
            ),
            "ghost_aware_pose_order_validation_last_status": warm_start.get(
                "ghost_aware_pose_order_validation_last_status"
            ),
            "ghost_aware_pose_order_validation_last_reason": warm_start.get(
                "ghost_aware_pose_order_validation_last_reason"
            ),
        }
        self._master_start_local_repair = {
            "local_repair_attempted": bool(
                warm_start.get("local_repair_attempted", False)
            ),
            "local_repair_success": bool(warm_start.get("local_repair_success", False)),
            "local_repair_trigger_reason": warm_start.get(
                "local_repair_trigger_reason"
            ),
            "local_repair_window_size": int(
                warm_start.get("local_repair_window_size", 0)
            ),
            "local_repair_anchor_idx": warm_start.get("local_repair_anchor_idx"),
            "local_repair_failed_group_id": warm_start.get(
                "local_repair_failed_group_id"
            ),
            "local_repair_failed_group_template": warm_start.get(
                "local_repair_failed_group_template"
            ),
            "local_repair_portfolio_attempt_count": int(
                warm_start.get("local_repair_portfolio_attempt_count", 0)
            ),
            "local_repair_selected_group_orderings": [
                str(token)
                for token in list(
                    warm_start.get("local_repair_selected_group_orderings", [])
                )[:2]
            ],
            "local_repair_attempt_count": int(
                warm_start.get("local_repair_attempt_count", 0)
            ),
            "local_repair_success_count": int(
                warm_start.get("local_repair_success_count", 0)
            ),
            "local_repair_intra_group_attempted_count": int(
                warm_start.get("local_repair_intra_group_attempted_count", 0)
            ),
            "local_repair_committed_attempted_count": int(
                warm_start.get("local_repair_committed_attempted_count", 0)
            ),
            "local_repair_window1_count": int(
                warm_start.get("local_repair_window1_count", 0)
            ),
            "local_repair_window2_count": int(
                warm_start.get("local_repair_window2_count", 0)
            ),
        }
        self._master_boundary_port_feasibility = dict(
            self.master.build_stats.get(
                "exact_candidate_warm_start_boundary_port_feasibility",
                {},
            )
        )
        self._master_mandatory_support_diagnostics = dict(
            self.master.build_stats.get(
                "exact_candidate_mandatory_support_diagnostics",
                {},
            )
        )
        self._master_mandatory_group_prechecks = dict(
            self.master.build_stats.get(
                "exact_candidate_warm_start_mandatory_group_prechecks",
                {},
            )
        )
        self._master_start_failure_attribution = dict(
            self.master.build_stats.get(
                "exact_candidate_warm_start_failure_attribution",
                {},
            )
        )
        for iteration in range(1, self.max_iterations + 1):
            print(f"\n--- [LBBD Exact Loop] Iteration {iteration}/{self.max_iterations} ---")
            print("  > Solving Master Problem...")
            self._emit_heartbeat(
                stage="master_solve",
                event="start",
                iteration=iteration,
                extra={
                    "master_search_profile": str(
                        getattr(self.master, "master_search_profile", "unknown")
                    )
                },
            )

            solve_hint: Optional[Mapping[str, int]] = None
            solve_ghost_anchor_hint_idx: Optional[int] = None
            solve_hint_inactive_residual_optionals = True
            if iteration == 1 and not self._master_warm_start_disabled:
                solve_hint = self._greedy_hint or None
                solve_ghost_anchor_hint_idx = self._ghost_anchor_hint_idx
                solve_hint_inactive_residual_optionals = bool(
                    self._residual_optional_zero_hinting_enabled
                )
                if self._greedy_hint:
                    self._used_greedy_hint = True

            master_log_limit = (
                _master_cp_sat_log_heartbeat_line_limit()
                if self._heartbeat_callback is not None
                else 0
            )
            master_log_max_chars = _master_cp_sat_log_heartbeat_max_chars()
            master_log_count = 0

            def _emit_master_solve_log(line: str) -> None:
                nonlocal master_log_count
                if master_log_limit <= 0 or master_log_count >= master_log_limit:
                    return
                text = str(line).strip()
                if not text:
                    return
                master_log_count += 1
                self._emit_heartbeat(
                    stage="master_solve_log",
                    event="line",
                    iteration=iteration,
                    extra={
                        "line_index": int(master_log_count),
                        "line_limit": int(master_log_limit),
                        "text": text[:master_log_max_chars],
                        "truncated": len(text) > master_log_max_chars,
                    },
                )

            master_status = self.master.solve(
                time_limit_seconds=self.master_seconds,
                solution_hint=solve_hint,
                known_feasible_hint=False,
                ghost_anchor_hint_idx=solve_ghost_anchor_hint_idx,
                hint_inactive_residual_optionals=solve_hint_inactive_residual_optionals,
                diagnostic_log_callback=_emit_master_solve_log
                if master_log_limit > 0
                else None,
            )
            if iteration == 1:
                last_solve = dict(self.master.build_stats.get("last_solve", {}))
                self._master_hinted_literals = int(last_solve.get("hinted_literals", 0))
                self._ghost_anchor_hint_applied = bool(
                    last_solve.get("ghost_anchor_hint_applied", False)
                )
                _ghost_anchor_hint_idx_value = last_solve.get("ghost_anchor_hint_idx")
                if _ghost_anchor_hint_idx_value is not None:
                    self._ghost_anchor_hint_idx = int(_ghost_anchor_hint_idx_value)
                self._residual_optional_zero_hinting_enabled = bool(
                    last_solve.get(
                        "residual_optional_zero_hinting_enabled",
                        self._residual_optional_zero_hinting_enabled,
                    )
                )
                self._residual_optional_zero_hints = int(
                    last_solve.get("residual_optional_zero_hints", 0)
                )
                self._master_start_feasibility["ghost_anchor_hint_applied"] = bool(
                    self._ghost_anchor_hint_applied
                )
                self._master_start_feasibility["ghost_anchor_hint_idx"] = (
                    self._ghost_anchor_hint_idx
                )
                self._master_start_feasibility["ghost_anchor_hint_status"] = str(
                    self._ghost_anchor_hint_status
                )
                self._master_start_feasibility["residual_optional_zero_hints"] = int(
                    self._residual_optional_zero_hints
                )
            if master_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                pass
            elif master_status == cp_model.INFEASIBLE:
                self.last_proof_summary = {
                    "mode": "certified_exact",
                    "benders_iterations": iteration,
                    "master_status": "INFEASIBLE",
                    "diagnostic_flow_status": diagnostic_flow_status,
                    "enumerated_bindings": 0,
                    "routing_attempts": 0,
                    "exact_safe_cut_count": len(self.loaded_exact_safe_cuts) + len(self.generated_exact_safe_cuts),
                    **self._exact_warm_start_summary(),
                    **self._master_search_summary(),
                    **self._subproblem_reuse_summary(),
                    **self._exact_cut_ladder_summary(),
                }
                return RUN_STATUS_INFEASIBLE, None
            else:
                self.last_proof_summary = {
                    "mode": "certified_exact",
                    "benders_iterations": iteration,
                    "master_status": "UNKNOWN",
                    "diagnostic_flow_status": diagnostic_flow_status,
                    "enumerated_bindings": 0,
                    "routing_attempts": 0,
                    **self._exact_warm_start_summary(),
                    **self._master_search_summary(),
                    **self._subproblem_reuse_summary(),
                    **self._exact_cut_ladder_summary(),
                }
                return RUN_STATUS_UNKNOWN, None

            solution = self.master.extract_solution()
            self._emit_heartbeat(
                stage="master_solution_extract",
                event="complete",
                iteration=iteration,
                extra={
                    "master_status": "FEASIBLE",
                    "solution_instance_count": len(solution) if solution else 0,
                },
            )
            if not solution:
                self.last_proof_summary = {
                    "mode": "certified_exact",
                    "benders_iterations": iteration,
                    "master_status": "EMPTY_SOLUTION",
                    "diagnostic_flow_status": diagnostic_flow_status,
                    "enumerated_bindings": 0,
                    "routing_attempts": 0,
                    **self._exact_warm_start_summary(),
                    **self._master_search_summary(),
                    **self._subproblem_reuse_summary(),
                    **self._exact_cut_ladder_summary(),
                }
                return RUN_STATUS_UNKNOWN, None

            if os.environ.get(
                "EXACT_POWER_PLACEMENT_SUBPROBLEM", ""
            ).strip() not in {"", "0", "false", "False"}:
                power_status, power_solution_or_cut = self._run_power_placement_subproblem(
                    solution=solution, iteration=iteration,
                )
                if power_status == "FEASIBLE":
                    solution = power_solution_or_cut
                elif power_status == "INFEASIBLE_CUT_ADDED":
                    iteration += 1
                    continue
                else:
                    return RUN_STATUS_UNKNOWN, None

            self._emit_heartbeat(
                stage="flow_diagnostic",
                event="start",
                iteration=iteration,
            )
            flow_status, _bottlenecks = self._run_flow_diagnostic(solution)
            diagnostic_flow_status = flow_status

            self._emit_heartbeat(
                stage="binding_build",
                event="start",
                iteration=iteration,
                extra={"diagnostic_flow_status": str(diagnostic_flow_status)},
            )
            result_status, certified_solution = self._run_exact_binding_and_routing(
                iteration=iteration,
                solution=solution,
                diagnostic_flow_status=diagnostic_flow_status,
            )
            if result_status == _EXACT_INTERNAL_STATUS_MASTER_CUT_ADDED_CONTINUE:
                continue
            if result_status == RUN_STATUS_CERTIFIED:
                return RUN_STATUS_CERTIFIED, certified_solution
            if result_status == RUN_STATUS_INFEASIBLE:
                return RUN_STATUS_INFEASIBLE, None
            if result_status == RUN_STATUS_UNKNOWN:
                return RUN_STATUS_UNKNOWN, None

        self.last_proof_summary = {
            "mode": "certified_exact",
            "benders_iterations": self.max_iterations,
            "master_status": "MAX_ITERATIONS",
            "diagnostic_flow_status": diagnostic_flow_status,
            "enumerated_bindings": 0,
            "routing_attempts": 0,
            "exact_safe_cut_count": len(self.loaded_exact_safe_cuts) + len(self.generated_exact_safe_cuts),
            **self._exact_warm_start_summary(),
            **self._subproblem_reuse_summary(),
            **self._exact_cut_ladder_summary(),
        }
        return RUN_STATUS_UNPROVEN, None

    def _selected_ghost_cells(self) -> Set[Tuple[int, int]]:
        u_vars = getattr(self.master, "u_vars", None) or {}
        ghost_domains = getattr(self.master, "_ghost_domains", None) or []
        solver = getattr(self.master, "_solver", None)
        if not u_vars or not ghost_domains or solver is None:
            return set()
        for rect_idx, var in u_vars.items():
            try:
                if int(solver.Value(var)) == 1:
                    cells = ghost_domains[int(rect_idx)].get("cells") or []
                    return {(int(c[0]), int(c[1])) for c in cells}
            except Exception:
                continue
        return set()

    def _selected_ghost_anchor(self) -> Optional[Tuple[int, Any, Mapping[str, Any]]]:
        # 返回 (rect_idx, u_var, anchor_dict) 给 power infeasible cut 当 condition
        # — 让 cut 只在当前 ghost anchor 下生效, 不过切 ghost B 下合法解.
        u_vars = getattr(self.master, "u_vars", None) or {}
        ghost_domains = getattr(self.master, "_ghost_domains", None) or []
        solver = getattr(self.master, "_solver", None)
        if not u_vars or not ghost_domains or solver is None:
            return None
        for rect_idx, var in u_vars.items():
            try:
                if int(solver.Value(var)) == 1:
                    domain = ghost_domains[int(rect_idx)]
                    return int(rect_idx), var, dict(domain.get("anchor") or {})
            except Exception:
                continue
        return None

    def _run_power_placement_subproblem(
        self,
        *,
        solution: Dict[str, Any],
        iteration: int,
    ) -> Tuple[str, Any]:
        # Returns ("FEASIBLE", updated_solution) | ("INFEASIBLE_CUT_ADDED", None) | ("ABORT", None)
        time_limit = float(os.environ.get("EXACT_POWER_SUBPROBLEM_SECONDS", "10") or "10")
        powered_templates: Set[str] = getattr(self.master, "_powered_templates", set()) or set()
        coverers = (
            getattr(self.master, "_power_coverers_by_template_pose", {}) or {}
        )
        ghost_cells = self._selected_ghost_cells()

        sub = PowerPlacementSubproblem(
            master_solution=solution,
            facility_pools=self.master.facility_pools,
            powered_templates=powered_templates,
            power_coverers_by_template_pose=coverers,
            ghost_cells=ghost_cells,
        )
        sub.build()
        result = sub.solve(time_limit_seconds=time_limit)

        self._emit_heartbeat(
            stage="power_placement_subproblem",
            event=result.status.lower(),
            iteration=iteration,
            extra=dict(result.stats),
        )

        if result.status == "FEASIBLE":
            updated = inject_power_poles_into_solution(
                solution,
                selected_pose_indices=result.selected_pose_indices,
                facility_pools=self.master.facility_pools,
                solve_mode=self.solve_mode,
            )
            return "FEASIBLE", updated

        if result.status == "INFEASIBLE":
            # power infeasibility 跟当前 selected ghost anchor 强相关 — pole 不能
            # 覆盖到 ghost cells, ghost A 挡住唯一可用 pole 时 infeasible 不代表
            # ghost B 下同一组 pose 也 infeasible. cut 必须 ghost-conditioned,
            # 否则 over-prune 跨 ghost alternatives.
            conflict_set: Dict[str, int] = {}
            for instance_id, entry in solution.items():
                tpl = str(entry.get("facility_type"))
                if tpl in powered_templates and tpl != "power_pole":
                    conflict_set[str(instance_id)] = int(entry["pose_idx"])
            if not conflict_set:
                return "ABORT", None

            ghost_anchor_info = self._selected_ghost_anchor()
            if ghost_anchor_info is None:
                # ghost anchor 取不到 → exact-safe fallback 是 abort, 不退化到
                # 全局 cut (按 GPT v3 P0 #1 建议).
                self._emit_heartbeat(
                    stage="power_placement_subproblem",
                    event="cut_skipped_no_ghost_anchor",
                    iteration=iteration,
                    extra={"conflict_size": len(conflict_set)},
                )
                return "ABORT", None

            rect_idx, u_var, anchor = ghost_anchor_info
            anchor_x = int(anchor.get("x", 0))
            anchor_y = int(anchor.get("y", 0))
            condition_set = {f"ghost_anchor::({anchor_x},{anchor_y})": int(rect_idx)}

            applied = self._add_exact_persisted_nogood(
                conflict_set=conflict_set,
                iteration=iteration,
                cut_type="power_subproblem_infeasible_nogood",
                proof_stage="power_placement_subproblem",
                proof_summary={
                    "mode": "certified_exact",
                    "benders_iterations": iteration,
                    "stage": "power_placement_subproblem",
                    "status": "INFEASIBLE",
                    "uncovered_instances": list(result.uncovered_instance_ids),
                    **self._exact_warm_start_summary(),
                },
                metadata={
                    "kind": "power_subproblem_ghost_conditioned_nogood",
                    "ghost_rect_idx": int(rect_idx),
                    "ghost_anchor": {"x": anchor_x, "y": anchor_y},
                },
                condition_set=condition_set,
                condition_lits=(u_var,),
            )
            self._emit_heartbeat(
                stage="power_placement_subproblem",
                event="cut_added" if applied else "cut_skipped",
                iteration=iteration,
                extra={
                    "conflict_size": len(conflict_set),
                    "condition_size": 1,
                    "ghost_rect_idx": int(rect_idx),
                    "uncovered_instances": list(result.uncovered_instance_ids),
                },
            )
            if not applied:
                return "ABORT", None
            return "INFEASIBLE_CUT_ADDED", None

        # TIMEOUT — no exact-safe cut available; abort this iteration.
        return "ABORT", None

    def _run_flow_diagnostic(
        self,
        solution: Mapping[str, Mapping[str, Any]],
    ) -> Tuple[str, Set[str]]:
        occupied_cells: Set[Tuple[int, int]] = set()
        port_dict: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for instance_id, solution_entry in solution.items():
            pose_idx = int(solution_entry["pose_idx"])
            facility_type = str(solution_entry["facility_type"])
            pose = self.master.facility_pools[facility_type][pose_idx]

            for cell in pose.get("occupied_cells", []):
                occupied_cells.add((int(cell[0]), int(cell[1])))

            for port in pose.get("input_port_cells", []):
                payload = dict(port)
                payload["instance_id"] = instance_id
                payload["type"] = "in"
                port_dict["dummy_commodity"].append(payload)

            for port in pose.get("output_port_cells", []):
                payload = dict(port)
                payload["instance_id"] = instance_id
                payload["type"] = "out"
                port_dict["dummy_commodity"].append(payload)

        flow_network = build_flow_network(occupied_cells, port_dict, self.commodity_demands)
        flow_subproblem = FlowSubproblem(
            flow_network,
            self.commodity_demands,
            solve_mode=self.solve_mode,
        )
        flow_status = flow_subproblem.build_and_solve(time_limit_ms=int(self.flow_seconds * 1000))
        return flow_status, set(flow_subproblem.extract_bottleneck_instances())

    def _run_exact_binding_and_routing(
        self,
        *,
        iteration: int,
        solution: Dict[str, Any],
        diagnostic_flow_status: str,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        # P1 #12 spike instrumentation: record placement → binding input for
        # offline repeat-rate analysis. Env-gated, no-op when probe is off.
        from src.runtime.subproblem_invocation_counter import record as _spike_record
        _spike_record("binding", solution)

        self._emit_heartbeat(
            stage="binding_build",
            event="start",
            iteration=iteration,
            extra={"diagnostic_flow_status": str(diagnostic_flow_status)},
        )
        binding_model = PortBindingModel(
            solution,
            self.master.facility_pools,
            self.master.source_instances,
            project_root=self.project_root,
        )
        binding_model.build()
        self._used_routing_core_reuse = False
        self._routing_core_build_seconds = 0.0
        self._routing_overlay_build_seconds = 0.0
        self._routing_domain_cells = 0
        self._routing_terminal_core_cells = 0
        self._routing_state_space_vars = 0
        self._routing_local_pattern_pruned_states = 0
        self._update_binding_cache_from_summary(binding_model.extract_conflict_summary())

        enumerated_bindings = 0
        routing_attempts = 0
        occupied_cells = self._extract_occupied_cells(solution)
        occupied_owner_by_cell = self._extract_occupied_owner_by_cell(solution)
        routing_placement_core: Optional[RoutingPlacementCore] = None
        empty_binding_domain_instances = list(
            getattr(binding_model, "extract_empty_binding_domain_instances", lambda: [])()
        )
        if empty_binding_domain_instances:
            cut_added = False
            for empty_domain in empty_binding_domain_instances:
                conflict_set = self._build_conflict_from_instance_ids(
                    solution,
                    [str(empty_domain["instance_id"])],
                )
                if not conflict_set:
                    continue
                cut_summary = {
                    "mode": "certified_exact",
                    "benders_iterations": iteration,
                    "master_status": "FEASIBLE",
                    "binding_status": "EMPTY_DOMAIN",
                    "diagnostic_flow_status": diagnostic_flow_status,
                    "enumerated_bindings": enumerated_bindings,
                    "routing_attempts": routing_attempts,
                    "binding_summary": binding_model.extract_conflict_summary(),
                    "empty_binding_domain_instance": dict(empty_domain),
                    **self._exact_warm_start_summary(),
                    **self._subproblem_reuse_summary(),
                    **self._exact_cut_ladder_summary_with_deltas(
                        fine_grained_delta=1,
                        binding_domain_empty_delta=1,
                    ),
                }
                was_added = self._add_exact_persisted_nogood(
                    conflict_set=conflict_set,
                    iteration=iteration,
                    cut_type="binding_pose_domain_empty_nogood",
                    proof_stage="binding",
                    proof_summary=cut_summary,
                    metadata={"kind": "placement_local_nogood"},
                )
                if was_added:
                    self._fine_grained_exact_safe_cut_count += 1
                    self._binding_domain_empty_cut_count += 1
                    cut_added = True

            self.last_proof_summary = {
                "mode": "certified_exact",
                "benders_iterations": iteration,
                "master_status": "FEASIBLE",
                "binding_status": "EMPTY_DOMAIN",
                "diagnostic_flow_status": diagnostic_flow_status,
                "enumerated_bindings": enumerated_bindings,
                "routing_attempts": routing_attempts,
                "binding_summary": binding_model.extract_conflict_summary(),
                "master_follow_up": (
                    _EXACT_INTERNAL_STATUS_MASTER_CUT_ADDED_CONTINUE if cut_added else "cut_stall"
                ),
                **self._exact_warm_start_summary(),
                **self._subproblem_reuse_summary(),
                **self._exact_cut_ladder_summary(),
            }
            if cut_added:
                return _EXACT_INTERNAL_STATUS_MASTER_CUT_ADDED_CONTINUE, None
            return RUN_STATUS_UNKNOWN, None

        self._emit_heartbeat(
            stage="binding_solve",
            event="start",
            iteration=iteration,
            extra={
                "empty_binding_domain_count": len(empty_binding_domain_instances),
            },
        )
        binding_status = binding_model.solve(time_limit_seconds=self.binding_seconds)
        if binding_status == "TIMEOUT":
            self.last_proof_summary = {
                "mode": "certified_exact",
                "benders_iterations": iteration,
                "master_status": "FEASIBLE",
                "binding_status": "TIMEOUT",
                "diagnostic_flow_status": diagnostic_flow_status,
                "enumerated_bindings": enumerated_bindings,
                "routing_attempts": routing_attempts,
                "binding_summary": binding_model.extract_conflict_summary(),
                **self._exact_warm_start_summary(),
                **self._subproblem_reuse_summary(),
                **self._exact_cut_ladder_summary(),
            }
            return RUN_STATUS_UNKNOWN, None

        if binding_status == "INFEASIBLE":
            # P1 #9 hint 2 stage 3: caller fallback ladder. If the first-pass
            # binding model had EXACT_BINDING_USE_OVERLOAD_SEPARATION on AND
            # actually injected overload nogoods, the INFEASIBLE may be a
            # spurious one caused by the heuristic high+low colocation
            # forbidding (player consensus, not a hard SAT invariant). Retry
            # once with the env forced off:
            #   FEASIBLE  -> recover, swap models, continue normally
            #   INFEASIBLE -> genuine infeasibility, fall through
            #   TIMEOUT    -> env-off status unknown; can't certify INFEASIBLE,
            #                 surface as TIMEOUT/UNKNOWN to keep the proof sound
            first_pass_summary = binding_model.extract_conflict_summary()
            if (
                first_pass_summary.get("overload_separation_enabled") is True
                and int(first_pass_summary.get("overload_nogoods_added", 0)) > 0
            ):
                retry_model, retry_status = (
                    self._retry_binding_without_overload_separation(
                        solution=solution,
                        iteration=iteration,
                    )
                )
                if retry_status == "FEASIBLE":
                    binding_model = retry_model
                    binding_status = retry_status
                    self._update_binding_cache_from_summary(
                        binding_model.extract_conflict_summary()
                    )
                elif retry_status == "TIMEOUT":
                    self.last_proof_summary = {
                        "mode": "certified_exact",
                        "benders_iterations": iteration,
                        "master_status": "FEASIBLE",
                        "binding_status": "TIMEOUT",
                        "diagnostic_flow_status": diagnostic_flow_status,
                        "enumerated_bindings": enumerated_bindings,
                        "routing_attempts": routing_attempts,
                        "binding_summary": retry_model.extract_conflict_summary(),
                        "overload_fallback_outcome": "TIMEOUT",
                        **self._exact_warm_start_summary(),
                        **self._subproblem_reuse_summary(),
                        **self._exact_cut_ladder_summary(),
                    }
                    return RUN_STATUS_UNKNOWN, None

        if binding_status == "INFEASIBLE":
            proof_summary = {
                "mode": "certified_exact",
                "benders_iterations": iteration,
                "master_status": "FEASIBLE",
                "binding_status": "INFEASIBLE",
                "diagnostic_flow_status": diagnostic_flow_status,
                "enumerated_bindings": enumerated_bindings,
                "routing_attempts": routing_attempts,
                "binding_summary": binding_model.extract_conflict_summary(),
                **self._exact_warm_start_summary(),
                **self._subproblem_reuse_summary(),
                **self._exact_cut_ladder_summary(),
            }
            cut_applied = self._add_exact_whole_layout_nogood(
                solution=solution,
                iteration=iteration,
                cut_type="binding_infeasible_nogood",
                proof_stage="binding",
                binding_exhausted=True,
                routing_exhausted=False,
                proof_summary=proof_summary,
            )
            self.last_proof_summary = dict(proof_summary)
            if not cut_applied:
                # GPT v4 P0 #2: power witness incomplete, 不可 certify INFEASIBLE.
                return RUN_STATUS_UNKNOWN, None
            # B1 Phase 3: pose-bool master 可以从 nogood cut 学习, 让 LBBD 重选 layout.
            # Coordinate path 直接 return INFEASIBLE (这个分支保留 default).
            if os.environ.get("EXACT_USE_POSE_BOOL_MASTER", "").strip().lower() in {"1", "true", "yes", "on"}:
                return _EXACT_INTERNAL_STATUS_MASTER_CUT_ADDED_CONTINUE, None
            return RUN_STATUS_INFEASIBLE, None

        self._emit_heartbeat(
            stage="routing_core_build",
            event="start",
            iteration=iteration,
            extra={"binding_status": str(binding_status)},
        )
        routing_core_started = time.perf_counter()
        routing_placement_core = RoutingPlacementCore.from_occupied_cells(
            occupied_cells,
            occupied_owner_by_cell=occupied_owner_by_cell,
        )
        self._used_routing_core_reuse = True
        self._routing_core_build_seconds = time.perf_counter() - routing_core_started

        while binding_status == "FEASIBLE":
            selection = binding_model.extract_selection()
            port_specs = binding_model.extract_port_specs()
            enumerated_bindings += 1
            self._emit_heartbeat(
                stage="routing_precheck",
                event="start",
                iteration=iteration,
                extra={
                    "binding_status": str(binding_status),
                    "enumerated_bindings": int(enumerated_bindings),
                    "port_spec_count": len(port_specs),
                },
            )

            routing_grid = None
            if routing_placement_core is not None and hasattr(RoutingGrid, "from_placement_core"):
                try:
                    routing_grid = RoutingGrid.from_placement_core(routing_placement_core, port_specs)
                except TypeError:
                    routing_grid = None
            if routing_grid is None:
                try:
                    routing_grid = RoutingGrid(
                        occupied_cells,
                        port_specs,
                        occupied_owner_by_cell=occupied_owner_by_cell,
                    )
                except TypeError:
                    routing_grid = RoutingGrid(occupied_cells, port_specs)

            routing_domain_analysis = None
            routing_precheck = None
            if routing_placement_core is not None and hasattr(RoutingGrid, "from_placement_core"):
                try:
                    routing_precheck = run_exact_routing_precheck(
                        placement_core=routing_placement_core,
                        port_specs=port_specs,
                        occupied_owner_by_cell=occupied_owner_by_cell,
                    )
                except TypeError:
                    routing_precheck = None
            if routing_precheck is None and hasattr(routing_grid, "free_cells") and hasattr(routing_grid, "port_specs"):
                try:
                    routing_precheck = run_exact_routing_precheck(
                        routing_grid,
                        occupied_owner_by_cell=occupied_owner_by_cell,
                    )
                except TypeError:
                    routing_precheck = run_exact_routing_precheck(routing_grid)
            if routing_precheck is None:
                routing_precheck = {
                    "status": "feasible",
                    "binding_selection_safe_reject": False,
                    "placement_level_conflict_set": [],
                    "blocked_ports": [],
                    "disconnected_commodities": [],
                }
            routing_domain_analysis = routing_precheck.get("_analysis")
            routing_precheck_summary = {
                str(key): value
                for key, value in routing_precheck.items()
                if str(key) != "_analysis"
            }
            self._update_routing_shrink_from_domain_stats(
                routing_precheck_summary.get("domain_stats")
            )
            precheck_status = str(routing_precheck_summary.get("status", "feasible"))
            self._routing_precheck_statuses.append(precheck_status)

            # B1 Phase 4: env on 时 skip front_blocked early reject — precheck 是
            # heuristic, routing CP-SAT 实际能绕路. pose-bool master 不知 port
            # direction, 每个 layout precheck 都 front_blocked ~500-600 ports,
            # cut accumulation 实测 15 iter 不收敛. 让 routing CP-SAT 完整跑.
            if precheck_status == "front_blocked" and os.environ.get(
                "EXACT_USE_POSE_BOOL_MASTER", ""
            ).strip().lower() in {"1", "true", "yes", "on"} and os.environ.get(
                "EXACT_B1_BYPASS_ROUTING_PRECHECK", ""
            ).strip().lower() in {"1", "true", "yes", "on"}:
                precheck_status = "feasible"  # 让 routing.solve 实际跑

            if precheck_status == "front_blocked":
                self._routing_precheck_rejections += 1
                cut_added = False
                for blocked_port in routing_precheck_summary.get("blocked_ports", []):
                    conflict_set = self._build_conflict_from_instance_ids(
                        solution,
                        list(blocked_port.get("placement_level_conflict_set", [])),
                    )
                    if not conflict_set:
                        continue
                    cut_summary = {
                        "mode": "certified_exact",
                        "benders_iterations": iteration,
                        "master_status": "FEASIBLE",
                        "binding_status": "FEASIBLE",
                        "routing_status": "PRECHECK_FRONT_BLOCKED",
                        "diagnostic_flow_status": diagnostic_flow_status,
                        "enumerated_bindings": enumerated_bindings,
                        "routing_attempts": routing_attempts,
                        "binding_summary": binding_model.extract_conflict_summary(),
                        "routing_precheck": dict(routing_precheck_summary),
                        "blocked_port": dict(blocked_port),
                        **self._exact_warm_start_summary(),
                        **self._subproblem_reuse_summary(),
                        **self._routing_shrink_summary(),
                        **self._exact_cut_ladder_summary_with_deltas(
                            fine_grained_delta=1,
                            routing_front_blocked_delta=1,
                        ),
                    }
                    was_added = self._add_exact_persisted_nogood(
                        conflict_set=conflict_set,
                        iteration=iteration,
                        cut_type="routing_front_blocked_nogood",
                        proof_stage="routing",
                        proof_summary=cut_summary,
                        metadata={"kind": "placement_local_nogood"},
                    )
                    if was_added:
                        self._fine_grained_exact_safe_cut_count += 1
                        self._routing_front_blocked_cut_count += 1
                        cut_added = True

                self.last_proof_summary = {
                    "mode": "certified_exact",
                    "benders_iterations": iteration,
                    "master_status": "FEASIBLE",
                    "binding_status": "FEASIBLE",
                    "routing_status": "PRECHECK_FRONT_BLOCKED",
                    "diagnostic_flow_status": diagnostic_flow_status,
                    "enumerated_bindings": enumerated_bindings,
                    "routing_attempts": routing_attempts,
                    "binding_summary": binding_model.extract_conflict_summary(),
                    "routing_precheck": dict(routing_precheck_summary),
                    "master_follow_up": (
                        _EXACT_INTERNAL_STATUS_MASTER_CUT_ADDED_CONTINUE if cut_added else "cut_stall"
                    ),
                    **self._exact_warm_start_summary(),
                    **self._subproblem_reuse_summary(),
                    **self._routing_shrink_summary(),
                    **self._exact_cut_ladder_summary(),
                }
                if cut_added:
                    return _EXACT_INTERNAL_STATUS_MASTER_CUT_ADDED_CONTINUE, None
                return RUN_STATUS_UNKNOWN, None

            if precheck_status == "relaxed_disconnected":
                self._routing_precheck_rejections += 1
                if self._binding_has_alternatives(binding_model):
                    binding_model.add_nogood_cut(selection)
                    binding_status = binding_model.solve(time_limit_seconds=self.binding_seconds)
                    if binding_status == "TIMEOUT":
                        self.last_proof_summary = {
                            "mode": "certified_exact",
                            "benders_iterations": iteration,
                            "master_status": "FEASIBLE",
                            "binding_status": "TIMEOUT",
                            "routing_status": "PRECHECK_RELAXED_DISCONNECTED",
                            "diagnostic_flow_status": diagnostic_flow_status,
                            "enumerated_bindings": enumerated_bindings,
                            "routing_attempts": routing_attempts,
                            "binding_summary": binding_model.extract_conflict_summary(),
                            "routing_precheck": dict(routing_precheck_summary),
                            **self._exact_warm_start_summary(),
                            **self._subproblem_reuse_summary(),
                            **self._routing_shrink_summary(),
                            **self._exact_cut_ladder_summary(),
                        }
                        return RUN_STATUS_UNKNOWN, None
                    continue
                break

            commodities = sorted({str(port["commodity"]) for port in port_specs})
            self._emit_heartbeat(
                stage="routing_model_build",
                event="start",
                iteration=iteration,
                extra={
                    "binding_status": str(binding_status),
                    "routing_precheck_status": str(precheck_status),
                    "enumerated_bindings": int(enumerated_bindings),
                    "commodity_count": len(commodities),
                },
            )
            routing_overlay_started = time.perf_counter()
            routing_model = None
            if (
                routing_placement_core is not None
                and hasattr(RoutingGrid, "from_placement_core")
                and hasattr(RoutingSubproblem, "from_placement_core")
            ):
                try:
                    routing_model = RoutingSubproblem.from_placement_core(
                        routing_placement_core,
                        port_specs,
                        commodities,
                        domain_analysis=routing_domain_analysis,
                    )
                except TypeError:
                    routing_model = None
            if routing_model is None:
                if routing_domain_analysis is None:
                    routing_model = RoutingSubproblem(routing_grid, commodities)
                else:
                    try:
                        routing_model = RoutingSubproblem(
                            routing_grid,
                            commodities,
                            domain_analysis=routing_domain_analysis,
                        )
                    except TypeError:
                        routing_model = RoutingSubproblem(routing_grid, commodities)
            routing_model.build()
            self._routing_overlay_build_seconds = time.perf_counter() - routing_overlay_started
            self._update_routing_shrink_from_build_stats(routing_model.build_stats)
            routing_attempts += 1
            self._emit_heartbeat(
                stage="routing_solve",
                event="start",
                iteration=iteration,
                extra={
                    "binding_status": str(binding_status),
                    "routing_precheck_status": str(precheck_status),
                    "enumerated_bindings": int(enumerated_bindings),
                    "routing_attempts": int(routing_attempts),
                    "routing_state_space_vars": int(self._routing_state_space_vars),
                    "routing_domain_cells": int(self._routing_domain_cells),
                },
            )
            routing_status = routing_model.solve(time_limit=self.routing_seconds)

            if routing_status == "FEASIBLE":
                self.last_proof_summary = {
                    "mode": "certified_exact",
                    "benders_iterations": iteration,
                    "master_status": "FEASIBLE",
                    "binding_status": "FEASIBLE",
                    "routing_status": "FEASIBLE",
                    "diagnostic_flow_status": diagnostic_flow_status,
                    "enumerated_bindings": enumerated_bindings,
                    "routing_attempts": routing_attempts,
                    "binding_summary": binding_model.extract_conflict_summary(),
                    "routing_summary": dict(routing_model.build_stats),
                    **self._exact_warm_start_summary(),
                    **self._subproblem_reuse_summary(),
                    **self._routing_shrink_summary(),
                    **self._exact_cut_ladder_summary(),
                }
                return RUN_STATUS_CERTIFIED, solution

            if routing_status == "TIMEOUT":
                self.last_proof_summary = {
                    "mode": "certified_exact",
                    "benders_iterations": iteration,
                    "master_status": "FEASIBLE",
                    "binding_status": "FEASIBLE",
                    "routing_status": "TIMEOUT",
                    "diagnostic_flow_status": diagnostic_flow_status,
                    "enumerated_bindings": enumerated_bindings,
                    "routing_attempts": routing_attempts,
                    "binding_summary": binding_model.extract_conflict_summary(),
                    "routing_summary": dict(routing_model.build_stats),
                    **self._exact_warm_start_summary(),
                    **self._subproblem_reuse_summary(),
                    **self._routing_shrink_summary(),
                    **self._exact_cut_ladder_summary(),
                }
                return RUN_STATUS_UNKNOWN, None

            if self._binding_has_alternatives(binding_model):
                binding_model.add_nogood_cut(selection)
                self._emit_heartbeat(
                    stage="binding_resolve",
                    event="start",
                    iteration=iteration,
                    extra={
                        "previous_routing_status": str(routing_status),
                        "enumerated_bindings": int(enumerated_bindings),
                        "routing_attempts": int(routing_attempts),
                    },
                )
                binding_status = binding_model.solve(time_limit_seconds=self.binding_seconds)
                if binding_status == "TIMEOUT":
                    self.last_proof_summary = {
                        "mode": "certified_exact",
                        "benders_iterations": iteration,
                        "master_status": "FEASIBLE",
                        "binding_status": "TIMEOUT",
                        "routing_status": "INFEASIBLE",
                        "diagnostic_flow_status": diagnostic_flow_status,
                        "enumerated_bindings": enumerated_bindings,
                        "routing_attempts": routing_attempts,
                        "binding_summary": binding_model.extract_conflict_summary(),
                        "routing_summary": dict(routing_model.build_stats),
                        **self._exact_warm_start_summary(),
                        **self._subproblem_reuse_summary(),
                        **self._routing_shrink_summary(),
                        **self._exact_cut_ladder_summary(),
                    }
                    return RUN_STATUS_UNKNOWN, None
                continue

            break

        proof_summary = {
            "mode": "certified_exact",
            "benders_iterations": iteration,
            "master_status": "FEASIBLE",
            "binding_status": "EXHAUSTED",
            "routing_status": "ALL_INFEASIBLE",
            "diagnostic_flow_status": diagnostic_flow_status,
            "enumerated_bindings": enumerated_bindings,
            "routing_attempts": routing_attempts,
            "binding_summary": binding_model.extract_conflict_summary(),
            **self._exact_warm_start_summary(),
            **self._subproblem_reuse_summary(),
            **self._routing_shrink_summary(),
            **self._exact_cut_ladder_summary(),
        }
        cut_applied = self._add_exact_whole_layout_nogood(
            solution=solution,
            iteration=iteration,
            cut_type="routing_exhausted_nogood",
            proof_stage="routing",
            binding_exhausted=True,
            routing_exhausted=True,
            proof_summary=proof_summary,
        )
        self.last_proof_summary = dict(proof_summary)
        if not cut_applied:
            # GPT v4 P0 #2: power witness incomplete, 不可 certify INFEASIBLE.
            return RUN_STATUS_UNKNOWN, None
        return RUN_STATUS_INFEASIBLE, None

    def _retry_binding_without_overload_separation(
        self,
        *,
        solution: Dict[str, Any],
        iteration: int,
    ) -> Tuple[PortBindingModel, str]:
        """P1 #9 hint 2 stage 3: caller fallback ladder.

        Re-construct the binding model with EXACT_BINDING_USE_OVERLOAD_SEPARATION
        forced off and re-solve once. Caller invokes this only after the
        first-pass solve returned INFEASIBLE while overload separation was
        active and had injected nogoods. Env value is restored before
        return regardless of outcome.

        Returns (retry_model, retry_status). retry_status is one of
        "FEASIBLE" | "INFEASIBLE" | "TIMEOUT".
        """
        env_key = "EXACT_BINDING_USE_OVERLOAD_SEPARATION"
        saved = os.environ.get(env_key)
        self._emit_heartbeat(
            stage="binding_overload_fallback",
            event="start",
            iteration=iteration,
        )
        try:
            os.environ[env_key] = ""
            retry_model = PortBindingModel(
                solution,
                self.master.facility_pools,
                self.master.source_instances,
                project_root=self.project_root,
            )
            retry_model.build()
            retry_status = retry_model.solve(time_limit_seconds=self.binding_seconds)
        finally:
            if saved is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = saved
        self._emit_heartbeat(
            stage="binding_overload_fallback",
            event="end",
            iteration=iteration,
            extra={"retry_status": str(retry_status)},
        )
        return retry_model, retry_status

    def _extract_occupied_owner_by_cell(
        self,
        solution: Mapping[str, Mapping[str, Any]],
    ) -> Dict[Tuple[int, int], str]:
        owner_by_cell: Dict[Tuple[int, int], str] = {}
        for instance_id, solution_entry in solution.items():
            pose_idx = int(solution_entry["pose_idx"])
            facility_type = str(solution_entry["facility_type"])
            pose = self.master.facility_pools[facility_type][pose_idx]
            for cell in pose.get("occupied_cells", []):
                owner_by_cell[(int(cell[0]), int(cell[1]))] = str(instance_id)
        return owner_by_cell

    def _extract_occupied_cells(
        self,
        solution: Mapping[str, Mapping[str, Any]],
    ) -> Set[Tuple[int, int]]:
        occupied_cells: Set[Tuple[int, int]] = set()
        for solution_entry in solution.values():
            pose_idx = int(solution_entry["pose_idx"])
            facility_type = str(solution_entry["facility_type"])
            pose = self.master.facility_pools[facility_type][pose_idx]
            for cell in pose.get("occupied_cells", []):
                occupied_cells.add((int(cell[0]), int(cell[1])))
        return occupied_cells

    def _binding_has_alternatives(self, binding_model: PortBindingModel) -> bool:
        return bool(
            binding_model.binding_vars
            or binding_model.generic_input_vars
            or binding_model.generic_output_vars
        )

    def _build_whole_layout_conflict(
        self,
        solution: Mapping[str, Mapping[str, Any]],
    ) -> Dict[str, int]:
        return {
            str(instance_id): int(solution_entry["pose_idx"])
            for instance_id, solution_entry in solution.items()
        }

    def _build_conflict_from_instance_ids(
        self,
        solution: Mapping[str, Mapping[str, Any]],
        instance_ids: Sequence[str],
    ) -> Dict[str, int]:
        conflict_set: Dict[str, int] = {}
        for instance_id in instance_ids:
            if instance_id not in solution:
                continue
            conflict_set[str(instance_id)] = int(solution[instance_id]["pose_idx"])
        return conflict_set

    def _add_exact_persisted_nogood(
        self,
        *,
        conflict_set: Mapping[str, int],
        iteration: int,
        cut_type: str,
        proof_stage: str,
        proof_summary: Mapping[str, Any],
        metadata: Optional[Mapping[str, Any]] = None,
        binding_exhausted: bool = False,
        routing_exhausted: bool = False,
        condition_set: Optional[Mapping[str, Any]] = None,
        condition_lits: Sequence[Any] = (),
    ) -> bool:
        cut = BendersCut(
            schema_version=3 if condition_set else 2,
            cut_type=cut_type,
            conflict_set={str(k): int(v) for k, v in conflict_set.items()},
            iteration=iteration,
            metadata=dict(metadata or {}),
            source_mode="certified_exact",
            exact_safe=True,
            artifact_hashes=dict(self.artifact_hashes),
            proof_stage=proof_stage,
            binding_exhausted=binding_exhausted,
            routing_exhausted=routing_exhausted,
            proof_summary=dict(proof_summary),
            created_at=now_iso(),
            epsilon_stage=self.epsilon_stage,
            condition_set={str(k): v for k, v in (condition_set or {}).items()},
        )
        if not self.cut_manager.register_structured_cut(cut):
            return False
        self.generated_exact_safe_cuts.append(cut)
        self.master.add_benders_cut(conflict_set, condition_lits=tuple(condition_lits))
        return True

    def _add_exact_whole_layout_nogood(
        self,
        *,
        solution: Mapping[str, Mapping[str, Any]],
        iteration: int,
        cut_type: str,
        proof_stage: str,
        binding_exhausted: bool,
        routing_exhausted: bool,
        proof_summary: Mapping[str, Any],
    ) -> bool:
        # GPT v4 P0 #2 stop-gap: EXACT_POWER_PLACEMENT_SUBPROBLEM=1 时 master 不带
        # power_pole residual slots, 而 power subproblem feasible 后会把 synthetic
        # power_pole entry 注入 solution. 这些 entry 进 whole-layout cut 后在
        # ExactCoordinateMaster._conflict_pose_entries 里找不到 slot → 没 presence
        # literal → cut 只约束上游 powered layout, 等价于 "layout + 任意 pole
        # witness" 都禁掉. 这会过切真实存在的 pole alternatives.
        # 当前修法: flag on 下 fail-closed 跳过 cut, 返回 False 让 caller 升 UNKNOWN.
        # 彻底修需要 pole alternatives enumeration / witness-complete cut (~3-5d).
        flag_on = os.environ.get(
            "EXACT_POWER_PLACEMENT_SUBPROBLEM", ""
        ).strip() not in {"", "0", "false", "False"}
        has_synthetic_pole = any(
            str(iid).startswith("pose_optional::power_pole::")
            or str(entry.get("facility_type")) == "power_pole"
            for iid, entry in solution.items()
        )
        if flag_on and has_synthetic_pole:
            self._emit_heartbeat(
                stage=proof_stage,
                event="whole_layout_nogood_skipped_power_witness_incomplete",
                iteration=iteration,
                extra={
                    "cut_type": cut_type,
                    "solution_size": len(solution),
                },
            )
            return False
        conflict_set = self._build_whole_layout_conflict(solution)
        self._add_exact_persisted_nogood(
            conflict_set=conflict_set,
            iteration=iteration,
            cut_type=cut_type,
            proof_stage=proof_stage,
            proof_summary=proof_summary,
            metadata={"kind": "whole_layout_nogood"},
            binding_exhausted=binding_exhausted,
            routing_exhausted=routing_exhausted,
        )
        return True


def run_benders_for_ghost_rect(
    *,
    ghost_w: int,
    ghost_h: int,
    max_iterations: int = 30,
    project_root: Optional[Path] = None,
    solve_mode: Optional[str] = None,
    certification_mode: Optional[bool] = None,
    master_seconds: float = 600.0,
    binding_seconds: float = 600.0,
    routing_seconds: float = 600.0,
    flow_seconds: float = 60.0,
    campaign: Optional[Any] = None,
    session: Optional[ExactSearchSession] = None,
    preloaded_exact_safe_cuts: Optional[Sequence[Mapping[str, Any]]] = None,
    master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    disable_master_warm_start: bool = False,
    heartbeat_callback: Optional[_CampaignHeartbeatCallback] = None,
    epsilon_stage: Optional[float] = None,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Run the current Benders loop for one ghost rectangle size."""

    _reset_last_run_metadata()

    solve_mode = _normalize_solve_mode(solve_mode, certification_mode)
    project_root = project_root or PROJECT_ROOT
    candidate_key = f"{int(ghost_w)}x{int(ghost_h)}"

    def _emit_campaign_heartbeat(payload: Mapping[str, Any]) -> None:
        heartbeat = {
            "schema_version": 1,
            "candidate_key": candidate_key,
            "ghost_rect": {
                "w": int(ghost_w),
                "h": int(ghost_h),
                "area": int(ghost_w) * int(ghost_h),
            },
            "updated_at": now_iso(),
            **dict(payload),
        }
        if heartbeat_callback is not None:
            try:
                heartbeat_callback(heartbeat)
            except Exception:
                pass
        if not isinstance(campaign, ExactCampaign):
            return
        campaign.update_candidate_running_proof_summary(
            int(ghost_w),
            int(ghost_h),
            {"campaign_heartbeat": heartbeat},
        )
        campaign.save()

    instances: List[Dict[str, Any]]
    facility_pools: Dict[str, List[Dict[str, Any]]]
    rules: Dict[str, Any]
    artifact_hashes: Dict[str, str] = {}
    used_exact_core_reuse = False
    core_build_seconds = 0.0
    overlay_build_seconds = 0.0
    ghost_constraint_seconds = 0.0
    cut_replay_seconds = 0.0
    exact_session: Optional[ExactSearchSession] = None
    if solve_mode == "certified_exact":
        _emit_campaign_heartbeat(
            {
                "stage": "exact_session",
                "event": "start",
                "master_search_profile": str(master_search_profile),
                "disable_master_warm_start": bool(disable_master_warm_start),
            }
        )
        exact_session = session
        if exact_session is None:
            exact_session = create_exact_search_session(
                project_root,
                solve_mode=solve_mode,
                master_search_profile=master_search_profile,
            )
        elif (
            exact_session.project_root != project_root
            or exact_session.solve_mode != solve_mode
            or str(exact_session.master_search_profile) != str(master_search_profile)
        ):
            raise ValueError(
                "ExactSearchSession does not match the requested project_root/solve_mode/master_search_profile"
            )

        instances = list(exact_session.instances)
        facility_pools = dict(exact_session.facility_pools)
        rules = dict(exact_session.rules)
        artifact_hashes = dict(exact_session.artifact_hashes)
        _emit_campaign_heartbeat(
            {
                "stage": "exact_session",
                "event": "complete",
                "master_search_profile": str(master_search_profile),
                "disable_master_warm_start": bool(disable_master_warm_start),
                "core_build_seconds": float(exact_session.core_build_seconds),
            }
        )
        core_build_seconds = float(exact_session.core_build_seconds)
        blockers = collect_certification_blockers(instances=instances, solve_mode=solve_mode)
        if blockers:
            _publish_last_run_metadata(
                _merge_reuse_metadata(
                    {
                        "mode": "certified_exact",
                        "master_status": "BLOCKED",
                        "blockers": blockers,
                        "enumerated_bindings": 0,
                        "routing_attempts": 0,
                        "diagnostic_flow_status": "NOT_RUN",
                        "used_greedy_hint": False,
                        "greedy_hint_instances": 0,
                        "master_hinted_literals": 0,
                    },
                    used_exact_core_reuse=True,
                    core_build_seconds=core_build_seconds,
                    overlay_build_seconds=0.0,
                    ghost_constraint_seconds=0.0,
                    cut_replay_seconds=0.0,
                ),
                [],
                loaded_exact_safe_cut_count=0,
                generated_exact_safe_cut_count=0,
            )
            return RUN_STATUS_UNPROVEN, None
    else:
        instances, facility_pools, rules = load_project_data(project_root, solve_mode=solve_mode)

    grid = dict(rules["globals"]["grid"])
    grid_area = int(grid["width"]) * int(grid["height"])
    static_area_lower_bound = compute_mandatory_area_lower_bound(instances, rules)
    if solve_mode == "certified_exact" and exact_session is not None:
        static_area_lower_bound = compute_exact_static_area_lower_bound(
            instances,
            rules,
            exact_session.core.generic_io_requirements,
        )
    if static_area_lower_bound + int(ghost_w) * int(ghost_h) > grid_area:
        _publish_last_run_metadata(
            _merge_reuse_metadata(
                {
                    "mode": solve_mode,
                    "master_status": "AREA_PRECHECK_FAILED",
                    "enumerated_bindings": 0,
                    "routing_attempts": 0,
                    "diagnostic_flow_status": "NOT_RUN",
                    "used_greedy_hint": False,
                    "greedy_hint_instances": 0,
                    "master_hinted_literals": 0,
                },
                used_exact_core_reuse=bool(solve_mode == "certified_exact"),
                core_build_seconds=core_build_seconds,
                overlay_build_seconds=0.0,
                ghost_constraint_seconds=0.0,
                cut_replay_seconds=0.0,
            ),
            [],
            loaded_exact_safe_cut_count=0,
            generated_exact_safe_cut_count=0,
        )
        return RUN_STATUS_INFEASIBLE, None

    loaded_exact_safe_cuts: List[BendersCut] = []

    if solve_mode == "certified_exact":
        if exact_session is None:
            raise RuntimeError("Exact exact_session should have been initialized")
        _emit_campaign_heartbeat(
            {
                "stage": "pre_master_precheck",
                "event": "start",
                "master_search_profile": str(master_search_profile),
                "disable_master_warm_start": bool(disable_master_warm_start),
            }
        )
        pre_master_precheck = evaluate_exact_candidate_pre_master_precheck(
            ghost_w=int(ghost_w),
            ghost_h=int(ghost_h),
            exact_session=exact_session,
            master_search_profile=str(master_search_profile),
        )
        boundary_port_precheck = dict(
            pre_master_precheck.get(
                "boundary_port_precheck",
                MasterPlacementModel._default_exact_candidate_boundary_port_feasibility_payload(),
            )
        )
        if bool(pre_master_precheck.get("triggered", False)):
            proof_summary = dict(pre_master_precheck.get("proof_summary", {}))
            _publish_last_run_metadata(
                proof_summary,
                loaded_exact_safe_cuts,
                loaded_exact_safe_cut_count=len(loaded_exact_safe_cuts),
                generated_exact_safe_cut_count=0,
            )
            return RUN_STATUS_INFEASIBLE, None
    cut_manager = CutManager(
        checkpoint_dir=project_root / "data" / "checkpoints",
        solve_mode=solve_mode,
        current_hashes=artifact_hashes,
    )
    if solve_mode == "certified_exact":
        if exact_session is None:
            raise RuntimeError("Exact exact_session should have been initialized")
        _emit_campaign_heartbeat(
            {
                "stage": "master_overlay_build",
                "event": "start",
                "master_search_profile": str(master_search_profile),
                "disable_master_warm_start": bool(disable_master_warm_start),
            }
        )
        overlay_started = time.perf_counter()
        ghost_anchor_filter_override = _resolve_ghost_anchor_filter_from_env()
        # B1 Phase 3: env on 时跳过 from_exact_core 的 proto-sharing (那是 coordinate-
        # specific), 走 direct instantiation. PoseBool delegate build 23s, 不需要
        # 跨 candidate 共享 proto.
        _use_pose_bool = os.environ.get(
            "EXACT_USE_POSE_BOOL_MASTER", ""
        ).strip().lower() in {"1", "true", "yes", "on"}
        if _use_pose_bool:
            # B1 Phase 3 fix: build_exact_core 不传 exact_required_pose_optional_counts,
            # 所以 session.core 那个 = empty dict. 走 PoseBool delegate 需要 inferred
            # counts 才能正确 build protocol_storage_box ro_vars. 不修这条 binding 会
            # 系统性 INFEASIBLE (master 不出 storage box).
            from src.models.master_model import infer_exact_required_pose_optional_counts
            _inferred_counts = infer_exact_required_pose_optional_counts(
                exact_session.core.rules, exact_session.core.generic_io_requirements
            )
            master = MasterPlacementModel(
                list(exact_session.core.source_instances),
                cast("Mapping[str, List[Dict[str, Any]]]", exact_session.core.facility_pools),
                exact_session.core.rules,
                ghost_rect=(int(ghost_w), int(ghost_h)),
                skip_power_coverage=bool(exact_session.core.skip_power_coverage),
                enable_symmetry_breaking=bool(exact_session.core.enable_symmetry_breaking),
                generic_io_requirements=exact_session.core.generic_io_requirements,
                exact_required_pose_optional_counts=_inferred_counts,
                solve_mode="certified_exact",
                master_search_profile=master_search_profile,
                ghost_anchor_filter=ghost_anchor_filter_override,
            )
            master.set_hint_persistence_context(project_root, candidate_key)
            master.build()
            overlay_build_seconds = time.perf_counter() - overlay_started
            ghost_constraint_seconds = 0.0
        else:
            master = MasterPlacementModel.from_exact_core(
                exact_session.core,
                ghost_rect=(int(ghost_w), int(ghost_h)),
                master_search_profile=master_search_profile,
                precomputed_boundary_port_feasibility=boundary_port_precheck,
                ghost_anchor_filter=ghost_anchor_filter_override,
            )
            # audit A H1 修复: from_exact_core 路径也需要 hint persistence context.
            # 修前只 else 分支 (4823 line) 调, 168h 4 worker exact_core_reuse 主路径
            # 漏配 → 即使 EXACT_MASTER_HINT_PERSISTENCE=1 也跑不到 load/save.
            # 配合 H3 repair_hint=True 让跨 wave hint 修补真正生效.
            master.set_hint_persistence_context(project_root, candidate_key)
            reuse_stats = dict(master.build_stats.get("exact_core_reuse", {}))
            overlay_build_seconds = float(
                reuse_stats.get("overlay_build_seconds", time.perf_counter() - overlay_started)
            )
            ghost_constraint_seconds = float(
                reuse_stats.get("ghost_constraint_seconds", 0.0)
            )
        used_exact_core_reuse = True
        _emit_campaign_heartbeat(
            {
                "stage": "master_overlay_build",
                "event": "complete",
                "master_search_profile": str(master_search_profile),
                "disable_master_warm_start": bool(disable_master_warm_start),
                "overlay_build_seconds": float(overlay_build_seconds),
                "ghost_constraint_seconds": float(ghost_constraint_seconds),
            }
        )
    else:
        master = MasterPlacementModel(
            instances,
            facility_pools,
            rules,
            ghost_rect=(int(ghost_w), int(ghost_h)),
            solve_mode=solve_mode,
            master_search_profile=master_search_profile,
        )
        # P1 #7 main #1+#2: 配 hint 跨 wave 持久化 context. master.build/solve
        # 自动钩子 (受 EXACT_MASTER_HINT_PERSISTENCE env 开关控制, default off).
        master.set_hint_persistence_context(project_root, candidate_key)
        master.build()

    cut_replay_started = time.perf_counter()
    raw_candidate_cuts: Sequence[Mapping[str, Any]] = []
    cut_replay_condition_skipped = 0
    if solve_mode == "certified_exact":
        if preloaded_exact_safe_cuts is not None:
            raw_candidate_cuts = list(preloaded_exact_safe_cuts)
        elif isinstance(campaign, ExactCampaign):
            raw_candidate_cuts = campaign.get_candidate_cuts(int(ghost_w), int(ghost_h))
    if solve_mode == "certified_exact":
        for raw_cut in raw_candidate_cuts:
            try:
                cut = BendersCut.from_dict(raw_cut)
            except Exception:
                continue
            blockers = collect_certification_blockers(
                solve_mode=solve_mode,
                loaded_cuts=[cut],
                current_hashes=artifact_hashes,
            )
            if blockers:
                continue
            # GPT v4 P0 #1 fix: condition_set 必须 resolve 回 u_var 再传 master,
            # 否则 conditioned cut replay 成 unconditional → 过切 ghost B 合法解.
            # 不可解析 (未知 key / anchor 不匹配) → certified mode 下 fail-closed
            # skip cut, 不退化为无条件.
            resolved_lits, condition_ok = _resolve_condition_lits_from_condition_set(
                master, cut.condition_set
            )
            if not condition_ok:
                cut_replay_condition_skipped += 1
                continue
            if cut_manager.register_structured_cut(cut):
                loaded_exact_safe_cuts.append(cut)
                master.add_benders_cut(
                    {str(k): int(v) for k, v in cut.conflict_set.items()},
                    condition_lits=tuple(resolved_lits),
                )
    cut_replay_seconds = time.perf_counter() - cut_replay_started

    if solve_mode == "certified_exact":
        _emit_campaign_heartbeat(
            {
                "stage": "pre_master_diagnostics",
                "event": "start",
                "master_search_profile": str(master_search_profile),
                "disable_master_warm_start": bool(disable_master_warm_start),
            }
        )
        _emit_campaign_heartbeat(
            {
                "stage": "mandatory_support_diagnostics",
                "event": "start",
                "master_search_profile": str(master_search_profile),
            }
        )
        mandatory_support_diagnostics = (
            master.evaluate_exact_candidate_mandatory_support_diagnostics()
        )
        mandatory_support_diagnostics_summary = (
            _compact_exact_candidate_mandatory_support_diagnostics(
                mandatory_support_diagnostics
            )
        )
        _emit_campaign_heartbeat(
            {
                "stage": "mandatory_support_diagnostics",
                "event": "complete",
                "unsupported_group_count": int(
                    mandatory_support_diagnostics_summary.get(
                        "unsupported_group_count",
                        0,
                    )
                ),
                "empty_candidate_pool_group_count": int(
                    mandatory_support_diagnostics_summary.get(
                        "empty_candidate_pool_group_count",
                        0,
                    )
                ),
                "group_count": len(
                    list(mandatory_support_diagnostics_summary.get("groups", []))
                ),
            }
        )
        _emit_campaign_heartbeat(
            {
                "stage": "boundary_port_precheck",
                "event": "start",
                "master_search_profile": str(master_search_profile),
            }
        )
        boundary_port_precheck = master.evaluate_exact_candidate_boundary_port_feasibility()
        _emit_campaign_heartbeat(
            {
                "stage": "boundary_port_precheck",
                "event": "complete",
                "supported": bool(boundary_port_precheck.get("supported", False)),
                "skipped_due_to_anchor_limit": bool(
                    boundary_port_precheck.get("skipped_due_to_anchor_limit", False)
                ),
                "considered_anchor_count": int(
                    boundary_port_precheck.get("considered_anchor_count", 0)
                ),
                "screen_pass_anchor_count": int(
                    boundary_port_precheck.get("screen_pass_anchor_count", 0)
                ),
                "screened_infeasible_anchor_count": int(
                    boundary_port_precheck.get("screened_infeasible_anchor_count", 0)
                ),
            }
        )
        boundary_pass_anchor_indices = tuple(
            int(idx)
            for idx in boundary_port_precheck.get("screen_pass_anchor_indices", ())
        )
        if bool(boundary_port_precheck.get("supported", False)) and boundary_pass_anchor_indices:
            _emit_campaign_heartbeat(
                {
                    "stage": "mandatory_rectangle_precheck",
                    "event": "start",
                    "upstream_anchor_filter_count": int(
                        len(boundary_pass_anchor_indices)
                    ),
                }
            )
            mandatory_group_prechecks = (
                master.evaluate_exact_candidate_mandatory_rectangle_prechecks(
                    anchor_indices=boundary_pass_anchor_indices
                )
            )
        else:
            mandatory_group_prechecks = {
                "evaluated": False,
                "skipped_due_to_upstream_precheck": False,
                "upstream_anchor_filter_count": 0,
                "supported_group_count": 0,
                "groups": [],
                "rebuild_anchor_indices": tuple(),
            }
        mandatory_group_precheck_summary = _compact_exact_candidate_mandatory_group_prechecks(
            mandatory_group_prechecks
        )
        _emit_campaign_heartbeat(
            {
                "stage": "mandatory_rectangle_precheck",
                "event": "complete",
                "evaluated": bool(mandatory_group_precheck_summary.get("evaluated", False)),
                "skipped_due_to_upstream_precheck": bool(
                    mandatory_group_precheck_summary.get(
                        "skipped_due_to_upstream_precheck",
                        False,
                    )
                ),
                "upstream_anchor_filter_count": int(
                    mandatory_group_precheck_summary.get(
                        "upstream_anchor_filter_count",
                        0,
                    )
                ),
                "supported_group_count": int(
                    mandatory_group_precheck_summary.get(
                        "supported_group_count",
                        0,
                    )
                ),
                "group_count": len(
                    list(mandatory_group_precheck_summary.get("groups", []))
                ),
            }
        )
        # B1 Phase 3: env on 时 skip mandatory_rectangle_precheck trigger. 那个
        # precheck 是 coordinate-only screen (假设 master 用 (x,y,mode) IntVar 形式
        # 验 packing-within-rect feasibility). pose-bool master 自己的 cell
        # exclusivity + power coverage 已经覆盖, 这里 precheck 误判 INFEASIBLE.
        triggered_mandatory_group = next(
            (
                dict(entry)
                for entry in list(mandatory_group_prechecks.get("groups", []))
                if bool(entry.get("supported", False))
                and int(entry.get("considered_anchor_count", 0)) > 0
                and int(entry.get("screen_pass_anchor_count", 0)) == 0
                and int(entry.get("screened_infeasible_anchor_count", 0))
                == int(entry.get("considered_anchor_count", 0))
                and int(entry.get("unsupported_anchor_count", 0)) == 0
            ),
            None,
        )
        if triggered_mandatory_group is not None and not _use_pose_bool:
            proof_summary = _merge_reuse_metadata(
                {
                    "mode": "certified_exact",
                    "benders_iterations": 0,
                    "master_status": "INFEASIBLE",
                    "diagnostic_flow_status": "NOT_RUN",
                    "enumerated_bindings": 0,
                    "routing_attempts": 0,
                    "used_greedy_hint": False,
                    "greedy_hint_instances": 0,
                    "master_hinted_literals": 0,
                    "master_search_profile": str(master_search_profile),
                    "master_boundary_port_feasibility": _compact_exact_candidate_boundary_port_feasibility(
                        boundary_port_precheck
                    ),
                    "master_mandatory_group_prechecks": dict(
                        mandatory_group_precheck_summary
                    ),
                    "master_mandatory_support_diagnostics": dict(
                        mandatory_support_diagnostics_summary
                    ),
                    "master_candidate_precheck": {
                        "triggered": True,
                        "precheck_reason": "mandatory_rect_group_all_anchors_infeasible",
                        "master_solve_skipped": True,
                        "supported": bool(triggered_mandatory_group.get("supported", False)),
                        "considered_anchor_count": int(
                            triggered_mandatory_group.get("considered_anchor_count", 0)
                        ),
                        "screened_infeasible_anchor_count": int(
                            triggered_mandatory_group.get(
                                "screened_infeasible_anchor_count",
                                0,
                            )
                        ),
                        "screen_pass_anchor_count": int(
                            triggered_mandatory_group.get("screen_pass_anchor_count", 0)
                        ),
                        "max_packable_min": triggered_mandatory_group.get(
                            "max_packable_min"
                        ),
                        "max_packable_max": triggered_mandatory_group.get(
                            "max_packable_max"
                        ),
                        "first_infeasible_anchor_idx": triggered_mandatory_group.get(
                            "first_infeasible_anchor_idx"
                        ),
                        "first_infeasible_anchor_max_packable": triggered_mandatory_group.get(
                            "first_infeasible_anchor_max_packable"
                        ),
                        "triggered_group_id": triggered_mandatory_group.get(
                            "group_id"
                        ),
                        "triggered_group_facility_type": triggered_mandatory_group.get(
                            "facility_type"
                        ),
                        "triggered_group_operation_type": triggered_mandatory_group.get(
                            "operation_type"
                        ),
                        "triggered_group_required_count": int(
                            triggered_mandatory_group.get("required_count", 0)
                        ),
                    },
                },
                used_exact_core_reuse=used_exact_core_reuse,
                core_build_seconds=core_build_seconds,
                overlay_build_seconds=overlay_build_seconds,
                ghost_constraint_seconds=ghost_constraint_seconds,
                cut_replay_seconds=cut_replay_seconds,
            )
            _publish_last_run_metadata(
                proof_summary,
                loaded_exact_safe_cuts,
                loaded_exact_safe_cut_count=len(loaded_exact_safe_cuts),
                generated_exact_safe_cut_count=0,
            )
            return RUN_STATUS_INFEASIBLE, None

    controller = LBBDController(
        master,
        cut_manager,
        project_root=project_root,
        solve_mode=solve_mode,
        max_iterations=max_iterations,
        master_seconds=master_seconds,
        binding_seconds=binding_seconds,
        routing_seconds=routing_seconds,
        flow_seconds=flow_seconds,
        artifact_hashes=artifact_hashes,
        loaded_exact_safe_cuts=loaded_exact_safe_cuts,
        heartbeat_callback=_emit_campaign_heartbeat
        if solve_mode == "certified_exact"
        else None,
        disable_master_warm_start=bool(disable_master_warm_start),
    )
    # P1 #7 main: 把 outer_search 算的 ε 阶段 (25h prep / 50h refine / 93h cert) tag 给
    # controller, 影响新生成的 BendersCut.epsilon_stage 字段; 配合 P1
    # #7b prep 的 cut_manager.cuts_for_stage 实现 ε 阶段跨 wave bucketing.
    controller.set_epsilon_stage(epsilon_stage)
    if solve_mode == "certified_exact":
        pre_master_proof_summary = dict(pre_master_precheck.get("proof_summary", {}))
        reused_advisory = _copy_anchor119_row_domain_guard_advisory_from_proof_summary(
            controller._master_candidate_precheck,
            proof_summary=pre_master_proof_summary,
        )
        if not reused_advisory:
            _maybe_attach_anchor119_row_domain_guard_advisory(
                controller._master_candidate_precheck,
                project_root=project_root,
                ghost_w=int(ghost_w),
                ghost_h=int(ghost_h),
            )
    status, solution = controller.run_with_status()
    binding_summary = dict(controller.last_proof_summary.get("binding_summary", {}))
    proof_summary = _merge_reuse_metadata(
        {
            **dict(controller.last_proof_summary),
            **controller._master_search_summary(),
            "binding_search_profile": str(
                binding_summary.get(
                    "search_profile",
                    dict(binding_summary.get("search_guidance", {})).get(
                        "profile",
                        "exact_binding_guided_branching_v1",
                    ),
                )
            ),
            **controller._routing_shrink_summary(),
        },
        used_exact_core_reuse=used_exact_core_reuse,
        core_build_seconds=core_build_seconds,
        overlay_build_seconds=overlay_build_seconds,
        ghost_constraint_seconds=ghost_constraint_seconds,
        cut_replay_seconds=cut_replay_seconds,
    )
    _publish_last_run_metadata(
        proof_summary,
        [*loaded_exact_safe_cuts, *controller.generated_exact_safe_cuts],
        loaded_exact_safe_cut_count=len(loaded_exact_safe_cuts),
        generated_exact_safe_cut_count=len(controller.generated_exact_safe_cuts),
    )
    return status, solution


run_benders_for_ghost_rect.last_run_metadata = {  # type: ignore[attr-defined]
    "proof_summary": {},
    "exact_safe_cuts": [],
    "loaded_exact_safe_cut_count": 0,
    "generated_exact_safe_cut_count": 0,
    "fine_grained_exact_safe_cut_count": 0,
    "binding_domain_empty_cut_count": 0,
    "routing_front_blocked_cut_count": 0,
    "routing_precheck_rejections": 0,
    "routing_precheck_statuses": [],
    "routing_domain_cells": 0,
    "routing_terminal_core_cells": 0,
    "routing_state_space_vars": 0,
    "routing_local_pattern_pruned_states": 0,
    "used_routing_core_reuse": False,
    "routing_core_build_seconds": 0.0,
    "routing_overlay_build_seconds": 0.0,
    "binding_domain_cache_hits": 0,
    "binding_domain_cache_misses": 0,
    "binding_domain_reused_instances": [],
    "master_search_profile": "default_automatic",
    "power_pole_family_order": [],
    "power_pole_family_count_literals": 0,
    "residual_optional_family_guided": False,
    "binding_search_profile": "exact_binding_guided_branching_v1",
    "diagnostic_flow_status": "NOT_RUN",
    "master_status": None,
    "binding_status": None,
    "routing_status": None,
    "mode": None,
    "used_exact_core_reuse": False,
    "core_build_seconds": 0.0,
    "overlay_build_seconds": 0.0,
    "ghost_constraint_seconds": 0.0,
    "cut_replay_seconds": 0.0,
    "master_representation": "pose_bool_v1",
    "master_slot_counts": {},
    "master_mode_literals": 0,
    "master_interval_count": 0,
    "master_pose_bool_literals": 0,
    "master_domain_encoding": "",
    "master_domain_table_rows": 0,
    "master_mode_rect_domains": {},
    "power_pole_shell_lookup_pairs": {},
    "power_coverage_representation": "",
    "power_coverage_encoding": "",
    "power_coverage_powered_slots": 0,
    "power_coverage_pole_slots": 0,
    "power_coverage_cover_literals": 0,
    "power_coverage_witness_indices": 0,
    "power_coverage_element_constraints": 0,
    "power_coverage_radius": 0,
    "power_capacity_shell_pairs": 0,
    "power_capacity_shell_pair_evaluations": 0,
    "power_capacity_signature_classes": 0,
    "power_capacity_signature_class_evaluations": 0,
    "power_capacity_raw_pole_evaluations": 0,
    "signature_bucket_cache_hits": 0,
    "signature_bucket_cache_misses": 0,
    "signature_bucket_distinct_keys": 0,
    "geometry_cache_templates": 0,
}
