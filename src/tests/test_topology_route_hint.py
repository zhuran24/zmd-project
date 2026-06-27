from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from src.preprocess.material_skeleton import build_material_connection_skeleton
from src.search.topology_route_hint import (
    compute_route_corridors,
    compute_route_hints,
    corridor_contains_cell,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _toy_skeleton() -> dict[str, Any]:
    return {
        "node_groups": [
            {"operation_type": "prod", "instance_ids": ["p1"]},
            {"operation_type": "cons", "instance_ids": ["c1"]},
        ],
        "material_edges": [
            {
                "commodity_id": "widget",
                "producers": [{"group_id": "operation:prod"}],
                "consumers": [{"group_id": "operation:cons"}],
                "pool_exchangeable": False,
            }
        ],
    }


def _toy_placement() -> dict[str, Any]:
    return {
        "p1": {"operation_type": "prod", "occupied_cells": [[0, 0]]},
        "c1": {"operation_type": "cons", "occupied_cells": [[10, 10]]},
    }


def test_corridor_geometry_is_bounding_box_of_centroids() -> None:
    corridors = compute_route_corridors(_toy_skeleton(), _toy_placement())
    assert set(corridors) == {"widget"}
    corridor = corridors["widget"]
    assert corridor["producer_centroid"] == [0.0, 0.0]
    assert corridor["consumer_centroid"] == [10.0, 10.0]
    assert corridor["band"] == [0.0, 0.0, 10.0, 10.0]


def test_corridor_contains_cell_inside_and_outside() -> None:
    corridor = compute_route_corridors(_toy_skeleton(), _toy_placement())["widget"]
    assert corridor_contains_cell(corridor, (5, 5)) is True
    assert corridor_contains_cell(corridor, (0, 0)) is True
    assert corridor_contains_cell(corridor, (10, 10)) is True
    assert corridor_contains_cell(corridor, (20, 20)) is False
    assert corridor_contains_cell(corridor, (-1, 5)) is False
    assert corridor_contains_cell(corridor, (11, 2)) is False
    # margin widens the band.
    assert corridor_contains_cell(corridor, (11, 2), margin=1.0) is True


def test_route_hints_are_off_corridor_only_and_zero_valued() -> None:
    hints = compute_route_hints(
        _toy_skeleton(),
        _toy_placement(),
        {"widget": [(5, 5), (3, 8), (20, 20), (11, 2)]},
    )
    cells = [tuple(hint["cell"]) for hint in hints]
    assert cells == [(11, 2), (20, 20)]  # sorted, on-corridor (5,5)/(3,8) excluded
    assert all(hint["suggested_hint"] == 0 for hint in hints)
    assert all(hint["commodity_id"] == "widget" for hint in hints)


def test_route_hints_are_deterministic() -> None:
    args = (_toy_skeleton(), _toy_placement(), {"widget": [(20, 20), (11, 2), (5, 5)]})
    assert compute_route_hints(*args) == compute_route_hints(*args)


def test_route_hints_do_not_mutate_inputs() -> None:
    skeleton = _toy_skeleton()
    placement = _toy_placement()
    commodity_cells = {"widget": [(20, 20), (5, 5)]}
    skeleton_snapshot = copy.deepcopy(skeleton)
    placement_snapshot = copy.deepcopy(placement)
    cells_snapshot = copy.deepcopy(commodity_cells)

    compute_route_hints(skeleton, placement, commodity_cells)

    assert skeleton == skeleton_snapshot
    assert placement == placement_snapshot
    assert commodity_cells == cells_snapshot


def test_no_corridor_when_producer_or_consumer_unplaced() -> None:
    skeleton = _toy_skeleton()
    placement = {"c1": {"operation_type": "cons", "occupied_cells": [[10, 10]]}}
    assert compute_route_corridors(skeleton, placement) == {}
    assert compute_route_hints(skeleton, placement, {"widget": [(20, 20)]}) == []


def test_garbage_cells_are_ignored() -> None:
    hints = compute_route_hints(
        _toy_skeleton(),
        _toy_placement(),
        {"widget": [(20, 20), "nope", (1.5, 2.5), (None, 3)]},
    )
    assert [tuple(hint["cell"]) for hint in hints] == [(20, 20)]


def test_real_skeleton_with_empty_placement_yields_no_corridors() -> None:
    skeleton = build_material_connection_skeleton(PROJECT_ROOT)
    assert compute_route_corridors(skeleton, {}) == {}
    assert compute_route_hints(skeleton, {}, {"steel_block": [(1, 1)]}) == []


def test_centroid_averages_multiple_producer_instances() -> None:
    skeleton = {
        "node_groups": [
            {"operation_type": "prod", "instance_ids": ["p1", "p2"]},
            {"operation_type": "cons", "instance_ids": ["c1"]},
        ],
        "material_edges": [
            {
                "commodity_id": "widget",
                "producers": [{"group_id": "operation:prod"}],
                "consumers": [{"group_id": "operation:cons"}],
                "pool_exchangeable": False,
            }
        ],
    }
    placement = {
        "p1": {"operation_type": "prod", "occupied_cells": [[0, 0]]},
        "p2": {"operation_type": "prod", "occupied_cells": [[4, 0]]},
        "c1": {"operation_type": "cons", "occupied_cells": [[10, 10]]},
    }
    corridor = compute_route_corridors(skeleton, placement)["widget"]
    assert corridor["producer_centroid"] == [2.0, 0.0]
    assert corridor["band"] == [2.0, 0.0, 10.0, 10.0]


def test_entry_point_averages_multiple_occupied_cells() -> None:
    placement = {
        "p1": {"operation_type": "prod", "occupied_cells": [[0, 0], [2, 0]]},
        "c1": {"operation_type": "cons", "occupied_cells": [[10, 10]]},
    }
    corridor = compute_route_corridors(_toy_skeleton(), placement)["widget"]
    assert corridor["producer_centroid"] == [1.0, 0.0]


def test_warehouse_endpoints_are_skipped() -> None:
    skeleton = {
        "node_groups": [{"operation_type": "cons", "instance_ids": ["c1"]}],
        "material_edges": [
            {
                "commodity_id": "widget",
                "producers": [{"group_id": "warehouse:generic_output_pool"}],
                "consumers": [{"group_id": "operation:cons"}],
                "pool_exchangeable": False,
            }
        ],
    }
    placement = {"c1": {"operation_type": "cons", "occupied_cells": [[10, 10]]}}
    # The only producer endpoint is a warehouse: pool (no placement coords), so
    # there is no producer point => no corridor.
    assert compute_route_corridors(skeleton, placement) == {}


def test_entry_point_anchor_and_bare_xy_fallbacks() -> None:
    anchor_placement = {
        "p1": {"operation_type": "prod", "anchor": [0, 0]},
        "c1": {"operation_type": "cons", "anchor": {"x": 10, "y": 10}},
    }
    corridor = compute_route_corridors(_toy_skeleton(), anchor_placement)["widget"]
    assert corridor["band"] == [0.0, 0.0, 10.0, 10.0]

    xy_placement = {
        "p1": {"operation_type": "prod", "x": 1, "y": 2},
        "c1": {"operation_type": "cons", "x": 5, "y": 6},
    }
    corridor_xy = compute_route_corridors(_toy_skeleton(), xy_placement)["widget"]
    assert corridor_xy["producer_centroid"] == [1.0, 2.0]
    assert corridor_xy["consumer_centroid"] == [5.0, 6.0]
