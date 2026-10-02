#!/usr/bin/env python3
"""Independent full enumeration of one k-item block; standard library only."""
import itertools
import json
from functools import lru_cache
from pathlib import Path


def branching(releases):
    """A: choose any empty, as-yet-unserved head at each judgment."""
    n = len(releases)

    @lru_cache(None)
    def visit(t, used):
        if used == (1 << n) - 1:
            return {t - 1: 1}
        available = [i for i, r in enumerate(releases)
                     if not used >> i & 1 and r <= t]
        if not available:
            return visit(min(r for i, r in enumerate(releases)
                             if not used >> i & 1), used)
        counts = {}
        for i in available:
            for end, count in visit(t + 1, used | (1 << i)).items():
                counts[end] = counts.get(end, 0) + count
        return counts

    return visit(0, 0)


def permutations(releases):
    """B: independently enumerate orders, rejecting avoidable idle steps."""
    counts = {}
    for order in itertools.permutations(range(len(releases))):
        now = 0
        valid = True
        for pos, head in enumerate(order):
            earliest_judgment = max(now, min(releases[j] for j in order[pos:]))
            if releases[head] > now:
                if releases[head] > earliest_judgment:
                    valid = False
                    break
                now = releases[head]
            now += 1
        if valid:
            counts[now - 1] = counts.get(now - 1, 0) + 1
    return counts


def main():
    rows = []
    profiles = []
    for k in range(2, 9):
        total_orders = 0
        worst = -1
        count = 0
        for occupied in range(k):
            for positive in itertools.combinations(range(1, 8), occupied):
                releases = (0,) * (k - occupied) + positive
                a, b = branching(releases), permutations(releases)
                assert a == b, (releases, a, b)
                assert len(a) == 1 and max(a) <= 7, (releases, a)
                total_orders += sum(a.values())
                worst = max(worst, max(a))
                count += 1
                profiles.append({"k": k, "releases": releases,
                                 "end_counts": a})
        rows.append({"k": k, "release_profiles": count,
                     "admissible_orders": total_orders,
                     "maximum_last_offset": worst,
                     "encoding_mismatches": 0})
    result = {"rows": rows,
              "physical_k": [2, 3],
              "all_profiles": profiles,
              "verification_note": "The permutation checker rejects waiting past any earlier release; all reported results are after this correction.",
              "negative_control_k9": {
                  "releases": [0] * 9,
                  "first_nine_routes": [0, 1, 2, 3, 4, 5, 6, 7, 0],
                  "note": "At step 8 route 0 is empty again; route 8 can be skipped."}}
    target = Path(__file__).with_name("blocks.json")
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    main()
