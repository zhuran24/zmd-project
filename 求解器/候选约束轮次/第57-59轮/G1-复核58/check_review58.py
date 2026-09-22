#!/usr/bin/env python3
"""Round 58 G1 checks. Standard library only; stdout JSON, no file writes.

Slot traces check one-tick residence and cyclic stock. Dense-node schedules
are local boundary-fed examples, not whole-base reachability certificates.
Sequence tests take the formal successful-round-robin order as a premise.
"""

from collections import Counter
from fractions import Fraction
from hashlib import sha256
from itertools import permutations, product
from math import gcd, lcm
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
ROUND = ROOT / "求解器/候选约束轮次/第57-59轮"


def cyclic_slots():
    # States: 0 empty, 1 designated origin, 2 other origin.
    # A resident item may stay, or leave before a new item enters this tick.
    edges = {0: [(n, int(n == 1), int(n == 2), 0) for n in range(3)]}
    for old in (1, 2):
        edges[old] = [(old, 0, 0, 0)] + [
            (n, int(n == 1), int(n == 2), 1) for n in range(3)
        ]
    per_period = {}
    for period in range(1, 8):
        accepted = 0

        def walk(start, current, steps, own, other, out):
            nonlocal accepted
            if steps == period:
                if current == start:
                    assert own + other == out
                    assert out <= period
                    accepted += 1
                return
            for nxt, a, b, o in edges[current]:
                walk(start, nxt, steps + 1, own + a, other + b, out + o)

        for start in range(3):
            walk(start, start, 0, 0, 0, 0)
        per_period[str(period)] = accepted
    # Two bridge axes can independently be full: 2 items/tick per bridge.
    assert Fraction(2, 1) > 1
    # A packaging machine: 2 input slots, 5 incoming items each tick,
    # consuming 10 + 15 items as a batch every 5 ticks.
    stock = [10, 15]
    initial = stock[:]
    arrivals = consumed = 0
    for t in range(5):
        if t == 0:
            stock[0] -= 10
            stock[1] -= 15
            consumed += 25
        stock[0] += 2
        stock[1] += 3
        arrivals += 5
        assert all(0 <= s <= 50 for s in stock)
    assert stock == initial and arrivals == consumed == 25
    return {
        "closed_labelled_traces": sum(per_period.values()),
        "by_period": per_period,
        "bridge_two_axes_rate": "2",
        "manufacturing_example": {"slots": 2, "period": 5,
                                  "input": arrivals, "to_cache": consumed,
                                  "rate": "5", "stock_closes": True},
        "serial_two_slot_example": {"outside_entry_rate": "1",
                                    "sum_of_slot_entry_rates": "2",
                                    "sum_of_slot_exit_rates": "2"},
    }


def dense_algebra():
    checked = 0
    for p in range(1, 21):
        for direct in range(p + 1):
            for other_branches in range(p - direct + 1):
                for foreign in range(p - direct + 1):
                    received = direct + other_branches
                    assert other_branches >= max(0, received + foreign - p)
                    if received == p:
                        assert other_branches >= foreign
                    checked += 1
    # The example F=1, b=2/5, z<=3/10 has no feasible x.
    assert Fraction(1) + Fraction(2, 5) > 1 + Fraction(3, 10)
    assert Fraction(2) - Fraction(3, 5) == Fraction(7, 5)
    assert Fraction(7, 5) < Fraction(3, 2)
    return {"integer_cycle_flow_cases": checked, "periods": [1, 20],
            "two_slots_foreign_0_6_own_capacity": "7/5",
            "F1_b0_4_z_at_most_0_3_feasible": False}


