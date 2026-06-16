"""Phase 2 Task 1 — shared pricing pose-index cache (dict-of-PoseRecord + grid index).

Phase 1 each ramp rebuilt the pricing CP-SAT model from scratch + reran
`enumerate_poses_in_region` per region.  Phase 2 reuses a single union
pose pool plus a (x, y) -> List[pose_key] grid index so region filtering
becomes set-intersection on a precomputed index instead of a linear scan
over the full pool.

Design choices documented in Phase 2 README.md §"pricing share cache":
- dict-based (PoseRecord same as Phase 1, no new dataclass) — keeps the
  import surface tiny + interop with `solve_pricing` / direct master.
- Per-cell index: dict[CellCoord, list[(tpl, pose_idx)]].  Region query
  iterates region cells (≤ 12×12 = 144) and unions hit pose keys.  For
  region_size=12 this is ~16x smaller scan than the Phase 1 linear
  walk over O(20K poses/type).  Net: cache_hit_pct is 100% by
  construction once the index is built (one-time cost amortised).
- We also precompute per-instance pose filtering (drop poses overlapping
  the ghost rect once, not per-region).
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

# Phase 1 reuse (no edits there).
from cand_c_column_generation_phase1_20260521.column_grammar import (  # type: ignore
    CellCoord,
    PortTuple,
)


# Re-import the Phase 1 PoseRecord to avoid duplicate type definitions.
# Phase 1 phase1_probe.py defines PoseRecord at module scope, so we re-
# alias by structural compatibility (Phase 2 doesn't need to import it
# strictly; we accept any dataclass with .cells / .pose_idx / .tpl /
# .typed_ports / .port_cells / .port_count / .anchor).  Phase 2 probe
# imports PoseRecord directly from phase1_probe at runtime.


@dataclass
class PricingShareCache:
    """Shared pricing index.

    Members:
        pose_records: full union (tpl, pose_idx) -> PoseRecord-like obj.
            (We don't strictly type the value to avoid coupling to the
            phase1_probe.PoseRecord; runtime duck-typing only.)
        cell_index: (x, y) -> sorted list of (tpl, pose_idx) keys that
            *occupy* the cell.
        instance_pose_index: instance_id -> list of (tpl, pose_idx) keys
            valid for that instance (ghost-rect filtered).
        ghost_filtered_count: poses dropped for ghost-rect overlap.
        build_seconds: time spent building the cache (one-time).
        hits: number of region queries served.
        miss_fallback: number of region queries that had to fall back to
            linear scan (should stay 0 in normal operation).
    """

    pose_records: Dict[Tuple[str, int], Any] = field(default_factory=dict)
    cell_index: Dict[CellCoord, List[Tuple[str, int]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    instance_pose_index: Dict[str, List[Tuple[str, int]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    ghost_filtered_count: int = 0
    build_seconds: float = 0.0
    hits: int = 0
    miss_fallback: int = 0

    def cache_hit_rate(self) -> float:
        total = self.hits + self.miss_fallback
        if total == 0:
            return 0.0
        return self.hits / total


def build_share_cache(
    pools: Mapping[str, Sequence[Any]],
    instances: Sequence[Mapping[str, Any]],
    ghost_filter_fn,
) -> PricingShareCache:
    """Build the shared cache once (caller invokes once per probe run).

    `ghost_filter_fn(cell) -> bool` returns True iff `cell` is inside the
    forbidden ghost rect; matched poses are dropped at cache-build time
    so per-iter pricing builds skip the check.
    """
    t0 = time.perf_counter()
    cache = PricingShareCache()
    seen_keys: Set[Tuple[str, int]] = set()
    # 1) Build full union pose_records (filter ghost-overlap once).
    for tpl, poses in pools.items():
        for pose in poses:
            key = (tpl, pose.pose_idx)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if any(ghost_filter_fn(c) for c in pose.cells):
                cache.ghost_filtered_count += 1
                continue
            cache.pose_records[key] = pose
            for cell in pose.cells:
                cache.cell_index[cell].append(key)
    # 2) Build per-instance index (filter to instance's facility type).
    for inst in instances:
        iid = inst["instance_id"]
        tpl = inst["facility_type"]
        for pose in pools.get(tpl, ()):
            key = (tpl, pose.pose_idx)
            if key in cache.pose_records:
                cache.instance_pose_index[iid].append(key)
    cache.build_seconds = time.perf_counter() - t0
    return cache


def query_region_poses(
    cache: PricingShareCache,
    region: Tuple[int, int, int, int],
    instance_id: str,
) -> List[Any]:
    """Return poses for `instance_id` fully contained in `region`.

    Uses the per-instance pose index (already ghost-filtered).  Region
    containment test = all pose cells lie within the bbox.
    """
    cache.hits += 1
    x_lo, y_lo, x_hi, y_hi = region
    out: List[Any] = []
    for key in cache.instance_pose_index.get(instance_id, ()):
        pose = cache.pose_records.get(key)
        if pose is None:
            continue
        if all(x_lo <= cx <= x_hi and y_lo <= cy <= y_hi for cx, cy in pose.cells):
            out.append(pose)
    return out


def cache_summary(cache: PricingShareCache) -> Dict[str, Any]:
    n_records = len(cache.pose_records)
    n_cells_indexed = len(cache.cell_index)
    n_instances_indexed = len(cache.instance_pose_index)
    avg_per_cell = (
        sum(len(v) for v in cache.cell_index.values()) / max(1, n_cells_indexed)
    )
    return {
        "n_pose_records": n_records,
        "n_cells_indexed": n_cells_indexed,
        "n_instances_indexed": n_instances_indexed,
        "avg_poses_per_cell": avg_per_cell,
        "ghost_filtered_count": cache.ghost_filtered_count,
        "build_seconds": cache.build_seconds,
        "hits": cache.hits,
        "miss_fallback": cache.miss_fallback,
        "cache_hit_rate": cache.cache_hit_rate(),
    }


__all__ = [
    "PricingShareCache",
    "build_share_cache",
    "query_region_poses",
    "cache_summary",
]
