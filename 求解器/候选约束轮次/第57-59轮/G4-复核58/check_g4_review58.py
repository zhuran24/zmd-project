#!/usr/bin/env python3
"""第 58 轮 G4 独立复算：分数配方守恒、整股划分、误料占格。

只读取六份列明的输入，唯一输出为本脚本目录中的 复算结果.json。
运行：python 求解器/候选约束轮次/第57-59轮/G4-复核58/check_g4_review58.py
"""

from fractions import Fraction as F
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EXPECTED_HASHES = {
    "《明日方舟：终末地》游戏规则.txt": "4f04de50b2f743aec1da903f00f0f89f92f1aeba60eb4513320b71d0ee0a57fd",
    "求解任务.txt": "1630ca1febec79b324aa3afb110be2d3330298e266c68b06415c3d1516108bac",
    "求解约束.txt": "f6503e6c1568ae5ef05bb2dfac249df0a6a371bb24342e23ba77fafc813648b6",
    "候选约束.txt": "a0ac3f9c82f371132b7de29fe47e4c6c587904680bc2786523de0c825fd5efd9",
    "思路.txt": "95d2af723613bfd61c325ab2fafd89bcd060f099d2a2172a1d79b206c3995cee",
    "求解器/候选约束轮次/第57-59轮/G4-推导.md": "26e5c5d3d7a21752ba47ed06a60212f00ecea9674e2006724861ab26902f9390",
}
MACHINES = ["粉碎机", "精炼炉", "研磨机", "塑形机", "配件机", "种植机", "采种机", "封装机", "灌装机"]


def parse_terms(text):
    terms = {}
    for term in text.strip().split("＋"):
        match = re.fullmatch(r"\s*(\d+)\s+(\S+)\s*", term)
        assert match, term
        amount, item = match.groups()
        assert item not in terms
        terms[item] = int(amount)
    return terms


def vector(n, index=None, value=1):
    result = [F(0)] * n
    if index is not None:
        result[index] = F(value)
    return result


def add(a, b, factor=1):
    return [x + factor * y for x, y in zip(a, b, strict=True)]


def sparse(expression, labels):
    return {label: str(value) for label, value in zip(labels, expression, strict=True) if value}


