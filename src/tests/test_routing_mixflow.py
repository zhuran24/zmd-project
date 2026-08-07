"""Mixflow surgery differential tests (2026-08-06, de-mix ban 2026-08-07).

Scenario geometry uses the DIR_DELTA math convention (N = y+1) and identity
front semantics (the stored port coordinate IS the front/belt cell).  Corridor
scenarios occupy every cell outside an explicit free set so commodities cannot
route around the structure under test — an open grid would prove nothing.

External review 2026-08-06 returned BLOCK on finding B-01: physical components
are content-blind, so declaring "a leaves east, b leaves north" on one shared
splitter is not realizable, and the reviewer exhibited a 4-free-cell instance
where neither post-split branch has room for the straight-only in-game item
filter that would be needed to make the declared sorting real.  Owner ruling
2026-08-07 chose the conservative repair: forbid de-mix outright
(`_add_demix_ban_constraints`) until filters are modelled.

Groups:
- de-mix ban: the reviewer's 4-cell counterexample is a permanent negative,
  and its mutation control (ban neutralized) reproduces the reviewed
  FEASIBLE-plus-clean-validator result verbatim;
- re-judged unlocks: merge-then-split (U-02) and source-front co-riding are
  INFEASIBLE under the ban.  Their mutation controls double as the proof that
  merging, straight co-riding and per-commodity sub-patterns all remain
  expressible — the ban is what rejects these instances, and it rejects them
  only because their end-to-end route has to split by commodity;
- pollution sentinels: machine-input front cells stay pure on ground.  Two
  walls divide the work — the ban stops de-mixing, `_mixflow_ground_banned`
  stops same-direction mixed ingestion — so the split geometries need both
  walls neutralized to flip, while the same-direction multi-owner front flips
  on the guard alone (the ban emits no rows there at all);
- regressions: pre-surgery FEASIBLE structures stay FEASIBLE, and the
  physical layer stays exactly the union of the commodity sub-patterns.
"""

from typing import Dict, List, Sequence, Set, Tuple

import pytest

from src.models import routing_subproblem as routing_module
from src.models.routing_subproblem import (
    GRID_H,
    GRID_W,
    SINK_RECEIVER_CLASS_MACHINE,
    SINK_RECEIVER_CLASS_WAREHOUSE_SYSTEM,
    RoutingGrid,
    RoutingSubproblem,
    analyze_exact_routing_domain,
    classify_sink_receiver,
)

Cell = Tuple[int, int]

# Operation names that exist in the frozen inputs: `_CORE_OPERATION` and
# `_BOX_OPERATION` are `rules/preprocess_plan.json` utility operations,
# `_MACHINE_OPERATION` is a recipe from the canonical rules.  Tests name real
# operations so the scenarios exercise the production classification path
# rather than the fail-closed default.
_MACHINE_OPERATION = "crusher_blue_iron"
_CORE_OPERATION = "protocol_core"
_BOX_OPERATION = "box_sink"
# A name the frozen plan does not know.  Scenarios use it so the classifier's
# fail-closed default is pinned by a solved instance, not only by a unit
# assertion — a mutation that resolved unknown operations to the warehouse
# class has to turn a pollution sentinel red, not just a lookup test.
_UNKNOWN_OPERATION = "protocol_core_evil"


def _occupied_except(free_cells: Sequence[Cell]) -> Set[Cell]:
    free = set(free_cells)
    return {(x, y) for x in range(GRID_W) for y in range(GRID_H) if (x, y) not in free}


def _build(free_cells: Sequence[Cell], port_specs: List[Dict], commodities: List[str]) -> RoutingSubproblem:
    grid = RoutingGrid(_occupied_except(free_cells), port_specs)
    analysis = analyze_exact_routing_domain(grid)
    assert analysis["status"] == "feasible", analysis
    routing = RoutingSubproblem(grid, commodities, domain_analysis=analysis)
    routing.build()
    return routing


def _solve(routing: RoutingSubproblem) -> str:
    return routing.solve(time_limit=30.0)


def _routes_by_cell_layer(routing: RoutingSubproblem) -> Dict[Tuple[int, int, int], Dict]:
    return {(r["x"], r["y"], r["layer"]): r for r in routing.extract_routes()}


def _use_flows(route: Dict) -> Dict[str, Tuple[Tuple[str, ...], Tuple[str, ...]]]:
    return {
        u["commodity"]: (tuple(u["flow_in"]), tuple(u["flow_out"]))
        for u in route["uses"]
    }


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------

def _sc_u02_merge_then_split():
    """Two sources merge onto a width-1 shared corridor, then split apart."""
    free = [
        (3, 2), (4, 2),          # a: source spur
        (3, 4), (4, 4),          # b: source spur
        (4, 3), (5, 3), (6, 3),  # shared corridor: merge at (4,3), split at (6,3)
        (6, 2), (7, 2),          # a: exit spur to its sink
        (6, 4), (7, 4),          # b: exit spur to its sink
    ]
    ports = [
        {"x": 3, "y": 2, "dir": "E", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 3, "y": 4, "dir": "E", "commodity": "b", "type": "out", "instance_id": "srcB"},
        {"x": 7, "y": 2, "dir": "W", "commodity": "a", "type": "in", "instance_id": "sinkA"},
        {"x": 7, "y": 4, "dir": "W", "commodity": "b", "type": "in", "instance_id": "sinkB"},
    ]
    return free, ports, ["a", "b"]


