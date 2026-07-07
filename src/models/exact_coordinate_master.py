"""Exact coordinate master backend (delegate for MasterPlacementModel).

负责精确坐标搜索路径的 CP-SAT 模型构造 + Benders 切平面应用 + ghost rect 强制.
被 master_model.py 的 ExactMasterCore.from_exact_core() 调用, 不是独立入口.

文件目录索引 (≈6530 行, 行号大约值, vintage 2026-05-16):
- L1-200    imports + 顶层常量 + env name 定义
- L200-540  env 解析 / search profile / formulation 选择 helpers (大量 resolve_* 函数)
- L540-670  family shell guard 几何 + 约束 helpers
- L671-715  数据类: ModeRectDomain / SignatureRegion / CoordinateSlotSpec
- L716-     class CoordinateExactMasterDelegate (主类) 起点:
    构造 / build 模型 / 加约束 / Benders cut 应用 / hint 应用
- L1430-1500 _apply_ghost_anchor_signature_bucket_tightening (build phase 关键步骤)
- L3196-3280 _add_ghost_constraints (ghost rect enforcement, 入口)
- L4193-     _apply_ghost_anchor_signature_bucket_tightening + 各种 tightening pass
- L6268      apply_solution_hint (接 Dict[instance_id, pose_idx], 调 model.AddHint per slot)
- L6346      _cut_name_token + tail helpers

主要外部 API:
- CoordinateExactMasterDelegate(owner, ...) — 构造时 owner 是 MasterPlacementModel
    .build(...) — 把约束/变量 attach 到 owner.model
    .apply_solution_hint(solution_hint, ghost_anchor_hint_idx, ...) — hint 应用
    .extract_solution(solver) — 从 solved CP-SAT solver 抽 placement_solution

env 变量 (本文件读): 主要在 docs/env_variable_index.md C/E/I 组 (Master 调优 + Search profile + Power encoding).
"""

from __future__ import annotations

import copy
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, DefaultDict, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from ortools.sat.python import cp_model

from src.models.solution_hint_parser import parse_strict_int_hint_value
from src.preprocess.operation_profiles import get_operation_port_profile


ModeToken = Tuple[str, str, str]
PoseTuple = Tuple[int, int, int]

DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE = "exact_coordinate_guided_branching_v4"
EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION_ENV = (
    "EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION"
)
EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION_ENV = (
    "EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION"
)
EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV = (
    "EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION"
)
EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV = (
    "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING"
)
EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV = (
    "EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION"
)
EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV = (
    "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT"
)
EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_ENV = (
    "EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION"
)
EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT_ENV = (
    "EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT"
)
EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION_ENV = (
    "EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION"
)
EXACT_POWER_FAMILY_LOOKUP_ENCODING_ENV = "EXACT_POWER_FAMILY_LOOKUP_ENCODING"
EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_ENV = "EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING"
EXACT_POWER_COVERAGE_WITNESS_ENCODING_ENV = "EXACT_POWER_COVERAGE_WITNESS_ENCODING"
EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV = (
    "EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY"
)
EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE_ENV = "EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE"
EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES_ENV = (
    "EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES"
)
EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_ENV = (
    "EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING"
)
EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION_BIG_M = "big_m"
EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION_ENFORCED = "enforced"
EXACT_POWER_FAMILY_LOOKUP_ENCODING_TABLE = "table"
EXACT_POWER_FAMILY_LOOKUP_ENCODING_LINEAR_SHELL_GUARDS = "linear_shell_guards"
EXACT_POWER_FAMILY_LOOKUP_ENCODING_SHELL_PAIR_INDEX = "shell_pair_index"
EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_ELEMENT = "element"
EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_LINEAR_MINMAX = "linear_minmax"
EXACT_POWER_COVERAGE_WITNESS_ENCODING_ELEMENT = "element"
EXACT_POWER_COVERAGE_WITNESS_ENCODING_BLOCK_ELEMENT = "block_element"
EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_FINAL_TARGET = "final_target"
EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK = "selected_block"
EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD = (
    "selected_block_active_guard"
)
EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_GROUPED_XY = (
    "selected_block_active_guard_grouped_xy"
)
EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_JOINED_XY = (
    "selected_block_active_guard_joined_xy"
)
EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_BOUNDS = "bounds"
EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_DELTA = "delta"
EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATIONS = {
    EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION_BIG_M,
    EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION_ENFORCED,
}
EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION_TRUE_VALUES = {"1", "true", "on"}
EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION_FALSE_VALUES = {
    "",
    "0",
    "false",
    "off",
    "no",
}
EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_TRUE_VALUES = {
    "1",
    "true",
    "on",
}
EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_FALSE_VALUES = {
    "",
    "0",
    "false",
    "off",
    "no",
}
EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_TRUE_VALUES = {
    "1",
    "true",
    "on",
}
EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_FALSE_VALUES = {
    "",
    "0",
    "false",
    "off",
    "no",
}
EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_TRUE_VALUES = {
    "1",
    "true",
    "on",
}
EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_FALSE_VALUES = {
    "",
    "0",
    "false",
    "off",
    "no",
}
EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_TRUE_VALUES = {
    "1",
    "true",
    "on",
}
EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_FALSE_VALUES = {
    "",
    "0",
    "false",
    "off",
    "no",
}
EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_TRUE_VALUES = {
    "1",
    "true",
    "on",
}
EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_FALSE_VALUES = {
    "",
    "0",
    "false",
    "off",
    "no",
}
EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT_TRUE_VALUES = {
    "1",
    "true",
    "on",
}
EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT_FALSE_VALUES = {
    "",
    "0",
    "false",
    "off",
    "no",
}
EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION_TRUE_VALUES = {
    "1",
    "true",
    "on",
}
EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION_FALSE_VALUES = {
    "",
    "0",
    "false",
    "off",
    "no",
}
EXACT_POWER_FAMILY_LOOKUP_ENCODINGS = {
    EXACT_POWER_FAMILY_LOOKUP_ENCODING_TABLE,
    EXACT_POWER_FAMILY_LOOKUP_ENCODING_LINEAR_SHELL_GUARDS,
    EXACT_POWER_FAMILY_LOOKUP_ENCODING_SHELL_PAIR_INDEX,
}
EXACT_POWER_POLE_SHELL_DISTANCE_ENCODINGS = {
    EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_ELEMENT,
    EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_LINEAR_MINMAX,
}
EXACT_POWER_COVERAGE_WITNESS_ENCODINGS = {
    EXACT_POWER_COVERAGE_WITNESS_ENCODING_ELEMENT,
    EXACT_POWER_COVERAGE_WITNESS_ENCODING_BLOCK_ELEMENT,
}
EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRIES = {
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_FINAL_TARGET,
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK,
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD,
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_GROUPED_XY,
    EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_JOINED_XY,
}
EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODINGS = {
    EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_BOUNDS,
    EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_DELTA,
}
EXACT_COORDINATE_MASTER_SEARCH_PROFILES = {
    DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE,
    "exact_coordinate_ghost_after_counts_v1",
    "exact_coordinate_ghost_first_v1",
}


def normalize_exact_coordinate_master_search_profile(raw_value: Optional[str]) -> str:
    if raw_value is None:
        return DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE
    normalized = str(raw_value).strip()
    if normalized in EXACT_COORDINATE_MASTER_SEARCH_PROFILES:
        return normalized
    raise ValueError(f"Unsupported master_search_profile: {raw_value}")


def resolve_ghost_conditioned_family_bound_formulation() -> str:
    raw_value = os.environ.get(EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION_ENV)
    normalized = (
        EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION_BIG_M
        if raw_value is None or not str(raw_value).strip()
        else str(raw_value).strip().lower()
    )
    if normalized not in EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATIONS:
        raise ValueError(
            "Unsupported "
            f"{EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION_ENV}: {raw_value!r}; "
            "expected one of "
            + ", ".join(sorted(EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATIONS))
        )
    return normalized


def resolve_ghost_via_pole_shape_instrumentation_enabled() -> bool:
    raw_value = os.environ.get(EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION_ENV)
    if raw_value is None:
        return False
    normalized = str(raw_value).strip().lower()
    if normalized in EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION_FALSE_VALUES:
        return False
    if normalized in EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION_TRUE_VALUES:
        return True
    raise ValueError(
        "Unsupported "
        f"{EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION_ENV}: {raw_value!r}; "
        "expected disabled/unset or one of "
        + ", ".join(sorted(EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION_TRUE_VALUES))
    )


def resolve_ghost_signature_bucket_tightening_instrumentation_enabled() -> bool:
    raw_value = os.environ.get(
        EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    )
    if raw_value is None:
        return False
    normalized = str(raw_value).strip().lower()
    if normalized in EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_FALSE_VALUES:
        return False
    if normalized in EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_TRUE_VALUES:
        return True
    raise ValueError(
        "Unsupported "
        f"{EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV}: "
        f"{raw_value!r}; expected disabled/unset or one of "
        + ", ".join(
            sorted(EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_TRUE_VALUES)
        )
    )


def resolve_ghost_signature_bucket_mandatory_region_counting_enabled() -> bool:
    raw_value = os.environ.get(
        EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    )
    if raw_value is None:
        return False
    normalized = str(raw_value).strip().lower()
    if normalized in EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_FALSE_VALUES:
        return False
    if normalized in EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_TRUE_VALUES:
        return True
    raise ValueError(
        "Unsupported "
        f"{EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV}: "
        f"{raw_value!r}; expected disabled/unset or one of "
        + ", ".join(
            sorted(EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_TRUE_VALUES)
        )
    )


def resolve_ghost_signature_bucket_mandatory_region_fallback_instrumentation_enabled() -> bool:
    raw_value = os.environ.get(
        EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    )
    if raw_value is None:
        return False
    normalized = str(raw_value).strip().lower()
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_FALSE_VALUES
    ):
        return False
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_TRUE_VALUES
    ):
        return True
    raise ValueError(
        "Unsupported "
        f"{EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV}: "
        f"{raw_value!r}; expected disabled/unset or one of "
        + ", ".join(
            sorted(
                EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_TRUE_VALUES
            )
        )
    )


def resolve_ghost_signature_bucket_template_footprint_support_enabled() -> bool:
    raw_value = os.environ.get(
        EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    )
    if raw_value is None:
        return False
    normalized = str(raw_value).strip().lower()
    if normalized in EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_FALSE_VALUES:
        return False
    if normalized in EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_TRUE_VALUES:
        return True
    raise ValueError(
        "Unsupported "
        f"{EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV}: "
        f"{raw_value!r}; expected disabled/unset or one of "
        + ", ".join(
            sorted(EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_TRUE_VALUES)
        )
    )


def resolve_ghost_signature_bucket_template_footprint_support_gap_instrumentation_enabled() -> bool:
    raw_value = os.environ.get(
        EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_ENV
    )
    if raw_value is None:
        return False
    normalized = str(raw_value).strip().lower()
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_FALSE_VALUES
    ):
        return False
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_TRUE_VALUES
    ):
        return True
    raise ValueError(
        "Unsupported "
        f"{EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_ENV}: "
        f"{raw_value!r}; expected disabled/unset or one of "
        + ", ".join(
            sorted(
                EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_TRUE_VALUES
            )
        )
    )


def resolve_ghost_signature_bucket_payload_footprint_stability_support_enabled() -> bool:
    raw_value = os.environ.get(
        EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT_ENV
    )
    if raw_value is None:
        return False
    normalized = str(raw_value).strip().lower()
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT_FALSE_VALUES
    ):
        return False
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT_TRUE_VALUES
    ):
        return True
    raise ValueError(
        "Unsupported "
        f"{EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT_ENV}: "
        f"{raw_value!r}; expected disabled/unset or one of "
        + ", ".join(
            sorted(
                EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT_TRUE_VALUES
            )
        )
    )


def resolve_ghost_signature_bucket_residual_overlay_instrumentation_enabled() -> bool:
    raw_value = os.environ.get(
        EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION_ENV
    )
    if raw_value is None:
        return False
    normalized = str(raw_value).strip().lower()
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION_FALSE_VALUES
    ):
        return False
    if (
        normalized
        in EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION_TRUE_VALUES
    ):
        return True
    raise ValueError(
        "Unsupported "
        f"{EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION_ENV}: "
        f"{raw_value!r}; expected disabled/unset or one of "
        + ", ".join(
            sorted(
                EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION_TRUE_VALUES
            )
        )
    )


def resolve_exact_power_family_lookup_encoding() -> str:
    raw_value = os.environ.get(EXACT_POWER_FAMILY_LOOKUP_ENCODING_ENV)
    normalized = (
        EXACT_POWER_FAMILY_LOOKUP_ENCODING_TABLE
        if raw_value is None or not str(raw_value).strip()
        else str(raw_value).strip().lower()
    )
    if normalized not in EXACT_POWER_FAMILY_LOOKUP_ENCODINGS:
        raise ValueError(
            f"Unsupported {EXACT_POWER_FAMILY_LOOKUP_ENCODING_ENV}: {raw_value!r}; "
            "expected one of "
            + ", ".join(sorted(EXACT_POWER_FAMILY_LOOKUP_ENCODINGS))
        )
    return normalized


def resolve_exact_power_pole_shell_distance_encoding() -> str:
    raw_value = os.environ.get(EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_ENV)
    normalized = (
        EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_ELEMENT
        if raw_value is None or not str(raw_value).strip()
        else str(raw_value).strip().lower()
    )
    if normalized not in EXACT_POWER_POLE_SHELL_DISTANCE_ENCODINGS:
        raise ValueError(
            f"Unsupported {EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_ENV}: {raw_value!r}; "
            "expected one of "
            + ", ".join(sorted(EXACT_POWER_POLE_SHELL_DISTANCE_ENCODINGS))
        )
    return normalized


def resolve_exact_power_coverage_witness_encoding() -> str:
    raw_value = os.environ.get(EXACT_POWER_COVERAGE_WITNESS_ENCODING_ENV)
    normalized = (
        EXACT_POWER_COVERAGE_WITNESS_ENCODING_ELEMENT
        if raw_value is None or not str(raw_value).strip()
        else str(raw_value).strip().lower()
    )
    if normalized not in EXACT_POWER_COVERAGE_WITNESS_ENCODINGS:
        raise ValueError(
            f"Unsupported {EXACT_POWER_COVERAGE_WITNESS_ENCODING_ENV}: {raw_value!r}; "
            "expected one of "
            + ", ".join(sorted(EXACT_POWER_COVERAGE_WITNESS_ENCODINGS))
        )
    return normalized


def resolve_exact_power_coverage_witness_block_geometry() -> str:
    raw_value = os.environ.get(EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV)
    normalized = (
        EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_FINAL_TARGET
        if raw_value is None or not str(raw_value).strip()
        else str(raw_value).strip().lower()
    )
    if normalized not in EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRIES:
        raise ValueError(
            f"Unsupported {EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV}: "
            f"{raw_value!r}; expected one of "
            + ", ".join(sorted(EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRIES))
        )
    return normalized


def resolve_exact_power_coverage_witness_block_size() -> int:
    raw_value = os.environ.get(EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE_ENV)
    if raw_value is None or not str(raw_value).strip():
        return 128
    try:
        block_size = int(str(raw_value).strip())
    except ValueError as exc:
        raise ValueError(
            f"Unsupported {EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE_ENV}: "
            f"{raw_value!r}; expected an integer >= 2"
        ) from exc
    if block_size < 2:
        raise ValueError(
            f"Unsupported {EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE_ENV}: "
            f"{raw_value!r}; expected an integer >= 2"
        )
    return int(block_size)


def resolve_exact_power_coverage_witness_block_templates() -> Set[str]:
    raw_value = os.environ.get(EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES_ENV)
    if raw_value is None or not str(raw_value).strip():
        return set()
    tokens: Set[str] = set()
    for token in str(raw_value).replace(";", ",").split(","):
        normalized = str(token).strip()
        if normalized:
            tokens.add(normalized)
    return tokens


def resolve_exact_power_coverage_selected_interval_encoding() -> str:
    raw_value = os.environ.get(EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_ENV)
    normalized = (
        EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_BOUNDS
        if raw_value is None or not str(raw_value).strip()
        else str(raw_value).strip().lower()
    )
    if normalized not in EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODINGS:
        raise ValueError(
            f"Unsupported {EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_ENV}: "
            f"{raw_value!r}; expected one of "
            + ", ".join(sorted(EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODINGS))
        )
    return normalized


def family_shell_guard_shape(rows: Sequence[Sequence[int]]) -> Dict[str, Any]:
    row_set = {
        (int(row[0]), int(row[1]))
        for row in list(rows)
        if isinstance(row, (list, tuple)) and len(row) == 2
    }
    if not row_set:
        return {"kind": "empty", "row_count": 0, "rows": []}
    if len(row_set) == 1:
        d_lo, d_hi = next(iter(row_set))
        return {"kind": "single", "row_count": 1, "d_lo": int(d_lo), "d_hi": int(d_hi)}
    d_los = sorted({int(row[0]) for row in row_set})
    d_his = sorted({int(row[1]) for row in row_set})
    rectangle = {
        (int(d_lo), int(d_hi))
        for d_lo in range(min(d_los), max(d_los) + 1)
        for d_hi in range(min(d_his), max(d_his) + 1)
    }
    if row_set == rectangle:
        return {
            "kind": "rectangle",
            "row_count": int(len(row_set)),
            "d_lo_min": int(min(d_los)),
            "d_lo_max": int(max(d_los)),
            "d_hi_min": int(min(d_his)),
            "d_hi_max": int(max(d_his)),
        }
    upper_triangle = {
        (int(d_lo), int(d_hi))
        for d_lo in range(min(d_los), max(d_los) + 1)
        for d_hi in range(min(d_his), max(d_his) + 1)
        if int(d_lo) <= int(d_hi)
    }
    if row_set == upper_triangle:
        return {
            "kind": "upper_triangle",
            "row_count": int(len(row_set)),
            "d_lo_min": int(min(d_los)),
            "d_lo_max": int(max(d_los)),
            "d_hi_min": int(min(d_his)),
            "d_hi_max": int(max(d_his)),
        }
    return {
        "kind": "fallback_table",
        "row_count": int(len(row_set)),
        "rows": [[int(row[0]), int(row[1])] for row in sorted(row_set)],
    }


def add_family_shell_guard_constraints(
    model: cp_model.CpModel,
    *,
    lit_var: Any,
    d_lo_var: Any,
    d_hi_var: Any,
    rows: Sequence[Sequence[int]],
) -> Dict[str, Any]:
    shape = family_shell_guard_shape(rows)
    kind = str(shape.get("kind"))
    linear_constraints = 0
    fallback_table_constraints = 0
    fallback_table_rows = 0
    if kind == "single":
        model.Add(d_lo_var == int(shape["d_lo"])).OnlyEnforceIf(lit_var)
        model.Add(d_hi_var == int(shape["d_hi"])).OnlyEnforceIf(lit_var)
        linear_constraints += 2
    elif kind == "rectangle":
        linear_constraints += _add_family_shell_guard_bounds(
            model,
            lit_var=lit_var,
            d_lo_var=d_lo_var,
            d_hi_var=d_hi_var,
            d_lo_min=int(shape["d_lo_min"]),
            d_lo_max=int(shape["d_lo_max"]),
            d_hi_min=int(shape["d_hi_min"]),
            d_hi_max=int(shape["d_hi_max"]),
        )
    elif kind == "upper_triangle":
        linear_constraints += _add_family_shell_guard_bounds(
            model,
            lit_var=lit_var,
            d_lo_var=d_lo_var,
            d_hi_var=d_hi_var,
            d_lo_min=int(shape["d_lo_min"]),
            d_lo_max=int(shape["d_lo_max"]),
            d_hi_min=int(shape["d_hi_min"]),
            d_hi_max=int(shape["d_hi_max"]),
        )
        model.Add(d_lo_var <= d_hi_var).OnlyEnforceIf(lit_var)
        linear_constraints += 1
    elif kind == "fallback_table":
        fallback_rows = [
            [int(row[0]), int(row[1])]
            for row in list(shape.get("rows", []))
            if isinstance(row, (list, tuple)) and len(row) == 2
        ]
        if fallback_rows:
            model.AddAllowedAssignments([d_lo_var, d_hi_var], fallback_rows).OnlyEnforceIf(
                lit_var
            )
            fallback_table_constraints += 1
            fallback_table_rows += int(len(fallback_rows))
    return {
        "shape": shape,
        "linear_constraint_count": int(linear_constraints),
        "fallback_table_constraint_count": int(fallback_table_constraints),
        "fallback_table_row_count": int(fallback_table_rows),
    }


def _add_family_shell_guard_bounds(
    model: cp_model.CpModel,
    *,
    lit_var: Any,
    d_lo_var: Any,
    d_hi_var: Any,
    d_lo_min: int,
    d_lo_max: int,
    d_hi_min: int,
    d_hi_max: int,
) -> int:
    model.Add(d_lo_var >= int(d_lo_min)).OnlyEnforceIf(lit_var)
    model.Add(d_lo_var <= int(d_lo_max)).OnlyEnforceIf(lit_var)
    model.Add(d_hi_var >= int(d_hi_min)).OnlyEnforceIf(lit_var)
    model.Add(d_hi_var <= int(d_hi_max)).OnlyEnforceIf(lit_var)
    return 4


@dataclass(frozen=True)
class ModeRectDomain:
    mode_id: int
    orientation: str
    port_mode: str
    footprint_key: str
    footprint_bounds: Tuple[int, int, int, int]
    footprint_width: int
    footprint_height: int
    x_min: int
    x_max: int
    y_min: int
    y_max: int
    pose_count: int


@dataclass(frozen=True)
class SignatureRegion:
    mode_id: int
    x_min: int
    x_max: int
    y_min: int
    y_max: int


@dataclass
class CoordinateSlotSpec:
    key: str
    template: str
    slot_kind: str
    slot_index: int
    dims: Tuple[int, int]
    candidate_pose_count: int
    tuple_to_pose_idx: Mapping[PoseTuple, int]
    mode_rect_domains: Mapping[int, ModeRectDomain]
    allowed_tuples: Tuple[PoseTuple, ...] = field(default_factory=tuple)
    use_domain_table: bool = False
    signature_id_to_bucket_id: Mapping[int, str] = field(default_factory=dict)
    family_id_to_family_name: Mapping[int, str] = field(default_factory=dict)
    active: Optional[cp_model.IntVar] = None
    x: Optional[cp_model.IntVar] = None
    y: Optional[cp_model.IntVar] = None
    mode: Optional[cp_model.IntVar] = None
    order_key: Optional[cp_model.IntVar] = None
    signature: Optional[cp_model.IntVar] = None
    family: Optional[cp_model.IntVar] = None
    footprint_dx_min: Optional[cp_model.IntVar] = None
    footprint_dy_min: Optional[cp_model.IntVar] = None
    footprint_width: Optional[cp_model.IntVar] = None
    footprint_height: Optional[cp_model.IntVar] = None
    footprint_x_start: Optional[cp_model.IntVar] = None
    footprint_y_start: Optional[cp_model.IntVar] = None
    footprint_x_end: Optional[cp_model.IntVar] = None
    footprint_y_end: Optional[cp_model.IntVar] = None
    x_interval: Optional[Any] = None
    y_interval: Optional[Any] = None


