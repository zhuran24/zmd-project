"""Family 6 shape_packing_hall partition lens helper.

Computes ghost+exterior-induced partition of a baseline region into maximal
contiguous unblocked segments. Per cut_family_specs/06_shape_packing_hall.md
v1.1 §5a — partition 必须只依赖 ``ghost_cells ∪ exterior_blocks`` (static),
**不**依赖 ``cell_owner``. 否则 cut 跨层活不下来 (Gemini round 14 finding #2).

Phase 1.0 P1.4 scope:
- ``compute_baseline_partition_lens(region_kind, state)`` → (lens, offsets)
- ``compute_region_cells(region_kind, grid_size=70)`` → ordered list of cells

P1.5+ family validator (src/cuts/families/shape_packing_hall.py) 用此 helper
+ cert.partition_lens 比对.

Refs:
- docs/research/p3_b_design_v2_20260521/cut_family_specs/06_shape_packing_hall.md v1.1
"""
from __future__ import annotations

from typing import List, Literal, Tuple

from src.cuts.lifecycle import BState, Cell


RegionKind = Literal["left_baseline", "bottom_baseline"]


def compute_region_cells(region_kind: RegionKind, grid_size: int = 70) -> List[Cell]:
    """Returns ordered list of cells along the baseline.

    left_baseline: column y=0, rows x=0..grid_size-1
    bottom_baseline: row x=0, cols y=0..grid_size-1
    """
    if region_kind == "left_baseline":
        return [(x, 0) for x in range(grid_size)]
    if region_kind == "bottom_baseline":
        return [(0, y) for y in range(grid_size)]
    raise ValueError(f"unsupported region_kind={region_kind!r}")


def compute_baseline_partition_lens(
    region_kind: RegionKind,
    state: BState,
    grid_size: int = 70,
) -> Tuple[List[int], List[int]]:
    """v1.1: partition 仅依赖 ghost_cells ∪ exterior_blocks (static).

    Returns (partition_lens, partition_offsets):
        e.g. left baseline length 70, ghost 占 (0, 30) 单格 →
             ([30, 39], [0, 31])
        (segment 0: cells 0..29 len 30, segment 1: cells 31..69 len 39)

    See cut_family_specs/06 §5a for the contract.
    """
    region_cells = compute_region_cells(region_kind, grid_size)

    # blocked = ghost ∪ exterior (static — 不含 cell_owner per Gemini r14 fix)
    blocked = set(state.ghost_cells) | set(state.exterior_blocks)

    partition_lens: List[int] = []
    partition_offsets: List[int] = []
    current_len = 0
    current_offset = 0

    for idx, cell in enumerate(region_cells):
        if cell in blocked:
            if current_len > 0:
                partition_lens.append(current_len)
                partition_offsets.append(current_offset)
            current_len = 0
            current_offset = idx + 1
        else:
            if current_len == 0:
                current_offset = idx
            current_len += 1

    if current_len > 0:
        partition_lens.append(current_len)
        partition_offsets.append(current_offset)

    return partition_lens, partition_offsets