def main():
    inputs = {}
    for name, expected in EXPECTED_HASHES.items():
        raw = (ROOT / name).read_bytes()
        actual = sha256(raw).hexdigest()
        assert actual == expected, f"输入已变化，需重新复核：{name}: {actual}"
        inputs[name] = actual

    rule_lines = (ROOT / "《明日方舟：终末地》游戏规则.txt").read_text().splitlines()
    recipes = []
    slots = {}
    current_slots = None
    machine = None
    for line_number, raw in enumerate(rule_lines, 1):
        line = raw.strip()
        match = re.search(r"(\d+) 个存货物品格", line)
        if match:
            current_slots = int(match.group(1))
        if line in MACHINES:
            machine = line
            if line_number < 78:
                slots[machine] = current_slots
        if "→" in line:
            left, right = line.split("→")
            right, duration = right.split("，")
            recipes.append({
                "machine": machine, "line": line_number,
                "inputs": parse_terms(left), "outputs": parse_terms(right),
                "ticks": int(duration.strip().split()[0]),
            })
    assert len(recipes) == 18 and set(slots) == set(MACHINES)
    items = sorted(set().union(*(set(r[side]) for r in recipes for side in ("inputs", "outputs"))))
    assert len(items) == 19
    ore_items = {"蓝铁矿", "源矿"}
    targets = {"高容谷地电池": F(3, 5), "精选荞愈胶囊": F(11, 20)}
    balanced_items = [item for item in items if item not in ore_items]
    sink_items = [item for item in balanced_items if item not in targets]
    reverse = next(i for i, r in enumerate(recipes)
                   if r["machine"] == "精炼炉" and r["inputs"] == {"蓝铁粉末": 1})
    # 每种中间物品的净入库率均先放宽为独立非负数。
    # q 是回炼配方批次率，不预先删掉正式规则第 89 行的配方。
    labels = ["常数"] + [f"入库:{item}" for item in sink_items] + ["回炼批次率:q"]
    width = len(labels)
    unknown = [i for i in range(len(recipes)) if i != reverse]
    assert len(unknown) == len(balanced_items) == 17

    def net(item, recipe):
        return recipe["outputs"].get(item, 0) - recipe["inputs"].get(item, 0)

    matrix = []
    for item in balanced_items:
        rhs = vector(width)
        if item in targets:
            rhs[0] = targets[item]
        else:
            rhs[labels.index(f"入库:{item}")] = F(1)
        rhs[-1] = -F(net(item, recipes[reverse]))
        matrix.append([F(net(item, recipes[i])) for i in unknown] + rhs)

    # 用精确有理数解 17 条守恒式；全部右端变量一起消元。
    size = len(unknown)
    for col in range(size):
        pivot = next(row for row in range(col, size) if matrix[row][col])
        matrix[col], matrix[pivot] = matrix[pivot], matrix[col]
        divisor = matrix[col][col]
        matrix[col] = [entry / divisor for entry in matrix[col]]
        for row in range(size):
            if row != col and matrix[row][col]:
                matrix[row] = add(matrix[row], matrix[col], -matrix[row][col])
    rates = {i: matrix[col][size:] for col, i in enumerate(unknown)}
    rates[reverse] = vector(width, width - 1)
    assert all(coefficient >= 0 for rate in rates.values() for coefficient in rate)

    # 将解逐系数代回原始配方，验证每种物品的守恒残差严格为零。
    for item in balanced_items:
        balance = vector(width)
        for i, recipe in enumerate(recipes):
            balance = add(balance, rates[i], net(item, recipe))
        expected = vector(width)
        if item in targets:
            expected[0] = targets[item]
        else:
            expected[labels.index(f"入库:{item}")] = F(1)
        assert balance == expected, item

    ore_supply = {}
    for item in sorted(ore_items):
        demand = vector(width)
        for i, recipe in enumerate(recipes):
            demand = add(demand, rates[i], -net(item, recipe))
        assert all(coefficient >= 0 for coefficient in demand)
        ore_supply[item] = demand
    assert ore_supply["蓝铁矿"][0] == 34 and ore_supply["源矿"][0] == 18

    workloads = {name: vector(width) for name in MACHINES}
    batches = {name: vector(width) for name in MACHINES}
    for i, recipe in enumerate(recipes):
        name = recipe["machine"]
        workloads[name] = add(workloads[name], rates[i], recipe["ticks"])
        batches[name] = add(batches[name], rates[i])
    expected_bounds = [68, 51, 32, 6, 6, 32, 16, 3, 3]
    capacity_results = []
    for name, expected in zip(MACHINES, expected_bounds, strict=True):
        expression = workloads[name]
        assert all(coefficient >= 0 for coefficient in expression)
        base = expression[0]
        lower = -(-base.numerator // base.denominator)
        assert lower == expected
        capacity_results.append({
            "machine": name,
            "minimum_batches_per_tick": str(batches[name][0]),
            "minimum_busy_ticks_per_tick": str(base),
            "minimum_uncontaminated_machines": lower,
            "full_workload_expression": sparse(expression, labels),
        })
    assert sum(expected_bounds) == 217

    # 种植机只有 32 台：其忙碌时间下界已为 32，所有正系数增量只能为零。
    planting = workloads["种植机"]
    assert planting[0] == 32
    forced_zero = {j for j in range(1, width) if planting[j] > 0}
    plant_results = []
    for plant in ("荞花", "砂叶"):
        selected = {}
        for role, recipe_machine, side in (("种植", "种植机", "outputs"),
                                          ("采种", "采种机", "inputs"),
                                          ("粉碎", "粉碎机", "inputs")):
            i = next(i for i, r in enumerate(recipes)
                     if r["machine"] == recipe_machine and plant in r[side])
            expr = rates[i]
            assert all(value == 0 or j in forced_zero for j, value in enumerate(expr) if j)
            selected[role] = expr[0]
        planted, seed, crushed = (selected[k] for k in ("种植", "采种", "粉碎"))
        assert planted == 2 * seed == 2 * crushed and planted.denominator == 1
        for item in (plant, plant + "种子"):
            assert labels.index(f"入库:{item}") in forced_zero
        n = int(planted)
        partitions = [(k, n - k) for k in range(n + 1)]
        matches = [(a, b) for a, b in partitions if a == seed and b == crushed]
        assert not matches
        period = 20
        assert all((period * value).denominator == 1 for value in selected.values())
        assert (period * seed) % period == 10
        plant_results.append({
            "plant": plant,
            "exact_batches_per_tick": {key: str(value) for key, value in selected.items()},
            "whole_stream_partitions_checked": len(partitions),
            "whole_stream_matches": matches,
            "period_20_batches": {key: int(period * value) for key, value in selected.items()},
            "nearest_integer_split": [n // 2, n // 2 + 1],
        })

    # 对现行物品逐一放入误料，并把其他存货格的可选物品及空格穷举。
    # 每个非空格放 50 件，给制造最有利的数量；所有单项用量均 <= 50。
    # 再加一个不在清单中的物品，代表其他任何从未作为配方输入的物品。
    contamination_results = []
    for name in MACHINES:
        own_recipes = [r for r in recipes if r["machine"] == name]
        legal_inputs = set().union(*(set(r["inputs"]) for r in own_recipes))
        wrong_items = [item for item in items if item not in legal_inputs] + ["未列物品"]
        checked = 0
        enabled = []
        seen_storage = set()
        for wrong in wrong_items:
            for wrong_slot in range(slots[name]):
                for other in product([None] + items + ["未列物品"], repeat=slots[name] - 1):
                    storage = list(other)
                    storage.insert(wrong_slot, wrong)
                    nonempty = [item for item in storage if item is not None]
                    if len(nonempty) != len(set(nonempty)):
                        continue  # 规则第 13 行：制造单位同种物品不能分放多格。
                    state = tuple(storage)
                    if state in seen_storage:
                        continue
                    seen_storage.add(state)
                    checked += 1
                    stock = {item: 50 for item in nonempty}
                    for recipe in own_recipes:
                        assert max(recipe["inputs"].values()) <= 50
                        if all(stock.get(item, 0) >= amount for item, amount in recipe["inputs"].items()):
                            enabled.append({"storage": storage, "recipe_line": recipe["line"]})
        assert not enabled, (name, enabled)
        contamination_results.append({
            "machine": name, "input_slots": slots[name],
            "recipe_input_kind_counts": [len(r["inputs"]) for r in own_recipes],
            "wrong_item_classes": len(wrong_items), "storage_assignments_checked": checked,
            "new_batch_counterexamples": enabled,
        })

    results = {
        "status": "PASS",
        "input_sha256": inputs,
        "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "method": "Fraction 精确消元；17 条物品守恒式，18 个配方，15 种中间物品非负净入库率与非负回炼率；逐系数代回校验。",
        "recipe_rates": [{**r, "minimum_batches_per_tick": str(rates[i][0]),
                          "full_rate_expression": sparse(rates[i], labels)}
                         for i, r in enumerate(recipes)],
        "ore_supply": {name: sparse(value, labels) for name, value in ore_supply.items()},
        "machine_capacity": capacity_results,
        "planting_32_forces_zero": [labels[j] for j in sorted(forced_zero)],
        "plant_partitions": plant_results,
        "contamination": contamination_results,
        "total_contaminated_storage_assignments": sum(r["storage_assignments_checked"] for r in contamination_results),
        "scope": "复算配方守恒、台数、整股划分和开批前存货格条件；通道图的一般论证、误料不可离开和周期推论见报告。",
    }
    # 输入在执行期间发生变动也不能留下误标为 PASS 的结果。
    for name, expected in EXPECTED_HASHES.items():
        assert sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    out = HERE / "复算结果.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "recipes": len(recipes),
                      "machine_bounds": expected_bounds,
                      "whole_stream_partitions": sum(r["whole_stream_partitions_checked"] for r in plant_results),
                      "contaminated_storage_assignments": results["total_contaminated_storage_assignments"],
                      "result": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
