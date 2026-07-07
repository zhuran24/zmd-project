"""M3-4 LBBD ↔ cut-framework wiring (P1.3).

Covers the glue only — oracle math has test_family_region_capacity, the
master translation has test_step_8_apply_to_master:

- env gate: EXACT_CUT_FRAMEWORK_ATTACH default-off → zero framework work.
- full chain: real oracle → real family validator → real step-6/7 → step_8
  against a spy master, on a self-consistent boundary-overflow BState.
- BState assembly from a real solved coordinate master (field fidelity).

The same env is registered in the certified unsafe map, so certified runs
with it enabled fail-close at the run entrance (red tests live in
test_ghost_anchor_filter / test_v62_candidate_frontier_contract patterns).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping
from unittest import mock

from ortools.sat.python import cp_model

from src.models.cut_manager import CutManager
from src.models.master_model import MasterPlacementModel
from src.search.benders_loop import LBBDController


# ---- fixtures ---------------------------------------------------------------


INSTANCE_TO_FT = {"boundary_io": "boundary_storage_port"}
FACILITY_TEMPLATES = {
    "boundary_storage_port": {
        "placement_rule": "left_or_bottom_boundary",
        "dimensions": {"w": 1, "h": 3},
    },
}
CANONICAL_RULES = {"facility_templates": FACILITY_TEMPLATES}


def _boundary_overflow_state():
    """Self-consistent BState where F1 fires: demand 46×3=138 vs cap 139-2=137."""
    from src.cuts.lifecycle import BState, GroupState

    poses = [
        {
            "pose_id": f"mock_p_{i}",
            "anchor": {"x": 0, "y": i},
            "occupied_cells": [[0, i % 68], [0, (i + 1) % 68], [0, (i + 2) % 68]],
            "input_port_cells": [],
            "output_port_cells": [],
        }
        for i in range(46)
    ]
    return BState(
        groups={
            "boundary_io": GroupState(
                "boundary_io",
                demand=46,
                pose_domain=frozenset(p["pose_id"] for p in poses),
            ),
        },
        ghost_rect=(10, 0, 2, 2),
        ghost_cells=frozenset({(10, 0), (11, 0), (10, 1), (11, 1)}),
        exterior_blocks=frozenset(),
        artifact_hashes={"canonical_rules.json": "h1"},
        available_oracle_versions=frozenset({"region_capacity_v1"}),
        canonical_rules=CANONICAL_RULES,
        facility_templates=FACILITY_TEMPLATES,
        instance_to_facility_type=INSTANCE_TO_FT,
        candidate_placements={
            "facility_pools": {"boundary_storage_port": poses}
        },
    )


class _SpyMaster:
    def __init__(self) -> None:
        self.build_stats: Dict[str, Any] = {}
        self.region_capacity_calls: list = []

    def add_region_capacity_cut(
        self, *, group_cell_weights: Mapping[str, int], capacity: int
    ) -> bool:
        self.region_capacity_calls.append(
            {"group_cell_weights": dict(group_cell_weights), "capacity": capacity}
        )
        return True


def _controller(master: Any) -> LBBDController:
    ckpt = Path(tempfile.mkdtemp(prefix="zmd_cfw_"))
    cm = CutManager(checkpoint_dir=ckpt, solve_mode="certified_exact")
    return LBBDController(
        master=master,
        cut_manager=cm,
        project_root=ckpt.parent,
        solve_mode="certified_exact",
    )


def _build_miner_master() -> MasterPlacementModel:
    instances = [
        {
            "instance_id": f"miner_{i:03d}",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for i in (1, 2)
    ]
    pools = {
        "miner": [
            {
                "pose_id": f"pose_{tag}",
                "anchor": {"x": x, "y": 0},
                "occupied_cells": [[x, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            }
            for tag, x in (("left", 0), ("mid", 2), ("right", 4))
        ]
    }
    rules = {
        "globals": {"grid": {"width": 5, "height": 1}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True
    )
    return MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


# ---- env gate ---------------------------------------------------------------


def test_attach_disabled_by_default_does_no_framework_work() -> None:
    controller = _controller(_SpyMaster())
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("EXACT_CUT_FRAMEWORK_ATTACH", None)
        with mock.patch.object(
            LBBDController,
            "_build_cut_framework_state",
            side_effect=AssertionError("state builder must not run when disabled"),
        ):
            assert (
                controller._maybe_attach_framework_cuts(
                    trigger="binding_infeasible", iteration=1
                )
                == 0
            )


# ---- full chain on spy master ----------------------------------------------


def test_full_chain_generates_validates_and_attaches() -> None:
    spy = _SpyMaster()
    controller = _controller(spy)
    state = _boundary_overflow_state()
    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with mock.patch.object(
            LBBDController, "_build_cut_framework_state", return_value=state
        ):
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=7
            )
    assert attached == 1
    assert len(spy.region_capacity_calls) == 1
    call = spy.region_capacity_calls[0]
    assert call["group_cell_weights"] == {"boundary_io": 3}
    assert call["capacity"] == 137  # 139-cell union minus 2 ghost cells
    stats = spy.build_stats["cut_framework_attach_last"]
    assert stats == {
        "trigger": "binding_infeasible",
        "iteration": 7,
        "generated": 1,
        "attached": 1,
    }


def test_full_chain_no_overflow_attaches_nothing() -> None:
    spy = _SpyMaster()
    controller = _controller(spy)
    state = _boundary_overflow_state()
    # Move the ghost off the union: cap stays 139 ≥ demand 138 → no cut.
    object.__setattr__(state, "ghost_cells", frozenset({(30, 30), (31, 30)}))
    object.__setattr__(state, "ghost_rect", (30, 30, 1, 2))
    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with mock.patch.object(
            LBBDController, "_build_cut_framework_state", return_value=state
        ):
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=1
            )
    assert attached == 0
    assert spy.region_capacity_calls == []


# ---- BState assembly from a real master --------------------------------------


def test_state_assembly_from_solved_coordinate_master() -> None:
    master = _build_miner_master()
    assert master.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )
    controller = _controller(master)
    state = controller._build_cut_framework_state()
    assert state is not None
    group_id = str(master._group_id_by_instance["miner_001"])
    assert set(state.groups) == {group_id}
    group = state.groups[group_id]
    assert group.demand == 2
    assert group.pose_domain == {"pose_left", "pose_mid", "pose_right"}
    assert state.instance_to_facility_type == {group_id: "miner"}
    assert state.facility_templates == master.templates
    assert state.candidate_placements == {"facility_pools": master.facility_pools}
    assert state.exterior_blocks == frozenset()
    assert "region_capacity_v1" in state.available_oracle_versions
    # ghost: (anchor_x, anchor_y, h, w) with cells matching the 1×1 ghost
    assert len(state.ghost_cells) == 1
    ax, ay, gh, gw = state.ghost_rect
    assert (gh, gw) == (1, 1)
    assert state.ghost_cells == {(ax, ay)}
