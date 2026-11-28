"""从现行文件重算原矿当量、出库口数及三条不等式的局部系数。"""

from fractions import Fraction
from itertools import product
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[4]
RULES = (ROOT / "《明日方舟：终末地》游戏规则.txt").read_text(encoding="utf-8")
TASK = (ROOT / "求解任务.txt").read_text(encoding="utf-8")
ORES = ("蓝铁矿", "源矿")
PRODUCTS = ("高容谷地电池", "精选荞愈胶囊")


def item(text):
    match = re.fullmatch(r"(\d+)\s+(\S+)", text.strip())
    return int(match[1]), match[2]


def read_recipes():
    rows = RULES.split("\n配方\n")[1].strip().splitlines()
    for row in rows:
        machine, recipes = row.strip().split("：")
        for recipe in recipes.split("；"):
            inputs, output_time = recipe.strip().split(" → ")
            output, duration = output_time.split("，")
            yield machine, [item(part) for part in inputs.split("＋")], item(output), int(duration.split()[0])


def ore_values(recipes):
    # 每个向量依次计蓝铁矿、源矿。植物种子是题面给的无矿原料。
    weights = {"蓝铁矿": (1, 0), "源矿": (0, 1), "荞花种子": (0, 0), "砂叶种子": (0, 0)}
    while True:
        before = len(weights)
        for _, inputs, (amount, name), _ in recipes:
            if any(material not in weights for _, material in inputs):
                continue
            value = tuple(Fraction(sum(n * weights[m][axis] for n, m in inputs), amount)
                          for axis in range(len(ORES)))
            if name in weights:
                assert value == weights[name], (name, value, weights[name])
            else:
                weights[name] = value
        if len(weights) == before:
            break
    assert all(name in weights for _, _, (_, name), _ in recipes)
    return weights


def mine_and_ports():
    recipes = list(read_recipes())
    weights = ore_values(recipes)
    length, first, second = re.search(
        r"平均每 ([\d.]+) tick 至少向仓库交付前者 ([\d.]+) 个、后者 ([\d.]+) 个", TASK
    ).groups()
    rates = [Fraction(q) / Fraction(length) for q in (first, second)]
    for name, rate in zip(PRODUCTS, rates):
        print(f"{name}：蓝铁矿 {weights[name][0]}，源矿 {weights[name][1]}，目标 {rate} 件/tick")
    demand = [sum(q * weights[name][axis] for name, q in zip(PRODUCTS, rates)) for axis in range(len(ORES))]
    print(f"蓝铁矿 {demand[0]}，源矿 {demand[1]}，共 {sum(demand)} 件/tick")
    sides = tuple(map(int, re.search(r"基地：(\d+)×(\d+) 格", RULES).groups()))
    width = int(re.search(r"仓库取货口：大小 (\d+)×1", RULES)[1])
    core = int(re.search(r"取货端口（共 (\d+) 个）", RULES)[1])
    assert "只放在基地的左边界或下边界" in TASK
    left, bottom = [side // width for side in sides]
    print(f"出库口上限 {left} + {bottom} + {core} = {left + bottom + core}")
    assert left + bottom + core == sum(demand)
    for ore in ORES:
        consumers = [(machine, inputs, duration) for machine, inputs, _, duration in recipes
                     if any(material == ore for _, material in inputs)]
        assert len(consumers) == 1
        machine, inputs, duration = consumers[0]
        assert inputs == [(1, ore)] and duration == 1
        assert all(name != ore for _, _, (_, name), _ in recipes)
        print(f"{ore}：仅{machine}消耗，每批 {inputs[0][0]} 件，历时 {duration} tick")


def feasible_total(full, partial, twice_total):
    # 以 1 件/tick 为单位。p 个部分负载口的总量严格介于 0 和 p 之间。
    if partial == 0:
        return twice_total == 2 * full
    return 2 * full < twice_total < 2 * (full + partial)


def degree_limits(inputs, outputs, capacity):
    # 面按 0、部分、满速编码。两侧可取流量都是整数端点的区间或单点，
    # 相交且为正时，交集中必有整数或半整数。因此这项度型判定没有采样误差。
    limits = []
    for state in product(("0", "P", "F"), repeat=inputs + outputs):
        incoming, outgoing = state[:inputs], state[inputs:]
        fi, pi = incoming.count("F"), incoming.count("P")
        fo, po = outgoing.count("F"), outgoing.count("P")
        if any(feasible_total(fi, pi, t) and feasible_total(fo, po, t)
               for t in range(1, 2 * capacity + 1)):
            limits.append(((fo + po) - (fi + pi), fi - fo, po - pi, fi))
    return tuple(map(max, zip(*limits)))


if __name__ == "__main__":
    mine_and_ports()
    print("局部上限依次为：正流出口减进口、满速进口减出口、部分负载出口减进口、满速进口数")
    box_size = int(re.search(r"协议储存箱：大小 (\d+)×\d+", RULES)[1])
    # 规则 80—87 行，桥以一个定向格为单位。箱的三进三出由 90 行的边长得出。
    ports = {"带格／准入口／桥的每个定向格": (1, 1, 1), "汇流器": (3, 1, 1),
             "分流器": (1, 3, 1), "协议储存箱": (box_size, box_size, box_size)}
    limits = {name: degree_limits(*spec) for name, spec in ports.items()}
    for name, values in limits.items():
        print(f"{name}：{values}")
    assert limits["分流器"] == (2, 1, 3, 1)
    assert limits["协议储存箱"] == (2, 2, 3, 3)
    assert limits["汇流器"][:3] == limits["带格／准入口／桥的每个定向格"][:3] == (0, 0, 0)
