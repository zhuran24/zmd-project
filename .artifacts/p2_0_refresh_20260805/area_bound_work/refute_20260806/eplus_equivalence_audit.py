#!/usr/bin/env python3
"""Exhaustively check the E+ packing/exact-partition identity."""

from itertools import combinations


def max_savings(edges: tuple[frozenset[int], ...]) -> int:
    best = 0
    for size in range(len(edges) + 1):
        for chosen in combinations(edges, size):
            if sum(map(len, chosen)) != len(set().union(*chosen)):
                continue
            best = max(best, sum(len(edge) - 1 for edge in chosen))
    return best


def min_exact(vertices: frozenset[int], edges: tuple[frozenset[int], ...]) -> int:
    for size in range(1, len(edges) + 1):
        for chosen in combinations(edges, size):
            if set().union(*chosen) != vertices:
                continue
            if sum(map(len, chosen)) == len(vertices):
                return size
    raise AssertionError("E+ contains every singleton, so an exact partition must exist")


def augment(vertices: frozenset[int], edges: tuple[frozenset[int], ...]) -> tuple[frozenset[int], ...]:
    return tuple(dict.fromkeys((*edges, *(frozenset({vertex}) for vertex in vertices))))


def audit_family(vertices: frozenset[int], physical_edges: tuple[frozenset[int], ...]) -> tuple[int, int]:
    augmented = augment(vertices, physical_edges)
    packing_rhs = len(vertices) - max_savings(augmented)
    exact_partition = min_exact(vertices, augmented)
    assert packing_rhs == exact_partition
    return packing_rhs, exact_partition


def main() -> None:
    # The overlapping-cover example now printed in v7.
    vertices5 = frozenset(range(5))
    report_example = (frozenset({0, 1, 2}), frozenset({2, 3, 4}))
    assert audit_family(vertices5, report_example) == (3, 3)

    # The fourth-review non-extendable physical packing. Formal singletons turn
    # its value from a false equality at 3 into a safe relaxed lower bound at 2.
    old_counterexample = (
        frozenset({0, 1}),
        frozenset({2, 3}),
        frozenset({4}),
        frozenset({0, 2, 3, 4}),
    )
    assert min_exact(vertices5, old_counterexample) == 3
    assert audit_family(vertices5, old_counterexample) == (2, 2)

    # Exhaust every hypergraph on four vertices (all 2^11 choices of
    # non-singleton edges); E+ must satisfy the identity in every case.
    vertices4 = frozenset(range(4))
    optional = tuple(
        frozenset(edge)
        for size in range(2, 5)
        for edge in combinations(vertices4, size)
    )
    checked = 0
    for mask in range(1 << len(optional)):
        physical = tuple(edge for index, edge in enumerate(optional) if mask & (1 << index))
        audit_family(vertices4, physical)
        checked += 1

    print(
        {
            "exhaustive_n4_hypergraphs": checked,
            "report_example": {"packing_rhs": 3, "eplus_exact_partition": 3},
            "old_counterexample_after_eplus": {
                "physical_exact_partition": 3,
                "relaxed_packing_rhs": 2,
                "eplus_exact_partition": 2,
            },
            "eplus_identity": True,
        }
    )


if __name__ == "__main__":
    main()
