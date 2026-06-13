from __future__ import annotations

from typing import Any, Dict, List, Mapping

from src.models.d2_commodity_flow_core import D2CommodityFlowCore, D2PoseAssumption
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
