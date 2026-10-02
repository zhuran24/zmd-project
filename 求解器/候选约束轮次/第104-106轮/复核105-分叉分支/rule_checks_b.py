#!/usr/bin/env python3
"""Local rule calculations B: bounded integer relations and successor walks.

For fully determined layers, a decreasing chosen edge gives an acyclic path,
so layers lie in 1..number_of_components. A closed graph having no such vector
does NOT certify a game layout as impossible; its unspecified case stays open.
"""
from itertools import permutations, product
import json
import math
from fractions import Fraction
from pathlib import Path

OUT = Path(__file__).resolve().parent


def conservation_arithmetic():
    # Solve mineral weights using every recipe, including the reversible iron
    # refinement and both seed/plant reproduction cycles. No expansion routine.
    reactions = [
        ({"源矿": 1}, {"源石粉末": 1}),
        ({"蓝铁块": 1}, {"蓝铁粉末": 1}),
        ({"荞花": 1}, {"荞花粉末": 2}),
        ({"砂叶": 1}, {"砂叶粉末": 3}),
        ({"蓝铁矿": 1}, {"蓝铁块": 1}),
        ({"致密蓝铁粉末": 1}, {"钢块": 1}),
        ({"蓝铁粉末": 1}, {"蓝铁块": 1}),
        ({"蓝铁粉末": 2, "砂叶粉末": 1}, {"致密蓝铁粉末": 1}),
        ({"源石粉末": 2, "砂叶粉末": 1}, {"致密源石粉末": 1}),
        ({"荞花粉末": 2, "砂叶粉末": 1}, {"细磨荞花粉末": 1}),
        ({"钢块": 2}, {"钢质瓶": 1}),
        ({"钢块": 1}, {"钢制零件": 1}),
        ({"荞花种子": 1}, {"荞花": 1}),
        ({"砂叶种子": 1}, {"砂叶": 1}),
        ({"荞花": 1}, {"荞花种子": 2}),
        ({"砂叶": 1}, {"砂叶种子": 2}),
        ({"钢制零件": 10, "致密源石粉末": 15}, {"高容谷地电池": 1}),
        ({"钢质瓶": 10, "细磨荞花粉末": 10}, {"精选荞愈胶囊": 1}),
    ]
    kinds = sorted({kind for reaction in reactions for side in reaction for kind in side})
    solutions = []
    for ore in ("源矿", "蓝铁矿"):
        matrix = [[Fraction(products.get(k, 0) - ingredients.get(k, 0)) for k in kinds]
                  + [Fraction(0)] for ingredients, products in reactions]
        for given in ("源矿", "蓝铁矿"):
            matrix.append([Fraction(k == given) for k in kinds] + [Fraction(given == ore)])
        row = 0
        pivots = []
        for col in range(len(kinds)):
            candidate = next((r for r in range(row, len(matrix)) if matrix[r][col]), None)
            if candidate is None:
                continue
            matrix[row], matrix[candidate] = matrix[candidate], matrix[row]
            scale = matrix[row][col]
            matrix[row] = [v / scale for v in matrix[row]]
            for r in range(len(matrix)):
                if r != row:
                    scale = matrix[r][col]
                    matrix[r] = [a - scale * b for a, b in zip(matrix[r], matrix[row])]
            pivots.append(col)
            row += 1
        assert len(pivots) == len(kinds)
        assert all(any(r[:-1]) or r[-1] == 0 for r in matrix)
        solutions.append({kinds[c]: matrix[r][-1] for r, c in enumerate(pivots)})
    battery = [solution["高容谷地电池"] for solution in solutions]
    capsule = [solution["精选荞愈胶囊"] for solution in solutions]
    rates = [(18 * battery[i] + Fraction(33, 2) * capsule[i]) / 30 for i in range(2)]
    maximum_on_one_edge = max(n for n in range(71) if 3 * n <= 70)
    return {"order": ["源矿", "蓝铁矿"],
            "battery": [str(v) for v in battery], "capsule": [str(v) for v in capsule],
            "required_rates": [str(v) for v in rates],
            "required_total": str(sum(rates)),
            "warehouse_output_port_bound": maximum_on_one_edge * 2 + 6}


