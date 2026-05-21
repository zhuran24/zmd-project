"""Phase 1.0 P1.4 test — Liang-Barsky line-AABB intersection.

Coverage:
- Standard cases: through-AABB / miss / one endpoint inside
- Edge cases: degenerate (point), touch (corner), axis-aligned along edge
- Ill-formed AABB → raise
"""
from __future__ import annotations

import pytest

from src.cuts.helpers.ghost_geometry import (
    cell_aabb_from_rect,
    segment_aabb_intersection_t,
    segment_intersects_aabb,
)


# Standard 10x10 AABB at (10,10)-(20,20)
AABB_STD = (10.0, 10.0, 20.0, 20.0)


# ============================================================================
# Standard cases
# ============================================================================

def test_segment_through_aabb_returns_t_range():
    """Segment 完全穿过 AABB."""
    p0 = (0.0, 15.0)
    p1 = (30.0, 15.0)
    result = segment_aabb_intersection_t(p0, p1, AABB_STD)
    assert result is not None
    t_enter, t_exit = result
    # Enter at x=10 → t = 10/30 = 1/3; Exit at x=20 → t = 20/30 = 2/3
    assert abs(t_enter - 1 / 3) < 1e-9
    assert abs(t_exit - 2 / 3) < 1e-9
    assert segment_intersects_aabb(p0, p1, AABB_STD) is True


def test_segment_misses_aabb_returns_none():
    """Segment 完全 miss AABB."""
    p0 = (0.0, 0.0)
    p1 = (5.0, 5.0)
    assert segment_aabb_intersection_t(p0, p1, AABB_STD) is None
    assert segment_intersects_aabb(p0, p1, AABB_STD) is False


def test_segment_one_endpoint_inside():
    """一个 endpoint 在 AABB 内, 另一在外."""
    p0 = (15.0, 15.0)  # inside
    p1 = (30.0, 30.0)  # outside
    result = segment_aabb_intersection_t(p0, p1, AABB_STD)
    assert result is not None
    t_enter, t_exit = result
    assert t_enter == 0.0  # 起点已在内
    assert 0 < t_exit < 1
    assert segment_intersects_aabb(p0, p1, AABB_STD) is True


def test_segment_both_endpoints_inside():
    p0 = (12.0, 12.0)
    p1 = (18.0, 18.0)
    result = segment_aabb_intersection_t(p0, p1, AABB_STD)
    assert result is not None
    assert result == (0.0, 1.0)


# ============================================================================
# Edge cases — degenerate / touch / axis-aligned
# ============================================================================

def test_degenerate_segment_point_inside():
    p = (15.0, 15.0)
    result = segment_aabb_intersection_t(p, p, AABB_STD)
    assert result == (0.0, 0.0)
    assert segment_intersects_aabb(p, p, AABB_STD) is True


def test_degenerate_segment_point_outside():
    p = (5.0, 5.0)
    assert segment_aabb_intersection_t(p, p, AABB_STD) is None
    assert segment_intersects_aabb(p, p, AABB_STD) is False


def test_segment_touches_corner():
    """Segment 端点恰在 AABB 角上 — touch counts as intersection."""
    p0 = (0.0, 0.0)
    p1 = (10.0, 10.0)  # 端点恰在 AABB 角 (10,10)
    result = segment_aabb_intersection_t(p0, p1, AABB_STD)
    assert result is not None
    # 仅角点接触: t_enter == t_exit == 1.0
    t_enter, t_exit = result
    assert abs(t_enter - 1.0) < 1e-9
    assert abs(t_exit - 1.0) < 1e-9


def test_segment_along_aabb_edge():
    """Axis-aligned segment 沿 AABB 一边 — 算 intersection."""
    p0 = (5.0, 10.0)
    p1 = (25.0, 10.0)
    result = segment_aabb_intersection_t(p0, p1, AABB_STD)
    assert result is not None
    t_enter, t_exit = result
    # x=10 → t=5/20=0.25; x=20 → t=15/20=0.75
    assert abs(t_enter - 0.25) < 1e-9
    assert abs(t_exit - 0.75) < 1e-9


def test_segment_parallel_miss():
    """Segment parallel to AABB 但在 strip 外."""
    p0 = (0.0, 5.0)
    p1 = (30.0, 5.0)  # y=5, AABB y in [10,20]
    assert segment_aabb_intersection_t(p0, p1, AABB_STD) is None


def test_segment_vertical_through_aabb():
    p0 = (15.0, 0.0)
    p1 = (15.0, 30.0)
    result = segment_aabb_intersection_t(p0, p1, AABB_STD)
    assert result is not None
    t_enter, t_exit = result
    assert abs(t_enter - 10 / 30) < 1e-9
    assert abs(t_exit - 20 / 30) < 1e-9


# ============================================================================
# AABB validation
# ============================================================================

def test_aabb_ill_formed_raises():
    bad = (20.0, 10.0, 10.0, 20.0)  # xmin > xmax
    with pytest.raises(ValueError, match="ill-formed"):
        segment_aabb_intersection_t((0.0, 0.0), (5.0, 5.0), bad)


# ============================================================================
# cell_aabb_from_rect helper
# ============================================================================

def test_cell_aabb_from_rect_conversion():
    """ghost_rect (x=10, y=20, h=5, w=8) → AABB (10, 20, 15, 28)."""
    rect = (10, 20, 5, 8)
    aabb = cell_aabb_from_rect(rect)
    assert aabb == (10.0, 20.0, 15.0, 28.0)
