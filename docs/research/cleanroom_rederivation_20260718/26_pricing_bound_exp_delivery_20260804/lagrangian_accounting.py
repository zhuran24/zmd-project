#!/usr/bin/env python3
"""Exact bucket-transport Lagrangian bookkeeping.

Research-only.  This module does no registry/ledger work.  Values may be ints,
floats, or Fractions; exact arithmetic is used internally.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
from pathlib import Path
from typing import Dict, Mapping, Sequence

FAMILY_ORDER = (
    "CLEAN", "LEFT_J1", "LEFT_J2", "LEFT_J3",
    "BOTTOM_I1", "BOTTOM_I2", "BOTTOM_I3", "BOTTOM_I4",
    "CORNER", "CORE",
)
FAMILY_MULTIPLICITY: Dict[str, int] = {
    "CLEAN": 16,
    "LEFT_J1": 1, "LEFT_J2": 1, "LEFT_J3": 1,
    "BOTTOM_I1": 1, "BOTTOM_I2": 1, "BOTTOM_I3": 1, "BOTTOM_I4": 1,
    "CORNER": 1, "CORE": 1,
}
CLASS_ORDER = ("3L", "3O2", "3O3", "3I2", "5L", "5O2", "6I3", "6I4", "6I5")
CLASS_DEMAND: Dict[str, int] = {
    "3L": 109, "3O2": 6, "3O3": 11, "3I2": 6,
    "5L": 32, "5O2": 17,
    "6I3": 32, "6I4": 3, "6I5": 3,
}
CLASS_AREA: Dict[str, int] = {
    "3L": 9, "3O2": 9, "3O3": 9, "3I2": 9,
    "5L": 25, "5O2": 25,
    "6I3": 24, "6I4": 24, "6I5": 24,
}
BUCKET_ORDER = (
    "M3_1i1o", "M3_1i2o+2i1o", "M3_1i3o+2i1o",
    "M5_1i1o", "M5_1i2o",
    "M6_3i1o", "M6_4i1o", "M6_5i1o",
)
BUCKET_SERVABLE: Dict[str, tuple[str, ...]] = {
    "M3_1i1o": ("3L",),
    "M3_1i2o+2i1o": ("3L", "3O2", "3I2"),
    "M3_1i3o+2i1o": ("3L", "3O2", "3O3", "3I2"),
    "M5_1i1o": ("5L",),
    "M5_1i2o": ("5L", "5O2"),
    "M6_3i1o": ("6I3",),
    "M6_4i1o": ("6I3", "6I4"),
    "M6_5i1o": ("6I3", "6I4", "6I5"),
}

BOUNDARY_FAMILIES = (
    "LEFT_J1", "LEFT_J2", "LEFT_J3",
    "BOTTOM_I1", "BOTTOM_I2", "BOTTOM_I3", "BOTTOM_I4",
)
BOUNDARY_HOLE_BASE: Dict[str, int] = {
    "LEFT_J1": 129, "LEFT_J2": 129, "LEFT_J3": 130,
    "BOTTOM_I1": 129, "BOTTOM_I2": 129, "BOTTOM_I3": 130, "BOTTOM_I4": 129,
}


def _f(value: Fraction | int | float | str) -> Fraction:
    return value if isinstance(value, Fraction) else Fraction(str(value))


def bucket_weights(mu: Mapping[str, Fraction | int | float | str]) -> Dict[str, Fraction]:
    """Return w_b(mu)=max_{c served by b}(A_c-mu_c)."""
    missing = set(CLASS_ORDER) - set(mu)
    if missing:
        raise KeyError(f"missing mu values: {sorted(missing)}")
    if any(_f(mu[c]) < 0 for c in CLASS_ORDER):
        raise ValueError("mu must be nonnegative because C2b is <= demand")
    return {
        b: max(Fraction(CLASS_AREA[c]) - _f(mu[c]) for c in BUCKET_SERVABLE[b])
        for b in BUCKET_ORDER
    }


def bound_from_pricing(
    pricing_upper: Mapping[str, Fraction | int | float | str],
    mu: Mapping[str, Fraction | int | float | str],
    hole_dual: Fraction | int | float | str,
) -> Fraction:
    """Compute Σ_f m_f B_f + Σ_c d_c μ_c + λ.

    B_f must legally upper-bound max_p[Σ_b w_b a_pb - λ h_p].
    """
    missing = set(FAMILY_ORDER) - set(pricing_upper)
    if missing:
        raise KeyError(f"missing family pricing bounds: {sorted(missing)}")
    bucket_weights(mu)  # validates μ and completeness
    return (
        sum(FAMILY_MULTIPLICITY[f] * _f(pricing_upper[f]) for f in FAMILY_ORDER)
        + sum(CLASS_DEMAND[c] * _f(mu[c]) for c in CLASS_ORDER)
        + _f(hole_dual)
    )


def bound_from_epsilon(
    pi: Mapping[str, Fraction | int | float | str],
    epsilon_upper: Mapping[str, Fraction | int | float | str],
    mu: Mapping[str, Fraction | int | float | str],
    hole_dual: Fraction | int | float | str,
) -> Fraction:
    """Signed-ε form.  Negative ε is deliberately not clipped."""
    missing = (set(FAMILY_ORDER) - set(pi)) | (set(FAMILY_ORDER) - set(epsilon_upper))
    if missing:
        raise KeyError(f"missing pi/epsilon values: {sorted(missing)}")
    repaired = {f: _f(pi[f]) + _f(epsilon_upper[f]) for f in FAMILY_ORDER}
    return bound_from_pricing(repaired, mu, hole_dual)


def contribution_breakdown(
    pricing_upper: Mapping[str, Fraction | int | float | str],
    mu: Mapping[str, Fraction | int | float | str],
    hole_dual: Fraction | int | float | str,
) -> Dict[str, object]:
    family_terms = {
        f: FAMILY_MULTIPLICITY[f] * _f(pricing_upper[f]) for f in FAMILY_ORDER
    }
    class_terms = {c: CLASS_DEMAND[c] * _f(mu[c]) for c in CLASS_ORDER}
    total = sum(family_terms.values()) + sum(class_terms.values()) + _f(hole_dual)
    return {"family_terms": family_terms, "class_terms": class_terms,
            "hole_term": _f(hole_dual), "total": total}


def hole_branch_bounds(
    nohole_upper: Mapping[str, Fraction | int | float | str],
    hole_upper: Mapping[str, Fraction | int | float | str],
) -> Dict[str, Fraction]:
    """Area-baseline branch accounting with exactly one hole.

    Inputs are local area upper bounds, not reduced-cost bounds.  CORE contributes 0.
    """
    required_nohole = {"CLEAN", *BOUNDARY_FAMILIES, "CORNER"}
    required_hole = {"CLEAN", *BOUNDARY_FAMILIES, "CORNER"}
    if required_nohole - set(nohole_upper):
        raise KeyError(f"missing no-hole bounds: {sorted(required_nohole-set(nohole_upper))}")
    if required_hole - set(hole_upper):
        raise KeyError(f"missing hole bounds: {sorted(required_hole-set(hole_upper))}")
    nh = {k: _f(v) for k, v in nohole_upper.items()}
    hh = {k: _f(v) for k, v in hole_upper.items()}
    common_boundary = sum(nh[f] for f in BOUNDARY_FAMILIES)
    result: Dict[str, Fraction] = {}
    result["hole@CLEAN"] = 15 * nh["CLEAN"] + hh["CLEAN"] + common_boundary + nh["CORNER"]
    for k in BOUNDARY_FAMILIES:
        result[f"hole@{k}"] = (
            16 * nh["CLEAN"]
            + sum(hh[k] if f == k else nh[f] for f in BOUNDARY_FAMILIES)
            + nh["CORNER"]
        )
    result["hole@CORNER"] = 16 * nh["CLEAN"] + common_boundary + hh["CORNER"]
    result["unified"] = max(result.values())
    return result


def _jsonable(value: object) -> object:
    if isinstance(value, Fraction):
        return value.numerator if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="JSON containing pricing_upper, mu, lambda")
    args = parser.parse_args(argv)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    out = contribution_breakdown(payload["pricing_upper"], payload["mu"], payload["lambda"])
    print(json.dumps(_jsonable(out), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
