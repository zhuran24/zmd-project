from __future__ import annotations

import importlib

import pytest


router = importlib.import_module(
    "docs.research.witness_constructor_20260717.07_routing_aware.network_router"
)


def _intersecting_directed_rings() -> frozenset[tuple[tuple[int, int], tuple[int, int]]]:
    edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    for x0, y0, x1, y1 in ((1, 3, 7, 5), (3, 1, 5, 7)):
        router._add_line(edges, (x0, y0), (x1, y0))
        router._add_line(edges, (x1, y0), (x1, y1))
        router._add_line(edges, (x1, y1), (x0, y1))
        router._add_line(edges, (x0, y1), (x0, y0))
    return frozenset(edges)


def test_shelf_network_is_one_strongly_connected_component() -> None:
    spec = router.ShelfNetworkSpec(chord_levels=(5, 9, 13, 17))
    edges = router.shelf_network_edges(spec)

    router.assert_strongly_connected(edges)
    cells = router.network_cells(edges)
    assert (1, 1) in cells
    assert (69, 69) in cells
    assert (2, 9) in cells
    assert (42, 13) in cells


def test_core_bypass_keeps_blocked_chord_out_of_body() -> None:
    spec = router.ShelfNetworkSpec(
        chord_levels=(37, 43, 49, 54, 59),
        core_anchor=(3, 44),
    )
    edges = router.shelf_network_edges(spec)
    cells = router.network_cells(edges)
    core = {(x, y) for x in range(3, 12) for y in range(44, 53)}

    router.assert_strongly_connected(edges)
    assert not (cells & core)
    assert (12, 49) in cells
    assert (11, 49) not in cells
    assert all((12, y) in cells for y in range(43, 55))


def test_components_accept_source_merger_and_sink_splitter() -> None:
    spec = router.ShelfNetworkSpec(chord_levels=(5,))
    edges = router.shelf_network_edges(spec)
    terminals = (
        router.Terminal("source", "out", "output", "ore", (10, 5), "N"),
        router.Terminal("sink", "in", "input", "ore", (20, 5), "S"),
    )
    components = router.build_route_components(
        edges=edges,
        terminals=terminals,
        commodities=("ore",),
    )
    by_cell = {(item["cell"]["x"], item["cell"]["y"]): item for item in components}

    assert by_cell[(10, 5)]["kind"] == "merger"
    assert set(by_cell[(10, 5)]["inputs"]) == {"W", "S"}
    assert by_cell[(20, 5)]["kind"] == "splitter"
    assert set(by_cell[(20, 5)]["outputs"]) == {"E", "N"}


def test_two_same_kind_opposite_side_terminals_fit_three_way_component() -> None:
    spec = router.ShelfNetworkSpec(chord_levels=(5,))
    edges = router.shelf_network_edges(spec)
    terminals = (
        router.Terminal("upper", "out", "output", "a", (10, 5), "S"),
        router.Terminal("lower", "out", "output", "b", (10, 5), "N"),
        router.Terminal("sink_a", "in", "input", "a", (20, 5), "S"),
        router.Terminal("sink_b", "in", "input", "b", (21, 5), "S"),
    )
    components = router.build_route_components(
        edges=edges,
        terminals=terminals,
        commodities=("a", "b"),
    )
    component = next(item for item in components if item["cell"] == {"x": 10, "y": 5})

    assert component["kind"] == "merger"
    assert set(component["inputs"]) == {"W", "N", "S"}
    assert component["outputs"] == ["E"]


@pytest.mark.parametrize(
    ("inputs", "outputs"),
    [
        ({"N", "W"}, {"S", "E"}),
        ({"N", "E"}, {"S", "W"}),
        ({"S", "W"}, {"N", "E"}),
        ({"S", "E"}, {"N", "W"}),
    ],
)
def test_four_cross_variants_are_two_stable_straight_channels(
    inputs: set[str], outputs: set[str]
) -> None:
    component = router._component_for_cell((8, 9), inputs, outputs, ("z", "a", "z"))

    assert component == {
        "cell": {"x": 8, "y": 9},
        "kind": "cross",
        "channels": [
            {
                "inputs": [next(direction for direction in inputs if direction in {"E", "W"})],
                "outputs": [
                    router._OPPOSITE[next(direction for direction in inputs if direction in {"E", "W"})]
                ],
                "commodities": ["a", "z"],
            },
            {
                "inputs": [next(direction for direction in inputs if direction in {"N", "S"})],
                "outputs": [
                    router._OPPOSITE[next(direction for direction in inputs if direction in {"N", "S"})]
                ],
                "commodities": ["a", "z"],
            },
        ],
    }


