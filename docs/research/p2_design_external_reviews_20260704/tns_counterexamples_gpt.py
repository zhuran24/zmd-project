#!/usr/bin/env python3
"""Tiny executable counterexamples for the TNS design review.

This file is not production code. It just demonstrates why the reviewed design
must enforce authoritative domain, oriented coverage, and non-empty domains.
"""

from __future__ import annotations


def covered(domain: set[tuple[int, int]], cover: set[tuple[int, int]]) -> bool:
    return all(any(w >= cw and h >= ch for cw, ch in cover) for w, h in domain)


def authoritative_domain(min_side: int = 6, max_side: int = 8) -> set[tuple[int, int]]:
    return {(w, h) for w in range(min_side, max_side + 1) for h in range(min_side, max_side + 1)}


def sliced_domain(min_side: int = 7, max_side: int = 8) -> set[tuple[int, int]]:
    return {(w, h) for w in range(min_side, max_side + 1) for h in range(min_side, max_side + 1)}


def main() -> None:
    full = authoritative_domain()
    sliced = sliced_domain()

    assert covered(sliced, {(7, 7)})
    assert not covered(full, {(7, 7)}), "min_side=7 evidence must not cover authoritative min_side=6 domain"

    oriented_domain = {(6, 7), (7, 6)}
    assert covered(oriented_domain, {(6, 7), (7, 6)})
    assert not covered(oriented_domain, {(6, 7)}), "6x7 must not cover 7x6 in oriented dimwise order"

    empty: set[tuple[int, int]] = set()
    assert covered(empty, set()), "vacuous truth is exactly why empty public TNS domains must be rejected"

    print("counterexamples confirmed")


if __name__ == "__main__":
    main()
