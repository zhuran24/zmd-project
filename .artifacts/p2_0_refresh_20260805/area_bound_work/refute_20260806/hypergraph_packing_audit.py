#!/usr/bin/env python3
"""Check the v5 weighted disjoint-packing identity and ordinary-cover claim."""

from __future__ import annotations

from itertools import combinations


def max_disjoint_savings(edges: tuple[frozenset[int], ...]) -> int:
    best = 0
    for mask in range(1 << len(edges)):
        used: set[int] = set()
        savings = 0
        for index, edge in enumerate(edges):
            if not (mask >> index) & 1:
                continue
            if used & edge:
                break
            used |= edge
            savings += len(edge) - 1
        else:
            best = max(best, savings)
    return best


def min_cover(vertex_count: int, edges: tuple[frozenset[int], ...], *, exact: bool) -> int:
    universe = set(range(vertex_count))
    for count in range(1, len(edges) + 1):
        for indexes in combinations(range(len(edges)), count):
            selected = [edges[index] for index in indexes]
            if set().union(*selected) != universe:
                continue
            if exact and sum(len(edge) for edge in selected) != vertex_count:
                continue
            return count
    raise AssertionError("singleton edges should guarantee a cover")


def main() -> None:
    vertices = 5
    edges = tuple(
        [frozenset({index}) for index in range(vertices)]
        + [frozenset({0, 1, 2}), frozenset({2, 3, 4})]
    )
    packing_bound = vertices - max_disjoint_savings(edges)
    ordinary_cover = min_cover(vertices, edges, exact=False)
    exact_cover = min_cover(vertices, edges, exact=True)
    assert packing_bound == exact_cover == 3
    assert ordinary_cover == 2
    print(
        {
            "vertices": vertices,
            "n_minus_max_weight_packing": packing_bound,
            "minimum_exact_cover": exact_cover,
            "minimum_ordinary_cover": ordinary_cover,
            "overlap_vertex": 2,
        }
    )


if __name__ == "__main__":
    main()
