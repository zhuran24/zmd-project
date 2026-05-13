"""Regression test for coordinate Benders cut over-pruning bug.

Bug: CoordinateExactMasterDelegate.add_benders_cut() forbids every (slot, pose)
combination globally for each pose in the conflict set. That makes single poses
in the conflict set permanently unusable, even though only the *combination*
was infeasible. Breaks certified-exact completeness.

Fix: emit a presence no-good — sum(present(pose) for pose in conflict) <= N-1.
Equivalent to the legacy BoolVar cut sum(z_conflict) <= N-1.
"""
from __future__ import annotations

from ortools.sat.python import cp_model

from src.models.master_model import MasterPlacementModel


def _build_two_miner_three_pose_fixture():
    """2 mandatory miners + 3 disjoint single-cell poses on a 5x1 grid.

    Two miners must occupy two distinct poses (NoOverlap2D). So solving picks
    2 out of 3 poses. Conflict set covering 2 of those poses must still allow
    the third pose to be used.
    """
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
                "pose_id": "pose_left",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "pose_mid",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "pose_right",
                "anchor": {"x": 4, "y": 0},
                "occupied_cells": [[4, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ]
    }
    rules = {
        "globals": {"grid": {"width": 5, "height": 1}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    return instances, pools, rules


def _solve_and_extract_pose_ids(overlay: MasterPlacementModel) -> dict[str, int]:
    status = overlay.solve(time_limit_seconds=5.0)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE), f"status={status}"
    solution = overlay.extract_solution()
    return {iid: int(entry["pose_idx"]) for iid, entry in solution.items() if iid.startswith("miner_")}


def test_coordinate_benders_cut_does_not_overprune_other_combinations() -> None:
    """Two-pose conflict cut must not permanently ban each pose individually."""
    instances, pools, rules = _build_two_miner_three_pose_fixture()
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True,
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    first_assignment = _solve_and_extract_pose_ids(overlay)
    assert set(first_assignment.keys()) == {"miner_001", "miner_002"}
    first_poses = set(first_assignment.values())
    assert len(first_poses) == 2, f"first solve should pick 2 distinct poses, got {first_assignment}"

    conflict_set = {iid: pose_idx for iid, pose_idx in first_assignment.items()}
    assert overlay.add_benders_cut(conflict_set) is True

    status = overlay.solve(time_limit_seconds=5.0)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE), (
        f"after a 2-pose presence no-good, the third pose + one of the original poses "
        f"should still be feasible; got status={status}. This is the over-prune bug."
    )
    second_assignment = _solve_and_extract_pose_ids(overlay)
    second_poses = set(second_assignment.values())
    assert second_poses != first_poses, (
        f"second solve must differ from first to avoid the cut; got identical {second_poses}"
    )
    assert second_poses & first_poses, (
        "presence no-good should still allow one of the original poses to recur "
        "paired with the third pose; got fully disjoint sets — over-cut suspected"
    )


def test_coordinate_benders_cut_single_pose_conflict_still_bans_that_pose() -> None:
    """Single-pose conflict (size==1) must forbid that single pose entirely."""
    instances, pools, rules = _build_two_miner_three_pose_fixture()
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True,
    )
    overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    first_assignment = _solve_and_extract_pose_ids(overlay)
    banned_pose_idx = next(iter(first_assignment.values()))
    cut_owner = next(iid for iid, p in first_assignment.items() if p == banned_pose_idx)

    assert overlay.add_benders_cut({cut_owner: banned_pose_idx}) is True

    status = overlay.solve(time_limit_seconds=5.0)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
    second_assignment = _solve_and_extract_pose_ids(overlay)
    assert banned_pose_idx not in second_assignment.values(), (
        f"single-pose presence no-good must remove that pose; got {second_assignment}"
    )
