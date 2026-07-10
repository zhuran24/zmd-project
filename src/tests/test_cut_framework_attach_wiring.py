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
        available_oracle_versions=frozenset(
            {"region_capacity_v1", "shape_packing_hall_v1"}
        ),
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
        self.baseline_packing_calls: list = []

    def add_region_capacity_cut(
        self,
        *,
        group_cell_weights: Mapping[str, int],
        capacity: int,
        condition_lits: Any = (),
    ) -> bool:
        self.region_capacity_calls.append(
            {
                "group_cell_weights": dict(group_cell_weights),
                "capacity": capacity,
                "condition_lits": tuple(condition_lits),
            }
        )
        return True

    def add_baseline_packing_cut(
        self,
        *,
        group_id: str,
        region_kind: str,
        capacity: int,
        condition_lits: Any = (),
    ) -> bool:
        self.baseline_packing_calls.append(
            {
                "group_id": group_id,
                "region_kind": region_kind,
                "capacity": capacity,
                "condition_lits": tuple(condition_lits),
            }
        )
        return True


_GHOST_U_VAR_SENTINEL = object()


def _mock_ghost_context():
    """(rect_idx, u_var, anchor, ghost_cells) matching _boundary_overflow_state."""
    return (
        0,
        _GHOST_U_VAR_SENTINEL,
        {"x": 10, "y": 0},
        {(10, 0), (11, 0), (10, 1), (11, 1)},
    )


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
        ), mock.patch.object(
            LBBDController,
            "_selected_ghost_context",
            return_value=_mock_ghost_context(),
        ):
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=7
            )
    # F1 overflow cut + one F6 Hall cut. The 2×2 ghost at (10,0) bites the
    # left baseline: left packable 10//3+58//3=22 < SoT bound 46-23=23 → cut.
    # The bottom side's bound 46-22=24 exceeds the single-side physical cap
    # 70//3=23, so the oracle's sane-bound guard deliberately skips it (the
    # left cut already refutes this anchor).
    assert attached == 2
    assert len(spy.region_capacity_calls) == 1
    call = spy.region_capacity_calls[0]
    assert call["group_cell_weights"] == {"boundary_io": 3}
    assert call["capacity"] == 137  # 139-cell union minus 2 ghost cells
    # The overflow cut is ghost-bound (ghost bites the union), so M4-A
    # conditioning must forward the selected ghost literal.
    assert call["condition_lits"] == (_GHOST_U_VAR_SENTINEL,)
    assert len(spy.baseline_packing_calls) == 1
    f6_call = spy.baseline_packing_calls[0]
    assert f6_call["region_kind"] == "left_baseline"
    assert f6_call["capacity"] == 22
    assert f6_call["group_id"] == "boundary_io"
    assert f6_call["condition_lits"] == (_GHOST_U_VAR_SENTINEL,)
    stats = spy.build_stats["cut_framework_attach_last"]
    assert stats == {
        "trigger": "binding_infeasible",
        "iteration": 7,
        "generated": 2,
        "attached": 2,
        "attached_by_family": {
            "region_capacity": 1,
            "shape_packing_hall": 1,
        },
        "rejected": {
            "integrity": 0,
            "validator_missing": 0,
            "validator_not_ok": 0,
            "scope": 0,
            "evaluate": 0,
        },
    }


def test_integrity_drift_cut_is_rejected_not_attached() -> None:
    """cert/oracle hash 漂移的 cut 必须被 direct attach 一票否决（外审 P0 回归）。

    2026-07-09 外审 3/3 共识：此前 attach 循环调 validate_cut_integrity() 却
    丢弃返回值——漂移 cut 照走 validator/Step8。本测试钉死拒绝语义与
    rejected.integrity telemetry。
    """
    import dataclasses

    from src.cuts.oracles import region_capacity_oracle

    spy = _SpyMaster()
    controller = _controller(spy)
    state = _boundary_overflow_state()
    real_generate = region_capacity_oracle.generate_region_capacity_cuts

    def tampered_generate(*args: Any, **kwargs: Any):
        cuts = list(real_generate(*args, **kwargs))
        assert cuts, "fixture 应产出至少一条 F1 cut"
        # oracle_cert_hash 与 cert.cert_hash 不一致 = integrity drift
        cuts[0] = dataclasses.replace(cuts[0], oracle_cert_hash="0" * 64)
        return cuts

    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with mock.patch.object(
            LBBDController, "_build_cut_framework_state", return_value=state
        ), mock.patch.object(
            LBBDController,
            "_selected_ghost_context",
            return_value=_mock_ghost_context(),
        ), mock.patch.object(
            region_capacity_oracle,
            "generate_region_capacity_cuts",
            side_effect=tampered_generate,
        ):
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=7
            )
    stats = spy.build_stats["cut_framework_attach_last"]
    assert stats["rejected"]["integrity"] == 1
    # F1 那条被拒；F6 Hall cut 不受影响仍可 attach
    assert "region_capacity" not in stats["attached_by_family"]
    assert len(spy.region_capacity_calls) == 0
    assert attached == stats["attached"] == 1


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
        ), mock.patch.object(
            LBBDController,
            "_selected_ghost_context",
            return_value=_mock_ghost_context(),
        ):
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=1
            )
    assert attached == 0
    assert spy.region_capacity_calls == []


