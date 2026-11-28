"""从现行规则、题面复算「满速独占」。只用 Python 标准库，不写文件。"""
from collections import Counter, deque
from fractions import Fraction
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[4]
rules = (ROOT / "《明日方舟：终末地》游戏规则.txt").read_text().splitlines()
task = (ROOT / "求解任务.txt").read_text()


def rule(term):
    return next(line.strip() for line in rules if line.strip().startswith(term + "："))


def amount_item(term):
    n, item = term.strip().split()
    return int(n), item


# 每列是一种配方。各物品按「产出减消耗」带符号记账。
recipes = []
for line in rules:
    if " → " not in line:
        continue
    machine, formulas = line.strip().split("：")
    for formula in formulas.split("；"):
        materials, right = formula.split(" → ")
        result, duration = right.split("，")
        amount, product = amount_item(result)
        net = Counter({product: amount})
        for term in materials.split("＋"):
            n, item = amount_item(term)
            net[item] -= n
        recipes.append((machine, product, net, int(duration.split()[0])))

period, batteries, capsules = map(Fraction, re.search(
    r"平均每 ([\d.]+) tick 至少向仓库交付前者 ([\d.]+) 个、后者 ([\d.]+) 个", task
).groups())
targets = {"高容谷地电池": batteries / period, "精选荞愈胶囊": capsules / period}
products = sorted({product for _, product, _, _ in recipes})


def solve(recycle):
    # 每种中间品周期净产量为零，成品净产率取目标值，再指定蓝铁粉末回炼率。
    matrix = [[net[item] for _, _, net, _ in recipes] + [targets.get(item, 0)]
              for item in products]
    matrix.append([int(net["蓝铁粉末"] < 0 and product == "蓝铁块")
                   for _, product, net, _ in recipes] + [recycle])
    rows = [list(map(Fraction, row)) for row in matrix]
    size = len(recipes)
    assert len(rows) == size
    for col in range(size):
        pivot = next(i for i in range(col, size) if rows[i][col])
        rows[col], rows[pivot] = rows[pivot], rows[col]
        rows[col] = [x / rows[col][col] for x in rows[col]]
        for i in range(size):
            if i != col and rows[i][col]:
                factor = rows[i][col]
                rows[i] = [x - factor * y for x, y in zip(rows[i], rows[col])]
    rates = [row[-1] for row in rows]
    assert min(rates) >= 0
    ore = {item: -sum(net[item] * rate for (_, _, net, _), rate in zip(recipes, rates))
           for item in ("蓝铁矿", "源矿")}
    batches = Counter()
    for (machine, _, _, _), rate in zip(recipes, rates):
        batches[machine] += rate
    return ore, batches


base_ore, base_batches = solve(0)
other_ore, other_batches = solve(1)
assert base_ore == other_ore
side_x, side_y = map(int, re.search(r"(\d+)×(\d+) 格", rule("基地")).groups())
port_width = int(re.search(r"大小 (\d+)×1", rule("仓库取货口"))[1])
core_ports = int(re.search(r"取货端口（共 (\d+) 个）", rule("协议核心"))[1])
ports = side_x // port_width + side_y // port_width + core_ports
print(f"每 tick 目标 {targets}；蓝铁矿 {base_ore['蓝铁矿']}，源矿 {base_ore['源矿']}")
print(f"出口上界 {side_y // port_width}+{side_x // port_width}+{core_ports}={ports}，"
      f"平均每口 {sum(base_ore.values()) / ports} 件/tick")
assert sum(base_ore.values()) == ports
for machine in ("粉碎机", "精炼炉", "配件机", "种植机"):
    times = {duration for name, _, _, duration in recipes if name == machine}
    assert times == {1}
    yields = sorted({net[product] for name, product, net, _ in recipes if name == machine})
    print(f"{machine} 批/tick = {base_batches[machine]} + "
          f"{other_batches[machine] - base_batches[machine]}r，每批件数可取 {yields}")

# 从第 1 步开始编号。用「段」直接判收货，不用首件启动窗口。
gate = rule("物品准入口")
first_steps, next_steps = map(int, re.search(r"第 1～(\d+) 步为第 1 段、此后每 (\d+) 步", gate).groups())
lookback = int(re.search(r"前面至多 (\d+) 段", gate)[1])
low, high = map(int, re.search(r"每 5 tick 的收下上限（(\d+)～(\d+)", gate).groups())
tick = int(re.search(r"1/(\d+) tick", rule("步"))[1])
dwell = int(re.search(r"至少 (\d+) tick", rule("滞留"))[1]) * tick
window = (1 + lookback) * next_steps


def segment(step):
    if step <= first_steps:
        return 1
    return 2 + (step - first_steps - 1) // next_steps


def admit(offer_steps, limit, clear_every=None):
    occupied = deque()
    accepted = []
    for step in offer_steps:
        current = segment(step)
        while occupied and occupied[0] < current - lookback:
            occupied.popleft()
        if len(occupied) < limit:
            occupied.append(current)
            accepted.append(step)
            # 只在检验假设时用：保留货及时长，收满指定件数后在步间清掉占用。
            if clear_every and len(accepted) % clear_every == 0:
                occupied.clear()
    return accepted


print(f"单格满速间隔 {dwell} 步；十个常规段 {window} 步 = {Fraction(window, tick)} tick")
# 枚举首件在一个 tick 的所有步位，包含初建首段和后续段的全部余数。
for limit in range(low, high + 1):
    first_misses = set()
    for start in range(1, tick + 1):
        offers = list(range(start, start + 100 * dwell, dwell))
        got = set(admit(offers, limit))
        miss = next((i for i, step in enumerate(offers, 1) if step not in got), None)
        first_misses.add(miss)
        assert miss == (limit + 1 if limit < high else None)
    print(f"k={limit}，满速连续来货首次被拒的件序 {first_misses.pop() or '前 100 件全收'}")
span = {segment(s + (high - 1) * dwell) - segment(s) for s in range(1, tick + 1)}
lag = {segment(s + high * dwell) - segment(s) for s in range(1, tick + 1)}
print(f"第 5 件与首件段号差 {span}，第 6 件与首件段号差 {lag}")
offers = list(range(1, 8 * dwell + 1, dwell))
print(f"k=4 的前八个满速到货步 {offers}，正常收下 {admit(offers, 4)}，"
      f"假设每四件后重建清占用则收下 {admit(offers, 4, clear_every=4)}")
assert admit(offers, 4, clear_every=4) == offers