def _sc_source_front_coride():
    """b joins a's output lane AT a's source front cell (owner-ruled safe)."""
    free = [
        (3, 3), (3, 4),          # b: source spur from the south
        (3, 5),                  # a's source front — b merges here
        (3, 6), (3, 7),          # shared lane north; split at (3,7)
        (2, 7),                  # a: sink front (west exit)
        (3, 8),                  # b: sink front (north exit)
    ]
    ports = [
        {"x": 3, "y": 5, "dir": "E", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 3, "y": 3, "dir": "N", "commodity": "b", "type": "out", "instance_id": "srcB"},
        {"x": 2, "y": 7, "dir": "E", "commodity": "a", "type": "in", "instance_id": "sinkA"},
        {"x": 3, "y": 8, "dir": "S", "commodity": "b", "type": "in", "instance_id": "sinkB"},
    ]
    return free, ports, ["a", "b"]


def _sc_door_corner_transit():
    """b would have to TURN on a's sink front cell; L1 bridges are straight."""
    free = [
        (5, 3), (5, 4), (5, 5),  # a: lane south->north; sink front F=(5,5)
        (4, 5),                  # b: source front, west of F
        (5, 6),                  # b: sink front, north of F
    ]
    ports = [
        {"x": 5, "y": 3, "dir": "N", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 5, "y": 5, "dir": "W", "commodity": "a", "type": "in", "instance_id": "sinkA"},
        {"x": 4, "y": 5, "dir": "E", "commodity": "b", "type": "out", "instance_id": "srcB"},
        {"x": 5, "y": 6, "dir": "S", "commodity": "b", "type": "in", "instance_id": "sinkB"},
    ]
    return free, ports, ["a", "b"]


def _sc_door_split_transit():
    """b co-rides a's lane and wants to peel off north AT a's sink front.

    The side union at the door cell is splitter W→{E,N} — a legal dictionary
    pattern — so the explicit ground-purity exclusion is the ONLY wall between
    this structure and a content-blind splitter feeding b's items into a's
    machine.  This is the mutation-detecting pollution sentinel.
    """
    free = [
        (2, 5), (3, 5),          # a: source front + shared lane cell
        (3, 4),                  # b: source front, merging into the lane at (3,5)
        (4, 5),                  # F: a's sink front (b would split N here)
        (4, 6),                  # b: sink front, north of F
    ]
    ports = [
        {"x": 2, "y": 5, "dir": "E", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 4, "y": 5, "dir": "W", "commodity": "a", "type": "in", "instance_id": "sinkA"},
        {"x": 3, "y": 4, "dir": "N", "commodity": "b", "type": "out", "instance_id": "srcB"},
        {"x": 4, "y": 6, "dir": "S", "commodity": "b", "type": "in", "instance_id": "sinkB"},
    ]
    return free, ports, ["a", "b"]


def _sc_multi_owner_sink_front():
    """Two different-commodity sink ports face the same front cell F=(5,5).

    Without the multi-owner full ban, a's N→E and b's N→W terminals would
    union into splitter N→{E,W}: a content-blind component alternately feeding
    both machines from a mixed lane.  Must stay INFEASIBLE.
    """
    free = [
        (5, 7),                  # a: source front (north end)
        (4, 6),                  # b: source front (west spur into (5,6))
        (5, 6),                  # shared feed cell (b merges here)
        (5, 5),                  # F: sink front of BOTH a (body east) and b (body west)
    ]
    ports = [
        {"x": 5, "y": 7, "dir": "S", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 4, "y": 6, "dir": "E", "commodity": "b", "type": "out", "instance_id": "srcB"},
        {"x": 5, "y": 5, "dir": "W", "commodity": "a", "type": "in", "instance_id": "sinkA"},
        {"x": 5, "y": 5, "dir": "E", "commodity": "b", "type": "in", "instance_id": "sinkB"},
    ]
    return free, ports, ["a", "b"]


