#!/usr/bin/env python3
"""复核94B 编码甲：在 70x70 显式格上枚举左、下两边的仓库取货口排布，核内带与矿石格相关的静态事实。

只用快照规则：仓库取货口 3x1、长边贴基地边界、向内长边中点一个取货端口；只放左、下边界；
取货口配置要求放满（46 个），边带排布给出每边恰留 1 格。这里用回溯直接铺 46 个 3x1，不预设排布公式。
坐标以左下角格为 (0,0)，x 向右为列，y 向上为行。
"""
import json, itertools, sys

N = 70
LEFT = [(0, y) for y in range(N)]
BOTTOM = [(x, 0) for x in range(N)]
EDGE = sorted(set(LEFT) | set(BOTTOM))  # 139 格


def tilings():
    order = [(0, y) for y in range(N - 1, -1, -1)] + [(x, 0) for x in range(1, N)]
    res = []

    def rec(i, covered, ports, free):
        while i < len(order) and order[i] in covered:
            i += 1
        if i == len(order):
            if len(ports) == 46:
                res.append((list(ports), free))
            return
        c = order[i]
        if free is None:
            rec(i + 1, covered | {c}, ports, c)
        x, y = c
        if x == 0:  # 竖放：c 为最上格，向下延伸
            cells = [(0, y), (0, y - 1), (0, y - 2)]
            if y - 2 >= 0 and not any(cc in covered for cc in cells):
                rec(i + 1, covered | set(cells), ports + [("V", cells)], free)
        if y == 0:  # 横放：c 为最左格，向右延伸
            cells = [(x, 0), (x + 1, 0), (x + 2, 0)]
            if x + 2 < N and not any(cc in covered for cc in cells):
                rec(i + 1, covered | set(cells), ports + [("H", cells)], free)

    sys.setrecursionlimit(10000)
    rec(0, frozenset(), [], None)
    return res


def ore_of(port):
    kind, cells = port
    mid = cells[1]
    return (1, mid[1]) if kind == "V" else (mid[0], 1)


def main():
    T = tilings()
    out = {"tilings": len(T), "bands": []}
    inner = [(1, y) for y in range(1, N)] + [(x, 1) for x in range(2, N)]
    inner_set = set(inner)
    shapes = [(3, 3), (5, 5), (6, 4), (4, 6), (9, 9)]
    all_ok = True
    worst = {"max_body_cover": 0, "max_pole_cover": 0, "max_pair_cover": 0,
             "ore_on_69": 0, "ring_ore_a3b3": 0, "ring_ore_a2_max": 0, "ring_ore_b2_max": 0}
    for ports, free in T:
        ores = [ore_of(p) for p in ports]
        ore_set = set(ores)
        body = set()
        for _, cells in ports:
            body |= set(cells)
        ok = len(ore_set) == 46 and ore_set <= inner_set and len(body) == 138
        ore69 = sum(1 for (x, y) in ores if x == N - 1 or y == N - 1)
        blocked = body | ore_set

        def placements(w, h):
            for x0 in range(0, N - w + 1):
                for y0 in range(0, N - h + 1):
                    cells = {(x0 + i, y0 + j) for i in range(w) for j in range(h)}
                    if cells & blocked:
                        continue
                    cov = len(cells & inner_set)
                    if cov:
                        yield cells, cov
        bodies = [pc for s in shapes for pc in placements(*s)]
        poles = list(placements(2, 2))
        max_body = max([c for _, c in bodies], default=0)
        max_pole = max([c for _, c in poles], default=0)
        # 两个互不重叠的边长 >=3 单位合计覆盖内带多少格
        max_pair = max_body
        for (c1, v1), (c2, v2) in itertools.combinations(bodies, 2):
            if not (c1 & c2):
                max_pair = max(max_pair, len((c1 | c2) & inner_set))
        # 矩形周圈与矿石格：a,b>=2，短边>=6，枚举左下角 (a,b) in {2,3}x{2..} 及 {2..}x{2,3}
        ring_a3b3 = 0
        ring_a2 = 0
        ring_b2 = 0
        for a in range(2, 6):
            for b in range(2, 6):
                for W in range(6, N - a + 1):
                    for H in range(6, N - b + 1):
                        if a > 3 and b > 3:
                            continue
                        rect_cells_left = [(a - 1, y) for y in range(b, b + H)]
                        rect_cells_bot = [(x, b - 1) for x in range(a, a + W)]
                        ring = set(rect_cells_left) | set(rect_cells_bot)
                        # 上、右两侧圈不可能碰第 1 列/第 1 行
                        k = len(ring & ore_set)
                        if a >= 3 and b >= 3:
                            ring_a3b3 = max(ring_a3b3, k)
                        if a == 2:
                            # 矩形离带：a=2 时 m<=e(a-1)，m 为左带取货端口落在行 b..b+H-1 的个数
                            e = 1 if b + H - 1 == N - 1 else 2
                            m = sum(1 for (x, y) in ores if x == 1 and b <= y < b + H)
                            if m <= e * (a - 1) and not (b == 2):  # (2,2) 由角区排除
                                ring_a2 = max(ring_a2, len(set(rect_cells_left) & ore_set))
                        if b == 2:
                            e = 1 if a + W - 1 == N - 1 else 2
                            m = sum(1 for (x, y) in ores if y == 1 and a <= x < a + W)
                            if m <= e * (b - 1) and not (a == 2):
                                ring_b2 = max(ring_b2, len(set(rect_cells_bot) & ore_set))
        rec = {"free": free, "ore_left_rows": sorted(y for (x, y) in ores if x == 1 and y >= 1 and (x, y) in ore_set and (1, y) == (x, y)),
               "max_body_cover": max_body, "max_pole_cover": max_pole, "max_pair_cover": max_pair,
               "ore_on_69": ore69, "ring_ore_a3b3": ring_a3b3, "ring_ore_a2": ring_a2, "ring_ore_b2": ring_b2,
               "corner_pole_possible": not ({(1, 1), (1, 2), (2, 1), (2, 2)} & blocked)}
        ok = ok and max_pair <= 3 and max_pole <= 2 and ore69 == 0 and ring_a3b3 == 0 and not rec["corner_pole_possible"]
        all_ok &= ok
        rec["ok"] = ok
        out["bands"].append(rec)
        worst["max_body_cover"] = max(worst["max_body_cover"], max_body)
        worst["max_pole_cover"] = max(worst["max_pole_cover"], max_pole)
        worst["max_pair_cover"] = max(worst["max_pair_cover"], max_pair)
        worst["ore_on_69"] = max(worst["ore_on_69"], ore69)
        worst["ring_ore_a3b3"] = max(worst["ring_ore_a3b3"], ring_a3b3)
        worst["ring_ore_a2_max"] = max(worst["ring_ore_a2_max"], ring_a2)
        worst["ring_ore_b2_max"] = max(worst["ring_ore_b2_max"], ring_b2)
    out["worst"] = worst
    out["all_ok"] = all_ok
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "band_a.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({"tilings": len(T), "worst": worst, "all_ok": all_ok}, ensure_ascii=False))


if __name__ == "__main__":
    main()
