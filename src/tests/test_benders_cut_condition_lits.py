"""Regression for ghost-conditioned Benders cut (P0 #1, GPT v3 finding).

Before fix: power infeasible cut omitted the selected ghost anchor literal,
which over-pruned the same powered-facility pose combination under a *different*
ghost anchor where the layout would have been power-feasible.

After fix: add_benders_cut(conflict, condition_lits=[u_var]) only bans the
combination when the condition literal is true, leaving other ghosts untouched.
"""
from __future__ import annotations

from ortools.sat.python import cp_model

from src.models.master_model import MasterPlacementModel


def _fixture_with_neutral_ghost_slot():
    # 4x1 grid:
    #   cell 0 -> pose A   cell 1 -> (ghost neutral)
    #   cell 2 -> pose B   cell 3 -> pose C
    # ghost_rect (1,1) -> 4 candidate anchors at (0..3, 0).
    # ghost anchor (1,0) doesn't overlap any miner pose -> all 3 miner combos
    # {AB, AC, BC} feasible under this ghost.
    instances = [
        {"instance_id": "miner_001", "facility_type": "miner",
         "operation_type": "mining", "is_mandatory": True, "bound_type": "exact"},
        {"instance_id": "miner_002", "facility_type": "miner",
         "operation_type": "mining", "is_mandatory": True, "bound_type": "exact"},
    ]
    pools = {
        "miner": [
            {"pose_id": "A", "anchor": {"x": 0, "y": 0},
             "occupied_cells": [[0, 0]], "input_port_cells": [],
             "output_port_cells": [], "power_coverage_cells": None},
            {"pose_id": "B", "anchor": {"x": 2, "y": 0},
             "occupied_cells": [[2, 0]], "input_port_cells": [],
             "output_port_cells": [], "power_coverage_cells": None},
            {"pose_id": "C", "anchor": {"x": 3, "y": 0},
             "occupied_cells": [[3, 0]], "input_port_cells": [],
             "output_port_cells": [], "power_coverage_cells": None},
        ]
    }
    rules = {
        "globals": {"grid": {"width": 4, "height": 1}},
        "facility_templates": {
            "miner": {"dimensions": {"w": 1, "h": 1}, "needs_power": False},
        },
    }
    return instances, pools, rules


def _build_overlay():
    instances, pools, rules = _fixture_with_neutral_ghost_slot()
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True,
    )
    return MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


def _miner_pose_ids(overlay: MasterPlacementModel) -> set:
    solution = overlay.extract_solution()
    pool = overlay.facility_pools["miner"]
    return {pool[int(e["pose_idx"])]["pose_id"]
            for iid, e in solution.items() if iid.startswith("miner_")}


def _solve_ok(overlay: MasterPlacementModel) -> int:
    status = overlay.solve(time_limit_seconds=5.0)
    assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE), f"status={status}"
    return status


def _ghost_rect_idx_for_anchor(overlay: MasterPlacementModel, x: int, y: int) -> int:
    for idx, dom in enumerate(overlay._ghost_domains):
        a = dom.get("anchor") or {}
        if int(a.get("x", -1)) == x and int(a.get("y", -1)) == y:
            return idx
    raise AssertionError(f"no ghost anchor at ({x},{y}); have {overlay._ghost_domains}")


def test_conditioned_cut_only_fires_under_its_own_ghost_anchor():
    # Pick the neutral ghost anchor (1,0). Force it, observe one miner combo,
    # add a conditioned cut against that combo for ghost=(1,0), then force a
    # *different* ghost anchor (still (1,0)-free) and the same forbidden combo
    # must remain feasible.
    overlay = _build_overlay()
    neutral_idx = _ghost_rect_idx_for_anchor(overlay, 1, 0)
    overlay.model.Add(overlay.u_vars[neutral_idx] == 1)
    _solve_ok(overlay)
    combo1 = _miner_pose_ids(overlay)
    assert combo1.issubset({"A", "B", "C"}) and len(combo1) == 2

    # Add conditioned cut: only forbid this combo when ghost=(1,0).
    solution = overlay.extract_solution()
    miners_assignment = {
        iid: int(e["pose_idx"]) for iid, e in solution.items()
        if iid.startswith("miner_")
    }
    cond_var = overlay.u_vars[neutral_idx]
    assert overlay.add_benders_cut(miners_assignment, condition_lits=[cond_var]) is True

    # Build a *fresh* overlay so the model is clean, replay the cut, then force
    # a different ghost — cut must not fire.
    overlay2 = _build_overlay()
    neutral_idx2 = _ghost_rect_idx_for_anchor(overlay2, 1, 0)
    assert overlay2.add_benders_cut(
        miners_assignment, condition_lits=[overlay2.u_vars[neutral_idx2]]
    ) is True
    other_idx = _ghost_rect_idx_for_anchor(overlay2, 0, 0)  # ghost overlaps pose A
    overlay2.model.Add(overlay2.u_vars[other_idx] == 1)
    _solve_ok(overlay2)
    combo2 = _miner_pose_ids(overlay2)
    # Under ghost=(0,0), pose A is blocked, so miners must use {B,C}. Cut was
    # conditioned on ghost=(1,0), so it should *not* contribute here.
    assert combo2 == {"B", "C"}, (
        f"conditioned cut over-pruned under a different ghost anchor: got {combo2}"
    )


def test_conditioned_cut_does_fire_when_its_condition_is_active():
    overlay = _build_overlay()
    neutral_idx = _ghost_rect_idx_for_anchor(overlay, 1, 0)
    overlay.model.Add(overlay.u_vars[neutral_idx] == 1)
    _solve_ok(overlay)
    combo1 = _miner_pose_ids(overlay)
    miners_assignment = {
        iid: int(e["pose_idx"]) for iid, e in overlay.extract_solution().items()
        if iid.startswith("miner_")
    }

    # Fresh overlay, same condition, force same neutral ghost — cut must fire.
    overlay2 = _build_overlay()
    neutral_idx2 = _ghost_rect_idx_for_anchor(overlay2, 1, 0)
    assert overlay2.add_benders_cut(
        miners_assignment, condition_lits=[overlay2.u_vars[neutral_idx2]]
    ) is True
    overlay2.model.Add(overlay2.u_vars[neutral_idx2] == 1)
    _solve_ok(overlay2)
    combo2 = _miner_pose_ids(overlay2)
    assert combo2 != combo1, (
        f"conditioned cut failed to fire under its own ghost: combo unchanged={combo1}"
    )
    assert combo2.issubset({"A", "B", "C"}) and len(combo2) == 2


def test_empty_condition_lits_behaves_like_unconditional_cut():
    overlay = _build_overlay()
    neutral_idx = _ghost_rect_idx_for_anchor(overlay, 1, 0)
    overlay.model.Add(overlay.u_vars[neutral_idx] == 1)
    _solve_ok(overlay)
    miners_assignment = {
        iid: int(e["pose_idx"]) for iid, e in overlay.extract_solution().items()
        if iid.startswith("miner_")
    }
    combo1 = _miner_pose_ids(overlay)

    overlay2 = _build_overlay()
    assert overlay2.add_benders_cut(miners_assignment, condition_lits=()) is True
    neutral_idx2 = _ghost_rect_idx_for_anchor(overlay2, 1, 0)
    overlay2.model.Add(overlay2.u_vars[neutral_idx2] == 1)
    _solve_ok(overlay2)
    combo2 = _miner_pose_ids(overlay2)
    assert combo2 != combo1, "unconditional cut must remove the original combo"
