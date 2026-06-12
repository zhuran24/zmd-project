"""Regression coverage for malformed solution hints.

Hints are search guidance only. Bad hint entries must not mutate the feasible
set, and direct API callers should not lose a solve because a performance hint
contains a malformed pose index.
"""

from __future__ import annotations

import pytest
from ortools.sat.python import cp_model

from src.models.master_model import MasterPlacementModel


def _fixture(*, ghost_rect=None) -> MasterPlacementModel:
    instances = [
        {
            "instance_id": "solid_1",
            "facility_type": "solid",
            "operation_type": "noop",
            "is_mandatory": True,
            "bound_type": "exact",
        }
    ]
    pools = {
        "solid": [
            {
                "pose_id": "solid_0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "solid_1",
                "anchor": {"x": 1, "y": 0},
                "occupied_cells": [[1, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ]
    }
    rules = {
        "globals": {"grid": {"width": 2, "height": 1}},
        "facility_templates": {
            "solid": {"dimensions": {"w": 1, "h": 1}, "needs_power": False}
        },
    }
    return MasterPlacementModel(
        instances=instances,
        facility_pools=pools,
        rules=rules,
        solve_mode="certified_exact",
        skip_power_coverage=True,
        ghost_rect=ghost_rect,
    )


def test_exact_solution_hint_skips_non_int_and_out_of_range_pose_indices() -> None:
    model = _fixture()

    status = model.solve(
        time_limit_seconds=2.0,
        solution_hint={
            "solid_1": "not_an_int",
            "pose_optional::power_pole::missing": 999,
        },
    )

    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    assert model.build_stats["last_solve"]["hinted_literals"] == 0
    assert model.extract_solution()["solid_1"]["pose_idx"] in {0, 1}

    model_oob = _fixture()
    status_oob = model_oob.solve(
        time_limit_seconds=2.0,
        solution_hint={"solid_1": 999},
    )
    assert status_oob in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    assert model_oob.build_stats["last_solve"]["hinted_literals"] == 0


@pytest.mark.parametrize("pose_idx", [0.0, 0.9, 1.0, True, False, "0", "1.0"])
def test_exact_solution_hint_skips_non_integral_pose_index_types(pose_idx: object) -> None:
    model = _fixture()

    status = model.solve(time_limit_seconds=2.0, solution_hint={"solid_1": pose_idx})

    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    assert model.build_stats["last_solve"]["hinted_literals"] == 0


def test_exact_ghost_anchor_hint_skips_missing_anchor_index() -> None:
    model = _fixture(ghost_rect=(1, 1))

    status = model.solve(time_limit_seconds=2.0, ghost_anchor_hint_idx=999)

    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    assert model.build_stats["last_solve"]["hinted_literals"] == 0
    assert model.build_stats["last_solve"]["ghost_anchor_hint_applied"] is False


@pytest.mark.parametrize("anchor_idx", ["not_an_int", "0", "2.0", 0.0, True, False])
def test_exact_ghost_anchor_hint_skips_non_integral_anchor_index_types(
    anchor_idx: object,
) -> None:
    model = _fixture(ghost_rect=(1, 1))

    status = model.solve(time_limit_seconds=2.0, ghost_anchor_hint_idx=anchor_idx)

    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    assert model.build_stats["last_solve"]["hinted_literals"] == 0
    assert model.build_stats["last_solve"]["ghost_anchor_hint_applied"] is False
    assert model.build_stats["last_solve"]["ghost_anchor_hint_idx"] is None


def test_legacy_solution_hint_skips_non_int_pose_index() -> None:
    instances, pools, rules = (
        _fixture().source_instances,
        _fixture().facility_pools,
        _fixture().rules,
    )
    model = MasterPlacementModel(
        instances=instances,
        facility_pools=pools,
        rules=rules,
        solve_mode="exploratory",
        skip_power_coverage=True,
    )

    status = model.solve(time_limit_seconds=2.0, solution_hint={"solid_1": "not_an_int"})

    assert status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
    assert model.build_stats["last_solve"]["hinted_literals"] == 0
