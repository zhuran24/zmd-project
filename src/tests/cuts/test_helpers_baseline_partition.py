"""Phase 1.0 P1.4 test — baseline partition lens helper (Family 6).

Coverage:
- Empty blocked → single segment full length
- Ghost cell in middle → split
- Exterior block at start → offset moves
- Ghost ∪ exterior intersection — union
- v1.1 critical: cell_owner 不影响 partition (Gemini r14 finding #2)
- Left vs bottom baseline
- Unsupported region kind → raise
"""
from __future__ import annotations

import pytest

from src.cuts.helpers.baseline_partition import (
    compute_baseline_partition_lens,
    compute_region_cells,
)
from src.cuts.lifecycle import BState, GroupState


def _state(
    ghost_cells: set = None,
    exterior_blocks: set = None,
    cell_owner: dict = None,
) -> BState:
    return BState(
        groups={"g": GroupState("g", demand=1, pose_domain=frozenset())},
        ghost_cells=frozenset(ghost_cells or set()),
        exterior_blocks=frozenset(exterior_blocks or set()),
        cell_owner=cell_owner or {},
    )


def test_compute_region_cells_left_baseline():
    cells = compute_region_cells("left_baseline", grid_size=5)
    assert cells == [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0)]


def test_compute_region_cells_bottom_baseline():
    cells = compute_region_cells("bottom_baseline", grid_size=5)
    assert cells == [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]


def test_compute_region_cells_unsupported_raises():
    with pytest.raises(ValueError, match="unsupported"):
        compute_region_cells("interior", grid_size=70)  # type: ignore[arg-type]


def test_empty_blocked_single_full_segment():
    state = _state()
    lens, offsets = compute_baseline_partition_lens("left_baseline", state, grid_size=70)
    assert lens == [70]
    assert offsets == [0]


def test_ghost_in_middle_splits_segment():
    """left baseline len=70, ghost 占 (30, 0) → 2 段."""
    state = _state(ghost_cells={(30, 0)})
    lens, offsets = compute_baseline_partition_lens("left_baseline", state, grid_size=70)
    assert lens == [30, 39]
    assert offsets == [0, 31]


def test_exterior_block_at_start_shifts_offset():
    state = _state(exterior_blocks={(0, 0)})
    lens, offsets = compute_baseline_partition_lens("left_baseline", state, grid_size=70)
    assert lens == [69]
    assert offsets == [1]


def test_ghost_and_exterior_union():
    state = _state(
        ghost_cells={(10, 0), (11, 0)},
        exterior_blocks={(30, 0)},
    )
    lens, offsets = compute_baseline_partition_lens("left_baseline", state, grid_size=70)
    # Segments: cells 0..9 (len 10), 12..29 (len 18), 31..69 (len 39)
    assert lens == [10, 18, 39]
    assert offsets == [0, 12, 31]


def test_cell_owner_does_not_affect_partition():
    """v1.1 critical fix (Gemini round 14 finding #2): partition 不看 cell_owner."""
    # cell_owner 在 (20, 0) (5, 0)..(8, 0) — 但 partition 不应分段
    state = _state(
        cell_owner={(5, 0): ("g", 0), (6, 0): ("g", 0), (20, 0): ("g", 1)},
    )
    lens, offsets = compute_baseline_partition_lens("left_baseline", state, grid_size=70)
    assert lens == [70]
    assert offsets == [0]


def test_adjacent_blocked_cells_no_empty_segment():
    """连续 blocked cells 不该产 0-len segment."""
    state = _state(ghost_cells={(10, 0), (11, 0), (12, 0)})
    lens, offsets = compute_baseline_partition_lens("left_baseline", state, grid_size=70)
    assert lens == [10, 57]
    assert offsets == [0, 13]


def test_all_blocked_returns_empty():
    blocks = {(x, 0) for x in range(70)}
    state = _state(ghost_cells=blocks)
    lens, offsets = compute_baseline_partition_lens("left_baseline", state, grid_size=70)
    assert lens == []
    assert offsets == []


def test_bottom_baseline():
    state = _state(ghost_cells={(0, 30)})
    lens, offsets = compute_baseline_partition_lens("bottom_baseline", state, grid_size=70)
    assert lens == [30, 39]
    assert offsets == [0, 31]
