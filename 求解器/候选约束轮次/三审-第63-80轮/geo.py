"""三审自写几何：制造单位、协议核心、供电桩的占格与端口邻格。

坐标：基地左下角格为 (0,0)，x 向右、y 向上；单位用左下角格 (x,y) 与宽 w、高 h 表示。
端口轴：'LR' 表示左右两边为端口边，'BT' 表示上下两边为端口边。
小制造单位 3x3、中制造单位 5x5 两种端口轴都有；大制造单位 6x4 只有上下长边为端口边（BT），
4x6 只有左右长边为端口边（LR）。供电桩 2x2，左下角 (px,py)，供电范围为
列 px-5..px+6、行 py-5..py+6（以桩中心为原点的 12x12）。
"""

KINDS = {
    # 名称: (类别, w, h, 端口轴)
    'S_LR': ('S', 3, 3, 'LR'),
    'S_BT': ('S', 3, 3, 'BT'),
    'M_LR': ('M', 5, 5, 'LR'),
    'M_BT': ('M', 5, 5, 'BT'),
    'L_BT': ('L', 6, 4, 'BT'),   # 6 宽 4 高，上下长边为端口边
    'L_LR': ('L', 4, 6, 'LR'),   # 4 宽 6 高，左右长边为端口边
}
WEIGHT = {'S': 2, 'M': 3, 'L': 3}


def body(x, y, w, h):
    return [(x + i, y + j) for i in range(w) for j in range(h)]


def port_sides(x, y, w, h, axis):
    """返回两条端口边外侧的邻格列表 (sideA, sideB)。LR：左、右；BT：下、上。"""
    if axis == 'LR':
        return ([(x - 1, y + j) for j in range(h)], [(x + w, y + j) for j in range(h)])
    else:
        return ([(x + i, y - 1) for i in range(w)], [(x + i, y + h) for i in range(w)])


def pole_body(px, py):
    return [(px, py), (px + 1, py), (px, py + 1), (px + 1, py + 1)]


def pole_range(px, py):
    """供电范围的格区间 [x0,x1]x[y0,y1]（闭区间）。"""
    return (px - 5, px + 6, py - 5, py + 6)


def rect_intersects(x, y, w, h, rng):
    x0, x1, y0, y1 = rng
    return x <= x1 and x + w - 1 >= x0 and y <= y1 and y + h - 1 >= y0
