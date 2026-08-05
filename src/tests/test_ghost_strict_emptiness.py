"""Strict empty-rectangle semantics: nothing at all may sit inside the ghost.

Authority: owner adjudication 2026-08-05
(``docs/research/rules_audit_20260718/02_empty_rectangle_semantics_adjudication_20260805.md``)
— "空地当时的定义就是什么都不能有".  Before that ruling the repo carried a
looser reading in which the ghost rect only excluded facility bodies, so belts
and bridges were free to cross the hole.  These tests pin the strict reading on
both certified consumers of the occupancy set: the live Benders routing domain
and the terminal fixed-witness verifier.

The second half of the file pins the cut side.  Making the ghost an obstacle
turns "blocked because of the hole" into a real outcome, and a blocked-port cut
carries no ghost condition — emitting it unconditionally would prune layouts
that are perfectly legal under a *different* ghost anchor.  v1 answers that by
emitting nothing at all: fewer cuts only costs iterations, never correctness.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Mapping, Sequence, Set, Tuple

import pytest

from src.search import benders_loop as bl
from src.search import pr2_l0_fixed_witness_core as fw
from src.models.routing_subproblem import (
    GHOST_RESERVED_OWNER_ID,
    RoutingGrid,
    RoutingPlacementCore,
    analyze_exact_routing_domain,
    run_exact_routing_precheck,
)


GRID_W = 70
GRID_H = 70

_GHOST_ANCHOR = (10, 10)
_GHOST_W = 3
_GHOST_H = 3
_GHOST_CELLS = {
    (_GHOST_ANCHOR[0] + dx, _GHOST_ANCHOR[1] + dy)
    for dx in range(_GHOST_W)
    for dy in range(_GHOST_H)
}


_MINIMAL_CERTIFIED_BINDING_RULES: Dict[str, Any] = {
    "commodity_metadata": {
        "ore": {"source_kind": "none", "sink_kind": "none"},
    },
}


def _ghost_master(
    *,
    facility_pools: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    source_instances: Sequence[Mapping[str, Any]] | None = None,
    ghost_cells: Set[Tuple[int, int]] = _GHOST_CELLS,
    anchor: Tuple[int, int] = _GHOST_ANCHOR,
) -> SimpleNamespace:
    """A master stub that carries a resolvable live ghost literal.

    ``_selected_ghost_context`` reads ``u_vars`` + ``_ghost_domains`` + the live
    solver, so a stub has to provide all three for the strict path to engage.
    """

    u_var = object()
    return SimpleNamespace(
        facility_pools=dict(facility_pools or {"T": [{"occupied_cells": [[0, 0]]}]}),
        source_instances=list(
            source_instances or [{"instance_id": "i", "facility_type": "T"}]
        ),
        grid_w=GRID_W,
        grid_h=GRID_H,
        generic_io_requirements={
            "required_generic_outputs": {},
            "required_generic_inputs": {},
        },
        rules=_MINIMAL_CERTIFIED_BINDING_RULES,
        u_vars={0: u_var},
        _ghost_domains=[
            {
                "anchor": {"x": anchor[0], "y": anchor[1]},
                "cells": sorted([int(c[0]), int(c[1])] for c in ghost_cells),
            }
        ],
        ghost_rect=(_GHOST_W, _GHOST_H),
        _solver=SimpleNamespace(Value=lambda _var: 1),
        _coordinate_delegate=None,
    )


def _ghost_pick(anchor: Tuple[int, int] = _GHOST_ANCHOR, pose_idx: int = 0) -> Dict[str, Any]:
    """The marker ``MasterPlacementModel.extract_solution`` stamps on a layout."""

    return {
        "instance_id": "ghost_pick",
        "facility_type": "ghost_rect",
        "pose_idx": pose_idx,
        "pose_id": f"ghost_anchor::{anchor[0]},{anchor[1]}",
        "anchor": {"x": anchor[0], "y": anchor[1]},
        "is_mandatory": False,
        "bound_type": "ghost_rect",
        "solve_mode": "certified_exact",
    }


def _solution_with_ghost() -> Dict[str, Any]:
    return {
        "i": {"facility_type": "T", "pose_idx": 0},
        "ghost_pick": _ghost_pick(),
    }


def _controller(master: SimpleNamespace, tmp_path: Path) -> Any:
    return bl.LBBDController(
        master=master,
        cut_manager=SimpleNamespace(),
        project_root=tmp_path,
        solve_mode="certified_exact",
        max_iterations=2,
        binding_seconds=0.01,
    )


# ---------------------------------------------------------------------------
# 1A #1/#2 — the live occupancy extractors must swallow the ghost
# ---------------------------------------------------------------------------


def test_extract_occupied_cells_includes_ghost_cells(tmp_path: Path) -> None:
    controller = _controller(_ghost_master(), tmp_path)
    occupied = controller._extract_occupied_cells(
        {"i": {"facility_type": "T", "pose_idx": 0}},
        ghost_cells=_GHOST_CELLS,
    )
    assert _GHOST_CELLS <= occupied
    assert (0, 0) in occupied


def test_extract_occupied_owner_by_cell_labels_ghost_with_reserved_id(
    tmp_path: Path,
) -> None:
    controller = _controller(_ghost_master(), tmp_path)
    owner_by_cell = controller._extract_occupied_owner_by_cell(
        {"i": {"facility_type": "T", "pose_idx": 0}},
        ghost_cells=_GHOST_CELLS,
    )
    for cell in _GHOST_CELLS:
        assert owner_by_cell[cell] == GHOST_RESERVED_OWNER_ID
    assert owner_by_cell[(0, 0)] == "i"


def test_ghost_owner_entries_fork_the_routing_occupancy_digest() -> None:
    """Two anchors must not share one occupancy digest.

    The terminal witness binds its routed layout through
    ``_routing_occupancy_digest``, which only reads the owner map.  Ghost cells
    that carried no owner would leave the digest anchor-blind — one digest
    "proving" occupancy under two different holes.
    """

    body_owner = {(0, 0): "i"}
    digest_a = fw._routing_occupancy_digest(
        {**body_owner, **{cell: GHOST_RESERVED_OWNER_ID for cell in _GHOST_CELLS}}
    )
    shifted = {(x + 20, y) for x, y in _GHOST_CELLS}
    digest_b = fw._routing_occupancy_digest(
        {**body_owner, **{cell: GHOST_RESERVED_OWNER_ID for cell in shifted}}
    )
    assert digest_a != digest_b


# ---------------------------------------------------------------------------
# 1H — an unresolvable ghost context must fail closed, never fall back to loose
# ---------------------------------------------------------------------------


def test_strict_ghost_occupancy_resolves_the_marked_ghost(tmp_path: Path) -> None:
    controller = _controller(_ghost_master(), tmp_path)
    assert controller._strict_ghost_occupancy(_solution_with_ghost()) == _GHOST_CELLS


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda sol: sol.pop("ghost_pick"), id="marker-missing"),
        pytest.param(
            lambda sol: sol["ghost_pick"].update({"pose_idx": 7}),
            id="index-out-of-range",
        ),
        pytest.param(
            lambda sol: sol["ghost_pick"].update({"anchor": {"x": 0, "y": 0}}),
            id="anchor-disagrees-with-domain",
        ),
        pytest.param(
            lambda sol: sol["ghost_pick"].update({"facility_type": "tiny"}),
            id="marker-is-not-a-ghost",
        ),
    ],
)
def test_strict_ghost_occupancy_fails_closed_on_broken_marker(
    tmp_path: Path, mutate: Any
) -> None:
    """Every unreadable shape must answer None, never an empty set.

    An empty set here is indistinguishable from "no hole", which is exactly the
    loose semantics this batch removed.
    """

    controller = _controller(_ghost_master(), tmp_path)
    solution = _solution_with_ghost()
    mutate(solution)
    assert controller._strict_ghost_occupancy(solution) is None


def test_strict_ghost_occupancy_fails_closed_when_live_literal_disagrees(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller = _controller(_ghost_master(), tmp_path)
    shifted = {(x + 20, y) for x, y in _GHOST_CELLS}
    monkeypatch.setattr(
        bl.LBBDController,
        "_selected_ghost_context",
        lambda self: (0, object(), {"x": 30, "y": 10}, shifted),
    )
    assert controller._strict_ghost_occupancy(_solution_with_ghost()) is None


def test_strict_ghost_occupancy_empty_without_ghost_machinery(tmp_path: Path) -> None:
    """A master with no ghost domain has no hole — that is not a fail-open."""

    master = _ghost_master()
    master.u_vars = {}
    master._ghost_domains = []
    controller = _controller(master, tmp_path)
    assert controller._strict_ghost_occupancy({"i": {"facility_type": "T"}}) == set()
    # A marker with no domain to resolve it against is malformed input.
    assert controller._strict_ghost_occupancy(_solution_with_ghost()) is None


def test_binding_and_routing_is_unknown_when_ghost_context_unresolvable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bl, "PortBindingModel", _FakeBindingModel)
    controller = _controller(_ghost_master(), tmp_path)

    status, result = controller._run_exact_binding_and_routing(
        iteration=1,
        solution={"i": {"facility_type": "T", "pose_idx": 0}},
        diagnostic_flow_status="not_run",
    )

    assert status == bl.RUN_STATUS_UNKNOWN
    assert result is None
    assert controller.last_proof_summary["master_follow_up"] == "fail_closed_unknown"
    assert (
        controller.last_proof_summary["subproblem_status_contract_violation"]
        == "strict_ghost_occupancy_unresolved"
    )


# ---------------------------------------------------------------------------
# 1B #4/#6 — the routing domain treats the hole as a wall
# ---------------------------------------------------------------------------


def _core_with_ghost(
    *,
    body_cells: Set[Tuple[int, int]] = frozenset(),
    ghost_cells: Set[Tuple[int, int]] = _GHOST_CELLS,
) -> RoutingPlacementCore:
    owner_map: Dict[Tuple[int, int], str] = {cell: "body" for cell in body_cells}
    owner_map.update({cell: GHOST_RESERVED_OWNER_ID for cell in ghost_cells})
    return RoutingPlacementCore.from_occupied_cells(
        set(body_cells) | set(ghost_cells),
        occupied_owner_by_cell=owner_map,
    )


def test_port_front_inside_the_ghost_is_reported_blocked() -> None:
    """Replays the band22 left_17/left_18 shape: a front cell inside the hole."""

    core = _core_with_ghost()
    port_specs = [
        {
            "instance_id": "left_17",
            "x": _GHOST_ANCHOR[0] + 1,
            "y": _GHOST_ANCHOR[1] + 1,
            "dir": "E",
            "type": "out",
            "commodity": "ore",
        }
    ]
    analysis = analyze_exact_routing_domain(
        placement_core=core,
        port_specs=port_specs,
        occupied_owner_by_cell=dict(core.occupied_owner_by_cell),
    )

    assert analysis["status"] == "front_blocked"
    blocked = analysis["blocked_ports"]
    assert len(blocked) == 1
    assert blocked[0]["instance_id"] == "left_17"
    assert GHOST_RESERVED_OWNER_ID in blocked[0]["blocking_instance_ids"]
    assert GHOST_RESERVED_OWNER_ID in blocked[0]["placement_level_conflict_set"]


def test_route_forced_through_the_ghost_is_not_feasible() -> None:
    """The hole is the only gap in a wall — the corridor must come apart."""

    wall_x = _GHOST_ANCHOR[0] + 1
    wall = {(wall_x, y) for y in range(GRID_H)} - _GHOST_CELLS
    core = _core_with_ghost(body_cells=wall)
    port_specs = [
        {
            "instance_id": "src",
            "x": wall_x - 2,
            "y": _GHOST_ANCHOR[1] + 1,
            "dir": "E",
            "type": "out",
            "commodity": "ore",
        },
        {
            "instance_id": "sink",
            "x": wall_x + 2,
            "y": _GHOST_ANCHOR[1] + 1,
            "dir": "W",
            "type": "in",
            "commodity": "ore",
        },
    ]
    analysis = analyze_exact_routing_domain(
        placement_core=core,
        port_specs=port_specs,
        occupied_owner_by_cell=dict(core.occupied_owner_by_cell),
    )
    assert analysis["status"] != "feasible"


def test_route_that_avoids_the_ghost_stays_feasible() -> None:
    """Same wall, but the gap is a real gap this time."""

    wall_x = _GHOST_ANCHOR[0] + 1
    gap = {(wall_x, _GHOST_ANCHOR[1] + 30)}
    wall = {(wall_x, y) for y in range(GRID_H)} - _GHOST_CELLS - gap
    core = _core_with_ghost(body_cells=wall)
    port_specs = [
        {
            "instance_id": "src",
            "x": wall_x - 2,
            "y": _GHOST_ANCHOR[1] + 30,
            "dir": "E",
            "type": "out",
            "commodity": "ore",
        },
        {
            "instance_id": "sink",
            "x": wall_x + 2,
            "y": _GHOST_ANCHOR[1] + 30,
            "dir": "W",
            "type": "in",
            "commodity": "ore",
        },
    ]
    analysis = analyze_exact_routing_domain(
        placement_core=core,
        port_specs=port_specs,
        occupied_owner_by_cell=dict(core.occupied_owner_by_cell),
    )
    assert analysis["status"] == "feasible"
    assert analysis["blocked_ports"] == []


# ---------------------------------------------------------------------------
# 1C — port cells inside the hole must not be added back to the walkable set
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("construction", ["init", "from_placement_core"])
def test_routable_cells_exclude_port_cells_inside_the_ghost(construction: str) -> None:
    ghost_port = (_GHOST_ANCHOR[0] + 1, _GHOST_ANCHOR[1] + 1)
    outside_port = (_GHOST_ANCHOR[0] + 1, _GHOST_ANCHOR[1] + 8)
    port_specs = [
        {
            "instance_id": "inside",
            "x": ghost_port[0],
            "y": ghost_port[1],
            "dir": "E",
            "type": "out",
            "commodity": "ore",
        },
        {
            "instance_id": "outside",
            "x": outside_port[0],
            "y": outside_port[1],
            "dir": "E",
            "type": "out",
            "commodity": "ore",
        },
    ]
    owner_map = {cell: GHOST_RESERVED_OWNER_ID for cell in _GHOST_CELLS}

    if construction == "init":
        grid = RoutingGrid(
            set(_GHOST_CELLS), port_specs, occupied_owner_by_cell=owner_map
        )
    else:
        grid = RoutingGrid.from_placement_core(_core_with_ghost(), port_specs)

    assert ghost_port not in grid.routable_cells
    assert outside_port in grid.routable_cells


# ---------------------------------------------------------------------------
# 1D — a ghost-attributed blocker must never mint an unconditional cut
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ghost_id", [GHOST_RESERVED_OWNER_ID, "ghost_pick"])
def test_conflict_from_instance_ids_is_empty_for_ghost_blockers(
    tmp_path: Path, ghost_id: str
) -> None:
    controller = _controller(_ghost_master(), tmp_path)
    solution = {
        "i": {"facility_type": "T", "pose_idx": 0},
        "ghost_pick": {"facility_type": "ghost_rect", "pose_idx": 0},
    }
    assert controller._build_conflict_from_instance_ids(solution, ["i", ghost_id]) == {}
    assert controller._build_conflict_from_instance_ids(solution, ["i"]) == {"i": 0}


def test_blocked_ports_well_formed_rejects_bad_ghost_sentinel_shapes() -> None:
    good = [
        {
            "instance_id": "left_17",
            "placement_level_conflict_set": ["left_17", GHOST_RESERVED_OWNER_ID],
            "blocking_instance_ids": [GHOST_RESERVED_OWNER_ID],
            "port_cell": [11, 11],
            "front_cell": [11, 11],
            "dir": "E",
        }
    ]
    assert bl._routing_precheck_blocked_ports_well_formed(good) is True

    ghost_as_owner = [{**good[0], "instance_id": GHOST_RESERVED_OWNER_ID}]
    assert bl._routing_precheck_blocked_ports_well_formed(ghost_as_owner) is False

    dropped_from_conflict_set = [
        {**good[0], "placement_level_conflict_set": ["left_17"]}
    ]
    assert (
        bl._routing_precheck_blocked_ports_well_formed(dropped_from_conflict_set)
        is False
    )


class _FakeBindingModel:
    """A binding model that is FEASIBLE once and offers no alternatives."""

    port_specs: List[Dict[str, Any]] = []

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.binding_vars: Dict[str, Any] = {}
        self.generic_input_vars: Dict[str, Any] = {}
        self.generic_output_vars: Dict[str, Any] = {}

    def build(self, *args: Any, **kwargs: Any) -> None:
        return None

    def extract_conflict_summary(self) -> Dict[str, Any]:
        return {}

    def extract_empty_binding_domain_instances(self) -> List[Any]:
        return []

    def solve(self, *args: Any, **kwargs: Any) -> str:
        return "FEASIBLE"

    def extract_selection(self) -> Dict[str, Any]:
        return {"sel": 1}

    def extract_port_specs(self) -> List[Dict[str, Any]]:
        return [dict(spec) for spec in type(self).port_specs]

    def add_nogood_cut(self, selection: Mapping[str, Any]) -> None:
        return None


class _FakeRoutingSubproblem:
    """Stand-in for the CP-SAT routing solve.

    Strict semantics reject the layout at the precheck and never build a routing
    model at all.  The stub exists so that a regression back to loose semantics
    fails fast instead of dropping into a real 70x70 solve.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.build_stats: Dict[str, Any] = {}

    @classmethod
    def from_placement_core(cls, *args: Any, **kwargs: Any) -> "_FakeRoutingSubproblem":
        return cls()

    def build(self) -> None:
        return None

    def solve(self, *args: Any, **kwargs: Any) -> str:
        return "INFEASIBLE"


