"""从现行规则和题面复算。只读输入，结果写到标准输出。"""
import re
from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from math import ceil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RULES = (ROOT / "《明日方舟：终末地》游戏规则.txt").read_text(encoding="utf-8")
TASK = (ROOT / "求解任务.txt").read_text(encoding="utf-8")


@dataclass
class Recipe:
    machine: str
    ingredients: dict[str, int]
    output: str
    yield_count: int
    duration: int


def read_recipes():
    recipes = []
    for line in RULES.split("\n配方\n")[1].strip().splitlines():
        machine, options = line.strip().split("：")
        for option in options.split("；"):
            materials, result = option.split(" → ")
            ingredients = {}
            for part in materials.split("＋"):
                count, item = part.split()
                ingredients[item] = int(count)
            quantity, output, duration = re.fullmatch(r"(\d+) (\S+)，(\d+) tick", result).groups()
            recipes.append(Recipe(machine, ingredients, output, int(quantity), int(duration)))
    return recipes


def batch_rates(recipes, target, recycle):
    # 逐种产品列「生产 − 配方消耗 = 净交付」。两个外部矿种没有生产配方。
    # 用 r 指定回炼批率，解除蓝铁块与蓝铁粉末之间的一维自由度。
    matrix = []
    for item in sorted({recipe.output for recipe in recipes}):
        row = [
            (recipe.yield_count if recipe.output == item else 0) - recipe.ingredients.get(item, 0)
            for recipe in recipes
        ]
        matrix.append(row + [target.get(item, 0)])
    matrix.append([int(r.machine == "精炼炉" and "蓝铁粉末" in r.ingredients)
                   for r in recipes] + [recycle])

    equations = [[Fraction(value) for value in row] for row in matrix]
    n = len(recipes)
    assert len(equations) == n
    for col in range(n):
        pivot = next(i for i in range(col, n) if equations[i][col])
        equations[col], equations[pivot] = equations[pivot], equations[col]
        divisor = equations[col][col]
        equations[col] = [v / divisor for v in equations[col]]
        for i, row in enumerate(equations):
            if i != col and (factor := row[col]):
                equations[i] = [a - factor * b for a, b in zip(row, equations[col])]
    solution = [row[-1] for row in equations]
    for row in matrix:
        assert sum(a * b for a, b in zip(row[:-1], solution)) == row[-1]
    return solution


def totals(recipes, solution, weighted):
    result = defaultdict(Fraction)
    for recipe, rate in zip(recipes, solution):
        result[recipe.machine] += rate * (recipe.duration if weighted else 1)
    return result


def check_grinder(recipes, capacity):
    common = set.intersection(*(set(r.ingredients) for r in recipes))
    assert common == {"砂叶粉末"}
    mains = set.union(*(set(r.ingredients) for r in recipes)) - common
    powders = sorted(common | mains)
    empty = ("", 0)
    slots = [empty] + [(item, n) for item in powders for n in range(1, capacity + 1)]
    states = starts_into_lock = receipts_into_lock = starts_in_lock = exits = 0

    def locked(state):
        return all(item in mains for item, _ in state) and state[0][0] != state[1][0]

    for state in product(slots, repeat=2):
        if state[0] != empty and state[0][0] == state[1][0]:
            continue
        states += 1
        was_locked = locked(state)
        stock = dict(state)
        for item in powders:
            for i, (held, n) in enumerate(state):
                if n == capacity or (held and held != item):
                    continue
                if not held and item in stock:
                    continue
                after = list(state)
                after[i] = (item, n + 1)
                if not was_locked and locked(after):
                    assert state[i] == empty and state[1 - i][0] in mains - {item}
                    receipts_into_lock += 1
                exits += was_locked and not locked(after)
        for recipe in recipes:
            if any(stock.get(item, 0) < n for item, n in recipe.ingredients.items()):
                continue
            after = []
            for item, n in state:
                left = n - recipe.ingredients.get(item, 0)
                after.append((item, left) if left else empty)
            starts_into_lock += not was_locked and locked(after)
            starts_in_lock += was_locked
            exits += was_locked and not locked(after)

    p, m = len(powders), len(mains)
    assert states == 1 + 2 * p * capacity + p * (p - 1) * capacity**2
    assert receipts_into_lock == 2 * m * capacity * (m - 1)
    assert starts_into_lock == starts_in_lock == exits == 0
    print(f"研磨机（{p} 种配方原料，两格有序）：状态 {states}，收一件首次入锁 {receipts_into_lock}，"
          f"开一批首次入锁 {starts_into_lock}，锁内可开批 {starts_in_lock}，离锁转移 {exits}")


def main():
    recipes = read_recipes()
    machines = list(dict.fromkeys(r.machine for r in recipes))
    slots_per_machine = {}
    for count, names in re.findall(r"含 (\d+) 个存货物品格；包括(.+)", RULES):
        slots_per_machine.update({name: int(count) for name in names.split("、")})
    assert set(slots_per_machine) == set(machines)
    assert all(len(r.ingredients) == slots_per_machine[r.machine] for r in recipes)
    capacity = int(re.search(r"存货/取货物品格：制造单位的物品格（上限 (\d+)）", RULES)[1])
    period, batteries, capsules = re.search(
        r"平均每 ([\d.]+) tick 至少向仓库交付前者 ([\d.]+) 个、后者 ([\d.]+) 个", TASK
    ).groups()
    target = {"高容谷地电池": Fraction(batteries) / Fraction(period),
              "精选荞愈胶囊": Fraction(capsules) / Fraction(period)}
    # 固定同一系数矩阵，以 r=0、1 两个右端求截距和斜率。
    base = batch_rates(recipes, target, 0)
    unit = batch_rates(recipes, target, 1)
    rates = totals(recipes, base, weighted=False)
    work = totals(recipes, base, weighted=True)
    unit_work = totals(recipes, unit, weighted=True)
    print(f"{len(machines)} 种机型，{len(recipes)} 个配方，所有配方的原料种数均等于该机存货格数")
    print("机型  基准批/tick  基准加工台时/tick  回炼每增1批/tick增加的台时/tick  基准台数下限")
    for m in machines:
        print(m, rates[m], work[m], unit_work[m] - work[m], ceil(work[m]))
    check_grinder([r for r in recipes if r.machine == "研磨机"], capacity)
    window, lo, hi = map(int, re.search(r"每 (\d+) tick 的收下上限（(\d+)～(\d+)", RULES).groups())
    print(f"格容量 {capacity}，准入口每 {window} tick 限额范围 {lo} 至 {hi}")


if __name__ == "__main__":
    main()
