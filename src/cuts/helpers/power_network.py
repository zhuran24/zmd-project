"""Family 8 power_grid_reach helpers — power network construction + BFS component.

Per cut_family_specs/08_power_grid_reach.md v1.1 §5a:
- ``build_power_network(poles, pc_cell, pole_radius, ghost_rect)`` →
  ``PowerGraph(V, E)`` where E_jump connects poles within radius and not
  blocked by ghost AABB (Liang-Barsky strict intersection — v1.0 中心点
  shortcut critical FN bug 已修).
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
from typing import Iterable, Optional, Set, Tuple

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
    vertices: frozenset = field(default_factory=frozenset)
    edges: frozenset = field(default_factory=frozenset)


def _canonical_edge(p1: Pole, p2: Pole) -> Edge:
    return (p1, p2) if p1 <= p2 else (p2, p1)


def _euclidean(p1: Pole, p2: Pole) -> float:
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def build_power_network(
    poles: Iterable[Pole],
    pole_radius: float,
    *,
    pc_cell: Optional[Pole] = None,
    ghost_rect: Optional[Tuple[int, int, int, int]] = None,
) -> PowerGraph:
    """Build undirected jump graph among poles + protocol_core.

    Edge (p1, p2) iff:
    - euclidean_distance(p1, p2) ≤ pole_radius (jump range), AND
    - line segment p1→p2 not intersecting ghost_rect AABB (Liang-Barsky)
      — ghost None means no obstacle, all in-range pairs connected.
    """
    pole_set = set(poles)
    if pc_cell is not None:
        pole_set.add(pc_cell)
    vertices = frozenset(pole_set)
    pole_list = sorted(pole_set)

    ghost_aabb = cell_aabb_from_rect(ghost_rect) if ghost_rect is not None else None

    edges: Set[Edge] = set()
    n = len(pole_list)
    for i in range(n):
        for j in range(i + 1, n):
            p1, p2 = pole_list[i], pole_list[j]
            if _euclidean(p1, p2) > pole_radius:
                continue
            if ghost_aabb is not None and segment_intersects_aabb(
                (float(p1[0]), float(p1[1])),
                (float(p2[0]), float(p2[1])),
                ghost_aabb,
            ):
                continue
            edges.add(_canonical_edge(p1, p2))

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
