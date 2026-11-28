"""生成可直接交给场地模式的 UTF-8 JSON。只使用 Python 标准库。"""
import argparse
import json
import random
import sys

SEED = 20261128
SIDES = ("上", "右", "下", "左")
OPPOSITE = dict(zip(SIDES, ("下", "左", "上", "右")))
MACHINES = ("粉碎机", "精炼炉", "配件机", "塑形机", "采种机", "种植机", "研磨机", "封装机", "灌装机")


def piece(u, x, y, *kind):
    return {"号": u, "种类": list(kind), "位置": [x, y]}


def core_keys(axis):
    return [(d, i) for d in SIDES for i in ((1, 4, 7) if d in axis else range(1, 8))]


def example(pieces, rng=None):
    core = next((p for p in pieces if p["种类"][0] == "协议核心"), None)
    keys = core_keys(core["种类"][1]) if core else []
    ranks = list(range(len(keys)))
    if rng is not None:
        if rng.randrange(2):
            ranks = [rng.randrange(4) for _ in keys]
        else:
            rng.shuffle(ranks)
    table = [[k, r] for k, r in zip(keys, ranks)]
    if rng is not None:
        rng.shuffle(table)
    return {"摆件": pieces, "核心先后": table}


def dense(rng):
    # 双路从左侧取货口出发，在桥上相交、在右端汇合；下支连核心。
    # 两行间距、叉点、机器、额外支路和直线里的准入口逐张抽取。
    pieces = []
    serial = rng.randrange(1, 5000)

    def add(x, y, *kind):
        nonlocal serial
        serial += rng.randrange(4, 12)
        pieces.append(piece(serial, x, y, *kind))

    def belt(x, y, a, b, gates=True):
        if gates and OPPOSITE[a] == b and rng.randrange(6) == 0:
            add(x, y, "物品准入口", b)
        else:
            add(x, y, "传送带", a, b)

    y = rng.randint(11, 35)
    upper = y - rng.randint(3, 6)
    split = rng.randint(5, 9)
    bridge = split + rng.randint(3, 6)
    join = bridge + rng.randint(3, 6)
    machine = join + rng.randint(3, 5)
    name = rng.choice(MACHINES)
    width, height = ((3, 3) if name in MACHINES[:4] else
                     (5, 5) if name in MACHINES[4:6] else (4, 6))
    axis = rng.choice(("上下", "左右"))
    add(0, y - 1, "仓库取货口", "右")
    for x in range(1, machine):
        if x == split:
            add(x, y, "分流器", "左")
        elif x == bridge:
            add(x, y, "桥接器", rng.choice(SIDES))
        elif x == join:
            add(x, y, "汇流器", "右")
        else:
            belt(x, y, "左", "右", x not in (1, machine - 1, bridge - 1, bridge + 1))
    add(machine, y - 1, "制造", name, "右")
    end = machine + width + rng.randint(2, 5)
    for x in range(machine + width, end):
        belt(x, y, "左", "右", x != end - 1)
    add(end, y - 1, "协议储存箱", "右")

    for j in range(upper + 1, y):
        belt(split, j, "下", "上")
        belt(join, j, "上", "下")
    belt(split, upper, "下", "右")
    belt(join, upper, "左", "下")
    for x in range(split + 1, join):
        if x == bridge:
            if axis == "上下":
                add(x, upper, "汇流器", "右")
            else:
                add(x, upper, "分流器", "左")
        else:
            belt(x, upper, "左", "右")
    if rng.randrange(2):
        belt(split, y + 1, "上", "左")
        belt(split - 1, y + 1, "右", "左", False)
        add(split - 4, y + 1, "协议储存箱", "左")

    top = y + rng.randint(5, 8)
    add(bridge - 4, top, "协议核心", axis)
    # 左右型在上边收货、右边出货，上下型把这两段反过来。
    a, b = ("上", "下") if axis == "左右" else ("下", "上")
    for j in range(upper + 1, top):
        if j != y:
            belt(bridge, j, a, b, j not in (top - 1, y - 1, y + 1))
    a, b = ("左", "右") if axis == "左右" else ("右", "左")
    length = rng.randint(2, 5)
    for x in range(bridge + 5, bridge + 5 + length):
        belt(x, top + 4, a, b, False)
    add(bridge + 5 + length, top + 3, "协议储存箱", b)

    # 在同一条取货边上再接一或两路，使同类先后及其并列也能改变历史。
    for n in rng.sample([1, 7], rng.randint(1, 2)):
        if axis == "上下":
            belt(bridge - 4 + n, top - 1, "下", "上", False)
        else:
            belt(bridge + 5, top + n, "左", "右", False)

    # 上路外侧靠近机器的桩可供电。另一种放法留下整张图断电。
    if rng.randrange(4):
        add(machine + width - 2, y - 4, "供电桩")
    else:
        add(end + 9, top + height, "供电桩")
    return pieces


def footprint(kind):
    """占地的宽、高（照 几何与端口.lean 的「摆件.大小」）。"""
    k = kind[0]
    if k == "协议储存箱":
        return 3, 3
    if k == "制造":
        if kind[1] in MACHINES[:4]:
            return 3, 3
        if kind[1] in MACHINES[4:6]:
            return 5, 5
        return (6, 4) if kind[2] in ("上", "下") else (4, 6)
    if k == "协议核心":
        return 9, 9
    if k == "仓库取货口":
        return (3, 1) if kind[1] in ("上", "下") else (1, 3)
    if k == "供电桩":
        return 2, 2
    return 1, 1


STEP = {"上": (0, -1), "右": (1, 0), "下": (0, 1), "左": (-1, 0)}


