from __future__ import annotations

from typing import Any, Dict, List, Mapping

from src.models.d2_commodity_flow_core import D2CommodityFlowCore, D2PoseAssumption
from src.models.routing_subproblem import (
    RoutingGrid,
    RoutingSubproblem,
    run_exact_routing_precheck,
)
from src.search.d2_separator import run_d2_separation


def _toy_corridor_case(
    *,
    blocked: bool,
) -> tuple[
    Dict[str, Dict[str, Any]],
    Dict[str, List[Dict[str, Any]]],
    List[Dict[str, Any]],
]:
    """Return a tiny one-row routing instance embedded in the 70x70 D2 grid.

    With ``blocked=True`` the wall pose occupies the only middle corridor cell,
    so D2 proves infeasibility under the current wall context.  With the wall
    moved away, the same source/sink poses are feasible; a cut over only the
    solver's terminal core would therefore over-cut.
    """

    grid = 70
    corridor = {(x, 0) for x in range(1, 69)}
    if blocked:
        free = corridor - {(35, 0)}
    else:
        free = corridor
    all_cells = {(x, y) for x in range(grid) for y in range(grid)}
    wall_cells = sorted(all_cells - free)

    facility_pools: Dict[str, List[Dict[str, Any]]] = {
        "src_tpl": [{"occupied_cells": [[0, 0]]}],
        "sink_tpl": [{"occupied_cells": [[69, 0]]}],
        "wall_tpl": [
            {"occupied_cells": [[int(x), int(y)] for x, y in wall_cells]}
        ],
    }
    placement = {
        "src": {"facility_type": "src_tpl", "pose_idx": 0},
        "sink": {"facility_type": "sink_tpl", "pose_idx": 0},
        "wall": {"facility_type": "wall_tpl", "pose_idx": 0},
    }
    ports = [
        {
            "instance_id": "src",
            "x": 0,
            "y": 0,
            "dir": "E",
            "commodity": "ore",
            "type": "out",
        },
        {
            "instance_id": "sink",
            "x": 69,
            "y": 0,
            "dir": "W",
            "commodity": "ore",
            "type": "in",
        },
    ]
    return placement, facility_pools, ports


class _RecordingMasterDelegate:
    def __init__(self) -> None:
        self.conflicts: List[Dict[str, int]] = []

    def add_benders_cut(self, conflict_set: Mapping[str, int]) -> bool:
        self.conflicts.append({str(k): int(v) for k, v in conflict_set.items()})
        return True


def test_d2_separator_cut_includes_occupancy_and_terminal_context() -> None:
    placement, facility_pools, ports = _toy_corridor_case(blocked=True)
    delegate = _RecordingMasterDelegate()

    result = run_d2_separation(
        master_delegate=delegate,
        placement_solution=placement,
        facility_pools=facility_pools,
        port_specs=ports,
        time_limit=5.0,
    )

    assert result.d2_status == "INFEASIBLE"
    assert result.cut_added is True
    assert delegate.conflicts == [{"src": 0, "sink": 0, "wall": 0}]
    assert result.raw_core_size == 1
    assert result.cut_metadata["support_conflict_size"] == 3
    assert result.cut_metadata["support_owners"] == ["sink", "src", "wall"]