def _sc_same_direction_multi_owner_front(iron_sink_op=None, copper_sink_op=None):
    """Two commodities' sink ports on ONE front cell with the SAME terminal
    direction — `EXTERNAL_REVIEW_BRIEF.md` §4.1's latent mixed-ingestion hole,
    and the reviewer's own F-02 reproduction instance.

    `_duplicate_terminal_front_keys` keys on commodity too, so two ports of
    *different* commodities sharing a front cell and direction are not caught
    as duplicate ports; they reach the model.  No splitter appears anywhere in
    this geometry, so the de-mix ban emits zero rows — the ground ban is the
    only wall stopping one mixed lane from feeding both receivers.

    U-01 makes that wall depend on WHAT receives: the optional operation
    arguments stamp the receiving instances' operation types, exactly as
    `BindingSubproblem.extract_port_specs` does in production.  Left unset the
    specs carry no operation at all, which is the fail-closed shape (machine
    rule) and reproduces the pre-U-01 behaviour verbatim.
    """
    free = [(1, 0), (2, 0), (3, 0)]
    ports = [
        {"x": 1, "y": 0, "dir": "E", "commodity": "iron", "type": "out", "instance_id": "ironSrc"},
        {"x": 1, "y": 0, "dir": "E", "commodity": "copper", "type": "out", "instance_id": "copperSrc"},
        {"x": 3, "y": 0, "dir": "W", "commodity": "iron", "type": "in", "instance_id": "ironSink"},
        {"x": 3, "y": 0, "dir": "W", "commodity": "copper", "type": "in", "instance_id": "copperSink"},
    ]
    if iron_sink_op is not None:
        ports[2]["operation_type"] = iron_sink_op
    if copper_sink_op is not None:
        ports[3]["operation_type"] = copper_sink_op
    return free, ports, ["iron", "copper"]


def _sc_adjacent_warehouse_ports_coride(final_sink_op=_CORE_OPERATION):
    """Two commodities co-ride one lane and get off one at a time.

    This is the shape U-01 was commissioned to unlock: finished goods sharing a
    belt into the wired warehouse ports.  Bodies sit east of the lane; b's port
    fronts on (4,5) and a rides past it to its own port on (4,6).  Both
    upstream producers inject from the west.

    Getting off at (4,5) while a rides on IS a de-mix — the component there must
    be splitter S->{N,E} — so under the plain ban this is INFEASIBLE regardless
    of the ground guard (measured, `DESIGN.md` §10.4).  What makes it legal is
    the drain closure: every physical path out of (4,5) ends in a warehouse
    port, so a's items being pushed east into the core are stored, not eaten by
    a machine.

    `final_sink_op` switches what a's own port at (4,6) is.  Pointing it at a
    machine turns this into the pollution geometry: the closure at (4,6) is
    forced false and the falsity propagates back to (4,5), so the same de-mix
    must be rejected.  That pair is the whole soundness claim in two instances.
    """
    free = [(4, 3), (4, 4), (4, 5), (4, 6)]
    ports = [
        {"x": 4, "y": 3, "dir": "E", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 4, "y": 4, "dir": "E", "commodity": "b", "type": "out", "instance_id": "srcB"},
        {"x": 4, "y": 5, "dir": "W", "commodity": "b", "type": "in", "instance_id": "core1",
         "operation_type": _CORE_OPERATION},
        {"x": 4, "y": 6, "dir": "W", "commodity": "a", "type": "in", "instance_id": "sinkA",
         "operation_type": final_sink_op},
    ]
    return free, ports, ["a", "b"]


def _sc_perpendicular_bridge_cross():
    free = [
        (3, 5), (4, 5), (5, 5), (6, 5), (7, 5),  # a: horizontal lane W->E
        (5, 3), (5, 4), (5, 6), (5, 7),          # b: vertical lane S->N
    ]
    ports = [
        {"x": 3, "y": 5, "dir": "E", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 7, "y": 5, "dir": "W", "commodity": "a", "type": "in", "instance_id": "sinkA"},
        {"x": 5, "y": 3, "dir": "N", "commodity": "b", "type": "out", "instance_id": "srcB"},
        {"x": 5, "y": 7, "dir": "S", "commodity": "b", "type": "in", "instance_id": "sinkB"},
    ]
    return free, ports, ["a", "b"]


def _sc_demix_no_filter_slot():
    """External review B-01 minimal counterexample (2026-08-06), verbatim.

    Only 4 free cells.  M=(5,5) is a content-blind merger, D=(6,5) a
    content-blind splitter, and BOTH post-split branches are single corner
    terminals — so the straight-only item filter that the pre-ban material
    leaned on has nowhere to go on either branch.  Pre-surgery: INFEASIBLE.
    Post-surgery without the ban: FEASIBLE with `a` declared east and `b`
    declared north off one blind splitter, and the connectivity validator
    reporting failure_count=0.  Must be INFEASIBLE under the ban.
    """
    free = [(5, 5), (6, 5), (7, 5), (6, 6)]
    ports = [
        {"x": 5, "y": 5, "dir": "E", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 5, "y": 5, "dir": "N", "commodity": "b", "type": "out", "instance_id": "srcB"},
        # a's branch terminal: W -> N corner
        {"x": 7, "y": 5, "dir": "S", "commodity": "a", "type": "in", "instance_id": "sinkA"},
        # b's branch terminal: S -> W corner
        {"x": 6, "y": 6, "dir": "E", "commodity": "b", "type": "in", "instance_id": "sinkB"},
    ]
    return free, ports, ["a", "b"]


def _sc_straight_corridor():
    """Width-1 straight lane: no cell has three supported sides, so no splitter
    state exists anywhere and the de-mix ban has nothing to constrain."""
    free = [(2, 5), (3, 5), (4, 5), (5, 5)]
    ports = [
        {"x": 2, "y": 5, "dir": "E", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 5, "y": 5, "dir": "W", "commodity": "a", "type": "in", "instance_id": "sinkA"},
    ]
    return free, ports, ["a"]


