"""三审自写：47 种左、下边带共同排布上的内带计数（第 81 轮 C 组「任意增配的运输与面积方向预算」）。

坐标左下角 (0,0)。按正式「边带排布」：左带（第 0 列）、下带（第 0 行）各 23 个 3×1 仓库取货口，
各留 1 个空格，空格在从角起第 3k+1 格（k=0…23），至少一带的空格在角格 (0,0)；两带共享角格，
所以 139 格里恰有 1 格 q 不是仓库取货口。取货端口在长边中点，正对的内侧格是矿石首运输格。

核三件事：
 1. 46 个边带矿石格共 92 个沿边切向方向中，能被非运输单位的端口对上的至多几个（条文说至少 90 个不能）；
    判据：切向邻格起沿边方向要有一个至少 3 格深、不含矿石格、不出基地、不压第 0 列/行的单位位置。
 2. 内带 I（第 1 列第 1…69 行、第 1 行第 2…69 列，137 格）去掉 46 个矿石格剩 91 格，
    非运输大单位（边长都 ≥3 的机身、协议储存箱、协议核心）至多能占其中几格（条文说 3）。
 3. 2×2 供电桩至多占 I 几格（条文说 2）。
"""
import json, pathlib

OUT = pathlib.Path(__file__).with_name("out") / "band.json"
N = 70


def arrangements():
    res = []
    positions = [3 * k + 1 for k in range(24)]  # 从角起第几格（1 = 角格）
    for side_corner in ("左", "下"):
        for p in positions:
            if side_corner == "下" and p == 1:
                continue  # 两带都在角格的情形已算在「左在角」里
            # 左带空格位置 pl、下带空格位置 pb（1 = 角格）
            pl, pb = (1, p) if side_corner == "左" else (p, 1)
            res.append((pl, pb))
    return res


def build(pl, pb):
    """返回 取货口占格集合、矿石格列表、q。"""
    occ, ores = set(), []
    # 左带：第 0 列 70 格，行 0..69；位置 i（1 起）对应行 i-1
    # 下带：第 0 行 70 格，列 0..69
    def fill(line_cells, empty_pos):
        cells = [c for i, c in enumerate(line_cells, 1) if i != empty_pos]
        assert len(cells) == 69
        return cells
    left = [(0, y) for y in range(N)]
    bottom = [(x, 0) for x in range(N)]
    # 角格属于哪一带：空格不在角的那一带占用角格；两带空格都在角则角格为 q
    if pl == 1 and pb == 1:
        lc, bc = fill(left, 1), fill(bottom, 1)
    elif pl == 1:
        lc = fill(left, 1)           # 左带不占角
        bc = fill(bottom, pb)        # 下带占角
    else:
        bc = fill(bottom, 1)
        lc = fill(left, pl)
    for line, horiz in ((lc, False), (bc, True)):
        assert len(line) == 69, len(line)
        # 连续 69 格被切成 23 段 3 格（空格把 70 格切成两段，各段长须是 3 的倍数）
        line = sorted(line, key=lambda c: c[0] if horiz else c[1])
        segs, cur = [], [line[0]]
        for c in line[1:]:
            prev = cur[-1]
            if (c[0] - prev[0] if horiz else c[1] - prev[1]) == 1:
                cur.append(c)
            else:
                segs.append(cur); cur = [c]
        segs.append(cur)
        for s in segs:
            assert len(s) % 3 == 0, (pl, pb, len(s))
            for j in range(0, len(s), 3):
                unit = s[j:j + 3]
                for c in unit:
                    assert c not in occ
                    occ.add(c)
                mid = unit[1]
                ores.append(((1, mid[1]), "左") if not horiz else ((mid[0], 1), "下"))
    allband = set(left) | set(bottom)
    q = allband - occ
    assert len(q) == 1 and len(occ) == 138 and len(ores) == 46
    assert len({c for c, _ in ores}) == 46
    return occ, ores, q.pop()


def main():
    arr = arrangements()
    assert len(arr) == 47
    out = []
    I = {(1, y) for y in range(1, N)} | {(x, 1) for x in range(2, N)}
    assert len(I) == 137
    worst_free, worst_body, worst_pole = 0, 0, 0
    for pl, pb in arr:
        occ, ores, q = build(pl, pb)
        oreset = {c for c, _ in ores}
        assert oreset <= I

        def ok_cell(c):
            return 0 < c[0] < N and 0 < c[1] < N and c not in oreset
        # 1. 切向方向能否对上非运输端口：左带矿石格 (1,y) 的上、下方向；下带 (x,1) 的左、右方向。
        #    对得上须有一个单位占切向邻格、沿该方向至少 3 格深、横向 3 格宽（含邻格），全在第 1…69 列行、
        #    不含矿石格；更大的单位含这样的 3×3 子块，所以只查 3×3。
        free_dirs = 0
        for (x, y), side in ores:
            dirs = [(0, 1), (0, -1)] if side == "左" else [(1, 0), (-1, 0)]
            for dx, dy in dirs:
                ok = False
                depth_cells = [(x + dx * s, y + dy * s) for s in range(1, 4)]
                px, py = abs(dy), abs(dx)
                for off in (-2, -1, 0):
                    block = [(cx + px * (off + t), cy + py * (off + t)) for (cx, cy) in depth_cells for t in range(3)]
                    if all(ok_cell(c) for c in block):
                        ok = True
                if ok:
                    free_dirs += 1
        # 2. 大单位（边长都 ≥3）至多占 U 几格：枚举全部 3×3 块（更大单位含 3×3 子块，占 U 的格
        #    只会被更少的放法取到；这里直接枚举所有与 I 相交、不含矿石格、不进第 0 列/行的矩形）
        best_body = 0
        for w in range(3, 10):
            for h in range(3, 10):
                for x0 in range(1, N - w + 1):
                    for y0 in range(1, N - h + 1):
                        if x0 > 1 and y0 > 1:
                            continue
                        cells = [(x0 + i, y0 + j) for i in range(w) for j in range(h)]
                        if any(c in oreset for c in cells):
                            continue
                        best_body = max(best_body, sum(1 for c in cells if c in I))
        # 直接求：所有不含矿石格、贴第 1 列或第 1 行的 3×3 块覆盖的 I 格之并
        union = set()
        for x0 in range(1, N - 2):
            for y0 in range(1, N - 2):
                if x0 > 1 and y0 > 1:
                    continue
                cells = [(x0 + i, y0 + j) for i in range(3) for j in range(3)]
                if any(c in oreset for c in cells):
                    continue
                union |= {c for c in cells if c in I}
        # 3. 2×2 桩至多占 I 几格
        best_pole = 0
        for x0 in range(1, N - 1):
            for y0 in range(1, N - 1):
                cells = [(x0 + i, y0 + j) for i in range(2) for j in range(2)]
                if any(c in oreset for c in cells):
                    continue
                best_pole = max(best_pole, sum(1 for c in cells if c in I))
        out.append({"左空格位": pl, "下空格位": pb, "q": q, "可对接切向方向": free_dirs,
                    "大单位最多占U格(单块)": best_body, "大单位可达U格之并": len(union), "桩最多占I格": best_pole})
        worst_free = max(worst_free, free_dirs)
        worst_body = max(worst_body, len(union))
        worst_pole = max(worst_pole, best_pole)
    summary = {"排布数": len(arr), "可对接切向方向最多": worst_free, "不能对接的切向方向至少": 92 - worst_free,
               "大单位可达U格之并最多": worst_body, "桩最多占I格": worst_pole}
    OUT.write_text(json.dumps({"汇总": summary, "逐排布": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
