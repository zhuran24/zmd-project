"""Tests for the master placement layer（主摆放层测试）.

文件目录索引 (10440 行, 200 tests + 37 helpers, vintage 2026-05-16):

主要 test cluster 按行号:
- L40-1989    helper functions: fixture builders + model fixtures (37 个 builder)
- L1990-2273  exact_candidate_warm_*  (8 tests)  — warm_start 失败 anchor 取样
- L2367-2476  boundary_storage_port_*  (5 tests) — 边界出货口 precheck
- L2545-2751  mandatory_manufacturing_rectangle_* (3 tests) — 强制制造矩形 precheck
- L2617-2895  mandatory_rectangle_precheck_*  (8 tests) — mandatory rect precheck 模式
- L2979-3030  mandatory_support_diagnostics_*  (3 tests) — mandatory support 诊断
- L3122-3232  warm_start_failure_*  (4 tests) — warm-start 失败处理
- L3321-10420 **exact_core_overlay_*  (41 tests)** — 最大 cluster, exact_core overlay 多维测试
- L3346-3650  exact_master_search_*  (3 tests) — search profile (guided_branching_v4 等)
- L3992-8629  exact_power_capacity_*  (3 tests) — 本地 power capacity 计算
- L4149-5542  ghost_conditioned_family_*  (4 tests) — ghost 条件 family bound
- L4199-4290  ghost_via_pole_*  (3 tests) — ghost via pole 形状 instrumentation
- L4303-5267  **ghost_signature_bucket_*  (25 tests)** — signature bucket optimization 系列
- L6331-6889  compact_rect_cpsat_*  (8 tests) — 紧凑矩形 CP-SAT
- L7432-8288  coordinate_exact_power_*  (15 tests) — coordinate exact power 子求解
- L7546-8341  coordinate_exact_rejects_*  (5 tests) — coordinate exact 拒绝 case

测试什么: src/models/master_model.py + exact_coordinate_master.py + power_placement_subproblem.py
  的 CP-SAT model construction / Benders cut / warm-start / precheck / signature bucket
  / family bound / coordinate exact 各维度.

pre-commit gate: 本文件 **不在** preflight_gate.py CORE_TEST_FILES 列表 (太大跑太慢).
  --full 模式才跑.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

import pytest
from ortools.sat.python import cp_model

import src.models.exact_coordinate_master as exact_coordinate_master_module
import src.models.master_model as master_model_module
from src.models.exact_coordinate_master import CoordinateExactMasterDelegate
from src.models.master_model import (
    MasterPlacementModel,
    _CompactRectCpSatFallback,
    _extract_solver_numeric_stat,
    _LOCAL_POWER_CAPACITY_COMPACT_RECT_CPSAT_DATA_CACHE,
    _LOCAL_POWER_CAPACITY_CACHE,
    _LOCAL_POWER_CAPACITY_COMPACT_CACHE,
    _LOCAL_POWER_CAPACITY_NORMALIZED_RECT_CACHE,
    _LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE,
    _LOCAL_POWER_CAPACITY_RECT_DP_CACHE,
    load_generic_io_requirements_artifact,
    load_project_data,
)
from src.models.cp_sat_worker_config import (
    DEFAULT_BINDING_CP_SAT_WORKERS,
    DEFAULT_LOCAL_CAPACITY_CP_SAT_WORKERS,
    DEFAULT_MASTER_CP_SAT_WORKERS,
    DEFAULT_ROUTING_CP_SAT_WORKERS,
    format_exact_cp_sat_worker_profile,
    resolve_exact_cp_sat_worker_profile,
    resolve_exact_cp_sat_worker_profile_details,
)


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _clear_local_power_capacity_caches() -> None:
    _LOCAL_POWER_CAPACITY_CACHE.clear()
    _LOCAL_POWER_CAPACITY_COMPACT_CACHE.clear()
    _LOCAL_POWER_CAPACITY_COMPACT_RECT_CPSAT_DATA_CACHE.clear()
    _LOCAL_POWER_CAPACITY_NORMALIZED_RECT_CACHE.clear()
    _LOCAL_POWER_CAPACITY_RECT_DP_CACHE.clear()
    _LOCAL_POWER_CAPACITY_RECT_DP_COMPILED_CACHE.clear()


def _constraint_type_counts(proto) -> dict[str, int]:
    counts: dict[str, int] = {}
    for constraint in proto.constraints:
        type_name = "unknown"
        for candidate in sorted(name[4:] for name in dir(constraint) if name.startswith("has_")):
            if getattr(constraint, f"has_{candidate}")():
                type_name = candidate
                break
        counts[type_name] = counts.get(type_name, 0) + 1
    return counts


def _solution_hint_values_by_var_index(model: MasterPlacementModel) -> dict[int, int]:
    proto = model.model.Proto()
    return {
        int(var_idx): int(value)
        for var_idx, value in zip(proto.solution_hint.vars, proto.solution_hint.values)
    }


def _shell_guard_pair_feasible(
    rows: Sequence[Sequence[int]],
    d_lo_value: int,
    d_hi_value: int,
) -> bool:
    model = cp_model.CpModel()
    d_lo = model.NewIntVar(0, 10, "d_lo")
    d_hi = model.NewIntVar(0, 10, "d_hi")
    lit = model.NewBoolVar("family_lit")
    model.Add(lit == 1)
    model.Add(d_lo == int(d_lo_value))
    model.Add(d_hi == int(d_hi_value))
    exact_coordinate_master_module.add_family_shell_guard_constraints(
        model,
        lit_var=lit,
        d_lo_var=d_lo,
        d_hi_var=d_hi,
        rows=rows,
    )
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 1
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model)
    return status in {cp_model.OPTIMAL, cp_model.FEASIBLE}


def _linear_minmax_distance_value(x_min: int, x_max: int, x_value: int) -> int:
    model = cp_model.CpModel()
    x = model.NewIntVar(int(x_min), int(x_max), "x")
    dx = model.NewIntVar(0, int(x_max) - int(x_min), "dx")
    model.Add(x == int(x_value))
    model.AddMinEquality(dx, [x - int(x_min), int(x_max) - x])
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 1
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model)
    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    return int(solver.Value(dx))


def _linear_minmax_distance_pair_feasible(
    *,
    x_min: int,
    x_max: int,
    y_min: int,
    y_max: int,
    x_value: int,
    y_value: int,
    dx_value: int,
    dy_value: int,
) -> bool:
    model = cp_model.CpModel()
    x = model.NewIntVar(int(x_min), int(x_max), "x")
    y = model.NewIntVar(int(y_min), int(y_max), "y")
    dx = model.NewIntVar(0, int(x_max) - int(x_min), "dx")
    dy = model.NewIntVar(0, int(y_max) - int(y_min), "dy")
    model.Add(x == int(x_value))
    model.Add(y == int(y_value))
    model.AddMinEquality(dx, [x - int(x_min), int(x_max) - x])
    model.AddMinEquality(dy, [y - int(y_min), int(y_max) - y])
    model.Add(dx == int(dx_value))
    model.Add(dy == int(dy_value))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 1
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model)
    return status in {cp_model.OPTIMAL, cp_model.FEASIBLE}


def _build_exact_ghost_warm_start_model(
    *,
    mandatory_pose_anchors: tuple[int, ...],
    grid_width: int,
    ghost_rect: tuple[int, int] | None = (1, 1),
) -> MasterPlacementModel:
    instances = [
        {
            "instance_id": f"miner_{index + 1:03d}",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for index, _anchor_x in enumerate(mandatory_pose_anchors)
    ]
    pools = {
        "miner": [
            {
                "pose_id": f"pose_{anchor_x}",
                "anchor": {"x": int(anchor_x), "y": 0},
                "occupied_cells": [[int(anchor_x), 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
            for anchor_x in mandatory_pose_anchors
        ]
    }
    rules = {
        "globals": {"grid": {"width": int(grid_width), "height": 1}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=ghost_rect,
        skip_power_coverage=True,
    )


def _build_exact_ghost_rebuild_warm_start_model() -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "miner_a_001",
            "facility_type": "miner_a",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "miner_b_001",
            "facility_type": "miner_b",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "miner_a": [
            {
                "pose_id": "miner_a_left",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "miner_a_right",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
        "miner_b": [
            {
                "pose_id": "miner_b_far_right",
                "anchor": {"x": 3, "y": 0},
                "occupied_cells": [[3, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
    }
    rules = {
        "globals": {"grid": {"width": 4, "height": 1}},
        "facility_templates": {
            "miner_a": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "miner_b": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        skip_power_coverage=True,
    )


def _override_all_ghost_domains(
    model: MasterPlacementModel,
    *,
    blocked_cells: set[tuple[int, int]],
) -> None:
    model.build()
    normalized_cells = [
        [int(cell_x), int(cell_y)] for cell_x, cell_y in sorted(blocked_cells)
    ]
    for rect_idx in list(model.u_vars):
        model._ghost_domains[int(rect_idx)] = {
            "anchor": {"x": int(rect_idx), "y": 0},
            "cells": list(normalized_cells),
        }


def _override_ghost_domains_by_index(
    model: MasterPlacementModel,
    *,
    blocked_cells_by_index: Mapping[int, set[tuple[int, int]]],
) -> None:
    model.build()
    for rect_idx in list(model.u_vars):
        blocked_cells = blocked_cells_by_index.get(int(rect_idx), set())
        model._ghost_domains[int(rect_idx)] = {
            "anchor": {"x": int(rect_idx), "y": 0},
            "cells": [
                [int(cell_x), int(cell_y)]
                for cell_x, cell_y in sorted(blocked_cells)
            ],
        }


def _build_blocked_cells_exhausted_failure_model() -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "miner": [
            {
                "pose_id": "pose_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ]
    }
    rules = {
        "globals": {"grid": {"width": 2, "height": 1}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        skip_power_coverage=True,
    )


def _build_committed_cells_exhausted_failure_model() -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "alpha_001",
            "facility_type": "alpha",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "beta_001",
            "facility_type": "beta",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "alpha": [
            {
                "pose_id": "alpha_pose",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
        "beta": [
            {
                "pose_id": "beta_pose",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
    }
    rules = {
        "globals": {"grid": {"width": 2, "height": 1}},
        "facility_templates": {
            "alpha": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "beta": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        skip_power_coverage=True,
    )


def _build_intra_group_greedy_exhausted_failure_model() -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "miner_002",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "miner": [
            {
                "pose_id": "a_wide",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": "wide"},
                "occupied_cells": [[0, 0], [1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "b_left",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": "left"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "c_right",
                "anchor": {"x": 1, "y": 0},
                "pose_params": {"orientation": "right"},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ]
    }
    rules = {
        "globals": {"grid": {"width": 3, "height": 1}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        skip_power_coverage=True,
    )


def _build_pose_order_portfolio_success_model() -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "miner_002",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "miner": [
            {
                "pose_id": "bad_x_first",
                "anchor": {"x": 0, "y": 1},
                "occupied_cells": [[1, 0], [2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "good_left",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "good_right",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ]
    }
    rules = {
        "globals": {"grid": {"width": 4, "height": 3}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        skip_power_coverage=True,
    )


def _build_committed_cells_local_repair_success_model() -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "alpha_001",
            "facility_type": "alpha",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "beta_001",
            "facility_type": "beta",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "alpha": [
            {
                "pose_id": "alpha_conflict",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": "conflict"},
                "occupied_cells": [[0, 0], [1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "alpha_safe",
                "anchor": {"x": 2, "y": 0},
                "pose_params": {"orientation": "safe"},
                "occupied_cells": [[2, 0], [3, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
        "beta": [
            {
                "pose_id": "beta_left",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": "left"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "beta_mid",
                "anchor": {"x": 1, "y": 0},
                "pose_params": {"orientation": "mid"},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
    }
    rules = {
        "globals": {"grid": {"width": 5, "height": 1}},
        "facility_templates": {
            "alpha": {"dimensions": {"w": 2, "h": 1}, "needs_power": False},
            "beta": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        skip_power_coverage=True,
    )


def _build_boundary_storage_port_screen_model(
    *,
    required_count: int = 4,
    malformed_geometry: bool = False,
) -> MasterPlacementModel:
    instances = [
        {
            "instance_id": f"boundary_port_{index + 1:03d}",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for index in range(int(required_count))
    ]
    pools = {
        "boundary_storage_port": [
            {
                "pose_id": "left_1",
                "anchor": {"x": 0, "y": 1},
                "occupied_cells": [[0, 1], [0, 2], [0, 3]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "left_2",
                "anchor": {"x": 0, "y": 2},
                "occupied_cells": [[0, 2], [0, 3], [0, 4]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "left_4",
                "anchor": {"x": 0, "y": 4},
                "occupied_cells": [[0, 4], [0, 5], [0, 6]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "bottom_1",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0], [2, 0], [3, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "bottom_2",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0], [3, 0], [4, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "bottom_4",
                "anchor": {"x": 4, "y": 0},
                "occupied_cells": [[4, 0], [5, 0], [6, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ]
    }
    if malformed_geometry:
        pools["boundary_storage_port"][0] = {
            "pose_id": "malformed",
            "anchor": {"x": 1, "y": 1},
            "occupied_cells": [[1, 1], [2, 1], [2, 2]],
            "input_port_cells": [],
            "output_port_cells": [],
            "power_coverage_cells": None,
        }
    rules = {
        "globals": {"grid": {"width": 8, "height": 8}},
        "facility_templates": {
            "boundary_storage_port": {
                "dimensions": {"w": 1, "h": 3},
                "rotatable": True,
                "needs_power": False,
            },
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        skip_power_coverage=True,
    )


def _build_mandatory_manufacturing_rectangle_precheck_model(
    *,
    facility_type: str = "manufacturing_3x3",
    operation_type: str = "smelting",
    required_count: int = 2,
    overlapping_pool: bool = False,
    malformed_geometry: bool = False,
    template_dimensions: tuple[int, int] | None = None,
    pose_dimensions: Sequence[tuple[int, int]] | None = None,
    pose_anchors: Sequence[tuple[int, int]] | None = None,
    rotatable: bool = True,
) -> MasterPlacementModel:
    def _rectangle_cells(
        anchor_x: int,
        anchor_y: int,
        width: int,
        height: int,
    ) -> list[list[int]]:
        return [
            [int(anchor_x + dx), int(anchor_y + dy)]
            for dx in range(int(width))
            for dy in range(int(height))
        ]

    default_template_dimensions = {
        "manufacturing_3x3": (3, 3),
        "manufacturing_5x5": (5, 5),
        "manufacturing_6x4": (6, 4),
    }
    template_w, template_h = template_dimensions or default_template_dimensions.get(
        str(facility_type),
        (3, 3),
    )
    if pose_dimensions is None:
        if str(facility_type) == "manufacturing_6x4":
            pose_dimensions = ((6, 4), (4, 6))
        else:
            pose_dimensions = ((int(template_w), int(template_h)),) * 2
    pose_dimensions = tuple(
        (int(width), int(height)) for width, height in list(pose_dimensions)
    )
    if pose_anchors is None:
        if (
            str(facility_type) == "manufacturing_3x3"
            and len(pose_dimensions) >= 2
        ):
            pose_anchors = ((0, 0), (1 if overlapping_pool else 3, 0))
        else:
            next_anchor_x = 0
            generated_anchors: list[tuple[int, int]] = []
            for width, _ in pose_dimensions:
                generated_anchors.append((int(next_anchor_x), 0))
                next_anchor_x += int(width)
            pose_anchors = tuple(generated_anchors)
    pose_anchors = tuple(
        (int(anchor_x), int(anchor_y))
        for anchor_x, anchor_y in list(pose_anchors)
    )

    instances = [
        {
            "instance_id": f"manufacturing_{index + 1:03d}",
            "facility_type": str(facility_type),
            "operation_type": str(operation_type),
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for index in range(int(required_count))
    ]
    pools = {
        str(facility_type): [
            {
                "pose_id": f"rect_{index}",
                "anchor": {"x": int(anchor_x), "y": int(anchor_y)},
                "occupied_cells": _rectangle_cells(
                    int(anchor_x),
                    int(anchor_y),
                    int(width),
                    int(height),
                ),
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
            for index, ((width, height), (anchor_x, anchor_y)) in enumerate(
                zip(pose_dimensions, pose_anchors),
                start=1,
            )
        ]
    }
    if malformed_geometry:
        anchor_x, anchor_y = pose_anchors[0]
        pools[str(facility_type)][0] = {
            "pose_id": "malformed",
            "anchor": {"x": int(anchor_x), "y": int(anchor_y)},
            "occupied_cells": [
                [int(anchor_x + 0), int(anchor_y + 0)],
                [int(anchor_x + 1), int(anchor_y + 0)],
                [int(anchor_x + 1), int(anchor_y + 1)],
                [int(anchor_x + 2), int(anchor_y + 1)],
            ],
            "input_port_cells": [],
            "output_port_cells": [],
            "power_coverage_cells": None,
        }
    grid_width = max(
        int(anchor_x) + int(width)
        for (width, _), (anchor_x, _) in zip(pose_dimensions, pose_anchors)
    )
    grid_height = max(
        int(anchor_y) + int(height)
        for (_, height), (_, anchor_y) in zip(pose_dimensions, pose_anchors)
    )
    rules = {
        "globals": {"grid": {"width": int(grid_width), "height": int(grid_height)}},
        "facility_templates": {
            str(facility_type): {
                "dimensions": {"w": int(template_w), "h": int(template_h)},
                "rotatable": bool(rotatable),
                "needs_power": False,
            },
        },
    }
    ghost_rect = (max(1, int(grid_width) - 1), int(grid_height))
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=ghost_rect,
        skip_power_coverage=True,
    )


def _build_mandatory_support_diagnostics_model(
    *,
    include_supported_rectangle_group: bool = True,
) -> MasterPlacementModel:
    instances = []
    facility_pools: dict[str, list[dict[str, object]]] = {"protocol_core": []}
    facility_templates: dict[str, dict[str, object]] = {
        "protocol_core": {
            "dimensions": {"w": 2, "h": 2},
            "rotatable": False,
            "needs_power": False,
        }
    }
    if include_supported_rectangle_group:
        instances.append(
            {
                "instance_id": "manufacturing_001",
                "facility_type": "manufacturing_3x3",
                "operation_type": "smelting",
                "is_mandatory": True,
                "bound_type": "exact",
            }
        )
        facility_pools["manufacturing_3x3"] = [
            {
                "pose_id": "mfg_a",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [
                    [0, 0],
                    [1, 0],
                    [2, 0],
                    [0, 1],
                    [1, 1],
                    [2, 1],
                    [0, 2],
                    [1, 2],
                    [2, 2],
                ],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ]
        facility_templates["manufacturing_3x3"] = {
            "dimensions": {"w": 3, "h": 3},
            "rotatable": False,
            "needs_power": False,
        }
    instances.append(
        {
            "instance_id": "protocol_core_001",
            "facility_type": "protocol_core",
            "operation_type": "protocol_core",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    )
    rules = {
        "globals": {"grid": {"width": 8, "height": 4}},
        "facility_templates": facility_templates,
    }
    return MasterPlacementModel(
        instances,
        facility_pools,
        rules,
        solve_mode="exploratory",
        ghost_rect=None,
        skip_power_coverage=True,
    )


def _build_exact_power_capacity_model(
    *,
    solve_mode: str = "certified_exact",
    ghost_rect: tuple[int, int] | None = None,
) -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "powered_001",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "powered_002",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "power_pole": [
            {
                "pose_id": "pole_left",
                "anchor": {"x": 0, "y": 1},
                "occupied_cells": [[0, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[1, 0], [2, 0]],
            },
            {
                "pose_id": "pole_right",
                "anchor": {"x": 3, "y": 1},
                "occupied_cells": [[3, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[4, 0], [5, 0]],
            },
        ],
        "protocol_storage_box": [],
        "powered_machine": [
            {
                "pose_id": "machine_left_a",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "machine_left_b",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "machine_right_a",
                "anchor": {"x": 4, "y": 0},
                "occupied_cells": [[4, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "machine_right_b",
                "anchor": {"x": 5, "y": 0},
                "occupied_cells": [[5, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
    }
    rules = {
        "globals": {"grid": {"width": 6, "height": 2}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "powered_machine": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode=solve_mode,
        ghost_rect=ghost_rect,
    )


def _build_exact_single_family_upper_bound_model() -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "powered_001",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "powered_002",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "power_pole": [
            {
                "pose_id": "pole_only",
                "anchor": {"x": 0, "y": 1},
                "occupied_cells": [[0, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[1, 0], [2, 0]],
            }
        ],
        "protocol_storage_box": [],
        "powered_machine": [
            {
                "pose_id": "machine_left",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "machine_right",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
    }
    rules = {
        "globals": {"grid": {"width": 3, "height": 2}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "powered_machine": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
    )


def _build_exact_ghost_conditioned_family_upper_bound_model(
    *,
    ghost_rect: tuple[int, int] | None = None,
) -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "powered_001",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "powered_002",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "power_pole": [
            {
                "pose_id": "pole_left",
                "anchor": {"x": 0, "y": 1},
                "occupied_cells": [[0, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[1, 0], [5, 0]],
            },
            {
                "pose_id": "pole_right",
                "anchor": {"x": 6, "y": 1},
                "occupied_cells": [[6, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[1, 0], [5, 0]],
            },
        ],
        "protocol_storage_box": [],
        "powered_machine": [
            {
                "pose_id": "machine_left",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "machine_right",
                "anchor": {"x": 5, "y": 0},
                "occupied_cells": [[5, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
    }
    rules = {
        "globals": {"grid": {"width": 7, "height": 2}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "powered_machine": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=ghost_rect,
    )


def _build_exact_mandatory_signature_upper_bound_model(
    *,
    ghost_rect: tuple[int, int] | None = None,
) -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "router_001",
            "facility_type": "router",
            "operation_type": "routing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "router_002",
            "facility_type": "router",
            "operation_type": "routing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "router": [
            {
                "pose_id": "plain_left",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "plain_mid",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "ported_right",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [{"x": 2, "y": 0, "dir": "E"}],
                "power_coverage_cells": None,
            },
        ],
        "power_pole": [],
        "protocol_storage_box": [],
    }
    rules = {
        "globals": {"grid": {"width": 4, "height": 2}},
        "facility_templates": {
            "router": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=ghost_rect,
        skip_power_coverage=True,
    )


def _build_exact_incompatible_signature_order_model() -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "tiny_001",
            "facility_type": "tiny_router",
            "operation_type": "routing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "tiny_002",
            "facility_type": "tiny_router",
            "operation_type": "routing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "tiny_router": [
            {
                "pose_id": "order_low_signature_high",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"orientation": "same", "port_mode": "same"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [{"x": 0, "y": 0, "dir": "E"}],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "order_high_signature_low",
                "anchor": {"x": 1, "y": 0},
                "pose_params": {"orientation": "same", "port_mode": "same"},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [{"x": 1, "y": 0, "dir": "W"}],
                "power_coverage_cells": None,
            },
        ],
        "power_pole": [],
        "protocol_storage_box": [],
    }
    rules = {
        "globals": {"grid": {"width": 2, "height": 1}},
        "facility_templates": {
            "tiny_router": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        skip_power_coverage=True,
    )


def _build_exact_mandatory_signature_multicell_region_model(
    *,
    ghost_rect: tuple[int, int] | None = None,
) -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "wide_router_001",
            "facility_type": "wide_router",
            "operation_type": "routing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "wide_router_002",
            "facility_type": "wide_router",
            "operation_type": "routing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "wide_router": [
            {
                "pose_id": "wide_left",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0], [1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "wide_mid",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0], [2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "wide_right",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0], [3, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
        "power_pole": [],
        "protocol_storage_box": [],
    }
    rules = {
        "globals": {"grid": {"width": 5, "height": 2}},
        "facility_templates": {
            "wide_router": {"dimensions": {"w": 2, "h": 1}, "needs_power": False},
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=ghost_rect,
        skip_power_coverage=True,
    )


def _build_exact_mandatory_signature_noncompact_footprint_model(
    *,
    ghost_rect: tuple[int, int] | None = None,
) -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "odd_router_001",
            "facility_type": "odd_router",
            "operation_type": "routing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "odd_router_002",
            "facility_type": "odd_router",
            "operation_type": "routing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "odd_router": [
            {
                "pose_id": "odd_left",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "odd_mid",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "odd_right",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
        "power_pole": [],
        "protocol_storage_box": [],
    }
    rules = {
        "globals": {"grid": {"width": 5, "height": 2}},
        "facility_templates": {
            "odd_router": {"dimensions": {"w": 2, "h": 1}, "needs_power": False},
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=ghost_rect,
        skip_power_coverage=True,
    )


def _build_exact_mandatory_signature_l_shape_footprint_model(
    *,
    ghost_rect: tuple[int, int] | None = None,
) -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "l_router_001",
            "facility_type": "l_router",
            "operation_type": "routing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "l_router_002",
            "facility_type": "l_router",
            "operation_type": "routing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "l_router": [
            {
                "pose_id": "l_left",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0], [1, 0], [0, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "l_mid",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0], [2, 0], [1, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "l_right",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0], [3, 0], [2, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
        "power_pole": [],
        "protocol_storage_box": [],
    }
    rules = {
        "globals": {"grid": {"width": 5, "height": 3}},
        "facility_templates": {
            "l_router": {"dimensions": {"w": 2, "h": 2}, "needs_power": False},
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=ghost_rect,
        skip_power_coverage=True,
    )


def _build_exact_mandatory_signature_unstable_rectangular_footprint_model(
    *,
    ghost_rect: tuple[int, int] | None = None,
) -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "shift_router_001",
            "facility_type": "shift_router",
            "operation_type": "routing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "shift_router_002",
            "facility_type": "shift_router",
            "operation_type": "routing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "shift_router": [
            {
                "pose_id": "left_a",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "left_b",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "right_a",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[3, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "right_b",
                "anchor": {"x": 3, "y": 0},
                "occupied_cells": [[4, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
        "power_pole": [],
        "protocol_storage_box": [],
    }
    rules = {
        "globals": {"grid": {"width": 6, "height": 2}},
        "facility_templates": {
            "shift_router": {"dimensions": {"w": 2, "h": 1}, "needs_power": False},
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=ghost_rect,
        skip_power_coverage=True,
    )


def _build_exact_required_optional_signature_upper_bound_model(
    *,
    ghost_rect: tuple[int, int] | None = None,
) -> MasterPlacementModel:
    pools = {
        "power_pole": [],
        "protocol_storage_box": [
            {
                "pose_id": "box_north_left",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"port_mode": "north"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [{"x": 0, "y": 1, "dir": "N"}],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "box_north_mid",
                "anchor": {"x": 1, "y": 0},
                "pose_params": {"port_mode": "north"},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [{"x": 1, "y": 1, "dir": "N"}],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "box_east",
                "anchor": {"x": 2, "y": 1},
                "pose_params": {"port_mode": "east"},
                "occupied_cells": [[2, 1]],
                "input_port_cells": [{"x": 3, "y": 1, "dir": "E"}],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
    }
    rules = {
        "globals": {"grid": {"width": 5, "height": 3}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    model = MasterPlacementModel(
        instances=[],
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        ghost_rect=ghost_rect,
        skip_power_coverage=True,
        generic_io_requirements={"required_generic_outputs": {}, "required_generic_inputs": {}},
        exact_required_pose_optional_counts={"protocol_storage_box": 2},
    )
    return model


def _build_exact_residual_optional_signature_model(
    *,
    ghost_rect: tuple[int, int] | None = None,
) -> MasterPlacementModel:
    pools = {
        "power_pole": [],
        "protocol_storage_box": [
            {
                "pose_id": "box_north_left",
                "anchor": {"x": 0, "y": 0},
                "pose_params": {"port_mode": "north"},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [{"x": 0, "y": 1, "dir": "N"}],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "box_north_mid",
                "anchor": {"x": 1, "y": 0},
                "pose_params": {"port_mode": "north"},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [{"x": 1, "y": 1, "dir": "N"}],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "box_east",
                "anchor": {"x": 2, "y": 1},
                "pose_params": {"port_mode": "east"},
                "occupied_cells": [[2, 1]],
                "input_port_cells": [{"x": 3, "y": 1, "dir": "E"}],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
    }
    rules = {
        "globals": {"grid": {"width": 5, "height": 3}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    return MasterPlacementModel(
        instances=[],
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        ghost_rect=ghost_rect,
        skip_power_coverage=True,
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1, "qiaoyu_capsule": 1},
        },
    )


def _build_minimal_master_model() -> MasterPlacementModel:
    return MasterPlacementModel(
        instances=[
            {
                "instance_id": "miner_001",
                "facility_type": "miner",
                "operation_type": "mining",
                "is_mandatory": True,
                "bound_type": "exact",
            }
        ],
        facility_pools={
            "miner": [
                {
                    "pose_id": "pose_left",
                    "anchor": {"x": 0, "y": 0},
                    "occupied_cells": [[0, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                }
            ]
        },
        rules={
            "globals": {"grid": {"width": 2, "height": 1}},
            "facility_templates": {
                "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            },
        },
        skip_power_coverage=True,
        solve_mode="certified_exact",
    )


def test_extract_solver_numeric_stat_handles_methods_properties_and_missing_fields() -> None:
    class _DummySolver:
        def NumBranches(self) -> int:
            return 7

        user_time = 1.25
        deterministic_time = 0.5

    solver = _DummySolver()

    assert _extract_solver_numeric_stat(solver, "NumBranches", default=0) == 7
    assert _extract_solver_numeric_stat(solver, "UserTime", "user_time", default=0.0) == 1.25
    assert _extract_solver_numeric_stat(solver, "deterministic_time", default=0.0) == 0.5
    assert _extract_solver_numeric_stat(solver, "NumConflicts", default=0) == 0


def _build_exact_geometric_power_coverage_model() -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "powered_001",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "powered_002",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "power_pole": [
            {
                "pose_id": "pole_center",
                "anchor": {"x": 0, "y": 1},
                "occupied_cells": [[0, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [
                    [0, 0],
                    [0, 1],
                    [1, 0],
                    [1, 1],
                    [2, 0],
                    [2, 1],
                ],
            }
        ],
        "protocol_storage_box": [],
        "powered_machine": [
            {
                "pose_id": "machine_left",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "machine_right",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
    }
    rules = {
        "globals": {"grid": {"width": 3, "height": 2}},
        "facility_templates": {
            "power_pole": {
                "dimensions": {"w": 1, "h": 1},
                "needs_power": False,
                "power_coverage_radius": 1,
            },
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "powered_machine": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    return MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
    )


def test_exact_cp_sat_worker_profile_defaults_and_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_name in [
        "EXACT_CP_SAT_WORKERS",
        "EXACT_MASTER_CP_SAT_WORKERS",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS",
        "EXACT_BINDING_CP_SAT_WORKERS",
        "EXACT_ROUTING_CP_SAT_WORKERS",
    ]:
        monkeypatch.delenv(env_name, raising=False)

    assert resolve_exact_cp_sat_worker_profile() == {
        "master": DEFAULT_MASTER_CP_SAT_WORKERS,
        "local_capacity": DEFAULT_LOCAL_CAPACITY_CP_SAT_WORKERS,
        "binding": DEFAULT_BINDING_CP_SAT_WORKERS,
        "routing": DEFAULT_ROUTING_CP_SAT_WORKERS,
    }

    monkeypatch.setenv("EXACT_CP_SAT_WORKERS", "3")
    assert resolve_exact_cp_sat_worker_profile() == {
        "master": 3,
        "local_capacity": 3,
        "binding": 3,
        "routing": 3,
    }

    monkeypatch.setenv("EXACT_BINDING_CP_SAT_WORKERS", "5")
    monkeypatch.setenv("EXACT_ROUTING_CP_SAT_WORKERS", "7")
    assert resolve_exact_cp_sat_worker_profile() == {
        "master": 3,
        "local_capacity": 3,
        "binding": 5,
        "routing": 7,
    }


def test_exact_cp_sat_worker_profile_details_and_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for env_name in [
        "EXACT_CP_SAT_WORKERS",
        "EXACT_MASTER_CP_SAT_WORKERS",
        "EXACT_LOCAL_CAPACITY_CP_SAT_WORKERS",
        "EXACT_BINDING_CP_SAT_WORKERS",
        "EXACT_ROUTING_CP_SAT_WORKERS",
    ]:
        monkeypatch.delenv(env_name, raising=False)

    monkeypatch.setenv("EXACT_MASTER_CP_SAT_WORKERS", "2")
    monkeypatch.setenv("EXACT_BINDING_CP_SAT_WORKERS", "6")

    details = resolve_exact_cp_sat_worker_profile_details()
    formatted = format_exact_cp_sat_worker_profile(details)

    assert details["master"]["workers"] == 2
    assert details["master"]["source"] == "EXACT_MASTER_CP_SAT_WORKERS"
    assert details["local_capacity"]["workers"] == DEFAULT_LOCAL_CAPACITY_CP_SAT_WORKERS
    assert details["local_capacity"]["source"] == "default"
    assert details["binding"]["workers"] == 6
    assert details["binding"]["source"] == "EXACT_BINDING_CP_SAT_WORKERS"
    assert details["routing"]["workers"] == DEFAULT_ROUTING_CP_SAT_WORKERS
    assert details["routing"]["source"] == "default"
    assert "master=2[EXACT_MASTER_CP_SAT_WORKERS]" in formatted
    assert (
        f"local_capacity={DEFAULT_LOCAL_CAPACITY_CP_SAT_WORKERS}[default]"
        in formatted
    )
    assert "binding=6[EXACT_BINDING_CP_SAT_WORKERS]" in formatted
    assert f"routing={DEFAULT_ROUTING_CP_SAT_WORKERS}[default]" in formatted


def test_master_solver_worker_override_changes_only_solver_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXACT_CP_SAT_WORKERS", raising=False)
    monkeypatch.setenv("EXACT_MASTER_CP_SAT_WORKERS", "2")

    model = _build_minimal_master_model()
    model.build()
    status = model.solve(time_limit_seconds=5.0)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert model._solver is not None
    assert int(model._solver.parameters.num_search_workers) == 2



def test_load_project_data_separates_exact_and_exploratory(project_root: Path) -> None:
    exact_instances, pools, rules = load_project_data(project_root, solve_mode="certified_exact")
    exploratory_instances, _, _ = load_project_data(project_root, solve_mode="exploratory")

    assert len(exact_instances) == 266
    assert all(inst["is_mandatory"] for inst in exact_instances)
    assert all(inst["bound_type"] == "exact" for inst in exact_instances)

    assert len(exploratory_instances) == 326
    assert sum(1 for inst in exploratory_instances if not inst["is_mandatory"]) == 60
    assert sum(len(pool) for pool in pools.values()) == 66403
    assert rules["globals"]["grid"]["width"] == 70
    assert rules["globals"]["grid"]["height"] == 70



def test_exact_mode_optional_pose_variables_ignore_provisional_caps() -> None:
    instances = [
        {
            "instance_id": f"power_pole_{idx:03d}",
            "facility_type": "power_pole",
            "operation_type": "power_supply",
            "is_mandatory": False,
            "bound_type": "provisional",
        }
        for idx in range(1, 51)
    ]
    pools = {
        "power_pole": [
            {
                "pose_id": f"pole_{idx}",
                "anchor": {"x": idx, "y": 0},
                "occupied_cells": [[idx, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[idx, 0]],
            }
            for idx in range(51)
        ],
        "protocol_storage_box": [],
    }
    rules = {
        "globals": {"grid": {"width": 70, "height": 70}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }

    exact_model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        skip_power_coverage=True,
    )
    exact_model.build()
    assert exact_model.build_stats["master_representation"] == "coordinate_exact_v2"
    assert exact_model.build_stats["master_domain_encoding"] == "mode_rect_factorized_v1"
    assert exact_model.build_stats["master_domain_table_rows"] == 0
    assert exact_model.build_stats["master_slot_counts"]["residual_optionals"] == {}
    assert "power_coverage" not in exact_model.build_stats
    assert exact_model.build_stats["exact_required_optionals"] == {}
    optional_bounds = exact_model.build_stats["global_valid_inequalities"]["optional_cardinality_bounds"]
    family_stats = exact_model.build_stats["global_valid_inequalities"]["power_capacity_families"]
    assert optional_bounds["power_pole"]["candidate_pose_count"] == 51
    assert optional_bounds["power_pole"]["mandatory_powered_nonpole"] == 0
    assert optional_bounds["power_pole"]["slot_pool_upper_bound"] == 0
    assert family_stats["applied"] is False
    assert family_stats["reason"] == "power_coverage_skipped"
    assert exact_model.solve(time_limit_seconds=5.0) in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    exploratory_model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="exploratory",
        skip_power_coverage=True,
    )
    exploratory_model.build()
    for var in exploratory_model.optional_pose_vars["power_pole"].values():
        exploratory_model.model.Add(var == 1)
    assert exploratory_model.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE



def test_extract_solution_emits_pose_optional_identifier() -> None:
    instances = []
    pools = {
        "power_pole": [],
        "protocol_storage_box": [
            {
                "pose_id": "box_0",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [{"x": 1, "y": 1, "dir": "N"}],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
    }
    rules = {
        "globals": {"grid": {"width": 70, "height": 70}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }

    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        skip_power_coverage=True,
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1},
        },
    )
    model.build()
    assert model.solve(time_limit_seconds=5.0) in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    solution = model.extract_solution()
    assert list(solution.keys()) == ["pose_optional::protocol_storage_box::box_0"]
    entry = solution["pose_optional::protocol_storage_box::box_0"]
    assert entry["facility_type"] == "protocol_storage_box"
    assert entry["bound_type"] == "exact_pose_optional"


def test_exact_greedy_solution_hint_is_deterministic_and_mandatory_only() -> None:
    instances = [
        {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "miner_002",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "miner": [
            {
                "pose_id": "pose_b",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "pose_a",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "pose_c",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ]
    }
    rules = {
        "globals": {"grid": {"width": 4, "height": 4}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }

    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        skip_power_coverage=True,
    )

    hint_1 = model.build_greedy_solution_hint()
    hint_2 = model.build_greedy_solution_hint()

    assert hint_1 == hint_2 == {"miner_001": 1, "miner_002": 2}
    assert all(not key.startswith("pose_optional::") for key in hint_1)
    assert model.build_stats["greedy_hint"] == {
        "supported": True,
        "complete": True,
        "hinted_groups": 1,
        "hinted_instances": 2,
        "skipped_groups": [],
        "used_power_coverage_filter": False,
    }


def test_exact_candidate_warm_start_can_rebuild_mandatory_hint_for_first_ghost_anchor() -> None:
    model = _build_exact_ghost_rebuild_warm_start_model()

    greedy_hint = model.build_greedy_solution_hint()
    warm_start = model.build_exact_candidate_warm_start()

    assert greedy_hint == {"miner_a_001": 0, "miner_b_001": 0}
    assert warm_start["solution_hint"] == {"miner_a_001": 1, "miner_b_001": 0}
    assert warm_start["ghost_anchor_hint_status"] == "applied"
    assert warm_start["warm_start_strategy"] == "ghost_aware_mandatory_rebuild"
    selected_idx = int(warm_start["ghost_anchor_hint_idx"])
    assert model._ghost_domains[selected_idx]["anchor"] == {"x": 0, "y": 0}
    assert warm_start["mandatory_hint_pose_count"] == 2
    assert warm_start["mandatory_hint_occupied_cell_count"] == 2
    assert warm_start["ghost_anchor_total_count"] == len(model.u_vars)
    assert warm_start["ghost_anchor_compatible_count"] == 1
    assert warm_start["first_compatible_ghost_anchor_idx"] == selected_idx
    assert warm_start["ghost_aware_anchor_attempt_count"] == 1
    assert warm_start["ghost_aware_anchor_selected_idx"] == selected_idx
    assert warm_start["ghost_aware_complete_mandatory_hint"] is True
    assert warm_start["ghost_aware_hint_instances"] == 2
    assert warm_start["required_optional_positive_hints"] == 0
    assert warm_start["residual_optional_positive_hints"] == 0
    assert warm_start["hint_inactive_residual_optionals"] is False
    assert warm_start["residual_optional_zero_hints"] == 0
    assert model.build_stats["exact_candidate_warm_start"]["warm_start_strategy"] == (
        "ghost_aware_mandatory_rebuild"
    )


def test_exact_candidate_warm_start_rejects_coordinate_invalid_rebuild_hint(
    monkeypatch,
) -> None:
    model = _build_exact_ghost_rebuild_warm_start_model()
    validation_calls: list[dict[str, object]] = []
    monkeypatch.setenv(
        master_model_module.EXACT_GHOST_AWARE_COORDINATE_VALIDATION_SECONDS_ENV,
        "7.5",
    )
    monkeypatch.setenv(
        master_model_module.EXACT_GHOST_AWARE_POSE_ORDER_VALIDATION_SECONDS_ENV,
        "1.25",
    )

    def _reject_coordinate_hint(**kwargs: object) -> dict[str, object]:
        validation_calls.append(dict(kwargs))
        return {
            "attempted": True,
            "status": "INFEASIBLE",
            "accepted": False,
            "reason": "infeasible",
            "forced_slot_field_count": 6,
            "forced_ghost_anchor": True,
            "wall_time": 0.01,
            "deterministic_time": 0.0,
            "branches": 0,
            "conflicts": 0,
            "solver_parameters": {},
        }

    monkeypatch.setattr(
        model,
        "_validate_coordinate_forced_hint",
        _reject_coordinate_hint,
    )

    warm_start = model.build_exact_candidate_warm_start()

    assert warm_start["ghost_anchor_hint_status"] == "none_compatible"
    assert warm_start["warm_start_strategy"] == "global_greedy_fallback"
    assert warm_start["ghost_aware_coordinate_validation_attempt_count"] >= 1
    assert warm_start["ghost_aware_coordinate_validation_rejected_count"] >= 1
    assert warm_start["ghost_aware_coordinate_validation_last_status"] == "INFEASIBLE"
    assert warm_start["ghost_aware_coordinate_validation_rejection_samples"][0][
        "strategy"
    ] == "ghost_aware_mandatory_rebuild"
    assert "coordinate_validation_infeasible" in model.build_stats[
        "exact_candidate_warm_start_failure_attribution"
    ]["failure_reason_counts"]
    assert validation_calls
    assert validation_calls[0]["time_limit_seconds"] == 7.5


def test_exact_candidate_warm_start_counts_no_solve_precheck_rejections(
    monkeypatch,
) -> None:
    model = _build_exact_ghost_rebuild_warm_start_model()
    monkeypatch.setenv(
        master_model_module.EXACT_GHOST_AWARE_COORDINATE_VALIDATION_MAX_ANCHORS_ENV,
        "1",
    )

    def _reject_by_precheck(**kwargs: object) -> dict[str, object]:
        return {
            "attempted": False,
            "attempted_solver": False,
            "status": "INFEASIBLE",
            "accepted": False,
            "reason": "signature_monotonic_forced_label_infeasible",
            "forced_slot_field_count": 2,
            "forced_ghost_anchor": kwargs.get("ghost_anchor_hint_idx") is not None,
            "wall_time": 0.0,
            "deterministic_time": 0.0,
            "branches": 0,
            "conflicts": 0,
            "solver_parameters": {"profile_id": "signature_monotonic_precheck"},
        }

    monkeypatch.setattr(
        model,
        "_validate_coordinate_forced_hint",
        _reject_by_precheck,
    )

    warm_start = model.build_exact_candidate_warm_start()

    assert warm_start["ghost_anchor_hint_status"] == "none_compatible"
    assert warm_start["ghost_aware_coordinate_validation_attempt_count"] == 1
    assert warm_start["ghost_aware_coordinate_validation_rejected_count"] == 1
    assert warm_start["ghost_aware_coordinate_validation_limit_reached"] is True
    assert warm_start["ghost_aware_coordinate_validation_rejection_samples"][0][
        "reason"
    ] == "signature_monotonic_forced_label_infeasible"
    attribution_sample = model.build_stats[
        "exact_candidate_warm_start_failure_attribution"
    ]["failed_anchor_samples"][0]
    assert attribution_sample["failure_reason"] == (
        "coordinate_validation_signature_monotonic_forced_label_infeasible"
    )
    assert attribution_sample["coordinate_validation_status"] == "INFEASIBLE"
    assert attribution_sample["coordinate_validation_reason"] == (
        "signature_monotonic_forced_label_infeasible"
    )
    assert attribution_sample["coordinate_validation_forced_slot_field_count"] == 2
    assert attribution_sample["coordinate_validation_forced_ghost_anchor"] is True
    assert attribution_sample["coordinate_validation_solver_profile_id"] == (
        "signature_monotonic_precheck"
    )


def test_exact_candidate_warm_start_reports_none_compatible_when_all_ghost_anchors_overlap() -> None:
    model = _build_exact_ghost_warm_start_model(
        mandatory_pose_anchors=(0, 1),
        grid_width=2,
        ghost_rect=(1, 1),
    )

    warm_start = model.build_exact_candidate_warm_start()

    assert warm_start["solution_hint"] == {"miner_001": 0, "miner_002": 1}
    assert warm_start["ghost_anchor_hint_idx"] is None
    assert warm_start["ghost_anchor_hint_status"] == "none_compatible"
    assert warm_start["mandatory_hint_pose_count"] == 2
    assert warm_start["mandatory_hint_occupied_cell_count"] == 2
    assert warm_start["ghost_anchor_total_count"] == len(model.u_vars)
    assert warm_start["ghost_anchor_compatible_count"] == 0
    assert warm_start["first_compatible_ghost_anchor_idx"] is None
    assert warm_start["warm_start_strategy"] == "global_greedy_fallback"
    assert warm_start["ghost_aware_anchor_attempt_count"] == len(model.u_vars)
    assert warm_start["ghost_aware_anchor_selected_idx"] is None
    assert warm_start["ghost_aware_complete_mandatory_hint"] is False
    assert warm_start["ghost_aware_hint_instances"] == 0
    assert model.build_stats["exact_candidate_warm_start"]["ghost_anchor_hint_status"] == (
        "none_compatible"
    )


def test_exact_candidate_warm_start_can_apply_single_group_local_repair() -> None:
    model = _build_intra_group_greedy_exhausted_failure_model()
    _override_all_ghost_domains(model, blocked_cells={(2, 0)})

    warm_start = model.build_exact_candidate_warm_start()

    assert warm_start["solution_hint"] == {"miner_001": 2, "miner_002": 1}
    assert warm_start["ghost_anchor_hint_status"] == "applied"
    assert warm_start["warm_start_strategy"] == "ghost_aware_local_repair"
    assert warm_start["local_repair_attempted"] is True
    assert warm_start["local_repair_success"] is True
    assert warm_start["local_repair_trigger_reason"] == "intra_group_greedy_exhausted"
    assert warm_start["local_repair_window_size"] == 1
    assert warm_start["local_repair_anchor_idx"] == 0
    assert warm_start["local_repair_failed_group_id"] == str(model._mandatory_groups[0]["group_id"])
    assert warm_start["local_repair_failed_group_template"] == "miner"
    assert warm_start["local_repair_portfolio_attempt_count"] == 2
    assert warm_start["local_repair_selected_group_orderings"] == ["reverse_canonical"]
    assert warm_start["local_repair_attempt_count"] == 1
    assert warm_start["local_repair_success_count"] == 1
    assert warm_start["local_repair_intra_group_attempted_count"] == 1
    assert warm_start["local_repair_committed_attempted_count"] == 0
    assert warm_start["local_repair_window1_count"] == 1
    assert warm_start["local_repair_window2_count"] == 0
    assert warm_start["ghost_aware_anchor_attempt_count"] == 1
    assert warm_start["ghost_aware_anchor_selected_idx"] == 0
    assert warm_start["ghost_aware_complete_mandatory_hint"] is True
    assert warm_start["ghost_aware_hint_instances"] == 2


def test_exact_candidate_warm_start_can_apply_two_group_local_repair() -> None:
    model = _build_committed_cells_local_repair_success_model()
    _override_all_ghost_domains(model, blocked_cells={(4, 0)})

    warm_start = model.build_exact_candidate_warm_start()

    assert warm_start["solution_hint"] == {"alpha_001": 1, "beta_001": 0}
    assert warm_start["ghost_anchor_hint_status"] == "applied"
    assert warm_start["warm_start_strategy"] == "ghost_aware_local_repair"
    assert warm_start["local_repair_attempted"] is True
    assert warm_start["local_repair_success"] is True
    assert warm_start["local_repair_trigger_reason"] == "committed_cells_exhausted"
    assert warm_start["local_repair_window_size"] == 2
    assert warm_start["local_repair_anchor_idx"] == 0
    assert warm_start["local_repair_failed_group_template"] == "beta"
    assert warm_start["local_repair_portfolio_attempt_count"] == 5
    assert warm_start["local_repair_selected_group_orderings"] == [
        "reverse_canonical",
        "canonical",
    ]
    assert warm_start["local_repair_attempt_count"] == 1
    assert warm_start["local_repair_success_count"] == 1
    assert warm_start["local_repair_intra_group_attempted_count"] == 0
    assert warm_start["local_repair_committed_attempted_count"] == 1
    assert warm_start["local_repair_window1_count"] == 0
    assert warm_start["local_repair_window2_count"] == 1
    assert warm_start["ghost_aware_anchor_attempt_count"] == 1
    assert warm_start["ghost_aware_anchor_selected_idx"] == 0
    assert warm_start["ghost_aware_complete_mandatory_hint"] is True
    assert warm_start["ghost_aware_hint_instances"] == 2


def test_exact_candidate_warm_start_can_apply_pose_order_portfolio(monkeypatch) -> None:
    model = _build_pose_order_portfolio_success_model()
    _override_all_ghost_domains(model, blocked_cells=set())

    monkeypatch.setattr(
        model,
        "_attempt_mandatory_local_repair",
        lambda **_kwargs: {
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
        },
    )

    warm_start = model.build_exact_candidate_warm_start()

    assert warm_start["solution_hint"] == {"miner_001": 1, "miner_002": 2}
    assert warm_start["ghost_anchor_hint_status"] == "applied"
    assert warm_start["warm_start_strategy"] == "ghost_aware_pose_order_portfolio"
    assert warm_start["ghost_aware_pose_order_portfolio_attempted"] is True
    assert warm_start["ghost_aware_pose_order_portfolio_success"] is True
    assert (
        warm_start["ghost_aware_pose_order_portfolio_selected_ordering"]
        == "y_then_x"
    )
    assert warm_start["ghost_aware_pose_order_portfolio_attempt_count"] == 1
    assert warm_start["ghost_aware_pose_order_portfolio_failed_anchor_count"] == 0
    assert warm_start["ghost_aware_pose_order_portfolio_failure_samples"] == []
    assert warm_start["ghost_aware_pose_order_validation_attempt_count"] == 1
    assert warm_start["ghost_aware_pose_order_validation_rejected_count"] == 0
    assert warm_start["ghost_aware_pose_order_validation_last_status"] in {
        "OPTIMAL",
        "FEASIBLE",
    }
    assert warm_start["ghost_aware_complete_mandatory_hint"] is True
    assert warm_start["ghost_aware_hint_instances"] == 2
    assert model.build_stats["exact_candidate_warm_start"][
        "ghost_aware_pose_order_portfolio_selected_ordering"
    ] == "y_then_x"


def test_exact_candidate_warm_start_rejects_invalid_pose_order_portfolio(
    monkeypatch,
) -> None:
    model = _build_pose_order_portfolio_success_model()
    _override_all_ghost_domains(model, blocked_cells=set())

    monkeypatch.setattr(
        model,
        "_attempt_mandatory_local_repair",
        lambda **_kwargs: {
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
        },
    )
    monkeypatch.setattr(
        model,
        "_validate_coordinate_forced_hint",
        lambda **_kwargs: {
            "attempted": True,
            "status": "INFEASIBLE",
            "accepted": False,
            "reason": "infeasible",
        },
    )

    warm_start = model.build_exact_candidate_warm_start()

    assert warm_start["ghost_anchor_hint_status"] == "none_compatible"
    assert warm_start["warm_start_strategy"] == "global_greedy_fallback"
    assert warm_start["ghost_aware_pose_order_portfolio_attempted"] is True
    assert warm_start["ghost_aware_pose_order_portfolio_success"] is False
    assert warm_start["ghost_aware_pose_order_validation_attempt_count"] == len(
        model.u_vars
    )
    assert warm_start["ghost_aware_pose_order_validation_rejected_count"] == len(
        model.u_vars
    )
    assert warm_start["ghost_aware_pose_order_validation_last_status"] == "INFEASIBLE"
    assert (
        warm_start["ghost_aware_pose_order_portfolio_failure_reason_counts"]
        == {"coordinate_validation_infeasible": len(model.u_vars)}
    )
    assert warm_start["ghost_aware_pose_order_portfolio_failure_samples"] == [
        {
            "anchor_idx": int(idx),
            "ordering": "y_then_x",
            "source": "coordinate_validation",
            "failure_reason": "coordinate_validation_infeasible",
            "status": "INFEASIBLE",
            "reason": "infeasible",
            "forced_slot_field_count": 0,
            "forced_ghost_anchor": False,
            "wall_time": 0.0,
            "deterministic_time": 0.0,
            "branches": 0,
            "conflicts": 0,
        }
        for idx in model._ordered_ghost_anchor_indices()[:8]
    ]
    assert warm_start["ghost_aware_pose_order_validation_rejection_samples"] == [
        {
            "anchor_idx": int(idx),
            "ordering": "y_then_x",
            "status": "INFEASIBLE",
            "reason": "infeasible",
            "forced_slot_field_count": 0,
            "forced_ghost_anchor": False,
            "wall_time": 0.0,
            "deterministic_time": 0.0,
            "branches": 0,
            "conflicts": 0,
            "solver_parameters": {},
        }
        for idx in model._ordered_ghost_anchor_indices()[:8]
    ]
    assert model.build_stats["exact_candidate_warm_start"][
        "ghost_aware_pose_order_validation_rejection_samples"
    ] == warm_start["ghost_aware_pose_order_validation_rejection_samples"]


def test_boundary_storage_port_feasibility_screen_passes_without_blocking() -> None:
    model = _build_boundary_storage_port_screen_model(required_count=4)
    _override_all_ghost_domains(model, blocked_cells=set())

    summary = model.evaluate_exact_candidate_boundary_port_feasibility()
    warm_start = model.build_exact_candidate_warm_start()
    stats = model.build_stats["exact_candidate_warm_start_boundary_port_feasibility"]

    assert summary["rebuild_anchor_indices"] == tuple(model._ordered_ghost_anchor_indices())
    assert stats == {
        "supported": True,
        "required_count": 4,
        "considered_anchor_count": len(model.u_vars),
        "screened_infeasible_anchor_count": 0,
        "screen_pass_anchor_count": len(model.u_vars),
        "unsupported_anchor_count": 0,
        "max_packable_min": 4,
        "max_packable_max": 4,
        "first_infeasible_anchor_idx": None,
        "first_infeasible_anchor_max_packable": None,
    }
    assert warm_start["ghost_anchor_hint_status"] == "applied"
    assert warm_start["warm_start_strategy"] == "ghost_aware_mandatory_rebuild"
    assert warm_start["ghost_aware_anchor_attempt_count"] == 1
    assert warm_start["local_repair_attempted"] is False


def test_boundary_storage_port_feasibility_screen_can_skip_infeasible_anchors() -> None:
    model = _build_boundary_storage_port_screen_model(required_count=4)
    _override_all_ghost_domains(model, blocked_cells={(0, 4)})

    summary = model.evaluate_exact_candidate_boundary_port_feasibility()
    warm_start = model.build_exact_candidate_warm_start()
    stats = model.build_stats["exact_candidate_warm_start_boundary_port_feasibility"]
    failure_stats = model.build_stats["exact_candidate_warm_start_failure_attribution"]

    assert summary["rebuild_anchor_indices"] == ()
    assert stats == {
        "supported": True,
        "required_count": 4,
        "considered_anchor_count": len(model.u_vars),
        "screened_infeasible_anchor_count": len(model.u_vars),
        "screen_pass_anchor_count": 0,
        "unsupported_anchor_count": 0,
        "max_packable_min": 3,
        "max_packable_max": 3,
        "first_infeasible_anchor_idx": 0,
        "first_infeasible_anchor_max_packable": 3,
    }
    assert warm_start["ghost_anchor_hint_idx"] is None
    assert warm_start["ghost_anchor_hint_status"] == "none_compatible"
    assert warm_start["warm_start_strategy"] == "global_greedy_fallback"
    assert warm_start["ghost_aware_anchor_attempt_count"] == 0
    assert warm_start["local_repair_attempted"] is False
    assert failure_stats["attempted_anchor_count"] == 0
    assert failure_stats["failed_anchor_count"] == 0
    assert failure_stats["failure_reason_counts"] == {}


def test_boundary_storage_port_feasibility_screen_blocks_port_cells() -> None:
    model = _build_boundary_storage_port_screen_model(required_count=4)
    for pose in model.facility_pools["boundary_storage_port"]:
        pose["output_port_cells"] = [{"x": 7, "y": 7, "dir": "E"}]
    _override_all_ghost_domains(model, blocked_cells={(7, 7)})

    summary = model.evaluate_exact_candidate_boundary_port_feasibility()
    warm_start = model.build_exact_candidate_warm_start()
    stats = model.build_stats["exact_candidate_warm_start_boundary_port_feasibility"]

    assert summary["rebuild_anchor_indices"] == ()
    assert stats == {
        "supported": True,
        "required_count": 4,
        "considered_anchor_count": len(model.u_vars),
        "screened_infeasible_anchor_count": len(model.u_vars),
        "screen_pass_anchor_count": 0,
        "unsupported_anchor_count": 0,
        "max_packable_min": 0,
        "max_packable_max": 0,
        "first_infeasible_anchor_idx": 0,
        "first_infeasible_anchor_max_packable": 0,
    }
    assert warm_start["ghost_anchor_hint_idx"] is None
    assert warm_start["ghost_anchor_hint_status"] == "none_compatible"
    assert warm_start["warm_start_strategy"] == "global_greedy_fallback"


def test_boundary_storage_port_greedy_blocks_port_cells() -> None:
    model = _build_boundary_storage_port_screen_model(required_count=1)
    for pose in model.facility_pools["boundary_storage_port"]:
        pose["output_port_cells"] = [{"x": 7, "y": 7, "dir": "E"}]
    model._pose_greedy_blocking_cells_by_template_pose = {}
    group = model._mandatory_groups[0]
    candidates_by_group = {
        str(group["group_id"]): model._candidate_pose_indices_for_group(group)
    }

    result = model._run_mandatory_greedy_pass(
        ordered_groups=[group],
        candidates_by_group=candidates_by_group,
        blocked_cells={(7, 7)},
        stop_on_first_failure=True,
    )

    assert result["complete"] is False
    assert result["first_failure_reason"] == "blocked_cells_exhausted"
    assert result["first_failed_group_surviving_after_blocked_count"] == 0


def test_boundary_storage_port_feasibility_screen_falls_back_when_geometry_is_unsupported() -> None:
    model = _build_boundary_storage_port_screen_model(
        required_count=1,
        malformed_geometry=True,
    )
    _override_all_ghost_domains(model, blocked_cells=set())

    summary = model.evaluate_exact_candidate_boundary_port_feasibility()
    warm_start = model.build_exact_candidate_warm_start()
    stats = model.build_stats["exact_candidate_warm_start_boundary_port_feasibility"]

    assert summary["rebuild_anchor_indices"] == tuple(model._ordered_ghost_anchor_indices())
    assert stats == {
        "supported": False,
        "required_count": 1,
        "considered_anchor_count": len(model.u_vars),
        "screened_infeasible_anchor_count": 0,
        "screen_pass_anchor_count": 0,
        "unsupported_anchor_count": len(model.u_vars),
        "max_packable_min": None,
        "max_packable_max": None,
        "first_infeasible_anchor_idx": None,
        "first_infeasible_anchor_max_packable": None,
    }
    assert warm_start["ghost_anchor_hint_status"] == "applied"
    assert warm_start["warm_start_strategy"] == "ghost_aware_mandatory_rebuild"
    assert warm_start["ghost_aware_anchor_attempt_count"] == 1


def test_boundary_port_precheck_skips_large_anchor_sets(monkeypatch) -> None:
    model = _build_boundary_storage_port_screen_model(required_count=4)
    monkeypatch.setenv(
        master_model_module.EXACT_BOUNDARY_PORT_PRECHECK_MAX_ANCHORS_ENV,
        "1",
    )

    summary = model.evaluate_exact_candidate_boundary_port_feasibility()
    stats = model.build_stats["exact_candidate_warm_start_boundary_port_feasibility"]
    helper_summary = MasterPlacementModel.evaluate_boundary_port_feasibility_from_screen_spec(
        rules=model.rules,
        ghost_rect=model.ghost_rect,
        screen_spec=model._boundary_storage_port_feasibility_screen_spec(),
    )
    warm_start = model.build_exact_candidate_warm_start()

    assert len(model._ordered_ghost_anchor_indices()) > 1
    assert summary == {
        **MasterPlacementModel._default_exact_candidate_boundary_port_feasibility_payload(),
        "skipped_due_to_anchor_limit": True,
    }
    assert helper_summary == summary
    assert stats == {
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
        "skipped_due_to_anchor_limit": True,
    }
    assert warm_start["ghost_anchor_hint_status"] == "skipped_anchor_limit"
    assert warm_start["ghost_anchor_compatibility_skipped"] is True
    assert warm_start["warm_start_strategy"] == "precheck_anchor_limit_skipped"


def test_mandatory_manufacturing_rectangle_precheck_detects_all_anchor_infeasibility() -> None:
    model = _build_mandatory_manufacturing_rectangle_precheck_model(
        required_count=2,
        overlapping_pool=True,
    )
    _override_ghost_domains_by_index(
        model,
        blocked_cells_by_index={
            0: set(),
            1: set(),
        },
    )

    summary = model.evaluate_exact_candidate_mandatory_rectangle_prechecks()
    stats = model.build_stats["exact_candidate_warm_start_mandatory_group_prechecks"]

    assert summary["supported_group_count"] == 1
    assert summary["evaluated"] is True
    assert summary["skipped_due_to_upstream_precheck"] is False
    assert summary["upstream_anchor_filter_count"] == 0
    assert summary["rebuild_anchor_indices"] == ()
    assert stats["supported_group_count"] == 1
    assert stats["evaluated"] is True
    assert stats["skipped_due_to_upstream_precheck"] is False
    assert stats["upstream_anchor_filter_count"] == 0
    assert len(summary["groups"]) == 1
    assert summary["groups"][0] == {
        "group_id": "group::manufacturing_3x3::smelting::0",
        "facility_type": "manufacturing_3x3",
        "operation_type": "smelting",
        "required_count": 2,
        "oracle_class": "uniform_3x3",
        "oracle_mode": "uniform_3x3",
        "supported": True,
        "unsupported_reason": None,
        "considered_anchor_count": len(model.u_vars),
        "screened_infeasible_anchor_count": len(model.u_vars),
        "screen_pass_anchor_count": 0,
        "unsupported_anchor_count": 0,
        "max_packable_min": 1,
        "max_packable_max": 1,
        "first_infeasible_anchor_idx": 0,
        "first_infeasible_anchor_max_packable": 1,
    }


def test_mandatory_manufacturing_rectangle_precheck_reuses_cached_pass_anchors() -> None:
    model = _build_mandatory_manufacturing_rectangle_precheck_model(required_count=2)
    _override_ghost_domains_by_index(
        model,
        blocked_cells_by_index={
            0: set(),
            1: {(3, 0)},
        },
    )

    summary = model.evaluate_exact_candidate_mandatory_rectangle_prechecks()
    warm_start = model.build_exact_candidate_warm_start()

    assert summary["supported_group_count"] == 1
    assert summary["evaluated"] is True
    assert summary["skipped_due_to_upstream_precheck"] is False
    assert summary["upstream_anchor_filter_count"] == 0
    assert summary["rebuild_anchor_indices"] == (0,)
    assert summary["groups"][0]["screened_infeasible_anchor_count"] == 1
    assert summary["groups"][0]["screen_pass_anchor_count"] == 1
    assert warm_start["ghost_aware_anchor_attempt_count"] == 2
    assert warm_start["ghost_anchor_hint_status"] == "none_compatible"
    assert warm_start["ghost_aware_coordinate_validation_rejected_count"] == 1
    assert warm_start["ghost_aware_coordinate_validation_last_status"] == "INFEASIBLE"


def test_mandatory_rectangle_precheck_supports_m6x4_mixed_mode() -> None:
    model = _build_mandatory_manufacturing_rectangle_precheck_model(
        facility_type="manufacturing_6x4",
        operation_type="refining",
        required_count=2,
    )
    second_pose_cells = set(model._pose_cells("manufacturing_6x4", 1))
    _override_ghost_domains_by_index(
        model,
        blocked_cells_by_index={
            0: set(),
            1: second_pose_cells,
        },
    )

    summary = model.evaluate_exact_candidate_mandatory_rectangle_prechecks()

    assert summary["supported_group_count"] == 1
    assert summary["groups"][0]["oracle_class"] == "m6x4_mixed"
    assert summary["groups"][0]["oracle_mode"] == "m6x4_mixed"
    assert summary["groups"][0]["unsupported_reason"] is None
    assert summary["groups"][0]["considered_anchor_count"] == len(model.u_vars)
    assert summary["groups"][0]["screened_infeasible_anchor_count"] == 1
    assert summary["groups"][0]["screen_pass_anchor_count"] == 1
    assert summary["rebuild_anchor_indices"] == (0,)


def test_mandatory_rectangle_precheck_witness_short_circuits_large_pass(
    monkeypatch,
) -> None:
    pose_dimensions = tuple((6, 4) if idx % 2 == 0 else (4, 6) for idx in range(130))
    model = _build_mandatory_manufacturing_rectangle_precheck_model(
        facility_type="manufacturing_6x4",
        operation_type="filling_capsule",
        required_count=3,
        pose_dimensions=pose_dimensions,
    )
    _override_all_ghost_domains(model, blocked_cells=set())

    def _unexpected_capacity_solver(*args, **kwargs):
        raise AssertionError("large pass case should use witness before exact capacity")

    monkeypatch.setattr(
        model,
        "_solve_exact_local_power_capacity_from_compact",
        _unexpected_capacity_solver,
    )

    summary = model.evaluate_exact_candidate_mandatory_rectangle_prechecks()
    group = summary["groups"][0]

    assert summary["rebuild_anchor_indices"] == tuple(model._ordered_ghost_anchor_indices())
    assert group["oracle_mode"] == "m6x4_mixed"
    assert group["screen_pass_anchor_count"] == len(model.u_vars)
    assert group["screened_infeasible_anchor_count"] == 0
    assert group["witness_pass_anchor_count"] == len(model.u_vars)
    assert group["exact_capacity_eval_count"] == 0
    assert group["max_packable_lower_bound_min"] == 3
    assert group["max_packable_lower_bound_max"] == 3


def test_mandatory_rectangle_precheck_time_budget_keeps_rebuild_anchors(
    monkeypatch,
) -> None:
    model = _build_mandatory_manufacturing_rectangle_precheck_model()
    _override_all_ghost_domains(model, blocked_cells=set())
    ticks = iter([0.0, 1.0, 1.0])
    monkeypatch.setenv(
        master_model_module.EXACT_MANDATORY_RECTANGLE_PRECHECK_TIME_BUDGET_SECONDS_ENV,
        "0.5",
    )
    monkeypatch.setattr(
        master_model_module.time,
        "perf_counter",
        lambda: next(ticks, 1.0),
    )

    summary = model.evaluate_exact_candidate_mandatory_rectangle_prechecks()

    assert summary["interrupted_due_to_time_budget"] is True
    assert summary["rebuild_anchor_indices"] == tuple(
        model._ordered_ghost_anchor_indices()
    )


def test_mandatory_rectangle_precheck_can_screen_all_m6x4_anchors() -> None:
    model = _build_mandatory_manufacturing_rectangle_precheck_model(
        facility_type="manufacturing_6x4",
        operation_type="refining",
        required_count=2,
    )
    first_pose_cells = set(model._pose_cells("manufacturing_6x4", 0))
    second_pose_cells = set(model._pose_cells("manufacturing_6x4", 1))
    _override_ghost_domains_by_index(
        model,
        blocked_cells_by_index={
            0: first_pose_cells,
            1: second_pose_cells,
        },
    )

    summary = model.evaluate_exact_candidate_mandatory_rectangle_prechecks()

    assert summary["supported_group_count"] == 1
    assert summary["rebuild_anchor_indices"] == ()
    assert summary["groups"][0]["oracle_mode"] == "m6x4_mixed"
    assert summary["groups"][0]["screen_pass_anchor_count"] == 0
    assert summary["groups"][0]["screened_infeasible_anchor_count"] == len(model.u_vars)
    assert summary["groups"][0]["unsupported_anchor_count"] == 0


def test_mandatory_rectangle_precheck_supports_generic_normalized_rectangles() -> None:
    model = _build_mandatory_manufacturing_rectangle_precheck_model(
        facility_type="manufacturing_5x5",
        operation_type="assembly",
        required_count=2,
    )
    _override_ghost_domains_by_index(
        model,
        blocked_cells_by_index={
            0: set(),
            1: set(),
        },
    )

    summary = model.evaluate_exact_candidate_mandatory_rectangle_prechecks()

    assert summary["supported_group_count"] == 1
    assert summary["groups"][0]["oracle_class"] is None
    assert summary["groups"][0]["oracle_mode"] == "generic_normalized_rect"
    assert summary["groups"][0]["supported"] is True
    assert summary["groups"][0]["unsupported_reason"] is None


def test_mandatory_manufacturing_rectangle_precheck_falls_back_when_geometry_is_unsupported() -> None:
    model = _build_mandatory_manufacturing_rectangle_precheck_model(
        required_count=2,
        malformed_geometry=True,
    )
    _override_ghost_domains_by_index(
        model,
        blocked_cells_by_index={
            0: set(),
            1: {(3, 0)},
        },
    )

    summary = model.evaluate_exact_candidate_mandatory_rectangle_prechecks()
    warm_start = model.build_exact_candidate_warm_start()
    stats = model.build_stats["exact_candidate_warm_start_mandatory_group_prechecks"]

    assert summary["supported_group_count"] == 0
    assert summary["evaluated"] is True
    assert summary["skipped_due_to_upstream_precheck"] is False
    assert summary["upstream_anchor_filter_count"] == 0
    assert summary["rebuild_anchor_indices"] == tuple(model._ordered_ghost_anchor_indices())
    assert stats["supported_group_count"] == 0
    assert stats["evaluated"] is False
    assert stats["skipped_due_to_upstream_precheck"] is False
    assert stats["upstream_anchor_filter_count"] == 0
    assert len(summary["groups"]) == 1
    assert summary["groups"][0] == {
        "group_id": "group::manufacturing_3x3::smelting::0",
        "facility_type": "manufacturing_3x3",
        "operation_type": "smelting",
        "required_count": 2,
        "oracle_class": None,
        "oracle_mode": "unsupported",
        "supported": False,
        "unsupported_reason": "non_rectangular_signature",
        "considered_anchor_count": len(model.u_vars),
        "screened_infeasible_anchor_count": 0,
        "screen_pass_anchor_count": 0,
        "unsupported_anchor_count": len(model.u_vars),
        "max_packable_min": None,
        "max_packable_max": None,
        "first_infeasible_anchor_idx": None,
        "first_infeasible_anchor_max_packable": None,
    }
    assert stats["groups"] == []
    assert warm_start["ghost_anchor_hint_status"] == "none_compatible"
    assert warm_start["ghost_aware_anchor_attempt_count"] == 2
    assert warm_start["ghost_aware_coordinate_validation_rejected_count"] == 1


def test_warm_start_skips_mandatory_rectangle_precheck_when_boundary_screen_has_no_pass_anchors(
    monkeypatch,
) -> None:
    model = _build_boundary_storage_port_screen_model(required_count=4)
    _override_all_ghost_domains(model, blocked_cells={(0, 4)})

    def _unexpected_mandatory_precheck(self, anchor_indices=None):
        raise AssertionError("manufacturing precheck should be skipped when boundary pass anchors are empty")

    monkeypatch.setattr(
        MasterPlacementModel,
        "evaluate_exact_candidate_mandatory_rectangle_prechecks",
        _unexpected_mandatory_precheck,
    )

    warm_start = model.build_exact_candidate_warm_start()

    assert warm_start["ghost_aware_anchor_attempt_count"] == 0
    assert warm_start["ghost_anchor_hint_status"] == "none_compatible"


def test_mandatory_rectangle_precheck_uses_subset_aware_cache() -> None:
    model = _build_mandatory_manufacturing_rectangle_precheck_model(required_count=2)
    _override_ghost_domains_by_index(
        model,
        blocked_cells_by_index={
            0: set(),
            1: {(3, 0)},
        },
    )
    solve_call_count = 0
    original_solver = model._solve_exact_local_power_capacity_from_compact

    def _counting_solver(tpl, compact_signature):
        nonlocal solve_call_count
        solve_call_count += 1
        return original_solver(tpl, compact_signature)

    model._solve_exact_local_power_capacity_from_compact = _counting_solver
    try:
        summary_1 = model.evaluate_exact_candidate_mandatory_rectangle_prechecks(
            anchor_indices=(0,)
        )
        first_call_count = solve_call_count
        summary_2 = model.evaluate_exact_candidate_mandatory_rectangle_prechecks(
            anchor_indices=(0,)
        )
    finally:
        model._solve_exact_local_power_capacity_from_compact = original_solver

    assert first_call_count == 1
    assert solve_call_count == 1
    assert summary_1 == summary_2
    assert summary_1["evaluated"] is True
    assert summary_1["skipped_due_to_upstream_precheck"] is False
    assert summary_1["upstream_anchor_filter_count"] == 1
    assert summary_1["groups"][0]["considered_anchor_count"] == 1


def test_mandatory_rectangle_precheck_skips_large_anchor_sets(monkeypatch) -> None:
    model = _build_mandatory_manufacturing_rectangle_precheck_model(required_count=2)
    monkeypatch.setenv(
        master_model_module.EXACT_MANDATORY_RECTANGLE_PRECHECK_MAX_ANCHORS_ENV,
        "1",
    )

    def _unexpected_capacity_solver(*args, **kwargs):
        raise AssertionError("large-anchor mandatory precheck should skip capacity oracles")

    monkeypatch.setattr(
        model,
        "_solve_exact_local_power_capacity_from_compact",
        _unexpected_capacity_solver,
    )

    summary = model.evaluate_exact_candidate_mandatory_rectangle_prechecks()
    stats = model.build_stats["exact_candidate_warm_start_mandatory_group_prechecks"]

    assert len(model._ordered_ghost_anchor_indices()) > 1
    assert summary["evaluated"] is False
    assert summary["skipped_due_to_upstream_precheck"] is False
    assert summary["supported_group_count"] == 0
    assert summary["groups"] == []
    assert summary["rebuild_anchor_indices"] == tuple(model._ordered_ghost_anchor_indices())
    assert stats == {
        "evaluated": False,
        "skipped_due_to_upstream_precheck": False,
        "upstream_anchor_filter_count": 0,
        "supported_group_count": 0,
        "groups": [],
    }


def test_mandatory_rectangle_precheck_time_budget_returns_partial(
    monkeypatch,
) -> None:
    model = _build_mandatory_manufacturing_rectangle_precheck_model(required_count=2)
    _override_ghost_domains_by_index(
        model,
        blocked_cells_by_index={
            0: set(),
            1: {(3, 0)},
        },
    )
    monkeypatch.setenv(
        master_model_module.EXACT_MANDATORY_RECTANGLE_PRECHECK_TIME_BUDGET_SECONDS_ENV,
        "0.5",
    )
    ticks = iter([100.0, 101.0, 101.0])
    monkeypatch.setattr(
        master_model_module.time,
        "perf_counter",
        lambda: next(ticks, 101.0),
    )

    def _unexpected_capacity_solver(*args, **kwargs):
        raise AssertionError("time-budgeted precheck should stop before capacity oracle")

    monkeypatch.setattr(
        model,
        "_solve_exact_local_power_capacity_from_compact",
        _unexpected_capacity_solver,
    )

    summary = model.evaluate_exact_candidate_mandatory_rectangle_prechecks()

    assert summary["evaluated"] is False
    assert summary["interrupted_due_to_time_budget"] is True
    assert summary["time_budget_seconds"] == 0.5
    assert summary["groups"] == []
    assert summary["rebuild_anchor_indices"] == tuple(
        model._ordered_ghost_anchor_indices()
    )


def test_warm_start_uses_boundary_pass_subset_for_mandatory_rectangle_precheck(
    monkeypatch,
) -> None:
    model = _build_mandatory_manufacturing_rectangle_precheck_model(required_count=2)
    _override_ghost_domains_by_index(
        model,
        blocked_cells_by_index={
            0: set(),
            1: {(3, 0)},
        },
    )
    original_boundary_precheck = model.evaluate_exact_candidate_boundary_port_feasibility

    def _fake_boundary_precheck():
        payload = dict(original_boundary_precheck())
        payload["supported"] = True
        payload["screen_pass_anchor_count"] = 1
        payload["screen_pass_anchor_indices"] = (0,)
        payload["rebuild_anchor_indices"] = (0,)
        model.build_stats["exact_candidate_warm_start_boundary_port_feasibility"] = {
            key: value
            for key, value in payload.items()
            if key not in {"screen_pass_anchor_indices", "rebuild_anchor_indices"}
        }
        return payload

    monkeypatch.setattr(
        model,
        "evaluate_exact_candidate_boundary_port_feasibility",
        _fake_boundary_precheck,
    )

    warm_start = model.build_exact_candidate_warm_start()
    stats = model.build_stats["exact_candidate_warm_start_mandatory_group_prechecks"]

    assert stats["evaluated"] is True
    assert stats["skipped_due_to_upstream_precheck"] is False
    assert stats["upstream_anchor_filter_count"] == 1
    assert stats["groups"][0]["considered_anchor_count"] == 1
    assert warm_start["ghost_aware_anchor_attempt_count"] == 1


def test_mandatory_support_diagnostics_report_protocol_core_empty_candidate_pool() -> None:
    model = _build_mandatory_support_diagnostics_model(
        include_supported_rectangle_group=False
    )

    summary = model.evaluate_exact_candidate_mandatory_support_diagnostics()

    assert summary == {
        "unsupported_group_count": 1,
        "empty_candidate_pool_group_count": 1,
        "groups": [
            {
                "group_id": "group::protocol_core::protocol_core::0",
                "facility_type": "protocol_core",
                "operation_type": "protocol_core",
                "required_count": 1,
                "candidate_pool_count": 0,
                "unsupported_reason": "empty_candidate_pool",
            }
        ],
    }
    assert model.build_stats["exact_candidate_mandatory_support_diagnostics"] == summary


def test_mandatory_support_diagnostics_distinguish_supported_and_empty_pool_groups() -> None:
    model = _build_mandatory_support_diagnostics_model()

    summary = model.evaluate_exact_candidate_mandatory_support_diagnostics()

    assert summary["unsupported_group_count"] == 1
    assert summary["empty_candidate_pool_group_count"] == 1
    assert summary["groups"] == [
        {
            "group_id": "group::manufacturing_3x3::smelting::0",
            "facility_type": "manufacturing_3x3",
            "operation_type": "smelting",
            "required_count": 1,
            "candidate_pool_count": 1,
            "unsupported_reason": None,
        },
        {
            "group_id": "group::protocol_core::protocol_core::1",
            "facility_type": "protocol_core",
            "operation_type": "protocol_core",
            "required_count": 1,
            "candidate_pool_count": 0,
            "unsupported_reason": "empty_candidate_pool",
        },
    ]


def test_mandatory_support_diagnostics_reuse_cache() -> None:
    model = _build_mandatory_support_diagnostics_model()
    summary_1 = model.evaluate_exact_candidate_mandatory_support_diagnostics()

    def _unexpected(*args, **kwargs):
        raise AssertionError("support diagnostics should reuse cached payload")

    model._candidate_pose_indices_for_group = _unexpected

    summary_2 = model.evaluate_exact_candidate_mandatory_support_diagnostics()

    assert summary_1 == summary_2


def test_pre_master_boundary_helper_matches_model_boundary_precheck() -> None:
    model = _build_boundary_storage_port_screen_model(required_count=4)

    summary = model.evaluate_exact_candidate_boundary_port_feasibility()
    helper_summary = MasterPlacementModel.evaluate_boundary_port_feasibility_from_screen_spec(
        rules=model.rules,
        ghost_rect=model.ghost_rect,
        screen_spec=model._boundary_storage_port_feasibility_screen_spec(),
    )

    assert helper_summary == summary


def test_build_exact_core_packages_candidate_precheck_artifacts() -> None:
    model = _build_boundary_storage_port_screen_model(required_count=4)
    expected_support = model.evaluate_exact_candidate_mandatory_support_diagnostics()
    expected_boundary_screen = model._boundary_storage_port_feasibility_screen_spec()

    core = MasterPlacementModel.build_exact_core(
        model.source_instances,
        model.facility_pools,
        model.rules,
        skip_power_coverage=model.skip_power_coverage,
        generic_io_requirements=model.generic_io_requirements,
    )

    assert core.candidate_precheck_artifacts["mandatory_support_diagnostics"] == expected_support
    assert core.candidate_precheck_artifacts["boundary_port_screen_spec"] == expected_boundary_screen


def test_from_exact_core_seeds_precomputed_boundary_feasibility_cache(
    monkeypatch,
) -> None:
    base_model = _build_boundary_storage_port_screen_model(required_count=4)
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    precomputed_boundary = MasterPlacementModel.evaluate_boundary_port_feasibility_from_screen_spec(
        rules=base_model.rules,
        ghost_rect=base_model.ghost_rect,
        screen_spec=core.candidate_precheck_artifacts["boundary_port_screen_spec"],
    )

    overlay = MasterPlacementModel.from_exact_core(
        core,
        ghost_rect=base_model.ghost_rect,
        precomputed_boundary_port_feasibility=precomputed_boundary,
    )

    def _unexpected_boundary_scan(*args, **kwargs):
        raise AssertionError("precomputed boundary precheck should be reused from cache")

    monkeypatch.setattr(
        overlay,
        "_evaluate_boundary_storage_port_anchor_feasibility",
        _unexpected_boundary_scan,
    )

    assert overlay.evaluate_exact_candidate_mandatory_support_diagnostics() == (
        core.candidate_precheck_artifacts["mandatory_support_diagnostics"]
    )
    assert overlay.evaluate_exact_candidate_boundary_port_feasibility() == (
        precomputed_boundary
    )
    warm_start = overlay.build_exact_candidate_warm_start()

    assert warm_start["ghost_anchor_total_count"] == len(overlay.u_vars)
    assert overlay.build_stats["exact_candidate_warm_start_boundary_port_feasibility"] == {
        key: value
        for key, value in precomputed_boundary.items()
        if key not in {"screen_pass_anchor_indices", "rebuild_anchor_indices"}
    }


def test_warm_start_failure_attribution_detects_blocked_cells_exhausted() -> None:
    model = _build_blocked_cells_exhausted_failure_model()
    _override_all_ghost_domains(model, blocked_cells={(0, 0)})

    warm_start = model.build_exact_candidate_warm_start()
    stats = model.build_stats["exact_candidate_warm_start_failure_attribution"]
    failed_group = model._mandatory_groups[0]

    assert warm_start["warm_start_strategy"] == "global_greedy_fallback"
    assert warm_start["local_repair_attempted"] is False
    assert stats["attempted_anchor_count"] == len(model.u_vars)
    assert stats["failed_anchor_count"] == len(model.u_vars)
    assert stats["failure_reason_counts"] == {
        "blocked_cells_exhausted": len(model.u_vars)
    }
    assert stats["first_failed_anchor_idx"] == 0
    assert stats["first_failed_group_id"] == str(failed_group["group_id"])
    assert stats["first_failed_group_template"] == "miner"
    assert stats["first_failed_group_required_count"] == 1
    assert stats["first_failed_group_candidate_count"] == 1
    assert stats["first_failed_group_surviving_after_blocked_count"] == 0
    assert stats["first_failed_group_surviving_at_failure_count"] == 0
    assert stats["first_failed_group_position"] == 0
    assert stats["top_failed_groups"][0] == {
        "group_id": str(failed_group["group_id"]),
        "facility_type": "miner",
        "count": len(model.u_vars),
    }
    assert stats["top_failed_group_failures"][0] == {
        "group_id": str(failed_group["group_id"]),
        "facility_type": "miner",
        "failure_reason": "blocked_cells_exhausted",
        "count": len(model.u_vars),
    }
    assert stats["failed_anchor_samples"][0] == {
        "anchor_idx": 0,
        "failure_reason": "blocked_cells_exhausted",
        "first_failed_group_id": str(failed_group["group_id"]),
        "first_failed_group_template": "miner",
        "first_failed_group_position": 0,
        "first_failed_group_required_count": 1,
        "first_failed_group_candidate_count": 1,
        "first_failed_group_surviving_after_blocked_count": 0,
        "first_failed_group_surviving_at_failure_count": 0,
        "blocked_cell_count": 1,
        "blocked_bbox": {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0},
        "local_repair_attempted": False,
        "local_repair_success": False,
        "local_repair_attempt_count": 0,
    }


def test_warm_start_failure_sample_limit_env_override(monkeypatch) -> None:
    model = _build_blocked_cells_exhausted_failure_model()
    _override_all_ghost_domains(model, blocked_cells={(0, 0)})
    monkeypatch.setenv(
        master_model_module.EXACT_WARM_START_FAILED_ANCHOR_SAMPLE_LIMIT_ENV,
        "1",
    )

    model.build_exact_candidate_warm_start()
    stats = model.build_stats["exact_candidate_warm_start_failure_attribution"]

    assert stats["failed_anchor_count"] == len(model.u_vars)
    assert len(stats["failed_anchor_samples"]) == 1


def test_warm_start_failure_attribution_detects_committed_cells_exhausted() -> None:
    model = _build_committed_cells_exhausted_failure_model()
    _override_all_ghost_domains(model, blocked_cells={(1, 0)})

    warm_start = model.build_exact_candidate_warm_start()
    stats = model.build_stats["exact_candidate_warm_start_failure_attribution"]
    failed_group = next(
        group for group in model._mandatory_groups if str(group["facility_type"]) == "beta"
    )

    assert warm_start["warm_start_strategy"] == "global_greedy_fallback"
    assert stats["attempted_anchor_count"] == len(model.u_vars)
    assert stats["failed_anchor_count"] == len(model.u_vars)
    assert stats["failure_reason_counts"] == {
        "committed_cells_exhausted": len(model.u_vars)
    }
    assert stats["first_failed_group_id"] == str(failed_group["group_id"])
    assert stats["first_failed_group_template"] == "beta"
    assert stats["first_failed_group_required_count"] == 1
    assert stats["first_failed_group_candidate_count"] == 1
    assert stats["first_failed_group_surviving_after_blocked_count"] == 1
    assert stats["first_failed_group_surviving_at_failure_count"] == 0
    assert stats["first_failed_group_position"] == 1
    assert stats["top_failed_groups"][0] == {
        "group_id": str(failed_group["group_id"]),
        "facility_type": "beta",
        "count": len(model.u_vars),
    }
    assert stats["top_failed_group_failures"][0] == {
        "group_id": str(failed_group["group_id"]),
        "facility_type": "beta",
        "failure_reason": "committed_cells_exhausted",
        "count": len(model.u_vars),
    }
    assert stats["failed_anchor_samples"][0]["failure_reason"] == (
        "committed_cells_exhausted"
    )
    assert stats["failed_anchor_samples"][0]["first_failed_group_id"] == str(
        failed_group["group_id"]
    )
    assert stats["failed_anchor_samples"][0]["first_failed_group_position"] == 1


def test_warm_start_failure_attribution_detects_intra_group_greedy_exhausted() -> None:
    model = _build_intra_group_greedy_exhausted_failure_model()
    raw_hint = model._build_mandatory_greedy_solution_hint(blocked_cells={(2, 0)})
    failed_group = model._mandatory_groups[0]

    assert raw_hint["complete"] is False
    assert raw_hint["first_failure_reason"] == "intra_group_greedy_exhausted"
    assert raw_hint["first_failed_group_id"] == str(failed_group["group_id"])
    assert raw_hint["first_failed_group_template"] == "miner"
    assert raw_hint["first_failed_group_required_count"] == 2
    assert raw_hint["first_failed_group_candidate_count"] == 3
    assert raw_hint["first_failed_group_surviving_after_blocked_count"] == 3
    assert raw_hint["first_failed_group_surviving_at_failure_count"] == 3
    assert raw_hint["first_failed_group_position"] == 0


def test_exact_coordinate_solution_hint_can_apply_one_hot_ghost_anchor() -> None:
    model = _build_exact_ghost_warm_start_model(
        mandatory_pose_anchors=(0,),
        grid_width=3,
        ghost_rect=(1, 1),
    )
    model.build()
    warm_start = model.build_exact_candidate_warm_start()
    selected_idx = int(warm_start["ghost_anchor_hint_idx"])

    hint_stats = model._coordinate_delegate.apply_solution_hint(
        warm_start["solution_hint"],
        ghost_anchor_hint_idx=selected_idx,
        hint_inactive_residual_optionals=False,
    )
    hint_values = _solution_hint_values_by_var_index(model)

    assert hint_stats["ghost_anchor_hint_applied"] is True
    assert hint_stats["ghost_anchor_hint_idx"] == selected_idx
    assert hint_values[model.u_vars[selected_idx].Index()] == 1
    for rect_idx, var in model.u_vars.items():
        expected = 1 if int(rect_idx) == selected_idx else 0
        assert hint_values[var.Index()] == expected


def test_exact_coordinate_solution_hint_can_disable_residual_zero_hints() -> None:
    model = _build_exact_residual_optional_signature_model()
    model.build()

    model._clear_solution_hints()
    hint_stats_without_zeroes = model._coordinate_delegate.apply_solution_hint(
        {},
        hint_inactive_residual_optionals=False,
    )
    hint_values_without_zeroes = _solution_hint_values_by_var_index(model)

    residual_active_indices = [
        slot.active.Index()
        for slot in model._coordinate_delegate.residual_optional_slots["protocol_storage_box"]
        if slot.active is not None
    ]
    assert hint_stats_without_zeroes["residual_optional_zero_hinting_enabled"] is False
    assert hint_stats_without_zeroes["residual_optional_zero_hints"] == 0
    assert all(index not in hint_values_without_zeroes for index in residual_active_indices)

    model._clear_solution_hints()
    hint_stats_with_zeroes = model._coordinate_delegate.apply_solution_hint(
        {},
        hint_inactive_residual_optionals=True,
    )
    hint_values_with_zeroes = _solution_hint_values_by_var_index(model)

    assert hint_stats_with_zeroes["residual_optional_zero_hinting_enabled"] is True
    assert hint_stats_with_zeroes["residual_optional_zero_hints"] == len(
        residual_active_indices
    )
    assert all(hint_values_with_zeroes[index] == 0 for index in residual_active_indices)


def test_coordinate_master_domain_activation_stats_are_recorded_for_required_optional_model() -> None:
    model = _build_exact_required_optional_signature_upper_bound_model(ghost_rect=(1, 1))
    model.build()

    stats = model.build_stats["domain_activation"]
    assert stats["ghost_anchor_count"] == len(model.u_vars)
    assert stats["mandatory_slot_count"] == 0
    assert stats["required_optional_slot_count"] == 2
    assert stats["residual_optional_slot_count"] == 0
    assert stats["required_optional_pose_literal_count"] >= 2
    assert stats["required_optional_active_slot_upper_bound_sum"] == 2
    assert stats["residual_optional_active_slot_upper_bound_sum"] == 0


def test_exact_core_overlay_recomputes_domain_activation_stats() -> None:
    base_model = _build_exact_residual_optional_signature_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))

    stats = overlay.build_stats["domain_activation"]
    assert overlay.build_stats["exact_core_reuse"]["used"] is True
    assert stats["ghost_anchor_count"] == len(overlay.u_vars)
    assert stats["mandatory_slot_count"] == 0
    assert stats["required_optional_slot_count"] == 0
    assert stats["residual_optional_slot_count"] == sum(
        len(v) for v in overlay._coordinate_delegate.residual_optional_slots.values()
    )
    assert stats["residual_optional_pose_literal_count"] > 0
    assert stats["residual_optional_active_slot_upper_bound_sum"] == stats[
        "residual_optional_slot_count"
    ]


def test_exact_master_search_guidance_profile_is_exposed() -> None:
    instances = [
        {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "miner": [
            {
                "pose_id": "pose_a",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "pose_b",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
        "power_pole": [
            {
                "pose_id": "pole_0",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[2, 0]],
            }
        ],
        "protocol_storage_box": [],
    }
    rules = {
        "globals": {"grid": {"width": 4, "height": 1}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }

    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        skip_power_coverage=True,
    )
    model.build()

    guidance = model.build_stats["search_guidance"]
    assert guidance["applied"] is True
    assert guidance["profile"] == "exact_coordinate_guided_branching_v4"
    assert guidance["mandatory_signature_counts"] == {
        "group::miner::mining::0": 1,
    }
    assert guidance["mandatory_signature_count_literals"] == 1
    assert guidance["mandatory_literals"] == 2
    assert guidance["ghost_literals"] == 4
    assert guidance["decision_strategy_phases"] == [
        "mandatory_signature_counts",
        "mandatory_slots",
        "ghost",
        "required_optional_signature_counts",
        "required_optional_slots",
        "residual_optional_family_counts",
        "residual_optional_slots",
    ]
    assert guidance["ghost_phase_index"] == 2
    assert guidance["power_pole_family_order"] == []
    assert guidance["power_pole_family_count_literals"] == 0
    assert guidance["residual_optional_family_guided"] is False
    assert guidance["optional_literals"] == {}
    assert guidance["optional_default"] == "SELECT_MIN_VALUE"
    assert model.build_stats["master_representation"] == "coordinate_exact_v2"
    assert model.build_stats["master_pose_bool_literals"] == 0
    assert model.build_stats["master_domain_encoding"] == "mode_rect_factorized_v1"
    assert model.build_stats["master_domain_table_rows"] == 0
    assert model.build_stats["master_mode_rect_domains"]["mandatory_groups"]["group::miner::mining::0"][0]["pose_count"] == 2

    status = model.solve(time_limit_seconds=5.0)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert model.build_stats["last_solve"]["search_profile"] == "exact_coordinate_guided_branching_v4"
    assert model.build_stats["last_solve"]["search_branching"].endswith("FIXED_SEARCH")
    assert isinstance(model.build_stats["last_solve"]["user_time"], float)
    assert isinstance(model.build_stats["last_solve"]["deterministic_time"], float)
    assert isinstance(model.build_stats["last_solve"]["branches"], int)
    assert isinstance(model.build_stats["last_solve"]["conflicts"], int)
    assert isinstance(model.build_stats["last_solve"]["binary_propagations"], int)
    assert isinstance(model.build_stats["last_solve"]["integer_propagations"], int)


def test_exact_master_search_branching_env_can_select_automatic(monkeypatch) -> None:
    model = _build_exact_ghost_warm_start_model(
        mandatory_pose_anchors=(0,),
        grid_width=3,
        ghost_rect=(1, 1),
    )
    model.build()
    monkeypatch.setenv(
        master_model_module.EXACT_MASTER_SEARCH_BRANCHING_ENV,
        "automatic",
    )

    status = model.solve(time_limit_seconds=5.0)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert model.build_stats["last_solve"]["requested_search_branching"] == "automatic"
    assert model.build_stats["last_solve"]["search_branching"].endswith(
        "AUTOMATIC_SEARCH"
    )


def test_exact_master_can_enable_diagnostic_solver_log_callback() -> None:
    model = _build_exact_ghost_warm_start_model(
        mandatory_pose_anchors=(0,),
        grid_width=3,
        ghost_rect=(1, 1),
    )
    model.build()
    log_lines: list[str] = []

    status = model.solve(
        time_limit_seconds=5.0,
        diagnostic_log_callback=log_lines.append,
    )

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    solver_parameters = model.build_stats["last_solve"]["solver_parameters"]
    assert solver_parameters["log_search_progress"] is True
    assert solver_parameters["log_to_stdout"] is False
    assert solver_parameters["log_callback_enabled"] is True
    assert isinstance(log_lines, list)


def test_exact_master_solver_parameter_env_can_disable_presolve_and_probe(
    monkeypatch,
) -> None:
    model = _build_exact_ghost_warm_start_model(
        mandatory_pose_anchors=(0,),
        grid_width=3,
        ghost_rect=(1, 1),
    )
    model.build()
    monkeypatch.setenv(master_model_module.EXACT_MASTER_CP_MODEL_PRESOLVE_ENV, "false")
    monkeypatch.setenv(master_model_module.EXACT_MASTER_CP_MODEL_PROBING_LEVEL_ENV, "0")
    monkeypatch.setenv(master_model_module.EXACT_MASTER_SYMMETRY_LEVEL_ENV, "0")
    monkeypatch.setenv(master_model_module.EXACT_MASTER_HINT_CONFLICT_LIMIT_ENV, "0")

    status = model.solve(time_limit_seconds=5.0)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    solver_parameters = model.build_stats["last_solve"]["solver_parameters"]
    assert solver_parameters["cp_model_presolve"] is False
    assert solver_parameters["cp_model_probing_level"] == 0
    assert solver_parameters["symmetry_level"] == 0
    assert solver_parameters["hint_conflict_limit"] == 0


@pytest.mark.parametrize("raw_value", ["-1", "1.5", "nan", "inf", "abc"])
def test_master_nonnegative_int_env_rejects_invalid_explicit_values(
    monkeypatch,
    raw_value: str,
) -> None:
    env_name = "EXACT_MASTER_TEST_NONNEGATIVE_INT"
    monkeypatch.setenv(env_name, raw_value)

    with pytest.raises(ValueError, match=env_name):
        master_model_module._resolve_nonnegative_int_env(env_name, 3)


@pytest.mark.parametrize("raw_value", ["-0.5", "nan", "inf", "-inf", "abc"])
def test_master_nonnegative_float_env_rejects_invalid_explicit_values(
    monkeypatch,
    raw_value: str,
) -> None:
    env_name = "EXACT_MASTER_TEST_NONNEGATIVE_FLOAT"
    monkeypatch.setenv(env_name, raw_value)

    with pytest.raises(ValueError, match=env_name):
        master_model_module._resolve_nonnegative_float_env(env_name, 1.0)


@pytest.mark.parametrize("raw_value", ["-1", "1.5", "nan", "inf", "abc"])
def test_master_optional_nonnegative_int_env_rejects_invalid_explicit_values(
    monkeypatch,
    raw_value: str,
) -> None:
    env_name = "EXACT_MASTER_TEST_OPTIONAL_NONNEGATIVE_INT"
    monkeypatch.setenv(env_name, raw_value)

    with pytest.raises(ValueError, match=env_name):
        master_model_module._resolve_optional_nonnegative_int_env(env_name)


def test_master_numeric_env_defaults_and_zero_remain_valid(monkeypatch) -> None:
    int_env = "EXACT_MASTER_TEST_NONNEGATIVE_INT"
    float_env = "EXACT_MASTER_TEST_NONNEGATIVE_FLOAT"
    optional_int_env = "EXACT_MASTER_TEST_OPTIONAL_NONNEGATIVE_INT"
    monkeypatch.delenv(int_env, raising=False)
    monkeypatch.delenv(float_env, raising=False)
    monkeypatch.delenv(optional_int_env, raising=False)

    assert master_model_module._resolve_nonnegative_int_env(int_env, -3) == 0
    assert master_model_module._resolve_nonnegative_float_env(float_env, -1.25) == 0.0
    assert master_model_module._resolve_optional_nonnegative_int_env(optional_int_env) is None

    monkeypatch.setenv(int_env, "0")
    monkeypatch.setenv(float_env, "0")
    monkeypatch.setenv(optional_int_env, "0")
    assert master_model_module._resolve_nonnegative_int_env(int_env, 3) == 0
    assert master_model_module._resolve_nonnegative_float_env(float_env, 1.0) == 0.0
    assert master_model_module._resolve_optional_nonnegative_int_env(optional_int_env) == 0


def test_coordinate_validation_solver_profile_is_reported() -> None:
    model = _build_exact_ghost_warm_start_model(
        mandatory_pose_anchors=(0,),
        grid_width=3,
        ghost_rect=(1, 1),
    )
    model.build()

    validation = model._validate_coordinate_forced_hint(
        solution_hint={},
        ghost_anchor_hint_idx=None,
        time_limit_seconds=1.0,
        require_complete=False,
        solver_parameter_profile={
            "profile_id": "validation_presolve_off",
            "search_branching": "fixed",
            "worker_count": 1,
            "cp_model_presolve": False,
            "cp_model_probing_level": 0,
            "symmetry_level": 0,
            "hint_conflict_limit": 0,
        },
    )

    assert validation["attempted"] is True
    assert isinstance(validation["deterministic_time"], float)
    assert isinstance(validation["branches"], int)
    solver_parameters = validation["solver_parameters"]
    assert solver_parameters["profile_id"] == "validation_presolve_off"
    assert solver_parameters["cp_model_presolve"] is False
    assert solver_parameters["cp_model_probing_level"] == 0
    assert solver_parameters["symmetry_level"] == 0
    assert solver_parameters["hint_conflict_limit"] == 0


@pytest.mark.parametrize(
    ("master_search_profile", "expected_phases", "expected_ghost_phase_index"),
    [
        (
            "exact_coordinate_guided_branching_v4",
            [
                "mandatory_signature_counts",
                "mandatory_slots",
                "ghost",
                "required_optional_signature_counts",
                "required_optional_slots",
                "residual_optional_family_counts",
                "residual_optional_slots",
            ],
            2,
        ),
        (
            "exact_coordinate_ghost_after_counts_v1",
            [
                "mandatory_signature_counts",
                "ghost",
                "mandatory_slots",
                "required_optional_signature_counts",
                "required_optional_slots",
                "residual_optional_family_counts",
                "residual_optional_slots",
            ],
            1,
        ),
        (
            "exact_coordinate_ghost_first_v1",
            [
                "ghost",
                "mandatory_signature_counts",
                "mandatory_slots",
                "required_optional_signature_counts",
                "required_optional_slots",
                "residual_optional_family_counts",
                "residual_optional_slots",
            ],
            0,
        ),
    ],
)
def test_exact_master_search_guidance_profiles_are_stably_exposed(
    master_search_profile: str,
    expected_phases: list[str],
    expected_ghost_phase_index: int,
) -> None:
    model = MasterPlacementModel(
        instances=[
            {
                "instance_id": "miner_001",
                "facility_type": "miner",
                "operation_type": "mining",
                "is_mandatory": True,
                "bound_type": "exact",
            }
        ],
        facility_pools={
            "miner": [
                {
                    "pose_id": "pose_a",
                    "anchor": {"x": 0, "y": 0},
                    "occupied_cells": [[0, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                },
                {
                    "pose_id": "pose_b",
                    "anchor": {"x": 1, "y": 0},
                    "occupied_cells": [[1, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                },
            ],
            "power_pole": [],
            "protocol_storage_box": [],
        },
        rules={
            "globals": {"grid": {"width": 3, "height": 2}},
            "facility_templates": {
                "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            },
        },
        solve_mode="certified_exact",
        ghost_rect=(1, 1),
        skip_power_coverage=True,
        master_search_profile=master_search_profile,
    )
    model.build()

    guidance = model.build_stats["search_guidance"]
    assert guidance["profile"] == master_search_profile
    assert guidance["search_branching"] == "FIXED_SEARCH"
    assert guidance["decision_strategy_phases"] == expected_phases
    assert guidance["ghost_phase_index"] == expected_ghost_phase_index
    assert guidance["ghost_literals"] > 0

    status = model.solve(time_limit_seconds=0.1)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE, cp_model.UNKNOWN)
    assert model.build_stats["last_solve"]["search_profile"] == master_search_profile
    assert model.build_stats["last_solve"]["known_feasible_hint"] is False
    assert isinstance(model.build_stats["last_solve"]["branches"], int)
    assert isinstance(model.build_stats["last_solve"]["conflicts"], int)


def test_exact_search_guidance_separates_required_and_residual_optionals() -> None:
    model = MasterPlacementModel(
        instances=[],
        facility_pools={
            "power_pole": [
                {
                    "pose_id": "pole_0",
                    "anchor": {"x": 0, "y": 0},
                    "occupied_cells": [[0, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": [[1, 0]],
                }
            ],
            "protocol_storage_box": [
                {
                    "pose_id": "box_0",
                    "anchor": {"x": 1, "y": 0},
                    "occupied_cells": [[1, 0]],
                    "input_port_cells": [{"x": 1, "y": 1, "dir": "N"}],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                }
            ],
        },
        rules={
            "globals": {"grid": {"width": 3, "height": 3}},
            "facility_templates": {
                "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            },
        },
        solve_mode="certified_exact",
        skip_power_coverage=True,
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1},
        },
    )

    model.build()

    assert model.build_stats["exact_required_optionals"] == {}
    assert model.build_stats["exact_optional_lower_bounds"] == {"protocol_storage_box": 1}
    guidance = model.build_stats["search_guidance"]
    assert guidance["required_optional_templates"] == []
    assert guidance["required_optional_signature_counts"] == {}
    assert guidance["required_optional_signature_count_literals"] == 0
    assert guidance["required_optional_literals"] == {}
    assert guidance["required_optional_default"] == "SELECT_MAX_VALUE"
    assert guidance["residual_optional_literals"] == {
        "power_pole": 1,
        "protocol_storage_box": 1,
    }
    assert guidance["power_pole_family_order"] == []
    assert guidance["power_pole_family_count_literals"] == 0
    assert guidance["residual_optional_family_guided"] is False
    assert guidance["residual_optional_default"] == "SELECT_MIN_VALUE"
    assert guidance["optional_literals"] == {
        "power_pole": 1,
        "protocol_storage_box": 1,
    }


def test_mandatory_signature_buckets_are_stable_and_linked_to_raw_vars() -> None:
    instances = [
        {
            "instance_id": "router_001",
            "facility_type": "router",
            "operation_type": "routing",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "router": [
            {
                "pose_id": "plain_left",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "plain_mid",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "ported_right",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [{"x": 2, "y": 0, "dir": "E"}],
                "power_coverage_cells": None,
            },
        ],
    }
    rules = {
        "globals": {"grid": {"width": 4, "height": 2}},
        "facility_templates": {
            "router": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }

    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        skip_power_coverage=True,
    )
    model.build()

    bucket_stats = model.build_stats["signature_buckets"]["mandatory_groups"]["group::router::routing::0"]
    assert bucket_stats == {
        "bucket_count": 2,
        "pose_count": 3,
        "bucket_sizes": [2, 1],
    }
    count_vars = model._mandatory_signature_count_vars["group::router::routing::0"]
    assert sorted(count_vars) == ["sig_000", "sig_001"]
    model.model.Add(count_vars["sig_000"] == 0)

    status = model.solve(time_limit_seconds=5.0)

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    solution = model.extract_solution()
    assert solution["router_001"]["pose_id"] == "ported_right"


def test_exact_greedy_solution_hint_filters_powered_poses_without_theoretical_cover() -> None:
    instances = [
        {
            "instance_id": "powered_001",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "power_pole": [
            {
                "pose_id": "pole_0",
                "anchor": {"x": 3, "y": 3},
                "occupied_cells": [[3, 3]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[1, 0]],
            }
        ],
        "powered_machine": [
            {
                "pose_id": "machine_uncov",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "machine_cov",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
    }
    rules = {
        "globals": {"grid": {"width": 4, "height": 4}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "powered_machine": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }

    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        skip_power_coverage=True,
    )

    hint = model.build_greedy_solution_hint()

    assert hint == {"powered_001": 1}
    assert model.build_stats["greedy_hint"]["used_power_coverage_filter"] is True


def test_exact_solve_records_hint_statistics_without_known_feasible_flag() -> None:
    instances = [
        {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "miner": [
            {
                "pose_id": "pose_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ]
    }
    rules = {
        "globals": {"grid": {"width": 3, "height": 3}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }

    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        skip_power_coverage=True,
    )
    model.build()
    hint = model.build_greedy_solution_hint()
    assert hint == {"miner_001": 0}

    status = model.solve(
        time_limit_seconds=5.0,
        solution_hint=hint,
        known_feasible_hint=False,
    )

    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    assert model.build_stats["last_solve"]["hinted_literals"] == 3
    assert model.build_stats["last_solve"]["known_feasible_hint"] is False
    assert model.build_stats["last_solve"]["ghost_anchor_hint_applied"] is False
    assert model.build_stats["last_solve"]["residual_optional_zero_hinting_enabled"] is True
    assert model.build_stats["last_solve"]["residual_optional_zero_hints"] == 0


def test_exploratory_mode_does_not_support_exact_greedy_hint() -> None:
    model = MasterPlacementModel(
        instances=[],
        facility_pools={"power_pole": [], "protocol_storage_box": []},
        rules={
            "globals": {"grid": {"width": 3, "height": 3}},
            "facility_templates": {
                "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            },
        },
        solve_mode="exploratory",
        skip_power_coverage=True,
    )

    hint = model.build_greedy_solution_hint()

    assert hint == {}
    assert model.build_stats["greedy_hint"]["supported"] is False
    assert model.build_stats["greedy_hint"]["reason"] == (
        "exact-safe greedy warm start only runs in certified_exact mode"
    )


def test_exact_power_capacity_lower_bound_records_template_demand_and_cache_hits() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()

    model.build()

    stats = model.build_stats["global_valid_inequalities"]
    precompute = model.build_stats["exact_precompute_profile"]
    assert {
        "type": "power_capacity_lower_bound",
        "template": "powered_machine",
        "demand": 2,
        "nonzero_poles": 2,
    } in stats["applied"]
    assert stats["fixed_required_optional_demands"] == {}
    assert stats["powered_template_demands"] == {"powered_machine": 2}
    assert stats["capacity_coeff_stats"]["powered_machine"]["max_coeff"] == 2
    assert stats["capacity_coeff_stats"]["powered_machine"]["min_nonzero_coeff"] == 2
    assert model._local_power_capacity_signature("powered_machine", 0) == model._local_power_capacity_signature(
        "powered_machine",
        1,
    )
    assert stats["capacity_cache"]["coefficient_source"] == "exact_compact_rect_cpsat_v14"
    assert stats["capacity_cache"]["shell_pair_count"] == 1
    assert stats["capacity_cache"]["pole_template_evaluations"] == 1
    assert stats["capacity_cache"]["signature_class_count"] == 1
    assert stats["capacity_cache"]["signature_class_evaluations"] == 1
    assert stats["capacity_cache"]["compact_signature_class_count"] == 1
    assert stats["capacity_cache"]["compact_signature_class_evaluations"] == 1
    assert stats["capacity_cache"]["compact_signature_hits"] == 0
    assert stats["capacity_cache"]["compact_signature_misses"] == 1
    assert stats["capacity_cache"]["legacy_signature_materializations"] == 0
    assert stats["capacity_cache"]["supported_by_pole_materializations"] == 0
    assert stats["capacity_cache"]["compact_rect_cpsat_evaluations"] == 1
    assert stats["capacity_cache"]["compact_rect_cpsat_cache_hits"] == 0
    assert stats["capacity_cache"]["compact_rect_cpsat_selected_cases"] == 1
    assert stats["capacity_cache"]["compact_rect_cpsat_rect_dp_fallbacks"] == 0
    assert stats["capacity_cache"]["normalized_rect_signature_count"] == 1
    assert stats["capacity_cache"]["normalized_rect_cache_hits"] == 0
    assert stats["capacity_cache"]["normalized_rect_cache_misses"] == 1
    assert stats["capacity_cache"]["rect_dp_evaluations"] == 0
    assert stats["capacity_cache"]["rect_dp_cache_hits"] == 0
    assert stats["capacity_cache"]["rect_dp_cache_misses"] == 0
    assert stats["capacity_cache"]["rect_dp_state_merges"] == 0
    assert stats["capacity_cache"]["rect_dp_peak_line_states"] == 0
    assert stats["capacity_cache"]["rect_dp_peak_pos_states"] == 0
    assert stats["capacity_cache"]["rect_dp_compiled_signatures"] == 0
    assert stats["capacity_cache"]["rect_dp_compiled_start_options"] == 0
    assert stats["capacity_cache"]["rect_dp_deduped_start_options"] == 0
    assert stats["capacity_cache"]["rect_dp_compiled_line_subsets"] == 0
    assert stats["capacity_cache"]["rect_dp_peak_line_subset_options"] == 0
    assert stats["capacity_cache"]["rect_dp_v3_fallbacks"] == 0
    assert stats["capacity_cache"]["m6x4_mixed_cpsat_evaluations"] == 0
    assert stats["capacity_cache"]["m6x4_mixed_cpsat_cache_hits"] == 0
    assert stats["capacity_cache"]["m6x4_mixed_cpsat_selected_cases"] == 0
    assert stats["capacity_cache"]["m6x4_mixed_cpsat_v3_fallbacks"] == 0
    assert stats["capacity_cache"]["uniform_3x3_cpsat_evaluations"] == 0
    assert stats["capacity_cache"]["uniform_3x3_cpsat_cache_hits"] == 0
    assert stats["capacity_cache"]["uniform_3x3_cpsat_selected_cases"] == 0
    assert stats["capacity_cache"]["uniform_3x3_cpsat_v3_fallbacks"] == 0
    assert stats["capacity_cache"]["bitset_oracle_evaluations"] == 0
    assert stats["capacity_cache"]["bitset_fallbacks"] == 0
    assert stats["capacity_cache"]["cpsat_fallbacks"] == 0
    assert stats["capacity_cache"]["oracle"] == "compact_rect_cpsat_v2"
    assert stats["capacity_cache"]["raw_pole_evaluations"] == 2
    assert stats["capacity_cache"]["signature_misses"] == 1
    assert stats["capacity_cache"]["signature_hits"] == 0
    assert stats["capacity_cache"]["signature_count"] >= 1
    assert precompute["power_capacity_shell_pairs"] == 1
    assert precompute["power_capacity_shell_pair_evaluations"] == 1
    assert precompute["power_capacity_signature_classes"] == 1
    assert precompute["power_capacity_signature_class_evaluations"] == 1
    assert precompute["power_capacity_compact_signature_classes"] == 1
    assert precompute["power_capacity_compact_signature_evaluations"] == 1
    assert precompute["power_capacity_compact_signature_cache_hits"] == 0
    assert precompute["power_capacity_compact_signature_cache_misses"] == 1
    assert precompute["power_capacity_legacy_signature_materializations"] == 0
    assert precompute["power_capacity_supported_by_pole_materializations"] == 0
    assert precompute["power_capacity_compact_rect_cpsat_evaluations"] == 1
    assert precompute["power_capacity_compact_rect_cpsat_cache_hits"] == 0
    assert precompute["power_capacity_compact_rect_cpsat_selected_cases"] == 1
    assert precompute["power_capacity_compact_rect_cpsat_rect_dp_fallbacks"] == 0
    assert precompute["power_capacity_normalized_rect_signature_count"] == 1
    assert precompute["power_capacity_normalized_rect_cache_hits"] == 0
    assert precompute["power_capacity_normalized_rect_cache_misses"] == 1
    assert precompute["power_capacity_rect_dp_evaluations"] == 0
    assert precompute["power_capacity_rect_dp_cache_hits"] == 0
    assert precompute["power_capacity_rect_dp_cache_misses"] == 0
    assert precompute["power_capacity_rect_dp_state_merges"] == 0
    assert precompute["power_capacity_rect_dp_peak_line_states"] == 0
    assert precompute["power_capacity_rect_dp_peak_pos_states"] == 0
    assert precompute["power_capacity_rect_dp_compiled_signatures"] == 0
    assert precompute["power_capacity_rect_dp_compiled_start_options"] == 0
    assert precompute["power_capacity_rect_dp_deduped_start_options"] == 0
    assert precompute["power_capacity_rect_dp_compiled_line_subsets"] == 0
    assert precompute["power_capacity_rect_dp_peak_line_subset_options"] == 0
    assert precompute["power_capacity_rect_dp_v3_fallbacks"] == 0
    assert precompute["power_capacity_m6x4_mixed_cpsat_evaluations"] == 0
    assert precompute["power_capacity_m6x4_mixed_cpsat_cache_hits"] == 0
    assert precompute["power_capacity_m6x4_mixed_cpsat_selected_cases"] == 0
    assert precompute["power_capacity_m6x4_mixed_cpsat_v3_fallbacks"] == 0
    assert precompute["power_capacity_uniform_3x3_cpsat_evaluations"] == 0
    assert precompute["power_capacity_uniform_3x3_cpsat_cache_hits"] == 0
    assert precompute["power_capacity_uniform_3x3_cpsat_selected_cases"] == 0
    assert precompute["power_capacity_uniform_3x3_cpsat_v3_fallbacks"] == 0
    assert precompute["power_capacity_bitset_oracle_evaluations"] == 0
    assert precompute["power_capacity_bitset_fallbacks"] == 0
    assert precompute["power_capacity_cpsat_fallbacks"] == 0
    assert precompute["power_capacity_oracle"] == "compact_rect_cpsat_v2"
    assert precompute["power_capacity_signature_classes"] == stats["capacity_cache"]["signature_class_count"]
    assert precompute["power_capacity_raw_pole_evaluations"] == 2
    assert stats["power_capacity_families"] == {
        "applied": True,
        "family_count": 1,
        "raw_pole_count": 2,
        "coefficient_source": "exact_compact_rect_cpsat_v14",
        "shell_pair_count": 1,
        "compact_signature_class_count": 1,
        "families": [
            {
                "family_id": "family_000",
                "size": 2,
                "count_var_upper_bound": 2,
                "coefficients": {"powered_machine": 2},
            }
        ],
    }
    assert stats["aggregated_power_capacity_terms"] == {
        "applied": True,
        "raw_nonzero_terms": 2,
        "aggregated_nonzero_terms": 1,
    }


def test_power_pole_family_count_uses_candidate_family_upper_bound() -> None:
    model = _build_exact_single_family_upper_bound_model()

    model.build()

    family_stats = model.build_stats["global_valid_inequalities"]["power_capacity_families"]
    optional_bounds = model.build_stats["global_valid_inequalities"]["optional_cardinality_bounds"]
    assert optional_bounds["power_pole"]["slot_pool_upper_bound"] == 2
    assert family_stats["family_count"] == 1
    assert family_stats["families"] == [
        {
            "family_id": "family_000",
            "size": 1,
            "count_var_upper_bound": 1,
            "coefficients": {"powered_machine": 2},
        }
    ]

    family_name = next(iter(model._power_pole_family_count_vars))
    model.model.Add(model._power_pole_family_count_vars[family_name] >= 2)
    assert model.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_ghost_conditioned_family_upper_bound_tightens_power_pole_family_counts() -> None:
    baseline = _build_exact_ghost_conditioned_family_upper_bound_model(ghost_rect=(1, 1))
    baseline.build()

    stats = baseline.build_stats["global_valid_inequalities"]
    ghost_stats = stats["ghost_aware_via_pole_feasibility"]
    family_stats = stats["power_capacity_families"]
    assert ghost_stats["explicit_u_conditioning"] is True
    assert ghost_stats["conditioned_family_upper_bound_constraints"] > 0
    assert ghost_stats["family_reduction_anchor_count"] > 0
    assert family_stats["families"] == [
        {
            "family_id": "family_000",
            "size": 2,
            "count_var_upper_bound": 2,
            "coefficients": {"powered_machine": 2},
        }
    ]

    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(baseline._ghost_domains)
        if domain["anchor"] == {"x": 0, "y": 1}
    )
    baseline.model.Add(baseline.u_vars[forced_anchor_idx] == 1)
    assert baseline.solve(time_limit_seconds=5.0) in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    constrained = _build_exact_ghost_conditioned_family_upper_bound_model(ghost_rect=(1, 1))
    constrained.build()
    family_name = next(iter(constrained._power_pole_family_count_vars))
    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(constrained._ghost_domains)
        if domain["anchor"] == {"x": 0, "y": 1}
    )
    constrained.model.Add(constrained.u_vars[forced_anchor_idx] == 1)
    constrained.model.Add(constrained._power_pole_family_count_vars[family_name] >= 2)
    assert constrained.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_ghost_conditioned_family_upper_bound_formulation_default_is_big_m() -> None:
    model = _build_exact_ghost_conditioned_family_upper_bound_model(ghost_rect=(1, 1))
    model.build()

    stats = model.build_stats["global_valid_inequalities"][
        "ghost_aware_via_pole_feasibility"
    ]
    assert stats["conditioned_family_bound_formulation"] == "big_m"


def test_ghost_via_pole_shape_instrumentation_default_off_is_absent(
    monkeypatch,
) -> None:
    env_var = (
        exact_coordinate_master_module.EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION_ENV
    )
    monkeypatch.delenv(env_var, raising=False)
    baseline = _build_exact_ghost_conditioned_family_upper_bound_model(
        ghost_rect=(1, 1)
    )
    baseline.build()
    baseline_stats = baseline.build_stats["global_valid_inequalities"][
        "ghost_aware_via_pole_feasibility"
    ]
    baseline_stats_snapshot = json.loads(json.dumps(baseline_stats, sort_keys=True))
    baseline_proto_fingerprint = str(baseline.model.Proto())

    assert "shape_instrumentation" not in baseline_stats

    monkeypatch.setenv(env_var, "0")
    disabled = _build_exact_ghost_conditioned_family_upper_bound_model(
        ghost_rect=(1, 1)
    )
    disabled.build()
    disabled_stats = disabled.build_stats["global_valid_inequalities"][
        "ghost_aware_via_pole_feasibility"
    ]

    assert "shape_instrumentation" not in disabled_stats
    assert (
        json.loads(json.dumps(disabled_stats, sort_keys=True))
        == baseline_stats_snapshot
    )
    assert str(disabled.model.Proto()) == baseline_proto_fingerprint


def test_ghost_via_pole_shape_instrumentation_records_diagnostics_without_model_delta(
    monkeypatch,
) -> None:
    env_var = (
        exact_coordinate_master_module.EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION_ENV
    )
    monkeypatch.delenv(env_var, raising=False)
    baseline = _build_exact_ghost_conditioned_family_upper_bound_model(
        ghost_rect=(1, 1)
    )
    baseline.build()
    baseline_proto = baseline.model.Proto()
    baseline_proto_fingerprint = str(baseline_proto)
    baseline_var_count = len(baseline_proto.variables)
    baseline_constraint_count = len(baseline_proto.constraints)
    baseline_constraint_type_counts = _constraint_type_counts(baseline_proto)

    monkeypatch.setenv(env_var, "1")
    instrumented = _build_exact_ghost_conditioned_family_upper_bound_model(
        ghost_rect=(1, 1)
    )
    instrumented.build()
    instrumented_proto = instrumented.model.Proto()
    stats = instrumented.build_stats["global_valid_inequalities"][
        "ghost_aware_via_pole_feasibility"
    ]
    instrumentation = stats["shape_instrumentation"]

    assert str(instrumented_proto) == baseline_proto_fingerprint
    assert len(instrumented_proto.variables) == baseline_var_count
    assert len(instrumented_proto.constraints) == baseline_constraint_count
    assert _constraint_type_counts(instrumented_proto) == baseline_constraint_type_counts
    assert instrumentation["enabled"] is True
    assert set(instrumentation["phase_seconds"]) == {
        "pole_cell_index",
        "per_anchor_blocked_counts",
        "per_anchor_family_reductions",
    }
    assert all(value >= 0.0 for value in instrumentation["phase_seconds"].values())
    assert instrumentation["blocked_pose_indices_histogram"]
    assert instrumentation["blocked_family_count_histogram"]
    assert instrumentation["family_reduction_count_histogram"]
    assert instrumentation["top_family_reduction_anchors"]
    top_anchor = instrumentation["top_family_reduction_anchors"][0]
    assert {
        "rect_idx",
        "anchor",
        "blocked_pose_indices",
        "blocked_family_count",
        "family_reduction_count",
        "family_reductions",
    }.issubset(top_anchor)
    assert top_anchor["family_reduction_count"] > 0


def test_ghost_via_pole_shape_instrumentation_rejects_unknown_value(
    monkeypatch,
) -> None:
    env_var = (
        exact_coordinate_master_module.EXACT_GHOST_VIA_POLE_SHAPE_INSTRUMENTATION_ENV
    )
    monkeypatch.setenv(env_var, "maybe")
    model = _build_exact_ghost_conditioned_family_upper_bound_model(ghost_rect=(1, 1))

    with pytest.raises(ValueError, match=env_var):
        model.build()


def test_ghost_signature_bucket_tightening_instrumentation_default_off_is_absent(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    monkeypatch.delenv(env_var, raising=False)
    baseline = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))
    baseline.build()
    baseline_proto_fingerprint = str(baseline.model.Proto())
    baseline_stats = baseline.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    baseline_stats_snapshot = json.loads(json.dumps(baseline_stats, sort_keys=True))

    assert "signature_tightening_instrumentation" not in baseline_stats

    monkeypatch.setenv(env_var, "0")
    disabled = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))
    disabled.build()
    disabled_stats = disabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]

    assert "signature_tightening_instrumentation" not in disabled_stats
    assert (
        json.loads(json.dumps(disabled_stats, sort_keys=True))
        == baseline_stats_snapshot
    )
    assert str(disabled.model.Proto()) == baseline_proto_fingerprint


def test_ghost_signature_bucket_tightening_instrumentation_records_mandatory_diagnostics_without_model_delta(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    monkeypatch.delenv(env_var, raising=False)
    baseline = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))
    baseline.build()
    baseline_proto = baseline.model.Proto()
    baseline_proto_fingerprint = str(baseline_proto)
    baseline_var_count = len(baseline_proto.variables)
    baseline_constraint_count = len(baseline_proto.constraints)
    baseline_constraint_type_counts = _constraint_type_counts(baseline_proto)

    monkeypatch.setenv(env_var, "1")
    instrumented = _build_exact_mandatory_signature_upper_bound_model(
        ghost_rect=(1, 1)
    )
    instrumented.build()
    instrumented_proto = instrumented.model.Proto()
    stats = instrumented.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    instrumentation = stats["signature_tightening_instrumentation"]

    assert str(instrumented_proto) == baseline_proto_fingerprint
    assert len(instrumented_proto.variables) == baseline_var_count
    assert len(instrumented_proto.constraints) == baseline_constraint_count
    assert _constraint_type_counts(instrumented_proto) == baseline_constraint_type_counts
    assert instrumentation["enabled"] is True
    assert set(instrumentation["phase_seconds"]) == {
        "mandatory_payload_build",
        "required_optional_payload_build",
        "per_anchor_mandatory_scan",
        "per_anchor_required_optional_scan",
        "constraint_add",
        "stats_finalize",
    }
    assert all(value >= 0.0 for value in instrumentation["phase_seconds"].values())
    totals = instrumentation["totals"]
    assert totals["evaluated_placements"] == len(instrumented._ghost_domains)
    assert totals["mandatory_payload_count"] > 0
    assert totals["required_optional_payload_count"] == 0
    assert totals["mandatory_constraints_added"] == stats[
        "ghost_conditioned_mandatory_bucket_constraints"
    ]
    assert totals["constraints_added"] == stats[
        "ghost_conditioned_mandatory_bucket_constraints"
    ]
    assert totals["mandatory_cells_scanned"] > 0
    assert totals["mandatory_pose_hits"] > 0
    assert totals["mandatory_unique_blocked_poses"] > 0
    assert instrumentation["top_slow_entries"]
    top_entry = instrumentation["top_slow_entries"][0]
    assert {
        "kind",
        "rect_idx",
        "anchor",
        "group_id_or_template",
        "bucket_id",
        "scan_count",
        "reduction_count",
        "elapsed_seconds",
    }.issubset(top_entry)
    assert top_entry["kind"] == "mandatory"
    assert top_entry["group_id_or_template"] == "group::router::routing::0"
    assert top_entry["scan_count"] > 0
    assert top_entry["reduction_count"] > 0
    assert top_entry["elapsed_seconds"] >= 0.0


def test_ghost_signature_bucket_tightening_instrumentation_records_required_optional_diagnostics(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    monkeypatch.setenv(env_var, "on")
    model = _build_exact_required_optional_signature_upper_bound_model(
        ghost_rect=(1, 1)
    )
    model.build()

    stats = model.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    instrumentation = stats["signature_tightening_instrumentation"]
    totals = instrumentation["totals"]

    assert totals["mandatory_payload_count"] == 0
    assert totals["required_optional_payload_count"] > 0
    assert totals["required_optional_constraints_added"] == stats[
        "ghost_conditioned_required_optional_bucket_constraints"
    ]
    assert totals["constraints_added"] == stats[
        "ghost_conditioned_required_optional_bucket_constraints"
    ]
    assert totals["required_optional_cells_scanned"] > 0
    assert totals["required_optional_pose_hits"] > 0
    assert totals["required_optional_unique_blocked_poses"] > 0
    assert any(
        entry["kind"] == "required_optional"
        and entry["group_id_or_template"] == "protocol_storage_box"
        for entry in instrumentation["top_slow_entries"]
    )


def test_ghost_signature_bucket_tightening_instrumentation_rejects_unknown_value(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    monkeypatch.setenv(env_var, "maybe")
    model = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))

    with pytest.raises(ValueError, match=env_var):
        model.build()


def test_ghost_signature_bucket_mandatory_region_counting_default_off_and_zero_are_no_delta(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    monkeypatch.delenv(env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    baseline = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))
    baseline.build()
    baseline_proto = baseline.model.Proto()
    baseline_stats = baseline.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    baseline_stats_snapshot = json.loads(json.dumps(baseline_stats, sort_keys=True))

    monkeypatch.setenv(env_var, "0")
    disabled = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))
    disabled.build()
    disabled_proto = disabled.model.Proto()
    disabled_stats = disabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]

    assert "signature_tightening_instrumentation" not in disabled_stats
    assert json.loads(json.dumps(disabled_stats, sort_keys=True)) == baseline_stats_snapshot
    assert str(disabled_proto) == str(baseline_proto)
    assert len(disabled_proto.variables) == len(baseline_proto.variables)
    assert len(disabled_proto.constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(disabled_proto) == _constraint_type_counts(
        baseline_proto
    )


def test_ghost_signature_bucket_mandatory_region_fallback_instrumentation_default_off_is_absent(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.delenv(fallback_env_var, raising=False)
    baseline = _build_exact_mandatory_signature_noncompact_footprint_model(
        ghost_rect=(1, 1)
    )
    baseline.build()
    baseline_proto = baseline.model.Proto()

    for disabled_value in ("0", "false"):
        monkeypatch.setenv(fallback_env_var, disabled_value)
        disabled = _build_exact_mandatory_signature_noncompact_footprint_model(
            ghost_rect=(1, 1)
        )
        disabled.build()
        disabled_proto = disabled.model.Proto()
        stats = disabled.build_stats["global_valid_inequalities"][
            "signature_bucket_capacity_bounds"
        ]
        instrumentation = stats["signature_tightening_instrumentation"]

        assert "fallback_reasons" not in instrumentation
        assert "top_fallback_entries" not in instrumentation
        assert str(disabled_proto) == str(baseline_proto)
        assert len(disabled_proto.variables) == len(baseline_proto.variables)
        assert len(disabled_proto.constraints) == len(baseline_proto.constraints)
        assert _constraint_type_counts(disabled_proto) == _constraint_type_counts(
            baseline_proto
        )

    monkeypatch.delenv(fallback_env_var, raising=False)
    assert "fallback_reasons" not in baseline.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]["signature_tightening_instrumentation"]


def test_ghost_signature_bucket_mandatory_region_counting_enabled_matches_legacy_supported_fixture(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    monkeypatch.delenv(env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    baseline = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))
    baseline.build()
    baseline_proto = baseline.model.Proto()
    baseline_stats = baseline.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    baseline_stats_snapshot = json.loads(json.dumps(baseline_stats, sort_keys=True))

    monkeypatch.setenv(env_var, "1")
    fast = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))
    fast.build()
    fast_proto = fast.model.Proto()
    fast_stats = fast.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]

    assert json.loads(json.dumps(fast_stats, sort_keys=True)) == baseline_stats_snapshot
    assert str(fast_proto) == str(baseline_proto)
    assert len(fast_proto.variables) == len(baseline_proto.variables)
    assert len(fast_proto.constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(fast_proto) == _constraint_type_counts(baseline_proto)


def test_ghost_signature_bucket_mandatory_region_fallback_instrumentation_supported_fixture_has_empty_output(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    monkeypatch.delenv(region_env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    monkeypatch.delenv(fallback_env_var, raising=False)
    legacy = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))
    legacy.build()
    legacy_proto = legacy.model.Proto()

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(fallback_env_var, "1")
    enabled = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))
    enabled.build()
    enabled_proto = enabled.model.Proto()
    stats = enabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    instrumentation = stats["signature_tightening_instrumentation"]

    assert str(enabled_proto) == str(legacy_proto)
    assert len(enabled_proto.variables) == len(legacy_proto.variables)
    assert len(enabled_proto.constraints) == len(legacy_proto.constraints)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        legacy_proto
    )
    assert instrumentation["fallback_reasons"] == {}
    assert instrumentation["top_fallback_entries"] == []
    assert instrumentation["totals"]["mandatory_region_counting_attempts"] > 0
    assert instrumentation["totals"]["mandatory_region_counting_fallbacks"] == 0


def test_ghost_signature_bucket_mandatory_region_counting_counts_pose_footprint_overlap(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    monkeypatch.delenv(region_env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    legacy = _build_exact_mandatory_signature_multicell_region_model(ghost_rect=(1, 1))
    legacy.build()
    legacy_proto = legacy.model.Proto()

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    fast = _build_exact_mandatory_signature_multicell_region_model(ghost_rect=(1, 1))
    fast.build()
    fast_proto = fast.model.Proto()
    stats = fast.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    instrumentation = stats["signature_tightening_instrumentation"]
    totals = instrumentation["totals"]

    assert str(fast_proto) == str(legacy_proto)
    assert len(fast_proto.variables) == len(legacy_proto.variables)
    assert len(fast_proto.constraints) == len(legacy_proto.constraints)
    assert _constraint_type_counts(fast_proto) == _constraint_type_counts(legacy_proto)
    assert totals["mandatory_region_counting_attempts"] > 0
    assert totals["mandatory_region_counting_used"] > 0
    assert totals["mandatory_region_counting_fallbacks"] == 0
    assert totals["mandatory_region_rectangles_evaluated"] > 0
    assert totals["mandatory_region_counted_blocked_poses"] > 0
    assert totals["mandatory_cells_scanned"] == 0


def test_ghost_signature_bucket_mandatory_region_counting_falls_back_for_unsupported_footprints(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    monkeypatch.delenv(region_env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    monkeypatch.delenv(fallback_env_var, raising=False)
    legacy = _build_exact_mandatory_signature_noncompact_footprint_model(
        ghost_rect=(1, 1)
    )
    legacy.build()
    legacy_proto = legacy.model.Proto()

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(fallback_env_var, "1")
    fallback = _build_exact_mandatory_signature_noncompact_footprint_model(
        ghost_rect=(1, 1)
    )
    fallback.build()
    fallback_proto = fallback.model.Proto()
    stats = fallback.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    instrumentation = stats["signature_tightening_instrumentation"]
    totals = instrumentation["totals"]

    assert str(fallback_proto) == str(legacy_proto)
    assert len(fallback_proto.variables) == len(legacy_proto.variables)
    assert len(fallback_proto.constraints) == len(legacy_proto.constraints)
    assert _constraint_type_counts(fallback_proto) == _constraint_type_counts(
        legacy_proto
    )
    assert totals["mandatory_region_counting_attempts"] > 0
    assert totals["mandatory_region_counting_used"] == 0
    assert totals["mandatory_region_counting_fallbacks"] > 0
    assert totals["mandatory_cells_scanned"] > 0
    assert totals["mandatory_pose_hits"] > 0
    assert (
        instrumentation["fallback_reasons"][
            "unsupported_or_missing_template_footprint"
        ]
        == totals["mandatory_region_counting_fallbacks"]
    )
    assert 0 < len(instrumentation["top_fallback_entries"]) <= 10
    top_entry = instrumentation["top_fallback_entries"][0]
    assert {
        "rect_idx",
        "anchor",
        "group_id_or_template",
        "bucket_id",
        "reason",
        "legacy_scan_count",
        "legacy_pose_hits",
        "elapsed_seconds",
    }.issubset(top_entry)
    assert top_entry["bucket_id"] == "__all__"
    assert top_entry["reason"] == "unsupported_or_missing_template_footprint"
    assert top_entry["legacy_scan_count"] > 0
    assert top_entry["legacy_pose_hits"] > 0
    assert top_entry["elapsed_seconds"] >= 0.0


def test_ghost_signature_bucket_template_footprint_support_default_off_and_zero_are_no_delta(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    monkeypatch.delenv(env_var, raising=False)
    monkeypatch.delenv(region_env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    baseline = _build_exact_mandatory_signature_noncompact_footprint_model(
        ghost_rect=(1, 1)
    )
    baseline.build()
    baseline_proto = baseline.model.Proto()
    baseline_stats = baseline.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    baseline_stats_snapshot = json.loads(json.dumps(baseline_stats, sort_keys=True))

    for disabled_value in ("0", "false"):
        monkeypatch.setenv(env_var, disabled_value)
        disabled = _build_exact_mandatory_signature_noncompact_footprint_model(
            ghost_rect=(1, 1)
        )
        disabled.build()
        disabled_proto = disabled.model.Proto()
        disabled_stats = disabled.build_stats["global_valid_inequalities"][
            "signature_bucket_capacity_bounds"
        ]

        assert "signature_tightening_instrumentation" not in disabled_stats
        assert (
            json.loads(json.dumps(disabled_stats, sort_keys=True))
            == baseline_stats_snapshot
        )
        assert str(disabled_proto) == str(baseline_proto)
        assert len(disabled_proto.variables) == len(baseline_proto.variables)
        assert len(disabled_proto.constraints) == len(baseline_proto.constraints)
        assert _constraint_type_counts(disabled_proto) == _constraint_type_counts(
            baseline_proto
        )


def test_ghost_signature_bucket_template_footprint_support_rejects_unknown_value(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    monkeypatch.setenv(env_var, "maybe")
    model = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))

    with pytest.raises(ValueError, match=env_var):
        model.build()


def test_ghost_signature_bucket_template_footprint_support_enables_rectangular_pose_footprints(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    template_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    monkeypatch.delenv(region_env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    monkeypatch.delenv(fallback_env_var, raising=False)
    monkeypatch.delenv(template_env_var, raising=False)
    legacy = _build_exact_mandatory_signature_noncompact_footprint_model(
        ghost_rect=(1, 1)
    )
    legacy.build()
    legacy_proto = legacy.model.Proto()

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(fallback_env_var, "1")
    monkeypatch.setenv(template_env_var, "1")
    enabled = _build_exact_mandatory_signature_noncompact_footprint_model(
        ghost_rect=(1, 1)
    )
    enabled.build()
    enabled_proto = enabled.model.Proto()
    stats = enabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    instrumentation = stats["signature_tightening_instrumentation"]
    totals = instrumentation["totals"]

    assert str(enabled_proto) == str(legacy_proto)
    assert len(enabled_proto.variables) == len(legacy_proto.variables)
    assert len(enabled_proto.constraints) == len(legacy_proto.constraints)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        legacy_proto
    )
    assert totals["mandatory_region_counting_attempts"] > 0
    assert totals["mandatory_region_counting_used"] > 0
    assert totals["mandatory_region_counting_fallbacks"] == 0
    assert totals["mandatory_template_footprint_support_attempts"] > 0
    assert totals["mandatory_template_footprint_support_used"] > 0
    assert totals["mandatory_template_footprint_support_fallbacks"] == 0
    assert totals["mandatory_cells_scanned"] == 0
    assert instrumentation["fallback_reasons"] == {}
    assert instrumentation["top_fallback_entries"] == []


def test_ghost_signature_bucket_template_footprint_support_falls_back_for_l_shape_footprints(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    template_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    monkeypatch.delenv(region_env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    monkeypatch.delenv(fallback_env_var, raising=False)
    monkeypatch.delenv(template_env_var, raising=False)
    legacy = _build_exact_mandatory_signature_l_shape_footprint_model(
        ghost_rect=(1, 1)
    )
    legacy.build()
    legacy_proto = legacy.model.Proto()

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(fallback_env_var, "1")
    monkeypatch.setenv(template_env_var, "1")
    fallback = _build_exact_mandatory_signature_l_shape_footprint_model(
        ghost_rect=(1, 1)
    )
    fallback.build()
    fallback_proto = fallback.model.Proto()
    stats = fallback.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    instrumentation = stats["signature_tightening_instrumentation"]
    totals = instrumentation["totals"]

    assert str(fallback_proto) == str(legacy_proto)
    assert len(fallback_proto.variables) == len(legacy_proto.variables)
    assert len(fallback_proto.constraints) == len(legacy_proto.constraints)
    assert _constraint_type_counts(fallback_proto) == _constraint_type_counts(
        legacy_proto
    )
    assert totals["mandatory_region_counting_attempts"] > 0
    assert totals["mandatory_region_counting_used"] == 0
    assert totals["mandatory_region_counting_fallbacks"] > 0
    assert totals["mandatory_template_footprint_support_attempts"] > 0
    assert totals["mandatory_template_footprint_support_used"] == 0
    assert (
        totals["mandatory_template_footprint_support_fallbacks"]
        == totals["mandatory_region_counting_fallbacks"]
    )
    assert totals["mandatory_cells_scanned"] > 0
    assert (
        instrumentation["fallback_reasons"][
            "unsupported_or_missing_template_footprint"
        ]
        == totals["mandatory_region_counting_fallbacks"]
    )
    assert 0 < len(instrumentation["top_fallback_entries"]) <= 10


def test_ghost_signature_bucket_template_footprint_support_gap_instrumentation_default_off_is_absent(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    template_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    gap_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_ENV

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(fallback_env_var, "1")
    monkeypatch.setenv(template_env_var, "1")
    monkeypatch.delenv(gap_env_var, raising=False)
    baseline = _build_exact_mandatory_signature_l_shape_footprint_model(
        ghost_rect=(1, 1)
    )
    baseline.build()
    baseline_proto = baseline.model.Proto()
    baseline_instrumentation = baseline.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]["signature_tightening_instrumentation"]
    assert "template_footprint_support_gap_reasons" not in baseline_instrumentation
    assert "top_template_footprint_gap_entries" not in baseline_instrumentation

    for disabled_value in ("0", "false"):
        monkeypatch.setenv(gap_env_var, disabled_value)
        disabled = _build_exact_mandatory_signature_l_shape_footprint_model(
            ghost_rect=(1, 1)
        )
        disabled.build()
        disabled_proto = disabled.model.Proto()
        instrumentation = disabled.build_stats["global_valid_inequalities"][
            "signature_bucket_capacity_bounds"
        ]["signature_tightening_instrumentation"]

        assert "template_footprint_support_gap_reasons" not in instrumentation
        assert "top_template_footprint_gap_entries" not in instrumentation
        assert str(disabled_proto) == str(baseline_proto)
        assert len(disabled_proto.variables) == len(baseline_proto.variables)
        assert len(disabled_proto.constraints) == len(baseline_proto.constraints)
        assert _constraint_type_counts(disabled_proto) == _constraint_type_counts(
            baseline_proto
        )


def test_ghost_signature_bucket_template_footprint_support_gap_instrumentation_rejects_unknown_value(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_ENV
    monkeypatch.setenv(env_var, "maybe")
    model = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))

    with pytest.raises(ValueError, match=env_var):
        model.build()


def test_ghost_signature_bucket_template_footprint_support_gap_instrumentation_records_l_shape_rejection(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    template_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    gap_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_ENV

    monkeypatch.delenv(region_env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    monkeypatch.delenv(fallback_env_var, raising=False)
    monkeypatch.delenv(template_env_var, raising=False)
    monkeypatch.delenv(gap_env_var, raising=False)
    legacy = _build_exact_mandatory_signature_l_shape_footprint_model(
        ghost_rect=(1, 1)
    )
    legacy.build()
    legacy_proto = legacy.model.Proto()

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(fallback_env_var, "1")
    monkeypatch.setenv(template_env_var, "1")
    monkeypatch.setenv(gap_env_var, "1")
    enabled = _build_exact_mandatory_signature_l_shape_footprint_model(
        ghost_rect=(1, 1)
    )
    enabled.build()
    enabled_proto = enabled.model.Proto()
    instrumentation = enabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]["signature_tightening_instrumentation"]
    totals = instrumentation["totals"]

    assert str(enabled_proto) == str(legacy_proto)
    assert len(enabled_proto.variables) == len(legacy_proto.variables)
    assert len(enabled_proto.constraints) == len(legacy_proto.constraints)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        legacy_proto
    )
    assert (
        instrumentation["template_footprint_support_gap_reasons"][
            "non_rectangular_occupied_cells"
        ]
        == totals["mandatory_region_counting_fallbacks"]
    )
    assert 0 < len(instrumentation["top_template_footprint_gap_entries"]) <= 10
    top_entry = instrumentation["top_template_footprint_gap_entries"][0]
    assert {
        "rect_idx",
        "anchor",
        "group_id_or_template",
        "bucket_id",
        "reason",
        "pose_count",
        "occupied_cell_count",
        "footprint_bounds_when_available",
        "elapsed_seconds",
    }.issubset(top_entry)
    assert top_entry["reason"] == "non_rectangular_occupied_cells"
    assert top_entry["pose_count"] > 0
    assert top_entry["occupied_cell_count"] > 0
    assert top_entry["footprint_bounds_when_available"] is not None


def test_ghost_signature_bucket_template_footprint_support_gap_instrumentation_supported_fixture_has_empty_output(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    template_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    gap_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_ENV

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(fallback_env_var, "1")
    monkeypatch.setenv(template_env_var, "1")
    monkeypatch.setenv(gap_env_var, "1")
    enabled = _build_exact_mandatory_signature_noncompact_footprint_model(
        ghost_rect=(1, 1)
    )
    enabled.build()
    instrumentation = enabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]["signature_tightening_instrumentation"]

    assert instrumentation["totals"]["mandatory_region_counting_used"] > 0
    assert instrumentation["totals"]["mandatory_region_counting_fallbacks"] == 0
    assert instrumentation["template_footprint_support_gap_reasons"] == {}
    assert instrumentation["top_template_footprint_gap_entries"] == []


def test_ghost_signature_bucket_payload_footprint_stability_default_off_and_zero_are_no_delta(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    template_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    gap_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_ENV
    stability_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT_ENV

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(fallback_env_var, "1")
    monkeypatch.setenv(template_env_var, "1")
    monkeypatch.setenv(gap_env_var, "1")
    monkeypatch.delenv(stability_env_var, raising=False)
    baseline = _build_exact_mandatory_signature_unstable_rectangular_footprint_model(
        ghost_rect=(1, 1)
    )
    baseline.build()
    baseline_proto = baseline.model.Proto()
    baseline_stats = baseline.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    baseline_static_stats = {
        key: value
        for key, value in baseline_stats.items()
        if key != "signature_tightening_instrumentation"
    }
    baseline_instrumentation = baseline_stats["signature_tightening_instrumentation"]
    assert "top_payload_footprint_stability_entries" not in baseline_instrumentation
    assert not any(
        key.startswith("mandatory_payload_footprint_stability")
        for key in baseline_instrumentation["totals"]
    )
    assert (
        baseline_instrumentation["template_footprint_support_gap_reasons"][
            "unstable_footprint_bounds_within_payload"
        ]
        == baseline_instrumentation["totals"]["mandatory_region_counting_fallbacks"]
    )

    for disabled_value in ("0", "false"):
        monkeypatch.setenv(stability_env_var, disabled_value)
        disabled = _build_exact_mandatory_signature_unstable_rectangular_footprint_model(
            ghost_rect=(1, 1)
        )
        disabled.build()
        disabled_proto = disabled.model.Proto()
        disabled_stats = disabled.build_stats["global_valid_inequalities"][
            "signature_bucket_capacity_bounds"
        ]
        disabled_static_stats = {
            key: value
            for key, value in disabled_stats.items()
            if key != "signature_tightening_instrumentation"
        }
        disabled_instrumentation = disabled_stats["signature_tightening_instrumentation"]

        assert disabled_static_stats == baseline_static_stats
        assert "top_payload_footprint_stability_entries" not in disabled_instrumentation
        assert not any(
            key.startswith("mandatory_payload_footprint_stability")
            for key in disabled_instrumentation["totals"]
        )
        assert (
            disabled_instrumentation["template_footprint_support_gap_reasons"]
            == baseline_instrumentation["template_footprint_support_gap_reasons"]
        )
        assert str(disabled_proto) == str(baseline_proto)
        assert len(disabled_proto.variables) == len(baseline_proto.variables)
        assert len(disabled_proto.constraints) == len(baseline_proto.constraints)
        assert _constraint_type_counts(disabled_proto) == _constraint_type_counts(
            baseline_proto
        )


def test_ghost_signature_bucket_payload_footprint_stability_rejects_unknown_value(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT_ENV
    monkeypatch.setenv(env_var, "maybe")
    model = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))

    with pytest.raises(ValueError, match=env_var):
        model.build()


def test_ghost_signature_bucket_payload_footprint_stability_cohorts_rectangular_bounds(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    template_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    gap_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_ENV
    stability_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT_ENV

    monkeypatch.delenv(region_env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    monkeypatch.delenv(fallback_env_var, raising=False)
    monkeypatch.delenv(template_env_var, raising=False)
    monkeypatch.delenv(gap_env_var, raising=False)
    monkeypatch.delenv(stability_env_var, raising=False)
    legacy = _build_exact_mandatory_signature_unstable_rectangular_footprint_model(
        ghost_rect=(1, 1)
    )
    legacy.build()
    legacy_proto = legacy.model.Proto()

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(fallback_env_var, "1")
    monkeypatch.setenv(template_env_var, "1")
    monkeypatch.setenv(gap_env_var, "1")
    monkeypatch.setenv(stability_env_var, "1")
    enabled = _build_exact_mandatory_signature_unstable_rectangular_footprint_model(
        ghost_rect=(1, 1)
    )
    enabled.build()
    enabled_proto = enabled.model.Proto()
    instrumentation = enabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]["signature_tightening_instrumentation"]
    totals = instrumentation["totals"]

    assert str(enabled_proto) == str(legacy_proto)
    assert len(enabled_proto.variables) == len(legacy_proto.variables)
    assert len(enabled_proto.constraints) == len(legacy_proto.constraints)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        legacy_proto
    )
    assert totals["mandatory_region_counting_attempts"] > 0
    assert totals["mandatory_region_counting_used"] > 0
    assert totals["mandatory_region_counting_fallbacks"] == 0
    assert totals["mandatory_template_footprint_support_used"] > 0
    assert totals["mandatory_payload_footprint_stability_attempts"] > 0
    assert totals["mandatory_payload_footprint_stability_used"] > 0
    assert totals["mandatory_payload_footprint_stability_fallbacks"] == 0
    assert totals["mandatory_payload_footprint_stability_cohorts"] >= (
        2 * totals["mandatory_payload_footprint_stability_used"]
    )
    assert totals["mandatory_cells_scanned"] == 0
    assert instrumentation["fallback_reasons"] == {}
    assert instrumentation["top_fallback_entries"] == []
    assert instrumentation["template_footprint_support_gap_reasons"] == {}
    assert 0 < len(instrumentation["top_payload_footprint_stability_entries"]) <= 10
    top_entry = instrumentation["top_payload_footprint_stability_entries"][0]
    assert {
        "rect_idx",
        "anchor",
        "group_id_or_template",
        "cohort_count",
        "rectangles_evaluated",
        "counted_blocked_poses",
        "elapsed_seconds",
    }.issubset(top_entry)
    assert top_entry["cohort_count"] >= 2
    assert top_entry["rectangles_evaluated"] >= 2


def test_ghost_signature_bucket_payload_footprint_stability_keeps_l_shape_fallback(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    template_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    gap_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_ENV
    stability_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT_ENV
    monkeypatch.delenv(region_env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    monkeypatch.delenv(fallback_env_var, raising=False)
    monkeypatch.delenv(template_env_var, raising=False)
    monkeypatch.delenv(gap_env_var, raising=False)
    monkeypatch.delenv(stability_env_var, raising=False)
    legacy = _build_exact_mandatory_signature_l_shape_footprint_model(
        ghost_rect=(1, 1)
    )
    legacy.build()
    legacy_proto = legacy.model.Proto()

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(fallback_env_var, "1")
    monkeypatch.setenv(template_env_var, "1")
    monkeypatch.setenv(gap_env_var, "1")
    monkeypatch.setenv(stability_env_var, "1")
    fallback = _build_exact_mandatory_signature_l_shape_footprint_model(
        ghost_rect=(1, 1)
    )
    fallback.build()
    fallback_proto = fallback.model.Proto()
    instrumentation = fallback.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]["signature_tightening_instrumentation"]
    totals = instrumentation["totals"]

    assert str(fallback_proto) == str(legacy_proto)
    assert len(fallback_proto.variables) == len(legacy_proto.variables)
    assert len(fallback_proto.constraints) == len(legacy_proto.constraints)
    assert _constraint_type_counts(fallback_proto) == _constraint_type_counts(
        legacy_proto
    )
    assert totals["mandatory_region_counting_used"] == 0
    assert totals["mandatory_region_counting_fallbacks"] > 0
    assert totals["mandatory_payload_footprint_stability_used"] == 0
    assert totals["mandatory_payload_footprint_stability_fallbacks"] > 0
    assert (
        instrumentation["template_footprint_support_gap_reasons"][
            "non_rectangular_occupied_cells"
        ]
        == totals["mandatory_region_counting_fallbacks"]
    )


def test_ghost_signature_bucket_mandatory_region_counting_does_not_change_required_optional_path(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    template_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    stability_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT_ENV
    monkeypatch.delenv(env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    monkeypatch.delenv(template_env_var, raising=False)
    monkeypatch.delenv(stability_env_var, raising=False)
    baseline = _build_exact_required_optional_signature_upper_bound_model(
        ghost_rect=(1, 1)
    )
    baseline.build()
    baseline_proto = baseline.model.Proto()
    baseline_stats = baseline.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    baseline_stats_snapshot = json.loads(json.dumps(baseline_stats, sort_keys=True))

    monkeypatch.setenv(env_var, "1")
    monkeypatch.setenv(template_env_var, "1")
    monkeypatch.setenv(stability_env_var, "1")
    enabled = _build_exact_required_optional_signature_upper_bound_model(
        ghost_rect=(1, 1)
    )
    enabled.build()
    enabled_proto = enabled.model.Proto()
    enabled_stats = enabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]

    assert json.loads(json.dumps(enabled_stats, sort_keys=True)) == baseline_stats_snapshot
    assert str(enabled_proto) == str(baseline_proto)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        baseline_proto
    )


def test_ghost_signature_bucket_mandatory_region_counting_rejects_unknown_value(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    monkeypatch.setenv(env_var, "maybe")
    model = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))

    with pytest.raises(ValueError, match=env_var):
        model.build()


def test_ghost_signature_bucket_mandatory_region_fallback_instrumentation_rejects_unknown_value(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    monkeypatch.setenv(env_var, "maybe")
    model = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))

    with pytest.raises(ValueError, match=env_var):
        model.build()


def test_exact_core_overlay_signature_bucket_mandatory_region_counting_matches_legacy(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    base_model = _build_exact_mandatory_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    monkeypatch.delenv(env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()
    baseline_stats = baseline.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    baseline_stats_snapshot = json.loads(json.dumps(baseline_stats, sort_keys=True))

    monkeypatch.setenv(env_var, "1")
    enabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    enabled_proto = enabled.model.Proto()
    enabled_stats = enabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]

    assert json.loads(json.dumps(enabled_stats, sort_keys=True)) == baseline_stats_snapshot
    assert str(enabled_proto) == str(baseline_proto)
    assert len(enabled_proto.variables) == len(baseline_proto.variables)
    assert len(enabled_proto.constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        baseline_proto
    )


def test_exact_core_overlay_signature_bucket_mandatory_region_fallback_instrumentation_matches_legacy(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    base_model = _build_exact_mandatory_signature_noncompact_footprint_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    monkeypatch.delenv(region_env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    monkeypatch.delenv(fallback_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(fallback_env_var, "1")
    enabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    enabled_proto = enabled.model.Proto()
    enabled_stats = enabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    instrumentation = enabled_stats["signature_tightening_instrumentation"]

    assert str(enabled_proto) == str(baseline_proto)
    assert len(enabled_proto.variables) == len(baseline_proto.variables)
    assert len(enabled_proto.constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        baseline_proto
    )
    assert instrumentation["fallback_reasons"][
        "unsupported_or_missing_template_footprint"
    ] == instrumentation["totals"]["mandatory_region_counting_fallbacks"]
    assert 0 < len(instrumentation["top_fallback_entries"]) <= 10


def test_exact_core_overlay_signature_bucket_template_footprint_support_matches_legacy(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    template_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    base_model = _build_exact_mandatory_signature_noncompact_footprint_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    monkeypatch.delenv(region_env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    monkeypatch.delenv(fallback_env_var, raising=False)
    monkeypatch.delenv(template_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(fallback_env_var, "1")
    monkeypatch.setenv(template_env_var, "1")
    enabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    enabled_proto = enabled.model.Proto()
    enabled_stats = enabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    instrumentation = enabled_stats["signature_tightening_instrumentation"]
    totals = instrumentation["totals"]

    assert str(enabled_proto) == str(baseline_proto)
    assert len(enabled_proto.variables) == len(baseline_proto.variables)
    assert len(enabled_proto.constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        baseline_proto
    )
    assert totals["mandatory_region_counting_attempts"] > 0
    assert totals["mandatory_region_counting_used"] > 0
    assert totals["mandatory_region_counting_fallbacks"] == 0
    assert totals["mandatory_template_footprint_support_used"] > 0
    assert instrumentation["fallback_reasons"] == {}
    assert instrumentation["top_fallback_entries"] == []


def test_exact_core_overlay_signature_bucket_template_footprint_support_gap_instrumentation_matches_legacy(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    template_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    gap_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_ENV
    base_model = _build_exact_mandatory_signature_l_shape_footprint_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    monkeypatch.delenv(region_env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    monkeypatch.delenv(fallback_env_var, raising=False)
    monkeypatch.delenv(template_env_var, raising=False)
    monkeypatch.delenv(gap_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(fallback_env_var, "1")
    monkeypatch.setenv(template_env_var, "1")
    monkeypatch.setenv(gap_env_var, "1")
    enabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    enabled_proto = enabled.model.Proto()
    instrumentation = enabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]["signature_tightening_instrumentation"]

    assert str(enabled_proto) == str(baseline_proto)
    assert len(enabled_proto.variables) == len(baseline_proto.variables)
    assert len(enabled_proto.constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        baseline_proto
    )
    assert (
        instrumentation["template_footprint_support_gap_reasons"][
            "non_rectangular_occupied_cells"
        ]
        == instrumentation["totals"]["mandatory_region_counting_fallbacks"]
    )
    assert 0 < len(instrumentation["top_template_footprint_gap_entries"]) <= 10


def test_exact_core_overlay_signature_bucket_payload_footprint_stability_matches_legacy(
    monkeypatch,
) -> None:
    region_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_COUNTING_ENV
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    fallback_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_MANDATORY_REGION_FALLBACK_INSTRUMENTATION_ENV
    template_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_ENV
    gap_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TEMPLATE_FOOTPRINT_SUPPORT_GAP_INSTRUMENTATION_ENV
    stability_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_PAYLOAD_FOOTPRINT_STABILITY_SUPPORT_ENV
    base_model = _build_exact_mandatory_signature_unstable_rectangular_footprint_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    monkeypatch.delenv(region_env_var, raising=False)
    monkeypatch.delenv(inst_env_var, raising=False)
    monkeypatch.delenv(fallback_env_var, raising=False)
    monkeypatch.delenv(template_env_var, raising=False)
    monkeypatch.delenv(gap_env_var, raising=False)
    monkeypatch.delenv(stability_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()

    monkeypatch.setenv(region_env_var, "1")
    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(fallback_env_var, "1")
    monkeypatch.setenv(template_env_var, "1")
    monkeypatch.setenv(gap_env_var, "1")
    monkeypatch.setenv(stability_env_var, "1")
    enabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    enabled_proto = enabled.model.Proto()
    instrumentation = enabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]["signature_tightening_instrumentation"]
    totals = instrumentation["totals"]

    assert str(enabled_proto) == str(baseline_proto)
    assert len(enabled_proto.variables) == len(baseline_proto.variables)
    assert len(enabled_proto.constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        baseline_proto
    )
    assert totals["mandatory_region_counting_used"] > 0
    assert totals["mandatory_region_counting_fallbacks"] == 0
    assert totals["mandatory_payload_footprint_stability_used"] > 0
    assert instrumentation["template_footprint_support_gap_reasons"] == {}
    assert instrumentation["top_payload_footprint_stability_entries"]


def test_ghost_conditioned_family_upper_bound_enforced_formulation_is_equivalent(
    monkeypatch,
) -> None:
    monkeypatch.setenv("EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION", "enforced")
    model = _build_exact_ghost_conditioned_family_upper_bound_model(ghost_rect=(1, 1))
    model.build()

    stats = model.build_stats["global_valid_inequalities"][
        "ghost_aware_via_pole_feasibility"
    ]
    assert stats["conditioned_family_bound_formulation"] == "enforced"
    assert stats["conditioned_family_upper_bound_constraints"] > 0

    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(model._ghost_domains)
        if domain["anchor"] == {"x": 0, "y": 1}
    )
    model.model.Add(model.u_vars[forced_anchor_idx] == 1)
    assert model.solve(time_limit_seconds=5.0) in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    constrained = _build_exact_ghost_conditioned_family_upper_bound_model(ghost_rect=(1, 1))
    constrained.build()
    family_name = next(iter(constrained._power_pole_family_count_vars))
    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(constrained._ghost_domains)
        if domain["anchor"] == {"x": 0, "y": 1}
    )
    constrained.model.Add(constrained.u_vars[forced_anchor_idx] == 1)
    constrained.model.Add(constrained._power_pole_family_count_vars[family_name] >= 2)
    assert constrained.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_ghost_conditioned_family_upper_bound_rejects_unknown_formulation(
    monkeypatch,
) -> None:
    monkeypatch.setenv("EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION", "bad")
    model = _build_exact_ghost_conditioned_family_upper_bound_model(ghost_rect=(1, 1))

    with pytest.raises(ValueError, match="EXACT_GHOST_CONDITIONED_FAMILY_BOUND_FORMULATION"):
        model.build()


def test_mandatory_signature_bucket_count_uses_concrete_bucket_upper_bound() -> None:
    model = _build_exact_mandatory_signature_upper_bound_model()

    model.build()

    signature_stats = model.build_stats["global_valid_inequalities"]["signature_bucket_capacity_bounds"]
    assert signature_stats["mandatory_bucket_upper_bound_constraints"] == 1
    group_payload = next(
        payload
        for payload in signature_stats["mandatory_groups"]
        if payload["group_id"] == "group::router::routing::0"
    )
    assert sorted(
        (bucket["bucket_pose_count"], bucket["count_var_upper_bound"])
        for bucket in group_payload["buckets"]
    ) == [
        (1, 1),
        (2, 2),
    ]

    constrained_bucket_id = next(
        bucket["bucket_id"]
        for bucket in group_payload["buckets"]
        if bucket["count_var_upper_bound"] == 1
    )
    model.model.Add(
        model._mandatory_signature_count_vars["group::router::routing::0"][constrained_bucket_id]
        >= 2
    )
    assert model.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_required_optional_signature_bucket_count_uses_concrete_bucket_upper_bound() -> None:
    model = _build_exact_required_optional_signature_upper_bound_model()

    model.build()

    assert model.build_stats["exact_required_optionals"] == {"protocol_storage_box": 2}
    signature_stats = model.build_stats["global_valid_inequalities"]["signature_bucket_capacity_bounds"]
    assert signature_stats["required_optional_bucket_upper_bound_constraints"] == 1
    template_payload = next(
        payload
        for payload in signature_stats["required_optionals"]
        if payload["template"] == "protocol_storage_box"
    )
    assert sorted(
        (bucket["bucket_pose_count"], bucket["count_var_upper_bound"])
        for bucket in template_payload["buckets"]
    ) == [
        (1, 1),
        (2, 2),
    ]

    constrained_bucket_id = next(
        bucket["bucket_id"]
        for bucket in template_payload["buckets"]
        if bucket["count_var_upper_bound"] == 1
    )
    model.model.Add(
        model._required_optional_signature_count_vars["protocol_storage_box"][constrained_bucket_id]
        >= 2
    )
    assert model.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_coordinate_symmetry_breaking_orders_mandatory_signature_slots() -> None:
    model = _build_exact_mandatory_signature_upper_bound_model()
    model.build()

    symmetry_stats = model.build_stats["coordinate_symmetry"]
    assert symmetry_stats["enabled"] is True
    assert symmetry_stats["mandatory_signature_monotonic_constraints"] > 0

    delegate = model._coordinate_delegate
    assert delegate is not None
    slots = delegate.mandatory_slots["group::router::routing::0"]
    assert len(slots) >= 2
    assert slots[0].signature is not None
    assert slots[1].signature is not None

    reverse_model = _build_exact_mandatory_signature_upper_bound_model()
    reverse_model.build()
    reverse_slots = reverse_model._coordinate_delegate.mandatory_slots[
        "group::router::routing::0"
    ]
    reverse_model.model.Add(reverse_slots[0].signature > reverse_slots[1].signature)
    assert reverse_model.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE

    canonical_model = _build_exact_mandatory_signature_upper_bound_model()
    canonical_model.build()
    canonical_slots = canonical_model._coordinate_delegate.mandatory_slots[
        "group::router::routing::0"
    ]
    canonical_model.model.Add(canonical_slots[0].signature <= canonical_slots[1].signature)
    assert canonical_model.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )


def test_coordinate_symmetry_breaking_skips_incompatible_signature_order_slots() -> None:
    model = _build_exact_incompatible_signature_order_model()

    status = model.solve(time_limit_seconds=5.0)

    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    symmetry_stats = model.build_stats["coordinate_symmetry"]
    assert symmetry_stats["enabled"] is True
    assert symmetry_stats["mandatory_signature_monotonic_constraints"] == 0
    assert symmetry_stats[
        "mandatory_signature_monotonic_skipped_incompatible_order"
    ] == 1
    assert {
        placement["pose_idx"] for placement in model.extract_solution().values()
    } == {0, 1}


def test_coordinate_symmetry_breaking_orders_required_optional_signature_slots() -> None:
    model = _build_exact_required_optional_signature_upper_bound_model()
    model.build()

    symmetry_stats = model.build_stats["coordinate_symmetry"]
    assert symmetry_stats["enabled"] is True
    assert symmetry_stats["required_optional_signature_monotonic_constraints"] > 0

    delegate = model._coordinate_delegate
    assert delegate is not None
    slots = delegate.required_optional_slots["protocol_storage_box"]
    assert len(slots) >= 2
    assert slots[0].signature is not None
    assert slots[1].signature is not None

    reverse_model = _build_exact_required_optional_signature_upper_bound_model()
    reverse_model.build()
    reverse_slots = reverse_model._coordinate_delegate.required_optional_slots[
        "protocol_storage_box"
    ]
    reverse_model.model.Add(reverse_slots[0].signature > reverse_slots[1].signature)
    assert reverse_model.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE

    canonical_model = _build_exact_required_optional_signature_upper_bound_model()
    canonical_model.build()
    canonical_slots = canonical_model._coordinate_delegate.required_optional_slots[
        "protocol_storage_box"
    ]
    canonical_model.model.Add(
        canonical_slots[0].signature <= canonical_slots[1].signature
    )
    assert canonical_model.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )


def test_residual_optional_signature_bucket_count_uses_concrete_bucket_upper_bound() -> None:
    model = _build_exact_residual_optional_signature_model()

    model.build()

    residual_stats = model.build_stats["global_valid_inequalities"][
        "residual_signature_bucket_capacity_bounds"
    ]
    assert residual_stats["bucket_upper_bound_constraints"] == 2
    template_payload = next(
        payload
        for payload in residual_stats["templates"]
        if payload["template"] == "protocol_storage_box"
    )
    assert sorted(
        (bucket["bucket_pose_count"], bucket["count_var_upper_bound"])
        for bucket in template_payload["buckets"]
    ) == [
        (1, 1),
        (2, 2),
    ]

    constrained_bucket_id = next(
        bucket["bucket_id"]
        for bucket in template_payload["buckets"]
        if bucket["count_var_upper_bound"] == 1
    )
    model.model.Add(
        model._residual_optional_signature_count_vars["protocol_storage_box"][
            constrained_bucket_id
        ]
        >= 2
    )
    assert model.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_coordinate_symmetry_breaking_orders_residual_optional_signature_slots() -> None:
    model = _build_exact_residual_optional_signature_model()
    model.build()

    symmetry_stats = model.build_stats["coordinate_symmetry"]
    assert symmetry_stats["enabled"] is True
    assert symmetry_stats["residual_optional_signature_monotonic_constraints"] > 0

    delegate = model._coordinate_delegate
    assert delegate is not None
    slots = delegate.residual_optional_slots["protocol_storage_box"]
    assert len(slots) >= 2
    assert slots[0].signature is not None
    assert slots[1].signature is not None

    reverse_model = _build_exact_residual_optional_signature_model()
    reverse_model.build()
    reverse_slots = reverse_model._coordinate_delegate.residual_optional_slots[
        "protocol_storage_box"
    ]
    reverse_model.model.Add(reverse_slots[0].active == 1)
    reverse_model.model.Add(reverse_slots[1].active == 1)
    reverse_model.model.Add(reverse_slots[0].signature > reverse_slots[1].signature)
    assert reverse_model.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE

    canonical_model = _build_exact_residual_optional_signature_model()
    canonical_model.build()
    canonical_slots = canonical_model._coordinate_delegate.residual_optional_slots[
        "protocol_storage_box"
    ]
    canonical_model.model.Add(canonical_slots[0].active == 1)
    canonical_model.model.Add(canonical_slots[1].active == 1)
    canonical_model.model.Add(
        canonical_slots[0].signature <= canonical_slots[1].signature
    )
    assert canonical_model.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )


def test_ghost_conditioned_mandatory_signature_bucket_upper_bounds_tighten_counts() -> None:
    baseline = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))
    baseline.build()

    signature_stats = baseline.build_stats["global_valid_inequalities"]["signature_bucket_capacity_bounds"]
    assert signature_stats["ghost_conditioned_mandatory_bucket_constraints"] > 0
    assert signature_stats["ghost_signature_reduction_anchor_count"] > 0

    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(baseline._ghost_domains)
        if domain["anchor"] == {"x": 2, "y": 0}
    )
    baseline.model.Add(baseline.u_vars[forced_anchor_idx] == 1)
    assert baseline.solve(time_limit_seconds=5.0) in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    constrained = _build_exact_mandatory_signature_upper_bound_model(ghost_rect=(1, 1))
    constrained.build()
    group_payload = next(
        payload
        for payload in constrained.build_stats["global_valid_inequalities"][
            "signature_bucket_capacity_bounds"
        ]["mandatory_groups"]
        if payload["group_id"] == "group::router::routing::0"
    )
    constrained_bucket_id = next(
        bucket["bucket_id"]
        for bucket in group_payload["buckets"]
        if bucket["count_var_upper_bound"] == 1
    )
    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(constrained._ghost_domains)
        if domain["anchor"] == {"x": 2, "y": 0}
    )
    constrained.model.Add(constrained.u_vars[forced_anchor_idx] == 1)
    constrained.model.Add(
        constrained._mandatory_signature_count_vars["group::router::routing::0"][
            constrained_bucket_id
        ]
        >= 1
    )
    assert constrained.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_ghost_conditioned_required_optional_signature_bucket_upper_bounds_tighten_counts() -> None:
    baseline = _build_exact_required_optional_signature_upper_bound_model(ghost_rect=(1, 1))
    baseline.build()

    signature_stats = baseline.build_stats["global_valid_inequalities"]["signature_bucket_capacity_bounds"]
    assert signature_stats["ghost_conditioned_required_optional_bucket_constraints"] > 0
    assert signature_stats["ghost_signature_reduction_anchor_count"] > 0

    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(baseline._ghost_domains)
        if domain["anchor"] == {"x": 2, "y": 1}
    )
    baseline.model.Add(baseline.u_vars[forced_anchor_idx] == 1)
    assert baseline.solve(time_limit_seconds=5.0) in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    constrained = _build_exact_required_optional_signature_upper_bound_model(ghost_rect=(1, 1))
    constrained.build()
    template_payload = next(
        payload
        for payload in constrained.build_stats["global_valid_inequalities"][
            "signature_bucket_capacity_bounds"
        ]["required_optionals"]
        if payload["template"] == "protocol_storage_box"
    )
    constrained_bucket_id = next(
        bucket["bucket_id"]
        for bucket in template_payload["buckets"]
        if bucket["count_var_upper_bound"] == 1
    )
    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(constrained._ghost_domains)
        if domain["anchor"] == {"x": 2, "y": 1}
    )
    constrained.model.Add(constrained.u_vars[forced_anchor_idx] == 1)
    constrained.model.Add(
        constrained._required_optional_signature_count_vars["protocol_storage_box"][
            constrained_bucket_id
        ]
        >= 1
    )
    assert constrained.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_ghost_conditioned_residual_optional_signature_bucket_upper_bounds_tighten_counts() -> None:
    baseline = _build_exact_residual_optional_signature_model(ghost_rect=(1, 1))
    baseline.build()

    residual_stats = baseline.build_stats["global_valid_inequalities"][
        "residual_signature_bucket_capacity_bounds"
    ]
    assert residual_stats["ghost_conditioned_residual_bucket_constraints"] > 0
    assert residual_stats["ghost_residual_signature_reduction_anchor_count"] > 0

    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(baseline._ghost_domains)
        if domain["anchor"] == {"x": 2, "y": 1}
    )
    baseline.model.Add(baseline.u_vars[forced_anchor_idx] == 1)
    assert baseline.solve(time_limit_seconds=5.0) in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    constrained = _build_exact_residual_optional_signature_model(ghost_rect=(1, 1))
    constrained.build()
    template_payload = next(
        payload
        for payload in constrained.build_stats["global_valid_inequalities"][
            "residual_signature_bucket_capacity_bounds"
        ]["templates"]
        if payload["template"] == "protocol_storage_box"
    )
    constrained_bucket_id = next(
        bucket["bucket_id"]
        for bucket in template_payload["buckets"]
        if bucket["count_var_upper_bound"] == 1
    )
    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(constrained._ghost_domains)
        if domain["anchor"] == {"x": 2, "y": 1}
    )
    constrained.model.Add(constrained.u_vars[forced_anchor_idx] == 1)
    constrained.model.Add(
        constrained._residual_optional_signature_count_vars["protocol_storage_box"][
            constrained_bucket_id
        ]
        >= 1
    )
    assert constrained.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_index_pools_prebuilds_compact_local_capacity_signature_classes() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()

    model._index_pools()

    compact_groups = model._power_pole_pose_indices_by_template_compact_capacity_signature[
        "powered_machine"
    ]
    assert len(compact_groups) == 1
    assert (
        model._ensure_local_power_capacity_compact_signature_classes("powered_machine")
        is compact_groups
    )
    assert "powered_machine" not in model._power_supported_pose_indices_by_template_pole
    assert model._compact_local_power_capacity_signature_by_template_pole["powered_machine"]
    assert model._power_pole_compact_capacity_signatures_by_template_shell_pair[
        "powered_machine"
    ]
    assert (
        model._exact_precompute_profile["power_capacity_legacy_signature_materializations"]
        == 0
    )
    assert (
        model._exact_precompute_profile["power_capacity_supported_by_pole_materializations"]
        == 0
    )


def test_lazy_supported_by_pole_materialization_and_counted_compact_fan_out_match_eager_result() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()

    model._index_pools()

    assert "powered_machine" not in model._power_supported_pose_indices_by_template_pole
    assert (
        model._exact_precompute_profile["power_capacity_supported_by_pole_materializations"]
        == 0
    )

    materialized_supported = model._ensure_power_supported_pose_indices_by_template_pole(
        "powered_machine"
    )
    assert materialized_supported
    assert (
        model._exact_precompute_profile["power_capacity_supported_by_pole_materializations"]
        == 1
    )
    assert (
        model._ensure_power_supported_pose_indices_by_template_pole("powered_machine")
        is materialized_supported
    )
    assert (
        model._exact_precompute_profile["power_capacity_supported_by_pole_materializations"]
        == 1
    )

    power_pole_anchors = model._pose_anchor_by_template_pose["power_pole"]
    pose_anchors = model._pose_anchor_by_template_pose["powered_machine"]
    pose_shape_tokens = model._pose_local_shape_token_by_template_pose["powered_machine"]
    expected_compact_by_pole = {}
    for pole_idx in range(len(model.facility_pools["power_pole"])):
        origin_x, origin_y = power_pole_anchors[int(pole_idx)]
        compact_items = []
        for pose_idx in materialized_supported.get(int(pole_idx), []):
            anchor_x, anchor_y = pose_anchors[int(pose_idx)]
            compact_items.append(
                (
                    int(anchor_x) - int(origin_x),
                    int(anchor_y) - int(origin_y),
                    int(pose_shape_tokens[int(pose_idx)]),
                )
            )
        expected_compact_by_pole[int(pole_idx)] = tuple(sorted(compact_items))

    assert (
        model._compact_local_power_capacity_signature_by_template_pole["powered_machine"]
        == expected_compact_by_pole
    )


def test_compact_local_capacity_signature_matches_legacy_signature_and_cpsat_oracle() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()
    model.build()

    compact_groups = model._power_pole_pose_indices_by_template_compact_capacity_signature[
        "powered_machine"
    ]
    assert len(compact_groups) == 1
    assert (
        model._ensure_local_power_capacity_compact_signature_classes("powered_machine")
        is compact_groups
    )
    assert (
        model.build_stats["exact_precompute_profile"][
            "power_capacity_legacy_signature_materializations"
        ]
        == 0
    )
    assert (
        model._legacy_local_power_capacity_signature_by_template_compact_signature.get(
            "powered_machine",
            {},
        )
        == {}
    )

    for compact_signature, pose_indices in compact_groups.items():
        assert compact_signature == model._compact_local_power_capacity_signature(
            "powered_machine",
            pose_indices[0],
        )
        legacy_signature = model._local_power_capacity_signature(
            "powered_machine",
            pose_indices[0],
        )
        assert (
            model.build_stats["exact_precompute_profile"][
                "power_capacity_legacy_signature_materializations"
            ]
            == 1
        )
        assert legacy_signature == model._local_power_capacity_signature(
            "powered_machine",
            pose_indices[-1],
        )
        assert (
            model.build_stats["exact_precompute_profile"][
                "power_capacity_legacy_signature_materializations"
            ]
            == 1
        )
        legacy_by_compact = model._legacy_local_power_capacity_signature_by_template_compact_signature[
            "powered_machine"
        ]
        assert legacy_by_compact[compact_signature] == legacy_signature
        assert legacy_signature == model._local_power_capacity_signature(
            "powered_machine",
            pose_indices[0],
        )
        assert legacy_signature == model._materialize_local_power_capacity_signature_from_compact(
            "powered_machine",
            compact_signature,
        )
        assert model._solve_exact_local_power_capacity_from_compact(
            "powered_machine",
            compact_signature,
        ) == model._solve_exact_local_power_capacity_compact_rect_cpsat_v2(
            "powered_machine",
            compact_signature,
        )
        assert model._solve_exact_local_power_capacity_rectangle_frontier_dp_v1(
            "powered_machine",
            compact_signature,
        ) == model._solve_exact_local_power_capacity_rectangle_frontier_dp_v2(
            "powered_machine",
            compact_signature,
        )
        assert model._solve_exact_local_power_capacity_rectangle_frontier_dp_v2(
            "powered_machine",
            compact_signature,
        ) == model._solve_exact_local_power_capacity_rectangle_frontier_dp_v3(
            "powered_machine",
            compact_signature,
        )
        assert model._solve_exact_local_power_capacity_rectangle_frontier_dp_v3(
            "powered_machine",
            compact_signature,
        ) == model._solve_exact_local_power_capacity_rectangle_frontier_dp_v4(
            "powered_machine",
            compact_signature,
        ) == model._solve_exact_local_power_capacity_cpsat(
            "powered_machine",
            legacy_signature,
        )
        assert model._solve_exact_local_power_capacity(
            "powered_machine",
            legacy_signature,
            compact_signature=compact_signature,
        ) == model._solve_exact_local_power_capacity_cpsat(
            "powered_machine",
            legacy_signature,
        )


def test_compact_local_capacity_signature_hard_fails_on_legacy_mismatch() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()
    token = model._pose_local_shape_token_by_template_pose["powered_machine"][0]
    model._local_shape_by_template_token["powered_machine"][token] = ((999, 999),)
    model._local_power_capacity_signature_by_template_pole.pop("powered_machine", None)
    model._compact_local_power_capacity_signature_by_template_pole.pop("powered_machine", None)
    model._power_pole_pose_indices_by_template_capacity_signature.pop("powered_machine", None)
    model._power_pole_pose_indices_by_template_compact_capacity_signature.pop(
        "powered_machine",
        None,
    )
    model._power_pole_compact_capacity_signatures_by_template_shell_pair.pop(
        "powered_machine",
        None,
    )
    model._legacy_local_power_capacity_signature_by_template_compact_signature.pop(
        "powered_machine",
        None,
    )
    model._compact_local_power_capacity_signature_by_template_legacy_signature.pop(
        "powered_machine",
        None,
    )

    with pytest.raises(RuntimeError, match="Compact local-capacity signature mismatch"):
        model._local_power_capacity_signature("powered_machine", 0)


def test_rectangle_frontier_dp_v4_matches_v3_v2_v1_bitset_and_cpsat_for_mixed_rectangles() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()
    rect_tpl = "mixed_rectangles"
    shape_6x4 = tuple((x_val, y_val) for x_val in range(6) for y_val in range(4))
    shape_4x6 = tuple((x_val, y_val) for x_val in range(4) for y_val in range(6))
    model._local_shape_by_template_token[rect_tpl] = {
        0: shape_6x4,
        1: shape_4x6,
    }
    model._local_rectangle_variant_by_template_token.pop(rect_tpl, None)
    compact_signature = tuple(
        sorted(
            [
                (0, 0, 0),
                (6, 0, 0),
                (0, 4, 1),
                (4, 4, 1),
            ]
        )
    )
    legacy_signature = model._materialize_local_power_capacity_signature_from_compact(
        rect_tpl,
        compact_signature,
    )

    row_capacity_v1 = model._solve_exact_local_power_capacity_rectangle_frontier_dp_v1(
        rect_tpl,
        compact_signature,
        scan_axis="row",
    )
    column_capacity_v1 = model._solve_exact_local_power_capacity_rectangle_frontier_dp_v1(
        rect_tpl,
        compact_signature,
        scan_axis="column",
    )
    row_capacity_v2 = model._solve_exact_local_power_capacity_rectangle_frontier_dp_v2(
        rect_tpl,
        compact_signature,
        scan_axis="row",
    )
    column_capacity_v2 = model._solve_exact_local_power_capacity_rectangle_frontier_dp_v2(
        rect_tpl,
        compact_signature,
        scan_axis="column",
    )
    row_capacity_v3 = model._solve_exact_local_power_capacity_rectangle_frontier_dp_v3(
        rect_tpl,
        compact_signature,
        scan_axis="row",
    )
    column_capacity_v3 = model._solve_exact_local_power_capacity_rectangle_frontier_dp_v3(
        rect_tpl,
        compact_signature,
        scan_axis="column",
    )
    row_capacity_v4 = model._solve_exact_local_power_capacity_rectangle_frontier_dp_v4(
        rect_tpl,
        compact_signature,
        scan_axis="row",
    )
    column_capacity_v4 = model._solve_exact_local_power_capacity_rectangle_frontier_dp_v4(
        rect_tpl,
        compact_signature,
        scan_axis="column",
    )
    bitset_capacity = model._solve_exact_local_power_capacity_bitset_mis(
        rect_tpl,
        legacy_signature,
    )
    cpsat_capacity = model._solve_exact_local_power_capacity_cpsat(
        rect_tpl,
        legacy_signature,
    )

    assert (
        row_capacity_v1
        == column_capacity_v1
        == row_capacity_v2
        == column_capacity_v2
        == row_capacity_v3
        == column_capacity_v3
        == row_capacity_v4
        == column_capacity_v4
        == bitset_capacity
        == cpsat_capacity
        == 4
    )


def test_manufacturing_6x4_mixed_specialized_cpsat_matches_v3_bitset_and_legacy_cpsat() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()

    shape_6x4 = tuple((x_val, y_val) for x_val in range(6) for y_val in range(4))
    shape_4x6 = tuple((x_val, y_val) for x_val in range(4) for y_val in range(6))
    model._local_shape_by_template_token["manufacturing_6x4"] = {0: shape_6x4, 1: shape_4x6}
    model._local_rectangle_variant_by_template_token.pop("manufacturing_6x4", None)

    compact_signature = tuple(
        sorted(
            [
                (0, 0, 0),
                (6, 0, 0),
                (0, 4, 1),
                (4, 4, 1),
            ]
        )
    )
    legacy_signature = model._materialize_local_power_capacity_signature_from_compact(
        "manufacturing_6x4",
        compact_signature,
    )

    specialized_capacity = (
        model._solve_exact_local_power_capacity_manufacturing_6x4_mixed_cpsat(
            "manufacturing_6x4",
            compact_signature,
        )
    )
    compact_entry_capacity = model._solve_exact_local_power_capacity_from_compact(
        "manufacturing_6x4",
        compact_signature,
    )
    generic_capacity = model._solve_exact_local_power_capacity_compact_rect_cpsat_v2(
        "manufacturing_6x4",
        compact_signature,
    )
    v3_capacity = model._solve_exact_local_power_capacity_rectangle_frontier_dp_v3(
        "manufacturing_6x4",
        compact_signature,
        scan_axis="row",
    )
    bitset_capacity = model._solve_exact_local_power_capacity_bitset_mis(
        "manufacturing_6x4",
        legacy_signature,
    )
    legacy_cpsat_capacity = model._solve_exact_local_power_capacity_cpsat(
        "manufacturing_6x4",
        legacy_signature,
    )

    assert (
        specialized_capacity
        == compact_entry_capacity
        == generic_capacity
        == v3_capacity
        == bitset_capacity
        == legacy_cpsat_capacity
        == 4
    )


def test_uniform_3x3_specialized_cpsat_matches_v3_bitset_and_legacy_cpsat() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()
    rect_tpl = "uniform_3x3"
    shape_3x3 = tuple((x_val, y_val) for x_val in range(3) for y_val in range(3))
    model._local_shape_by_template_token[rect_tpl] = {0: shape_3x3}
    model._local_rectangle_variant_by_template_token.pop(rect_tpl, None)
    compact_signature = tuple(
        sorted(
            [
                (0, 0, 0),
                (3, 0, 0),
                (0, 3, 0),
                (3, 3, 0),
            ]
        )
    )
    legacy_signature = model._materialize_local_power_capacity_signature_from_compact(
        rect_tpl,
        compact_signature,
    )

    specialized_capacity = model._solve_exact_local_power_capacity_uniform_3x3_cpsat(
        rect_tpl,
        compact_signature,
    )
    compact_entry_capacity = model._solve_exact_local_power_capacity_from_compact(
        rect_tpl,
        compact_signature,
    )
    generic_capacity = model._solve_exact_local_power_capacity_compact_rect_cpsat_v2(
        rect_tpl,
        compact_signature,
    )
    v3_capacity = model._solve_exact_local_power_capacity_rectangle_frontier_dp_v3(
        rect_tpl,
        compact_signature,
        scan_axis="row",
    )
    bitset_capacity = model._solve_exact_local_power_capacity_bitset_mis(
        rect_tpl,
        legacy_signature,
    )
    legacy_cpsat_capacity = model._solve_exact_local_power_capacity_cpsat(
        rect_tpl,
        legacy_signature,
    )

    assert (
        specialized_capacity
        == compact_entry_capacity
        == generic_capacity
        == v3_capacity
        == bitset_capacity
        == legacy_cpsat_capacity
        == 4
    )


def test_compact_rect_cpsat_v2_matches_v4_v3_bitset_and_legacy_cpsat_for_5x5() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()
    rect_tpl = "representative_5x5"
    shape_5x5 = tuple((x_val, y_val) for x_val in range(5) for y_val in range(5))
    model._local_shape_by_template_token[rect_tpl] = {0: shape_5x5}
    model._local_rectangle_variant_by_template_token.pop(rect_tpl, None)
    compact_signature = tuple(
        sorted(
            [
                (0, 0, 0),
                (5, 0, 0),
                (0, 5, 0),
                (5, 5, 0),
            ]
        )
    )
    legacy_signature = model._materialize_local_power_capacity_signature_from_compact(
        rect_tpl,
        compact_signature,
    )

    compact_entry_capacity = model._solve_exact_local_power_capacity_from_compact(
        rect_tpl,
        compact_signature,
    )
    generic_capacity = model._solve_exact_local_power_capacity_compact_rect_cpsat_v2(
        rect_tpl,
        compact_signature,
    )
    v4_capacity = model._solve_exact_local_power_capacity_rectangle_frontier_dp_v4(
        rect_tpl,
        compact_signature,
        scan_axis="row",
    )
    v3_capacity = model._solve_exact_local_power_capacity_rectangle_frontier_dp_v3(
        rect_tpl,
        compact_signature,
        scan_axis="row",
    )
    bitset_capacity = model._solve_exact_local_power_capacity_bitset_mis(
        rect_tpl,
        legacy_signature,
    )
    legacy_cpsat_capacity = model._solve_exact_local_power_capacity_cpsat(
        rect_tpl,
        legacy_signature,
    )

    assert (
        compact_entry_capacity
        == generic_capacity
        == v4_capacity
        == v3_capacity
        == bitset_capacity
        == legacy_cpsat_capacity
        == 4
    )


def test_compact_rect_cpsat_v2_primary_routing_handles_small_5x5_and_dense_6x4() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()

    shape_5x5 = tuple((x_val, y_val) for x_val in range(5) for y_val in range(5))
    shape_6x4 = tuple((x_val, y_val) for x_val in range(6) for y_val in range(4))
    shape_4x6 = tuple((x_val, y_val) for x_val in range(4) for y_val in range(6))
    model._local_shape_by_template_token["representative_5x5"] = {0: shape_5x5}
    model._local_shape_by_template_token["manufacturing_6x4"] = {0: shape_6x4, 1: shape_4x6}
    model._local_rectangle_variant_by_template_token.pop("representative_5x5", None)
    model._local_rectangle_variant_by_template_token.pop("manufacturing_6x4", None)

    compact_signature_5x5 = tuple(
        sorted(
            [
                (0, 0, 0),
                (5, 0, 0),
                (0, 5, 0),
                (5, 5, 0),
                (10, 0, 0),
                (10, 5, 0),
            ]
        )
    )
    compact_signature_dense_6x4 = tuple(
        sorted(
            [
                (x_val, y_val, token)
                for x_val in range(16)
                for y_val in range(8)
                for token, (width, height) in ((0, (6, 4)), (1, (4, 6)))
                if x_val + width <= 16 and y_val + height <= 8
            ]
        )
    )

    compiled_5x5 = model._compile_rectangle_frontier_dp(
        "representative_5x5",
        compact_signature_5x5,
        scan_axis="row",
    )
    compiled_dense_6x4 = model._compile_rectangle_frontier_dp(
        "manufacturing_6x4",
        compact_signature_dense_6x4,
        scan_axis="row",
    )

    assert model._should_use_rectangle_frontier_dp_v4(compiled_5x5) is True
    assert model._should_use_rectangle_frontier_dp_v4(compiled_dense_6x4) is False

    cache_stats_v4 = {
        "compact_rect_cpsat_evaluations": 0,
        "compact_rect_cpsat_cache_hits": 0,
        "compact_rect_cpsat_selected_cases": 0,
        "compact_rect_cpsat_rect_dp_fallbacks": 0,
        "rect_dp_evaluations": 0,
        "rect_dp_v3_fallbacks": 0,
        "m6x4_mixed_cpsat_evaluations": 0,
        "m6x4_mixed_cpsat_cache_hits": 0,
        "m6x4_mixed_cpsat_selected_cases": 0,
        "m6x4_mixed_cpsat_v3_fallbacks": 0,
    }
    cache_stats_mixed = {
        "compact_rect_cpsat_evaluations": 0,
        "compact_rect_cpsat_cache_hits": 0,
        "compact_rect_cpsat_selected_cases": 0,
        "compact_rect_cpsat_rect_dp_fallbacks": 0,
        "rect_dp_evaluations": 0,
        "rect_dp_v3_fallbacks": 0,
        "m6x4_mixed_cpsat_evaluations": 0,
        "m6x4_mixed_cpsat_cache_hits": 0,
        "m6x4_mixed_cpsat_selected_cases": 0,
        "m6x4_mixed_cpsat_v3_fallbacks": 0,
    }
    routed_5x5 = model._solve_exact_local_power_capacity(
        "representative_5x5",
        model._materialize_local_power_capacity_signature_from_compact(
            "representative_5x5",
            compact_signature_5x5,
        ),
        compact_signature=compact_signature_5x5,
        cache_stats=cache_stats_v4,
    )
    routed_dense_6x4 = model._solve_exact_local_power_capacity(
        "manufacturing_6x4",
        model._materialize_local_power_capacity_signature_from_compact(
            "manufacturing_6x4",
            compact_signature_dense_6x4,
        ),
        compact_signature=compact_signature_dense_6x4,
        cache_stats=cache_stats_mixed,
    )
    direct_primary_5x5 = model._solve_exact_local_power_capacity_compact_rect_cpsat_v2(
        "representative_5x5",
        compact_signature_5x5,
        cache_stats={
            "compact_rect_cpsat_evaluations": 0,
            "compact_rect_cpsat_cache_hits": 0,
            "compact_rect_cpsat_selected_cases": 0,
            "compact_rect_cpsat_rect_dp_fallbacks": 0,
        },
    )
    direct_primary_mixed = model._solve_exact_local_power_capacity_compact_rect_cpsat_v2(
        "manufacturing_6x4",
        compact_signature_dense_6x4,
        cache_stats={
            "compact_rect_cpsat_evaluations": 0,
            "compact_rect_cpsat_cache_hits": 0,
            "compact_rect_cpsat_selected_cases": 0,
            "compact_rect_cpsat_rect_dp_fallbacks": 0,
            "m6x4_mixed_cpsat_evaluations": 0,
            "m6x4_mixed_cpsat_cache_hits": 0,
            "m6x4_mixed_cpsat_selected_cases": 0,
            "m6x4_mixed_cpsat_v3_fallbacks": 0,
        },
    )

    assert cache_stats_v4["compact_rect_cpsat_selected_cases"] == 1
    assert cache_stats_v4["compact_rect_cpsat_evaluations"] == 1
    assert cache_stats_v4["compact_rect_cpsat_rect_dp_fallbacks"] == 0
    assert cache_stats_v4["rect_dp_evaluations"] == 0
    assert cache_stats_v4["m6x4_mixed_cpsat_selected_cases"] == 0
    assert cache_stats_v4["rect_dp_v3_fallbacks"] == 0
    assert cache_stats_mixed["compact_rect_cpsat_selected_cases"] == 1
    assert cache_stats_mixed["compact_rect_cpsat_evaluations"] == 1
    assert cache_stats_mixed["compact_rect_cpsat_rect_dp_fallbacks"] == 0
    assert cache_stats_mixed["rect_dp_evaluations"] == 0
    assert cache_stats_mixed["rect_dp_v3_fallbacks"] == 0
    assert cache_stats_mixed["m6x4_mixed_cpsat_selected_cases"] == 1
    assert cache_stats_mixed["m6x4_mixed_cpsat_evaluations"] == 1
    assert cache_stats_mixed["m6x4_mixed_cpsat_v3_fallbacks"] == 0
    assert routed_5x5 == direct_primary_5x5
    assert routed_5x5 == model._solve_exact_local_power_capacity_rectangle_frontier_dp_v4(
        "representative_5x5",
        compact_signature_5x5,
        scan_axis="row",
        compiled=compiled_5x5,
    )
    assert routed_dense_6x4 == direct_primary_mixed
    assert routed_dense_6x4 == model._solve_exact_local_power_capacity_rectangle_frontier_dp_v3(
        "manufacturing_6x4",
        compact_signature_dense_6x4,
        scan_axis="row",
        compiled=compiled_dense_6x4,
    )


def test_compact_rect_cpsat_v2_primary_routing_handles_dense_3x3() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()

    shape_3x3 = tuple((x_val, y_val) for x_val in range(3) for y_val in range(3))
    model._local_shape_by_template_token["uniform_3x3"] = {0: shape_3x3}
    model._local_rectangle_variant_by_template_token.pop("uniform_3x3", None)
    compact_signature_dense_3x3 = tuple(
        sorted(
            [
                (x_val, y_val, 0)
                for x_val in range(14)
                for y_val in range(14)
            ]
        )
    )

    compiled_dense_3x3 = model._compile_rectangle_frontier_dp(
        "uniform_3x3",
        compact_signature_dense_3x3,
        scan_axis="row",
    )

    assert model._should_use_rectangle_frontier_dp_v4(compiled_dense_3x3) is False
    cache_stats = {
        "compact_rect_cpsat_evaluations": 0,
        "compact_rect_cpsat_cache_hits": 0,
        "compact_rect_cpsat_selected_cases": 0,
        "compact_rect_cpsat_rect_dp_fallbacks": 0,
        "rect_dp_evaluations": 0,
        "rect_dp_v3_fallbacks": 0,
        "uniform_3x3_cpsat_evaluations": 0,
        "uniform_3x3_cpsat_cache_hits": 0,
        "uniform_3x3_cpsat_selected_cases": 0,
        "uniform_3x3_cpsat_v3_fallbacks": 0,
    }
    routed_dense_3x3 = model._solve_exact_local_power_capacity(
        "uniform_3x3",
        model._materialize_local_power_capacity_signature_from_compact(
            "uniform_3x3",
            compact_signature_dense_3x3,
        ),
        compact_signature=compact_signature_dense_3x3,
        cache_stats=cache_stats,
    )
    direct_specialized = model._solve_exact_local_power_capacity_compact_rect_cpsat_v2(
        "uniform_3x3",
        compact_signature_dense_3x3,
        cache_stats={
            "compact_rect_cpsat_evaluations": 0,
            "compact_rect_cpsat_cache_hits": 0,
            "compact_rect_cpsat_selected_cases": 0,
            "compact_rect_cpsat_rect_dp_fallbacks": 0,
            "uniform_3x3_cpsat_evaluations": 0,
            "uniform_3x3_cpsat_cache_hits": 0,
            "uniform_3x3_cpsat_selected_cases": 0,
            "uniform_3x3_cpsat_v3_fallbacks": 0,
        },
    )

    assert cache_stats["compact_rect_cpsat_selected_cases"] == 1
    assert cache_stats["compact_rect_cpsat_evaluations"] == 1
    assert cache_stats["compact_rect_cpsat_rect_dp_fallbacks"] == 0
    assert cache_stats["rect_dp_evaluations"] == 0
    assert cache_stats["rect_dp_v3_fallbacks"] == 0
    assert cache_stats["uniform_3x3_cpsat_selected_cases"] == 1
    assert cache_stats["uniform_3x3_cpsat_evaluations"] == 1
    assert cache_stats["uniform_3x3_cpsat_v3_fallbacks"] == 0
    assert routed_dense_3x3 == direct_specialized
    assert routed_dense_3x3 == model._solve_exact_local_power_capacity_rectangle_frontier_dp_v3(
        "uniform_3x3",
        compact_signature_dense_3x3,
        scan_axis="row",
        compiled=compiled_dense_3x3,
    )


def test_compact_rect_cpsat_v2_reuses_shared_normalized_cache_across_templates() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()

    shape_3x3 = tuple((x_val, y_val) for x_val in range(3) for y_val in range(3))
    for tpl in ("manufacturing_3x3", "protocol_storage_box"):
        model._local_shape_by_template_token[tpl] = {0: shape_3x3}
        model._local_rectangle_variant_by_template_token.pop(tpl, None)

    compact_signature = tuple(
        sorted(
            [
                (0, 0, 0),
                (3, 0, 0),
                (0, 3, 0),
                (3, 3, 0),
            ]
        )
    )
    stats_first = {
        "compact_rect_cpsat_evaluations": 0,
        "compact_rect_cpsat_cache_hits": 0,
        "compact_rect_cpsat_selected_cases": 0,
        "compact_rect_cpsat_rect_dp_fallbacks": 0,
        "normalized_rect_cache_hits": 0,
        "normalized_rect_cache_misses": 0,
    }
    stats_second = {
        "compact_rect_cpsat_evaluations": 0,
        "compact_rect_cpsat_cache_hits": 0,
        "compact_rect_cpsat_selected_cases": 0,
        "compact_rect_cpsat_rect_dp_fallbacks": 0,
        "normalized_rect_cache_hits": 0,
        "normalized_rect_cache_misses": 0,
    }

    first_capacity = model._solve_exact_local_power_capacity_from_compact(
        "manufacturing_3x3",
        compact_signature,
        cache_stats=stats_first,
    )
    expected_normalized = model._normalize_rectangle_frontier_signature(
        "manufacturing_3x3",
        compact_signature,
    )
    second_capacity = model._solve_exact_local_power_capacity_from_compact(
        "protocol_storage_box",
        compact_signature,
        cache_stats=stats_second,
    )

    assert first_capacity == second_capacity == 4
    assert stats_first["compact_rect_cpsat_selected_cases"] == 1
    assert stats_first["compact_rect_cpsat_evaluations"] == 1
    assert stats_first["normalized_rect_cache_hits"] == 0
    assert stats_first["normalized_rect_cache_misses"] == 1
    assert stats_second["compact_rect_cpsat_selected_cases"] == 1
    assert stats_second["compact_rect_cpsat_evaluations"] == 0
    assert stats_second["normalized_rect_cache_hits"] == 1
    assert stats_second["normalized_rect_cache_misses"] == 0
    assert _LOCAL_POWER_CAPACITY_NORMALIZED_RECT_CACHE[expected_normalized] == 4


def test_compact_rect_cpsat_v2_reuses_shared_normalized_cache_within_template() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()

    shape_3x3 = tuple((x_val, y_val) for x_val in range(3) for y_val in range(3))
    tpl = "aliased_3x3"
    model._local_shape_by_template_token[tpl] = {0: shape_3x3, 1: shape_3x3}
    model._local_rectangle_variant_by_template_token.pop(tpl, None)

    compact_signature_token0 = tuple(
        sorted(
            [
                (0, 0, 0),
                (3, 0, 0),
                (0, 3, 0),
                (3, 3, 0),
            ]
        )
    )
    compact_signature_token1 = tuple(
        sorted(
            [
                (0, 0, 1),
                (3, 0, 1),
                (0, 3, 1),
                (3, 3, 1),
            ]
        )
    )
    assert model._normalize_rectangle_frontier_signature(
        tpl,
        compact_signature_token0,
    ) == model._normalize_rectangle_frontier_signature(
        tpl,
        compact_signature_token1,
    )

    stats_first = {
        "compact_rect_cpsat_evaluations": 0,
        "compact_rect_cpsat_cache_hits": 0,
        "compact_rect_cpsat_selected_cases": 0,
        "compact_rect_cpsat_rect_dp_fallbacks": 0,
        "normalized_rect_cache_hits": 0,
        "normalized_rect_cache_misses": 0,
    }
    stats_second = {
        "compact_rect_cpsat_evaluations": 0,
        "compact_rect_cpsat_cache_hits": 0,
        "compact_rect_cpsat_selected_cases": 0,
        "compact_rect_cpsat_rect_dp_fallbacks": 0,
        "normalized_rect_cache_hits": 0,
        "normalized_rect_cache_misses": 0,
    }

    first_capacity = model._solve_exact_local_power_capacity_from_compact(
        tpl,
        compact_signature_token0,
        cache_stats=stats_first,
    )
    expected_normalized = model._normalize_rectangle_frontier_signature(
        tpl,
        compact_signature_token0,
    )
    second_capacity = model._solve_exact_local_power_capacity_from_compact(
        tpl,
        compact_signature_token1,
        cache_stats=stats_second,
    )

    assert first_capacity == second_capacity == 4
    assert stats_first["compact_rect_cpsat_selected_cases"] == 1
    assert stats_first["compact_rect_cpsat_evaluations"] == 1
    assert stats_first["normalized_rect_cache_hits"] == 0
    assert stats_first["normalized_rect_cache_misses"] == 1
    assert stats_second["compact_rect_cpsat_selected_cases"] == 1
    assert stats_second["compact_rect_cpsat_evaluations"] == 0
    assert stats_second["normalized_rect_cache_hits"] == 1
    assert stats_second["normalized_rect_cache_misses"] == 0
    assert _LOCAL_POWER_CAPACITY_NORMALIZED_RECT_CACHE[expected_normalized] == 4


def test_compact_rect_cpsat_v2_falls_back_to_v3_explicitly_for_dense_mixed_6x4(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()

    shape_6x4 = tuple((x_val, y_val) for x_val in range(6) for y_val in range(4))
    shape_4x6 = tuple((x_val, y_val) for x_val in range(4) for y_val in range(6))
    model._local_shape_by_template_token["manufacturing_6x4"] = {0: shape_6x4, 1: shape_4x6}
    model._local_rectangle_variant_by_template_token.pop("manufacturing_6x4", None)
    compact_signature_dense_6x4 = tuple(
        sorted(
            [
                (x_val, y_val, token)
                for x_val in range(16)
                for y_val in range(8)
                for token, (width, height) in ((0, (6, 4)), (1, (4, 6)))
                if x_val + width <= 16 and y_val + height <= 8
            ]
        )
    )
    expected = model._solve_exact_local_power_capacity_rectangle_frontier_dp(
        "manufacturing_6x4",
        compact_signature_dense_6x4,
    )
    _LOCAL_POWER_CAPACITY_RECT_DP_CACHE.clear()

    def _force_fallback(*args: object, **kwargs: object) -> int:
        raise _CompactRectCpSatFallback("forced_for_test")

    monkeypatch.setattr(
        model,
        "_solve_exact_local_power_capacity_compact_rect_cpsat",
        _force_fallback,
    )
    cache_stats = {
        "compact_rect_cpsat_evaluations": 0,
        "compact_rect_cpsat_cache_hits": 0,
        "compact_rect_cpsat_selected_cases": 0,
        "compact_rect_cpsat_rect_dp_fallbacks": 0,
        "rect_dp_evaluations": 0,
        "rect_dp_v3_fallbacks": 0,
        "m6x4_mixed_cpsat_evaluations": 0,
        "m6x4_mixed_cpsat_cache_hits": 0,
        "m6x4_mixed_cpsat_selected_cases": 0,
        "m6x4_mixed_cpsat_v3_fallbacks": 0,
    }

    routed = model._solve_exact_local_power_capacity(
        "manufacturing_6x4",
        model._materialize_local_power_capacity_signature_from_compact(
            "manufacturing_6x4",
            compact_signature_dense_6x4,
        ),
        compact_signature=compact_signature_dense_6x4,
        cache_stats=cache_stats,
    )

    assert cache_stats["compact_rect_cpsat_selected_cases"] == 1
    assert cache_stats["compact_rect_cpsat_rect_dp_fallbacks"] == 1
    assert cache_stats["rect_dp_evaluations"] == 1
    assert cache_stats["m6x4_mixed_cpsat_selected_cases"] == 1
    assert cache_stats["m6x4_mixed_cpsat_v3_fallbacks"] == 1
    assert routed == expected


def test_compact_rect_cpsat_v2_falls_back_to_v4_for_small_5x5() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()

    shape_5x5 = tuple((x_val, y_val) for x_val in range(5) for y_val in range(5))
    model._local_shape_by_template_token["representative_5x5"] = {0: shape_5x5}
    model._local_rectangle_variant_by_template_token.pop("representative_5x5", None)
    compact_signature_5x5 = tuple(
        sorted(
            [
                (0, 0, 0),
                (5, 0, 0),
                (0, 5, 0),
                (5, 5, 0),
                (10, 0, 0),
                (10, 5, 0),
            ]
        )
    )
    compiled = model._compile_rectangle_frontier_dp(
        "representative_5x5",
        compact_signature_5x5,
        scan_axis="row",
    )
    expected = model._solve_exact_local_power_capacity_rectangle_frontier_dp_v4(
        "representative_5x5",
        compact_signature_5x5,
        scan_axis="row",
        compiled=compiled,
    )

    def _force_fallback(*args: object, **kwargs: object) -> int:
        raise _CompactRectCpSatFallback("forced_for_test")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(model, "_solve_exact_local_power_capacity_compact_rect_cpsat", _force_fallback)
    cache_stats = {
        "compact_rect_cpsat_evaluations": 0,
        "compact_rect_cpsat_cache_hits": 0,
        "compact_rect_cpsat_selected_cases": 0,
        "compact_rect_cpsat_rect_dp_fallbacks": 0,
        "rect_dp_evaluations": 0,
        "rect_dp_v3_fallbacks": 0,
    }
    try:
        routed = model._solve_exact_local_power_capacity(
            "representative_5x5",
            model._materialize_local_power_capacity_signature_from_compact(
                "representative_5x5",
                compact_signature_5x5,
            ),
            compact_signature=compact_signature_5x5,
            cache_stats=cache_stats,
        )
    finally:
        monkeypatch.undo()

    assert cache_stats["compact_rect_cpsat_selected_cases"] == 1
    assert cache_stats["compact_rect_cpsat_rect_dp_fallbacks"] == 1
    assert cache_stats["rect_dp_evaluations"] == 1
    assert cache_stats["rect_dp_v3_fallbacks"] == 0
    assert routed == expected


def test_compact_rect_cpsat_v2_falls_back_to_v3_explicitly_for_dense_3x3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()

    shape_3x3 = tuple((x_val, y_val) for x_val in range(3) for y_val in range(3))
    model._local_shape_by_template_token["uniform_3x3"] = {0: shape_3x3}
    model._local_rectangle_variant_by_template_token.pop("uniform_3x3", None)
    compact_signature_dense_3x3 = tuple(
        sorted(
            [
                (x_val, y_val, 0)
                for x_val in range(14)
                for y_val in range(14)
            ]
        )
    )
    expected = model._solve_exact_local_power_capacity_rectangle_frontier_dp_v3(
        "uniform_3x3",
        compact_signature_dense_3x3,
        scan_axis="row",
    )

    def _force_fallback(*args: object, **kwargs: object) -> int:
        raise _CompactRectCpSatFallback("forced_for_test")

    monkeypatch.setattr(
        model,
        "_solve_exact_local_power_capacity_compact_rect_cpsat",
        _force_fallback,
    )
    cache_stats = {
        "compact_rect_cpsat_evaluations": 0,
        "compact_rect_cpsat_cache_hits": 0,
        "compact_rect_cpsat_selected_cases": 0,
        "compact_rect_cpsat_rect_dp_fallbacks": 0,
        "rect_dp_evaluations": 0,
        "rect_dp_v3_fallbacks": 0,
        "uniform_3x3_cpsat_evaluations": 0,
        "uniform_3x3_cpsat_cache_hits": 0,
        "uniform_3x3_cpsat_selected_cases": 0,
        "uniform_3x3_cpsat_v3_fallbacks": 0,
    }

    routed = model._solve_exact_local_power_capacity(
        "uniform_3x3",
        model._materialize_local_power_capacity_signature_from_compact(
            "uniform_3x3",
            compact_signature_dense_3x3,
        ),
        compact_signature=compact_signature_dense_3x3,
        cache_stats=cache_stats,
    )

    assert cache_stats["compact_rect_cpsat_selected_cases"] == 1
    assert cache_stats["compact_rect_cpsat_rect_dp_fallbacks"] == 1
    assert cache_stats["rect_dp_evaluations"] == 1
    assert cache_stats["uniform_3x3_cpsat_selected_cases"] == 1
    assert cache_stats["uniform_3x3_cpsat_v3_fallbacks"] == 1
    assert cache_stats["rect_dp_v3_fallbacks"] == 1
    assert routed == expected


def test_exact_local_power_capacity_rect_dp_falls_back_to_bitset_then_cpsat_without_losing_exactness() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()
    model.build()
    non_rect_tpl = "non_rectangles"
    l_shape = ((0, 0), (1, 0), (1, 1))
    model._local_shape_by_template_token[non_rect_tpl] = {0: l_shape}
    model._local_rectangle_variant_by_template_token.pop(non_rect_tpl, None)
    compact_signature = tuple(sorted([(0, 0, 0), (2, 0, 0)]))
    legacy_signature = model._materialize_local_power_capacity_signature_from_compact(
        non_rect_tpl,
        compact_signature,
    )

    _LOCAL_POWER_CAPACITY_CACHE.clear()
    _LOCAL_POWER_CAPACITY_COMPACT_CACHE.clear()
    _LOCAL_POWER_CAPACITY_RECT_DP_CACHE.clear()
    model._local_power_capacity_bitset_max_iterations = 0
    cache_stats = {
        "legacy_signature_materializations": 0,
        "compact_rect_cpsat_evaluations": 0,
        "compact_rect_cpsat_cache_hits": 0,
        "compact_rect_cpsat_selected_cases": 0,
        "compact_rect_cpsat_rect_dp_fallbacks": 0,
        "rect_dp_evaluations": 0,
        "rect_dp_cache_hits": 0,
        "rect_dp_cache_misses": 0,
        "bitset_oracle_evaluations": 0,
        "bitset_fallbacks": 0,
        "cpsat_fallbacks": 0,
    }

    exact_capacity = model._solve_exact_local_power_capacity_from_compact(
        non_rect_tpl,
        compact_signature,
        cache_stats=cache_stats,
    )

    assert cache_stats["compact_rect_cpsat_evaluations"] == 0
    assert cache_stats["compact_rect_cpsat_cache_hits"] == 0
    assert cache_stats["compact_rect_cpsat_selected_cases"] == 0
    assert cache_stats["compact_rect_cpsat_rect_dp_fallbacks"] == 0
    assert cache_stats["rect_dp_evaluations"] == 0
    assert cache_stats["rect_dp_cache_hits"] == 0
    assert cache_stats["rect_dp_cache_misses"] == 0
    assert cache_stats["bitset_fallbacks"] == 1
    assert cache_stats["bitset_oracle_evaluations"] == 1
    assert cache_stats["cpsat_fallbacks"] == 1
    assert cache_stats["legacy_signature_materializations"] == 1
    assert exact_capacity == model._solve_exact_local_power_capacity_cpsat(
        non_rect_tpl,
        legacy_signature,
    )


def test_exact_search_guidance_orders_residual_power_poles_by_family() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model()

    model.build()

    guidance = model.build_stats["search_guidance"]
    family_stats = model.build_stats["global_valid_inequalities"]["power_capacity_families"]
    assert guidance["profile"] == "exact_coordinate_guided_branching_v4"
    assert guidance["power_pole_family_count_literals"] == family_stats["family_count"]
    assert guidance["power_pole_family_order"] == [
        family["family_id"] for family in family_stats["families"]
    ]
    assert guidance["residual_optional_family_guided"] is True

    status = model.solve(time_limit_seconds=5.0)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    delegate = model._coordinate_delegate
    assert delegate is not None
    pole_slots = delegate.residual_optional_slots["power_pole"]
    active_slots = [
        slot
        for slot in pole_slots
        if slot.active is not None and model._solver.Value(slot.active) == 1
    ]
    active_family_ints = [model._solver.Value(slot.family) for slot in active_slots if slot.family is not None]
    assert active_family_ints == sorted(active_family_ints)

    for left_slot, right_slot in zip(active_slots, active_slots[1:]):
        left_family = model._solver.Value(left_slot.family)
        right_family = model._solver.Value(right_slot.family)
        assert left_family <= right_family
        if left_family == right_family:
            assert model._solver.Value(left_slot.order_key) <= model._solver.Value(right_slot.order_key)

    active_family_counts: dict[str, int] = {}
    for slot in active_slots:
        family_int = model._solver.Value(slot.family)
        family_name = slot.family_id_to_family_name[family_int]
        active_family_counts[family_name] = active_family_counts.get(family_name, 0) + 1

    for family_name, count_var in delegate.power_pole_family_count_vars.items():
        assert model._solver.Value(count_var) == active_family_counts.get(family_name, 0)


def test_exact_geometric_power_coverage_uses_witness_indices_and_reuses_one_pole() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_geometric_power_coverage_model()

    model.build()

    power_coverage = model.build_stats["power_coverage"]
    assert power_coverage == {
        "representation": "coordinate_geometric",
        "encoding": "geometric_element_witness_v1",
        "powered_slots": 2,
        "pole_slots": 2,
        "cover_literals": 0,
        "witness_indices": 2,
        "element_constraints": 6,
        "radius": 1,
    }

    status = model.solve(time_limit_seconds=5.0)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    solution = model.extract_solution()
    active_poles = [
        entry for entry in solution.values() if str(entry.get("facility_type")) == "power_pole"
    ]
    assert len(active_poles) == 1
    assert {str(entry["pose_id"]) for entry in active_poles} == {"pole_center"}


def test_exact_power_capacity_lower_bound_excludes_pole_overlapping_pose() -> None:
    _clear_local_power_capacity_caches()
    instances = [
        {
            "instance_id": "powered_001",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "power_pole": [
            {
                "pose_id": "pole_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0], [1, 0]],
            }
        ],
        "protocol_storage_box": [],
        "powered_machine": [
            {
                "pose_id": "machine_overlap",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "machine_safe",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
    }
    rules = {
        "globals": {"grid": {"width": 2, "height": 1}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "powered_machine": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }

    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
    )
    model.build()

    assert model._power_coverers_by_template_pose["powered_machine"][0] == []
    assert model._power_coverers_by_template_pose["powered_machine"][1] == [0]
    assert model.build_stats["global_valid_inequalities"]["capacity_coeff_stats"]["powered_machine"] == {
        "demand": 1,
        "total_poles": 1,
        "nonzero_poles": 1,
        "max_coeff": 1,
        "min_nonzero_coeff": 1,
    }


def test_index_pools_anchor_shape_coverer_dedup_fans_out_to_pose_and_pole_views() -> None:
    _clear_local_power_capacity_caches()
    model = MasterPlacementModel(
        instances=[
            {
                "instance_id": "powered_001",
                "facility_type": "powered_machine",
                "operation_type": "processing",
                "is_mandatory": True,
                "bound_type": "exact",
            }
        ],
        facility_pools={
            "power_pole": [
                {
                    "pose_id": "pole_0",
                    "anchor": {"x": 0, "y": 0},
                    "occupied_cells": [[0, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": [[1, 1]],
                }
            ],
            "protocol_storage_box": [],
            "powered_machine": [
                {
                    "pose_id": "machine_east",
                    "anchor": {"x": 1, "y": 1},
                    "pose_params": {"port_mode": "east"},
                    "occupied_cells": [[1, 1]],
                    "input_port_cells": [{"x": 2, "y": 1, "dir": "E"}],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                },
                {
                    "pose_id": "machine_north",
                    "anchor": {"x": 1, "y": 1},
                    "pose_params": {"port_mode": "north"},
                    "occupied_cells": [[1, 1]],
                    "input_port_cells": [{"x": 1, "y": 2, "dir": "N"}],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                },
            ],
        },
        rules={
            "globals": {"grid": {"width": 4, "height": 4}},
            "facility_templates": {
                "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
                "powered_machine": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            },
        },
        solve_mode="certified_exact",
    )

    model._index_pools()

    assert (
        model._pose_local_shape_token_by_template_pose["powered_machine"][0]
        == model._pose_local_shape_token_by_template_pose["powered_machine"][1]
    )
    assert (
        model._pose_local_fronts_by_template_pose["powered_machine"][0]
        != model._pose_local_fronts_by_template_pose["powered_machine"][1]
    )
    assert model._power_coverers_by_template_pose["powered_machine"][0] == [0]
    assert model._power_coverers_by_template_pose["powered_machine"][1] == [0]
    assert "powered_machine" not in model._power_supported_pose_indices_by_template_pole
    assert (
        model._ensure_power_supported_pose_indices_by_template_pole("powered_machine")[0]
        == [0, 1]
    )


def test_exact_optional_cardinality_bound_fixes_protocol_storage_box_count() -> None:
    instances = []
    pools = {
        "power_pole": [],
        "protocol_storage_box": [
            {
                "pose_id": "box_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [{"x": 0, "y": 1, "dir": "N"}],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "box_1",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [{"x": 2, "y": 1, "dir": "N"}],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
    }
    rules = {
        "globals": {"grid": {"width": 4, "height": 4}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }

    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        skip_power_coverage=True,
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1, "qiaoyu_capsule": 1},
        },
    )
    model.build()

    bounds = model.build_stats["global_valid_inequalities"]["optional_cardinality_bounds"]
    assert bounds["protocol_storage_box"] == {
        "mode": "required_lower_bound",
        "required_generic_input_slots": 2,
        "slots_per_pose": 3,
        "lower": 1,
        "upper": None,
        "candidate_pose_count": 2,
        "slot_pool_upper_bound": 2,
    }
    assert model.build_stats["master_slot_counts"]["required_optionals"] == {}
    assert model.build_stats["master_slot_counts"]["residual_optionals"]["protocol_storage_box"] == 2
    box_slots = model._coordinate_delegate.residual_optional_slots["protocol_storage_box"]
    for slot in box_slots:
        model.model.Add(slot.active == 1)
    assert model.solve(time_limit_seconds=5.0) in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    solution = model.extract_solution()
    protocol_boxes = [
        key for key in solution if key.startswith("pose_optional::protocol_storage_box::")
    ]
    assert protocol_boxes == [
        "pose_optional::protocol_storage_box::box_0",
        "pose_optional::protocol_storage_box::box_1",
    ]


def test_exact_optional_cardinality_bound_limits_power_poles_to_powered_facilities() -> None:
    instances = [
        {
            "instance_id": "powered_001",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "power_pole": [
            {
                "pose_id": f"pole_{idx}",
                "anchor": {"x": idx, "y": 0},
                "occupied_cells": [[idx, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[idx, 0]],
            }
            for idx in range(3)
        ],
        "protocol_storage_box": [
            {
                "pose_id": "box_0",
                "anchor": {"x": 4, "y": 0},
                "occupied_cells": [[4, 0]],
                "input_port_cells": [{"x": 4, "y": 1, "dir": "N"}],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
        "powered_machine": [
            {
                "pose_id": "machine_0",
                "anchor": {"x": 6, "y": 0},
                "occupied_cells": [[6, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
        ],
    }
    rules = {
        "globals": {"grid": {"width": 8, "height": 2}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "powered_machine": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }

    model = MasterPlacementModel(
        instances,
        pools,
        rules,
        solve_mode="certified_exact",
        skip_power_coverage=True,
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1},
        },
    )
    model.build()

    bounds = model.build_stats["global_valid_inequalities"]["optional_cardinality_bounds"]
    assert bounds["power_pole"] == {
        "mode": "selected_powered_upper_bound",
        "lower": 0,
        "candidate_pose_count": 3,
        "mandatory_powered_nonpole": 1,
        "optional_powered_templates": ["protocol_storage_box"],
        "slot_pool_upper_bound": 2,
    }
    assert model.build_stats["master_slot_counts"]["residual_optionals"]["power_pole"] == 2
    assert model.build_stats["master_pose_bool_literals"] == 0


def test_coordinate_exact_v2_emits_factorized_domain_and_shell_metadata() -> None:
    model = MasterPlacementModel(
        instances=[],
        facility_pools={
            "power_pole": [
                {
                    "pose_id": f"pole_{idx}",
                    "anchor": {"x": idx, "y": 0},
                    "occupied_cells": [[idx, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": [[idx, 0]],
                }
                for idx in range(3)
            ],
            "protocol_storage_box": [
                {
                    "pose_id": "box_0",
                    "anchor": {"x": 0, "y": 1},
                    "occupied_cells": [[0, 1]],
                    "input_port_cells": [{"x": 0, "y": 2, "dir": "N"}],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                }
            ],
        },
        rules={
            "globals": {"grid": {"width": 4, "height": 4}},
            "facility_templates": {
                "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            },
        },
        solve_mode="certified_exact",
        skip_power_coverage=True,
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1},
        },
    )

    model.build()

    assert model.build_stats["master_representation"] == "coordinate_exact_v2"
    assert model.build_stats["master_domain_encoding"] == "mode_rect_factorized_v1"
    assert model.build_stats["master_domain_table_rows"] == 0
    assert model.build_stats["master_mode_rect_domains"]["required_optionals"] == {}
    assert "protocol_storage_box" in model.build_stats["master_mode_rect_domains"]["residual_optionals"]
    assert "power_pole" in model.build_stats["master_mode_rect_domains"]["residual_optionals"]
    assert "pair_count" in model.build_stats["power_pole_shell_lookup_pairs"]
    assert model.build_stats["power_family_lookup_encoding"]["encoding"] == "table"
    assert "table_constraint_count" in model.build_stats["power_family_lookup_encoding"]
    assert model.build_stats["power_pole_shell_distance_encoding"]["encoding"] == "element"
    assert "element_constraint_count" in model.build_stats["power_pole_shell_distance_encoding"]


def test_coordinate_exact_power_family_lookup_linear_shell_guard_encoding(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_FAMILY_LOOKUP_ENCODING_ENV,
        exact_coordinate_master_module.EXACT_POWER_FAMILY_LOOKUP_ENCODING_LINEAR_SHELL_GUARDS,
    )
    model = MasterPlacementModel(
        instances=[],
        facility_pools={
            "power_pole": [
                {
                    "pose_id": f"pole_{idx}",
                    "anchor": {"x": idx, "y": 0},
                    "occupied_cells": [[idx, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": [[idx, 0]],
                }
                for idx in range(3)
            ],
            "protocol_storage_box": [
                {
                    "pose_id": "box_0",
                    "anchor": {"x": 0, "y": 1},
                    "occupied_cells": [[0, 1]],
                    "input_port_cells": [{"x": 0, "y": 2, "dir": "N"}],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                }
            ],
        },
        rules={
            "globals": {"grid": {"width": 4, "height": 4}},
            "facility_templates": {
                "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            },
        },
        solve_mode="certified_exact",
        skip_power_coverage=True,
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1},
        },
    )

    model.build()

    encoding = model.build_stats["power_family_lookup_encoding"]
    assert encoding["encoding"] == "linear_shell_guards"
    assert encoding["table_constraint_count"] == 0
    assert "linear_guard_constraint_count" in encoding
    assert "fallback_table_constraint_count" in encoding
    assert "family_lit_count" in encoding


def test_coordinate_exact_power_family_lookup_shell_pair_index_encoding(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_FAMILY_LOOKUP_ENCODING_ENV,
        exact_coordinate_master_module.EXACT_POWER_FAMILY_LOOKUP_ENCODING_SHELL_PAIR_INDEX,
    )
    model = MasterPlacementModel(
        instances=[],
        facility_pools={
            "power_pole": [
                {
                    "pose_id": f"pole_{idx}",
                    "anchor": {"x": idx, "y": 0},
                    "occupied_cells": [[idx, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": [[idx, 0]],
                }
                for idx in range(3)
            ],
            "protocol_storage_box": [
                {
                    "pose_id": "box_0",
                    "anchor": {"x": 0, "y": 1},
                    "occupied_cells": [[0, 1]],
                    "input_port_cells": [{"x": 0, "y": 2, "dir": "N"}],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                }
            ],
        },
        rules={
            "globals": {"grid": {"width": 4, "height": 4}},
            "facility_templates": {
                "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            },
        },
        solve_mode="certified_exact",
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1},
        },
    )

    model.build()

    encoding = model.build_stats["power_family_lookup_encoding"]
    assert encoding["encoding"] == "shell_pair_index"
    assert "shell_pair_index_var_count" in encoding
    assert "shell_pair_table_constraint_count" in encoding
    assert "shell_pair_table_row_count" in encoding
    assert "shell_pair_element_constraint_count" in encoding
    assert encoding["table_constraint_count"] == 0


def test_coordinate_exact_rejects_unknown_power_family_lookup_encoding(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_FAMILY_LOOKUP_ENCODING_ENV,
        "bad_encoding",
    )

    with pytest.raises(ValueError, match="EXACT_POWER_FAMILY_LOOKUP_ENCODING"):
        exact_coordinate_master_module.resolve_exact_power_family_lookup_encoding()


def test_coordinate_exact_power_pole_shell_distance_linear_minmax_encoding(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_ENV,
        exact_coordinate_master_module.EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_LINEAR_MINMAX,
    )
    model = MasterPlacementModel(
        instances=[],
        facility_pools={
            "power_pole": [
                {
                    "pose_id": f"pole_{idx}",
                    "anchor": {"x": idx, "y": 0},
                    "occupied_cells": [[idx, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": [[idx, 0]],
                }
                for idx in range(3)
            ],
            "protocol_storage_box": [
                {
                    "pose_id": "box_0",
                    "anchor": {"x": 0, "y": 1},
                    "occupied_cells": [[0, 1]],
                    "input_port_cells": [{"x": 0, "y": 2, "dir": "N"}],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                }
            ],
        },
        rules={
            "globals": {"grid": {"width": 4, "height": 4}},
            "facility_templates": {
                "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            },
        },
        solve_mode="certified_exact",
        skip_power_coverage=True,
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1},
        },
    )

    model.build()

    encoding = model.build_stats["power_pole_shell_distance_encoding"]
    assert encoding["encoding"] == "linear_minmax"
    assert "linear_minmax_constraint_count" in encoding


def test_coordinate_exact_rejects_unknown_shell_distance_encoding(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING_ENV,
        "bad_encoding",
    )

    with pytest.raises(ValueError, match="EXACT_POWER_POLE_SHELL_DISTANCE_ENCODING"):
        exact_coordinate_master_module.resolve_exact_power_pole_shell_distance_encoding()


def test_coordinate_exact_power_coverage_block_element_witness_encoding(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_ENCODING_ENV,
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_ENCODING_BLOCK_ELEMENT,
    )
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE_ENV,
        "2",
    )
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES_ENV,
        "protocol_storage_box",
    )

    def coverage_cells(x0: int, y0: int) -> list[list[int]]:
        cells: list[list[int]] = []
        for cell_x in range(max(0, x0 - 1), min(5, x0 + 2) + 1):
            for cell_y in range(max(0, y0 - 1), min(2, y0 + 2) + 1):
                cells.append([cell_x, cell_y])
        return cells

    model = MasterPlacementModel(
        instances=[],
        facility_pools={
            "power_pole": [
                {
                    "pose_id": f"pole_{idx}",
                    "anchor": {"x": idx, "y": 0},
                    "occupied_cells": [[idx, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": coverage_cells(idx, 0),
                }
                for idx in range(4)
            ],
            "protocol_storage_box": [
                {
                    "pose_id": "box_0",
                    "anchor": {"x": 1, "y": 1},
                    "occupied_cells": [[1, 1]],
                    "input_port_cells": [{"x": 1, "y": 2, "dir": "N"}],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                }
            ],
        },
        rules={
            "globals": {"grid": {"width": 6, "height": 3}},
            "facility_templates": {
                "power_pole": {
                    "dimensions": {"w": 1, "h": 1},
                    "needs_power": False,
                    "power_coverage_radius": 1,
                },
                "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            },
        },
        solve_mode="certified_exact",
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1},
        },
    )

    model.build()

    power_coverage = model.build_stats["power_coverage"]
    witness = power_coverage["witness_encoding"]
    assert power_coverage["encoding"] == "geometric_block_element_witness_v1"
    assert witness["encoding"] == "block_element"
    assert witness["block_size"] == 2
    assert witness["block_templates"] == ["protocol_storage_box"]
    assert witness["block_witness_count"] == power_coverage["powered_slots"]
    assert witness["wide_witness_count"] == 0
    assert witness["final_target_channel_count"] == 3
    assert witness["wide_element_target_channel_count"] == 0
    assert witness["block_intermediate_target_channel_count"] == 3
    assert witness["block_element_constraint_count"] == power_coverage["element_constraints"]
    assert witness["template_counts"] == {"protocol_storage_box": {"block_element": 1}}


def _build_block64_power_coverage_equivalence_model(
    monkeypatch: pytest.MonkeyPatch,
    *,
    block_templates: str,
    covered: bool,
    block_geometry: str | None = None,
    pole_count: int | None = None,
) -> MasterPlacementModel:
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_ENCODING_ENV,
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_ENCODING_BLOCK_ELEMENT,
    )
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE_ENV,
        "64",
    )
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES_ENV,
        block_templates,
    )
    if block_geometry is None:
        monkeypatch.delenv(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV,
            raising=False,
        )
    else:
        monkeypatch.setenv(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV,
            block_geometry,
        )

    grid_w = max(6, int(pole_count or 2) + 4)
    grid_h = 4

    def coverage_cells(x0: int, y0: int) -> list[list[int]]:
        cells: list[list[int]] = []
        for cell_x in range(max(0, x0 - 1), min(grid_w - 1, x0 + 2) + 1):
            for cell_y in range(max(0, y0 - 1), min(grid_h - 1, y0 + 2) + 1):
                cells.append([cell_x, cell_y])
        return cells

    if pole_count is None:
        pole_xs = [0, 1] if covered else [5]
    elif covered:
        pole_xs = list(range(int(pole_count)))
    else:
        pole_xs = [max(5, int(pole_count) + 2)]
    model = MasterPlacementModel(
        instances=[
            {
                "instance_id": "machine_0",
                "facility_type": "manufacturing_3x3",
                "operation_type": "manufacturing_3x3",
                "is_mandatory": True,
                "bound_type": "exact",
            }
        ],
        facility_pools={
            "power_pole": [
                {
                    "pose_id": f"pole_{idx}",
                    "anchor": {"x": x_value, "y": 0},
                    "occupied_cells": [[x_value, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": coverage_cells(x_value, 0),
                }
                for idx, x_value in enumerate(pole_xs)
            ],
            "manufacturing_3x3": [
                {
                    "pose_id": "machine_pose",
                    "anchor": {"x": 1, "y": 1},
                    "occupied_cells": [[1, 1]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                }
            ],
            "protocol_storage_box": [
                {
                    "pose_id": "box_0",
                    "anchor": {"x": 2, "y": 1},
                    "occupied_cells": [[2, 1]],
                    "input_port_cells": [{"x": 2, "y": 2, "dir": "N"}],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                }
            ],
        },
        rules={
            "globals": {"grid": {"width": grid_w, "height": grid_h}},
            "facility_templates": {
                "power_pole": {
                    "dimensions": {"w": 1, "h": 1},
                    "needs_power": False,
                    "power_coverage_radius": 1,
                },
                "manufacturing_3x3": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
                "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            },
        },
        solve_mode="certified_exact",
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1},
        },
    )
    model.build()
    return model


def test_coordinate_exact_power_coverage_block64_all_template_is_default_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_ENCODING_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_TEMPLATES_ENV,
        raising=False,
    )
    monkeypatch.delenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV,
        raising=False,
    )

    assert (
        exact_coordinate_master_module.resolve_exact_power_coverage_witness_encoding()
        == exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_ENCODING_ELEMENT
    )
    assert exact_coordinate_master_module.resolve_exact_power_coverage_witness_block_size() == 128
    assert exact_coordinate_master_module.resolve_exact_power_coverage_witness_block_templates() == set()
    assert (
        exact_coordinate_master_module.resolve_exact_power_coverage_witness_block_geometry()
        == exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_FINAL_TARGET
    )
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV,
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD,
    )
    assert (
        exact_coordinate_master_module.resolve_exact_power_coverage_witness_block_geometry()
        == exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD
    )
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV,
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_GROUPED_XY,
    )
    assert (
        exact_coordinate_master_module.resolve_exact_power_coverage_witness_block_geometry()
        == exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_GROUPED_XY
    )
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV,
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_JOINED_XY,
    )
    assert (
        exact_coordinate_master_module.resolve_exact_power_coverage_witness_block_geometry()
        == exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_JOINED_XY
    )


def test_coordinate_exact_power_coverage_block64_all_template_profile_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protocol_only_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="protocol_storage_box",
        covered=True,
    )
    all_template_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=True,
    )

    protocol_only = protocol_only_model.build_stats["power_coverage"]
    all_template = all_template_model.build_stats["power_coverage"]
    protocol_witness = protocol_only["witness_encoding"]
    all_template_witness = all_template["witness_encoding"]

    assert protocol_only["powered_slots"] == all_template["powered_slots"] == 2
    assert protocol_only["pole_slots"] == all_template["pole_slots"] == 2
    assert protocol_only["witness_indices"] == all_template["witness_indices"] == 2
    assert protocol_only["cover_literals"] == all_template["cover_literals"] == 0
    assert protocol_witness["encoding"] == all_template_witness["encoding"] == "block_element"
    assert protocol_witness["block_size"] == all_template_witness["block_size"] == 64

    assert protocol_only["encoding"] == "geometric_mixed_block_element_witness_v1"
    assert protocol_witness["block_templates"] == ["protocol_storage_box"]
    assert protocol_witness["template_counts"] == {
        "manufacturing_3x3": {"wide_element": 1},
        "protocol_storage_box": {"block_element": 1},
    }
    assert protocol_witness["block_witness_count"] == 1
    assert protocol_witness["wide_witness_count"] == 1

    assert all_template["encoding"] == "geometric_block_element_witness_v1"
    assert all_template_witness["block_templates"] == []
    assert all_template_witness["template_counts"] == {
        "manufacturing_3x3": {"block_element": 1},
        "protocol_storage_box": {"block_element": 1},
    }
    assert all_template_witness["block_witness_count"] == 2
    assert all_template_witness["wide_witness_count"] == 0


def test_coordinate_exact_power_coverage_block_selected_geometry_profile_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    final_target_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=True,
    )
    selected_block_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=True,
        block_geometry=(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK
        ),
    )

    final_witness = final_target_model.build_stats["power_coverage"]["witness_encoding"]
    selected_witness = selected_block_model.build_stats["power_coverage"]["witness_encoding"]

    assert final_witness["block_geometry_mode"] == "final_target"
    assert selected_witness["block_geometry_mode"] == "selected_block"
    assert final_witness["final_target_channel_count"] == 6
    assert selected_witness["final_target_channel_count"] == 0
    assert final_witness["block_final_join_element_constraint_count"] == 6
    assert selected_witness["block_final_join_element_constraint_count"] == 0
    assert final_witness["block_element_constraint_count"] == 12
    assert selected_witness["block_element_constraint_count"] == 6
    assert selected_witness["block_intermediate_target_channel_count"] == 6
    assert selected_witness["block_selected_literal_count"] == 2
    assert selected_witness["block_selected_channel_constraint_count"] == 4
    assert selected_witness["block_selected_geometry_constraint_count"] == 10


def test_coordinate_exact_power_coverage_block_active_guard_profile_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active_guard_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=True,
        block_geometry=(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD
        ),
    )

    active_guard_witness = active_guard_model.build_stats["power_coverage"][
        "witness_encoding"
    ]
    proto = active_guard_model.model.Proto()
    variable_names = {variable.name for variable in proto.variables}

    assert active_guard_witness["block_geometry_mode"] == "selected_block_active_guard"
    assert active_guard_witness["final_target_channel_count"] == 0
    assert active_guard_witness["block_final_join_element_constraint_count"] == 0
    assert active_guard_witness["block_element_constraint_count"] == 4
    assert active_guard_witness["block_intermediate_target_channel_count"] == 4
    assert active_guard_witness["block_selected_literal_count"] == 2
    assert active_guard_witness["block_selected_channel_constraint_count"] == 4
    assert active_guard_witness["block_selected_geometry_constraint_count"] == 8
    assert active_guard_witness["local_selected_literal_count"] == 128
    assert active_guard_witness["local_selected_channel_constraint_count"] == 256
    assert active_guard_witness["block_active_guard_clause_count"] == 128
    assert not any(
        name.startswith("cover_choice_block_active__") for name in variable_names
    )
    assert any(
        name.startswith("cover_choice_local_selected__") for name in variable_names
    )


def test_coordinate_exact_power_coverage_grouped_xy_profile_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active_guard_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=True,
        pole_count=65,
        block_geometry=(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD
        ),
    )
    grouped_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=True,
        pole_count=65,
        block_geometry=(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_GROUPED_XY
        ),
    )

    active_guard_witness = active_guard_model.build_stats["power_coverage"][
        "witness_encoding"
    ]
    grouped_witness = grouped_model.build_stats["power_coverage"][
        "witness_encoding"
    ]
    proto = grouped_model.model.Proto()
    variable_names = {variable.name for variable in proto.variables}

    assert grouped_witness["block_geometry_mode"] == "selected_block_active_guard_grouped_xy"
    assert grouped_witness["final_target_channel_count"] == 0
    assert grouped_witness["block_final_join_element_constraint_count"] == 0
    assert grouped_witness["block_intermediate_target_channel_count"] == 4
    assert grouped_witness["block_element_constraint_count"] == 4
    assert grouped_witness["grouped_xy_target_channel_count"] == 4
    assert grouped_witness["grouped_xy_element_constraint_count"] == 4
    assert grouped_witness["grouped_xy_padded_index_constraint_count"] == 2
    assert grouped_witness["grouped_xy_selected_geometry_constraint_count"] == 8
    assert grouped_witness["block_selected_literal_count"] == active_guard_witness[
        "block_selected_literal_count"
    ]
    assert grouped_witness["local_selected_literal_count"] == active_guard_witness[
        "local_selected_literal_count"
    ]
    assert grouped_witness["block_active_guard_clause_count"] == active_guard_witness[
        "block_active_guard_clause_count"
    ]
    assert grouped_witness["block_selected_geometry_constraint_count"] == 0
    assert (
        grouped_witness["grouped_xy_selected_geometry_constraint_count"]
        == active_guard_witness["block_selected_geometry_constraint_count"]
    )
    assert not any(
        name.startswith("cover_choice_block_x__") for name in variable_names
    )
    assert not any(
        name.startswith("cover_choice_block_y__") for name in variable_names
    )
    assert not any(
        name.startswith("cover_choice_block_active__") for name in variable_names
    )
    assert any(
        name.startswith("cover_choice_grouped_x__") for name in variable_names
    )
    assert any(
        name.startswith("cover_choice_grouped_y__") for name in variable_names
    )


def test_coordinate_exact_power_coverage_joined_xy_profile_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active_guard_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=True,
        pole_count=65,
        block_geometry=(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD
        ),
    )
    joined_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=True,
        pole_count=65,
        block_geometry=(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_JOINED_XY
        ),
    )

    active_guard_witness = active_guard_model.build_stats["power_coverage"][
        "witness_encoding"
    ]
    joined_witness = joined_model.build_stats["power_coverage"]["witness_encoding"]
    proto = joined_model.model.Proto()
    variable_names = {variable.name for variable in proto.variables}

    assert joined_witness["block_geometry_mode"] == "selected_block_active_guard_joined_xy"
    assert joined_witness["final_target_channel_count"] == 0
    assert joined_witness["block_final_join_element_constraint_count"] == 4
    assert joined_witness["block_intermediate_target_channel_count"] == active_guard_witness[
        "block_intermediate_target_channel_count"
    ]
    assert joined_witness["block_element_constraint_count"] == (
        active_guard_witness["block_element_constraint_count"] + 4
    )
    assert joined_witness["joined_xy_target_channel_count"] == 4
    assert joined_witness["joined_xy_element_constraint_count"] == 4
    assert joined_witness["joined_xy_selected_geometry_constraint_count"] == 8
    assert joined_witness["grouped_xy_padded_index_constraint_count"] == 0
    assert joined_witness["block_selected_literal_count"] == active_guard_witness[
        "block_selected_literal_count"
    ]
    assert joined_witness["local_selected_literal_count"] == active_guard_witness[
        "local_selected_literal_count"
    ]
    assert joined_witness["block_active_guard_clause_count"] == active_guard_witness[
        "block_active_guard_clause_count"
    ]
    assert joined_witness["block_selected_geometry_constraint_count"] == 0
    assert (
        joined_witness["joined_xy_selected_geometry_constraint_count"]
        == active_guard_witness["block_selected_geometry_constraint_count"]
    )
    assert any(
        name.startswith("cover_choice_block_x__") for name in variable_names
    )
    assert any(
        name.startswith("cover_choice_block_y__") for name in variable_names
    )
    assert any(
        name.startswith("cover_choice_joined_x__") for name in variable_names
    )
    assert any(
        name.startswith("cover_choice_joined_y__") for name in variable_names
    )
    assert not any(
        name.startswith("cover_choice_padded_idx__") for name in variable_names
    )
    assert not any(
        name.startswith("cover_choice_grouped_x__") for name in variable_names
    )
    assert not any(
        name.startswith("cover_choice_grouped_y__") for name in variable_names
    )
    assert not any(name.startswith("cover_literal__") for name in variable_names)
    assert not any(name.startswith("covers__") for name in variable_names)
    assert not any(
        name.startswith("cover_choice_block_active__") for name in variable_names
    )


@pytest.mark.parametrize(
    ("covered", "expected_status"),
    [
        (True, {cp_model.OPTIMAL, cp_model.FEASIBLE}),
        (False, {cp_model.INFEASIBLE}),
    ],
)
def test_coordinate_exact_power_coverage_block64_all_template_matches_protocol_only_feasibility(
    monkeypatch: pytest.MonkeyPatch,
    covered: bool,
    expected_status: set[int],
) -> None:
    protocol_only_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="protocol_storage_box",
        covered=covered,
    )
    all_template_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=covered,
    )

    protocol_status = protocol_only_model.solve(time_limit_seconds=2.0)
    all_template_status = all_template_model.solve(time_limit_seconds=2.0)

    assert protocol_status in expected_status
    assert all_template_status in expected_status


@pytest.mark.parametrize(
    ("covered", "expected_status"),
    [
        (True, {cp_model.OPTIMAL, cp_model.FEASIBLE}),
        (False, {cp_model.INFEASIBLE}),
    ],
)
def test_coordinate_exact_power_coverage_selected_block_matches_final_target_feasibility(
    monkeypatch: pytest.MonkeyPatch,
    covered: bool,
    expected_status: set[int],
) -> None:
    final_target_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=covered,
    )
    selected_block_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=covered,
        block_geometry=(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK
        ),
    )

    final_target_status = final_target_model.solve(time_limit_seconds=2.0)
    selected_block_status = selected_block_model.solve(time_limit_seconds=2.0)

    assert final_target_status in expected_status
    assert selected_block_status in expected_status


@pytest.mark.parametrize(
    ("covered", "expected_status"),
    [
        (True, {cp_model.OPTIMAL, cp_model.FEASIBLE}),
        (False, {cp_model.INFEASIBLE}),
    ],
)
def test_coordinate_exact_power_coverage_active_guard_matches_selected_block_feasibility(
    monkeypatch: pytest.MonkeyPatch,
    covered: bool,
    expected_status: set[int],
) -> None:
    selected_block_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=covered,
        block_geometry=(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK
        ),
    )
    active_guard_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=covered,
        block_geometry=(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD
        ),
    )

    selected_block_status = selected_block_model.solve(time_limit_seconds=2.0)
    active_guard_status = active_guard_model.solve(time_limit_seconds=2.0)

    assert selected_block_status in expected_status
    assert active_guard_status in expected_status


@pytest.mark.parametrize(
    ("covered", "expected_status"),
    [
        (True, {cp_model.OPTIMAL, cp_model.FEASIBLE}),
        (False, {cp_model.INFEASIBLE}),
    ],
)
def test_coordinate_exact_power_coverage_grouped_xy_matches_active_guard_feasibility(
    monkeypatch: pytest.MonkeyPatch,
    covered: bool,
    expected_status: set[int],
) -> None:
    active_guard_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=covered,
        block_geometry=(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD
        ),
    )
    grouped_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=covered,
        block_geometry=(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_GROUPED_XY
        ),
    )

    active_guard_status = active_guard_model.solve(time_limit_seconds=2.0)
    grouped_status = grouped_model.solve(time_limit_seconds=2.0)

    assert active_guard_status in expected_status
    assert grouped_status in expected_status


@pytest.mark.parametrize(
    ("covered", "expected_status"),
    [
        (True, {cp_model.OPTIMAL, cp_model.FEASIBLE}),
        (False, {cp_model.INFEASIBLE}),
    ],
)
def test_coordinate_exact_power_coverage_joined_xy_matches_active_guard_feasibility(
    monkeypatch: pytest.MonkeyPatch,
    covered: bool,
    expected_status: set[int],
) -> None:
    active_guard_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=covered,
        block_geometry=(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD
        ),
    )
    joined_model = _build_block64_power_coverage_equivalence_model(
        monkeypatch,
        block_templates="",
        covered=covered,
        block_geometry=(
            exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_SELECTED_BLOCK_ACTIVE_GUARD_JOINED_XY
        ),
    )

    active_guard_status = active_guard_model.solve(time_limit_seconds=2.0)
    joined_status = joined_model.solve(time_limit_seconds=2.0)

    assert active_guard_status in expected_status
    assert joined_status in expected_status


def test_coordinate_exact_rejects_unknown_power_coverage_witness_encoding(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_ENCODING_ENV,
        "bad_encoding",
    )

    with pytest.raises(ValueError, match="EXACT_POWER_COVERAGE_WITNESS_ENCODING"):
        exact_coordinate_master_module.resolve_exact_power_coverage_witness_encoding()


def test_coordinate_exact_rejects_unknown_power_coverage_block_geometry(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY_ENV,
        "bad_geometry",
    )

    with pytest.raises(ValueError, match="EXACT_POWER_COVERAGE_WITNESS_BLOCK_GEOMETRY"):
        exact_coordinate_master_module.resolve_exact_power_coverage_witness_block_geometry()


def test_coordinate_exact_rejects_too_small_power_coverage_block_size(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE_ENV,
        "1",
    )

    with pytest.raises(ValueError, match="EXACT_POWER_COVERAGE_WITNESS_BLOCK_SIZE"):
        exact_coordinate_master_module.resolve_exact_power_coverage_witness_block_size()


def test_family_shell_guard_constraints_match_allowed_rows() -> None:
    rows = [(0, 0), (0, 1), (1, 1)]
    for d_lo in range(3):
        for d_hi in range(3):
            expected = (d_lo, d_hi) in rows
            assert _shell_guard_pair_feasible(rows, d_lo, d_hi) is expected


@pytest.mark.parametrize(
    ("rows", "expected_shape", "allowed_pairs", "rejected_pairs"),
    [
        ([(2, 3)], "single", [(2, 3)], [(2, 2), (3, 3)]),
        (
            [(1, 2), (1, 3), (2, 2), (2, 3)],
            "rectangle",
            [(1, 2), (2, 3)],
            [(0, 2), (1, 4), (2, 1)],
        ),
        (
            [(0, 0), (0, 1), (0, 2), (1, 1), (1, 2), (2, 2)],
            "upper_triangle",
            [(0, 2), (1, 1), (2, 2)],
            [(1, 0), (2, 0), (2, 1)],
        ),
        (
            [(0, 2), (2, 0), (2, 2)],
            "fallback_table",
            [(0, 2), (2, 0), (2, 2)],
            [(0, 0), (1, 1), (1, 2)],
        ),
    ],
)
def test_family_shell_guard_shapes_preserve_allowed_pairs_and_reject_invalid_pairs(
    rows: Sequence[Sequence[int]],
    expected_shape: str,
    allowed_pairs: Sequence[tuple[int, int]],
    rejected_pairs: Sequence[tuple[int, int]],
) -> None:
    shape = exact_coordinate_master_module.family_shell_guard_shape(rows)

    assert shape["kind"] == expected_shape
    for d_lo, d_hi in allowed_pairs:
        assert _shell_guard_pair_feasible(rows, d_lo, d_hi)
    for d_lo, d_hi in rejected_pairs:
        assert not _shell_guard_pair_feasible(rows, d_lo, d_hi)


def test_linear_minmax_shell_distance_matches_lookup_formula() -> None:
    for x_value in range(2, 8):
        expected = min(x_value - 2, 7 - x_value)
        assert _linear_minmax_distance_value(2, 7, x_value) == expected


@pytest.mark.parametrize(
    ("x_value", "y_value"),
    [(2, 1), (3, 2), (4, 3), (6, 4), (7, 5)],
)
def test_linear_minmax_shell_distance_pair_rejects_wrong_distances(
    x_value: int,
    y_value: int,
) -> None:
    expected_dx = min(x_value - 2, 7 - x_value)
    expected_dy = min(y_value - 1, 5 - y_value)

    assert _linear_minmax_distance_pair_feasible(
        x_min=2,
        x_max=7,
        y_min=1,
        y_max=5,
        x_value=x_value,
        y_value=y_value,
        dx_value=expected_dx,
        dy_value=expected_dy,
    )
    assert not _linear_minmax_distance_pair_feasible(
        x_min=2,
        x_max=7,
        y_min=1,
        y_max=5,
        x_value=x_value,
        y_value=y_value,
        dx_value=expected_dx + 1,
        dy_value=expected_dy,
    )
    assert not _linear_minmax_distance_pair_feasible(
        x_min=2,
        x_max=7,
        y_min=1,
        y_max=5,
        x_value=x_value,
        y_value=y_value,
        dx_value=expected_dx,
        dy_value=expected_dy + 1,
    )


def _rectangular_power_coverage_cells(
    *,
    x0: int,
    y0: int,
    radius: int,
    grid_w: int,
    grid_h: int,
) -> list[list[int]]:
    return [
        [int(cell_x), int(cell_y)]
        for cell_x in range(max(0, x0 - radius), min(grid_w - 1, x0 + 1 + radius) + 1)
        for cell_y in range(max(0, y0 - radius), min(grid_h - 1, y0 + 1 + radius) + 1)
    ]


def _build_power_coverage_selected_interval_fixture() -> MasterPlacementModel:
    grid_w = 4
    grid_h = 3
    radius = 1
    return MasterPlacementModel(
        instances=[],
        facility_pools={
            "power_pole": [
                {
                    "pose_id": "pole_0",
                    "anchor": {"x": 0, "y": 0},
                    "occupied_cells": [[0, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": _rectangular_power_coverage_cells(
                        x0=0,
                        y0=0,
                        radius=radius,
                        grid_w=grid_w,
                        grid_h=grid_h,
                    ),
                }
            ],
            "protocol_storage_box": [
                {
                    "pose_id": "box_0",
                    "anchor": {"x": 1, "y": 1},
                    "occupied_cells": [[1, 1]],
                    "input_port_cells": [{"x": 1, "y": 2, "dir": "N"}],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                }
            ],
        },
        rules={
            "globals": {"grid": {"width": grid_w, "height": grid_h}},
            "facility_templates": {
                "power_pole": {
                    "dimensions": {"w": 1, "h": 1},
                    "needs_power": False,
                    "power_coverage_radius": radius,
                },
                "protocol_storage_box": {
                    "dimensions": {"w": 1, "h": 1},
                    "needs_power": True,
                },
            },
        },
        solve_mode="certified_exact",
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1},
        },
    )


def test_power_coverage_selected_interval_encoding_defaults_to_bounds(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_ENV,
        raising=False,
    )
    model = _build_power_coverage_selected_interval_fixture()

    model.build()

    power_coverage = model.build_stats["power_coverage"]
    assert power_coverage["encoding"] == "geometric_element_witness_v1"
    assert "witness_encoding" not in power_coverage


def test_power_coverage_selected_interval_delta_encoding_is_default_off(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_ENV,
        exact_coordinate_master_module.EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_DELTA,
    )
    model = _build_power_coverage_selected_interval_fixture()

    model.build()

    stats = model.build_stats["power_coverage"]["witness_encoding"]
    assert stats["selected_interval_encoding"] == "delta"
    assert stats["selected_interval_delta_var_count"] == 2
    # P0-2 / B-01 fix: selected geometry now links the powered slot's x/y start
    # through footprint channels instead of slot.x/slot.y + template dims, so the
    # delta encoding emits the footprint-channel linking constraints in addition
    # to the two delta vars (var count unchanged at 2; constraint count 2 -> 6).
    assert stats["selected_interval_delta_constraint_count"] == 6
    assert stats["selected_interval_bounds_constraint_count"] == 0
    assert stats["final_target_channel_count"] == 3


def _selected_interval_projection_feasible(
    *,
    encoding: str,
    powered_x: int,
    powered_y: int,
    cover_x_value: int,
    cover_y_value: int,
    span_x: int,
    span_y: int,
    radius: int,
) -> bool:
    model = cp_model.CpModel()
    cover_x = model.NewIntVar(-20, 20, "cover_x")
    cover_y = model.NewIntVar(-20, 20, "cover_y")
    active = model.NewBoolVar("cover_choice_active")
    model.Add(active == 1)
    model.Add(cover_x == int(cover_x_value))
    model.Add(cover_y == int(cover_y_value))
    if encoding == exact_coordinate_master_module.EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_BOUNDS:
        model.Add(int(powered_x) <= cover_x + int(radius) + 1)
        model.Add(cover_x - int(radius) <= int(powered_x) + int(span_x) - 1)
        model.Add(int(powered_y) <= cover_y + int(radius) + 1)
        model.Add(cover_y - int(radius) <= int(powered_y) + int(span_y) - 1)
    elif encoding == exact_coordinate_master_module.EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_DELTA:
        dx = model.NewIntVar(1 - int(span_x) - int(radius), int(radius) + 1, "dx")
        dy = model.NewIntVar(1 - int(span_y) - int(radius), int(radius) + 1, "dy")
        model.Add(dx == int(powered_x) - cover_x)
        model.Add(dy == int(powered_y) - cover_y)
    else:  # pragma: no cover - defensive test helper guard
        raise AssertionError(f"unsupported encoding: {encoding}")
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 1
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model)
    return status in {cp_model.OPTIMAL, cp_model.FEASIBLE}


def test_power_coverage_selected_interval_delta_matches_bounds_projection() -> None:
    powered_x = 4
    powered_y = 5
    for span_x, span_y, radius in [(1, 1, 0), (1, 2, 1), (3, 1, 2)]:
        x_lower = 1 - span_x - radius
        x_upper = radius + 1
        y_lower = 1 - span_y - radius
        y_upper = radius + 1
        dx_values = [x_lower - 1, x_lower, 0, x_upper, x_upper + 1]
        dy_values = [y_lower - 1, y_lower, 0, y_upper, y_upper + 1]
        for dx in dx_values:
            for dy in dy_values:
                cover_x = powered_x - dx
                cover_y = powered_y - dy
                bounds_feasible = _selected_interval_projection_feasible(
                    encoding=exact_coordinate_master_module.EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_BOUNDS,
                    powered_x=powered_x,
                    powered_y=powered_y,
                    cover_x_value=cover_x,
                    cover_y_value=cover_y,
                    span_x=span_x,
                    span_y=span_y,
                    radius=radius,
                )
                delta_feasible = _selected_interval_projection_feasible(
                    encoding=exact_coordinate_master_module.EXACT_POWER_COVERAGE_SELECTED_INTERVAL_ENCODING_DELTA,
                    powered_x=powered_x,
                    powered_y=powered_y,
                    cover_x_value=cover_x,
                    cover_y_value=cover_y,
                    span_x=span_x,
                    span_y=span_y,
                    radius=radius,
                )
                assert delta_feasible == bounds_feasible


def test_exact_power_capacity_lower_bound_includes_protocol_storage_box_lower_bound_demand() -> None:
    _clear_local_power_capacity_caches()
    model = MasterPlacementModel(
        instances=[],
        facility_pools={
            "power_pole": [
                {
                    "pose_id": "pole_0",
                    "anchor": {"x": 0, "y": 0},
                    "occupied_cells": [[0, 0]],
                    "input_port_cells": [],
                    "output_port_cells": [],
                    "power_coverage_cells": [[1, 0]],
                }
            ],
            "protocol_storage_box": [
                {
                    "pose_id": "box_0",
                    "anchor": {"x": 1, "y": 0},
                    "occupied_cells": [[1, 0]],
                    "input_port_cells": [{"x": 1, "y": 1, "dir": "N"}],
                    "output_port_cells": [],
                    "power_coverage_cells": None,
                }
            ],
        },
        rules={
            "globals": {"grid": {"width": 3, "height": 2}},
            "facility_templates": {
                "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
                "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            },
        },
        solve_mode="certified_exact",
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {"valley_battery": 1},
        },
    )

    model.build()

    stats = model.build_stats["global_valid_inequalities"]
    assert model.build_stats["exact_required_optionals"] == {}
    assert model.build_stats["exact_optional_lower_bounds"] == {"protocol_storage_box": 1}
    assert stats["fixed_required_optional_demands"] == {}
    assert stats["lower_bound_optional_powered_demands"] == {"protocol_storage_box": 1}
    assert stats["powered_template_demands"] == {"protocol_storage_box": 1}
    assert stats["capacity_coeff_stats"]["protocol_storage_box"] == {
        "demand": 1,
        "total_poles": 1,
        "nonzero_poles": 1,
        "max_coeff": 1,
        "min_nonzero_coeff": 1,
    }
    assert {
        "type": "power_capacity_lower_bound",
        "template": "protocol_storage_box",
        "demand": 1,
        "nonzero_poles": 1,
    } in stats["applied"]
    assert stats["power_capacity_families"] == {
        "applied": True,
        "family_count": 1,
        "raw_pole_count": 1,
        "coefficient_source": "exact_compact_rect_cpsat_v14",
        "shell_pair_count": 1,
        "compact_signature_class_count": 1,
        "families": [
            {
                "family_id": "family_000",
                "size": 1,
                "count_var_upper_bound": 1,
                "coefficients": {"protocol_storage_box": 1},
            }
        ],
    }


def test_exploratory_mode_does_not_apply_exact_power_capacity_lower_bound() -> None:
    _clear_local_power_capacity_caches()
    model = _build_exact_power_capacity_model(solve_mode="exploratory")

    model.build()

    stats = model.build_stats["global_valid_inequalities"]
    assert stats["applied"] == []
    assert stats["powered_template_demands"] == {}
    assert stats["capacity_cache"]["pole_template_evaluations"] == 0
    assert stats["capacity_cache"]["signature_class_evaluations"] == 0
    assert stats["capacity_cache"]["compact_signature_class_evaluations"] == 0
    assert stats["capacity_cache"]["rect_dp_evaluations"] == 0
    assert stats["capacity_cache"]["bitset_oracle_evaluations"] == 0
    assert stats["capacity_cache"]["bitset_fallbacks"] == 0
    assert stats["capacity_cache"]["cpsat_fallbacks"] == 0
    assert stats["capacity_cache"]["raw_pole_evaluations"] == 0
    assert stats["capacity_cache"]["coefficient_source"] == "exact_compact_rect_cpsat_v14"


def _build_exact_core_reuse_fixture() -> tuple[
    list[dict[str, object]],
    dict[str, list[dict[str, object]]],
    dict[str, object],
]:
    instances: list[dict[str, object]] = [
        {
            "instance_id": "miner_001",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools: dict[str, list[dict[str, object]]] = {
        "miner": [
            {
                "pose_id": "pose_left",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "pose_mid",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ]
    }
    rules: dict[str, object] = {
        "globals": {"grid": {"width": 3, "height": 1}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    return instances, pools, rules


def _build_exact_core_power_capacity_screen_fixture() -> tuple[
    list[dict[str, object]],
    dict[str, list[dict[str, object]]],
    dict[str, object],
]:
    instances: list[dict[str, object]] = [
        {
            "instance_id": "powered_001",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "powered_002",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools: dict[str, list[dict[str, object]]] = {
        "power_pole": [
            {
                "pose_id": "pole_high",
                "anchor": {"x": 0, "y": 1},
                "occupied_cells": [[0, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0], [1, 0], [3, 0], [4, 0]],
            },
            {
                "pose_id": "pole_low",
                "anchor": {"x": 5, "y": 1},
                "occupied_cells": [[5, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0], [1, 0], [2, 0]],
            },
        ],
        "protocol_storage_box": [],
        "powered_machine": [
            {
                "pose_id": "machine_a",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0], [1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "machine_b",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0], [2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "machine_c",
                "anchor": {"x": 3, "y": 0},
                "occupied_cells": [[3, 0], [4, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
    }
    rules: dict[str, object] = {
        "globals": {"grid": {"width": 6, "height": 2}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "powered_machine": {"dimensions": {"w": 2, "h": 1}, "needs_power": True},
        },
    }
    return instances, pools, rules


def test_exact_core_clone_rebinds_solution_extraction_and_benders_cuts() -> None:
    instances, pools, rules = _build_exact_core_reuse_fixture()

    core = MasterPlacementModel.build_exact_core(
        instances,
        pools,
        rules,
        skip_power_coverage=True,
    )
    packaging_profile = core.build_stats["exact_core_packaging_profile"]
    assert packaging_profile["proto_storage_mode"] == "owned_proto"
    assert packaging_profile["facility_pools_snapshot_mode"] == "owned_model_reference"
    assert packaging_profile["coordinate_binding_snapshot_mode"] == "fresh_export"
    assert packaging_profile["packaging_seconds"] >= 0.0
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(overlay._ghost_domains)
        if domain["anchor"] == {"x": 2, "y": 0}
    )
    overlay.model.Add(overlay.u_vars[forced_anchor_idx] == 1)

    status = overlay.solve(time_limit_seconds=5.0)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    first_solution = overlay.extract_solution()
    first_pose_idx = int(first_solution["miner_001"]["pose_idx"])
    assert overlay.build_stats["exact_core_reuse"]["used"] is True
    assert overlay.build_stats["ghost_rect"]["size"] == {"w": 1, "h": 1}
    assert core.master_representation == "coordinate_exact_v2"
    assert overlay.build_stats["master_domain_table_rows"] == 0
    assert all("rank" not in binding for binding in core.coordinate_binding["slot_binding"].values())

    assert overlay.add_benders_cut({"miner_001": first_pose_idx}) is True
    status = overlay.solve(time_limit_seconds=5.0)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    second_solution = overlay.extract_solution()
    assert int(second_solution["miner_001"]["pose_idx"]) != first_pose_idx


def test_exact_core_overlay_rebuilds_search_guidance_after_ghost_overlay() -> None:
    instances, pools, rules = _build_exact_core_reuse_fixture()

    core = MasterPlacementModel.build_exact_core(
        instances,
        pools,
        rules,
        skip_power_coverage=True,
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))

    guidance = overlay.build_stats["search_guidance"]
    reuse_stats = overlay.build_stats["exact_core_reuse"]
    assert guidance["profile"] == "exact_coordinate_guided_branching_v4"
    assert guidance["ghost_literals"] == len(overlay.u_vars)
    assert guidance["ghost_literals"] > 0
    assert guidance["ghost_phase_index"] == 2
    assert reuse_stats["search_guidance_rebuilt_after_ghost_overlay"] is True
    assert reuse_stats["cleared_existing_search_strategy_count"] > 0
    assert reuse_stats["rebuilt_search_strategy_count"] == len(
        overlay.model.Proto().search_strategy
    )


def test_exact_core_overlay_reuse_does_not_corrupt_core_snapshot() -> None:
    instances, pools, rules = _build_exact_core_reuse_fixture()
    core = MasterPlacementModel.build_exact_core(
        instances,
        pools,
        rules,
        skip_power_coverage=True,
    )

    core_source_snapshot = json.dumps(list(core.source_instances), sort_keys=True)
    core_pool_snapshot = json.dumps(core.facility_pools, sort_keys=True)
    core_rules_snapshot = json.dumps(core.rules, sort_keys=True)
    core_group_snapshot = json.dumps(list(core.mandatory_groups), sort_keys=True)
    core_build_stats_snapshot = json.dumps(core.build_stats, sort_keys=True)
    core_proto_constraints = len(core.proto.constraints)

    overlay_a = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    overlay_b = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))

    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(overlay_a._ghost_domains)
        if domain["anchor"] == {"x": 2, "y": 0}
    )
    overlay_a.model.Add(overlay_a.u_vars[forced_anchor_idx] == 1)

    status_a = overlay_a.solve(time_limit_seconds=5.0)
    assert status_a in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    solution_a = overlay_a.extract_solution()
    pose_idx_a = int(solution_a["miner_001"]["pose_idx"])
    assert overlay_a.add_benders_cut({"miner_001": pose_idx_a}) is True
    status_a_after_cut = overlay_a.solve(time_limit_seconds=5.0)
    assert status_a_after_cut in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    status_b = overlay_b.solve(time_limit_seconds=5.0)
    assert status_b in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    overlay_b.extract_solution()

    overlay_a.build_stats["mutation_probe"] = {"changed": True}
    overlay_a._mandatory_groups[0]["instance_ids"].append("mutated_instance")

    assert "mutation_probe" not in core.build_stats
    assert "mutation_probe" not in overlay_b.build_stats
    assert json.dumps(list(core.mandatory_groups), sort_keys=True) == core_group_snapshot
    assert overlay_b._mandatory_groups[0]["instance_ids"] == ["miner_001"]
    assert json.dumps(list(core.source_instances), sort_keys=True) == core_source_snapshot
    assert json.dumps(core.facility_pools, sort_keys=True) == core_pool_snapshot
    assert json.dumps(core.rules, sort_keys=True) == core_rules_snapshot
    assert len(core.proto.constraints) == core_proto_constraints

    core_build_stats_after = json.loads(json.dumps(core.build_stats, sort_keys=True))
    core_build_stats_after.pop("exact_core_reuse", None)
    expected_build_stats = json.loads(core_build_stats_snapshot)
    expected_build_stats.pop("exact_core_reuse", None)
    assert core_build_stats_after == expected_build_stats


def test_exact_core_overlay_applies_ghost_anchor_power_capacity_screen() -> None:
    _clear_local_power_capacity_caches()
    instances, pools, rules = _build_exact_core_power_capacity_screen_fixture()

    core = MasterPlacementModel.build_exact_core(
        instances,
        pools,
        rules,
        skip_power_coverage=False,
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    stats = overlay.build_stats["global_valid_inequalities"]["ghost_aware_via_pole_feasibility"]

    assert overlay.build_stats["exact_core_reuse"]["used"] is True
    assert stats["enabled"] is True
    assert stats["explicit_u_conditioning"] is True
    assert stats["disabled_placements"] >= 1
    assert stats["conditioned_family_upper_bound_constraints"] > 0
    assert stats["family_reduction_anchor_count"] > 0
    assert stats["template_fail_counts"] == {"powered_machine": 1}

    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(overlay._ghost_domains)
        if domain["anchor"] == {"x": 0, "y": 1}
    )
    overlay.model.Add(overlay.u_vars[forced_anchor_idx] == 1)
    assert overlay.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_exact_core_overlay_applies_ghost_conditioned_family_upper_bounds() -> None:
    instances = [
        {
            "instance_id": "powered_001",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "powered_002",
            "facility_type": "powered_machine",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "power_pole": [
            {
                "pose_id": "pole_left",
                "anchor": {"x": 0, "y": 1},
                "occupied_cells": [[0, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[1, 0], [5, 0]],
            },
            {
                "pose_id": "pole_right",
                "anchor": {"x": 6, "y": 1},
                "occupied_cells": [[6, 1]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[1, 0], [5, 0]],
            },
        ],
        "protocol_storage_box": [],
        "powered_machine": [
            {
                "pose_id": "machine_left",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "machine_right",
                "anchor": {"x": 5, "y": 0},
                "occupied_cells": [[5, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
    }
    rules = {
        "globals": {"grid": {"width": 7, "height": 2}},
        "facility_templates": {
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "powered_machine": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }

    core = MasterPlacementModel.build_exact_core(
        instances,
        pools,
        rules,
        skip_power_coverage=False,
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    stats = overlay.build_stats["global_valid_inequalities"]["ghost_aware_via_pole_feasibility"]

    assert overlay.build_stats["exact_core_reuse"]["used"] is True
    assert stats["conditioned_family_upper_bound_constraints"] > 0
    assert stats["family_reduction_anchor_count"] > 0
    assert stats["disabled_placements"] == 0

    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(overlay._ghost_domains)
        if domain["anchor"] == {"x": 0, "y": 1}
    )
    family_name = next(iter(overlay._power_pole_family_count_vars))
    overlay.model.Add(overlay.u_vars[forced_anchor_idx] == 1)
    overlay.model.Add(overlay._power_pole_family_count_vars[family_name] >= 2)
    assert overlay.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_exact_core_overlay_applies_ghost_conditioned_mandatory_signature_bucket_upper_bounds() -> None:
    base_model = _build_exact_mandatory_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    signature_stats = overlay.build_stats["global_valid_inequalities"]["signature_bucket_capacity_bounds"]

    assert overlay.build_stats["exact_core_reuse"]["used"] is True
    assert signature_stats["ghost_conditioned_mandatory_bucket_constraints"] > 0
    assert signature_stats["ghost_signature_reduction_anchor_count"] > 0

    group_payload = next(
        payload
        for payload in signature_stats["mandatory_groups"]
        if payload["group_id"] == "group::router::routing::0"
    )
    constrained_bucket_id = next(
        bucket["bucket_id"]
        for bucket in group_payload["buckets"]
        if bucket["count_var_upper_bound"] == 1
    )
    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(overlay._ghost_domains)
        if domain["anchor"] == {"x": 2, "y": 0}
    )
    overlay.model.Add(overlay.u_vars[forced_anchor_idx] == 1)
    overlay.model.Add(
        overlay._mandatory_signature_count_vars["group::router::routing::0"][constrained_bucket_id]
        >= 1
    )
    assert overlay.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_exact_core_overlay_applies_ghost_conditioned_required_optional_signature_bucket_upper_bounds() -> None:
    base_model = _build_exact_required_optional_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
        exact_required_pose_optional_counts=base_model.build_stats["exact_required_optionals"],
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    signature_stats = overlay.build_stats["global_valid_inequalities"]["signature_bucket_capacity_bounds"]

    assert overlay.build_stats["exact_core_reuse"]["used"] is True
    assert signature_stats["ghost_conditioned_required_optional_bucket_constraints"] > 0
    assert signature_stats["ghost_signature_reduction_anchor_count"] > 0

    template_payload = next(
        payload
        for payload in signature_stats["required_optionals"]
        if payload["template"] == "protocol_storage_box"
    )
    constrained_bucket_id = next(
        bucket["bucket_id"]
        for bucket in template_payload["buckets"]
        if bucket["count_var_upper_bound"] == 1
    )
    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(overlay._ghost_domains)
        if domain["anchor"] == {"x": 2, "y": 1}
    )
    overlay.model.Add(overlay.u_vars[forced_anchor_idx] == 1)
    overlay.model.Add(
        overlay._required_optional_signature_count_vars["protocol_storage_box"][constrained_bucket_id]
        >= 1
    )
    assert overlay.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_exact_core_overlay_signature_bucket_tightening_instrumentation_default_off_is_absent(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    monkeypatch.delenv(env_var, raising=False)
    base_model = _build_exact_mandatory_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto_fingerprint = str(baseline.model.Proto())
    baseline_stats = baseline.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    baseline_stats_snapshot = json.loads(json.dumps(baseline_stats, sort_keys=True))

    assert "signature_tightening_instrumentation" not in baseline_stats

    monkeypatch.setenv(env_var, "0")
    disabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    disabled_stats = disabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]

    assert "signature_tightening_instrumentation" not in disabled_stats
    assert (
        json.loads(json.dumps(disabled_stats, sort_keys=True))
        == baseline_stats_snapshot
    )
    assert str(disabled.model.Proto()) == baseline_proto_fingerprint


def test_exact_core_overlay_signature_bucket_tightening_instrumentation_records_mandatory_without_model_delta(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    monkeypatch.delenv(env_var, raising=False)
    base_model = _build_exact_mandatory_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()
    baseline_proto_fingerprint = str(baseline_proto)
    baseline_var_count = len(baseline_proto.variables)
    baseline_constraint_count = len(baseline_proto.constraints)
    baseline_constraint_type_counts = _constraint_type_counts(baseline_proto)

    monkeypatch.setenv(env_var, "1")
    instrumented = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    instrumented_proto = instrumented.model.Proto()
    stats = instrumented.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    instrumentation = stats["signature_tightening_instrumentation"]

    assert str(instrumented_proto) == baseline_proto_fingerprint
    assert len(instrumented_proto.variables) == baseline_var_count
    assert len(instrumented_proto.constraints) == baseline_constraint_count
    assert _constraint_type_counts(instrumented_proto) == baseline_constraint_type_counts
    assert instrumentation["enabled"] is True
    assert set(instrumentation["phase_seconds"]) == {
        "mandatory_payload_build",
        "required_optional_payload_build",
        "per_anchor_mandatory_scan",
        "per_anchor_required_optional_scan",
        "constraint_add",
        "stats_finalize",
    }
    totals = instrumentation["totals"]
    assert totals["evaluated_placements"] == len(instrumented._ghost_domains)
    assert totals["mandatory_payload_count"] > 0
    assert totals["required_optional_payload_count"] == 0
    assert totals["mandatory_constraints_added"] == stats[
        "ghost_conditioned_mandatory_bucket_constraints"
    ]
    assert instrumentation["top_slow_entries"]
    assert instrumentation["top_slow_entries"][0]["kind"] == "mandatory"


def test_exact_core_overlay_signature_bucket_tightening_instrumentation_records_required_optional(
    monkeypatch,
) -> None:
    env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    base_model = _build_exact_required_optional_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
        exact_required_pose_optional_counts=base_model.build_stats["exact_required_optionals"],
    )
    monkeypatch.delenv(env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()
    baseline_proto_fingerprint = str(baseline_proto)
    baseline_constraint_type_counts = _constraint_type_counts(baseline_proto)

    monkeypatch.setenv(env_var, "on")
    instrumented = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    instrumented_proto = instrumented.model.Proto()
    stats = instrumented.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]
    instrumentation = stats["signature_tightening_instrumentation"]
    totals = instrumentation["totals"]

    assert str(instrumented_proto) == baseline_proto_fingerprint
    assert len(instrumented_proto.variables) == len(baseline_proto.variables)
    assert len(instrumented_proto.constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(instrumented_proto) == baseline_constraint_type_counts
    assert instrumentation["enabled"] is True
    assert totals["mandatory_payload_count"] == 0
    assert totals["required_optional_payload_count"] > 0
    assert totals["required_optional_constraints_added"] == stats[
        "ghost_conditioned_required_optional_bucket_constraints"
    ]
    assert any(
        entry["kind"] == "required_optional"
        and entry["group_id_or_template"] == "protocol_storage_box"
        for entry in instrumentation["top_slow_entries"]
    )


def test_exact_core_overlay_signature_bucket_residual_overlay_instrumentation_default_off_is_absent(
    monkeypatch,
) -> None:
    residual_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION_ENV
    base_model = _build_exact_mandatory_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    monkeypatch.delenv(residual_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto_fingerprint = str(baseline.model.Proto())
    assert "residual_overlay_instrumentation" not in baseline.build_stats[
        "exact_core_reuse"
    ]

    monkeypatch.setenv(residual_env_var, "0")
    disabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    assert str(disabled.model.Proto()) == baseline_proto_fingerprint
    assert "residual_overlay_instrumentation" not in disabled.build_stats[
        "exact_core_reuse"
    ]


def test_exact_core_overlay_signature_bucket_residual_overlay_instrumentation_records_payload_without_model_delta(
    monkeypatch,
) -> None:
    inst_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_TIGHTENING_INSTRUMENTATION_ENV
    residual_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION_ENV
    base_model = _build_exact_mandatory_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    monkeypatch.delenv(inst_env_var, raising=False)
    monkeypatch.delenv(residual_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()

    monkeypatch.setenv(inst_env_var, "1")
    monkeypatch.setenv(residual_env_var, "1")
    enabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    enabled_proto = enabled.model.Proto()
    instrumentation = enabled.build_stats["global_valid_inequalities"][
        "signature_bucket_capacity_bounds"
    ]["signature_tightening_instrumentation"]
    residual_overlay = instrumentation["residual_overlay_instrumentation"]
    phase_seconds = residual_overlay["phase_seconds"]

    assert str(enabled_proto) == str(baseline_proto)
    assert len(enabled_proto.variables) == len(baseline_proto.variables)
    assert len(enabled_proto.constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        baseline_proto
    )
    assert residual_overlay["enabled"] is True
    assert set(phase_seconds) == {
        "payload_region_metadata_build_seconds",
        "payload_footprint_cohort_build_seconds",
        "payload_bucket_region_rebuild_seconds",
        "payload_compactness_guard_seconds",
    }
    assert phase_seconds["payload_region_metadata_build_seconds"] >= 0.0
    assert residual_overlay["top_slow_payload_groups"]
    exact_core_residual_overlay = enabled.build_stats["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]
    assert exact_core_residual_overlay["outer_exact_core_overlay_residual_seconds"] >= 0.0
    assert exact_core_residual_overlay["profile_validation_seconds"] >= 0.0
    outer_subphases = exact_core_residual_overlay[
        "outer_exact_core_overlay_subphase_seconds"
    ]
    for phase in (
        "model_shell_construction",
        "model_proto_clone_bind",
        "build_stats_deepcopy",
        "mandatory_group_and_candidate_cache_copy",
        "candidate_support_cache_restore",
        "boundary_port_cache_restore",
        "pre_ghost_stats_publish",
    ):
        assert outer_subphases[phase] >= 0.0
    assert (
        exact_core_residual_overlay[
            "outer_exact_core_overlay_subphase_total_seconds"
        ]
        >= 0.0
    )
    assert (
        exact_core_residual_overlay[
            "outer_exact_core_overlay_unattributed_seconds"
        ]
        >= 0.0
    )
    ghost_subphases = exact_core_residual_overlay["ghost_overlay_subphase_seconds"]
    assert ghost_subphases["coordinate_delegate_bind_from_core"] >= 0.0
    assert ghost_subphases["ghost_constraint_add"] >= 0.0
    assert ghost_subphases["search_guidance_rebuild"] >= 0.0
    assert ghost_subphases["coordinate_delegate_finalize_build_stats"] >= 0.0
    assert ghost_subphases["signature_var_sync"] >= 0.0


def test_exact_core_overlay_signature_bucket_residual_overlay_instrumentation_records_residual_signature_without_model_delta(
    monkeypatch,
) -> None:
    residual_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION_ENV
    base_model = _build_exact_residual_optional_signature_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    monkeypatch.delenv(residual_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()

    monkeypatch.setenv(residual_env_var, "on")
    enabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    enabled_proto = enabled.model.Proto()
    residual_stats = enabled.build_stats["global_valid_inequalities"][
        "residual_signature_bucket_capacity_bounds"
    ]
    residual_overlay = residual_stats["residual_overlay_instrumentation"]

    assert str(enabled_proto) == str(baseline_proto)
    assert len(enabled_proto.variables) == len(baseline_proto.variables)
    assert len(enabled_proto.constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        baseline_proto
    )
    assert residual_overlay["enabled"] is True
    assert residual_overlay["phase_seconds"][
        "residual_signature_scan_seconds"
    ] >= 0.0
    assert residual_overlay["phase_seconds"][
        "residual_signature_constraint_add_seconds"
    ] >= 0.0
    assert residual_overlay["top_slow_residual_signature_entries"]


def test_exact_core_overlay_signature_bucket_model_shell_instrumentation_default_off_is_absent(
    monkeypatch,
) -> None:
    model_shell_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION_ENV
    )
    residual_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION_ENV
    base_model = _build_exact_mandatory_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    monkeypatch.delenv(model_shell_env_var, raising=False)
    monkeypatch.delenv(residual_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto_fingerprint = str(baseline.model.Proto())

    assert "residual_overlay_instrumentation" not in baseline.build_stats[
        "exact_core_reuse"
    ]

    monkeypatch.setenv(model_shell_env_var, "0")
    disabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))

    assert str(disabled.model.Proto()) == baseline_proto_fingerprint
    assert "residual_overlay_instrumentation" not in disabled.build_stats[
        "exact_core_reuse"
    ]


def test_exact_core_overlay_signature_bucket_model_shell_instrumentation_records_subphases_without_model_delta(
    monkeypatch,
) -> None:
    model_shell_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION_ENV
    )
    residual_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION_ENV
    base_model = _build_exact_mandatory_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    monkeypatch.delenv(model_shell_env_var, raising=False)
    monkeypatch.delenv(residual_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()

    monkeypatch.setenv(model_shell_env_var, "1")
    enabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    enabled_proto = enabled.model.Proto()
    instrumentation = enabled.build_stats["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]
    subphases = instrumentation["model_shell_subphase_seconds"]

    assert str(enabled_proto) == str(baseline_proto)
    assert len(enabled_proto.variables) == len(baseline_proto.variables)
    assert len(enabled_proto.constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        baseline_proto
    )
    assert instrumentation["enabled"] is True
    assert instrumentation["model_shell_instrumentation_enabled"] is True
    for phase in (
        "constructor_enter_to_instance_copy",
        "dimension_and_profile_normalization",
        "mandatory_group_build",
        "candidate_domain_or_pose_cache_initialization",
        "port_profile_and_boundary_cache_initialization",
        "optional_cap_and_support_cache_initialization",
        "build_stats_initialization",
        "constructor_finalize",
    ):
        assert subphases[phase] >= 0.0
    assert subphases["signature_bucket_seed_build"] >= 0.0
    assert instrumentation["model_shell_subphase_total_seconds"] >= sum(
        max(0.0, float(value)) for value in subphases.values()
    ) - 1e-9
    assert instrumentation["model_shell_total_seconds"] >= 0.0
    assert instrumentation["model_shell_unattributed_seconds"] >= 0.0


def test_exact_core_overlay_signature_bucket_model_shell_instrumentation_rejects_unknown_value(
    monkeypatch,
) -> None:
    model_shell_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_MODEL_SHELL_INSTRUMENTATION_ENV
    )
    base_model = _build_exact_mandatory_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.setenv(model_shell_env_var, "maybe")
    with pytest.raises(ValueError, match=model_shell_env_var):
        MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


def test_exact_core_overlay_signature_bucket_port_profile_cache_instrumentation_default_off_is_absent(
    monkeypatch,
) -> None:
    env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION_ENV
    )
    coverer_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV
    )
    base_model = _build_exact_mandatory_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    monkeypatch.delenv(env_var, raising=False)
    monkeypatch.delenv(coverer_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto_fingerprint = str(baseline.model.Proto())

    assert "residual_overlay_instrumentation" not in baseline.build_stats[
        "exact_core_reuse"
    ]

    monkeypatch.setenv(env_var, "0")
    disabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))

    assert str(disabled.model.Proto()) == baseline_proto_fingerprint
    assert set(disabled.build_stats["exact_core_reuse"]) == set(
        baseline.build_stats["exact_core_reuse"]
    )
    assert "residual_overlay_instrumentation" not in disabled.build_stats[
        "exact_core_reuse"
    ]


def test_exact_core_overlay_signature_bucket_port_profile_cache_instrumentation_records_subphases_without_model_delta(
    monkeypatch,
) -> None:
    env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION_ENV
    )
    coverer_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV
    )
    base_model = _build_exact_mandatory_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    monkeypatch.delenv(env_var, raising=False)
    monkeypatch.delenv(coverer_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()

    monkeypatch.setenv(env_var, "1")
    enabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    enabled_proto = enabled.model.Proto()
    residual_overlay = enabled.build_stats["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]
    instrumentation = residual_overlay["port_profile_cache_instrumentation"]
    phase_seconds = instrumentation["phase_seconds"]
    totals = instrumentation["totals"]

    assert str(enabled_proto) == str(baseline_proto)
    assert len(enabled_proto.variables) == len(baseline_proto.variables)
    assert len(enabled_proto.constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        baseline_proto
    )
    assert residual_overlay["enabled"] is True
    assert instrumentation["enabled"] is True
    assert instrumentation["env_var"] == env_var
    assert "powered_support_coverer_instrumentation" not in instrumentation
    assert set(phase_seconds) == {
        "index_container_initialization",
        "power_pole_index_build",
        "per_template_pose_cache_build",
        "port_front_extraction",
        "local_signature_build",
        "powered_anchor_shape_grouping",
        "powered_support_coverer_build",
        "compact_capacity_signature_store",
        "exact_precompute_profile_update",
        "index_pools_unattributed_seconds",
    }
    assert all(value >= 0.0 for value in phase_seconds.values())
    assert instrumentation["total_seconds"] >= sum(
        max(0.0, float(value))
        for key, value in phase_seconds.items()
        if key != "index_pools_unattributed_seconds"
    )
    assert totals["template_count"] == len(enabled.facility_pools)
    assert totals["pose_count"] == sum(len(pool) for pool in enabled.facility_pools.values())
    assert totals["power_pole_count"] == len(
        enabled.facility_pools.get("power_pole", [])
    )
    assert totals["pose_cells_scanned"] > 0
    assert totals["local_signature_cells_scanned"] > 0
    assert instrumentation["top_slow_templates_or_groups"]
    top_entry = instrumentation["top_slow_templates_or_groups"][0]
    assert "kind" in top_entry
    assert "elapsed_seconds" in top_entry


def test_exact_core_overlay_signature_bucket_port_profile_cache_instrumentation_rejects_unknown_value(
    monkeypatch,
) -> None:
    env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION_ENV
    )
    base_model = _build_exact_mandatory_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.setenv(env_var, "maybe")
    with pytest.raises(ValueError, match=env_var):
        MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


def test_exact_core_overlay_signature_bucket_powered_support_coverer_instrumentation_default_off_is_absent(
    monkeypatch,
) -> None:
    port_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION_ENV
    )
    coverer_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV
    )
    base_model = _build_exact_power_capacity_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.delenv(port_env_var, raising=False)
    monkeypatch.delenv(coverer_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()

    monkeypatch.setenv(port_env_var, "1")
    monkeypatch.delenv(coverer_env_var, raising=False)
    parent_only = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    parent_instrumentation = parent_only.build_stats["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]

    assert str(parent_only.model.Proto()) == str(baseline_proto)
    assert _constraint_type_counts(parent_only.model.Proto()) == _constraint_type_counts(
        baseline_proto
    )
    assert "powered_support_coverer_instrumentation" not in parent_instrumentation

    monkeypatch.setenv(coverer_env_var, "0")
    disabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    disabled_instrumentation = disabled.build_stats["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]

    assert str(disabled.model.Proto()) == str(baseline_proto)
    assert "powered_support_coverer_instrumentation" not in disabled_instrumentation


def test_exact_core_overlay_signature_bucket_powered_support_coverer_instrumentation_records_detail_without_model_delta(
    monkeypatch,
) -> None:
    port_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_PORT_PROFILE_CACHE_INSTRUMENTATION_ENV
    )
    coverer_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV
    )
    base_model = _build_exact_power_capacity_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.delenv(port_env_var, raising=False)
    monkeypatch.delenv(coverer_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()

    monkeypatch.setenv(coverer_env_var, "1")
    enabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    enabled_proto = enabled.model.Proto()
    residual_overlay = enabled.build_stats["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]
    parent_instrumentation = residual_overlay["port_profile_cache_instrumentation"]
    coverer_instrumentation = parent_instrumentation[
        "powered_support_coverer_instrumentation"
    ]
    phase_seconds = coverer_instrumentation["phase_seconds"]
    totals = coverer_instrumentation["totals"]

    assert str(enabled_proto) == str(baseline_proto)
    assert len(enabled_proto.variables) == len(baseline_proto.variables)
    assert len(enabled_proto.constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(enabled_proto) == _constraint_type_counts(
        baseline_proto
    )
    assert residual_overlay["enabled"] is True
    assert parent_instrumentation["enabled"] is True
    assert coverer_instrumentation["enabled"] is True
    assert coverer_instrumentation["env_var"] == coverer_env_var
    assert set(phase_seconds) == {
        "coverer_union_collection",
        "disjoint_filtering",
        "power_index_expansion",
        "compact_item_accumulation",
        "stats_finalize",
    }
    assert all(value >= 0.0 for value in phase_seconds.values())
    assert coverer_instrumentation["total_phase_seconds"] >= 0.0
    assert totals["template_count"] >= 1
    assert totals["group_count"] > 0
    assert totals["pose_count"] == len(
        enabled.facility_pools.get("powered_machine", [])
    )
    assert totals["representative_cell_count"] > 0
    assert totals["candidate_coverer_count"] >= totals["filtered_coverer_count"]
    assert totals["power_index_assignment_count"] == totals["pose_count"]
    assert coverer_instrumentation["top_slow_groups"]
    top_entry = coverer_instrumentation["top_slow_groups"][0]
    assert top_entry["kind"] == "powered_support_coverer_group"
    assert {
        "template",
        "anchor",
        "shape_token",
        "pose_count",
        "representative_cell_count",
        "candidate_coverer_count",
        "filtered_coverer_count",
        "rejected_coverer_count",
        "elapsed_seconds",
    } <= set(top_entry)


def test_exact_core_overlay_signature_bucket_powered_support_coverer_instrumentation_rejects_unknown_value(
    monkeypatch,
) -> None:
    env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV
    )
    base_model = _build_exact_power_capacity_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.setenv(env_var, "maybe")
    with pytest.raises(ValueError, match=env_var):
        MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


def test_exact_core_overlay_signature_bucket_compact_item_optimization_default_off_is_absent(
    monkeypatch,
) -> None:
    coverer_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV
    )
    compact_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_ENV
    )
    base_model = _build_exact_power_capacity_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.setenv(coverer_env_var, "1")
    monkeypatch.delenv(compact_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()
    baseline_instrumentation = baseline.build_stats["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]["powered_support_coverer_instrumentation"]

    assert str(baseline_proto)
    assert not any(
        key.startswith("compact_item_optimization")
        or key == "compact_item_optimized_update_count"
        or key == "compact_item_fallback_update_count"
        for key in baseline_instrumentation["totals"]
    )

    for disabled_value in ("0", "false"):
        monkeypatch.setenv(compact_env_var, disabled_value)
        disabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
        disabled_instrumentation = disabled.build_stats["exact_core_reuse"][
            "residual_overlay_instrumentation"
        ]["port_profile_cache_instrumentation"][
            "powered_support_coverer_instrumentation"
        ]

        assert str(disabled.model.Proto()) == str(baseline_proto)
        assert _constraint_type_counts(disabled.model.Proto()) == _constraint_type_counts(
            baseline_proto
        )
        assert not any(
            key.startswith("compact_item_optimization")
            or key == "compact_item_optimized_update_count"
            or key == "compact_item_fallback_update_count"
            for key in disabled_instrumentation["totals"]
        )


def test_exact_core_overlay_signature_bucket_compact_item_optimization_matches_legacy(
    monkeypatch,
) -> None:
    coverer_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV
    )
    compact_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_ENV
    )
    base_model = _build_exact_power_capacity_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.delenv(coverer_env_var, raising=False)
    monkeypatch.delenv(compact_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()
    baseline_compact = dict(
        baseline._compact_local_power_capacity_signature_by_template_pole[
            "powered_machine"
        ]
    )

    monkeypatch.setenv(compact_env_var, "1")
    optimized = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))

    assert str(optimized.model.Proto()) == str(baseline_proto)
    assert len(optimized.model.Proto().variables) == len(baseline_proto.variables)
    assert len(optimized.model.Proto().constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(optimized.model.Proto()) == _constraint_type_counts(
        baseline_proto
    )
    assert (
        optimized._compact_local_power_capacity_signature_by_template_pole[
            "powered_machine"
        ]
        == baseline_compact
    )

    monkeypatch.setenv(coverer_env_var, "1")
    instrumented = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    instrumentation = instrumented.build_stats["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]["powered_support_coverer_instrumentation"]
    totals = instrumentation["totals"]

    assert str(instrumented.model.Proto()) == str(baseline_proto)
    assert totals["compact_item_optimization_attempts"] > 0
    assert (
        totals["compact_item_optimization_attempts"]
        == totals["compact_item_optimization_used"]
    )
    assert totals["compact_item_optimization_fallbacks"] == 0
    assert (
        totals["compact_item_optimized_update_count"]
        == totals["compact_item_update_count"]
    )
    assert totals["compact_item_fallback_update_count"] == 0
    assert instrumentation["top_slow_groups"]
    assert (
        instrumentation["top_slow_groups"][0]["compact_item_accumulation_mode"]
        == "optimized"
    )


def test_exact_core_overlay_signature_bucket_compact_item_optimization_rejects_unknown_value(
    monkeypatch,
) -> None:
    env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_ENV
    )
    base_model = _build_exact_power_capacity_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.setenv(env_var, "maybe")
    with pytest.raises(ValueError, match=env_var):
        MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


def test_exact_core_overlay_signature_bucket_compact_item_batched_counter_default_off_is_absent(
    monkeypatch,
) -> None:
    coverer_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV
    )
    compact_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_ENV
    )
    batched_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION_ENV
    )
    base_model = _build_exact_power_capacity_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.setenv(coverer_env_var, "1")
    monkeypatch.setenv(compact_env_var, "1")
    monkeypatch.delenv(batched_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()
    baseline_instrumentation = baseline.build_stats["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]["powered_support_coverer_instrumentation"]

    assert str(baseline_proto)
    assert not any(
        key.startswith("compact_item_batched_counter")
        for key in baseline_instrumentation["totals"]
    )

    for disabled_value in ("0", "false"):
        monkeypatch.setenv(batched_env_var, disabled_value)
        disabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
        disabled_instrumentation = disabled.build_stats["exact_core_reuse"][
            "residual_overlay_instrumentation"
        ]["port_profile_cache_instrumentation"][
            "powered_support_coverer_instrumentation"
        ]

        assert str(disabled.model.Proto()) == str(baseline_proto)
        assert _constraint_type_counts(disabled.model.Proto()) == _constraint_type_counts(
            baseline_proto
        )
        assert not any(
            key.startswith("compact_item_batched_counter")
            for key in disabled_instrumentation["totals"]
        )


def test_exact_core_overlay_signature_bucket_compact_item_batched_counter_matches_s131(
    monkeypatch,
) -> None:
    coverer_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV
    )
    compact_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_ENV
    )
    batched_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION_ENV
    )
    base_model = _build_exact_power_capacity_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.delenv(coverer_env_var, raising=False)
    monkeypatch.setenv(compact_env_var, "1")
    monkeypatch.delenv(batched_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()
    baseline_compact = dict(
        baseline._compact_local_power_capacity_signature_by_template_pole[
            "powered_machine"
        ]
    )

    monkeypatch.setenv(batched_env_var, "1")
    batched = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))

    assert str(batched.model.Proto()) == str(baseline_proto)
    assert len(batched.model.Proto().variables) == len(baseline_proto.variables)
    assert len(batched.model.Proto().constraints) == len(baseline_proto.constraints)
    assert _constraint_type_counts(batched.model.Proto()) == _constraint_type_counts(
        baseline_proto
    )
    assert (
        batched._compact_local_power_capacity_signature_by_template_pole[
            "powered_machine"
        ]
        == baseline_compact
    )

    monkeypatch.setenv(coverer_env_var, "1")
    instrumented = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    instrumentation = instrumented.build_stats["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]["powered_support_coverer_instrumentation"]
    totals = instrumentation["totals"]

    assert str(instrumented.model.Proto()) == str(baseline_proto)
    assert totals["compact_item_batched_counter_attempts"] > 0
    assert (
        totals["compact_item_batched_counter_attempts"]
        == totals["compact_item_batched_counter_used"]
    )
    assert totals["compact_item_batched_counter_fallbacks"] == 0
    assert (
        totals["compact_item_batched_counter_local_update_count"]
        == totals["compact_item_update_count"]
    )
    assert 0 < totals["compact_item_batched_counter_merge_update_count"] <= totals[
        "compact_item_batched_counter_local_update_count"
    ]
    assert totals["compact_item_batched_counter_unique_item_count"] == totals[
        "compact_item_batched_counter_merge_update_count"
    ]
    assert (
        totals["compact_item_optimization_attempts"]
        == totals["compact_item_optimization_used"]
    )
    assert instrumentation["top_slow_groups"]
    assert (
        instrumentation["top_slow_groups"][0]["compact_item_accumulation_mode"]
        == "batched_counter"
    )


def test_exact_core_overlay_signature_bucket_compact_item_detail_instrumentation_default_off_is_absent(
    monkeypatch,
) -> None:
    coverer_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV
    )
    compact_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_ENV
    )
    batched_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION_ENV
    )
    detail_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_DETAIL_INSTRUMENTATION_ENV
    )
    base_model = _build_exact_power_capacity_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.setenv(coverer_env_var, "1")
    monkeypatch.setenv(compact_env_var, "1")
    monkeypatch.setenv(batched_env_var, "1")
    monkeypatch.delenv(detail_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()
    baseline_instrumentation = baseline.build_stats["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]["powered_support_coverer_instrumentation"]

    assert "compact_item_detail_instrumentation" not in baseline_instrumentation

    for disabled_value in ("0", "false"):
        monkeypatch.setenv(detail_env_var, disabled_value)
        disabled = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
        disabled_instrumentation = disabled.build_stats["exact_core_reuse"][
            "residual_overlay_instrumentation"
        ]["port_profile_cache_instrumentation"][
            "powered_support_coverer_instrumentation"
        ]

        assert str(disabled.model.Proto()) == str(baseline_proto)
        assert _constraint_type_counts(disabled.model.Proto()) == _constraint_type_counts(
            baseline_proto
        )
        assert "compact_item_detail_instrumentation" not in disabled_instrumentation


def test_exact_core_overlay_signature_bucket_compact_item_detail_instrumentation_records_batched_counter_detail_without_model_delta(
    monkeypatch,
) -> None:
    coverer_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COVERER_INSTRUMENTATION_ENV
    )
    compact_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_ACCUMULATION_OPTIMIZATION_ENV
    )
    batched_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION_ENV
    )
    detail_env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_DETAIL_INSTRUMENTATION_ENV
    )
    base_model = _build_exact_power_capacity_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.delenv(coverer_env_var, raising=False)
    monkeypatch.setenv(compact_env_var, "1")
    monkeypatch.setenv(batched_env_var, "1")
    monkeypatch.delenv(detail_env_var, raising=False)
    baseline = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    baseline_proto = baseline.model.Proto()
    baseline_compact = dict(
        baseline._compact_local_power_capacity_signature_by_template_pole[
            "powered_machine"
        ]
    )

    monkeypatch.setenv(coverer_env_var, "1")
    monkeypatch.setenv(detail_env_var, "1")
    instrumented = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    instrumentation = instrumented.build_stats["exact_core_reuse"][
        "residual_overlay_instrumentation"
    ]["port_profile_cache_instrumentation"]["powered_support_coverer_instrumentation"]
    detail = instrumentation["compact_item_detail_instrumentation"]
    phase_seconds = detail["phase_seconds"]
    totals = detail["totals"]
    duplicate_compression = detail["duplicate_compression"]

    assert str(instrumented.model.Proto()) == str(baseline_proto)
    assert len(instrumented.model.Proto().variables) == len(baseline_proto.variables)
    assert len(instrumented.model.Proto().constraints) == len(
        baseline_proto.constraints
    )
    assert _constraint_type_counts(
        instrumented.model.Proto()
    ) == _constraint_type_counts(baseline_proto)
    assert (
        instrumented._compact_local_power_capacity_signature_by_template_pole[
            "powered_machine"
        ]
        == baseline_compact
    )
    assert detail["enabled"] is True
    assert detail["env_var"] == detail_env_var
    assert set(phase_seconds) == {
        "compact_item_key_build",
        "local_counter_update",
        "merge_fanout",
        "compact_signature_storage",
        "stats_finalize",
    }
    assert all(value >= 0.0 for value in phase_seconds.values())
    assert totals["group_count"] > 0
    assert totals["key_build_count"] == totals["local_counter_update_count"]
    assert totals["local_counter_update_count"] == instrumentation["totals"][
        "compact_item_batched_counter_local_update_count"
    ]
    assert 0 < totals["merge_update_count"] <= totals["local_counter_update_count"]
    assert totals["unique_item_count"] > 0
    assert totals["signature_storage_item_count"] > 0
    assert detail["per_template"]
    assert detail["per_template"][0]["template"] == "powered_machine"
    assert detail["top_slow_groups"]
    top_entry = detail["top_slow_groups"][0]
    assert {
        "kind",
        "template",
        "anchor",
        "shape_token",
        "pose_count",
        "representative_cell_count",
        "candidate_coverer_count",
        "filtered_coverer_count",
        "compact_item_accumulation_mode",
        "local_update_count",
        "unique_item_count",
        "merge_update_count",
        "elapsed_seconds",
    } <= set(top_entry)
    assert top_entry["compact_item_accumulation_mode"] == "batched_counter"
    assert duplicate_compression["local_update_count"] == totals[
        "local_counter_update_count"
    ]
    assert duplicate_compression["unique_item_count"] == totals["unique_item_count"]
    assert 0.0 <= duplicate_compression["unique_to_local_ratio"] <= 1.0
    assert 0.0 <= duplicate_compression["merge_to_local_ratio"] <= 1.0


def test_exact_core_overlay_signature_bucket_compact_item_detail_instrumentation_rejects_unknown_value(
    monkeypatch,
) -> None:
    env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_DETAIL_INSTRUMENTATION_ENV
    )
    base_model = _build_exact_power_capacity_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.setenv(env_var, "maybe")
    with pytest.raises(ValueError, match=env_var):
        MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


def test_exact_core_overlay_signature_bucket_compact_item_batched_counter_rejects_unknown_value(
    monkeypatch,
) -> None:
    env_var = (
        master_model_module.EXACT_GHOST_SIGNATURE_BUCKET_POWERED_SUPPORT_COMPACT_ITEM_BATCHED_COUNTER_OPTIMIZATION_ENV
    )
    base_model = _build_exact_power_capacity_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.setenv(env_var, "maybe")
    with pytest.raises(ValueError, match=env_var):
        MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


def test_exact_core_overlay_signature_bucket_residual_overlay_instrumentation_rejects_unknown_value(
    monkeypatch,
) -> None:
    residual_env_var = exact_coordinate_master_module.EXACT_GHOST_SIGNATURE_BUCKET_RESIDUAL_OVERLAY_INSTRUMENTATION_ENV
    base_model = _build_exact_mandatory_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )

    monkeypatch.setenv(residual_env_var, "maybe")
    with pytest.raises(ValueError, match=residual_env_var):
        MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


def test_exact_core_overlay_applies_mandatory_signature_monotonic_symmetry() -> None:
    base_model = _build_exact_mandatory_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))

    symmetry_stats = overlay.build_stats["coordinate_symmetry"]
    assert overlay.build_stats["exact_core_reuse"]["used"] is True
    assert symmetry_stats["enabled"] is True
    assert symmetry_stats["mandatory_signature_monotonic_constraints"] > 0

    slots = overlay._coordinate_delegate.mandatory_slots["group::router::routing::0"]
    overlay.model.Add(slots[0].signature > slots[1].signature)
    assert overlay.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_exact_core_overlay_applies_required_optional_signature_monotonic_symmetry() -> None:
    base_model = _build_exact_required_optional_signature_upper_bound_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
        exact_required_pose_optional_counts=base_model.build_stats["exact_required_optionals"],
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))

    symmetry_stats = overlay.build_stats["coordinate_symmetry"]
    assert overlay.build_stats["exact_core_reuse"]["used"] is True
    assert symmetry_stats["enabled"] is True
    assert symmetry_stats["required_optional_signature_monotonic_constraints"] > 0

    slots = overlay._coordinate_delegate.required_optional_slots["protocol_storage_box"]
    overlay.model.Add(slots[0].signature > slots[1].signature)
    assert overlay.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_exact_core_overlay_applies_ghost_conditioned_residual_optional_signature_bucket_upper_bounds() -> None:
    base_model = _build_exact_residual_optional_signature_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    residual_stats = overlay.build_stats["global_valid_inequalities"][
        "residual_signature_bucket_capacity_bounds"
    ]

    assert overlay.build_stats["exact_core_reuse"]["used"] is True
    assert residual_stats["ghost_conditioned_residual_bucket_constraints"] > 0
    assert residual_stats["ghost_residual_signature_reduction_anchor_count"] > 0

    template_payload = next(
        payload
        for payload in residual_stats["templates"]
        if payload["template"] == "protocol_storage_box"
    )
    constrained_bucket_id = next(
        bucket["bucket_id"]
        for bucket in template_payload["buckets"]
        if bucket["count_var_upper_bound"] == 1
    )
    forced_anchor_idx = next(
        idx
        for idx, domain in enumerate(overlay._ghost_domains)
        if domain["anchor"] == {"x": 2, "y": 1}
    )
    overlay.model.Add(overlay.u_vars[forced_anchor_idx] == 1)
    overlay.model.Add(
        overlay._residual_optional_signature_count_vars["protocol_storage_box"][
            constrained_bucket_id
        ]
        >= 1
    )
    assert overlay.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_exact_core_overlay_applies_residual_optional_signature_monotonic_symmetry() -> None:
    base_model = _build_exact_residual_optional_signature_model()
    core = MasterPlacementModel.build_exact_core(
        base_model.source_instances,
        base_model.facility_pools,
        base_model.rules,
        skip_power_coverage=base_model.skip_power_coverage,
        generic_io_requirements=base_model.generic_io_requirements,
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))

    symmetry_stats = overlay.build_stats["coordinate_symmetry"]
    assert overlay.build_stats["exact_core_reuse"]["used"] is True
    assert symmetry_stats["enabled"] is True
    assert symmetry_stats["residual_optional_signature_monotonic_constraints"] > 0

    slots = overlay._coordinate_delegate.residual_optional_slots["protocol_storage_box"]
    overlay.model.Add(slots[0].active == 1)
    overlay.model.Add(slots[1].active == 1)
    overlay.model.Add(slots[0].signature > slots[1].signature)
    assert overlay.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE
