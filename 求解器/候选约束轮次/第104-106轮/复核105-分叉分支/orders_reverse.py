#!/usr/bin/env python3
"""Independent encoding B: test a channel order by removing the last unit.

The edges incident to the last unit must form a suffix. Recursing on the prefix
is both necessary and sufficient. No build permutations or encoding-A imports.
"""
from functools import lru_cache
from itertools import permutations
import hashlib
import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent


def check(n, edges, detailed=False):
    incident = [{i for i, edge in enumerate(edges) if v in edge}
                for v in range(n)]
    orders = []
    witness = {}
    for order in permutations(range(len(edges))):
        @lru_cache(None)
        def remove_last(vertices, prefix_length):
            if vertices == 0:
                return () if prefix_length == 0 else None
            prefix = order[:prefix_length]
            for v in range(n):
                if not vertices & (1 << v):
                    continue
                ids = incident[v].intersection(prefix)
                cut = prefix_length - len(ids)
                if set(order[cut:prefix_length]) != ids:
                    continue
                before = remove_last(vertices ^ (1 << v), cut)
                if before is not None:
                    return before + (v,)
            return None

        build = remove_last((1 << n) - 1, len(edges))
        if build is not None:
            orders.append(order)
            if detailed:
                witness[",".join(map(str, order))] = list(build)

    # Count strict builds using a subset recurrence, not explicit permutations.
    counts = [0] * (1 << n)
    counts[0] = 1
    for subset in range(1 << n):
        for v in range(n):
            if subset & (1 << v):
                continue
            new_edges = sum(1 for u, w in edges
                            if (u == v and subset & (1 << w))
                            or (w == v and subset & (1 << u)))
            if new_edges <= 1:
                counts[subset | (1 << v)] += counts[subset]

    # A separate disjoint-set check includes parallel edges as cycles.
    parent = list(range(n))
    def root(v):
        while parent[v] != v:
            v = parent[v]
        return v
    forest = True
    for u, v in edges:
        ru, rv = root(u), root(v)
        if ru == rv:
            forest = False
        else:
            parent[ru] = rv
    assert bool(counts[-1]) == forest
    payload = json.dumps(sorted(orders), separators=(",", ":")).encode()
    result = {"n": n, "edges": edges, "build_count": math.factorial(n),
              "strict_build_count": counts[-1],
              "channel_permutations": math.factorial(len(edges)),
              "realizable_orders": len(orders),
              "orders_sha256": hashlib.sha256(payload).hexdigest(),
              "forest": forest}
    if detailed:
        result["orders"] = orders
        result["witness_builds"] = witness
    return result


def main():
    cases = {}
    for n in range(1, 6):
        pairs = [(u, v) for u in range(n) for v in range(u + 1, n)]
        for mask in range(1 << len(pairs)):
            if mask.bit_count() > 6:
                continue
            edges = [pair for k, pair in enumerate(pairs) if mask >> k & 1]
            cases[f"simple_{n}_{mask}"] = check(n, edges)
    named = [
        ("triangle", 3, [(0, 1), (0, 2), (1, 2)]),
        ("square", 4, [(0, 1), (0, 3), (1, 2), (2, 3)]),
        ("s3x", 5, [(0, 1), (0, 2), (0, 3), (1, 4), (2, 4), (3, 4)]),
        ("parallel_pair", 2, [(0, 1), (0, 1)]),
        ("tree_star", 4, [(0, 1), (0, 2), (0, 3)]),
        ("parallel_path", 4, [(0, 1), (0, 1), (1, 2), (2, 3)]),
    ]
    examples = {name: check(n, edges, True) for name, n, edges in named}
    data = {"method": "last-unit suffix removal; subset DP; disjoint-set forest check",
            "simple_graph_cases": len(cases), "cases": cases, "examples": examples}
    (OUT / "orders_reverse.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"simple_graph_cases": len(cases),
                      "examples": {name: {k: v for k, v in d.items()
                                           if k not in ("orders", "witness_builds")}
                                   for name, d in examples.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