def test_attach_budget_exhausted_stops_emitting() -> None:
    """M4-A budget gate: at EXACT_CUT_FRAMEWORK_ATTACH_BUDGET attached
    constraints the framework stops before generating anything."""
    from src.search.benders_loop import EXACT_CUT_FRAMEWORK_ATTACH_BUDGET

    spy = _SpyMaster()
    spy.build_stats["coordinate_framework_cut_count"] = (
        EXACT_CUT_FRAMEWORK_ATTACH_BUDGET
    )
    controller = _controller(spy)
    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        with mock.patch.object(
            LBBDController,
            "_build_cut_framework_state",
            side_effect=AssertionError("budget gate must fire before the state build"),
        ):
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=3
            )
    assert attached == 0
    assert spy.region_capacity_calls == []
    stats = spy.build_stats["cut_framework_attach_last"]
    assert stats["budget_exhausted"] is True
    assert stats["budget"] == EXACT_CUT_FRAMEWORK_ATTACH_BUDGET
    assert stats["attached"] == 0


def test_framework_target_poses_resolves_groups_and_pose_ids() -> None:
    """Solution keys are instance-level; targets must be (group_id, pose_id)."""
    master = _build_miner_master()
    controller = _controller(master)
    group_id = str(master._group_id_by_instance["miner_001"])
    solution = {
        "miner_001": {"facility_type": "miner", "pose_idx": 0},
        "miner_002": {"facility_type": "miner", "pose_idx": 2},
        "ghost_pick": {"rect_idx": 3},
        "unknown_instance": {"facility_type": "miner", "pose_idx": 1},
    }
    targets = controller._framework_target_poses(solution)
    assert targets == sorted(
        [(group_id, "pose_left"), (group_id, "pose_right")]
    )


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
    # ghost: (anchor_x, anchor_y, width, height), matching BState's
    # (x, y, x_span, y_span) contract.
    assert len(state.ghost_cells) == 1
    ax, ay, gw, gh = state.ghost_rect
    assert (gw, gh) == (1, 1)
    assert state.ghost_cells == {(ax, ay)}


def test_state_assembly_preserves_rectangular_ghost_axis_order() -> None:
    """A square ghost masks width/height swaps; keep a rectangular red test."""
    master = _build_miner_master()
    master.ghost_rect = (2, 1)  # master convention: (width, height)
    controller = _controller(master)
    context = (
        0,
        _GHOST_U_VAR_SENTINEL,
        {"x": 1, "y": 0},
        {(1, 0), (2, 0)},
    )
    with mock.patch.object(
        LBBDController, "_selected_ghost_context", return_value=context
    ):
        state = controller._build_cut_framework_state()

    assert state is not None
    assert state.ghost_rect == (1, 0, 2, 1)
    assert state.ghost_cells == {(1, 0), (2, 0)}


def test_rectangular_ghost_scope_attaches_only_with_matching_axis_order() -> None:
    """A ghost-bound cut must distinguish (width, height) from its transpose."""
    from src.cuts.lifecycle import (
        GHOST_AGNOSTIC,
        compute_ghost_rect_id,
        step_6_attach_scope_check,
    )
    from src.cuts.oracles.region_capacity_oracle import (
        generate_region_capacity_cuts,
    )

    state = _boundary_overflow_state()
    state.ghost_rect = (10, 0, 2, 1)
    state.ghost_cells = frozenset({(10, 0), (11, 0)})
    cuts = generate_region_capacity_cuts(state, state.canonical_rules)

    assert len(cuts) == 1
    cut = cuts[0]
    assert cut.scope is not None
    assert cut.scope.ghost_rect_id != GHOST_AGNOSTIC
    assert cut.scope.ghost_rect_id == compute_ghost_rect_id((10, 0, 2, 1))
    assert step_6_attach_scope_check(cut, state) == "ATTACH"

    # The occupied cells are intentionally unchanged: the axis-aware scope ID
    # alone must prevent replay under the transposed rectangular geometry.
    state.ghost_rect = (10, 0, 1, 2)
    assert step_6_attach_scope_check(cut, state) == "HOLD"


