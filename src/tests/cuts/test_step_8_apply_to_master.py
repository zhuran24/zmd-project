"""Step 8 apply-to-master — F1 region_capacity translation (M3-3, P1.3).

Covers the first wired family end-to-end on a REAL coordinate master (the
lightweight 2-miner/3-pose fixture from the presence-nogood regression), plus
the fail-closed dispatch surface:

- F1 weighted-presence capacity constraint actually prunes: capacity 1 with a
  2-miner mandatory demand → INFEASIBLE; capacity 2 → still solvable.
- master rejecting the push (unknown group) → step_8 raises RuntimeError.
- un-wired families (F3 literal et al.) → NotImplementedError (M4 ladder).
- malformed cert numerics → ValueError before touching the master.

Scope/staleness gating deliberately NOT exercised here: that lives in
lifecycle steps 5-7; step_8 only translates an already-validated cut. The
attached inequality is physically valid for any feasible layout, so attach
soundness does not depend on cert freshness (see step_8 docstring).
"""
from __future__ import annotations

import hashlib
from typing import Mapping

import pytest
from ortools.sat.python import cp_model

from src.cuts.lifecycle import (
    AnonymousSlotRef,
    Cut,
    CutLiteral,
    CutScope,
    OracleCert,
    _encode_region_bitset,
    step_0_canonicalize,
    step_8_apply_to_master,
)
from src.models.master_model import MasterPlacementModel


def _f1_cert_payload(
    *,
    group_id: str,
    cells_per_pose: int,
    cap_r: int,
    demand_r: int,
) -> bytes:
    cert_dict = {
        "cert_kind": "region_capacity_combinatorial",
        "region_kind": "left_or_bottom_union",
        "region_cells_bitset_b64": _encode_region_bitset(
            [(0, 0), (2, 0), (4, 0)], grid_size=70
        ),
        "cap_R": cap_r,
        "demand_R": demand_r,
        "gap": demand_r - cap_r,
        "contributing_groups": [[group_id, demand_r]],
        "cells_per_pose": {group_id: cells_per_pose},
        "lp_dual_ray_b64": None,
        "lp_dual_objective": None,
    }
    return step_0_canonicalize(cert_dict)


def _f1_cut(payload: bytes) -> Cut:
    cert_hash = hashlib.sha256(payload).hexdigest()
    return Cut(
        cut_id=f"f1_test_{cert_hash[:8]}",
        family="region_capacity",
        literals=None,
        geometric_payload=payload,
        scope=CutScope(
            ghost_rect_id="ghost_test",
            blocked_cells_hash="h_blocked",
            exterior_blocks_hash="h_ext",
            source_digest="h_source",
            oracle_abstraction_version="region_capacity_v1",
            artifact_hashes={"canonical_rules.json": "h1"},
        ),
        cert=OracleCert(
            cert_kind="region_capacity_combinatorial",
            cert_payload=payload,
            cert_hash=cert_hash,
        ),
        oracle_name="region_capacity_v1",
    )


def _build_fixture_master() -> MasterPlacementModel:
    """2 mandatory miners / 3 disjoint single-cell poses on a 5×1 grid."""
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


def test_step_8_f1_capacity_prunes_end_to_end() -> None:
    """capacity=1 vs mandatory demand 2 → INFEASIBLE; capacity=2 → solvable."""
    master = _build_fixture_master()
    group_id = str(master._group_id_by_instance["miner_001"])

    # sanity: unconstrained fixture is solvable
    assert master.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )

    cut = _f1_cut(
        _f1_cert_payload(group_id=group_id, cells_per_pose=1, cap_r=1, demand_r=2)
    )
    step_8_apply_to_master(cut, master)
    stats = master.build_stats["coordinate_region_capacity_last_cut"]
    assert stats["capacity"] == 1
    assert stats["presence_terms"] == 3  # full 3-pose domain, weight 1 each
    assert master.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE

    # A fresh master with capacity=2 stays solvable (the inequality is the
    # physically-true bound, not an unconditional kill switch).
    master2 = _build_fixture_master()
    group2 = str(master2._group_id_by_instance["miner_001"])
    cut2 = _f1_cut(
        _f1_cert_payload(group_id=group2, cells_per_pose=1, cap_r=2, demand_r=2)
    )
    step_8_apply_to_master(cut2, master2)
    assert master2.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )


def test_step_8_f1_unknown_group_raises_fail_closed() -> None:
    master = _build_fixture_master()
    cut = _f1_cut(
        _f1_cert_payload(
            group_id="no_such_group", cells_per_pose=1, cap_r=1, demand_r=2
        )
    )
    with pytest.raises(RuntimeError, match="fail-closed"):
        step_8_apply_to_master(cut, master)


def test_step_8_unwired_family_fails_closed() -> None:
    payload = step_0_canonicalize(
        {
            "cert_kind": "port_exposure_blocked",
            "facility_group": "g",
            "facility_pose_id": "p",
            "port_cell": [0, 0],
            "port_direction": "W",
            "front_cell": [-1, 0],
            "blocking_facility": ["g2", 0, "p2"],
            "active_port_witness_b64": None,
        }
    )
    cut = Cut(
        cut_id="f3_test",
        family="port_exposure",
        literals=(
            CutLiteral(slot_ref=AnonymousSlotRef(group_id="g", slot_index=0), pose_id="p"),
        ),
        geometric_payload=None,
        scope=CutScope(
            ghost_rect_id="ghost_test",
            blocked_cells_hash="h",
            exterior_blocks_hash="h",
            source_digest="h",
            oracle_abstraction_version="port_exposure_v2_canonical_dirs",
            artifact_hashes={},
        ),
        cert=OracleCert(
            cert_kind="port_exposure_blocked",
            cert_payload=payload,
            cert_hash=hashlib.sha256(payload).hexdigest(),
        ),
        oracle_name="port_exposure_v2_canonical_dirs",
    )
    master = _build_fixture_master()
    with pytest.raises(NotImplementedError, match="port_exposure"):
        step_8_apply_to_master(cut, master)


def test_step_8_f1_malformed_numerics_raise_before_master() -> None:
    class _ExplodingMaster:
        def add_region_capacity_cut(
            self, *, group_cell_weights: Mapping[str, int], capacity: int
        ) -> bool:
            raise AssertionError("master must not be touched on malformed cert")

    bad_cpp = _f1_cut(
        _f1_cert_payload(group_id="g", cells_per_pose=0, cap_r=1, demand_r=2)
    )
    with pytest.raises(ValueError, match="cells_per_pose"):
        step_8_apply_to_master(bad_cpp, _ExplodingMaster())

    bad_cap = _f1_cut(
        _f1_cert_payload(group_id="g", cells_per_pose=1, cap_r=-1, demand_r=2)
    )
    with pytest.raises(ValueError, match="cap_R"):
        step_8_apply_to_master(bad_cap, _ExplodingMaster())
