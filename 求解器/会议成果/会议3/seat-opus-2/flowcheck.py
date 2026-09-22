#!/usr/bin/env python3
"""固定布局上查全幺模版不分物品流是否可行（带上下界的循环流 → 最大流）。
输入：aggflow.py --out 写出的 json（含 units/core/transport/bridge_cells）。
输出：可行与否；不可行时给最小割（超级源一侧的结点集合）在格上的样子。
全幺模版：逐台只给流入/流出上下限，按机型给合计；桥接器按每格容量 2、两轴合并（放松）。
"""
import json, sys
import networkx as nx

CAP = 20
INF = 10 ** 7
DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]
OPP = [2, 3, 0, 1]
N = 70

BOUNDS = {  # type: (in_lo, in_hi, out_lo, out_hi)
    'crush': (20, 20, 20, 60), 'refine': (20, 20, 20, 20), 'parts': (20, 20, 20, 20),
    'plant': (20, 20, 20, 20), 'seed': (20, 20, 40, 40), 'pack': (100, 100, 4, 4),
    'grind': (0, 60, 0, 20), 'mold': (0, 40, 0, 20), 'fill': (0, 80, 0, 4),
}
TOT = {  # type: (tot_in_lo, tot_out_lo)
    'crush': (1360, 1890), 'refine': (1020, 1020), 'parts': (120, 120), 'plant': (640, 640),
    'seed': (320, 640), 'pack': (300, 12), 'grind': (1890, 630), 'mold': (220, 110), 'fill': (220, 11),
}


def edge_cells(ax, ay, w, h, side):
    if side == 0:
        return [(ax + w - 1, y) for y in range(ay, ay + h)]
    if side == 1:
        return [(x, ay + h - 1) for x in range(ax, ax + w)]
    if side == 2:
        return [(ax, y) for y in range(ay, ay + h)]
    return [(x, ay) for x in range(ax, ax + w)]


def ore_cells():
    out = []
    for j in range(23):
        out.append((1, 2 + 3 * j))
        out.append((2 + 3 * j, 1))
    return out


def build(res):
    T = set(map(tuple, res['transport']))
    B = set(map(tuple, res.get('bridge_cells', [])))
    arcs = []  # (u, v, lo, hi)
    for c in T:
        arcs.append((('ci', c), ('co', c), 0, CAP * (2 if c in B else 1)))
        for d in range(4):
            n = (c[0] + DIRS[d][0], c[1] + DIRS[d][1])
            if n in T:
                arcs.append((('co', c), ('ci', n), 0, CAP))
    bad = []
    for i, (k, ax, ay, w, h, s) in enumerate(res['units']):
        so = OPP[s]
        for (ex, ey) in edge_cells(ax, ay, w, h, s):
            c = (ex + DIRS[s][0], ey + DIRS[s][1])
            if c in T:
                arcs.append((('co', c), ('mi', i), 0, CAP))
        for (ex, ey) in edge_cells(ax, ay, w, h, so):
            c = (ex + DIRS[so][0], ey + DIRS[so][1])
            if c in T:
                arcs.append((('mo', i), ('ci', c), 0, CAP))
        il, ih, ol, oh = BOUNDS[k]
        arcs.append((('mi', i), ('Kin', k), il, ih))
        arcs.append((('Kout', k), ('mo', i), ol, oh))
    for k, (ti, to) in TOT.items():
        arcs.append((('Kin', k), 'T', ti, INF))
        arcs.append(('S', ('Kout', k), to, INF))
    for c in ore_cells():
        if c not in T:
            bad.append(('ore cell not transport', c))
            continue
        arcs.append(('S', ('ci', c), CAP, CAP))
    ori, cx, cy = res['core']
    in_sides = [0, 2] if ori == 0 else [1, 3]
    out_sides = [1, 3] if ori == 0 else [0, 2]
    for s in in_sides:
        ec = edge_cells(cx, cy, 9, 9, s)
        for i in range(1, 8):
            c = (ec[i][0] + DIRS[s][0], ec[i][1] + DIRS[s][1])
            if c in T:
                arcs.append((('co', c), 'CORE', 0, CAP))
    for s in out_sides:
        ec = edge_cells(cx, cy, 9, 9, s)
        for i in (1, 4, 7):
            c = (ec[i][0] + DIRS[s][0], ec[i][1] + DIRS[s][1])
            if c in T:
                arcs.append(('S', ('ci', c), CAP, CAP))
            else:
                bad.append(('core out-port cell not transport', c))
    arcs.append(('CORE', 'T', 23, INF))
    arcs.append(('T', 'S', 0, INF))
    return arcs, bad


def feasible(arcs):
    G = nx.DiGraph()
    excess = {}
    for (u, v, lo, hi) in arcs:
        if hi < lo:
            return False, None, 0
        cap = hi - lo
        if G.has_edge(u, v):
            G[u][v]['capacity'] += cap
        else:
            G.add_edge(u, v, capacity=cap)
        if lo:
            excess[v] = excess.get(v, 0) + lo
            excess[u] = excess.get(u, 0) - lo
    need = 0
    for x, e in excess.items():
        if e > 0:
            G.add_edge('SS', x, capacity=e)
            need += e
        elif e < 0:
            G.add_edge(x, 'TT', capacity=-e)
    val, part = nx.maximum_flow(G, 'SS', 'TT')
    if val == need:
        return True, None, 0
    cut_val, (Sset, Tset) = nx.minimum_cut(G, 'SS', 'TT')
    return False, Sset, need - val


if __name__ == '__main__':
    res = json.load(open(sys.argv[1]))
    arcs, bad = build(res)
    if bad:
        # 结构缺陷（如矿口或核心取货端口外侧不是运输格）：布局直接不合格，不再往下认证
        print('INFEASIBLE (structural):', bad[:10], len(bad))
        sys.exit(1)
    ok, S, deficit = feasible(arcs)
    print('feasible' if ok else f'INFEASIBLE, deficit {deficit} (1/20 件/tick)')
    if not ok:
        cells = sorted(set(x[1] for x in S if isinstance(x, tuple) and x[0] in ('ci', 'co')))
        machines = sorted(set(x[1] for x in S if isinstance(x, tuple) and x[0] in ('mi', 'mo')))
        print('S side: transport cells', len(cells), 'machine nodes', len(machines))
        # 保存完整割：超级源一侧的全部结点（含辅助结点），供复核 d(X)+l(出X) <= u(入X) 的违反
        out = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1] + '.cut.json'
        json.dump({'deficit': deficit, 'source_side': [repr(x) for x in S]}, open(out, 'w'))
        print('cut saved to', out)