def test_d2_raw_terminal_core_alone_is_not_a_sound_master_cut() -> None:
    placement, facility_pools, ports = _toy_corridor_case(blocked=True)
    occupied = set()
    for solution in placement.values():
        pool = facility_pools[solution["facility_type"]]
        for x, y in pool[int(solution["pose_idx"])]["occupied_cells"]:
            occupied.add((int(x), int(y)))
    assumptions = [
        D2PoseAssumption("src", 0, "d2_assum_src"),
        D2PoseAssumption("sink", 0, "d2_assum_sink"),
    ]
    blocked_d2 = D2CommodityFlowCore(
        occupied_cells=occupied,
        port_specs=ports,
        pose_assumptions=assumptions,
    )
    blocked_d2.build()
    assert blocked_d2.solve(time_limit=5.0) == "INFEASIBLE"
    blocked_result = blocked_d2.build_result()
    assert [(pa.instance_id, pa.pose_idx) for pa in blocked_result.core] == [("src", 0)]

    moved_placement, moved_pools, moved_ports = _toy_corridor_case(blocked=False)
    moved_occupied = set()
    for solution in moved_placement.values():
        pool = moved_pools[solution["facility_type"]]
        for x, y in pool[int(solution["pose_idx"])]["occupied_cells"]:
            moved_occupied.add((int(x), int(y)))
    moved_d2 = D2CommodityFlowCore(
        occupied_cells=moved_occupied,
        port_specs=moved_ports,
        pose_assumptions=assumptions,
    )
    moved_d2.build()
    assert moved_d2.solve(time_limit=5.0) == "FEASIBLE"


def _bridge_crossing_case() -> tuple[
    Dict[str, Dict[str, Any]],
    Dict[str, List[Dict[str, Any]]],
    List[Dict[str, Any]],
]:
    """A production-feasible two-layer crossing that D2's 2-D capacity rejects."""

    grid = 70
    free = {(x, 35) for x in range(1, 69)} | {(35, y) for y in range(1, 69)}
    port_cells = {(0, 35), (69, 35), (35, 0), (35, 69)}
    wall_cells = {(x, y) for x in range(grid) for y in range(grid)} - free - port_cells
    facility_pools: Dict[str, List[Dict[str, Any]]] = {
        "port_tpl": [
            {"occupied_cells": [[0, 35]]},
            {"occupied_cells": [[69, 35]]},
            {"occupied_cells": [[35, 0]]},
            {"occupied_cells": [[35, 69]]},
        ],
        "wall_tpl": [
            {"occupied_cells": [[int(x), int(y)] for x, y in sorted(wall_cells)]}
        ],
    }
    placement = {
        "h_src": {"facility_type": "port_tpl", "pose_idx": 0},
        "h_sink": {"facility_type": "port_tpl", "pose_idx": 1},
        "v_src": {"facility_type": "port_tpl", "pose_idx": 2},
        "v_sink": {"facility_type": "port_tpl", "pose_idx": 3},
        "wall": {"facility_type": "wall_tpl", "pose_idx": 0},
    }
    ports = [
        {
            "instance_id": "h_src",
            "x": 0,
            "y": 35,
            "dir": "E",
            "commodity": "h",
            "type": "out",
        },
        {
            "instance_id": "h_sink",
            "x": 69,
            "y": 35,
            "dir": "W",
            "commodity": "h",
            "type": "in",
        },
        {
            "instance_id": "v_src",
            "x": 35,
            "y": 0,
            "dir": "N",
            "commodity": "v",
            "type": "out",
        },
        {
            "instance_id": "v_sink",
            "x": 35,
            "y": 69,
            "dir": "S",
            "commodity": "v",
            "type": "in",
        },
    ]
    return placement, facility_pools, ports


