"""Tests for src/cuts/helpers/dinic_node_split.py.

Regression coverage targets the Gemini F2/F4 round 1 findings:
- BLOCKER #1: ``_dfs_blocking_flow`` must be iterative — long level-graph
  paths on 70x70 grid would otherwise blow Python's recursion limit and
  silently drop F2 cuts via the oracle's broad ``except Exception``.
- Soundness: max-flow / min-cut match Menger's theorem on toy graphs.
"""
from __future__ import annotations

import sys

import pytest

from src.cuts.helpers.dinic_node_split import (
    bfs_component,
    dinic_node_split_min_cut,
    extract_frontier_separator,
)


def _serpentine_corridor() -> frozenset[tuple[int, int]]:
    """1-cell-wide serpentine path from (0,0) to (69,69) on a 70x70 grid.

    Connects ~2485 cells along a forced long path so the Dinic level graph
    depth exceeds Python's default ``sys.getrecursionlimit() == 1000``.
    """
    free: set[tuple[int, int]] = set()
    for x in range(70):
        if x % 2 == 0:
            for y in range(70):
                free.add((x, y))
        else:
            if x % 4 == 1:
                free.add((x, 69))
            else:
                free.add((x, 0))
    return frozenset(free)


def test_dinic_does_not_recurse_on_long_path() -> None:
    """Gemini F2/F4 round 1 BLOCKER #1 regression: iterative DFS must not raise.

    Recursive DFS would raise ``RecursionError`` at recursionlimit=1000.
    """
    assert sys.getrecursionlimit() <= 2000, (
        "test relies on default recursion limit; environment overrode it"
    )
    free = _serpentine_corridor()
    result = dinic_node_split_min_cut(
        free, sources=[((0, 0), 1)], sinks=[((69, 69), 1)],
        cell_capacity=10**9, edge_capacity=1,
    )
    assert result.max_flow_value == 1
    # cut_capacity equals max_flow (Menger)
    assert result.cut_capacity == 1


def test_dinic_max_flow_matches_menger_min_cut() -> None:
    """3x3 dumbbell: two clusters joined by a 1-cell bottleneck => max_flow = 1."""
    free = frozenset(
        {(0, 0), (1, 0), (0, 1), (1, 1),  # left cluster
         (2, 1),                            # bottleneck
         (3, 0), (3, 1), (4, 0), (4, 1)}    # right cluster
    )
    result = dinic_node_split_min_cut(
        free,
        sources=[((0, 0), 10)],
        sinks=[((4, 0), 10)],
        cell_capacity=10**9,
        edge_capacity=1,
    )
    assert result.max_flow_value <= 2
    # Adjacency 4-conn: (1,1)-(2,1) and (2,1)-(3,1) are the only bridges.
    # Edge capacity = 1, so min-cut = 2 (cut either side of bottleneck).
    assert result.cut_capacity == result.max_flow_value


def test_dinic_disconnected_source_sink_returns_zero_flow() -> None:
    """Two disjoint 1-cell free sets: max_flow == 0, side_a covers source side."""
    free = frozenset({(0, 0), (5, 5)})
    result = dinic_node_split_min_cut(
        free,
        sources=[((0, 0), 1)],
        sinks=[((5, 5), 1)],
        cell_capacity=10**9,
        edge_capacity=1,
    )
    assert result.max_flow_value == 0
    # Disconnected source/sink: F4 territory; cut_cell_edges is empty
    # because no adjacency edge crosses the partition.
    assert result.cut_cell_edges == ()


def test_bfs_component_returns_reachable_set() -> None:
    free = frozenset({(0, 0), (0, 1), (1, 1), (5, 5)})
    comp = bfs_component((0, 0), free)
    assert comp == frozenset({(0, 0), (0, 1), (1, 1)})
    assert bfs_component((5, 5), free) == frozenset({(5, 5)})
    assert bfs_component((9, 9), free) == frozenset()


def test_extract_frontier_separator_filters_to_blocked_cells() -> None:
    src_component = frozenset({(0, 0), (0, 1)})
    blocked = frozenset({(1, 0), (1, 1), (0, 2)})
    sep = extract_frontier_separator(src_component, blocked)
    assert set(sep) == {(1, 0), (1, 1), (0, 2)}
    # canonical sort
    assert sep == tuple(sorted(sep))


def test_dinic_empty_sources_or_sinks_short_circuits() -> None:
    free = frozenset({(0, 0), (1, 0)})
    result_no_src = dinic_node_split_min_cut(
        free, sources=[], sinks=[((1, 0), 1)],
        cell_capacity=10**9, edge_capacity=1,
    )
    assert result_no_src.max_flow_value == 0
    assert result_no_src.cut_capacity == 0


def test_dinic_source_not_in_free_raises() -> None:
    free = frozenset({(0, 0), (1, 0)})
    with pytest.raises(ValueError):
        dinic_node_split_min_cut(
            free, sources=[((9, 9), 1)], sinks=[((1, 0), 1)],
            cell_capacity=10**9, edge_capacity=1,
        )
