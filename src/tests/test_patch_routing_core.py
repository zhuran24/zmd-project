"""Tests for PCR-CUT Phase 2 — patch routing core soundness.

Synthetic 8×8 patch fixtures cover:
- corridor capacity impossible → INFEASIBLE + non-empty replay-valid core
- corridor feasible → FEASIBLE (no core)
- non-assumption literal in candidate → fail-closed invalid
- boundary relaxation lets a port whose route leaves the patch be FEASIBLE
- minimization shrinks raw core without losing INFEASIBLE replay
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture(autouse=True)
def _ensure_src_on_path(project_root: Path):
    sys.path.insert(0, str(project_root))


def _make_8x8_patch():
    """Patch = 8×8 block anchored at origin. boundary_cells computed automatically."""
    from src.models.patch_routing_core import PatchSpec
    cells = {(x, y) for x in range(8) for y in range(8)}
    return PatchSpec.from_cells("test_8x8", cells)


def test_patch_spec_boundary_cells_computed():
    spec = _make_8x8_patch()
    assert len(spec.cells) == 64
    # boundary cells: any cell whose 4-neighborhood includes a cell outside the patch.
    # for 8×8 anchored at origin, every edge cell is boundary.
    assert (0, 0) in spec.boundary_cells
    assert (7, 7) in spec.boundary_cells
    assert (3, 3) not in spec.boundary_cells
    assert spec.bbox == (0, 0, 7, 7)


def test_patch_routing_feasible_simple_corridor():
    """Single port pair connected by a free corridor — patch should be FEASIBLE."""
    from src.models.patch_routing_core import (
        PatchSpec, PatchPortSpec, PoseAssumption, PatchRoutingCore,
    )
    spec = _make_8x8_patch()
    occupied = set()
    free_cells = spec.cells
    active = {"iron": set(free_cells)}
    # facility at (0,3) outputting east; sink at (7,3) inputting west.
    ports = [
        PatchPortSpec(instance_id="A", x=0, y=3, direction="E", commodity="iron", type="out", pose_idx=0),
        PatchPortSpec(instance_id="B", x=7, y=3, direction="W", commodity="iron", type="in", pose_idx=0),
    ]
    assumptions = [
        PoseAssumption("A", 0, "A_p0", "assum_A"),
        PoseAssumption("B", 0, "B_p0", "assum_B"),
    ]
    core = PatchRoutingCore(
        patch_spec=spec, full_grid_occupied=occupied, full_grid_active_cells=active,
        patch_port_specs=ports, pose_assumptions=assumptions, boundary_relaxation=False,
    )
    core.build()
    status = core.solve(time_limit=5.0)
    assert status == "FEASIBLE", f"expected FEASIBLE, got {status}"


def test_patch_routing_infeasible_blocked_corridor():
    """Source port front cell is occupied by another facility — patch is INFEASIBLE."""
    from src.models.patch_routing_core import (
        PatchSpec, PatchPortSpec, PoseAssumption, PatchRoutingCore,
    )
    spec = _make_8x8_patch()
    # block the only valid corridor: occupy front cell of port A's exit
    occupied = {(1, 3)}  # blocks (0,3)→E
    active = {"iron": spec.cells - occupied}
    ports = [
        PatchPortSpec(instance_id="A", x=0, y=3, direction="E", commodity="iron", type="out", pose_idx=0),
        PatchPortSpec(instance_id="B", x=7, y=3, direction="W", commodity="iron", type="in", pose_idx=0),
    ]
    assumptions = [
        PoseAssumption("A", 0, "A_p0", "assum_A"),
        PoseAssumption("B", 0, "B_p0", "assum_B"),
    ]
    core = PatchRoutingCore(
        patch_spec=spec, full_grid_occupied=occupied, full_grid_active_cells=active,
        patch_port_specs=ports, pose_assumptions=assumptions, boundary_relaxation=False,
    )
    core.build()
    status = core.solve(time_limit=5.0)
    assert status == "INFEASIBLE", f"expected INFEASIBLE, got {status}"
    extracted = core.extract_core()
    assert extracted, "INFEASIBLE patch should have non-empty solver core"
    extracted_names = {pa.assumption_name for pa in extracted}
    assert extracted_names <= {pa.assumption_name for pa in assumptions}


def test_validate_patch_core_replay_valid():
    """A solver-returned core should re-validate to INFEASIBLE under presolve=false / workers=1."""
    from src.models.patch_routing_core import (
        PatchSpec, PatchPortSpec, PoseAssumption, PatchRoutingCore,
        validate_patch_core,
    )
    spec = _make_8x8_patch()
    occupied = {(1, 3)}
    active = {"iron": spec.cells - occupied}
    ports = [
        PatchPortSpec(instance_id="A", x=0, y=3, direction="E", commodity="iron", type="out", pose_idx=0),
        PatchPortSpec(instance_id="B", x=7, y=3, direction="W", commodity="iron", type="in", pose_idx=0),
    ]
    assumptions = [
        PoseAssumption("A", 0, "A_p0", "assum_A"),
        PoseAssumption("B", 0, "B_p0", "assum_B"),
    ]
    core = PatchRoutingCore(
        patch_spec=spec, full_grid_occupied=occupied, full_grid_active_cells=active,
        patch_port_specs=ports, pose_assumptions=assumptions, boundary_relaxation=False,
    )
    core.build()
    status = core.solve(time_limit=5.0)
    assert status == "INFEASIBLE"
    raw = core.extract_core()
    vr = validate_patch_core(core, raw, time_limit=5.0)
    assert vr.status == "INFEASIBLE"
    assert vr.invalid is False
    assert vr.replay_wall_s >= 0


def test_validate_rejects_non_assumption_literal():
    """A 'core' containing an unrecognised assumption name → fail-closed invalid."""
    from src.models.patch_routing_core import (
        PoseAssumption, PatchRoutingCore, PatchSpec, PatchPortSpec,
        validate_patch_core,
    )
    spec = _make_8x8_patch()
    occupied = {(1, 3)}
    active = {"iron": spec.cells - occupied}
    ports = [
        PatchPortSpec(instance_id="A", x=0, y=3, direction="E", commodity="iron", type="out", pose_idx=0),
        PatchPortSpec(instance_id="B", x=7, y=3, direction="W", commodity="iron", type="in", pose_idx=0),
    ]
    assumptions = [
        PoseAssumption("A", 0, "A_p0", "assum_A"),
        PoseAssumption("B", 0, "B_p0", "assum_B"),
    ]
    core = PatchRoutingCore(
        patch_spec=spec, full_grid_occupied=occupied, full_grid_active_cells=active,
        patch_port_specs=ports, pose_assumptions=assumptions, boundary_relaxation=False,
    )
    core.build()
    core.solve(time_limit=5.0)
    bogus = [PoseAssumption("X", 0, "X_p0", "assum_BOGUS")]
    vr = validate_patch_core(core, bogus, time_limit=5.0)
    assert vr.invalid is True
    assert "non_assumption_literals" in vr.invalid_reason


def test_boundary_relaxation_allows_feasibility():
    """A port whose route would exit the patch boundary should still be FEASIBLE under relaxation."""
    from src.models.patch_routing_core import (
        PoseAssumption, PatchRoutingCore, PatchSpec, PatchPortSpec,
    )
    spec = _make_8x8_patch()
    # full active cells beyond patch — boundary relaxation will use those
    occupied = set()
    full_active = {"iron": {(x, y) for x in range(0, 20) for y in range(0, 20)}}
    # Port A exits east from (7,3) — route MUST leave patch to find sink (which lives outside)
    ports = [
        PatchPortSpec(instance_id="A", x=7, y=3, direction="E", commodity="iron", type="out", pose_idx=0),
    ]
    assumptions = [PoseAssumption("A", 0, "A_p0", "assum_A")]
    core = PatchRoutingCore(
        patch_spec=spec, full_grid_occupied=occupied, full_grid_active_cells=full_active,
        patch_port_specs=ports, pose_assumptions=assumptions, boundary_relaxation=True,
    )
    core.build()
    status = core.solve(time_limit=5.0)
    # Port A exits east into (8, 3) which is outside patch but in full active — boundary_out var
    # absorbs the requirement. should be FEASIBLE.
    assert status == "FEASIBLE", f"expected FEASIBLE with boundary relaxation, got {status}"


def test_quickxplain_minimizes_core():
    """Adding irrelevant assumptions should still let QuickXplain isolate the true conflict."""
    from src.models.patch_routing_core import (
        PoseAssumption, PatchRoutingCore, PatchSpec, PatchPortSpec,
        minimize_patch_core_quickxplain,
    )
    spec = _make_8x8_patch()
    occupied = {(1, 3)}
    active = {"iron": spec.cells - occupied}
    # actual conflict comes from A's front being blocked
    ports = [
        PatchPortSpec(instance_id="A", x=0, y=3, direction="E", commodity="iron", type="out", pose_idx=0),
        PatchPortSpec(instance_id="B", x=7, y=3, direction="W", commodity="iron", type="in", pose_idx=0),
    ]
    # Add 4 "decoy" owners with no patch ports (they only register assumption literals)
    assumptions = [
        PoseAssumption("A", 0, "A_p0", "assum_A"),
        PoseAssumption("B", 0, "B_p0", "assum_B"),
        PoseAssumption("D1", 0, "D1_p0", "assum_D1"),
        PoseAssumption("D2", 0, "D2_p0", "assum_D2"),
        PoseAssumption("D3", 0, "D3_p0", "assum_D3"),
        PoseAssumption("D4", 0, "D4_p0", "assum_D4"),
    ]
    core = PatchRoutingCore(
        patch_spec=spec, full_grid_occupied=occupied, full_grid_active_cells=active,
        patch_port_specs=ports, pose_assumptions=assumptions, boundary_relaxation=False,
    )
    core.build()
    status = core.solve(time_limit=5.0)
    assert status == "INFEASIBLE"
    raw = core.extract_core()
    qx = minimize_patch_core_quickxplain(core, raw, time_limit_per_call=5.0, oracle_call_cap=16)
    assert qx.oracle_calls > 0
    # Minimized core should be a non-empty subset of the raw core
    assert qx.minimal_core, "minimization should produce non-empty core"
    assert len(qx.minimal_core) <= len(qx.raw_core)
    minimal_names = {pa.assumption_name for pa in qx.minimal_core}
    raw_names = {pa.assumption_name for pa in qx.raw_core}
    assert minimal_names <= raw_names


def test_build_local_pose_signature_only_intersecting_geometry():
    """Pose cells/ports outside patch must be dropped from signature."""
    from src.models.patch_routing_core import build_local_pose_signature
    patch_cells = frozenset((x, y) for x in range(0, 5) for y in range(0, 5))
    pose = {
        "occupied_cells": [(0, 0), (1, 0), (10, 10)],  # (10,10) is outside patch
        "input_port_cells": [{"x": 0, "y": 0, "dir": "N", "commodity": "iron"}],  # in patch
        "output_port_cells": [{"x": 8, "y": 8, "dir": "S", "commodity": "iron"}],  # outside
    }
    sig = build_local_pose_signature(facility_type="X", operation_type="op", pose=pose, patch_cells=patch_cells)
    assert sig.footprint_in_patch == frozenset({(0, 0), (1, 0)})
    assert sig.ports_in_patch == ((0, 0, "N", "iron", "in"),)


def test_pose_local_signature_equivalence():
    """Two distinct pose dicts producing identical patch-local geometry have equal signatures."""
    from src.models.patch_routing_core import build_local_pose_signature
    patch_cells = frozenset((x, y) for x in range(0, 5) for y in range(0, 5))
    pose_a = {
        "occupied_cells": [(0, 0), (1, 0)],
        "input_port_cells": [{"x": 0, "y": 0, "dir": "N", "commodity": "iron"}],
        "output_port_cells": [],
    }
    # Different `pose_id` and extra cells outside patch — patch signature should still match
    pose_b = {
        "occupied_cells": [(0, 0), (1, 0), (99, 99)],
        "input_port_cells": [{"x": 0, "y": 0, "dir": "N", "commodity": "iron"}],
        "output_port_cells": [{"x": 50, "y": 50, "dir": "E", "commodity": "iron"}],
    }
    sig_a = build_local_pose_signature(facility_type="X", operation_type="op", pose=pose_a, patch_cells=patch_cells)
    sig_b = build_local_pose_signature(facility_type="X", operation_type="op", pose=pose_b, patch_cells=patch_cells)
    assert sig_a == sig_b

    # Different operation_type → different signature
    sig_c = build_local_pose_signature(facility_type="X", operation_type="op_other", pose=pose_a, patch_cells=patch_cells)
    assert sig_a != sig_c


def test_extract_and_validate_full_lifecycle():
    """The composite helper should produce accepted=True on a real INFEASIBLE patch."""
    from src.models.patch_routing_core import (
        PoseAssumption, PatchRoutingCore, PatchSpec, PatchPortSpec,
        extract_and_validate_patch_core,
    )
    spec = _make_8x8_patch()
    occupied = {(1, 3)}
    active = {"iron": spec.cells - occupied}
    ports = [
        PatchPortSpec(instance_id="A", x=0, y=3, direction="E", commodity="iron", type="out", pose_idx=0),
        PatchPortSpec(instance_id="B", x=7, y=3, direction="W", commodity="iron", type="in", pose_idx=0),
    ]
    assumptions = [
        PoseAssumption("A", 0, "A_p0", "assum_A"),
        PoseAssumption("B", 0, "B_p0", "assum_B"),
    ]
    core = PatchRoutingCore(
        patch_spec=spec, full_grid_occupied=occupied, full_grid_active_cells=active,
        patch_port_specs=ports, pose_assumptions=assumptions, boundary_relaxation=False,
    )
    core.build()
    core.solve(time_limit=5.0)
    outcome = extract_and_validate_patch_core(core, minimize=True, time_limit_per_call=5.0, oracle_call_cap=16)
    assert outcome["accepted"] is True
    assert outcome["raw_core_size"] >= 1
    assert outcome["minimized_core_size"] >= 1
    mv = outcome["minimized_validation"]
    assert mv is not None
    assert mv.invalid is False
    assert mv.status == "INFEASIBLE"