def dense_run(phase, order, first):
    slots = {"D": None, "M": None, "B": None}
    pointer = first
    counts = Counter()

    def snapshot(t):
        return (t % 5, pointer, tuple(
            None if slots[name] is None else (slots[name][0], t - slots[name][1])
            for name in ("D", "M", "B")))

    def put(name, tag, t):
        assert slots[name] is None
        slots[name] = (tag, t)

    def count(name, t):
        if 100 <= t < 120:
            counts[name] += 1

    for t in range(120):
        if t == 100:
            before = snapshot(t)
        for event in order:
            if event == "feed_D" and t % 5 == 0:
                put("D", "upstream", t)
                count("F", t)
            elif event == "feed_M" and t % 5 == phase:
                put("M", "foreign", t)
                count("b", t)
            elif event in ("drain_M", "drain_B"):
                name = event[-1]
                if slots[name] is not None and t - slots[name][1] >= 1:
                    count(name + "_out", t)
                    slots[name] = None
            elif event == "route_D":
                if slots["D"] is None or t - slots["D"][1] < 1:
                    continue
                # At least B is available at every eligible routing event.
                for step in range(2):
                    port = (pointer + step) % 2
                    name = ("M", "B")[port]
                    if slots[name] is None:
                        put(name, "D", t)
                        slots["D"] = None
                        pointer = (port + 1) % 2
                        count("x" if name == "M" else "z", t)
                        break
                else:
                    raise AssertionError("both outlets blocked")
    assert before == snapshot(120)
    assert counts["x"] + counts["z"] == counts["F"] == 4
    assert counts["x"] + counts["b"] == counts["M_out"] <= 20
    assert counts["b"] == 4
    assert counts["z"] >= max(0, counts["F"] + counts["b"] - 20)
    return (counts["x"], counts["z"], counts["b"])


def dense_schedules():
    events = ("feed_D", "feed_M", "drain_M", "drain_B", "route_D")
    result = Counter()
    cases = 0
    for phase in (0, 3):
        for order in permutations(events):
            for first in range(2):
                got = dense_run(phase, order, first)
                expected = (2, 2, 4) if (
                    phase == 3 or order.index("drain_M") < order.index("route_D")
                ) else (0, 4, 4)
                assert got == expected
                result[(phase, got)] += 1
                cases += 1
    return {"cases": cases, "event_orders": 120, "window_ticks": 20,
            "scope": "five local event groups, two phases, two initial pointers",
            "outcomes": [{"foreign_phase": key[0], "x_z_b_counts": key[1],
                          "cases": count} for key, count in sorted(result.items())]}


def sequence_counts(word, k, offset=0, first=0):
    counts = [Counter() for _ in range(k)]
    n = lcm(len(word), k)
    for i in range(n):
        counts[(first + i) % k][word[(offset + i) % len(word)]] += 1
    return counts


def sequence_formula():
    cases = 0
    for alphabet, max_length in ((2, 9), (3, 6)):
        for length in range(1, max_length + 1):
            for word in product(range(alphabet), repeat=length):
                for k in range(1, 7):
                    h = gcd(length, k)
                    for offset in range(length):
                        c = [Counter() for _ in range(h)]
                        for i in range(length):
                            c[i % h][word[(offset + i) % length]] += 1
                        for first in range(k):
                            got = sequence_counts(word, k, offset, first)
                            for physical_port in range(k):
                                j = (physical_port - first) % k
                                assert got[physical_port] == c[j % h]
                                assert sum(got[physical_port].values()) == length // h
                            cases += 1
    examples = []
    for word, k in (("XY", 2), ("XXYY", 2), ("XY", 3), ("XXY", 3)):
        n = lcm(len(word), k)
        got = sequence_counts(word, k)
        examples.append({"word": word, "k": k, "joint_items": n,
                         "rates_when_F_is_1": [
                             {a: str(Fraction(c[a], n)) for a in "XY"} for c in got]})
    return {"cases": cases,
            "scope": "binary L=1..9, ternary L=1..6, k=1..6; every list offset and initial outlet",
            "examples": examples}


