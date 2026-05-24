"""Phase 1.0 P1.4 test — power network construction + bfs_component (Family 8).

Coverage:
- No-ghost: in-range poles all connected
- Ghost blocks jump line: edge dropped (Liang-Barsky)
- Out-of-range poles: no edge
- bfs_component reach / unreachable
- protocol_core anchor inclusion
- Empty pole set
- Edge canonicalization (no dup (p1,p2) + (p2,p1))
"""
from __future__ import annotations

from src.cuts.helpers.power_network import (
    PowerGraph,
    bfs_component,
    build_power_network,
)


# ============================================================================
# build_power_network
# ============================================================================

def test_build_no_ghost_in_range_all_connected():
    """3 poles at (0,0)(5,0)(10,0), radius=5 → (0,0)-(5,0) and (5,0)-(10,0) connect."""
    poles = [(0, 0), (5, 0), (10, 0)]
    graph = build_power_network(poles, pole_radius=5.0)
    assert (0, 0) in graph.vertices
    assert (5, 0) in graph.vertices
    assert (10, 0) in graph.vertices
    # edges (canonical: smaller first)
    assert ((0, 0), (5, 0)) in graph.edges
    assert ((5, 0), (10, 0)) in graph.edges
    # (0,0)-(10,0) distance 10 > 5 → no edge
    assert ((0, 0), (10, 0)) not in graph.edges


def test_build_out_of_range_no_edge():
    poles = [(0, 0), (10, 0)]
    graph = build_power_network(poles, pole_radius=5.0)
    assert len(graph.edges) == 0


def test_build_includes_protocol_core_single_cell():
    """Backwards-compat: a single-cell ``pc_cells`` still works (round 1 fix
    changed API from ``pc_cell`` → ``pc_cells: Iterable`` so single-cell
    callers wrap with a 1-tuple)."""
    poles = [(0, 0)]
    graph = build_power_network(poles, pole_radius=5.0, pc_cells=[(2, 2)])
    assert (0, 0) in graph.vertices
    assert (2, 2) in graph.vertices
    # distance sqrt(8) ≈ 2.83 < 5
    assert ((0, 0), (2, 2)) in graph.edges


def test_build_protocol_core_multi_cell_autoconnect():
    """Gemini F8 round 1 Finding #2: protocol_core 9×9; full footprint
    auto-pairwise-connected (one building), pole connects iff *any* core
    cell within radius."""
    poles = [(20, 0)]
    pc_cells = [(0, 0), (0, 1), (1, 0), (1, 1)]  # mock 2×2 core for test
    graph = build_power_network(poles, pole_radius=5.0, pc_cells=pc_cells)
    # all pc cells are vertices
    for c in pc_cells:
        assert c in graph.vertices
    # pc internal: every pair must be edge (auto-connect, 6 pairs for 4 cells)
    assert ((0, 0), (0, 1)) in graph.edges
    assert ((0, 0), (1, 0)) in graph.edges
    assert ((0, 0), (1, 1)) in graph.edges
    assert ((0, 1), (1, 0)) in graph.edges
    assert ((0, 1), (1, 1)) in graph.edges
    assert ((1, 0), (1, 1)) in graph.edges
    # pole far from core → no pole↔core edge
    assert all(((20, 0), c) not in graph.edges and (c, (20, 0)) not in graph.edges for c in pc_cells)


def test_build_protocol_core_pole_connects_via_any_core_cell():
    """Round 1 Finding #2: pole within radius of *one* pc cell connects to
    the entire core via the auto-connected internal edges. Previously
    distance was measured only to the anchor, missing poles near far cells."""
    # 9×9 core anchored at (0,0): far cell (8,8). pole at (12,12) is
    # distance sqrt(32) ≈ 5.66 from (8,8) — within radius 6, but
    # sqrt(288) ≈ 16.97 from (0,0) — way over the pre-fix single-anchor
    # interpretation. With multi-cell pc, this MUST connect.
    pc_cells = [(x, y) for x in range(9) for y in range(9)]
    poles = [(12, 12)]
    graph = build_power_network(poles, pole_radius=6.0, pc_cells=pc_cells)
    # bfs from anchor reaches pole
    reach = bfs_component(graph, (0, 0))
    assert (12, 12) in reach


