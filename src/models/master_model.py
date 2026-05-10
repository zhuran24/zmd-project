"""
Master Placement Model（主摆放模型）.

设计目标：
1. certified_exact（严格认证精确）与 exploratory（探索）两条路径严格分离。
2. 严格精确路径只读取 mandatory exact（必选精确）实例，
   可选设施通过 pose-level optional variables（位姿级可选变量）直接建模；
   不再把 50 / 10 之类经验上限写成正式约束。
3. exploratory（探索）路径可以继续对位姿级可选设施施加经验上限。
4. extract_solution()（提取解）为位姿级可选设施生成可持久化识别的完整实例条目。
5. 集成 Benders 切平面反馈（Cuts），支持外部的 conflict set 并打回重摆。
"""

from __future__ import annotations

import copy
import json
import math
import os
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Collection, DefaultDict, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from ortools.sat.python import cp_model

from src.models.cp_sat_worker_config import (
    DEFAULT_LOCAL_CAPACITY_CP_SAT_WORKERS,
    DEFAULT_MASTER_CP_SAT_WORKERS,
    apply_master_cp_sat_strong_disjunctive_propagation,
    apply_master_cp_sat_subsolver_filter,
    resolve_cp_sat_worker_count,
)
from src.models._cpsat_compat import cp_model_from_proto, search_branching_name
from src.models.exact_coordinate_master import (
    CoordinateExactMasterDelegate,
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    normalize_exact_coordinate_master_search_profile,
    resolve_ghost_signature_bucket_residual_overlay_instrumentation_enabled,
)
from src.preprocess.operation_profiles import get_operation_port_profile

ModeToken = Tuple[str, str]
POSE_LEVEL_OPTIONAL_TEMPLATES = {"power_pole", "protocol_storage_box"}
POSE_LEVEL_OPTIONAL_OPERATIONS = {
    "power_pole": "power_supply",
    "protocol_storage_box": "wireless_sink",
}
DIR_DELTA = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
BOUNDARY_STORAGE_PORT_SCREEN_GROUP_ID = "group::boundary_storage_port::boundary_io::0"
EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS = 64
EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS = 64
EXACT_MANDATORY_RECTANGLE_PRECHECK_TIME_BUDGET_SECONDS = 0.0
EXACT_MANDATORY_RECTANGLE_PRECHECK_WITNESS_MIN_SURVIVORS = 128
EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS = 2.0
EXACT_GHOST_AWARE_COORDINATE_VALIDATION_SECONDS = 2.0
EXACT_GHOST_AWARE_COORDINATE_VALIDATION_MAX_ANCHORS = 8
EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV = (
    "EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS"
)
EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS_ENV = (
    "EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS"
)
EXACT_MANDATORY_RECTANGLE_PRECHECK_TIME_BUDGET_SECONDS_ENV = (
    "EXACT_MANDATORY_RECTANGLE_PRECHECK_TIME_BUDGET_SECONDS"
)
EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS_ENV = (
    "EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS"
)
EXACT_GHOST_AWARE_COORDINATE_VALIDATION_SECONDS_ENV = (
    "EXACT_GHOST_AWARE_COORDINATE_VALIDATION_SECONDS"
)
EXACT_GHOST_AWARE_COORDINATE_VALIDATION_MAX_ANCHORS_ENV = (
    "EXACT_GHOST_AWARE_COORDINATE_VALIDATION_MAX_ANCHORS"
)
EXACT_SIGNATURE_MONOTONIC_FORCED_LABEL_PRECHECK_ENV = (
    "EXACT_SIGNATURE_MONOTONIC_FORCED_LABEL_PRECHECK"
)
EXACT_GHOST_Y_OVERLAP_FORCED_LABEL_PRECHECK_ENV = (
    "EXACT_GHOST_Y_OVERLAP_FORCED_LABEL_PRECHECK"
)
EXACT_GHOST_OVERLAP_FORCED_DOMAIN_PRECHECK_ENV = (
    "EXACT_GHOST_OVERLAP_FORCED_DOMAIN_PRECHECK"
)
EXACT_SAME_X_STRIP_FIXED_GHOST_CAPACITY_PRECHECK_ENV = (
    "EXACT_SAME_X_STRIP_FIXED_GHOST_CAPACITY_PRECHECK"
)
EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT = 8
EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT_ENV = (
    "EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT"
)
EXACT_MASTER_SEARCH_BRANCHING_ENV = "EXACT_MASTER_SEARCH_BRANCHING"
EXACT_MASTER_CP_MODEL_PRESOLVE_ENV = "EXACT_MASTER_CP_MODEL_PRESOLVE"
EXACT_MASTER_CP_MODEL_PROBING_LEVEL_ENV = "EXACT_MASTER_CP_MODEL_PROBING_LEVEL"
EXACT_MASTER_SYMMETRY_LEVEL_ENV = "EXACT_MASTER_SYMMETRY_LEVEL"
EXACT_MASTER_HINT_CONFLICT_LIMIT_ENV = "EXACT_MASTER_HINT_CONFLICT_LIMIT"
# P1 #7c prep: 让 master CpSolver 在 response 里返回 worker 收紧后的变量域。
# 这是 CP-SAT 公开的唯一"跨 solve 传 dual 信息"通道，给 ε-Certified 三阶
# 段下一波用作初始域上界。default=True (启用); env "0/false/no/off" 关闭。
EXACT_MASTER_FILL_TIGHTENED_DOMAINS_ENV = "EXACT_MASTER_FILL_TIGHTENED_DOMAINS"
EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION_ENV = (
    "EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION"
)
EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION_TRUE_VALUES = {
    "1",
    "true",
    "on",
}
EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION_FALSE_VALUES = {
    "",
    "0",
    "false",
    "off",
    "no",
}
EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION_ENV = (
    "EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION"
)
EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION_TRUE_VALUES = {
    "1",
    "true",
    "on",
}
EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION_FALSE_VALUES = {
    "",
    "0",
    "false",
    "off",
    "no",
}
EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV = (
    "EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION"
)
EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_TRUE_VALUES = {
    "1",
    "true",
    "on",
}
EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_FALSE_VALUES = {
    "",
    "0",
    "false",
    "off",
    "no",
}
EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_ENV = (
    "EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION"
)
EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_TRUE_VALUES = {
    "1",
    "true",
    "on",
}
EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_FALSE_VALUES = {
    "",
    "0",
    "false",
    "off",
    "no",
}
EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION_ENV = (
    "EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION"
)
EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION_TRUE_VALUES = {
    "1",
    "true",
    "on",
}
EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION_FALSE_VALUES = {
    "",
    "0",
    "false",
    "off",
    "no",
}
EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_DETAIL_INSTRUMENTATION_ENV = (
    "EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_DETAIL_INSTRUMENTATION"
)
EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_DETAIL_INSTRUMENTATION_TRUE_VALUES = {
    "1",
    "true",
    "on",
}
EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_DETAIL_INSTRUMENTATION_FALSE_VALUES = {
    "",
    "0",
    "false",
    "off",
    "no",
}
LocalPoseShape = Tuple[Tuple[int, int], ...]
PoseLocalSignature = Tuple[LocalPoseShape, LocalPoseShape, LocalPoseShape, int]
LocalCapacitySignature = Tuple[LocalPoseShape, ...]
CompactLocalCapacityItem = Tuple[int, int, int]
CompactLocalCapacitySignature = Tuple[CompactLocalCapacityItem, ...]
NormalizedRectangleSignature = Tuple[Tuple[int, int, int, int], ...]
ShellPair = Tuple[int, int]


def evaluate_same_x_strip_fixed_ghost_capacity_conflict(
    owner: Any,
    *,
    solution_hint: Mapping[str, int],
    ghost_anchor_hint_idx: Optional[int],
    force_fields: Sequence[str] = ("x", "y", "mode"),
    force_equality_keys: Optional[Collection[str]] = None,
) -> Dict[str, Any]:
    """Conservative pre-solver certificate for fixed-ghost same-x strip overloads."""

    try:
        forced_fields = {str(field) for field in force_fields}
        if "x" not in forced_fields:
            return _same_x_capacity_skip("x_not_forced")
        if ghost_anchor_hint_idx is None:
            return _same_x_capacity_skip("ghost_anchor_hint_unavailable")
        delegate = getattr(owner, "_coordinate_delegate", None)
        if delegate is None:
            return _same_x_capacity_skip("coordinate_delegate_unavailable")
        ghost_rect = tuple(int(v) for v in (getattr(owner, "ghost_rect", None) or ()))
        if len(ghost_rect) != 2:
            return _same_x_capacity_skip("ghost_rect_unavailable")
        ghost_w, ghost_h = int(ghost_rect[0]), int(ghost_rect[1])
        if ghost_w <= 0 or ghost_h <= 0:
            return _same_x_capacity_skip("ghost_rect_invalid")
        ghost_domains = list(getattr(owner, "_ghost_domains", []))
        anchor_idx = int(ghost_anchor_hint_idx)
        if not (0 <= anchor_idx < len(ghost_domains)):
            return _same_x_capacity_skip("ghost_anchor_domain_unavailable")
        domain = ghost_domains[anchor_idx]
        anchor = dict(domain.get("anchor", {})) if isinstance(domain, Mapping) else {}
        if "x" not in anchor or "y" not in anchor:
            return _same_x_capacity_skip("ghost_anchor_missing_xy")
        ghost_x, ghost_y = int(anchor["x"]), int(anchor["y"])
        grid_w, grid_h = int(getattr(owner, "grid_w", 0)), int(getattr(owner, "grid_h", 0))
        if grid_w <= 0 or grid_h <= 0:
            return _same_x_capacity_skip("grid_unavailable")
        if ghost_x < 0 or ghost_y < 0 or ghost_x + ghost_w > grid_w or ghost_y + ghost_h > grid_h:
            return _same_x_capacity_skip("ghost_outside_grid")

        selected_keys = (
            None
            if force_equality_keys is None
            else {str(key) for key in force_equality_keys}
        )
        grouped_hints: DefaultDict[str, List[int]] = defaultdict(list)
        optional_hints: DefaultDict[str, List[int]] = defaultdict(list)
        for solution_id, pose_idx in dict(solution_hint or {}).items():
            solution_id = str(solution_id)
            pose_idx = int(pose_idx)
            group_by_instance = getattr(owner, "_group_id_by_instance", {})
            if solution_id in group_by_instance:
                grouped_hints[str(group_by_instance[solution_id])].append(pose_idx)
                continue
            infer_optional = getattr(owner, "_infer_optional_template_from_solution_id", None)
            tpl = infer_optional(solution_id) if callable(infer_optional) else None
            if tpl is not None:
                optional_hints[str(tpl)].append(pose_idx)

        buckets: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
        skipped_slots: List[Dict[str, Any]] = []
        force_labels: List[Dict[str, Any]] = []

        def _pose_sort_key(tpl: str, pose_idx: int) -> Any:
            sorter = getattr(owner, "_pose_sort_key", None)
            if callable(sorter):
                return sorter(str(tpl), int(pose_idx))
            return int(pose_idx)

        def _record_slot(
            *,
            slot: Any,
            tpl: str,
            pose_idx: int,
            group_id: str,
            solution_id: str,
            slot_key: str,
            slot_index: int,
        ) -> None:
            pose_tuple = getattr(delegate, "_template_pose_tuple_by_idx", {}).get(str(tpl), {}).get(int(pose_idx))
            if pose_tuple is None:
                skipped_slots.append(
                    {
                        "reason": "missing_pose_tuple",
                        "group_id": str(group_id),
                        "slot_index": int(slot_index),
                        "pose_index": int(pose_idx),
                    }
                )
                return
            x_val, _y_val, _mode_id = pose_tuple
            stable_key = _same_x_capacity_stable_key(
                group_id=str(group_id),
                solution_id=str(solution_id),
                slot_key=str(slot_key),
                slot_index=int(slot_index),
                pose_idx=int(pose_idx),
                field="x",
            )
            selected = selected_keys is None or stable_key in selected_keys
            label = {
                "stable_key": stable_key,
                "group_id": str(group_id),
                "solution_id": str(solution_id),
                "slot_key": str(slot_key),
                "slot_index": int(slot_index),
                "template": str(tpl),
                "pose_index": int(pose_idx),
                "field": "x",
                "forced_value": int(x_val),
                "selected": bool(selected),
            }
            force_labels.append(dict(label))
            if not selected:
                return
            dims = tuple(getattr(slot, "dims", ()) or ())
            if len(dims) != 2:
                skipped_slots.append({**label, "reason": "slot_dims_unavailable"})
                return
            slot_w, slot_h = int(dims[0]), int(dims[1])
            if slot_w <= 0 or slot_h <= 0:
                skipped_slots.append({**label, "reason": "slot_dims_invalid"})
                return
            x_start = int(x_val)
            x_end = int(x_start + slot_w)
            if not _same_x_capacity_intervals_overlap(x_start, x_end, ghost_x, ghost_x + ghost_w):
                return
            bucket_key = (str(group_id), int(x_start), int(x_end))
            bucket = buckets.setdefault(
                bucket_key,
                {
                    "group_id": str(group_id),
                    "x_interval": {"start": int(x_start), "end": int(x_end)},
                    "slot_heights": set(),
                    "forced_slots": [],
                },
            )
            bucket["slot_heights"].add(int(slot_h))
            bucket["forced_slots"].append(dict(label) | {"slot_width": int(slot_w), "slot_height": int(slot_h)})

        for group in list(getattr(owner, "_mandatory_groups", [])):
            group_id = str(group["group_id"])
            tpl = str(group["facility_type"])
            slot_specs = list(getattr(delegate, "mandatory_slots", {}).get(group_id, []))
            solution_ids = [str(item) for item in list(group.get("instance_ids", []))]
            pose_indices = sorted(grouped_hints.get(group_id, []), key=lambda pose_idx: _pose_sort_key(tpl, int(pose_idx)))
            for slot_index, (slot, pose_idx) in enumerate(zip(slot_specs, pose_indices)):
                solution_id = (
                    solution_ids[int(slot_index)]
                    if int(slot_index) < len(solution_ids)
                    else f"{group_id}::{slot_index}"
                )
                _record_slot(
                    slot=slot,
                    tpl=tpl,
                    pose_idx=int(pose_idx),
                    group_id=group_id,
                    solution_id=solution_id,
                    slot_key=str(slot_index),
                    slot_index=int(slot_index),
                )

        for tpl, slot_specs in getattr(delegate, "required_optional_slots", {}).items():
            pose_indices = sorted(optional_hints.get(str(tpl), []), key=lambda pose_idx: _pose_sort_key(str(tpl), int(pose_idx)))
            for slot_index, (slot, pose_idx) in enumerate(zip(list(slot_specs), pose_indices)):
                _record_slot(
                    slot=slot,
                    tpl=str(tpl),
                    pose_idx=int(pose_idx),
                    group_id=f"optional::{tpl}",
                    solution_id=f"optional::{tpl}::{slot_index}",
                    slot_key=str(slot_index),
                    slot_index=int(slot_index),
                )

        evaluated_buckets: List[Dict[str, Any]] = []
        skipped_buckets: List[Dict[str, Any]] = []
        first_conflict: Optional[Dict[str, Any]] = None
        for raw_bucket in buckets.values():
            heights = sorted(int(h) for h in raw_bucket.get("slot_heights", set()))
            forced_slots = list(raw_bucket.get("forced_slots", []))
            if len(heights) != 1:
                skipped_buckets.append(
                    {
                        "group_id": raw_bucket.get("group_id"),
                        "x_interval": dict(raw_bucket.get("x_interval", {})),
                        "reason": "mixed_slot_heights",
                        "slot_heights": heights,
                        "forced_count": int(len(forced_slots)),
                    }
                )
                continue
            slot_h = int(heights[0])
            lower_capacity = max(0, int(ghost_y)) // slot_h
            upper_capacity = max(0, int(grid_h) - int(ghost_y + ghost_h)) // slot_h
            capacity = int(lower_capacity + upper_capacity)
            forced_count = int(len(forced_slots))
            bucket_payload = {
                "group_id": raw_bucket.get("group_id"),
                "x_interval": dict(raw_bucket.get("x_interval", {})),
                "slot_height": int(slot_h),
                "forced_count": int(forced_count),
                "capacity": int(capacity),
                "lower_capacity": int(lower_capacity),
                "upper_capacity": int(upper_capacity),
                "conflict": bool(forced_count > capacity),
                "forced_slots": forced_slots,
                "y_capacity_source": "grid_bounds_conservative",
            }
            evaluated_buckets.append(bucket_payload)
            if first_conflict is None and bool(bucket_payload["conflict"]):
                first_conflict = dict(bucket_payload)

        payload = {
            "evaluated": True,
            "conflict": first_conflict is not None,
            "reason": (
                "same_x_strip_fixed_ghost_capacity_conflict"
                if first_conflict is not None
                else "no_conflicting_same_x_bucket"
            ),
            "anchor_idx": int(anchor_idx),
            "ghost_rect": {
                "x": int(ghost_x),
                "y": int(ghost_y),
                "w": int(ghost_w),
                "h": int(ghost_h),
            },
            "grid": {"w": int(grid_w), "h": int(grid_h)},
            "bucket_count": int(len(evaluated_buckets)),
            "buckets": evaluated_buckets,
            "skipped_buckets": skipped_buckets,
            "skipped_slots": skipped_slots[:16],
            "force_equality_filter_active": selected_keys is not None,
            "force_equality_labels": force_labels,
        }
        if first_conflict is not None:
            payload["first_conflict_bucket"] = dict(first_conflict)
        return payload
    except Exception as exc:
        return _same_x_capacity_skip(
            "capacity_precheck_error",
            error=f"{type(exc).__name__}: {exc}",
        )


def _same_x_capacity_skip(reason: str, **extra: Any) -> Dict[str, Any]:
    return {"evaluated": False, "conflict": False, "reason": str(reason), **extra}


def evaluate_ghost_y_overlap_forced_label_conflict(
    owner: Any,
    *,
    solution_hint: Mapping[str, int],
    ghost_anchor_hint_idx: Optional[int],
    force_fields: Sequence[str] = ("x", "y", "mode"),
    force_equality_keys: Optional[Collection[str]] = None,
) -> Dict[str, Any]:
    """No-solve certificate for fixed-y labels that cannot avoid a fixed ghost."""

    try:
        forced_fields = {str(field) for field in force_fields}
        if "y" not in forced_fields:
            return _ghost_y_overlap_skip("y_not_forced")
        if ghost_anchor_hint_idx is None:
            return _ghost_y_overlap_skip("ghost_anchor_hint_unavailable")
        delegate = getattr(owner, "_coordinate_delegate", None)
        if delegate is None:
            return _ghost_y_overlap_skip("coordinate_delegate_unavailable")
        ghost_rect = tuple(int(v) for v in (getattr(owner, "ghost_rect", None) or ()))
        if len(ghost_rect) != 2:
            return _ghost_y_overlap_skip("ghost_rect_unavailable")
        ghost_w, ghost_h = int(ghost_rect[0]), int(ghost_rect[1])
        if ghost_w <= 0 or ghost_h <= 0:
            return _ghost_y_overlap_skip("ghost_rect_invalid")
        ghost_domains = list(getattr(owner, "_ghost_domains", []))
        anchor_idx = int(ghost_anchor_hint_idx)
        if not (0 <= anchor_idx < len(ghost_domains)):
            return _ghost_y_overlap_skip("ghost_anchor_domain_unavailable")
        domain = ghost_domains[anchor_idx]
        anchor = dict(domain.get("anchor", {})) if isinstance(domain, Mapping) else {}
        if "x" not in anchor or "y" not in anchor:
            return _ghost_y_overlap_skip("ghost_anchor_missing_xy")
        ghost_x, ghost_y = int(anchor["x"]), int(anchor["y"])
        grid_w, grid_h = int(getattr(owner, "grid_w", 0)), int(getattr(owner, "grid_h", 0))
        if grid_w <= 0 or grid_h <= 0:
            return _ghost_y_overlap_skip("grid_unavailable")
        if ghost_x < 0 or ghost_y < 0 or ghost_x + ghost_w > grid_w or ghost_y + ghost_h > grid_h:
            return _ghost_y_overlap_skip("ghost_outside_grid")

        selected_keys = (
            None
            if force_equality_keys is None
            else {str(key) for key in force_equality_keys}
        )
        grouped_hints: DefaultDict[str, List[int]] = defaultdict(list)
        for solution_id, pose_idx in dict(solution_hint or {}).items():
            solution_id = str(solution_id)
            if solution_id in getattr(owner, "_group_id_by_instance", {}):
                grouped_hints[str(owner._group_id_by_instance[solution_id])].append(
                    int(pose_idx)
                )

        left_width = max(0, int(ghost_x))
        right_width = max(0, int(grid_w) - int(ghost_x + ghost_w))
        max_horizontal_strip_width = max(int(left_width), int(right_width))
        force_labels: List[Dict[str, Any]] = []
        conflicts: List[Dict[str, Any]] = []
        skipped_slots: List[Dict[str, Any]] = []

        def _pose_sort_key(tpl: str, pose_idx: int) -> Any:
            sorter = getattr(owner, "_pose_sort_key", None)
            if callable(sorter):
                return sorter(str(tpl), int(pose_idx))
            return int(pose_idx)

        for group in list(getattr(owner, "_mandatory_groups", [])):
            group_id = str(group["group_id"])
            tpl = str(group["facility_type"])
            slot_specs = list(getattr(delegate, "mandatory_slots", {}).get(group_id, []))
            solution_ids = [str(item) for item in list(group.get("instance_ids", []))]
            pose_indices = sorted(
                grouped_hints.get(group_id, []),
                key=lambda pose_idx: _pose_sort_key(tpl, int(pose_idx)),
            )
            for slot_index, (slot, pose_idx) in enumerate(zip(slot_specs, pose_indices)):
                pose_tuple = getattr(delegate, "_template_pose_tuple_by_idx", {}).get(str(tpl), {}).get(int(pose_idx))
                solution_id = (
                    solution_ids[int(slot_index)]
                    if int(slot_index) < len(solution_ids)
                    else f"{group_id}::{slot_index}"
                )
                stable_key = _same_x_capacity_stable_key(
                    group_id=group_id,
                    solution_id=solution_id,
                    slot_key=str(slot_index),
                    slot_index=int(slot_index),
                    pose_idx=int(pose_idx),
                    field="y",
                )
                selected = selected_keys is None or stable_key in selected_keys
                if pose_tuple is None:
                    skipped_slots.append(
                        {
                            "stable_key": stable_key,
                            "group_id": group_id,
                            "slot_index": int(slot_index),
                            "pose_index": int(pose_idx),
                            "reason": "missing_pose_tuple",
                            "selected": bool(selected),
                        }
                    )
                    continue
                _x_val, y_val, _mode_id = pose_tuple
                label = {
                    "stable_key": stable_key,
                    "group_id": group_id,
                    "solution_id": solution_id,
                    "slot_key": str(slot_index),
                    "slot_index": int(slot_index),
                    "template": tpl,
                    "pose_index": int(pose_idx),
                    "field": "y",
                    "forced_value": int(y_val),
                    "selected": bool(selected),
                }
                force_labels.append(dict(label))
                if not selected:
                    continue
                dims = tuple(getattr(slot, "dims", ()) or ())
                if len(dims) != 2:
                    skipped_slots.append({**label, "reason": "slot_dims_unavailable"})
                    continue
                slot_w, slot_h = int(dims[0]), int(dims[1])
                if slot_w <= 0 or slot_h <= 0:
                    skipped_slots.append({**label, "reason": "slot_dims_invalid"})
                    continue
                y_start = int(y_val)
                y_end = int(y_start + slot_h)
                overlaps_ghost_y = _same_x_capacity_intervals_overlap(
                    y_start,
                    y_end,
                    int(ghost_y),
                    int(ghost_y + ghost_h),
                )
                if not overlaps_ghost_y:
                    continue
                conflict = bool(slot_w > max_horizontal_strip_width)
                conflict_payload = {
                    **label,
                    "slot_width": int(slot_w),
                    "slot_height": int(slot_h),
                    "y_interval": {"start": int(y_start), "end": int(y_end)},
                    "ghost_y_interval": {
                        "start": int(ghost_y),
                        "end": int(ghost_y + ghost_h),
                    },
                    "ghost_x_interval": {
                        "start": int(ghost_x),
                        "end": int(ghost_x + ghost_w),
                    },
                    "left_width": int(left_width),
                    "right_width": int(right_width),
                    "max_horizontal_strip_width": int(max_horizontal_strip_width),
                    "conflict": conflict,
                }
                if conflict:
                    conflicts.append(conflict_payload)

        return {
            "evaluated": True,
            "conflict": bool(conflicts),
            "triggered": bool(conflicts),
            "reason": (
                "ghost_y_overlap_forced_label_infeasible"
                if conflicts
                else "no_ghost_y_overlap_forced_label_conflict"
            ),
            "anchor_idx": int(anchor_idx),
            "ghost_rect": {
                "x": int(ghost_x),
                "y": int(ghost_y),
                "w": int(ghost_w),
                "h": int(ghost_h),
            },
            "grid": {"w": int(grid_w), "h": int(grid_h)},
            "left_width": int(left_width),
            "right_width": int(right_width),
            "max_horizontal_strip_width": int(max_horizontal_strip_width),
            "forced_label_count": int(sum(1 for label in force_labels if label.get("selected"))),
            "conflict_count": int(len(conflicts)),
            "first_conflict": dict(conflicts[0]) if conflicts else None,
            "conflicts": conflicts[:16],
            "skipped_slots": skipped_slots[:16],
            "force_equality_filter_active": selected_keys is not None,
            "force_equality_labels": force_labels,
        }
    except Exception as exc:
        return _ghost_y_overlap_skip(
            "ghost_y_overlap_precheck_error",
            error=f"{type(exc).__name__}: {exc}",
        )


def _ghost_y_overlap_skip(reason: str, **extra: Any) -> Dict[str, Any]:
    return {
        "evaluated": False,
        "conflict": False,
        "triggered": False,
        "reason": str(reason),
        **extra,
    }


def evaluate_ghost_overlap_forced_domain_conflict(
    owner: Any,
    *,
    solution_hint: Mapping[str, int],
    ghost_anchor_hint_idx: Optional[int],
    force_fields: Sequence[str] = ("x", "y", "mode"),
    force_equality_keys: Optional[Collection[str]] = None,
) -> Dict[str, Any]:
    """No-solve certificate when selected forced labels imply fixed-ghost overlap."""

    try:
        forced_fields = {str(field) for field in force_fields}
        if not forced_fields.intersection({"x", "y", "mode"}):
            return _ghost_overlap_forced_domain_skip("no_supported_force_fields")
        if ghost_anchor_hint_idx is None:
            return _ghost_overlap_forced_domain_skip("ghost_anchor_hint_unavailable")
        delegate = getattr(owner, "_coordinate_delegate", None)
        if delegate is None:
            return _ghost_overlap_forced_domain_skip("coordinate_delegate_unavailable")
        ghost_rect = tuple(int(v) for v in (getattr(owner, "ghost_rect", None) or ()))
        if len(ghost_rect) != 2:
            return _ghost_overlap_forced_domain_skip("ghost_rect_unavailable")
        ghost_w, ghost_h = int(ghost_rect[0]), int(ghost_rect[1])
        if ghost_w <= 0 or ghost_h <= 0:
            return _ghost_overlap_forced_domain_skip("ghost_rect_invalid")
        ghost_domains = list(getattr(owner, "_ghost_domains", []))
        anchor_idx = int(ghost_anchor_hint_idx)
        if not (0 <= anchor_idx < len(ghost_domains)):
            return _ghost_overlap_forced_domain_skip("ghost_anchor_domain_unavailable")
        domain = ghost_domains[anchor_idx]
        anchor = dict(domain.get("anchor", {})) if isinstance(domain, Mapping) else {}
        if "x" not in anchor or "y" not in anchor:
            return _ghost_overlap_forced_domain_skip("ghost_anchor_missing_xy")
        ghost_x, ghost_y = int(anchor["x"]), int(anchor["y"])
        grid_w, grid_h = int(getattr(owner, "grid_w", 0)), int(getattr(owner, "grid_h", 0))
        if grid_w <= 0 or grid_h <= 0:
            return _ghost_overlap_forced_domain_skip("grid_unavailable")
        if ghost_x < 0 or ghost_y < 0 or ghost_x + ghost_w > grid_w or ghost_y + ghost_h > grid_h:
            return _ghost_overlap_forced_domain_skip("ghost_outside_grid")

        selected_keys = (
            None
            if force_equality_keys is None
            else {str(key) for key in force_equality_keys}
        )
        grouped_hints: DefaultDict[str, List[int]] = defaultdict(list)
        for solution_id, pose_idx in dict(solution_hint or {}).items():
            solution_id = str(solution_id)
            if solution_id in getattr(owner, "_group_id_by_instance", {}):
                grouped_hints[str(owner._group_id_by_instance[solution_id])].append(
                    int(pose_idx)
                )

        force_labels: List[Dict[str, Any]] = []
        slot_constraints: Dict[Tuple[str, int], Dict[str, Any]] = {}
        skipped_slots: List[Dict[str, Any]] = []

        def _pose_sort_key(tpl: str, pose_idx: int) -> Any:
            sorter = getattr(owner, "_pose_sort_key", None)
            if callable(sorter):
                return sorter(str(tpl), int(pose_idx))
            return int(pose_idx)

        for group in list(getattr(owner, "_mandatory_groups", [])):
            group_id = str(group["group_id"])
            tpl = str(group["facility_type"])
            slot_specs = list(getattr(delegate, "mandatory_slots", {}).get(group_id, []))
            solution_ids = [str(item) for item in list(group.get("instance_ids", []))]
            pose_indices = sorted(
                grouped_hints.get(group_id, []),
                key=lambda pose_idx: _pose_sort_key(tpl, int(pose_idx)),
            )
            for slot_index, (slot, pose_idx) in enumerate(zip(slot_specs, pose_indices)):
                pose_tuple = getattr(delegate, "_template_pose_tuple_by_idx", {}).get(str(tpl), {}).get(int(pose_idx))
                if pose_tuple is None:
                    skipped_slots.append(
                        {
                            "group_id": group_id,
                            "slot_index": int(slot_index),
                            "pose_index": int(pose_idx),
                            "reason": "missing_pose_tuple",
                        }
                    )
                    continue
                solution_id = (
                    solution_ids[int(slot_index)]
                    if int(slot_index) < len(solution_ids)
                    else f"{group_id}::{slot_index}"
                )
                forced_values = {
                    "x": int(pose_tuple[0]),
                    "y": int(pose_tuple[1]),
                    "mode": int(pose_tuple[2]),
                }
                for field in ("x", "y", "mode"):
                    if field not in forced_fields:
                        continue
                    stable_key = _same_x_capacity_stable_key(
                        group_id=group_id,
                        solution_id=solution_id,
                        slot_key=str(slot_index),
                        slot_index=int(slot_index),
                        pose_idx=int(pose_idx),
                        field=field,
                    )
                    selected = selected_keys is None or stable_key in selected_keys
                    label = {
                        "stable_key": stable_key,
                        "group_id": group_id,
                        "solution_id": solution_id,
                        "slot_key": str(slot_index),
                        "slot_index": int(slot_index),
                        "template": tpl,
                        "pose_index": int(pose_idx),
                        "field": field,
                        "forced_value": int(forced_values[field]),
                        "selected": bool(selected),
                    }
                    force_labels.append(dict(label))
                    if not selected:
                        continue
                    slot_key = (group_id, int(slot_index))
                    slot_payload = slot_constraints.setdefault(
                        slot_key,
                        {
                            "group_id": group_id,
                            "slot_index": int(slot_index),
                            "solution_id": solution_id,
                            "template": tpl,
                            "pose_index": int(pose_idx),
                            "slot": slot,
                            "forced_fields": {},
                            "selected_labels": [],
                        },
                    )
                    slot_payload["forced_fields"][field] = int(forced_values[field])
                    slot_payload["selected_labels"].append(dict(label))

        conflicts: List[Dict[str, Any]] = []
        for slot_payload in slot_constraints.values():
            slot = slot_payload["slot"]
            rows = [
                tuple(int(value) for value in row)
                for row in list(getattr(slot, "allowed_tuples", []) or [])
                if len(tuple(row)) == 3
            ]
            if not rows:
                skipped_slots.append(
                    {
                        "group_id": slot_payload.get("group_id"),
                        "slot_index": int(slot_payload.get("slot_index", -1)),
                        "reason": "allowed_tuples_unavailable",
                    }
                )
                continue
            dims = tuple(getattr(slot, "dims", ()) or ())
            if len(dims) != 2:
                skipped_slots.append(
                    {
                        "group_id": slot_payload.get("group_id"),
                        "slot_index": int(slot_payload.get("slot_index", -1)),
                        "reason": "slot_dims_unavailable",
                    }
                )
                continue
            slot_w, slot_h = int(dims[0]), int(dims[1])
            if slot_w <= 0 or slot_h <= 0:
                skipped_slots.append(
                    {
                        "group_id": slot_payload.get("group_id"),
                        "slot_index": int(slot_payload.get("slot_index", -1)),
                        "reason": "slot_dims_invalid",
                    }
                )
                continue
            constraints = dict(slot_payload.get("forced_fields", {}))
            compatible_rows = [
                row
                for row in rows
                if all(
                    int(row[{"x": 0, "y": 1, "mode": 2}[field]]) == int(value)
                    for field, value in constraints.items()
                )
            ]
            if not compatible_rows:
                continue
            overlapping_rows = [
                row
                for row in compatible_rows
                if _same_x_capacity_intervals_overlap(
                    int(row[0]),
                    int(row[0]) + slot_w,
                    ghost_x,
                    ghost_x + ghost_w,
                )
                and _same_x_capacity_intervals_overlap(
                    int(row[1]),
                    int(row[1]) + slot_h,
                    ghost_y,
                    ghost_y + ghost_h,
                )
            ]
            if len(overlapping_rows) != len(compatible_rows):
                continue
            conflicts.append(
                {
                    "reason": "all_compatible_rows_overlap_fixed_ghost",
                    "group_id": slot_payload.get("group_id"),
                    "solution_id": slot_payload.get("solution_id"),
                    "slot_index": int(slot_payload.get("slot_index", -1)),
                    "template": slot_payload.get("template"),
                    "pose_index": int(slot_payload.get("pose_index", -1)),
                    "slot_width": int(slot_w),
                    "slot_height": int(slot_h),
                    "forced_fields": constraints,
                    "selected_labels": [
                        dict(label)
                        for label in list(slot_payload.get("selected_labels", []))
                        if isinstance(label, Mapping)
                    ],
                    "allowed_tuple_count": int(len(rows)),
                    "compatible_tuple_count": int(len(compatible_rows)),
                    "compatible_rows": [
                        {"x": int(row[0]), "y": int(row[1]), "mode": int(row[2])}
                        for row in compatible_rows[:16]
                    ],
                    "ghost_rect": {
                        "x": int(ghost_x),
                        "y": int(ghost_y),
                        "w": int(ghost_w),
                        "h": int(ghost_h),
                    },
                }
            )

        return {
            "evaluated": True,
            "conflict": bool(conflicts),
            "triggered": bool(conflicts),
            "reason": (
                "ghost_overlap_forced_domain_infeasible"
                if conflicts
                else "no_ghost_overlap_forced_domain_conflict"
            ),
            "anchor_idx": int(anchor_idx),
            "ghost_rect": {
                "x": int(ghost_x),
                "y": int(ghost_y),
                "w": int(ghost_w),
                "h": int(ghost_h),
            },
            "grid": {"w": int(grid_w), "h": int(grid_h)},
            "forced_label_count": int(sum(1 for label in force_labels if label.get("selected"))),
            "checked_slot_count": int(len(slot_constraints)),
            "conflict_count": int(len(conflicts)),
            "first_conflict": dict(conflicts[0]) if conflicts else None,
            "conflicts": conflicts[:16],
            "skipped_slots": skipped_slots[:16],
            "force_equality_filter_active": selected_keys is not None,
            "force_equality_labels": force_labels,
        }
    except Exception as exc:
        return _ghost_overlap_forced_domain_skip(
            "ghost_overlap_forced_domain_precheck_error",
            error=f"{type(exc).__name__}: {exc}",
        )


def _ghost_overlap_forced_domain_skip(reason: str, **extra: Any) -> Dict[str, Any]:
    return {
        "evaluated": False,
        "conflict": False,
        "triggered": False,
        "reason": str(reason),
        **extra,
    }


def evaluate_signature_monotonic_forced_label_conflict(
    owner: Any,
    *,
    solution_hint: Mapping[str, int],
    force_fields: Sequence[str] = ("x", "y", "mode"),
    force_equality_keys: Optional[Collection[str]] = None,
) -> Dict[str, Any]:
    """No-solve certificate for impossible mandatory signature monotonicity."""

    try:
        delegate = getattr(owner, "_coordinate_delegate", None)
        if delegate is None:
            return _signature_monotonic_skip("coordinate_delegate_unavailable")
        selected_keys = (
            None
            if force_equality_keys is None
            else {str(key) for key in force_equality_keys}
        )
        forced_fields = {str(field) for field in force_fields}
        grouped_hints: DefaultDict[str, List[int]] = defaultdict(list)
        for solution_id, pose_idx in dict(solution_hint or {}).items():
            solution_id = str(solution_id)
            pose_idx = int(pose_idx)
            if solution_id in getattr(owner, "_group_id_by_instance", {}):
                grouped_hints[str(owner._group_id_by_instance[solution_id])].append(
                    int(pose_idx)
                )
        if not grouped_hints:
            return _signature_monotonic_skip("empty_mandatory_solution_hint")

        groups_checked = 0
        skipped_groups: List[Dict[str, Any]] = []
        for group in list(getattr(owner, "_mandatory_groups", [])):
            group_id = str(group.get("group_id", ""))
            tpl = str(group.get("facility_type", ""))
            slot_specs = list(getattr(delegate, "mandatory_slots", {}).get(group_id, []))
            if not slot_specs or group_id not in grouped_hints:
                continue
            if bool(
                getattr(delegate, "_mandatory_group_uses_signature_table", {}).get(
                    group_id,
                    False,
                )
            ):
                skipped_groups.append(
                    {"group_id": group_id, "reason": "signature_table_path"}
                )
                continue
            signature_by_pose_idx = _signature_monotonic_signature_by_pose_idx(
                delegate,
                group_id=group_id,
                slot=slot_specs[0],
            )
            signature_ids = set(int(value) for value in signature_by_pose_idx.values())
            if not signature_ids:
                skipped_groups.append(
                    {"group_id": group_id, "reason": "signature_pose_mapping_missing"}
                )
                continue
            solution_ids = [str(item) for item in list(group.get("instance_ids", []))]
            pose_indices = sorted(
                grouped_hints.get(group_id, []),
                key=lambda pose_idx: owner._pose_sort_key(tpl, int(pose_idx)),
            )
            slot_allowed: List[Set[int]] = [set(signature_ids) for _ in slot_specs]
            slot_forced_values: List[Dict[str, int]] = [dict() for _ in slot_specs]
            slot_pose_indices: List[Optional[int]] = [None for _ in slot_specs]
            label_implications: List[Dict[str, Any]] = []
            selected_label_count = 0
            for slot_index, (_slot, pose_idx) in enumerate(zip(slot_specs, pose_indices)):
                pose_tuple = getattr(delegate, "_template_pose_tuple_by_idx", {}).get(
                    tpl,
                    {},
                ).get(int(pose_idx))
                if pose_tuple is None:
                    continue
                slot_pose_indices[int(slot_index)] = int(pose_idx)
                x_val, y_val, mode_id = pose_tuple
                solution_id = (
                    solution_ids[int(slot_index)]
                    if int(slot_index) < len(solution_ids)
                    else f"{group_id}::{slot_index}"
                )
                for field, forced_value in (
                    ("x", int(x_val)),
                    ("y", int(y_val)),
                    ("mode", int(mode_id)),
                ):
                    if field not in forced_fields:
                        continue
                    stable_key = _same_x_capacity_stable_key(
                        group_id=group_id,
                        solution_id=solution_id,
                        slot_key=str(slot_index),
                        slot_index=int(slot_index),
                        pose_idx=int(pose_idx),
                        field=field,
                    )
                    selected = selected_keys is None or stable_key in selected_keys
                    if not selected:
                        continue
                    selected_label_count += 1
                    slot_forced_values[int(slot_index)][str(field)] = int(forced_value)
                    label_implications.append(
                        {
                            "stable_key": stable_key,
                            "group_id": group_id,
                            "slot_index": int(slot_index),
                            "solution_id": solution_id,
                            "pose_index": int(pose_idx),
                            "field": field,
                            "forced_value": int(forced_value),
                            "allowed_signature_ids": None,
                            "slot_conjunctive_forced_fields": None,
                            "slot_conjunctive_allowed_signature_ids": None,
                        }
                    )
            if selected_label_count <= 0:
                continue
            slot_constraint_entries: List[Dict[str, Any]] = []
            rows_by_signature: Optional[Dict[int, List[Tuple[int, int, int]]]] = None
            missing_rows = False
            for slot_index, constraints in enumerate(slot_forced_values):
                if not constraints:
                    continue
                pose_idx = slot_pose_indices[int(slot_index)]
                direct_signature_id = (
                    signature_by_pose_idx.get(int(pose_idx))
                    if pose_idx is not None
                    else None
                )
                if (
                    direct_signature_id is not None
                    and {"x", "y", "mode"}.issubset(set(constraints))
                ):
                    allowed_by_slot = {int(direct_signature_id)}
                else:
                    if rows_by_signature is None:
                        rows_by_signature = _signature_monotonic_rows_by_signature(
                            delegate,
                            group_id=group_id,
                            template=tpl,
                            slot=slot_specs[0],
                        )
                    if not rows_by_signature:
                        skipped_groups.append(
                            {
                                "group_id": group_id,
                                "reason": "signature_rows_missing",
                            }
                        )
                        missing_rows = True
                        break
                    allowed_by_slot = {
                        int(signature_id)
                        for signature_id, rows in rows_by_signature.items()
                        if any(
                            all(
                                _signature_monotonic_row_matches(
                                    row,
                                    field=str(field),
                                    value=int(value),
                                )
                                for field, value in constraints.items()
                            )
                            for row in rows
                        )
                    }
                slot_allowed[int(slot_index)] = allowed_by_slot
                slot_constraint_entries.append(
                    {
                        "slot_index": int(slot_index),
                        "forced_fields": {
                            str(field): int(value)
                            for field, value in sorted(constraints.items())
                        },
                        "allowed_signature_ids": sorted(allowed_by_slot),
                    }
                )
            if missing_rows:
                continue
            slot_allowed_by_index = {
                int(entry["slot_index"]): list(entry["allowed_signature_ids"])
                for entry in slot_constraint_entries
            }
            slot_fields_by_index = {
                int(entry["slot_index"]): dict(entry["forced_fields"])
                for entry in slot_constraint_entries
            }
            for implication in label_implications:
                slot_index = int(implication["slot_index"])
                implication["slot_conjunctive_forced_fields"] = slot_fields_by_index.get(
                    slot_index,
                    {},
                )
                implication["slot_conjunctive_allowed_signature_ids"] = (
                    slot_allowed_by_index.get(slot_index, sorted(signature_ids))
                )
            groups_checked += 1
            dp_entries, feasible, failure = _signature_monotonic_dp(slot_allowed)
            constrained_slots = [
                {
                    "slot_index": int(index),
                    "allowed_signature_ids": sorted(values),
                }
                for index, values in enumerate(slot_allowed)
                if set(values) != signature_ids
            ]
            if not feasible:
                return {
                    "evaluated": True,
                    "conflict": True,
                    "triggered": True,
                    "reason": "signature_monotonic_forced_label_infeasible",
                    "group_id": group_id,
                    "template": tpl,
                    "forced_label_count": int(selected_label_count),
                    "constrained_slot_count": int(len(constrained_slots)),
                    "constrained_slots": constrained_slots,
                    "failure": failure,
                    "label_implications": label_implications,
                    "slot_constraint_implications": slot_constraint_entries,
                    "dp": dp_entries,
                    "groups_checked": int(groups_checked),
                    "skipped_groups": skipped_groups,
                }
        return {
            "evaluated": True,
            "conflict": False,
            "triggered": False,
            "reason": "no_signature_monotonic_conflict",
            "groups_checked": int(groups_checked),
            "skipped_groups": skipped_groups,
        }
    except Exception as exc:
        return _signature_monotonic_skip(
            "signature_monotonic_precheck_error",
            error=f"{type(exc).__name__}: {exc}",
        )


def _signature_monotonic_skip(reason: str, **extra: Any) -> Dict[str, Any]:
    return {
        "evaluated": False,
        "conflict": False,
        "triggered": False,
        "reason": str(reason),
        **extra,
    }


def _same_x_capacity_stable_key(
    *,
    group_id: str,
    solution_id: str,
    slot_key: str,
    slot_index: int,
    pose_idx: int,
    field: str,
) -> str:
    return (
        "mandatory"
        + "|"
        + str(group_id)
        + "|"
        + str(slot_index)
        + "|"
        + str(solution_id)
        + "|"
        + str(pose_idx)
        + "|"
        + str(field)
    )


def _same_x_capacity_intervals_overlap(
    left_start: int,
    left_end: int,
    right_start: int,
    right_end: int,
) -> bool:
    return int(left_start) < int(right_end) and int(right_start) < int(left_end)


def _signature_monotonic_rows_by_signature(
    delegate: Any,
    *,
    group_id: str,
    template: str,
    slot: Any,
) -> Dict[int, List[Tuple[int, int, int]]]:
    bucket_by_signature = dict(getattr(slot, "signature_id_to_bucket_id", {}))
    signature_by_bucket = {
        str(bucket_id): int(signature_id)
        for signature_id, bucket_id in bucket_by_signature.items()
    }
    pose_tuple_by_idx = dict(
        getattr(delegate, "_template_pose_tuple_by_idx", {}).get(str(template), {})
    )
    bucket_pose_indices = dict(
        getattr(delegate, "_mandatory_group_bucket_pose_indices", {}).get(
            str(group_id),
            {},
        )
    )
    rows: Dict[int, List[Tuple[int, int, int]]] = {}
    for bucket_id, pose_indices in bucket_pose_indices.items():
        if str(bucket_id) not in signature_by_bucket:
            continue
        signature_id = int(signature_by_bucket[str(bucket_id)])
        rows.setdefault(signature_id, [])
        for pose_idx in list(pose_indices):
            pose_tuple = pose_tuple_by_idx.get(int(pose_idx))
            if pose_tuple is None:
                continue
            x_val, y_val, mode_id = pose_tuple
            rows[signature_id].append((int(x_val), int(y_val), int(mode_id)))
    return rows


def _signature_monotonic_signature_by_pose_idx(
    delegate: Any,
    *,
    group_id: str,
    slot: Any,
) -> Dict[int, int]:
    bucket_by_signature = dict(getattr(slot, "signature_id_to_bucket_id", {}))
    signature_by_bucket = {
        str(bucket_id): int(signature_id)
        for signature_id, bucket_id in bucket_by_signature.items()
    }
    bucket_pose_indices = dict(
        getattr(delegate, "_mandatory_group_bucket_pose_indices", {}).get(
            str(group_id),
            {},
        )
    )
    result: Dict[int, int] = {}
    for bucket_id, pose_indices in bucket_pose_indices.items():
        if str(bucket_id) not in signature_by_bucket:
            continue
        signature_id = int(signature_by_bucket[str(bucket_id)])
        for pose_idx in list(pose_indices):
            result[int(pose_idx)] = int(signature_id)
    return result


def _signature_monotonic_row_matches(
    row: Tuple[int, int, int],
    *,
    field: str,
    value: int,
) -> bool:
    field_index = {"x": 0, "y": 1, "mode": 2}[str(field)]
    return int(row[field_index]) == int(value)


def _signature_monotonic_dp(
    slot_allowed: Sequence[Set[int]],
) -> Tuple[List[Dict[str, Any]], bool, Optional[Dict[str, Any]]]:
    possible: Optional[Set[int]] = None
    entries: List[Dict[str, Any]] = []
    for slot_index, allowed in enumerate(slot_allowed):
        current_allowed = {int(value) for value in allowed}
        if possible is None:
            current_possible = set(current_allowed)
        else:
            current_possible = {
                current
                for current in current_allowed
                if any(previous <= current for previous in possible)
            }
        entries.append(
            {
                "slot_index": int(slot_index),
                "allowed_signature_ids": sorted(current_allowed),
                "possible_signature_ids": sorted(current_possible),
            }
        )
        if not current_possible:
            return (
                entries,
                False,
                {
                    "slot_index": int(slot_index),
                    "previous_possible_signature_ids": sorted(possible or set()),
                    "current_allowed_signature_ids": sorted(current_allowed),
                },
            )
        possible = current_possible
    return entries, True, None


PackedRectTransition = Tuple[int, int, int]
_LOCAL_POWER_CAPACITY_CACHE: Dict[Tuple[str, LocalCapacitySignature], int] = {}
_LOCAL_POWER_CAPACITY_COMPACT_CACHE: Dict[
    Tuple[str, CompactLocalCapacitySignature],
    int,
] = {}
_LOCAL_POWER_CAPACITY_NORMALIZED_RECT_CACHE: Dict[NormalizedRectangleSignature, int] = {}
_LOCAL_POWER_CAPACITY_COMPACT_RECT_CACHE = _LOCAL_POWER_CAPACITY_COMPACT_CACHE
_LOCAL_POWER_CAPACITY_RECT_DP_CACHE: Dict[
    Tuple[str, CompactLocalCapacitySignature],
    int,
] = {}
_LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE: Dict[
    Tuple[str, CompactLocalCapacitySignature, str],
    "_CompiledRectangleFrontierDP",
] = {}
_LOCAL_POWER_CAPACITY_COMPACT_RECT_CPSAT_DATA_CACHE: Dict[
    NormalizedRectangleSignature,
    "_CompiledCompactRectCpSatData",
] = {}
_LOCAL_POWER_CAPACITY_M6X4_MIXED_CPSAT_DATA_CACHE = (
    _LOCAL_POWER_CAPACITY_COMPACT_RECT_CPSAT_DATA_CACHE
)


def _rebuild_exact_core_overlay_search_guidance(
    model: Any,
    add_search_guidance: Any,
) -> Dict[str, Any]:
    search_strategy = model.model.Proto().search_strategy
    cleared_count = int(len(search_strategy))
    search_strategy.clear()
    add_search_guidance()
    return {
        "cleared_existing_strategy_count": int(cleared_count),
        "rebuilt_strategy_count": int(len(search_strategy)),
        "rebuilt_after_ghost_overlay": True,
    }


def _resolve_nonnegative_int_env(env_name: str, default: int) -> int:
    raw_value = os.environ.get(env_name)
    if raw_value is None or str(raw_value).strip() == "":
        return max(0, int(default))
    text = str(raw_value).strip()
    try:
        value = int(text)
    except ValueError:
        raise ValueError(
            f"Unsupported {env_name}: {raw_value!r}; expected a non-negative integer."
        ) from None
    if value < 0:
        raise ValueError(
            f"Unsupported {env_name}: {raw_value!r}; expected a non-negative integer."
        )
    return value


def _resolve_nonnegative_float_env(env_name: str, default: float) -> float:
    raw_value = os.environ.get(env_name)
    if raw_value is None or str(raw_value).strip() == "":
        return max(0.0, float(default))
    text = str(raw_value).strip()
    try:
        value = float(text)
    except ValueError:
        raise ValueError(
            f"Unsupported {env_name}: {raw_value!r}; expected a non-negative number."
        ) from None
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(
            f"Unsupported {env_name}: {raw_value!r}; expected a finite non-negative number."
        )
    return value


def _resolve_optional_nonnegative_int_env(env_name: str) -> Optional[int]:
    raw_value = os.environ.get(env_name)
    if raw_value is None or str(raw_value).strip() == "":
        return None
    text = str(raw_value).strip()
    try:
        value = int(text)
    except ValueError:
        raise ValueError(
            f"Unsupported {env_name}: {raw_value!r}; expected a non-negative integer."
        ) from None
    if value < 0:
        raise ValueError(
            f"Unsupported {env_name}: {raw_value!r}; expected a non-negative integer."
        )
    return value


def _resolve_optional_bool_env(env_name: str) -> Optional[bool]:
    raw_value = os.environ.get(env_name)
    if raw_value is None or str(raw_value).strip() == "":
        return None
    text = str(raw_value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        f"Unsupported {env_name}: {raw_value!r}; expected true/false."
    )


def resolve_ghost_signature_bucket_model_shell_instrumentation_enabled() -> bool:
    raw_value = os.environ.get(
        EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION_ENV
    )
    if raw_value is None:
        return False
    normalized = str(raw_value).strip().lower()
    if normalized in EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION_FALSE_VALUES:
        return False
    if normalized in EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION_TRUE_VALUES:
        return True
    raise ValueError(
        "Unsupported "
        f"{EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION_ENV}: "
        f"{raw_value!r}; expected disabled/unset or one of "
        + ", ".join(
            sorted(EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION_TRUE_VALUES)
        )
    )


def resolve_ghost_signature_bucket_port_profile_cache_instrumentation_enabled() -> bool:
    raw_value = os.environ.get(
        EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION_ENV
    )
    if raw_value is None:
        return False
    normalized = str(raw_value).strip().lower()
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION_FALSE_VALUES
    ):
        return False
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION_TRUE_VALUES
    ):
        return True
    raise ValueError(
        "Unsupported "
        f"{EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION_ENV}: "
        f"{raw_value!r}; expected disabled/unset or one of "
        + ", ".join(
            sorted(
                EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION_TRUE_VALUES
            )
        )
    )


def resolve_ghost_signature_bucket_powered_support_coverer_instrumentation_enabled() -> bool:
    raw_value = os.environ.get(
        EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV
    )
    if raw_value is None:
        return False
    normalized = str(raw_value).strip().lower()
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_FALSE_VALUES
    ):
        return False
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_TRUE_VALUES
    ):
        return True
    raise ValueError(
        "Unsupported "
        f"{EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV}: "
        f"{raw_value!r}; expected disabled/unset or one of "
        + ", ".join(
            sorted(
                EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_TRUE_VALUES
            )
        )
    )


def resolve_ghost_signature_bucket_powered_support_compact_item_accumulation_optimization_enabled() -> bool:
    raw_value = os.environ.get(
        EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_ENV
    )
    if raw_value is None:
        return False
    normalized = str(raw_value).strip().lower()
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_FALSE_VALUES
    ):
        return False
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_TRUE_VALUES
    ):
        return True
    raise ValueError(
        "Unsupported "
        f"{EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_ENV}: "
        f"{raw_value!r}; expected disabled/unset or one of "
        + ", ".join(
            sorted(
                EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_TRUE_VALUES
            )
        )
    )


def resolve_ghost_signature_bucket_powered_support_compact_item_batched_counter_optimization_enabled() -> bool:
    raw_value = os.environ.get(
        EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION_ENV
    )
    if raw_value is None:
        return False
    normalized = str(raw_value).strip().lower()
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION_FALSE_VALUES
    ):
        return False
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION_TRUE_VALUES
    ):
        return True
    raise ValueError(
        "Unsupported "
        f"{EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION_ENV}: "
        f"{raw_value!r}; expected disabled/unset or one of "
        + ", ".join(
            sorted(
                EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION_TRUE_VALUES
            )
        )
    )


def resolve_ghost_signature_bucket_powered_support_compact_item_detail_instrumentation_enabled() -> bool:
    raw_value = os.environ.get(
        EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_DETAIL_INSTRUMENTATION_ENV
    )
    if raw_value is None:
        return False
    normalized = str(raw_value).strip().lower()
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_DETAIL_INSTRUMENTATION_FALSE_VALUES
    ):
        return False
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_DETAIL_INSTRUMENTATION_TRUE_VALUES
    ):
        return True
    raise ValueError(
        "Unsupported "
        f"{EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_DETAIL_INSTRUMENTATION_ENV}: "
        f"{raw_value!r}; expected disabled/unset or one of "
        + ", ".join(
            sorted(
                EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_DETAIL_INSTRUMENTATION_TRUE_VALUES
            )
        )
    )


def _profile_bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value!r}")


def _apply_coordinate_validation_solver_profile(
    solver: Any,
    *,
    time_limit_seconds: float,
    profile: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    raw = dict(profile or {})
    solver.parameters.max_time_in_seconds = float(time_limit_seconds)
    worker_count = max(1, int(raw.get("worker_count", raw.get("num_search_workers", 1))))
    solver.parameters.num_search_workers = int(worker_count)
    branching = str(raw.get("search_branching", "")).strip().lower()
    if branching:
        if branching == "fixed":
            solver.parameters.search_branching = cp_model.FIXED_SEARCH
        elif branching == "automatic":
            solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
        elif branching == "portfolio":
            solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
        else:
            raise ValueError(f"Unsupported search_branching: {branching!r}")
    for integer_key in (
        "cp_model_probing_level",
        "symmetry_level",
        "hint_conflict_limit",
        "linearization_level",
        "random_seed",
    ):
        if integer_key in raw and raw[integer_key] is not None and hasattr(
            solver.parameters,
            integer_key,
        ):
            setattr(solver.parameters, integer_key, int(raw[integer_key]))
    for boolean_key in ("cp_model_presolve", "randomize_search"):
        if boolean_key in raw and raw[boolean_key] is not None and hasattr(
            solver.parameters,
            boolean_key,
        ):
            setattr(solver.parameters, boolean_key, _profile_bool_value(raw[boolean_key]))
    return {
        "profile_id": str(raw.get("profile_id", "default_coordinate_validation")),
        "max_time_in_seconds": float(solver.parameters.max_time_in_seconds),
        "num_search_workers": int(solver.parameters.num_search_workers),
        "search_branching": search_branching_name(solver.parameters.search_branching),
        "symmetry_level": int(solver.parameters.symmetry_level),
        "cp_model_probing_level": int(solver.parameters.cp_model_probing_level),
        "hint_conflict_limit": int(solver.parameters.hint_conflict_limit),
        "cp_model_presolve": bool(
            getattr(solver.parameters, "cp_model_presolve", True)
        ),
        "randomize_search": bool(
            getattr(solver.parameters, "randomize_search", False)
        ),
    }


def _normalize_coordinate_force_fields(force_fields: Sequence[str]) -> Tuple[str, ...]:
    allowed = ("x", "y", "mode")
    allowed_set = set(allowed)
    normalized: List[str] = []
    seen: Set[str] = set()
    for raw_field in force_fields:
        field = str(raw_field).strip().lower()
        if field not in allowed_set:
            raise ValueError(
                f"Unsupported coordinate force field: {raw_field!r}; "
                "expected one of x, y, mode."
            )
        if field in seen:
            continue
        seen.add(field)
        normalized.append(field)
    if not normalized:
        raise ValueError("force_fields must contain at least one of x, y, mode.")
    return tuple(field for field in allowed if field in seen)


def _coordinate_validation_was_evaluated(payload: Mapping[str, Any]) -> bool:
    status = str(payload.get("status", ""))
    return bool(payload.get("attempted", False)) or status in {
        "FEASIBLE",
        "INFEASIBLE",
        "OPTIMAL",
        "UNKNOWN",
    }


def _exact_mandatory_rectangle_precheck_max_anchors() -> int:
    return _resolve_nonnegative_int_env(
        EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV,
        EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS,
    )


def _exact_mandatory_rectangle_precheck_time_budget_seconds() -> float:
    return _resolve_nonnegative_float_env(
        EXACT_MANDATORY_RECTANGLE_PRECHECK_TIME_BUDGET_SECONDS_ENV,
        EXACT_MANDATORY_RECTANGLE_PRECHECK_TIME_BUDGET_SECONDS,
    )


def _exact_boundary_port_precheck_max_anchors() -> int:
    return _resolve_nonnegative_int_env(
        EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS_ENV,
        EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS,
    )


def _exact_ghost_aware_pose_order_validation_seconds() -> float:
    return _resolve_nonnegative_float_env(
        EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS_ENV,
        EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS,
    )


def _exact_ghost_aware_coordinate_validation_seconds() -> float:
    return _resolve_nonnegative_float_env(
        EXACT_GHOST_AWARE_COORDINATE_VALIDATION_SECONDS_ENV,
        EXACT_GHOST_AWARE_COORDINATE_VALIDATION_SECONDS,
    )


def _exact_ghost_aware_coordinate_validation_max_anchors() -> int:
    return _resolve_nonnegative_int_env(
        EXACT_GHOST_AWARE_COORDINATE_VALIDATION_MAX_ANCHORS_ENV,
        EXACT_GHOST_AWARE_COORDINATE_VALIDATION_MAX_ANCHORS,
    )


def _exact_signature_monotonic_forced_label_precheck_enabled() -> bool:
    return bool(
        _resolve_optional_bool_env(
            EXACT_SIGNATURE_MONOTONIC_FORCED_LABEL_PRECHECK_ENV
        )
        or False
    )


def _exact_ghost_y_overlap_forced_label_precheck_enabled() -> bool:
    return bool(
        _resolve_optional_bool_env(
            EXACT_GHOST_Y_OVERLAP_FORCED_LABEL_PRECHECK_ENV
        )
        or False
    )


def _exact_ghost_overlap_forced_domain_precheck_enabled() -> bool:
    return bool(
        _resolve_optional_bool_env(
            EXACT_GHOST_OVERLAP_FORCED_DOMAIN_PRECHECK_ENV
        )
        or False
    )


def _exact_same_x_strip_fixed_ghost_capacity_precheck_enabled() -> bool:
    return bool(
        _resolve_optional_bool_env(
            EXACT_SAME_X_STRIP_FIXED_GHOST_CAPACITY_PRECHECK_ENV
        )
        or False
    )


def _exact_warm_start_failed_anchor_sample_limit() -> int:
    return _resolve_nonnegative_int_env(
        EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT_ENV,
        EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT,
    )


def _extract_solver_numeric_stat(
    solver: Any,
    *names: str,
    default: int | float,
) -> int | float:
    """Read a numeric CpSolver stat without assuming one exact OR-Tools surface."""

    for name in names:
        try:
            value = getattr(solver, str(name))
        except Exception:
            continue
        try:
            value = value() if callable(value) else value
        except Exception:
            continue
        if value is None:
            continue
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return value
        try:
            return float(value) if isinstance(default, float) else int(value)
        except Exception:
            continue
    return default


class _BitsetLocalCapacityFallback(RuntimeError):
    """Internal exact-safe signal to fall back to the legacy CP-SAT oracle."""


class _RectangleFrontierDPFallback(RuntimeError):
    """Internal exact-safe signal to fall back to the bitset local-capacity oracle."""


class _Manufacturing6x4MixedCpSatFallback(RuntimeError):
    """Internal exact-safe signal to fall back to rect-DP v3 explicitly."""


class _Uniform3x3CpSatFallback(RuntimeError):
    """Internal exact-safe signal to fall back to rect-DP v3 explicitly."""


class _CompactRectCpSatFallback(RuntimeError):
    """Internal exact-safe signal for compact-rectangle CP-SAT specializations."""


@dataclass(frozen=True)
class _LocalRectangleVariant:
    min_x: int
    min_y: int
    max_x: int
    max_y: int
    width: int
    height: int


@dataclass(frozen=True)
class _CompiledRectangleFrontierDP:
    scan_axis: str
    line_count: int
    line_width: int
    frontier_bits: int
    horizon: int
    line_end_shift: int
    current_bit_masks: Tuple[int, ...]
    placements_by_line_and_pos: Tuple[
        Tuple[Tuple[Tuple[int, int, Tuple[int, ...]], ...], ...],
        ...,
    ]
    start_options_by_line_and_pos: Tuple[
        Tuple[Tuple[PackedRectTransition, ...], ...],
        ...,
    ]
    line_subset_transitions_by_line: Tuple[Tuple[PackedRectTransition, ...], ...]
    compiled_start_options: int
    deduped_start_options: int
    compiled_line_subsets: int
    peak_line_subset_options: int


@dataclass(frozen=True)
class _CompiledCompactRectCpSatData:
    window_w: int
    window_h: int
    placements: Tuple[Tuple[int, int, int, int], ...]
    cell_to_placement_indices: Dict[Tuple[int, int], Tuple[int, ...]]


_CompiledManufacturing6x4MixedCpSatData = _CompiledCompactRectCpSatData


@dataclass(frozen=True)
class _PowerSupportBucketRecord:
    pose_indices: Tuple[int, ...]
    coverers: Tuple[int, ...]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _normalize_generic_io_requirements_payload(
    payload: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Dict[str, int]]:
    payload = dict(payload or {})
    return {
        "required_generic_outputs": {
            str(k): int(v)
            for k, v in dict(payload.get("required_generic_outputs", {})).items()
        },
        "required_generic_inputs": {
            str(k): int(v)
            for k, v in dict(payload.get("required_generic_inputs", {})).items()
        },
    }


def load_generic_io_requirements_artifact(project_root: Path) -> Dict[str, Dict[str, int]]:
    data_dir = project_root / "data" / "preprocessed"
    return _normalize_generic_io_requirements_payload(
        _load_json(data_dir / "generic_io_requirements.json")
    )


def infer_certified_optional_lower_bounds(
    rules: Mapping[str, Any],
    generic_io_requirements: Optional[Mapping[str, Any]] = None,
) -> Dict[str, int]:
    normalized_requirements = _normalize_generic_io_requirements_payload(
        generic_io_requirements
    )
    templates = dict(rules.get("facility_templates", {}))
    required_counts: Dict[str, int] = {}

    if "protocol_storage_box" in templates:
        slots_per_box = int(
            get_operation_port_profile(
                POSE_LEVEL_OPTIONAL_OPERATIONS["protocol_storage_box"]
            ).generic_input_slots
        )
        required_slots = sum(
            int(v)
            for v in normalized_requirements.get("required_generic_inputs", {}).values()
        )
        if slots_per_box > 0:
            required_box_count = (required_slots + slots_per_box - 1) // slots_per_box
            if required_box_count > 0:
                required_counts["protocol_storage_box"] = int(required_box_count)

    return required_counts


def infer_exact_required_pose_optional_counts(
    rules: Mapping[str, Any],
    generic_io_requirements: Optional[Mapping[str, Any]] = None,
) -> Dict[str, int]:
    """Backward-compatible alias for certified-exact lower-bound inference."""

    return infer_certified_optional_lower_bounds(
        rules,
        generic_io_requirements,
    )


def _clone_model_proto(proto: Any) -> Any:
    cloned = proto.__class__()
    if hasattr(cloned, "CopyFrom"):
        cloned.CopyFrom(proto)
    else:
        cloned.copy_from(proto)
    return cloned


def _normalize_solve_mode(
    solve_mode: Optional[str] = None,
    exact_mode: Optional[bool] = None,
) -> str:
    if exact_mode is not None:
        return "certified_exact" if exact_mode else "exploratory"
    if solve_mode is None:
        return "certified_exact"
    if solve_mode not in {"certified_exact", "exploratory"}:
        raise ValueError(f"Unsupported solve_mode（不支持的求解模式）: {solve_mode}")
    return solve_mode


def _load_mandatory_exact_instances(data_dir: Path) -> List[Dict[str, Any]]:
    exact_path = data_dir / "mandatory_exact_instances.json"
    if exact_path.exists():
        payload = _load_json(exact_path)
        if isinstance(payload, dict) and "instances" in payload:
            return list(payload["instances"])
        return list(payload)

    all_path = data_dir / "all_facility_instances.json"
    payload = _load_json(all_path)
    return [
        dict(inst)
        for inst in payload
        if bool(inst.get("is_mandatory")) and inst.get("bound_type") == "exact"
    ]


def _load_all_facility_instances(data_dir: Path) -> List[Dict[str, Any]]:
    all_path = data_dir / "all_facility_instances.json"
    if all_path.exists():
        payload = _load_json(all_path)
        if isinstance(payload, dict) and "instances" in payload:
            return list(payload["instances"])
        return list(payload)

    mandatory = _load_mandatory_exact_instances(data_dir)
    caps_path = data_dir / "exploratory_optional_caps.json"
    if not caps_path.exists():
        return mandatory
    caps = _load_json(caps_path)
    optional_instances: List[Dict[str, Any]] = []
    for facility_type, spec in dict(caps).items():
        cap = int(spec.get("cap", 0))
        prefix = "power_pole" if facility_type == "power_pole" else "protocol_box"
        for index in range(1, cap + 1):
            optional_instances.append(
                {
                    "instance_id": f"{prefix}_{index:03d}",
                    "facility_type": facility_type,
                    "operation_type": spec.get("operation_type", POSE_LEVEL_OPTIONAL_OPERATIONS.get(facility_type, facility_type)),
                    "is_mandatory": False,
                    "bound_type": spec.get("bound_type", "provisional"),
                }
            )
    return mandatory + optional_instances


def load_project_data(
    project_root: Path,
    solve_mode: str = "certified_exact",
) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    """Load canonical project data（加载项目工件）.

    certified_exact（严格认证精确）默认只读取 mandatory_exact_instances.json。
    exploratory（探索）读取 all_facility_instances.json。
    """

    solve_mode = _normalize_solve_mode(solve_mode)
    data_dir = project_root / "data" / "preprocessed"

    if solve_mode == "certified_exact":
        instances = _load_mandatory_exact_instances(data_dir)
    else:
        instances = _load_all_facility_instances(data_dir)

    placements_payload = _load_json(data_dir / "candidate_placements.json")
    facility_pools = dict(placements_payload["facility_pools"])
    rules = dict(_load_json(project_root / "rules" / "canonical_rules.json"))
    return instances, facility_pools, rules


@dataclass
class ExactMasterCore:
    """Candidate-independent exact master core that can be cloned per ghost rectangle."""

    proto: Any
    source_instances: Sequence[Mapping[str, Any]]
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]]
    rules: Mapping[str, Any]
    generic_io_requirements: Mapping[str, Mapping[str, int]]
    exact_required_pose_optional_counts: Mapping[str, int]
    build_stats: Mapping[str, Any]
    z_var_indices: Dict[str, Dict[int, int]]
    optional_pose_var_indices: Dict[str, Dict[int, int]]
    mandatory_groups: Sequence[Mapping[str, Any]]
    group_id_by_instance: Mapping[str, str]
    skip_power_coverage: bool
    enable_symmetry_breaking: bool
    master_representation: str = "pose_bool_v1"
    coordinate_binding: Mapping[str, Any] = field(default_factory=dict)
    candidate_precheck_artifacts: Mapping[str, Any] = field(default_factory=dict)


class MasterPlacementModel:
    """CP-SAT feasibility model（可行性模型） for placement（摆放）."""

    def __init__(
        self,
        instances: Sequence[Mapping[str, Any]],
        facility_pools: Mapping[str, List[Dict[str, Any]]],
        rules: Mapping[str, Any],
        ghost_rect: Optional[Tuple[int, int]] = None,
        skip_power_coverage: bool = False,
        enable_symmetry_breaking: bool = True,
        generic_io_requirements: Optional[Mapping[str, Any]] = None,
        exact_required_pose_optional_counts: Optional[Mapping[str, Any]] = None,
        exact_mode: Optional[bool] = None,
        solve_mode: Optional[str] = None,
        master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    ):
        model_shell_instrumentation_enabled = (
            resolve_ghost_signature_bucket_model_shell_instrumentation_enabled()
        )
        model_shell_started = time.perf_counter()
        model_shell_phase_started = model_shell_started
        model_shell_subphase_seconds: Dict[str, float] = {}

        def _record_model_shell_subphase(phase: str, started_at: float) -> None:
            if not model_shell_instrumentation_enabled:
                return
            model_shell_subphase_seconds[phase] = float(
                model_shell_subphase_seconds.get(phase, 0.0)
                + max(0.0, time.perf_counter() - started_at)
            )

        self.solve_mode = _normalize_solve_mode(solve_mode, exact_mode)
        self.exact_mode = self.solve_mode == "certified_exact"
        self.master_search_profile = normalize_exact_coordinate_master_search_profile(
            master_search_profile
        )
        _record_model_shell_subphase(
            "dimension_and_profile_normalization",
            model_shell_phase_started,
        )
        model_shell_phase_started = time.perf_counter()

        self.source_instances: List[Dict[str, Any]] = [dict(item) for item in instances]
        self.instances: List[Dict[str, Any]] = [
            item for item in self.source_instances if bool(item.get("is_mandatory"))
        ]
        self.facility_pools = {tpl: list(pool) for tpl, pool in facility_pools.items()}
        self.rules = dict(rules)
        self.templates = dict(self.rules["facility_templates"])
        self.generic_io_requirements = _normalize_generic_io_requirements_payload(
            generic_io_requirements
        )
        self._exact_required_pose_optional_counts = {
            str(k): int(v)
            for k, v in dict(exact_required_pose_optional_counts or {}).items()
            if int(v) > 0
        }
        self._certified_optional_lower_bounds = (
            infer_certified_optional_lower_bounds(
                self.rules,
                self.generic_io_requirements,
            )
            if self.exact_mode
            else {}
        )
        self.ghost_rect = ghost_rect
        self.skip_power_coverage = skip_power_coverage
        self.enable_symmetry_breaking = enable_symmetry_breaking
        _record_model_shell_subphase(
            "constructor_enter_to_instance_copy",
            model_shell_phase_started,
        )
        model_shell_phase_started = time.perf_counter()

        grid = self.rules["globals"]["grid"]
        self.grid_w = int(grid["width"])
        self.grid_h = int(grid["height"])

        self.model = cp_model.CpModel()
        self._solver: Optional[cp_model.CpSolver] = None
        self._status: Optional[int] = None
        self._built = False
        # P1 #7 main: hint 跨 wave 持久化 context. 外部调 set_hint_persistence_context
        # 传 (project_root, candidate_key) 后, build 末尾自动 load+apply, solve
        # FEASIBLE/OPTIMAL 末尾自动 extract+write. 受 EXACT_MASTER_HINT_PERSISTENCE
        # env 开关控制, default off (prep 阶段已 land).
        self._hint_persistence_context: Optional[Tuple[Path, str]] = None

        self.z_vars: Dict[str, Dict[int, cp_model.IntVar]] = {}
        self.optional_pose_vars: Dict[str, Dict[int, cp_model.IntVar]] = {}
        self.u_vars: Dict[int, cp_model.IntVar] = {}
        self._mandatory_signature_count_vars: Dict[str, Dict[str, cp_model.IntVar]] = {}
        self._required_optional_signature_count_vars: Dict[str, Dict[str, cp_model.IntVar]] = {}
        self._residual_optional_signature_count_vars: Dict[str, Dict[str, cp_model.IntVar]] = {}
        self._power_pole_family_count_vars: Dict[str, cp_model.IntVar] = {}

        self._mandatory_groups: List[Dict[str, Any]] = []
        self._group_id_by_instance: Dict[str, str] = {}
        self._optional_cap_by_template = self._infer_optional_caps()
        self._powered_templates = {
            tpl for tpl, spec in self.templates.items() if bool(spec.get("needs_power", False))
        }
        _record_model_shell_subphase(
            "optional_cap_and_support_cache_initialization",
            model_shell_phase_started,
        )
        model_shell_phase_started = time.perf_counter()

        self._covering_pose_indices: Dict[str, Dict[Tuple[int, int], List[int]]] = {}
        self._heuristic_port_fronts: Dict[str, Dict[int, Optional[List[Tuple[int, int]]]]] = {}
        self._power_coverers_by_template_pose: Dict[str, Dict[int, List[int]]] = {}
        self._pose_cells_by_template_pose: Dict[str, Dict[int, FrozenSet[Tuple[int, int]]]] = {}
        self._pose_greedy_blocking_cells_by_template_pose: Dict[
            str,
            Dict[int, FrozenSet[Tuple[int, int]]],
        ] = {}
        self._pose_anchor_by_template_pose: Dict[str, Dict[int, Tuple[int, int]]] = {}
        self._pose_local_cells_by_template_pose: Dict[str, Dict[int, LocalPoseShape]] = {}
        self._pose_local_fronts_by_template_pose: Dict[str, Dict[int, Optional[LocalPoseShape]]] = {}
        self._pose_local_power_coverage_by_template_pose: Dict[str, Dict[int, LocalPoseShape]] = {}
        self._pose_local_signature_by_template_pose: Dict[str, Dict[int, PoseLocalSignature]] = {}
        self._pose_local_shape_token_by_template_pose: Dict[str, Dict[int, int]] = {}
        self._local_shape_token_by_template_shape: Dict[str, Dict[LocalPoseShape, int]] = {}
        self._local_shape_by_template_token: Dict[str, Dict[int, LocalPoseShape]] = {}
        self._local_rectangle_variant_by_template_token: Dict[
            str,
            Dict[int, Optional[_LocalRectangleVariant]],
        ] = {}
        self._power_supported_pose_indices_by_template_pole: Dict[str, Dict[int, List[int]]] = {}
        self._power_supported_pose_bucket_records_by_template: Dict[
            str,
            Tuple[_PowerSupportBucketRecord, ...],
        ] = {}
        self._power_pole_shell_pair_by_pose_idx: Dict[int, ShellPair] = {}
        self._power_pole_pose_indices_by_shell_pair: Dict[ShellPair, List[int]] = {}
        self._local_power_capacity_signature_by_template_pole: Dict[str, Dict[int, LocalCapacitySignature]] = {}
        self._compact_local_power_capacity_signature_by_template_pole: Dict[
            str,
            Dict[int, CompactLocalCapacitySignature],
        ] = {}
        self._power_pole_pose_indices_by_template_capacity_signature: Dict[
            str,
            Dict[LocalCapacitySignature, List[int]],
        ] = {}
        self._power_pole_pose_indices_by_template_compact_capacity_signature: Dict[
            str,
            Dict[CompactLocalCapacitySignature, List[int]],
        ] = {}
        self._power_pole_compact_capacity_signatures_by_template_shell_pair: Dict[
            str,
            Dict[ShellPair, Tuple[CompactLocalCapacitySignature, ...]],
        ] = {}
        self._fully_materialized_local_power_capacity_signature_classes_by_template: Set[
            str
        ] = set()
        self._legacy_local_power_capacity_signature_by_template_compact_signature: Dict[
            str,
            Dict[CompactLocalCapacitySignature, LocalCapacitySignature],
        ] = {}
        self._compact_local_power_capacity_signature_by_template_legacy_signature: Dict[
            str,
            Dict[LocalCapacitySignature, CompactLocalCapacitySignature],
        ] = {}
        self._mandatory_signature_buckets: Dict[str, List[Dict[str, Any]]] = {}
        self._required_optional_signature_buckets: Dict[str, List[Dict[str, Any]]] = {}
        self._signature_bucket_payload_cache: Dict[Tuple[str, FrozenSet[int]], List[Dict[str, Any]]] = {}
        self._signature_domain_payload_cache: Dict[Tuple[str, FrozenSet[int]], Dict[str, Any]] = {}
        self._candidate_pose_indices_by_template: Dict[str, List[int]] = {}
        self._boundary_storage_port_feasibility_screen_cache: Optional[Dict[str, Any]] = None
        self._exact_candidate_boundary_port_feasibility_cache: Optional[Dict[str, Any]] = None
        self._exact_candidate_mandatory_support_diagnostics_cache: Optional[
            Dict[str, Any]
        ] = None
        self._exact_candidate_mandatory_rectangle_precheck_cache: Dict[
            Tuple[int, ...],
            Dict[str, Any],
        ] = {}
        self._ghost_domains: List[Dict[str, Any]] = []
        self._cell_occupancy_terms: DefaultDict[Tuple[int, int], List[cp_model.IntVar]] = defaultdict(list)
        self._last_solution: Optional[Dict[str, Any]] = None
        self._local_power_capacity_bitset_max_iterations = 200_000
        self._local_power_capacity_rect_dp_max_states = 50_000_000
        self._local_power_capacity_rect_dp_max_line_subsets = 200_000
        self._local_power_capacity_rect_dp_v4_max_peak_line_subset_options = 160
        self._local_power_capacity_rect_dp_v4_max_compiled_line_subsets = 2_000
        _record_model_shell_subphase(
            "candidate_domain_or_pose_cache_initialization",
            model_shell_phase_started,
        )
        model_shell_phase_started = time.perf_counter()

        self.build_stats: Dict[str, Any] = {
            "solve_mode": self.solve_mode,
            "requested_master_search_profile": str(self.master_search_profile),
            "optional_caps": dict(self._optional_cap_by_template),
            "generic_io_requirements": copy.deepcopy(self.generic_io_requirements),
            "exact_required_optionals": dict(self._exact_required_pose_optional_counts),
            "exact_optional_lower_bounds": dict(self._certified_optional_lower_bounds),
        }
        self._exact_precompute_profile: Dict[str, Any] = {
            "power_capacity_shell_pairs": 0,
            "power_capacity_shell_pair_evaluations": 0,
            "power_capacity_signature_classes": 0,
            "power_capacity_signature_class_evaluations": 0,
            "power_capacity_compact_signature_classes": 0,
            "power_capacity_compact_signature_evaluations": 0,
            "power_capacity_compact_signature_cache_hits": 0,
            "power_capacity_compact_signature_cache_misses": 0,
            "power_capacity_normalized_rect_signature_count": 0,
            "power_capacity_normalized_rect_cache_hits": 0,
            "power_capacity_normalized_rect_cache_misses": 0,
            "power_capacity_legacy_signature_materializations": 0,
            "power_capacity_supported_by_pole_materializations": 0,
            "power_capacity_rect_dp_evaluations": 0,
            "power_capacity_rect_dp_cache_hits": 0,
            "power_capacity_rect_dp_cache_misses": 0,
            "power_capacity_rect_dp_state_merges": 0,
            "power_capacity_rect_dp_peak_line_states": 0,
            "power_capacity_rect_dp_peak_pos_states": 0,
            "power_capacity_rect_dp_compiled_signatures": 0,
            "power_capacity_rect_dp_compiled_start_options": 0,
            "power_capacity_rect_dp_deduped_start_options": 0,
            "power_capacity_rect_dp_compiled_line_subsets": 0,
            "power_capacity_rect_dp_peak_line_subset_options": 0,
            "power_capacity_rect_dp_v3_fallbacks": 0,
            "power_capacity_compact_rect_cpsat_evaluations": 0,
            "power_capacity_compact_rect_cpsat_cache_hits": 0,
            "power_capacity_compact_rect_cpsat_selected_cases": 0,
            "power_capacity_compact_rect_cpsat_rect_dp_fallbacks": 0,
            "power_capacity_m6x4_mixed_cpsat_evaluations": 0,
            "power_capacity_m6x4_mixed_cpsat_cache_hits": 0,
            "power_capacity_m6x4_mixed_cpsat_selected_cases": 0,
            "power_capacity_m6x4_mixed_cpsat_v3_fallbacks": 0,
            "power_capacity_uniform_3x3_cpsat_evaluations": 0,
            "power_capacity_uniform_3x3_cpsat_cache_hits": 0,
            "power_capacity_uniform_3x3_cpsat_selected_cases": 0,
            "power_capacity_uniform_3x3_cpsat_v3_fallbacks": 0,
            "power_capacity_bitset_oracle_evaluations": 0,
            "power_capacity_bitset_fallbacks": 0,
            "power_capacity_cpsat_fallbacks": 0,
            "power_capacity_oracle": "compact_rect_cpsat_v2",
            "power_capacity_raw_pole_evaluations": 0,
            "signature_bucket_cache_hits": 0,
            "signature_bucket_cache_misses": 0,
            "signature_bucket_distinct_keys": 0,
            "geometry_cache_templates": 0,
        }
        self.build_stats["exact_precompute_profile"] = dict(self._exact_precompute_profile)
        _record_model_shell_subphase(
            "build_stats_initialization",
            model_shell_phase_started,
        )

        model_shell_phase_started = time.perf_counter()
        self._build_mandatory_groups()
        _record_model_shell_subphase(
            "mandatory_group_build",
            model_shell_phase_started,
        )
        model_shell_phase_started = time.perf_counter()
        self._index_pools()
        _record_model_shell_subphase(
            "port_profile_and_boundary_cache_initialization",
            model_shell_phase_started,
        )
        model_shell_phase_started = time.perf_counter()
        self._build_signature_buckets()
        _record_model_shell_subphase(
            "signature_bucket_seed_build",
            model_shell_phase_started,
        )
        model_shell_phase_started = time.perf_counter()
        self._coordinate_delegate: Optional[CoordinateExactMasterDelegate] = (
            CoordinateExactMasterDelegate(self) if self.exact_mode else None
        )
        _record_model_shell_subphase(
            "constructor_finalize",
            model_shell_phase_started,
        )
        if model_shell_instrumentation_enabled:
            self._model_shell_subphase_seconds = dict(
                sorted(model_shell_subphase_seconds.items())
            )
            self._model_shell_total_seconds = float(
                max(0.0, time.perf_counter() - model_shell_started)
            )

    @classmethod
    def build_exact_core(
        cls,
        instances: Sequence[Mapping[str, Any]],
        facility_pools: Mapping[str, List[Dict[str, Any]]],
        rules: Mapping[str, Any],
        *,
        skip_power_coverage: bool = False,
        enable_symmetry_breaking: bool = True,
        generic_io_requirements: Optional[Mapping[str, Any]] = None,
        exact_required_pose_optional_counts: Optional[Mapping[str, Any]] = None,
        master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    ) -> ExactMasterCore:
        packaging_started = time.perf_counter()
        model = cls(
            instances,
            facility_pools,
            rules,
            ghost_rect=None,
            skip_power_coverage=skip_power_coverage,
            enable_symmetry_breaking=enable_symmetry_breaking,
            generic_io_requirements=generic_io_requirements,
            exact_required_pose_optional_counts=exact_required_pose_optional_counts,
            solve_mode="certified_exact",
            master_search_profile=master_search_profile,
        )
        model.build()
        proto_capture_started = time.perf_counter()
        core_proto = model.model.Proto()
        proto_capture_seconds = time.perf_counter() - proto_capture_started
        coordinate_binding_export_started = time.perf_counter()
        coordinate_binding = (
            model._coordinate_delegate.export_core_binding()
            if model._coordinate_delegate is not None and model.exact_mode
            else {}
        )
        coordinate_binding_export_seconds = (
            time.perf_counter() - coordinate_binding_export_started
        )
        candidate_precheck_artifacts = {
            "mandatory_support_diagnostics": (
                model.evaluate_exact_candidate_mandatory_support_diagnostics()
            ),
            "boundary_port_screen_spec": model._boundary_storage_port_feasibility_screen_spec(),
        }
        build_stats = model.build_stats
        build_stats["exact_core_packaging_profile"] = {
            "proto_storage_mode": "owned_proto",
            "source_instances_snapshot_mode": "owned_model_reference",
            "facility_pools_snapshot_mode": "owned_model_reference",
            "rules_snapshot_mode": "owned_model_reference",
            "generic_io_requirements_snapshot_mode": "owned_model_reference",
            "build_stats_snapshot_mode": "owned_model_reference",
            "mandatory_groups_snapshot_mode": "owned_model_reference",
            "group_id_by_instance_snapshot_mode": "copied_dict",
            "coordinate_binding_snapshot_mode": "fresh_export",
            "proto_variable_count": int(len(core_proto.variables)),
            "proto_constraint_count": int(len(core_proto.constraints)),
            "coordinate_binding_export_seconds": float(
                coordinate_binding_export_seconds
            ),
            "proto_capture_seconds": float(proto_capture_seconds),
            "packaging_seconds": 0.0,
        }
        build_stats["exact_core_packaging_profile"]["packaging_seconds"] = float(
            time.perf_counter() - packaging_started
        )
        return ExactMasterCore(
            proto=core_proto,
            source_instances=model.source_instances,
            facility_pools=model.facility_pools,
            rules=model.rules,
            generic_io_requirements=model.generic_io_requirements,
            exact_required_pose_optional_counts=dict(model._exact_required_pose_optional_counts),
            build_stats=build_stats,
            z_var_indices=model._current_z_var_indices(),
            optional_pose_var_indices=model._current_optional_pose_var_indices(),
            mandatory_groups=model._mandatory_groups,
            group_id_by_instance=dict(model._group_id_by_instance),
            skip_power_coverage=bool(model.skip_power_coverage),
            enable_symmetry_breaking=bool(model.enable_symmetry_breaking),
            master_representation=str(model.build_stats.get("master_representation", "pose_bool_v1")),
            coordinate_binding=coordinate_binding,
            candidate_precheck_artifacts=copy.deepcopy(candidate_precheck_artifacts),
        )

    @classmethod
    def from_exact_core(
        cls,
        core: ExactMasterCore,
        ghost_rect: Optional[Tuple[int, int]],
        *,
        master_search_profile: str = DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
        precomputed_boundary_port_feasibility: Optional[Mapping[str, Any]] = None,
    ) -> "MasterPlacementModel":
        residual_overlay_instrumentation_enabled = (
            resolve_ghost_signature_bucket_residual_overlay_instrumentation_enabled()
        )
        model_shell_instrumentation_enabled = (
            resolve_ghost_signature_bucket_model_shell_instrumentation_enabled()
        )
        port_profile_cache_instrumentation_enabled = (
            resolve_ghost_signature_bucket_port_profile_cache_instrumentation_enabled()
        )
        powered_support_coverer_instrumentation_enabled = (
            resolve_ghost_signature_bucket_powered_support_coverer_instrumentation_enabled()
        )
        compact_item_accumulation_optimization_enabled = (
            resolve_ghost_signature_bucket_powered_support_compact_item_accumulation_optimization_enabled()
        )
        compact_item_batched_counter_optimization_enabled = (
            resolve_ghost_signature_bucket_powered_support_compact_item_batched_counter_optimization_enabled()
        )
        resolve_ghost_signature_bucket_powered_support_compact_item_detail_instrumentation_enabled()
        port_profile_cache_publication_enabled = (
            port_profile_cache_instrumentation_enabled
            or powered_support_coverer_instrumentation_enabled
        )
        outer_overlay_instrumentation_enabled = (
            residual_overlay_instrumentation_enabled
            or model_shell_instrumentation_enabled
            or port_profile_cache_publication_enabled
        )
        profile_validation_started = time.perf_counter()
        normalized_master_search_profile = normalize_exact_coordinate_master_search_profile(
            master_search_profile
        )
        core_profile = str(
            dict(core.build_stats.get("search_guidance", {})).get(
                "profile",
                DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
            )
        )
        if core_profile != normalized_master_search_profile:
            raise ValueError(
                "ExactMasterCore search profile does not match the requested master_search_profile"
            )
        profile_validation_seconds = time.perf_counter() - profile_validation_started
        outer_exact_core_overlay_subphase_seconds: Dict[str, float] = {}
        ghost_overlay_subphase_seconds: Dict[str, float] = {}

        def _record_outer_subphase(
            phase_seconds: Dict[str, float],
            phase: str,
            started_at: float,
        ) -> None:
            if not outer_overlay_instrumentation_enabled:
                return
            phase_seconds[phase] = float(
                phase_seconds.get(phase, 0.0)
                + max(0.0, time.perf_counter() - started_at)
            )

        overlay_started = time.perf_counter()
        phase_started = time.perf_counter()
        model = cls(
            core.source_instances,
            core.facility_pools,
            core.rules,
            ghost_rect=ghost_rect,
            skip_power_coverage=core.skip_power_coverage,
            enable_symmetry_breaking=core.enable_symmetry_breaking,
            generic_io_requirements=core.generic_io_requirements,
            exact_required_pose_optional_counts=core.exact_required_pose_optional_counts,
            solve_mode="certified_exact",
            master_search_profile=normalized_master_search_profile,
        )
        model_shell_subphase_seconds = (
            dict(getattr(model, "_model_shell_subphase_seconds", {}))
            if model_shell_instrumentation_enabled
            else {}
        )
        model_shell_total_seconds = (
            float(getattr(model, "_model_shell_total_seconds", 0.0))
            if model_shell_instrumentation_enabled
            else 0.0
        )
        port_profile_cache_instrumentation = (
            copy.deepcopy(getattr(model, "_port_profile_cache_instrumentation", {}))
            if port_profile_cache_publication_enabled
            else {}
        )
        _record_outer_subphase(
            outer_exact_core_overlay_subphase_seconds,
            "model_shell_construction",
            phase_started,
        )
        phase_started = time.perf_counter()
        model.model = cp_model_from_proto(_clone_model_proto(core.proto))
        model._solver = None
        model._status = None
        model._last_solution = None
        model._built = False
        _record_outer_subphase(
            outer_exact_core_overlay_subphase_seconds,
            "model_proto_clone_bind",
            phase_started,
        )
        phase_started = time.perf_counter()
        model.build_stats = copy.deepcopy(core.build_stats)
        _record_outer_subphase(
            outer_exact_core_overlay_subphase_seconds,
            "build_stats_deepcopy",
            phase_started,
        )
        phase_started = time.perf_counter()
        model._mandatory_groups = copy.deepcopy(core.mandatory_groups)
        model._group_id_by_instance = dict(core.group_id_by_instance)
        candidate_precheck_artifacts = dict(core.candidate_precheck_artifacts)
        _record_outer_subphase(
            outer_exact_core_overlay_subphase_seconds,
            "mandatory_group_and_candidate_cache_copy",
            phase_started,
        )
        phase_started = time.perf_counter()
        cached_support_diagnostics = candidate_precheck_artifacts.get(
            "mandatory_support_diagnostics"
        )
        if isinstance(cached_support_diagnostics, Mapping):
            model._exact_candidate_mandatory_support_diagnostics_cache = {
                "unsupported_group_count": int(
                    cached_support_diagnostics.get("unsupported_group_count", 0)
                ),
                "empty_candidate_pool_group_count": int(
                    cached_support_diagnostics.get(
                        "empty_candidate_pool_group_count",
                        0,
                    )
                ),
                "groups": [
                    dict(entry)
                    for entry in list(cached_support_diagnostics.get("groups", []))
                ],
            }
            model._publish_exact_candidate_mandatory_support_diagnostics_summary(
                model._exact_candidate_mandatory_support_diagnostics_cache
            )
        _record_outer_subphase(
            outer_exact_core_overlay_subphase_seconds,
            "candidate_support_cache_restore",
            phase_started,
        )
        phase_started = time.perf_counter()
        cached_boundary_screen_spec = candidate_precheck_artifacts.get(
            "boundary_port_screen_spec"
        )
        if isinstance(cached_boundary_screen_spec, Mapping):
            model._boundary_storage_port_feasibility_screen_cache = dict(
                cached_boundary_screen_spec
            )
        _record_outer_subphase(
            outer_exact_core_overlay_subphase_seconds,
            "boundary_port_cache_restore",
            phase_started,
        )
        phase_started = time.perf_counter()
        model.build_stats.setdefault("global_valid_inequalities", {}).setdefault(
            "ghost_aware_via_pole_feasibility",
            {},
        )["enabled"] = bool(ghost_rect)
        _record_outer_subphase(
            outer_exact_core_overlay_subphase_seconds,
            "pre_ghost_stats_publish",
            phase_started,
        )
        ghost_started = time.perf_counter()
        search_strategy_rebuild: Dict[str, Any] = {
            "cleared_existing_strategy_count": 0,
            "rebuilt_strategy_count": 0,
            "rebuilt_after_ghost_overlay": False,
        }
        if str(core.master_representation).startswith("coordinate_exact_v"):
            if model._coordinate_delegate is None:
                raise RuntimeError("coordinate exact core requires a coordinate delegate")
            phase_started = time.perf_counter()
            model._coordinate_delegate.model = model.model
            model._coordinate_delegate.bind_from_core(core.coordinate_binding)
            _record_outer_subphase(
                ghost_overlay_subphase_seconds,
                "coordinate_delegate_bind_from_core",
                phase_started,
            )
            phase_started = time.perf_counter()
            model._coordinate_delegate._add_ghost_constraints()
            _record_outer_subphase(
                ghost_overlay_subphase_seconds,
                "ghost_constraint_add",
                phase_started,
            )
            phase_started = time.perf_counter()
            search_strategy_rebuild = _rebuild_exact_core_overlay_search_guidance(
                model,
                model._coordinate_delegate._add_search_guidance,
            )
            _record_outer_subphase(
                ghost_overlay_subphase_seconds,
                "search_guidance_rebuild",
                phase_started,
            )
            phase_started = time.perf_counter()
            model._coordinate_delegate._finalize_build_stats()
            _record_outer_subphase(
                ghost_overlay_subphase_seconds,
                "coordinate_delegate_finalize_build_stats",
                phase_started,
            )
            phase_started = time.perf_counter()
            model._mandatory_signature_count_vars = model._coordinate_delegate.mandatory_signature_count_vars
            model._required_optional_signature_count_vars = model._coordinate_delegate.required_optional_signature_count_vars
            model._residual_optional_signature_count_vars = (
                model._coordinate_delegate.residual_optional_signature_count_vars
            )
            model._power_pole_family_count_vars = model._coordinate_delegate.power_pole_family_count_vars
            _record_outer_subphase(
                ghost_overlay_subphase_seconds,
                "signature_var_sync",
                phase_started,
            )
        else:
            phase_started = time.perf_counter()
            model._bind_vars_from_exact_core(core)
            _record_outer_subphase(
                ghost_overlay_subphase_seconds,
                "legacy_bind_vars_from_exact_core",
                phase_started,
            )
            phase_started = time.perf_counter()
            model._populate_cell_occupancy_terms()
            _record_outer_subphase(
                ghost_overlay_subphase_seconds,
                "legacy_populate_cell_occupancy_terms",
                phase_started,
            )
            model._ghost_domains.clear()
            model.u_vars.clear()
            phase_started = time.perf_counter()
            model._add_ghost_rect_constraints()
            _record_outer_subphase(
                ghost_overlay_subphase_seconds,
                "legacy_ghost_rect_constraint_add",
                phase_started,
            )
            phase_started = time.perf_counter()
            search_strategy_rebuild = _rebuild_exact_core_overlay_search_guidance(
                model,
                model._add_search_guidance,
            )
            _record_outer_subphase(
                ghost_overlay_subphase_seconds,
                "search_guidance_rebuild",
                phase_started,
            )
        overlay_build_seconds = time.perf_counter() - overlay_started
        ghost_constraint_seconds = time.perf_counter() - ghost_started
        exact_core_reuse_stats = {
            "used": True,
            "core_proto_variables": len(core.proto.variables),
            "core_proto_constraints": len(core.proto.constraints),
            "overlay_build_seconds": overlay_build_seconds,
            "ghost_constraint_seconds": ghost_constraint_seconds,
            "search_guidance_rebuilt_after_ghost_overlay": bool(
                search_strategy_rebuild.get("rebuilt_after_ghost_overlay", False)
            ),
            "cleared_existing_search_strategy_count": int(
                search_strategy_rebuild.get("cleared_existing_strategy_count", 0)
            ),
            "rebuilt_search_strategy_count": int(
                search_strategy_rebuild.get("rebuilt_strategy_count", 0)
            ),
        }
        if outer_overlay_instrumentation_enabled:
            outer_residual_seconds = float(max(0.0, overlay_build_seconds - ghost_constraint_seconds))
            outer_subphase_total_seconds = float(
                sum(max(0.0, value) for value in outer_exact_core_overlay_subphase_seconds.values())
            )
            residual_overlay_instrumentation = {
                "enabled": True,
                "profile_validation_seconds": float(max(0.0, profile_validation_seconds)),
                "outer_exact_core_overlay_residual_seconds": outer_residual_seconds,
                "outer_exact_core_overlay_subphase_seconds": dict(
                    sorted(outer_exact_core_overlay_subphase_seconds.items())
                ),
                "outer_exact_core_overlay_subphase_total_seconds": outer_subphase_total_seconds,
                "outer_exact_core_overlay_unattributed_seconds": float(
                    max(0.0, outer_residual_seconds - outer_subphase_total_seconds)
                ),
                "ghost_overlay_subphase_seconds": dict(
                    sorted(ghost_overlay_subphase_seconds.items())
                ),
                "overlay_build_seconds": float(overlay_build_seconds),
                "ghost_constraint_seconds": float(ghost_constraint_seconds),
                "search_guidance_rebuilt_after_ghost_overlay": bool(
                    search_strategy_rebuild.get("rebuilt_after_ghost_overlay", False)
                ),
            }
            if model_shell_instrumentation_enabled:
                model_shell_subphase_total_seconds = float(
                    sum(max(0.0, value) for value in model_shell_subphase_seconds.values())
                )
                residual_overlay_instrumentation.update(
                    {
                        "model_shell_instrumentation_enabled": True,
                        "model_shell_subphase_seconds": dict(
                            sorted(model_shell_subphase_seconds.items())
                        ),
                        "model_shell_subphase_total_seconds": model_shell_subphase_total_seconds,
                        "model_shell_total_seconds": float(max(0.0, model_shell_total_seconds)),
                        "model_shell_unattributed_seconds": float(
                            max(0.0, model_shell_total_seconds - model_shell_subphase_total_seconds)
                        ),
                    }
                )
            if port_profile_cache_publication_enabled:
                residual_overlay_instrumentation[
                    "port_profile_cache_instrumentation"
                ] = copy.deepcopy(port_profile_cache_instrumentation)
            exact_core_reuse_stats[
                "residual_overlay_instrumentation"
            ] = residual_overlay_instrumentation
        model.build_stats["exact_core_reuse"] = exact_core_reuse_stats
        if precomputed_boundary_port_feasibility is not None:
            model._exact_candidate_boundary_port_feasibility_cache = (
                model._normalize_exact_candidate_boundary_port_feasibility_payload(
                    precomputed_boundary_port_feasibility
                )
            )
            model._publish_exact_candidate_boundary_port_feasibility_summary(
                model._exact_candidate_boundary_port_feasibility_cache
            )
        model._built = True
        return model

    def _infer_optional_caps(self) -> Dict[str, int]:
        counts: Dict[str, int] = defaultdict(int)
        for inst in self.source_instances:
            if bool(inst.get("is_mandatory")):
                continue
            tpl = str(inst.get("facility_type", ""))
            if tpl in POSE_LEVEL_OPTIONAL_TEMPLATES:
                counts[tpl] += 1
        return dict(counts)

    def _build_mandatory_groups(self) -> None:
        grouped: DefaultDict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for inst in self.instances:
            tpl = str(inst["facility_type"])
            operation_type = str(inst.get("operation_type", ""))
            grouped[(tpl, operation_type)].append(inst)

        self._mandatory_groups.clear()
        self._group_id_by_instance.clear()
        for group_index, ((tpl, operation_type), members) in enumerate(sorted(grouped.items())):
            members = sorted(members, key=lambda item: str(item["instance_id"]))
            group_id = f"group::{tpl}::{operation_type}::{group_index}"
            group = {
                "group_id": group_id,
                "facility_type": tpl,
                "operation_type": operation_type,
                "count": len(members),
                "instance_ids": [str(item["instance_id"]) for item in members],
            }
            self._mandatory_groups.append(group)
            for instance_id in group["instance_ids"]:
                self._group_id_by_instance[instance_id] = group_id

        self.build_stats["grouped_encoding"] = {
            "mandatory_instances": len(self.instances),
            "mandatory_groups": len(self._mandatory_groups),
        }

    def _pose_mode_token(self, pose: Mapping[str, Any]) -> ModeToken:
        params = dict(pose.get("pose_params", {}))
        return (str(params.get("orientation", "")), str(params.get("port_mode", "")))

    def _update_exact_precompute_profile(self, **updates: Any) -> None:
        self._exact_precompute_profile.update(updates)
        self.build_stats["exact_precompute_profile"] = dict(self._exact_precompute_profile)

    def _intern_local_shape_token(self, tpl: str, local_shape: LocalPoseShape) -> int:
        tpl = str(tpl)
        token_by_shape = self._local_shape_token_by_template_shape.setdefault(tpl, {})
        cached = token_by_shape.get(local_shape)
        if cached is not None:
            return int(cached)

        token = int(len(token_by_shape))
        token_by_shape[local_shape] = token
        self._local_shape_by_template_token.setdefault(tpl, {})[token] = local_shape
        return token

    def _rectangle_variant_for_local_shape(
        self,
        local_shape: LocalPoseShape,
    ) -> Optional[_LocalRectangleVariant]:
        if not local_shape:
            return None
        xs = sorted({int(cell_x) for cell_x, _ in local_shape})
        ys = sorted({int(cell_y) for _, cell_y in local_shape})
        if not xs or not ys:
            return None
        min_x = int(min(xs))
        max_x = int(max(xs))
        min_y = int(min(ys))
        max_y = int(max(ys))
        expected = {
            (int(cell_x), int(cell_y))
            for cell_x in range(min_x, max_x + 1)
            for cell_y in range(min_y, max_y + 1)
        }
        if expected != set(local_shape):
            return None
        return _LocalRectangleVariant(
            min_x=min_x,
            min_y=min_y,
            max_x=max_x,
            max_y=max_y,
            width=int(max_x - min_x + 1),
            height=int(max_y - min_y + 1),
        )

    def _ensure_local_rectangle_variants(
        self,
        tpl: str,
    ) -> Dict[int, Optional[_LocalRectangleVariant]]:
        tpl = str(tpl)
        cached = self._local_rectangle_variant_by_template_token.get(tpl)
        if cached is not None:
            return cached
        variants: Dict[int, Optional[_LocalRectangleVariant]] = {}
        for token, local_shape in sorted(self._local_shape_by_template_token.get(tpl, {}).items()):
            variants[int(token)] = self._rectangle_variant_for_local_shape(local_shape)
        self._local_rectangle_variant_by_template_token[tpl] = variants
        return variants

    def _clone_signature_bucket_payload(
        self,
        payload: Sequence[Mapping[str, Any]],
    ) -> List[Dict[str, Any]]:
        return [
            {
                "bucket_id": str(bucket["bucket_id"]),
                "signature": bucket["signature"],
                "pose_indices": list(bucket.get("pose_indices", [])),
            }
            for bucket in payload
        ]

    def _power_pole_shell_pair(self, pose_idx: int) -> Optional[ShellPair]:
        return self._power_pole_shell_pair_by_pose_idx.get(int(pose_idx))

    def _store_local_power_capacity_compact_signature_classes(
        self,
        tpl: str,
        compact_signature_by_pole: Mapping[int, CompactLocalCapacitySignature],
    ) -> Dict[CompactLocalCapacitySignature, List[int]]:
        tpl = str(tpl)
        grouped_pose_indices_by_compact: DefaultDict[
            CompactLocalCapacitySignature,
            List[int],
        ] = defaultdict(list)
        for pole_idx, compact_signature in compact_signature_by_pole.items():
            grouped_pose_indices_by_compact[tuple(compact_signature)].append(int(pole_idx))

        grouped_pose_indices = {
            compact_signature: sorted(
                pose_indices,
                key=lambda idx: self._pose_sort_key("power_pole", int(idx)),
            )
            for compact_signature, pose_indices in sorted(grouped_pose_indices_by_compact.items())
        }
        shell_pair_compact_signatures: Dict[
            ShellPair,
            Tuple[CompactLocalCapacitySignature, ...],
        ] = {}
        for shell_pair, pose_indices in sorted(self._power_pole_pose_indices_by_shell_pair.items()):
            shell_pair_compact_signatures[shell_pair] = tuple(
                sorted(
                    {
                        tuple(compact_signature_by_pole.get(int(pole_idx), tuple()))
                        for pole_idx in pose_indices
                    }
                )
            )

        self._compact_local_power_capacity_signature_by_template_pole[tpl] = dict(
            compact_signature_by_pole
        )
        self._power_pole_pose_indices_by_template_compact_capacity_signature[tpl] = (
            grouped_pose_indices
        )
        self._power_pole_compact_capacity_signatures_by_template_shell_pair[tpl] = (
            shell_pair_compact_signatures
        )
        self._legacy_local_power_capacity_signature_by_template_compact_signature.setdefault(
            tpl,
            {},
        )
        self._compact_local_power_capacity_signature_by_template_legacy_signature.setdefault(
            tpl,
            {},
        )
        return grouped_pose_indices

    def _index_pools(self) -> None:
        """Build indices（构建索引） for occupancy, power and exploratory port heuristics."""

        port_profile_cache_instrumentation_enabled = (
            resolve_ghost_signature_bucket_port_profile_cache_instrumentation_enabled()
        )
        powered_support_coverer_instrumentation_enabled = (
            resolve_ghost_signature_bucket_powered_support_coverer_instrumentation_enabled()
        )
        compact_item_accumulation_optimization_enabled = (
            resolve_ghost_signature_bucket_powered_support_compact_item_accumulation_optimization_enabled()
        )
        compact_item_batched_counter_optimization_enabled = (
            resolve_ghost_signature_bucket_powered_support_compact_item_batched_counter_optimization_enabled()
        )
        compact_item_detail_instrumentation_enabled = (
            resolve_ghost_signature_bucket_powered_support_compact_item_detail_instrumentation_enabled()
        )
        compact_item_detail_instrumentation_active = (
            powered_support_coverer_instrumentation_enabled
            and compact_item_detail_instrumentation_enabled
        )
        port_profile_cache_publication_enabled = (
            port_profile_cache_instrumentation_enabled
            or powered_support_coverer_instrumentation_enabled
        )
        if (
            not port_profile_cache_publication_enabled
            and hasattr(self, "_port_profile_cache_instrumentation")
        ):
            delattr(self, "_port_profile_cache_instrumentation")
        instrumentation_started = time.perf_counter()
        instrumentation_phase_started = instrumentation_started
        port_profile_cache_phase_seconds: Dict[str, float] = {}
        port_profile_cache_totals: Dict[str, int] = {
            "template_count": 0,
            "pose_count": 0,
            "powered_template_count": 0,
            "power_pole_count": 0,
            "power_pole_cells_scanned": 0,
            "power_pole_coverage_cells_scanned": 0,
            "pose_cells_scanned": 0,
            "port_cells_scanned": 0,
            "front_cells_scanned": 0,
            "local_signature_cells_scanned": 0,
            "anchor_shape_group_count": 0,
            "support_coverer_scan_count": 0,
            "support_coverer_candidate_count": 0,
            "compact_capacity_signature_item_count": 0,
        }
        port_profile_cache_top_entries: List[Dict[str, Any]] = []
        powered_support_coverer_phase_seconds: Dict[str, float] = {}
        powered_support_coverer_totals: Dict[str, int] = {
            "template_count": 0,
            "group_count": 0,
            "pose_count": 0,
            "representative_cell_count": 0,
            "candidate_coverer_count": 0,
            "filtered_coverer_count": 0,
            "rejected_coverer_count": 0,
            "power_index_assignment_count": 0,
            "compact_item_update_count": 0,
        }
        if compact_item_accumulation_optimization_enabled:
            powered_support_coverer_totals.update(
                {
                    "compact_item_optimization_attempts": 0,
                    "compact_item_optimization_used": 0,
                    "compact_item_optimization_fallbacks": 0,
                    "compact_item_optimized_update_count": 0,
                    "compact_item_fallback_update_count": 0,
                }
            )
        if compact_item_batched_counter_optimization_enabled:
            powered_support_coverer_totals.update(
                {
                    "compact_item_batched_counter_attempts": 0,
                    "compact_item_batched_counter_used": 0,
                    "compact_item_batched_counter_fallbacks": 0,
                    "compact_item_batched_counter_local_update_count": 0,
                    "compact_item_batched_counter_fallback_update_count": 0,
                    "compact_item_batched_counter_merge_update_count": 0,
                    "compact_item_batched_counter_unique_item_count": 0,
                }
            )
        compact_item_detail_phase_seconds: Dict[str, float] = {}
        compact_item_detail_totals: Dict[str, int] = {}
        compact_item_detail_per_template: Dict[str, Dict[str, Any]] = {}
        compact_item_detail_top_entries: List[Dict[str, Any]] = []
        if compact_item_detail_instrumentation_active:
            compact_item_detail_totals.update(
                {
                    "group_count": 0,
                    "key_build_count": 0,
                    "local_counter_update_count": 0,
                    "merge_update_count": 0,
                    "unique_item_count": 0,
                    "signature_storage_item_count": 0,
                }
            )
        powered_support_coverer_top_entries: List[Dict[str, Any]] = []

        def _record_port_profile_cache_phase(phase: str, started_at: float) -> float:
            now = time.perf_counter()
            if port_profile_cache_instrumentation_enabled:
                port_profile_cache_phase_seconds[phase] = float(
                    port_profile_cache_phase_seconds.get(phase, 0.0)
                    + max(0.0, now - started_at)
                )
            return now

        def _add_port_profile_cache_top_entry(entry: Mapping[str, Any]) -> None:
            if port_profile_cache_instrumentation_enabled:
                port_profile_cache_top_entries.append(dict(entry))

        def _record_powered_support_coverer_phase(
            phase: str,
            started_at: float,
        ) -> float:
            now = time.perf_counter()
            if powered_support_coverer_instrumentation_enabled:
                powered_support_coverer_phase_seconds[phase] = float(
                    powered_support_coverer_phase_seconds.get(phase, 0.0)
                    + max(0.0, now - started_at)
                )
            return now

        def _add_powered_support_coverer_top_entry(
            entry: Mapping[str, Any],
        ) -> None:
            if powered_support_coverer_instrumentation_enabled:
                powered_support_coverer_top_entries.append(dict(entry))

        def _record_compact_item_detail_phase(
            phase: str,
            elapsed_seconds: float,
        ) -> None:
            if compact_item_detail_instrumentation_active:
                compact_item_detail_phase_seconds[phase] = float(
                    compact_item_detail_phase_seconds.get(phase, 0.0)
                    + max(0.0, float(elapsed_seconds))
                )

        def _compact_item_detail_template_stats(tpl_name: str) -> Dict[str, Any]:
            stats = compact_item_detail_per_template.setdefault(
                str(tpl_name),
                {
                    "template": str(tpl_name),
                    "group_count": 0,
                    "key_build_count": 0,
                    "local_counter_update_count": 0,
                    "merge_update_count": 0,
                    "unique_item_count": 0,
                    "signature_storage_item_count": 0,
                    "key_build_seconds": 0.0,
                    "local_counter_update_seconds": 0.0,
                    "merge_fanout_seconds": 0.0,
                    "signature_storage_seconds": 0.0,
                },
            )
            return stats

        def _add_compact_item_detail_top_entry(
            entry: Mapping[str, Any],
        ) -> None:
            if compact_item_detail_instrumentation_active:
                compact_item_detail_top_entries.append(dict(entry))

        self._covering_pose_indices = {}
        self._heuristic_port_fronts = {}
        self._power_coverers_by_template_pose = {}
        self._pose_cells_by_template_pose = {}
        self._pose_greedy_blocking_cells_by_template_pose = {}
        self._pose_anchor_by_template_pose = {}
        self._pose_local_cells_by_template_pose = {}
        self._pose_local_fronts_by_template_pose = {}
        self._pose_local_power_coverage_by_template_pose = {}
        self._pose_local_signature_by_template_pose = {}
        self._power_supported_pose_indices_by_template_pole = {}
        self._power_supported_pose_bucket_records_by_template = {}
        self._power_pole_shell_pair_by_pose_idx = {}
        self._power_pole_pose_indices_by_shell_pair = {}
        self._local_power_capacity_signature_by_template_pole = {}
        self._compact_local_power_capacity_signature_by_template_pole = {}
        self._power_pole_pose_indices_by_template_capacity_signature = {}
        self._power_pole_pose_indices_by_template_compact_capacity_signature = {}
        self._power_pole_compact_capacity_signatures_by_template_shell_pair = {}
        self._fully_materialized_local_power_capacity_signature_classes_by_template = set()
        self._legacy_local_power_capacity_signature_by_template_compact_signature = {}
        self._compact_local_power_capacity_signature_by_template_legacy_signature = {}
        self._candidate_pose_indices_by_template = {}

        cell_to_poles: DefaultDict[Tuple[int, int], Set[int]] = defaultdict(set)
        power_pole_cells: Dict[int, FrozenSet[Tuple[int, int]]] = {}
        power_pole_anchors: Dict[int, Tuple[int, int]] = {}
        instrumentation_phase_started = _record_port_profile_cache_phase(
            "index_container_initialization",
            instrumentation_phase_started,
        )

        power_pole_phase_started = instrumentation_phase_started
        for pole_idx, pose in enumerate(self.facility_pools.get("power_pole", [])):
            anchor = dict(pose.get("anchor", {}))
            anchor_xy = (int(anchor.get("x", 0)), int(anchor.get("y", 0)))
            pole_cells = frozenset((int(cell[0]), int(cell[1])) for cell in pose.get("occupied_cells", []))
            local_cells = tuple(
                sorted((cell_x - anchor_xy[0], cell_y - anchor_xy[1]) for cell_x, cell_y in pole_cells)
            )
            local_coverage = tuple(
                sorted(
                    (
                        int(cell[0]) - anchor_xy[0],
                        int(cell[1]) - anchor_xy[1],
                    )
                    for cell in pose.get("power_coverage_cells", []) or []
                )
            )
            power_pole_cells[pole_idx] = pole_cells
            power_pole_anchors[pole_idx] = anchor_xy
            if port_profile_cache_instrumentation_enabled:
                port_profile_cache_totals["power_pole_cells_scanned"] += int(
                    len(pole_cells)
                )
                port_profile_cache_totals["power_pole_coverage_cells_scanned"] += int(
                    len(list(pose.get("power_coverage_cells", []) or []))
                )
            self._pose_anchor_by_template_pose.setdefault("power_pole", {})[int(pole_idx)] = anchor_xy
            self._pose_cells_by_template_pose.setdefault("power_pole", {})[int(pole_idx)] = pole_cells
            self._pose_greedy_blocking_cells_by_template_pose.setdefault("power_pole", {})[
                int(pole_idx)
            ] = pole_cells
            self._pose_local_cells_by_template_pose.setdefault("power_pole", {})[int(pole_idx)] = local_cells
            self._pose_local_fronts_by_template_pose.setdefault("power_pole", {})[int(pole_idx)] = tuple()
            self._pose_local_power_coverage_by_template_pose.setdefault("power_pole", {})[int(pole_idx)] = local_coverage
            self._pose_local_shape_token_by_template_pose.setdefault("power_pole", {})[
                int(pole_idx)
            ] = self._intern_local_shape_token("power_pole", local_cells)
            self._pose_local_signature_by_template_pose.setdefault("power_pole", {})[int(pole_idx)] = (
                local_cells,
                tuple(),
                local_coverage,
                0,
            )
            for cell in pose.get("power_coverage_cells", []) or []:
                cell_to_poles[(int(cell[0]), int(cell[1]))].add(pole_idx)
        power_pole_count = int(len(power_pole_anchors))

        if power_pole_anchors:
            x_values = [coords[0] for coords in power_pole_anchors.values()]
            y_values = [coords[1] for coords in power_pole_anchors.values()]
            x_min, x_max = min(x_values), max(x_values)
            y_min, y_max = min(y_values), max(y_values)
            for pole_idx, (anchor_x, anchor_y) in power_pole_anchors.items():
                dx = min(int(anchor_x - x_min), int(x_max - anchor_x))
                dy = min(int(anchor_y - y_min), int(y_max - anchor_y))
                shell_pair = tuple(sorted((int(dx), int(dy))))
                self._power_pole_shell_pair_by_pose_idx[int(pole_idx)] = shell_pair
                self._power_pole_pose_indices_by_shell_pair.setdefault(shell_pair, []).append(int(pole_idx))
            for shell_pair, pose_indices in list(self._power_pole_pose_indices_by_shell_pair.items()):
                self._power_pole_pose_indices_by_shell_pair[shell_pair] = sorted(
                    pose_indices,
                    key=lambda idx: self._pose_sort_key("power_pole", int(idx)),
                )

        instrumentation_phase_started = _record_port_profile_cache_phase(
            "power_pole_index_build",
            power_pole_phase_started,
        )

        for tpl, pool in self.facility_pools.items():
            template_phase_started = time.perf_counter()
            template_pose_cache_seconds = 0.0
            template_port_front_seconds = 0.0
            template_local_signature_seconds = 0.0
            template_powered_grouping_seconds = 0.0
            template_pose_count = int(len(pool))
            if port_profile_cache_instrumentation_enabled:
                port_profile_cache_totals["template_count"] += 1
                port_profile_cache_totals["pose_count"] += template_pose_count
                if tpl in self._powered_templates and tpl != "power_pole":
                    port_profile_cache_totals["powered_template_count"] += 1
            cover_index: DefaultDict[Tuple[int, int], List[int]] = defaultdict(list)
            front_index: Dict[int, Optional[List[Tuple[int, int]]]] = {}
            power_index: Dict[int, List[int]] = {}
            pose_cells_index: Dict[int, FrozenSet[Tuple[int, int]]] = {}
            compact_item_counts_by_pole: DefaultDict[
                int,
                DefaultDict[CompactLocalCapacityItem, int],
            ] = defaultdict(lambda: defaultdict(int))
            compact_item_batched_counts_by_pole: DefaultDict[
                int,
                Dict[CompactLocalCapacityItem, int],
            ] = defaultdict(dict)
            anchor_shape_pose_indices: DefaultDict[Tuple[Tuple[int, int], int], List[int]] = defaultdict(list)
            support_bucket_records: List[_PowerSupportBucketRecord] = []

            for pose_idx, pose in enumerate(pool):
                pose_cache_started = time.perf_counter()
                anchor = dict(pose.get("anchor", {}))
                anchor_xy = (int(anchor.get("x", 0)), int(anchor.get("y", 0)))
                pose_cells = frozenset((int(cell[0]), int(cell[1])) for cell in pose.get("occupied_cells", []))
                port_cells = frozenset(
                    (int(port["x"]), int(port["y"]))
                    for port in list(pose.get("input_port_cells", []))
                    + list(pose.get("output_port_cells", []))
                )
                greedy_blocking_cells = (
                    frozenset(set(pose_cells) | set(port_cells))
                    if str(tpl) == "boundary_storage_port"
                    else pose_cells
                )
                local_cells = tuple(
                    sorted((cell_x - anchor_xy[0], cell_y - anchor_xy[1]) for cell_x, cell_y in pose_cells)
                )
                pose_cells_index[pose_idx] = pose_cells
                self._pose_greedy_blocking_cells_by_template_pose.setdefault(str(tpl), {})[
                    int(pose_idx)
                ] = greedy_blocking_cells
                self._pose_anchor_by_template_pose.setdefault(str(tpl), {})[int(pose_idx)] = anchor_xy
                self._pose_local_cells_by_template_pose.setdefault(str(tpl), {})[int(pose_idx)] = local_cells
                shape_token = self._intern_local_shape_token(str(tpl), local_cells)
                self._pose_local_shape_token_by_template_pose.setdefault(str(tpl), {})[
                    int(pose_idx)
                ] = int(shape_token)
                for cell in pose_cells:
                    cover_index[cell].append(pose_idx)
                pose_cache_finished = time.perf_counter()
                if port_profile_cache_instrumentation_enabled:
                    template_pose_cache_seconds += max(
                        0.0,
                        pose_cache_finished - pose_cache_started,
                    )
                    port_profile_cache_totals["pose_cells_scanned"] += int(
                        len(pose_cells)
                    )
                    port_profile_cache_totals["port_cells_scanned"] += int(
                        len(port_cells)
                    )

                port_front_started = time.perf_counter()
                unique_fronts: List[Tuple[int, int]] = []
                seen_fronts: Set[Tuple[int, int]] = set()
                invalid_front = False
                for port in list(pose.get("input_port_cells", [])) + list(pose.get("output_port_cells", [])):
                    px = int(port["x"])
                    py = int(port["y"])
                    direction = str(port["dir"])
                    if direction not in DIR_DELTA:
                        continue
                    dx, dy = DIR_DELTA[direction]
                    fx, fy = px + dx, py + dy
                    if not (0 <= fx < self.grid_w and 0 <= fy < self.grid_h):
                        invalid_front = True
                        break
                    if (fx, fy) not in seen_fronts:
                        seen_fronts.add((fx, fy))
                        unique_fronts.append((fx, fy))
                front_index[pose_idx] = None if invalid_front else unique_fronts
                local_fronts = tuple(
                    sorted(
                        (cell_x - anchor_xy[0], cell_y - anchor_xy[1])
                        for cell_x, cell_y in (unique_fronts if not invalid_front else [])
                    )
                )
                port_front_finished = time.perf_counter()
                if port_profile_cache_instrumentation_enabled:
                    template_port_front_seconds += max(
                        0.0,
                        port_front_finished - port_front_started,
                    )
                    port_profile_cache_totals["front_cells_scanned"] += int(
                        len(list(pose.get("input_port_cells", [])))
                        + len(list(pose.get("output_port_cells", [])))
                    )

                local_signature_started = time.perf_counter()
                local_coverage = tuple(
                    sorted(
                        (
                            int(cell[0]) - anchor_xy[0],
                            int(cell[1]) - anchor_xy[1],
                        )
                        for cell in pose.get("power_coverage_cells", []) or []
                    )
                )
                self._pose_local_fronts_by_template_pose.setdefault(str(tpl), {})[int(pose_idx)] = local_fronts
                self._pose_local_power_coverage_by_template_pose.setdefault(str(tpl), {})[int(pose_idx)] = local_coverage
                self._pose_local_signature_by_template_pose.setdefault(str(tpl), {})[int(pose_idx)] = (
                    local_cells,
                    local_fronts,
                    local_coverage,
                    1 if invalid_front else 0,
                )
                local_signature_finished = time.perf_counter()
                if port_profile_cache_instrumentation_enabled:
                    template_local_signature_seconds += max(
                        0.0,
                        local_signature_finished - local_signature_started,
                    )
                    port_profile_cache_totals["local_signature_cells_scanned"] += int(
                        len(local_cells) + len(local_fronts) + len(local_coverage)
                    )

                if tpl in self._powered_templates and tpl != "power_pole":
                    powered_grouping_started = time.perf_counter()
                    anchor_shape_pose_indices[(anchor_xy, int(shape_token))].append(int(pose_idx))
                    if port_profile_cache_instrumentation_enabled:
                        template_powered_grouping_seconds += max(
                            0.0,
                            time.perf_counter() - powered_grouping_started,
                        )

            if port_profile_cache_instrumentation_enabled:
                port_profile_cache_phase_seconds[
                    "per_template_pose_cache_build"
                ] = float(
                    port_profile_cache_phase_seconds.get(
                        "per_template_pose_cache_build",
                        0.0,
                    )
                    + max(0.0, template_pose_cache_seconds)
                )
                port_profile_cache_phase_seconds["port_front_extraction"] = float(
                    port_profile_cache_phase_seconds.get("port_front_extraction", 0.0)
                    + max(0.0, template_port_front_seconds)
                )
                port_profile_cache_phase_seconds["local_signature_build"] = float(
                    port_profile_cache_phase_seconds.get("local_signature_build", 0.0)
                    + max(0.0, template_local_signature_seconds)
                )
                port_profile_cache_phase_seconds[
                    "powered_anchor_shape_grouping"
                ] = float(
                    port_profile_cache_phase_seconds.get(
                        "powered_anchor_shape_grouping",
                        0.0,
                    )
                    + max(0.0, template_powered_grouping_seconds)
                )
                _add_port_profile_cache_top_entry(
                    {
                        "kind": "template_pose_cache",
                        "template": str(tpl),
                        "pose_count": template_pose_count,
                        "elapsed_seconds": float(
                            max(0.0, time.perf_counter() - template_phase_started)
                        ),
                    }
                )

            if tpl in self._powered_templates and tpl != "power_pole":
                support_coverer_phase_started = time.perf_counter()
                support_coverer_scan_count = 0
                if powered_support_coverer_instrumentation_enabled:
                    powered_support_coverer_totals["template_count"] += 1
                for (anchor_xy, shape_token), pose_indices in anchor_shape_pose_indices.items():
                    support_group_started = time.perf_counter()
                    representative_pose_cells = pose_cells_index[int(pose_indices[0])]
                    coverers: Set[int] = set()
                    coverer_union_started = time.perf_counter()
                    for cell in representative_pose_cells:
                        coverers.update(cell_to_poles.get(cell, set()))
                    _record_powered_support_coverer_phase(
                        "coverer_union_collection",
                        coverer_union_started,
                    )
                    support_coverer_scan_count += int(len(representative_pose_cells))
                    disjoint_filtering_started = time.perf_counter()
                    filtered_coverers = tuple(
                        sorted(
                            pole_idx
                            for pole_idx in coverers
                            if representative_pose_cells.isdisjoint(
                                power_pole_cells.get(pole_idx, frozenset())
                            )
                        )
                    )
                    _record_powered_support_coverer_phase(
                        "disjoint_filtering",
                        disjoint_filtering_started,
                    )
                    pose_indices_tuple = tuple(int(pose_idx) for pose_idx in pose_indices)
                    if port_profile_cache_instrumentation_enabled:
                        port_profile_cache_totals[
                            "support_coverer_candidate_count"
                        ] += int(len(coverers))
                        _add_port_profile_cache_top_entry(
                            {
                                "kind": "powered_support_coverer_group",
                                "template": str(tpl),
                                "anchor": [int(anchor_xy[0]), int(anchor_xy[1])],
                                "shape_token": int(shape_token),
                                "pose_count": int(len(pose_indices_tuple)),
                                "coverer_count": int(len(filtered_coverers)),
                                "scan_count": int(len(representative_pose_cells)),
                                "elapsed_seconds": float(
                                    max(
                                        0.0,
                                        time.perf_counter() - support_group_started,
                                    )
                                ),
                            }
                        )
                    support_bucket_records.append(
                        _PowerSupportBucketRecord(
                            pose_indices=pose_indices_tuple,
                            coverers=filtered_coverers,
                        )
                    )
                    power_index_started = time.perf_counter()
                    for pose_idx in pose_indices_tuple:
                        power_index[int(pose_idx)] = list(filtered_coverers)
                    _record_powered_support_coverer_phase(
                        "power_index_expansion",
                        power_index_started,
                    )
                    compact_item_started = time.perf_counter()
                    compact_item_accumulation_mode = "legacy"
                    compact_item_detail_key_build_seconds = 0.0
                    compact_item_detail_local_update_seconds = 0.0
                    compact_item_detail_local_update_count = 0
                    compact_item_detail_group_items: Optional[
                        Set[Tuple[int, CompactLocalCapacityItem]]
                    ] = set() if compact_item_detail_instrumentation_active else None
                    compact_item_can_use_anchor_delta = all(
                        int(pole_idx) in power_pole_anchors
                        for pole_idx in filtered_coverers
                    )
                    if (
                        compact_item_batched_counter_optimization_enabled
                        and compact_item_can_use_anchor_delta
                    ):
                        compact_item_accumulation_mode = "batched_counter"
                        anchor_x_int = int(anchor_xy[0])
                        anchor_y_int = int(anchor_xy[1])
                        shape_token_int = int(shape_token)
                        pose_multiplicity = int(len(pose_indices_tuple))
                        anchors_by_pole = power_pole_anchors
                        batch_counts_by_pole = compact_item_batched_counts_by_pole
                        for pole_idx in filtered_coverers:
                            pole_idx_int = int(pole_idx)
                            pole_anchor_x, pole_anchor_y = anchors_by_pole[
                                pole_idx_int
                            ]
                            detail_key_started = (
                                time.perf_counter()
                                if compact_item_detail_instrumentation_active
                                else 0.0
                            )
                            compact_item = (
                                anchor_x_int - int(pole_anchor_x),
                                anchor_y_int - int(pole_anchor_y),
                                shape_token_int,
                            )
                            if compact_item_detail_instrumentation_active:
                                compact_item_detail_key_build_seconds += max(
                                    0.0,
                                    time.perf_counter() - detail_key_started,
                                )
                                assert compact_item_detail_group_items is not None
                                compact_item_detail_group_items.add(
                                    (pole_idx_int, compact_item)
                                )
                            pole_batch_counts = batch_counts_by_pole[pole_idx_int]
                            detail_update_started = (
                                time.perf_counter()
                                if compact_item_detail_instrumentation_active
                                else 0.0
                            )
                            pole_batch_counts[compact_item] = int(
                                pole_batch_counts.get(compact_item, 0)
                            ) + pose_multiplicity
                            if compact_item_detail_instrumentation_active:
                                compact_item_detail_local_update_seconds += max(
                                    0.0,
                                    time.perf_counter() - detail_update_started,
                                )
                                compact_item_detail_local_update_count += 1
                    elif (
                        compact_item_accumulation_optimization_enabled
                        and compact_item_can_use_anchor_delta
                    ):
                        compact_item_accumulation_mode = "optimized"
                        anchor_x_int = int(anchor_xy[0])
                        anchor_y_int = int(anchor_xy[1])
                        shape_token_int = int(shape_token)
                        pose_multiplicity = int(len(pose_indices_tuple))
                        counts_by_pole = compact_item_counts_by_pole
                        anchors_by_pole = power_pole_anchors
                        for pole_idx in filtered_coverers:
                            pole_idx_int = int(pole_idx)
                            pole_anchor_x, pole_anchor_y = anchors_by_pole[
                                pole_idx_int
                            ]
                            detail_key_started = (
                                time.perf_counter()
                                if compact_item_detail_instrumentation_active
                                else 0.0
                            )
                            compact_item = (
                                anchor_x_int - int(pole_anchor_x),
                                anchor_y_int - int(pole_anchor_y),
                                shape_token_int,
                            )
                            if compact_item_detail_instrumentation_active:
                                compact_item_detail_key_build_seconds += max(
                                    0.0,
                                    time.perf_counter() - detail_key_started,
                                )
                                assert compact_item_detail_group_items is not None
                                compact_item_detail_group_items.add(
                                    (pole_idx_int, compact_item)
                                )
                            detail_update_started = (
                                time.perf_counter()
                                if compact_item_detail_instrumentation_active
                                else 0.0
                            )
                            counts_by_pole[pole_idx_int][compact_item] += (
                                pose_multiplicity
                            )
                            if compact_item_detail_instrumentation_active:
                                compact_item_detail_local_update_seconds += max(
                                    0.0,
                                    time.perf_counter() - detail_update_started,
                                )
                                compact_item_detail_local_update_count += 1
                    else:
                        if compact_item_batched_counter_optimization_enabled:
                            compact_item_accumulation_mode = (
                                "batched_counter_fallback_missing_power_pole_anchor"
                            )
                        elif compact_item_accumulation_optimization_enabled:
                            compact_item_accumulation_mode = (
                                "fallback_missing_power_pole_anchor"
                            )
                        for pole_idx in filtered_coverers:
                            pole_anchor_x, pole_anchor_y = power_pole_anchors.get(
                                int(pole_idx),
                                (0, 0),
                            )
                            pole_idx_int = int(pole_idx)
                            detail_key_started = (
                                time.perf_counter()
                                if compact_item_detail_instrumentation_active
                                else 0.0
                            )
                            compact_item = (
                                int(anchor_xy[0]) - int(pole_anchor_x),
                                int(anchor_xy[1]) - int(pole_anchor_y),
                                int(shape_token),
                            )
                            if compact_item_detail_instrumentation_active:
                                compact_item_detail_key_build_seconds += max(
                                    0.0,
                                    time.perf_counter() - detail_key_started,
                                )
                                assert compact_item_detail_group_items is not None
                                compact_item_detail_group_items.add(
                                    (pole_idx_int, compact_item)
                                )
                            detail_update_started = (
                                time.perf_counter()
                                if compact_item_detail_instrumentation_active
                                else 0.0
                            )
                            compact_item_counts_by_pole[pole_idx_int][
                                compact_item
                            ] += int(len(pose_indices_tuple))
                            if compact_item_detail_instrumentation_active:
                                compact_item_detail_local_update_seconds += max(
                                    0.0,
                                    time.perf_counter() - detail_update_started,
                                )
                                compact_item_detail_local_update_count += 1
                    _record_powered_support_coverer_phase(
                        "compact_item_accumulation",
                        compact_item_started,
                    )
                    if compact_item_detail_instrumentation_active:
                        compact_item_detail_unique_item_count = int(
                            len(compact_item_detail_group_items or set())
                        )
                        _record_compact_item_detail_phase(
                            "compact_item_key_build",
                            compact_item_detail_key_build_seconds,
                        )
                        _record_compact_item_detail_phase(
                            "local_counter_update",
                            compact_item_detail_local_update_seconds,
                        )
                        compact_item_detail_totals["group_count"] += 1
                        compact_item_detail_totals["key_build_count"] += int(
                            len(filtered_coverers)
                        )
                        compact_item_detail_totals[
                            "local_counter_update_count"
                        ] += compact_item_detail_local_update_count
                        compact_item_detail_totals[
                            "unique_item_count"
                        ] += compact_item_detail_unique_item_count
                        compact_item_template_stats = (
                            _compact_item_detail_template_stats(str(tpl))
                        )
                        compact_item_template_stats["group_count"] = int(
                            compact_item_template_stats["group_count"]
                        ) + 1
                        compact_item_template_stats["key_build_count"] = int(
                            compact_item_template_stats["key_build_count"]
                        ) + int(len(filtered_coverers))
                        compact_item_template_stats[
                            "local_counter_update_count"
                        ] = int(
                            compact_item_template_stats[
                                "local_counter_update_count"
                            ]
                        ) + compact_item_detail_local_update_count
                        compact_item_template_stats["unique_item_count"] = int(
                            compact_item_template_stats["unique_item_count"]
                        ) + compact_item_detail_unique_item_count
                        compact_item_template_stats["key_build_seconds"] = float(
                            compact_item_template_stats["key_build_seconds"]
                        ) + compact_item_detail_key_build_seconds
                        compact_item_template_stats[
                            "local_counter_update_seconds"
                        ] = float(
                            compact_item_template_stats[
                                "local_counter_update_seconds"
                            ]
                        ) + compact_item_detail_local_update_seconds
                        _add_compact_item_detail_top_entry(
                            {
                                "kind": "compact_item_detail_group",
                                "template": str(tpl),
                                "anchor": [
                                    int(anchor_xy[0]),
                                    int(anchor_xy[1]),
                                ],
                                "shape_token": int(shape_token),
                                "pose_count": int(len(pose_indices_tuple)),
                                "representative_cell_count": int(
                                    len(representative_pose_cells)
                                ),
                                "candidate_coverer_count": int(len(coverers)),
                                "filtered_coverer_count": int(len(filtered_coverers)),
                                "compact_item_accumulation_mode": compact_item_accumulation_mode,
                                "local_update_count": int(
                                    compact_item_detail_local_update_count
                                ),
                                "unique_item_count": compact_item_detail_unique_item_count,
                                "merge_update_count": 0,
                                "elapsed_seconds": float(
                                    max(
                                        0.0,
                                        time.perf_counter() - compact_item_started,
                                    )
                                ),
                            }
                        )
                    if powered_support_coverer_instrumentation_enabled:
                        rejected_coverer_count = int(
                            max(0, len(coverers) - len(filtered_coverers))
                        )
                        powered_support_coverer_totals["group_count"] += 1
                        powered_support_coverer_totals["pose_count"] += int(
                            len(pose_indices_tuple)
                        )
                        powered_support_coverer_totals[
                            "representative_cell_count"
                        ] += int(len(representative_pose_cells))
                        powered_support_coverer_totals[
                            "candidate_coverer_count"
                        ] += int(len(coverers))
                        powered_support_coverer_totals[
                            "filtered_coverer_count"
                        ] += int(len(filtered_coverers))
                        powered_support_coverer_totals[
                            "rejected_coverer_count"
                        ] += rejected_coverer_count
                        powered_support_coverer_totals[
                            "power_index_assignment_count"
                        ] += int(len(pose_indices_tuple))
                        powered_support_coverer_totals[
                                "compact_item_update_count"
                            ] += int(len(filtered_coverers))
                        if compact_item_accumulation_optimization_enabled:
                            powered_support_coverer_totals[
                                "compact_item_optimization_attempts"
                            ] += 1
                            if compact_item_accumulation_mode in {
                                "optimized",
                                "batched_counter",
                            }:
                                powered_support_coverer_totals[
                                    "compact_item_optimization_used"
                                ] += 1
                                powered_support_coverer_totals[
                                    "compact_item_optimized_update_count"
                                ] += int(len(filtered_coverers))
                            else:
                                powered_support_coverer_totals[
                                    "compact_item_optimization_fallbacks"
                                ] += 1
                                powered_support_coverer_totals[
                                    "compact_item_fallback_update_count"
                                ] += int(len(filtered_coverers))
                        if compact_item_batched_counter_optimization_enabled:
                            powered_support_coverer_totals[
                                "compact_item_batched_counter_attempts"
                            ] += 1
                            if compact_item_accumulation_mode == "batched_counter":
                                powered_support_coverer_totals[
                                    "compact_item_batched_counter_used"
                                ] += 1
                                powered_support_coverer_totals[
                                    "compact_item_batched_counter_local_update_count"
                                ] += int(len(filtered_coverers))
                            else:
                                powered_support_coverer_totals[
                                    "compact_item_batched_counter_fallbacks"
                                ] += 1
                                powered_support_coverer_totals[
                                    "compact_item_batched_counter_fallback_update_count"
                                ] += int(len(filtered_coverers))
                        _add_powered_support_coverer_top_entry(
                            {
                                "kind": "powered_support_coverer_group",
                                "template": str(tpl),
                                "anchor": [int(anchor_xy[0]), int(anchor_xy[1])],
                                "shape_token": int(shape_token),
                                "pose_count": int(len(pose_indices_tuple)),
                                "representative_cell_count": int(
                                    len(representative_pose_cells)
                                ),
                                "candidate_coverer_count": int(len(coverers)),
                                "filtered_coverer_count": int(len(filtered_coverers)),
                                "rejected_coverer_count": rejected_coverer_count,
                                **(
                                    {
                                        "compact_item_accumulation_mode": compact_item_accumulation_mode,
                                    }
                                    if compact_item_accumulation_optimization_enabled
                                    else {}
                                ),
                                "elapsed_seconds": float(
                                    max(
                                        0.0,
                                        time.perf_counter() - support_group_started,
                                    )
                                ),
                            }
                        )

                support_coverer_finished = time.perf_counter()
                if port_profile_cache_instrumentation_enabled:
                    port_profile_cache_phase_seconds[
                        "powered_support_coverer_build"
                    ] = float(
                        port_profile_cache_phase_seconds.get(
                            "powered_support_coverer_build",
                            0.0,
                        )
                        + max(
                            0.0,
                            support_coverer_finished - support_coverer_phase_started,
                        )
                    )
                    port_profile_cache_totals["anchor_shape_group_count"] += int(
                        len(anchor_shape_pose_indices)
                    )
                    port_profile_cache_totals["support_coverer_scan_count"] += int(
                        support_coverer_scan_count
                    )

            self._covering_pose_indices[tpl] = dict(cover_index)
            self._heuristic_port_fronts[tpl] = front_index
            self._power_coverers_by_template_pose[tpl] = power_index
            self._pose_cells_by_template_pose[tpl] = pose_cells_index
            if tpl in self._powered_templates and tpl != "power_pole":
                self._power_supported_pose_bucket_records_by_template[tpl] = tuple(
                    support_bucket_records
                )
                if compact_item_batched_counter_optimization_enabled:
                    compact_item_batch_merge_started = time.perf_counter()
                    compact_item_batch_merge_update_count = 0
                    compact_item_batch_unique_item_count = 0
                    for pole_idx, compact_item_counts in sorted(
                        compact_item_batched_counts_by_pole.items()
                    ):
                        pole_counts = compact_item_counts_by_pole[int(pole_idx)]
                        compact_item_batch_unique_item_count += int(
                            len(compact_item_counts)
                        )
                        for compact_item, multiplicity in sorted(
                            compact_item_counts.items()
                        ):
                            pole_counts[compact_item] += int(multiplicity)
                            compact_item_batch_merge_update_count += 1
                    _record_powered_support_coverer_phase(
                        "compact_item_accumulation",
                        compact_item_batch_merge_started,
                    )
                    if compact_item_detail_instrumentation_active:
                        compact_item_batch_merge_seconds = max(
                            0.0,
                            time.perf_counter() - compact_item_batch_merge_started,
                        )
                        _record_compact_item_detail_phase(
                            "merge_fanout",
                            compact_item_batch_merge_seconds,
                        )
                        compact_item_detail_totals[
                            "merge_update_count"
                        ] += compact_item_batch_merge_update_count
                        compact_item_template_stats = (
                            _compact_item_detail_template_stats(str(tpl))
                        )
                        compact_item_template_stats["merge_update_count"] = int(
                            compact_item_template_stats["merge_update_count"]
                        ) + compact_item_batch_merge_update_count
                        compact_item_template_stats["merge_fanout_seconds"] = float(
                            compact_item_template_stats["merge_fanout_seconds"]
                        ) + compact_item_batch_merge_seconds
                    if powered_support_coverer_instrumentation_enabled:
                        powered_support_coverer_totals[
                            "compact_item_batched_counter_merge_update_count"
                        ] += compact_item_batch_merge_update_count
                        powered_support_coverer_totals[
                            "compact_item_batched_counter_unique_item_count"
                        ] += compact_item_batch_unique_item_count
                compact_store_started = time.perf_counter()
                compact_signature_by_pole = {
                    int(pole_idx): tuple(
                        compact_item
                        for compact_item, multiplicity in sorted(
                            compact_item_counts_by_pole.get(int(pole_idx), {}).items()
                        )
                        for _ in range(int(multiplicity))
                    )
                    for pole_idx in range(power_pole_count)
                }
                self._store_local_power_capacity_compact_signature_classes(
                    str(tpl),
                    compact_signature_by_pole,
                )
                if compact_item_detail_instrumentation_active:
                    compact_item_count = int(
                        sum(len(items) for items in compact_signature_by_pole.values())
                    )
                    compact_signature_storage_seconds = max(
                        0.0,
                        time.perf_counter() - compact_store_started,
                    )
                    _record_compact_item_detail_phase(
                        "compact_signature_storage",
                        compact_signature_storage_seconds,
                    )
                    compact_item_detail_totals[
                        "signature_storage_item_count"
                    ] += compact_item_count
                    compact_item_template_stats = (
                        _compact_item_detail_template_stats(str(tpl))
                    )
                    compact_item_template_stats[
                        "signature_storage_item_count"
                    ] = int(
                        compact_item_template_stats[
                            "signature_storage_item_count"
                        ]
                    ) + compact_item_count
                    compact_item_template_stats[
                        "signature_storage_seconds"
                    ] = float(
                        compact_item_template_stats[
                            "signature_storage_seconds"
                        ]
                    ) + compact_signature_storage_seconds
                if port_profile_cache_instrumentation_enabled:
                    compact_item_count = int(
                        sum(len(items) for items in compact_signature_by_pole.values())
                    )
                    port_profile_cache_phase_seconds[
                        "compact_capacity_signature_store"
                    ] = float(
                        port_profile_cache_phase_seconds.get(
                            "compact_capacity_signature_store",
                            0.0,
                        )
                        + max(0.0, time.perf_counter() - compact_store_started)
                    )
                    port_profile_cache_totals[
                        "compact_capacity_signature_item_count"
                    ] += compact_item_count
                    _add_port_profile_cache_top_entry(
                        {
                            "kind": "compact_capacity_signature_store",
                            "template": str(tpl),
                            "item_count": compact_item_count,
                            "elapsed_seconds": float(
                                max(0.0, time.perf_counter() - compact_store_started)
                            ),
                        }
                    )
        exact_precompute_profile_started = time.perf_counter()
        self._update_exact_precompute_profile(
            power_capacity_shell_pairs=int(len(self._power_pole_pose_indices_by_shell_pair)),
            geometry_cache_templates=int(len(self._pose_local_signature_by_template_pose)),
        )
        if port_profile_cache_publication_enabled:
            index_pools_total_seconds = 0.0
            port_profile_cache_phase_seconds_payload: Dict[str, float] = {}
            port_profile_cache_totals_payload: Dict[str, int] = {}
            port_profile_cache_top_entries_payload: List[Dict[str, Any]] = []
            if port_profile_cache_instrumentation_enabled:
                port_profile_cache_totals["power_pole_count"] = power_pole_count
                port_profile_cache_phase_seconds[
                    "exact_precompute_profile_update"
                ] = float(
                    port_profile_cache_phase_seconds.get(
                        "exact_precompute_profile_update",
                        0.0,
                    )
                    + max(0.0, time.perf_counter() - exact_precompute_profile_started)
                )
                for phase_name in (
                    "index_container_initialization",
                    "power_pole_index_build",
                    "per_template_pose_cache_build",
                    "port_front_extraction",
                    "local_signature_build",
                    "powered_anchor_shape_grouping",
                    "powered_support_coverer_build",
                    "compact_capacity_signature_store",
                    "exact_precompute_profile_update",
                ):
                    port_profile_cache_phase_seconds.setdefault(phase_name, 0.0)
                index_pools_total_seconds = float(
                    max(0.0, time.perf_counter() - instrumentation_started)
                )
                measured_seconds = float(
                    sum(
                        max(0.0, value)
                        for value in port_profile_cache_phase_seconds.values()
                    )
                )
                port_profile_cache_phase_seconds[
                    "index_pools_unattributed_seconds"
                ] = float(max(0.0, index_pools_total_seconds - measured_seconds))
                port_profile_cache_phase_seconds_payload = dict(
                    sorted(port_profile_cache_phase_seconds.items())
                )
                port_profile_cache_totals_payload = {
                    key: int(value)
                    for key, value in sorted(port_profile_cache_totals.items())
                }
                port_profile_cache_top_entries_payload = sorted(
                    port_profile_cache_top_entries,
                    key=lambda entry: (
                        -float(entry.get("elapsed_seconds", 0.0)),
                        str(entry.get("kind", "")),
                        str(entry.get("template", "")),
                        str(entry.get("anchor", "")),
                        str(entry.get("shape_token", "")),
                    ),
                )[:10]
            powered_support_coverer_instrumentation: Dict[str, Any] = {}
            if powered_support_coverer_instrumentation_enabled:
                powered_support_finalize_started = time.perf_counter()
                for phase_name in (
                    "coverer_union_collection",
                    "disjoint_filtering",
                    "power_index_expansion",
                    "compact_item_accumulation",
                    "stats_finalize",
                ):
                    powered_support_coverer_phase_seconds.setdefault(phase_name, 0.0)
                compact_item_detail_payload: Dict[str, Any] = {}
                if compact_item_detail_instrumentation_active:
                    compact_item_detail_finalize_started = time.perf_counter()
                    for phase_name in (
                        "compact_item_key_build",
                        "local_counter_update",
                        "merge_fanout",
                        "compact_signature_storage",
                        "stats_finalize",
                    ):
                        compact_item_detail_phase_seconds.setdefault(phase_name, 0.0)
                    compact_item_detail_top_entries_payload = sorted(
                        compact_item_detail_top_entries,
                        key=lambda entry: (
                            -float(entry.get("elapsed_seconds", 0.0)),
                            str(entry.get("template", "")),
                            str(entry.get("anchor", "")),
                            str(entry.get("shape_token", "")),
                            str(entry.get("compact_item_accumulation_mode", "")),
                        ),
                    )[:10]
                    compact_item_detail_per_template_payload = [
                        {
                            key: (
                                int(value)
                                if key.endswith("_count")
                                or key in {"group_count"}
                                else float(value)
                                if key.endswith("_seconds")
                                else value
                            )
                            for key, value in sorted(stats.items())
                        }
                        for _template, stats in sorted(
                            compact_item_detail_per_template.items()
                        )
                    ]
                    local_update_count = int(
                        compact_item_detail_totals.get(
                            "local_counter_update_count",
                            0,
                        )
                    )
                    unique_item_count = int(
                        compact_item_detail_totals.get("unique_item_count", 0)
                    )
                    merge_update_count = int(
                        compact_item_detail_totals.get("merge_update_count", 0)
                    )
                    compact_item_detail_phase_seconds["stats_finalize"] = float(
                        compact_item_detail_phase_seconds.get("stats_finalize", 0.0)
                        + max(
                            0.0,
                            time.perf_counter()
                            - compact_item_detail_finalize_started,
                        )
                    )
                    compact_item_detail_payload = {
                        "enabled": True,
                        "env_var": EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_DETAIL_INSTRUMENTATION_ENV,
                        "phase_seconds": dict(
                            sorted(compact_item_detail_phase_seconds.items())
                        ),
                        "total_phase_seconds": float(
                            sum(
                                max(0.0, value)
                                for value in compact_item_detail_phase_seconds.values()
                            )
                        ),
                        "totals": {
                            key: int(value)
                            for key, value in sorted(
                                compact_item_detail_totals.items()
                            )
                        },
                        "per_template": compact_item_detail_per_template_payload,
                        "top_slow_groups": compact_item_detail_top_entries_payload,
                        "duplicate_compression": {
                            "local_update_count": local_update_count,
                            "unique_item_count": unique_item_count,
                            "merge_update_count": merge_update_count,
                            "duplicate_update_count": int(
                                max(0, local_update_count - unique_item_count)
                            ),
                            "unique_to_local_ratio": (
                                float(unique_item_count) / float(local_update_count)
                                if local_update_count > 0
                                else 0.0
                            ),
                            "merge_to_local_ratio": (
                                float(merge_update_count) / float(local_update_count)
                                if local_update_count > 0
                                else 0.0
                            ),
                        },
                    }
                powered_support_top_entries = sorted(
                    powered_support_coverer_top_entries,
                    key=lambda entry: (
                        -float(entry.get("elapsed_seconds", 0.0)),
                        str(entry.get("template", "")),
                        str(entry.get("anchor", "")),
                        str(entry.get("shape_token", "")),
                    ),
                )[:10]
                powered_support_coverer_phase_seconds["stats_finalize"] = float(
                    powered_support_coverer_phase_seconds.get("stats_finalize", 0.0)
                    + max(0.0, time.perf_counter() - powered_support_finalize_started)
                )
                powered_support_coverer_instrumentation = {
                    "enabled": True,
                    "env_var": EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV,
                    "phase_seconds": dict(
                        sorted(powered_support_coverer_phase_seconds.items())
                    ),
                    "total_phase_seconds": float(
                        sum(
                            max(0.0, value)
                            for value in powered_support_coverer_phase_seconds.values()
                        )
                    ),
                    "totals": {
                        key: int(value)
                        for key, value in sorted(
                            powered_support_coverer_totals.items()
                        )
                    },
                    "top_slow_groups": powered_support_top_entries,
                }
                if compact_item_detail_payload:
                    powered_support_coverer_instrumentation[
                        "compact_item_detail_instrumentation"
                    ] = compact_item_detail_payload
            self._port_profile_cache_instrumentation = {
                "enabled": True,
                "env_var": EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION_ENV,
                "phase_seconds": port_profile_cache_phase_seconds_payload,
                "total_seconds": index_pools_total_seconds,
                "totals": port_profile_cache_totals_payload,
                "top_slow_templates_or_groups": port_profile_cache_top_entries_payload,
            }
            if powered_support_coverer_instrumentation_enabled:
                self._port_profile_cache_instrumentation[
                    "powered_support_coverer_instrumentation"
                ] = powered_support_coverer_instrumentation

    def _pose_local_signature(self, tpl: str, pose_idx: int) -> PoseLocalSignature:
        return self._pose_local_signature_by_template_pose.get(str(tpl), {}).get(
            int(pose_idx),
            (tuple(), tuple(), tuple(), 0),
        )

    def _build_signature_bucket_payload(
        self,
        tpl: str,
        pose_indices: Iterable[int],
    ) -> List[Dict[str, Any]]:
        cache_key = (
            str(tpl),
            frozenset(int(pose_idx) for pose_idx in pose_indices),
        )
        cached = self._signature_bucket_payload_cache.get(cache_key)
        if cached is not None:
            self._update_exact_precompute_profile(
                signature_bucket_cache_hits=int(self._exact_precompute_profile["signature_bucket_cache_hits"]) + 1,
                signature_bucket_distinct_keys=int(len(self._signature_bucket_payload_cache)),
            )
            return self._clone_signature_bucket_payload(cached)

        self._update_exact_precompute_profile(
            signature_bucket_cache_misses=int(self._exact_precompute_profile["signature_bucket_cache_misses"]) + 1,
        )
        buckets_by_signature: DefaultDict[PoseLocalSignature, List[int]] = defaultdict(list)
        for pose_idx in sorted(cache_key[1]):
            buckets_by_signature[self._pose_local_signature(tpl, int(pose_idx))].append(int(pose_idx))

        ordered_buckets: List[Dict[str, Any]] = []
        for bucket_index, signature in enumerate(sorted(buckets_by_signature)):
            ordered_pose_indices = sorted(
                buckets_by_signature[signature],
                key=lambda idx: self._pose_sort_key(tpl, int(idx)),
            )
            ordered_buckets.append(
                {
                    "bucket_id": f"sig_{bucket_index:03d}",
                    "signature": signature,
                    "pose_indices": ordered_pose_indices,
                }
            )
        self._signature_bucket_payload_cache[cache_key] = self._clone_signature_bucket_payload(
            ordered_buckets
        )
        self._update_exact_precompute_profile(
            signature_bucket_distinct_keys=int(len(self._signature_bucket_payload_cache)),
        )
        return self._clone_signature_bucket_payload(ordered_buckets)

    def _bucket_stats_payload(self, buckets: Mapping[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        for bucket_owner, bucket_defs in sorted(buckets.items()):
            payload[str(bucket_owner)] = {
                "bucket_count": len(bucket_defs),
                "pose_count": sum(len(bucket["pose_indices"]) for bucket in bucket_defs),
                "bucket_sizes": [len(bucket["pose_indices"]) for bucket in bucket_defs],
            }
        return payload

    def _build_signature_buckets(self) -> None:
        self._mandatory_signature_buckets = {}
        for group in self._mandatory_groups:
            group_id = str(group["group_id"])
            tpl = str(group["facility_type"])
            self._mandatory_signature_buckets[group_id] = self._build_signature_bucket_payload(
                tpl,
                range(len(self.facility_pools.get(tpl, []))),
            )

        self._required_optional_signature_buckets = {}
        for tpl, required_count in sorted(self._exact_required_pose_optional_counts.items()):
            if int(required_count) <= 0:
                continue
            self._required_optional_signature_buckets[str(tpl)] = self._build_signature_bucket_payload(
                str(tpl),
                range(len(self.facility_pools.get(str(tpl), []))),
            )

        self.build_stats["signature_buckets"] = {
            "mandatory_groups": self._bucket_stats_payload(self._mandatory_signature_buckets),
            "required_optionals": self._bucket_stats_payload(self._required_optional_signature_buckets),
        }

    def _current_z_var_indices(self) -> Dict[str, Dict[int, int]]:
        return {
            group_id: {
                int(pose_idx): int(var.Index())
                for pose_idx, var in vars_by_pose.items()
            }
            for group_id, vars_by_pose in self.z_vars.items()
        }

    def _current_optional_pose_var_indices(self) -> Dict[str, Dict[int, int]]:
        return {
            tpl: {
                int(pose_idx): int(var.Index())
                for pose_idx, var in vars_by_pose.items()
            }
            for tpl, vars_by_pose in self.optional_pose_vars.items()
        }

    def _bind_vars_from_exact_core(self, core: ExactMasterCore) -> None:
        self.z_vars = {}
        for group_id, indices_by_pose in core.z_var_indices.items():
            self.z_vars[group_id] = {
                int(pose_idx): self.model.GetBoolVarFromProtoIndex(int(proto_idx))
                for pose_idx, proto_idx in indices_by_pose.items()
            }

        self.optional_pose_vars = {}
        for tpl, indices_by_pose in core.optional_pose_var_indices.items():
            self.optional_pose_vars[tpl] = {
                int(pose_idx): self.model.GetBoolVarFromProtoIndex(int(proto_idx))
                for pose_idx, proto_idx in indices_by_pose.items()
            }

    def _populate_cell_occupancy_terms(self) -> None:
        self._cell_occupancy_terms = defaultdict(list)

        for group in self._mandatory_groups:
            group_id = group["group_id"]
            tpl = group["facility_type"]
            cover_index = self._covering_pose_indices.get(tpl, {})
            for cell, pose_indices in cover_index.items():
                self._cell_occupancy_terms[cell].extend(
                    self.z_vars[group_id][pose_idx] for pose_idx in pose_indices
                )

        for tpl, vars_by_pose in self.optional_pose_vars.items():
            cover_index = self._covering_pose_indices.get(tpl, {})
            for cell, pose_indices in cover_index.items():
                self._cell_occupancy_terms[cell].extend(
                    vars_by_pose[pose_idx] for pose_idx in pose_indices
                )

    def build(self) -> None:
        if self._built:
            return
        if self.exact_mode and self._coordinate_delegate is not None:
            self._coordinate_delegate.model = self.model
            self._coordinate_delegate.build()
            self._mandatory_signature_count_vars = self._coordinate_delegate.mandatory_signature_count_vars
            self._required_optional_signature_count_vars = self._coordinate_delegate.required_optional_signature_count_vars
            self._residual_optional_signature_count_vars = (
                self._coordinate_delegate.residual_optional_signature_count_vars
            )
            self._power_pole_family_count_vars = self._coordinate_delegate.power_pole_family_count_vars
            self._built = True
            # P1 #7 main #1: build 末尾自动 load+apply 上一波 hint (env-gated).
            self._maybe_load_hints_from_persistence()
            return
        self._create_variables()
        self._add_assignment_constraints()
        self._add_signature_count_constraints()
        self._add_set_packing_constraints()
        self._add_ghost_rect_constraints()
        self._add_port_clearance_constraints()
        if not self.skip_power_coverage:
            self._add_power_coverage_constraints()
        if self.enable_symmetry_breaking:
            self._add_symmetry_breaking_constraints()
        self._add_global_valid_inequalities()
        self._add_search_guidance()
        self._built = True
        # P1 #7 main #1: build 末尾自动 load+apply 上一波 hint (env-gated).
        self._maybe_load_hints_from_persistence()

    def _create_variables(self) -> None:
        for group in self._mandatory_groups:
            group_id = group["group_id"]
            tpl = group["facility_type"]
            pool = self.facility_pools[tpl]
            self.z_vars[group_id] = {
                pose_idx: self.model.NewBoolVar(f"z__{group_id}__{pose_idx}")
                for pose_idx in range(len(pool))
            }

        for tpl in sorted(POSE_LEVEL_OPTIONAL_TEMPLATES):
            pool = self.facility_pools.get(tpl, [])
            self.optional_pose_vars[tpl] = {
                pose_idx: self.model.NewBoolVar(f"opt__{tpl}__{pose_idx}")
                for pose_idx in range(len(pool))
            }

        self._mandatory_signature_count_vars = {}
        for group in self._mandatory_groups:
            group_id = str(group["group_id"])
            required_count = int(group["count"])
            self._mandatory_signature_count_vars[group_id] = {}
            for bucket in self._mandatory_signature_buckets.get(group_id, []):
                bucket_id = str(bucket["bucket_id"])
                upper_bound = min(required_count, len(bucket["pose_indices"]))
                self._mandatory_signature_count_vars[group_id][bucket_id] = self.model.NewIntVar(
                    0,
                    int(upper_bound),
                    f"sig_count__{group_id}__{bucket_id}",
                )

        self._required_optional_signature_count_vars = {}
        for tpl, bucket_defs in sorted(self._required_optional_signature_buckets.items()):
            required_count = int(self._exact_required_pose_optional_counts.get(str(tpl), 0))
            self._required_optional_signature_count_vars[str(tpl)] = {}
            for bucket in bucket_defs:
                bucket_id = str(bucket["bucket_id"])
                upper_bound = min(required_count, len(bucket["pose_indices"]))
                self._required_optional_signature_count_vars[str(tpl)][bucket_id] = self.model.NewIntVar(
                    0,
                    int(upper_bound),
                    f"req_opt_sig_count__{tpl}__{bucket_id}",
                )

    def _add_assignment_constraints(self) -> None:
        for group in self._mandatory_groups:
            group_id = group["group_id"]
            self.model.Add(sum(self.z_vars[group_id].values()) == int(group["count"]))

        for tpl, vars_by_pose in self.optional_pose_vars.items():
            if self.solve_mode == "exploratory":
                cap = int(self._optional_cap_by_template.get(tpl, 0))
                self.model.Add(sum(vars_by_pose.values()) <= cap)
            else:
                # certified_exact（严格认证精确）不加经验上限。
                pass

    def _add_signature_count_constraints(self) -> None:
        for group in self._mandatory_groups:
            group_id = str(group["group_id"])
            bucket_vars = self._mandatory_signature_count_vars.get(group_id, {})
            for bucket in self._mandatory_signature_buckets.get(group_id, []):
                bucket_id = str(bucket["bucket_id"])
                pose_terms = [
                    self.z_vars[group_id][int(pose_idx)]
                    for pose_idx in bucket["pose_indices"]
                    if int(pose_idx) in self.z_vars.get(group_id, {})
                ]
                self.model.Add(bucket_vars[bucket_id] == sum(pose_terms))
            if bucket_vars:
                self.model.Add(sum(bucket_vars.values()) == int(group["count"]))

        for tpl, bucket_defs in sorted(self._required_optional_signature_buckets.items()):
            bucket_vars = self._required_optional_signature_count_vars.get(str(tpl), {})
            for bucket in bucket_defs:
                bucket_id = str(bucket["bucket_id"])
                pose_terms = [
                    self.optional_pose_vars[str(tpl)][int(pose_idx)]
                    for pose_idx in bucket["pose_indices"]
                    if int(pose_idx) in self.optional_pose_vars.get(str(tpl), {})
                ]
                self.model.Add(bucket_vars[bucket_id] == sum(pose_terms))
            if bucket_vars:
                self.model.Add(
                    sum(bucket_vars.values())
                    == int(self._exact_required_pose_optional_counts.get(str(tpl), 0))
                )

    def _add_set_packing_constraints(self) -> None:
        self._populate_cell_occupancy_terms()

        for terms in self._cell_occupancy_terms.values():
            if terms:
                self.model.Add(sum(terms) <= 1)

    def _add_ghost_rect_constraints(self) -> None:
        if not self.ghost_rect:
            self.build_stats["ghost_rect"] = {"enabled": False}
            return

        ghost_w, ghost_h = self.ghost_rect
        rect_cover_terms: DefaultDict[Tuple[int, int], List[cp_model.IntVar]] = defaultdict(list)
        self._ghost_domains.clear()
        self.u_vars.clear()

        for anchor_x in range(self.grid_w - ghost_w + 1):
            for anchor_y in range(self.grid_h - ghost_h + 1):
                rect_idx = len(self._ghost_domains)
                cells = [
                    (anchor_x + dx, anchor_y + dy)
                    for dx in range(ghost_w)
                    for dy in range(ghost_h)
                ]
                var = self.model.NewBoolVar(f"ghost__{anchor_x}_{anchor_y}_{ghost_w}_{ghost_h}")
                self.u_vars[rect_idx] = var
                self._ghost_domains.append(
                    {
                        "anchor": {"x": anchor_x, "y": anchor_y},
                        "cells": cells,
                    }
                )
                for cell in cells:
                    rect_cover_terms[cell].append(var)

        if not self.u_vars:
            self.model.Add(0 == 1)
            self.build_stats["ghost_rect"] = {
                "enabled": True,
                "placements": 0,
                "reason": "rectangle larger than grid",
            }
            return

        self.model.AddExactlyOne(list(self.u_vars.values()))
        for cell, rect_terms in rect_cover_terms.items():
            occupancy_terms = self._cell_occupancy_terms.get(cell, [])
            self.model.Add(sum(occupancy_terms) + sum(rect_terms) <= 1)

        self.build_stats["ghost_rect"] = {
            "enabled": True,
            "placements": len(self._ghost_domains),
            "size": {"w": ghost_w, "h": ghost_h},
        }

    def _add_port_clearance_constraints(self) -> None:
        """Exploratory heuristic（探索启发式） only.

        严格精确路径不允许把“所有端口前方都必须畅通”这种近似假设
        当成正式剪枝，因此 exact 模式跳过。
        """

        if self.exact_mode:
            self.build_stats["port_clearance"] = {"skipped_in_exact_mode": True}
            return

        constraints = 0
        for group in self._mandatory_groups:
            group_id = group["group_id"]
            tpl = group["facility_type"]
            for pose_idx, z_var in self.z_vars[group_id].items():
                fronts = self._heuristic_port_fronts.get(tpl, {}).get(pose_idx)
                if fronts is None:
                    self.model.Add(z_var == 0)
                    constraints += 1
                    continue
                for cell in fronts:
                    occupancy_terms = [term for term in self._cell_occupancy_terms.get(cell, []) if term is not z_var]
                    if occupancy_terms:
                        self.model.Add(sum(occupancy_terms) + z_var <= 1)
                        constraints += 1

        for tpl, vars_by_pose in self.optional_pose_vars.items():
            for pose_idx, z_var in vars_by_pose.items():
                fronts = self._heuristic_port_fronts.get(tpl, {}).get(pose_idx)
                if fronts is None:
                    self.model.Add(z_var == 0)
                    constraints += 1
                    continue
                for cell in fronts:
                    occupancy_terms = [term for term in self._cell_occupancy_terms.get(cell, []) if term is not z_var]
                    if occupancy_terms:
                        self.model.Add(sum(occupancy_terms) + z_var <= 1)
                        constraints += 1

        self.build_stats["port_clearance"] = {
            "heuristic_constraints": constraints,
            "mode": "exploratory",
        }

    def _add_power_coverage_constraints(self) -> None:
        pole_vars = self.optional_pose_vars.get("power_pole", {})
        constraints = 0

        for group in self._mandatory_groups:
            tpl = group["facility_type"]
            if tpl not in self._powered_templates or tpl == "power_pole":
                continue
            group_id = group["group_id"]
            pose_coverers = self._power_coverers_by_template_pose.get(tpl, {})
            for pose_idx, z_var in self.z_vars[group_id].items():
                coverers = pose_coverers.get(pose_idx, [])
                if not coverers:
                    self.model.Add(z_var == 0)
                    constraints += 1
                    continue
                self.model.Add(sum(pole_vars[idx] for idx in coverers) >= z_var)
                constraints += 1

        for tpl, vars_by_pose in self.optional_pose_vars.items():
            if tpl not in self._powered_templates or tpl == "power_pole":
                continue
            pose_coverers = self._power_coverers_by_template_pose.get(tpl, {})
            for pose_idx, z_var in vars_by_pose.items():
                coverers = pose_coverers.get(pose_idx, [])
                if not coverers:
                    self.model.Add(z_var == 0)
                    constraints += 1
                    continue
                self.model.Add(sum(pole_vars[idx] for idx in coverers) >= z_var)
                constraints += 1

        self.build_stats["power_coverage"] = {
            "constraints": constraints,
            "pole_cap": None if self.exact_mode else self._optional_cap_by_template.get("power_pole", 0),
        }

    def _add_symmetry_breaking_constraints(self) -> None:
        # Grouped encoding（分组编码） already removes clone permutations（克隆置换）.
        self.build_stats["symmetry_breaking"] = {"grouped_encoding_only": True}

    def _ordered_groups_for_exact_search(self) -> List[Dict[str, Any]]:
        if not self.exact_mode:
            return list(self._mandatory_groups)

        candidate_counts: Dict[str, int] = {}
        for group in self._mandatory_groups:
            group_id = str(group["group_id"])
            candidate_counts[group_id] = len(self._candidate_pose_indices_for_group(group))

        return sorted(
            self._mandatory_groups,
            key=lambda group: (
                int(candidate_counts.get(str(group["group_id"]), 0)),
                str(group["facility_type"]),
                str(group["group_id"]),
            ),
        )

    def _ordered_optional_pose_indices(self, tpl: str) -> List[int]:
        return sorted(
            self.optional_pose_vars.get(tpl, {}),
            key=lambda pose_idx: self._pose_sort_key(tpl, int(pose_idx)),
        )

    def _ordered_ghost_anchor_indices(self) -> List[int]:
        return sorted(
            self.u_vars,
            key=lambda rect_idx: (
                int(self._ghost_domains[int(rect_idx)]["anchor"]["x"]),
                int(self._ghost_domains[int(rect_idx)]["anchor"]["y"]),
                int(rect_idx),
            ),
        )

    def _add_search_guidance(self) -> None:
        if not self.exact_mode:
            self.build_stats["search_guidance"] = {
                "applied": False,
                "profile": "default_automatic",
                "reason": "exact-guided branching only runs in certified_exact mode",
            }
            return

        mandatory_literals = 0
        ghost_literals = 0
        optional_literals: Dict[str, int] = {}
        required_optional_literals: Dict[str, int] = {}
        residual_optional_literals: Dict[str, int] = {}
        mandatory_signature_counts: Dict[str, int] = {}
        required_optional_signature_counts: Dict[str, int] = {}
        mandatory_signature_count_literals = 0
        required_optional_signature_count_literals = 0
        required_optional_templates = [
            tpl
            for tpl in sorted(POSE_LEVEL_OPTIONAL_TEMPLATES)
            if int(self._exact_required_pose_optional_counts.get(tpl, 0)) > 0
        ]
        required_optional_template_set = set(required_optional_templates)
        ordered_groups = self._ordered_groups_for_exact_search()
        for group in ordered_groups:
            group_id = str(group["group_id"])
            ordered_signature_count_vars = [
                self._mandatory_signature_count_vars[group_id][str(bucket["bucket_id"])]
                for bucket in self._mandatory_signature_buckets.get(group_id, [])
                if str(bucket["bucket_id"]) in self._mandatory_signature_count_vars.get(group_id, {})
            ]
            if ordered_signature_count_vars:
                self.model.AddDecisionStrategy(
                    ordered_signature_count_vars,
                    cp_model.CHOOSE_FIRST,
                    cp_model.SELECT_MAX_VALUE,
                )
            mandatory_signature_counts[group_id] = len(ordered_signature_count_vars)
            mandatory_signature_count_literals += len(ordered_signature_count_vars)
            candidate_pose_set = {
                int(pose_idx) for pose_idx in self._candidate_pose_indices_for_group(group)
            }
            ordered_pose_indices: List[int] = []
            for bucket in self._mandatory_signature_buckets.get(group_id, []):
                ordered_pose_indices.extend(
                    int(pose_idx)
                    for pose_idx in bucket["pose_indices"]
                    if int(pose_idx) in candidate_pose_set
                )
            ordered_vars = [
                self.z_vars[group_id][pose_idx]
                for pose_idx in ordered_pose_indices
                if pose_idx in self.z_vars.get(group_id, {})
            ]
            if not ordered_vars:
                continue
            self.model.AddDecisionStrategy(
                ordered_vars,
                cp_model.CHOOSE_FIRST,
                cp_model.SELECT_MAX_VALUE,
            )
            mandatory_literals += len(ordered_vars)

        ordered_ghost_indices = self._ordered_ghost_anchor_indices()
        ghost_vars = [
            self.u_vars[rect_idx]
            for rect_idx in ordered_ghost_indices
            if rect_idx in self.u_vars
        ]
        if ghost_vars:
            self.model.AddDecisionStrategy(
                ghost_vars,
                cp_model.CHOOSE_FIRST,
                cp_model.SELECT_MAX_VALUE,
            )
            ghost_literals = len(ghost_vars)

        for tpl in required_optional_templates:
            ordered_signature_count_vars = [
                self._required_optional_signature_count_vars[tpl][str(bucket["bucket_id"])]
                for bucket in self._required_optional_signature_buckets.get(tpl, [])
                if str(bucket["bucket_id"])
                in self._required_optional_signature_count_vars.get(tpl, {})
            ]
            if ordered_signature_count_vars:
                self.model.AddDecisionStrategy(
                    ordered_signature_count_vars,
                    cp_model.CHOOSE_FIRST,
                    cp_model.SELECT_MAX_VALUE,
                )
            required_optional_signature_counts[tpl] = len(ordered_signature_count_vars)
            required_optional_signature_count_literals += len(ordered_signature_count_vars)
            ordered_pose_indices: List[int] = []
            for bucket in self._required_optional_signature_buckets.get(tpl, []):
                ordered_pose_indices.extend(int(pose_idx) for pose_idx in bucket["pose_indices"])
            ordered_vars = [
                self.optional_pose_vars[tpl][pose_idx]
                for pose_idx in ordered_pose_indices
                if pose_idx in self.optional_pose_vars.get(tpl, {})
            ]
            if not ordered_vars:
                required_optional_literals[tpl] = 0
                optional_literals[tpl] = 0
                continue
            self.model.AddDecisionStrategy(
                ordered_vars,
                cp_model.CHOOSE_FIRST,
                cp_model.SELECT_MAX_VALUE,
            )
            required_optional_literals[tpl] = len(ordered_vars)
            optional_literals[tpl] = len(ordered_vars)

        for tpl in sorted(POSE_LEVEL_OPTIONAL_TEMPLATES):
            if tpl in required_optional_template_set:
                continue
            ordered_pose_indices = self._ordered_optional_pose_indices(tpl)
            ordered_vars = [
                self.optional_pose_vars[tpl][pose_idx]
                for pose_idx in ordered_pose_indices
                if pose_idx in self.optional_pose_vars.get(tpl, {})
            ]
            if not ordered_vars:
                residual_optional_literals[tpl] = 0
                optional_literals[tpl] = 0
                continue
            self.model.AddDecisionStrategy(
                ordered_vars,
                cp_model.CHOOSE_FIRST,
                cp_model.SELECT_MIN_VALUE,
            )
            residual_optional_literals[tpl] = len(ordered_vars)
            optional_literals[tpl] = len(ordered_vars)

        self.build_stats["search_guidance"] = {
            "applied": True,
            "profile": "exact_signature_guided_branching_v2",
            "search_branching": "FIXED_SEARCH",
            "mandatory_group_order": [str(group["group_id"]) for group in ordered_groups],
            "mandatory_signature_counts": {
                str(k): int(v) for k, v in mandatory_signature_counts.items()
            },
            "mandatory_signature_count_literals": int(mandatory_signature_count_literals),
            "mandatory_literals": int(mandatory_literals),
            "ghost_literals": int(ghost_literals),
            "required_optional_templates": [str(tpl) for tpl in required_optional_templates],
            "required_optional_signature_counts": {
                str(k): int(v) for k, v in required_optional_signature_counts.items()
            },
            "required_optional_signature_count_literals": int(
                required_optional_signature_count_literals
            ),
            "required_optional_literals": {
                str(k): int(v) for k, v in required_optional_literals.items()
            },
            "required_optional_default": "SELECT_MAX_VALUE",
            "residual_optional_literals": {
                str(k): int(v) for k, v in residual_optional_literals.items()
            },
            "residual_optional_default": "SELECT_MIN_VALUE",
            "optional_literals": {str(k): int(v) for k, v in optional_literals.items()},
            "optional_default": "SELECT_MIN_VALUE",
        }

    def _add_global_valid_inequalities(self) -> None:
        stats: Dict[str, Any] = {
            "exact_safe_only": True,
            "applied": [],
            "optional_cardinality_bounds": {},
            "fixed_required_optional_demands": {},
            "lower_bound_optional_powered_demands": {},
            "powered_template_demands": {},
            "capacity_cache": {
                "scope": "process_memory",
                "signature_hits": 0,
                "signature_misses": 0,
                "signature_count": len(_LOCAL_POWER_CAPACITY_COMPACT_CACHE),
                "pole_template_evaluations": 0,
                "signature_class_count": 0,
                "signature_class_evaluations": 0,
                "compact_signature_class_count": 0,
                "compact_signature_class_evaluations": 0,
                "compact_signature_hits": 0,
                "compact_signature_misses": 0,
                "legacy_signature_materializations": 0,
                "rect_dp_evaluations": 0,
                "rect_dp_cache_hits": 0,
                "rect_dp_cache_misses": 0,
                "rect_dp_state_merges": 0,
                "rect_dp_peak_line_states": 0,
                "rect_dp_peak_pos_states": 0,
                "rect_dp_compiled_signatures": 0,
                "rect_dp_compiled_start_options": 0,
                "rect_dp_deduped_start_options": 0,
                "rect_dp_compiled_line_subsets": 0,
                "rect_dp_peak_line_subset_options": 0,
                "rect_dp_v3_fallbacks": 0,
                "compact_rect_cpsat_evaluations": 0,
                "compact_rect_cpsat_cache_hits": 0,
                "compact_rect_cpsat_selected_cases": 0,
                "compact_rect_cpsat_rect_dp_fallbacks": 0,
                "normalized_rect_signature_count": 0,
                "normalized_rect_cache_hits": 0,
                "normalized_rect_cache_misses": 0,
                "m6x4_mixed_cpsat_evaluations": 0,
                "m6x4_mixed_cpsat_cache_hits": 0,
                "m6x4_mixed_cpsat_selected_cases": 0,
                "m6x4_mixed_cpsat_v3_fallbacks": 0,
                "uniform_3x3_cpsat_evaluations": 0,
                "uniform_3x3_cpsat_cache_hits": 0,
                "uniform_3x3_cpsat_selected_cases": 0,
                "uniform_3x3_cpsat_v3_fallbacks": 0,
                "bitset_oracle_evaluations": 0,
                "bitset_fallbacks": 0,
                "cpsat_fallbacks": 0,
                "oracle": "compact_rect_cpsat_v2",
                "raw_pole_evaluations": 0,
                "coefficient_source": "exact_compact_rect_cpsat_v14",
                "shell_pair_count": 0,
            },
            "capacity_coeff_stats": {},
            "power_capacity_families": {
                "applied": False,
                "family_count": 0,
                "raw_pole_count": 0,
                "coefficient_source": "exact_compact_rect_cpsat_v14",
                "shell_pair_count": 0,
                "compact_signature_class_count": 0,
                "families": [],
            },
            "aggregated_power_capacity_terms": {
                "applied": False,
                "raw_nonzero_terms": 0,
                "aggregated_nonzero_terms": 0,
            },
            "ghost_aware_via_pole_feasibility": {
                "enabled": bool(self.ghost_rect),
                "explicit_u_conditioning": False,
            },
            "notes": [
                "No power-pole area lower bound is injected into certified exact mode.",
                "Exploratory mode only keeps optional pose caps through assignment constraints.",
            ],
        }
        self.build_stats["global_valid_inequalities"] = stats
        if not self.exact_mode:
            return

        self._add_exact_optional_cardinality_bounds(stats)
        stats["fixed_required_optional_demands"] = self._exact_fixed_required_optional_powered_demands()
        stats["lower_bound_optional_powered_demands"] = self._lower_bound_optional_powered_demands()
        self._power_pole_family_count_vars = {}
        if self.skip_power_coverage:
            stats["notes"].append(
                "Exact local power-capacity lower bounds are skipped when power coverage is disabled."
            )
            stats["power_capacity_families"]["reason"] = "power_coverage_skipped"
            stats["aggregated_power_capacity_terms"]["reason"] = "power_coverage_skipped"
            return

        powered_template_demands = self._exact_powered_template_demands()
        stats["powered_template_demands"] = dict(powered_template_demands)
        if not powered_template_demands:
            stats["power_capacity_families"]["reason"] = "no_powered_template_demands"
            stats["aggregated_power_capacity_terms"]["reason"] = "no_powered_template_demands"
            return

        pole_vars = self.optional_pose_vars.get("power_pole", {})
        coeff_stats: Dict[str, Any] = {}
        cache_stats = dict(stats["capacity_cache"])
        coeff_by_template_and_pole: Dict[str, Dict[int, int]] = {}
        for tpl, demand in sorted(powered_template_demands.items()):
            coeff_by_pole: Dict[int, int] = {}
            for pole_idx in sorted(pole_vars):
                coeff = self._exact_local_power_capacity_coefficient(tpl, int(pole_idx), cache_stats)
                coeff_by_pole[int(pole_idx)] = coeff
            positive_coeffs = [value for value in coeff_by_pole.values() if value > 0]
            coeff_by_template_and_pole[tpl] = coeff_by_pole
            coeff_stats[tpl] = {
                "demand": demand,
                "total_poles": len(coeff_by_pole),
                "nonzero_poles": len(positive_coeffs),
                "max_coeff": max(positive_coeffs) if positive_coeffs else 0,
                "min_nonzero_coeff": min(positive_coeffs) if positive_coeffs else None,
            }
            stats["applied"].append(
                {
                    "type": "power_capacity_lower_bound",
                    "template": tpl,
                    "demand": demand,
                    "nonzero_poles": coeff_stats[tpl]["nonzero_poles"],
                }
            )

        family_members: DefaultDict[Tuple[Tuple[str, int], ...], List[int]] = defaultdict(list)
        template_order = sorted(powered_template_demands)
        for pole_idx in sorted(pole_vars):
            family_key = tuple(
                (tpl, int(coeff_by_template_and_pole.get(tpl, {}).get(int(pole_idx), 0)))
                for tpl in template_order
            )
            family_members[family_key].append(int(pole_idx))

        family_coefficients: Dict[str, Dict[str, int]] = {}
        family_sizes: Dict[str, int] = {}
        family_terms: Dict[str, cp_model.IntVar] = {}
        for family_index, family_key in enumerate(sorted(family_members)):
            family_id = f"family_{family_index:03d}"
            members = sorted(family_members[family_key])
            family_var = self.model.NewIntVar(
                0,
                len(members),
                f"power_pole_family_count__{family_id}",
            )
            self.model.Add(sum(pole_vars[pole_idx] for pole_idx in members) == family_var)
            self._power_pole_family_count_vars[family_id] = family_var
            family_terms[family_id] = family_var
            family_sizes[family_id] = len(members)
            family_coefficients[family_id] = {
                str(tpl): int(coeff)
                for tpl, coeff in family_key
            }

        aggregated_nonzero_terms = 0
        raw_nonzero_terms = sum(
            int(template_stats["nonzero_poles"])
            for template_stats in coeff_stats.values()
        )
        for tpl, demand in sorted(powered_template_demands.items()):
            terms: List[cp_model.LinearExpr] = []
            for family_id, family_var in family_terms.items():
                coeff = int(family_coefficients[family_id].get(tpl, 0))
                if coeff <= 0:
                    continue
                aggregated_nonzero_terms += 1
                terms.append(coeff * family_var)

            if terms:
                self.model.Add(sum(terms) >= demand)
            else:
                self.model.Add(0 >= demand)

        cache_stats["signature_count"] = len(_LOCAL_POWER_CAPACITY_COMPACT_CACHE)
        stats["capacity_cache"] = cache_stats
        stats["capacity_coeff_stats"] = coeff_stats
        stats["power_capacity_families"] = {
            "applied": True,
            "family_count": len(family_members),
            "raw_pole_count": len(pole_vars),
            "coefficient_source": str(
                cache_stats.get("coefficient_source", "exact_compact_rect_cpsat_v14")
            ),
            "shell_pair_count": int(cache_stats.get("shell_pair_count", 0)),
            "compact_signature_class_count": int(
                cache_stats.get("compact_signature_class_count", 0)
            ),
            "families": [
                {
                    "family_id": family_id,
                    "size": int(family_sizes[family_id]),
                    "coefficients": {
                        str(tpl): int(coefficients[tpl])
                        for tpl in template_order
                    },
                }
                for family_id, coefficients in sorted(family_coefficients.items())
            ],
        }
        stats["aggregated_power_capacity_terms"] = {
            "applied": True,
            "raw_nonzero_terms": int(raw_nonzero_terms),
            "aggregated_nonzero_terms": int(aggregated_nonzero_terms),
        }

    def _required_generic_input_slot_total(self) -> int:
        return sum(
            int(v)
            for v in self.generic_io_requirements.get("required_generic_inputs", {}).values()
        )

    def _mandatory_powered_nonpole_count(self) -> int:
        return sum(
            int(group["count"])
            for group in self._mandatory_groups
            if str(group["facility_type"]) in self._powered_templates
            and str(group["facility_type"]) != "power_pole"
        )

    def _required_protocol_storage_box_lower_bound(self) -> int:
        return int(self._certified_optional_lower_bounds.get("protocol_storage_box", 0))

    def _certified_optional_slot_upper_bound(self, tpl: str) -> int:
        tpl = str(tpl)
        if tpl == "power_pole":
            return 0
        pool = list(self.facility_pools.get(tpl, []))
        if not pool:
            return 0
        template = dict(self.templates.get(tpl, {}))
        dims = dict(template.get("dimensions", {}))
        width = int(dims.get("w", 0))
        height = int(dims.get("h", 0))
        area = int(width) * int(height)
        if area <= 0:
            return 0
        candidate_pose_count = int(len(pool))
        grid_area = int(self.grid_w) * int(self.grid_h)
        geometric_upper_bound = int(grid_area // area)
        return int(min(candidate_pose_count, geometric_upper_bound))

    def _certified_optional_slot_upper_bounds(self) -> Dict[str, int]:
        return {
            str(tpl): int(self._certified_optional_slot_upper_bound(str(tpl)))
            for tpl in sorted(POSE_LEVEL_OPTIONAL_TEMPLATES)
            if str(tpl) != "power_pole"
            and int(self._certified_optional_slot_upper_bound(str(tpl))) > 0
        }

    def _residual_optional_powered_slot_upper_bounds(self) -> Dict[str, int]:
        return {
            str(tpl): int(upper_bound)
            for tpl, upper_bound in sorted(self._certified_optional_slot_upper_bounds().items())
            if str(tpl) in self._powered_templates
            and str(tpl) != "power_pole"
            and int(self._exact_required_pose_optional_counts.get(str(tpl), 0)) <= 0
        }

    def _add_exact_optional_cardinality_bounds(self, stats: Dict[str, Any]) -> None:
        optional_bounds: Dict[str, Any] = {}

        protocol_box_vars = self.optional_pose_vars.get("protocol_storage_box", {})
        required_generic_input_slots = self._required_generic_input_slot_total()
        protocol_storage_box_count = self._required_protocol_storage_box_lower_bound()
        protocol_box_terms = list(protocol_box_vars.values())
        self.model.Add(sum(protocol_box_terms) >= int(protocol_storage_box_count))
        optional_bounds["protocol_storage_box"] = {
            "mode": "required_lower_bound",
            "required_generic_input_slots": int(required_generic_input_slots),
            "slots_per_pose": int(
                get_operation_port_profile(
                    POSE_LEVEL_OPTIONAL_OPERATIONS["protocol_storage_box"]
                ).generic_input_slots
            ),
            "lower": int(protocol_storage_box_count),
            "upper": None,
            "candidate_pose_count": len(protocol_box_terms),
        }
        stats["applied"].append(
            {
                "type": "optional_cardinality_bound",
                "template": "protocol_storage_box",
                "mode": "required_lower_bound",
                "lower": int(protocol_storage_box_count),
                "upper": None,
            }
        )

        power_pole_vars = self.optional_pose_vars.get("power_pole", {})
        mandatory_powered_nonpole = self._mandatory_powered_nonpole_count()
        optional_powered_templates = sorted(
            tpl
            for tpl in self.optional_pose_vars
            if tpl != "power_pole" and tpl in self._powered_templates
        )
        optional_powered_terms = [
            var
            for tpl in optional_powered_templates
            for var in self.optional_pose_vars.get(tpl, {}).values()
        ]
        self.model.Add(
            sum(power_pole_vars.values())
            <= int(mandatory_powered_nonpole) + sum(optional_powered_terms)
        )
        optional_bounds["power_pole"] = {
            "mode": "selected_powered_upper_bound",
            "lower": 0,
            "candidate_pose_count": len(power_pole_vars),
            "mandatory_powered_nonpole": int(mandatory_powered_nonpole),
            "optional_powered_templates": optional_powered_templates,
        }
        stats["applied"].append(
            {
                "type": "optional_cardinality_bound",
                "template": "power_pole",
                "mode": "selected_powered_upper_bound",
                "mandatory_powered_nonpole": int(mandatory_powered_nonpole),
                "optional_powered_templates": optional_powered_templates,
            }
        )
        stats["optional_cardinality_bounds"] = optional_bounds

    def _pose_sort_key(self, tpl: str, pose_idx: int) -> Tuple[int, int, str, int]:
        pose = self.facility_pools[tpl][pose_idx]
        anchor = dict(pose.get("anchor", {}))
        return (
            int(anchor.get("x", 0)),
            int(anchor.get("y", 0)),
            str(pose.get("pose_id", "")),
            int(pose_idx),
        )

    def _pose_cells(self, tpl: str, pose_idx: int) -> Set[Tuple[int, int]]:
        return set(self._pose_cells_by_template_pose.get(tpl, {}).get(pose_idx, frozenset()))

    def _pose_greedy_blocking_cells(self, tpl: str, pose_idx: int) -> Set[Tuple[int, int]]:
        cached = self._pose_greedy_blocking_cells_by_template_pose.get(str(tpl), {}).get(
            int(pose_idx)
        )
        if cached is not None:
            return set(cached)
        cells = self._pose_cells(str(tpl), int(pose_idx))
        if str(tpl) != "boundary_storage_port":
            return cells
        try:
            pose = dict(self.facility_pools[str(tpl)][int(pose_idx)])
        except Exception:
            return cells
        for port in list(pose.get("input_port_cells", [])) + list(
            pose.get("output_port_cells", [])
        ):
            cells.add((int(port["x"]), int(port["y"])))
        return cells

    def _find_mandatory_rectangle_precheck_witness(
        self,
        tpl: str,
        pose_indices: Sequence[int],
        required_count: int,
    ) -> Optional[Tuple[int, ...]]:
        required = int(required_count)
        if required <= 0:
            return tuple()
        if len(pose_indices) < required:
            return None
        if len(pose_indices) < EXACT_MANDATORY_RECTANGLE_PRECHECK_WITNESS_MIN_SURVIVORS:
            return None
        selected: List[int] = []
        occupied_cells: Set[Tuple[int, int]] = set()
        for pose_idx in pose_indices:
            cells = self._pose_cells(str(tpl), int(pose_idx))
            if not cells or not occupied_cells.isdisjoint(cells):
                continue
            selected.append(int(pose_idx))
            occupied_cells.update(cells)
            if len(selected) >= required:
                return tuple(selected)
        return None

    def _exact_powered_template_demands(self) -> Dict[str, int]:
        counts: Dict[str, int] = defaultdict(int)
        for group in self._mandatory_groups:
            tpl = str(group["facility_type"])
            if tpl in self._powered_templates and tpl != "power_pole":
                counts[tpl] += int(group["count"])
        for tpl, count in self._lower_bound_optional_powered_demands().items():
            counts[str(tpl)] += int(count)
        return dict(sorted(counts.items()))

    def _lower_bound_optional_powered_demands(self) -> Dict[str, int]:
        return {
            str(tpl): int(count)
            for tpl, count in sorted(self._certified_optional_lower_bounds.items())
            if int(count) > 0 and str(tpl) in self._powered_templates and str(tpl) != "power_pole"
        }

    def _exact_fixed_required_optional_powered_demands(self) -> Dict[str, int]:
        return {
            str(tpl): int(count)
            for tpl, count in sorted(self._exact_required_pose_optional_counts.items())
            if int(count) > 0 and str(tpl) in self._powered_templates and str(tpl) != "power_pole"
        }

    def _materialize_local_power_capacity_signature_for_pole(
        self,
        tpl: str,
        pole_idx: int,
    ) -> LocalCapacitySignature:
        tpl = str(tpl)
        origin_x, origin_y = self._pose_anchor_by_template_pose.get("power_pole", {}).get(
            int(pole_idx),
            (0, 0),
        )
        pose_anchors = self._pose_anchor_by_template_pose.get(tpl, {})
        pose_local_cells = self._pose_local_cells_by_template_pose.get(tpl, {})
        supported_by_pole = self._ensure_power_supported_pose_indices_by_template_pole(tpl)

        relative_shapes: List[LocalPoseShape] = []
        for pose_idx in supported_by_pole.get(int(pole_idx), []):
            anchor_x, anchor_y = pose_anchors.get(int(pose_idx), (0, 0))
            delta_x = int(anchor_x) - int(origin_x)
            delta_y = int(anchor_y) - int(origin_y)
            local_cells = pose_local_cells.get(int(pose_idx), tuple())
            relative_shapes.append(
                tuple(
                    (int(cell_x) + delta_x, int(cell_y) + delta_y)
                    for cell_x, cell_y in local_cells
                )
            )
        return tuple(sorted(relative_shapes))

    def _materialize_local_power_capacity_signature_from_compact(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
    ) -> LocalCapacitySignature:
        tpl = str(tpl)
        local_shapes = self._local_shape_by_template_token.get(tpl, {})
        relative_shapes: List[LocalPoseShape] = []
        for delta_x, delta_y, shape_token in compact_signature:
            local_shape = local_shapes.get(int(shape_token))
            if local_shape is None:
                raise RuntimeError(
                    f"Missing local shape token {shape_token} for template {tpl}"
                )
            relative_shapes.append(
                tuple(
                    (int(cell_x) + int(delta_x), int(cell_y) + int(delta_y))
                    for cell_x, cell_y in local_shape
                )
            )
        return tuple(sorted(relative_shapes))

    def _compact_local_power_capacity_signature(
        self,
        tpl: str,
        pole_idx: int,
    ) -> CompactLocalCapacitySignature:
        tpl = str(tpl)
        cached = self._compact_local_power_capacity_signature_by_template_pole.get(
            tpl,
            {},
        ).get(int(pole_idx))
        if cached is not None:
            return cached
        self._ensure_local_power_capacity_compact_signature_classes(tpl)
        return self._compact_local_power_capacity_signature_by_template_pole.get(
            tpl,
            {},
        ).get(int(pole_idx), tuple())

    def _bump_power_capacity_legacy_signature_materializations(
        self,
        cache_stats: Optional[Dict[str, Any]] = None,
        count: int = 1,
    ) -> None:
        increment = int(count)
        self._exact_precompute_profile[
            "power_capacity_legacy_signature_materializations"
        ] = int(
            self._exact_precompute_profile.get(
                "power_capacity_legacy_signature_materializations",
                0,
            )
        ) + increment
        self.build_stats["exact_precompute_profile"] = dict(self._exact_precompute_profile)
        if cache_stats is not None:
            cache_stats["legacy_signature_materializations"] = int(
                cache_stats.get("legacy_signature_materializations", 0)
            ) + increment

    def _bump_power_capacity_supported_by_pole_materializations(self, count: int = 1) -> None:
        increment = int(count)
        self._exact_precompute_profile[
            "power_capacity_supported_by_pole_materializations"
        ] = int(
            self._exact_precompute_profile.get(
                "power_capacity_supported_by_pole_materializations",
                0,
            )
        ) + increment
        self.build_stats["exact_precompute_profile"] = dict(self._exact_precompute_profile)

    def _ensure_power_supported_pose_indices_by_template_pole(
        self,
        tpl: str,
    ) -> Dict[int, List[int]]:
        tpl = str(tpl)
        cached = self._power_supported_pose_indices_by_template_pole.get(tpl)
        if cached is not None:
            return cached

        bucket_records = self._power_supported_pose_bucket_records_by_template.get(tpl)
        if bucket_records is None:
            self._power_supported_pose_indices_by_template_pole[tpl] = {}
            return self._power_supported_pose_indices_by_template_pole[tpl]

        supported_by_pole: DefaultDict[int, List[int]] = defaultdict(list)
        for record in bucket_records:
            for pole_idx in record.coverers:
                supported_by_pole[int(pole_idx)].extend(
                    int(pose_idx) for pose_idx in record.pose_indices
                )

        materialized = {
            int(pole_idx): list(indices)
            for pole_idx, indices in supported_by_pole.items()
        }
        self._power_supported_pose_indices_by_template_pole[tpl] = materialized
        self._bump_power_capacity_supported_by_pole_materializations()
        return materialized

    def _ensure_local_power_capacity_compact_signature_classes(
        self,
        tpl: str,
    ) -> Dict[CompactLocalCapacitySignature, List[int]]:
        tpl = str(tpl)
        cached = self._power_pole_pose_indices_by_template_compact_capacity_signature.get(tpl)
        if cached is not None:
            return cached

        pole_count = int(len(self.facility_pools.get("power_pole", [])))
        power_pole_anchors = self._pose_anchor_by_template_pose.get("power_pole", {})
        pose_anchors = self._pose_anchor_by_template_pose.get(tpl, {})
        pose_shape_tokens = self._pose_local_shape_token_by_template_pose.get(tpl, {})
        supported_by_pole = self._ensure_power_supported_pose_indices_by_template_pole(tpl)

        compact_signature_by_pole: Dict[int, CompactLocalCapacitySignature] = {}
        for pole_idx in range(pole_count):
            origin_x, origin_y = power_pole_anchors.get(int(pole_idx), (0, 0))
            compact_items: List[CompactLocalCapacityItem] = []
            for pose_idx in supported_by_pole.get(int(pole_idx), []):
                anchor_x, anchor_y = pose_anchors.get(int(pose_idx), (0, 0))
                delta_x = int(anchor_x) - int(origin_x)
                delta_y = int(anchor_y) - int(origin_y)
                shape_token = pose_shape_tokens.get(int(pose_idx))
                if shape_token is None:
                    raise RuntimeError(
                        f"Missing local shape token for template {tpl} pose {pose_idx}"
                    )
                compact_items.append((int(delta_x), int(delta_y), int(shape_token)))
            compact_signature = tuple(sorted(compact_items))
            compact_signature_by_pole[int(pole_idx)] = compact_signature

        return self._store_local_power_capacity_compact_signature_classes(
            tpl,
            compact_signature_by_pole,
        )

    def _ensure_local_power_capacity_legacy_signature_materialized(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
        *,
        representative_pole_idx: Optional[int] = None,
        cache_stats: Optional[Dict[str, Any]] = None,
    ) -> LocalCapacitySignature:
        tpl = str(tpl)
        legacy_by_compact = self._legacy_local_power_capacity_signature_by_template_compact_signature.setdefault(
            tpl,
            {},
        )
        cached = legacy_by_compact.get(compact_signature)
        if cached is not None:
            return cached

        legacy_signature = self._materialize_local_power_capacity_signature_from_compact(
            tpl,
            compact_signature,
        )
        if representative_pole_idx is None:
            representative_pole_idx = next(
                iter(
                    self._power_pole_pose_indices_by_template_compact_capacity_signature.get(
                        tpl,
                        {},
                    ).get(compact_signature, [])
                ),
                None,
            )
        if representative_pole_idx is not None:
            representative_signature = self._materialize_local_power_capacity_signature_for_pole(
                tpl,
                int(representative_pole_idx),
            )
            if legacy_signature != representative_signature:
                raise RuntimeError(
                    f"Compact local-capacity signature mismatch for template {tpl}"
                )

        compact_by_legacy = self._compact_local_power_capacity_signature_by_template_legacy_signature.setdefault(
            tpl,
            {},
        )
        existing_compact = compact_by_legacy.get(legacy_signature)
        if existing_compact is not None and existing_compact != compact_signature:
            raise RuntimeError(
                f"Distinct compact local-capacity signatures map to the same legacy signature for template {tpl}"
            )

        legacy_by_compact[compact_signature] = legacy_signature
        compact_by_legacy[legacy_signature] = compact_signature
        for pole_idx in self._power_pole_pose_indices_by_template_compact_capacity_signature.get(
            tpl,
            {},
        ).get(compact_signature, []):
            self._local_power_capacity_signature_by_template_pole.setdefault(tpl, {})[
                int(pole_idx)
            ] = legacy_signature
        self._power_pole_pose_indices_by_template_capacity_signature.setdefault(tpl, {})[
            legacy_signature
        ] = list(
            self._power_pole_pose_indices_by_template_compact_capacity_signature.get(
                tpl,
                {},
            ).get(compact_signature, [])
        )
        self._bump_power_capacity_legacy_signature_materializations(
            cache_stats=cache_stats,
        )
        return legacy_signature

    def _local_power_capacity_signature(self, tpl: str, pole_idx: int) -> LocalCapacitySignature:
        tpl = str(tpl)
        cached = self._local_power_capacity_signature_by_template_pole.get(tpl, {}).get(
            int(pole_idx)
        )
        if cached is not None:
            return cached
        compact_signature = self._compact_local_power_capacity_signature(
            tpl,
            int(pole_idx),
        )
        if not compact_signature:
            return tuple()
        return self._ensure_local_power_capacity_legacy_signature_materialized(
            tpl,
            compact_signature,
            representative_pole_idx=int(pole_idx),
        )

    def _build_local_power_capacity_signature_classes(
        self,
        tpl: str,
    ) -> Dict[LocalCapacitySignature, List[int]]:
        tpl = str(tpl)
        cached = self._power_pole_pose_indices_by_template_capacity_signature.get(tpl)
        if (
            cached is not None
            and tpl in self._fully_materialized_local_power_capacity_signature_classes_by_template
        ):
            return cached
        grouped_pose_indices: DefaultDict[LocalCapacitySignature, List[int]] = defaultdict(list)
        compact_signature_classes = self._ensure_local_power_capacity_compact_signature_classes(
            tpl
        )
        for compact_signature, pose_indices in sorted(compact_signature_classes.items()):
            legacy_signature = self._ensure_local_power_capacity_legacy_signature_materialized(
                tpl,
                compact_signature,
                representative_pole_idx=int(pose_indices[0]) if pose_indices else None,
            )
            grouped_pose_indices[legacy_signature].extend(
                sorted(
                    pose_indices,
                    key=lambda idx: self._pose_sort_key("power_pole", int(idx)),
                )
            )

        self._power_pole_pose_indices_by_template_capacity_signature[tpl] = {
            signature: sorted(
                pose_indices,
                key=lambda idx: self._pose_sort_key("power_pole", int(idx)),
            )
            for signature, pose_indices in sorted(grouped_pose_indices.items())
        }
        self._fully_materialized_local_power_capacity_signature_classes_by_template.add(tpl)
        return self._power_pole_pose_indices_by_template_capacity_signature[tpl]

    def _solve_exact_local_power_capacity_cpsat(
        self,
        tpl: str,
        signature: LocalCapacitySignature,
    ) -> int:
        if not signature:
            return 0

        cache_key = (str(tpl), signature)
        cached = _LOCAL_POWER_CAPACITY_CACHE.get(cache_key)
        if cached is not None:
            return cached

        local_model = cp_model.CpModel()
        local_vars = [
            local_model.NewBoolVar(f"local_power_cap__{tpl}__{idx}")
            for idx in range(len(signature))
        ]
        cell_terms: DefaultDict[Tuple[int, int], List[cp_model.IntVar]] = defaultdict(list)
        for idx, relative_cells in enumerate(signature):
            for cell in relative_cells:
                cell_terms[cell].append(local_vars[idx])
        for terms in cell_terms.values():
            if len(terms) > 1:
                local_model.Add(sum(terms) <= 1)
        local_model.Maximize(sum(local_vars))

        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = resolve_cp_sat_worker_count(
            env_name="EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS",
            default=DEFAULT_LOCAL_CAPACITY_CP_SAT_WORKERS,
        )
        status = solver.Solve(local_model)
        if status != cp_model.OPTIMAL:
            raise RuntimeError(
                f"Failed to compute exact local power capacity for template {tpl}: {solver.StatusName(status)}"
            )
        capacity = int(round(solver.ObjectiveValue()))
        _LOCAL_POWER_CAPACITY_CACHE[cache_key] = capacity
        return capacity

    def _solve_exact_local_power_capacity_bitset_mis(
        self,
        tpl: str,
        signature: LocalCapacitySignature,
    ) -> int:
        if not signature:
            return 0

        unique_shapes = list(dict.fromkeys(signature))
        if len(unique_shapes) <= 1:
            return int(len(unique_shapes))

        try:
            min_x = min(cell_x for shape in unique_shapes for cell_x, _ in shape)
            min_y = min(cell_y for shape in unique_shapes for _, cell_y in shape)
            max_x = max(cell_x for shape in unique_shapes for cell_x, _ in shape)
        except ValueError as exc:
            raise _BitsetLocalCapacityFallback(
                f"Unsupported empty local-capacity shape for template {tpl}"
            ) from exc

        width = int(max_x - min_x + 1)
        if width <= 0:
            raise _BitsetLocalCapacityFallback(
                f"Invalid local-capacity bitset width for template {tpl}"
            )

        bitsets: List[int] = []
        seen_bitsets: Set[int] = set()
        for shape in unique_shapes:
            bitset = 0
            for cell_x, cell_y in shape:
                bit_index = (int(cell_y) - int(min_y)) * width + (int(cell_x) - int(min_x))
                bitset |= 1 << int(bit_index)
            if bitset <= 0:
                raise _BitsetLocalCapacityFallback(
                    f"Unsupported zero-bit local-capacity shape for template {tpl}"
                )
            if bitset not in seen_bitsets:
                seen_bitsets.add(bitset)
                bitsets.append(bitset)

        vertex_count = len(bitsets)
        if vertex_count <= 1:
            return int(vertex_count)

        adjacency = [0] * vertex_count
        for left in range(vertex_count):
            left_bits = bitsets[left]
            for right in range(left + 1, vertex_count):
                if left_bits & bitsets[right]:
                    adjacency[left] |= 1 << right
                    adjacency[right] |= 1 << left

        max_iterations = int(self._local_power_capacity_bitset_max_iterations)
        iteration_count = 0
        memo: Dict[int, int] = {}

        def split_components(mask: int) -> List[int]:
            components: List[int] = []
            remaining = int(mask)
            while remaining:
                seed = remaining & -remaining
                component = 0
                frontier = seed
                while frontier:
                    bit = frontier & -frontier
                    frontier &= ~bit
                    if component & bit:
                        continue
                    component |= bit
                    idx = bit.bit_length() - 1
                    frontier |= adjacency[idx] & remaining & ~component
                components.append(component)
                remaining &= ~component
            return components

        def solve_component(mask: int) -> int:
            nonlocal iteration_count
            iteration_count += 1
            if iteration_count > max_iterations:
                raise _BitsetLocalCapacityFallback(
                    f"Bitset MIS iteration limit exceeded for template {tpl}"
                )
            if mask == 0:
                return 0
            cached = memo.get(mask)
            if cached is not None:
                return cached

            forced = 0
            reduced = int(mask)
            while reduced:
                isolated = 0
                remaining = int(reduced)
                while remaining:
                    bit = remaining & -remaining
                    remaining &= ~bit
                    idx = bit.bit_length() - 1
                    if (adjacency[idx] & reduced) == 0:
                        isolated |= bit
                if isolated == 0:
                    break
                forced += isolated.bit_count()
                reduced &= ~isolated
            if reduced == 0:
                memo[mask] = forced
                return forced

            components = split_components(reduced)
            if len(components) > 1:
                total = forced + sum(solve_component(component) for component in components)
                memo[mask] = total
                return total

            branch_vertex = -1
            branch_degree = -1
            remaining = int(reduced)
            while remaining:
                bit = remaining & -remaining
                remaining &= ~bit
                idx = bit.bit_length() - 1
                degree = int((adjacency[idx] & reduced).bit_count())
                if degree > branch_degree:
                    branch_degree = degree
                    branch_vertex = idx
            if branch_vertex < 0:
                memo[mask] = forced + reduced.bit_count()
                return memo[mask]
            if branch_degree <= 0:
                memo[mask] = forced + reduced.bit_count()
                return memo[mask]

            branch_bit = 1 << branch_vertex
            include_value = forced + 1 + solve_component(
                reduced & ~adjacency[branch_vertex] & ~branch_bit
            )
            exclude_mask = reduced & ~branch_bit
            if exclude_mask.bit_count() <= include_value - forced:
                memo[mask] = include_value
                return include_value
            exclude_value = forced + solve_component(exclude_mask)
            best = max(include_value, exclude_value)
            memo[mask] = best
            return best

        return int(solve_component((1 << vertex_count) - 1))

    def _normalize_rectangle_frontier_signature(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
    ) -> Tuple[Tuple[int, int, int, int], ...]:
        if not compact_signature:
            return tuple()
        rect_variants = self._ensure_local_rectangle_variants(tpl)
        placements: Set[Tuple[int, int, int, int]] = set()
        for delta_x, delta_y, shape_token in compact_signature:
            variant = rect_variants.get(int(shape_token))
            if variant is None:
                raise _RectangleFrontierDPFallback(
                    f"Non-rectangular local shape token {shape_token} for template {tpl}"
                )
            placements.add(
                (
                    int(delta_x) + int(variant.min_x),
                    int(delta_y) + int(variant.min_y),
                    int(variant.width),
                    int(variant.height),
                )
            )
        if not placements:
            return tuple()
        min_x = min(int(x_val) for x_val, _, _, _ in placements)
        min_y = min(int(y_val) for _, y_val, _, _ in placements)
        normalized = {
            (
                int(x_val) - int(min_x),
                int(y_val) - int(min_y),
                int(width),
                int(height),
            )
            for x_val, y_val, width, height in placements
        }
        return tuple(sorted(normalized))

    def _rectangle_frontier_scan_stats(
        self,
        normalized: Sequence[Tuple[int, int, int, int]],
    ) -> Tuple[int, int]:
        if not normalized:
            return 0, 0
        window_w = max(int(x_val) + int(width) for x_val, _, width, _ in normalized)
        window_h = max(int(y_val) + int(height) for _, y_val, _, height in normalized)
        max_rect_w = max(int(width) for _, _, width, _ in normalized)
        max_rect_h = max(int(height) for _, _, _, height in normalized)
        row_frontier_bits = int(window_w) * max(0, int(max_rect_h) - 1)
        col_frontier_bits = int(window_h) * max(0, int(max_rect_w) - 1)
        return int(row_frontier_bits), int(col_frontier_bits)

    def _should_use_rectangle_frontier_dp_v4(
        self,
        compiled: _CompiledRectangleFrontierDP,
    ) -> bool:
        return (
            int(compiled.peak_line_subset_options)
            <= int(self._local_power_capacity_rect_dp_v4_max_peak_line_subset_options)
            and int(compiled.compiled_line_subsets)
            <= int(self._local_power_capacity_rect_dp_v4_max_compiled_line_subsets)
        )

    def _is_manufacturing_6x4_mixed_signature(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
    ) -> bool:
        if str(tpl) != "manufacturing_6x4":
            return False
        normalized = self._normalize_rectangle_frontier_signature(str(tpl), compact_signature)
        if not normalized:
            return False
        variants = {(int(width), int(height)) for _, _, width, height in normalized}
        return variants == {(6, 4), (4, 6)}

    def _is_uniform_3x3_signature(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
    ) -> bool:
        normalized = self._normalize_rectangle_frontier_signature(str(tpl), compact_signature)
        if not normalized:
            return False
        variants = {(int(width), int(height)) for _, _, width, height in normalized}
        return variants == {(3, 3)}

    def _compact_rect_cpsat_class_tag_from_normalized(
        self,
        tpl: str,
        normalized: Sequence[Tuple[int, int, int, int]],
    ) -> Optional[str]:
        if not normalized:
            return None
        variants = {(int(width), int(height)) for _, _, width, height in normalized}
        if str(tpl) == "manufacturing_6x4" and variants == {(6, 4), (4, 6)}:
            return "m6x4_mixed"
        if variants == {(3, 3)}:
            return "uniform_3x3"
        return None

    def _bump_compact_rect_cpsat_stats(
        self,
        cache_stats: Optional[Dict[str, Any]],
        class_tag: Optional[str],
        event: str,
    ) -> None:
        if cache_stats is None:
            return

        generic_key = {
            "evaluations": "compact_rect_cpsat_evaluations",
            "cache_hits": "compact_rect_cpsat_cache_hits",
            "selected_cases": "compact_rect_cpsat_selected_cases",
            "rect_dp_fallbacks": "compact_rect_cpsat_rect_dp_fallbacks",
        }.get(str(event))
        if generic_key is not None:
            cache_stats[generic_key] = int(cache_stats.get(generic_key, 0)) + 1

        class_prefix = {
            "m6x4_mixed": "m6x4_mixed_cpsat",
            "uniform_3x3": "uniform_3x3_cpsat",
        }.get(str(class_tag))
        if class_prefix is None:
            return

        class_key = {
            "evaluations": f"{class_prefix}_evaluations",
            "cache_hits": f"{class_prefix}_cache_hits",
            "selected_cases": f"{class_prefix}_selected_cases",
            "rect_dp_fallbacks": f"{class_prefix}_v3_fallbacks",
        }.get(str(event))
        if class_key is not None:
            cache_stats[class_key] = int(cache_stats.get(class_key, 0)) + 1

    def _compile_compact_rect_cpsat_data(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
        *,
        normalized: Optional[NormalizedRectangleSignature] = None,
    ) -> _CompiledCompactRectCpSatData:
        if normalized is None:
            normalized = self._normalize_rectangle_frontier_signature(str(tpl), compact_signature)
        cache_key = tuple(normalized)
        cached = _LOCAL_POWER_CAPACITY_COMPACT_RECT_CPSAT_DATA_CACHE.get(cache_key)
        if cached is not None:
            return cached

        if not normalized:
            compiled = _CompiledCompactRectCpSatData(
                window_w=0,
                window_h=0,
                placements=tuple(),
                cell_to_placement_indices={},
            )
            _LOCAL_POWER_CAPACITY_COMPACT_RECT_CPSAT_DATA_CACHE[cache_key] = compiled
            return compiled

        placements = tuple(
            sorted(
                {
                    (
                        int(x_val),
                        int(y_val),
                        int(width),
                        int(height),
                    )
                    for x_val, y_val, width, height in normalized
                }
            )
        )
        window_w = max(int(x_val) + int(width) for x_val, _, width, _ in placements)
        window_h = max(int(y_val) + int(height) for _, y_val, _, height in placements)
        cell_to_indices: DefaultDict[Tuple[int, int], List[int]] = defaultdict(list)
        for placement_idx, (x_val, y_val, width, height) in enumerate(placements):
            for dx in range(int(width)):
                for dy in range(int(height)):
                    cell_to_indices[(int(x_val) + dx, int(y_val) + dy)].append(
                        int(placement_idx)
                    )
        compiled = _CompiledCompactRectCpSatData(
            window_w=int(window_w),
            window_h=int(window_h),
            placements=placements,
            cell_to_placement_indices={
                cell: tuple(indices) for cell, indices in cell_to_indices.items()
            },
        )
        _LOCAL_POWER_CAPACITY_COMPACT_RECT_CPSAT_DATA_CACHE[cache_key] = compiled
        return compiled

    def _compile_rectangle_frontier_dp(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
        *,
        scan_axis: str,
    ) -> _CompiledRectangleFrontierDP:
        cache_key = (str(tpl), compact_signature, str(scan_axis))
        cached = _LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE.get(cache_key)
        if cached is not None:
            return cached

        normalized = self._normalize_rectangle_frontier_signature(str(tpl), compact_signature)
        if not normalized:
            compiled = _CompiledRectangleFrontierDP(
                scan_axis=str(scan_axis),
                line_count=0,
                line_width=0,
                frontier_bits=0,
                horizon=0,
                line_end_shift=0,
                current_bit_masks=tuple(),
                placements_by_line_and_pos=tuple(),
                start_options_by_line_and_pos=tuple(),
                line_subset_transitions_by_line=tuple(),
                compiled_start_options=0,
                deduped_start_options=0,
                compiled_line_subsets=0,
                peak_line_subset_options=0,
            )
            _LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE[cache_key] = compiled
            return compiled

        placements = list(normalized)
        window_w = max(int(x_val) + int(width) for x_val, _, width, _ in placements)
        window_h = max(int(y_val) + int(height) for _, y_val, _, height in placements)
        max_rect_w = max(int(width) for _, _, width, _ in placements)
        max_rect_h = max(int(height) for _, _, _, height in placements)
        if window_w <= 0 or window_h <= 0 or max_rect_w <= 0 or max_rect_h <= 0:
            raise _RectangleFrontierDPFallback(
                f"Invalid rectangle frontier domain for template {tpl}"
            )

        if scan_axis == "row":
            line_count = int(window_h)
            line_width = int(window_w)
            max_span = int(max_rect_h)
            frontier_bits = int(window_w) * max(0, int(max_rect_h) - 1)
            encoded = [
                (int(y_val), int(x_val), int(height), int(width))
                for x_val, y_val, width, height in placements
            ]
        elif scan_axis == "column":
            line_count = int(window_w)
            line_width = int(window_h)
            max_span = int(max_rect_w)
            frontier_bits = int(window_h) * max(0, int(max_rect_w) - 1)
            encoded = [
                (int(x_val), int(y_val), int(width), int(height))
                for x_val, y_val, width, height in placements
            ]
        else:
            raise ValueError(f"Unsupported rectangle frontier scan_axis: {scan_axis}")

        if line_count <= 0 or line_width <= 0 or max_span <= 0:
            raise _RectangleFrontierDPFallback(
                f"Invalid rectangle frontier geometry for template {tpl}"
            )

        horizon = max(0, int(max_span) - 1)
        placements_by_line_and_pos: List[List[List[Tuple[int, int, Tuple[int, ...]]]]] = [
            [[] for _ in range(int(line_width))]
            for _ in range(int(line_count))
        ]
        start_options_by_line_and_pos: List[List[List[PackedRectTransition]]] = [
            [[] for _ in range(int(line_width))]
            for _ in range(int(line_count))
        ]
        line_level_options_by_line: List[List[PackedRectTransition]] = [
            [] for _ in range(int(line_count))
        ]
        compiled_start_options = 0
        for start_line, start_pos, span_lines, span_pos in encoded:
            if (
                int(start_line) < 0
                or int(start_pos) < 0
                or int(span_lines) <= 0
                or int(span_pos) <= 0
                or int(start_line) + int(span_lines) > int(line_count)
                or int(start_pos) + int(span_pos) > int(line_width)
            ):
                raise _RectangleFrontierDPFallback(
                    f"Out-of-bounds rectangle frontier placement for template {tpl}"
                )
            interval_mask = ((1 << int(span_pos)) - 1) << int(start_pos)
            placements_by_line_and_pos[int(start_line)][int(start_pos)].append(
                (
                    int(span_lines),
                    int(span_pos),
                    tuple(int(interval_mask) for _ in range(int(span_lines))),
                )
            )
            conflict_mask = 0
            future_write_mask = 0
            for line_offset in range(int(span_lines)):
                placed_mask = int(interval_mask) << (int(line_offset) * int(line_width))
                conflict_mask |= int(placed_mask)
                if int(line_offset) == 0:
                    future_write_mask |= int(interval_mask) & ~(
                        (1 << (int(start_pos) + 1)) - 1
                    )
                else:
                    future_write_mask |= int(placed_mask)
            start_options_by_line_and_pos[int(start_line)][int(start_pos)].append(
                (int(conflict_mask), int(future_write_mask), 1)
            )
            next_line_write_mask = 0
            for line_offset in range(1, int(span_lines)):
                next_line_write_mask |= int(interval_mask) << (
                    (int(line_offset) - 1) * int(line_width)
                )
            line_level_options_by_line[int(start_line)].append(
                (int(conflict_mask), int(next_line_write_mask), 1)
            )
            compiled_start_options += 1

        deduped_start_options = 0
        deduped_start_options_by_line_and_pos: List[List[Tuple[PackedRectTransition, ...]]] = []
        for line_row in start_options_by_line_and_pos:
            deduped_line: List[Tuple[PackedRectTransition, ...]] = []
            for placements_at_pos in line_row:
                deduped = tuple(
                    sorted(
                        set(placements_at_pos),
                        key=lambda item: (
                            int(item[0]),
                            int(item[1]),
                            int(item[2]),
                        ),
                    )
                )
                deduped_start_options += int(len(deduped))
                deduped_line.append(deduped)
            deduped_start_options_by_line_and_pos.append(deduped_line)

        max_line_subsets = int(self._local_power_capacity_rect_dp_max_line_subsets)
        compiled_line_subsets = 0
        peak_line_subset_options = 0
        line_subset_transitions_by_line: List[Tuple[PackedRectTransition, ...]] = []
        for line_options in line_level_options_by_line:
            unique_line_options = tuple(
                sorted(
                    set(line_options),
                    key=lambda item: (
                        int(item[0]),
                        int(item[1]),
                        int(item[2]),
                    ),
                )
            )
            subset_best: Dict[Tuple[int, int], int] = {}
            subset_visits = 0

            def enumerate_subsets(
                option_idx: int,
                combined_conflict: int,
                combined_next_write: int,
                gain: int,
            ) -> None:
                nonlocal subset_visits
                subset_visits += 1
                if subset_visits > max_line_subsets:
                    raise _RectangleFrontierDPFallback(
                        f"Rectangle frontier DP line-subset limit exceeded for template {tpl}"
                    )
                if gain > 0:
                    subset_key = (int(combined_conflict), int(combined_next_write))
                    previous_gain = subset_best.get(subset_key)
                    if previous_gain is None or int(gain) > int(previous_gain):
                        subset_best[subset_key] = int(gain)
                for next_idx in range(int(option_idx), len(unique_line_options)):
                    conflict_mask, next_write_mask, option_gain = unique_line_options[int(next_idx)]
                    if int(combined_conflict) & int(conflict_mask):
                        continue
                    enumerate_subsets(
                        int(next_idx) + 1,
                        int(combined_conflict) | int(conflict_mask),
                        int(combined_next_write) | int(next_write_mask),
                        int(gain) + int(option_gain),
                    )

            enumerate_subsets(0, 0, 0, 0)
            line_subset_transitions = tuple(
                sorted(
                    (
                        (int(conflict_mask), int(next_write_mask), int(gain))
                        for (conflict_mask, next_write_mask), gain in subset_best.items()
                    ),
                    key=lambda item: (
                        int(item[0]),
                        int(item[1]),
                        int(item[2]),
                    ),
                )
            )
            compiled_line_subsets += int(len(line_subset_transitions))
            peak_line_subset_options = max(
                int(peak_line_subset_options),
                int(len(line_subset_transitions)),
            )
            line_subset_transitions_by_line.append(line_subset_transitions)

        compiled = _CompiledRectangleFrontierDP(
            scan_axis=str(scan_axis),
            line_count=int(line_count),
            line_width=int(line_width),
            frontier_bits=int(frontier_bits),
            horizon=int(horizon),
            line_end_shift=int(line_width),
            current_bit_masks=tuple(1 << int(pos) for pos in range(int(line_width))),
            placements_by_line_and_pos=tuple(
                tuple(
                    tuple(
                        sorted(
                            placements_at_pos,
                            key=lambda item: (
                                int(item[0]),
                                int(item[1]),
                                tuple(int(mask) for mask in item[2]),
                            ),
                        )
                    )
                    for placements_at_pos in line_row
                )
                for line_row in placements_by_line_and_pos
            ),
            start_options_by_line_and_pos=tuple(
                tuple(line_row) for line_row in deduped_start_options_by_line_and_pos
            ),
            line_subset_transitions_by_line=tuple(line_subset_transitions_by_line),
            compiled_start_options=int(compiled_start_options),
            deduped_start_options=int(deduped_start_options),
            compiled_line_subsets=int(compiled_line_subsets),
            peak_line_subset_options=int(peak_line_subset_options),
        )
        _LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE[cache_key] = compiled
        return compiled

    def _solve_exact_local_power_capacity_rectangle_frontier_dp_v1(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
        *,
        scan_axis: Optional[str] = None,
    ) -> int:
        normalized = self._normalize_rectangle_frontier_signature(str(tpl), compact_signature)
        if not normalized:
            return 0
        if len(normalized) <= 1:
            return int(len(normalized))

        placements = list(normalized)
        window_w = max(int(x_val) + int(width) for x_val, _, width, _ in placements)
        window_h = max(int(y_val) + int(height) for _, y_val, _, height in placements)
        max_rect_w = max(int(width) for _, _, width, _ in placements)
        max_rect_h = max(int(height) for _, _, _, height in placements)
        if window_w <= 0 or window_h <= 0 or max_rect_w <= 0 or max_rect_h <= 0:
            raise _RectangleFrontierDPFallback(
                f"Invalid rectangle frontier domain for template {tpl}"
            )

        row_frontier_bits = int(window_w) * max(0, int(max_rect_h) - 1)
        col_frontier_bits = int(window_h) * max(0, int(max_rect_w) - 1)
        if scan_axis is None:
            scan_axis = "row" if row_frontier_bits <= col_frontier_bits else "column"
        if scan_axis not in {"row", "column"}:
            raise ValueError(f"Unsupported rectangle frontier scan_axis: {scan_axis}")

        if scan_axis == "row":
            line_count = int(window_h)
            line_width = int(window_w)
            encoded = [
                (int(y_val), int(x_val), int(height), int(width))
                for x_val, y_val, width, height in placements
            ]
        else:
            line_count = int(window_w)
            line_width = int(window_h)
            encoded = [
                (int(x_val), int(y_val), int(width), int(height))
                for x_val, y_val, width, height in placements
            ]

        max_span = max(int(span_lines) for _, _, span_lines, _ in encoded)
        if line_count <= 0 or line_width <= 0 or max_span <= 0:
            raise _RectangleFrontierDPFallback(
                f"Invalid rectangle frontier geometry for template {tpl}"
            )

        placements_by_line: Dict[int, Dict[int, List[Tuple[int, int, Tuple[int, ...]]]]] = {}
        for start_line, start_pos, span_lines, span_pos in encoded:
            if (
                int(start_line) < 0
                or int(start_pos) < 0
                or int(span_lines) <= 0
                or int(span_pos) <= 0
                or int(start_line) + int(span_lines) > int(line_count)
                or int(start_pos) + int(span_pos) > int(line_width)
            ):
                raise _RectangleFrontierDPFallback(
                    f"Out-of-bounds rectangle frontier placement for template {tpl}"
                )
            interval_mask = ((1 << int(span_pos)) - 1) << int(start_pos)
            placements_by_line.setdefault(int(start_line), {}).setdefault(int(start_pos), []).append(
                (
                    int(span_lines),
                    int(span_pos),
                    tuple(int(interval_mask) for _ in range(int(span_lines))),
                )
            )

        max_states = int(self._local_power_capacity_rect_dp_max_states)
        state_visits = 0
        line_cache: Dict[Tuple[int, int], int] = {}

        def solve_line(line_idx: int, packed_state: int) -> int:
            nonlocal state_visits
            if line_idx >= line_count:
                return 0 if packed_state == 0 else -10**9
            cache_key = (int(line_idx), int(packed_state))
            cached = line_cache.get(cache_key)
            if cached is not None:
                return int(cached)
            state_visits += 1
            if state_visits > max_states:
                raise _RectangleFrontierDPFallback(
                    f"Rectangle frontier DP state limit exceeded for template {tpl}"
                )

            placements_by_pos = placements_by_line.get(int(line_idx), {})
            pos_cache: Dict[Tuple[int, int], int] = {}

            def solve_pos(pos: int, working_state: int) -> int:
                nonlocal state_visits
                while pos < line_width and ((int(working_state) >> int(pos)) & 1):
                    pos += 1
                if pos >= line_width:
                    return solve_line(int(line_idx) + 1, int(working_state) >> int(line_width))
                pos_key = (int(pos), int(working_state))
                cached_pos = pos_cache.get(pos_key)
                if cached_pos is not None:
                    return int(cached_pos)
                state_visits += 1
                if state_visits > max_states:
                    raise _RectangleFrontierDPFallback(
                        f"Rectangle frontier DP state limit exceeded for template {tpl}"
                    )

                best = int(solve_pos(int(pos) + 1, int(working_state)))
                for span_lines, span_pos, line_masks in placements_by_pos.get(int(pos), []):
                    conflict = False
                    for line_offset, line_mask in enumerate(line_masks):
                        if (int(working_state) >> (int(line_offset) * int(line_width))) & int(line_mask):
                            conflict = True
                            break
                    if conflict:
                        continue
                    next_state = int(working_state)
                    for line_offset, line_mask in enumerate(line_masks):
                        next_state |= int(line_mask) << (int(line_offset) * int(line_width))
                    best = max(
                        int(best),
                        1 + int(solve_pos(int(pos) + int(span_pos), int(next_state))),
                    )
                pos_cache[pos_key] = int(best)
                return int(best)

            result = int(solve_pos(0, int(packed_state)))
            line_cache[cache_key] = int(result)
            return int(result)

        return int(solve_line(0, 0))

    def _solve_exact_local_power_capacity_rectangle_frontier_dp_v2(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
        *,
        scan_axis: Optional[str] = None,
        cache_stats: Optional[Dict[str, Any]] = None,
    ) -> int:
        normalized = self._normalize_rectangle_frontier_signature(str(tpl), compact_signature)
        if not normalized:
            return 0
        if len(normalized) <= 1:
            return int(len(normalized))

        cache_key = (str(tpl), compact_signature)
        rect_cached = _LOCAL_POWER_CAPACITY_RECT_DP_CACHE.get(cache_key)
        if rect_cached is not None:
            if cache_stats is not None:
                cache_stats["rect_dp_cache_hits"] = int(
                    cache_stats.get("rect_dp_cache_hits", 0)
                ) + 1
            return int(rect_cached)
        if cache_stats is not None:
            cache_stats["rect_dp_cache_misses"] = int(
                cache_stats.get("rect_dp_cache_misses", 0)
            ) + 1
            cache_stats["rect_dp_evaluations"] = int(
                cache_stats.get("rect_dp_evaluations", 0)
            ) + 1

        row_frontier_bits, col_frontier_bits = self._rectangle_frontier_scan_stats(normalized)
        if scan_axis is None:
            scan_axis = "row" if row_frontier_bits <= col_frontier_bits else "column"
        if scan_axis not in {"row", "column"}:
            raise ValueError(f"Unsupported rectangle frontier scan_axis: {scan_axis}")

        compiled = self._compile_rectangle_frontier_dp(
            str(tpl),
            compact_signature,
            scan_axis=str(scan_axis),
        )
        if compiled.line_count <= 0 or compiled.line_width <= 0:
            return 0

        max_states = int(self._local_power_capacity_rect_dp_max_states)
        line_states: Dict[int, int] = {0: 0}
        state_counter = 1
        state_merges = 0
        peak_line_states = 1
        peak_pos_states = 0

        def merge_state(
            state_map: Dict[int, int],
            packed_state: int,
            best_count: int,
        ) -> None:
            nonlocal state_counter, state_merges
            existing = state_map.get(int(packed_state))
            if existing is None:
                state_map[int(packed_state)] = int(best_count)
                state_counter += 1
                if state_counter > max_states:
                    raise _RectangleFrontierDPFallback(
                        f"Rectangle frontier DP state limit exceeded for template {tpl}"
                    )
                return
            state_merges += 1
            if int(best_count) > int(existing):
                state_map[int(packed_state)] = int(best_count)

        line_width = int(compiled.line_width)
        for line_idx in range(int(compiled.line_count)):
            placements_by_pos = compiled.placements_by_line_and_pos[int(line_idx)]
            pos_states = dict(line_states)
            peak_pos_states = max(int(peak_pos_states), int(len(pos_states)))
            for pos in range(int(line_width)):
                next_pos_states: Dict[int, int] = {}
                bit_mask = 1 << int(pos)
                for packed_state, current_count in pos_states.items():
                    if int(packed_state) & int(bit_mask):
                        merge_state(next_pos_states, int(packed_state), int(current_count))
                        continue
                    merge_state(next_pos_states, int(packed_state), int(current_count))
                    for span_lines, span_pos, line_masks in placements_by_pos[int(pos)]:
                        conflict = False
                        for line_offset, line_mask in enumerate(line_masks):
                            chunk_bits = int(packed_state) >> (int(line_offset) * int(line_width))
                            if int(chunk_bits) & int(line_mask):
                                conflict = True
                                break
                        if conflict:
                            continue
                        next_state = int(packed_state)
                        for line_offset, line_mask in enumerate(line_masks):
                            next_state |= int(line_mask) << (int(line_offset) * int(line_width))
                        merge_state(
                            next_pos_states,
                            int(next_state),
                            int(current_count) + 1,
                        )
                pos_states = next_pos_states
                peak_pos_states = max(int(peak_pos_states), int(len(pos_states)))
            line_states = {}
            for packed_state, current_count in pos_states.items():
                merge_state(line_states, int(packed_state) >> int(line_width), int(current_count))
            peak_line_states = max(int(peak_line_states), int(len(line_states)))

        result = int(line_states.get(0, -10**9))
        if result < 0:
            raise _RectangleFrontierDPFallback(
                f"Rectangle frontier DP terminated with residual frontier for template {tpl}"
            )

        if cache_stats is not None:
            cache_stats["rect_dp_state_merges"] = int(
                cache_stats.get("rect_dp_state_merges", 0)
            ) + int(state_merges)
            cache_stats["rect_dp_peak_line_states"] = max(
                int(cache_stats.get("rect_dp_peak_line_states", 0)),
                int(peak_line_states),
            )
            cache_stats["rect_dp_peak_pos_states"] = max(
                int(cache_stats.get("rect_dp_peak_pos_states", 0)),
                int(peak_pos_states),
            )
            cache_stats["rect_dp_compiled_signatures"] = int(
                len(_LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE)
            )
        return int(result)

    def _solve_exact_local_power_capacity_rectangle_frontier_dp_v3(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
        *,
        scan_axis: Optional[str] = None,
        compiled: Optional[_CompiledRectangleFrontierDP] = None,
        cache_stats: Optional[Dict[str, Any]] = None,
    ) -> int:
        normalized = self._normalize_rectangle_frontier_signature(str(tpl), compact_signature)
        if not normalized:
            return 0
        if len(normalized) <= 1:
            return int(len(normalized))

        row_frontier_bits, col_frontier_bits = self._rectangle_frontier_scan_stats(normalized)
        if scan_axis is None:
            scan_axis = "row" if row_frontier_bits <= col_frontier_bits else "column"
        if scan_axis not in {"row", "column"}:
            raise ValueError(f"Unsupported rectangle frontier scan_axis: {scan_axis}")

        if compiled is None:
            compiled = self._compile_rectangle_frontier_dp(
                str(tpl),
                compact_signature,
                scan_axis=str(scan_axis),
            )
        if compiled.line_count <= 0 or compiled.line_width <= 0:
            return 0

        max_states = int(self._local_power_capacity_rect_dp_max_states)
        line_states: Dict[int, int] = {0: 0}
        state_counter = 1
        state_merges = 0
        peak_line_states = 1
        peak_pos_states = 1

        current_bit_masks = compiled.current_bit_masks
        line_end_shift = int(compiled.line_end_shift)
        for line_idx in range(int(compiled.line_count)):
            pos_states = line_states
            placements_by_pos = compiled.start_options_by_line_and_pos[int(line_idx)]
            peak_pos_states = max(int(peak_pos_states), int(len(pos_states)))
            for pos in range(int(compiled.line_width)):
                next_pos_states: Dict[int, int] = {}
                current_bit_mask = int(current_bit_masks[int(pos)])
                start_options = placements_by_pos[int(pos)]
                for packed_state, current_count in pos_states.items():
                    advance_state = int(packed_state) & ~int(current_bit_mask)
                    existing_advance = next_pos_states.get(int(advance_state))
                    if existing_advance is None:
                        next_pos_states[int(advance_state)] = int(current_count)
                        state_counter += 1
                        if state_counter > max_states:
                            raise _RectangleFrontierDPFallback(
                                f"Rectangle frontier DP state limit exceeded for template {tpl}"
                            )
                    else:
                        state_merges += 1
                        if int(current_count) > int(existing_advance):
                            next_pos_states[int(advance_state)] = int(current_count)

                    if int(packed_state) & int(current_bit_mask):
                        continue
                    for conflict_mask, future_write_mask, gain in start_options:
                        if int(packed_state) & int(conflict_mask):
                            continue
                        next_state = int(packed_state) | int(future_write_mask)
                        next_count = int(current_count) + int(gain)
                        existing_next = next_pos_states.get(int(next_state))
                        if existing_next is None:
                            next_pos_states[int(next_state)] = int(next_count)
                            state_counter += 1
                            if state_counter > max_states:
                                raise _RectangleFrontierDPFallback(
                                    f"Rectangle frontier DP state limit exceeded for template {tpl}"
                                )
                        else:
                            state_merges += 1
                            if int(next_count) > int(existing_next):
                                next_pos_states[int(next_state)] = int(next_count)
                pos_states = next_pos_states
                peak_pos_states = max(int(peak_pos_states), int(len(pos_states)))

            line_states = {}
            for packed_state, current_count in pos_states.items():
                shifted_state = int(packed_state) >> int(line_end_shift)
                existing_shifted = line_states.get(int(shifted_state))
                if existing_shifted is None:
                    line_states[int(shifted_state)] = int(current_count)
                    state_counter += 1
                    if state_counter > max_states:
                        raise _RectangleFrontierDPFallback(
                            f"Rectangle frontier DP state limit exceeded for template {tpl}"
                        )
                else:
                    state_merges += 1
                    if int(current_count) > int(existing_shifted):
                        line_states[int(shifted_state)] = int(current_count)
            peak_line_states = max(int(peak_line_states), int(len(line_states)))

        result = int(line_states.get(0, -10**9))
        if result < 0:
            raise _RectangleFrontierDPFallback(
                f"Rectangle frontier DP terminated with residual frontier for template {tpl}"
            )

        if cache_stats is not None:
            cache_stats["rect_dp_state_merges"] = int(
                cache_stats.get("rect_dp_state_merges", 0)
            ) + int(state_merges)
            cache_stats["rect_dp_peak_line_states"] = max(
                int(cache_stats.get("rect_dp_peak_line_states", 0)),
                int(peak_line_states),
            )
            cache_stats["rect_dp_peak_pos_states"] = max(
                int(cache_stats.get("rect_dp_peak_pos_states", 0)),
                int(peak_pos_states),
            )
            cache_stats["rect_dp_compiled_signatures"] = int(
                len(_LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE)
            )
            cache_stats["rect_dp_compiled_start_options"] = int(
                sum(
                    int(item.compiled_start_options)
                    for item in _LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE.values()
                )
            )
            cache_stats["rect_dp_deduped_start_options"] = int(
                sum(
                    int(item.deduped_start_options)
                    for item in _LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE.values()
                )
            )
        return int(result)

    def _solve_exact_local_power_capacity_rectangle_frontier_dp_v4(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
        *,
        scan_axis: Optional[str] = None,
        compiled: Optional[_CompiledRectangleFrontierDP] = None,
        cache_stats: Optional[Dict[str, Any]] = None,
    ) -> int:
        normalized = self._normalize_rectangle_frontier_signature(str(tpl), compact_signature)
        if not normalized:
            return 0
        if len(normalized) <= 1:
            return int(len(normalized))

        row_frontier_bits, col_frontier_bits = self._rectangle_frontier_scan_stats(normalized)
        if scan_axis is None:
            scan_axis = "row" if row_frontier_bits <= col_frontier_bits else "column"
        if scan_axis not in {"row", "column"}:
            raise ValueError(f"Unsupported rectangle frontier scan_axis: {scan_axis}")

        if compiled is None:
            compiled = self._compile_rectangle_frontier_dp(
                str(tpl),
                compact_signature,
                scan_axis=str(scan_axis),
            )
        if compiled.line_count <= 0 or compiled.line_width <= 0:
            return 0

        max_states = int(self._local_power_capacity_rect_dp_max_states)
        line_states: Dict[int, int] = {0: 0}
        state_counter = 1
        state_merges = 0
        peak_line_states = 1
        peak_pos_states = 1
        peak_line_subset_options = 0

        def merge_state(
            state_map: Dict[int, int],
            packed_state: int,
            best_count: int,
        ) -> None:
            nonlocal state_counter, state_merges
            existing = state_map.get(int(packed_state))
            if existing is None:
                state_map[int(packed_state)] = int(best_count)
                state_counter += 1
                if state_counter > max_states:
                    raise _RectangleFrontierDPFallback(
                        f"Rectangle frontier DP state limit exceeded for template {tpl}"
                    )
                return
            state_merges += 1
            if int(best_count) > int(existing):
                state_map[int(packed_state)] = int(best_count)

        line_end_shift = int(compiled.line_end_shift)
        for line_transitions in compiled.line_subset_transitions_by_line:
            peak_pos_states = max(int(peak_pos_states), int(len(line_states)))
            peak_line_subset_options = max(
                int(peak_line_subset_options),
                int(len(line_transitions)),
            )
            next_line_states: Dict[int, int] = {}
            for packed_state, current_count in line_states.items():
                shifted_state = int(packed_state) >> int(line_end_shift)
                merge_state(next_line_states, int(shifted_state), int(current_count))
                for conflict_mask, next_write_mask, gain in line_transitions:
                    if int(packed_state) & int(conflict_mask):
                        continue
                    merge_state(
                        next_line_states,
                        int(shifted_state) | int(next_write_mask),
                        int(current_count) + int(gain),
                    )
            line_states = next_line_states
            peak_line_states = max(int(peak_line_states), int(len(line_states)))

        result = int(line_states.get(0, -10**9))
        if result < 0:
            raise _RectangleFrontierDPFallback(
                f"Rectangle frontier DP terminated with residual frontier for template {tpl}"
            )

        if cache_stats is not None:
            cache_stats["rect_dp_state_merges"] = int(
                cache_stats.get("rect_dp_state_merges", 0)
            ) + int(state_merges)
            cache_stats["rect_dp_peak_line_states"] = max(
                int(cache_stats.get("rect_dp_peak_line_states", 0)),
                int(peak_line_states),
            )
            cache_stats["rect_dp_peak_pos_states"] = max(
                int(cache_stats.get("rect_dp_peak_pos_states", 0)),
                int(peak_pos_states),
            )
            cache_stats["rect_dp_peak_line_subset_options"] = max(
                int(cache_stats.get("rect_dp_peak_line_subset_options", 0)),
                int(peak_line_subset_options),
            )
            cache_stats["rect_dp_compiled_signatures"] = int(
                len(_LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE)
            )
            cache_stats["rect_dp_compiled_start_options"] = int(
                sum(
                    int(item.compiled_start_options)
                    for item in _LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE.values()
                )
            )
            cache_stats["rect_dp_deduped_start_options"] = int(
                sum(
                    int(item.deduped_start_options)
                    for item in _LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE.values()
                )
            )
            cache_stats["rect_dp_compiled_line_subsets"] = int(
                sum(
                    int(item.compiled_line_subsets)
                    for item in _LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE.values()
                )
            )
        return int(result)

    def _solve_exact_local_power_capacity_manufacturing_6x4_mixed_cpsat(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
        *,
        cache_stats: Optional[Dict[str, Any]] = None,
    ) -> int:
        normalized = self._normalize_rectangle_frontier_signature(str(tpl), compact_signature)
        if cache_stats is not None:
            if normalized and tuple(normalized) in _LOCAL_POWER_CAPACITY_COMPACT_RECT_CPSAT_DATA_CACHE:
                self._bump_compact_rect_cpsat_stats(
                    cache_stats,
                    "m6x4_mixed",
                    "cache_hits",
                )
            self._bump_compact_rect_cpsat_stats(
                cache_stats,
                "m6x4_mixed",
                "evaluations",
            )

        if not self._is_manufacturing_6x4_mixed_signature(str(tpl), compact_signature):
            raise _Manufacturing6x4MixedCpSatFallback(
                f"Template-specialized manufacturing_6x4 mixed CP-SAT is unsupported for {tpl}"
            )

        try:
            return self._solve_exact_local_power_capacity_compact_rect_cpsat(
                str(tpl),
                compact_signature,
                var_prefix="m6x4_mixed_cap",
                normalized=normalized if normalized else None,
            )
        except _CompactRectCpSatFallback as exc:
            raise _Manufacturing6x4MixedCpSatFallback(str(exc)) from exc

    def _solve_exact_local_power_capacity_uniform_3x3_cpsat(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
        *,
        cache_stats: Optional[Dict[str, Any]] = None,
    ) -> int:
        normalized = self._normalize_rectangle_frontier_signature(str(tpl), compact_signature)
        if cache_stats is not None:
            if normalized and tuple(normalized) in _LOCAL_POWER_CAPACITY_COMPACT_RECT_CPSAT_DATA_CACHE:
                self._bump_compact_rect_cpsat_stats(
                    cache_stats,
                    "uniform_3x3",
                    "cache_hits",
                )
            self._bump_compact_rect_cpsat_stats(
                cache_stats,
                "uniform_3x3",
                "evaluations",
            )

        if not self._is_uniform_3x3_signature(str(tpl), compact_signature):
            raise _Uniform3x3CpSatFallback(
                f"Template-specialized uniform 3x3 CP-SAT is unsupported for {tpl}"
            )

        try:
            return self._solve_exact_local_power_capacity_compact_rect_cpsat(
                str(tpl),
                compact_signature,
                var_prefix="uniform_3x3_cap",
                normalized=normalized if normalized else None,
            )
        except _CompactRectCpSatFallback as exc:
            raise _Uniform3x3CpSatFallback(str(exc)) from exc

    def _solve_exact_local_power_capacity_compact_rect_cpsat(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
        *,
        var_prefix: str,
        normalized: Optional[NormalizedRectangleSignature] = None,
    ) -> int:
        compiled = self._compile_compact_rect_cpsat_data(
            str(tpl),
            compact_signature,
            normalized=normalized,
        )
        if not compiled.placements:
            return 0

        local_model = cp_model.CpModel()
        local_vars = [
            local_model.NewBoolVar(f"{var_prefix}__{tpl}__{idx}")
            for idx in range(len(compiled.placements))
        ]
        for terms in compiled.cell_to_placement_indices.values():
            if len(terms) > 1:
                local_model.Add(sum(local_vars[idx] for idx in terms) <= 1)
        local_model.Maximize(sum(local_vars))

        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = resolve_cp_sat_worker_count(
            env_name="EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS",
            default=DEFAULT_LOCAL_CAPACITY_CP_SAT_WORKERS,
        )
        status = solver.Solve(local_model)
        if status != cp_model.OPTIMAL:
            raise _CompactRectCpSatFallback(
                f"Compact-rectangle CP-SAT did not prove optimal for template {tpl}: "
                f"{solver.StatusName(status)}"
            )
        return int(round(solver.ObjectiveValue()))

    def _solve_exact_local_power_capacity_compact_rect_cpsat_v2(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
        *,
        cache_stats: Optional[Dict[str, Any]] = None,
        normalized: Optional[NormalizedRectangleSignature] = None,
        class_tag: Optional[str] = None,
    ) -> int:
        if not compact_signature:
            return 0
        if normalized is None:
            normalized = self._normalize_rectangle_frontier_signature(str(tpl), compact_signature)
        if not normalized:
            raise _CompactRectCpSatFallback(
                f"compact_rect_cpsat_v2: unsupported non-rectangular signature for {tpl}"
            )
        if len(normalized) <= 1:
            return int(len(normalized))

        if class_tag is None:
            class_tag = self._compact_rect_cpsat_class_tag_from_normalized(str(tpl), normalized)
        if tuple(normalized) in _LOCAL_POWER_CAPACITY_COMPACT_RECT_CPSAT_DATA_CACHE:
            self._bump_compact_rect_cpsat_stats(cache_stats, class_tag, "cache_hits")
        self._bump_compact_rect_cpsat_stats(cache_stats, class_tag, "evaluations")
        return self._solve_exact_local_power_capacity_compact_rect_cpsat(
            str(tpl),
            compact_signature,
            var_prefix="compact_rect_cap",
            normalized=normalized,
        )

    def _solve_exact_local_power_capacity_rectangle_frontier_dp(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
        *,
        scan_axis: Optional[str] = None,
        cache_stats: Optional[Dict[str, Any]] = None,
    ) -> int:
        if not compact_signature:
            return 0
        normalized = self._normalize_rectangle_frontier_signature(str(tpl), compact_signature)
        if not normalized:
            raise _RectangleFrontierDPFallback(
                f"rectangle_frontier_dp: unsupported non-rectangular signature for {tpl}"
            )
        if len(normalized) <= 1:
            return int(len(normalized))

        cache_key = (str(tpl), compact_signature)
        rect_cached = _LOCAL_POWER_CAPACITY_RECT_DP_CACHE.get(cache_key)
        if rect_cached is not None:
            if cache_stats is not None:
                cache_stats["rect_dp_cache_hits"] = int(
                    cache_stats.get("rect_dp_cache_hits", 0)
                ) + 1
            return int(rect_cached)
        if cache_stats is not None:
            cache_stats["rect_dp_cache_misses"] = int(
                cache_stats.get("rect_dp_cache_misses", 0)
            ) + 1
            cache_stats["rect_dp_evaluations"] = int(
                cache_stats.get("rect_dp_evaluations", 0)
            ) + 1

        row_frontier_bits, col_frontier_bits = self._rectangle_frontier_scan_stats(normalized)
        if scan_axis is None:
            scan_axis = "row" if row_frontier_bits <= col_frontier_bits else "column"
        if scan_axis not in {"row", "column"}:
            raise ValueError(f"Unsupported rectangle frontier scan_axis: {scan_axis}")

        compiled = self._compile_rectangle_frontier_dp(
            str(tpl),
            compact_signature,
            scan_axis=str(scan_axis),
        )
        if self._should_use_rectangle_frontier_dp_v4(compiled):
            capacity = self._solve_exact_local_power_capacity_rectangle_frontier_dp_v4(
                str(tpl),
                compact_signature,
                scan_axis=scan_axis,
                compiled=compiled,
                cache_stats=cache_stats,
            )
            _LOCAL_POWER_CAPACITY_RECT_DP_CACHE[cache_key] = int(capacity)
            return int(capacity)
        if cache_stats is not None:
            cache_stats["rect_dp_v3_fallbacks"] = int(
                cache_stats.get("rect_dp_v3_fallbacks", 0)
            ) + 1
        capacity = self._solve_exact_local_power_capacity_rectangle_frontier_dp_v3(
            str(tpl),
            compact_signature,
            scan_axis=scan_axis,
            compiled=compiled,
            cache_stats=cache_stats,
        )
        _LOCAL_POWER_CAPACITY_RECT_DP_CACHE[cache_key] = int(capacity)
        return int(capacity)

    def _solve_exact_local_power_capacity_from_compact(
        self,
        tpl: str,
        compact_signature: CompactLocalCapacitySignature,
        *,
        cache_stats: Optional[Dict[str, Any]] = None,
    ) -> int:
        tpl = str(tpl)
        if not compact_signature:
            return 0

        cache_key = (tpl, compact_signature)
        cached = _LOCAL_POWER_CAPACITY_COMPACT_CACHE.get(cache_key)
        if cached is not None:
            return int(cached)

        capacity: Optional[int] = None
        try:
            normalized = self._normalize_rectangle_frontier_signature(tpl, compact_signature)
        except _RectangleFrontierDPFallback:
            normalized = tuple()
        class_tag: Optional[str] = None
        if normalized:
            class_tag = self._compact_rect_cpsat_class_tag_from_normalized(tpl, normalized)
            self._bump_compact_rect_cpsat_stats(cache_stats, class_tag, "selected_cases")
            normalized_cached = _LOCAL_POWER_CAPACITY_NORMALIZED_RECT_CACHE.get(normalized)
            if normalized_cached is not None:
                if cache_stats is not None:
                    cache_stats["normalized_rect_cache_hits"] = int(
                        cache_stats.get("normalized_rect_cache_hits", 0)
                    ) + 1
                _LOCAL_POWER_CAPACITY_COMPACT_CACHE[cache_key] = int(normalized_cached)
                legacy_signature = self._legacy_local_power_capacity_signature_by_template_compact_signature.get(
                    tpl,
                    {},
                ).get(compact_signature)
                if legacy_signature is not None:
                    _LOCAL_POWER_CAPACITY_CACHE.setdefault(
                        (tpl, legacy_signature),
                        int(normalized_cached),
                    )
                return int(normalized_cached)
            if cache_stats is not None:
                cache_stats["normalized_rect_cache_misses"] = int(
                    cache_stats.get("normalized_rect_cache_misses", 0)
                ) + 1

        try:
            capacity = self._solve_exact_local_power_capacity_compact_rect_cpsat_v2(
                tpl,
                compact_signature,
                cache_stats=cache_stats,
                normalized=normalized if normalized else None,
                class_tag=class_tag,
            )
        except _RectangleFrontierDPFallback:
            capacity = None
        except _CompactRectCpSatFallback:
            self._bump_compact_rect_cpsat_stats(
                cache_stats,
                class_tag,
                "rect_dp_fallbacks",
            )
            try:
                capacity = self._solve_exact_local_power_capacity_rectangle_frontier_dp(
                    tpl,
                    compact_signature,
                    cache_stats=cache_stats,
                )
            except _RectangleFrontierDPFallback:
                capacity = None

        legacy_signature: Optional[LocalCapacitySignature] = None
        if capacity is None:
            if cache_stats is not None:
                cache_stats["bitset_fallbacks"] = int(
                    cache_stats.get("bitset_fallbacks", 0)
                ) + 1
                cache_stats["bitset_oracle_evaluations"] = int(
                    cache_stats.get("bitset_oracle_evaluations", 0)
                ) + 1
            legacy_signature = self._ensure_local_power_capacity_legacy_signature_materialized(
                tpl,
                compact_signature,
                cache_stats=cache_stats,
            )
            try:
                capacity = self._solve_exact_local_power_capacity_bitset_mis(
                    tpl,
                    legacy_signature,
                )
            except _BitsetLocalCapacityFallback:
                if cache_stats is not None:
                    cache_stats["cpsat_fallbacks"] = int(
                        cache_stats.get("cpsat_fallbacks", 0)
                    ) + 1
                capacity = self._solve_exact_local_power_capacity_cpsat(
                    tpl,
                    legacy_signature,
                )

        if capacity is None:
            if legacy_signature is None:
                legacy_signature = self._ensure_local_power_capacity_legacy_signature_materialized(
                    tpl,
                    compact_signature,
                    cache_stats=cache_stats,
                )
            if cache_stats is not None:
                cache_stats["cpsat_fallbacks"] = int(
                    cache_stats.get("cpsat_fallbacks", 0)
                ) + 1
            capacity = self._solve_exact_local_power_capacity_cpsat(
                tpl,
                legacy_signature,
            )

        if normalized:
            _LOCAL_POWER_CAPACITY_NORMALIZED_RECT_CACHE[normalized] = int(capacity)
        _LOCAL_POWER_CAPACITY_COMPACT_CACHE[cache_key] = int(capacity)
        legacy_signature = self._legacy_local_power_capacity_signature_by_template_compact_signature.get(
            tpl,
            {},
        ).get(compact_signature)
        if legacy_signature is not None:
            _LOCAL_POWER_CAPACITY_CACHE.setdefault((tpl, legacy_signature), int(capacity))
        return int(capacity)

    def _solve_exact_local_power_capacity(
        self,
        tpl: str,
        signature: LocalCapacitySignature,
        *,
        compact_signature: Optional[CompactLocalCapacitySignature] = None,
        cache_stats: Optional[Dict[str, Any]] = None,
    ) -> int:
        if not signature:
            return 0

        if compact_signature is not None:
            capacity = self._solve_exact_local_power_capacity_from_compact(
                str(tpl),
                compact_signature,
                cache_stats=cache_stats,
            )
            _LOCAL_POWER_CAPACITY_CACHE.setdefault((str(tpl), signature), int(capacity))
            return int(capacity)

        legacy_key = (str(tpl), signature)
        cached = _LOCAL_POWER_CAPACITY_CACHE.get(legacy_key)
        if cached is not None:
            return int(cached)

        if cache_stats is not None:
            cache_stats["bitset_oracle_evaluations"] = int(
                cache_stats.get("bitset_oracle_evaluations", 0)
            ) + 1
        try:
            capacity = self._solve_exact_local_power_capacity_bitset_mis(str(tpl), signature)
        except _BitsetLocalCapacityFallback:
            if cache_stats is not None:
                cache_stats["cpsat_fallbacks"] = int(
                    cache_stats.get("cpsat_fallbacks", 0)
                ) + 1
            capacity = self._solve_exact_local_power_capacity_cpsat(str(tpl), signature)

        if capacity is None:
            if cache_stats is not None:
                cache_stats["cpsat_fallbacks"] = int(
                    cache_stats.get("cpsat_fallbacks", 0)
                ) + 1
            capacity = self._solve_exact_local_power_capacity_cpsat(str(tpl), signature)

        _LOCAL_POWER_CAPACITY_CACHE[legacy_key] = int(capacity)
        return int(capacity)

    def _exact_local_power_capacity_coefficients(
        self,
        powered_template_demands: Mapping[str, int],
        cache_stats: Dict[str, Any],
    ) -> Dict[str, Dict[int, int]]:
        coeff_by_template_and_pole: Dict[str, Dict[int, int]] = {}
        normalized_signatures_seen: Set[NormalizedRectangleSignature] = set()
        shell_pair_items = sorted(self._power_pole_pose_indices_by_shell_pair.items())
        template_order = sorted(str(tpl) for tpl in powered_template_demands)

        cache_stats.setdefault("raw_pole_evaluations", 0)
        cache_stats.setdefault("coefficient_source", "exact_compact_rect_cpsat_v14")
        cache_stats.setdefault("shell_pair_count", len(shell_pair_items))
        cache_stats.setdefault("signature_class_count", 0)
        cache_stats.setdefault("signature_class_evaluations", 0)
        cache_stats.setdefault("compact_signature_class_count", 0)
        cache_stats.setdefault("compact_signature_class_evaluations", 0)
        cache_stats.setdefault("compact_signature_hits", 0)
        cache_stats.setdefault("compact_signature_misses", 0)
        cache_stats.setdefault("normalized_rect_signature_count", 0)
        cache_stats.setdefault("normalized_rect_cache_hits", 0)
        cache_stats.setdefault("normalized_rect_cache_misses", 0)
        cache_stats.setdefault("legacy_signature_materializations", 0)
        cache_stats.setdefault("supported_by_pole_materializations", 0)
        cache_stats.setdefault("compact_rect_cpsat_evaluations", 0)
        cache_stats.setdefault("compact_rect_cpsat_cache_hits", 0)
        cache_stats.setdefault("compact_rect_cpsat_selected_cases", 0)
        cache_stats.setdefault("compact_rect_cpsat_rect_dp_fallbacks", 0)
        cache_stats.setdefault("rect_dp_evaluations", 0)
        cache_stats.setdefault("rect_dp_cache_hits", 0)
        cache_stats.setdefault("rect_dp_cache_misses", 0)
        cache_stats.setdefault("rect_dp_state_merges", 0)
        cache_stats.setdefault("rect_dp_peak_line_states", 0)
        cache_stats.setdefault("rect_dp_peak_pos_states", 0)
        cache_stats.setdefault("rect_dp_compiled_signatures", 0)
        cache_stats.setdefault("rect_dp_compiled_start_options", 0)
        cache_stats.setdefault("rect_dp_deduped_start_options", 0)
        cache_stats.setdefault("rect_dp_compiled_line_subsets", 0)
        cache_stats.setdefault("rect_dp_peak_line_subset_options", 0)
        cache_stats.setdefault("rect_dp_v3_fallbacks", 0)
        cache_stats.setdefault("m6x4_mixed_cpsat_evaluations", 0)
        cache_stats.setdefault("m6x4_mixed_cpsat_cache_hits", 0)
        cache_stats.setdefault("m6x4_mixed_cpsat_selected_cases", 0)
        cache_stats.setdefault("m6x4_mixed_cpsat_v3_fallbacks", 0)
        cache_stats.setdefault("uniform_3x3_cpsat_evaluations", 0)
        cache_stats.setdefault("uniform_3x3_cpsat_cache_hits", 0)
        cache_stats.setdefault("uniform_3x3_cpsat_selected_cases", 0)
        cache_stats.setdefault("uniform_3x3_cpsat_v3_fallbacks", 0)
        cache_stats.setdefault("bitset_oracle_evaluations", 0)
        cache_stats.setdefault("bitset_fallbacks", 0)
        cache_stats.setdefault("cpsat_fallbacks", 0)
        cache_stats.setdefault("oracle", "compact_rect_cpsat_v2")
        shell_pair_evaluations = 0
        for tpl in template_order:
            coeff_by_template_and_pole[str(tpl)] = {}
            compact_signature_classes = self._ensure_local_power_capacity_compact_signature_classes(
                str(tpl)
            )
            shell_pair_compact_signatures = (
                self._power_pole_compact_capacity_signatures_by_template_shell_pair.get(
                    str(tpl),
                    {},
                )
            )
            cache_stats["compact_signature_class_count"] += int(len(compact_signature_classes))
            cache_stats["signature_class_count"] += int(len(compact_signature_classes))
            for _shell_pair, pose_indices in shell_pair_items:
                shell_pair_signatures = shell_pair_compact_signatures.get(_shell_pair, tuple())
                shell_pair_evaluations += int(len(shell_pair_signatures))
                cache_stats["raw_pole_evaluations"] += int(len(pose_indices))
            for compact_signature, grouped_pose_indices in sorted(compact_signature_classes.items()):
                cache_stats["pole_template_evaluations"] += 1
                try:
                    normalized = self._normalize_rectangle_frontier_signature(
                        str(tpl),
                        compact_signature,
                    )
                except _RectangleFrontierDPFallback:
                    normalized = tuple()
                if normalized:
                    normalized_signatures_seen.add(tuple(normalized))
                cache_key = (str(tpl), compact_signature)
                coeff = _LOCAL_POWER_CAPACITY_COMPACT_CACHE.get(cache_key)
                if coeff is None:
                    cache_stats["signature_misses"] += 1
                    cache_stats["signature_class_evaluations"] += 1
                    cache_stats["compact_signature_misses"] += 1
                    cache_stats["compact_signature_class_evaluations"] += 1
                    coeff = self._solve_exact_local_power_capacity_from_compact(
                        str(tpl),
                        compact_signature,
                        cache_stats=cache_stats,
                    )
                else:
                    cache_stats["signature_hits"] += 1
                    cache_stats["compact_signature_hits"] += 1
                for pole_idx in grouped_pose_indices:
                    coeff_by_template_and_pole[str(tpl)][int(pole_idx)] = int(coeff)

        cache_stats["signature_count"] = int(len(_LOCAL_POWER_CAPACITY_COMPACT_CACHE))
        cache_stats["normalized_rect_signature_count"] = int(
            len(normalized_signatures_seen)
        )
        cache_stats["rect_dp_compiled_signatures"] = int(
            len(_LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE)
        )
        cache_stats["rect_dp_compiled_start_options"] = int(
            sum(
                int(item.compiled_start_options)
                for item in _LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE.values()
            )
        )
        cache_stats["rect_dp_deduped_start_options"] = int(
            sum(
                int(item.deduped_start_options)
                for item in _LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE.values()
            )
        )
        cache_stats["rect_dp_compiled_line_subsets"] = int(
            sum(
                int(item.compiled_line_subsets)
                for item in _LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE.values()
            )
        )
        cache_stats["rect_dp_peak_line_subset_options"] = int(
            max(
                [0]
                + [
                    int(item.peak_line_subset_options)
                    for item in _LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE.values()
                ]
            )
        )
        self._update_exact_precompute_profile(
            power_capacity_shell_pairs=int(len(shell_pair_items)),
            power_capacity_shell_pair_evaluations=int(shell_pair_evaluations),
            power_capacity_signature_classes=int(cache_stats["signature_class_count"]),
            power_capacity_signature_class_evaluations=int(
                cache_stats["signature_class_evaluations"]
            ),
            power_capacity_compact_signature_classes=int(
                cache_stats["compact_signature_class_count"]
            ),
            power_capacity_compact_signature_evaluations=int(
                cache_stats["compact_signature_class_evaluations"]
            ),
            power_capacity_compact_signature_cache_hits=int(
                cache_stats["compact_signature_hits"]
            ),
            power_capacity_compact_signature_cache_misses=int(
                cache_stats["compact_signature_misses"]
            ),
            power_capacity_normalized_rect_signature_count=int(
                cache_stats["normalized_rect_signature_count"]
            ),
            power_capacity_normalized_rect_cache_hits=int(
                cache_stats["normalized_rect_cache_hits"]
            ),
            power_capacity_normalized_rect_cache_misses=int(
                cache_stats["normalized_rect_cache_misses"]
            ),
            power_capacity_legacy_signature_materializations=int(
                cache_stats["legacy_signature_materializations"]
            ),
            power_capacity_supported_by_pole_materializations=int(
                self._exact_precompute_profile.get(
                    "power_capacity_supported_by_pole_materializations",
                    0,
                )
            ),
            power_capacity_compact_rect_cpsat_evaluations=int(
                cache_stats["compact_rect_cpsat_evaluations"]
            ),
            power_capacity_compact_rect_cpsat_cache_hits=int(
                cache_stats["compact_rect_cpsat_cache_hits"]
            ),
            power_capacity_compact_rect_cpsat_selected_cases=int(
                cache_stats["compact_rect_cpsat_selected_cases"]
            ),
            power_capacity_compact_rect_cpsat_rect_dp_fallbacks=int(
                cache_stats["compact_rect_cpsat_rect_dp_fallbacks"]
            ),
            power_capacity_rect_dp_evaluations=int(cache_stats["rect_dp_evaluations"]),
            power_capacity_rect_dp_cache_hits=int(cache_stats["rect_dp_cache_hits"]),
            power_capacity_rect_dp_cache_misses=int(cache_stats["rect_dp_cache_misses"]),
            power_capacity_rect_dp_state_merges=int(cache_stats["rect_dp_state_merges"]),
            power_capacity_rect_dp_peak_line_states=int(
                cache_stats["rect_dp_peak_line_states"]
            ),
            power_capacity_rect_dp_peak_pos_states=int(
                cache_stats["rect_dp_peak_pos_states"]
            ),
            power_capacity_rect_dp_compiled_signatures=int(
                cache_stats["rect_dp_compiled_signatures"]
            ),
            power_capacity_rect_dp_compiled_start_options=int(
                cache_stats["rect_dp_compiled_start_options"]
            ),
            power_capacity_rect_dp_deduped_start_options=int(
                cache_stats["rect_dp_deduped_start_options"]
            ),
            power_capacity_rect_dp_compiled_line_subsets=int(
                cache_stats["rect_dp_compiled_line_subsets"]
            ),
            power_capacity_rect_dp_peak_line_subset_options=int(
                cache_stats["rect_dp_peak_line_subset_options"]
            ),
            power_capacity_rect_dp_v3_fallbacks=int(
                cache_stats["rect_dp_v3_fallbacks"]
            ),
            power_capacity_m6x4_mixed_cpsat_evaluations=int(
                cache_stats["m6x4_mixed_cpsat_evaluations"]
            ),
            power_capacity_m6x4_mixed_cpsat_cache_hits=int(
                cache_stats["m6x4_mixed_cpsat_cache_hits"]
            ),
            power_capacity_m6x4_mixed_cpsat_selected_cases=int(
                cache_stats["m6x4_mixed_cpsat_selected_cases"]
            ),
            power_capacity_m6x4_mixed_cpsat_v3_fallbacks=int(
                cache_stats["m6x4_mixed_cpsat_v3_fallbacks"]
            ),
            power_capacity_uniform_3x3_cpsat_evaluations=int(
                cache_stats["uniform_3x3_cpsat_evaluations"]
            ),
            power_capacity_uniform_3x3_cpsat_cache_hits=int(
                cache_stats["uniform_3x3_cpsat_cache_hits"]
            ),
            power_capacity_uniform_3x3_cpsat_selected_cases=int(
                cache_stats["uniform_3x3_cpsat_selected_cases"]
            ),
            power_capacity_uniform_3x3_cpsat_v3_fallbacks=int(
                cache_stats["uniform_3x3_cpsat_v3_fallbacks"]
            ),
            power_capacity_bitset_oracle_evaluations=int(
                cache_stats["bitset_oracle_evaluations"]
            ),
            power_capacity_bitset_fallbacks=int(cache_stats["bitset_fallbacks"]),
            power_capacity_cpsat_fallbacks=int(cache_stats["cpsat_fallbacks"]),
            power_capacity_oracle=str(cache_stats.get("oracle", "compact_rect_cpsat_v2")),
            power_capacity_raw_pole_evaluations=int(cache_stats["raw_pole_evaluations"]),
        )
        return coeff_by_template_and_pole

    def _exact_local_power_capacity_coefficient(
        self,
        tpl: str,
        pole_idx: int,
        cache_stats: Dict[str, Any],
    ) -> int:
        coeff_by_template_and_pole = self._exact_local_power_capacity_coefficients(
            {str(tpl): 1},
            cache_stats,
        )
        return int(coeff_by_template_and_pole[str(tpl)][int(pole_idx)])

    def _candidate_pose_indices_for_group(self, group: Mapping[str, Any]) -> List[int]:
        tpl = str(group["facility_type"])
        cached = self._candidate_pose_indices_by_template.get(tpl)
        if cached is not None:
            return list(cached)
        pool = self.facility_pools.get(tpl, [])
        if not pool:
            return []

        candidate_indices = list(range(len(pool)))
        if tpl in self._powered_templates and tpl != "power_pole":
            pose_coverers = self._power_coverers_by_template_pose.get(tpl, {})
            candidate_indices = [
                pose_idx
                for pose_idx in candidate_indices
                if pose_coverers.get(pose_idx, [])
            ]
        candidate_indices.sort(key=lambda pose_idx: self._pose_sort_key(tpl, pose_idx))
        self._candidate_pose_indices_by_template[tpl] = list(candidate_indices)
        return list(candidate_indices)

    def _ordered_mandatory_groups_for_greedy(
        self,
        candidates_by_group: Optional[Mapping[str, Sequence[int]]] = None,
    ) -> List[Mapping[str, Any]]:
        if candidates_by_group is None:
            candidates_by_group = {
                str(group["group_id"]): self._candidate_pose_indices_for_group(group)
                for group in self._mandatory_groups
            }
        return sorted(
            self._mandatory_groups,
            key=lambda group: (
                len(candidates_by_group.get(str(group["group_id"]), [])),
                str(group["facility_type"]),
                str(group["group_id"]),
            ),
        )

    def _run_mandatory_greedy_pass(
        self,
        *,
        ordered_groups: Sequence[Mapping[str, Any]],
        candidates_by_group: Mapping[str, Sequence[int]],
        blocked_cells: Optional[Set[Tuple[int, int]]] = None,
        initial_solution_hint: Optional[Mapping[str, int]] = None,
        initial_committed_cells: Optional[Set[Tuple[int, int]]] = None,
        initial_hinted_occupied_cells: Optional[Set[Tuple[int, int]]] = None,
        custom_group_orders: Optional[Mapping[str, Sequence[int]]] = None,
        stop_on_first_failure: bool = False,
    ) -> Dict[str, Any]:
        blocked_cells_only: Set[Tuple[int, int]] = {
            (int(cell[0]), int(cell[1])) for cell in (blocked_cells or set())
        }
        committed_cells: Set[Tuple[int, int]] = (
            {
                (int(cell[0]), int(cell[1]))
                for cell in (initial_committed_cells or set())
            }
            if initial_committed_cells is not None
            else set(blocked_cells_only)
        )
        hinted_occupied_cells: Set[Tuple[int, int]] = {
            (int(cell[0]), int(cell[1]))
            for cell in (initial_hinted_occupied_cells or set())
        }
        solution_hint: Dict[str, int] = {
            str(instance_id): int(pose_idx)
            for instance_id, pose_idx in dict(initial_solution_hint or {}).items()
        }
        hinted_groups = 0
        skipped_groups: List[str] = []
        first_failed_group_id: Optional[str] = None
        first_failed_group_template: Optional[str] = None
        first_failed_group_required_count = 0
        first_failed_group_candidate_count = 0
        first_failed_group_surviving_after_blocked_count = 0
        first_failed_group_surviving_at_failure_count = 0
        first_failure_reason: Optional[str] = None
        first_failed_group_position: Optional[int] = None
        chosen_pose_indices_by_group: Dict[str, List[int]] = {}
        used_power_coverage_filter = False

        for position, group in enumerate(ordered_groups):
            group_id = str(group["group_id"])
            tpl = str(group["facility_type"])
            if tpl in self._powered_templates and tpl != "power_pole":
                used_power_coverage_filter = True
            required_count = int(group["count"])
            base_candidate_indices = [
                int(pose_idx) for pose_idx in candidates_by_group.get(group_id, [])
            ]
            candidate_indices = [
                int(pose_idx)
                for pose_idx in dict(custom_group_orders or {}).get(
                    group_id,
                    base_candidate_indices,
                )
            ]
            surviving_after_blocked = [
                int(pose_idx)
                for pose_idx in base_candidate_indices
                if blocked_cells_only.isdisjoint(
                    self._pose_greedy_blocking_cells(tpl, int(pose_idx))
                )
            ]
            surviving_at_failure = [
                int(pose_idx)
                for pose_idx in base_candidate_indices
                if committed_cells.isdisjoint(
                    self._pose_greedy_blocking_cells(tpl, int(pose_idx))
                )
            ]

            trial_cells = set(committed_cells)
            trial_hinted_cells = set(hinted_occupied_cells)
            chosen_pose_indices: List[int] = []
            for pose_idx in candidate_indices:
                pose_cells = self._pose_cells(tpl, int(pose_idx))
                blocking_cells = self._pose_greedy_blocking_cells(tpl, int(pose_idx))
                if trial_cells.intersection(blocking_cells):
                    continue
                trial_cells.update(blocking_cells)
                trial_hinted_cells.update(pose_cells)
                chosen_pose_indices.append(int(pose_idx))
                if len(chosen_pose_indices) == required_count:
                    break

            if len(chosen_pose_indices) != required_count:
                skipped_groups.append(group_id)
                if first_failed_group_id is None:
                    if len(surviving_after_blocked) < required_count:
                        first_failure_reason = "blocked_cells_exhausted"
                    elif len(surviving_at_failure) < required_count:
                        first_failure_reason = "committed_cells_exhausted"
                    else:
                        first_failure_reason = "intra_group_greedy_exhausted"
                    first_failed_group_id = str(group_id)
                    first_failed_group_template = str(tpl)
                    first_failed_group_required_count = int(required_count)
                    first_failed_group_candidate_count = int(len(base_candidate_indices))
                    first_failed_group_surviving_after_blocked_count = int(
                        len(surviving_after_blocked)
                    )
                    first_failed_group_surviving_at_failure_count = int(
                        len(surviving_at_failure)
                    )
                    first_failed_group_position = int(position)
                if stop_on_first_failure:
                    break
                continue

            committed_cells = trial_cells
            hinted_occupied_cells = trial_hinted_cells
            hinted_groups += 1
            chosen_pose_indices_by_group[group_id] = list(chosen_pose_indices)
            for instance_id, pose_idx in zip(list(group["instance_ids"]), chosen_pose_indices):
                solution_hint[str(instance_id)] = int(pose_idx)

        hinted_instances = len(solution_hint)
        greedy_stats: Dict[str, Any] = {
            "supported": True,
            "complete": first_failed_group_id is None and hinted_groups == len(ordered_groups),
            "hinted_groups": int(hinted_groups),
            "hinted_instances": int(hinted_instances),
            "skipped_groups": list(skipped_groups),
            "used_power_coverage_filter": bool(used_power_coverage_filter),
            "solution_hint": dict(solution_hint),
            "committed_cells": set(committed_cells),
            "hinted_occupied_cells": set(hinted_occupied_cells),
            "first_failed_group_id": first_failed_group_id,
            "first_failed_group_template": first_failed_group_template,
            "first_failed_group_required_count": int(first_failed_group_required_count),
            "first_failed_group_candidate_count": int(first_failed_group_candidate_count),
            "first_failed_group_surviving_after_blocked_count": int(
                first_failed_group_surviving_after_blocked_count
            ),
            "first_failed_group_surviving_at_failure_count": int(
                first_failed_group_surviving_at_failure_count
            ),
            "first_failure_reason": first_failure_reason,
            "first_failed_group_position": first_failed_group_position,
            "chosen_pose_indices_by_group": {
                str(group_id): [int(pose_idx) for pose_idx in pose_indices]
                for group_id, pose_indices in chosen_pose_indices_by_group.items()
            },
        }
        if hinted_instances == 0:
            greedy_stats["reason"] = "no exact-safe greedy placements found"
        return greedy_stats

    def _local_repair_pose_orderings(
        self,
        tpl: str,
        candidate_indices: Sequence[int],
        frozen_committed_cells: Set[Tuple[int, int]],
    ) -> Dict[str, List[int]]:
        canonical = [
            int(pose_idx)
            for pose_idx in candidate_indices
            if frozen_committed_cells.isdisjoint(
                self._pose_greedy_blocking_cells(tpl, int(pose_idx))
            )
        ]
        if not canonical:
            return {
                "canonical": [],
                "reverse_canonical": [],
                "overlap_degree_asc": [],
                "overlap_degree_desc": [],
            }

        pose_cells_by_idx = {
            int(pose_idx): self._pose_greedy_blocking_cells(tpl, int(pose_idx))
            for pose_idx in canonical
        }
        cell_to_pose_indices: DefaultDict[Tuple[int, int], Set[int]] = defaultdict(set)
        for pose_idx, pose_cells in pose_cells_by_idx.items():
            for cell in pose_cells:
                cell_to_pose_indices[(int(cell[0]), int(cell[1]))].add(int(pose_idx))

        canonical_rank = {
            int(pose_idx): int(rank) for rank, pose_idx in enumerate(canonical)
        }
        overlap_degree_by_idx: Dict[int, int] = {}
        for pose_idx, pose_cells in pose_cells_by_idx.items():
            overlapping_pose_indices: Set[int] = set()
            for cell in pose_cells:
                overlapping_pose_indices.update(
                    int(other_pose_idx)
                    for other_pose_idx in cell_to_pose_indices[(int(cell[0]), int(cell[1]))]
                )
            overlapping_pose_indices.discard(int(pose_idx))
            overlap_degree_by_idx[int(pose_idx)] = int(len(overlapping_pose_indices))

        return {
            "canonical": list(canonical),
            "reverse_canonical": list(reversed(canonical)),
            "overlap_degree_asc": sorted(
                canonical,
                key=lambda pose_idx: (
                    int(overlap_degree_by_idx[int(pose_idx)]),
                    int(canonical_rank[int(pose_idx)]),
                ),
            ),
            "overlap_degree_desc": sorted(
                canonical,
                key=lambda pose_idx: (
                    -int(overlap_degree_by_idx[int(pose_idx)]),
                    int(canonical_rank[int(pose_idx)]),
                ),
            ),
        }

    def _y_then_x_pose_order(
        self,
        tpl: str,
        candidate_indices: Sequence[int],
    ) -> List[int]:
        anchors_by_pose = self._pose_anchor_by_template_pose.get(str(tpl), {})
        return sorted(
            [int(pose_idx) for pose_idx in candidate_indices],
            key=lambda pose_idx: (
                int(anchors_by_pose.get(int(pose_idx), (0, 0))[1]),
                int(anchors_by_pose.get(int(pose_idx), (0, 0))[0]),
                str(self.facility_pools[str(tpl)][int(pose_idx)].get("pose_id", "")),
                int(pose_idx),
            ),
        )

    def _ghost_aware_pose_order_portfolio(
        self,
        *,
        ordered_groups: Sequence[Mapping[str, Any]],
        candidates_by_group: Mapping[str, Sequence[int]],
    ) -> Dict[str, Dict[str, List[int]]]:
        y_then_x_orders: Dict[str, List[int]] = {}
        changed = False
        for group in ordered_groups:
            group_id = str(group["group_id"])
            tpl = str(group["facility_type"])
            canonical = [int(pose_idx) for pose_idx in candidates_by_group.get(group_id, [])]
            y_then_x = self._y_then_x_pose_order(tpl, canonical)
            y_then_x_orders[group_id] = list(y_then_x)
            if y_then_x != canonical:
                changed = True
        if not changed:
            return {}
        return {"y_then_x": y_then_x_orders}

    def _validate_coordinate_forced_hint(
        self,
        *,
        solution_hint: Mapping[str, int],
        ghost_anchor_hint_idx: Optional[int],
        time_limit_seconds: float,
        require_complete: bool = True,
        solver_parameter_profile: Optional[Mapping[str, Any]] = None,
        force_fields: Sequence[str] = ("x", "y", "mode"),
        use_assumptions: bool = False,
        force_equality_keys: Optional[Collection[str]] = None,
        collect_force_equality_labels: bool = False,
    ) -> Dict[str, Any]:
        forced_fields = _normalize_coordinate_force_fields(force_fields)
        selected_force_equality_keys = (
            None
            if force_equality_keys is None
            else {str(key) for key in force_equality_keys}
        )
        if self._coordinate_delegate is None:
            return {
                "attempted": False,
                "status": "SKIPPED",
                "accepted": True,
                "reason": "coordinate_delegate_unavailable",
                "forced_slot_field_count": 0,
                "forced_ghost_anchor": ghost_anchor_hint_idx is not None,
                "require_complete": bool(require_complete),
                "forced_fields": list(forced_fields),
                "use_assumptions": bool(use_assumptions),
                "assumption_core_supported": False,
                "assumption_count": 0,
                "assumption_labels": [],
                "infeasible_assumption_core": [],
                "infeasible_assumption_core_status": "not_evaluated",
                "force_equality_filter_active": selected_force_equality_keys is not None,
                "force_equality_labels": [],
            }
        if float(time_limit_seconds) <= 0.0:
            return {
                "attempted": False,
                "status": "SKIPPED",
                "accepted": False,
                "reason": "validation_disabled",
                "forced_slot_field_count": 0,
                "forced_ghost_anchor": ghost_anchor_hint_idx is not None,
                "require_complete": bool(require_complete),
                "forced_fields": list(forced_fields),
                "use_assumptions": bool(use_assumptions),
                "assumption_core_supported": False,
                "assumption_count": 0,
                "assumption_labels": [],
                "infeasible_assumption_core": [],
                "infeasible_assumption_core_status": "not_evaluated",
                "force_equality_filter_active": selected_force_equality_keys is not None,
                "force_equality_labels": [],
            }

        capacity_precheck: Dict[str, Any] = {"evaluated": False}
        if _exact_same_x_strip_fixed_ghost_capacity_precheck_enabled():
            capacity_precheck = evaluate_same_x_strip_fixed_ghost_capacity_conflict(
                self,
                solution_hint=solution_hint,
                ghost_anchor_hint_idx=ghost_anchor_hint_idx,
                force_fields=forced_fields,
                force_equality_keys=selected_force_equality_keys,
            )
            if bool(capacity_precheck.get("conflict", False)):
                first_conflict = dict(capacity_precheck.get("first_conflict_bucket", {}))
                capacity_conflict = {
                    "reason": "same_x_strip_fixed_ghost_capacity_conflict",
                    "anchor_idx": int(capacity_precheck.get("anchor_idx", ghost_anchor_hint_idx or -1)),
                    "ghost_rect": dict(capacity_precheck.get("ghost_rect", {})),
                    "group_id": first_conflict.get("group_id"),
                    "x_interval": dict(first_conflict.get("x_interval", {})),
                    "slot_height": int(first_conflict.get("slot_height", 0)),
                    "forced_count": int(first_conflict.get("forced_count", 0)),
                    "capacity": int(first_conflict.get("capacity", 0)),
                    "lower_capacity": int(first_conflict.get("lower_capacity", 0)),
                    "upper_capacity": int(first_conflict.get("upper_capacity", 0)),
                    "force_equality_filter_active": selected_force_equality_keys is not None,
                    "y_capacity_source": first_conflict.get("y_capacity_source"),
                }
                return {
                    "attempted": False,
                    "attempted_solver": False,
                    "status": "INFEASIBLE",
                    "accepted": False,
                    "reason": "same_x_strip_fixed_ghost_capacity_conflict",
                    "capacity_conflict": capacity_conflict,
                    "same_x_strip_capacity_precheck": dict(capacity_precheck),
                    "wall_time": 0.0,
                    "user_time": 0.0,
                    "deterministic_time": 0.0,
                    "branches": 0,
                    "conflicts": 0,
                    "binary_propagations": 0,
                    "integer_propagations": 0,
                    "solver_parameters": {"profile_id": "same_x_strip_capacity_precheck"},
                    "response_stats": "",
                    "missing_hint_count": 0,
                    "missing_pose_tuple_count": 0,
                    "forced_slot_field_count": int(first_conflict.get("forced_count", 0)),
                    "forced_ghost_anchor": ghost_anchor_hint_idx is not None,
                    "require_complete": bool(require_complete),
                    "forced_fields": list(forced_fields),
                    "use_assumptions": bool(use_assumptions),
                    "assumption_core_supported": False,
                    "assumption_count": 0,
                    "assumption_labels": [],
                    "infeasible_assumption_core": [],
                    "infeasible_assumption_core_status": "precheck_conflict",
                    "force_equality_filter_active": selected_force_equality_keys is not None,
                    "force_equality_labels": list(
                        capacity_precheck.get("force_equality_labels", [])
                        if bool(collect_force_equality_labels)
                        else []
                    ),
                }

        ghost_overlap_forced_domain_precheck: Dict[str, Any] = {"evaluated": False}
        if _exact_ghost_overlap_forced_domain_precheck_enabled():
            ghost_overlap_forced_domain_precheck = dict(
                evaluate_ghost_overlap_forced_domain_conflict(
                    self,
                    solution_hint=solution_hint,
                    ghost_anchor_hint_idx=ghost_anchor_hint_idx,
                    force_fields=forced_fields,
                    force_equality_keys=selected_force_equality_keys,
                )
            )
            ghost_overlap_forced_domain_precheck.setdefault(
                "triggered",
                bool(ghost_overlap_forced_domain_precheck.get("conflict", False)),
            )
            if bool(ghost_overlap_forced_domain_precheck.get("conflict", False)):
                first_conflict = dict(
                    ghost_overlap_forced_domain_precheck.get("first_conflict", {})
                    or {}
                )
                conflict_selected_labels = [
                    dict(label)
                    for label in list(first_conflict.get("selected_labels", []))
                    if isinstance(label, Mapping)
                ]
                return {
                    "attempted": False,
                    "attempted_solver": False,
                    "status": "INFEASIBLE",
                    "accepted": False,
                    "reason": "ghost_overlap_forced_domain_infeasible",
                    "ghost_overlap_forced_domain_precheck": dict(
                        ghost_overlap_forced_domain_precheck
                    ),
                    "wall_time": 0.0,
                    "user_time": 0.0,
                    "deterministic_time": 0.0,
                    "branches": 0,
                    "conflicts": 0,
                    "binary_propagations": 0,
                    "integer_propagations": 0,
                    "solver_parameters": {
                        "profile_id": "ghost_overlap_forced_domain_precheck"
                    },
                    "response_stats": "",
                    "missing_hint_count": 0,
                    "missing_pose_tuple_count": 0,
                    "forced_slot_field_count": int(
                        len(conflict_selected_labels)
                        or int(
                            ghost_overlap_forced_domain_precheck.get(
                                "forced_label_count",
                                0,
                            )
                        )
                    ),
                    "forced_ghost_anchor": ghost_anchor_hint_idx is not None,
                    "require_complete": bool(require_complete),
                    "forced_fields": list(forced_fields),
                    "use_assumptions": bool(use_assumptions),
                    "assumption_core_supported": False,
                    "assumption_count": 0,
                    "assumption_labels": [],
                    "infeasible_assumption_core": [],
                    "infeasible_assumption_core_status": "precheck_conflict",
                    "force_equality_filter_active": selected_force_equality_keys is not None,
                    "force_equality_labels": (
                        conflict_selected_labels
                        if bool(collect_force_equality_labels)
                        else []
                    ),
                }

        ghost_y_overlap_precheck: Dict[str, Any] = {"evaluated": False}
        if _exact_ghost_y_overlap_forced_label_precheck_enabled():
            ghost_y_overlap_precheck = dict(
                evaluate_ghost_y_overlap_forced_label_conflict(
                    self,
                    solution_hint=solution_hint,
                    ghost_anchor_hint_idx=ghost_anchor_hint_idx,
                    force_fields=forced_fields,
                    force_equality_keys=selected_force_equality_keys,
                )
            )
            ghost_y_overlap_precheck.setdefault(
                "triggered",
                bool(ghost_y_overlap_precheck.get("conflict", False)),
            )
            if bool(ghost_y_overlap_precheck.get("conflict", False)):
                first_conflict = dict(
                    ghost_y_overlap_precheck.get("first_conflict", {}) or {}
                )
                return {
                    "attempted": False,
                    "attempted_solver": False,
                    "status": "INFEASIBLE",
                    "accepted": False,
                    "reason": "ghost_y_overlap_forced_label_infeasible",
                    "ghost_y_overlap_precheck": dict(ghost_y_overlap_precheck),
                    "wall_time": 0.0,
                    "user_time": 0.0,
                    "deterministic_time": 0.0,
                    "branches": 0,
                    "conflicts": 0,
                    "binary_propagations": 0,
                    "integer_propagations": 0,
                    "solver_parameters": {
                        "profile_id": "ghost_y_overlap_forced_label_precheck"
                    },
                    "response_stats": "",
                    "missing_hint_count": 0,
                    "missing_pose_tuple_count": 0,
                    "forced_slot_field_count": int(
                        ghost_y_overlap_precheck.get("conflict_count", 0)
                    ),
                    "forced_ghost_anchor": ghost_anchor_hint_idx is not None,
                    "require_complete": bool(require_complete),
                    "forced_fields": list(forced_fields),
                    "use_assumptions": bool(use_assumptions),
                    "assumption_core_supported": False,
                    "assumption_count": 0,
                    "assumption_labels": [],
                    "infeasible_assumption_core": [],
                    "infeasible_assumption_core_status": "precheck_conflict",
                    "force_equality_filter_active": selected_force_equality_keys is not None,
                    "force_equality_labels": [
                        dict(first_conflict)
                    ]
                    if bool(collect_force_equality_labels) and first_conflict
                    else [],
                }

        signature_monotonic_precheck: Dict[str, Any] = {"evaluated": False}
        if _exact_signature_monotonic_forced_label_precheck_enabled():
            signature_monotonic_precheck = dict(
                evaluate_signature_monotonic_forced_label_conflict(
                    self,
                    solution_hint=solution_hint,
                    force_fields=forced_fields,
                    force_equality_keys=selected_force_equality_keys,
                )
            )
            signature_monotonic_precheck.setdefault(
                "triggered",
                bool(signature_monotonic_precheck.get("conflict", False)),
            )
            if bool(signature_monotonic_precheck.get("conflict", False)):
                return {
                    "attempted": False,
                    "attempted_solver": False,
                    "status": "INFEASIBLE",
                    "accepted": False,
                    "reason": "signature_monotonic_forced_label_infeasible",
                    "signature_monotonic_precheck": dict(signature_monotonic_precheck),
                    "wall_time": 0.0,
                    "user_time": 0.0,
                    "deterministic_time": 0.0,
                    "branches": 0,
                    "conflicts": 0,
                    "binary_propagations": 0,
                    "integer_propagations": 0,
                    "solver_parameters": {
                        "profile_id": "signature_monotonic_forced_label_precheck"
                    },
                    "response_stats": "",
                    "missing_hint_count": 0,
                    "missing_pose_tuple_count": 0,
                    "forced_slot_field_count": int(
                        signature_monotonic_precheck.get("forced_label_count", 0)
                    ),
                    "forced_ghost_anchor": ghost_anchor_hint_idx is not None,
                    "require_complete": bool(require_complete),
                    "forced_fields": list(forced_fields),
                    "use_assumptions": bool(use_assumptions),
                    "assumption_core_supported": False,
                    "assumption_count": 0,
                    "assumption_labels": [],
                    "infeasible_assumption_core": [],
                    "infeasible_assumption_core_status": "precheck_conflict",
                    "force_equality_filter_active": selected_force_equality_keys is not None,
                    "force_equality_labels": [],
                }

        local_model = cp_model_from_proto(_clone_model_proto(self.model.Proto()))
        delegate = self._coordinate_delegate
        use_assumptions = bool(use_assumptions)
        assumption_core_supported = bool(
            hasattr(local_model, "AddAssumption")
            and hasattr(cp_model.CpSolver(), "SufficientAssumptionsForInfeasibility")
        )
        assumption_labels_by_index: Dict[int, Dict[str, Any]] = {}
        assumption_labels: List[Dict[str, Any]] = []
        force_equality_labels: List[Dict[str, Any]] = []
        grouped_hints: DefaultDict[str, List[int]] = defaultdict(list)
        optional_hints: DefaultDict[str, List[int]] = defaultdict(list)
        for solution_id, pose_idx in dict(solution_hint).items():
            solution_id = str(solution_id)
            pose_idx = int(pose_idx)
            if solution_id in self._group_id_by_instance:
                grouped_hints[str(self._group_id_by_instance[solution_id])].append(
                    int(pose_idx)
                )
                continue
            tpl = self._infer_optional_template_from_solution_id(solution_id)
            if tpl is not None:
                optional_hints[str(tpl)].append(int(pose_idx))

        forced_slot_field_count = 0
        missing_hint_count = 0
        missing_pose_tuple_count = 0

        def _local_int_var(var: Any) -> Any:
            return local_model.GetIntVarFromProtoIndex(int(var.Index()))

        def _local_bool_var(var: Any) -> Any:
            return local_model.GetBoolVarFromProtoIndex(int(var.Index()))

        def _force_equality_with_optional_assumption(
            *,
            var: Any,
            value: int,
            label: Dict[str, Any],
        ) -> int:
            stable_key = (
                "mandatory"
                + "|"
                + str(label["group_id"])
                + "|"
                + str(label["slot_index"])
                + "|"
                + str(label["solution_id"])
                + "|"
                + str(label["pose_index"])
                + "|"
                + str(label["field"])
            )
            enriched_label = dict(label)
            enriched_label["stable_key"] = stable_key
            selected = (
                selected_force_equality_keys is None
                or stable_key in selected_force_equality_keys
            )
            enriched_label["selected"] = bool(selected)
            if bool(collect_force_equality_labels):
                force_equality_labels.append(dict(enriched_label))
            if not selected:
                return 0
            local_var = _local_int_var(var)
            if use_assumptions and assumption_core_supported:
                assumption = local_model.NewBoolVar(
                    "assume_"
                    + str(label["solution_id"]).replace(":", "_")
                    + "_"
                    + str(label["slot_key"])
                    + "_"
                    + str(label["field"])
                )
                local_model.Add(local_var == int(value)).OnlyEnforceIf(assumption)
                local_model.AddAssumption(assumption)
                enriched = dict(enriched_label)
                enriched["assumption_index"] = int(assumption.Index())
                assumption_labels_by_index[int(assumption.Index())] = dict(enriched)
                assumption_labels.append(dict(enriched))
                return 1
            local_model.Add(local_var == int(value))
            return 1

        def _force_slot_pose(
            slot: Any,
            tpl: str,
            pose_idx: int,
            *,
            group_id: str,
            solution_id: str,
            slot_key: str,
            slot_index: int,
        ) -> bool:
            pose_tuple = delegate._template_pose_tuple_by_idx.get(str(tpl), {}).get(
                int(pose_idx)
            )
            if pose_tuple is None:
                return -1
            x_val, y_val, mode_id = pose_tuple
            added_count = 0
            if "x" in forced_fields:
                added_count += _force_equality_with_optional_assumption(
                    var=slot.x,
                    value=int(x_val),
                    label={
                        "group_id": str(group_id),
                        "solution_id": str(solution_id),
                        "slot_key": str(slot_key),
                        "slot_index": int(slot_index),
                        "template": str(tpl),
                        "pose_index": int(pose_idx),
                        "field": "x",
                        "forced_value": int(x_val),
                    },
                )
            if "y" in forced_fields:
                added_count += _force_equality_with_optional_assumption(
                    var=slot.y,
                    value=int(y_val),
                    label={
                        "group_id": str(group_id),
                        "solution_id": str(solution_id),
                        "slot_key": str(slot_key),
                        "slot_index": int(slot_index),
                        "template": str(tpl),
                        "pose_index": int(pose_idx),
                        "field": "y",
                        "forced_value": int(y_val),
                    },
                )
            if "mode" in forced_fields:
                added_count += _force_equality_with_optional_assumption(
                    var=slot.mode,
                    value=int(mode_id),
                    label={
                        "group_id": str(group_id),
                        "solution_id": str(solution_id),
                        "slot_key": str(slot_key),
                        "slot_index": int(slot_index),
                        "template": str(tpl),
                        "pose_index": int(pose_idx),
                        "field": "mode",
                        "forced_value": int(mode_id),
                    },
                )
            return int(added_count)

        for group in self._mandatory_groups:
            group_id = str(group["group_id"])
            tpl = str(group["facility_type"])
            slot_specs = list(delegate.mandatory_slots.get(group_id, []))
            solution_ids = [str(item) for item in list(group.get("instance_ids", []))]
            pose_indices = sorted(
                grouped_hints.get(group_id, []),
                key=lambda pose_idx: self._pose_sort_key(tpl, int(pose_idx)),
            )
            if len(pose_indices) < len(slot_specs):
                missing_hint_count += int(len(slot_specs) - len(pose_indices))
            for slot_index, (slot, pose_idx) in enumerate(zip(slot_specs, pose_indices)):
                solution_id = (
                    solution_ids[int(slot_index)]
                    if int(slot_index) < len(solution_ids)
                    else f"{group_id}::{slot_index}"
                )
                added_count = _force_slot_pose(
                    slot,
                    tpl,
                    int(pose_idx),
                    group_id=group_id,
                    solution_id=solution_id,
                    slot_key=str(slot_index),
                    slot_index=int(slot_index),
                )
                if added_count < 0:
                    missing_pose_tuple_count += 1
                    continue
                forced_slot_field_count += int(added_count)

        for tpl, slot_specs in delegate.required_optional_slots.items():
            pose_indices = sorted(
                optional_hints.get(str(tpl), []),
                key=lambda pose_idx: self._pose_sort_key(str(tpl), int(pose_idx)),
            )
            if len(pose_indices) < len(slot_specs):
                missing_hint_count += int(len(slot_specs) - len(pose_indices))
            for slot_index, (slot, pose_idx) in enumerate(zip(list(slot_specs), pose_indices)):
                added_count = _force_slot_pose(
                    slot,
                    str(tpl),
                    int(pose_idx),
                    group_id=f"optional::{tpl}",
                    solution_id=f"optional::{tpl}::{slot_index}",
                    slot_key=str(slot_index),
                    slot_index=int(slot_index),
                )
                if added_count < 0:
                    missing_pose_tuple_count += 1
                    continue
                forced_slot_field_count += int(added_count)

        if ghost_anchor_hint_idx is not None:
            u_var = self.u_vars.get(int(ghost_anchor_hint_idx))
            if u_var is not None:
                local_model.Add(_local_bool_var(u_var) == 1)

        if bool(require_complete) and (
            missing_hint_count > 0 or missing_pose_tuple_count > 0
        ):
            return {
                "attempted": False,
                "status": "SKIPPED",
                "accepted": False,
                "reason": "missing_hint_or_pose_tuple",
                "missing_hint_count": int(missing_hint_count),
                "missing_pose_tuple_count": int(missing_pose_tuple_count),
                "forced_slot_field_count": int(forced_slot_field_count),
                "forced_ghost_anchor": ghost_anchor_hint_idx is not None,
                "require_complete": bool(require_complete),
                "forced_fields": list(forced_fields),
                "use_assumptions": bool(use_assumptions),
                "assumption_core_supported": bool(assumption_core_supported),
                "assumption_count": int(len(assumption_labels)),
                "assumption_labels": list(assumption_labels),
                "infeasible_assumption_core": [],
                "infeasible_assumption_core_status": "not_evaluated",
                "force_equality_filter_active": selected_force_equality_keys is not None,
                "force_equality_labels": list(force_equality_labels),
            }

        solver = cp_model.CpSolver()
        solver_parameters = _apply_coordinate_validation_solver_profile(
            solver,
            time_limit_seconds=float(time_limit_seconds),
            profile=solver_parameter_profile,
        )
        status = solver.Solve(local_model)
        status_name = solver.StatusName(status)
        accepted = status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
        core_labels: List[Dict[str, Any]] = []
        core_status = "not_requested"
        if use_assumptions:
            if not assumption_core_supported:
                core_status = "unsupported"
            elif status == cp_model.INFEASIBLE:
                try:
                    raw_core = list(solver.SufficientAssumptionsForInfeasibility())
                except Exception:
                    raw_core = []
                    core_status = "api_error"
                if raw_core:
                    for raw_index in raw_core:
                        label = assumption_labels_by_index.get(abs(int(raw_index)))
                        if label is not None:
                            core_labels.append(dict(label))
                    core_status = "extracted" if core_labels else "unmapped"
                elif core_status != "api_error":
                    core_status = "empty"
            else:
                core_status = "not_infeasible"
        return {
            "attempted": True,
            "attempted_solver": True,
            "status": str(status_name),
            "accepted": bool(accepted),
            "reason": "accepted" if accepted else str(status_name).lower(),
            "wall_time": float(solver.WallTime()),
            "user_time": float(
                _extract_solver_numeric_stat(
                    solver,
                    "UserTime",
                    "user_time",
                    default=0.0,
                )
            ),
            "deterministic_time": float(
                _extract_solver_numeric_stat(
                    solver,
                    "deterministic_time",
                    default=0.0,
                )
            ),
            "branches": int(solver.NumBranches()),
            "conflicts": int(solver.NumConflicts()),
            "binary_propagations": int(
                _extract_solver_numeric_stat(
                    solver,
                    "num_binary_propagations",
                    default=0,
                )
            ),
            "integer_propagations": int(
                _extract_solver_numeric_stat(
                    solver,
                    "num_integer_propagations",
                    default=0,
                )
            ),
            "solver_parameters": solver_parameters,
            "response_stats": solver.ResponseStats(),
            "missing_hint_count": int(missing_hint_count),
            "missing_pose_tuple_count": int(missing_pose_tuple_count),
            "forced_slot_field_count": int(forced_slot_field_count),
            "forced_ghost_anchor": ghost_anchor_hint_idx is not None,
            "require_complete": bool(require_complete),
            "forced_fields": list(forced_fields),
            "use_assumptions": bool(use_assumptions),
            "assumption_core_supported": bool(assumption_core_supported),
            "assumption_count": int(len(assumption_labels)),
            "assumption_labels": list(assumption_labels),
            "infeasible_assumption_core": list(core_labels),
            "infeasible_assumption_core_status": str(core_status),
            "force_equality_filter_active": selected_force_equality_keys is not None,
            "force_equality_labels": list(force_equality_labels),
            "ghost_overlap_forced_domain_precheck": dict(
                ghost_overlap_forced_domain_precheck
            ),
            "ghost_y_overlap_precheck": dict(ghost_y_overlap_precheck),
            "signature_monotonic_precheck": dict(signature_monotonic_precheck),
        }

    def _attempt_mandatory_local_repair(
        self,
        *,
        anchor_idx: int,
        blocked_cells: Set[Tuple[int, int]],
        ordered_groups: Sequence[Mapping[str, Any]],
        candidates_by_group: Mapping[str, Sequence[int]],
        canonical_result: Mapping[str, Any],
    ) -> Dict[str, Any]:
        first_failure_reason = canonical_result.get("first_failure_reason")
        if first_failure_reason not in {
            "intra_group_greedy_exhausted",
            "committed_cells_exhausted",
        }:
            return {
                "attempted": False,
                "success": False,
                "trigger_reason": None,
                "window_size": 0,
                "anchor_idx": None,
                "failed_group_id": None,
                "failed_group_template": None,
                "portfolio_attempt_count": 0,
                "selected_group_orderings": [],
                "result": None,
                "attempt_count": 0,
                "success_count": 0,
                "intra_group_attempt_count": 0,
                "committed_attempt_count": 0,
                "window1_count": 0,
                "window2_count": 0,
            }

        failed_group_position = canonical_result.get("first_failed_group_position")
        if failed_group_position is None:
            return {
                "attempted": False,
                "success": False,
                "trigger_reason": None,
                "window_size": 0,
                "anchor_idx": None,
                "failed_group_id": None,
                "failed_group_template": None,
                "portfolio_attempt_count": 0,
                "selected_group_orderings": [],
                "result": None,
                "attempt_count": 0,
                "success_count": 0,
                "intra_group_attempt_count": 0,
                "committed_attempt_count": 0,
                "window1_count": 0,
                "window2_count": 0,
            }

        failed_group_position = int(failed_group_position)
        if str(first_failure_reason) == "committed_cells_exhausted" and failed_group_position > 0:
            window_start = int(failed_group_position - 1)
        else:
            window_start = int(failed_group_position)
        repair_groups = list(ordered_groups[window_start : failed_group_position + 1])
        suffix_groups = list(ordered_groups[failed_group_position + 1 :])
        prefix_groups = list(ordered_groups[:window_start])
        prefix_result = self._run_mandatory_greedy_pass(
            ordered_groups=prefix_groups,
            candidates_by_group=candidates_by_group,
            blocked_cells=set(blocked_cells),
            stop_on_first_failure=False,
        )
        if not bool(prefix_result.get("complete", False)):
            return {
                "attempted": True,
                "success": False,
                "trigger_reason": str(first_failure_reason),
                "window_size": int(len(repair_groups)),
                "anchor_idx": int(anchor_idx),
                "failed_group_id": canonical_result.get("first_failed_group_id"),
                "failed_group_template": canonical_result.get("first_failed_group_template"),
                "portfolio_attempt_count": 0,
                "selected_group_orderings": [],
                "result": None,
                "attempt_count": 1,
                "success_count": 0,
                "intra_group_attempt_count": 1
                if str(first_failure_reason) == "intra_group_greedy_exhausted"
                else 0,
                "committed_attempt_count": 1
                if str(first_failure_reason) == "committed_cells_exhausted"
                else 0,
                "window1_count": 1 if len(repair_groups) == 1 else 0,
                "window2_count": 1 if len(repair_groups) == 2 else 0,
            }

        order_portfolio = [
            "canonical",
            "reverse_canonical",
            "overlap_degree_asc",
            "overlap_degree_desc",
        ]
        frozen_prefix_committed_cells = set(prefix_result.get("committed_cells", set()))
        group_orderings: Dict[str, Dict[str, List[int]]] = {}
        for group in repair_groups:
            group_id = str(group["group_id"])
            tpl = str(group["facility_type"])
            group_orderings[group_id] = self._local_repair_pose_orderings(
                tpl,
                candidates_by_group.get(group_id, []),
                frozen_prefix_committed_cells,
            )

        portfolio_attempt_count = 0
        selected_group_orderings: List[str] = []
        selected_result: Optional[Dict[str, Any]] = None
        if len(repair_groups) == 1:
            repair_group_id = str(repair_groups[0]["group_id"])
            for order_name in order_portfolio:
                portfolio_attempt_count += 1
                window_result = self._run_mandatory_greedy_pass(
                    ordered_groups=repair_groups,
                    candidates_by_group=candidates_by_group,
                    blocked_cells=set(blocked_cells),
                    initial_solution_hint=prefix_result.get("solution_hint", {}),
                    initial_committed_cells=set(prefix_result.get("committed_cells", set())),
                    initial_hinted_occupied_cells=set(
                        prefix_result.get("hinted_occupied_cells", set())
                    ),
                    custom_group_orders={
                        repair_group_id: list(
                            group_orderings.get(repair_group_id, {}).get(order_name, [])
                        )
                    },
                    stop_on_first_failure=True,
                )
                if not bool(window_result.get("complete", False)):
                    continue
                selected_group_orderings = [str(order_name)]
                if not suffix_groups:
                    selected_result = window_result
                else:
                    suffix_result = self._run_mandatory_greedy_pass(
                        ordered_groups=suffix_groups,
                        candidates_by_group=candidates_by_group,
                        blocked_cells=set(blocked_cells),
                        initial_solution_hint=window_result.get("solution_hint", {}),
                        initial_committed_cells=set(
                            window_result.get("committed_cells", set())
                        ),
                        initial_hinted_occupied_cells=set(
                            window_result.get("hinted_occupied_cells", set())
                        ),
                        stop_on_first_failure=True,
                    )
                    if bool(suffix_result.get("complete", False)):
                        selected_result = suffix_result
                break
        else:
            previous_group_id = str(repair_groups[0]["group_id"])
            failed_group_id = str(repair_groups[1]["group_id"])
            for previous_order_name in order_portfolio:
                for failed_order_name in order_portfolio:
                    portfolio_attempt_count += 1
                    window_result = self._run_mandatory_greedy_pass(
                        ordered_groups=repair_groups,
                        candidates_by_group=candidates_by_group,
                        blocked_cells=set(blocked_cells),
                        initial_solution_hint=prefix_result.get("solution_hint", {}),
                        initial_committed_cells=set(
                            prefix_result.get("committed_cells", set())
                        ),
                        initial_hinted_occupied_cells=set(
                            prefix_result.get("hinted_occupied_cells", set())
                        ),
                        custom_group_orders={
                            previous_group_id: list(
                                group_orderings.get(previous_group_id, {}).get(
                                    previous_order_name,
                                    [],
                                )
                            ),
                            failed_group_id: list(
                                group_orderings.get(failed_group_id, {}).get(
                                    failed_order_name,
                                    [],
                                )
                            ),
                        },
                        stop_on_first_failure=True,
                    )
                    if not bool(window_result.get("complete", False)):
                        continue
                    selected_group_orderings = [
                        str(previous_order_name),
                        str(failed_order_name),
                    ]
                    if not suffix_groups:
                        selected_result = window_result
                    else:
                        suffix_result = self._run_mandatory_greedy_pass(
                            ordered_groups=suffix_groups,
                            candidates_by_group=candidates_by_group,
                            blocked_cells=set(blocked_cells),
                            initial_solution_hint=window_result.get("solution_hint", {}),
                            initial_committed_cells=set(
                                window_result.get("committed_cells", set())
                            ),
                            initial_hinted_occupied_cells=set(
                                window_result.get("hinted_occupied_cells", set())
                            ),
                            stop_on_first_failure=True,
                        )
                        if bool(suffix_result.get("complete", False)):
                            selected_result = suffix_result
                    break
                if selected_group_orderings:
                    break

        success = bool(selected_result is not None and selected_result.get("complete", False))
        return {
            "attempted": True,
            "success": bool(success),
            "trigger_reason": str(first_failure_reason),
            "window_size": int(len(repair_groups)),
            "anchor_idx": int(anchor_idx),
            "failed_group_id": canonical_result.get("first_failed_group_id"),
            "failed_group_template": canonical_result.get("first_failed_group_template"),
            "portfolio_attempt_count": int(portfolio_attempt_count),
            "selected_group_orderings": list(selected_group_orderings)
            if success
            else [],
            "result": selected_result if success else None,
            "attempt_count": 1,
            "success_count": 1 if success else 0,
            "intra_group_attempt_count": 1
            if str(first_failure_reason) == "intra_group_greedy_exhausted"
            else 0,
            "committed_attempt_count": 1
            if str(first_failure_reason) == "committed_cells_exhausted"
            else 0,
            "window1_count": 1 if len(repair_groups) == 1 else 0,
            "window2_count": 1 if len(repair_groups) == 2 else 0,
        }

    def _build_mandatory_greedy_solution_hint(
        self,
        blocked_cells: Optional[Set[Tuple[int, int]]] = None,
    ) -> Dict[str, Any]:
        empty_failure_payload = {
            "first_failed_group_id": None,
            "first_failed_group_template": None,
            "first_failed_group_required_count": 0,
            "first_failed_group_candidate_count": 0,
            "first_failed_group_surviving_after_blocked_count": 0,
            "first_failed_group_surviving_at_failure_count": 0,
            "first_failure_reason": None,
        }
        if not self.exact_mode:
            return {
                "supported": False,
                "complete": False,
                "hinted_groups": 0,
                "hinted_instances": 0,
                "skipped_groups": [],
                "used_power_coverage_filter": False,
                "reason": "exact-safe greedy warm start only runs in certified_exact mode",
                "solution_hint": {},
                "committed_cells": set(),
                "hinted_occupied_cells": set(),
                **empty_failure_payload,
            }

        if not self._mandatory_groups:
            return {
                "supported": True,
                "complete": True,
                "hinted_groups": 0,
                "hinted_instances": 0,
                "skipped_groups": [],
                "used_power_coverage_filter": False,
                "reason": "no mandatory exact groups available for warm start",
                "solution_hint": {},
                "committed_cells": set(),
                "hinted_occupied_cells": set(),
                **empty_failure_payload,
            }

        candidates_by_group = {
            str(group["group_id"]): self._candidate_pose_indices_for_group(group)
            for group in self._mandatory_groups
        }
        ordered_groups = self._ordered_mandatory_groups_for_greedy(candidates_by_group)
        return self._run_mandatory_greedy_pass(
            ordered_groups=ordered_groups,
            candidates_by_group=candidates_by_group,
            blocked_cells=set(blocked_cells or set()),
            stop_on_first_failure=False,
        )

    @staticmethod
    def _max_non_overlapping_closed_intervals(
        intervals: Sequence[Tuple[int, int]],
    ) -> int:
        if not intervals:
            return 0
        ordered_intervals = sorted(
            (
                (int(start), int(end))
                for start, end in intervals
            ),
            key=lambda item: (int(item[1]), int(item[0])),
        )
        selected = 0
        last_end = -(10**9)
        for start, end in ordered_intervals:
            if int(start) > int(last_end):
                selected += 1
                last_end = int(end)
        return int(selected)

    def _boundary_storage_port_target_group(self) -> Optional[Mapping[str, Any]]:
        matching_groups = [
            group
            for group in self._mandatory_groups
            if str(group.get("facility_type", "")) == "boundary_storage_port"
            and str(group.get("operation_type", "")) == "boundary_io"
        ]
        if len(matching_groups) != 1:
            return None
        return matching_groups[0]

    def _boundary_storage_port_feasibility_screen_spec(self) -> Dict[str, Any]:
        cached = self._boundary_storage_port_feasibility_screen_cache
        if cached is not None:
            return dict(cached)

        unsupported_payload: Dict[str, Any] = {
            "supported": False,
            "group_id": None,
            "required_count": 0,
            "reason": "missing_boundary_storage_port_group",
            "interval_records_by_family": {},
        }

        group = self._boundary_storage_port_target_group()
        if group is None:
            self._boundary_storage_port_feasibility_screen_cache = dict(unsupported_payload)
            return dict(unsupported_payload)

        group_id = str(group.get("group_id", ""))
        if group_id != BOUNDARY_STORAGE_PORT_SCREEN_GROUP_ID:
            unsupported_payload.update(
                {
                    "group_id": group_id,
                    "required_count": int(group.get("count", 0)),
                    "reason": "unexpected_boundary_storage_port_group_id",
                }
            )
            self._boundary_storage_port_feasibility_screen_cache = dict(unsupported_payload)
            return dict(unsupported_payload)

        candidate_indices = [
            int(pose_idx) for pose_idx in self._candidate_pose_indices_for_group(group)
        ]
        if not candidate_indices:
            unsupported_payload.update(
                {
                    "group_id": group_id,
                    "required_count": int(group.get("count", 0)),
                    "reason": "empty_boundary_storage_port_candidate_pool",
                }
            )
            self._boundary_storage_port_feasibility_screen_cache = dict(unsupported_payload)
            return dict(unsupported_payload)

        interval_records_by_family: Dict[str, List[Dict[str, Any]]] = {
            "left": [],
            "bottom": [],
        }
        family_cells: Dict[str, Set[Tuple[int, int]]] = {
            "left": set(),
            "bottom": set(),
        }

        for pose_idx in candidate_indices:
            cells = self._pose_cells("boundary_storage_port", int(pose_idx))
            pose = dict(self.facility_pools["boundary_storage_port"][int(pose_idx)])
            port_cells: Set[Tuple[int, int]] = set()
            for port_entry in list(pose.get("input_port_cells", [])) + list(
                pose.get("output_port_cells", [])
            ):
                if isinstance(port_entry, Mapping):
                    port_cells.add(
                        (int(port_entry.get("x", 0)), int(port_entry.get("y", 0)))
                    )
                else:
                    port_pair = list(port_entry)
                    if len(port_pair) >= 2:
                        port_cells.add((int(port_pair[0]), int(port_pair[1])))
            if len(cells) != 3:
                unsupported_payload.update(
                    {
                        "group_id": group_id,
                        "required_count": int(group.get("count", 0)),
                        "reason": "non_three_cell_boundary_port_pose",
                    }
                )
                self._boundary_storage_port_feasibility_screen_cache = dict(unsupported_payload)
                return dict(unsupported_payload)

            xs = sorted({int(cell_x) for cell_x, _ in cells})
            ys = sorted({int(cell_y) for _, cell_y in cells})
            family: Optional[str] = None
            start = 0
            end = 0
            if len(xs) == 1 and int(xs[0]) == 0 and len(ys) == 3:
                expected_ys = list(range(int(ys[0]), int(ys[0]) + 3))
                if ys != expected_ys:
                    unsupported_payload.update(
                        {
                            "group_id": group_id,
                            "required_count": int(group.get("count", 0)),
                            "reason": "non_contiguous_left_boundary_port_pose",
                        }
                    )
                    self._boundary_storage_port_feasibility_screen_cache = dict(
                        unsupported_payload
                    )
                    return dict(unsupported_payload)
                family = "left"
                start = int(ys[0])
                end = int(ys[-1])
            elif len(ys) == 1 and int(ys[0]) == 0 and len(xs) == 3:
                expected_xs = list(range(int(xs[0]), int(xs[0]) + 3))
                if xs != expected_xs:
                    unsupported_payload.update(
                        {
                            "group_id": group_id,
                            "required_count": int(group.get("count", 0)),
                            "reason": "non_contiguous_bottom_boundary_port_pose",
                        }
                    )
                    self._boundary_storage_port_feasibility_screen_cache = dict(
                        unsupported_payload
                    )
                    return dict(unsupported_payload)
                family = "bottom"
                start = int(xs[0])
                end = int(xs[-1])
            else:
                unsupported_payload.update(
                    {
                        "group_id": group_id,
                        "required_count": int(group.get("count", 0)),
                        "reason": "unsupported_boundary_port_geometry",
                    }
                )
                self._boundary_storage_port_feasibility_screen_cache = dict(unsupported_payload)
                return dict(unsupported_payload)

            family_cells[family].update(cells)
            interval_records_by_family[family].append(
                {
                    "pose_idx": int(pose_idx),
                    "start": int(start),
                    "end": int(end),
                    "cells": frozenset(cells),
                    "blocking_cells": frozenset(set(cells) | port_cells),
                }
            )

        if not interval_records_by_family["left"] or not interval_records_by_family["bottom"]:
            unsupported_payload.update(
                {
                    "group_id": group_id,
                    "required_count": int(group.get("count", 0)),
                    "reason": "missing_boundary_port_edge_family",
                }
            )
            self._boundary_storage_port_feasibility_screen_cache = dict(unsupported_payload)
            return dict(unsupported_payload)

        if family_cells["left"] & family_cells["bottom"]:
            unsupported_payload.update(
                {
                    "group_id": group_id,
                    "required_count": int(group.get("count", 0)),
                    "reason": "overlapping_boundary_port_edge_families",
                }
            )
            self._boundary_storage_port_feasibility_screen_cache = dict(unsupported_payload)
            return dict(unsupported_payload)

        supported_payload = {
            "supported": True,
            "group_id": group_id,
            "required_count": int(group.get("count", 0)),
            "reason": "supported",
            "interval_records_by_family": {
                family: tuple(
                    sorted(
                        records,
                        key=lambda entry: (
                            int(entry["end"]),
                            int(entry["start"]),
                            int(entry["pose_idx"]),
                        ),
                    )
                )
                for family, records in interval_records_by_family.items()
            },
        }
        self._boundary_storage_port_feasibility_screen_cache = dict(supported_payload)
        return dict(supported_payload)

    @staticmethod
    def _default_exact_candidate_boundary_port_feasibility_payload() -> Dict[str, Any]:
        return {
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
            "screen_pass_anchor_indices": (),
            "rebuild_anchor_indices": (),
        }

    @staticmethod
    def _normalize_exact_candidate_boundary_port_feasibility_payload(
        payload: Mapping[str, Any],
    ) -> Dict[str, Any]:
        normalized = {
            "supported": bool(payload.get("supported", False)),
            "required_count": int(payload.get("required_count", 0)),
            "considered_anchor_count": int(payload.get("considered_anchor_count", 0)),
            "screened_infeasible_anchor_count": int(
                payload.get("screened_infeasible_anchor_count", 0)
            ),
            "screen_pass_anchor_count": int(
                payload.get("screen_pass_anchor_count", 0)
            ),
            "unsupported_anchor_count": int(
                payload.get("unsupported_anchor_count", 0)
            ),
            "max_packable_min": payload.get("max_packable_min"),
            "max_packable_max": payload.get("max_packable_max"),
            "first_infeasible_anchor_idx": payload.get("first_infeasible_anchor_idx"),
            "first_infeasible_anchor_max_packable": payload.get(
                "first_infeasible_anchor_max_packable"
            ),
            "screen_pass_anchor_indices": tuple(
                int(idx) for idx in payload.get("screen_pass_anchor_indices", ())
            ),
            "rebuild_anchor_indices": tuple(
                int(idx) for idx in payload.get("rebuild_anchor_indices", ())
            ),
        }
        if bool(payload.get("skipped_due_to_anchor_limit", False)):
            normalized["skipped_due_to_anchor_limit"] = True
        return normalized

    def _publish_exact_candidate_boundary_port_feasibility_summary(
        self,
        payload: Mapping[str, Any],
    ) -> None:
        normalized = self._normalize_exact_candidate_boundary_port_feasibility_payload(
            payload
        )
        self.build_stats["exact_candidate_warm_start_boundary_port_feasibility"] = {
            key: value
            for key, value in normalized.items()
            if key not in {"screen_pass_anchor_indices", "rebuild_anchor_indices"}
        }

    @staticmethod
    def _canonical_ghost_anchor_domains_for_rect(
        *,
        grid_w: int,
        grid_h: int,
        ghost_rect: Optional[Tuple[int, int]],
    ) -> Tuple[Dict[str, Any], ...]:
        if not ghost_rect:
            return ()
        ghost_w, ghost_h = (int(ghost_rect[0]), int(ghost_rect[1]))
        if ghost_w <= 0 or ghost_h <= 0:
            return ()
        if ghost_w > int(grid_w) or ghost_h > int(grid_h):
            return ()

        domains: List[Dict[str, Any]] = []
        for anchor_x in range(int(grid_w) - ghost_w + 1):
            for anchor_y in range(int(grid_h) - ghost_h + 1):
                domains.append(
                    {
                        "anchor": {"x": int(anchor_x), "y": int(anchor_y)},
                        "cells": tuple(
                            (int(anchor_x + dx), int(anchor_y + dy))
                            for dx in range(ghost_w)
                            for dy in range(ghost_h)
                        ),
                    }
                )
        return tuple(domains)

    @staticmethod
    def _evaluate_boundary_storage_port_anchor_feasibility_from_screen_spec(
        *,
        screen_spec: Mapping[str, Any],
        blocked_cells: Set[Tuple[int, int]],
    ) -> Dict[str, Any]:
        if not bool(screen_spec.get("supported", False)):
            return {
                "supported": False,
                "required_count": int(screen_spec.get("required_count", 0)),
                "max_packable": None,
                "screened_infeasible": False,
                "unsupported": True,
            }

        normalized_blocked_cells = {
            (int(cell_x), int(cell_y)) for cell_x, cell_y in set(blocked_cells)
        }
        max_packable = 0
        for family in ("left", "bottom"):
            surviving_intervals = [
                (int(entry["start"]), int(entry["end"]))
                for entry in list(
                    screen_spec.get("interval_records_by_family", {}).get(family, ())
                )
                if set(
                    entry.get(
                        "blocking_cells",
                        entry.get("cells", frozenset()),
                    )
                ).isdisjoint(
                    normalized_blocked_cells
                )
            ]
            max_packable += MasterPlacementModel._max_non_overlapping_closed_intervals(
                surviving_intervals
            )

        required_count = int(screen_spec.get("required_count", 0))
        return {
            "supported": True,
            "required_count": int(required_count),
            "max_packable": int(max_packable),
            "screened_infeasible": bool(int(max_packable) < int(required_count)),
            "unsupported": False,
        }

    @classmethod
    def evaluate_boundary_port_feasibility_from_screen_spec(
        cls,
        *,
        rules: Mapping[str, Any],
        ghost_rect: Optional[Tuple[int, int]],
        screen_spec: Mapping[str, Any],
    ) -> Dict[str, Any]:
        default_payload = cls._default_exact_candidate_boundary_port_feasibility_payload()
        domains = cls._canonical_ghost_anchor_domains_for_rect(
            grid_w=int(dict(rules["globals"]["grid"])["width"]),
            grid_h=int(dict(rules["globals"]["grid"])["height"]),
            ghost_rect=ghost_rect,
        )
        if not ghost_rect or not domains:
            return dict(default_payload)
        if len(domains) > _exact_boundary_port_precheck_max_anchors():
            return cls._normalize_exact_candidate_boundary_port_feasibility_payload(
                {
                    **dict(default_payload),
                    "skipped_due_to_anchor_limit": True,
                }
            )

        considered_anchor_count = 0
        screened_infeasible_anchor_count = 0
        screen_pass_anchor_count = 0
        unsupported_anchor_count = 0
        max_packable_values: List[int] = []
        first_infeasible_anchor_idx: Optional[int] = None
        first_infeasible_anchor_max_packable: Optional[int] = None
        screen_pass_anchor_indices: List[int] = []
        rebuild_anchor_indices: List[int] = []

        for rect_idx, domain in enumerate(domains):
            considered_anchor_count += 1
            domain_cells = {
                (int(cell[0]), int(cell[1]))
                for cell in list(domain.get("cells", ()))
            }
            anchor_feasibility = cls._evaluate_boundary_storage_port_anchor_feasibility_from_screen_spec(
                screen_spec=screen_spec,
                blocked_cells=domain_cells,
            )
            if bool(anchor_feasibility.get("unsupported", False)):
                unsupported_anchor_count += 1
                rebuild_anchor_indices.append(int(rect_idx))
                continue

            max_packable = int(anchor_feasibility.get("max_packable", 0))
            max_packable_values.append(max_packable)
            if bool(anchor_feasibility.get("screened_infeasible", False)):
                screened_infeasible_anchor_count += 1
                if first_infeasible_anchor_idx is None:
                    first_infeasible_anchor_idx = int(rect_idx)
                    first_infeasible_anchor_max_packable = int(max_packable)
                continue

            screen_pass_anchor_count += 1
            screen_pass_anchor_indices.append(int(rect_idx))
            rebuild_anchor_indices.append(int(rect_idx))

        return cls._normalize_exact_candidate_boundary_port_feasibility_payload(
            {
                "supported": bool(screen_spec.get("supported", False)),
                "required_count": int(screen_spec.get("required_count", 0)),
                "considered_anchor_count": int(considered_anchor_count),
                "screened_infeasible_anchor_count": int(
                    screened_infeasible_anchor_count
                ),
                "screen_pass_anchor_count": int(screen_pass_anchor_count),
                "unsupported_anchor_count": int(unsupported_anchor_count),
                "max_packable_min": None
                if not max_packable_values
                else int(min(max_packable_values)),
                "max_packable_max": None
                if not max_packable_values
                else int(max(max_packable_values)),
                "first_infeasible_anchor_idx": first_infeasible_anchor_idx,
                "first_infeasible_anchor_max_packable": first_infeasible_anchor_max_packable,
                "screen_pass_anchor_indices": tuple(
                    int(idx) for idx in screen_pass_anchor_indices
                ),
                "rebuild_anchor_indices": tuple(
                    int(idx) for idx in rebuild_anchor_indices
                ),
            }
        )

    def _evaluate_boundary_storage_port_anchor_feasibility(
        self,
        blocked_cells: Set[Tuple[int, int]],
    ) -> Dict[str, Any]:
        return self._evaluate_boundary_storage_port_anchor_feasibility_from_screen_spec(
            screen_spec=self._boundary_storage_port_feasibility_screen_spec(),
            blocked_cells=blocked_cells,
        )

    def evaluate_exact_candidate_boundary_port_feasibility(self) -> Dict[str, Any]:
        if not self._built:
            self.build()

        cached = self._exact_candidate_boundary_port_feasibility_cache
        if cached is not None:
            return self._normalize_exact_candidate_boundary_port_feasibility_payload(
                cached
            )

        default_payload = self._default_exact_candidate_boundary_port_feasibility_payload()
        if not self.exact_mode or not self.ghost_rect or not self._ghost_domains or not self.u_vars:
            self._exact_candidate_boundary_port_feasibility_cache = dict(default_payload)
            self._publish_exact_candidate_boundary_port_feasibility_summary(
                default_payload
            )
            return dict(default_payload)
        if len(tuple(self._ordered_ghost_anchor_indices())) > _exact_boundary_port_precheck_max_anchors():
            skipped_payload = self._normalize_exact_candidate_boundary_port_feasibility_payload(
                {
                    **dict(default_payload),
                    "skipped_due_to_anchor_limit": True,
                }
            )
            self._exact_candidate_boundary_port_feasibility_cache = dict(skipped_payload)
            self._publish_exact_candidate_boundary_port_feasibility_summary(
                skipped_payload
            )
            return dict(skipped_payload)

        screen_spec = self._boundary_storage_port_feasibility_screen_spec()
        considered_anchor_count = 0
        screened_infeasible_anchor_count = 0
        screen_pass_anchor_count = 0
        unsupported_anchor_count = 0
        max_packable_values: List[int] = []
        first_infeasible_anchor_idx: Optional[int] = None
        first_infeasible_anchor_max_packable: Optional[int] = None
        screen_pass_anchor_indices: List[int] = []
        rebuild_anchor_indices: List[int] = []

        for rect_idx in self._ordered_ghost_anchor_indices():
            considered_anchor_count += 1
            domain = self._ghost_domains[int(rect_idx)]
            domain_cells = {
                (int(cell[0]), int(cell[1]))
                for cell in list(domain.get("cells", []))
            }
            anchor_feasibility = self._evaluate_boundary_storage_port_anchor_feasibility(
                blocked_cells=domain_cells
            )
            if bool(anchor_feasibility.get("unsupported", False)):
                unsupported_anchor_count += 1
                rebuild_anchor_indices.append(int(rect_idx))
                continue

            max_packable = int(anchor_feasibility.get("max_packable", 0))
            max_packable_values.append(max_packable)
            if bool(anchor_feasibility.get("screened_infeasible", False)):
                screened_infeasible_anchor_count += 1
                if first_infeasible_anchor_idx is None:
                    first_infeasible_anchor_idx = int(rect_idx)
                    first_infeasible_anchor_max_packable = int(max_packable)
                continue

            screen_pass_anchor_count += 1
            screen_pass_anchor_indices.append(int(rect_idx))
            rebuild_anchor_indices.append(int(rect_idx))

        payload = self._normalize_exact_candidate_boundary_port_feasibility_payload(
            {
                "supported": bool(screen_spec.get("supported", False)),
                "required_count": int(screen_spec.get("required_count", 0)),
                "considered_anchor_count": int(considered_anchor_count),
                "screened_infeasible_anchor_count": int(
                    screened_infeasible_anchor_count
                ),
                "screen_pass_anchor_count": int(screen_pass_anchor_count),
                "unsupported_anchor_count": int(unsupported_anchor_count),
                "max_packable_min": None
                if not max_packable_values
                else int(min(max_packable_values)),
                "max_packable_max": None
                if not max_packable_values
                else int(max(max_packable_values)),
                "first_infeasible_anchor_idx": first_infeasible_anchor_idx,
                "first_infeasible_anchor_max_packable": first_infeasible_anchor_max_packable,
                "screen_pass_anchor_indices": tuple(
                    int(idx) for idx in screen_pass_anchor_indices
                ),
                "rebuild_anchor_indices": tuple(
                    int(idx) for idx in rebuild_anchor_indices
                ),
            }
        )
        self._exact_candidate_boundary_port_feasibility_cache = dict(payload)
        self._publish_exact_candidate_boundary_port_feasibility_summary(payload)
        return dict(payload)

    def _compact_signature_for_pose_indices(
        self,
        tpl: str,
        pose_indices: Iterable[int],
    ) -> Optional[CompactLocalCapacitySignature]:
        anchor_by_pose = self._pose_anchor_by_template_pose.get(str(tpl), {})
        shape_token_by_pose = self._pose_local_shape_token_by_template_pose.get(
            str(tpl),
            {},
        )
        compact_items: List[CompactLocalCapacityItem] = []
        for pose_idx in pose_indices:
            pose_idx = int(pose_idx)
            anchor_xy = anchor_by_pose.get(pose_idx)
            shape_token = shape_token_by_pose.get(pose_idx)
            if anchor_xy is None or shape_token is None:
                return None
            compact_items.append(
                (int(anchor_xy[0]), int(anchor_xy[1]), int(shape_token))
            )
        return tuple(sorted(compact_items))

    def _normalized_ghost_anchor_indices_for_precheck(
        self,
        anchor_indices: Optional[Iterable[int]] = None,
    ) -> Tuple[int, ...]:
        ordered_anchor_indices = tuple(
            int(idx) for idx in self._ordered_ghost_anchor_indices()
        )
        if anchor_indices is None:
            return ordered_anchor_indices
        allowed = {int(idx) for idx in anchor_indices}
        return tuple(int(idx) for idx in ordered_anchor_indices if int(idx) in allowed)

    def _publish_exact_candidate_mandatory_rectangle_precheck_summary(
        self,
        payload: Mapping[str, Any],
    ) -> None:
        self.build_stats["exact_candidate_warm_start_mandatory_group_prechecks"] = {
            key: value
            for key, value in dict(payload).items()
            if key != "rebuild_anchor_indices"
        }

    def _publish_exact_candidate_mandatory_support_diagnostics_summary(
        self,
        payload: Mapping[str, Any],
    ) -> None:
        self.build_stats["exact_candidate_mandatory_support_diagnostics"] = {
            "unsupported_group_count": int(
                payload.get("unsupported_group_count", 0)
            ),
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

    def _exact_candidate_mandatory_pool_support_info(
        self,
        tpl: str,
        candidate_indices: Sequence[int],
    ) -> Dict[str, Any]:
        if not candidate_indices:
            return {
                "supported": False,
                "oracle_class": None,
                "oracle_mode": "unsupported",
                "unsupported_reason": "empty_candidate_pool",
            }
        compact_signature = self._compact_signature_for_pose_indices(
            tpl,
            candidate_indices,
        )
        if compact_signature is None:
            return {
                "supported": False,
                "oracle_class": None,
                "oracle_mode": "unsupported",
                "unsupported_reason": "missing_compact_signature",
            }
        try:
            normalized = self._normalize_rectangle_frontier_signature(
                tpl,
                compact_signature,
            )
        except _RectangleFrontierDPFallback:
            return {
                "supported": False,
                "oracle_class": None,
                "oracle_mode": "unsupported",
                "unsupported_reason": "non_rectangular_signature",
            }
        if not normalized:
            return {
                "supported": False,
                "oracle_class": None,
                "oracle_mode": "unsupported",
                "unsupported_reason": "normalization_failed",
            }
        oracle_class = self._compact_rect_cpsat_class_tag_from_normalized(
            tpl,
            normalized,
        )
        oracle_mode = (
            str(oracle_class)
            if oracle_class in {"uniform_3x3", "m6x4_mixed"}
            else "generic_normalized_rect"
        )
        return {
            "supported": True,
            "oracle_class": oracle_class,
            "oracle_mode": str(oracle_mode),
            "unsupported_reason": None,
        }

    def evaluate_exact_candidate_mandatory_support_diagnostics(self) -> Dict[str, Any]:
        if not self._built:
            self.build()

        cached = self._exact_candidate_mandatory_support_diagnostics_cache
        if cached is not None:
            return {
                "unsupported_group_count": int(
                    cached.get("unsupported_group_count", 0)
                ),
                "empty_candidate_pool_group_count": int(
                    cached.get("empty_candidate_pool_group_count", 0)
                ),
                "groups": [
                    dict(entry)
                    for entry in list(cached.get("groups", []))
                ],
            }

        target_groups = [
            dict(group)
            for group in self._mandatory_groups
            if str(group.get("facility_type", "")) != "boundary_storage_port"
        ]
        group_summaries: List[Dict[str, Any]] = []
        unsupported_group_count = 0
        empty_candidate_pool_group_count = 0
        for group in target_groups:
            tpl = str(group.get("facility_type", ""))
            candidate_indices = [
                int(pose_idx)
                for pose_idx in self._candidate_pose_indices_for_group(group)
            ]
            support_info = self._exact_candidate_mandatory_pool_support_info(
                tpl,
                candidate_indices,
            )
            unsupported_reason = support_info.get("unsupported_reason")
            if unsupported_reason is not None:
                unsupported_group_count += 1
                if str(unsupported_reason) == "empty_candidate_pool":
                    empty_candidate_pool_group_count += 1
            group_summaries.append(
                {
                    "group_id": str(group.get("group_id", "")),
                    "facility_type": tpl,
                    "operation_type": str(group.get("operation_type", "")),
                    "required_count": int(group.get("count", 0)),
                    "candidate_pool_count": int(len(candidate_indices)),
                    "unsupported_reason": unsupported_reason,
                }
            )

        payload = {
            "unsupported_group_count": int(unsupported_group_count),
            "empty_candidate_pool_group_count": int(
                empty_candidate_pool_group_count
            ),
            "groups": [dict(entry) for entry in group_summaries],
        }
        self._exact_candidate_mandatory_support_diagnostics_cache = {
            "unsupported_group_count": int(unsupported_group_count),
            "empty_candidate_pool_group_count": int(
                empty_candidate_pool_group_count
            ),
            "groups": [dict(entry) for entry in group_summaries],
        }
        self._publish_exact_candidate_mandatory_support_diagnostics_summary(payload)
        return payload

    def _default_exact_candidate_mandatory_rectangle_precheck_payload(
        self,
        *,
        rebuild_anchor_indices: Sequence[int],
        evaluated: bool,
        skipped_due_to_upstream_precheck: bool,
        upstream_anchor_filter_count: int,
    ) -> Dict[str, Any]:
        return {
            "evaluated": bool(evaluated),
            "skipped_due_to_upstream_precheck": bool(
                skipped_due_to_upstream_precheck
            ),
            "upstream_anchor_filter_count": int(upstream_anchor_filter_count),
            "supported_group_count": 0,
            "groups": [],
            "rebuild_anchor_indices": tuple(
                int(idx) for idx in rebuild_anchor_indices
            ),
        }

    def evaluate_exact_candidate_mandatory_rectangle_prechecks(
        self,
        anchor_indices: Optional[Iterable[int]] = None,
    ) -> Dict[str, Any]:
        if not self._built:
            self.build()

        normalized_anchor_indices = self._normalized_ghost_anchor_indices_for_precheck(
            anchor_indices
        )
        upstream_anchor_filter_count = 0 if anchor_indices is None else int(
            len(normalized_anchor_indices)
        )
        cache_key = tuple(int(idx) for idx in normalized_anchor_indices)
        cached = self._exact_candidate_mandatory_rectangle_precheck_cache.get(cache_key)
        if cached is not None:
            return {
                "evaluated": bool(cached.get("evaluated", False)),
                "skipped_due_to_upstream_precheck": bool(
                    cached.get("skipped_due_to_upstream_precheck", False)
                ),
                "upstream_anchor_filter_count": int(
                    cached.get("upstream_anchor_filter_count", 0)
                ),
                "supported_group_count": int(cached.get("supported_group_count", 0)),
                "groups": [
                    dict(entry)
                    for entry in list(cached.get("groups", []))
                ],
                "rebuild_anchor_indices": tuple(
                    int(idx) for idx in cached.get("rebuild_anchor_indices", ())
                ),
            }

        default_payload = self._default_exact_candidate_mandatory_rectangle_precheck_payload(
            rebuild_anchor_indices=normalized_anchor_indices
            if self.exact_mode and self.ghost_rect and self._ghost_domains and self.u_vars
            else (),
            evaluated=False,
            skipped_due_to_upstream_precheck=False,
            upstream_anchor_filter_count=upstream_anchor_filter_count,
        )
        if not self.exact_mode or not self.ghost_rect or not self._ghost_domains or not self.u_vars:
            self._exact_candidate_mandatory_rectangle_precheck_cache[cache_key] = {
                **dict(default_payload),
            }
            self._publish_exact_candidate_mandatory_rectangle_precheck_summary(
                default_payload
            )
            return dict(default_payload)

        def _surviving_signature_support_status(
            tpl: str,
            pose_indices: Sequence[int],
        ) -> Dict[str, Any]:
            compact_signature = self._compact_signature_for_pose_indices(
                tpl,
                pose_indices,
            )
            if compact_signature is None:
                return {
                    "supported": False,
                    "unsupported_reason": "missing_compact_signature",
                    "compact_signature": None,
                }
            try:
                normalized = self._normalize_rectangle_frontier_signature(
                    tpl,
                    compact_signature,
                )
            except _RectangleFrontierDPFallback:
                return {
                    "supported": False,
                    "unsupported_reason": "non_rectangular_signature",
                    "compact_signature": compact_signature,
                }
            if pose_indices and not normalized:
                return {
                    "supported": False,
                    "unsupported_reason": "normalization_failed",
                    "compact_signature": compact_signature,
                }
            return {
                "supported": True,
                "unsupported_reason": None,
                "compact_signature": compact_signature,
            }

        target_groups = [
            dict(group)
            for group in self._mandatory_groups
            if str(group.get("facility_type", "")) != "boundary_storage_port"
        ]
        if not target_groups:
            self._exact_candidate_mandatory_rectangle_precheck_cache[cache_key] = {
                **dict(default_payload),
            }
            self._publish_exact_candidate_mandatory_rectangle_precheck_summary(
                default_payload
            )
            return dict(default_payload)

        candidate_rebuild_anchor_indices: Set[int] = set(normalized_anchor_indices)
        supported_group_count = 0
        group_summaries: List[Dict[str, Any]] = []
        anchor_count = int(len(normalized_anchor_indices))
        time_budget_seconds = _exact_mandatory_rectangle_precheck_time_budget_seconds()
        precheck_started = time.perf_counter()

        def _time_budget_exhausted() -> bool:
            return (
                float(time_budget_seconds) > 0.0
                and (time.perf_counter() - precheck_started) >= float(time_budget_seconds)
            )

        def _time_budget_payload(
            *,
            partial_group: Optional[Mapping[str, Any]] = None,
        ) -> Dict[str, Any]:
            groups_payload = [dict(entry) for entry in group_summaries]
            if partial_group is not None:
                groups_payload.append(dict(partial_group))
            rebuild_anchor_indices: Tuple[int, ...] = tuple(
                int(idx) for idx in normalized_anchor_indices
            )
            payload = {
                "evaluated": bool(groups_payload),
                "skipped_due_to_upstream_precheck": False,
                "upstream_anchor_filter_count": int(upstream_anchor_filter_count),
                "supported_group_count": int(supported_group_count),
                "groups": groups_payload,
                "rebuild_anchor_indices": rebuild_anchor_indices,
                "interrupted_due_to_time_budget": True,
                "time_budget_seconds": float(time_budget_seconds),
                "elapsed_seconds": float(time.perf_counter() - precheck_started),
            }
            self._exact_candidate_mandatory_rectangle_precheck_cache[cache_key] = {
                **dict(payload),
                "rebuild_anchor_indices": tuple(
                    int(idx) for idx in rebuild_anchor_indices
                ),
            }
            self._publish_exact_candidate_mandatory_rectangle_precheck_summary(payload)
            return payload

        if anchor_count > _exact_mandatory_rectangle_precheck_max_anchors():
            self._exact_candidate_mandatory_rectangle_precheck_cache[cache_key] = {
                **dict(default_payload),
            }
            self._publish_exact_candidate_mandatory_rectangle_precheck_summary(
                default_payload
            )
            return dict(default_payload)

        for group in target_groups:
            if _time_budget_exhausted():
                return _time_budget_payload()
            group_id = str(group.get("group_id", ""))
            tpl = str(group.get("facility_type", ""))
            operation_type = str(group.get("operation_type", ""))
            required_count = int(group.get("count", 0))
            candidate_indices = [
                int(pose_idx)
                for pose_idx in self._candidate_pose_indices_for_group(group)
            ]
            support_info = self._exact_candidate_mandatory_pool_support_info(
                tpl,
                candidate_indices,
            )
            group_supported = bool(support_info.get("supported", False))
            oracle_class = support_info.get("oracle_class")
            oracle_mode = str(support_info.get("oracle_mode", "unsupported"))
            unsupported_reason = support_info.get("unsupported_reason")

            if not group_supported:
                group_summaries.append(
                    {
                        "group_id": group_id,
                        "facility_type": tpl,
                        "operation_type": operation_type,
                        "required_count": int(required_count),
                        "oracle_class": oracle_class,
                        "oracle_mode": oracle_mode,
                        "supported": False,
                        "unsupported_reason": unsupported_reason,
                        "considered_anchor_count": int(anchor_count),
                        "screened_infeasible_anchor_count": 0,
                        "screen_pass_anchor_count": 0,
                        "unsupported_anchor_count": int(anchor_count),
                        "max_packable_min": None,
                        "max_packable_max": None,
                        "first_infeasible_anchor_idx": None,
                        "first_infeasible_anchor_max_packable": None,
                    }
                )
                continue

            supported_group_count += 1
            pass_anchor_indices: Set[int] = set()
            considered_anchor_count = 0
            screened_infeasible_anchor_count = 0
            screen_pass_anchor_count = 0
            unsupported_anchor_count = 0
            max_packable_values: List[int] = []
            witness_lower_bound_values: List[int] = []
            witness_pass_anchor_count = 0
            exact_capacity_eval_count = 0
            first_infeasible_anchor_idx: Optional[int] = None
            first_infeasible_anchor_max_packable: Optional[int] = None

            def _optional_witness_fields() -> Dict[str, Any]:
                if witness_pass_anchor_count <= 0:
                    return {}
                return {
                    "witness_pass_anchor_count": int(witness_pass_anchor_count),
                    "exact_capacity_eval_count": int(exact_capacity_eval_count),
                    "max_packable_lower_bound_min": int(
                        min(witness_lower_bound_values)
                    )
                    if witness_lower_bound_values
                    else None,
                    "max_packable_lower_bound_max": int(
                        max(witness_lower_bound_values)
                    )
                    if witness_lower_bound_values
                    else None,
                }

            for rect_idx in normalized_anchor_indices:
                if _time_budget_exhausted() and considered_anchor_count > 0:
                    return _time_budget_payload(
                        partial_group={
                            "group_id": group_id,
                            "facility_type": tpl,
                            "operation_type": operation_type,
                            "required_count": int(required_count),
                            "oracle_class": oracle_class,
                            "oracle_mode": oracle_mode,
                            "supported": True,
                            "unsupported_reason": None,
                            "considered_anchor_count": int(considered_anchor_count),
                            "screened_infeasible_anchor_count": int(
                                screened_infeasible_anchor_count
                            ),
                            "screen_pass_anchor_count": int(screen_pass_anchor_count),
                            "unsupported_anchor_count": int(unsupported_anchor_count),
                            "max_packable_min": None
                            if not max_packable_values
                            else int(min(max_packable_values)),
                            "max_packable_max": None
                            if not max_packable_values
                            else int(max(max_packable_values)),
                            "first_infeasible_anchor_idx": first_infeasible_anchor_idx,
                            "first_infeasible_anchor_max_packable": first_infeasible_anchor_max_packable,
                            "partial_due_to_time_budget": True,
                            **_optional_witness_fields(),
                        }
                    )
                considered_anchor_count += 1
                domain = self._ghost_domains[int(rect_idx)]
                blocked_cells = {
                    (int(cell[0]), int(cell[1]))
                    for cell in list(domain.get("cells", []))
                }
                surviving_pose_indices = [
                    int(pose_idx)
                    for pose_idx in candidate_indices
                    if self._pose_cells(tpl, int(pose_idx)).isdisjoint(blocked_cells)
                ]
                witness = self._find_mandatory_rectangle_precheck_witness(
                    tpl,
                    surviving_pose_indices,
                    required_count,
                )
                if witness is not None:
                    witness_pass_anchor_count += 1
                    witness_lower_bound_values.append(int(len(witness)))
                    screen_pass_anchor_count += 1
                    pass_anchor_indices.add(int(rect_idx))
                    continue
                surviving_support = _surviving_signature_support_status(
                    tpl,
                    surviving_pose_indices,
                )
                surviving_signature = surviving_support.get("compact_signature")
                if not bool(surviving_support.get("supported", False)):
                    unsupported_anchor_count += 1
                    pass_anchor_indices.add(int(rect_idx))
                    continue

                exact_capacity_eval_count += 1
                max_packable = int(
                    self._solve_exact_local_power_capacity_from_compact(
                        tpl,
                        surviving_signature,
                    )
                )
                max_packable_values.append(int(max_packable))
                if int(max_packable) < int(required_count):
                    screened_infeasible_anchor_count += 1
                    if first_infeasible_anchor_idx is None:
                        first_infeasible_anchor_idx = int(rect_idx)
                        first_infeasible_anchor_max_packable = int(max_packable)
                    continue

                screen_pass_anchor_count += 1
                pass_anchor_indices.add(int(rect_idx))

            if _time_budget_exhausted():
                return _time_budget_payload(
                    partial_group={
                        "group_id": group_id,
                        "facility_type": tpl,
                        "operation_type": operation_type,
                        "required_count": int(required_count),
                        "oracle_class": oracle_class,
                        "oracle_mode": oracle_mode,
                        "supported": True,
                        "unsupported_reason": None,
                        "considered_anchor_count": int(considered_anchor_count),
                        "screened_infeasible_anchor_count": int(
                            screened_infeasible_anchor_count
                        ),
                        "screen_pass_anchor_count": int(screen_pass_anchor_count),
                        "unsupported_anchor_count": int(unsupported_anchor_count),
                        "max_packable_min": None
                        if not max_packable_values
                        else int(min(max_packable_values)),
                        "max_packable_max": None
                        if not max_packable_values
                        else int(max(max_packable_values)),
                        "first_infeasible_anchor_idx": first_infeasible_anchor_idx,
                        "first_infeasible_anchor_max_packable": first_infeasible_anchor_max_packable,
                        "partial_due_to_time_budget": True,
                        **_optional_witness_fields(),
                    }
                )

            if unsupported_anchor_count == 0:
                candidate_rebuild_anchor_indices &= pass_anchor_indices

            group_summaries.append(
                {
                    "group_id": group_id,
                    "facility_type": tpl,
                    "operation_type": operation_type,
                    "required_count": int(required_count),
                    "oracle_class": oracle_class,
                    "oracle_mode": oracle_mode,
                    "supported": True,
                    "unsupported_reason": None,
                    "considered_anchor_count": int(considered_anchor_count),
                    "screened_infeasible_anchor_count": int(
                        screened_infeasible_anchor_count
                    ),
                    "screen_pass_anchor_count": int(screen_pass_anchor_count),
                    "unsupported_anchor_count": int(unsupported_anchor_count),
                    "max_packable_min": None
                    if not max_packable_values
                    else int(min(max_packable_values)),
                    "max_packable_max": None
                    if not max_packable_values
                    else int(max(max_packable_values)),
                    "first_infeasible_anchor_idx": first_infeasible_anchor_idx,
                    "first_infeasible_anchor_max_packable": first_infeasible_anchor_max_packable,
                    **_optional_witness_fields(),
                }
            )

        rebuild_anchor_indices = tuple(
            int(idx)
            for idx in normalized_anchor_indices
            if int(idx) in candidate_rebuild_anchor_indices
        )
        payload = {
            "evaluated": True,
            "skipped_due_to_upstream_precheck": False,
            "upstream_anchor_filter_count": int(upstream_anchor_filter_count),
            "supported_group_count": int(supported_group_count),
            "groups": [dict(entry) for entry in group_summaries],
            "rebuild_anchor_indices": rebuild_anchor_indices,
        }
        self._exact_candidate_mandatory_rectangle_precheck_cache[cache_key] = {
            "evaluated": True,
            "skipped_due_to_upstream_precheck": False,
            "upstream_anchor_filter_count": int(upstream_anchor_filter_count),
            "supported_group_count": int(supported_group_count),
            "groups": [dict(entry) for entry in group_summaries],
            "rebuild_anchor_indices": tuple(int(idx) for idx in rebuild_anchor_indices),
        }
        self._publish_exact_candidate_mandatory_rectangle_precheck_summary(payload)
        return payload

    def _publish_greedy_hint_stats(self, greedy_hint: Mapping[str, Any]) -> None:
        published = {
            "supported": bool(greedy_hint.get("supported", False)),
            "complete": bool(greedy_hint.get("complete", False)),
            "hinted_groups": int(greedy_hint.get("hinted_groups", 0)),
            "hinted_instances": int(greedy_hint.get("hinted_instances", 0)),
            "skipped_groups": list(greedy_hint.get("skipped_groups", [])),
            "used_power_coverage_filter": bool(
                greedy_hint.get("used_power_coverage_filter", False)
            ),
        }
        reason = greedy_hint.get("reason")
        if reason is not None:
            published["reason"] = str(reason)
        self.build_stats["greedy_hint"] = published

    def build_greedy_solution_hint(self) -> Dict[str, int]:
        greedy_hint = self._build_mandatory_greedy_solution_hint()
        self._publish_greedy_hint_stats(greedy_hint)
        return dict(greedy_hint.get("solution_hint", {}))

    def build_exact_candidate_warm_start(self) -> Dict[str, Any]:
        if not self._built:
            self.build()

        global_greedy_hint = self._build_mandatory_greedy_solution_hint()
        self._publish_greedy_hint_stats(global_greedy_hint)
        solution_hint = dict(global_greedy_hint.get("solution_hint", {}))
        instance_template_by_id: Dict[str, str] = {}
        for group in self._mandatory_groups:
            tpl = str(group["facility_type"])
            for instance_id in list(group["instance_ids"]):
                instance_template_by_id[str(instance_id)] = tpl

        required_optional_templates: Set[str] = set()
        residual_optional_templates: Set[str] = set()
        if self._coordinate_delegate is not None:
            required_optional_templates = {
                str(tpl) for tpl in self._coordinate_delegate.required_optional_slots
            }
            residual_optional_templates = {
                str(tpl) for tpl in self._coordinate_delegate.residual_optional_slots
            }

        def _summarize_solution_hint(
            hint_payload: Mapping[str, int],
            *,
            hinted_occupied_cells: Optional[Set[Tuple[int, int]]] = None,
        ) -> Dict[str, int]:
            mandatory_hint_pose_count = 0
            required_optional_positive_hints = 0
            residual_optional_positive_hints = 0
            occupied_cells = (
                {
                    (int(cell[0]), int(cell[1]))
                    for cell in hinted_occupied_cells
                }
                if hinted_occupied_cells is not None
                else set()
            )
            for solution_id, pose_idx in hint_payload.items():
                tpl = instance_template_by_id.get(str(solution_id))
                if tpl is not None:
                    mandatory_hint_pose_count += 1
                    if hinted_occupied_cells is None:
                        occupied_cells.update(self._pose_cells(str(tpl), int(pose_idx)))
                    continue
                tpl = self._infer_optional_template_from_solution_id(str(solution_id))
                if tpl is None:
                    continue
                if str(tpl) in required_optional_templates:
                    required_optional_positive_hints += 1
                elif str(tpl) in residual_optional_templates:
                    residual_optional_positive_hints += 1
            return {
                "mandatory_hint_pose_count": int(mandatory_hint_pose_count),
                "mandatory_hint_occupied_cell_count": int(len(occupied_cells)),
                "required_optional_positive_hints": int(
                    required_optional_positive_hints
                ),
                "residual_optional_positive_hints": int(
                    residual_optional_positive_hints
                ),
            }

        def _record_exact_candidate_warm_start(warm_start_payload: Mapping[str, Any]) -> None:
            self.build_stats["exact_candidate_warm_start"] = {
                "ghost_anchor_hint_applied": bool(
                    warm_start_payload.get("ghost_anchor_hint_idx") is not None
                ),
                "ghost_anchor_hint_idx": warm_start_payload.get("ghost_anchor_hint_idx"),
                "ghost_anchor_hint_status": str(
                    warm_start_payload.get("ghost_anchor_hint_status", "not_applicable")
                ),
                "hint_inactive_residual_optionals": bool(
                    warm_start_payload.get("hint_inactive_residual_optionals", False)
                ),
                "residual_optional_zero_hints": int(
                    warm_start_payload.get("residual_optional_zero_hints", 0)
                ),
                "greedy_hint_instances": int(
                    len(dict(warm_start_payload.get("solution_hint", {})))
                ),
                "mandatory_hint_pose_count": int(
                    warm_start_payload.get("mandatory_hint_pose_count", 0)
                ),
                "mandatory_hint_occupied_cell_count": int(
                    warm_start_payload.get("mandatory_hint_occupied_cell_count", 0)
                ),
                "ghost_anchor_total_count": int(
                    warm_start_payload.get("ghost_anchor_total_count", 0)
                ),
                "ghost_anchor_compatible_count": int(
                    warm_start_payload.get("ghost_anchor_compatible_count", 0)
                ),
                "first_compatible_ghost_anchor_idx": warm_start_payload.get(
                    "first_compatible_ghost_anchor_idx"
                ),
                **(
                    {"ghost_anchor_compatibility_skipped": True}
                    if bool(warm_start_payload.get("ghost_anchor_compatibility_skipped", False))
                    else {}
                ),
                "required_optional_positive_hints": int(
                    warm_start_payload.get("required_optional_positive_hints", 0)
                ),
                "residual_optional_positive_hints": int(
                    warm_start_payload.get("residual_optional_positive_hints", 0)
                ),
                "warm_start_strategy": str(
                    warm_start_payload.get("warm_start_strategy", "unsupported")
                ),
                "ghost_aware_anchor_attempt_count": int(
                    warm_start_payload.get("ghost_aware_anchor_attempt_count", 0)
                ),
                "ghost_aware_anchor_selected_idx": warm_start_payload.get(
                    "ghost_aware_anchor_selected_idx"
                ),
                "ghost_aware_complete_mandatory_hint": bool(
                    warm_start_payload.get("ghost_aware_complete_mandatory_hint", False)
                ),
                "ghost_aware_hint_instances": int(
                    warm_start_payload.get("ghost_aware_hint_instances", 0)
                ),
                "ghost_aware_pose_order_portfolio_attempted": bool(
                    warm_start_payload.get(
                        "ghost_aware_pose_order_portfolio_attempted",
                        False,
                    )
                ),
                "ghost_aware_pose_order_portfolio_success": bool(
                    warm_start_payload.get(
                        "ghost_aware_pose_order_portfolio_success",
                        False,
                    )
                ),
                "ghost_aware_pose_order_portfolio_selected_ordering": warm_start_payload.get(
                    "ghost_aware_pose_order_portfolio_selected_ordering"
                ),
                "ghost_aware_pose_order_portfolio_attempt_count": int(
                    warm_start_payload.get(
                        "ghost_aware_pose_order_portfolio_attempt_count",
                        0,
                    )
                ),
                "ghost_aware_pose_order_portfolio_failed_anchor_count": int(
                    warm_start_payload.get(
                        "ghost_aware_pose_order_portfolio_failed_anchor_count",
                        0,
                    )
                ),
                "ghost_aware_pose_order_portfolio_failure_reason_counts": {
                    str(key): int(value)
                    for key, value in dict(
                        warm_start_payload.get(
                            "ghost_aware_pose_order_portfolio_failure_reason_counts",
                            {},
                        )
                    ).items()
                    if int(value) > 0
                },
                "ghost_aware_pose_order_portfolio_failure_samples": [
                    dict(entry)
                    for entry in list(
                        warm_start_payload.get(
                            "ghost_aware_pose_order_portfolio_failure_samples",
                            [],
                        )
                    )
                    if isinstance(entry, Mapping)
                ],
                "ghost_aware_pose_order_validation_attempt_count": int(
                    warm_start_payload.get(
                        "ghost_aware_pose_order_validation_attempt_count",
                        0,
                    )
                ),
                "ghost_aware_pose_order_validation_rejected_count": int(
                    warm_start_payload.get(
                        "ghost_aware_pose_order_validation_rejected_count",
                        0,
                    )
                ),
                "ghost_aware_pose_order_validation_last_status": warm_start_payload.get(
                    "ghost_aware_pose_order_validation_last_status"
                ),
                "ghost_aware_pose_order_validation_last_reason": warm_start_payload.get(
                    "ghost_aware_pose_order_validation_last_reason"
                ),
                "ghost_aware_pose_order_validation_rejection_samples": [
                    {
                        "anchor_idx": int(entry.get("anchor_idx", 0)),
                        "ordering": str(entry.get("ordering", "")),
                        "status": str(entry.get("status", "")),
                        "reason": str(entry.get("reason", "")),
                        "forced_slot_field_count": int(
                            entry.get("forced_slot_field_count", 0)
                        ),
                        "forced_ghost_anchor": bool(
                            entry.get("forced_ghost_anchor", False)
                        ),
                        "wall_time": float(entry.get("wall_time", 0.0)),
                        "deterministic_time": float(
                            entry.get("deterministic_time", 0.0)
                        ),
                        "branches": int(entry.get("branches", 0)),
                        "conflicts": int(entry.get("conflicts", 0)),
                        "solver_parameters": dict(
                            entry.get("solver_parameters", {})
                        ),
                    }
                    for entry in list(
                        warm_start_payload.get(
                            "ghost_aware_pose_order_validation_rejection_samples",
                            [],
                        )
                    )
                    if isinstance(entry, Mapping)
                ],
                "ghost_aware_coordinate_validation_attempt_count": int(
                    warm_start_payload.get(
                        "ghost_aware_coordinate_validation_attempt_count",
                        0,
                    )
                ),
                "ghost_aware_coordinate_validation_rejected_count": int(
                    warm_start_payload.get(
                        "ghost_aware_coordinate_validation_rejected_count",
                        0,
                    )
                ),
                "ghost_aware_coordinate_validation_last_status": warm_start_payload.get(
                    "ghost_aware_coordinate_validation_last_status"
                ),
                "ghost_aware_coordinate_validation_last_reason": warm_start_payload.get(
                    "ghost_aware_coordinate_validation_last_reason"
                ),
                "ghost_aware_coordinate_validation_rejection_samples": [
                    {
                        "anchor_idx": int(entry.get("anchor_idx", 0)),
                        "strategy": str(entry.get("strategy", "")),
                        "status": str(entry.get("status", "")),
                        "reason": str(entry.get("reason", "")),
                        "forced_slot_field_count": int(
                            entry.get("forced_slot_field_count", 0)
                        ),
                        "forced_ghost_anchor": bool(
                            entry.get("forced_ghost_anchor", False)
                        ),
                        "wall_time": float(entry.get("wall_time", 0.0)),
                        "deterministic_time": float(
                            entry.get("deterministic_time", 0.0)
                        ),
                        "branches": int(entry.get("branches", 0)),
                        "conflicts": int(entry.get("conflicts", 0)),
                        "solver_parameters": dict(
                            entry.get("solver_parameters", {})
                        ),
                    }
                    for entry in list(
                        warm_start_payload.get(
                            "ghost_aware_coordinate_validation_rejection_samples",
                            [],
                        )
                    )
                    if isinstance(entry, Mapping)
                ],
                "ghost_aware_coordinate_validation_limit_reached": bool(
                    warm_start_payload.get(
                        "ghost_aware_coordinate_validation_limit_reached",
                        False,
                    )
                ),
                "local_repair_attempted": bool(
                    warm_start_payload.get("local_repair_attempted", False)
                ),
                "local_repair_success": bool(
                    warm_start_payload.get("local_repair_success", False)
                ),
                "local_repair_trigger_reason": warm_start_payload.get(
                    "local_repair_trigger_reason"
                ),
                "local_repair_window_size": int(
                    warm_start_payload.get("local_repair_window_size", 0)
                ),
                "local_repair_anchor_idx": warm_start_payload.get(
                    "local_repair_anchor_idx"
                ),
                "local_repair_failed_group_id": warm_start_payload.get(
                    "local_repair_failed_group_id"
                ),
                "local_repair_failed_group_template": warm_start_payload.get(
                    "local_repair_failed_group_template"
                ),
                "local_repair_portfolio_attempt_count": int(
                    warm_start_payload.get("local_repair_portfolio_attempt_count", 0)
                ),
                "local_repair_selected_group_orderings": [
                    str(token)
                    for token in list(
                        warm_start_payload.get(
                            "local_repair_selected_group_orderings",
                            [],
                        )
                    )[:2]
                ],
                "local_repair_attempt_count": int(
                    warm_start_payload.get("local_repair_attempt_count", 0)
                ),
                "local_repair_success_count": int(
                    warm_start_payload.get("local_repair_success_count", 0)
                ),
                "local_repair_intra_group_attempted_count": int(
                    warm_start_payload.get(
                        "local_repair_intra_group_attempted_count",
                        0,
                    )
                ),
                "local_repair_committed_attempted_count": int(
                    warm_start_payload.get(
                        "local_repair_committed_attempted_count",
                        0,
                    )
                ),
                "local_repair_window1_count": int(
                    warm_start_payload.get("local_repair_window1_count", 0)
                ),
                "local_repair_window2_count": int(
                    warm_start_payload.get("local_repair_window2_count", 0)
                ),
            }

        def _coordinate_validation_sample_fields(
            entry: Mapping[str, Any],
        ) -> Dict[str, Any]:
            fields: Dict[str, Any] = {}
            if "status" in entry:
                fields["coordinate_validation_status"] = str(entry.get("status", ""))
            if "reason" in entry:
                fields["coordinate_validation_reason"] = str(entry.get("reason", ""))
            if "forced_slot_field_count" in entry:
                fields["coordinate_validation_forced_slot_field_count"] = int(
                    entry.get("forced_slot_field_count", 0)
                )
            if "forced_ghost_anchor" in entry:
                fields["coordinate_validation_forced_ghost_anchor"] = bool(
                    entry.get("forced_ghost_anchor", False)
                )
            solver_parameters = entry.get("solver_parameters")
            if isinstance(solver_parameters, Mapping):
                profile_id = solver_parameters.get("profile_id")
                if profile_id is not None:
                    fields["coordinate_validation_solver_profile_id"] = str(
                        profile_id
                    )
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

        def _record_exact_candidate_warm_start_failure_attribution(
            failure_payload: Mapping[str, Any]
        ) -> None:
            self.build_stats["exact_candidate_warm_start_failure_attribution"] = {
                "attempted_anchor_count": int(
                    failure_payload.get("attempted_anchor_count", 0)
                ),
                "failed_anchor_count": int(
                    failure_payload.get("failed_anchor_count", 0)
                ),
                "failure_reason_counts": {
                    str(key): int(value)
                    for key, value in dict(
                        failure_payload.get("failure_reason_counts", {})
                    ).items()
                    if int(value) > 0
                },
                "first_failed_anchor_idx": failure_payload.get(
                    "first_failed_anchor_idx"
                ),
                "first_failed_group_id": failure_payload.get("first_failed_group_id"),
                "first_failed_group_template": failure_payload.get(
                    "first_failed_group_template"
                ),
                "first_failed_group_required_count": int(
                    failure_payload.get("first_failed_group_required_count", 0)
                ),
                "first_failed_group_candidate_count": int(
                    failure_payload.get("first_failed_group_candidate_count", 0)
                ),
                "first_failed_group_surviving_after_blocked_count": int(
                    failure_payload.get(
                        "first_failed_group_surviving_after_blocked_count",
                        0,
                    )
                ),
                "first_failed_group_surviving_at_failure_count": int(
                    failure_payload.get(
                        "first_failed_group_surviving_at_failure_count",
                        0,
                    )
                ),
                "first_failed_group_position": failure_payload.get(
                    "first_failed_group_position"
                ),
                "top_failed_groups": [
                    {
                        "group_id": str(entry.get("group_id", "")),
                        "facility_type": str(entry.get("facility_type", "")),
                        "count": int(entry.get("count", 0)),
                    }
                    for entry in list(failure_payload.get("top_failed_groups", []))[:5]
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
                        failure_payload.get("top_failed_group_failures", [])
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
                        **_coordinate_validation_sample_fields(entry),
                    }
                    for entry in list(
                        failure_payload.get("failed_anchor_samples", [])
                    )[:_exact_warm_start_failed_anchor_sample_limit()]
                    if isinstance(entry, Mapping)
                ],
            }

        def _record_exact_candidate_boundary_port_feasibility(
            feasibility_payload: Mapping[str, Any]
        ) -> None:
            self.build_stats["exact_candidate_warm_start_boundary_port_feasibility"] = {
                "supported": bool(feasibility_payload.get("supported", False)),
                "required_count": int(feasibility_payload.get("required_count", 0)),
                "considered_anchor_count": int(
                    feasibility_payload.get("considered_anchor_count", 0)
                ),
                "screened_infeasible_anchor_count": int(
                    feasibility_payload.get("screened_infeasible_anchor_count", 0)
                ),
                "screen_pass_anchor_count": int(
                    feasibility_payload.get("screen_pass_anchor_count", 0)
                ),
                "unsupported_anchor_count": int(
                    feasibility_payload.get("unsupported_anchor_count", 0)
                ),
                "max_packable_min": None
                if feasibility_payload.get("max_packable_min") is None
                else int(feasibility_payload.get("max_packable_min", 0)),
                "max_packable_max": None
                if feasibility_payload.get("max_packable_max") is None
                else int(feasibility_payload.get("max_packable_max", 0)),
                "first_infeasible_anchor_idx": feasibility_payload.get(
                    "first_infeasible_anchor_idx"
                ),
                "first_infeasible_anchor_max_packable": None
                if feasibility_payload.get("first_infeasible_anchor_max_packable") is None
                else int(
                    feasibility_payload.get(
                        "first_infeasible_anchor_max_packable",
                        0,
                    )
                ),
                **(
                    {"skipped_due_to_anchor_limit": True}
                    if bool(feasibility_payload.get("skipped_due_to_anchor_limit", False))
                    else {}
                ),
            }

        global_hint_summary = _summarize_solution_hint(
            solution_hint,
            hinted_occupied_cells=set(
                global_greedy_hint.get("hinted_occupied_cells", set())
            ),
        )
        default_failure_attribution: Dict[str, Any] = {
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
        default_boundary_port_feasibility: Dict[str, Any] = {
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

        warm_start: Dict[str, Any] = {
            "solution_hint": dict(solution_hint),
            "ghost_anchor_hint_idx": None,
            "ghost_anchor_hint_status": "not_applicable",
            "hint_inactive_residual_optionals": False,
            "residual_optional_zero_hints": 0,
            "mandatory_hint_pose_count": int(
                global_hint_summary["mandatory_hint_pose_count"]
            ),
            "mandatory_hint_occupied_cell_count": int(
                global_hint_summary["mandatory_hint_occupied_cell_count"]
            ),
            "ghost_anchor_total_count": 0,
            "ghost_anchor_compatible_count": 0,
            "first_compatible_ghost_anchor_idx": None,
            "ghost_anchor_compatibility_skipped": False,
            "required_optional_positive_hints": int(
                global_hint_summary["required_optional_positive_hints"]
            ),
            "residual_optional_positive_hints": int(
                global_hint_summary["residual_optional_positive_hints"]
            ),
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
            "ghost_aware_pose_order_validation_rejection_samples": [],
            "ghost_aware_coordinate_validation_attempt_count": 0,
            "ghost_aware_coordinate_validation_rejected_count": 0,
            "ghost_aware_coordinate_validation_last_status": None,
            "ghost_aware_coordinate_validation_last_reason": None,
            "ghost_aware_coordinate_validation_rejection_samples": [],
            "ghost_aware_coordinate_validation_limit_reached": False,
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

        if not self.exact_mode:
            warm_start["ghost_anchor_hint_status"] = "unsupported"
            warm_start["warm_start_strategy"] = "unsupported"
            _record_exact_candidate_warm_start(warm_start)
            _record_exact_candidate_warm_start_failure_attribution(
                default_failure_attribution
            )
            self.evaluate_exact_candidate_boundary_port_feasibility()
            return warm_start

        if not self.ghost_rect or not self._ghost_domains or not self.u_vars:
            warm_start["ghost_anchor_hint_status"] = "no_ghost_rect"
            warm_start["warm_start_strategy"] = "no_ghost_rect"
            _record_exact_candidate_warm_start(warm_start)
            _record_exact_candidate_warm_start_failure_attribution(
                default_failure_attribution
            )
            self.evaluate_exact_candidate_boundary_port_feasibility()
            return warm_start

        mandatory_candidates_by_group = {
            str(group["group_id"]): self._candidate_pose_indices_for_group(group)
            for group in self._mandatory_groups
        }
        ordered_mandatory_groups = self._ordered_mandatory_groups_for_greedy(
            mandatory_candidates_by_group
        )

        warm_start["ghost_anchor_total_count"] = int(len(self.u_vars))
        selected_anchor_idx: Optional[int] = None
        selected_hint_data: Optional[Dict[str, Any]] = None
        selected_warm_start_strategy = "ghost_aware_mandatory_rebuild"
        ghost_aware_anchor_attempt_count = 0
        failed_anchor_count = 0
        failure_reason_counts: Counter[str] = Counter()
        failed_group_counts: Counter[Tuple[str, str]] = Counter()
        failed_group_reason_counts: Counter[Tuple[str, str, str]] = Counter()
        failed_anchor_samples: List[Dict[str, Any]] = []
        failed_anchor_sample_limit = _exact_warm_start_failed_anchor_sample_limit()
        first_failed_anchor_idx: Optional[int] = None
        first_failed_group_id: Optional[str] = None
        first_failed_group_template: Optional[str] = None
        first_failed_group_required_count = 0
        first_failed_group_candidate_count = 0
        first_failed_group_surviving_after_blocked_count = 0
        first_failed_group_surviving_at_failure_count = 0
        first_failed_group_position: Optional[int] = None
        local_repair_attempt_count = 0
        local_repair_success_count = 0
        local_repair_intra_group_attempted_count = 0
        local_repair_committed_attempted_count = 0
        local_repair_window1_count = 0
        local_repair_window2_count = 0
        local_repair_portfolio_attempt_count = 0
        pose_order_portfolio_attempt_count = 0
        pose_order_portfolio_failed_anchor_count = 0
        pose_order_portfolio_failure_reason_counts: Counter[str] = Counter()
        pose_order_portfolio_failure_samples: List[Dict[str, Any]] = []
        pose_order_portfolio_selected_ordering: Optional[str] = None
        pose_order_validation_attempt_count = 0
        pose_order_validation_rejected_count = 0
        pose_order_validation_last_status: Optional[str] = None
        pose_order_validation_last_reason: Optional[str] = None
        pose_order_validation_rejection_samples: List[Dict[str, Any]] = []
        coordinate_validation_attempt_count = 0
        coordinate_validation_rejected_count = 0
        coordinate_validation_last_status: Optional[str] = None
        coordinate_validation_last_reason: Optional[str] = None
        coordinate_validation_rejection_samples: List[Dict[str, Any]] = []
        coordinate_validation_limit_reached = False
        first_local_repair_metadata: Optional[Dict[str, Any]] = None
        successful_local_repair_metadata: Optional[Dict[str, Any]] = None
        boundary_port_feasibility = self.evaluate_exact_candidate_boundary_port_feasibility()
        boundary_port_precheck_skipped = bool(
            boundary_port_feasibility.get("skipped_due_to_anchor_limit", False)
        )
        boundary_screen_pass_anchor_indices = tuple(
            int(idx)
            for idx in boundary_port_feasibility.get("screen_pass_anchor_indices", ())
        )
        boundary_rebuild_anchor_indices = tuple(
            int(idx)
            for idx in boundary_port_feasibility.get("rebuild_anchor_indices", ())
        )
        mandatory_group_prechecks = self._default_exact_candidate_mandatory_rectangle_precheck_payload(
            rebuild_anchor_indices=boundary_rebuild_anchor_indices,
            evaluated=False,
            skipped_due_to_upstream_precheck=False,
            upstream_anchor_filter_count=0,
        )
        eligible_anchor_indices: Tuple[int, ...]
        if bool(boundary_port_feasibility.get("supported", False)):
            if boundary_screen_pass_anchor_indices:
                mandatory_group_prechecks = (
                    self.evaluate_exact_candidate_mandatory_rectangle_prechecks(
                        anchor_indices=boundary_screen_pass_anchor_indices
                    )
                )
                mandatory_group_rebuild_anchor_indices = {
                    int(idx)
                    for idx in mandatory_group_prechecks.get(
                        "rebuild_anchor_indices",
                        (),
                    )
                }
                eligible_anchor_indices = tuple(
                    int(idx)
                    for idx in boundary_screen_pass_anchor_indices
                    if int(idx) in mandatory_group_rebuild_anchor_indices
                )
            else:
                self._publish_exact_candidate_mandatory_rectangle_precheck_summary(
                    mandatory_group_prechecks
                )
                eligible_anchor_indices = tuple()
        else:
            self._publish_exact_candidate_mandatory_rectangle_precheck_summary(
                mandatory_group_prechecks
            )
            eligible_anchor_indices = boundary_rebuild_anchor_indices
        for rect_idx in eligible_anchor_indices:
            domain = self._ghost_domains[int(rect_idx)]
            domain_cells = {
                (int(cell[0]), int(cell[1]))
                for cell in list(domain.get("cells", []))
            }
            ghost_aware_anchor_attempt_count += 1
            ghost_aware_hint = self._run_mandatory_greedy_pass(
                ordered_groups=ordered_mandatory_groups,
                candidates_by_group=mandatory_candidates_by_group,
                blocked_cells=domain_cells,
                stop_on_first_failure=True,
            )
            if bool(ghost_aware_hint.get("complete", False)):
                if coordinate_validation_attempt_count >= _exact_ghost_aware_coordinate_validation_max_anchors():
                    coordinate_validation_limit_reached = True
                    failure_reason_counts[
                        "coordinate_validation_attempt_limit_reached"
                    ] += 1
                    break
                validation = self._validate_coordinate_forced_hint(
                    solution_hint=dict(ghost_aware_hint.get("solution_hint", {})),
                    ghost_anchor_hint_idx=int(rect_idx),
                    time_limit_seconds=_exact_ghost_aware_coordinate_validation_seconds(),
                )
                if _coordinate_validation_was_evaluated(validation):
                    coordinate_validation_attempt_count += 1
                coordinate_validation_last_status = str(validation.get("status"))
                coordinate_validation_last_reason = str(validation.get("reason"))
                if not bool(validation.get("accepted", False)):
                    coordinate_validation_rejected_count += 1
                    failed_anchor_count += 1
                    normalized_failure_reason = (
                        f"coordinate_validation_{str(validation.get('reason', 'rejected'))}"
                    )
                    failure_reason_counts[normalized_failure_reason] += 1
                    if first_failed_anchor_idx is None:
                        first_failed_anchor_idx = int(rect_idx)
                        first_failed_group_id = None
                        first_failed_group_template = None
                        first_failed_group_required_count = 0
                        first_failed_group_candidate_count = 0
                        first_failed_group_surviving_after_blocked_count = 0
                        first_failed_group_surviving_at_failure_count = 0
                        first_failed_group_position = None
                    rejection_sample = {
                        "anchor_idx": int(rect_idx),
                        "strategy": "ghost_aware_mandatory_rebuild",
                        "status": str(validation.get("status")),
                        "reason": str(validation.get("reason")),
                        "forced_slot_field_count": int(
                            validation.get("forced_slot_field_count", 0)
                        ),
                        "forced_ghost_anchor": bool(
                            validation.get("forced_ghost_anchor", False)
                        ),
                        "wall_time": float(validation.get("wall_time", 0.0)),
                        "deterministic_time": float(
                            validation.get("deterministic_time", 0.0)
                        ),
                        "branches": int(validation.get("branches", 0)),
                        "conflicts": int(validation.get("conflicts", 0)),
                        "solver_parameters": dict(
                            validation.get("solver_parameters", {})
                        ),
                    }
                    for key in (
                        "capacity_conflict",
                        "same_x_strip_capacity_precheck",
                        "ghost_overlap_forced_domain_precheck",
                        "ghost_y_overlap_precheck",
                        "signature_monotonic_precheck",
                    ):
                        value = validation.get(key)
                        if isinstance(value, Mapping):
                            rejection_sample[key] = dict(value)
                    if len(coordinate_validation_rejection_samples) < int(
                        failed_anchor_sample_limit
                    ):
                        coordinate_validation_rejection_samples.append(
                            dict(rejection_sample)
                        )
                    if len(failed_anchor_samples) < int(failed_anchor_sample_limit):
                        failed_anchor_samples.append(
                            {
                                **dict(rejection_sample),
                                "failure_reason": normalized_failure_reason,
                                "first_failed_group_id": None,
                                "first_failed_group_template": None,
                                "first_failed_group_position": None,
                                "first_failed_group_required_count": 0,
                                "first_failed_group_candidate_count": 0,
                                "first_failed_group_surviving_after_blocked_count": 0,
                                "first_failed_group_surviving_at_failure_count": 0,
                                "blocked_cell_count": int(len(domain_cells)),
                                "blocked_bbox": None,
                                "local_repair_attempted": False,
                                "local_repair_success": False,
                                "local_repair_attempt_count": 0,
                            }
                        )
                    continue
                selected_anchor_idx = int(rect_idx)
                selected_hint_data = ghost_aware_hint
                selected_warm_start_strategy = "ghost_aware_mandatory_rebuild"
                break
            failed_anchor_count += 1
            first_failure_reason = ghost_aware_hint.get("first_failure_reason")
            normalized_failure_reason = str(first_failure_reason or "unknown")
            if first_failure_reason is not None:
                failure_reason_counts[normalized_failure_reason] += 1
            failed_group_id = ghost_aware_hint.get("first_failed_group_id")
            failed_group_template = ghost_aware_hint.get("first_failed_group_template")
            if failed_group_id is not None and failed_group_template is not None:
                failed_group_counts[
                    (str(failed_group_id), str(failed_group_template))
                ] += 1
                failed_group_reason_counts[
                    (
                        str(failed_group_id),
                        str(failed_group_template),
                        normalized_failure_reason,
                    )
                ] += 1
            failed_anchor_sample: Optional[Dict[str, Any]] = None
            if len(failed_anchor_samples) < int(failed_anchor_sample_limit):
                if domain_cells:
                    xs = [int(cell[0]) for cell in domain_cells]
                    ys = [int(cell[1]) for cell in domain_cells]
                    blocked_bbox: Optional[Dict[str, int]] = {
                        "min_x": int(min(xs)),
                        "min_y": int(min(ys)),
                        "max_x": int(max(xs)),
                        "max_y": int(max(ys)),
                    }
                else:
                    blocked_bbox = None
                raw_failed_group_position_for_sample = ghost_aware_hint.get(
                    "first_failed_group_position"
                )
                failed_anchor_sample = {
                    "anchor_idx": int(rect_idx),
                    "failure_reason": normalized_failure_reason,
                    "first_failed_group_id": (
                        None if failed_group_id is None else str(failed_group_id)
                    ),
                    "first_failed_group_template": (
                        None
                        if failed_group_template is None
                        else str(failed_group_template)
                    ),
                    "first_failed_group_position": (
                        None
                        if raw_failed_group_position_for_sample is None
                        else int(raw_failed_group_position_for_sample)
                    ),
                    "first_failed_group_required_count": int(
                        ghost_aware_hint.get("first_failed_group_required_count", 0)
                    ),
                    "first_failed_group_candidate_count": int(
                        ghost_aware_hint.get("first_failed_group_candidate_count", 0)
                    ),
                    "first_failed_group_surviving_after_blocked_count": int(
                        ghost_aware_hint.get(
                            "first_failed_group_surviving_after_blocked_count",
                            0,
                        )
                    ),
                    "first_failed_group_surviving_at_failure_count": int(
                        ghost_aware_hint.get(
                            "first_failed_group_surviving_at_failure_count",
                            0,
                        )
                    ),
                    "blocked_cell_count": int(len(domain_cells)),
                    "blocked_bbox": blocked_bbox,
                    "local_repair_attempted": False,
                    "local_repair_success": False,
                    "local_repair_attempt_count": 0,
                }
            if first_failed_anchor_idx is None:
                first_failed_anchor_idx = int(rect_idx)
                first_failed_group_id = (
                    None if failed_group_id is None else str(failed_group_id)
                )
                first_failed_group_template = (
                    None
                    if failed_group_template is None
                    else str(failed_group_template)
                )
                first_failed_group_required_count = int(
                    ghost_aware_hint.get("first_failed_group_required_count", 0)
                )
                first_failed_group_candidate_count = int(
                    ghost_aware_hint.get("first_failed_group_candidate_count", 0)
                )
                first_failed_group_surviving_after_blocked_count = int(
                    ghost_aware_hint.get(
                        "first_failed_group_surviving_after_blocked_count",
                        0,
                    )
                )
                first_failed_group_surviving_at_failure_count = int(
                    ghost_aware_hint.get(
                        "first_failed_group_surviving_at_failure_count",
                        0,
                    )
                )
                raw_failed_group_position = ghost_aware_hint.get(
                    "first_failed_group_position"
                )
                first_failed_group_position = (
                    None
                    if raw_failed_group_position is None
                    else int(raw_failed_group_position)
                )

            repair_result = self._attempt_mandatory_local_repair(
                anchor_idx=int(rect_idx),
                blocked_cells=set(domain_cells),
                ordered_groups=ordered_mandatory_groups,
                candidates_by_group=mandatory_candidates_by_group,
                canonical_result=ghost_aware_hint,
            )
            if bool(repair_result.get("attempted", False)):
                local_repair_attempt_count += int(repair_result.get("attempt_count", 0))
                local_repair_success_count += int(repair_result.get("success_count", 0))
                local_repair_intra_group_attempted_count += int(
                    repair_result.get("intra_group_attempt_count", 0)
                )
                local_repair_committed_attempted_count += int(
                    repair_result.get("committed_attempt_count", 0)
                )
                local_repair_window1_count += int(
                    repair_result.get("window1_count", 0)
                )
                local_repair_window2_count += int(
                    repair_result.get("window2_count", 0)
                )
                local_repair_portfolio_attempt_count += int(
                    repair_result.get("portfolio_attempt_count", 0)
                )
                if first_local_repair_metadata is None:
                    first_local_repair_metadata = {
                        "trigger_reason": repair_result.get("trigger_reason"),
                        "window_size": int(repair_result.get("window_size", 0)),
                        "anchor_idx": repair_result.get("anchor_idx"),
                        "failed_group_id": repair_result.get("failed_group_id"),
                        "failed_group_template": repair_result.get(
                            "failed_group_template"
                        ),
                        "selected_group_orderings": list(
                            repair_result.get("selected_group_orderings", [])
                        ),
                    }
                if bool(repair_result.get("success", False)):
                    successful_local_repair_metadata = {
                        "trigger_reason": repair_result.get("trigger_reason"),
                        "window_size": int(repair_result.get("window_size", 0)),
                        "anchor_idx": repair_result.get("anchor_idx"),
                        "failed_group_id": repair_result.get("failed_group_id"),
                        "failed_group_template": repair_result.get(
                            "failed_group_template"
                        ),
                        "selected_group_orderings": list(
                            repair_result.get("selected_group_orderings", [])
                        ),
                    }
                    selected_anchor_idx = int(rect_idx)
                    selected_hint_data = repair_result.get("result")
                    selected_warm_start_strategy = "ghost_aware_local_repair"
                    break
            if failed_anchor_sample is not None:
                failed_anchor_sample["local_repair_attempted"] = bool(
                    repair_result.get("attempted", False)
                )
                failed_anchor_sample["local_repair_success"] = bool(
                    repair_result.get("success", False)
                )
                failed_anchor_sample["local_repair_attempt_count"] = int(
                    repair_result.get("attempt_count", 0)
                )
                failed_anchor_samples.append(failed_anchor_sample)

        if (
            selected_anchor_idx is None
            and eligible_anchor_indices
            and not coordinate_validation_limit_reached
        ):
            for ordering_name, custom_group_orders in self._ghost_aware_pose_order_portfolio(
                ordered_groups=ordered_mandatory_groups,
                candidates_by_group=mandatory_candidates_by_group,
            ).items():
                for rect_idx in eligible_anchor_indices:
                    domain = self._ghost_domains[int(rect_idx)]
                    domain_cells = {
                        (int(cell[0]), int(cell[1]))
                        for cell in list(domain.get("cells", []))
                    }
                    pose_order_portfolio_attempt_count += 1
                    ghost_aware_hint = self._run_mandatory_greedy_pass(
                        ordered_groups=ordered_mandatory_groups,
                        candidates_by_group=mandatory_candidates_by_group,
                        blocked_cells=domain_cells,
                        custom_group_orders=custom_group_orders,
                        stop_on_first_failure=True,
                    )
                    if bool(ghost_aware_hint.get("complete", False)):
                        validation = self._validate_coordinate_forced_hint(
                            solution_hint=dict(
                                ghost_aware_hint.get("solution_hint", {})
                            ),
                            ghost_anchor_hint_idx=int(rect_idx),
                            time_limit_seconds=_exact_ghost_aware_pose_order_validation_seconds(),
                        )
                        if _coordinate_validation_was_evaluated(validation):
                            pose_order_validation_attempt_count += 1
                        if not bool(validation.get("accepted", False)):
                            pose_order_validation_rejected_count += 1
                            pose_order_validation_last_status = str(
                                validation.get("status")
                            )
                            pose_order_validation_last_reason = str(
                                validation.get("reason")
                            )
                            if len(pose_order_validation_rejection_samples) < int(
                                failed_anchor_sample_limit
                            ):
                                pose_order_validation_rejection_samples.append(
                                    {
                                        "anchor_idx": int(rect_idx),
                                        "ordering": str(ordering_name),
                                        "status": str(validation.get("status")),
                                        "reason": str(validation.get("reason")),
                                        "forced_slot_field_count": int(
                                            validation.get("forced_slot_field_count", 0)
                                        ),
                                        "forced_ghost_anchor": bool(
                                            validation.get("forced_ghost_anchor", False)
                                        ),
                                        "wall_time": float(
                                            validation.get("wall_time", 0.0)
                                        ),
                                        "deterministic_time": float(
                                            validation.get("deterministic_time", 0.0)
                                        ),
                                        "branches": int(validation.get("branches", 0)),
                                        "conflicts": int(validation.get("conflicts", 0)),
                                        "solver_parameters": dict(
                                            validation.get("solver_parameters", {})
                                        ),
                                    }
                                )
                            normalized_failure_reason = (
                                f"coordinate_validation_{str(validation.get('reason', 'rejected'))}"
                            )
                            if len(pose_order_portfolio_failure_samples) < int(
                                failed_anchor_sample_limit
                            ):
                                pose_order_portfolio_failure_samples.append(
                                    {
                                        "anchor_idx": int(rect_idx),
                                        "ordering": str(ordering_name),
                                        "source": "coordinate_validation",
                                        "failure_reason": normalized_failure_reason,
                                        "status": str(validation.get("status")),
                                        "reason": str(validation.get("reason")),
                                        "forced_slot_field_count": int(
                                            validation.get("forced_slot_field_count", 0)
                                        ),
                                        "forced_ghost_anchor": bool(
                                            validation.get("forced_ghost_anchor", False)
                                        ),
                                        "wall_time": float(
                                            validation.get("wall_time", 0.0)
                                        ),
                                        "deterministic_time": float(
                                            validation.get("deterministic_time", 0.0)
                                        ),
                                        "branches": int(validation.get("branches", 0)),
                                        "conflicts": int(validation.get("conflicts", 0)),
                                    }
                                )
                            pose_order_portfolio_failed_anchor_count += 1
                            pose_order_portfolio_failure_reason_counts[
                                normalized_failure_reason
                            ] += 1
                            continue
                        pose_order_validation_last_status = str(
                            validation.get("status")
                        )
                        pose_order_validation_last_reason = str(
                            validation.get("reason")
                        )
                        selected_anchor_idx = int(rect_idx)
                        selected_hint_data = ghost_aware_hint
                        selected_warm_start_strategy = "ghost_aware_pose_order_portfolio"
                        pose_order_portfolio_selected_ordering = str(ordering_name)
                        break
                    pose_order_portfolio_failed_anchor_count += 1
                    first_failure_reason = ghost_aware_hint.get("first_failure_reason")
                    normalized_failure_reason = str(first_failure_reason or "unknown")
                    if len(pose_order_portfolio_failure_samples) < int(
                        failed_anchor_sample_limit
                    ):
                        pose_order_portfolio_failure_samples.append(
                            {
                                "anchor_idx": int(rect_idx),
                                "ordering": str(ordering_name),
                                "source": "greedy_incomplete",
                                "failure_reason": normalized_failure_reason,
                                "first_failed_group_id": ghost_aware_hint.get(
                                    "first_failed_group_id"
                                ),
                                "first_failed_group_template": ghost_aware_hint.get(
                                    "first_failed_group_template"
                                ),
                                "first_failed_group_position": ghost_aware_hint.get(
                                    "first_failed_group_position"
                                ),
                                "first_failed_group_required_count": int(
                                    ghost_aware_hint.get(
                                        "first_failed_group_required_count",
                                        0,
                                    )
                                ),
                                "first_failed_group_candidate_count": int(
                                    ghost_aware_hint.get(
                                        "first_failed_group_candidate_count",
                                        0,
                                    )
                                ),
                                "first_failed_group_surviving_after_blocked_count": int(
                                    ghost_aware_hint.get(
                                        "first_failed_group_surviving_after_blocked_count",
                                        0,
                                    )
                                ),
                                "first_failed_group_surviving_at_failure_count": int(
                                    ghost_aware_hint.get(
                                        "first_failed_group_surviving_at_failure_count",
                                        0,
                                    )
                                ),
                            }
                        )
                    pose_order_portfolio_failure_reason_counts[
                        normalized_failure_reason
                    ] += 1
                if selected_anchor_idx is not None:
                    break

        warm_start["ghost_aware_anchor_attempt_count"] = int(
            ghost_aware_anchor_attempt_count
        )
        warm_start["ghost_aware_pose_order_portfolio_attempted"] = bool(
            pose_order_portfolio_attempt_count > 0
        )
        warm_start["ghost_aware_pose_order_portfolio_success"] = bool(
            pose_order_portfolio_selected_ordering is not None
        )
        warm_start["ghost_aware_pose_order_portfolio_selected_ordering"] = (
            pose_order_portfolio_selected_ordering
        )
        warm_start["ghost_aware_pose_order_portfolio_attempt_count"] = int(
            pose_order_portfolio_attempt_count
        )
        warm_start["ghost_aware_pose_order_portfolio_failed_anchor_count"] = int(
            pose_order_portfolio_failed_anchor_count
        )
        warm_start["ghost_aware_pose_order_portfolio_failure_reason_counts"] = dict(
            pose_order_portfolio_failure_reason_counts
        )
        warm_start["ghost_aware_pose_order_portfolio_failure_samples"] = [
            dict(entry) for entry in pose_order_portfolio_failure_samples
        ]
        warm_start["ghost_aware_pose_order_validation_attempt_count"] = int(
            pose_order_validation_attempt_count
        )
        warm_start["ghost_aware_pose_order_validation_rejected_count"] = int(
            pose_order_validation_rejected_count
        )
        warm_start["ghost_aware_pose_order_validation_last_status"] = (
            pose_order_validation_last_status
        )
        warm_start["ghost_aware_pose_order_validation_last_reason"] = (
            pose_order_validation_last_reason
        )
        warm_start["ghost_aware_pose_order_validation_rejection_samples"] = [
            dict(entry) for entry in pose_order_validation_rejection_samples
        ]
        warm_start["ghost_aware_coordinate_validation_attempt_count"] = int(
            coordinate_validation_attempt_count
        )
        warm_start["ghost_aware_coordinate_validation_rejected_count"] = int(
            coordinate_validation_rejected_count
        )
        warm_start["ghost_aware_coordinate_validation_last_status"] = (
            coordinate_validation_last_status
        )
        warm_start["ghost_aware_coordinate_validation_last_reason"] = (
            coordinate_validation_last_reason
        )
        warm_start["ghost_aware_coordinate_validation_rejection_samples"] = [
            dict(entry) for entry in coordinate_validation_rejection_samples
        ]
        warm_start["ghost_aware_coordinate_validation_limit_reached"] = bool(
            coordinate_validation_limit_reached
        )
        warm_start["local_repair_attempted"] = bool(local_repair_attempt_count > 0)
        warm_start["local_repair_success"] = bool(local_repair_success_count > 0)
        warm_start["local_repair_portfolio_attempt_count"] = int(
            local_repair_portfolio_attempt_count
        )
        warm_start["local_repair_attempt_count"] = int(local_repair_attempt_count)
        warm_start["local_repair_success_count"] = int(local_repair_success_count)
        warm_start["local_repair_intra_group_attempted_count"] = int(
            local_repair_intra_group_attempted_count
        )
        warm_start["local_repair_committed_attempted_count"] = int(
            local_repair_committed_attempted_count
        )
        warm_start["local_repair_window1_count"] = int(local_repair_window1_count)
        warm_start["local_repair_window2_count"] = int(local_repair_window2_count)
        local_repair_metadata = (
            successful_local_repair_metadata or first_local_repair_metadata or {}
        )
        warm_start["local_repair_trigger_reason"] = local_repair_metadata.get(
            "trigger_reason"
        )
        warm_start["local_repair_window_size"] = int(
            local_repair_metadata.get("window_size", 0)
        )
        warm_start["local_repair_anchor_idx"] = local_repair_metadata.get("anchor_idx")
        warm_start["local_repair_failed_group_id"] = local_repair_metadata.get(
            "failed_group_id"
        )
        warm_start["local_repair_failed_group_template"] = local_repair_metadata.get(
            "failed_group_template"
        )
        warm_start["local_repair_selected_group_orderings"] = [
            str(token)
            for token in list(local_repair_metadata.get("selected_group_orderings", []))[:2]
        ]

        if selected_anchor_idx is not None and selected_hint_data is not None:
            rebuilt_solution_hint = dict(selected_hint_data.get("solution_hint", {}))
            rebuilt_hint_summary = _summarize_solution_hint(
                rebuilt_solution_hint,
                hinted_occupied_cells=set(
                    selected_hint_data.get("hinted_occupied_cells", set())
                ),
            )
            warm_start["solution_hint"] = rebuilt_solution_hint
            warm_start["ghost_anchor_hint_idx"] = int(selected_anchor_idx)
            warm_start["ghost_anchor_hint_status"] = "applied"
            warm_start["mandatory_hint_pose_count"] = int(
                rebuilt_hint_summary["mandatory_hint_pose_count"]
            )
            warm_start["mandatory_hint_occupied_cell_count"] = int(
                rebuilt_hint_summary["mandatory_hint_occupied_cell_count"]
            )
            warm_start["required_optional_positive_hints"] = int(
                rebuilt_hint_summary["required_optional_positive_hints"]
            )
            warm_start["residual_optional_positive_hints"] = int(
                rebuilt_hint_summary["residual_optional_positive_hints"]
            )
            warm_start["ghost_anchor_compatible_count"] = 1
            warm_start["first_compatible_ghost_anchor_idx"] = int(selected_anchor_idx)
            warm_start["warm_start_strategy"] = str(selected_warm_start_strategy)
            warm_start["ghost_aware_anchor_selected_idx"] = int(selected_anchor_idx)
            warm_start["ghost_aware_complete_mandatory_hint"] = bool(
                selected_hint_data.get("complete", False)
            )
            warm_start["ghost_aware_hint_instances"] = int(
                len(rebuilt_solution_hint)
            )
        else:
            warm_start["ghost_anchor_compatible_count"] = 0
            if boundary_port_precheck_skipped:
                warm_start["ghost_anchor_hint_status"] = "skipped_anchor_limit"
                warm_start["ghost_anchor_compatibility_skipped"] = True
                warm_start["warm_start_strategy"] = "precheck_anchor_limit_skipped"
            else:
                warm_start["ghost_anchor_hint_status"] = "none_compatible"
                warm_start["warm_start_strategy"] = "global_greedy_fallback"

        _record_exact_candidate_warm_start(warm_start)
        _record_exact_candidate_boundary_port_feasibility(boundary_port_feasibility)
        _record_exact_candidate_warm_start_failure_attribution(
            {
                "attempted_anchor_count": int(ghost_aware_anchor_attempt_count),
                "failed_anchor_count": int(failed_anchor_count),
                "failure_reason_counts": dict(failure_reason_counts),
                "first_failed_anchor_idx": first_failed_anchor_idx,
                "first_failed_group_id": first_failed_group_id,
                "first_failed_group_template": first_failed_group_template,
                "first_failed_group_required_count": int(
                    first_failed_group_required_count
                ),
                "first_failed_group_candidate_count": int(
                    first_failed_group_candidate_count
                ),
                "first_failed_group_surviving_after_blocked_count": int(
                    first_failed_group_surviving_after_blocked_count
                ),
                "first_failed_group_surviving_at_failure_count": int(
                    first_failed_group_surviving_at_failure_count
                ),
                "first_failed_group_position": first_failed_group_position,
                "top_failed_groups": [
                    {
                        "group_id": str(group_id),
                        "facility_type": str(facility_type),
                        "count": int(count),
                    }
                    for (group_id, facility_type), count in failed_group_counts.most_common(5)
                ],
                "top_failed_group_failures": [
                    {
                        "group_id": str(group_id),
                        "facility_type": str(facility_type),
                        "failure_reason": str(failure_reason),
                        "count": int(count),
                    }
                    for (
                        group_id,
                        facility_type,
                        failure_reason,
                    ), count in failed_group_reason_counts.most_common(8)
                ],
                "failed_anchor_samples": list(failed_anchor_samples),
            }
        )
        return warm_start

    def _clear_solution_hints(self) -> None:
        if hasattr(self.model, "ClearHints"):
            self.model.ClearHints()
            return
        proto = self.model.Proto()
        del proto.solution_hint.vars[:]
        del proto.solution_hint.values[:]

    def _hint_var_for_key(self, solution_key: str, pose_idx: int) -> Optional[cp_model.IntVar]:
        if solution_key in self._group_id_by_instance:
            group_id = self._group_id_by_instance[solution_key]
            return self.z_vars.get(group_id, {}).get(int(pose_idx))
        tpl = self._infer_optional_template_from_solution_id(solution_key)
        if tpl is not None:
            return self.optional_pose_vars.get(tpl, {}).get(int(pose_idx))
        return None

    def solve(
        self,
        time_limit_seconds: float = 60.0,
        solution_hint: Optional[Mapping[str, int]] = None,
        known_feasible_hint: bool = False,
        ghost_anchor_hint_idx: Optional[int] = None,
        hint_inactive_residual_optionals: bool = True,
        diagnostic_log_callback: Optional[Callable[[str], None]] = None,
    ) -> int:
        if not self._built:
            self.build()

        self._clear_solution_hints()
        hinted = 0
        hint_application: Dict[str, Any] = {
            "hinted_literals": 0,
            "ghost_anchor_hint_applied": False,
            "ghost_anchor_hint_idx": None,
            "residual_optional_zero_hinting_enabled": bool(
                hint_inactive_residual_optionals
            ),
            "residual_optional_zero_hints": 0,
        }
        if (
            self.exact_mode
            and self._coordinate_delegate is not None
            and (
                bool(solution_hint)
                or ghost_anchor_hint_idx is not None
                or not bool(hint_inactive_residual_optionals)
            )
        ):
            hint_application = self._coordinate_delegate.apply_solution_hint(
                solution_hint or {},
                ghost_anchor_hint_idx=ghost_anchor_hint_idx,
                hint_inactive_residual_optionals=hint_inactive_residual_optionals,
            )
            hinted = int(hint_application.get("hinted_literals", 0))
        elif solution_hint:
            for key, pose_idx in solution_hint.items():
                var = self._hint_var_for_key(str(key), int(pose_idx))
                if var is None:
                    continue
                self.model.AddHint(var, 1)
                hinted += 1

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(time_limit_seconds)
        solver.parameters.num_search_workers = resolve_cp_sat_worker_count(
            env_name="EXACT_MASTER_CP_SAT_WORKERS",
            default=DEFAULT_MASTER_CP_SAT_WORKERS,
        )
        # Phase 3C P0 #3 (R12-revised conservative): exclude unhelpful LNS
        # subsolvers for max_lex objective. See cp_sat_worker_config.py.
        apply_master_cp_sat_subsolver_filter(solver)
        # Phase 3C P0 #4 #8 (env-gated): stronger no_overlap_2d propagation.
        # Default off; A/B benchmark via env to validate cost/benefit.
        apply_master_cp_sat_strong_disjunctive_propagation(solver)
        # Phase 3C P1 #11 (PT-style portfolio): allow per-process random_seed
        # override so multi-process invocation can spawn parallel-tempering
        # diverse search trajectories. Default falls back to CP-SAT default
        # (1) when env not set. R10 a2d29f537e2b0ba30 audit recommendation.
        seed_env = os.environ.get("EXACT_MASTER_RANDOM_SEED")
        if seed_env:
            try:
                solver.parameters.random_seed = int(seed_env)
            except ValueError:
                pass
        requested_search_branching = "default"
        if self.exact_mode:
            requested_search_branching = str(
                os.environ.get(EXACT_MASTER_SEARCH_BRANCHING_ENV, "fixed")
            ).strip().lower()
            if requested_search_branching in {"", "fixed"}:
                solver.parameters.search_branching = cp_model.FIXED_SEARCH
                requested_search_branching = "fixed"
            elif requested_search_branching == "automatic":
                solver.parameters.search_branching = cp_model.AUTOMATIC_SEARCH
            elif requested_search_branching == "portfolio":
                solver.parameters.search_branching = cp_model.PORTFOLIO_SEARCH
            else:
                raise ValueError(
                    f"Unsupported {EXACT_MASTER_SEARCH_BRANCHING_ENV}: "
                    f"{requested_search_branching}"
                )
            cp_model_presolve = _resolve_optional_bool_env(
                EXACT_MASTER_CP_MODEL_PRESOLVE_ENV
            )
            if cp_model_presolve is not None and hasattr(
                solver.parameters,
                "cp_model_presolve",
            ):
                solver.parameters.cp_model_presolve = bool(cp_model_presolve)
            symmetry_level = _resolve_optional_nonnegative_int_env(
                EXACT_MASTER_SYMMETRY_LEVEL_ENV
            )
            if symmetry_level is None:
                symmetry_level = max(int(solver.parameters.symmetry_level), 3)
            solver.parameters.symmetry_level = int(symmetry_level)
            probing_level = _resolve_optional_nonnegative_int_env(
                EXACT_MASTER_CP_MODEL_PROBING_LEVEL_ENV
            )
            if probing_level is None:
                probing_level = max(int(solver.parameters.cp_model_probing_level), 3)
            solver.parameters.cp_model_probing_level = int(probing_level)
            # P1 #7c prep: enable fill_tightened_domains_in_response (default
            # True; env "0/false/no/off" disable). Prep only: 这一阶段只是把
            # 参数打开让 response 包含 tightened domain。下一波 read + 用作
            # 初始域是 P1 #7 主体阶段的事。
            if hasattr(solver.parameters, "fill_tightened_domains_in_response"):
                fill_tightened_env = os.environ.get(
                    EXACT_MASTER_FILL_TIGHTENED_DOMAINS_ENV, ""
                ).strip().lower()
                if fill_tightened_env in {"0", "false", "no", "off"}:
                    solver.parameters.fill_tightened_domains_in_response = False
                else:
                    solver.parameters.fill_tightened_domains_in_response = True
            hint_conflict_limit = _resolve_optional_nonnegative_int_env(
                EXACT_MASTER_HINT_CONFLICT_LIMIT_ENV
            )
            if hint_conflict_limit is None:
                hint_conflict_limit = max(
                    int(solver.parameters.hint_conflict_limit),
                    1000,
                )
            solver.parameters.hint_conflict_limit = int(hint_conflict_limit)
            # audit A H3 修复: 启用 repair_hint 让 solver 修补部分过期 hint
            # 而不是全 reject. 跨 wave hint reuse 场景必需 (warm-start hint
            # 来自上一 wave, 后续 wave cut 让部分变量值过期).
            # **env-gate**: 只在 hint persistence 真启用时设, 因为 OR-Tools 9.15
            # MinimizeL1DistanceWithHint 在某些 model 状态 (空 hint / 边角)
            # 上加 repair_hint 会 SIGABRT (实测 86 guard 偶发崩溃). default off
            # 时不动, 走 OR-Tools 默认路径.
            if hasattr(solver.parameters, "repair_hint"):
                try:
                    from src.search.master_hint_persistence import is_enabled
                    if is_enabled():
                        solver.parameters.repair_hint = True
                except Exception:
                    pass
        log_callback_enabled = False
        if diagnostic_log_callback is not None:
            if hasattr(solver.parameters, "log_search_progress"):
                solver.parameters.log_search_progress = True
            if hasattr(solver.parameters, "log_to_stdout"):
                solver.parameters.log_to_stdout = False
            try:
                solver.log_callback = diagnostic_log_callback
                log_callback_enabled = True
            except Exception:
                log_callback_enabled = False
        status = solver.Solve(self.model)

        self._solver = solver
        self._status = status
        self._last_solution = None
        self.build_stats["last_solve"] = {
            "status": solver.StatusName(status),
            "wall_time": solver.WallTime(),
            "user_time": float(
                _extract_solver_numeric_stat(
                    solver,
                    "UserTime",
                    "user_time",
                    default=0.0,
                )
            ),
            "deterministic_time": float(
                _extract_solver_numeric_stat(
                    solver,
                    "deterministic_time",
                    default=0.0,
                )
            ),
            "branches": int(
                _extract_solver_numeric_stat(
                    solver,
                    "NumBranches",
                    "num_branches",
                    default=0,
                )
            ),
            "conflicts": int(
                _extract_solver_numeric_stat(
                    solver,
                    "NumConflicts",
                    "num_conflicts",
                    default=0,
                )
            ),
            "binary_propagations": int(
                _extract_solver_numeric_stat(
                    solver,
                    "num_binary_propagations",
                    default=0,
                )
            ),
            "integer_propagations": int(
                _extract_solver_numeric_stat(
                    solver,
                    "num_integer_propagations",
                    default=0,
                )
            ),
            "hinted_literals": hinted,
            "known_feasible_hint": bool(known_feasible_hint),
            "search_profile": str(
                self.build_stats.get("search_guidance", {}).get("profile", "default_automatic")
            ),
            "search_branching": search_branching_name(
                solver.parameters.search_branching
            ),
            "requested_search_branching": requested_search_branching,
            "solver_parameters": {
                "max_time_in_seconds": float(solver.parameters.max_time_in_seconds),
                "num_search_workers": int(solver.parameters.num_search_workers),
                "symmetry_level": int(solver.parameters.symmetry_level),
                "cp_model_probing_level": int(solver.parameters.cp_model_probing_level),
                "hint_conflict_limit": int(solver.parameters.hint_conflict_limit),
                "cp_model_presolve": bool(
                    getattr(solver.parameters, "cp_model_presolve", True)
                ),
                "log_search_progress": bool(
                    getattr(solver.parameters, "log_search_progress", False)
                ),
                "log_to_stdout": bool(getattr(solver.parameters, "log_to_stdout", False)),
                "log_callback_enabled": bool(log_callback_enabled),
            },
            "response_stats": solver.ResponseStats(),
            "ghost_anchor_hint_applied": bool(
                hint_application.get("ghost_anchor_hint_applied", False)
            ),
            "ghost_anchor_hint_idx": hint_application.get("ghost_anchor_hint_idx"),
            "residual_optional_zero_hinting_enabled": bool(
                hint_application.get(
                    "residual_optional_zero_hinting_enabled",
                    hint_inactive_residual_optionals,
                )
            ),
            "residual_optional_zero_hints": int(
                hint_application.get("residual_optional_zero_hints", 0)
            ),
        }
        # P1 #7 main #2: solve 末尾 FEASIBLE/OPTIMAL 时自动 extract+write hint.
        # No-op if env unset or context not set.
        self._maybe_save_hints_to_persistence()
        return status

    # ---- P1 #7 main: hint 跨 wave 持久化 helpers ----

    def set_hint_persistence_context(
        self,
        project_root: Optional[Path],
        candidate_key: Optional[str],
    ) -> None:
        """配 (project_root, candidate_key); 任一为 None 则 disable.

        configured 后 build/solve 自动 load+apply / extract+write (受
        EXACT_MASTER_HINT_PERSISTENCE env 开关控制).
        """
        if project_root is None or candidate_key is None:
            self._hint_persistence_context = None
        else:
            self._hint_persistence_context = (Path(project_root), str(candidate_key))

    def extract_master_hints(self) -> Dict[str, int]:
        """Extract decision-variable values for cross-wave hint persistence.

        Only returns values when solver finished FEASIBLE/OPTIMAL. exact_mode
        fall back to delegate if it implements `extract_master_hints`; else
        returns {} (delegate 未实现 hint 接口).
        """
        if self._solver is None or self._status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {}
        if self.exact_mode and self._coordinate_delegate is not None:
            delegate_extract = getattr(
                self._coordinate_delegate, "extract_master_hints", None,
            )
            if callable(delegate_extract):
                try:
                    return dict(delegate_extract(self._solver))
                except Exception:
                    return {}
            return {}
        out: Dict[str, int] = {}
        for by_pose in self.z_vars.values():
            for var in by_pose.values():
                try:
                    out[var.Name()] = int(self._solver.Value(var))
                except Exception:
                    continue
        for by_pose in getattr(self, "optional_pose_vars", {}).values():
            for var in by_pose.values():
                try:
                    out[var.Name()] = int(self._solver.Value(var))
                except Exception:
                    continue
        return out

    def apply_master_hints(self, hints: Mapping[str, int]) -> int:
        """Apply previously-saved hints to current model. Returns hit count."""
        if not self._built or not hints:
            return 0
        if self.exact_mode and self._coordinate_delegate is not None:
            delegate_apply = getattr(
                self._coordinate_delegate, "apply_master_hints", None,
            )
            if callable(delegate_apply):
                try:
                    return int(delegate_apply(hints))
                except Exception:
                    return 0
            return 0
        hits = 0
        for by_pose in self.z_vars.values():
            for var in by_pose.values():
                name = var.Name()
                if name in hints:
                    try:
                        self.model.AddHint(var, int(hints[name]))
                        hits += 1
                    except Exception:
                        continue
        for by_pose in getattr(self, "optional_pose_vars", {}).values():
            for var in by_pose.values():
                name = var.Name()
                if name in hints:
                    try:
                        self.model.AddHint(var, int(hints[name]))
                        hits += 1
                    except Exception:
                        continue
        return hits

    def _maybe_load_hints_from_persistence(self) -> int:
        """P1 #7 main #1: build 末尾自动 load+apply hints (env-gated)."""
        try:
            from src.search import master_hint_persistence as mhp
        except Exception:
            return 0
        if not mhp.is_enabled():
            return 0
        if self._hint_persistence_context is None:
            return 0
        project_root, candidate_key = self._hint_persistence_context
        loaded = mhp.load_master_hints(project_root, candidate_key)
        if not loaded:
            return 0
        try:
            return int(self.apply_master_hints(loaded))
        except Exception:
            return 0

    def _maybe_save_hints_to_persistence(self) -> int:
        """P1 #7 main #2: solve 末尾 FEASIBLE/OPTIMAL 时自动 extract+write."""
        try:
            from src.search import master_hint_persistence as mhp
        except Exception:
            return 0
        if not mhp.is_enabled():
            return 0
        if self._hint_persistence_context is None:
            return 0
        if self._status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return 0
        project_root, candidate_key = self._hint_persistence_context
        hints = self.extract_master_hints()
        if not hints:
            return 0
        try:
            mhp.write_master_hints(project_root, candidate_key, hints)
            return len(hints)
        except Exception:
            return 0

    def extract_bound_state(
        self,
        *,
        epsilon_target: Optional[float] = None,
    ) -> Dict[str, Any]:
        """P1 #7 main: 给 ε-Certified 三阶段写回 bound_state 用.

        从 self._solver 提取 best objective bound (lb) + objective value
        (ub), 算 gap, 返回 bound_state dict (可直接喂给
        ExactCampaign.update_candidate_bound_state).

        防御性: ObjectiveValue() 在 INFEASIBLE/UNKNOWN 无 incumbent 时
        会 raise; BestObjectiveBound() 一般可调. 失败则该字段返 None.
        """
        out: Dict[str, Any] = {
            "lb": None,
            "ub": None,
            "gap": None,
            "epsilon_target": (
                None if epsilon_target is None else float(epsilon_target)
            ),
            "prover": "master_cpsat",
        }
        if self._solver is None:
            return out
        try:
            best_bound = self._solver.BestObjectiveBound()
            if best_bound is not None and not (
                isinstance(best_bound, float) and math.isinf(best_bound)
            ):
                out["lb"] = int(best_bound)
        except Exception:
            pass
        if self._status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            try:
                obj = self._solver.ObjectiveValue()
                if obj is not None and not (
                    isinstance(obj, float) and math.isinf(obj)
                ):
                    out["ub"] = int(obj)
            except Exception:
                pass
        if out["lb"] is not None and out["ub"] is not None:
            denom = max(abs(out["ub"]), 1)
            out["gap"] = float(out["ub"] - out["lb"]) / float(denom)
        return out

    def extract_solution(self) -> Dict[str, Any]:
        if self._solver is None or self._status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {}
        if self._last_solution is not None:
            return dict(self._last_solution)
        if self.exact_mode and self._coordinate_delegate is not None:
            self._last_solution = dict(self._coordinate_delegate.extract_solution())
            return dict(self._last_solution)

        solution: Dict[str, Any] = {}

        for group in self._mandatory_groups:
            group_id = group["group_id"]
            tpl = group["facility_type"]
            operation_type = group["operation_type"]
            selected_pose_indices = sorted(
                pose_idx
                for pose_idx, var in self.z_vars[group_id].items()
                if self._solver.Value(var) == 1
            )
            for instance_id, pose_idx in zip(sorted(group["instance_ids"]), selected_pose_indices):
                pose = self.facility_pools[tpl][pose_idx]
                solution[instance_id] = {
                    "instance_id": instance_id,
                    "facility_type": tpl,
                    "operation_type": operation_type,
                    "pose_idx": pose_idx,
                    "pose_id": pose["pose_id"],
                    "anchor": dict(pose["anchor"]),
                    "is_mandatory": True,
                    "bound_type": "exact",
                    "solve_mode": self.solve_mode,
                }

        for tpl, vars_by_pose in self.optional_pose_vars.items():
            operation_type = POSE_LEVEL_OPTIONAL_OPERATIONS[tpl]
            for pose_idx, var in vars_by_pose.items():
                if self._solver.Value(var) != 1:
                    continue
                pose = self.facility_pools[tpl][pose_idx]
                synthetic_id = f"pose_optional::{tpl}::{pose['pose_id']}"
                solution[synthetic_id] = {
                    "instance_id": synthetic_id,
                    "facility_type": tpl,
                    "operation_type": operation_type,
                    "pose_idx": pose_idx,
                    "pose_id": pose["pose_id"],
                    "anchor": dict(pose["anchor"]),
                    "is_mandatory": False,
                    "bound_type": "exact_pose_optional" if self.exact_mode else "exploratory_pose_optional",
                    "solve_mode": self.solve_mode,
                }

        self._last_solution = dict(solution)
        return solution

    def _infer_optional_template_from_solution_id(self, solution_id: str) -> Optional[str]:
        if solution_id.startswith("pose_optional::power_pole::"):
            return "power_pole"
        if solution_id.startswith("pose_optional::protocol_storage_box::"):
            return "protocol_storage_box"
        if solution_id.startswith("power_pole_"):
            return "power_pole"
        if solution_id.startswith("protocol_box_") or solution_id.startswith("protocol_storage_box_"):
            return "protocol_storage_box"
        return None

    def add_benders_cut(self, conflict_set: Mapping[str, int]) -> bool:
        if self.exact_mode and self._coordinate_delegate is not None:
            return self._coordinate_delegate.add_benders_cut(conflict_set)
        literals: List[cp_model.IntVar] = []
        seen_names: Set[str] = set()
        for solution_id, pose_idx in conflict_set.items():
            var: Optional[cp_model.IntVar] = None
            if solution_id in self._group_id_by_instance:
                group_id = self._group_id_by_instance[solution_id]
                var = self.z_vars.get(group_id, {}).get(int(pose_idx))
            else:
                tpl = self._infer_optional_template_from_solution_id(str(solution_id))
                if tpl is not None:
                    var = self.optional_pose_vars.get(tpl, {}).get(int(pose_idx))
            if var is None:
                continue
            name = var.Name()
            if name in seen_names:
                continue
            seen_names.add(name)
            literals.append(var)

        if not literals:
            return False
        # The Benders Cut: sum of conflicting z_vars <= N - 1
        self.model.Add(sum(literals) <= len(literals) - 1)
        self._last_solution = None
        return True


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent.parent
    instances, pools, rules = load_project_data(project_root)
    model = MasterPlacementModel(instances, pools, rules, ghost_rect=(6, 6))
    model.build()
    status = model.solve(time_limit_seconds=5.0)
    print("status=", status)