def _sc_single_commodity_split():
    free = [
        (3, 5), (4, 5),
        (5, 5),
        (5, 6), (5, 7),
        (5, 4), (5, 3),
    ]
    ports = [
        {"x": 3, "y": 5, "dir": "E", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 5, "y": 7, "dir": "S", "commodity": "a", "type": "in", "instance_id": "sinkA1"},
        {"x": 5, "y": 3, "dir": "N", "commodity": "a", "type": "in", "instance_id": "sinkA2"},
    ]
    return free, ports, ["a"]


def _neutralize_purity_guard(monkeypatch):
    monkeypatch.setattr(
        RoutingSubproblem,
        "_mixflow_ground_banned",
        lambda self, x, y, commodity: False,
    )


def _neutralize_demix_ban(monkeypatch):
    monkeypatch.setattr(
        RoutingSubproblem,
        "_add_demix_ban_constraints",
        lambda self: None,
    )


def _mixed_cells(routing: RoutingSubproblem) -> List[Tuple[int, int, int, str]]:
    return [
        (r["x"], r["y"], r["layer"], r["component_type"])
        for r in routing.extract_routes()
        if len({u["commodity"] for u in r["uses"]}) > 1
    ]


# ---------------------------------------------------------------------------
# De-mix ban (external review B-01 repair, owner ruling 2026-08-07)
# ---------------------------------------------------------------------------

def test_demix_no_filter_slot_counterexample_is_infeasible():
    """The reviewed 4-cell instance must be rejected outright."""
    routing = _build(*_sc_demix_no_filter_slot())
    assert _solve(routing) == "INFEASIBLE"


def test_demix_ban_is_load_bearing(monkeypatch):
    """Mutation self-verification, and a verbatim reproduction of the review.

    With the ban neutralized the counterexample flips FEASIBLE, the extracted
    hardware is exactly the reviewer's blind splitter at D=(6,5) with `a`
    declared east and `b` declared north, and the global connectivity
    re-validator still reports a clean pass — i.e. nothing else in the model
    catches this, so the ban is the only wall.
    """
    _neutralize_demix_ban(monkeypatch)
    routing = _build(*_sc_demix_no_filter_slot())
    assert _solve(routing) == "FEASIBLE"

    split = _routes_by_cell_layer(routing)[(6, 5, 0)]
    assert split["component_type"] == "splitter"
    split_flows = _use_flows(split)
    assert split_flows["a"] == (("W",), ("E",))
    assert split_flows["b"] == (("W",), ("N",))

    connected, summary = routing._validate_selected_route_connectivity(routing._solver)
    assert connected
    assert summary["failure_count"] == 0


def test_demix_ban_leaves_split_free_geometry_untouched():
    """Row scope: a width-1 lane supports no splitter state, so the ban emits
    no rows at all — straight co-riding and plain belts are not what it cuts.
    """
    routing = _build(*_sc_straight_corridor())
    assert _solve(routing) == "FEASIBLE"
    assert routing.build_stats["demix_ban"] == {
        "rows": 0,
        "multi_out_cell_layers": 0,
        # No warehouse port in this scenario, so no drain variables exist and
        # every row the ban would emit is the plain two-literal form.
        "drain_excusable_rows": 0,
    }


def test_elevated_layer_carries_no_multi_output_state():
    """Why the ban emits no elevated-layer rows: L1 holds only straight
    1-in/1-out bridges, so no L1 cell can carry a multi-output state and L1
    transit stays untouched."""
    routing = _build(*_sc_perpendicular_bridge_cross())
    assert _solve(routing) == "FEASIBLE"
    elevated_multi_out = [
        key for key in routing.phys_vars
        if key[2] == 1 and len(key[4]) >= 2
    ]
    assert elevated_multi_out == []


# ---------------------------------------------------------------------------
# Re-judged unlocks: expressible, but no longer completable end to end
# ---------------------------------------------------------------------------

def test_u02_merge_then_split_now_infeasible():
    """U-02's end-to-end route has to split by commodity at (6,3); banned."""
    routing = _build(*_sc_u02_merge_then_split())
    assert _solve(routing) == "INFEASIBLE"


def test_u02_mutation_control_shows_merge_and_coride_expressible(monkeypatch):
    """The ban — not the sub-pattern machinery — is what rejects U-02.

    With the ban off the corridor solves with all three mixflow shapes live:
    a two-commodity merger, a two-commodity straight belt (co-riding) and the
    de-mix splitter.  Only the third is unsound, and it is the reason the
    banned model rejects the instance.
    """
    _neutralize_demix_ban(monkeypatch)
    routing = _build(*_sc_u02_merge_then_split())
    assert _solve(routing) == "FEASIBLE"

    merge = _routes_by_cell_layer(routing)[(4, 3, 0)]
    assert merge["component_type"] == "merger"
    merge_flows = _use_flows(merge)
    assert merge_flows["a"] == (("S",), ("E",))
    assert merge_flows["b"] == (("N",), ("E",))

    shapes = {component_type for _x, _y, _layer, component_type in _mixed_cells(routing)}
    assert {"merger", "belt", "splitter"} <= shapes