def test_build_protocol_core_dedup_overlap_with_pole():
    """If a pole cell coincides with a pc cell, pc takes priority (the cell
    is a single vertex, not double-counted, and falls under pc rules)."""
    poles = [(5, 5), (10, 10)]
    pc_cells = [(5, 5)]
    graph = build_power_network(poles, pole_radius=10.0, pc_cells=pc_cells)
    # only 2 vertices ((5,5) once, (10,10) once)
    assert len(graph.vertices) == 2
    assert (5, 5) in graph.vertices
    assert (10, 10) in graph.vertices


def test_build_ghost_blocks_jump():
    """ghost rect (3,0)-(5,0) blocks jump (0,0) → (10,0) — but distance 10 > 5
    so not in range anyway. Use closer poles + ghost in middle."""
    poles = [(0, 0), (8, 0)]
    # ghost AABB (3,0)-(5,1) — at y=0 covers from x=3 to x=5
    graph = build_power_network(
        poles, pole_radius=10.0, ghost_rect=(3, 0, 2, 1)
    )
    # segment (0,0)→(8,0) intersects ghost AABB → no edge
    assert len(graph.edges) == 0


def test_build_ghost_outside_path_does_not_block():
    """ghost not on line → jump kept."""
    poles = [(0, 0), (8, 0)]
    # ghost AABB at y=5, far from y=0 line
    graph = build_power_network(
        poles, pole_radius=10.0, ghost_rect=(3, 5, 2, 1)
    )
    assert ((0, 0), (8, 0)) in graph.edges


def test_build_empty_poles():
    graph = build_power_network([], pole_radius=5.0)
    assert len(graph.vertices) == 0
    assert len(graph.edges) == 0


# ============================================================================
# bfs_component
# ============================================================================

def test_bfs_component_full_reach():
    poles = [(0, 0), (5, 0), (10, 0)]
    graph = build_power_network(poles, pole_radius=5.0)
    reach = bfs_component(graph, (0, 0))
    assert reach == {(0, 0), (5, 0), (10, 0)}


def test_bfs_component_disconnected():
    """2 cluster: {(0,0),(2,0)} and {(20,0),(22,0)} radius=3 → 2 components."""
    poles = [(0, 0), (2, 0), (20, 0), (22, 0)]
    graph = build_power_network(poles, pole_radius=3.0)
    reach_first = bfs_component(graph, (0, 0))
    assert reach_first == {(0, 0), (2, 0)}
    reach_second = bfs_component(graph, (20, 0))
    assert reach_second == {(20, 0), (22, 0)}


def test_bfs_component_start_not_in_graph():
    poles = [(0, 0)]
    graph = build_power_network(poles, pole_radius=5.0)
    assert bfs_component(graph, (99, 99)) == set()


def test_bfs_component_isolated_pole():
    poles = [(0, 0), (100, 100)]  # far apart
    graph = build_power_network(poles, pole_radius=5.0)
    assert bfs_component(graph, (0, 0)) == {(0, 0)}
    assert bfs_component(graph, (100, 100)) == {(100, 100)}


def test_edge_canonicalization_no_duplicate():
    """Edge (p1, p2) 跟 (p2, p1) 必须只存一次."""
    poles = [(0, 0), (5, 0)]
    graph = build_power_network(poles, pole_radius=10.0)
    assert len(graph.edges) == 1


# ============================================================================
# PowerGraph dataclass
# ============================================================================

def test_power_graph_default_empty():
    g = PowerGraph()
    assert g.vertices == frozenset()
    assert g.edges == frozenset()
