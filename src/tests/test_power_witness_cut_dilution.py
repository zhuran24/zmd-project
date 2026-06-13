"""Regression for power-pole witness dilution in whole-layout cut (GPT v4 P0 #2).

EXACT_POWER_PLACEMENT_SUBPROBLEM=1 时 master 删 power_pole residual slots.
power subproblem feasible 后注入 synthetic power_pole entry, 但 cut 走
ExactCoordinateMaster._conflict_pose_entries 找 slots 时 power_pole tpl 已
没 slot → 找不到 presence literal → cut 只约束 powered widget, 等于 cut 掉
"layout + 任意 pole witness" = 过切真实存在的 pole alternatives.

stop-gap: _add_exact_whole_layout_nogood 在 flag on 时如果 solution 含
synthetic pole, 直接 fail-closed 跳过 cut 并返回 False, caller 升 UNKNOWN.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import mock

from ortools.sat.python import cp_model

from src.models.cut_manager import CutManager
from src.models.master_model import MasterPlacementModel


def _fixture_one_powered_one_pole():
    instances = [
        {
            "instance_id": "powered_001",
            "facility_type": "powered_widget",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "powered_widget": [
            {
                "pose_id": "machine_left",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
        "power_pole": [
            {
                "pose_id": "pole_right",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0]],
            },
        ],
        "protocol_storage_box": [],
    }
    rules = {
        "globals": {"grid": {"width": 3, "height": 1}},
        "facility_templates": {
            "powered_widget": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    return instances, pools, rules


def _build_controller(master):
    from src.search.benders_loop import LBBDController

    ckpt = Path(tempfile.mkdtemp(prefix="zmd_pwcd_"))
    cm = CutManager(checkpoint_dir=ckpt, solve_mode="certified_exact")
    return LBBDController(
        master=master,
        cut_manager=cm,
        project_root=ckpt.parent,
        solve_mode="certified_exact",
    )


def test_whole_layout_cut_dilution_fails_closed_when_synthetic_pole_loses_literal():
    """synthetic pose_optional::power_pole:: 不能贡献 presence literal.

    The cut builder must fail closed instead of diluting {machine, pole} into a
    stronger machine-only nogood.
    """
    from src.models.power_placement_subproblem import (
        PowerPlacementSubproblem,
        inject_power_poles_into_solution,
    )

    instances, pools, rules = _fixture_one_powered_one_pole()
    with mock.patch.dict(
        os.environ,
        {
            "EXACT_POWER_PLACEMENT_SUBPROBLEM": "1",
            "EXACT_POWER_PLACEMENT_SUBPROBLEM_ALLOW_FORENSIC_TEST": "1",
        },
    ):
        core = MasterPlacementModel.build_exact_core(
            instances, pools, rules, skip_power_coverage=True,
        )
        slot_counts = core.build_stats.get("master_slot_counts", {})
        residuals = slot_counts.get("residual_optionals", {})
        assert "power_pole" not in residuals, (
            "P0 #2 fixture 前提失败: flag on 应删 power_pole residual slots"
        )

        overlay = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
        status = overlay.solve(time_limit_seconds=5.0)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        solution = overlay.extract_solution()
        sub = PowerPlacementSubproblem(
            master_solution=solution,
            facility_pools=overlay.facility_pools,
            powered_templates=overlay._powered_templates,
            power_coverers_by_template_pose=overlay._power_coverers_by_template_pose,
        )
        sub.build()
        result = sub.solve(time_limit_seconds=5.0)
        assert result.status == "FEASIBLE"
        injected = inject_power_poles_into_solution(
            solution,
            selected_pose_indices=result.selected_pose_indices,
            facility_pools=overlay.facility_pools,
            solve_mode="certified_exact",
        )
        conflict_set = {k: int(v["pose_idx"]) for k, v in injected.items()}
        added = overlay.add_benders_cut(conflict_set)
        assert added is False
        assert overlay.build_stats.get("coordinate_benders_last_cut") is None


def test_whole_layout_nogood_fails_closed_when_flag_on_with_synthetic_pole():
    """flag on 且 solution 含 synthetic pole → _add_exact_whole_layout_nogood
    返回 False (fail-closed, cut 没产生).
    """
    instances, pools, rules = _fixture_one_powered_one_pole()
    with mock.patch.dict(
        os.environ,
        {
            "EXACT_POWER_PLACEMENT_SUBPROBLEM": "1",
            "EXACT_POWER_PLACEMENT_SUBPROBLEM_ALLOW_FORENSIC_TEST": "1",
        },
    ):
        core = MasterPlacementModel.build_exact_core(
            instances, pools, rules, skip_power_coverage=True,
        )
        master = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
        master.solve(time_limit_seconds=5.0)
        controller = _build_controller(master)
        fake_solution = {
            "powered_001": {
                "instance_id": "powered_001",
                "facility_type": "powered_widget",
                "pose_idx": 0,
            },
            "pose_optional::power_pole::pole_right": {
                "instance_id": "pose_optional::power_pole::pole_right",
                "facility_type": "power_pole",
                "pose_idx": 0,
            },
        }
        applied = controller._add_exact_whole_layout_nogood(
            solution=fake_solution,
            iteration=1,
            cut_type="binding_infeasible_nogood",
            proof_stage="binding",
            binding_exhausted=True,
            routing_exhausted=False,
            proof_summary={"mode": "certified_exact"},
        )
    assert applied is False, (
        "flag on + synthetic pole 时 whole-layout cut 应 fail-closed 不产 cut. "
        "否则 cut 会丢 pole literal → 过切 pole alternatives."
    )


def test_whole_layout_nogood_normal_path_flag_off():
    """flag off (default) 时, _add_exact_whole_layout_nogood 应正常产 cut → True."""
    instances, pools, rules = _fixture_one_powered_one_pole()
    with mock.patch.dict(os.environ, {"EXACT_POWER_PLACEMENT_SUBPROBLEM": ""}):
        core = MasterPlacementModel.build_exact_core(
            instances, pools, rules, skip_power_coverage=True,
        )
        master = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
        master.solve(time_limit_seconds=5.0)
        controller = _build_controller(master)
        fake_solution = {
            "powered_001": {
                "instance_id": "powered_001",
                "facility_type": "powered_widget",
                "pose_idx": 0,
            },
        }
        applied = controller._add_exact_whole_layout_nogood(
            solution=fake_solution,
            iteration=1,
            cut_type="binding_infeasible_nogood",
            proof_stage="binding",
            binding_exhausted=True,
            routing_exhausted=False,
            proof_summary={"mode": "certified_exact"},
        )
    assert applied is True


def test_whole_layout_nogood_propagates_master_rejection_for_unresolved_member():
    """If the master cannot encode a whole-layout member, helper must return False.

    This keeps binding/routing callers from treating a rejected exact-safe cut as
    an applied master cut.
    """
    instances, pools, rules = _fixture_one_powered_one_pole()
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True,
    )
    master = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
    master.solve(time_limit_seconds=5.0)
    controller = _build_controller(master)

    applied = controller._add_exact_whole_layout_nogood(
        solution={
            "missing_001": {
                "instance_id": "missing_001",
                "facility_type": "powered_widget",
                "pose_idx": 0,
            }
        },
        iteration=1,
        cut_type="binding_infeasible_nogood",
        proof_stage="binding",
        binding_exhausted=True,
        routing_exhausted=False,
        proof_summary={"mode": "certified_exact"},
    )

    assert applied is False
    assert controller.generated_exact_safe_cuts == []
    assert controller.cut_manager.cuts == []


def _fixture_powered_with_unpowered_pole_blocker():
    instances = [
        {
            "instance_id": "powered_001",
            "facility_type": "powered_widget",
            "operation_type": "processing",
            "is_mandatory": True,
            "bound_type": "exact",
        },
        {
            "instance_id": "boundary_001",
            "facility_type": "boundary_storage_port",
            "operation_type": "boundary_io",
            "is_mandatory": True,
            "bound_type": "exact",
        },
    ]
    pools = {
        "powered_widget": [
            {
                "pose_id": "machine_left",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
        "boundary_storage_port": [
            {
                "pose_id": "unpowered_blocker_on_only_pole_cell",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ],
        "power_pole": [
            {
                "pose_id": "only_covering_pole",
                "anchor": {"x": 2, "y": 0},
                "occupied_cells": [[2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": [[0, 0]],
            },
        ],
        "protocol_storage_box": [],
    }
    rules = {
        "globals": {"grid": {"width": 4, "height": 1}},
        "facility_templates": {
            "powered_widget": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
            "boundary_storage_port": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "power_pole": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
            "protocol_storage_box": {"dimensions": {"w": 1, "h": 1}, "needs_power": True},
        },
    }
    return instances, pools, rules


def test_power_subproblem_infeasible_cut_keeps_unpowered_occupancy_support():
    """Unpowered placed cells can make the deferred pole subproblem infeasible.

    The ghost-conditioned power cut must therefore retain every fixed facility
    occupancy literal used by the subproblem, not just the powered consumers.
    Otherwise the cut can reject a later layout with the same powered machine
    and ghost anchor after moving the unpowered blocker away from the only pole
    cell.
    """
    instances, pools, rules = _fixture_powered_with_unpowered_pole_blocker()
    with mock.patch.dict(
        os.environ,
        {
            "EXACT_POWER_PLACEMENT_SUBPROBLEM": "1",
            "EXACT_POWER_PLACEMENT_SUBPROBLEM_ALLOW_FORENSIC_TEST": "1",
        },
    ):
        core = MasterPlacementModel.build_exact_core(
            instances, pools, rules, skip_power_coverage=True,
        )
        master = MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))
        status = master.solve(time_limit_seconds=5.0)
        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        controller = _build_controller(master)
        solution = {
            "powered_001": {
                "instance_id": "powered_001",
                "facility_type": "powered_widget",
                "pose_idx": 0,
            },
            "boundary_001": {
                "instance_id": "boundary_001",
                "facility_type": "boundary_storage_port",
                "pose_idx": 0,
            },
        }
        outcome, payload = controller._run_power_placement_subproblem(
            solution=solution,
            iteration=1,
        )

    assert outcome == "INFEASIBLE_CUT_ADDED"
    assert payload is None
    assert controller.generated_exact_safe_cuts
    cut = controller.generated_exact_safe_cuts[-1]
    assert cut.cut_type == "power_subproblem_infeasible_nogood"
    assert cut.conflict_set == {"powered_001": 0, "boundary_001": 0}