class CoordinateExactMasterDelegate:
    def __init__(self, owner: Any):
        self.owner = owner
        self.model = owner.model
        self.grid_w = int(owner.grid_w)
        self.grid_h = int(owner.grid_h)
        self.master_representation = "coordinate_exact_v2"

        self._template_mode_tokens: Dict[str, List[ModeToken]] = {}
        self._template_mode_id_by_token: Dict[str, Dict[ModeToken, int]] = {}
        self._template_pose_idx_by_tuple: Dict[str, Dict[PoseTuple, int]] = {}
        self._template_pose_tuple_by_idx: Dict[str, Dict[int, PoseTuple]] = {}
        self._template_signature_bucket_id_by_int: Dict[str, Dict[int, str]] = {}
        self._template_mode_literals: Dict[str, int] = {}
        self._template_full_mode_rect_domains: Dict[str, Dict[int, ModeRectDomain]] = {}
        self._template_uses_domain_table: Dict[str, bool] = {}

        # M3-2 (P1.3): content-addressed reuse caches for Benders-cut presence
        # literals. Pre-M3 every add_benders_cut call rebuilt the reified
        # equality / match / presence literals from scratch with a per-cut tag
        # baked into their identity — the M1 sizing spike measured that as the
        # dominant super-linear cost (66→252 ms/cut, ~0.9 MB RSS/cut, and the
        # model-proto bloat behind the 232 s solve-side transfer overhead at
        # 10K cuts). Identity is now purely content-addressed: same
        # (variable, value) / (slot, pose) / (slot-set, pose) → same literal.
        # Lifetime is tied to this delegate's model; caches are never
        # invalidated because the cached constraints are state-independent
        # definitions (reified equalities over build-time variable bindings).
        self._eq_literal_cache: Dict[Tuple[int, int], cp_model.IntVar] = {}
        self._slot_pose_match_cache: Dict[
            Tuple[str, Tuple[int, int, int]], Optional[cp_model.IntVar]
        ] = {}
        self._pose_present_cache: Dict[
            Tuple[Tuple[str, ...], Tuple[int, int, int]], Optional[cp_model.IntVar]
        ] = {}

        self._mandatory_group_mode_rect_domains: Dict[str, Dict[int, ModeRectDomain]] = {}
        self._required_optional_mode_rect_domains: Dict[str, Dict[int, ModeRectDomain]] = {}
        self._mandatory_group_bucket_regions: Dict[str, Dict[str, List[SignatureRegion]]] = {}
        self._required_optional_bucket_regions: Dict[str, Dict[str, List[SignatureRegion]]] = {}
        self._residual_optional_signature_buckets: Dict[str, List[Dict[str, Any]]] = {}
        self._residual_optional_bucket_regions: Dict[str, Dict[str, List[SignatureRegion]]] = {}
        self._mandatory_group_bucket_pose_indices: Dict[str, Dict[str, Tuple[int, ...]]] = {}
        self._required_optional_bucket_pose_indices: Dict[str, Dict[str, Tuple[int, ...]]] = {}
        self._residual_optional_bucket_pose_indices: Dict[str, Dict[str, Tuple[int, ...]]] = {}
        self._mandatory_group_bucket_pose_counts: Dict[str, Dict[str, int]] = {}
        self._required_optional_bucket_pose_counts: Dict[str, Dict[str, int]] = {}
        self._residual_optional_bucket_pose_counts: Dict[str, Dict[str, int]] = {}
        self._mandatory_group_bucket_count_upper_bounds: Dict[str, Dict[str, int]] = {}
        self._required_optional_bucket_count_upper_bounds: Dict[str, Dict[str, int]] = {}
        self._residual_optional_bucket_count_upper_bounds: Dict[str, Dict[str, int]] = {}
        self._mandatory_group_pose_counts: Dict[str, int] = {}
        self._required_optional_pose_counts: Dict[str, int] = {}
        self._mandatory_group_uses_domain_table: Dict[str, bool] = {}
        self._required_optional_uses_domain_table: Dict[str, bool] = {}
        self._mandatory_group_uses_signature_table: Dict[str, bool] = {}
        self._required_optional_uses_signature_table: Dict[str, bool] = {}
        self._residual_optional_uses_signature_table: Dict[str, bool] = {}

        self._power_pole_family_name_by_int: Dict[int, str] = {}
        self._power_pole_family_coefficients: Dict[str, Dict[str, int]] = {}
        self._power_pole_family_id_by_pose_idx: Dict[int, int] = {}
        self._power_pole_family_pose_counts: Dict[str, int] = {}
        self._power_pole_family_order: List[str] = []
        self._power_pole_use_shell_lookup = True
        self._power_pole_family_tuple_rows: List[Tuple[int, int, int, int]] = []
        self._power_pole_shell_lookup_rows: List[Tuple[int, int, int]] = []
        self._power_pole_shell_lookup_pairs: List[Dict[str, Any]] = []
        self._power_family_lookup_encoding = resolve_exact_power_family_lookup_encoding()
        self._power_pole_shell_distance_encoding = (
            resolve_exact_power_pole_shell_distance_encoding()
        )
        self._power_coverage_witness_encoding = (
            resolve_exact_power_coverage_witness_encoding()
        )
        self._power_coverage_witness_block_geometry = (
            resolve_exact_power_coverage_witness_block_geometry()
        )
        self._power_coverage_witness_block_size = (
            resolve_exact_power_coverage_witness_block_size()
        )
        self._power_coverage_witness_block_templates = (
            resolve_exact_power_coverage_witness_block_templates()
        )
        self._power_coverage_selected_interval_encoding = (
            resolve_exact_power_coverage_selected_interval_encoding()
        )
        self._power_family_lookup_encoding_stats: Dict[str, Any] = {
            "encoding": self._power_family_lookup_encoding,
            "slot_count": 0,
            "table_constraint_count": 0,
            "linear_guard_constraint_count": 0,
            "fallback_table_constraint_count": 0,
            "fallback_table_row_count": 0,
            "family_lit_count": 0,
            "shape_counts": {},
        }
        self._power_pole_shell_distance_encoding_stats: Dict[str, Any] = {
            "encoding": self._power_pole_shell_distance_encoding,
            "slot_count": 0,
            "element_constraint_count": 0,
            "linear_minmax_constraint_count": 0,
        }
        self._power_coverage_witness_encoding_stats: Dict[str, Any] = {
            "encoding": self._power_coverage_witness_encoding,
            "block_geometry_mode": self._power_coverage_witness_block_geometry,
            "block_size": int(self._power_coverage_witness_block_size),
            "block_templates": sorted(self._power_coverage_witness_block_templates),
            "selected_interval_encoding": self._power_coverage_selected_interval_encoding,
            "selected_interval_bounds_constraint_count": 0,
            "selected_interval_delta_var_count": 0,
            "selected_interval_delta_constraint_count": 0,
            "wide_witness_count": 0,
            "wide_element_constraint_count": 0,
            "wide_element_target_channel_count": 0,
            "block_witness_count": 0,
            "block_element_constraint_count": 0,
            "block_final_join_element_constraint_count": 0,
            "block_intermediate_target_channel_count": 0,
            "block_selected_literal_count": 0,
            "block_selected_channel_constraint_count": 0,
            "block_selected_geometry_constraint_count": 0,
            "local_selected_literal_count": 0,
            "local_selected_channel_constraint_count": 0,
            "block_active_guard_clause_count": 0,
            "grouped_xy_target_channel_count": 0,
            "grouped_xy_element_constraint_count": 0,
            "grouped_xy_padded_index_constraint_count": 0,
            "grouped_xy_selected_geometry_constraint_count": 0,
            "joined_xy_target_channel_count": 0,
            "joined_xy_element_constraint_count": 0,
            "joined_xy_selected_geometry_constraint_count": 0,
            "block_selector_count": 0,
            "local_selector_count": 0,
            "final_target_channel_count": 0,
            "padded_block_value_count": 0,
            "template_counts": {},
        }
        self._power_pole_slot_upper_bound = 0
        self._power_capacity_cache_stats: Dict[str, Any] = {
            "scope": "process_memory",
            "signature_hits": 0,
            "signature_misses": 0,
            "signature_count": 0,
            "pole_template_evaluations": 0,
            "signature_class_count": 0,
            "signature_class_evaluations": 0,
            "raw_pole_evaluations": 0,
            "compact_signature_class_count": 0,
            "compact_signature_class_evaluations": 0,
            "compact_signature_hits": 0,
            "compact_signature_misses": 0,
            "normalized_rect_signature_count": 0,
            "normalized_rect_cache_hits": 0,
            "normalized_rect_cache_misses": 0,
            "legacy_signature_materializations": 0,
            "supported_by_pole_materializations": 0,
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
            "coefficient_source": "exact_compact_rect_cpsat_v14",
            "shell_pair_count": 0,
        }
        self._power_capacity_coeff_stats: Dict[str, Any] = {}

        self.mandatory_slots: Dict[str, List[CoordinateSlotSpec]] = {}
        self.required_optional_slots: Dict[str, List[CoordinateSlotSpec]] = {}
        self.residual_optional_slots: Dict[str, List[CoordinateSlotSpec]] = {}

        self.mandatory_signature_count_vars: Dict[str, Dict[str, cp_model.IntVar]] = {}
        self.required_optional_signature_count_vars: Dict[str, Dict[str, cp_model.IntVar]] = {}
        self.residual_optional_signature_count_vars: Dict[str, Dict[str, cp_model.IntVar]] = {}
        self.power_pole_family_count_vars: Dict[str, cp_model.IntVar] = {}

        self._mandatory_signature_membership: Dict[str, Dict[str, List[cp_model.IntVar]]] = {}
        self._required_optional_signature_membership: Dict[str, Dict[str, List[cp_model.IntVar]]] = {}
        self._residual_optional_signature_membership: Dict[str, Dict[str, List[cp_model.IntVar]]] = {}
        self._power_pole_family_membership: Dict[str, List[cp_model.IntVar]] = {}

        self._core_x_intervals: List[Any] = []
        self._core_y_intervals: List[Any] = []
        self._ghost_x_intervals: List[Any] = []
        self._ghost_y_intervals: List[Any] = []
        self._ghost_anchor_power_capacity_screen_stats: Dict[str, Any] = {}
        self._coordinate_symmetry_stats: Dict[str, Any] = {
            "enabled": bool(getattr(owner, "enable_symmetry_breaking", True)),
            "mandatory_signature_monotonic_constraints": 0,
            "required_optional_signature_monotonic_constraints": 0,
            "residual_optional_signature_monotonic_constraints": 0,
            "mandatory_signature_monotonic_skipped_incompatible_order": 0,
            "required_optional_signature_monotonic_skipped_incompatible_order": 0,
            "residual_optional_signature_monotonic_skipped_incompatible_order": 0,
            "slot_order_key_monotonic_constraints": 0,
            "power_pole_family_order_constraints": 0,
        }
        self._slot_binding: Dict[str, Dict[str, int]] = {}
        self._interval_binding: Dict[str, Tuple[int, int]] = {}
        self._domain_table_row_count = 0

        self._prepare_template_domains()
        self._prepare_signature_maps()
        self._prepare_power_pole_families()
        self._prepare_slot_specs()

    def _pose_relative_occupied_cells(
        self,
        pose: Mapping[str, Any],
    ) -> Set[Tuple[int, int]]:
        anchor = dict(pose.get("anchor", {}))
        anchor_x = int(anchor.get("x", 0))
        anchor_y = int(anchor.get("y", 0))
        relative_cells: Set[Tuple[int, int]] = set()
        for cell in pose.get("occupied_cells", []) or []:
            if isinstance(cell, Mapping):
                cell_x, cell_y = int(cell.get("x", 0)), int(cell.get("y", 0))
            else:
                cell_x, cell_y = int(cell[0]), int(cell[1])
            relative_cells.add((int(cell_x - anchor_x), int(cell_y - anchor_y)))
        return relative_cells

    def _pose_footprint_bounds_from_pose(
        self,
        pose: Mapping[str, Any],
    ) -> Optional[Tuple[int, int, int, int]]:
        relative_cells = self._pose_relative_occupied_cells(pose)
        if not relative_cells:
            return None
        xs = sorted({int(x_val) for x_val, _ in relative_cells})
        ys = sorted({int(y_val) for _, y_val in relative_cells})
        return int(min(xs)), int(max(xs)), int(min(ys)), int(max(ys))

    def _pose_footprint_key(self, pose: Mapping[str, Any]) -> str:
        relative_cells = sorted(self._pose_relative_occupied_cells(pose))
        if not relative_cells:
            return "footprint::missing"
        bounds = self._pose_footprint_bounds_from_pose(pose)
        bounds_token = "missing" if bounds is None else ":".join(str(int(v)) for v in bounds)
        cell_token = ";".join(f"{int(x)}:{int(y)}" for x, y in relative_cells)
        return f"footprint::{bounds_token}::{cell_token}"

    def _pose_mode_token(self, pose: Mapping[str, Any]) -> ModeToken:
        params = dict(pose.get("pose_params", {}))
        return (
            str(params.get("orientation", "")),
            str(params.get("port_mode", "")),
            self._pose_footprint_key(pose),
        )

    def _rect_points(
        self,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
    ) -> Set[Tuple[int, int]]:
        if x_min > x_max or y_min > y_max:
            return set()
        return {
            (int(x_val), int(y_val))
            for x_val in range(int(x_min), int(x_max) + 1)
            for y_val in range(int(y_min), int(y_max) + 1)
        }

    def _is_rectangular_set(self, cells: Set[Tuple[int, int]]) -> bool:
        if not cells:
            return False
        xs = sorted({int(x_val) for x_val, _ in cells})
        ys = sorted({int(y_val) for _, y_val in cells})
        return cells == self._rect_points(min(xs), max(xs), min(ys), max(ys))

    def _bounding_region(self, mode_id: int, cells: Set[Tuple[int, int]]) -> SignatureRegion:
        xs = sorted({int(x_val) for x_val, _ in cells})
        ys = sorted({int(y_val) for _, y_val in cells})
        return SignatureRegion(
            mode_id=int(mode_id),
            x_min=int(min(xs)),
            x_max=int(max(xs)),
            y_min=int(min(ys)),
            y_max=int(max(ys)),
        )

    def _pose_has_template_rect_footprint(
        self,
        tpl: str,
        pose_idx: int,
        dims: Tuple[int, int],
    ) -> bool:
        pool = self.owner.facility_pools.get(str(tpl), [])
        if int(pose_idx) < 0 or int(pose_idx) >= len(pool):
            return False
        pose = pool[int(pose_idx)]
        anchor = dict(pose.get("anchor", {}))
        anchor_x = int(anchor.get("x", 0))
        anchor_y = int(anchor.get("y", 0))
        width, height = int(dims[0]), int(dims[1])
        if width <= 0 or height <= 0:
            return False
        expected = {
            (anchor_x + dx, anchor_y + dy)
            for dx in range(width)
            for dy in range(height)
        }
        actual: Set[Tuple[int, int]] = set()
        for cell in pose.get("occupied_cells", []) or []:
            if isinstance(cell, Mapping):
                actual.add((int(cell.get("x", 0)), int(cell.get("y", 0))))
            else:
                actual.add((int(cell[0]), int(cell[1])))
        return actual == expected

    def _pose_rectangular_footprint_bounds(
        self,
        tpl: str,
        pose_idx: int,
    ) -> Optional[Tuple[int, int, int, int]]:
        pool = self.owner.facility_pools.get(str(tpl), [])
        if int(pose_idx) < 0 or int(pose_idx) >= len(pool):
            return None
        pose = pool[int(pose_idx)]
        relative_cells = self._pose_relative_occupied_cells(pose)
        if not relative_cells:
            return None
        xs = sorted({int(x_val) for x_val, _ in relative_cells})
        ys = sorted({int(y_val) for _, y_val in relative_cells})
        min_dx, max_dx = int(min(xs)), int(max(xs))
        min_dy, max_dy = int(min(ys)), int(max(ys))
        expected = self._rect_points(min_dx, max_dx, min_dy, max_dy)
        if relative_cells != expected:
            return None
        return min_dx, max_dx, min_dy, max_dy

    def _pose_template_footprint_support_gap(
        self,
        tpl: str,
        pose_idx: int,
    ) -> Dict[str, Any]:
        pool = self.owner.facility_pools.get(str(tpl), [])
        if int(pose_idx) < 0 or int(pose_idx) >= len(pool):
            return {
                "reason": "missing_pose_occupied_cells",
                "occupied_cell_count": 0,
                "footprint_bounds_when_available": None,
            }
        pose = pool[int(pose_idx)]
        if "occupied_cells" not in pose or pose.get("occupied_cells") is None:
            return {
                "reason": "missing_pose_occupied_cells",
                "occupied_cell_count": 0,
                "footprint_bounds_when_available": None,
            }
        anchor = dict(pose.get("anchor", {}))
        anchor_x = int(anchor.get("x", 0))
        anchor_y = int(anchor.get("y", 0))
        relative_cells: Set[Tuple[int, int]] = set()
        for cell in pose.get("occupied_cells", []) or []:
            if isinstance(cell, Mapping):
                cell_x, cell_y = int(cell.get("x", 0)), int(cell.get("y", 0))
            else:
                cell_x, cell_y = int(cell[0]), int(cell[1])
            relative_cells.add((int(cell_x - anchor_x), int(cell_y - anchor_y)))
        if not relative_cells:
            return {
                "reason": "empty_pose_occupied_cells",
                "occupied_cell_count": 0,
                "footprint_bounds_when_available": None,
            }
        xs = sorted({int(x_val) for x_val, _ in relative_cells})
        ys = sorted({int(y_val) for _, y_val in relative_cells})
        bounds = (int(min(xs)), int(max(xs)), int(min(ys)), int(max(ys)))
        expected = self._rect_points(*bounds)
        if relative_cells != expected:
            return {
                "reason": "non_rectangular_occupied_cells",
                "occupied_cell_count": int(len(relative_cells)),
                "footprint_bounds_when_available": bounds,
            }
        return {
            "reason": "region_counting_guard_rejected",
            "occupied_cell_count": int(len(relative_cells)),
            "footprint_bounds_when_available": bounds,
        }

    def _signature_regions_non_overlapping(
        self,
        regions: Sequence[SignatureRegion],
    ) -> bool:
        by_mode: DefaultDict[int, List[SignatureRegion]] = defaultdict(list)
        for region in regions:
            by_mode[int(region.mode_id)].append(region)
        for mode_regions in by_mode.values():
            for left_idx, left in enumerate(mode_regions):
                for right in mode_regions[left_idx + 1 :]:
                    x_overlap = int(left.x_min) <= int(right.x_max) and int(
                        right.x_min
                    ) <= int(left.x_max)
                    y_overlap = int(left.y_min) <= int(right.y_max) and int(
                        right.y_min
                    ) <= int(left.y_max)
                    if x_overlap and y_overlap:
                        return False
        return True

    def _mandatory_region_counting_payload(
        self,
        *,
        group_id: str,
        tpl: str,
        pose_to_bucket: Mapping[int, str],
        template_footprint_support_enabled: bool = False,
        support_gap_instrumentation_enabled: bool = False,
        payload_footprint_stability_support_enabled: bool = False,
        residual_overlay_instrumentation_enabled: bool = False,
    ) -> Dict[str, Any]:
        def _gap(
            reason: str,
            *,
            bucket_id: str = "__all__",
            occupied_cell_count: int = 0,
            footprint_bounds_when_available: Optional[Tuple[int, int, int, int]] = None,
        ) -> Dict[str, Any]:
            return {
                "reason": str(reason),
                "bucket_id": str(bucket_id),
                "pose_count": int(len(pose_to_bucket)),
                "occupied_cell_count": int(occupied_cell_count),
                "footprint_bounds_when_available": list(footprint_bounds_when_available)
                if footprint_bounds_when_available is not None
                else None,
            }

        payload_timing = {
            "payload_footprint_cohort_build_seconds": 0.0,
            "payload_bucket_region_rebuild_seconds": 0.0,
            "payload_compactness_guard_seconds": 0.0,
        }

        def _record_payload_timing(phase: str, started: float) -> None:
            if not residual_overlay_instrumentation_enabled:
                return
            payload_timing[phase] = float(
                payload_timing.get(phase, 0.0)
                + max(0.0, time.perf_counter() - started)
            )

        def _with_payload_timing(result: Dict[str, Any]) -> Dict[str, Any]:
            if residual_overlay_instrumentation_enabled:
                result["residual_overlay_payload_timing"] = {
                    key: float(value) for key, value in sorted(payload_timing.items())
                }
            return result

        def _unsupported(reason: str, gap: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            result: Dict[str, Any] = {"supported": False, "reason": str(reason)}
            if support_gap_instrumentation_enabled and gap is not None:
                result["template_footprint_support_gap"] = gap
            return _with_payload_timing(result)

        bucket_regions = self._mandatory_group_bucket_regions.get(str(group_id), {})
        if not bucket_regions:
            return _unsupported(
                "missing_bucket_regions",
                _gap("bucket_region_metadata_missing"),
            )
        dims_payload = dict(self.owner.templates[str(tpl)]["dimensions"])
        dims = (int(dims_payload.get("w", 0)), int(dims_payload.get("h", 0)))
        if dims[0] <= 0 or dims[1] <= 0:
            return _unsupported(
                "invalid_template_dimensions",
                _gap("missing_template_or_group_metadata"),
            )

        bucket_pose_indices = self._mandatory_group_bucket_pose_indices.get(
            str(group_id),
            {},
        )
        pose_bucket_ids = {str(bucket_id) for bucket_id in set(pose_to_bucket.values())}
        if pose_bucket_ids != {str(bucket_id) for bucket_id in bucket_regions}:
            return _unsupported(
                "bucket_region_coverage_mismatch",
                _gap("bucket_region_metadata_missing"),
            )

        footprint_bounds: Optional[Tuple[int, int, int, int]] = None
        footprint_bounds_seen: Set[Tuple[int, int, int, int]] = set()
        pose_indices_by_bounds_by_bucket: DefaultDict[
            str, DefaultDict[Tuple[int, int, int, int], List[int]]
        ] = defaultdict(lambda: defaultdict(list))
        template_footprint_support_used = False
        for bucket_id in sorted(pose_bucket_ids):
            regions = list(bucket_regions.get(str(bucket_id), []))
            if not regions:
                return _unsupported(
                    "empty_bucket_region",
                    _gap("bucket_region_metadata_missing", bucket_id=str(bucket_id)),
                )
            compactness_started = time.perf_counter()
            regions_non_overlapping = self._signature_regions_non_overlapping(regions)
            _record_payload_timing(
                "payload_compactness_guard_seconds",
                compactness_started,
            )
            if not regions_non_overlapping:
                return _unsupported(
                    "overlapping_bucket_regions",
                    _gap("same_bucket_regions_overlap", bucket_id=str(bucket_id)),
                )
            cohort_started = time.perf_counter()
            for pose_idx in bucket_pose_indices.get(str(bucket_id), ()):
                if int(pose_idx) not in pose_to_bucket:
                    _record_payload_timing(
                        "payload_footprint_cohort_build_seconds",
                        cohort_started,
                    )
                    return _unsupported(
                        "bucket_pose_map_mismatch",
                        _gap(
                            "bucket_region_metadata_missing",
                            bucket_id=str(bucket_id),
                        ),
                    )
                if self._pose_has_template_rect_footprint(str(tpl), int(pose_idx), dims):
                    current_bounds = (0, int(dims[0]) - 1, 0, int(dims[1]) - 1)
                elif template_footprint_support_enabled:
                    supported_bounds = self._pose_rectangular_footprint_bounds(
                        str(tpl),
                        int(pose_idx),
                    )
                    if supported_bounds is None:
                        pose_gap = self._pose_template_footprint_support_gap(
                            str(tpl),
                            int(pose_idx),
                        )
                        _record_payload_timing(
                            "payload_footprint_cohort_build_seconds",
                            cohort_started,
                        )
                        return _with_payload_timing({
                            "supported": False,
                            "reason": "unsupported_pose_footprint",
                            **(
                                {
                                    "template_footprint_support_gap": {
                                        **pose_gap,
                                        "bucket_id": str(bucket_id),
                                        "pose_count": int(len(pose_to_bucket)),
                                    }
                                }
                                if support_gap_instrumentation_enabled
                                else {}
                            ),
                        })
                    current_bounds = supported_bounds
                    template_footprint_support_used = True
                else:
                    return _unsupported(
                        "unsupported_pose_footprint",
                        _gap(
                            "legacy_scan_required_other",
                            bucket_id=str(bucket_id),
                        ),
                    )
                if footprint_bounds is None:
                    footprint_bounds = current_bounds
                elif footprint_bounds != current_bounds:
                    gap = _gap(
                        "unstable_footprint_bounds_within_payload",
                        bucket_id=str(bucket_id),
                        footprint_bounds_when_available=current_bounds,
                    )
                    if not payload_footprint_stability_support_enabled:
                        return _unsupported(
                            "unsupported_pose_footprint",
                            gap,
                        )
                footprint_bounds_seen.add(current_bounds)
                pose_indices_by_bounds_by_bucket[str(bucket_id)][
                    current_bounds
                ].append(int(pose_idx))
            _record_payload_timing(
                "payload_footprint_cohort_build_seconds",
                cohort_started,
            )

        if len(footprint_bounds_seen) > 1:
            rebuild_started = time.perf_counter()
            mode_rect_domains = self._mandatory_group_mode_rect_domains.get(
                str(group_id),
                {},
            )
            if not mode_rect_domains:
                return _unsupported(
                    "bucket_region_coverage_mismatch",
                    _gap("bucket_region_metadata_missing"),
                )
            footprint_cohorts: List[Dict[str, Any]] = []
            for current_bounds in sorted(footprint_bounds_seen):
                cohort_bucket_regions: Dict[str, Tuple[SignatureRegion, ...]] = {}
                for bucket_id in sorted(pose_bucket_ids):
                    cohort_pose_indices = list(
                        pose_indices_by_bounds_by_bucket[str(bucket_id)].get(
                            current_bounds,
                            (),
                        )
                    )
                    if not cohort_pose_indices:
                        continue
                    cells_by_mode: DefaultDict[int, Set[Tuple[int, int]]] = defaultdict(set)
                    for pose_idx in cohort_pose_indices:
                        pose_tuple = self._template_pose_tuple_by_idx[str(tpl)].get(
                            int(pose_idx)
                        )
                        if pose_tuple is None:
                            return _unsupported(
                                "bucket_pose_map_mismatch",
                                _gap(
                                    "bucket_region_metadata_missing",
                                    bucket_id=str(bucket_id),
                                    footprint_bounds_when_available=current_bounds,
                                ),
                            )
                        x_val, y_val, mode_id = pose_tuple
                        if int(mode_id) not in mode_rect_domains:
                            return _unsupported(
                                "bucket_region_coverage_mismatch",
                                _gap(
                                    "bucket_region_metadata_missing",
                                    bucket_id=str(bucket_id),
                                    footprint_bounds_when_available=current_bounds,
                                ),
                            )
                        cells_by_mode[int(mode_id)].add((int(x_val), int(y_val)))
                    regions: List[SignatureRegion] = []
                    for mode_id, bucket_cells in sorted(cells_by_mode.items()):
                        region_candidates = self._bucket_region_candidates_for_mode(
                            int(mode_id),
                            mode_rect_domains[int(mode_id)],
                            set(bucket_cells),
                        )
                        if region_candidates is None:
                            return _unsupported(
                                "unsupported_pose_footprint",
                                _gap(
                                    "region_counting_guard_rejected",
                                    bucket_id=str(bucket_id),
                                    footprint_bounds_when_available=current_bounds,
                                ),
                            )
                        regions.extend(region_candidates)
                    if not regions:
                        return _unsupported(
                            "empty_bucket_region",
                            _gap(
                                "bucket_region_metadata_missing",
                                bucket_id=str(bucket_id),
                                footprint_bounds_when_available=current_bounds,
                            ),
                        )
                    compactness_started = time.perf_counter()
                    regions_non_overlapping = self._signature_regions_non_overlapping(
                        regions
                    )
                    _record_payload_timing(
                        "payload_compactness_guard_seconds",
                        compactness_started,
                    )
                    if not regions_non_overlapping:
                        return _unsupported(
                            "overlapping_bucket_regions",
                            _gap(
                                "same_bucket_regions_overlap",
                                bucket_id=str(bucket_id),
                                footprint_bounds_when_available=current_bounds,
                            ),
                        )
                    cohort_bucket_regions[str(bucket_id)] = tuple(regions)
                if cohort_bucket_regions:
                    footprint_cohorts.append(
                        {
                            "footprint_bounds": tuple(int(value) for value in current_bounds),
                            "bucket_regions": cohort_bucket_regions,
                        }
                    )
            if not footprint_cohorts:
                return _unsupported(
                    "unsupported_pose_footprint",
                    _gap("region_counting_guard_rejected"),
                )
            _record_payload_timing(
                "payload_bucket_region_rebuild_seconds",
                rebuild_started,
            )
            return _with_payload_timing({
                "supported": True,
                "dims": dims,
                "footprint_cohorts": tuple(footprint_cohorts),
                "payload_footprint_stability_support_used": True,
                "payload_footprint_stability_cohort_count": int(len(footprint_cohorts)),
                "template_footprint_support_used": bool(template_footprint_support_used),
            })

        return _with_payload_timing({
            "supported": True,
            "dims": dims,
            "footprint_bounds": footprint_bounds
            if footprint_bounds is not None
            else (0, int(dims[0]) - 1, 0, int(dims[1]) - 1),
            "template_footprint_support_used": bool(template_footprint_support_used),
            "bucket_regions": {
                str(bucket_id): tuple(regions)
                for bucket_id, regions in sorted(bucket_regions.items())
            },
        })

    def _region_overlap_integer_area(
        self,
        region: SignatureRegion,
        x_min: int,
        x_max: int,
        y_min: int,
        y_max: int,
    ) -> int:
        ix_min = max(int(region.x_min), int(x_min))
        ix_max = min(int(region.x_max), int(x_max))
        iy_min = max(int(region.y_min), int(y_min))
        iy_max = min(int(region.y_max), int(y_max))
        if ix_min > ix_max or iy_min > iy_max:
            return 0
        return int((ix_max - ix_min + 1) * (iy_max - iy_min + 1))

    def _mandatory_region_blocked_counts_for_domain(
        self,
        domain: Mapping[str, Any],
        region_payload: Mapping[str, Any],
    ) -> Tuple[DefaultDict[str, int], Dict[str, int]]:
        anchor = dict(domain.get("anchor", {}))
        ghost_rect = self.owner.ghost_rect
        if not ghost_rect:
            return defaultdict(int), {
                "rectangles_evaluated": 0,
                "overlap_counts": 0,
                "counted_blocked_poses": 0,
                "payload_footprint_stability_cohorts": 0,
            }
        ghost_x = int(anchor.get("x", 0))
        ghost_y = int(anchor.get("y", 0))
        ghost_w, ghost_h = int(ghost_rect[0]), int(ghost_rect[1])
        blocked_counts: DefaultDict[str, int] = defaultdict(int)
        rectangles_evaluated = 0
        overlap_counts = 0
        footprint_cohorts = list(region_payload.get("footprint_cohorts") or [])
        if not footprint_cohorts:
            if "footprint_bounds" in region_payload:
                footprint_bounds = tuple(
                    int(value) for value in region_payload["footprint_bounds"]
                )
            else:
                tpl_w, tpl_h = tuple(int(value) for value in region_payload["dims"])
                footprint_bounds = (0, int(tpl_w) - 1, 0, int(tpl_h) - 1)
            footprint_cohorts = [
                {
                    "footprint_bounds": footprint_bounds,
                    "bucket_regions": region_payload["bucket_regions"],
                }
            ]
        for cohort in footprint_cohorts:
            min_dx, max_dx, min_dy, max_dy = tuple(
                int(value) for value in cohort["footprint_bounds"]
            )
            block_x_min = int(ghost_x - max_dx)
            block_x_max = int(ghost_x + ghost_w - 1 - min_dx)
            block_y_min = int(ghost_y - max_dy)
            block_y_max = int(ghost_y + ghost_h - 1 - min_dy)
            for bucket_id, regions in sorted(cohort["bucket_regions"].items()):
                for region in regions:
                    rectangles_evaluated += 1
                    count = self._region_overlap_integer_area(
                        region,
                        block_x_min,
                        block_x_max,
                        block_y_min,
                        block_y_max,
                    )
                    if count <= 0:
                        continue
                    overlap_counts += 1
                    blocked_counts[str(bucket_id)] += int(count)
        return blocked_counts, {
            "rectangles_evaluated": int(rectangles_evaluated),
            "overlap_counts": int(overlap_counts),
            "counted_blocked_poses": int(sum(blocked_counts.values())),
            "payload_footprint_stability_cohorts": int(
                len(region_payload.get("footprint_cohorts") or [])
            ),
        }

    def _build_mode_rect_domains_from_pose_indices(
        self,
        tpl: str,
        pose_indices: Iterable[int],
        *,
        label: str,
    ) -> Tuple[Dict[int, ModeRectDomain], bool]:
        cells_by_mode: DefaultDict[int, Set[Tuple[int, int]]] = defaultdict(set)
        footprint_bounds_by_mode: DefaultDict[int, Set[Tuple[int, int, int, int]]] = defaultdict(set)
        for pose_idx in pose_indices:
            pose_tuple = self._template_pose_tuple_by_idx[tpl].get(int(pose_idx))
            if pose_tuple is None:
                continue
            x_val, y_val, mode_id = pose_tuple
            cells_by_mode[int(mode_id)].add((int(x_val), int(y_val)))
            pool = self.owner.facility_pools.get(str(tpl), [])
            if int(pose_idx) < 0 or int(pose_idx) >= len(pool):
                raise ValueError(
                    f"Missing candidate pose for coordinate footprint domain: {label} {tpl}[{pose_idx}]"
                )
            footprint_bounds = self._pose_footprint_bounds_from_pose(pool[int(pose_idx)])
            if footprint_bounds is None:
                raise ValueError(
                    "Missing occupied_cells for coordinate footprint domain: "
                    f"{label} {tpl}[{pose_idx}]"
                )
            footprint_bounds_by_mode[int(mode_id)].add(
                tuple(int(value) for value in footprint_bounds)
            )

        mode_rect_domains: Dict[int, ModeRectDomain] = {}
        use_domain_table = False
        for mode_id, cells in sorted(cells_by_mode.items()):
            footprint_bounds_seen = footprint_bounds_by_mode.get(int(mode_id), set())
            if len(footprint_bounds_seen) != 1:
                raise ValueError(
                    "Coordinate mode footprint is not stable after footprint-token split: "
                    f"{label} tpl={tpl} mode={mode_id} bounds={sorted(footprint_bounds_seen)}"
                )
            footprint_bounds = next(iter(footprint_bounds_seen))
            min_dx, max_dx, min_dy, max_dy = tuple(int(value) for value in footprint_bounds)
            xs = sorted({int(x_val) for x_val, _ in cells})
            ys = sorted({int(y_val) for _, y_val in cells})
            if xs != list(range(min(xs), max(xs) + 1)) or ys != list(range(min(ys), max(ys) + 1)):
                use_domain_table = True
            full_rect = self._rect_points(min(xs), max(xs), min(ys), max(ys))
            if cells != full_rect:
                use_domain_table = True
            orientation, port_mode, footprint_key = self._template_mode_tokens[tpl][int(mode_id)]
            mode_rect_domains[int(mode_id)] = ModeRectDomain(
                mode_id=int(mode_id),
                orientation=str(orientation),
                port_mode=str(port_mode),
                footprint_key=str(footprint_key),
                footprint_bounds=(int(min_dx), int(max_dx), int(min_dy), int(max_dy)),
                footprint_width=int(max_dx - min_dx + 1),
                footprint_height=int(max_dy - min_dy + 1),
                x_min=int(min(xs)),
                x_max=int(max(xs)),
                y_min=int(min(ys)),
                y_max=int(max(ys)),
                pose_count=int(len(cells)),
            )
        return mode_rect_domains, bool(use_domain_table)

    def _exact_templates_for_coordinate_master(self) -> List[str]:
        pose_level_optional_templates = {"power_pole", "protocol_storage_box"}
        templates: Set[str] = {
            str(group["facility_type"]) for group in self.owner._mandatory_groups
        }
        templates.update(
            str(tpl)
            for tpl, count in self.owner._exact_required_pose_optional_counts.items()
            if int(count) > 0
        )
        templates.update(
            str(tpl)
            for tpl in pose_level_optional_templates
            if str(tpl) in self.owner.facility_pools
            and self.owner.facility_pools.get(str(tpl))
        )
        return sorted(
            str(tpl) for tpl in templates if str(tpl) in self.owner.facility_pools
        )

    def _residual_optional_slot_upper_bound(self, tpl: str) -> int:
        tpl = str(tpl)
        if tpl == "power_pole":
            return int(self._power_pole_slot_upper_bound)
        total_upper_bound = int(self.owner._certified_optional_slot_upper_bound(str(tpl)))
        fixed_required_count = int(
            self.owner._exact_required_pose_optional_counts.get(str(tpl), 0)
        )
        if fixed_required_count > 0:
            return int(max(0, total_upper_bound - fixed_required_count))
        return int(total_upper_bound)

    def _needs_residual_optional_slots_after_fixed_required(self, tpl: str) -> bool:
        tpl = str(tpl)
        fixed_required_count = int(
            self.owner._exact_required_pose_optional_counts.get(str(tpl), 0)
        )
        if fixed_required_count <= 0:
            return True
        if tpl == "protocol_storage_box":
            lower_bound = int(self.owner._required_protocol_storage_box_lower_bound())
            return bool(lower_bound > fixed_required_count)
        return False

    def _power_pole_family_count_upper_bound(self, family_name: str) -> int:
        family_name = str(family_name)
        family_size = int(self._power_pole_family_pose_counts.get(family_name, 0))
        slot_pool_upper_bound = int(len(self._all_power_pole_slots()))
        return int(min(family_size, slot_pool_upper_bound))

    def _prepare_template_domains(self) -> None:
        for tpl in self._exact_templates_for_coordinate_master():
            pool = list(self.owner.facility_pools.get(str(tpl), []))
            mode_tokens = sorted({self._pose_mode_token(pose) for pose in pool}) or [
                ("", "", "footprint::missing")
            ]
            mode_id_by_token = {token: idx for idx, token in enumerate(mode_tokens)}
            tuple_to_pose_idx: Dict[PoseTuple, int] = {}
            pose_tuple_by_idx: Dict[int, PoseTuple] = {}
            for pose_idx, pose in enumerate(pool):
                anchor = dict(pose.get("anchor", {}))
                pose_tuple = (
                    int(anchor.get("x", 0)),
                    int(anchor.get("y", 0)),
                    int(mode_id_by_token[self._pose_mode_token(pose)]),
                )
                if pose_tuple in tuple_to_pose_idx:
                    raise ValueError(f"Duplicate coordinate pose key for {tpl}: {pose_tuple}")
                tuple_to_pose_idx[pose_tuple] = int(pose_idx)
                pose_tuple_by_idx[int(pose_idx)] = pose_tuple
            self._template_mode_tokens[tpl] = mode_tokens
            self._template_mode_id_by_token[tpl] = mode_id_by_token
            self._template_pose_idx_by_tuple[tpl] = tuple_to_pose_idx
            self._template_pose_tuple_by_idx[tpl] = pose_tuple_by_idx
            self._template_mode_literals[tpl] = max(1, len(mode_tokens))
            domains, uses_domain_table = self._build_mode_rect_domains_from_pose_indices(
                tpl,
                range(len(pool)),
                label=f"template::{tpl}",
            )
            self._template_full_mode_rect_domains[tpl] = domains
            self._template_uses_domain_table[tpl] = bool(uses_domain_table)

    def _build_bucket_regions(
        self,
        tpl: str,
        bucket_defs: Sequence[Mapping[str, Any]],
        mode_rect_domains: Mapping[int, ModeRectDomain],
        allowed_pose_indices: Optional[Set[int]] = None,
    ) -> Dict[str, List[SignatureRegion]]:
        bucket_regions: Dict[str, List[SignatureRegion]] = {}
        self._template_signature_bucket_id_by_int.setdefault(tpl, {})
        expected_pose_indices: Set[int]
        if allowed_pose_indices is None:
            expected_pose_indices = set(range(len(self.owner.facility_pools.get(str(tpl), []))))
        else:
            expected_pose_indices = {int(pose_idx) for pose_idx in allowed_pose_indices}
        covered_pose_indices: Set[int] = set()
        for signature_idx, bucket in enumerate(bucket_defs):
            bucket_id = str(bucket["bucket_id"])
            self._template_signature_bucket_id_by_int[tpl][int(signature_idx)] = bucket_id
            cells_by_mode: DefaultDict[int, Set[Tuple[int, int]]] = defaultdict(set)
            for pose_idx in bucket.get("pose_indices", []):
                pose_idx = int(pose_idx)
                if allowed_pose_indices is not None and pose_idx not in allowed_pose_indices:
                    continue
                if pose_idx in covered_pose_indices:
                    raise ValueError(
                        f"Overlapping signature bucket coverage for {tpl}: pose_idx={pose_idx} "
                        f"appears in multiple buckets"
                    )
                covered_pose_indices.add(int(pose_idx))
                pose_tuple = self._template_pose_tuple_by_idx[tpl].get(int(pose_idx))
                if pose_tuple is None:
                    continue
                x_val, y_val, mode_id = pose_tuple
                if int(mode_id) not in mode_rect_domains:
                    continue
                cells_by_mode[int(mode_id)].add((int(x_val), int(y_val)))

            regions: List[SignatureRegion] = []
            for mode_id, domain in sorted(mode_rect_domains.items()):
                bucket_cells = cells_by_mode.get(int(mode_id), set())
                if not bucket_cells:
                    continue
                mode_regions = self._bucket_region_candidates_for_mode(
                    int(mode_id),
                    domain,
                    bucket_cells,
                )
                if mode_regions is None:
                    raise ValueError(
                        f"Unsupported compact signature geometry for {tpl} bucket={bucket_id} mode={mode_id}"
                    )
                regions.extend(mode_regions)
            bucket_regions[bucket_id] = regions
        missing_pose_indices = sorted(expected_pose_indices - covered_pose_indices)
        if missing_pose_indices:
            raise ValueError(
                f"Incomplete signature bucket coverage for {tpl}: "
                f"missing {len(missing_pose_indices)} pose(s), first={missing_pose_indices[:5]}"
            )
        return bucket_regions

    def _bucket_region_candidates_for_mode(
        self,
        mode_id: int,
        domain: ModeRectDomain,
        bucket_cells: Set[Tuple[int, int]],
    ) -> Optional[List[SignatureRegion]]:
        full_cells = self._rect_points(domain.x_min, domain.x_max, domain.y_min, domain.y_max)
        if bucket_cells == full_cells:
            return [self._bounding_region(mode_id, bucket_cells)]

        if self._is_rectangular_set(bucket_cells):
            return [self._bounding_region(mode_id, bucket_cells)]

        width = int(domain.x_max - domain.x_min + 1)
        height = int(domain.y_max - domain.y_min + 1)

        for thickness in range(1, (width // 2) + 1):
            left = self._rect_points(domain.x_min, domain.x_min + thickness - 1, domain.y_min, domain.y_max)
            right = self._rect_points(domain.x_max - thickness + 1, domain.x_max, domain.y_min, domain.y_max)
            if bucket_cells == left | right:
                return [
                    SignatureRegion(mode_id, domain.x_min, domain.x_min + thickness - 1, domain.y_min, domain.y_max),
                    SignatureRegion(mode_id, domain.x_max - thickness + 1, domain.x_max, domain.y_min, domain.y_max),
                ]

        for thickness in range(1, (height // 2) + 1):
            bottom = self._rect_points(domain.x_min, domain.x_max, domain.y_min, domain.y_min + thickness - 1)
            top = self._rect_points(domain.x_min, domain.x_max, domain.y_max - thickness + 1, domain.y_max)
            if bucket_cells == bottom | top:
                return [
                    SignatureRegion(mode_id, domain.x_min, domain.x_max, domain.y_min, domain.y_min + thickness - 1),
                    SignatureRegion(mode_id, domain.x_min, domain.x_max, domain.y_max - thickness + 1, domain.y_max),
                ]

        max_ring_thickness = max(0, min(width, height) // 2)
        for thickness in range(1, max_ring_thickness + 1):
            inner = self._rect_points(
                domain.x_min + thickness,
                domain.x_max - thickness,
                domain.y_min + thickness,
                domain.y_max - thickness,
            )
            ring = full_cells - inner
            if bucket_cells != ring:
                continue
            regions: List[SignatureRegion] = [
                SignatureRegion(mode_id, domain.x_min, domain.x_max, domain.y_min, domain.y_min + thickness - 1),
                SignatureRegion(mode_id, domain.x_min, domain.x_max, domain.y_max - thickness + 1, domain.y_max),
            ]
            if domain.y_min + thickness <= domain.y_max - thickness:
                regions.append(
                    SignatureRegion(
                        mode_id,
                        domain.x_min,
                        domain.x_min + thickness - 1,
                        domain.y_min + thickness,
                        domain.y_max - thickness,
                    )
                )
                regions.append(
                    SignatureRegion(
                        mode_id,
                        domain.x_max - thickness + 1,
                        domain.x_max,
                        domain.y_min + thickness,
                        domain.y_max - thickness,
                    )
                )
            return [region for region in regions if region.x_min <= region.x_max and region.y_min <= region.y_max]

        return None

    def _signature_domain_payload(
        self,
        tpl: str,
        pose_indices: Iterable[int],
        bucket_defs: Sequence[Mapping[str, Any]],
        *,
        label: str,
    ) -> Dict[str, Any]:
        cache_key = (str(tpl), frozenset(int(pose_idx) for pose_idx in pose_indices))
        cached = self.owner._signature_domain_payload_cache.get(cache_key)
        if cached is not None:
            self.owner._update_exact_precompute_profile(
                signature_bucket_cache_hits=int(self.owner._exact_precompute_profile["signature_bucket_cache_hits"]) + 1,
                signature_bucket_distinct_keys=int(len(self.owner._signature_domain_payload_cache)),
            )
            return {
                "mode_rect_domains": dict(cached["mode_rect_domains"]),
                "uses_domain_table": bool(cached["uses_domain_table"]),
                "pose_count": int(cached["pose_count"]),
                "bucket_regions": copy.deepcopy(cached["bucket_regions"]),
                "uses_signature_table": bool(cached["uses_signature_table"]),
            }

        self.owner._update_exact_precompute_profile(
            signature_bucket_cache_misses=int(self.owner._exact_precompute_profile["signature_bucket_cache_misses"]) + 1,
        )
        candidate_pose_indices = set(cache_key[1])
        mode_rect_domains, uses_domain_table = self._build_mode_rect_domains_from_pose_indices(
            str(tpl),
            candidate_pose_indices,
            label=label,
        )
        if uses_domain_table:
            bucket_regions: Dict[str, List[SignatureRegion]] = {}
            uses_signature_table = True
        else:
            bucket_regions = self._build_bucket_regions(
                str(tpl),
                bucket_defs,
                mode_rect_domains,
                allowed_pose_indices=candidate_pose_indices,
            )
            uses_signature_table = False
        payload = {
            "mode_rect_domains": dict(mode_rect_domains),
            "uses_domain_table": bool(uses_domain_table),
            "pose_count": int(sum(domain.pose_count for domain in mode_rect_domains.values())),
            "bucket_regions": copy.deepcopy(bucket_regions),
            "uses_signature_table": bool(uses_signature_table),
        }
        self.owner._signature_domain_payload_cache[cache_key] = payload
        self.owner._update_exact_precompute_profile(
            signature_bucket_distinct_keys=int(len(self.owner._signature_domain_payload_cache)),
        )
        return {
            "mode_rect_domains": dict(payload["mode_rect_domains"]),
            "uses_domain_table": bool(payload["uses_domain_table"]),
            "pose_count": int(payload["pose_count"]),
            "bucket_regions": copy.deepcopy(payload["bucket_regions"]),
            "uses_signature_table": bool(payload["uses_signature_table"]),
        }

    def _filtered_bucket_pose_index_map(
        self,
        bucket_defs: Sequence[Mapping[str, Any]],
        allowed_pose_indices: Iterable[int],
    ) -> Dict[str, Tuple[int, ...]]:
        allowed_pose_index_set = {int(pose_idx) for pose_idx in allowed_pose_indices}
        return {
            str(bucket["bucket_id"]): tuple(
                sorted(
                    int(pose_idx)
                    for pose_idx in bucket.get("pose_indices", [])
                    if int(pose_idx) in allowed_pose_index_set
                )
            )
            for bucket in bucket_defs
        }

    def _coordinate_master_pose_indices_for_group(
        self,
        group: Mapping[str, Any],
    ) -> List[int]:
        tpl = str(group["facility_type"])
        if (
            self.owner.skip_power_coverage
            and tpl in self.owner._powered_templates
            and tpl != "power_pole"
        ):
            return sorted(
                range(len(self.owner.facility_pools.get(tpl, []))),
                key=lambda pose_idx: self.owner._pose_sort_key(tpl, int(pose_idx)),
            )
        return self.owner._candidate_pose_indices_for_group(group)

    def _prepare_signature_maps(self) -> None:
        for group in self.owner._mandatory_groups:
            group_id = str(group["group_id"])
            tpl = str(group["facility_type"])
            allowed_pose_indices = {
                int(pose_idx) for pose_idx in self._coordinate_master_pose_indices_for_group(group)
            }
            payload = self._signature_domain_payload(
                tpl,
                allowed_pose_indices,
                self.owner._mandatory_signature_buckets.get(group_id, []),
                label=f"mandatory_group::{group_id}",
            )
            bucket_pose_indices = self._filtered_bucket_pose_index_map(
                self.owner._mandatory_signature_buckets.get(group_id, []),
                allowed_pose_indices,
            )
            self._mandatory_group_mode_rect_domains[group_id] = payload["mode_rect_domains"]
            self._mandatory_group_uses_domain_table[group_id] = bool(payload["uses_domain_table"])
            self._mandatory_group_pose_counts[group_id] = int(payload["pose_count"])
            self._mandatory_group_bucket_regions[group_id] = payload["bucket_regions"]
            self._mandatory_group_uses_signature_table[group_id] = bool(payload["uses_signature_table"])
            self._mandatory_group_bucket_pose_indices[group_id] = dict(bucket_pose_indices)
            self._mandatory_group_bucket_pose_counts[group_id] = {
                str(bucket_id): int(len(pose_indices))
                for bucket_id, pose_indices in bucket_pose_indices.items()
            }
            self._mandatory_group_bucket_count_upper_bounds[group_id] = {
                str(bucket_id): int(min(int(group["count"]), len(pose_indices)))
                for bucket_id, pose_indices in bucket_pose_indices.items()
            }

        for tpl, required_count in sorted(self.owner._exact_required_pose_optional_counts.items()):
            if int(required_count) <= 0:
                continue
            allowed_pose_indices = set(range(len(self.owner.facility_pools.get(str(tpl), []))))
            payload = self._signature_domain_payload(
                str(tpl),
                allowed_pose_indices,
                self.owner._required_optional_signature_buckets.get(str(tpl), []),
                label=f"required_optional::{tpl}",
            )
            bucket_pose_indices = self._filtered_bucket_pose_index_map(
                self.owner._required_optional_signature_buckets.get(str(tpl), []),
                allowed_pose_indices,
            )
            self._required_optional_mode_rect_domains[str(tpl)] = payload["mode_rect_domains"]
            self._required_optional_uses_domain_table[str(tpl)] = bool(payload["uses_domain_table"])
            self._required_optional_pose_counts[str(tpl)] = int(payload["pose_count"])
            self._required_optional_bucket_regions[str(tpl)] = payload["bucket_regions"]
            self._required_optional_uses_signature_table[str(tpl)] = bool(payload["uses_signature_table"])
            self._required_optional_bucket_pose_indices[str(tpl)] = dict(bucket_pose_indices)
            self._required_optional_bucket_pose_counts[str(tpl)] = {
                str(bucket_id): int(len(pose_indices))
                for bucket_id, pose_indices in bucket_pose_indices.items()
            }
            self._required_optional_bucket_count_upper_bounds[str(tpl)] = {
                str(bucket_id): int(min(int(required_count), len(pose_indices)))
                for bucket_id, pose_indices in bucket_pose_indices.items()
            }

        for tpl in ("protocol_storage_box",):
            if str(tpl) not in self.owner.templates:
                continue
            if not self._needs_residual_optional_slots_after_fixed_required(str(tpl)):
                continue
            slot_upper_bound = int(self._residual_optional_slot_upper_bound(str(tpl)))
            if slot_upper_bound <= 0:
                continue
            bucket_defs = list(self.owner._required_optional_signature_buckets.get(str(tpl), []))
            if not bucket_defs:
                bucket_defs = list(
                    self.owner._build_signature_bucket_payload(
                        str(tpl),
                        range(len(self.owner.facility_pools.get(str(tpl), []))),
                    )
                )
            if not bucket_defs:
                continue
            self._residual_optional_signature_buckets[str(tpl)] = copy.deepcopy(bucket_defs)
            allowed_pose_indices = set(range(len(self.owner.facility_pools.get(str(tpl), []))))
            payload = self._signature_domain_payload(
                str(tpl),
                allowed_pose_indices,
                bucket_defs,
                label=f"residual_optional::{tpl}",
            )
            bucket_pose_indices = self._filtered_bucket_pose_index_map(
                bucket_defs,
                allowed_pose_indices,
            )
            self._residual_optional_bucket_regions[str(tpl)] = payload["bucket_regions"]
            self._residual_optional_uses_signature_table[str(tpl)] = bool(
                payload["uses_signature_table"]
            )
            self._residual_optional_bucket_pose_indices[str(tpl)] = dict(
                bucket_pose_indices
            )
            self._residual_optional_bucket_pose_counts[str(tpl)] = {
                str(bucket_id): int(len(pose_indices))
                for bucket_id, pose_indices in bucket_pose_indices.items()
            }
            self._residual_optional_bucket_count_upper_bounds[str(tpl)] = {
                str(bucket_id): int(min(int(slot_upper_bound), len(pose_indices)))
                for bucket_id, pose_indices in bucket_pose_indices.items()
            }

    def _power_pole_shell_distance(
        self,
        domain: ModeRectDomain,
        x_val: int,
        y_val: int,
    ) -> Tuple[int, int]:
        dx = min(int(x_val - domain.x_min), int(domain.x_max - x_val))
        dy = min(int(y_val - domain.y_min), int(domain.y_max - y_val))
        return int(dx), int(dy)

    def _power_pole_family_sort_key(self, family_name: str) -> Tuple[Any, ...]:
        template_order = sorted(self.owner._exact_powered_template_demands())
        coefficients = self._power_pole_family_coefficients.get(str(family_name), {})
        coefficient_key = tuple(-int(coefficients.get(str(tpl), 0)) for tpl in template_order)
        return (
            coefficient_key,
            -int(self._power_pole_family_pose_counts.get(str(family_name), 0)),
            str(family_name),
        )

    def _prepare_power_pole_families(self) -> None:
        self._power_pole_family_name_by_int = {}
        self._power_pole_family_coefficients = {}
        self._power_pole_family_id_by_pose_idx = {}
        self._power_pole_family_pose_counts = {}
        self._power_pole_family_order = []
        self._power_pole_use_shell_lookup = True
        self._power_pole_family_tuple_rows = []
        self._power_pole_shell_lookup_rows = []
        self._power_pole_shell_lookup_pairs = []
        self._power_pole_slot_upper_bound = int(
            self.owner._mandatory_powered_nonpole_count()
            + sum(int(v) for v in self.owner._exact_fixed_required_optional_powered_demands().values())
            + sum(int(v) for v in self.owner._residual_optional_powered_slot_upper_bounds().values())
        )
        # 2026-05-15 spike hook: env-gated tight upper bound override.
        # 默认 763 是 worst-case (per powered_slot 1 pole). 实际 radius=5
        # 一个 pole cover ~12 cells, 估真需 60-100. env 显式 set 触发 spike,
        # 验 RAM 峰值减幅. 详 [[project_30gb_real_culprit_power_coverage]].
        # 风险: 若 instance 真需要 > override 个 pole, master INFEASIBLE 假阳性.
        # default 不动, env 缺/garbage no-op.
        import os as _os
        override_env = _os.environ.get("EXACT_POLE_SLOT_UPPER_BOUND_OVERRIDE", "").strip()
        if override_env:
            try:
                override_val = int(override_env)
                if 0 < override_val < self._power_pole_slot_upper_bound:
                    self._power_pole_slot_upper_bound = override_val
            except ValueError:
                pass
        if self.owner.skip_power_coverage:
            return
        powered_template_demands = self.owner._exact_powered_template_demands()
        if not powered_template_demands:
            return

        template_order = sorted(powered_template_demands)
        family_members: DefaultDict[Tuple[Tuple[str, int], ...], List[int]] = defaultdict(list)
        cache_stats = {
            "scope": "process_memory",
            "signature_hits": 0,
            "signature_misses": 0,
            "signature_count": 0,
            "pole_template_evaluations": 0,
            "signature_class_count": 0,
            "signature_class_evaluations": 0,
            "raw_pole_evaluations": 0,
            "compact_signature_class_count": 0,
            "compact_signature_class_evaluations": 0,
            "compact_signature_hits": 0,
            "compact_signature_misses": 0,
            "normalized_rect_signature_count": 0,
            "normalized_rect_cache_hits": 0,
            "normalized_rect_cache_misses": 0,
            "legacy_signature_materializations": 0,
            "supported_by_pole_materializations": 0,
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
            "coefficient_source": "exact_compact_rect_cpsat_v14",
            "shell_pair_count": int(len(self.owner._power_pole_pose_indices_by_shell_pair)),
        }
        coeff_by_template_and_pole = self.owner._exact_local_power_capacity_coefficients(
            powered_template_demands,
            cache_stats,
        )
        for pole_idx, _pose in enumerate(self.owner.facility_pools.get("power_pole", [])):
            family_key = tuple(
                (str(tpl), int(coeff_by_template_and_pole.get(str(tpl), {}).get(int(pole_idx), 0)))
                for tpl in template_order
            )
            family_members[family_key].append(int(pole_idx))

        for family_index, family_key in enumerate(sorted(family_members)):
            family_name = f"family_{family_index:03d}"
            self._power_pole_family_name_by_int[int(family_index)] = family_name
            self._power_pole_family_coefficients[family_name] = {
                str(tpl): int(coeff)
                for tpl, coeff in family_key
            }
            self._power_pole_family_pose_counts[family_name] = int(len(family_members[family_key]))
            for pose_idx in family_members[family_key]:
                self._power_pole_family_id_by_pose_idx[int(pose_idx)] = int(family_index)
        self._power_pole_family_order = sorted(
            self._power_pole_family_coefficients,
            key=self._power_pole_family_sort_key,
        )

        coeff_stats: Dict[str, Any] = {}
        for tpl in template_order:
            positive_coeffs = [
                int(value)
                for value in coeff_by_template_and_pole.get(str(tpl), {}).values()
                if int(value) > 0
            ]
            coeff_stats[str(tpl)] = {
                "demand": int(powered_template_demands[str(tpl)]),
                "total_poles": len(coeff_by_template_and_pole.get(str(tpl), {})),
                "nonzero_poles": len(positive_coeffs),
                "max_coeff": max(positive_coeffs) if positive_coeffs else 0,
                "min_nonzero_coeff": min(positive_coeffs) if positive_coeffs else None,
            }
        self._power_capacity_cache_stats = cache_stats
        self._power_capacity_coeff_stats = coeff_stats

        mode_rect_domains = self._template_full_mode_rect_domains.get("power_pole", {})
        pair_to_family_name: Dict[Tuple[int, int], str] = {}
        for pose_idx, pose_tuple in sorted(self._template_pose_tuple_by_idx.get("power_pole", {}).items()):
            x_val, y_val, mode_id = pose_tuple
            domain = mode_rect_domains.get(int(mode_id))
            if domain is None:
                continue
            family_id = self._power_pole_family_id_by_pose_idx.get(int(pose_idx))
            if family_id is None:
                raise ValueError(f"Missing power pole family for pose_idx={pose_idx}")
            family_name = self._power_pole_family_name_by_int[int(family_id)]
            dx, dy = self._power_pole_shell_distance(domain, int(x_val), int(y_val))
            shell_pair = tuple(sorted((int(dx), int(dy))))
            existing = pair_to_family_name.get(shell_pair)
            if existing is not None and existing != family_name:
                self._power_pole_use_shell_lookup = False
                pair_to_family_name = {}
                break
            pair_to_family_name[shell_pair] = family_name

        if self._power_pole_use_shell_lookup:
            for d_lo, d_hi in sorted(pair_to_family_name):
                family_name = pair_to_family_name[(int(d_lo), int(d_hi))]
                family_id = next(
                    int(idx)
                    for idx, name in self._power_pole_family_name_by_int.items()
                    if str(name) == str(family_name)
                )
                self._power_pole_shell_lookup_rows.append((int(d_lo), int(d_hi), int(family_id)))
                self._power_pole_shell_lookup_pairs.append(
                    {
                        "d_lo": int(d_lo),
                        "d_hi": int(d_hi),
                        "family_id": str(family_name),
                    }
                )
        else:
            for pose_idx, pose_tuple in sorted(self._template_pose_tuple_by_idx.get("power_pole", {}).items()):
                family_id = self._power_pole_family_id_by_pose_idx.get(int(pose_idx))
                if family_id is None:
                    continue
                x_val, y_val, mode_id = pose_tuple
                self._power_pole_family_tuple_rows.append(
                    (int(x_val), int(y_val), int(mode_id), int(family_id))
                )

    def _delegate_power_placement_to_subproblem(self) -> bool:
        # Read fresh from env each call so build vs solve sees the same flag.
        # Flag default OFF — existing certified path unchanged.
        return os.environ.get("EXACT_POWER_PLACEMENT_SUBPROBLEM", "").strip() not in {
            "",
            "0",
            "false",
            "False",
        }

    def _lazy_power_completion_enabled(self) -> bool:
        # 新边界 (PROJECT_LOCK L4b): master 保留 power_pole residual slots, 只跳过
        # _add_geometric_power_coverage_constraints. completion 由 subproblem 提供
        # proof-carrying witness. 跟旧 EXACT_POWER_PLACEMENT_SUBPROBLEM (L4a 禁开)
        # 的关键区别是 pole slot 仍 materialized — downstream cut 可 resolve
        # runtime literal.
        return os.environ.get("EXACT_LAZY_POWER_COMPLETION", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _prepare_slot_specs(self) -> None:
        self.mandatory_slots = {}
        for group in self.owner._mandatory_groups:
            group_id = str(group["group_id"])
            tpl = str(group["facility_type"])
            dims = dict(self.owner.templates[tpl]["dimensions"])
            mode_rect_domains = dict(self._mandatory_group_mode_rect_domains.get(group_id, {}))
            candidate_pose_count = int(self._mandatory_group_pose_counts.get(group_id, 0))
            candidate_tuples = tuple(
                sorted(
                    self._template_pose_tuple_by_idx[tpl][int(pose_idx)]
                    for pose_idx in sorted(self._coordinate_master_pose_indices_for_group(group))
                    if int(pose_idx) in self._template_pose_tuple_by_idx[tpl]
                )
            )
            self.mandatory_slots[group_id] = [
                CoordinateSlotSpec(
                    key=f"{group_id}::slot::{slot_index}",
                    template=tpl,
                    slot_kind="mandatory",
                    slot_index=int(slot_index),
                    dims=(int(dims["w"]), int(dims["h"])),
                    candidate_pose_count=int(candidate_pose_count),
                    tuple_to_pose_idx=dict(self._template_pose_idx_by_tuple[tpl]),
                    mode_rect_domains=mode_rect_domains,
                    allowed_tuples=candidate_tuples,
                    use_domain_table=bool(self._mandatory_group_uses_domain_table.get(group_id, False)),
                    signature_id_to_bucket_id=dict(self._template_signature_bucket_id_by_int.get(tpl, {})),
                )
                for slot_index in range(int(group["count"]))
            ]

        self.required_optional_slots = {}
        for tpl, required_count in sorted(self.owner._exact_required_pose_optional_counts.items()):
            if int(required_count) <= 0:
                continue
            dims = dict(self.owner.templates[str(tpl)]["dimensions"])
            mode_rect_domains = dict(self._required_optional_mode_rect_domains.get(str(tpl), {}))
            candidate_pose_count = int(self._required_optional_pose_counts.get(str(tpl), 0))
            self.required_optional_slots[str(tpl)] = [
                CoordinateSlotSpec(
                    key=f"required_optional::{tpl}::slot::{slot_index}",
                    template=str(tpl),
                    slot_kind="required_optional",
                    slot_index=int(slot_index),
                    dims=(int(dims["w"]), int(dims["h"])),
                    candidate_pose_count=int(candidate_pose_count),
                    tuple_to_pose_idx=dict(self._template_pose_idx_by_tuple[str(tpl)]),
                    mode_rect_domains=mode_rect_domains,
                    allowed_tuples=tuple(sorted(self._template_pose_idx_by_tuple[str(tpl)])),
                    use_domain_table=bool(self._required_optional_uses_domain_table.get(str(tpl), False)),
                    signature_id_to_bucket_id=dict(self._template_signature_bucket_id_by_int.get(str(tpl), {})),
                )
                for slot_index in range(int(required_count))
            ]

        self.residual_optional_slots = {}
        for tpl in ("protocol_storage_box", "power_pole"):
            if tpl not in self.owner.templates:
                continue
            if not self._needs_residual_optional_slots_after_fixed_required(str(tpl)):
                continue
            if (
                str(tpl) == "power_pole"
                and self._delegate_power_placement_to_subproblem()
            ):
                self.owner.build_stats["power_placement"] = {
                    "representation": "delegated_power_subproblem_v1",
                    "skipped_residual_power_pole_slot_upper_bound": int(
                        self._residual_optional_slot_upper_bound("power_pole")
                    ),
                }
                continue
            slot_upper_bound = int(self._residual_optional_slot_upper_bound(str(tpl)))
            if slot_upper_bound <= 0:
                continue
            mode_rect_domains = dict(self._template_full_mode_rect_domains.get(str(tpl), {}))
            candidate_pose_count = int(sum(domain.pose_count for domain in mode_rect_domains.values()))
            if candidate_pose_count <= 0:
                continue
            dims = dict(self.owner.templates[str(tpl)]["dimensions"])
            slot_specs = [
                CoordinateSlotSpec(
                    key=f"residual_optional::{tpl}::slot::{slot_index}",
                    template=str(tpl),
                    slot_kind="residual_optional",
                    slot_index=int(slot_index),
                    dims=(int(dims["w"]), int(dims["h"])),
                    candidate_pose_count=int(candidate_pose_count),
                    tuple_to_pose_idx=dict(self._template_pose_idx_by_tuple[str(tpl)]),
                    mode_rect_domains=mode_rect_domains,
                    allowed_tuples=tuple(sorted(self._template_pose_idx_by_tuple[str(tpl)])),
                    use_domain_table=bool(self._template_uses_domain_table.get(str(tpl), False)),
                    family_id_to_family_name=(
                        dict(self._power_pole_family_name_by_int)
                        if str(tpl) == "power_pole"
                        else {}
                    ),
                )
                for slot_index in range(int(slot_upper_bound))
            ]
            if slot_specs:
                self.residual_optional_slots[str(tpl)] = slot_specs

    def _new_interval_end(
        self,
        start_var: cp_model.IntVar,
        size: int,
        name: str,
    ) -> cp_model.IntVar:
        end_var = self.model.NewIntVar(0, max(self.grid_w, self.grid_h) + int(size), name)
        self.model.Add(end_var == start_var + int(size))
        return end_var

    def _create_slot_footprint_intervals(
        self,
        slot: CoordinateSlotSpec,
        *,
        optional: bool,
    ) -> None:
        domains = list(slot.mode_rect_domains.values())
        if not domains:
            raise ValueError(f"slot has no footprint domains: {slot.key}")
        if slot.x is None or slot.y is None or slot.mode is None:
            raise RuntimeError(f"slot missing base coordinate channels: {slot.key}")
        min_dx = min(int(domain.footprint_bounds[0]) for domain in domains)
        max_dx = max(int(domain.footprint_bounds[1]) for domain in domains)
        min_dy = min(int(domain.footprint_bounds[2]) for domain in domains)
        max_dy = max(int(domain.footprint_bounds[3]) for domain in domains)
        max_width = max(int(domain.footprint_width) for domain in domains)
        max_height = max(int(domain.footprint_height) for domain in domains)
        x_start_lower = min(int(domain.x_min) + int(domain.footprint_bounds[0]) for domain in domains)
        x_start_upper = max(int(domain.x_max) + int(domain.footprint_bounds[0]) for domain in domains)
        y_start_lower = min(int(domain.y_min) + int(domain.footprint_bounds[2]) for domain in domains)
        y_start_upper = max(int(domain.y_max) + int(domain.footprint_bounds[2]) for domain in domains)
        x_end_lower = min(int(domain.x_min) + int(domain.footprint_bounds[1]) + 1 for domain in domains)
        x_end_upper = max(int(domain.x_max) + int(domain.footprint_bounds[1]) + 1 for domain in domains)
        y_end_lower = min(int(domain.y_min) + int(domain.footprint_bounds[3]) + 1 for domain in domains)
        y_end_upper = max(int(domain.y_max) + int(domain.footprint_bounds[3]) + 1 for domain in domains)

        slot.footprint_dx_min = self.model.NewIntVar(
            int(min_dx),
            int(max_dx),
            f"footprint_dx_min__{slot.key}",
        )
        slot.footprint_dy_min = self.model.NewIntVar(
            int(min_dy),
            int(max_dy),
            f"footprint_dy_min__{slot.key}",
        )
        slot.footprint_width = self.model.NewIntVar(
            1,
            int(max_width),
            f"footprint_w__{slot.key}",
        )
        slot.footprint_height = self.model.NewIntVar(
            1,
            int(max_height),
            f"footprint_h__{slot.key}",
        )
        footprint_rows = [
            [
                int(domain.mode_id),
                int(domain.footprint_bounds[0]),
                int(domain.footprint_bounds[2]),
                int(domain.footprint_width),
                int(domain.footprint_height),
            ]
            for domain in sorted(domains, key=lambda item: int(item.mode_id))
        ]
        self.model.AddAllowedAssignments(
            [
                slot.mode,
                slot.footprint_dx_min,
                slot.footprint_dy_min,
                slot.footprint_width,
                slot.footprint_height,
            ],
            footprint_rows,
        )

        slot.footprint_x_start = self.model.NewIntVar(
            int(x_start_lower),
            int(x_start_upper),
            f"footprint_x_start__{slot.key}",
        )
        slot.footprint_y_start = self.model.NewIntVar(
            int(y_start_lower),
            int(y_start_upper),
            f"footprint_y_start__{slot.key}",
        )
        slot.footprint_x_end = self.model.NewIntVar(
            int(x_end_lower),
            int(x_end_upper),
            f"footprint_x_end__{slot.key}",
        )
        slot.footprint_y_end = self.model.NewIntVar(
            int(y_end_lower),
            int(y_end_upper),
            f"footprint_y_end__{slot.key}",
        )
        self.model.Add(slot.footprint_x_start == slot.x + slot.footprint_dx_min)
        self.model.Add(slot.footprint_y_start == slot.y + slot.footprint_dy_min)
        self.model.Add(slot.footprint_x_end == slot.footprint_x_start + slot.footprint_width)
        self.model.Add(slot.footprint_y_end == slot.footprint_y_start + slot.footprint_height)

        if optional:
            if slot.active is None:
                raise RuntimeError(f"optional slot missing active literal: {slot.key}")
            slot.x_interval = self.model.NewOptionalIntervalVar(
                slot.footprint_x_start,
                slot.footprint_width,
                slot.footprint_x_end,
                slot.active,
                f"x_iv__{slot.key}",
            )
            slot.y_interval = self.model.NewOptionalIntervalVar(
                slot.footprint_y_start,
                slot.footprint_height,
                slot.footprint_y_end,
                slot.active,
                f"y_iv__{slot.key}",
            )
        else:
            slot.x_interval = self.model.NewIntervalVar(
                slot.footprint_x_start,
                slot.footprint_width,
                slot.footprint_x_end,
                f"x_iv__{slot.key}",
            )
            slot.y_interval = self.model.NewIntervalVar(
                slot.footprint_y_start,
                slot.footprint_height,
                slot.footprint_y_end,
                f"y_iv__{slot.key}",
            )
        self._core_x_intervals.append(slot.x_interval)
        self._core_y_intervals.append(slot.y_interval)

    def _slot_footprint_x_start(self, slot: CoordinateSlotSpec) -> cp_model.IntVar:
        if slot.footprint_x_start is None:
            raise RuntimeError(f"slot missing footprint x start channel: {slot.key}")
        return slot.footprint_x_start

    def _slot_footprint_y_start(self, slot: CoordinateSlotSpec) -> cp_model.IntVar:
        if slot.footprint_y_start is None:
            raise RuntimeError(f"slot missing footprint y start channel: {slot.key}")
        return slot.footprint_y_start

    def _slot_footprint_width(self, slot: CoordinateSlotSpec) -> cp_model.IntVar:
        if slot.footprint_width is None:
            raise RuntimeError(f"slot missing footprint width channel: {slot.key}")
        return slot.footprint_width

    def _slot_footprint_height(self, slot: CoordinateSlotSpec) -> cp_model.IntVar:
        if slot.footprint_height is None:
            raise RuntimeError(f"slot missing footprint height channel: {slot.key}")
        return slot.footprint_height

    def _slot_order_key_bounds(self, slot: CoordinateSlotSpec) -> Tuple[int, int]:
        mode_count = max(1, self._template_mode_literals.get(slot.template, 1))
        scale_x = int(self.grid_h * mode_count)
        scale_y = int(mode_count)
        return int(scale_x), int(scale_y)

    def _slot_order_key_upper_bound(self, slot: CoordinateSlotSpec) -> int:
        scale_x, scale_y = self._slot_order_key_bounds(slot)
        mode_count = max(1, self._template_mode_literals.get(slot.template, 1))
        return int((self.grid_w - 1) * scale_x + (self.grid_h - 1) * scale_y + (mode_count - 1))

    def _slot_order_key_for_pose_tuple(
        self,
        slot: CoordinateSlotSpec,
        pose_tuple: PoseTuple,
    ) -> int:
        scale_x, scale_y = self._slot_order_key_bounds(slot)
        x_val, y_val, mode_id = pose_tuple
        return int(int(x_val) * int(scale_x) + int(y_val) * int(scale_y) + int(mode_id))

    def _slot_signature_order_pose_indices(
        self,
        slot: CoordinateSlotSpec,
    ) -> Tuple[int, ...]:
        pose_indices: Set[int] = set()
        if slot.allowed_tuples:
            for raw_pose_tuple in slot.allowed_tuples:
                pose_tuple = tuple(int(value) for value in raw_pose_tuple)
                pose_idx = slot.tuple_to_pose_idx.get(pose_tuple)
                if pose_idx is not None:
                    pose_indices.add(int(pose_idx))
            return tuple(sorted(pose_indices))
        return tuple(sorted(int(pose_idx) for pose_idx in slot.tuple_to_pose_idx.values()))

    def _pose_signature_int_by_bucket_defs(
        self,
        bucket_defs: Sequence[Mapping[str, Any]],
        allowed_pose_indices: Optional[Iterable[int]] = None,
    ) -> Dict[int, int]:
        allowed_set: Optional[Set[int]] = None
        if allowed_pose_indices is not None:
            allowed_set = {int(pose_idx) for pose_idx in allowed_pose_indices}
        pose_signature_int_by_idx: Dict[int, int] = {}
        for signature_int, bucket in enumerate(bucket_defs):
            for raw_pose_idx in bucket.get("pose_indices", []) or []:
                pose_idx = int(raw_pose_idx)
                if allowed_set is not None and pose_idx not in allowed_set:
                    continue
                pose_signature_int_by_idx[pose_idx] = int(signature_int)
        return pose_signature_int_by_idx

    def _signature_order_is_compatible_with_slot_order(
        self,
        slot: CoordinateSlotSpec,
        pose_signature_int_by_idx: Mapping[int, int],
    ) -> bool:
        rows: List[Tuple[int, int, int]] = []
        template_pose_tuples = self._template_pose_tuple_by_idx.get(str(slot.template), {})
        for pose_idx in self._slot_signature_order_pose_indices(slot):
            signature_int = pose_signature_int_by_idx.get(int(pose_idx))
            pose_tuple = template_pose_tuples.get(int(pose_idx))
            if signature_int is None or pose_tuple is None:
                continue
            rows.append(
                (
                    self._slot_order_key_for_pose_tuple(slot, pose_tuple),
                    int(signature_int),
                    int(pose_idx),
                )
            )
        previous_signature: Optional[int] = None
        for _, signature_int, _ in sorted(rows):
            if previous_signature is not None and int(signature_int) < int(previous_signature):
                return False
            previous_signature = int(signature_int)
        return True

    def _add_signature_monotonic_constraints_if_compatible(
        self,
        slot_specs: Sequence[CoordinateSlotSpec],
        *,
        bucket_defs: Sequence[Mapping[str, Any]],
        allowed_pose_indices: Optional[Iterable[int]],
        skipped_stats_key: str,
    ) -> int:
        ordered_slots = list(slot_specs)
        if len(ordered_slots) < 2:
            return 0
        pose_signature_int_by_idx = self._pose_signature_int_by_bucket_defs(
            bucket_defs,
            allowed_pose_indices,
        )
        if any(
            not self._signature_order_is_compatible_with_slot_order(
                slot,
                pose_signature_int_by_idx,
            )
            for slot in ordered_slots
        ):
            skipped = len(ordered_slots) - 1
            self._coordinate_symmetry_stats[skipped_stats_key] = int(
                self._coordinate_symmetry_stats.get(skipped_stats_key, 0)
            ) + int(skipped)
            return 0

        added = 0
        for left_slot, right_slot in zip(ordered_slots, ordered_slots[1:]):
            if left_slot.signature is None or right_slot.signature is None:
                continue
            self.model.Add(left_slot.signature <= right_slot.signature)
            added += 1
        return int(added)

    def _create_base_slot_geometry(
        self,
        slot: CoordinateSlotSpec,
        *,
        optional: bool,
    ) -> None:
        all_domains = list(slot.mode_rect_domains.values())
        if not all_domains:
            slot.x = self.model.NewIntVar(0, 0, f"x__{slot.key}")
            slot.y = self.model.NewIntVar(0, 0, f"y__{slot.key}")
            slot.mode = self.model.NewIntVar(0, 0, f"mode__{slot.key}")
            slot.order_key = self.model.NewIntVar(0, 0, f"order_key__{slot.key}")
            self.model.Add(slot.order_key == 0)
            x_end = self._new_interval_end(slot.x, int(slot.dims[0]), f"x_end__{slot.key}")
            y_end = self._new_interval_end(slot.y, int(slot.dims[1]), f"y_end__{slot.key}")
            if optional:
                if slot.active is None:
                    raise RuntimeError(f"optional slot missing active literal: {slot.key}")
                slot.x_interval = self.model.NewOptionalIntervalVar(
                    slot.x,
                    int(slot.dims[0]),
                    x_end,
                    slot.active,
                    f"x_iv__{slot.key}",
                )
                slot.y_interval = self.model.NewOptionalIntervalVar(
                    slot.y,
                    int(slot.dims[1]),
                    y_end,
                    slot.active,
                    f"y_iv__{slot.key}",
                )
            else:
                slot.x_interval = self.model.NewIntervalVar(slot.x, int(slot.dims[0]), x_end, f"x_iv__{slot.key}")
                slot.y_interval = self.model.NewIntervalVar(slot.y, int(slot.dims[1]), y_end, f"y_iv__{slot.key}")
            self._core_x_intervals.append(slot.x_interval)
            self._core_y_intervals.append(slot.y_interval)
            self.model.Add(0 == 1)
            return
        x_lower = min(int(domain.x_min) for domain in all_domains)
        x_upper = max(int(domain.x_max) for domain in all_domains)
        y_lower = min(int(domain.y_min) for domain in all_domains)
        y_upper = max(int(domain.y_max) for domain in all_domains)
        mode_count = max(1, self._template_mode_literals.get(slot.template, 1))

        slot.x = self.model.NewIntVar(int(x_lower), int(x_upper), f"x__{slot.key}")
        slot.y = self.model.NewIntVar(int(y_lower), int(y_upper), f"y__{slot.key}")
        slot.mode = self.model.NewIntVar(0, mode_count - 1, f"mode__{slot.key}")
        slot.order_key = self.model.NewIntVar(
            0,
            self._slot_order_key_upper_bound(slot),
            f"order_key__{slot.key}",
        )
        scale_x, scale_y = self._slot_order_key_bounds(slot)
        self.model.Add(
            slot.order_key
            == slot.x * int(scale_x) + slot.y * int(scale_y) + slot.mode
        )

        self._create_slot_footprint_intervals(slot, optional=optional)

        if slot.use_domain_table and slot.allowed_tuples:
            allowed_rows = [
                [int(x_val), int(y_val), int(mode_id)]
                for x_val, y_val, mode_id in slot.allowed_tuples
            ]
            if optional:
                if slot.active is None:
                    raise RuntimeError(f"optional slot missing active literal: {slot.key}")
                self.model.AddAllowedAssignments(
                    [slot.x, slot.y, slot.mode],
                    allowed_rows,
                ).OnlyEnforceIf(slot.active)
            else:
                self.model.AddAllowedAssignments(
                    [slot.x, slot.y, slot.mode],
                    allowed_rows,
                )
            self._domain_table_row_count += len(allowed_rows)

    def _add_region_constraints(
        self,
        slot: CoordinateSlotSpec,
        region: SignatureRegion,
        lit: cp_model.IntVar,
    ) -> None:
        self.model.Add(slot.mode == int(region.mode_id)).OnlyEnforceIf(lit)
        self.model.Add(slot.x >= int(region.x_min)).OnlyEnforceIf(lit)
        self.model.Add(slot.x <= int(region.x_max)).OnlyEnforceIf(lit)
        self.model.Add(slot.y >= int(region.y_min)).OnlyEnforceIf(lit)
        self.model.Add(slot.y <= int(region.y_max)).OnlyEnforceIf(lit)

    def _create_signature_slot_vars(
        self,
        slot_specs: Sequence[CoordinateSlotSpec],
        *,
        bucket_defs: Sequence[Mapping[str, Any]],
        bucket_regions: Mapping[str, List[SignatureRegion]],
        membership_store: Dict[str, List[cp_model.IntVar]],
        membership_prefix: str,
    ) -> None:
        if not bucket_defs:
            example_key = str(slot_specs[0].key) if slot_specs else membership_prefix
            raise ValueError(
                f"Missing signature bucket definitions for coordinate-exact slot set: {example_key}"
            )
        bucket_id_to_int = {str(bucket["bucket_id"]): idx for idx, bucket in enumerate(bucket_defs)}
        for slot in slot_specs:
            self._create_base_slot_geometry(slot, optional=False)
            slot.signature = self.model.NewIntVar(
                0,
                max(0, len(bucket_defs) - 1),
                f"signature__{slot.key}",
            )
            self._slot_binding[slot.key] = {
                "x": int(slot.x.Index()),
                "y": int(slot.y.Index()),
                "mode": int(slot.mode.Index()),
                "signature": int(slot.signature.Index()),
            }
            self._interval_binding[slot.key] = (int(slot.x_interval.Index()), int(slot.y_interval.Index()))

            all_region_lits: List[cp_model.IntVar] = []
            bucket_lits_for_slot: List[cp_model.IntVar] = []
            for bucket in bucket_defs:
                bucket_id = str(bucket["bucket_id"])
                int(bucket_id_to_int[bucket_id])
                bucket_lit = self.model.NewBoolVar(f"{membership_prefix}__{slot.key}__{bucket_id}")
                # P0 #6 改造 4 (membership channeling): replaced double-reify
                # `signature == bucket_int <=> bucket_lit` with a single
                # linear channel + ExactlyOne after the loop.
                # Mathematically equivalent because signature domain
                # [0, n-1] equals bucket_int set {0..n-1} (dense, line 2326).
                membership_store[bucket_id].append(bucket_lit)
                bucket_lits_for_slot.append(bucket_lit)

                bucket_region_lits: List[cp_model.IntVar] = []
                for region_index, region in enumerate(bucket_regions.get(bucket_id, [])):
                    region_lit = self.model.NewBoolVar(
                        f"region__{slot.key}__{bucket_id}__{region_index}"
                    )
                    self._add_region_constraints(slot, region, region_lit)
                    bucket_region_lits.append(region_lit)
                    all_region_lits.append(region_lit)
                if bucket_region_lits:
                    # P0 #6 改造 3 (sum-channel): bucket_lit ∈ {0,1} so the
                    # paired half-reify (==1 if lit, ==0 if not lit) is
                    # mathematically equivalent to a single channeling.
                    self.model.Add(sum(bucket_region_lits) == bucket_lit)
                else:
                    self.model.Add(bucket_lit == 0)

            if bucket_lits_for_slot:
                # P0 #6 改造 4 closing: signature = Σ idx · lit_idx,
                # combined with AddExactlyOne(bucket_lits) gives the same
                # signature ↔ bucket_lit binding as the original double-reify.
                self.model.Add(
                    slot.signature == sum(
                        int(bucket_id_to_int[str(b["bucket_id"])]) * lit
                        for b, lit in zip(bucket_defs, bucket_lits_for_slot)
                    )
                )
                self.model.AddExactlyOne(bucket_lits_for_slot)

            if all_region_lits:
                self.model.AddExactlyOne(all_region_lits)
            else:
                self.model.Add(0 == 1)

    def _create_optional_signature_slot_vars(
        self,
        slot_specs: Sequence[CoordinateSlotSpec],
        *,
        bucket_defs: Sequence[Mapping[str, Any]],
        bucket_regions: Mapping[str, List[SignatureRegion]],
        membership_store: Dict[str, List[cp_model.IntVar]],
        membership_prefix: str,
    ) -> None:
        if not bucket_defs:
            example_key = str(slot_specs[0].key) if slot_specs else membership_prefix
            raise ValueError(
                "Missing optional signature bucket definitions for coordinate-exact slot "
                f"set: {example_key}"
            )
        bucket_id_to_int = {str(bucket["bucket_id"]): idx for idx, bucket in enumerate(bucket_defs)}
        inactive_signature_value = int(len(bucket_defs))
        for slot in slot_specs:
            if slot.active is None:
                slot.active = self.model.NewBoolVar(f"active__{slot.key}")
            self._create_base_slot_geometry(slot, optional=True)
            slot.signature = self.model.NewIntVar(
                0,
                int(inactive_signature_value),
                f"signature__{slot.key}",
            )
            self.model.Add(slot.signature == int(inactive_signature_value)).OnlyEnforceIf(
                slot.active.Not()
            )
            self._slot_binding[slot.key] = {
                "active": int(slot.active.Index()),
                "x": int(slot.x.Index()),
                "y": int(slot.y.Index()),
                "mode": int(slot.mode.Index()),
                "order_key": int(slot.order_key.Index()),
                "signature": int(slot.signature.Index()),
            }
            self._interval_binding[slot.key] = (
                int(slot.x_interval.Index()),
                int(slot.y_interval.Index()),
            )

            bucket_lits: List[cp_model.IntVar] = []
            for bucket in bucket_defs:
                bucket_id = str(bucket["bucket_id"])
                bucket_int = int(bucket_id_to_int[bucket_id])
                bucket_lit = self.model.NewBoolVar(
                    f"{membership_prefix}__{slot.key}__{bucket_id}"
                )
                # P1 #25 micro-improvement: removed `AddImplication(bucket_lit,
                # slot.active)` — it is implied by the later sum-channel
                # `sum(bucket_lits) == slot.active`: if any bucket_lit_i = 1
                # then sum ≥ 1 ⟹ slot.active ≥ 1 ⟹ slot.active = 1 (bool).
                self.model.Add(slot.signature == int(bucket_int)).OnlyEnforceIf(bucket_lit)
                membership_store[bucket_id].append(bucket_lit)
                bucket_lits.append(bucket_lit)

                bucket_region_lits: List[cp_model.IntVar] = []
                for region_index, region in enumerate(bucket_regions.get(bucket_id, [])):
                    region_lit = self.model.NewBoolVar(
                        f"region__{slot.key}__{bucket_id}__{region_index}"
                    )
                    self._add_region_constraints(slot, region, region_lit)
                    bucket_region_lits.append(region_lit)
                if bucket_region_lits:
                    # P0 #6 改造 3 (sum-channel): bucket_lit ∈ {0,1} so the
                    # paired half-reify is equivalent to single channeling.
                    self.model.Add(sum(bucket_region_lits) == bucket_lit)
                else:
                    self.model.Add(bucket_lit == 0)

            if bucket_lits:
                # P0 #6 改造 3 (sum-channel): slot.active ∈ {0,1}.
                self.model.Add(sum(bucket_lits) == slot.active)
            else:
                self.model.Add(slot.active == 0)

    def _create_plain_slot_vars(
        self,
        slot_specs: Sequence[CoordinateSlotSpec],
    ) -> None:
        for slot in slot_specs:
            self._create_base_slot_geometry(slot, optional=False)
            self._slot_binding[slot.key] = {
                "x": int(slot.x.Index()),
                "y": int(slot.y.Index()),
                "mode": int(slot.mode.Index()),
            }
            self._interval_binding[slot.key] = (int(slot.x_interval.Index()), int(slot.y_interval.Index()))

    def _create_mandatory_slot_vars(self) -> None:
        self.mandatory_signature_count_vars = {}
        self._mandatory_signature_membership = {}
        for group in self.owner._mandatory_groups:
            group_id = str(group["group_id"])
            slot_specs = self.mandatory_slots[group_id]
            bucket_defs = list(self.owner._mandatory_signature_buckets.get(group_id, []))
            if self._mandatory_group_uses_signature_table.get(group_id, False):
                self._mandatory_signature_membership[group_id] = {}
                self._create_plain_slot_vars(slot_specs)
            else:
                self._mandatory_signature_membership[group_id] = {
                    str(bucket["bucket_id"]): [] for bucket in bucket_defs
                }
                self._create_signature_slot_vars(
                    slot_specs,
                    bucket_defs=bucket_defs,
                    bucket_regions=self._mandatory_group_bucket_regions.get(group_id, {}),
                    membership_store=self._mandatory_signature_membership[group_id],
                    membership_prefix="is_sig",
                )
            for left_slot, right_slot in zip(slot_specs, slot_specs[1:]):
                self.model.Add(left_slot.order_key <= right_slot.order_key)
                self._coordinate_symmetry_stats["slot_order_key_monotonic_constraints"] = int(
                    self._coordinate_symmetry_stats.get("slot_order_key_monotonic_constraints", 0)
                ) + 1
            self.mandatory_signature_count_vars[group_id] = {}
            for bucket in bucket_defs if not self._mandatory_group_uses_signature_table.get(group_id, False) else []:
                bucket_id = str(bucket["bucket_id"])
                bucket_upper_bound = int(
                    self._mandatory_group_bucket_count_upper_bounds.get(group_id, {}).get(
                        bucket_id,
                        int(group["count"]),
                    )
                )
                count_var = self.model.NewIntVar(
                    0,
                    int(bucket_upper_bound),
                    f"group_signature_count__{group_id}__{bucket_id}",
                )
                self.model.Add(count_var == sum(self._mandatory_signature_membership[group_id][bucket_id]))
                self.mandatory_signature_count_vars[group_id][bucket_id] = count_var

    def _create_required_optional_slot_vars(self) -> None:
        self.required_optional_signature_count_vars = {}
        self._required_optional_signature_membership = {}
        for tpl, slot_specs in sorted(self.required_optional_slots.items()):
            bucket_defs = list(self.owner._required_optional_signature_buckets.get(tpl, []))
            if self._required_optional_uses_signature_table.get(tpl, False):
                self._required_optional_signature_membership[tpl] = {}
                self._create_plain_slot_vars(slot_specs)
            else:
                self._required_optional_signature_membership[tpl] = {
                    str(bucket["bucket_id"]): [] for bucket in bucket_defs
                }
                self._create_signature_slot_vars(
                    slot_specs,
                    bucket_defs=bucket_defs,
                    bucket_regions=self._required_optional_bucket_regions.get(tpl, {}),
                    membership_store=self._required_optional_signature_membership[tpl],
                    membership_prefix="is_req_sig",
                )
            for left_slot, right_slot in zip(slot_specs, slot_specs[1:]):
                self.model.Add(left_slot.order_key <= right_slot.order_key)
                self._coordinate_symmetry_stats["slot_order_key_monotonic_constraints"] = int(
                    self._coordinate_symmetry_stats.get("slot_order_key_monotonic_constraints", 0)
                ) + 1
            self.required_optional_signature_count_vars[tpl] = {}
            for bucket in bucket_defs if not self._required_optional_uses_signature_table.get(tpl, False) else []:
                bucket_id = str(bucket["bucket_id"])
                bucket_upper_bound = int(
                    self._required_optional_bucket_count_upper_bounds.get(tpl, {}).get(
                        bucket_id,
                        len(slot_specs),
                    )
                )
                count_var = self.model.NewIntVar(
                    0,
                    int(bucket_upper_bound),
                    f"required_optional_signature_count__{tpl}__{bucket_id}",
                )
                self.model.Add(count_var == sum(self._required_optional_signature_membership[tpl][bucket_id]))
                self.required_optional_signature_count_vars[tpl][bucket_id] = count_var

    def _create_residual_optional_slot_vars(self) -> None:
        self.residual_optional_signature_count_vars = {}
        self._residual_optional_signature_membership = {}
        for tpl, slot_specs in sorted(self.residual_optional_slots.items()):
            if str(tpl) == "power_pole":
                continue
            bucket_defs = list(self._residual_optional_signature_buckets.get(str(tpl), []))
            use_signature_path = (
                str(tpl) == "protocol_storage_box"
                and bool(bucket_defs)
                and not bool(self._residual_optional_uses_signature_table.get(str(tpl), False))
            )
            if use_signature_path:
                self._residual_optional_signature_membership[str(tpl)] = {
                    str(bucket["bucket_id"]): [] for bucket in bucket_defs
                }
                self._create_optional_signature_slot_vars(
                    slot_specs,
                    bucket_defs=bucket_defs,
                    bucket_regions=self._residual_optional_bucket_regions.get(str(tpl), {}),
                    membership_store=self._residual_optional_signature_membership[str(tpl)],
                    membership_prefix="is_res_sig",
                )
                self.residual_optional_signature_count_vars[str(tpl)] = {}
                for bucket in bucket_defs:
                    bucket_id = str(bucket["bucket_id"])
                    bucket_upper_bound = int(
                        self._residual_optional_bucket_count_upper_bounds.get(str(tpl), {}).get(
                            bucket_id,
                            len(slot_specs),
                        )
                    )
                    count_var = self.model.NewIntVar(
                        0,
                        int(bucket_upper_bound),
                        f"residual_optional_signature_count__{tpl}__{bucket_id}",
                    )
                    self.model.Add(
                        count_var
                        == sum(
                            self._residual_optional_signature_membership[str(tpl)][
                                bucket_id
                            ]
                        )
                    )
                    self.residual_optional_signature_count_vars[str(tpl)][bucket_id] = (
                        count_var
                    )
            else:
                all_domains = list(self._template_full_mode_rect_domains.get(str(tpl), {}).values())
                if not all_domains:
                    continue
                default_domain = min(
                    all_domains,
                    key=lambda domain: (
                        int(domain.mode_id),
                        int(domain.x_min),
                        int(domain.y_min),
                    ),
                )
                for slot in slot_specs:
                    slot.active = self.model.NewBoolVar(f"active__{slot.key}")
                    self._create_base_slot_geometry(slot, optional=True)
                    self.model.Add(slot.mode == int(default_domain.mode_id)).OnlyEnforceIf(slot.active.Not())
                    self.model.Add(slot.x == int(default_domain.x_min)).OnlyEnforceIf(slot.active.Not())
                    self.model.Add(slot.y == int(default_domain.y_min)).OnlyEnforceIf(slot.active.Not())
                    self._slot_binding[slot.key] = {
                        "active": int(slot.active.Index()),
                        "x": int(slot.x.Index()),
                        "y": int(slot.y.Index()),
                        "mode": int(slot.mode.Index()),
                        "order_key": int(slot.order_key.Index()),
                    }
                    self._interval_binding[slot.key] = (
                        int(slot.x_interval.Index()),
                        int(slot.y_interval.Index()),
                    )
            for left_slot, right_slot in zip(slot_specs, slot_specs[1:]):
                self.model.Add(left_slot.active >= right_slot.active)
                self.model.Add(left_slot.order_key <= right_slot.order_key).OnlyEnforceIf(
                    right_slot.active
                )
                self._coordinate_symmetry_stats["slot_order_key_monotonic_constraints"] = int(
                    self._coordinate_symmetry_stats.get("slot_order_key_monotonic_constraints", 0)
                ) + 1

    def _power_pole_shell_payload(self) -> Dict[str, Any]:
        return {
            "pair_count": int(len(self._power_pole_shell_lookup_pairs)),
            "pairs": copy.deepcopy(self._power_pole_shell_lookup_pairs),
        }

    def _create_power_pole_family_literals(
        self,
        slot: CoordinateSlotSpec,
    ) -> Dict[int, cp_model.IntVar]:
        family_lits_by_int: Dict[int, cp_model.IntVar] = {}
        for family_int, family_name in self._power_pole_family_name_by_int.items():
            family_lit = self.model.NewBoolVar(f"is_family__{slot.key}__{family_name}")
            self.model.Add(slot.family == int(family_int)).OnlyEnforceIf(family_lit)
            self.model.Add(slot.family != int(family_int)).OnlyEnforceIf(family_lit.Not())
            self._power_pole_family_membership[family_name].append(family_lit)
            family_lits_by_int[int(family_int)] = family_lit
        return family_lits_by_int

    def _power_pole_family_pose_tuple_rows_for_required_slots(self) -> List[Tuple[int, int, int, int]]:
        rows: List[Tuple[int, int, int, int]] = []
        for pose_idx, pose_tuple in sorted(self._template_pose_tuple_by_idx.get("power_pole", {}).items()):
            family_id = self._power_pole_family_id_by_pose_idx.get(int(pose_idx))
            if family_id is None:
                continue
            rows.append(
                (
                    int(pose_tuple[0]),
                    int(pose_tuple[1]),
                    int(pose_tuple[2]),
                    int(family_id),
                )
            )
        return rows

    def _slot_active_lookup_value(self, slot: CoordinateSlotSpec) -> cp_model.LinearExpr:
        if slot.active is not None:
            return slot.active
        return self.model.NewConstant(1)

    def _all_power_pole_slots(self) -> List[CoordinateSlotSpec]:
        pole_slots: List[CoordinateSlotSpec] = []
        pole_slots.extend(self.required_optional_slots.get("power_pole", []))
        pole_slots.extend(self.residual_optional_slots.get("power_pole", []))
        return [slot for slot in pole_slots if slot.x is not None and slot.y is not None]

    def _attach_required_power_pole_family_channels(self) -> None:
        required_pole_slots = list(self.required_optional_slots.get("power_pole", []))
        if not required_pole_slots:
            return
        if not self._power_pole_family_name_by_int:
            # There is no capacity-family semantic channel to attach when power
            # coverage is explicitly skipped or when the model has no powered
            # demand at all.  Fixed required poles are still real geometry slots;
            # forcing an empty family table here would reject those legal
            # geometry-only configurations before the relevant witness/capacity
            # constraints even exist.
            return
        sentinel_family = int(len(self._power_pole_family_name_by_int))
        tuple_rows = self._power_pole_family_pose_tuple_rows_for_required_slots()
        for slot in required_pole_slots:
            if slot.x is None or slot.y is None or slot.mode is None:
                # Empty-domain required slots have already made the model infeasible
                # in _create_base_slot_geometry; there is no live pole channel to add.
                continue
            slot.family = self.model.NewIntVar(
                0,
                max(0, sentinel_family - 1),
                f"family__{slot.key}",
            )
            if tuple_rows:
                self.model.AddAllowedAssignments(
                    [slot.x, slot.y, slot.mode, slot.family],
                    tuple_rows,
                )
            else:
                self.model.Add(0 == 1)
            self._slot_binding.setdefault(slot.key, {})["family"] = int(slot.family.Index())
            self._create_power_pole_family_literals(slot)

    def _add_power_pole_linear_shell_lookup_constraints(
        self,
        *,
        slot: CoordinateSlotSpec,
        d_lo: cp_model.IntVar,
        d_hi: cp_model.IntVar,
        sentinel_family: int,
        family_lits_by_int: Mapping[int, cp_model.IntVar],
    ) -> None:
        rows_by_family: Dict[int, List[Tuple[int, int]]] = defaultdict(list)
        for d_lo_value, d_hi_value, family_id in self._power_pole_shell_lookup_rows:
            rows_by_family[int(family_id)].append((int(d_lo_value), int(d_hi_value)))
        stats = self._power_family_lookup_encoding_stats
        stats["slot_count"] = int(stats.get("slot_count", 0)) + 1
        self.model.Add(slot.family <= int(sentinel_family) - 1).OnlyEnforceIf(slot.active)
        stats["linear_guard_constraint_count"] = int(
            stats.get("linear_guard_constraint_count", 0)
        ) + 1
        shape_counts = dict(stats.get("shape_counts", {}) or {})
        for family_id, lit_var in sorted(family_lits_by_int.items()):
            rows = rows_by_family.get(int(family_id), [])
            if not rows:
                continue
            payload = add_family_shell_guard_constraints(
                self.model,
                lit_var=lit_var,
                d_lo_var=d_lo,
                d_hi_var=d_hi,
                rows=rows,
            )
            shape_kind = str(payload.get("shape", {}).get("kind", "unknown"))
            shape_counts[shape_kind] = int(shape_counts.get(shape_kind, 0)) + 1
            stats["family_lit_count"] = int(stats.get("family_lit_count", 0)) + 1
            stats["linear_guard_constraint_count"] = int(
                stats.get("linear_guard_constraint_count", 0)
            ) + int(payload.get("linear_constraint_count", 0))
            stats["fallback_table_constraint_count"] = int(
                stats.get("fallback_table_constraint_count", 0)
            ) + int(payload.get("fallback_table_constraint_count", 0))
            stats["fallback_table_row_count"] = int(
                stats.get("fallback_table_row_count", 0)
            ) + int(payload.get("fallback_table_row_count", 0))
        stats["shape_counts"] = dict(sorted(shape_counts.items()))

    def _add_power_pole_shell_pair_index_lookup_constraints(
        self,
        *,
        slot: CoordinateSlotSpec,
        d_lo: cp_model.IntVar,
        d_hi: cp_model.IntVar,
        sentinel_family: int,
    ) -> None:
        pair_to_family: Dict[Tuple[int, int], int] = {}
        for d_lo_value, d_hi_value, family_id in self._power_pole_shell_lookup_rows:
            pair = (int(d_lo_value), int(d_hi_value))
            existing = pair_to_family.get(pair)
            if existing is not None and int(existing) != int(family_id):
                raise ValueError(
                    "Cannot build shell_pair_index family lookup: shell pair "
                    f"{pair!r} maps to both family {existing} and {family_id}."
                )
            pair_to_family[pair] = int(family_id)

        family_by_pair = [
            int(family_id) for _pair, family_id in sorted(pair_to_family.items())
        ]
        shell_pair_rows = [
            [int(pair[0]), int(pair[1]), int(pair_index)]
            for pair_index, (pair, _family_id) in enumerate(sorted(pair_to_family.items()))
        ]
        sentinel_pair_index = int(len(family_by_pair))
        shell_pair_idx = self.model.NewIntVar(
            0,
            max(0, sentinel_pair_index),
            f"shell_pair_idx__{slot.key}",
        )
        if shell_pair_rows:
            self.model.AddAllowedAssignments(
                [d_lo, d_hi, shell_pair_idx],
                shell_pair_rows,
            ).OnlyEnforceIf(slot.active)
            self.model.Add(shell_pair_idx <= sentinel_pair_index - 1).OnlyEnforceIf(
                slot.active
            )
        self.model.Add(shell_pair_idx == sentinel_pair_index).OnlyEnforceIf(
            slot.active.Not()
        )
        self.model.AddElement(
            shell_pair_idx,
            list(family_by_pair) + [int(sentinel_family)],
            slot.family,
        )

        stats = self._power_family_lookup_encoding_stats
        stats["slot_count"] = int(stats.get("slot_count", 0)) + 1
        stats["shell_pair_index_var_count"] = int(
            stats.get("shell_pair_index_var_count", 0)
        ) + 1
        stats["shell_pair_table_constraint_count"] = int(
            stats.get("shell_pair_table_constraint_count", 0)
        ) + (1 if shell_pair_rows else 0)
        stats["shell_pair_table_row_count"] = int(
            stats.get("shell_pair_table_row_count", 0)
        ) + int(len(shell_pair_rows))
        stats["shell_pair_element_constraint_count"] = int(
            stats.get("shell_pair_element_constraint_count", 0)
        ) + 1
        stats["shell_pair_active_bound_constraint_count"] = int(
            stats.get("shell_pair_active_bound_constraint_count", 0)
        ) + (2 if shell_pair_rows else 1)

    def _add_power_pole_shell_distance_constraints(
        self,
        *,
        slot: CoordinateSlotSpec,
        pole_domain: ModeRectDomain,
        dx: cp_model.IntVar,
        dy: cp_model.IntVar,
    ) -> None:
        stats = self._power_pole_shell_distance_encoding_stats
        stats["slot_count"] = int(stats.get("slot_count", 0)) + 1
        if (
            self._power_pole_shell_distance_encoding
            == EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_LINEAR_MINMAX
        ):
            self.model.AddMinEquality(
                dx,
                [
                    slot.x - int(pole_domain.x_min),
                    int(pole_domain.x_max) - slot.x,
                ],
            )
            self.model.AddMinEquality(
                dy,
                [
                    slot.y - int(pole_domain.y_min),
                    int(pole_domain.y_max) - slot.y,
                ],
            )
            stats["linear_minmax_constraint_count"] = int(
                stats.get("linear_minmax_constraint_count", 0)
            ) + 2
            return
        x_lookup = [
            min(int(x_val - pole_domain.x_min), int(pole_domain.x_max - x_val))
            if pole_domain.x_min <= x_val <= pole_domain.x_max
            else 0
            for x_val in range(int(pole_domain.x_max) + 1)
        ]
        y_lookup = [
            min(int(y_val - pole_domain.y_min), int(pole_domain.y_max - y_val))
            if pole_domain.y_min <= y_val <= pole_domain.y_max
            else 0
            for y_val in range(int(pole_domain.y_max) + 1)
        ]
        self.model.AddElement(slot.x, x_lookup, dx)
        self.model.AddElement(slot.y, y_lookup, dy)
        stats["element_constraint_count"] = int(
            stats.get("element_constraint_count", 0)
        ) + 2

    def _create_power_pole_slot_vars(self) -> None:
        self.power_pole_family_count_vars = {}
        self._power_pole_family_membership = {
            family_name: [] for family_name in self._power_pole_family_name_by_int.values()
        }
        pole_domains = dict(self._template_full_mode_rect_domains.get("power_pole", {}))
        if not pole_domains:
            return
        pole_mode_id = min(pole_domains)
        pole_domain = pole_domains[int(pole_mode_id)]
        sentinel_family = len(self._power_pole_family_name_by_int)

        self._attach_required_power_pole_family_channels()

        for slot in self.residual_optional_slots.get("power_pole", []):
            slot.active = self.model.NewBoolVar(f"active__{slot.key}")
            self._create_base_slot_geometry(slot, optional=True)
            slot.family = self.model.NewIntVar(
                0,
                max(0, sentinel_family),
                f"family__{slot.key}",
            )

            self.model.Add(slot.mode == int(pole_mode_id))
            self.model.Add(slot.x == int(pole_domain.x_min)).OnlyEnforceIf(slot.active.Not())
            self.model.Add(slot.y == int(pole_domain.y_min)).OnlyEnforceIf(slot.active.Not())

            family_lits_by_int: Dict[int, cp_model.IntVar] = {}
            if self._power_pole_use_shell_lookup and self._power_pole_shell_lookup_rows:
                dx = self.model.NewIntVar(0, int(pole_domain.x_max - pole_domain.x_min), f"dx__{slot.key}")
                dy = self.model.NewIntVar(0, int(pole_domain.y_max - pole_domain.y_min), f"dy__{slot.key}")
                max_shell = max(int(pole_domain.x_max - pole_domain.x_min), int(pole_domain.y_max - pole_domain.y_min))
                d_lo = self.model.NewIntVar(0, max_shell, f"d_lo__{slot.key}")
                d_hi = self.model.NewIntVar(0, max_shell, f"d_hi__{slot.key}")
                self._add_power_pole_shell_distance_constraints(
                    slot=slot,
                    pole_domain=pole_domain,
                    dx=dx,
                    dy=dy,
                )
                self.model.AddMinEquality(d_lo, [dx, dy])
                self.model.AddMaxEquality(d_hi, [dx, dy])
                if (
                    self._power_family_lookup_encoding
                    == EXACT_POWER_FAMILY_LOOKUP_ENCODING_LINEAR_SHELL_GUARDS
                ):
                    family_lits_by_int = self._create_power_pole_family_literals(slot)
                    self._add_power_pole_linear_shell_lookup_constraints(
                        slot=slot,
                        d_lo=d_lo,
                        d_hi=d_hi,
                        sentinel_family=int(sentinel_family),
                        family_lits_by_int=family_lits_by_int,
                    )
                elif (
                    self._power_family_lookup_encoding
                    == EXACT_POWER_FAMILY_LOOKUP_ENCODING_SHELL_PAIR_INDEX
                ):
                    self._add_power_pole_shell_pair_index_lookup_constraints(
                        slot=slot,
                        d_lo=d_lo,
                        d_hi=d_hi,
                        sentinel_family=int(sentinel_family),
                    )
                else:
                    self.model.AddAllowedAssignments(
                        [d_lo, d_hi, slot.family],
                        list(self._power_pole_shell_lookup_rows),
                    ).OnlyEnforceIf(slot.active)
                    stats = self._power_family_lookup_encoding_stats
                    stats["slot_count"] = int(stats.get("slot_count", 0)) + 1
                    stats["table_constraint_count"] = int(
                        stats.get("table_constraint_count", 0)
                    ) + 1
            elif self._power_pole_family_tuple_rows:
                self.model.AddAllowedAssignments(
                    [slot.x, slot.y, slot.mode, slot.family],
                    list(self._power_pole_family_tuple_rows),
                ).OnlyEnforceIf(slot.active)
            else:
                self.model.Add(slot.family == 0).OnlyEnforceIf(slot.active)
            self.model.Add(slot.family == int(sentinel_family)).OnlyEnforceIf(slot.active.Not())

            self._slot_binding[slot.key] = {
                "active": int(slot.active.Index()),
                "x": int(slot.x.Index()),
                "y": int(slot.y.Index()),
                "mode": int(slot.mode.Index()),
                "family": int(slot.family.Index()),
            }
            self._interval_binding[slot.key] = (int(slot.x_interval.Index()), int(slot.y_interval.Index()))

            if not family_lits_by_int:
                self._create_power_pole_family_literals(slot)

        pole_slots = self.residual_optional_slots.get("power_pole", [])
        for left_slot, right_slot in zip(pole_slots, pole_slots[1:]):
            self.model.Add(left_slot.active >= right_slot.active)
            self.model.Add(left_slot.family <= right_slot.family)
            same_family = self.model.NewBoolVar(
                f"same_family__{left_slot.key}__{right_slot.key}"
            )
            self.model.Add(left_slot.family == right_slot.family).OnlyEnforceIf(same_family)
            self.model.Add(left_slot.family != right_slot.family).OnlyEnforceIf(same_family.Not())
            self.model.Add(left_slot.order_key <= right_slot.order_key).OnlyEnforceIf(same_family)
            self._coordinate_symmetry_stats["power_pole_family_order_constraints"] = int(
                self._coordinate_symmetry_stats.get("power_pole_family_order_constraints", 0)
            ) + 1

        for family_name, members in sorted(self._power_pole_family_membership.items()):
            count_var_upper_bound = int(self._power_pole_family_count_upper_bound(family_name))
            count_var = self.model.NewIntVar(
                0,
                int(count_var_upper_bound),
                f"power_pole_family_count__{family_name}",
            )
            self.model.Add(count_var == sum(members))
            self.power_pole_family_count_vars[family_name] = count_var

    def build(self) -> None:
        # PROJECT_LOCK L4a: 旧 EXACT_POWER_PLACEMENT_SUBPROBLEM 在 certified mode
        # 必须 fail-closed. 它会从 master 拿走 power_pole slot, 让 downstream cut
        # 无法 resolve runtime literal. 新路径用 EXACT_LAZY_POWER_COMPLETION (L4b).
        # forensic test (test_power_placement_subproblem.py / test_power_witness_cut_dilution.py)
        # 文档 PoC 时代的 bug, 用 EXACT_POWER_PLACEMENT_SUBPROBLEM_ALLOW_FORENSIC_TEST
        # 显式 opt-in 绕开 L4a, production runbook 禁用此 bypass.
        if (
            self._delegate_power_placement_to_subproblem()
            and str(getattr(self.owner, "solve_mode", "")) == "certified_exact"
            and os.environ.get(
                "EXACT_POWER_PLACEMENT_SUBPROBLEM_ALLOW_FORENSIC_TEST", ""
            ).strip().lower() not in {"1", "true", "yes", "on"}
        ):
            raise RuntimeError(
                "PROJECT_LOCK L4a: EXACT_POWER_PLACEMENT_SUBPROBLEM is forbidden "
                "in certified_exact mode. Use EXACT_LAZY_POWER_COMPLETION instead."
            )
        self._create_mandatory_slot_vars()
        self._create_required_optional_slot_vars()
        self._create_residual_optional_slot_vars()
        self._create_power_pole_slot_vars()
        self._add_coordinate_symmetry_breaking()
        if self._core_x_intervals:
            self.model.AddNoOverlap2D(self._core_x_intervals, self._core_y_intervals)
        self._add_ghost_constraints()
        lazy_completion = self._lazy_power_completion_enabled()
        if (
            not self.owner.skip_power_coverage
            and not self._delegate_power_placement_to_subproblem()
            and not lazy_completion
        ):
            self._add_geometric_power_coverage_constraints()
        elif lazy_completion:
            # L4b: 留 pole slot, 跳 coverage witness. completion 由 subproblem 接管.
            self.owner.build_stats["power_coverage"] = {
                "representation": "lazy_power_completion_v1",
                "master_constraints": 0,
                "master_witness_vars": 0,
                "power_pole_slots_materialized": bool(
                    self._all_power_pole_slots()
                ),
            }
        elif self._delegate_power_placement_to_subproblem():
            self.owner.build_stats["power_coverage"] = {
                "representation": "delegated_power_subproblem_v1",
                "master_constraints": 0,
            }
        self._add_global_valid_inequalities()
        self._add_search_guidance()
        self._finalize_build_stats()

    def _bind_slot_specs(
        self,
        slot_specs: Iterable[CoordinateSlotSpec],
        binding: Mapping[str, Dict[str, int]],
        interval_binding: Mapping[str, Tuple[int, int]],
    ) -> None:
        for slot in slot_specs:
            slot_binding = dict(binding[str(slot.key)])
            if "active" in slot_binding:
                slot.active = self.model.GetBoolVarFromProtoIndex(int(slot_binding["active"]))
            slot.x = self.model.GetIntVarFromProtoIndex(int(slot_binding["x"]))
            slot.y = self.model.GetIntVarFromProtoIndex(int(slot_binding["y"]))
            slot.mode = self.model.GetIntVarFromProtoIndex(int(slot_binding["mode"]))
            if "order_key" in slot_binding:
                slot.order_key = self.model.GetIntVarFromProtoIndex(int(slot_binding["order_key"]))
            if "signature" in slot_binding:
                slot.signature = self.model.GetIntVarFromProtoIndex(int(slot_binding["signature"]))
            if "family" in slot_binding:
                slot.family = self.model.GetIntVarFromProtoIndex(int(slot_binding["family"]))
            x_iv_idx, y_iv_idx = interval_binding[str(slot.key)]
            slot.x_interval = self.model.GetIntervalVarFromProtoIndex(int(x_iv_idx))
            slot.y_interval = self.model.GetIntervalVarFromProtoIndex(int(y_iv_idx))

    def bind_from_core(self, coordinate_binding: Mapping[str, Any]) -> None:
        self._slot_binding = {
            str(k): {str(inner_k): int(inner_v) for inner_k, inner_v in dict(v).items()}
            for k, v in dict(coordinate_binding.get("slot_binding", {})).items()
        }
        self._interval_binding = {
            str(k): (int(v[0]), int(v[1]))
            for k, v in dict(coordinate_binding.get("interval_binding", {})).items()
        }
        for slot_specs in [*self.mandatory_slots.values(), *self.required_optional_slots.values(), *self.residual_optional_slots.values()]:
            self._bind_slot_specs(slot_specs, self._slot_binding, self._interval_binding)
        self.mandatory_signature_count_vars = {
            str(group_id): {
                str(bucket_id): self.model.GetIntVarFromProtoIndex(int(proto_idx))
                for bucket_id, proto_idx in dict(bucket_map).items()
            }
            for group_id, bucket_map in dict(coordinate_binding.get("mandatory_signature_count_vars", {})).items()
        }
        self.required_optional_signature_count_vars = {
            str(tpl): {
                str(bucket_id): self.model.GetIntVarFromProtoIndex(int(proto_idx))
                for bucket_id, proto_idx in dict(bucket_map).items()
            }
            for tpl, bucket_map in dict(coordinate_binding.get("required_optional_signature_count_vars", {})).items()
        }
        self.residual_optional_signature_count_vars = {
            str(tpl): {
                str(bucket_id): self.model.GetIntVarFromProtoIndex(int(proto_idx))
                for bucket_id, proto_idx in dict(bucket_map).items()
            }
            for tpl, bucket_map in dict(
                coordinate_binding.get("residual_optional_signature_count_vars", {})
            ).items()
        }
        self.power_pole_family_count_vars = {
            str(family_name): self.model.GetIntVarFromProtoIndex(int(proto_idx))
            for family_name, proto_idx in dict(coordinate_binding.get("power_pole_family_count_vars", {})).items()
        }
        self._core_x_intervals = []
        self._core_y_intervals = []
        for slot_specs in [*self.mandatory_slots.values(), *self.required_optional_slots.values(), *self.residual_optional_slots.values()]:
            for slot in slot_specs:
                if slot.x_interval is not None and slot.y_interval is not None:
                    self._core_x_intervals.append(slot.x_interval)
                    self._core_y_intervals.append(slot.y_interval)

    def export_core_binding(self) -> Dict[str, Any]:
        return {
            "slot_binding": {
                str(slot_key): {
                    str(binding_name): int(binding_index)
                    for binding_name, binding_index in binding.items()
                }
                for slot_key, binding in self._slot_binding.items()
            },
            "interval_binding": {
                str(slot_key): (int(binding[0]), int(binding[1]))
                for slot_key, binding in self._interval_binding.items()
            },
            "mandatory_signature_count_vars": {
                str(group_id): {str(bucket_id): int(var.Index()) for bucket_id, var in bucket_map.items()}
                for group_id, bucket_map in self.mandatory_signature_count_vars.items()
            },
            "required_optional_signature_count_vars": {
                str(tpl): {str(bucket_id): int(var.Index()) for bucket_id, var in bucket_map.items()}
                for tpl, bucket_map in self.required_optional_signature_count_vars.items()
            },
            "residual_optional_signature_count_vars": {
                str(tpl): {str(bucket_id): int(var.Index()) for bucket_id, var in bucket_map.items()}
                for tpl, bucket_map in self.residual_optional_signature_count_vars.items()
            },
            "power_pole_family_count_vars": {
                str(family_name): int(var.Index()) for family_name, var in self.power_pole_family_count_vars.items()
            },
        }

    def _add_coordinate_symmetry_breaking(self) -> None:
        stats = self._coordinate_symmetry_stats
        stats["enabled"] = bool(getattr(self.owner, "enable_symmetry_breaking", True))
        if not bool(stats["enabled"]):
            self.owner.build_stats["coordinate_symmetry"] = copy.deepcopy(stats)
            return

        mandatory_signature_monotonic_constraints = 0
        for group in self.owner._mandatory_groups:
            group_id = str(group["group_id"])
            slot_specs = list(self.mandatory_slots.get(group_id, []))
            if len(slot_specs) < 2 or self._mandatory_group_uses_signature_table.get(group_id, False):
                continue
            mandatory_signature_monotonic_constraints += (
                self._add_signature_monotonic_constraints_if_compatible(
                    slot_specs,
                    bucket_defs=list(
                        self.owner._mandatory_signature_buckets.get(group_id, [])
                    ),
                    allowed_pose_indices=self.owner._candidate_pose_indices_for_group(group),
                    skipped_stats_key=(
                        "mandatory_signature_monotonic_skipped_incompatible_order"
                    ),
                )
            )

        required_optional_signature_monotonic_constraints = 0
        for tpl, slot_specs in sorted(self.required_optional_slots.items()):
            ordered_slot_specs = list(slot_specs)
            if len(ordered_slot_specs) < 2 or self._required_optional_uses_signature_table.get(str(tpl), False):
                continue
            required_optional_signature_monotonic_constraints += (
                self._add_signature_monotonic_constraints_if_compatible(
                    ordered_slot_specs,
                    bucket_defs=list(
                        self.owner._required_optional_signature_buckets.get(str(tpl), [])
                    ),
                    allowed_pose_indices=range(len(self.owner.facility_pools.get(str(tpl), []))),
                    skipped_stats_key=(
                        "required_optional_signature_monotonic_skipped_incompatible_order"
                    ),
                )
            )

        stats["mandatory_signature_monotonic_constraints"] = int(
            mandatory_signature_monotonic_constraints
        )
        stats["required_optional_signature_monotonic_constraints"] = int(
            required_optional_signature_monotonic_constraints
        )
        residual_optional_signature_monotonic_constraints = 0
        for tpl, slot_specs in sorted(self.residual_optional_slots.items()):
            if str(tpl) != "protocol_storage_box":
                continue
            ordered_slot_specs = list(slot_specs)
            if len(ordered_slot_specs) < 2 or self._residual_optional_uses_signature_table.get(
                str(tpl),
                False,
            ):
                continue
            residual_optional_signature_monotonic_constraints += (
                self._add_signature_monotonic_constraints_if_compatible(
                    ordered_slot_specs,
                    bucket_defs=list(
                        self._residual_optional_signature_buckets.get(str(tpl), [])
                    ),
                    allowed_pose_indices=range(len(self.owner.facility_pools.get(str(tpl), []))),
                    skipped_stats_key=(
                        "residual_optional_signature_monotonic_skipped_incompatible_order"
                    ),
                )
            )
        stats["residual_optional_signature_monotonic_constraints"] = int(
            residual_optional_signature_monotonic_constraints
        )
        self.owner.build_stats["coordinate_symmetry"] = copy.deepcopy(stats)

    def _add_ghost_constraints(self) -> None:
        self.owner._ghost_domains.clear()
        self.owner.u_vars.clear()
        self._ghost_x_intervals = []
        self._ghost_y_intervals = []
        self._ghost_anchor_power_capacity_screen_stats = {
            "enabled": bool(self.owner.ghost_rect),
            "explicit_u_conditioning": False,
            "evaluated_placements": 0,
            "disabled_placements": 0,
            "surviving_placements": 0,
            "conditioned_family_upper_bound_constraints": 0,
            "family_reduction_anchor_count": 0,
            "template_fail_counts": {},
        }
        self._ghost_anchor_signature_bucket_tightening_stats = {
            "enabled": bool(self.owner.ghost_rect),
            "explicit_u_conditioning": False,
            "evaluated_placements": 0,
            "conditioned_mandatory_bucket_constraints": 0,
            "conditioned_required_optional_bucket_constraints": 0,
            "signature_reduction_anchor_count": 0,
        }
        self._ghost_anchor_residual_signature_bucket_tightening_stats = {
            "enabled": bool(self.owner.ghost_rect),
            "explicit_u_conditioning": False,
            "evaluated_placements": 0,
            "conditioned_residual_bucket_constraints": 0,
            "signature_reduction_anchor_count": 0,
        }
        ghost_rect = self.owner.ghost_rect
        if not ghost_rect:
            self.owner.build_stats["ghost_rect"] = {"enabled": False}
            return

        ghost_w, ghost_h = int(ghost_rect[0]), int(ghost_rect[1])
        if ghost_w > self.grid_w or ghost_h > self.grid_h:
            self.model.Add(0 == 1)
            self.owner.build_stats["ghost_rect"] = {
                "enabled": True,
                "placements": 0,
                "reason": "rectangle larger than grid",
            }
            return

        anchor_filter = getattr(self.owner, "ghost_anchor_filter", None)
        anchor_filter_skipped = 0
        for anchor_x in range(self.grid_w - ghost_w + 1):
            for anchor_y in range(self.grid_h - ghost_h + 1):
                if anchor_filter is not None and (int(anchor_x), int(anchor_y)) not in anchor_filter:
                    anchor_filter_skipped += 1
                    continue
                rect_idx = len(self.owner._ghost_domains)
                cells = [
                    (anchor_x + dx, anchor_y + dy)
                    for dx in range(ghost_w)
                    for dy in range(ghost_h)
                ]
                var = self.model.NewBoolVar(f"ghost__{anchor_x}_{anchor_y}_{ghost_w}_{ghost_h}")
                self.owner.u_vars[rect_idx] = var
                self.owner._ghost_domains.append({"anchor": {"x": anchor_x, "y": anchor_y}, "cells": cells})
                x_interval = self.model.NewOptionalIntervalVar(
                    anchor_x,
                    ghost_w,
                    anchor_x + ghost_w,
                    var,
                    f"ghost_x_iv__{anchor_x}_{anchor_y}_{ghost_w}_{ghost_h}",
                )
                y_interval = self.model.NewOptionalIntervalVar(
                    anchor_y,
                    ghost_h,
                    anchor_y + ghost_h,
                    var,
                    f"ghost_y_iv__{anchor_x}_{anchor_y}_{ghost_w}_{ghost_h}",
                )
                self._ghost_x_intervals.append(x_interval)
                self._ghost_y_intervals.append(y_interval)

        if not self.owner.u_vars:
            self.model.Add(0 == 1)
            self.owner.build_stats["ghost_rect"] = {
                "enabled": True,
                "placements": 0,
                "reason": (
                    "anchor_filter_empty"
                    if anchor_filter is not None and not anchor_filter
                    else "anchor_filter_excludes_all_anchors"
                ),
                "size": {"w": ghost_w, "h": ghost_h},
                "anchor_filter_applied": True,
                "anchor_filter_skipped": int(anchor_filter_skipped),
            }
            return
        self._apply_ghost_anchor_power_capacity_screen()
        self._apply_ghost_anchor_signature_bucket_tightening()
        self._apply_ghost_anchor_residual_signature_bucket_tightening()
        self.model.AddExactlyOne(list(self.owner.u_vars.values()))
        self.model.AddNoOverlap2D(
            [*self._core_x_intervals, *self._ghost_x_intervals],
            [*self._core_y_intervals, *self._ghost_y_intervals],
        )
        self.owner.build_stats["ghost_rect"] = {
            "enabled": True,
            "placements": len(self.owner._ghost_domains),
            "size": {"w": ghost_w, "h": ghost_h},
            "power_capacity_screened_disabled_placements": int(
                self._ghost_anchor_power_capacity_screen_stats.get("disabled_placements", 0)
            ),
            "power_capacity_screened_surviving_placements": int(
                self._ghost_anchor_power_capacity_screen_stats.get("surviving_placements", 0)
            ),
            "signature_tightening_anchor_reductions": int(
                self._ghost_anchor_signature_bucket_tightening_stats.get(
                    "signature_reduction_anchor_count",
                    0,
                )
            ),
            "anchor_filter_applied": anchor_filter is not None,
            "anchor_filter_skipped": int(anchor_filter_skipped),
        }

    def _apply_ghost_anchor_power_capacity_screen(self) -> None:
        family_bound_formulation = resolve_ghost_conditioned_family_bound_formulation()
        shape_instrumentation_enabled = (
            resolve_ghost_via_pole_shape_instrumentation_enabled()
        )
        shape_instrumentation: Optional[Dict[str, Any]] = None
        if shape_instrumentation_enabled:
            shape_instrumentation = {
                "enabled": True,
                "phase_seconds": {
                    "pole_cell_index": 0.0,
                    "per_anchor_blocked_counts": 0.0,
                    "per_anchor_family_reductions": 0.0,
                },
                "blocked_pose_indices_histogram": {},
                "blocked_family_count_histogram": {},
                "family_reduction_count_histogram": {},
                "top_family_reduction_anchors": [],
            }
        screen_stats: Dict[str, Any] = {
            "enabled": bool(self.owner.ghost_rect),
            "explicit_u_conditioning": False,
            "evaluated_placements": int(len(self.owner._ghost_domains)),
            "disabled_placements": 0,
            "surviving_placements": int(len(self.owner._ghost_domains)),
            "conditioned_family_upper_bound_constraints": 0,
            "family_reduction_anchor_count": 0,
            "template_fail_counts": {},
            "conditioned_family_bound_formulation": str(family_bound_formulation),
        }

        def _store_screen_stats() -> None:
            if shape_instrumentation is not None:
                screen_stats["shape_instrumentation"] = copy.deepcopy(
                    shape_instrumentation
                )
            self._ghost_anchor_power_capacity_screen_stats = screen_stats
            self.owner.build_stats.setdefault("global_valid_inequalities", {})[
                "ghost_aware_via_pole_feasibility"
            ] = copy.deepcopy(screen_stats)

        def _increment_shape_histogram(name: str, value: int) -> None:
            if shape_instrumentation is None:
                return
            histogram = shape_instrumentation[name]
            key = str(int(value))
            histogram[key] = int(histogram.get(key, 0)) + 1

        if not self.owner.ghost_rect or not self.owner.u_vars:
            screen_stats["reason"] = "ghost_disabled"
            if shape_instrumentation is not None:
                shape_instrumentation["reason"] = "ghost_disabled"
            _store_screen_stats()
            return

        powered_template_demands = {
            str(tpl): int(demand)
            for tpl, demand in sorted(self.owner._exact_powered_template_demands().items())
            if int(demand) > 0
        }
        if not powered_template_demands:
            screen_stats["reason"] = "no_powered_template_demands"
            if shape_instrumentation is not None:
                shape_instrumentation["reason"] = "no_powered_template_demands"
            _store_screen_stats()
            return

        pole_cells_by_pose = {
            int(pose_idx): frozenset(cells)
            for pose_idx, cells in self.owner._pose_cells_by_template_pose.get(
                "power_pole", {}
            ).items()
        }
        if not pole_cells_by_pose or not self._power_pole_family_coefficients:
            screen_stats["reason"] = "no_power_pole_capacity_families"
            if shape_instrumentation is not None:
                shape_instrumentation["reason"] = "no_power_pole_capacity_families"
            _store_screen_stats()
            return

        pole_cell_index_start = (
            time.perf_counter() if shape_instrumentation is not None else 0.0
        )
        pole_indices_by_cell: DefaultDict[Tuple[int, int], List[int]] = defaultdict(list)
        for pose_idx, pole_cells in pole_cells_by_pose.items():
            for cell in pole_cells:
                pole_indices_by_cell[(int(cell[0]), int(cell[1]))].append(int(pose_idx))
        if shape_instrumentation is not None:
            shape_instrumentation["phase_seconds"]["pole_cell_index"] = round(
                time.perf_counter() - pole_cell_index_start,
                6,
            )

        family_name_by_pose: Dict[int, str] = {}
        for pose_idx in sorted(pole_cells_by_pose):
            family_id = self._power_pole_family_id_by_pose_idx.get(int(pose_idx))
            if family_id is None:
                continue
            family_name = self._power_pole_family_name_by_int.get(int(family_id))
            if family_name is None:
                continue
            family_name_by_pose[int(pose_idx)] = str(family_name)

        family_sizes = {
            str(family_name): int(size)
            for family_name, size in sorted(self._power_pole_family_pose_counts.items())
        }
        template_fail_counts: DefaultDict[str, int] = defaultdict(int)
        disabled_placements = 0
        conditioned_family_upper_bound_constraints = 0
        family_reduction_anchor_count = 0
        top_family_reduction_anchors: List[Dict[str, Any]] = []

        for rect_idx, domain in enumerate(self.owner._ghost_domains):
            blocked_count_start = (
                time.perf_counter() if shape_instrumentation is not None else 0.0
            )
            blocked_counts: DefaultDict[str, int] = defaultdict(int)
            blocked_pose_indices: Set[int] = set()
            for cell in domain.get("cells", []):
                for pose_idx in pole_indices_by_cell.get((int(cell[0]), int(cell[1])), []):
                    if int(pose_idx) in blocked_pose_indices:
                        continue
                    blocked_pose_indices.add(int(pose_idx))
                    family_name = family_name_by_pose.get(int(pose_idx))
                    if family_name is None:
                        continue
                    blocked_counts[str(family_name)] += 1

            blocked_family_count = sum(
                1 for count in blocked_counts.values() if int(count) > 0
            )
            if shape_instrumentation is not None:
                shape_instrumentation["phase_seconds"][
                    "per_anchor_blocked_counts"
                ] = round(
                    float(
                        shape_instrumentation["phase_seconds"][
                            "per_anchor_blocked_counts"
                        ]
                    )
                    + (time.perf_counter() - blocked_count_start),
                    6,
                )
                _increment_shape_histogram(
                    "blocked_pose_indices_histogram",
                    len(blocked_pose_indices),
                )
                _increment_shape_histogram(
                    "blocked_family_count_histogram",
                    blocked_family_count,
                )

            family_reduction_start = (
                time.perf_counter() if shape_instrumentation is not None else 0.0
            )
            failing_templates: List[str] = []
            for tpl, demand in powered_template_demands.items():
                max_capacity = 0
                for family_name, coefficients in sorted(
                    self._power_pole_family_coefficients.items()
                ):
                    coeff = int(coefficients.get(str(tpl), 0))
                    if coeff <= 0:
                        continue
                    available_count = int(family_sizes.get(str(family_name), 0)) - int(
                        blocked_counts.get(str(family_name), 0)
                    )
                    if available_count > 0:
                        max_capacity += coeff * int(available_count)
                if int(max_capacity) < int(demand):
                    failing_templates.append(str(tpl))
                    template_fail_counts[str(tpl)] += 1

            if failing_templates:
                self.model.Add(self.owner.u_vars[int(rect_idx)] == 0)
                disabled_placements += 1
                domain["screened_by_power_capacity"] = list(sorted(failing_templates))
                if shape_instrumentation is not None:
                    shape_instrumentation["phase_seconds"][
                        "per_anchor_family_reductions"
                    ] = round(
                        float(
                            shape_instrumentation["phase_seconds"][
                                "per_anchor_family_reductions"
                            ]
                        )
                        + (time.perf_counter() - family_reduction_start),
                        6,
                    )
                    _increment_shape_histogram(
                        "family_reduction_count_histogram",
                        0,
                    )
                continue

            family_reductions: Dict[str, int] = {}
            for family_name, count_var in sorted(self.power_pole_family_count_vars.items()):
                family_size = int(family_sizes.get(str(family_name), 0))
                global_upper_bound = int(
                    self._power_pole_family_count_upper_bound(str(family_name))
                )
                if family_size <= 0 or global_upper_bound <= 0:
                    continue
                available_count = int(family_size) - int(blocked_counts.get(str(family_name), 0))
                conditioned_upper_bound = int(min(max(0, available_count), global_upper_bound))
                if conditioned_upper_bound >= global_upper_bound:
                    continue
                if (
                    family_bound_formulation
                    == EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION_ENFORCED
                ):
                    self.model.Add(
                        count_var <= int(conditioned_upper_bound)
                    ).OnlyEnforceIf(self.owner.u_vars[int(rect_idx)])
                else:
                    self.model.Add(
                        count_var
                        <= int(conditioned_upper_bound)
                        + int(global_upper_bound) * (1 - self.owner.u_vars[int(rect_idx)])
                    )
                family_reductions[str(family_name)] = int(conditioned_upper_bound)
                conditioned_family_upper_bound_constraints += 1
            if family_reductions:
                family_reduction_anchor_count += 1
                domain["conditioned_power_pole_family_upper_bounds"] = dict(
                    sorted(family_reductions.items())
                )
            if shape_instrumentation is not None:
                family_reduction_count = len(family_reductions)
                shape_instrumentation["phase_seconds"][
                    "per_anchor_family_reductions"
                ] = round(
                    float(
                        shape_instrumentation["phase_seconds"][
                            "per_anchor_family_reductions"
                        ]
                    )
                    + (time.perf_counter() - family_reduction_start),
                    6,
                )
                _increment_shape_histogram(
                    "family_reduction_count_histogram",
                    family_reduction_count,
                )
                if family_reduction_count:
                    top_family_reduction_anchors.append(
                        {
                            "rect_idx": int(rect_idx),
                            "anchor": copy.deepcopy(domain.get("anchor")),
                            "blocked_pose_indices": int(len(blocked_pose_indices)),
                            "blocked_family_count": int(blocked_family_count),
                            "family_reduction_count": int(family_reduction_count),
                            "family_reductions": dict(sorted(family_reductions.items())),
                        }
                    )

        if shape_instrumentation is not None:
            shape_instrumentation["top_family_reduction_anchors"] = sorted(
                top_family_reduction_anchors,
                key=lambda item: (
                    -int(item["family_reduction_count"]),
                    -int(item["blocked_pose_indices"]),
                    int(item["rect_idx"]),
                ),
            )[:10]

        screen_stats["explicit_u_conditioning"] = True
        screen_stats["disabled_placements"] = int(disabled_placements)
        screen_stats["surviving_placements"] = int(
            max(0, len(self.owner._ghost_domains) - disabled_placements)
        )
        screen_stats["conditioned_family_upper_bound_constraints"] = int(
            conditioned_family_upper_bound_constraints
        )
        screen_stats["family_reduction_anchor_count"] = int(family_reduction_anchor_count)
        screen_stats["template_fail_counts"] = {
            str(tpl): int(count) for tpl, count in sorted(template_fail_counts.items())
        }
        _store_screen_stats()

    def _apply_ghost_anchor_signature_bucket_tightening(self) -> None:
        instrumentation_enabled = (
            resolve_ghost_signature_bucket_tightening_instrumentation_enabled()
        )
        mandatory_region_counting_enabled = (
            resolve_ghost_signature_bucket_mandatory_region_counting_enabled()
        )
        mandatory_region_fallback_instrumentation_enabled = (
            resolve_ghost_signature_bucket_mandatory_region_fallback_instrumentation_enabled()
        )
        template_footprint_support_enabled = (
            resolve_ghost_signature_bucket_template_footprint_support_enabled()
        )
        template_footprint_support_gap_instrumentation_enabled = (
            resolve_ghost_signature_bucket_template_footprint_support_gap_instrumentation_enabled()
        )
        payload_footprint_stability_support_enabled = (
            resolve_ghost_signature_bucket_payload_footprint_stability_support_enabled()
        )
        residual_overlay_instrumentation_requested = (
            resolve_ghost_signature_bucket_residual_overlay_instrumentation_enabled()
        )
        fallback_instrumentation_enabled = bool(
            instrumentation_enabled
            and mandatory_region_counting_enabled
            and mandatory_region_fallback_instrumentation_enabled
        )
        support_gap_instrumentation_enabled = bool(
            fallback_instrumentation_enabled
            and template_footprint_support_enabled
            and template_footprint_support_gap_instrumentation_enabled
        )
        tightening_stats: Dict[str, Any] = {
            "enabled": bool(self.owner.ghost_rect),
            "explicit_u_conditioning": False,
            "evaluated_placements": int(len(self.owner._ghost_domains)),
            "conditioned_mandatory_bucket_constraints": 0,
            "conditioned_required_optional_bucket_constraints": 0,
            "signature_reduction_anchor_count": 0,
        }
        instrumentation: Optional[Dict[str, Any]] = None
        top_slow_entries: List[Dict[str, Any]] = []
        fallback_reason_counts: DefaultDict[str, int] = defaultdict(int)
        top_fallback_entries: List[Dict[str, Any]] = []
        support_gap_reason_counts: DefaultDict[str, int] = defaultdict(int)
        top_support_gap_entries: List[Dict[str, Any]] = []
        top_payload_footprint_stability_entries: List[Dict[str, Any]] = []
        residual_overlay_instrumentation: Optional[Dict[str, Any]] = None
        top_slow_payload_groups: List[Dict[str, Any]] = []
        if instrumentation_enabled:
            instrumentation = {
                "enabled": True,
                "phase_seconds": {
                    "mandatory_payload_build": 0.0,
                    "required_optional_payload_build": 0.0,
                    "per_anchor_mandatory_scan": 0.0,
                    "per_anchor_required_optional_scan": 0.0,
                    "constraint_add": 0.0,
                    "stats_finalize": 0.0,
                },
                "totals": {
                    "evaluated_placements": int(len(self.owner._ghost_domains)),
                    "mandatory_payload_count": 0,
                    "required_optional_payload_count": 0,
                    "mandatory_cells_scanned": 0,
                    "required_optional_cells_scanned": 0,
                    "cells_scanned": 0,
                    "mandatory_pose_hits": 0,
                    "required_optional_pose_hits": 0,
                    "pose_hits": 0,
                    "mandatory_unique_blocked_poses": 0,
                    "required_optional_unique_blocked_poses": 0,
                    "unique_blocked_poses": 0,
                    "mandatory_bucket_reductions": 0,
                    "required_optional_bucket_reductions": 0,
                    "bucket_reductions": 0,
                    "mandatory_constraints_added": 0,
                    "required_optional_constraints_added": 0,
                    "constraints_added": 0,
                    "mandatory_region_counting_attempts": 0,
                    "mandatory_region_counting_used": 0,
                    "mandatory_region_counting_fallbacks": 0,
                    "mandatory_region_rectangles_evaluated": 0,
                    "mandatory_region_overlap_counts": 0,
                    "mandatory_region_counted_blocked_poses": 0,
                    "mandatory_template_footprint_support_attempts": 0,
                    "mandatory_template_footprint_support_used": 0,
                    "mandatory_template_footprint_support_fallbacks": 0,
                },
                "top_slow_entries": [],
            }
            if payload_footprint_stability_support_enabled:
                instrumentation["totals"].update(
                    {
                        "mandatory_payload_footprint_stability_attempts": 0,
                        "mandatory_payload_footprint_stability_used": 0,
                        "mandatory_payload_footprint_stability_fallbacks": 0,
                        "mandatory_payload_footprint_stability_cohorts": 0,
                    }
                )
            if residual_overlay_instrumentation_requested:
                residual_overlay_instrumentation = {
                    "enabled": True,
                    "phase_seconds": {
                        "payload_region_metadata_build_seconds": 0.0,
                        "payload_footprint_cohort_build_seconds": 0.0,
                        "payload_bucket_region_rebuild_seconds": 0.0,
                        "payload_compactness_guard_seconds": 0.0,
                    },
                    "top_slow_payload_groups": [],
                }

        def _fallback_reason_category(reason: Any) -> str:
            normalized = str(reason or "").strip()
            if normalized in {"missing_bucket_regions", "empty_bucket_region"}:
                return "missing_compact_bucket_regions"
            if normalized in {
                "bucket_region_coverage_mismatch",
                "bucket_pose_map_mismatch",
            }:
                return "missing_bucket_region_metadata"
            if normalized == "overlapping_bucket_regions":
                return "overlapping_same_bucket_regions"
            if normalized in {
                "invalid_template_dimensions",
                "unsupported_pose_footprint",
            }:
                return "unsupported_or_missing_template_footprint"
            if normalized == "disabled":
                return "legacy_scan_required_other"
            return "region_counting_guard_rejected"

        def _add_phase_seconds(phase: str, seconds: float) -> None:
            if instrumentation is None:
                return
            instrumentation["phase_seconds"][phase] = float(
                instrumentation["phase_seconds"].get(phase, 0.0) + max(0.0, seconds)
            )

        def _add_total(name: str, value: int) -> None:
            if instrumentation is None:
                return
            instrumentation["totals"][name] = int(
                instrumentation["totals"].get(name, 0) + int(value)
            )

        def _add_residual_overlay_phase_seconds(phase: str, seconds: float) -> None:
            if residual_overlay_instrumentation is None:
                return
            phase_seconds = residual_overlay_instrumentation["phase_seconds"]
            phase_seconds[phase] = float(
                phase_seconds.get(phase, 0.0) + max(0.0, seconds)
            )

        def _record_payload_group_timing(
            *,
            group_id: str,
            template: str,
            pose_count: int,
            bucket_count: int,
            supported: bool,
            reason: Any,
            elapsed_seconds: float,
        ) -> None:
            if residual_overlay_instrumentation is None:
                return
            top_slow_payload_groups.append(
                {
                    "group_id": str(group_id),
                    "template": str(template),
                    "pose_count": int(pose_count),
                    "bucket_count": int(bucket_count),
                    "supported": bool(supported),
                    "reason": str(reason or ""),
                    "elapsed_seconds": float(max(0.0, elapsed_seconds)),
                }
            )

        def _record_slow_entry(
            *,
            kind: str,
            rect_idx: int,
            domain: Mapping[str, Any],
            group_id_or_template: str,
            bucket_id: str,
            scan_count: int,
            reduction_count: int,
            elapsed_seconds: float,
        ) -> None:
            if instrumentation is None:
                return
            anchor = domain.get("anchor", {})
            top_slow_entries.append(
                {
                    "kind": str(kind),
                    "rect_idx": int(rect_idx),
                    "anchor": {
                        "x": int(anchor.get("x", 0)),
                        "y": int(anchor.get("y", 0)),
                    },
                    "group_id_or_template": str(group_id_or_template),
                    "bucket_id": str(bucket_id),
                    "scan_count": int(scan_count),
                    "reduction_count": int(reduction_count),
                    "elapsed_seconds": float(max(0.0, elapsed_seconds)),
                }
            )

        def _record_fallback_entry(
            *,
            rect_idx: int,
            domain: Mapping[str, Any],
            group_id_or_template: str,
            reason: Any,
            legacy_scan_count: int,
            legacy_pose_hits: int,
            elapsed_seconds: float,
        ) -> None:
            if instrumentation is None or not fallback_instrumentation_enabled:
                return
            category = _fallback_reason_category(reason)
            fallback_reason_counts[category] += 1
            anchor = domain.get("anchor", {})
            top_fallback_entries.append(
                {
                    "rect_idx": int(rect_idx),
                    "anchor": {
                        "x": int(anchor.get("x", 0)),
                        "y": int(anchor.get("y", 0)),
                    },
                    "group_id_or_template": str(group_id_or_template),
                    "bucket_id": "__all__",
                    "reason": category,
                    "legacy_scan_count": int(legacy_scan_count),
                    "legacy_pose_hits": int(legacy_pose_hits),
                    "elapsed_seconds": float(max(0.0, elapsed_seconds)),
                }
            )

        def _record_support_gap_entry(
            *,
            rect_idx: int,
            domain: Mapping[str, Any],
            group_id_or_template: str,
            gap: Mapping[str, Any],
            elapsed_seconds: float,
        ) -> None:
            if instrumentation is None or not support_gap_instrumentation_enabled:
                return
            reason = str(gap.get("reason") or "legacy_scan_required_other")
            support_gap_reason_counts[reason] += 1
            anchor = domain.get("anchor", {})
            top_support_gap_entries.append(
                {
                    "rect_idx": int(rect_idx),
                    "anchor": {
                        "x": int(anchor.get("x", 0)),
                        "y": int(anchor.get("y", 0)),
                    },
                    "group_id_or_template": str(group_id_or_template),
                    "bucket_id": str(gap.get("bucket_id") or "__all__"),
                    "reason": reason,
                    "pose_count": int(gap.get("pose_count") or 0),
                    "occupied_cell_count": int(gap.get("occupied_cell_count") or 0),
                    "footprint_bounds_when_available": copy.deepcopy(
                        gap.get("footprint_bounds_when_available")
                    ),
                    "elapsed_seconds": float(max(0.0, elapsed_seconds)),
                }
            )

        def _record_payload_footprint_stability_entry(
            *,
            rect_idx: int,
            domain: Mapping[str, Any],
            group_id_or_template: str,
            cohort_count: int,
            rectangles_evaluated: int,
            counted_blocked_poses: int,
            elapsed_seconds: float,
        ) -> None:
            if instrumentation is None or not payload_footprint_stability_support_enabled:
                return
            anchor = domain.get("anchor", {})
            top_payload_footprint_stability_entries.append(
                {
                    "rect_idx": int(rect_idx),
                    "anchor": {
                        "x": int(anchor.get("x", 0)),
                        "y": int(anchor.get("y", 0)),
                    },
                    "group_id_or_template": str(group_id_or_template),
                    "cohort_count": int(cohort_count),
                    "rectangles_evaluated": int(rectangles_evaluated),
                    "counted_blocked_poses": int(counted_blocked_poses),
                    "elapsed_seconds": float(max(0.0, elapsed_seconds)),
                }
            )

        def _finalize_instrumentation(reason: Optional[str] = None) -> None:
            if instrumentation is None:
                return
            finalize_started = time.perf_counter()
            if reason is not None:
                instrumentation["reason"] = str(reason)
            totals = instrumentation["totals"]
            totals["mandatory_payload_count"] = int(len(mandatory_payloads))
            totals["required_optional_payload_count"] = int(
                len(required_optional_payloads)
            )
            totals["cells_scanned"] = int(
                totals.get("mandatory_cells_scanned", 0)
                + totals.get("required_optional_cells_scanned", 0)
            )
            totals["pose_hits"] = int(
                totals.get("mandatory_pose_hits", 0)
                + totals.get("required_optional_pose_hits", 0)
            )
            totals["unique_blocked_poses"] = int(
                totals.get("mandatory_unique_blocked_poses", 0)
                + totals.get("required_optional_unique_blocked_poses", 0)
            )
            totals["bucket_reductions"] = int(
                totals.get("mandatory_bucket_reductions", 0)
                + totals.get("required_optional_bucket_reductions", 0)
            )
            totals["constraints_added"] = int(
                totals.get("mandatory_constraints_added", 0)
                + totals.get("required_optional_constraints_added", 0)
            )
            instrumentation["top_slow_entries"] = sorted(
                top_slow_entries,
                key=lambda item: (
                    -float(item["elapsed_seconds"]),
                    str(item["kind"]),
                    int(item["rect_idx"]),
                    str(item["group_id_or_template"]),
                    str(item["bucket_id"]),
                ),
            )[:10]
            if fallback_instrumentation_enabled:
                instrumentation["fallback_reasons"] = {
                    str(reason): int(count)
                    for reason, count in sorted(fallback_reason_counts.items())
                }
                instrumentation["top_fallback_entries"] = sorted(
                    top_fallback_entries,
                    key=lambda item: (
                        -float(item["elapsed_seconds"]),
                        str(item["reason"]),
                        int(item["rect_idx"]),
                        str(item["group_id_or_template"]),
                        str(item["bucket_id"]),
                    ),
                )[:10]
            if support_gap_instrumentation_enabled:
                instrumentation["template_footprint_support_gap_reasons"] = {
                    str(reason): int(count)
                    for reason, count in sorted(support_gap_reason_counts.items())
                }
                instrumentation["top_template_footprint_gap_entries"] = sorted(
                    top_support_gap_entries,
                    key=lambda item: (
                        -float(item["elapsed_seconds"]),
                        str(item["reason"]),
                        int(item["rect_idx"]),
                        str(item["group_id_or_template"]),
                        str(item["bucket_id"]),
                    ),
                )[:10]
            if payload_footprint_stability_support_enabled:
                instrumentation["top_payload_footprint_stability_entries"] = sorted(
                    top_payload_footprint_stability_entries,
                    key=lambda item: (
                        -float(item["elapsed_seconds"]),
                        int(item["rect_idx"]),
                        str(item["group_id_or_template"]),
                        int(item["cohort_count"]),
                    ),
                )[:10]
            if residual_overlay_instrumentation is not None:
                residual_overlay_instrumentation["top_slow_payload_groups"] = sorted(
                    top_slow_payload_groups,
                    key=lambda item: (
                        -float(item["elapsed_seconds"]),
                        str(item["group_id"]),
                        str(item["template"]),
                    ),
                )[:10]
                instrumentation["residual_overlay_instrumentation"] = (
                    residual_overlay_instrumentation
                )
            instrumentation["phase_seconds"]["stats_finalize"] = float(
                instrumentation["phase_seconds"].get("stats_finalize", 0.0)
                + max(0.0, time.perf_counter() - finalize_started)
            )
            tightening_stats["signature_tightening_instrumentation"] = instrumentation

        mandatory_payloads: Dict[str, Dict[str, Any]] = {}
        required_optional_payloads: Dict[str, Dict[str, Any]] = {}
        if not self.owner.ghost_rect or not self.owner.u_vars:
            tightening_stats["reason"] = "ghost_disabled"
            _finalize_instrumentation("ghost_disabled")
            self._ghost_anchor_signature_bucket_tightening_stats = tightening_stats
            return

        mandatory_payload_started = time.perf_counter()
        for group in self.owner._mandatory_groups:
            payload_group_started = time.perf_counter()
            group_id = str(group["group_id"])
            bucket_vars = self.mandatory_signature_count_vars.get(group_id, {})
            if not bucket_vars:
                continue
            tpl = str(group["facility_type"])
            pose_to_bucket: Dict[int, str] = {}
            for bucket_id, pose_indices in self._mandatory_group_bucket_pose_indices.get(group_id, {}).items():
                for pose_idx in pose_indices:
                    pose_to_bucket[int(pose_idx)] = str(bucket_id)
            if not pose_to_bucket:
                continue
            cover_index_by_cell: Dict[Tuple[int, int], List[int]] = {}
            for cell, pose_indices in self.owner._covering_pose_indices.get(tpl, {}).items():
                filtered_pose_indices = [
                    int(pose_idx)
                    for pose_idx in pose_indices
                    if int(pose_idx) in pose_to_bucket
                ]
                if filtered_pose_indices:
                    cover_index_by_cell[(int(cell[0]), int(cell[1]))] = filtered_pose_indices
            payload_region_metadata_elapsed = time.perf_counter() - payload_group_started
            region_payload_started = time.perf_counter()
            region_counting_payload = (
                self._mandatory_region_counting_payload(
                    group_id=group_id,
                    tpl=tpl,
                    pose_to_bucket=pose_to_bucket,
                    template_footprint_support_enabled=(
                        template_footprint_support_enabled
                    ),
                    support_gap_instrumentation_enabled=(
                        support_gap_instrumentation_enabled
                    ),
                    payload_footprint_stability_support_enabled=(
                        payload_footprint_stability_support_enabled
                    ),
                    residual_overlay_instrumentation_enabled=(
                        residual_overlay_instrumentation is not None
                    ),
                )
                if mandatory_region_counting_enabled
                else {"supported": False, "reason": "disabled"}
            )
            _add_residual_overlay_phase_seconds(
                "payload_region_metadata_build_seconds",
                payload_region_metadata_elapsed,
            )
            payload_timing = region_counting_payload.get(
                "residual_overlay_payload_timing",
                {},
            )
            if isinstance(payload_timing, Mapping):
                for phase, seconds in payload_timing.items():
                    _add_residual_overlay_phase_seconds(str(phase), float(seconds or 0.0))
            _record_payload_group_timing(
                group_id=group_id,
                template=tpl,
                pose_count=len(pose_to_bucket),
                bucket_count=len(bucket_vars),
                supported=bool(region_counting_payload.get("supported", False)),
                reason=region_counting_payload.get("reason"),
                elapsed_seconds=time.perf_counter() - region_payload_started
                + payload_region_metadata_elapsed,
            )
            mandatory_payloads[group_id] = {
                "count_vars": dict(bucket_vars),
                "pose_to_bucket": dict(pose_to_bucket),
                "cover_index_by_cell": dict(cover_index_by_cell),
                "bucket_pose_counts": dict(self._mandatory_group_bucket_pose_counts.get(group_id, {})),
                "bucket_upper_bounds": dict(
                    self._mandatory_group_bucket_count_upper_bounds.get(group_id, {})
                ),
                "region_counting": region_counting_payload,
            }
        _add_phase_seconds(
            "mandatory_payload_build",
            time.perf_counter() - mandatory_payload_started,
        )

        required_optional_payload_started = time.perf_counter()
        for tpl, bucket_vars in sorted(self.required_optional_signature_count_vars.items()):
            if not bucket_vars:
                continue
            pose_to_bucket: Dict[int, str] = {}
            for bucket_id, pose_indices in self._required_optional_bucket_pose_indices.get(tpl, {}).items():
                for pose_idx in pose_indices:
                    pose_to_bucket[int(pose_idx)] = str(bucket_id)
            if not pose_to_bucket:
                continue
            cover_index_by_cell: Dict[Tuple[int, int], List[int]] = {}
            for cell, pose_indices in self.owner._covering_pose_indices.get(str(tpl), {}).items():
                filtered_pose_indices = [
                    int(pose_idx)
                    for pose_idx in pose_indices
                    if int(pose_idx) in pose_to_bucket
                ]
                if filtered_pose_indices:
                    cover_index_by_cell[(int(cell[0]), int(cell[1]))] = filtered_pose_indices
            required_optional_payloads[str(tpl)] = {
                "count_vars": dict(bucket_vars),
                "pose_to_bucket": dict(pose_to_bucket),
                "cover_index_by_cell": dict(cover_index_by_cell),
                "bucket_pose_counts": dict(
                    self._required_optional_bucket_pose_counts.get(str(tpl), {})
                ),
                "bucket_upper_bounds": dict(
                    self._required_optional_bucket_count_upper_bounds.get(str(tpl), {})
                ),
            }
        _add_phase_seconds(
            "required_optional_payload_build",
            time.perf_counter() - required_optional_payload_started,
        )

        if not mandatory_payloads and not required_optional_payloads:
            tightening_stats["reason"] = "no_signature_count_vars"
            _finalize_instrumentation("no_signature_count_vars")
            self._ghost_anchor_signature_bucket_tightening_stats = tightening_stats
            return

        conditioned_mandatory_bucket_constraints = 0
        conditioned_required_optional_bucket_constraints = 0
        signature_reduction_anchor_count = 0

        for rect_idx, domain in enumerate(self.owner._ghost_domains):
            anchor_has_reduction = False

            for group_id, payload in sorted(mandatory_payloads.items()):
                scan_started = time.perf_counter()
                region_metrics = {
                    "rectangles_evaluated": 0,
                    "overlap_counts": 0,
                    "counted_blocked_poses": 0,
                }
                region_counting = dict(payload.get("region_counting", {}))
                use_region_counting = bool(
                    mandatory_region_counting_enabled
                    and region_counting.get("supported", False)
                )
                if mandatory_region_counting_enabled:
                    _add_total("mandatory_region_counting_attempts", 1)
                    if template_footprint_support_enabled:
                        _add_total("mandatory_template_footprint_support_attempts", 1)
                    if payload_footprint_stability_support_enabled:
                        _add_total(
                            "mandatory_payload_footprint_stability_attempts",
                            1,
                        )
                if use_region_counting:
                    blocked_counts, region_metrics = (
                        self._mandatory_region_blocked_counts_for_domain(
                            domain,
                            region_counting,
                        )
                    )
                    blocked_pose_indices: Set[int] = set()
                    cells_scanned = 0
                    pose_hits = 0
                    _add_total("mandatory_region_counting_used", 1)
                    if (
                        template_footprint_support_enabled
                        and region_counting.get("template_footprint_support_used", False)
                    ):
                        _add_total("mandatory_template_footprint_support_used", 1)
                    if region_counting.get(
                        "payload_footprint_stability_support_used",
                        False,
                    ):
                        _add_total("mandatory_payload_footprint_stability_used", 1)
                        _add_total(
                            "mandatory_payload_footprint_stability_cohorts",
                            int(
                                region_metrics.get(
                                    "payload_footprint_stability_cohorts",
                                    0,
                                )
                            ),
                        )
                    _add_total(
                        "mandatory_region_rectangles_evaluated",
                        int(region_metrics["rectangles_evaluated"]),
                    )
                    _add_total(
                        "mandatory_region_overlap_counts",
                        int(region_metrics["overlap_counts"]),
                    )
                    _add_total(
                        "mandatory_region_counted_blocked_poses",
                        int(region_metrics["counted_blocked_poses"]),
                    )
                    _add_total(
                        "mandatory_unique_blocked_poses",
                        int(region_metrics["counted_blocked_poses"]),
                    )
                else:
                    fallback_reason = region_counting.get("reason")
                    if mandatory_region_counting_enabled:
                        _add_total("mandatory_region_counting_fallbacks", 1)
                        if (
                            template_footprint_support_enabled
                            and str(fallback_reason) == "unsupported_pose_footprint"
                        ):
                            _add_total(
                                "mandatory_template_footprint_support_fallbacks",
                                1,
                            )
                        if payload_footprint_stability_support_enabled:
                            _add_total(
                                "mandatory_payload_footprint_stability_fallbacks",
                                1,
                            )
                    blocked_counts = defaultdict(int)
                    blocked_pose_indices = set()
                    cells_scanned = 0
                    pose_hits = 0
                    for cell in domain.get("cells", []):
                        cells_scanned += 1
                        for pose_idx in payload["cover_index_by_cell"].get(
                            (int(cell[0]), int(cell[1])),
                            [],
                        ):
                            pose_hits += 1
                            if int(pose_idx) in blocked_pose_indices:
                                continue
                            blocked_pose_indices.add(int(pose_idx))
                            bucket_id = payload["pose_to_bucket"].get(int(pose_idx))
                            if bucket_id is None:
                                continue
                            blocked_counts[str(bucket_id)] += 1
                scan_elapsed = time.perf_counter() - scan_started
                if not use_region_counting:
                    _record_fallback_entry(
                        rect_idx=int(rect_idx),
                        domain=domain,
                        group_id_or_template=str(group_id),
                        reason=fallback_reason,
                        legacy_scan_count=int(cells_scanned),
                        legacy_pose_hits=int(pose_hits),
                        elapsed_seconds=scan_elapsed,
                    )
                    _record_support_gap_entry(
                        rect_idx=int(rect_idx),
                        domain=domain,
                        group_id_or_template=str(group_id),
                        gap=region_counting.get(
                            "template_footprint_support_gap",
                            {},
                        ),
                        elapsed_seconds=scan_elapsed,
                    )
                elif region_counting.get(
                    "payload_footprint_stability_support_used",
                    False,
                ):
                    _record_payload_footprint_stability_entry(
                        rect_idx=int(rect_idx),
                        domain=domain,
                        group_id_or_template=str(group_id),
                        cohort_count=int(
                            region_metrics.get(
                                "payload_footprint_stability_cohorts",
                                0,
                            )
                        ),
                        rectangles_evaluated=int(
                            region_metrics.get("rectangles_evaluated", 0)
                        ),
                        counted_blocked_poses=int(
                            region_metrics.get("counted_blocked_poses", 0)
                        ),
                        elapsed_seconds=scan_elapsed,
                    )
                _add_phase_seconds("per_anchor_mandatory_scan", scan_elapsed)
                _add_total("mandatory_cells_scanned", cells_scanned)
                _add_total("mandatory_pose_hits", pose_hits)
                if not use_region_counting:
                    _add_total(
                        "mandatory_unique_blocked_poses",
                        len(blocked_pose_indices),
                    )

                for bucket_id, count_var in sorted(payload["count_vars"].items()):
                    global_upper_bound = int(
                        payload["bucket_upper_bounds"].get(str(bucket_id), 0)
                    )
                    if global_upper_bound <= 0:
                        continue
                    bucket_pose_count = int(
                        payload["bucket_pose_counts"].get(str(bucket_id), 0)
                    )
                    available_count = int(bucket_pose_count) - int(
                        blocked_counts.get(str(bucket_id), 0)
                    )
                    conditioned_upper_bound = int(
                        min(max(0, available_count), global_upper_bound)
                    )
                    if conditioned_upper_bound >= global_upper_bound:
                        continue
                    add_started = time.perf_counter()
                    self.model.Add(
                        count_var
                        <= int(conditioned_upper_bound)
                        + int(global_upper_bound) * (1 - self.owner.u_vars[int(rect_idx)])
                    )
                    add_elapsed = time.perf_counter() - add_started
                    _add_phase_seconds("constraint_add", add_elapsed)
                    _add_total("mandatory_bucket_reductions", 1)
                    _add_total("mandatory_constraints_added", 1)
                    _record_slow_entry(
                        kind="mandatory",
                        rect_idx=int(rect_idx),
                        domain=domain,
                        group_id_or_template=str(group_id),
                        bucket_id=str(bucket_id),
                        scan_count=int(
                            region_metrics["rectangles_evaluated"]
                            if use_region_counting
                            else cells_scanned
                        ),
                        reduction_count=1,
                        elapsed_seconds=scan_elapsed + add_elapsed,
                    )
                    conditioned_mandatory_bucket_constraints += 1
                    anchor_has_reduction = True

            for template, payload in sorted(required_optional_payloads.items()):
                scan_started = time.perf_counter()
                blocked_counts: DefaultDict[str, int] = defaultdict(int)
                blocked_pose_indices: Set[int] = set()
                cells_scanned = 0
                pose_hits = 0
                for cell in domain.get("cells", []):
                    cells_scanned += 1
                    for pose_idx in payload["cover_index_by_cell"].get(
                        (int(cell[0]), int(cell[1])),
                        [],
                    ):
                        pose_hits += 1
                        if int(pose_idx) in blocked_pose_indices:
                            continue
                        blocked_pose_indices.add(int(pose_idx))
                        bucket_id = payload["pose_to_bucket"].get(int(pose_idx))
                        if bucket_id is None:
                            continue
                        blocked_counts[str(bucket_id)] += 1
                scan_elapsed = time.perf_counter() - scan_started
                _add_phase_seconds("per_anchor_required_optional_scan", scan_elapsed)
                _add_total("required_optional_cells_scanned", cells_scanned)
                _add_total("required_optional_pose_hits", pose_hits)
                _add_total(
                    "required_optional_unique_blocked_poses",
                    len(blocked_pose_indices),
                )

                for bucket_id, count_var in sorted(payload["count_vars"].items()):
                    global_upper_bound = int(
                        payload["bucket_upper_bounds"].get(str(bucket_id), 0)
                    )
                    if global_upper_bound <= 0:
                        continue
                    bucket_pose_count = int(
                        payload["bucket_pose_counts"].get(str(bucket_id), 0)
                    )
                    available_count = int(bucket_pose_count) - int(
                        blocked_counts.get(str(bucket_id), 0)
                    )
                    conditioned_upper_bound = int(
                        min(max(0, available_count), global_upper_bound)
                    )
                    if conditioned_upper_bound >= global_upper_bound:
                        continue
                    add_started = time.perf_counter()
                    self.model.Add(
                        count_var
                        <= int(conditioned_upper_bound)
                        + int(global_upper_bound) * (1 - self.owner.u_vars[int(rect_idx)])
                    )
                    add_elapsed = time.perf_counter() - add_started
                    _add_phase_seconds("constraint_add", add_elapsed)
                    _add_total("required_optional_bucket_reductions", 1)
                    _add_total("required_optional_constraints_added", 1)
                    _record_slow_entry(
                        kind="required_optional",
                        rect_idx=int(rect_idx),
                        domain=domain,
                        group_id_or_template=str(template),
                        bucket_id=str(bucket_id),
                        scan_count=int(cells_scanned),
                        reduction_count=1,
                        elapsed_seconds=scan_elapsed + add_elapsed,
                    )
                    conditioned_required_optional_bucket_constraints += 1
                    anchor_has_reduction = True

            if anchor_has_reduction:
                signature_reduction_anchor_count += 1

        tightening_stats["explicit_u_conditioning"] = True
        tightening_stats["conditioned_mandatory_bucket_constraints"] = int(
            conditioned_mandatory_bucket_constraints
        )
        tightening_stats["conditioned_required_optional_bucket_constraints"] = int(
            conditioned_required_optional_bucket_constraints
        )
        tightening_stats["signature_reduction_anchor_count"] = int(
            signature_reduction_anchor_count
        )
        _finalize_instrumentation()
        self._ghost_anchor_signature_bucket_tightening_stats = tightening_stats
        signature_stats = self.owner.build_stats.setdefault(
            "global_valid_inequalities",
            {},
        ).setdefault(
            "signature_bucket_capacity_bounds",
            {},
        )
        signature_stats["ghost_conditioned_mandatory_bucket_constraints"] = int(
            conditioned_mandatory_bucket_constraints
        )
        signature_stats["ghost_conditioned_required_optional_bucket_constraints"] = int(
            conditioned_required_optional_bucket_constraints
        )
        signature_stats["ghost_signature_reduction_anchor_count"] = int(
            signature_reduction_anchor_count
        )
        signature_tightening_instrumentation = tightening_stats.get(
            "signature_tightening_instrumentation"
        )
        if signature_tightening_instrumentation is not None:
            signature_stats["signature_tightening_instrumentation"] = copy.deepcopy(
                signature_tightening_instrumentation
            )

    def _apply_ghost_anchor_residual_signature_bucket_tightening(self) -> None:
        residual_overlay_instrumentation_enabled = (
            resolve_ghost_signature_bucket_residual_overlay_instrumentation_enabled()
        )
        tightening_stats: Dict[str, Any] = {
            "enabled": bool(self.owner.ghost_rect),
            "explicit_u_conditioning": False,
            "evaluated_placements": int(len(self.owner._ghost_domains)),
            "conditioned_residual_bucket_constraints": 0,
            "signature_reduction_anchor_count": 0,
        }
        residual_overlay_instrumentation: Optional[Dict[str, Any]] = None
        top_slow_residual_signature_entries: List[Dict[str, Any]] = []
        if residual_overlay_instrumentation_enabled:
            residual_overlay_instrumentation = {
                "enabled": True,
                "phase_seconds": {
                    "residual_signature_scan_seconds": 0.0,
                    "residual_signature_constraint_add_seconds": 0.0,
                },
                "top_slow_residual_signature_entries": [],
            }

        def _add_residual_phase_seconds(phase: str, seconds: float) -> None:
            if residual_overlay_instrumentation is None:
                return
            phase_seconds = residual_overlay_instrumentation["phase_seconds"]
            phase_seconds[phase] = float(
                phase_seconds.get(phase, 0.0) + max(0.0, seconds)
            )

        def _record_residual_entry(
            *,
            template: str,
            rect_idx: int,
            domain: Mapping[str, Any],
            bucket_id: str,
            scan_count: int,
            reduction_count: int,
            elapsed_seconds: float,
        ) -> None:
            if residual_overlay_instrumentation is None:
                return
            anchor = domain.get("anchor", {})
            top_slow_residual_signature_entries.append(
                {
                    "template": str(template),
                    "rect_idx": int(rect_idx),
                    "anchor": {
                        "x": int(anchor.get("x", 0)),
                        "y": int(anchor.get("y", 0)),
                    },
                    "bucket_id": str(bucket_id),
                    "scan_count": int(scan_count),
                    "reduction_count": int(reduction_count),
                    "elapsed_seconds": float(max(0.0, elapsed_seconds)),
                }
            )

        def _finalize_residual_overlay_instrumentation() -> None:
            if residual_overlay_instrumentation is None:
                return
            residual_overlay_instrumentation[
                "top_slow_residual_signature_entries"
            ] = sorted(
                top_slow_residual_signature_entries,
                key=lambda item: (
                    -float(item["elapsed_seconds"]),
                    str(item["template"]),
                    int(item["rect_idx"]),
                    str(item["bucket_id"]),
                ),
            )[:10]
            tightening_stats["residual_overlay_instrumentation"] = (
                residual_overlay_instrumentation
            )

        if not self.owner.ghost_rect or not self.owner.u_vars:
            tightening_stats["reason"] = "ghost_disabled"
            _finalize_residual_overlay_instrumentation()
            self._ghost_anchor_residual_signature_bucket_tightening_stats = tightening_stats
            return

        residual_payloads: Dict[str, Dict[str, Any]] = {}
        for tpl, bucket_vars in sorted(self.residual_optional_signature_count_vars.items()):
            if not bucket_vars:
                continue
            pose_to_bucket: Dict[int, str] = {}
            for bucket_id, pose_indices in self._residual_optional_bucket_pose_indices.get(
                str(tpl),
                {},
            ).items():
                for pose_idx in pose_indices:
                    pose_to_bucket[int(pose_idx)] = str(bucket_id)
            if not pose_to_bucket:
                continue
            cover_index_by_cell: Dict[Tuple[int, int], List[int]] = {}
            for cell, pose_indices in self.owner._covering_pose_indices.get(str(tpl), {}).items():
                filtered_pose_indices = [
                    int(pose_idx)
                    for pose_idx in pose_indices
                    if int(pose_idx) in pose_to_bucket
                ]
                if filtered_pose_indices:
                    cover_index_by_cell[(int(cell[0]), int(cell[1]))] = filtered_pose_indices
            residual_payloads[str(tpl)] = {
                "count_vars": dict(bucket_vars),
                "pose_to_bucket": dict(pose_to_bucket),
                "cover_index_by_cell": dict(cover_index_by_cell),
                "bucket_pose_counts": dict(
                    self._residual_optional_bucket_pose_counts.get(str(tpl), {})
                ),
                "bucket_upper_bounds": dict(
                    self._residual_optional_bucket_count_upper_bounds.get(str(tpl), {})
                ),
            }

        if not residual_payloads:
            tightening_stats["reason"] = "no_residual_signature_count_vars"
            _finalize_residual_overlay_instrumentation()
            self._ghost_anchor_residual_signature_bucket_tightening_stats = tightening_stats
            return

        conditioned_residual_bucket_constraints = 0
        signature_reduction_anchor_count = 0

        for rect_idx, domain in enumerate(self.owner._ghost_domains):
            anchor_has_reduction = False
            for template, payload in sorted(residual_payloads.items()):
                scan_started = time.perf_counter()
                blocked_counts: DefaultDict[str, int] = defaultdict(int)
                blocked_pose_indices: Set[int] = set()
                cells_scanned = 0
                pose_hits = 0
                for cell in domain.get("cells", []):
                    cells_scanned += 1
                    for pose_idx in payload["cover_index_by_cell"].get(
                        (int(cell[0]), int(cell[1])),
                        [],
                    ):
                        pose_hits += 1
                        if int(pose_idx) in blocked_pose_indices:
                            continue
                        blocked_pose_indices.add(int(pose_idx))
                        bucket_id = payload["pose_to_bucket"].get(int(pose_idx))
                        if bucket_id is None:
                            continue
                        blocked_counts[str(bucket_id)] += 1
                scan_elapsed = time.perf_counter() - scan_started
                _add_residual_phase_seconds(
                    "residual_signature_scan_seconds",
                    scan_elapsed,
                )

                for bucket_id, count_var in sorted(payload["count_vars"].items()):
                    global_upper_bound = int(
                        payload["bucket_upper_bounds"].get(str(bucket_id), 0)
                    )
                    if global_upper_bound <= 0:
                        continue
                    bucket_pose_count = int(
                        payload["bucket_pose_counts"].get(str(bucket_id), 0)
                    )
                    available_count = int(bucket_pose_count) - int(
                        blocked_counts.get(str(bucket_id), 0)
                    )
                    conditioned_upper_bound = int(
                        min(max(0, available_count), global_upper_bound)
                    )
                    if conditioned_upper_bound >= global_upper_bound:
                        continue
                    add_started = time.perf_counter()
                    self.model.Add(
                        count_var
                        <= int(conditioned_upper_bound)
                        + int(global_upper_bound) * (1 - self.owner.u_vars[int(rect_idx)])
                    )
                    add_elapsed = time.perf_counter() - add_started
                    _add_residual_phase_seconds(
                        "residual_signature_constraint_add_seconds",
                        add_elapsed,
                    )
                    _record_residual_entry(
                        template=str(template),
                        rect_idx=int(rect_idx),
                        domain=domain,
                        bucket_id=str(bucket_id),
                        scan_count=int(cells_scanned),
                        reduction_count=1,
                        elapsed_seconds=scan_elapsed + add_elapsed,
                    )
                    conditioned_residual_bucket_constraints += 1
                    anchor_has_reduction = True

            if anchor_has_reduction:
                signature_reduction_anchor_count += 1

        tightening_stats["explicit_u_conditioning"] = True
        tightening_stats["conditioned_residual_bucket_constraints"] = int(
            conditioned_residual_bucket_constraints
        )
        tightening_stats["signature_reduction_anchor_count"] = int(
            signature_reduction_anchor_count
        )
        _finalize_residual_overlay_instrumentation()
        self._ghost_anchor_residual_signature_bucket_tightening_stats = tightening_stats
        residual_signature_stats = self.owner.build_stats.setdefault(
            "global_valid_inequalities",
            {},
        ).setdefault(
            "residual_signature_bucket_capacity_bounds",
            {},
        )
        residual_signature_stats["ghost_conditioned_residual_bucket_constraints"] = int(
            conditioned_residual_bucket_constraints
        )
        residual_signature_stats["ghost_residual_signature_reduction_anchor_count"] = int(
            signature_reduction_anchor_count
        )
        if residual_overlay_instrumentation is not None:
            residual_signature_stats["residual_overlay_instrumentation"] = copy.deepcopy(
                residual_overlay_instrumentation
            )

    def _all_powered_slots(self) -> List[CoordinateSlotSpec]:
        powered_slots: List[CoordinateSlotSpec] = []
        for group in self.owner._mandatory_groups:
            tpl = str(group["facility_type"])
            if tpl in self.owner._powered_templates and tpl != "power_pole":
                powered_slots.extend(self.mandatory_slots.get(str(group["group_id"]), []))
        for tpl, slot_specs in self.required_optional_slots.items():
            if tpl in self.owner._powered_templates and tpl != "power_pole":
                powered_slots.extend(slot_specs)
        for tpl, slot_specs in self.residual_optional_slots.items():
            if tpl in self.owner._powered_templates and tpl != "power_pole":
                powered_slots.extend(slot_specs)
        # Empty-domain slots take the _create_base_slot_geometry fast path that
        # forces the model infeasible (Add(0 == 1)) and never builds footprint
        # channels.  Their power-coverage geometry is moot (the model is already
        # UNSAT) and the footprint-based witnesses would crash on the missing
        # channel, so exclude them: power coverage only constrains placeable slots.
        return [slot for slot in powered_slots if slot.footprint_x_start is not None]

    def _power_coverage_radius(self) -> int:
        template = self.owner.templates.get("power_pole")
        if not template:
            return 0
        return int(template.get("power_coverage_radius", 0))

    def _supports_rectangular_power_coverage(self) -> bool:
        template = self.owner.templates.get("power_pole")
        if not template or "power_coverage_radius" not in template:
            return False
        radius = int(template.get("power_coverage_radius", 0))
        # Geometric power witnesses below test rectangle intersection between a
        # pole coverage rectangle and the powered slot's footprint bounding box.
        # That is exact only when every powered facility footprint is itself a
        # full rectangle.  For an L-shaped powered footprint, a pole can touch a
        # bounding-box hole without covering any occupied powered cell, so the
        # coordinate table witness must be used instead.
        for powered_tpl in sorted(self.owner._powered_templates):
            if str(powered_tpl) == "power_pole":
                continue
            for pose in self.owner.facility_pools.get(str(powered_tpl), []):
                relative_cells = self._pose_relative_occupied_cells(pose)
                if not relative_cells:
                    return False
                if not self._is_rectangular_set(relative_cells):
                    return False
        for pose in self.owner.facility_pools.get("power_pole", []):
            anchor = dict(pose.get("anchor", {}))
            x0 = int(anchor.get("x", 0))
            y0 = int(anchor.get("y", 0))
            expected: Set[Tuple[int, int]] = set()
            for cell_x in range(max(0, x0 - radius), min(self.grid_w - 1, x0 + 1 + radius) + 1):
                for cell_y in range(max(0, y0 - radius), min(self.grid_h - 1, y0 + 1 + radius) + 1):
                    expected.add((int(cell_x), int(cell_y)))
            actual = {
                (int(cell[0]), int(cell[1]))
                for cell in pose.get("power_coverage_cells", []) or []
            }
            if actual != expected:
                return False
        return True

    def _add_table_power_coverage_constraints(self) -> int:
        powered_slots = self._all_powered_slots()
        pole_slots = self._all_power_pole_slots()
        cover_literals = 0
        for powered_slot in powered_slots:
            allowed_tuples: List[Tuple[int, ...]] = []
            for powered_pose_idx, coverers in self.owner._power_coverers_by_template_pose.get(powered_slot.template, {}).items():
                powered_tuple = self._template_pose_tuple_by_idx[powered_slot.template].get(int(powered_pose_idx))
                if powered_tuple is None:
                    continue
                for pole_idx in coverers:
                    pole_tuple = self._template_pose_tuple_by_idx["power_pole"].get(int(pole_idx))
                    if pole_tuple is None:
                        continue
                    allowed_tuples.append(
                        (
                            int(pole_tuple[0]),
                            int(pole_tuple[1]),
                            int(pole_tuple[2]),
                            int(powered_tuple[0]),
                            int(powered_tuple[1]),
                            int(powered_tuple[2]),
                        )
                    )

            witnesses: List[cp_model.IntVar] = []
            for pole_slot in pole_slots:
                cover_lit = self.model.NewBoolVar(f"covers__{pole_slot.key}__{powered_slot.key}")
                if pole_slot.active is not None:
                    self.model.Add(cover_lit <= pole_slot.active)
                if powered_slot.active is not None:
                    self.model.Add(cover_lit <= powered_slot.active)
                if allowed_tuples:
                    self.model.AddAllowedAssignments(
                        [pole_slot.x, pole_slot.y, pole_slot.mode, powered_slot.x, powered_slot.y, powered_slot.mode],
                        allowed_tuples,
                    ).OnlyEnforceIf(cover_lit)
                else:
                    self.model.Add(cover_lit == 0)
                witnesses.append(cover_lit)
                cover_literals += 1
            if witnesses:
                if powered_slot.active is not None:
                    self.model.Add(sum(witnesses) >= powered_slot.active)
                else:
                    self.model.Add(sum(witnesses) >= 1)
            else:
                if powered_slot.active is not None:
                    self.model.Add(powered_slot.active == 0)
                else:
                    self.model.Add(0 >= 1)
        return int(cover_literals)

    def _use_block_element_power_coverage_for_template(self, template: str) -> bool:
        if (
            self._power_coverage_witness_encoding
            != EXACT_POWER_COVERAGE_WITNESS_ENCODING_BLOCK_ELEMENT
        ):
            return False
        templates = set(self._power_coverage_witness_block_templates)
        return not templates or str(template) in templates

    def _record_power_coverage_witness_template_count(
        self,
        *,
        template: str,
        mode: str,
    ) -> None:
        stats = self._power_coverage_witness_encoding_stats
        template_counts = dict(stats.get("template_counts", {}) or {})
        template_payload = dict(template_counts.get(str(template), {}) or {})
        template_payload[str(mode)] = int(template_payload.get(str(mode), 0)) + 1
        template_counts[str(template)] = template_payload
        stats["template_counts"] = dict(sorted(template_counts.items()))

    def _create_cover_choice_target_vars(
        self,
        powered_slot: CoordinateSlotSpec,
    ) -> Tuple[cp_model.IntVar, cp_model.IntVar, cp_model.IntVar]:
        cover_choice_active = self.model.NewBoolVar(
            f"cover_choice_active__{powered_slot.key}"
        )
        cover_choice_x = self.model.NewIntVar(
            0,
            max(0, self.grid_w - 1),
            f"cover_choice_x__{powered_slot.key}",
        )
        cover_choice_y = self.model.NewIntVar(
            0,
            max(0, self.grid_h - 1),
            f"cover_choice_y__{powered_slot.key}",
        )
        stats = self._power_coverage_witness_encoding_stats
        stats["final_target_channel_count"] = int(
            stats.get("final_target_channel_count", 0)
        ) + 3
        return cover_choice_active, cover_choice_x, cover_choice_y

    def _add_power_coverage_selected_geometry(
        self,
        *,
        powered_slot: CoordinateSlotSpec,
        cover_choice_active: Optional[cp_model.IntVar],
        cover_choice_x: cp_model.IntVar,
        cover_choice_y: cp_model.IntVar,
        radius: int,
        extra_enforcement_literals: Sequence[Any] = (),
    ) -> int:
        extra_enforcements = list(extra_enforcement_literals or [])
        if powered_slot.active is not None:
            enforcements = [powered_slot.active] + extra_enforcements
        else:
            enforcements = extra_enforcements
        stats = self._power_coverage_witness_encoding_stats
        constraints = []
        powered_x_start = self._slot_footprint_x_start(powered_slot)
        powered_y_start = self._slot_footprint_y_start(powered_slot)
        powered_width = self._slot_footprint_width(powered_slot)
        powered_height = self._slot_footprint_height(powered_slot)
        if cover_choice_active is not None:
            constraints.append(self.model.Add(cover_choice_active == 1))
        if (
            self._power_coverage_selected_interval_encoding
            == EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_DELTA
        ):
            x_constraints = self._add_power_coverage_axis_delta_constraints(
                powered_coord=powered_x_start,
                cover_coord=cover_choice_x,
                span=powered_width,
                span_upper=max(
                    int(domain.footprint_width)
                    for domain in powered_slot.mode_rect_domains.values()
                ),
                radius=int(radius),
                name=f"cover_choice_delta_x__{powered_slot.key}",
            )
            y_constraints = self._add_power_coverage_axis_delta_constraints(
                powered_coord=powered_y_start,
                cover_coord=cover_choice_y,
                span=powered_height,
                span_upper=max(
                    int(domain.footprint_height)
                    for domain in powered_slot.mode_rect_domains.values()
                ),
                radius=int(radius),
                name=f"cover_choice_delta_y__{powered_slot.key}",
            )
            constraints.extend(x_constraints)
            constraints.extend(y_constraints)
            stats["selected_interval_delta_constraint_count"] = int(
                stats.get("selected_interval_delta_constraint_count", 0)
            ) + int(len(x_constraints) + len(y_constraints))
        else:
            constraints.extend(
                [
                    self.model.Add(powered_x_start <= cover_choice_x + 2 + radius - 1),
                    self.model.Add(
                        cover_choice_x
                        - radius
                        <= powered_x_start + powered_width - 1
                    ),
                    self.model.Add(powered_y_start <= cover_choice_y + 2 + radius - 1),
                    self.model.Add(
                        cover_choice_y
                        - radius
                        <= powered_y_start + powered_height - 1
                    ),
                ]
            )
            stats["selected_interval_bounds_constraint_count"] = int(
                stats.get("selected_interval_bounds_constraint_count", 0)
            ) + 4
        if enforcements:
            for constraint in constraints:
                constraint.OnlyEnforceIf(enforcements)
        return int(len(constraints))

    def _add_power_coverage_axis_delta_constraints(
        self,
        *,
        powered_coord: cp_model.IntVar,
        cover_coord: cp_model.IntVar,
        span: cp_model.IntVar,
        span_upper: int,
        radius: int,
        name: str,
    ) -> List[Any]:
        lower = 1 - int(span_upper) - int(radius)
        upper = int(radius) + 1
        delta = self.model.NewIntVar(int(lower), int(upper), str(name))
        stats = self._power_coverage_witness_encoding_stats
        stats["selected_interval_delta_var_count"] = int(
            stats.get("selected_interval_delta_var_count", 0)
        ) + 1
        return [
            self.model.Add(delta == powered_coord - cover_coord),
            self.model.Add(delta <= int(radius) + 1),
            self.model.Add(delta + span >= 1 - int(radius)),
        ]

    def _create_cover_choice_local_selected_literals(
        self,
        *,
        powered_slot: CoordinateSlotSpec,
        cover_choice_local_idx: cp_model.IntVar,
        block_size: int,
    ) -> List[cp_model.IntVar]:
        local_selected_literals: List[cp_model.IntVar] = []
        for local_index in range(int(block_size)):
            local_selected = self.model.NewBoolVar(
                f"cover_choice_local_selected__{powered_slot.key}__local::{local_index:03d}"
            )
            self.model.Add(cover_choice_local_idx == int(local_index)).OnlyEnforceIf(
                local_selected
            )
            self.model.Add(cover_choice_local_idx != int(local_index)).OnlyEnforceIf(
                local_selected.Not()
            )
            local_selected_literals.append(local_selected)
        stats = self._power_coverage_witness_encoding_stats
        stats["local_selected_literal_count"] = int(
            stats.get("local_selected_literal_count", 0)
        ) + int(len(local_selected_literals))
        stats["local_selected_channel_constraint_count"] = int(
            stats.get("local_selected_channel_constraint_count", 0)
        ) + int(len(local_selected_literals) * 2)
        return local_selected_literals

    def _add_power_coverage_block_selected_geometry(
        self,
        *,
        powered_slot: CoordinateSlotSpec,
        cover_choice_block_idx: cp_model.IntVar,
        block_active_lookup: Sequence[Optional[cp_model.IntVar]],
        block_x_lookup: Sequence[cp_model.IntVar],
        block_y_lookup: Sequence[cp_model.IntVar],
        radius: int,
        padded_slot_blocks: Optional[Sequence[Sequence[CoordinateSlotSpec]]] = None,
        local_selected_literals: Optional[Sequence[cp_model.IntVar]] = None,
    ) -> int:
        stats = self._power_coverage_witness_encoding_stats
        geometry_constraint_count = 0
        use_active_guard = (
            padded_slot_blocks is not None and local_selected_literals is not None
        )
        for block_index, (block_active, block_x, block_y) in enumerate(
            zip(block_active_lookup, block_x_lookup, block_y_lookup)
        ):
            block_selected = self.model.NewBoolVar(
                f"cover_choice_block_selected__{powered_slot.key}__block::{block_index:03d}"
            )
            self.model.Add(cover_choice_block_idx == int(block_index)).OnlyEnforceIf(
                block_selected
            )
            self.model.Add(cover_choice_block_idx != int(block_index)).OnlyEnforceIf(
                block_selected.Not()
            )
            selected_geometry_count = self._add_power_coverage_selected_geometry(
                powered_slot=powered_slot,
                cover_choice_active=block_active,
                cover_choice_x=block_x,
                cover_choice_y=block_y,
                radius=radius,
                extra_enforcement_literals=[block_selected],
            )
            if use_active_guard:
                padded_slots = list(padded_slot_blocks[block_index])
                for local_selected, pole_slot in zip(local_selected_literals, padded_slots):
                    if pole_slot.active is None:
                        continue
                    active_guard_clause = [
                        block_selected.Not(),
                        local_selected.Not(),
                        pole_slot.active,
                    ]
                    if powered_slot.active is not None:
                        active_guard_clause.insert(0, powered_slot.active.Not())
                    self.model.AddBoolOr(active_guard_clause)
                    stats["block_active_guard_clause_count"] = int(
                        stats.get("block_active_guard_clause_count", 0)
                    ) + 1
            stats["block_selected_literal_count"] = int(
                stats.get("block_selected_literal_count", 0)
            ) + 1
            stats["block_selected_channel_constraint_count"] = int(
                stats.get("block_selected_channel_constraint_count", 0)
            ) + 2
            stats["block_selected_geometry_constraint_count"] = int(
                stats.get("block_selected_geometry_constraint_count", 0)
            ) + int(selected_geometry_count)
            geometry_constraint_count += int(selected_geometry_count)
        return geometry_constraint_count

    def _add_power_coverage_block_selected_active_guards(
        self,
        *,
        powered_slot: CoordinateSlotSpec,
        cover_choice_block_idx: cp_model.IntVar,
        padded_slot_blocks: Sequence[Sequence[CoordinateSlotSpec]],
        local_selected_literals: Sequence[cp_model.IntVar],
    ) -> None:
        stats = self._power_coverage_witness_encoding_stats
        for block_index, padded_slots in enumerate(padded_slot_blocks):
            block_selected = self.model.NewBoolVar(
                f"cover_choice_block_selected__{powered_slot.key}__block::{block_index:03d}"
            )
            self.model.Add(cover_choice_block_idx == int(block_index)).OnlyEnforceIf(
                block_selected
            )
            self.model.Add(cover_choice_block_idx != int(block_index)).OnlyEnforceIf(
                block_selected.Not()
            )
            for local_selected, pole_slot in zip(local_selected_literals, padded_slots):
                if pole_slot.active is None:
                    continue
                active_guard_clause = [
                    block_selected.Not(),
                    local_selected.Not(),
                    pole_slot.active,
                ]
                if powered_slot.active is not None:
                    active_guard_clause.insert(0, powered_slot.active.Not())
                self.model.AddBoolOr(active_guard_clause)
                stats["block_active_guard_clause_count"] = int(
                    stats.get("block_active_guard_clause_count", 0)
                ) + 1
            stats["block_selected_literal_count"] = int(
                stats.get("block_selected_literal_count", 0)
            ) + 1
            stats["block_selected_channel_constraint_count"] = int(
                stats.get("block_selected_channel_constraint_count", 0)
            ) + 2

    def _add_wide_element_power_coverage_witness(
        self,
        *,
        powered_slot: CoordinateSlotSpec,
        active_lookup: Sequence[cp_model.IntVar],
        x_lookup: Sequence[cp_model.IntVar],
        y_lookup: Sequence[cp_model.IntVar],
        radius: int,
    ) -> Tuple[int, int]:
        cover_choice_idx = self.model.NewIntVar(
            0,
            len(active_lookup) - 1,
            f"cover_choice_idx__{powered_slot.key}",
        )
        cover_choice_active, cover_choice_x, cover_choice_y = (
            self._create_cover_choice_target_vars(powered_slot)
        )
        self.model.AddElement(cover_choice_idx, list(active_lookup), cover_choice_active)
        self.model.AddElement(cover_choice_idx, list(x_lookup), cover_choice_x)
        self.model.AddElement(cover_choice_idx, list(y_lookup), cover_choice_y)
        self._add_power_coverage_selected_geometry(
            powered_slot=powered_slot,
            cover_choice_active=cover_choice_active,
            cover_choice_x=cover_choice_x,
            cover_choice_y=cover_choice_y,
            radius=radius,
        )
        stats = self._power_coverage_witness_encoding_stats
        stats["wide_witness_count"] = int(stats.get("wide_witness_count", 0)) + 1
        stats["wide_element_constraint_count"] = int(
            stats.get("wide_element_constraint_count", 0)
        ) + 3
        stats["wide_element_target_channel_count"] = int(
            stats.get("wide_element_target_channel_count", 0)
        ) + 3
        self._record_power_coverage_witness_template_count(
            template=powered_slot.template,
            mode="wide_element",
        )
        return 1, 3

    def _add_block_element_power_coverage_witness(
        self,
        *,
        powered_slot: CoordinateSlotSpec,
        pole_slots: Sequence[CoordinateSlotSpec],
        radius: int,
    ) -> Tuple[int, int]:
        block_size = max(2, int(self._power_coverage_witness_block_size))
        blocks = [
            list(pole_slots[start : start + block_size])
            for start in range(0, len(pole_slots), block_size)
        ]
        cover_choice_block_idx = self.model.NewIntVar(
            0,
            len(blocks) - 1,
            f"cover_choice_block_idx__{powered_slot.key}",
        )
        cover_choice_local_idx = self.model.NewIntVar(
            0,
            block_size - 1,
            f"cover_choice_local_idx__{powered_slot.key}",
        )
        use_selected_block_geometry = (
            self._power_coverage_witness_block_geometry
            in {
                EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK,
                EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD,
                EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_GROUPED_XY,
                EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_JOINED_XY,
            }
        )
        use_selected_block_active_guard = (
            self._power_coverage_witness_block_geometry
            in {
                EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD,
                EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_GROUPED_XY,
                EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_JOINED_XY,
            }
        )
        use_grouped_xy = (
            self._power_coverage_witness_block_geometry
            == EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_GROUPED_XY
        )
        use_joined_xy = (
            self._power_coverage_witness_block_geometry
            == EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_JOINED_XY
        )
        cover_choice_active: Optional[cp_model.IntVar] = None
        cover_choice_x: Optional[cp_model.IntVar] = None
        cover_choice_y: Optional[cp_model.IntVar] = None
        if not use_selected_block_geometry:
            cover_choice_active, cover_choice_x, cover_choice_y = (
                self._create_cover_choice_target_vars(powered_slot)
            )

        block_active_lookup: List[Optional[cp_model.IntVar]] = []
        block_x_lookup: List[cp_model.IntVar] = []
        block_y_lookup: List[cp_model.IntVar] = []
        padded_slot_blocks: List[List[CoordinateSlotSpec]] = []
        flattened_padded_slots: List[CoordinateSlotSpec] = []
        padded_values = 0
        for block_index, block_slots in enumerate(blocks):
            if not block_slots:
                continue
            padded_slots = list(block_slots)
            if len(padded_slots) < block_size:
                pad_slot = padded_slots[-1]
                padded_values += int(block_size - len(padded_slots))
                padded_slots.extend([pad_slot] * (block_size - len(padded_slots)))
            block_active: Optional[cp_model.IntVar] = None
            if not use_selected_block_active_guard:
                block_active = self.model.NewBoolVar(
                    f"cover_choice_block_active__{powered_slot.key}__block::{block_index:03d}"
                )
            if use_grouped_xy:
                block_active_lookup.append(block_active)
                padded_slot_blocks.append(padded_slots)
                flattened_padded_slots.extend(padded_slots)
                continue
            block_x = self.model.NewIntVar(
                0,
                max(0, self.grid_w - 1),
                f"cover_choice_block_x__{powered_slot.key}__block::{block_index:03d}",
            )
            block_y = self.model.NewIntVar(
                0,
                max(0, self.grid_h - 1),
                f"cover_choice_block_y__{powered_slot.key}__block::{block_index:03d}",
            )
            if block_active is not None:
                self.model.AddElement(
                    cover_choice_local_idx,
                    [self._slot_active_lookup_value(slot) for slot in padded_slots],
                    block_active,
                )
            self.model.AddElement(cover_choice_local_idx, [slot.x for slot in padded_slots], block_x)
            self.model.AddElement(cover_choice_local_idx, [slot.y for slot in padded_slots], block_y)
            block_active_lookup.append(block_active)
            block_x_lookup.append(block_x)
            block_y_lookup.append(block_y)
            padded_slot_blocks.append(padded_slots)

        block_intermediate_target_channel_delta = int(len(block_x_lookup) * 3)
        element_count = int(len(block_x_lookup) * 3)
        local_selected_literals: Optional[List[cp_model.IntVar]] = None
        if use_selected_block_active_guard:
            block_intermediate_target_channel_delta = int(len(block_x_lookup) * 2)
            element_count = int(len(block_x_lookup) * 2)
            local_selected_literals = self._create_cover_choice_local_selected_literals(
                powered_slot=powered_slot,
                cover_choice_local_idx=cover_choice_local_idx,
                block_size=int(block_size),
            )
        if use_grouped_xy:
            if not flattened_padded_slots:
                raise AssertionError("missing grouped x/y padded slots")
            if local_selected_literals is None:
                raise AssertionError("missing grouped x/y local selected literals")
            cover_choice_padded_idx = self.model.NewIntVar(
                0,
                len(flattened_padded_slots) - 1,
                f"cover_choice_padded_idx__{powered_slot.key}",
            )
            self.model.Add(
                cover_choice_padded_idx
                == cover_choice_block_idx * int(block_size) + cover_choice_local_idx
            )
            grouped_x = self.model.NewIntVar(
                0,
                max(0, self.grid_w - 1),
                f"cover_choice_grouped_x__{powered_slot.key}",
            )
            grouped_y = self.model.NewIntVar(
                0,
                max(0, self.grid_h - 1),
                f"cover_choice_grouped_y__{powered_slot.key}",
            )
            self.model.AddElement(
                cover_choice_padded_idx,
                [slot.x for slot in flattened_padded_slots],
                grouped_x,
            )
            self.model.AddElement(
                cover_choice_padded_idx,
                [slot.y for slot in flattened_padded_slots],
                grouped_y,
            )
            self._add_power_coverage_block_selected_active_guards(
                powered_slot=powered_slot,
                cover_choice_block_idx=cover_choice_block_idx,
                padded_slot_blocks=padded_slot_blocks,
                local_selected_literals=local_selected_literals,
            )
            selected_geometry_count = self._add_power_coverage_selected_geometry(
                powered_slot=powered_slot,
                cover_choice_active=None,
                cover_choice_x=grouped_x,
                cover_choice_y=grouped_y,
                radius=radius,
            )
            stats = self._power_coverage_witness_encoding_stats
            stats["grouped_xy_target_channel_count"] = int(
                stats.get("grouped_xy_target_channel_count", 0)
            ) + 2
            stats["grouped_xy_element_constraint_count"] = int(
                stats.get("grouped_xy_element_constraint_count", 0)
            ) + 2
            stats["grouped_xy_padded_index_constraint_count"] = int(
                stats.get("grouped_xy_padded_index_constraint_count", 0)
            ) + 1
            stats["grouped_xy_selected_geometry_constraint_count"] = int(
                stats.get("grouped_xy_selected_geometry_constraint_count", 0)
            ) + int(selected_geometry_count)
            block_intermediate_target_channel_delta = 2
            element_count = 2
        elif use_joined_xy:
            if local_selected_literals is None:
                raise AssertionError("missing joined x/y local selected literals")
            joined_x = self.model.NewIntVar(
                0,
                max(0, self.grid_w - 1),
                f"cover_choice_joined_x__{powered_slot.key}",
            )
            joined_y = self.model.NewIntVar(
                0,
                max(0, self.grid_h - 1),
                f"cover_choice_joined_y__{powered_slot.key}",
            )
            self.model.AddElement(cover_choice_block_idx, block_x_lookup, joined_x)
            self.model.AddElement(cover_choice_block_idx, block_y_lookup, joined_y)
            self._add_power_coverage_block_selected_active_guards(
                powered_slot=powered_slot,
                cover_choice_block_idx=cover_choice_block_idx,
                padded_slot_blocks=padded_slot_blocks,
                local_selected_literals=local_selected_literals,
            )
            selected_geometry_count = self._add_power_coverage_selected_geometry(
                powered_slot=powered_slot,
                cover_choice_active=None,
                cover_choice_x=joined_x,
                cover_choice_y=joined_y,
                radius=radius,
            )
            stats = self._power_coverage_witness_encoding_stats
            stats["joined_xy_target_channel_count"] = int(
                stats.get("joined_xy_target_channel_count", 0)
            ) + 2
            stats["joined_xy_element_constraint_count"] = int(
                stats.get("joined_xy_element_constraint_count", 0)
            ) + 2
            stats["joined_xy_selected_geometry_constraint_count"] = int(
                stats.get("joined_xy_selected_geometry_constraint_count", 0)
            ) + int(selected_geometry_count)
            stats["block_final_join_element_constraint_count"] = int(
                stats.get("block_final_join_element_constraint_count", 0)
            ) + 2
            element_count += 2
        elif use_selected_block_geometry:
            self._add_power_coverage_block_selected_geometry(
                powered_slot=powered_slot,
                cover_choice_block_idx=cover_choice_block_idx,
                block_active_lookup=block_active_lookup,
                block_x_lookup=block_x_lookup,
                block_y_lookup=block_y_lookup,
                radius=radius,
                padded_slot_blocks=(
                    padded_slot_blocks if use_selected_block_active_guard else None
                ),
                local_selected_literals=local_selected_literals,
            )
        else:
            if (
                cover_choice_active is None
                or cover_choice_x is None
                or cover_choice_y is None
            ):
                raise AssertionError("missing final cover-choice target channels")
            self.model.AddElement(
                cover_choice_block_idx,
                block_active_lookup,
                cover_choice_active,
            )
            self.model.AddElement(cover_choice_block_idx, block_x_lookup, cover_choice_x)
            self.model.AddElement(cover_choice_block_idx, block_y_lookup, cover_choice_y)
            self._add_power_coverage_selected_geometry(
                powered_slot=powered_slot,
                cover_choice_active=cover_choice_active,
                cover_choice_x=cover_choice_x,
                cover_choice_y=cover_choice_y,
                radius=radius,
            )
            element_count += 3
            stats = self._power_coverage_witness_encoding_stats
            stats["block_final_join_element_constraint_count"] = int(
                stats.get("block_final_join_element_constraint_count", 0)
            ) + 3

        stats = self._power_coverage_witness_encoding_stats
        stats["block_witness_count"] = int(stats.get("block_witness_count", 0)) + 1
        stats["block_element_constraint_count"] = int(
            stats.get("block_element_constraint_count", 0)
        ) + element_count
        stats["block_intermediate_target_channel_count"] = int(
            stats.get("block_intermediate_target_channel_count", 0)
        ) + int(block_intermediate_target_channel_delta)
        stats["block_selector_count"] = int(stats.get("block_selector_count", 0)) + 1
        stats["local_selector_count"] = int(stats.get("local_selector_count", 0)) + 1
        stats["padded_block_value_count"] = int(
            stats.get("padded_block_value_count", 0)
        ) + int(padded_values)
        self._record_power_coverage_witness_template_count(
            template=powered_slot.template,
            mode="block_element",
        )
        return 1, element_count

    def _add_geometric_power_coverage_constraints(self) -> None:
        powered_slots = self._all_powered_slots()
        pole_slots = self._all_power_pole_slots()
        radius = self._power_coverage_radius()
        if not self._supports_rectangular_power_coverage():
            cover_literals = self._add_table_power_coverage_constraints()
            self.owner.build_stats["power_coverage"] = {
                "representation": "coordinate_cover_table",
                "encoding": "table_pairwise_witness_v1",
                "powered_slots": len(powered_slots),
                "pole_slots": len(pole_slots),
                "cover_literals": int(cover_literals),
                "witness_indices": 0,
                "element_constraints": 0,
            }
            return
        witness_indices = 0
        element_constraints = 0
        if not pole_slots:
            for powered_slot in powered_slots:
                if powered_slot.active is not None:
                    self.model.Add(powered_slot.active == 0)
                else:
                    self.model.Add(0 >= 1)
            self.owner.build_stats["power_coverage"] = {
                "representation": "coordinate_geometric",
                "encoding": "geometric_element_witness_v1",
                "powered_slots": len(powered_slots),
                "pole_slots": 0,
                "cover_literals": 0,
                "witness_indices": 0,
                "element_constraints": 0,
                "radius": int(radius),
            }
            return

        active_lookup = [self._slot_active_lookup_value(slot) for slot in pole_slots]
        x_lookup = [slot.x for slot in pole_slots if slot.x is not None]
        y_lookup = [slot.y for slot in pole_slots if slot.y is not None]
        for powered_slot in powered_slots:
            if self._use_block_element_power_coverage_for_template(powered_slot.template):
                witness_delta, element_delta = self._add_block_element_power_coverage_witness(
                    powered_slot=powered_slot,
                    pole_slots=pole_slots,
                    radius=int(radius),
                )
            else:
                witness_delta, element_delta = self._add_wide_element_power_coverage_witness(
                    powered_slot=powered_slot,
                    active_lookup=active_lookup,
                    x_lookup=x_lookup,
                    y_lookup=y_lookup,
                    radius=int(radius),
                )
            witness_indices += int(witness_delta)
            element_constraints += int(element_delta)
        power_coverage_encoding = "geometric_element_witness_v1"
        if int(self._power_coverage_witness_encoding_stats.get("block_witness_count", 0)):
            if int(self._power_coverage_witness_encoding_stats.get("wide_witness_count", 0)):
                power_coverage_encoding = "geometric_mixed_block_element_witness_v1"
            else:
                power_coverage_encoding = "geometric_block_element_witness_v1"
        power_coverage_payload = {
            "representation": "coordinate_geometric",
            "encoding": power_coverage_encoding,
            "powered_slots": len(powered_slots),
            "pole_slots": len(pole_slots),
            "cover_literals": 0,
            "witness_indices": int(witness_indices),
            "element_constraints": int(element_constraints),
            "radius": int(radius),
        }
        if (
            self._power_coverage_witness_encoding
            != EXACT_POWER_COVERAGE_WITNESS_ENCODING_ELEMENT
            or self._power_coverage_selected_interval_encoding
            != EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_BOUNDS
            or int(self._power_coverage_witness_encoding_stats.get("block_witness_count", 0))
        ):
            power_coverage_payload["witness_encoding"] = copy.deepcopy(
                self._power_coverage_witness_encoding_stats
            )
        self.owner.build_stats["power_coverage"] = power_coverage_payload

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
                "signature_count": 0,
                "pole_template_evaluations": 0,
                "signature_class_count": 0,
                "signature_class_evaluations": 0,
                "compact_signature_class_count": 0,
                "compact_signature_class_evaluations": 0,
                "compact_signature_hits": 0,
                "compact_signature_misses": 0,
                "normalized_rect_signature_count": 0,
                "normalized_rect_cache_hits": 0,
                "normalized_rect_cache_misses": 0,
                "legacy_signature_materializations": 0,
                "supported_by_pole_materializations": 0,
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
            "signature_bucket_capacity_bounds": {
                "applied": False,
                "mandatory_bucket_upper_bound_constraints": 0,
                "required_optional_bucket_upper_bound_constraints": 0,
                "ghost_conditioned_mandatory_bucket_constraints": int(
                    self._ghost_anchor_signature_bucket_tightening_stats.get(
                        "conditioned_mandatory_bucket_constraints",
                        0,
                    )
                ),
                "ghost_conditioned_required_optional_bucket_constraints": int(
                    self._ghost_anchor_signature_bucket_tightening_stats.get(
                        "conditioned_required_optional_bucket_constraints",
                        0,
                    )
                ),
                "ghost_signature_reduction_anchor_count": int(
                    self._ghost_anchor_signature_bucket_tightening_stats.get(
                        "signature_reduction_anchor_count",
                        0,
                    )
                ),
                "mandatory_groups": [],
                "required_optionals": [],
            },
            "residual_signature_bucket_capacity_bounds": {
                "applied": False,
                "bucket_upper_bound_constraints": 0,
                "ghost_conditioned_residual_bucket_constraints": int(
                    self._ghost_anchor_residual_signature_bucket_tightening_stats.get(
                        "conditioned_residual_bucket_constraints",
                        0,
                    )
                ),
                "ghost_residual_signature_reduction_anchor_count": int(
                    self._ghost_anchor_residual_signature_bucket_tightening_stats.get(
                        "signature_reduction_anchor_count",
                        0,
                    )
                ),
                "templates": [],
            },
            "power_capacity_families": {
                "applied": False,
                "family_count": 0,
                "raw_pole_count": len(self.owner.facility_pools.get("power_pole", [])),
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
            "ghost_aware_via_pole_feasibility": copy.deepcopy(
                self._ghost_anchor_power_capacity_screen_stats
                or {
                    "enabled": bool(self.owner.ghost_rect),
                    "explicit_u_conditioning": False,
                    "evaluated_placements": 0,
                    "disabled_placements": 0,
                    "surviving_placements": 0,
                    "conditioned_family_upper_bound_constraints": 0,
                    "family_reduction_anchor_count": 0,
                    "template_fail_counts": {},
                }
            ),
            "notes": [
                "No power-pole area lower bound is injected into certified exact mode.",
                "Coordinate exact master preserves exact-safe evidence semantics.",
            ],
        }

        signature_stats = stats["signature_bucket_capacity_bounds"]
        mandatory_bucket_upper_bound_constraints = 0
        required_optional_bucket_upper_bound_constraints = 0
        for group in self.owner._mandatory_groups:
            group_id = str(group["group_id"])
            bucket_vars = self.mandatory_signature_count_vars.get(group_id, {})
            if not bucket_vars:
                continue
            group_upper_bound = int(group["count"])
            buckets_payload: List[Dict[str, Any]] = []
            for bucket in self.owner._mandatory_signature_buckets.get(group_id, []):
                bucket_id = str(bucket["bucket_id"])
                if bucket_id not in bucket_vars:
                    continue
                count_var_upper_bound = int(
                    self._mandatory_group_bucket_count_upper_bounds.get(group_id, {}).get(
                        bucket_id,
                        group_upper_bound,
                    )
                )
                if count_var_upper_bound < group_upper_bound:
                    mandatory_bucket_upper_bound_constraints += 1
                buckets_payload.append(
                    {
                        "bucket_id": bucket_id,
                        "bucket_pose_count": int(
                            self._mandatory_group_bucket_pose_counts.get(group_id, {}).get(
                                bucket_id,
                                0,
                            )
                        ),
                        "count_var_upper_bound": int(count_var_upper_bound),
                    }
                )
            signature_stats["mandatory_groups"].append(
                {
                    "group_id": group_id,
                    "buckets": buckets_payload,
                }
            )

        for tpl, slot_specs in sorted(self.required_optional_slots.items()):
            bucket_vars = self.required_optional_signature_count_vars.get(str(tpl), {})
            if not bucket_vars:
                continue
            template_upper_bound = int(len(slot_specs))
            buckets_payload: List[Dict[str, Any]] = []
            for bucket in self.owner._required_optional_signature_buckets.get(str(tpl), []):
                bucket_id = str(bucket["bucket_id"])
                if bucket_id not in bucket_vars:
                    continue
                count_var_upper_bound = int(
                    self._required_optional_bucket_count_upper_bounds.get(str(tpl), {}).get(
                        bucket_id,
                        template_upper_bound,
                    )
                )
                if count_var_upper_bound < template_upper_bound:
                    required_optional_bucket_upper_bound_constraints += 1
                buckets_payload.append(
                    {
                        "bucket_id": bucket_id,
                        "bucket_pose_count": int(
                            self._required_optional_bucket_pose_counts.get(str(tpl), {}).get(
                                bucket_id,
                                0,
                            )
                        ),
                        "count_var_upper_bound": int(count_var_upper_bound),
                    }
                )
            signature_stats["required_optionals"].append(
                {
                    "template": str(tpl),
                    "buckets": buckets_payload,
                }
            )

        signature_stats["mandatory_bucket_upper_bound_constraints"] = int(
            mandatory_bucket_upper_bound_constraints
        )
        signature_stats["required_optional_bucket_upper_bound_constraints"] = int(
            required_optional_bucket_upper_bound_constraints
        )
        signature_stats["applied"] = bool(
            signature_stats["mandatory_groups"] or signature_stats["required_optionals"]
        )

        residual_signature_stats = stats["residual_signature_bucket_capacity_bounds"]
        residual_bucket_upper_bound_constraints = 0
        for tpl, slot_specs in sorted(self.residual_optional_slots.items()):
            bucket_vars = self.residual_optional_signature_count_vars.get(str(tpl), {})
            if not bucket_vars:
                continue
            template_upper_bound = int(len(slot_specs))
            buckets_payload: List[Dict[str, Any]] = []
            for bucket in self._residual_optional_signature_buckets.get(str(tpl), []):
                bucket_id = str(bucket["bucket_id"])
                if bucket_id not in bucket_vars:
                    continue
                count_var_upper_bound = int(
                    self._residual_optional_bucket_count_upper_bounds.get(str(tpl), {}).get(
                        bucket_id,
                        template_upper_bound,
                    )
                )
                if count_var_upper_bound < template_upper_bound:
                    residual_bucket_upper_bound_constraints += 1
                buckets_payload.append(
                    {
                        "bucket_id": bucket_id,
                        "bucket_pose_count": int(
                            self._residual_optional_bucket_pose_counts.get(str(tpl), {}).get(
                                bucket_id,
                                0,
                            )
                        ),
                        "count_var_upper_bound": int(count_var_upper_bound),
                    }
                )
            residual_signature_stats["templates"].append(
                {
                    "template": str(tpl),
                    "buckets": buckets_payload,
                }
            )

        residual_signature_stats["bucket_upper_bound_constraints"] = int(
            residual_bucket_upper_bound_constraints
        )
        residual_signature_stats["applied"] = bool(
            residual_signature_stats["templates"]
        )
        signature_tightening_instrumentation = (
            self._ghost_anchor_signature_bucket_tightening_stats.get(
                "signature_tightening_instrumentation"
            )
        )
        if signature_tightening_instrumentation is not None:
            signature_stats["signature_tightening_instrumentation"] = copy.deepcopy(
                signature_tightening_instrumentation
            )
        residual_overlay_instrumentation = (
            self._ghost_anchor_residual_signature_bucket_tightening_stats.get(
                "residual_overlay_instrumentation"
            )
        )
        if residual_overlay_instrumentation is not None:
            residual_signature_stats["residual_overlay_instrumentation"] = copy.deepcopy(
                residual_overlay_instrumentation
            )

        protocol_count = int(self.owner._required_protocol_storage_box_lower_bound())
        protocol_fixed_required_count = int(
            len(self.required_optional_slots.get("protocol_storage_box", []))
        )
        protocol_slots = list(self.residual_optional_slots.get("protocol_storage_box", []))
        stats["optional_cardinality_bounds"]["protocol_storage_box"] = {
            "mode": "required_lower_bound",
            "required_generic_input_slots": int(self.owner._required_generic_input_slot_total()),
            "slots_per_pose": int(self.owner.wireless_sink_generic_input_slots),
            "lower": int(protocol_count),
            "upper": None,
            "candidate_pose_count": int(len(self.owner.facility_pools.get("protocol_storage_box", []))),
            "slot_pool_upper_bound": int(len(protocol_slots)),
        }
        stats["applied"].append(
            {
                "type": "optional_cardinality_bound",
                "template": "protocol_storage_box",
                "mode": "required_lower_bound",
                "lower": int(protocol_count),
                "upper": None,
            }
        )
        if protocol_count > 0:
            protocol_terms = [
                slot.active
                for slot in protocol_slots
                if slot.active is not None
            ]
            protocol_shortfall = int(protocol_count) - int(protocol_fixed_required_count)
            if protocol_shortfall > 0:
                if protocol_terms:
                    self.model.Add(sum(protocol_terms) >= int(protocol_shortfall))
                else:
                    self.model.Add(0 >= int(protocol_shortfall))

        mandatory_powered_nonpole = int(self.owner._mandatory_powered_nonpole_count())
        optional_powered_templates = sorted(
            {
                str(tpl)
                for tpl in self.required_optional_slots
                if str(tpl) in self.owner._powered_templates and str(tpl) != "power_pole"
            }
            | {
                str(tpl)
                for tpl in self.residual_optional_slots
                if str(tpl) in self.owner._powered_templates and str(tpl) != "power_pole"
            }
        )
        stats["optional_cardinality_bounds"]["power_pole"] = {
            "mode": "selected_powered_upper_bound",
            "lower": 0,
            "candidate_pose_count": int(len(self.owner.facility_pools.get("power_pole", []))),
            "mandatory_powered_nonpole": int(mandatory_powered_nonpole),
            "optional_powered_templates": optional_powered_templates,
            "slot_pool_upper_bound": int(self._power_pole_slot_upper_bound),
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
        if self.residual_optional_slots.get("power_pole"):
            required_optional_powered_count = sum(
                len(slot_specs)
                for tpl, slot_specs in self.required_optional_slots.items()
                if str(tpl) in self.owner._powered_templates and str(tpl) != "power_pole"
            )
            residual_powered_optional_terms = [
                slot.active
                for tpl, slot_specs in self.residual_optional_slots.items()
                if str(tpl) in self.owner._powered_templates and str(tpl) != "power_pole"
                for slot in slot_specs
                if slot.active is not None
            ]
            self.model.Add(
                sum(slot.active for slot in self.residual_optional_slots["power_pole"] if slot.active is not None)
                <= int(mandatory_powered_nonpole)
                + int(required_optional_powered_count)
                + sum(residual_powered_optional_terms)
            )

        stats["fixed_required_optional_demands"] = dict(self.owner._exact_fixed_required_optional_powered_demands())
        stats["lower_bound_optional_powered_demands"] = dict(self.owner._lower_bound_optional_powered_demands())
        if self.owner.skip_power_coverage:
            stats["power_capacity_families"]["reason"] = "power_coverage_skipped"
            stats["aggregated_power_capacity_terms"]["reason"] = "power_coverage_skipped"
            stats["capacity_cache"] = dict(self._power_capacity_cache_stats)
            stats["capacity_coeff_stats"] = copy.deepcopy(self._power_capacity_coeff_stats)
            self.owner.build_stats["global_valid_inequalities"] = stats
            return

        powered_template_demands = self.owner._exact_powered_template_demands()
        stats["powered_template_demands"] = dict(powered_template_demands)
        if not powered_template_demands or not self.power_pole_family_count_vars:
            stats["power_capacity_families"]["reason"] = "no_powered_template_demands"
            stats["aggregated_power_capacity_terms"]["reason"] = "no_powered_template_demands"
            stats["capacity_cache"] = dict(self._power_capacity_cache_stats)
            stats["capacity_coeff_stats"] = copy.deepcopy(self._power_capacity_coeff_stats)
            self.owner.build_stats["global_valid_inequalities"] = stats
            return

        template_order = sorted(powered_template_demands)
        family_payload: List[Dict[str, Any]] = []
        for family_name, coefficients in sorted(self._power_pole_family_coefficients.items()):
            family_payload.append(
                {
                    "family_id": family_name,
                    "size": int(self._power_pole_family_pose_counts.get(family_name, 0)),
                    "count_var_upper_bound": int(
                        self._power_pole_family_count_upper_bound(family_name)
                    ),
                    "coefficients": {str(tpl): int(coefficients.get(str(tpl), 0)) for tpl in template_order},
                }
            )

        raw_nonzero_terms = 0
        aggregated_nonzero_terms = 0
        for tpl, demand in sorted(powered_template_demands.items()):
            terms: List[cp_model.LinearExpr] = []
            nonzero_pose_count = 0
            for pose_idx in range(len(self.owner.facility_pools.get("power_pole", []))):
                family_id = self._power_pole_family_id_by_pose_idx.get(int(pose_idx))
                if family_id is None:
                    continue
                family_name = self._power_pole_family_name_by_int[int(family_id)]
                if int(self._power_pole_family_coefficients[family_name].get(str(tpl), 0)) > 0:
                    nonzero_pose_count += 1
            raw_nonzero_terms += int(nonzero_pose_count)
            for family_name, count_var in sorted(self.power_pole_family_count_vars.items()):
                coeff = int(self._power_pole_family_coefficients[family_name].get(str(tpl), 0))
                if coeff <= 0:
                    continue
                aggregated_nonzero_terms += 1
                terms.append(coeff * count_var)
            if terms:
                self.model.Add(sum(terms) >= int(demand))
            else:
                self.model.Add(0 >= int(demand))
            stats["applied"].append(
                {
                    "type": "power_capacity_lower_bound",
                    "template": str(tpl),
                    "demand": int(demand),
                    "nonzero_poles": int(nonzero_pose_count),
                }
            )

        stats["power_capacity_families"] = {
            "applied": True,
            "family_count": int(len(self.power_pole_family_count_vars)),
            "raw_pole_count": int(len(self.owner.facility_pools.get("power_pole", []))),
            "coefficient_source": str(
                self._power_capacity_cache_stats.get(
                    "coefficient_source",
                    "exact_compact_rect_cpsat_v14",
                )
            ),
            "shell_pair_count": int(self._power_capacity_cache_stats.get("shell_pair_count", 0)),
            "compact_signature_class_count": int(
                self._power_capacity_cache_stats.get("compact_signature_class_count", 0)
            ),
            "families": family_payload,
        }
        stats["aggregated_power_capacity_terms"] = {
            "applied": True,
            "raw_nonzero_terms": int(raw_nonzero_terms),
            "aggregated_nonzero_terms": int(aggregated_nonzero_terms),
        }
        stats["capacity_cache"] = dict(self._power_capacity_cache_stats)
        stats["capacity_coeff_stats"] = copy.deepcopy(self._power_capacity_coeff_stats)
        self.owner.build_stats["global_valid_inequalities"] = stats

    def _group_port_demand(self, operation_type: str) -> int:
        try:
            profile = get_operation_port_profile(str(operation_type))
        except KeyError:
            return 0
        return int(
            sum(profile.input_slots.values())
            + sum(profile.output_slots.values())
            + int(profile.generic_input_slots)
            + int(profile.generic_output_slots)
        )

    def _ordered_groups_for_search(self) -> List[Dict[str, Any]]:
        return sorted(
            self.owner._mandatory_groups,
            key=lambda group: (
                int(self._mandatory_group_pose_counts.get(str(group["group_id"]), 0)),
                -self._group_port_demand(str(group.get("operation_type", ""))),
                str(group["facility_type"]),
                str(group["group_id"]),
            ),
        )

    def _add_slot_decision_strategies(self, slot_specs: Sequence[CoordinateSlotSpec]) -> int:
        mode_literals = 0
        for slot in slot_specs:
            if slot.slot_kind == "residual_optional" and slot.active is not None:
                self.model.AddDecisionStrategy([slot.active], cp_model.CHOOSE_FIRST, cp_model.SELECT_MIN_VALUE)
            if slot.slot_kind == "residual_optional" and slot.template == "power_pole":
                if slot.family is not None and self._power_pole_family_order:
                    self.model.AddDecisionStrategy([slot.family], cp_model.CHOOSE_FIRST, cp_model.SELECT_MIN_VALUE)
            else:
                self.model.AddDecisionStrategy([slot.mode], cp_model.CHOOSE_FIRST, cp_model.SELECT_MIN_VALUE)
            self.model.AddDecisionStrategy([slot.x], cp_model.CHOOSE_FIRST, cp_model.SELECT_MIN_VALUE)
            self.model.AddDecisionStrategy([slot.y], cp_model.CHOOSE_FIRST, cp_model.SELECT_MIN_VALUE)
            if not (slot.slot_kind == "residual_optional" and slot.template == "power_pole"):
                mode_literals += int(self._template_mode_literals.get(slot.template, 1))
        return mode_literals

    def _add_search_guidance(self) -> None:
        search_profile = normalize_exact_coordinate_master_search_profile(
            getattr(self.owner, "master_search_profile", None)
        )
        ordered_groups = self._ordered_groups_for_search()
        mandatory_signature_counts: Dict[str, int] = {}
        required_optional_signature_counts: Dict[str, int] = {}
        mandatory_signature_count_literals = 0
        required_optional_signature_count_literals = 0
        mandatory_mode_literals = 0
        required_optional_mode_literals = 0
        residual_optional_mode_literals = 0
        mandatory_literals = 0
        ghost_literals = 0
        required_optional_literals: Dict[str, int] = {}
        residual_optional_literals: Dict[str, int] = {}
        power_pole_family_count_literals = 0
        power_pole_family_order: List[str] = []
        residual_optional_family_guided = False
        decision_strategy_phases: List[str] = []

        mandatory_count_vars_by_group: Dict[str, List[cp_model.IntVar]] = {}
        mandatory_slot_specs_by_group: Dict[str, List[CoordinateSlotSpec]] = {}
        for group in ordered_groups:
            group_id = str(group["group_id"])
            mandatory_count_vars_by_group[group_id] = [
                self.mandatory_signature_count_vars[group_id][str(bucket["bucket_id"])]
                for bucket in self.owner._mandatory_signature_buckets.get(group_id, [])
                if str(bucket["bucket_id"]) in self.mandatory_signature_count_vars.get(group_id, {})
            ]
            mandatory_slot_specs_by_group[group_id] = list(self.mandatory_slots[group_id])

        ordered_ghost_indices = sorted(
            self.owner.u_vars,
            key=lambda rect_idx: (
                int(self.owner._ghost_domains[int(rect_idx)]["anchor"]["x"]),
                int(self.owner._ghost_domains[int(rect_idx)]["anchor"]["y"]),
                int(rect_idx),
            ),
        )

        def add_mandatory_counts_phase() -> None:
            nonlocal mandatory_signature_count_literals
            decision_strategy_phases.append("mandatory_signature_counts")
            for group in ordered_groups:
                group_id = str(group["group_id"])
                count_vars = list(mandatory_count_vars_by_group[group_id])
                if count_vars:
                    self.model.AddDecisionStrategy(
                        count_vars,
                        cp_model.CHOOSE_FIRST,
                        cp_model.SELECT_MAX_VALUE,
                    )
                mandatory_signature_counts[group_id] = len(count_vars)
                mandatory_signature_count_literals += len(count_vars)

        def add_mandatory_slots_phase() -> None:
            nonlocal mandatory_mode_literals, mandatory_literals
            decision_strategy_phases.append("mandatory_slots")
            for group in ordered_groups:
                group_id = str(group["group_id"])
                mandatory_mode_literals += self._add_slot_decision_strategies(
                    mandatory_slot_specs_by_group[group_id]
                )
                mandatory_literals += sum(
                    slot.candidate_pose_count
                    for slot in mandatory_slot_specs_by_group[group_id]
                )

        def add_ghost_phase() -> None:
            nonlocal ghost_literals
            decision_strategy_phases.append("ghost")
            if ordered_ghost_indices:
                self.model.AddDecisionStrategy(
                    [self.owner.u_vars[idx] for idx in ordered_ghost_indices],
                    cp_model.CHOOSE_FIRST,
                    cp_model.SELECT_MAX_VALUE,
                )
                ghost_literals = len(ordered_ghost_indices)

        if search_profile == DEFAULT_EXACT_COORDINATE_MASTER_SEARCH_PROFILE:
            add_mandatory_counts_phase()
            add_mandatory_slots_phase()
            add_ghost_phase()
        elif search_profile == "exact_coordinate_ghost_after_counts_v1":
            add_mandatory_counts_phase()
            add_ghost_phase()
            add_mandatory_slots_phase()
        elif search_profile == "exact_coordinate_ghost_first_v1":
            add_ghost_phase()
            add_mandatory_counts_phase()
            add_mandatory_slots_phase()
        else:
            raise ValueError(f"Unsupported master_search_profile: {search_profile}")

        required_optional_templates = sorted(self.required_optional_slots)
        decision_strategy_phases.append("required_optional_signature_counts")
        for tpl in required_optional_templates:
            count_vars = [
                self.required_optional_signature_count_vars[tpl][str(bucket["bucket_id"])]
                for bucket in self.owner._required_optional_signature_buckets.get(tpl, [])
                if str(bucket["bucket_id"]) in self.required_optional_signature_count_vars.get(tpl, {})
            ]
            if count_vars:
                self.model.AddDecisionStrategy(count_vars, cp_model.CHOOSE_FIRST, cp_model.SELECT_MAX_VALUE)
            required_optional_signature_counts[tpl] = len(count_vars)
            required_optional_signature_count_literals += len(count_vars)

        decision_strategy_phases.append("required_optional_slots")
        for tpl in required_optional_templates:
            required_optional_mode_literals += self._add_slot_decision_strategies(self.required_optional_slots[tpl])
            required_optional_literals[tpl] = sum(
                slot.candidate_pose_count for slot in self.required_optional_slots[tpl]
            )

        decision_strategy_phases.append("residual_optional_family_counts")
        for tpl, slot_specs in sorted(self.residual_optional_slots.items()):
            if tpl == "power_pole":
                ordered_family_vars = [
                    self.power_pole_family_count_vars[family_name]
                    for family_name in self._power_pole_family_order
                    if family_name in self.power_pole_family_count_vars
                ]
                if ordered_family_vars:
                    self.model.AddDecisionStrategy(
                        ordered_family_vars,
                        cp_model.CHOOSE_FIRST,
                        cp_model.SELECT_MIN_VALUE,
                    )
                    power_pole_family_count_literals = len(ordered_family_vars)
                    power_pole_family_order = list(self._power_pole_family_order)
                    residual_optional_family_guided = True
        decision_strategy_phases.append("residual_optional_slots")
        for tpl, slot_specs in sorted(self.residual_optional_slots.items()):
            residual_optional_mode_literals += self._add_slot_decision_strategies(slot_specs)
            residual_optional_literals[tpl] = sum(slot.candidate_pose_count for slot in slot_specs)

        self.owner.build_stats["search_guidance"] = {
            "applied": True,
            "profile": search_profile,
            "search_branching": "FIXED_SEARCH",
            "decision_strategy_phases": list(decision_strategy_phases),
            "ghost_phase_index": int(decision_strategy_phases.index("ghost")),
            "mandatory_group_order": [str(group["group_id"]) for group in ordered_groups],
            "mandatory_signature_counts": {str(k): int(v) for k, v in mandatory_signature_counts.items()},
            "mandatory_signature_count_literals": int(mandatory_signature_count_literals),
            "required_optional_templates": [str(tpl) for tpl in required_optional_templates],
            "required_optional_signature_counts": {str(k): int(v) for k, v in required_optional_signature_counts.items()},
            "required_optional_signature_count_literals": int(required_optional_signature_count_literals),
            "required_optional_default": "SELECT_MAX_VALUE",
            "power_pole_family_order": list(power_pole_family_order),
            "power_pole_family_count_literals": int(power_pole_family_count_literals),
            "residual_optional_family_guided": bool(residual_optional_family_guided),
            "residual_optional_default": "SELECT_MIN_VALUE",
            "mandatory_literals": int(mandatory_literals),
            "ghost_literals": int(ghost_literals),
            "required_optional_literals": {str(k): int(v) for k, v in required_optional_literals.items()},
            "residual_optional_literals": {str(k): int(v) for k, v in residual_optional_literals.items()},
            "optional_literals": {
                **{str(k): int(v) for k, v in required_optional_literals.items()},
                **{str(k): int(v) for k, v in residual_optional_literals.items()},
            },
            "optional_default": "SELECT_MIN_VALUE",
            "mandatory_signature_guided": True,
            "required_optional_signature_guided": True,
            "mandatory_mode_literals": int(mandatory_mode_literals),
            "required_optional_mode_literals": int(required_optional_mode_literals),
            "residual_optional_mode_literals": int(residual_optional_mode_literals),
        }

    def _mode_rect_domains_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "mandatory_groups": {},
            "required_optionals": {},
            "residual_optionals": {},
        }
        for group_id, domains in sorted(self._mandatory_group_mode_rect_domains.items()):
            payload["mandatory_groups"][str(group_id)] = [
                {
                    "mode_id": int(domain.mode_id),
                    "orientation": str(domain.orientation),
                    "port_mode": str(domain.port_mode),
                    "x_min": int(domain.x_min),
                    "x_max": int(domain.x_max),
                    "y_min": int(domain.y_min),
                    "y_max": int(domain.y_max),
                    "pose_count": int(domain.pose_count),
                }
                for _mode_id, domain in sorted(domains.items())
            ]
        for tpl, domains in sorted(self._required_optional_mode_rect_domains.items()):
            payload["required_optionals"][str(tpl)] = [
                {
                    "mode_id": int(domain.mode_id),
                    "orientation": str(domain.orientation),
                    "port_mode": str(domain.port_mode),
                    "x_min": int(domain.x_min),
                    "x_max": int(domain.x_max),
                    "y_min": int(domain.y_min),
                    "y_max": int(domain.y_max),
                    "pose_count": int(domain.pose_count),
                }
                for _mode_id, domain in sorted(domains.items())
            ]
        for tpl in sorted(self.residual_optional_slots):
            domains = self._template_full_mode_rect_domains.get(str(tpl), {})
            payload["residual_optionals"][str(tpl)] = [
                {
                    "mode_id": int(domain.mode_id),
                    "orientation": str(domain.orientation),
                    "port_mode": str(domain.port_mode),
                    "x_min": int(domain.x_min),
                    "x_max": int(domain.x_max),
                    "y_min": int(domain.y_min),
                    "y_max": int(domain.y_max),
                    "pose_count": int(domain.pose_count),
                }
                for _mode_id, domain in sorted(domains.items())
            ]
        return payload

    def _finalize_build_stats(self) -> None:
        mandatory_slot_count = int(sum(len(v) for v in self.mandatory_slots.values()))
        required_optional_slot_count = int(
            sum(len(v) for v in self.required_optional_slots.values())
        )
        residual_optional_slot_count = int(
            sum(len(v) for v in self.residual_optional_slots.values())
        )
        slot_counts = {
            "mandatory": int(mandatory_slot_count),
            "required_optionals": {str(tpl): int(len(v)) for tpl, v in sorted(self.required_optional_slots.items())},
            "residual_optionals": {str(tpl): int(len(v)) for tpl, v in sorted(self.residual_optional_slots.items())},
        }
        interval_count = 2 * (
            int(mandatory_slot_count)
            + int(required_optional_slot_count)
            + int(residual_optional_slot_count)
            + len(self.owner.u_vars)
        )
        guidance = dict(self.owner.build_stats.get("search_guidance", {}))
        mode_literals = int(guidance.get("mandatory_mode_literals", 0)) + int(guidance.get("required_optional_mode_literals", 0)) + int(guidance.get("residual_optional_mode_literals", 0))
        domain_activation = {
            "ghost_anchor_count": int(len(self.owner.u_vars)),
            "mandatory_slot_count": int(mandatory_slot_count),
            "required_optional_slot_count": int(required_optional_slot_count),
            "residual_optional_slot_count": int(residual_optional_slot_count),
            "mandatory_pose_literal_count": int(
                sum(
                    int(slot.candidate_pose_count)
                    for slot_specs in self.mandatory_slots.values()
                    for slot in slot_specs
                )
            ),
            "required_optional_pose_literal_count": int(
                sum(
                    int(slot.candidate_pose_count)
                    for slot_specs in self.required_optional_slots.values()
                    for slot in slot_specs
                )
            ),
            "residual_optional_pose_literal_count": int(
                sum(
                    int(slot.candidate_pose_count)
                    for slot_specs in self.residual_optional_slots.values()
                    for slot in slot_specs
                )
            ),
            "required_optional_active_slot_upper_bound_sum": int(
                required_optional_slot_count
            ),
            "residual_optional_active_slot_upper_bound_sum": int(
                residual_optional_slot_count
            ),
        }
        self.owner.build_stats["master_representation"] = self.master_representation
        self.owner.build_stats["master_domain_encoding"] = "mode_rect_factorized_v1"
        self.owner.build_stats["master_domain_table_rows"] = int(self._domain_table_row_count)
        self.owner.build_stats["master_mode_rect_domains"] = self._mode_rect_domains_payload()
        self.owner.build_stats["power_pole_shell_lookup_pairs"] = self._power_pole_shell_payload()
        lookup_stats = copy.deepcopy(self._power_family_lookup_encoding_stats)
        existing_lookup_stats = dict(
            self.owner.build_stats.get("power_family_lookup_encoding", {})
        )
        if (
            int(lookup_stats.get("slot_count", 0)) == 0
            and int(existing_lookup_stats.get("slot_count", 0)) > 0
            and str(existing_lookup_stats.get("encoding"))
            == str(self._power_family_lookup_encoding)
        ):
            lookup_stats = copy.deepcopy(existing_lookup_stats)
        self.owner.build_stats["power_family_lookup_encoding"] = lookup_stats
        distance_stats = copy.deepcopy(self._power_pole_shell_distance_encoding_stats)
        existing_distance_stats = dict(
            self.owner.build_stats.get("power_pole_shell_distance_encoding", {})
        )
        if (
            int(distance_stats.get("slot_count", 0)) == 0
            and int(existing_distance_stats.get("slot_count", 0)) > 0
            and str(existing_distance_stats.get("encoding"))
            == str(self._power_pole_shell_distance_encoding)
        ):
            distance_stats = copy.deepcopy(existing_distance_stats)
        self.owner.build_stats["power_pole_shell_distance_encoding"] = distance_stats
        self.owner.build_stats["master_slot_counts"] = slot_counts
        self.owner.build_stats["domain_activation"] = domain_activation
        self.owner.build_stats["master_interval_count"] = int(interval_count)
        self.owner.build_stats["master_mode_literals"] = int(mode_literals)
        self.owner.build_stats["master_pose_bool_literals"] = 0
        proto = self.model.Proto()
        self.owner.build_stats["exact_core_profile"] = {
            "proto_vars": len(proto.variables),
            "proto_constraints": len(proto.constraints),
            "master_representation": self.master_representation,
        }

    def _slot_pose_idx(self, slot: CoordinateSlotSpec) -> int:
        pose_tuple = (
            int(self.owner._solver.Value(slot.x)),
            int(self.owner._solver.Value(slot.y)),
            int(self.owner._solver.Value(slot.mode)),
        )
        pose_idx = slot.tuple_to_pose_idx.get(pose_tuple)
        if pose_idx is None:
            raise KeyError(f"Unknown pose tuple for {slot.key}: {pose_tuple}")
        return int(pose_idx)

    def extract_solution(self) -> Dict[str, Any]:
        solution: Dict[str, Any] = {}
        optional_operations = {"power_pole": "power_supply", "protocol_storage_box": "wireless_sink"}
        for group in self.owner._mandatory_groups:
            group_id = str(group["group_id"])
            tpl = str(group["facility_type"])
            operation_type = str(group["operation_type"])
            selected_pose_indices = sorted(self._slot_pose_idx(slot) for slot in self.mandatory_slots.get(group_id, []))
            for instance_id, pose_idx in zip(sorted(group["instance_ids"]), selected_pose_indices):
                pose = self.owner.facility_pools[tpl][int(pose_idx)]
                solution[str(instance_id)] = {
                    "instance_id": str(instance_id),
                    "facility_type": tpl,
                    "operation_type": operation_type,
                    "pose_idx": int(pose_idx),
                    "pose_id": pose["pose_id"],
                    "anchor": dict(pose["anchor"]),
                    "is_mandatory": True,
                    "bound_type": "exact",
                    "solve_mode": self.owner.solve_mode,
                }
        for tpl, slot_specs in sorted(self.required_optional_slots.items()):
            for pose_idx in sorted(self._slot_pose_idx(slot) for slot in slot_specs):
                pose = self.owner.facility_pools[tpl][int(pose_idx)]
                synthetic_id = f"pose_optional::{tpl}::{pose['pose_id']}"
                solution[synthetic_id] = {
                    "instance_id": synthetic_id,
                    "facility_type": tpl,
                    "operation_type": optional_operations[tpl],
                    "pose_idx": int(pose_idx),
                    "pose_id": pose["pose_id"],
                    "anchor": dict(pose["anchor"]),
                    "is_mandatory": False,
                    "bound_type": "exact_pose_optional",
                    "solve_mode": self.owner.solve_mode,
                }
        for tpl, slot_specs in sorted(self.residual_optional_slots.items()):
            selected = [
                self._slot_pose_idx(slot)
                for slot in slot_specs
                if slot.active is not None and self.owner._solver.Value(slot.active) == 1
            ]
            for pose_idx in sorted(selected):
                pose = self.owner.facility_pools[tpl][int(pose_idx)]
                synthetic_id = f"pose_optional::{tpl}::{pose['pose_id']}"
                solution[synthetic_id] = {
                    "instance_id": synthetic_id,
                    "facility_type": tpl,
                    "operation_type": optional_operations[tpl],
                    "pose_idx": int(pose_idx),
                    "pose_id": pose["pose_id"],
                    "anchor": dict(pose["anchor"]),
                    "is_mandatory": False,
                    "bound_type": "exact_pose_optional",
                    "solve_mode": self.owner.solve_mode,
                }
        return solution

    @staticmethod
    def _strict_int_hint_value(value: Any) -> Optional[int]:
        return parse_strict_int_hint_value(value)

    def apply_solution_hint(
        self,
        solution_hint: Mapping[str, int],
        *,
        ghost_anchor_hint_idx: Optional[int] = None,
        hint_inactive_residual_optionals: bool = True,
    ) -> Dict[str, Any]:
        hinted = 0
        residual_optional_zero_hints = 0
        grouped_hints: DefaultDict[str, List[int]] = defaultdict(list)
        optional_hints: DefaultDict[str, List[int]] = defaultdict(list)
        mandatory_template_by_group = {
            str(group["group_id"]): str(group["facility_type"])
            for group in self.owner._mandatory_groups
        }
        for solution_id, pose_idx in solution_hint.items():
            pose_idx_int = self._strict_int_hint_value(pose_idx)
            if pose_idx_int is None:
                continue
            if solution_id in self.owner._group_id_by_instance:
                group_id = str(self.owner._group_id_by_instance[solution_id])
                tpl = mandatory_template_by_group.get(group_id)
                if tpl is None or pose_idx_int not in self._template_pose_tuple_by_idx.get(tpl, {}):
                    continue
                grouped_hints[group_id].append(pose_idx_int)
                continue
            tpl = self.owner._infer_optional_template_from_solution_id(str(solution_id))
            if tpl is not None:
                tpl_key = str(tpl)
                if pose_idx_int not in self._template_pose_tuple_by_idx.get(tpl_key, {}):
                    continue
                optional_hints[tpl_key].append(pose_idx_int)

        for group in self.owner._mandatory_groups:
            group_id = str(group["group_id"])
            tpl = str(group["facility_type"])
            hinted_pose_indices = sorted(grouped_hints.get(group_id, []), key=lambda pose_idx: self.owner._pose_sort_key(tpl, int(pose_idx)))
            for slot, pose_idx in zip(self.mandatory_slots.get(group_id, []), hinted_pose_indices):
                x_val, y_val, mode_id = self._template_pose_tuple_by_idx[tpl][int(pose_idx)]
                self.model.AddHint(slot.x, int(x_val))
                self.model.AddHint(slot.y, int(y_val))
                self.model.AddHint(slot.mode, int(mode_id))
                hinted += 3

        for tpl, slot_specs in self.required_optional_slots.items():
            hinted_pose_indices = sorted(optional_hints.get(str(tpl), []), key=lambda pose_idx: self.owner._pose_sort_key(str(tpl), int(pose_idx)))
            for slot, pose_idx in zip(slot_specs, hinted_pose_indices):
                x_val, y_val, mode_id = self._template_pose_tuple_by_idx[str(tpl)][int(pose_idx)]
                self.model.AddHint(slot.x, int(x_val))
                self.model.AddHint(slot.y, int(y_val))
                self.model.AddHint(slot.mode, int(mode_id))
                hinted += 3

        for tpl, slot_specs in self.residual_optional_slots.items():
            hinted_pose_indices = sorted(optional_hints.get(str(tpl), []), key=lambda pose_idx: self.owner._pose_sort_key(str(tpl), int(pose_idx)))
            for slot_idx, slot in enumerate(slot_specs):
                if slot_idx < len(hinted_pose_indices):
                    pose_idx = hinted_pose_indices[slot_idx]
                    x_val, y_val, mode_id = self._template_pose_tuple_by_idx[str(tpl)][int(pose_idx)]
                    self.model.AddHint(slot.active, 1)
                    self.model.AddHint(slot.x, int(x_val))
                    self.model.AddHint(slot.y, int(y_val))
                    self.model.AddHint(slot.mode, int(mode_id))
                    hinted += 4
                elif hint_inactive_residual_optionals:
                    self.model.AddHint(slot.active, 0)
                    hinted += 1
                    residual_optional_zero_hints += 1

        ghost_anchor_hint_applied = False
        selected_ghost_anchor_hint_idx = self._strict_int_hint_value(ghost_anchor_hint_idx)
        if selected_ghost_anchor_hint_idx is not None and self.owner.u_vars:
            if selected_ghost_anchor_hint_idx in self.owner.u_vars:
                for rect_idx in self.owner._ordered_ghost_anchor_indices():
                    self.model.AddHint(
                        self.owner.u_vars[int(rect_idx)],
                        1 if int(rect_idx) == selected_ghost_anchor_hint_idx else 0,
                    )
                    hinted += 1
                ghost_anchor_hint_applied = True

        return {
            "hinted_literals": int(hinted),
            "ghost_anchor_hint_applied": bool(ghost_anchor_hint_applied),
            "ghost_anchor_hint_idx": selected_ghost_anchor_hint_idx,
            "residual_optional_zero_hinting_enabled": bool(
                hint_inactive_residual_optionals
            ),
            "residual_optional_zero_hints": int(residual_optional_zero_hints),
        }

    def _cut_name_token(self, raw: Any) -> str:
        token = re.sub(r"[^A-Za-z0-9_]+", "_", str(raw))
        return token[:96] or "cut"

    def _slot_can_take_pose(self, slot: CoordinateSlotSpec, pose_tuple: PoseTuple) -> bool:
        normalized = tuple(int(v) for v in pose_tuple)
        if slot.allowed_tuples:
            return normalized in set(slot.allowed_tuples)
        return normalized in set(slot.tuple_to_pose_idx)

    def _eq_literal(
        self, var: cp_model.IntVar, value: int, name: str
    ) -> cp_model.IntVar:
        # Content-addressed: one reified equality per (variable, value). The
        # `name` argument is only used the first time the literal is minted;
        # the definition is identical for every caller, so reuse is exact.
        key = (var.Index(), int(value))
        cached = self._eq_literal_cache.get(key)
        if cached is not None:
            return cached
        lit = self.model.NewBoolVar(name)
        self.model.Add(var == int(value)).OnlyEnforceIf(lit)
        self.model.Add(var != int(value)).OnlyEnforceIf(lit.Not())
        self._eq_literal_cache[key] = lit
        return lit

    def _slot_pose_match_literal(
        self,
        slot: CoordinateSlotSpec,
        pose_tuple: PoseTuple,
    ) -> Optional[cp_model.IntVar]:
        # lit ⇔ slot realizes pose_tuple. Residual optional slots additionally
        # require active==1 (so the cut only fires when the optional is on).
        # Content-addressed on (slot.key, pose): the definition depends only on
        # build-time variable bindings and the pose constants, never on which
        # cut requested it, so cross-cut reuse is exact (M3-2). A None result
        # (slot cannot take the pose) is equally state-independent and cached.
        normalized = (
            int(pose_tuple[0]), int(pose_tuple[1]), int(pose_tuple[2])
        )
        cache_key = (str(slot.key), normalized)
        if cache_key in self._slot_pose_match_cache:
            return self._slot_pose_match_cache[cache_key]

        if slot.x is None or slot.y is None or slot.mode is None:
            self._slot_pose_match_cache[cache_key] = None
            return None
        if not self._slot_can_take_pose(slot, pose_tuple):
            self._slot_pose_match_cache[cache_key] = None
            return None

        x_val, y_val, mode_id = normalized
        slot_tag = self._cut_name_token(slot.key)
        pose_tag = f"{x_val}_{y_val}_{mode_id}"

        conditions: List[cp_model.IntVar] = [
            self._eq_literal(slot.x, x_val, f"eq_x__{slot_tag}__{pose_tag}"),
            self._eq_literal(slot.y, y_val, f"eq_y__{slot_tag}__{pose_tag}"),
            self._eq_literal(slot.mode, mode_id, f"eq_m__{slot_tag}__{pose_tag}"),
        ]
        if slot.active is not None:
            conditions.append(
                self._eq_literal(slot.active, 1, f"eq_a__{slot_tag}__{pose_tag}")
            )

        match = self.model.NewBoolVar(f"match_pose__{slot_tag}__{pose_tag}")
        for cond in conditions:
            self.model.AddImplication(match, cond)
        self.model.AddBoolOr([cond.Not() for cond in conditions] + [match])
        self._slot_pose_match_cache[cache_key] = match
        return match

    def _pose_present_literal(
        self,
        slots: Sequence[CoordinateSlotSpec],
        pose_tuple: PoseTuple,
    ) -> Optional[cp_model.IntVar]:
        # lit ⇔ any slot in `slots` realizes pose_tuple. Content-addressed on
        # (sorted slot keys, pose) — see the cache-field comment in __init__.
        normalized = (
            int(pose_tuple[0]), int(pose_tuple[1]), int(pose_tuple[2])
        )
        slot_keys = tuple(sorted(str(slot.key) for slot in slots))
        cache_key = (slot_keys, normalized)
        if cache_key in self._pose_present_cache:
            return self._pose_present_cache[cache_key]

        match_lits: List[cp_model.IntVar] = []
        for slot in slots:
            lit = self._slot_pose_match_literal(slot, pose_tuple)
            if lit is not None:
                match_lits.append(lit)
        if not match_lits:
            self._pose_present_cache[cache_key] = None
            return None

        pose_tag = f"{normalized[0]}_{normalized[1]}_{normalized[2]}"
        present = self.model.NewBoolVar(
            f"pose_present__{self._cut_name_token(slot_keys[0])}__{pose_tag}__{len(match_lits)}"
        )
        for match in match_lits:
            self.model.AddImplication(match, present)
        self.model.AddBoolOr(match_lits).OnlyEnforceIf(present)
        self._pose_present_cache[cache_key] = present
        return present

    def _conflict_pose_entries(
        self, conflict_set: Mapping[str, int]
    ) -> List[Tuple[str, int, List[CoordinateSlotSpec], PoseTuple]]:
        # Normalize each (solution_id, pose_idx) into the slot set + pose tuple
        # it can land in. Certified replay must be all-or-nothing: silently
        # dropping one malformed member of a persisted conflict would dilute a
        # nogood over {A, B} into a stronger nogood over {A}, which can
        # over-prune valid layouts. The same fail-closed rule applies when two
        # distinct conflict members alias to the same abstract presence literal
        # (for example two symmetric mandatory instances in the same group with
        # the same pose_idx): that persisted cut cannot be represented faithfully
        # by this master backend.
        entries: List[Tuple[str, int, List[CoordinateSlotSpec], PoseTuple]] = []
        seen: Set[Tuple[str, int]] = set()
        for solution_id, raw_pose_idx in conflict_set.items():
            try:
                pose_idx = int(raw_pose_idx)
            except Exception:
                return []
            sid = str(solution_id)

            if sid in self.owner._group_id_by_instance:
                group_id = str(self.owner._group_id_by_instance[sid])
                tpl = next(
                    (
                        str(group["facility_type"])
                        for group in self.owner._mandatory_groups
                        if str(group["group_id"]) == group_id
                    ),
                    None,
                )
                if tpl is None:
                    return []
                pose_tuple = self._template_pose_tuple_by_idx.get(tpl, {}).get(pose_idx)
                if pose_tuple is None:
                    return []
                key = (f"mandatory::{group_id}", pose_idx)
                if key in seen:
                    return []
                seen.add(key)
                entries.append(
                    (
                        key[0],
                        pose_idx,
                        list(self.mandatory_slots.get(group_id, [])),
                        pose_tuple,
                    )
                )
                continue

            tpl = self.owner._infer_optional_template_from_solution_id(sid)
            if tpl is None:
                return []
            tpl = str(tpl)
            pose_tuple = self._template_pose_tuple_by_idx.get(tpl, {}).get(pose_idx)
            if pose_tuple is None:
                return []
            key = (f"optional::{tpl}", pose_idx)
            if key in seen:
                return []
            seen.add(key)
            slots: List[CoordinateSlotSpec] = []
            slots.extend(self.required_optional_slots.get(tpl, []))
            slots.extend(self.residual_optional_slots.get(tpl, []))
            entries.append((key[0], pose_idx, slots, pose_tuple))
        return entries

    def add_benders_cut(
        self,
        conflict_set: Mapping[str, int],
        *,
        condition_lits: Sequence[cp_model.IntVar] = (),
    ) -> bool:
        # Exact-coordinate Benders cut as a presence no-good:
        #   sum(present(pose) for pose in conflict_set) <= N - 1
        # i.e. "these poses cannot all be present at once" — same shape as the
        # legacy BoolVar cut sum(z_conflict) <= N-1. The earlier implementation
        # used AddForbiddenAssignments per (slot, pose), which permanently
        # banned each pose individually and over-cut combinatorial failures.
        entries = self._conflict_pose_entries(conflict_set)
        if not entries:
            return False

        cut_index = int(self.owner.build_stats.get("coordinate_benders_cut_count", 0))

        present_lits: List[cp_model.IntVar] = []
        for _scope_key, pose_idx, slots, pose_tuple in entries:
            # M3-2: presence literals are content-addressed (reused across
            # cuts); cut_tag no longer participates in literal identity.
            lit = self._pose_present_literal(slots, pose_tuple)
            if lit is None:
                return False
            present_lits.append(lit)

        if not present_lits:
            return False

        cond = [lit for lit in condition_lits if lit is not None]
        bound = self.model.Add(sum(present_lits) <= len(present_lits) - 1)
        if cond:
            bound.OnlyEnforceIf(cond)
        self.owner.build_stats["coordinate_benders_cut_count"] = cut_index + 1
        self.owner.build_stats["coordinate_benders_last_cut"] = {
            "entries": len(entries),
            "presence_literals": len(present_lits),
            "semantics": (
                "pose_presence_nogood_v2_conditioned" if cond else "pose_presence_nogood_v1"
            ),
            "condition_count": len(cond),
        }
        # The model now contains a new constraint, so the previous CpSolver
        # response is no longer a valid witness for this model version.  Clearing
        # only _last_solution is insufficient: extract_solution() can otherwise
        # re-read the old solver assignment and hand downstream a layout that the
        # just-applied cut forbids.
        self.owner._last_solution = None
        self.owner._solver = None
        self.owner._status = None
        return True

    def add_region_capacity_cut(
        self,
        *,
        group_cell_weights: Mapping[str, int],
        capacity: int,
    ) -> bool:
        # F1 region_capacity master attach (M3-3, step_8 translation).
        # Valid inequality: for a region R with static capacity `capacity`
        # (= |R| - |blocked ∩ R|) and contributing MANDATORY groups whose full
        # pose domain lies inside R (P(g) ⊆ R, verified upstream in lifecycle
        # steps 5-7), any feasible layout satisfies
        #   sum_g weight_g * sum_{p ∈ domain(g)} presence(g, p) <= capacity
        # because each placed pose occupies weight_g = cells_per_pose disjoint
        # cells of R under the master's no-overlap. Physically true regardless
        # of the triggering cert, so attaching is always sound.
        #
        # Fail-closed shape: unknown group / no slots / empty pose domain /
        # non-positive weight or capacity → False with NO partial constraint.
        # Unlike conflict nogoods (where dropping a member over-strengthens),
        # omitting a pose whose presence literal cannot exist is lossless here:
        # such a pose can never be realized, so its occupancy term is
        # identically zero — but a group with NO representable pose at all is
        # rejected as a deeper inconsistency.
        cap = int(capacity)
        if cap < 0:
            return False
        terms: List[Tuple[int, cp_model.IntVar]] = []
        for group_id in sorted(group_cell_weights):
            weight = int(group_cell_weights[group_id])
            if weight <= 0:
                return False
            gid = str(group_id)
            tpl = next(
                (
                    str(group["facility_type"])
                    for group in self.owner._mandatory_groups
                    if str(group["group_id"]) == gid
                ),
                None,
            )
            if tpl is None:
                return False
            slots = list(self.mandatory_slots.get(gid, []))
            if not slots:
                return False
            pose_tuples = self._template_pose_tuple_by_idx.get(tpl, {})
            if not pose_tuples:
                return False
            group_terms: List[Tuple[int, cp_model.IntVar]] = []
            for pose_idx in sorted(pose_tuples):
                lit = self._pose_present_literal(slots, pose_tuples[pose_idx])
                if lit is None:
                    continue
                group_terms.append((weight, lit))
            if not group_terms:
                return False
            terms.extend(group_terms)
        if not terms:
            return False

        cut_index = int(
            self.owner.build_stats.get("coordinate_region_capacity_cut_count", 0)
        )
        self.model.Add(sum(w * lit for w, lit in terms) <= cap)
        self.owner.build_stats["coordinate_region_capacity_cut_count"] = cut_index + 1
        self.owner.build_stats["coordinate_region_capacity_last_cut"] = {
            "groups": len(group_cell_weights),
            "presence_terms": len(terms),
            "capacity": cap,
            "semantics": "region_capacity_weighted_presence_v1",
        }
        # Same witness-invalidation obligation as add_benders_cut
        # (F-GM-R6-01): a new constraint invalidates any prior solver response.
        self.owner._last_solution = None
        self.owner._solver = None
        self.owner._status = None
        return True