def test_source_front_coride_now_infeasible():
    """b joins a's output lane legally, but the pair still has to separate."""
    routing = _build(*_sc_source_front_coride())
    assert _solve(routing) == "INFEASIBLE"


def test_source_front_coride_mutation_control(monkeypatch):
    _neutralize_demix_ban(monkeypatch)
    routing = _build(*_sc_source_front_coride())
    assert _solve(routing) == "FEASIBLE"
    door = _routes_by_cell_layer(routing)[(3, 5, 0)]
    assert door["component_type"] == "merger"
    door_flows = _use_flows(door)
    assert door_flows["a"] == (("W",), ("N",))   # a receives from its port (west body)
    assert door_flows["b"] == (("S",), ("N",))   # b transits/merges at the door
    assert sorted(door["commodities"]) == ["a", "b"]


# ---------------------------------------------------------------------------
# Pollution sentinels (machine-input front purity, owner ironclad)
# ---------------------------------------------------------------------------

def test_door_corner_transit_stays_infeasible():
    routing = _build(*_sc_door_corner_transit())
    assert _solve(routing) == "INFEASIBLE"


def test_door_split_transit_stays_infeasible():
    routing = _build(*_sc_door_split_transit())
    assert _solve(routing) == "INFEASIBLE"


def test_no_foreign_ground_states_at_sink_front():
    routing = _build(*_sc_door_split_transit())
    foreign_ground_keys = [
        key
        for key in routing.use_vars
        if (key[0], key[1]) == (4, 5) and key[2] == 0 and key[5] == "b"
    ]
    assert foreign_ground_keys == []


def test_demix_ban_subsumes_purity_guard_on_split_geometries(monkeypatch):
    """Ledger entry: which wall now carries which pollution geometry.

    Peeling foreign items off at a machine-input front is itself a de-mix (the
    owner exits toward its port, the freeloader exits elsewhere), and a foreign
    commodity cannot claim the port-ward side because the body cell behind the
    port is occupied.  So on both *split* pollution geometries the ban alone
    already rejects the instance and `_mixflow_ground_banned` is no longer the
    sole defence — a sentinel that neutralized the guard alone would be vacuous
    here, which is why the two below neutralize both walls.

    This does NOT generalize: see
    `test_purity_guard_is_load_bearing_on_same_direction_multi_owner`.
    """
    _neutralize_purity_guard(monkeypatch)
    assert _solve(_build(*_sc_door_split_transit())) == "INFEASIBLE"
    assert _solve(_build(*_sc_multi_owner_sink_front())) == "INFEASIBLE"


@pytest.mark.parametrize(
    "sink_op",
    [None, "", _UNKNOWN_OPERATION, _MACHINE_OPERATION, _BOX_OPERATION],
    ids=["absent", "empty", "unknown_operation", "machine", "protocol_box"],
)
def test_same_direction_multi_owner_front_stays_infeasible(sink_op):
    """Machine-rule receivers keep the wall after the U-01 fork.

    Every machine-rule shape must stay closed: specs carrying no operation at
    all, an empty one, an operation the frozen plan does not know (all three
    are the fail-closed default), real manufacturing operations, and protocol
    boxes (bounded mixers, deliberately not relaxed in phase 1).
    """
    routing = _build(*_sc_same_direction_multi_owner_front(sink_op, sink_op))
    assert _solve(routing) == "INFEASIBLE"


@pytest.mark.parametrize(
    "sink_op",
    [None, "", _UNKNOWN_OPERATION, _MACHINE_OPERATION, _BOX_OPERATION],
    ids=["absent", "empty", "unknown_operation", "machine", "protocol_box"],
)
def test_purity_guard_is_load_bearing_on_same_direction_multi_owner(monkeypatch, sink_op):
    """The wall the de-mix ban does NOT subsume, per receiver class.

    Same-direction multi-owner fronts contain no splitter at all, so the ban
    emits zero rows and is vacuous on them.  Neutralizing the guard alone must
    therefore flip this scenario FEASIBLE — with all three cells carrying both
    commodities on one straight belt, i.e. exactly the mixed ingestion that
    `EXTERNAL_REVIEW_BRIEF.md` §4.1 recorded as the pre-surgery model's latent
    acceptance.  The two walls divide the work: the ban stops de-mixing, the
    guard stops same-direction mixed ingestion.  Neither may be deleted.

    Running it per receiver class is what keeps the U-01 fork honest: each
    machine-rule branch — the three fail-closed shapes, a real machine, a box —
    has to be carrying its geometry on its own, not inheriting closure from a
    neighbouring branch.
    """
    _neutralize_purity_guard(monkeypatch)
    routing = _build(*_sc_same_direction_multi_owner_front(sink_op, sink_op))
    assert routing.build_stats["demix_ban"]["rows"] == 0
    assert _solve(routing) == "FEASIBLE"

    for route in routing.extract_routes():
        assert route["component_type"] == "belt"
        assert sorted(_use_flows(route)) == ["copper", "iron"]


