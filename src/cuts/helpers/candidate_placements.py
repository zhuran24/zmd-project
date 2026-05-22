"""candidate_placements.json lookup helpers (Gap 9 修, round 30 audit).

修 F3 port_exposure (跟未来 F8 power_grid_reach) 假设 ports_by_pose 在
canonical_rules — 真 ports 在 candidate_placements.json pose 层
(input_port_cells + output_port_cells, 含 x/y/dir/commodity).

Structure (data/preprocessed/candidate_placements.json):
```
{
  "facility_pools": {
    "boundary_storage_port": [
      {
        "pose_id": "viewer::boundary_required_output_blue_iron_ore_019",
        "anchor": {"x": 0, "y": 10},
        "occupied_cells": [[0, 10], [0, 11], [0, 12]],
        "input_port_cells": [],
        "output_port_cells": [
          {"x": 0, "y": 10, "dir": "N", "commodity": "blue_iron_ore"}
        ]
      },
      ...
    ],
    "manufacturing_3x3": [...],
    ...
  }
}
```

Direction encoding: N/S/E/W (cardinal). Grid coords (x=row, y=col):
- N (north): x decrease (dx=-1, dy=0)
- S (south): x increase (dx=+1, dy=0)
- E (east):  y increase (dx=0, dy=+1)
- W (west):  y decrease (dx=0, dy=-1)

Refs:
- docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_30_gap6_audit_NOT_GO.md
- data/preprocessed/candidate_placements.json — schema source-of-truth
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from src.cuts.helpers.canonical_rules import facility_type_for_group
from src.cuts.lifecycle import BState, GroupId, PoseId


# Direction encoding (N/S/E/W) → (dx, dy) cell offset.
DIRECTION_OFFSETS = {
    "N": (-1, 0),
    "S": (1, 0),
    "E": (0, 1),
    "W": (0, -1),
}


def find_pose(
    state: BState,
    gid: GroupId,
    pose_id: PoseId,
) -> Optional[dict]:
    """Locate pose dict from candidate_placements.

    Maps group_id → facility_type via instance_to_facility_type, then linear-scans
    facility_pools[ft] for pose_id match.

    Returns None if any lookup step fails (candidate_placements not injected /
    facility_type unmapped / pose_id not found).

    Phase 1.5+ optimize: pre-build pose_id → pose dict cache on state.
    """
    cp = state.candidate_placements
    if cp is None:
        return None
    ft = facility_type_for_group(state, gid)
    if ft is None:
        return None
    pools = cp.get("facility_pools", {})
    pool = pools.get(ft, [])
    for pose in pool:
        if pose.get("pose_id") == pose_id:
            return pose
    return None


def pose_ports(
    state: BState,
    gid: GroupId,
    pose_id: PoseId,
) -> Optional[List[dict]]:
    """Returns concat list of input_port_cells + output_port_cells for pose.

    Each entry: {"x": int, "y": int, "dir": str, "commodity": str}.

    Returns None if pose lookup fails (caller fail-closed).
    """
    pose = find_pose(state, gid, pose_id)
    if pose is None:
        return None
    inputs = pose.get("input_port_cells", [])
    outputs = pose.get("output_port_cells", [])
    return list(inputs) + list(outputs)


def direction_offset(direction: str) -> Tuple[int, int]:
    """Cardinal direction (N/S/E/W) → (dx, dy) offset. Raises ValueError on unknown."""
    if direction not in DIRECTION_OFFSETS:
        raise ValueError(f"unknown port direction={direction!r}, expect N/S/E/W")
    return DIRECTION_OFFSETS[direction]