def test_ghost_blocked_port_emits_no_nogood(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """front_blocked caused by the hole must stall, not cut.

    The blocker is the ghost, which owns no master literal.  Emitting the
    instance-level nogood anyway would forbid this layout under *every* anchor.
    """

    monkeypatch.delenv("EXACT_USE_POSE_BOOL_MASTER", raising=False)
    monkeypatch.setattr(
        _FakeBindingModel,
        "port_specs",
        [
            {
                "instance_id": "i",
                "x": _GHOST_ANCHOR[0] + 1,
                "y": _GHOST_ANCHOR[1] + 1,
                "dir": "E",
                "type": "out",
                "commodity": "ore",
            }
        ],
    )
    monkeypatch.setattr(bl, "PortBindingModel", _FakeBindingModel)
    monkeypatch.setattr(bl, "RoutingSubproblem", _FakeRoutingSubproblem)

    master = _ghost_master(
        facility_pools={"T": [{"occupied_cells": [[0, 0]]}]},
        source_instances=[{"instance_id": "i", "facility_type": "T"}],
    )
    controller = _controller(master, tmp_path)

    emitted: List[Dict[str, Any]] = []
    monkeypatch.setattr(
        controller,
        "_add_exact_persisted_nogood",
        lambda **kwargs: emitted.append(dict(kwargs)) or True,
    )

    status, result = controller._run_exact_binding_and_routing(
        iteration=1,
        solution=_solution_with_ghost(),
        diagnostic_flow_status="not_run",
    )

    assert status == bl.RUN_STATUS_UNKNOWN
    assert result is None
    assert emitted == []
    summary = controller.last_proof_summary
    assert summary["routing_status"] == "PRECHECK_FRONT_BLOCKED"
    assert summary["master_follow_up"] == "cut_stall"


# ---------------------------------------------------------------------------
# 1A #3 — the terminal fixed-witness chain uses the same occupancy reading
# ---------------------------------------------------------------------------


_WITNESS_GHOST_RECT = {
    "anchor_x": _GHOST_ANCHOR[0],
    "anchor_y": _GHOST_ANCHOR[1],
    "w": _GHOST_W,
    "h": _GHOST_H,
}


def test_witness_pose_resolved_occupancy_includes_ghost() -> None:
    owner_by_cell, occupied_cells = fw._extract_pose_resolved_occupancy(
        solution={
            "i": {"facility_type": "T", "pose_idx": 0},
            "ghost_pick": {"facility_type": "ghost_rect", "pose_idx": 0},
        },
        facility_pools={"T": [{"occupied_cells": [[0, 0]]}]},
        ghost_cells=fw._ghost_cells(_WITNESS_GHOST_RECT),
    )
    assert _GHOST_CELLS <= occupied_cells
    assert owner_by_cell[(0, 0)] == "i"
    for cell in _GHOST_CELLS:
        assert owner_by_cell[cell] == GHOST_RESERVED_OWNER_ID


def test_witness_pose_resolved_occupancy_rejects_body_inside_ghost() -> None:
    """A body overlapping the hole breaks predicate (1) — reject, do not merge."""

    with pytest.raises(ValueError):
        fw._extract_pose_resolved_occupancy(
            solution={"i": {"facility_type": "T", "pose_idx": 0}},
            facility_pools={
                "T": [{"occupied_cells": [[_GHOST_ANCHOR[0], _GHOST_ANCHOR[1]]]}]
            },
            ghost_cells=fw._ghost_cells(_WITNESS_GHOST_RECT),
        )


def test_witness_connector_backstop_stays_body_scoped() -> None:
    """Freezes a deliberate non-change (plan section 1G #20).

    The owner map now labels ghost cells, which would silently widen this
    backstop.  It keeps reading bodies only: a port cell inside the hole is
    already rejected by the routing precheck that runs on the same
    ghost-inclusive placement core, and the legacy reject string names bodies.
    A future reader finding ghost cells waved through here should read this as
    registered, not as a missed case.
    """

    ghost_only = {cell: GHOST_RESERVED_OWNER_ID for cell in _GHOST_CELLS}
    port_in_hole = [{"x": _GHOST_ANCHOR[0] + 1, "y": _GHOST_ANCHOR[1] + 1, "dir": "E"}]
    assert (
        fw._connector_body_exclusion_violation(
            port_specs=port_in_hole,
            occupied_owner_by_cell=ghost_only,
            grid_dimensions=(GRID_W, GRID_H),
        )
        is None
    )

    with_body = {**ghost_only, (_GHOST_ANCHOR[0] + 1, _GHOST_ANCHOR[1] + 1): "other"}
    assert (
        fw._connector_body_exclusion_violation(
            port_specs=port_in_hole,
            occupied_owner_by_cell=with_body,
            grid_dimensions=(GRID_W, GRID_H),
        )
        == "terminal_fixed_witness_connector_cell_occupied_by_other_body"
    )