def test_door_split_sentinel_is_load_bearing(monkeypatch):
    """Mutation self-verification: with BOTH walls neutralized the door split
    scenario MUST flip FEASIBLE, so the sentinel cannot rot into a vacuous
    assertion — some wall is always carrying it."""
    _neutralize_purity_guard(monkeypatch)
    _neutralize_demix_ban(monkeypatch)
    routing = _build(*_sc_door_split_transit())
    assert _solve(routing) == "FEASIBLE"


def test_multi_owner_sink_front_stays_infeasible():
    routing = _build(*_sc_multi_owner_sink_front())
    assert _solve(routing) == "INFEASIBLE"
    assert routing.build_stats["mixflow"]["multi_owner_sink_fronts"] == [[5, 5]]


def test_multi_owner_sentinel_is_load_bearing(monkeypatch):
    _neutralize_purity_guard(monkeypatch)
    _neutralize_demix_ban(monkeypatch)
    routing = _build(*_sc_multi_owner_sink_front())
    assert _solve(routing) == "FEASIBLE"


# ---------------------------------------------------------------------------
# Regressions (pre-surgery FEASIBLE must stay FEASIBLE)
# ---------------------------------------------------------------------------

def test_perpendicular_bridge_cross_stays_feasible():
    routing = _build(*_sc_perpendicular_bridge_cross())
    assert _solve(routing) == "FEASIBLE"


def test_single_commodity_split_stays_feasible():
    routing = _build(*_sc_single_commodity_split())
    assert _solve(routing) == "FEASIBLE"
    routes = routing.extract_routes()
    assert any(r["component_type"] == "splitter" for r in routes)


def test_phys_pattern_equals_union_of_use_sides():
    """Exact-side rows: every extracted component carries exactly the union of
    its commodities' sub-pattern sides (minimal hardware invariant)."""
    for builder in (
        _sc_straight_corridor,
        _sc_perpendicular_bridge_cross,
        _sc_single_commodity_split,
    ):
        routing = _build(*builder())
        assert _solve(routing) == "FEASIBLE"
        for route in routing.extract_routes():
            flows = _use_flows(route)
            assert flows, route
            in_union: Set[str] = set()
            out_union: Set[str] = set()
            for flow_in, flow_out in flows.values():
                in_union |= set(flow_in)
                out_union |= set(flow_out)
            assert in_union == set(route["flow_in"]), route
            assert out_union == set(route["flow_out"]), route


def test_every_present_commodity_claims_all_outgoing_sides():
    """The de-mix ban's invariant, read off extracted solutions.

    Exact-side rows pin the component pattern to the union of the commodity
    sub-patterns; the ban pins every present commodity's outgoing set to that
    same union.  So a commodity's declared outgoing edges are exactly the
    component's physical outgoing edges wherever it is present — content-blind
    round-robin propagation cannot leave the declared face.
    """
    for builder in (
        _sc_straight_corridor,
        _sc_perpendicular_bridge_cross,
        _sc_single_commodity_split,
    ):
        routing = _build(*builder())
        assert _solve(routing) == "FEASIBLE"
        for route in routing.extract_routes():
            phys_out = set(route["flow_out"])
            for commodity, (_flow_in, flow_out) in _use_flows(route).items():
                assert set(flow_out) == phys_out, (commodity, route)


def test_connectivity_validator_accepts_post_ban_solutions():
    for builder in (_sc_perpendicular_bridge_cross, _sc_single_commodity_split):
        routing = _build(*builder())
        assert _solve(routing) == "FEASIBLE"
        connected, summary = routing._validate_selected_route_connectivity(routing._solver)
        assert connected, summary
        assert summary["failure_count"] == 0


# ---------------------------------------------------------------------------
# U-01 port-class admission fork (owner 口岸三分法, 2026-08-06)
# ---------------------------------------------------------------------------

def test_sink_receiver_classification_comes_from_the_frozen_plan():
    """Classification provenance, and the fail-closed shape of every gap.

    `protocol_core` and `box_sink` are `rules/preprocess_plan.json` utility
    operations; the assertion below reads their facility types back out of the
    profile table rather than restating them, so a plan edit that re-labelled a
    facility would surface here instead of silently re-classifying ports.
    """
    from src.preprocess.operation_profiles import OPERATION_PORT_PROFILES

    assert OPERATION_PORT_PROFILES[_CORE_OPERATION].facility_type == "protocol_core"
    assert OPERATION_PORT_PROFILES[_BOX_OPERATION].facility_type == "protocol_storage_box"
    assert (
        OPERATION_PORT_PROFILES[_CORE_OPERATION].facility_type
        in routing_module.WAREHOUSE_SYSTEM_SINK_FACILITY_TYPES
    )
    assert (
        OPERATION_PORT_PROFILES[_BOX_OPERATION].facility_type
        not in routing_module.WAREHOUSE_SYSTEM_SINK_FACILITY_TYPES
    )

    assert classify_sink_receiver(_CORE_OPERATION) == SINK_RECEIVER_CLASS_WAREHOUSE_SYSTEM
    for widening_attempt in (
        _MACHINE_OPERATION,      # a real machine
        _BOX_OPERATION,          # bounded mixer, phase-1 conservative
        "boundary_io",           # 0 inputs, never a sink front anyway
        _UNKNOWN_OPERATION,      # a name the frozen plan does not know
        "",
        None,
    ):
        assert classify_sink_receiver(widening_attempt) == SINK_RECEIVER_CLASS_MACHINE


