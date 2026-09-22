"""flowcheck 的正对照：小布局上应判可行，断开一段应判不可行。"""
import flowcheck as F
F.ore_cells = lambda: [(1, 2)]
F.BOUNDS = dict(F.BOUNDS); F.BOUNDS['refine'] = (20, 20, 0, 20)
F.TOT = {'refine': (40, 20), 'crush': (20, 20)}
orig_build = F.build
def build_nocore(res):
    # 去掉核心部分：复制 build，但不加核心弧
    T = set(map(tuple, res['transport'])); B = set()
    arcs = []
    for c in T:
        arcs.append((('ci', c), ('co', c), 0, F.CAP))
        for d in range(4):
            n = (c[0] + F.DIRS[d][0], c[1] + F.DIRS[d][1])
            if n in T:
                arcs.append((('co', c), ('ci', n), 0, F.CAP))
    for i, (k, ax, ay, w, h, s) in enumerate(res['units']):
        so = F.OPP[s]
        for (ex, ey) in F.edge_cells(ax, ay, w, h, s):
            c = (ex + F.DIRS[s][0], ey + F.DIRS[s][1])
            if c in T: arcs.append((('co', c), ('mi', i), 0, F.CAP))
        for (ex, ey) in F.edge_cells(ax, ay, w, h, so):
            c = (ex + F.DIRS[so][0], ey + F.DIRS[so][1])
            if c in T: arcs.append((('mo', i), ('ci', c), 0, F.CAP))
        il, ih, ol, oh = F.BOUNDS[k]
        arcs.append((('mi', i), ('Kin', k), il, ih)); arcs.append((('Kout', k), ('mo', i), ol, oh))
    for k, (ti, to) in F.TOT.items():
        arcs.append((('Kin', k), 'T', ti, F.INF)); arcs.append(('S', ('Kout', k), to, F.INF))
    for c in F.ore_cells():
        arcs.append(('S', ('ci', c), F.CAP, F.CAP))
    arcs.append(('T', 'S', 0, F.INF))
    return arcs
units = [['refine', 2, 1, 3, 3, 2], ['crush', 6, 1, 3, 3, 2], ['refine', 10, 1, 3, 3, 2]]
good = {'units': units, 'transport': [[1, 2], [5, 1], [5, 2], [5, 3], [9, 2]]}
print('positive control:', F.feasible(build_nocore(good))[0], '(expect True)')
bad = {'units': units, 'transport': [[1, 2], [9, 2]]}
print('negative control:', F.feasible(build_nocore(bad))[0], '(expect False)')
# 走廊容量：矿格旁边多接一条长带，仍可行