def _splitter_case() -> tuple[
    Dict[str, Dict[str, Any]],
    Dict[str, List[Dict[str, Any]]],
    List[Dict[str, Any]],
]:
    """A production-feasible splitter topology that D2 flow balance rejects."""

    grid = 70
    free = {(x, 35) for x in range(1, 50)} | {(49, y) for y in range(35, 60)}
    port_cells = {(0, 35), (50, 35), (49, 60)}
    wall_cells = {(x, y) for x in range(grid) for y in range(grid)} - free - port_cells
    facility_pools: Dict[str, List[Dict[str, Any]]] = {
        "port_tpl": [
            {"occupied_cells": [[0, 35]]},
            {"occupied_cells": [[50, 35]]},
            {"occupied_cells": [[49, 60]]},
        ],
        "wall_tpl": [
            {"occupied_cells": [[int(x), int(y)] for x, y in sorted(wall_cells)]}
        ],
    }
    placement = {
        "src": {"facility_type": "port_tpl", "pose_idx": 0},
        "sink_e": {"facility_type": "port_tpl", "pose_idx": 1},
        "sink_n": {"facility_type": "port_tpl", "pose_idx": 2},
        "wall": {"facility_type": "wall_tpl", "pose_idx": 0},
    }
    ports = [
        {
            "instance_id": "src",
            "x": 0,
            "y": 35,
            "dir": "E",
            "commodity": "ore",
            "type": "out",
        },
        {
            "instance_id": "sink_e",
            "x": 50,
            "y": 35,
            "dir": "W",
            "commodity": "ore",
            "type": "in",
        },
        {
            "instance_id": "sink_n",
            "x": 49,
            "y": 60,
            "dir": "S",
            "commodity": "ore",
            "type": "in",
        },
    ]
    return placement, facility_pools, ports


def _occupied_from_case(
    placement: Mapping[str, Mapping[str, Any]],
    facility_pools: Mapping[str, List[Dict[str, Any]]],
) -> set[tuple[int, int]]:
    occupied: set[tuple[int, int]] = set()
    for solution in placement.values():
        pool = facility_pools[solution["facility_type"]]
        for x, y in pool[int(solution["pose_idx"])]["occupied_cells"]:
            occupied.add((int(x), int(y)))
    return occupied


def _assert_production_routing_feasible(
    occupied: set[tuple[int, int]],
    ports: List[Dict[str, Any]],
    commodities: List[str],
) -> None:
    assert (
        run_exact_routing_precheck(RoutingGrid(occupied, ports))["status"]
        == "feasible"
    )
    routing = RoutingSubproblem(RoutingGrid(occupied, ports), commodities)
    routing.build()
    assert routing.solve(time_limit=5.0) == "FEASIBLE"


def _assert_raw_d2_rejects(
    occupied: set[tuple[int, int]],
    ports: List[Dict[str, Any]],
) -> None:
    assumptions = [
        D2PoseAssumption(str(port["instance_id"]), 0, f"d2_assum_{port['instance_id']}")
        for port in ports
    ]
    d2 = D2CommodityFlowCore(
        occupied_cells=occupied,
        port_specs=ports,
        pose_assumptions=assumptions,
    )
    d2.build()
    assert d2.solve(time_limit=5.0) == "INFEASIBLE"


def test_d2_separator_refuses_precheck_feasible_bridge_crossing_context() -> None:
    placement, facility_pools, ports = _bridge_crossing_case()
    occupied = _occupied_from_case(placement, facility_pools)
    _assert_production_routing_feasible(occupied, ports, ["h", "v"])
    _assert_raw_d2_rejects(occupied, ports)

    delegate = _RecordingMasterDelegate()
    result = run_d2_separation(
        master_delegate=delegate,
        placement_solution=placement,
        facility_pools=facility_pools,
        port_specs=ports,
        time_limit=5.0,
    )

    assert result.cut_added is False
    assert delegate.conflicts == []
    assert result.d2_status == "MODEL_INVALID"
    assert result.reason == "routing_precheck_feasible_not_certified_for_d2_cut"


def test_d2_separator_refuses_precheck_feasible_splitter_context() -> None:
    placement, facility_pools, ports = _splitter_case()
    occupied = _occupied_from_case(placement, facility_pools)
    _assert_production_routing_feasible(occupied, ports, ["ore"])
    _assert_raw_d2_rejects(occupied, ports)

    delegate = _RecordingMasterDelegate()
    result = run_d2_separation(
        master_delegate=delegate,
        placement_solution=placement,
        facility_pools=facility_pools,
        port_specs=ports,
        time_limit=5.0,
    )

    assert result.cut_added is False
    assert delegate.conflicts == []
    assert result.d2_status == "MODEL_INVALID"
    assert result.reason == "routing_precheck_feasible_not_certified_for_d2_cut"