def test_warehouse_system_front_admits_foreign_ground_states():
    """The fork's actual unlock: no exclusion at an all-warehouse sink front.

    Same geometry as the machine-rule sentinel above, with both receivers
    declared as core inputs.  A foreign item a content-blind belt pushes into
    a wired warehouse port is written to that item's own warehouse slot and
    stored (#3/#12) — there is nothing to keep out, so the cell generates
    ground states for both commodities and one mixed belt feeds both ports.
    """
    routing = _build(*_sc_same_direction_multi_owner_front(_CORE_OPERATION, _CORE_OPERATION))
    stats = routing.build_stats["mixflow"]
    assert stats["warehouse_system_sink_fronts"] == [[3, 0]]
    assert stats["machine_rule_sink_fronts"] == 0
    assert stats["purity_excluded_cell_layers"] == 0

    assert _solve(routing) == "FEASIBLE"
    for route in routing.extract_routes():
        assert route["component_type"] == "belt"
        assert sorted(_use_flows(route)) == ["copper", "iron"]


@pytest.mark.parametrize(
    "iron_op,copper_op",
    [
        (_CORE_OPERATION, _MACHINE_OPERATION),
        (_CORE_OPERATION, _BOX_OPERATION),
        (_CORE_OPERATION, None),
    ],
    ids=["core_plus_machine", "core_plus_box", "core_plus_unclassified"],
)
def test_mixed_class_front_keeps_the_machine_rule(iron_op, copper_op):
    """One poisonable receiver on the cell is enough to keep the wall.

    The exclusion is cell-level — a component feeding a shared front cell
    cannot feed one port selectively — so a cell mixing receiver classes gets
    the strictest applicable rule.
    """
    routing = _build(*_sc_same_direction_multi_owner_front(iron_op, copper_op))
    assert routing.build_stats["mixflow"]["warehouse_system_sink_fronts"] == []
    assert _solve(routing) == "INFEASIBLE"


def test_warehouse_relaxation_is_load_bearing_on_the_policy_set(monkeypatch):
    """Mutation self-verification of the fork itself, from the policy side.

    The box front stays closed because `protocol_storage_box` is absent from
    `WAREHOUSE_SYSTEM_SINK_FACILITY_TYPES`.  Adding it must flip the very same
    instance FEASIBLE — proof that the phase-1 box decision is carried by that
    set and not by some unrelated constraint that would keep boxes closed even
    if the set were widened by accident.
    """
    scenario = _sc_same_direction_multi_owner_front(_BOX_OPERATION, _BOX_OPERATION)
    assert _solve(_build(*scenario)) == "INFEASIBLE"

    monkeypatch.setattr(
        routing_module,
        "WAREHOUSE_SYSTEM_SINK_FACILITY_TYPES",
        frozenset({"protocol_core", "protocol_storage_box"}),
    )
    monkeypatch.setattr(routing_module, "_SINK_RECEIVER_CLASS_BY_OPERATION", {})
    assert classify_sink_receiver(_BOX_OPERATION) == SINK_RECEIVER_CLASS_WAREHOUSE_SYSTEM
    assert _solve(_build(*_sc_same_direction_multi_owner_front(_BOX_OPERATION, _BOX_OPERATION))) == "FEASIBLE"


def test_warehouse_drain_unlocks_coride_dropoff():
    """The delivery surface U-01 was commissioned for, now reachable.

    Two commodities share one lane; b gets off into a wired warehouse port at
    (4,5) while a rides on to its own warehouse port at (4,6).  The component at
    (4,5) is a splitter and the declaration is a de-mix, so the plain ban
    rejects it — what makes it legal is that every physical path out of (4,5)
    ends in a warehouse port, so a's items that the content-blind splitter
    pushes east are *stored*, not fed to a machine.
    """
    routing = _build(*_sc_adjacent_warehouse_ports_coride())
    stats = routing.build_stats["mixflow"]
    assert stats["warehouse_system_sink_fronts"] == [[4, 5], [4, 6]]
    assert stats["purity_excluded_cell_layers"] == 0
    assert routing.build_stats["warehouse_drain"]["cells"] > 0
    assert routing.build_stats["demix_ban"]["drain_excusable_rows"] > 0

    assert _solve(routing) == "FEASIBLE"
    routes = _routes_by_cell_layer(routing)

    merge = routes[(4, 4, 0)]
    assert merge["component_type"] == "merger"
    assert _use_flows(merge) == {"a": (("S",), ("N",)), "b": (("W",), ("N",))}

    split = routes[(4, 5, 0)]
    assert split["component_type"] == "splitter"
    assert _use_flows(split) == {"a": (("S",), ("N",)), "b": (("S",), ("E",))}

    connected, summary = routing._validate_selected_route_connectivity(routing._solver)
    assert connected, summary
    assert summary["failure_count"] == 0


