"""三审自写：1113 空矩形位于 (49,b)（宽 21、高 53，占列 49..69、行 b..b+52）时的场地几何。

可用格：列、行 1..69 且不在空矩形内（第 0 行、列是仓库取货口，唯一空格不能承载循环正流量）。
计数格：正式「内带缺口」的 X、Y。
  X：第 69 列第 1..68 行与第 69 行第 1..68 列中不在空矩形内的格；(69,69) 不在空矩形时另记 2（被桩占则不记）。
  Y：空矩形外与它四边正交相邻的一圈格（不含对角格；贴基地边界的一侧没有）。
两者各自计「不属于制造单位、协议核心、供电桩」的格数，同一格在 X、Y 中各计一次。
"""
from geo import pole_body, pole_range

W, H = 21, 53
RX0 = 49


def rect(b):
    return (RX0, RX0 + W - 1, b, b + H - 1)


def in_rect(c, b):
    x0, x1, y0, y1 = rect(b)
    return x0 <= c[0] <= x1 and y0 <= c[1] <= y1


def usable(c, b):
    return 1 <= c[0] <= 69 and 1 <= c[1] <= 69 and not in_rect(c, b)


def count_cells(b):
    """返回 (Xcells, Ycells, corner_counts)。Xcells、Ycells 为格列表（可有公共格）。
    corner_counts 为 True 时 (69,69) 不在空矩形内，未被桩占则 X 另加 2。"""
    X = []
    for y in range(1, 69):
        if not in_rect((69, y), b):
            X.append((69, y))
    for x in range(1, 69):
        if not in_rect((x, 69), b):
            X.append((x, 69))
    corner = not in_rect((69, 69), b)
    x0, x1, y0, y1 = rect(b)
    Y = []
    if x0 - 1 >= 1:
        Y += [(x0 - 1, y) for y in range(y0, y1 + 1)]
    if x1 + 1 <= 69:
        Y += [(x1 + 1, y) for y in range(y0, y1 + 1)]
    if y0 - 1 >= 1:
        Y += [(x, y0 - 1) for x in range(x0, x1 + 1)]
    if y1 + 1 <= 69:
        Y += [(x, y1 + 1) for x in range(x0, x1 + 1)]
    return X, Y, corner


def is_edge_pole(px, py):
    """2x2 占格含第 1 列、第 69 列、第 1 行或第 69 行。"""
    xs = {px, px + 1}
    ys = {py, py + 1}
    return bool(xs & {1, 69}) or bool(ys & {1, 69})


def edge_sides(px, py):
    xs = {px, px + 1}
    ys = {py, py + 1}
    return int(bool(xs & {1, 69})) + int(bool(ys & {1, 69}))


def pole_positions(b):
    out = []
    for px in range(1, 69):
        for py in range(1, 69):
            if all(usable(c, b) for c in pole_body(px, py)):
                out.append((px, py))
    return out


def band_ports(e):
    """一条边 70 格，空格在第 e 格（e=0,3,...,69），其余每 3 格一个仓库取货口，端口在中间格。
    返回端口所在的沿边坐标。"""
    ports = []
    pos = 0
    while pos < 70:
        if pos == e:
            pos += 1
            continue
        ports.append(pos + 1)
        pos += 3
    assert len(ports) == 23, (e, ports)
    return ports


def band_arrangements():
    """47 种共同边带：左、下两边空格各为 3k（从角起第 3k+1 格），至少一个在角格 0。
    返回 (eL, eB) 列表。"""
    es = list(range(0, 70, 3))
    return [(eL, eB) for eL in es for eB in es if eL == 0 or eB == 0]
