# 第 106 轮复核「分叉分支」：按规则第 13—16、60—74 行从格子和端口求通道（编码二的输入）。
# 坐标：x 向右、y 向上。方向 E N W S。端口记为 (格, 朝向, 种类)，种类 in=存货端口、out=取货端口、io=兼。
# 通道：U 的取货端口与 V 的存货端口隔一条边相对，且 U、V 至少一个是运输单位（规则第 16 行、端口对接）。
E, N, W, S = (1, 0), (0, 1), (-1, 0), (0, -1)
DIRS = {'E': E, 'N': N, 'W': W, 'S': S}
OPP = {E: W, W: E, N: S, S: N}


class Unit:
    def __init__(self, name, kind, cells, ports, transport):
        self.name, self.kind, self.cells, self.ports, self.transport = name, kind, set(cells), ports, transport


def belt(name, x, y, din, dout):
    assert din != dout
    return Unit(name, '传送带', [(x, y)], [((x, y), DIRS[din], 'in'), ((x, y), DIRS[dout], 'out')], True)


def splitter(name, x, y, din):
    ps = [((x, y), DIRS[din], 'in')] + [((x, y), DIRS[d], 'out') for d in 'ENWS' if d != din]
    return Unit(name, '分流器', [(x, y)], ps, True)


def converger(name, x, y, dout):
    ps = [((x, y), DIRS[dout], 'out')] + [((x, y), DIRS[d], 'in') for d in 'ENWS' if d != dout]
    return Unit(name, '汇流器', [(x, y)], ps, True)


def gate(name, x, y, din):
    d = DIRS[din]
    return Unit(name, '物品准入口', [(x, y)], [((x, y), d, 'in'), ((x, y), OPP[d], 'out')], True)


def bridge(name, x, y):
    return Unit(name, '桥接器', [(x, y)], [((x, y), DIRS[d], 'io') for d in 'ENWS'], True)


def machine(name, kind, x, y, w, h, din):
    """din：存货端口那条边的朝向；取货端口在对边。"""
    cells = [(x + i, y + j) for i in range(w) for j in range(h)]
    d = DIRS[din]
    o = OPP[d]

    def edge(dd):
        if dd == E:
            return [(x + w - 1, y + j) for j in range(h)]
        if dd == W:
            return [(x, y + j) for j in range(h)]
        if dd == N:
            return [(x + i, y + h - 1) for i in range(w)]
        return [(x + i, y) for i in range(w)]
    ps = [(c, d, 'in') for c in edge(d)] + [(c, o, 'out') for c in edge(o)]
    return Unit(name, kind, cells, ps, False)


def check_disjoint(units):
    seen = {}
    for u in units:
        for c in u.cells:
            assert c not in seen, (u.name, seen.get(c), c)
            seen[c] = u.name


def channels(units):
    """返回通道列表 [(from, to, cell, dir)]，同一对单位之间的两条来回通道分开记。"""
    check_disjoint(units)
    owner = {}
    for u in units:
        for c in u.cells:
            owner[c] = u
    out = []
    for u in units:
        for (c, d, k) in u.ports:
            if k not in ('out', 'io'):
                continue
            nc = (c[0] + d[0], c[1] + d[1])
            v = owner.get(nc)
            if v is None or v is u:
                continue
            if not (u.transport or v.transport):
                continue
            for (c2, d2, k2) in v.ports:
                if c2 == nc and d2 == OPP[d] and k2 in ('in', 'io'):
                    out.append((u.name, v.name, c, d))
    return out


# ---------- 本席自己摆的几个构型 ----------

def G1_triangle():
    """精炼炉 M（3×3，存货边朝南、取货边朝北）上方并排一个汇流器 X 和一个分流器 Y，Y 往西送进 X。"""
    return [machine('M', '精炼炉', 0, 0, 3, 3, 'S'),
            converger('X', 0, 3, 'N'),
            splitter('Y', 1, 3, 'S')]


def G2_ring():
    """四格传送带首尾相接成一个 2×2 的环。"""
    return [belt('b1', 0, 0, 'N', 'E'), belt('b2', 1, 0, 'W', 'N'),
            belt('b3', 1, 1, 'S', 'W'), belt('b4', 0, 1, 'E', 'S')]


def G5_bridges():
    """传送带 → 桥接器 X → 桥接器 Y → 传送带，X、Y 同一轴相邻，二者之间来回两条通道。"""
    return [belt('w', 0, 0, 'W', 'E'), bridge('X', 1, 0), bridge('Y', 2, 0), belt('e', 3, 0, 'W', 'E')]


def G6_split3():
    """分流器 S 三支：西支一格带进汇流器 X 的西口，北支一格带进 X 的南口，东支一格带进 X 的东口；
    X 往北送出。S 由南面一格带供货。"""
    return [belt('in', 1, 0, 'S', 'N'),
            splitter('S', 1, 1, 'S'),
            belt('bw', 0, 1, 'E', 'N'), belt('bw2', 0, 2, 'S', 'N'), belt('bw3', 0, 3, 'S', 'E'),
            belt('bn', 1, 2, 'S', 'N'),
            belt('be', 2, 1, 'W', 'N'), belt('be2', 2, 2, 'S', 'N'), belt('be3', 2, 3, 'S', 'W'),
            converger('X', 1, 3, 'N')]


def G3_seedloop():
    """种植机 P（5×5，西存东取）与采种机 Q（5×5，南存北取）：P→一格带→Q，Q→14 格带绕回 P。"""
    us = [machine('P', '种植机', 0, 0, 5, 5, 'W'), machine('Q', '采种机', 5, 5, 5, 5, 'S'),
          belt('t0', 5, 4, 'W', 'N'), belt('r0', 5, 10, 'S', 'W')]
    for i, x in enumerate(range(4, -1, -1)):
        us.append(belt('r%d' % (1 + i), x, 10, 'E', 'W'))
    us.append(belt('r6', -1, 10, 'E', 'S'))
    for i, y in enumerate(range(9, 4, -1)):
        us.append(belt('r%d' % (7 + i), -1, y, 'N', 'S'))
    us.append(belt('r12', -1, 4, 'N', 'E'))
    return us


EXAMPLES = {'G1_triangle': G1_triangle, 'G2_ring': G2_ring, 'G5_bridges': G5_bridges,
            'G6_split3': G6_split3, 'G3_seedloop': G3_seedloop}

if __name__ == '__main__':
    for k, f in EXAMPLES.items():
        us = f()
        ch = channels(us)
        print(k, len(us), 'units', len(ch), 'channels')
        for c in ch:
            print('   ', c[0], '->', c[1])
