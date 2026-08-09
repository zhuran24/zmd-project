#!/usr/bin/env python3
"""Exact, continuous-domain verification of REJUDGE_REPORT Part F.

No CP-SAT and no 1/660 lattice.  For a threshold t, each machine duty d
must lie in the exact union of intervals where every intermediate-port
residual is > t.  We enumerate interval-count compositions and test whether
n such duties can sum to the required aggregate occupancy x.
"""
from __future__ import annotations

from fractions import Fraction as F
from itertools import product
from math import ceil


def residual(c: int, d: F) -> F:
    y = c * d
    return y - (ceil(y) - 1)


def intersect_unions(a: list[tuple[F, F]], b: list[tuple[F, F]]) -> list[tuple[F, F]]:
    """Intervals are (lo, hi], represented by endpoint pairs."""
    out: list[tuple[F, F]] = []
    for alo, ahi in a:
        for blo, bhi in b:
            lo, hi = max(alo, blo), min(ahi, bhi)
            if lo < hi:
                out.append((lo, hi))
    return sorted(set(out))


def allowed_intervals(rates: tuple[int, ...], t: F) -> list[tuple[F, F]]:
    allowed = [(F(0), F(1))]
    for c in rates:
        one_rate = [(F(j, c) + t / c, F(j + 1, c)) for j in range(c)]
        allowed = intersect_unions(allowed, one_rate)
    return allowed


def compositions(n: int, k: int):
    if k == 1:
        yield (n,)
        return
    for first in range(n + 1):
        for tail in compositions(n - first, k - 1):
            yield (first,) + tail


def strict_threshold_feasible(n: int, x: F, rates: tuple[int, ...], t: F) -> bool:
    intervals = allowed_intervals(rates, t)
    for counts in compositions(n, len(intervals)):
        lo = sum((count * intervals[i][0] for i, count in enumerate(counts)), F(0))
        hi = sum((count * intervals[i][1] for i, count in enumerate(counts)), F(0))
        # Every lower endpoint is open.  Upper endpoints are closed.
        if lo < x <= hi:
            return True
    return False


CASES = {
    "crusher_buckwheat":        (6,  F(11, 2), (1, 2), F(5, 6),  F(11, 12)),
    "crusher_sandleaf":         (11, F(21, 2), (1, 3), F(19, 22), F(21, 22)),
    "filling_capsule":          (3,  F(11, 4), (2,),   F(5, 6),  F(11, 12)),
    "grinder_fine_buckwheat":   (6,  F(11, 2), (1, 2), F(5, 6),  F(11, 12)),
    "molding_bottle":           (6,  F(11, 2), (1, 2), F(5, 6),  F(11, 12)),
    "seed_collector_buckwheat": (6,  F(11, 2), (1, 2), F(5, 6),  F(11, 12)),
    "seed_collector_sandleaf":  (11, F(21, 2), (1, 2), F(10, 11), F(21, 22)),
}

for name, (n, x, rates, optimum, uniform) in CASES.items():
    assert n * uniform == x
    achieved = min(residual(c, uniform) for c in rates)
    assert achieved == optimum, (name, achieved, optimum)
    assert not strict_threshold_feasible(n, x, rates, optimum), name
    intervals = allowed_intervals(rates, optimum)
    pretty = ", ".join(f"({lo},{hi}]" for lo, hi in intervals)
    print(
        f"{name}: continuous_optimum={optimum}; uniform={uniform}; "
        f"allowed_for_residual>{optimum}: {pretty}; strict_improvement_feasible=False"
    )
