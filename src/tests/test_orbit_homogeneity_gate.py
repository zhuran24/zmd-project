"""M4-D4 red tests (R8): the P-HOM structural gate.

The F5 orbit lift is sound only while mandatory groups are homogeneous;
these tests pin the three failure surfaces: non-homogeneous groups are
refused (digest None → state builder attaches nothing), per-instance pose
dimensions are refused, and a digest drift quarantines stale cuts through
the existing step-6 artifact-hash mechanism.
"""
from __future__ import annotations

from src.search.orbit_homogeneity import (
    ORBIT_HOMOGENEITY_DIGEST_KEY,
    compute_orbit_homogeneity_digest,
)


def _homogeneous_instances():
    return [
        {
            "instance_id": f"miner_{i:03d}",
            "facility_type": "miner",
            "operation_type": "mining",
            "is_mandatory": True,
            "bound_type": "exact",
        }
        for i in (1, 2, 3)
    ]


def _pools():
    return {
        "miner": [
            {
                "pose_id": "p0",
                "anchor": {"x": 0, "y": 0},
                "occupied_cells": [[0, 0]],
                "input_port_cells": [],
                "output_port_cells": [],
            }
        ]
    }


def test_homogeneous_groups_yield_stable_digest() -> None:
    d1 = compute_orbit_homogeneity_digest(_homogeneous_instances(), _pools())
    d2 = compute_orbit_homogeneity_digest(_homogeneous_instances(), _pools())
    assert d1 is not None
    assert d1 == d2  # deterministic — safe to pin into CutScope


def test_non_homogeneous_group_fails_closed() -> None:
    """R8: one member carrying an extra per-instance attribute poisons the
    whole premise — lifting a pattern across such a group would generalise a
    verdict past what the oracle refuted."""
    instances = _homogeneous_instances()
    instances[1] = dict(instances[1], special_attribute="golden_miner")
    assert compute_orbit_homogeneity_digest(instances, _pools()) is None


def test_per_instance_pose_dimension_fails_closed() -> None:
    pools = _pools()
    pools["miner"][0] = dict(pools["miner"][0], instance_id="miner_001")
    assert compute_orbit_homogeneity_digest(_homogeneous_instances(), pools) is None


def test_digest_shifts_when_group_record_changes() -> None:
    """A homogeneous-but-different group snapshot must change the digest —
    that is what re-scopes (quarantines) previously attached F5 cuts."""
    base = compute_orbit_homogeneity_digest(_homogeneous_instances(), _pools())
    changed_instances = [
        dict(inst, bound_type="relaxed") for inst in _homogeneous_instances()
    ]
    changed = compute_orbit_homogeneity_digest(changed_instances, _pools())
    assert base is not None and changed is not None
    assert base != changed


def test_state_builder_refuses_non_homogeneous_master() -> None:
    """End-to-end fail-closed: a master whose source_instances are not
    homogeneous must yield no framework state at all (no attach, no cuts)."""
    import os
    from unittest import mock

    from ortools.sat.python import cp_model

    from src.models.master_model import MasterPlacementModel
    from src.tests.test_cut_framework_attach_wiring import _controller

    instances = _homogeneous_instances()[:2]
    instances[1] = dict(instances[1], special_attribute="golden_miner")
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
    with mock.patch.dict(os.environ, {"EXACT_CUT_FRAMEWORK_ATTACH": "1"}):
        state = controller._build_cut_framework_state()
        attached = controller._maybe_attach_framework_cuts(
            trigger="binding_infeasible", iteration=1
        )
    assert state is None
    assert attached == 0


def test_digest_key_is_injected_into_state_artifact_hashes() -> None:
    from ortools.sat.python import cp_model

    from src.models.master_model import MasterPlacementModel
    from src.tests.test_cut_framework_attach_wiring import (
        _build_miner_master,
        _controller,
    )

    master = _build_miner_master()
    assert master.solve(time_limit_seconds=5.0) in (
        cp_model.OPTIMAL,
        cp_model.FEASIBLE,
    )
    controller = _controller(master)
    state = controller._build_cut_framework_state()
    assert state is not None
    digest = state.artifact_hashes.get(ORBIT_HOMOGENEITY_DIGEST_KEY)
    assert isinstance(digest, str) and len(digest) == 64
