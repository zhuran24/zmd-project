# 复核80：单桩局部放松的几何枚举（从规则尺寸重写，不导入推导席脚本）
# 坐标：桩身占列、行 5..6，供电范围为列、行 0..11（桩中心为格点 (6,6)，12x12）。
# 机型：小 3x3（端口轴左右或上下）、中 5x5（左右或上下）、大 6x4（端口在上下长边）、4x6（端口在左右长边）。
# 普通模型：除桩身外不设其他禁区；占边模型：机身与端口邻格都只能在 x<=6。

POLE = {(5, 5), (5, 6), (6, 5), (6, 6)}
TYPES = [
    # (类别, 宽, 高, 端口轴, 权重)  端口轴 'H' 表示端口边为左右两边，'V' 表示上下两边
    ("S", 3, 3, "H", 2),
    ("S", 3, 3, "V", 2),
    ("M", 5, 5, "H", 3),
    ("M", 5, 5, "V", 3),
    ("L", 6, 4, "V", 3),
    ("L", 4, 6, "H", 3),
]


def body(x, y, w, h):
    return [(x + i, y + j) for i in range(w) for j in range(h)]


def sides(x, y, w, h, axis):
    if axis == "H":
        return [[(x - 1, y + j) for j in range(h)], [(x + w, y + j) for j in range(h)]]
    return [[(x + i, y - 1) for i in range(w)], [(x + i, y + h) for i in range(w)]]


def enumerate_options(wall=False, lo=-8, hi=20):
    """独立于推导席的写法：在大方框里逐锚点试，按实际格集合判断与范围相交。"""
    opts = []
    rng = {(i, j) for i in range(12) for j in range(12)}
    for (cat, w, h, axis, wt) in TYPES:
        for x in range(lo, hi):
            for y in range(lo, hi):
                cells = body(x, y, w, h)
                cs = set(cells)
                if not (cs & rng):
                    continue
                if cs & POLE:
                    continue
                if wall and any(cx > 6 for (cx, cy) in cells):
                    continue
                sd = []
                ok = True
                for side in sides(x, y, w, h, axis):
                    valid = [g for g in side if g not in POLE and (not wall or g[0] <= 6)]
                    if not valid:
                        ok = False
                        break
                    sd.append(valid)
                if not ok:
                    continue
                opts.append(dict(cat=cat, w=w, h=h, axis=axis, wt=wt, x=x, y=y,
                                 cells=cells, sides=sd))
    return opts


if __name__ == "__main__":
    for wall in (False, True):
        o = enumerate_options(wall)
        from collections import Counter
        c = Counter((d["cat"], d["w"], d["h"], d["axis"]) for d in o)
        print("wall" if wall else "general", len(o), dict(c))