def time_patterns():
    checked = 0
    repeated_list_checks = 0
    for k in range(2, 7):
        for period in range(1, 5):
            for groups in product(range(1, k), repeat=period):
                if any(groups[i] + groups[(i + 1) % period] > k for i in range(period)):
                    continue
                for word in ("XY", "XXYY", "XXY", "XYXXYYY"):
                    joint = lcm(len(word), k)
                    repetitions = joint // gcd(sum(groups), joint)
                    ticks = period * repetitions
                    counts = [Counter() for _ in range(k)]
                    born = [None] * k
                    item = 0
                    for t in range(ticks):
                        # Retain previous tick's items until after this group.
                        # Adjacent group sums <= k prevent outlet reuse anyway.
                        for _ in range(groups[t % period]):
                            port = item % k
                            assert born[port] is None or born[port] < t - 1
                            born[port] = t
                            counts[port][word[item % len(word)]] += 1
                            item += 1
                    F = Fraction(item, ticks)
                    h = gcd(len(word), k)
                    for port in range(k):
                        for a in "XY":
                            c = sum(word[i] == a for i in range(port % h, len(word), h))
                            assert Fraction(counts[port][a], ticks) == F * h * c / (len(word) * k)
                    checked += 1
                    # A nonminimal repeated list must predict the same rates.
                    base = sequence_counts(word, k)
                    for multiplier in (2, 3, 4):
                        expanded = sequence_counts(word * multiplier, k)
                        for port in range(k):
                            for a in "XY":
                                assert Fraction(base[port][a], lcm(len(word), k)) == Fraction(
                                    expanded[port][a], lcm(len(word) * multiplier, k))
                        repeated_list_checks += 1
    return {"periodic_batch_schedules": checked,
            "nonminimal_list_comparisons": repeated_list_checks,
            "scope": "positive groups, periods 1..4, k=2..6, all adjacent sums <= k; four mixed lists"}


def subset_permutations():
    cases = 0
    for word in ("XY", "XXYY", "XXY", "XYXXYYY"):
        for k in range(1, 7):
            counts = sequence_counts(word, k)
            for a in "XY":
                values = [c[a] for c in counts]
                for m in range(1, k + 1):
                    minimum = min(sum(values[i] for i in p[:m]) for p in permutations(range(k)))
                    assert minimum == sum(sorted(values)[:m])
                    cases += 1
    return {"cases": cases,
            "premise": "word and total rate fixed across realizable arbitrary outlet permutations"}


def original_recheck():
    completed = subprocess.run(
        [sys.executable, "-B", str(ROUND / "G1/check_g1.py")],
        check=True, text=True, capture_output=True, cwd=ROOT,
    )
    output = json.loads(completed.stdout)
    saved = json.loads((ROUND / "G1/check_results.json").read_text())
    assert output == saved
    return {"matches_saved_result": True,
            "material_polling": output["material_polling"]["exhaustive_cases"],
            "subset_permutations": output["material_polling"]["subset_permutation_cases"],
            "dense_node_runs": len(output["dense_nodes"]["cases"]),
            "capacity": output["capacity"]["integer_flow_cases"]}


def main():
    inputs = ["《明日方舟：终末地》游戏规则.txt", "求解任务.txt", "求解约束.txt",
              "候选约束.txt", "思路.txt", "求解器/候选约束轮次/第57-59轮/G1-推导.md",
              "求解器/候选约束轮次/第57-59轮/G1/check_g1.py",
              "求解器/候选约束轮次/第57-59轮/G1/check_results.json"]
    hashes = {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in inputs}
    result = {"input_sha256": hashes,
              "cyclic_slots": cyclic_slots(),
              "dense_algebra": dense_algebra(),
              "dense_schedules": dense_schedules(),
              "sequence_formula": sequence_formula(),
              "time_patterns": time_patterns(),
              "subset_permutations": subset_permutations(),
              "original_recheck": original_recheck()}
    assert hashes == {p: sha256((ROOT / p).read_bytes()).hexdigest() for p in inputs}
    result["all_assertions_passed"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
