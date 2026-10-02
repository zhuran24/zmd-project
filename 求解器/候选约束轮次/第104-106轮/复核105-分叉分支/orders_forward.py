#!/usr/bin/env python3
"""Independent encoding A: build units, then permute each new-channel batch.

No imports from another review or from the game simulator. All output stays here.
The graphs are connection-order test cases, not certificates of game feasibility.
"""
import hashlib
import itertools as it
import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent


def digest(orders):
    raw = json.dumps(sorted(orders), separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def examine(n, edges, detailed=False):
    found = set()
    witnesses = {}
    strict_build_count = 0
    for build in it.permutations(range(n)):
        rank = {unit: k for k, unit in enumerate(build)}
        batches = [[] for _ in build]
        for eid, (u, v) in enumerate(edges):
            batches[max(rank[u], rank[v])].append(eid)
        if all(len(batch) <= 1 for batch in batches):
            strict_build_count += 1
        refinements = [it.permutations(batch) for batch in batches if batch]
        for chosen in it.product(*refinements):
            order = tuple(eid for batch in chosen for eid in batch)
            found.add(order)
            if detailed:
                witnesses.setdefault(",".join(map(str, order)), list(build))
    result = {
        "n": n, "edges": edges, "build_count": math.factorial(n),
        "strict_build_count": strict_build_count,
        "channel_permutations": math.factorial(len(edges)),
        "realizable_orders": len(found), "orders_sha256": digest(found),
    }
    if detailed:
        result["orders"] = sorted(found)
        result["witness_builds"] = witnesses
    return result


def main():
    cases = {}
    for n in range(1, 6):
        possible = list(it.combinations(range(n), 2))
        for count in range(min(6, len(possible)) + 1):
            for edge_indices in it.combinations(range(len(possible)), count):
                mask = sum(1 << k for k in edge_indices)
                edges = [possible[k] for k in edge_indices]
                cases[f"simple_{n}_{mask}"] = examine(n, edges)
    examples = {
        "triangle": (3, [(0, 1), (0, 2), (1, 2)]),
        "square": (4, [(0, 1), (0, 3), (1, 2), (2, 3)]),
        "s3x": (5, [(0, 1), (0, 2), (0, 3), (1, 4), (2, 4), (3, 4)]),
        "parallel_pair": (2, [(0, 1), (0, 1)]),
        "tree_star": (4, [(0, 1), (0, 2), (0, 3)]),
        "parallel_path": (4, [(0, 1), (0, 1), (1, 2), (2, 3)]),
    }
    detail = {name: examine(n, edges, True)
              for name, (n, edges) in examples.items()}
    data = {"method": "endpoint maximum plus independent within-batch permutations",
            "simple_graph_cases": len(cases), "cases": cases, "examples": detail}
    (OUT / "orders_forward.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"simple_graph_cases": len(cases),
                      "examples": {name: {k: v for k, v in d.items()
                                           if k not in ("orders", "witness_builds")}
                                   for name, d in detail.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
