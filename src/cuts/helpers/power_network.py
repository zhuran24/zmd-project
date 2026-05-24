"""Family 8 power_grid_reach helpers — power network construction + BFS component.

Per cut_family_specs/08_power_grid_reach.md v1.1 §5a:
- ``build_power_network(poles, pole_radius, *, pc_cells, ghost_rect)`` →
  ``PowerGraph(V, E)`` where E_jump connects poles within radius and not
  blocked by ghost AABB (Liang-Barsky strict intersection — v1.0 中心点
  shortcut critical FN bug 已修). ``pc_cells`` is the protocol_core multi-cell
  footprint (Gemini F8 round 1 Finding #2: 9×9 facility, not a single point).
  Internal pc_cell pairs are auto-connected (one building).
- ``bfs_component(graph, start)`` → set of pole cells reachable from start.

Phase 1.0 P1.4 scope:
- Pure data-structure helper (no oracle wiring — Phase 1.2 P1.14 接 Family 8
  validator + ``compute_cover_set`` for full F8 cut generation).

Refs:
- docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md v1.1
- src/cuts/helpers/ghost_geometry.py (Liang-Barsky)
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import FrozenSet, Iterable, Optional, Set, Tuple

from src.cuts.helpers.ghost_geometry import (
    cell_aabb_from_rect,
    segment_intersects_aabb,
)


Pole = Tuple[int, int]
Edge = Tuple[Pole, Pole]


@dataclass(frozen=True)
class PowerGraph:
    """Undirected graph of pole-pole jumps + protocol_core anchor.

    ``vertices`` includes the protocol_core cell (if provided) — F8 uses it as
    the reach origin for connectivity check.
    ``edges`` is an undirected set; ``(p1, p2)`` and ``(p2, p1)`` stored as
    canonicalized tuple (smaller first) to dedupe.
    """
    vertices: FrozenSet[Pole] = field(default_factory=frozenset)
    edges: FrozenSet[Edge] = field(default_factory=frozenset)


def _canonical_edge(p1: Pole, p2: Pole) -> Edge:
    return (p1, p2) if p1 <= p2 else (p2, p1)


def _euclidean(p1: Pole, p2: Pole) -> float:
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


# canonical_rules.facility_templates.power_pole.dimensions.{w,h} = 2.
_POLE_SIZE: int = 2


def _footprint_cells(anchor: Pole, size: int) -> Tuple[Pole, ...]:
    """Cells occupied by a square footprint anchored at ``anchor``."""
    return tuple(
        (anchor[0] + dx, anchor[1] + dy) for dx in range(size) for dy in range(size)
    )


def _can_jump_via_cells(
    cells1: Tuple[Pole, ...],
    cells2: Tuple[Pole, ...],
    pole_radius: float,
    ghost_aabb: Optional[Tuple[float, float, float, float]],
) -> bool:
    """Jump iff ANY cell pair (c1 ∈ cells1, c2 ∈ cells2) satisfies BOTH
    (a) euclidean distance ≤ ``pole_radius`` AND (b) the segment between
    cell centers does not intersect the ghost AABB.

    Gemini F8 round 2 Finding #1: distance must be cell-to-cell min (not
    anchor-to-anchor) to stay consistent with ``compute_cover_set``.
    Gemini F8 round 2 Finding #2: segment endpoints must be cell centers
    (anchor + 0.5), not raw anchor coords.

    Gemini F8 round 3 Finding #1 (CRITICAL): scanning ONLY the closest
    pair drops legitimate edges when the closest pair's segment crosses
    the ghost but another in-range pair has unblocked line-of-sight.
    Power can physically jump along *any* viable cell-pair path, so this
    function must scan all in-range pairs and accept the first unblocked
    one. This is still bounded — 2×2 vs 1×1 footprints yield at most 16
    pairs per call, and the outer ``_pole_*_edges`` early-reject filters
    far pairs before reaching this function.
    """
    r_sq = pole_radius * pole_radius
    for c1 in cells1:
        for c2 in cells2:
            dx = c1[0] - c2[0]
            dy = c1[1] - c2[1]
            d_sq = dx * dx + dy * dy
            if d_sq > r_sq:
                continue
            if ghost_aabb is None:
                return True
            if not segment_intersects_aabb(
                (float(c1[0]) + 0.5, float(c1[1]) + 0.5),
                (float(c2[0]) + 0.5, float(c2[1]) + 0.5),
                ghost_aabb,
            ):
                return True
    return False


def _pole_pole_edges(
    pole_list: list[Pole],
    pole_radius: float,
    ghost_aabb: Optional[Tuple[float, float, float, float]],
) -> Iterable[Edge]:
    """Pole-pole edges with anchor-distance early reject for hot-path speed.

    Bound: min cell-to-cell ≥ anchor_dist - 2·√2 (each anchor at most √2
    from any cell of its 2×2 footprint), so anchor_dist > pole_radius +
    2·√2 ⇒ no cell pair can be within pole_radius. This rejects ~99% of
    far pairs on a 70×70 grid with R=5 (cutoff ≈ 7.83), dropping
    ``build_power_network`` from minutes to seconds (R2-Gap E).
    """
    n = len(pole_list)
    if n == 0:
        return
    footprints = [_footprint_cells(p, _POLE_SIZE) for p in pole_list]
    cutoff_sq = (pole_radius + 2.0 * math.sqrt(2.0)) ** 2
    for i in range(n):
        ax, ay = pole_list[i]
        for j in range(i + 1, n):
            bx, by = pole_list[j]
            dsq = (ax - bx) ** 2 + (ay - by) ** 2
            if dsq > cutoff_sq:
                continue
            if _can_jump_via_cells(
                footprints[i], footprints[j], pole_radius, ghost_aabb
            ):
                yield _canonical_edge(pole_list[i], pole_list[j])


def _pc_internal_edges(pc_list: list[Pole]) -> Iterable[Edge]:
    """protocol_core internal: all pc cells form a single supernode.

    Always mutually connected — ghost cannot pass through the core's
    footprint since master_solution disallows ghost overlap with placed
    facilities.
    """
    m = len(pc_list)
    for i in range(m):
        for j in range(i + 1, m):
            yield _canonical_edge(pc_list[i], pc_list[j])


def _pole_pc_edges(
    pole_list: list[Pole],
    pc_list: list[Pole],
    pole_radius: float,
    ghost_aabb: Optional[Tuple[float, float, float, float]],
) -> Iterable[Edge]:
    """Pole↔pc edges with anchor-distance early reject.

    Bound: min cell-to-cell ≥ anchor_dist - √2 (pole footprint at most √2
    away from its anchor; pc cell is 1×1). Cutoff: anchor_dist ≤ R + √2.
    Same R2-Gap E optimization rationale as ``_pole_pole_edges``.
    """
    if not pole_list or not pc_list:
        return
    pole_footprints = [_footprint_cells(p, _POLE_SIZE) for p in pole_list]
    cutoff_sq = (pole_radius + math.sqrt(2.0)) ** 2
    for p, cells_p in zip(pole_list, pole_footprints):
        px, py = p
        for c in pc_list:
            cx, cy = c
            dsq = (px - cx) ** 2 + (py - cy) ** 2
            if dsq > cutoff_sq:
                continue
            if _can_jump_via_cells(cells_p, (c,), pole_radius, ghost_aabb):
                yield _canonical_edge(p, c)


def build_power_network(
    poles: Iterable[Pole],
    pole_radius: float,
    *,
    pc_cells: Optional[Iterable[Pole]] = None,
    ghost_rect: Optional[Tuple[int, int, int, int]] = None,
) -> PowerGraph:
    """Build undirected jump graph among poles + protocol_core footprint.

    ``poles`` are the candidate pole anchor cells on the current free mask
    (Gemini F8 round 1 Finding #1: callers must enumerate the full free-mask
    anchor set — passing only ``CoverSet`` produces 100% false positives
    because the graph then lacks the intermediate poles that span the grid).

    ``pc_cells`` is the protocol_core's full footprint (Gemini F8 round 1
    Finding #2: protocol_core is a 9×9 facility, not a single point — using
    only the lex anchor makes pole-to-core distance overshoot the radius for
    poles near the far side of the core). The footprint cells are added as
    graph vertices, pairwise zero-distance auto-connected (core is one
    building), and the pole↔core edge fires when *any* pole-to-pc_cell pair
    satisfies (distance ≤ ``pole_radius``) AND (segment does not intersect
    ghost AABB).

    Edge (p1, p2) for two poles:
    - euclidean_distance(p1, p2) ≤ pole_radius (jump range), AND
    - line segment p1→p2 not intersecting ghost_rect AABB (Liang-Barsky)
      — ghost None means no obstacle, all in-range pairs connected.
    """
    pole_set = set(poles)
    pc_set: Set[Pole] = set(pc_cells) if pc_cells is not None else set()
    # Gemini F8 round 2 Finding #3: comment said "pc cells take priority,
    # drop overlapping pole copy" but the prior ``pc_set -= pole_set`` did
    # the opposite. The pc footprint is a placed facility, so the pole-as-
    # placeable interpretation is the spurious one — drop overlaps from
    # ``pole_set``. In practice ``free_cells`` excludes pc cells so overlap
    # never occurs, but the API contract now matches the comment.
    pole_set -= pc_set
    vertices = frozenset(pole_set | pc_set)
    pole_list = sorted(pole_set)
    pc_list = sorted(pc_set)

    ghost_aabb = cell_aabb_from_rect(ghost_rect) if ghost_rect is not None else None

    edges: Set[Edge] = set()
    edges.update(_pole_pole_edges(pole_list, pole_radius, ghost_aabb))
    edges.update(_pc_internal_edges(pc_list))
    edges.update(_pole_pc_edges(pole_list, pc_list, pole_radius, ghost_aabb))
    return PowerGraph(vertices=vertices, edges=frozenset(edges))


def bfs_component(graph: PowerGraph, start: Pole) -> Set[Pole]:
    """Return set of poles reachable from ``start`` via graph edges.

    Returns empty set if ``start`` not in graph.vertices.
    """
    if start not in graph.vertices:
        return set()

    adj: dict[Pole, Set[Pole]] = {v: set() for v in graph.vertices}
    for p1, p2 in graph.edges:
        adj[p1].add(p2)
        adj[p2].add(p1)

    visited: Set[Pole] = {start}
    q: deque[Pole] = deque([start])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in visited:
                visited.add(v)
                q.append(v)
    return visited
