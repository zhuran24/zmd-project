"""Liang-Barsky line-AABB intersection for Family 8 power_grid_reach.

Family 8 power_grid_reach (cut_family_specs/08_power_grid_reach.md v1.1) tests
whether a candidate pole→facility line segment is blocked by the ghost rect.
Liang-Barsky AABB clip is the standard algorithm — robust, O(1), no FP edge
cases when carefully implemented.

Phase 1.0 P1.4 scope:
- ``segment_intersects_aabb(p0, p1, aabb)`` → bool
- ``segment_aabb_intersection_t(p0, p1, aabb)`` → Optional[(t_enter, t_exit)]
  in [0, 1] parametric on segment (None if no intersection)

Edge cases handled:
- Degenerate segment (p0 == p1): treat as point-in-AABB test
- Segment touching AABB boundary (t_enter == t_exit): True (touch counts)
- Axis-aligned segment along AABB edge: True
- Both endpoints inside AABB: True (full enclosure)

Refs:
- docs/research/p3_b_design_v2_20260521/cut_family_specs/08_power_grid_reach.md v1.1
- https://en.wikipedia.org/wiki/Liang%E2%80%93Barsky_algorithm
"""
from __future__ import annotations

from typing import Optional, Tuple


# Cell grid coordinates (matches src.cuts.lifecycle.Cell).
Point = Tuple[float, float]
AABB = Tuple[float, float, float, float]  # (xmin, ymin, xmax, ymax)


def _aabb_well_formed(aabb: AABB) -> bool:
    xmin, ymin, xmax, ymax = aabb
    return xmin <= xmax and ymin <= ymax


def segment_aabb_intersection_t(
    p0: Point, p1: Point, aabb: AABB
) -> Optional[Tuple[float, float]]:
    """Liang-Barsky 参数化 line-AABB clip.

    Returns (t_enter, t_exit) ∈ [0, 1] such that segment param t in
    [t_enter, t_exit] lies inside the AABB; None if no intersection.

    For touch (t_enter == t_exit) returns the touching t — caller decides
    whether tangent counts as intersection.
    """
    if not _aabb_well_formed(aabb):
        raise ValueError(f"AABB ill-formed: {aabb}")

    x0, y0 = p0
    x1, y1 = p1
    xmin, ymin, xmax, ymax = aabb
    dx = x1 - x0
    dy = y1 - y0

    # Degenerate segment: point-in-AABB
    if dx == 0 and dy == 0:
        if xmin <= x0 <= xmax and ymin <= y0 <= ymax:
            return (0.0, 0.0)
        return None

    t_enter = 0.0
    t_exit = 1.0

    # 4 boundary planes: p * t + q == 0 form; p = -dx (or +dx) etc.
    p = (-dx, dx, -dy, dy)
    q = (x0 - xmin, xmax - x0, y0 - ymin, ymax - y0)

    for i in range(4):
        pi = p[i]
        qi = q[i]
        if pi == 0:
            # Parallel to this boundary; reject only if outside the AABB strip
            if qi < 0:
                return None
            # else: this constraint is inactive, continue
            continue

        t = qi / pi
        if pi < 0:
            # Entering boundary
            if t > t_exit:
                return None
            if t > t_enter:
                t_enter = t
        else:
            # pi > 0, exiting boundary
            if t < t_enter:
                return None
            if t < t_exit:
                t_exit = t

    if t_enter > t_exit:
        return None
    return (t_enter, t_exit)


def segment_intersects_aabb(p0: Point, p1: Point, aabb: AABB) -> bool:
    """True iff segment p0→p1 intersects (含相切) AABB.

    Standard wrapper over segment_aabb_intersection_t.
    """
    return segment_aabb_intersection_t(p0, p1, aabb) is not None


def cell_aabb_from_rect(rect: Tuple[int, int, int, int]) -> AABB:
    """Convert ghost_rect (x, y, h, w) — top-left + size — to AABB float bounds.

    Spec uses cell grid (integer coords); AABB extends to (x+h, y+w) inclusive
    edge. Liang-Barsky compares float t so we add 1.0 for inclusive max edge
    iff the spec treats cells as unit squares — see callers in F8 validator.
    """
    x, y, h, w = rect
    return (float(x), float(y), float(x + h), float(y + w))
