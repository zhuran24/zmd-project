"""Exact regression contract for the first routing-aware witness campaign."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
import importlib
import json
from pathlib import Path
from typing import Any

import pytest


geometry = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.geometry"
)
router = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.network_router"
)


CAMPAIGN_LEVELS = (5, 9, 13, 17, 21, 25, 31, 37, 43, 49, 54, 59, 64)
CORE_ANCHOR = (3, 44)
CORE_BODY = frozenset((x, y) for x in range(3, 12) for y in range(44, 53))
OPPOSITE = {"N": "S", "E": "W", "S": "N", "W": "E"}
DELTA = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}


@pytest.fixture(scope="module")
def strict_instance() -> dict[str, Any]:
    project_root = Path(__file__).resolve().parents[2]
    instance_path = (
        project_root
        / "docs/research/cleanroom_rederivation_20260718/strict/external/problem_instance.json"
    )
    return json.loads(instance_path.read_text(encoding="utf-8"))


def _campaign_edges(*, extra_levels: tuple[int, ...] = ()) -> frozenset[Any]:
    return router.shelf_network_edges(
        router.ShelfNetworkSpec(
            chord_levels=tuple(sorted({*CAMPAIGN_LEVELS, *extra_levels})),
            core_anchor=CORE_ANCHOR,
        )
    )


def _boundary_contract() -> tuple[list[Any], set[tuple[int, int]]]:
    placements = geometry.place_boundary_instances(
        (f"boundary_port_{number:03d}" for number in range(1, 47)),
        geometry.BoundaryPattern(69, 0),
    )
    terminals = []
    occupied: set[tuple[int, int]] = set()
    for placement in placements:
        occupied.update(placement.body_cells)
        outward = "E" if placement.side == "left" else "N"
        terminals.append(
            router.Terminal(
                placement.instance_id,
                "output",
                "output",
                "source_ore",
                next(iter(placement.front_cells)),
                outward,
            )
        )
    return terminals, occupied


def _core_terminals(
    strict_instance: dict[str, Any],
    *,
    north_inputs: tuple[str, ...] = (),
) -> tuple[Any, ...]:
    mode = next(
        mode
        for mode in strict_instance["facility_templates"]["protocol_core"]["modes"]
        if mode["id"] == "inputs_north_south"
    )
    bindings = {port["id"]: None for port in mode["ports"]}
    for port in mode["ports"]:
        if port["kind"] == "output":
            bindings[port["id"]] = "source_ore"
    bindings["input_S_1"] = "qiaoyu_capsule"
    bindings["input_S_2"] = "valley_battery"
    for index, commodity in enumerate(north_inputs, start=1):
        bindings[f"input_N_{index}"] = commodity
    placement = {
        "instance_id": "protocol_core_001",
        "template": "protocol_core",
        "mode": "inputs_north_south",
        "anchor": {"x": CORE_ANCHOR[0], "y": CORE_ANCHOR[1]},
        "port_bindings": bindings,
    }
    return router.terminals_from_witness(strict_instance, [placement])


def _safe_lower_tb_shared_sinks() -> tuple[Any, ...]:
    """TB row below y=43 presents north-facing input/sink terminals."""

    return (
        router.Terminal("lower_tb_a", "input_N", "input", "qiaoyu_capsule", (4, 43), "N"),
        router.Terminal("lower_tb_b", "input_N", "input", "valley_battery", (5, 43), "N"),
    )


def _assert_strict_component_shape(component: dict[str, Any], commodities: set[str]) -> None:
    assert component["kind"] in {"straight", "turn", "splitter", "merger"}
    inputs = component["inputs"]
    outputs = component["outputs"]
    assert len(inputs) == len(set(inputs))
    assert len(outputs) == len(set(outputs))
    assert not (set(inputs) & set(outputs))
    assert set(component["commodities"]) == commodities
    if component["kind"] == "straight":
        assert len(inputs) == len(outputs) == 1
        assert outputs[0] == OPPOSITE[inputs[0]]
    elif component["kind"] == "turn":
        assert len(inputs) == len(outputs) == 1
        assert outputs[0] not in {inputs[0], OPPOSITE[inputs[0]]}
    elif component["kind"] == "splitter":
        assert len(inputs) == 1 and len(outputs) in {2, 3}
    else:
        assert len(outputs) == 1 and len(inputs) in {2, 3}


def _checker_graph_is_scc(
    components: list[dict[str, Any]],
    commodity: str,
) -> bool:
    by_cell = {
        (component["cell"]["x"], component["cell"]["y"]): component
        for component in components
    }
    graph: defaultdict[tuple[int, int], set[tuple[int, int]]] = defaultdict(set)
    reverse: defaultdict[tuple[int, int], set[tuple[int, int]]] = defaultdict(set)
    for cell, component in by_cell.items():
        if commodity not in component["commodities"]:
            continue
        for direction in component["outputs"]:
            dx, dy = DELTA[direction]
            neighbor_cell = (cell[0] + dx, cell[1] + dy)
            neighbor = by_cell.get(neighbor_cell)
            if (
                neighbor is not None
                and commodity in neighbor["commodities"]
                and OPPOSITE[direction] in neighbor["inputs"]
            ):
                graph[cell].add(neighbor_cell)
                reverse[neighbor_cell].add(cell)

    start = min(by_cell)

    def visit(adjacency: defaultdict[tuple[int, int], set[tuple[int, int]]]) -> set[tuple[int, int]]:
        seen = {start}
        queue = deque([start])
        while queue:
            cell = queue.popleft()
            for neighbor in adjacency[cell]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        return seen

    return visit(graph) == set(by_cell) == visit(reverse)


def _strict_source_sink_totals(strict_instance: dict[str, Any]) -> tuple[Counter[str], Counter[str]]:
    sources = Counter(strict_instance["generic_requirements"]["raw_outputs"])
    sinks = Counter(strict_instance["generic_requirements"]["final_inputs"])
    for group in strict_instance["operation_groups"]:
        for commodity, count in group["port_needs"]["outputs"].items():
            sources[commodity] += group["count"] * count
        for commodity, count in group["port_needs"]["inputs"].items():
            sinks[commodity] += group["count"] * count
    return sources, sinks


def test_exact_campaign_boundary_core_and_shelf_phase_are_strict_legal(
    strict_instance: dict[str, Any],
) -> None:
    boundary_terminals, occupied = _boundary_contract()
    occupied.update(CORE_BODY)
    terminals = [
        *boundary_terminals,
        *_core_terminals(strict_instance),
        *_safe_lower_tb_shared_sinks(),
    ]
    edges = _campaign_edges()
    components = router.build_route_components(
        edges=edges,
        terminals=terminals,
        commodities=strict_instance["commodities"],
        occupied_cells=occupied,
    )
    by_cell = {
        (component["cell"]["x"], component["cell"]["y"]): component
        for component in components
    }

    assert len(boundary_terminals) == 46
    assert len(_core_terminals(strict_instance)) == 8
    assert len(occupied) == 138 + 81
    assert len(edges) == 1212
    assert len(components) == 1197
    assert Counter(component["kind"] for component in components) == {
        "straight": 1111,
        "merger": 66,
        "splitter": 17,
        "turn": 3,
    }
    for component in components:
        _assert_strict_component_shape(component, set(strict_instance["commodities"]))

    assert (by_cell[(1, 1)]["kind"], by_cell[(1, 1)]["inputs"], by_cell[(1, 1)]["outputs"]) == (
        "merger",
        ["N", "W"],
        ["E"],
    )
    assert (by_cell[(2, 1)]["kind"], by_cell[(2, 1)]["inputs"], by_cell[(2, 1)]["outputs"]) == (
        "merger",
        ["N", "S", "W"],
        ["E"],
    )
    assert (by_cell[(12, 49)]["kind"], by_cell[(12, 49)]["inputs"], by_cell[(12, 49)]["outputs"]) == (
        "splitter",
        ["N"],
        ["E", "S"],
    )
    for cell, expected_inputs in (
        ((2, 45), ["N", "E"]),
        ((2, 48), ["N", "E"]),
        ((2, 51), ["N", "E"]),
        ((12, 45), ["N", "W"]),
        ((12, 48), ["N", "W"]),
        ((12, 51), ["N", "W"]),
    ):
        assert by_cell[cell]["kind"] == "merger"
        assert by_cell[cell]["inputs"] == expected_inputs
        assert by_cell[cell]["outputs"] == ["S"]
    for cell in ((4, 43), (5, 43)):
        assert by_cell[cell]["kind"] == "splitter"
        assert by_cell[cell]["inputs"] == ["W"]
        assert by_cell[cell]["outputs"] == ["N", "E", "S"]

    sources, sinks = _strict_source_sink_totals(strict_instance)
    assert sum(sources.values()) == 316
    assert sum(sinks.values()) == 312
    assert len(strict_instance["commodities"]) == 19
    assert all(sources[commodity] > 0 and sinks[commodity] > 0 for commodity in strict_instance["commodities"])
    assert all(
        _checker_graph_is_scc(components, commodity)
        for commodity in strict_instance["commodities"]
    )


def test_north_core_input_is_off_campaign_network(strict_instance: dict[str, Any]) -> None:
    with pytest.raises(router.NetworkRoutingError) as exc_info:
        router.build_route_components(
            edges=_campaign_edges(),
            terminals=_core_terminals(strict_instance, north_inputs=("qiaoyu_capsule",)),
            commodities=strict_instance["commodities"],
            occupied_cells=CORE_BODY,
        )

    assert exc_info.value.code == "TERMINAL_OFF_NETWORK"
    assert exc_info.value.cell == (4, 53)


def test_chord_at_core_output_level_compiles_to_straight_cross(
    strict_instance: dict[str, Any],
) -> None:
    components = router.build_route_components(
        edges=_campaign_edges(extra_levels=(45,)),
        terminals=_core_terminals(strict_instance),
        commodities=strict_instance["commodities"],
        occupied_cells=CORE_BODY,
    )
    component = next(item for item in components if item["cell"] == {"x": 12, "y": 45})

    assert component["kind"] == "cross"
    assert component["channels"] == [
        {
            "inputs": ["W"],
            "outputs": ["E"],
            "commodities": sorted(strict_instance["commodities"]),
        },
        {
            "inputs": ["N"],
            "outputs": ["S"],
            "commodities": sorted(strict_instance["commodities"]),
        },
    ]


def test_opposite_phase_terminal_below_core_compiles_to_straight_cross(
    strict_instance: dict[str, Any],
) -> None:
    # A BT row below the chord presents a north-facing output/source.  At the
    # same cell the core presents a south-facing input/sink, so the eastbound
    # chord would need two inputs and two outputs.
    wrong_phase_terminal = router.Terminal(
        "lower_bt",
        "output_N",
        "output",
        "qiaoyu_capsule",
        (4, 43),
        "N",
    )
    components = router.build_route_components(
        edges=_campaign_edges(),
        terminals=(*_core_terminals(strict_instance), wrong_phase_terminal),
        commodities=strict_instance["commodities"],
        occupied_cells=CORE_BODY,
    )
    component = next(item for item in components if item["cell"] == {"x": 4, "y": 43})

    assert component["kind"] == "cross"
    assert component["channels"] == [
        {
            "inputs": ["W"],
            "outputs": ["E"],
            "commodities": sorted(strict_instance["commodities"]),
        },
        {
            "inputs": ["S"],
            "outputs": ["N"],
            "commodities": sorted(strict_instance["commodities"]),
        },
    ]
