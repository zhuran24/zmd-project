"""Dinic max-flow + min-cut on node-split graph for F2/F4 generators.

Phase 1.2 P1.2B-F2/F4 helper. F2 (cutset) uses Dinic max-flow / min-cut to
prove capacity insufficiency on a partition; F4 (component_reach) uses BFS
reachability + frontier separator extraction to prove disconnection.

Node-split convention (cell capacity model, default cap=1):
    Each cell v ∈ free_cells → two vertices: v_in, v_out.
    Internal edge: v_in --cap=cell_capacity--> v_out (single direction).
    Adjacency edge: u_out --cap=edge_capacity--> v_in for each 4-neighbor
        pair (u, v). Anti-parallel: also v_out --cap=edge_capacity--> u_in.
        Each direction is its own residual edge (NOT a single edge with
        rev_cap == fwd_cap — that would double-count).

Super-source / super-sink:
    F2 multi-commodity: SS → src_c_in (cap=demand), sink_c_out → ST (cap=demand).
    F4 single commodity: src→sink BFS reachability only, no max-flow.

Residual graph stored as adjacency list: adj[u] = list of (v, cap, rev_idx).
Adding edge (u→v, cap):
    adj[u].append((v, cap, len(adj[v])))
    adj[v].append((u, 0, len(adj[u]) - 1))    # reverse residual

Refs:
- docs/项目说明/08_phase_1_2_plan.md §P1.2B-F2/F4
- docs/项目说明/12_go_criteria.md §8.1.x acceptance C
- docs/research/p3_b_design_v2_20260521/cut_family_specs/02_cutset.md
- docs/research/p3_b_design_v2_20260521/cut_family_specs/04_component_reach.md
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Tuple

from src.cuts.lifecycle import Cell


# 4-connected neighbor offsets (N, S, E, W)
_NEIGHBOR_OFFSETS: Tuple[Tuple[int, int], ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))


def neighbors_4conn(cell: Cell, grid_size: int = 70) -> List[Cell]:
    """Return 4-connected neighbors of a cell that lie inside the grid."""
    x, y = cell
    result: List[Cell] = []
    for dx, dy in _NEIGHBOR_OFFSETS:
        nx, ny = x + dx, y + dy
        if 0 <= nx < grid_size and 0 <= ny < grid_size:
            result.append((nx, ny))
    return result


def bfs_component(
    start: Cell,
    free_cells: FrozenSet[Cell],
    grid_size: int = 70,
) -> FrozenSet[Cell]:
    """4-connected BFS over ``free_cells`` starting at ``start``.

    Returns the reachable component as a frozenset. Empty if ``start`` is
    not in ``free_cells``.
    """
    if start not in free_cells:
        return frozenset()
    visited: set[Cell] = {start}
    queue: deque[Cell] = deque([start])
    while queue:
        cell = queue.popleft()
        for nbr in neighbors_4conn(cell, grid_size):
            if nbr in free_cells and nbr not in visited:
                visited.add(nbr)
                queue.append(nbr)
    return frozenset(visited)


def extract_frontier_separator(
    src_component: FrozenSet[Cell],
    blocked_cells: FrozenSet[Cell],
    grid_size: int = 70,
) -> Tuple[Cell, ...]:
    """Return blocked cells 4-adjacent to ``src_component``.

    Per F4 spec §3 + validator (component_reach.py): separator_cells must be
    in ``cell_owner ∪ ghost_cells`` (NOT ``exterior_blocks``). Caller passes
    ``blocked_cells = state.cell_owner.keys() ∪ state.ghost_cells``.

    Returns deterministic canonical order (sorted by (x, y)) for cert hash
    stability.
    """
    separator: set[Cell] = set()
    for cell in src_component:
        for nbr in neighbors_4conn(cell, grid_size):
            if nbr in blocked_cells and nbr not in src_component:
                separator.add(nbr)
    return tuple(sorted(separator))


# ============================================================================
# Dinic max-flow on node-split graph
# ============================================================================


@dataclass
class _DinicGraph:
    """Mutable residual graph for one Dinic solve.

    Vertex layout for cells: v_in = 2 * cell_idx, v_out = 2 * cell_idx + 1.
    Special vertices: super_source = 2*N, super_sink = 2*N + 1.
    """

    n_cells: int
    cell_to_idx: Dict[Cell, int]
    idx_to_cell: List[Cell]
    super_source: int
    super_sink: int
    # adj[u] = list of [v, residual_cap, rev_idx_in_adj_v]
    adj: List[List[List[int]]]
    # Original edges for cut extraction: (u, v, original_cap)
    forward_edges: List[Tuple[int, int, int]]

    def add_edge(self, u: int, v: int, cap: int) -> None:
        """Add directed edge u→v with capacity ``cap`` + reverse residual.

        Note: bidirectional adjacency requires two add_edge calls
        (u→v + v→u), each with their own residual.
        """
        rev_in_v = len(self.adj[v])
        rev_in_u = len(self.adj[u])
        self.adj[u].append([v, cap, rev_in_v])
        self.adj[v].append([u, 0, rev_in_u])
        self.forward_edges.append((u, v, cap))


def _build_node_split_graph(
    free_cells: FrozenSet[Cell],
    sources: List[Tuple[Cell, int]],  # (src_cell, demand)
    sinks: List[Tuple[Cell, int]],
    *,
    cell_capacity: int = 1,
    edge_capacity: int = 1,
    grid_size: int = 70,
) -> _DinicGraph:
    """Build node-split graph with super-source / super-sink.

    Each free cell gets v_in, v_out with internal cap = cell_capacity.
    Each 4-adjacent free cell pair gets two anti-parallel edges
    (u_out → v_in, v_out → u_in) each with cap = edge_capacity.
    """
    cell_list = sorted(free_cells)
    cell_to_idx = {cell: i for i, cell in enumerate(cell_list)}
    n_cells = len(cell_list)
    super_source = 2 * n_cells
    super_sink = 2 * n_cells + 1
    n_vertices = super_sink + 1

    graph = _DinicGraph(
        n_cells=n_cells,
        cell_to_idx=cell_to_idx,
        idx_to_cell=cell_list,
        super_source=super_source,
        super_sink=super_sink,
        adj=[[] for _ in range(n_vertices)],
        forward_edges=[],
    )

    # Internal node-split edges: v_in → v_out
    for idx in range(n_cells):
        v_in = 2 * idx
        v_out = 2 * idx + 1
        graph.add_edge(v_in, v_out, cell_capacity)

    # Adjacency edges: for each unordered free-pair, add both directions
    seen_pairs: set[Tuple[int, int]] = set()
    for cell, idx in cell_to_idx.items():
        for nbr in neighbors_4conn(cell, grid_size):
            nbr_idx = cell_to_idx.get(nbr)
            if nbr_idx is None:
                continue
            key = (min(idx, nbr_idx), max(idx, nbr_idx))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            # u_out → v_in
            graph.add_edge(2 * idx + 1, 2 * nbr_idx, edge_capacity)
            # v_out → u_in (anti-parallel)
            graph.add_edge(2 * nbr_idx + 1, 2 * idx, edge_capacity)

    # Super-source → src.v_in (demand cap)
    for src_cell, demand in sources:
        src_idx = cell_to_idx.get(src_cell)
        if src_idx is None:
            raise ValueError(f"src {src_cell} not in free_cells")
        graph.add_edge(super_source, 2 * src_idx, demand)

    # sink.v_out → super-sink (demand cap)
    for sink_cell, demand in sinks:
        sink_idx = cell_to_idx.get(sink_cell)
        if sink_idx is None:
            raise ValueError(f"sink {sink_cell} not in free_cells")
        graph.add_edge(2 * sink_idx + 1, super_sink, demand)

    return graph


def _bfs_level(graph: _DinicGraph) -> List[int]:
    """BFS level graph from super_source. Returns level[u] = depth or -1."""
    n = len(graph.adj)
    level = [-1] * n
    level[graph.super_source] = 0
    queue: deque[int] = deque([graph.super_source])
    while queue:
        u = queue.popleft()
        for edge in graph.adj[u]:
            v, cap, _rev = edge
            if cap > 0 and level[v] == -1:
                level[v] = level[u] + 1
                queue.append(v)
    return level


def _dfs_blocking_flow(
    graph: _DinicGraph,
    u: int,
    pushed: int,
    level: List[int],
    iter_ptr: List[int],
) -> int:
    """Recursive DFS to push blocking flow. Returns flow pushed."""
    if u == graph.super_sink:
        return pushed
    while iter_ptr[u] < len(graph.adj[u]):
        edge = graph.adj[u][iter_ptr[u]]
        v, cap, rev = edge
        if cap > 0 and level[v] == level[u] + 1:
            d = _dfs_blocking_flow(graph, v, min(pushed, cap), level, iter_ptr)
            if d > 0:
                edge[1] -= d
                graph.adj[v][rev][1] += d
                return d
        iter_ptr[u] += 1
    return 0


def _dinic_max_flow(graph: _DinicGraph) -> int:
    """Run Dinic to completion. Returns total max flow."""
    flow = 0
    while True:
        level = _bfs_level(graph)
        if level[graph.super_sink] == -1:
            return flow
        iter_ptr = [0] * len(graph.adj)
        while True:
            pushed = _dfs_blocking_flow(graph, graph.super_source, 10**9, level, iter_ptr)
            if pushed == 0:
                break
            flow += pushed


def _min_cut_reachable(graph: _DinicGraph) -> FrozenSet[int]:
    """BFS from super_source on residual graph. Reachable vertex set."""
    visited: set[int] = {graph.super_source}
    queue: deque[int] = deque([graph.super_source])
    while queue:
        u = queue.popleft()
        for edge in graph.adj[u]:
            v, cap, _rev = edge
            if cap > 0 and v not in visited:
                visited.add(v)
                queue.append(v)
    return frozenset(visited)


@dataclass(frozen=True)
class MaxFlowMinCutResult:
    """Result of a Dinic solve on a node-split graph.

    Invariants (Menger / max-flow min-cut theorem):
    - ``max_flow_value == cut_capacity`` (sum of original caps on cut edges)
    - ``cut_cell_edges`` are adjacency cuts (cell_u, cell_v) — internal
      node-split edges + super-source/sink links are filtered out
    - ``side_a`` (free_cells whose v_in OR v_out reachable from super_source)
    - ``side_b`` = free_cells \\ side_a (sink side)
    """

    max_flow_value: int
    cut_cell_edges: Tuple[Tuple[Cell, Cell], ...]  # canonical (smaller, larger)
    cut_capacity: int
    side_a: FrozenSet[Cell]
    side_b: FrozenSet[Cell]


def dinic_node_split_min_cut(
    free_cells: FrozenSet[Cell],
    sources: List[Tuple[Cell, int]],
    sinks: List[Tuple[Cell, int]],
    *,
    cell_capacity: int = 1,
    edge_capacity: int = 1,
    grid_size: int = 70,
) -> MaxFlowMinCutResult:
    """Run Dinic + extract min-cut on a node-split grid graph.

    Returns ``MaxFlowMinCutResult`` carrying max_flow + cut edges +
    partition. Caller is responsible for verifying ``side_a`` ∪ ``side_b``
    is enclosed (no escape to free_cells outside the patch) before
    constructing a cut cert — per F2 validator ``_has_patch_escape``.
    """
    if not sources or not sinks:
        return MaxFlowMinCutResult(
            max_flow_value=0,
            cut_cell_edges=(),
            cut_capacity=0,
            side_a=frozenset(),
            side_b=frozenset(),
        )
    graph = _build_node_split_graph(
        free_cells,
        sources,
        sinks,
        cell_capacity=cell_capacity,
        edge_capacity=edge_capacity,
        grid_size=grid_size,
    )
    max_flow = _dinic_max_flow(graph)
    reachable = _min_cut_reachable(graph)
    n_cells = graph.n_cells
    super_min = 2 * n_cells

    # Extract cut edges. Forward edges where u reachable, v not reachable.
    # Three edge kinds emit:
    # - super_source → src.v_in (skip; not adjacency)
    # - sink.v_out → super_sink (skip)
    # - v_in → v_out (internal node-split; skip — represented as same-cell)
    # - u_out → v_in (adjacency between distinct cells; KEEP, canonicalize)
    cell_cut_edges_set: set[Tuple[Cell, Cell]] = set()
    cut_capacity = 0
    for (u, v, cap) in graph.forward_edges:
        if u not in reachable or v in reachable:
            continue
        cut_capacity += cap
        if u >= super_min or v >= super_min:
            continue  # super-source/sink link, not adjacency
        u_idx = u // 2
        v_idx = v // 2
        if u_idx == v_idx:
            continue  # internal v_in → v_out, not adjacency
        cell_u = graph.idx_to_cell[u_idx]
        cell_v = graph.idx_to_cell[v_idx]
        pair = (cell_u, cell_v) if cell_u <= cell_v else (cell_v, cell_u)
        cell_cut_edges_set.add(pair)

    side_a_cells: set[Cell] = set()
    side_b_cells: set[Cell] = set()
    for cell, idx in graph.cell_to_idx.items():
        v_in = 2 * idx
        v_out = 2 * idx + 1
        if v_in in reachable or v_out in reachable:
            side_a_cells.add(cell)
        else:
            side_b_cells.add(cell)

    return MaxFlowMinCutResult(
        max_flow_value=max_flow,
        cut_cell_edges=tuple(sorted(cell_cut_edges_set)),
        cut_capacity=cut_capacity,
        side_a=frozenset(side_a_cells),
        side_b=frozenset(side_b_cells),
    )