def test_drain_closure_rejects_dropoff_whose_lane_ends_at_a_machine():
    """The pollution twin of the test above — one port changed, verdict flips.

    a's own port at (4,6) is a machine now.  Its port-ward side points at the
    machine body, which is off-domain and is not a warehouse exit, so the
    closure is forced false at (4,6); the falsity propagates back along the lane
    to (4,5), where the de-mix therefore stays banned.  Physically this is
    exactly external review finding B-01: the content-blind splitter would push
    b's items north into a's machine.
    """
    routing = _build(*_sc_adjacent_warehouse_ports_coride(_MACHINE_OPERATION))
    assert _solve(routing) == "INFEASIBLE"


def test_warehouse_drain_propagation_is_load_bearing(monkeypatch):
    """Mutation self-verification of the propagation rows.

    Neutralizing propagation (the closure variables stay, unconstrained) must
    flip the pollution geometry above to FEASIBLE and admit exactly the split
    the reviewer objected to — proof that the rows, not something else, are what
    rejects it.  Neutralizing them must NOT be needed for the legal geometry.
    """
    original = RoutingSubproblem._add_warehouse_drain_constraints

    def _vars_only(self):
        original(self)
        # Drop every propagation row by rebuilding the variables in a fresh
        # model-free state: re-issue unconstrained booleans under the same keys.
        for cell in list(self._wh_drain_vars):
            self._wh_drain_vars[cell] = self.model.NewBoolVar(f"whdrain_free_{cell[0]}_{cell[1]}")

    monkeypatch.setattr(RoutingSubproblem, "_add_warehouse_drain_constraints", _vars_only)
    routing = _build(*_sc_adjacent_warehouse_ports_coride(_MACHINE_OPERATION))
    assert _solve(routing) == "FEASIBLE"

    split = _routes_by_cell_layer(routing)[(4, 5, 0)]
    assert split["component_type"] == "splitter"
    assert _use_flows(split) == {"a": (("S",), ("N",)), "b": (("S",), ("E",))}


def test_warehouse_drain_is_load_bearing_for_the_unlock(monkeypatch):
    """The other direction: without the closure the unlock does not happen.

    With `_add_warehouse_drain_constraints` a no-op there are no closure
    variables, every ban row falls back to the plain two-literal form, and the
    legal co-ride/drop-off geometry goes back to INFEASIBLE — i.e. the unlock is
    carried by this mechanism and not by the U-01 guard fork alone.
    """
    monkeypatch.setattr(
        RoutingSubproblem,
        "_add_warehouse_drain_constraints",
        lambda self: self.build_stats.__setitem__("warehouse_drain", {"cells": 0}),
    )
    routing = _build(*_sc_adjacent_warehouse_ports_coride())
    assert routing.build_stats["demix_ban"]["drain_excusable_rows"] == 0
    assert _solve(routing) == "INFEASIBLE"


def test_drain_exit_requires_the_body_cell_to_be_off_domain():
    """A port whose body cell is routable must not count as an absorbing exit.

    Malformed inputs (a probe fixture with exactly this defect turned up in the
    de-mix batch's evidence) make the same side both "the port" and "an edge
    into a free cell".  Treating it as absorbing would let goods leave the
    closure unchecked, so `_is_warehouse_drain_exit` demands an off-domain
    neighbour and this scenario keeps propagating instead.
    """
    free = [(4, 5), (5, 5), (6, 5)]
    ports = [
        # a is produced east of the lane and consumed by a core port at (4,5)
        # whose body would be (5,5) — a cell that carries routing variables,
        # so "the port" and "an edge into (5,5)" are the same physical side.
        {"x": 6, "y": 5, "dir": "W", "commodity": "a", "type": "out", "instance_id": "srcA"},
        {"x": 4, "y": 5, "dir": "W", "commodity": "a", "type": "in", "instance_id": "core1",
         "operation_type": _CORE_OPERATION},
    ]
    routing = _build(free, ports, ["a"])
    assert (5, 5) in routing._wh_drain_vars, "fixture must make the body cell routable"
    assert routing._is_warehouse_drain_exit(4, 5, "E") is False

    # Sanity: the same side IS an absorbing exit once the body is off-domain.
    faithful = _build(
        [(4, 5), (3, 5)],
        [
            {"x": 3, "y": 5, "dir": "W", "commodity": "a", "type": "out", "instance_id": "srcA"},
            {"x": 4, "y": 5, "dir": "W", "commodity": "a", "type": "in", "instance_id": "core1",
             "operation_type": _CORE_OPERATION},
        ],
        ["a"],
    )
    assert faithful._is_warehouse_drain_exit(4, 5, "E") is True
