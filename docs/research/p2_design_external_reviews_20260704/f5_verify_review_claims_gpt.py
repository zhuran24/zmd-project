#!/usr/bin/env python3
"""Evidence script for f5 orbit-lift adversarial review.
Reads only files extracted from f5_orbit_lift_design_v1.zip.
"""
from __future__ import annotations

import collections
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def verify_p_hom() -> None:
    records = json.loads((ROOT / "data/preprocessed/mandatory_exact_instances.json").read_text(encoding="utf-8"))
    groups: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for rec in records:
        groups[(str(rec.get("facility_type")), str(rec.get("operation_type")))].append(rec)

    violations = []
    for key, items in sorted(groups.items()):
        base = {k: v for k, v in items[0].items() if k != "instance_id"}
        for item in items[1:]:
            stripped = {k: v for k, v in item.items() if k != "instance_id"}
            if stripped != base:
                violations.append((key, items[0]["instance_id"], item["instance_id"]))
                break

    print("P-HOM mandatory_exact_instances groups:", len(groups), "records:", len(records))
    print("P-HOM violations modulo instance_id:", len(violations))
    for key, items in sorted(groups.items()):
        print(f"  {key}: n={len(items)}")


def count_math() -> None:
    manufacturing_3x3_counts = [34, 34, 18, 17, 11, 6, 6, 6]
    log10_product = sum(math.lgamma(n + 1) / math.log(10) for n in manufacturing_3x3_counts)
    all_group_counts = [46,34,6,11,18,6,6,34,17,11,21,6,11,3,17,9,6,3,1]
    log10_all = sum(math.lgamma(n + 1) / math.log(10) for n in all_group_counts)
    n, k = 34, 8
    falling = math.prod(range(n - k + 1, n + 1))
    print("log10 Π n_g! for 8 manufacturing_3x3 groups:", round(log10_product, 6))
    print("log10 Π n_g! for all mandatory groups in bundle:", round(log10_all, 6))
    print("(34)_8 = 34·33·...·27:", falling)


def toy_context_dependent_oracle_fp() -> None:
    # The core contains only g:pA. In one incumbent, an outside blocker h:q blocks pA;
    # in another incumbent, h:q is absent. A context-reading oracle can reject the
    # first, but the lifted F5 cut would fire in both because it evaluates only the
    # core multiset.
    core = collections.Counter({("g", "pA"): 1})
    state_with_blocker = collections.Counter({("g", "pA"): 1, ("h", "q_blocker"): 1})
    state_without_blocker = collections.Counter({("g", "pA"): 1, ("h", "q_else"): 1})

    def oracle(core_counter: collections.Counter, state_counter: collections.Counter) -> str:
        return "INFEASIBLE" if core_counter[("g", "pA")] and state_counter[("h", "q_blocker")] else "FEASIBLE"

    def lifted_cut_fires(core_counter: collections.Counter, state_counter: collections.Counter) -> bool:
        return all(state_counter[key] >= count for key, count in core_counter.items())

    assert oracle(core, state_with_blocker) == "INFEASIBLE"
    assert oracle(core, state_without_blocker) == "FEASIBLE"
    assert lifted_cut_fires(core, state_without_blocker)
    print("toy context-dependent oracle FP: reproduced")


def toy_multiplicity_collapse_fp() -> None:
    # Correct multiset semantics forbids two copies of p. Boolean-presence collapse
    # forbids one copy of p, which is strictly stronger and can be false-positive.
    forbidden_multiset = collections.Counter({("g", "p"): 2})
    feasible_one_copy_state = collections.Counter({("g", "p"): 1})

    correct_multiset_cut_fires = all(
        feasible_one_copy_state[key] >= count for key, count in forbidden_multiset.items()
    )
    boolean_presence_cut_fires = feasible_one_copy_state[("g", "p")] >= 1

    assert not correct_multiset_cut_fires
    assert boolean_presence_cut_fires
    print("toy multiplicity-collapse FP: reproduced")


if __name__ == "__main__":
    verify_p_hom()
    count_math()
    toy_context_dependent_oracle_fp()
    toy_multiplicity_collapse_fp()