def integer_layers(graph):
    n = len(graph)
    solutions = []
    selectors = 0
    for values in product(range(1, n + 1), repeat=n):
        multiplicity = 1
        for v, targets in enumerate(graph):
            if not targets:
                if values[v] != 1:
                    multiplicity = 0
                    break
            else:
                choices = sum(values[v] == values[w] + 1 for w in targets)
                multiplicity *= choices
                if choices == 0:
                    break
        if multiplicity:
            solutions.append(values)
            selectors += multiplicity
    return {"raw_choices": math.prod(max(1, len(row)) for row in graph),
            "fully_determined_choices": selectors, "vectors": sorted(solutions),
            "fully_determined_vector_count": len(solutions)}


def walk_cycle(order, last, possible):
    following = dict(zip(order, order[1:] + order[:1]))
    candidate = order[1] if last is None else following[last]
    for _ in order:
        if candidate in possible:
            return candidate
        candidate = following[candidate]
    return None


def oldest(order, record, possible):
    never = [channel for channel in order if record[channel] is None]
    used = {channel: time for channel, time in enumerate(record) if time is not None}
    while never:
        candidate = never.pop(0)
        if candidate in possible:
            return candidate
    while used:
        candidate = min(used, key=used.get)
        if candidate in possible:
            return candidate
        del used[candidate]
    return None


def main():
    graphs = [
        ("fork_short_long", [[1, 2], [], [3], []]),
        ("square_one_exit", [[1], [2], [3], [0, 4], []]),
        ("square_two_exits", [[1, 4], [2], [3, 4], [0], []]),
        ("closed_square", [[1], [2], [3], [0]]),
    ]
    layer_results = {name: integer_layers(graph) for name, graph in graphs}
    histories = set()
    for length in range(4):
        for channels in permutations(range(3), length):
            for times in permutations(range(1, 4), length):
                history = [None, None, None]
                for channel, time in zip(channels, times):
                    history[channel] = time
                histories.add(tuple(history))
    cyclic_results = {}
    take_results = {}
    for order in permutations((0, 1, 2)):
        for mask in range(8):
            possible = {v for v in range(3) if (1 << v) & mask}
            for previous in (None, 0, 1, 2):
                key = json.dumps([order, previous, mask], separators=(",", ":"))
                cyclic_results[key] = walk_cycle(order, previous, possible)
            for history in histories:
                for mode in ("keep", "clear"):
                    key = json.dumps([order, history, mask, mode], separators=(",", ":"))
                    record = history if mode == "keep" else (None, None, None)
                    take_results[key] = oldest(order, record, possible)
    cooldown = {f"{r}:{mode}": max(1, r) if mode == "keep" else 1
                for r in range(41) for mode in ("keep", "clear")}
    bridge = {}
    for mode in ("keep", "clear"):
        bridge[mode] = {
            "item_after": {"kind": "源矿", "slot": "桥接器乙横轴", "previous_unit": "桥接器甲"},
            "can_move_to_甲": False, "can_move_to_丙": True,
        }
    sequences = {}
    for order in ((0, 1, 2), (2, 1, 0)):
        successor = {order[i]: order[(i + 1) % 3] for i in range(3)}
        first = order[1]
        sequences[",".join(map(str, order))] = [first, successor[first], successor[successor[first]]]
    examples = {
        "splitter_after_last_B": {"keep": walk_cycle((0, 1, 2), 1, {0, 1, 2}),
                                   "clear": walk_cycle((0, 1, 2), None, {0, 1, 2})},
        "take_side_after_A9_C7": {"keep": oldest((0, 1, 2), (9, None, 7), {0, 1, 2}),
                                  "clear": oldest((0, 1, 2), (None, None, None), {0, 1, 2})},
        "same_start_success_sequence": sequences,
    }
    data = {"mineral_arithmetic": conservation_arithmetic(),
            "layers": layer_results, "cyclic": cyclic_results,
            "take_side": take_results, "cooldown": cooldown,
            "bridge_moves": bridge, "examples": examples,
            "counts": {"cyclic_cases": len(cyclic_results),
                       "take_side_histories": len(histories),
                       "take_side_cases": len(take_results),
                       "cooldown_cases": len(cooldown)}}
    (OUT / "rule_checks_b.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: data[k] for k in ("layers", "counts", "examples")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