def test_bent_two_by_two_component_is_not_a_cross() -> None:
    with pytest.raises(router.NetworkRoutingError) as exc_info:
        router._component_for_cell((8, 9), {"N", "S"}, {"E", "W"}, ("a",))

    assert exc_info.value.code == "INVALID_CROSS"


def test_mixed_source_and_sink_attachment_fails_closed() -> None:
    spec = router.ShelfNetworkSpec(chord_levels=(5,))
    terminals = (
        router.Terminal("source", "out", "output", "a", (10, 5), "N"),
        router.Terminal("sink", "in", "input", "a", (10, 5), "N"),
    )
    with pytest.raises(router.NetworkRoutingError) as exc_info:
        router.build_route_components(
            edges=router.shelf_network_edges(spec),
            terminals=terminals,
            commodities=("a",),
        )

    assert exc_info.value.code == "DIRECTION_REUSED"


def test_terminal_off_network_and_body_collision_fail_closed() -> None:
    spec = router.ShelfNetworkSpec(chord_levels=(5,))
    edges = router.shelf_network_edges(spec)
    with pytest.raises(router.NetworkRoutingError, match="TERMINAL_OFF_NETWORK"):
        router.build_route_components(
            edges=edges,
            terminals=(router.Terminal("x", "p", "input", "a", (30, 30), "N"),),
            commodities=("a",),
        )
    with pytest.raises(router.NetworkRoutingError, match="NETWORK_BODY_COLLISION"):
        router.build_route_components(
            edges=edges,
            terminals=(),
            commodities=("a",),
            occupied_cells=((10, 5),),
        )


def test_non_scc_scaffold_is_rejected() -> None:
    with pytest.raises(router.NetworkRoutingError, match="NETWORK_NOT_STRONGLY_CONNECTED"):
        router.assert_strongly_connected({((0, 0), (1, 0)), ((1, 0), (2, 0))})


def test_cell_scc_does_not_hide_cross_channel_route_disconnection() -> None:
    edges = _intersecting_directed_rings()
    terminals = (
        router.Terminal("horizontal_source", "out", "output", "ore", (2, 3), "S"),
        router.Terminal("vertical_sink", "in", "input", "ore", (5, 6), "W"),
    )

    # The four shared cells make the raw cell graph one SCC, but each is a
    # no-transfer crossing.  A lane-aware check must keep the rings separate.
    router.assert_strongly_connected(edges)
    with pytest.raises(router.NetworkRoutingError) as exc_info:
        router.build_route_components(edges=edges, terminals=terminals, commodities=("ore",))

    assert exc_info.value.code == "COMMODITY_SINK_UNREACHABLE"
    assert exc_info.value.cell == (5, 6)


def test_lane_validator_rejects_source_island_without_any_sink() -> None:
    edges = _intersecting_directed_rings()
    terminals = (
        router.Terminal("horizontal_source", "out", "output", "ore", (2, 3), "S"),
        router.Terminal("horizontal_sink", "in", "input", "ore", (6, 3), "S"),
        router.Terminal("vertical_source", "out", "output", "ore", (5, 2), "W"),
    )

    with pytest.raises(router.NetworkRoutingError) as exc_info:
        router.build_route_components(edges=edges, terminals=terminals, commodities=("ore",))

    assert exc_info.value.code == "COMMODITY_SOURCE_DEAD_END"
    assert exc_info.value.cell == (5, 2)


def test_intersecting_rings_with_local_source_sink_pairs_are_route_valid() -> None:
    edges = _intersecting_directed_rings()
    terminals = (
        router.Terminal("horizontal_source", "out", "output", "ore", (2, 3), "S"),
        router.Terminal("horizontal_sink", "in", "input", "ore", (6, 3), "S"),
        router.Terminal("vertical_source", "out", "output", "ore", (5, 2), "W"),
        router.Terminal("vertical_sink", "in", "input", "ore", (5, 6), "W"),
    )

    components = router.build_route_components(edges=edges, terminals=terminals, commodities=("ore",))
    crosses = [component for component in components if component["kind"] == "cross"]

    assert len(crosses) == 4
    assert all(len(component["channels"]) == 2 for component in crosses)