def test_full_chain_f5_binding_empty_domain_end_to_end() -> None:
    """M4-D3: incumbent → liftable binding adapter → minimizer → F5 cut →
    validator/scope/evaluate gauntlet → real master presence nogood.

    The fixture poses carry no port cells; with an exact-binding operation
    whose profile requires ports, every pose has an empty binding domain —
    the adapter refutes the incumbent, the minimizer shrinks to a single
    literal, and the attach chain lands a real constraint on the master.
    """
    import pytest as _pytest

    from src.cuts.oracles.pattern_nogood_oracle import (
        clear_sub_problem_oracle_registry,
    )
    from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES

    op = None
    for cand, profile in sorted(OPERATION_PORT_PROFILES.items()):
        if profile.generic_input_slots or profile.generic_output_slots:
            continue
        if sum(profile.input_slots.values()) + sum(profile.output_slots.values()) > 0:
            op = cand
            break
    if op is None:
        _pytest.skip("no exact-binding operation with port slots in profiles")

    instances = [
        {
            "instance_id": f"miner_{i:03d}",
            "facility_type": "miner",
            "operation_type": op,
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
    master = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    assert master.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )
    controller = _controller(master)
    solution = {
        "miner_001": {"facility_type": "miner", "pose_idx": 0},
        "miner_002": {"facility_type": "miner", "pose_idx": 1},
    }
    clear_sub_problem_oracle_registry()
    try:
        with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
            attached = controller._maybe_attach_framework_cuts(
                trigger="binding_infeasible", iteration=2, solution=solution
            )
    finally:
        clear_sub_problem_oracle_registry()
    assert attached >= 1
    f5_stats = master.build_stats.get("coordinate_pattern_nogood_last_cut")
    assert f5_stats is not None
    # deletion minimisation converges to a single dead literal
    assert f5_stats["pattern_size"] == 1


def test_r10_f5_cut_is_rejected_on_drifted_state() -> None:
    """R10 (two-state scope soundness, F5 instance): a cut generated on state
    A must NOT re-attach on a state B whose ghost anchor or homogeneity
    surface differs — step-6 must answer HOLD/QUARANTINE, never ATTACH."""
    import pytest as _pytest

    from src.cuts.lifecycle import step_6_attach_scope_check
    from src.cuts.oracles.pattern_nogood_oracle import (
        clear_sub_problem_oracle_registry,
        generate_pattern_nogood_cuts,
        register_sub_problem_oracle,
    )
    from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES
    from src.search.f5_binding_empty_domain_adapter import (
        build_binding_empty_domain_adapter,
    )
    from src.search.orbit_homogeneity import ORBIT_HOMOGENEITY_DIGEST_KEY

    op = None
    for cand, profile in sorted(OPERATION_PORT_PROFILES.items()):
        if profile.generic_input_slots or profile.generic_output_slots:
            continue
        if sum(profile.input_slots.values()) + sum(profile.output_slots.values()) > 0:
            op = cand
            break
    if op is None:
        _pytest.skip("no exact-binding operation with port slots in profiles")

    instances = [
        {
            "instance_id": f"miner_{i:03d}",
            "facility_type": "miner",
            "operation_type": op,
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
    master = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    assert master.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )
    controller = _controller(master)
    solution = {
        "miner_001": {"facility_type": "miner", "pose_idx": 0},
        "miner_002": {"facility_type": "miner", "pose_idx": 1},
    }
    clear_sub_problem_oracle_registry()
    try:
        state_a = controller._build_cut_framework_state(solution=solution)
        assert state_a is not None
        adapter = build_binding_empty_domain_adapter(master._mandatory_groups)
        register_sub_problem_oracle(adapter)
        literals = controller._framework_full_assignment_literals(solution)
        cuts = generate_pattern_nogood_cuts(
            state_a, sub_problem_oracle=adapter, full_assignment_literals=literals
        )
        assert len(cuts) == 1
        cut = cuts[0]
        # Same state → ATTACH (sanity).
        assert step_6_attach_scope_check(cut, state_a) == "ATTACH"

        # Drift 1: different ghost anchor → HOLD (ghost-bound scope mismatch).
        state_b = controller._build_cut_framework_state(solution=solution)
        assert state_b is not None
        object.__setattr__(state_b, "ghost_rect", (3, 0, 1, 1))
        object.__setattr__(state_b, "ghost_cells", frozenset({(3, 0)}))
        assert step_6_attach_scope_check(cut, state_b) != "ATTACH"

        # Drift 2: homogeneity surface changed → artifact-hash mismatch.
        state_c = controller._build_cut_framework_state(solution=solution)
        assert state_c is not None
        drifted_hashes = dict(state_c.artifact_hashes)
        drifted_hashes[ORBIT_HOMOGENEITY_DIGEST_KEY] = "0" * 64
        object.__setattr__(state_c, "artifact_hashes", drifted_hashes)
        assert step_6_attach_scope_check(cut, state_c) != "ATTACH"
    finally:
        clear_sub_problem_oracle_registry()
