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

Direction encoding: N/S/E/W (cardinal). **Gap 11 修 (round 31)**: 真数据
geometry 实测 (manufacturing_3x3 pose anchor x=1 y=10 occupied x∈[1,3] y∈[10,12],
output port (x=2, y=10, dir="N") — front must be outside facility):
- 若 N=(-1,0): front=(1,10) — **in** occupied (facility 内). ✗
- 若 N=(0,-1): front=(2,9) — out of occupied. ✓

所以 grid coord (x=column, y=row) — y is row 上下方向, x is col 左右方向:
- N (north): y decrease (dx=0, dy=-1)
- S (south): y increase (dx=0, dy=+1)
- E (east):  x increase (dx=+1, dy=0)
- W (west):  x decrease (dx=-1, dy=0)

Refs:
- docs/research/p3_b_design_v2_20260521/cross_check/gemini_round_30_gap6_audit_NOT_GO.md
- data/preprocessed/candidate_placements.json — schema source-of-truth
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, FrozenSet, List, Optional, Tuple, cast

from src.cuts.helpers.canonical_rules import facility_type_for_group
from src.cuts.lifecycle import BState, GroupId, PoseId


# Direction encoding (N/S/E/W) → (dx, dy) cell offset.
# Gap 11 修 (round 31): 真数据实测 — y is row, x is col.
DIRECTION_OFFSETS = {
    "N": (0, -1),
    "S": (0, 1),
    "E": (1, 0),
    "W": (-1, 0),
}


_POSE_CACHE_KEY = "__pose_id_cache__"
_POSE_CACHE_DIGEST_KEY = "__pose_id_cache_digest__"


def _cache_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, item in value.items():
            out[str(key)] = _cache_jsonable(item)
        return out
    if isinstance(value, (list, tuple)):
        return [_cache_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_cache_jsonable(item) for item in value), key=repr)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _facility_pools_digest(cp: Dict[str, Any]) -> Optional[str]:
    pools = cp.get("facility_pools", {})
    if not isinstance(pools, dict):
        return None
    blob = json.dumps(
        _cache_jsonable(pools),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _build_pose_cache(cp: Dict[str, Any]) -> Optional[Dict[Tuple[str, str], Dict[str, Any]]]:
    pools = cp.get("facility_pools", {})
    if not isinstance(pools, dict):
        return None
    cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for pool_ft, pool in pools.items():
        if not isinstance(pool_ft, str) or not isinstance(pool, list):
            continue
        for pose_raw in pool:
            if not isinstance(pose_raw, dict):
                continue
            pose = cast(Dict[str, Any], pose_raw)
            pid = pose.get("pose_id")
            if isinstance(pid, str):
                cache[(pool_ft, pid)] = pose
    return cache


def find_pose(
    state: BState,
    gid: GroupId,
    pose_id: PoseId,
) -> Optional[Dict[str, Any]]:
    """Locate pose dict from candidate_placements.

    Gap 14 修 (round 31): O(1) cache (dict[pose_id, pose]) 替 linear scan.
    Cache 存 candidate_placements 内部 (under "__pose_id_cache__" key),
    lazy-built first lookup. 266 instance × 4 facility_type, pool size up to
    132 — linear scan was O(N) per validate.

    Maps group_id → facility_type via instance_to_facility_type, then O(1)
    dict lookup. Returns None if any step fails.
    """
    cp = state.candidate_placements
    if cp is None:
        return None
    ft = facility_type_for_group(state, gid)
    if ft is None:
        return None
    # Lazy build cache (first call cost O(N), subsequent O(1) when source is
    # unchanged).  The digest is required for soundness because validators use
    # this helper while CutScope.source_digest hashes candidate_placements
    # without runtime ``__*`` caches.  A stale cache must not outlive a replaced
    # or edited facility pool.
    current_digest = _facility_pools_digest(cp)
    if current_digest is None:
        return None
    raw_cache = cp.get(_POSE_CACHE_KEY)
    raw_digest = cp.get(_POSE_CACHE_DIGEST_KEY)
    if isinstance(raw_cache, dict) and raw_digest == current_digest:
        cache = cast(Dict[Tuple[str, str], Dict[str, Any]], raw_cache)
    else:
        rebuilt = _build_pose_cache(cp)
        if rebuilt is None:
            return None
        cache = rebuilt
        cp[_POSE_CACHE_KEY] = cache
        cp[_POSE_CACHE_DIGEST_KEY] = current_digest
    return cache.get((ft, pose_id))


def pose_ports(
    state: BState,
    gid: GroupId,
    pose_id: PoseId,
) -> Optional[List[Dict[str, Any]]]:
    """Returns concat list of input_port_cells + output_port_cells for pose.

    Each entry: {"x": int, "y": int, "dir": str, "commodity": str}.

    Returns None if pose lookup fails (caller fail-closed).
    """
    pose = find_pose(state, gid, pose_id)
    if pose is None:
        return None
    inputs = pose.get("input_port_cells", [])
    outputs = pose.get("output_port_cells", [])
    if not isinstance(inputs, list) or not isinstance(outputs, list):
        return []
    return [cast(Dict[str, Any], p) for p in inputs + outputs if isinstance(p, dict)]


def direction_offset(direction: str) -> Tuple[int, int]:
    """Cardinal direction (N/S/E/W) → (dx, dy) offset. Raises ValueError on unknown."""
    if direction not in DIRECTION_OFFSETS:
        raise ValueError(f"unknown port direction={direction!r}, expect N/S/E/W")
    return DIRECTION_OFFSETS[direction]


def all_poses_in_region(
    state: BState,
    gid: GroupId,
    region_cells: FrozenSet[Tuple[int, int]],
) -> Optional[bool]:
    """Verify P(g) ⊆ R — group's全 pose 的 occupied_cells 都 ⊆ R (GPT pro round 2 P0-1).

    Spec §2b 严格条件: group g 只 contributing 当所有 pose 的占格集 ⊆ R.
    若有任一 pose 占格 in cells outside R, group 不 contributing (demand 不
    必落 R 内, cut 假证).

    真数据 (boundary_io 46 instance):
    - placement_rule="left_or_bottom_boundary" + R=left∪bottom union
    - 54 pose 中 14 个占格 (31,69)/(32,69)/(33,69) 等不在 union
    - 整 group 不 P(g)⊆R → 不 contributing (Phase 1.1 v1.1 fail-closed)
    - Phase 1.5+ 可能拆 group 为 "P(g)⊆R subset" + "其余"

    Returns:
    - True iff 所有 pose 的占格 ⊆ region_cells
    - False iff ∃ pose 占格 包含 region_cells 外的 cell
    - None iff data 不全 (state.candidate_placements / pose_domain 缺失) —
      fail-closed: 调用方应 skip group (not contributing) / 拒 cut
    """
    if gid not in state.groups:
        return None
    pose_domain = state.groups[gid].pose_domain
    if not pose_domain:
        return None  # 无 pose info, fail-closed
    for pose_id in pose_domain:
        pose = find_pose(state, gid, pose_id)
        if pose is None:
            return None  # data 不全
        occupied_cells = pose.get("occupied_cells", [])
        if not isinstance(occupied_cells, list):
            return None
        for cell in occupied_cells:
            if tuple(cell) not in region_cells:
                return False  # 反例: pose 占 R 外 cell
    return True