def packed(rng):
    # 密铺：在一小块地里先随机落几件大的，再让几条「走线」贴着它们乱走，最后往空格里随机补运输单位。
    # 不照着任何「该怎么接」来摆，所以端口对端口、端口对侧面、同类端口相对、带子成环和断头都会大量出现。
    w, h = rng.randint(10, 18), rng.randint(10, 18)
    ox = rng.choice((0, 70 - w, rng.randint(0, 70 - w)))
    oy = rng.choice((0, 70 - h, rng.randint(0, 70 - h)))
    pieces, used = [], {}
    serial = rng.randrange(1, 5000)

    def fits(x, y, kind):
        fw, fh = footprint(kind)
        cells = [(x + i, y + j) for i in range(fw) for j in range(fh)]
        if any(not (ox <= cx < ox + w and oy <= cy < oy + h) or (cx, cy) in used for cx, cy in cells):
            return None
        if kind[0] == "协议核心" and any(p["种类"][0] == "协议核心" for p in pieces):
            return None
        if kind[0] == "仓库取货口":
            d = kind[1]
            if not {"上": y + fh == 70, "右": x == 0, "下": y == 0, "左": x + fw == 70}[d]:
                return None
        return cells

    def put(x, y, *kind):
        nonlocal serial
        cells = fits(x, y, kind)
        if cells is None:
            return False
        serial += rng.randrange(4, 12)
        pieces.append(piece(serial, x, y, *kind))
        for c in cells:
            used[c] = serial
        return True

    def anywhere(*kind, tries=30):
        for _ in range(tries):
            if put(rng.randrange(ox, ox + w), rng.randrange(oy, oy + h), *kind):
                return True
        return False

    if rng.randrange(3) == 0:
        anywhere("协议核心", rng.choice(("上下", "左右")))
    for _ in range(rng.randint(2, 5)):
        anywhere("制造", rng.choice(MACHINES), rng.choice(SIDES))
    for _ in range(rng.randint(1, 3)):
        anywhere("协议储存箱", rng.choice(SIDES))
    for _ in range(rng.randint(0, 3)):
        anywhere("供电桩")
    for d, ok in (("右", ox == 0), ("左", ox + w == 70), ("下", oy == 0), ("上", oy + h == 70)):
        for _ in range(rng.randint(0, 2) if ok else 0):
            fw, fh = footprint(("仓库取货口", d))
            x = {"右": 0, "左": 70 - fw}.get(d, rng.randrange(ox, ox + w))
            y = {"下": 0, "上": 70 - fh}.get(d, rng.randrange(oy, oy + h))
            put(x, y, "仓库取货口", d)

    def walk(x, y, a, steps):
        # a 是当前这格的存货边；每走一格随机定取货边，下一格的存货边就是它的对边
        for _ in range(steps):
            b = rng.choice([s for s in SIDES if s != a])
            r = rng.random()
            if r < 0.66:
                done = put(x, y, "传送带", a, b)
            elif r < 0.75:
                done = put(x, y, "分流器", a)
            elif r < 0.84:
                done = put(x, y, "汇流器", b)
            elif r < 0.92:
                done = put(x, y, "桥接器", rng.choice(SIDES))
            else:
                b = OPPOSITE[a]
                done = put(x, y, "物品准入口", b)
            if not done:
                return
            x, y, a = x + STEP[b][0], y + STEP[b][1], OPPOSITE[b]

    for _ in range(rng.randint(6, 14)):
        walk(rng.randrange(ox, ox + w), rng.randrange(oy, oy + h), rng.choice(SIDES), rng.randint(3, 25))
    for _ in range(rng.randint(10, 60)):
        kind = rng.choice((("传送带",), ("传送带",), ("分流器",), ("汇流器",), ("桥接器",), ("物品准入口",)))[0]
        if kind == "传送带":
            a, b = rng.sample(SIDES, 2)
            anywhere(kind, a, b, tries=3)
        else:
            anywhere(kind, rng.choice(SIDES), tries=3)
    return pieces


def generate(count, orders, rng, base_of=None):
    base_of = base_of or dense
    for _ in range(count):
        base = base_of(rng)
        for _ in range(orders):
            layout = rng.sample(base, len(base))
            yield example(layout, rng)
        # 每张图再配一份几何或占号冲突，原有的顺序、冲突件的插入位置也随机。
        layout = rng.sample(base, len(base))
        old = rng.choice(base)
        u = max(p["号"] for p in base) + 10
        free = next((x, y) for x in range(70) for y in range(70)
                    if not any(p["位置"][0] <= x < p["位置"][0] + footprint(p["种类"])[0]
                               and p["位置"][1] <= y < p["位置"][1] + footprint(p["种类"])[1] for p in base))
        bad = rng.choice([piece(old["号"], *free, "传送带", "上", "下"),      # 重号
                          piece(u, *old["位置"], "传送带", "上", "下"),      # 重叠
                          piece(u, 69, 69, "协议储存箱", "右"),             # 越界
                          piece(u, *free, "传送带", "右", "右")])           # 带子两条边相同
        layout.insert(rng.randrange(len(layout) + 1), bad)
        yield example(layout, rng)


def document(examples):
    return '{"版本":1,"场地":[\n' + ",\n".join(
        json.dumps(x, ensure_ascii=False, separators=(",", ":")) for x in examples) + "\n]}\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--场地数", type=int, default=12)
    parser.add_argument("--排列数", type=int, default=3)
    parser.add_argument("--模式", choices=("模板", "密铺"), default="模板")
    parser.add_argument("--种子", type=int, default=SEED)
    options = parser.parse_args()
    if options.场地数 < 0 or options.排列数 < 1:
        parser.error("场地数须非负，排列数须为正")
    base_of = packed if options.模式 == "密铺" else dense
    sys.stdout.write(document(generate(options.场地数, options.排列数, random.Random(options.种子), base_of)))
