#!/usr/bin/env python3
"""Local rule calculations A: explicit choices, trial lists, and step loops.

These are audits of individual rule clauses, not a complete game simulator.
No claim of layout feasibility or long-run delivery is made by these checks.
"""
import itertools as it
import json
import math
from fractions import Fraction
from pathlib import Path

OUT = Path(__file__).resolve().parent


def mineral_arithmetic():
    # Recipe expansion, stopping at ores and material with no mineral source.
    recipes = {
        "源石粉末": (1, {"源矿": 1}),
        "蓝铁块": (1, {"蓝铁矿": 1}),
        "蓝铁粉末": (1, {"蓝铁块": 1}),
        "致密蓝铁粉末": (1, {"蓝铁粉末": 2, "砂叶粉末": 1}),
        "致密源石粉末": (1, {"源石粉末": 2, "砂叶粉末": 1}),
        "细磨荞花粉末": (1, {"荞花粉末": 2, "砂叶粉末": 1}),
        "钢块": (1, {"致密蓝铁粉末": 1}),
        "钢制零件": (1, {"钢块": 1}),
        "钢质瓶": (1, {"钢块": 2}),
        "高容谷地电池": (1, {"钢制零件": 10, "致密源石粉末": 15}),
        "精选荞愈胶囊": (1, {"钢质瓶": 10, "细磨荞花粉末": 10}),
    }
    bases = {"源矿": (Fraction(1), Fraction(0)),
             "蓝铁矿": (Fraction(0), Fraction(1)),
             "砂叶粉末": (Fraction(0), Fraction(0)),
             "荞花粉末": (Fraction(0), Fraction(0))}
    def expand(item):
        if item in bases:
            return bases[item]
        amount, ingredients = recipes[item]
        return tuple(sum(count * expand(kind)[axis] for kind, count in ingredients.items()) / amount
                     for axis in range(2))
    battery, capsule = expand("高容谷地电池"), expand("精选荞愈胶囊")
    ore_rates = tuple(Fraction(3, 5) * battery[i] + Fraction(11, 20) * capsule[i]
                      for i in range(2))
    return {"order": ["源矿", "蓝铁矿"],
            "battery": list(map(str, battery)), "capsule": list(map(str, capsule)),
            "required_rates": list(map(str, ore_rates)),
            "required_total": str(sum(ore_rates)),
            "warehouse_output_port_bound": 2 * (70 // 3) + 6}


def layers(downstream):
    n = len(downstream)
    vectors = set()
    valid_choices = 0
    options = [row or [None] for row in downstream]
    for choice in it.product(*options):
        found = []
        for start in range(n):
            seen = set()
            v = start
            while v is not None and v not in seen:
                seen.add(v)
                v = choice[v]
            if v is not None:
                break
            found.append(len(seen))
        if len(found) == n:
            valid_choices += 1
            vectors.add(tuple(found))
    return {"raw_choices": math.prod(len(row) for row in options),
            "fully_determined_choices": valid_choices, "vectors": sorted(vectors),
            "fully_determined_vector_count": len(vectors)}


def cyclic(order, previous, mask):
    start = 1 if previous is None else order.index(previous) + 1
    trials = [order[(start + k) % len(order)] for k in range(len(order))]
    return next((v for v in trials if mask >> v & 1), None)


def take_side(order, history, mask):
    rank = {v: k for k, v in enumerate(order)}
    trials = sorted(order, key=lambda v:
                    (0, rank[v]) if history[v] is None else (1, history[v]))
    return next((v for v in trials if mask >> v & 1), None)


def main():
    layer_cases = {
        "fork_short_long": [[1, 2], [], [3], []],
        "square_one_exit": [[1], [2], [3], [0, 4], []],
        "square_two_exits": [[1, 4], [2], [3, 4], [0], []],
        "closed_square": [[1], [2], [3], [0]],
    }
    layer_results = {name: layers(graph) for name, graph in layer_cases.items()}
    cyclic_results = {}
    nontransport_results = {}
    histories = [h for h in it.product((None, 1, 2, 3), repeat=3)
                 if len([v for v in h if v is not None]) ==
                 len({v for v in h if v is not None})]
    for order in it.permutations(range(3)):
        for previous in (None, 0, 1, 2):
            for mask in range(8):
                key = json.dumps([order, previous, mask], separators=(",", ":"))
                cyclic_results[key] = cyclic(order, previous, mask)
        for history in histories:
            for mask in range(8):
                for mode in ("keep", "clear"):
                    key = json.dumps([order, history, mask, mode], separators=(",", ":"))
                    record = history if mode == "keep" else (None,) * 3
                    nontransport_results[key] = take_side(order, record, mask)

    cooldown = {}
    for remaining in range(41):
        for mode in ("keep", "clear"):
            deadline = remaining if mode == "keep" else 0
            for step in range(1, 42):
                if step >= deadline:
                    cooldown[f"{remaining}:{mode}"] = step
                    break

    # Every item retains its source-unit identity in both offline readings.
    bridge_moves = {}
    for mode in ("keep", "clear"):
        item = {"kind": "源矿", "slot": "桥接器乙横轴", "previous_unit": "桥接器甲"}
        bridge_moves[mode] = {"item_after": dict(item),
                              "can_move_to_甲": item["previous_unit"] != "桥接器甲",
                              "can_move_to_丙": item["previous_unit"] != "桥接器丙"}

    same_start_sequence = {}
    for order in ((0, 1, 2), (2, 1, 0)):
        previous = None
        free = 0b111
        seq = []
        for _ in range(3):
            previous = cyclic(order, previous, free)
            seq.append(previous)
            free &= ~(1 << previous)
        same_start_sequence[",".join(map(str, order))] = seq

    examples = {
        "splitter_after_last_B": {mode: cyclic((0, 1, 2), 1 if mode == "keep" else None, 7)
                                  for mode in ("keep", "clear")},
        "take_side_after_A9_C7": {mode: take_side((0, 1, 2),
                                                   (9, None, 7) if mode == "keep" else (None,) * 3, 7)
                                     for mode in ("keep", "clear")},
        "same_start_success_sequence": same_start_sequence,
    }
    data = {"mineral_arithmetic": mineral_arithmetic(),
            "layers": layer_results, "cyclic": cyclic_results,
            "take_side": nontransport_results, "cooldown": cooldown,
            "bridge_moves": bridge_moves, "examples": examples,
            "counts": {"cyclic_cases": len(cyclic_results),
                       "take_side_histories": len(histories),
                       "take_side_cases": len(nontransport_results),
                       "cooldown_cases": len(cooldown)}}
    (OUT / "rule_checks_a.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: data[k] for k in ("layers", "counts", "examples")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
