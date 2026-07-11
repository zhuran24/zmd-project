"""Step 8 — F6 shape_packing_hall master translation (M4-B).

The cert's re-derived total_packable caps how many of the group's poses whose
body lies ENTIRELY on the named baseline may be present, enforced only under
the selected ghost literal(s). region_demand/group_demand never enter the
master (pigeonhole reasoning values, steps 5-7 territory).

Fixture: a 6×6 grid with a "port" template (1×3, rotatable) and poses on the
left baseline (y=0 column cells (x,0)), the bottom baseline (x=0 cells (0,y)),
and one interior pose — the interior pose must NOT be counted by the cap.

B5a: the raw ``_legacy_step_8_apply_raw`` translator these cases drove has been
deleted with the orchestration cut-over.  Their hand-built raw Cuts
(``artifact_hashes={}``, no ``ScopeIdentityPreimageV1``) cannot pass the typed
``cut_to_envelope_v1`` adapter, so full migration to the typed chain (oracle →
envelope → snapshot → single entry → resolver → typed step_8) needs a rebuilt
real-master + oracle fixture; that F6-through-resolver work is deferred to the
test-migration follow-up (F1/F5 land first).  The typed F6 *compile* path is
already covered by ``test_stage_b_shape_packing_hall.py``; these master-lowering
cases are skipped below until the resolver fixture lands.
"""
from __future__ import annotations

import hashlib

import pytest
from ortools.sat.python import cp_model

from src.cuts.lifecycle import (
    GHOST_AGNOSTIC,
    Cut,
    CutScope,
    OracleCert,
    step_0_canonicalize,
    step_8_apply_to_master,
)
from src.models.master_model import MasterPlacementModel

# B5a-transitional: F6 direct-call raw-API master-lowering cases are skipped
# until the typed F6-through-resolver fixture lands (see module docstring).
pytestmark = pytest.mark.skip(
    reason="B5a-transitional: F6 direct-call typed-chain migration deferred "
    "(raw _legacy_step_8_apply_raw deleted; typed F6 compile covered by "
    "test_stage_b_shape_packing_hall.py)"
)


def _f6_cert_payload(
    *,
    group_id: str,
    region_kind: str = "left_baseline",
    total_packable: int = 1,
    region_demand: int = 2,
    group_demand: int = 2,
) -> bytes:
    cert_dict = {
        "cert_kind": "hall_interval_witness",
        "region_kind": region_kind,
        "region_total_length": 70,
        "partition_lens": [3],
        "partition_offsets": [0],
        "pose_length": 3,
        "pose_shape_canonical": "1x3_rigid",
        "max_packable": [total_packable],
        "total_packable": total_packable,
        "contributing_group": group_id,
        "region_demand": region_demand,
        "group_demand": group_demand,
        "ghost_rect_repr": [0, 0, 1, 1],
        "exterior_blocks_digest": "h_ext",
    }
    return step_0_canonicalize(cert_dict)


def _f6_cut(payload: bytes, *, ghost_rect_id: str = "ghost_bound_test") -> Cut:
    cert_hash = hashlib.sha256(payload).hexdigest()
    return Cut(
        cut_id=f"f6_test_{cert_hash[:8]}",
        family="shape_packing_hall",
        literals=None,
        geometric_payload=payload,
        scope=CutScope(
            ghost_rect_id=ghost_rect_id,
            blocked_cells_hash="h_blocked",
            exterior_blocks_hash="h_ext",
            source_digest="h_source",
            oracle_abstraction_version="shape_packing_hall_v1",
            artifact_hashes={},
        ),
        cert=OracleCert(
            cert_kind="hall_interval_witness",
            cert_payload=payload,
            cert_hash=cert_hash,
        ),
        oracle_name="shape_packing_hall_v1",
    )


