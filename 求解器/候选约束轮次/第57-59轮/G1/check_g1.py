#!/usr/bin/env python3
"""Finite checks of local G1 claims; not a base-layout simulator.

Prints JSON only. No files are written by this script. The dense-node model
uses two explicitly fixed event orders, single-item transport slots, and
one-tick residence. Boundary sources and sinks are specified in the result.
"""

from collections import Counter
from fractions import Fraction
from hashlib import sha256
from itertools import product, permutations
from math import gcd, lcm
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[4]


def literal_polling(word, k, initial_port=0):
    """Follow individual successful items until both indices return."""
    counts = [Counter() for _ in range(k)]
    j, port = 0, initial_port
    steps = 0
    while True:
        counts[port][word[j]] += 1
        steps += 1
        j = (j + 1) % len(word)
        port = (port + 1) % k
        if j == 0 and port == initial_port:
            return counts, steps


def modular_counts(word, k, initial_port=0):
    h = gcd(len(word), k)
    residue = [Counter(word[r::h]) for r in range(h)]
    return [residue[(p - initial_port) % h] for p in range(k)]


def check_material_polling():
    cases = 0
    for alphabet, max_length in ((2, 8), (3, 6)):
        for length in range(1, max_length + 1):
            for word in product(range(alphabet), repeat=length):
                for k in range(1, 7):
                    for start in range(k):
                        got, steps = literal_polling(word, k, start)
                        assert got == modular_counts(word, k, start)
                        assert steps == lcm(length, k)
                        assert all(sum(c.values()) == length // gcd(length, k)
                                   for c in got)
                        cases += 1
    # The least flow to m physical outlets under arbitrary outlet permutations
    # is the sum of the m smallest canonical outlet flows, when word/F persist.
    permutation_cases = 0
    for word in ((0, 1), (0, 0, 1, 1), (0, 1, 2), (0, 1, 0, 2)):
        for k in range(1, 7):
            counts, _ = literal_polling(word, k)
            for item in set(word):
                values = [c[item] for c in counts]
                for m in range(1, k + 1):
                    brute = min(sum(values[p] for p in perm[:m])
                                for perm in permutations(range(k)))
                    assert brute == sum(sorted(values)[:m])
                    permutation_cases += 1
    examples = []
    for word, k in (("XY", 2), ("XXYY", 2), ("XY", 3), ("XXY", 3)):
        got, steps = literal_polling(word, k)
        examples.append({"word": word, "outlets": k,
                         "joint_success_period": steps,
                         "counts_per_outlet": [dict(c) for c in got]})
    return {"passed": True, "exhaustive_cases": cases,
            "subset_permutation_cases": permutation_cases,
            "scope": "binary words length 1..8; ternary 1..6; k 1..6; all initial ports",
            "examples": examples}


def dense_node(foreign_phase, merger_early, initial_pointer):
    """D -> {M,B}; foreign source -> M. Both sinks accept immediately.

    D receives at 0 mod 5, foreign enters M at foreign_phase mod 5.
    At each tick: boundary arrivals; eligible early drains; D polling;
    eligible late drains. These phases repeat unchanged every tick.
    B always drains early. M drains early or late, fixed for the whole run.
    All transport slots carry (source_tag, birth_tick).
    """
    slots = {"D": None, "M": None, "B": None}
    pointer = initial_pointer
    count = Counter()
    events = []
    start_state = None

    def enter(slot, tag, tick):
        assert slots[slot] is None, (slot, tick, slots)
        slots[slot] = (tag, tick)
        if 20 <= tick < 40:
            events.append({"tick": tick - 20, "event": f"{tag}->{slot}"})

    def drain(slot, tick):
        old = slots[slot]
        if old is not None and tick - old[1] >= 1:
            if 20 <= tick < 40:
                count[f"{slot}_out"] += 1
                events.append({"tick": tick - 20,
                               "event": f"{slot}->sink", "tag": old[0]})
            slots[slot] = None

    def state(tick):
        return (tick % 5, pointer, tuple(
            (name, None if slots[name] is None else
             (slots[name][0], tick - slots[name][1]))
            for name in ("D", "M", "B")))

    for t in range(40):
        if t == 20:
            start_state = state(t)
        if t % 5 == 0:
            enter("D", "upstream", t)
            if 20 <= t < 40:
                count["D_in"] += 1
        if t % 5 == foreign_phase:
            enter("M", "foreign", t)
            if 20 <= t < 40:
                count["foreign_to_M"] += 1
        drain("B", t)
        if merger_early:
            drain("M", t)
        if slots["D"] is not None and t - slots["D"][1] >= 1:
            for offset in range(2):
                dest_index = (pointer + offset) % 2
                dest = ("M", "B")[dest_index]
                if slots[dest] is None:
                    enter(dest, "D", t)
                    slots["D"] = None
                    pointer = (dest_index + 1) % 2
                    if 20 <= t < 40:
                        count[f"D_to_{dest}"] += 1
                    break
        if not merger_early:
            drain("M", t)
    assert state(40) == start_state
    count = {name: count[name] for name in
             ("D_in", "D_to_M", "D_to_B", "foreign_to_M", "M_out", "B_out")}
    assert count["D_in"] == count["D_to_M"] + count["D_to_B"]
    assert count["M_out"] == count["D_to_M"] + count["foreign_to_M"]
    assert count["M_out"] <= 20
    return {"foreign_phase": foreign_phase, "M_drains_before_D": merger_early,
            "initial_pointer": initial_pointer, "period_ticks": 20,
            "counts": count, "period_state_closes": True, "events": events}


def check_dense():
    cases = [dense_node(phase, early, pointer)
             for phase in (0, 3) for early in (False, True)
             for pointer in (0, 1)]
    for case in cases:
        c = case["counts"]
        if case["foreign_phase"] == 3 or case["M_drains_before_D"]:
            assert (c["D_to_M"], c["D_to_B"]) == (2, 2)
        else:
            assert (c["D_to_M"], c["D_to_B"]) == (0, 4)
        assert c["foreign_to_M"] == 4
    return {"passed": True, "cases": cases,
            "scope": "local periodic boundary streams, not a whole-base reachability certificate"}


def check_capacity():
    cases = 0
    for p in range(1, 21):
        for own in range(p + 1):
            for foreign in range(p - own + 1):
                a, b = Fraction(own, p), Fraction(foreign, p)
                assert a <= 1 - b
                # If a splitter receives one per tick and sends a to M,
                # all other outlets together carry 1-a, at least b.
                assert 1 - a >= b
                cases += 1
    return {"passed": True, "integer_flow_cases": cases,
            "scope": "checks algebra on feasible integer cycle counts; proof is conservation"}


def main():
    official = ("《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt")
    hashes = {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in official}
    print(json.dumps({"formal_file_sha256": hashes,
                      "material_polling": check_material_polling(),
                      "dense_nodes": check_dense(),
                      "capacity": check_capacity()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
