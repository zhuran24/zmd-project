"""HiGHS power_coverage helper 单元测试 — Phase 3 重写组件.

测试:
- build_pole_cell_index: 正确构建 cell → pole pose indices 映射
- compute_facility_pose_coverers: facility pose 跟 pole PCC 重叠检测
- emit_power_coverage_rows: 加 CSR rows 正确表达约束
"""

from __future__ import annotations

from src.models.highs_power_coverage import (
    build_pole_cell_index,
    compute_facility_pose_coverers,
    emit_power_coverage_rows,
)


def test_build_pole_cell_index_simple() -> None:
    pole_pool = [
        {"pose_id": "p0", "power_coverage_cells": [[0, 0], [0, 1]]},
        {"pose_id": "p1", "power_coverage_cells": [[0, 0], [1, 0]]},
        {"pose_id": "p2", "power_coverage_cells": [[5, 5]]},
    ]
    idx = build_pole_cell_index(pole_pool)
    assert idx[(0, 0)] == [0, 1]
    assert idx[(0, 1)] == [0]
    assert idx[(1, 0)] == [1]
    assert idx[(5, 5)] == [2]
    assert (9, 9) not in idx


def test_compute_facility_pose_coverers_overlap() -> None:
    idx = {
        (0, 0): [0, 1],
        (1, 1): [2],
    }
    # facility 占 (0,0) → coverers {0, 1}
    pose1 = {"occupied_cells": [[0, 0]]}
    assert compute_facility_pose_coverers(pose1, idx) == {0, 1}
    # facility 占 (0,0) + (1,1) → coverers {0, 1, 2}
    pose2 = {"occupied_cells": [[0, 0], [1, 1]]}
    assert compute_facility_pose_coverers(pose2, idx) == {0, 1, 2}
    # facility 占 cell 没 pole cover → empty
    pose3 = {"occupied_cells": [[9, 9]]}
    assert compute_facility_pose_coverers(pose3, idx) == set()


def test_emit_power_coverage_rows_basic() -> None:
    facility_pools = {
        "miner": [
            {"pose_id": "m0", "occupied_cells": [[0, 0]]},  # covered by pole 0, 1
            {"pose_id": "m1", "occupied_cells": [[5, 5]]},  # no coverer → fixed 0
        ],
        "power_pole": [
            {"pose_id": "p0", "occupied_cells": [[0, 0]], "power_coverage_cells": [[0, 0]]},
            {"pose_id": "p1", "occupied_cells": [[0, 1]], "power_coverage_cells": [[0, 0]]},
        ],
    }
    z_col_by_group_pose = {("g_miner_1", 0): 0, ("g_miner_1", 1): 1}
    pole_col_by_pose_idx = {0: 2, 1: 3}
    mandatory_groups = {"g_miner_1": "miner"}
    pole_cell_index = build_pole_cell_index(facility_pools["power_pole"])

    row_starts = [0]
    col_indices: list = []
    values: list = []
    row_lower: list = []
    row_upper: list = []
    INF = 1e30

    added_rows, added_nz = emit_power_coverage_rows(
        facility_pools=facility_pools,
        z_col_by_group_pose=z_col_by_group_pose,
        pole_col_by_pose_idx=pole_col_by_pose_idx,
        mandatory_groups=mandatory_groups,
        pole_cell_index=pole_cell_index,
        row_starts=row_starts,
        col_indices=col_indices,
        values=values,
        row_lower=row_lower,
        row_upper=row_upper,
        INF=INF,
    )

    # row 0: sum(pole_2, pole_3) - z_0 >= 0 (3 nonzero)
    # row 1: z_1 == 0 (1 nonzero)
    assert added_rows == 2
    assert added_nz == 4
    # row 0 lower = 0, upper = INF
    assert row_lower[0] == 0.0
    assert row_upper[0] == INF
    # row 1 lower = upper = 0
    assert row_lower[1] == 0.0
    assert row_upper[1] == 0.0