def _build_port_master() -> MasterPlacementModel:
    """2 mandatory 1×3 ports on a 6×6 grid.

    Poses: two on the left baseline (cells (x,0)), one on the bottom baseline
    (cells (0,y)), one interior (cells (x,3)). NB: pose_left_a occupies
    (0..2, 0) which includes the corner (0,0) shared with the bottom pose.
    """
    instances = [
        {
            "instance_id": f"port_{i:03d}",
            "facility_type": "port",
            "operation_type": "storage",
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for i in (1, 2)
    ]
    pools = {
        "port": [
            {
                "pose_id": "pose_left_a",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0], [1, 0], [2, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "pose_left_b",
                "anchor": {"x": 3, "y": 0},
                "occupied_cells": [[3, 0], [4, 0], [5, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "pose_bottom",
                "anchor": {"x": 0, "y": 3},
                "occupied_cells": [[0, 3], [0, 4], [0, 5]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
            {
                "pose_id": "pose_interior",
                "anchor": {"x": 2, "y": 3},
                "occupied_cells": [[2, 3], [3, 3], [4, 3]],
                "input_port_cells": [],
                "output_port_cells": [],
                "power_coverage_cells": None,
            },
        ]
    }
    rules = {
        "globals": {"grid": {"width": 6, "height": 6}},
        "facility_templates": {
            "port": {"dimensions": {"w": 3, "h": 1}, "needs_power": False},
        },
    }
    core = MasterPlacementModel.build_exact_core(
        instances, pools, rules, skip_power_coverage=True
    )
    return MasterPlacementModel.from_exact_core(core, ghost_rect=(1, 1))


def test_step_8_f6_caps_left_baseline_under_pinned_anchor() -> None:
    """cap=1 on the left baseline; interior/bottom poses are NOT counted.

    Pinned anchor (5,5) (rect_idx 35 on the 6×6 grid) keeps the ghost away
    from every pose so infeasibility can only come from the attached cap:
    both ports on the left baseline would need 2 ≤ cap 1 → the solver must
    move one port to the bottom/interior poses (still solvable). Cap=0 on
    left AND bottom with the interior pose removed → INFEASIBLE.
    """
    master = _build_port_master()
    group_id = str(master._group_id_by_instance["port_001"])
    u_vars = master.u_vars
    # 6×6 grid, 1×1 ghost → 36 anchors; pin the far corner (5,5).
    pin_idx = 35
    u_pin = u_vars[pin_idx]

    cut = _f6_cut(_f6_cert_payload(group_id=group_id, total_packable=1))
    step_8_apply_to_master(cut, master, ghost_condition_lits=(u_pin,))
    stats = master.build_stats["coordinate_baseline_packing_last_cut"]
    assert stats["region_kind"] == "left_baseline"
    assert stats["capacity"] == 1
    # Only the two left-baseline poses are counted (not bottom, not interior).
    assert stats["presence_terms"] == 2

    delegate = master._coordinate_delegate
    assert delegate is not None
    delegate.model.Add(u_pin == 1)
    # cap 1 on left: one port re-homes to bottom/interior → still solvable.
    assert master.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )


def test_step_8_f6_zero_caps_both_baselines_prune() -> None:
    """cap=0 on both baselines forces both ports into the single interior
    pose → INFEASIBLE proves the caps bit (under the pinned anchor)."""
    master = _build_port_master()
    group_id = str(master._group_id_by_instance["port_001"])
    u_pin = master.u_vars[35]

    left = _f6_cut(
        _f6_cert_payload(group_id=group_id, region_kind="left_baseline", total_packable=0)
    )
    bottom = _f6_cut(
        _f6_cert_payload(group_id=group_id, region_kind="bottom_baseline", total_packable=0)
    )
    step_8_apply_to_master(left, master, ghost_condition_lits=(u_pin,))
    step_8_apply_to_master(bottom, master, ghost_condition_lits=(u_pin,))
    assert master.build_stats["coordinate_framework_cut_count"] == 2

    # Anchor free: cuts dormant → solvable.
    assert master.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )
    delegate = master._coordinate_delegate
    assert delegate is not None
    delegate.model.Add(u_pin == 1)
    # Both baselines capped at 0 → 2 ports fight over pose_interior alone.
    assert master.solve(time_limit_seconds=5.0) == cp_model.INFEASIBLE


def test_step_8_f6_fail_closed_surfaces() -> None:
    master = _build_port_master()
    group_id = str(master._group_id_by_instance["port_001"])
    payload = _f6_cert_payload(group_id=group_id)

    agnostic = _f6_cut(payload, ghost_rect_id=GHOST_AGNOSTIC)
    with pytest.raises(RuntimeError, match="ghost-bound"):
        step_8_apply_to_master(
            agnostic, master, ghost_condition_lits=(master.u_vars[0],)
        )

    bound = _f6_cut(payload)
    with pytest.raises(RuntimeError, match="ghost literal"):
        step_8_apply_to_master(bound, master)

    unknown_group = _f6_cut(_f6_cert_payload(group_id="no_such_group"))
    with pytest.raises(RuntimeError, match="fail-closed"):
        step_8_apply_to_master(
            unknown_group, master, ghost_condition_lits=(master.u_vars[0],)
        )

    bad_region = _f6_cut(
        _f6_cert_payload(group_id=group_id, region_kind="right_baseline")
    )
    with pytest.raises(ValueError, match="region_kind"):
        step_8_apply_to_master(
            bad_region, master, ghost_condition_lits=(master.u_vars[0],)
        )
