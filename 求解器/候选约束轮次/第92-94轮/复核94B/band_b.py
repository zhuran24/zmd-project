#!/usr/bin/env python3
"""复核94B 编码乙：把左、下两边看成一条 139 格的折线（从 (0,69) 向下到 (0,0) 再向右到 (69,0)），
用一维位置算术枚举空格位置，再用游程推内带覆盖，不做二维放置搜索。与 band_a.py 互相核对。
"""
import json, sys

N = 70
L = 2 * N - 1  # 139


def cell(s):  # 折线位置 s=1..139 -> 格
    return (0, N - s) if s <= N else (s - N, 0)


def bands():
    out = []
    for p in range(1, L + 1):
        if (p - 1) % 3 or (L - p) % 3:
            continue
        starts = list(range(1, p, 3)) + list(range(p + 1, L + 1, 3))
        # 三格不得跨过角（位置 69,70,71 同时出现即弯折）
        if any(s <= N - 1 and s + 2 >= N + 1 for s in starts):
            continue
        mids = [s + 1 for s in starts]
        ores = []
        for m in mids:
            x, y = cell(m)
            ores.append((1, y) if x == 0 and y > 0 else (x, 1))
        out.append((p, ores))
    return out


def runs(free_idx, lo, hi):
    """lo..hi 内不在 free_idx 集合里的格视为被占，返回连续可用段 [(start,len)]"""
    res, cur = [], None
    for i in range(lo, hi + 1):
        if i in free_idx:
            cur = (cur[0], cur[1] + 1) if cur else (i, 1)
        else:
            if cur:
                res.append(cur)
            cur = None
    if cur:
        res.append(cur)
    return res


def main():
    B = bands()
    rep = {"bands": len(B), "rows": []}
    worst = dict(max_body_cover=0, max_pole_cover=0, ore_on_69=0, ring_ore_a3b3=0, ring_ore_a2_max=0, ring_ore_b2_max=0, corner_pole=0)
    for p, ores in B:
        col1 = {y for (x, y) in ores if x == 1}
        row1 = {x for (x, y) in ores if y == 1}
        # 第 1 列可用行（1..69 中非矿石格），第 1 行可用列（1..69 中非矿石格，(1,1) 与第 1 列共用）
        free_col = {y for y in range(1, N) if y not in col1}
        free_row = {x for x in range(1, N) if x not in row1 and not (x == 1 and 1 in col1)}
        rc = runs(free_col, 1, N - 1)
        rr = runs(free_row, 1, N - 1)
        # 边长 >=3 的单位：贴第 1 列时覆盖其全部高度 h>=3 的连续可用行；贴第 1 行同理；
        # 同时贴两者须含 (1,1)，覆盖 h+w-1；这里取各段长度 >=3 时的段长上界（单位最小边 3）
        cov = 0
        for (s, l) in rc:
            if l >= 3:
                cov = max(cov, l if s > 1 else l)
        for (s, l) in rr:
            if l >= 3:
                cov = max(cov, l)
        # 角上同时贴两边：需要 (1,1),(1,2),(1,3) 与 (2,1),(3,1) 都可用
        corner_both = all(y in free_col for y in (1, 2, 3)) and all(x in free_row for x in (1, 2, 3))
        if corner_both:
            cov = max(cov, 5)
        # 段长 >=3 的段在单位最小边 3 时实际只容 3（下面断言段长 <=3）
        long_runs = [l for (_, l) in rc + rr if l >= 3]
        body_cover = min(cov, 3) if all(l <= 3 for l in long_runs) and not corner_both else cov
        # 两个单位同时覆盖内带：需要两段长度 >=3
        two_bodies = len(long_runs) >= 2
        # 供电桩 2x2：贴第 1 列覆盖 2 格；角上 [1,2]x[1,2] 覆盖 3 格，需要 (1,1),(1,2),(2,1) 都非矿石
        corner_pole = (1 in free_col) and (2 in free_col) and (2 in free_row)
        pole_cover = 3 if corner_pole else 2
        ore69 = sum(1 for (x, y) in ores if x == N - 1 or y == N - 1)
        # 周圈：a>=3 时左圈在第 a-1>=2 列，b>=3 时下圈在第 b-1>=2 行，矿石格只在第 1 列/第 1 行
        ring_a3b3 = sum(1 for (x, y) in ores if x >= 2 and y >= 2)
        # a=2：左圈第 1 列 b..b+H-1；矩形离带 m<=e，m 即该段矿石数；所以圈内矿石至多 e<=2
        best_a2 = 0
        for b in range(3, N - 5):
            for H in range(6, N - b + 1):
                e = 1 if b + H - 1 == N - 1 else 2
                m = sum(1 for y in col1 if b <= y < b + H)
                if m <= e:
                    best_a2 = max(best_a2, m)
        best_b2 = 0
        for a in range(3, N - 5):
            for W in range(6, N - a + 1):
                e = 1 if a + W - 1 == N - 1 else 2
                m = sum(1 for x in row1 if a <= x < a + W and (x, 1) in set(ores))
                if m <= e:
                    best_b2 = max(best_b2, m)
        row = dict(p=p, free_cell=cell(p), long_runs=long_runs, body_cover=body_cover, two_bodies=two_bodies,
                   pole_cover=pole_cover, ore69=ore69, ring_a3b3=ring_a3b3, ring_a2=best_a2, ring_b2=best_b2)
        rep["rows"].append(row)
        worst["max_body_cover"] = max(worst["max_body_cover"], body_cover + (3 if two_bodies else 0))
        worst["max_pole_cover"] = max(worst["max_pole_cover"], pole_cover)
        worst["ore_on_69"] = max(worst["ore_on_69"], ore69)
        worst["ring_ore_a3b3"] = max(worst["ring_ore_a3b3"], ring_a3b3)
        worst["ring_ore_a2_max"] = max(worst["ring_ore_a2_max"], best_a2)
        worst["ring_ore_b2_max"] = max(worst["ring_ore_b2_max"], best_b2)
        worst["corner_pole"] = max(worst["corner_pole"], int(corner_pole))
    rep["worst"] = worst
    json.dump(rep, open(sys.argv[1] if len(sys.argv) > 1 else "band_b.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({"bands": len(B), "worst": worst}, ensure_ascii=False))


if __name__ == "__main__":
    main()
