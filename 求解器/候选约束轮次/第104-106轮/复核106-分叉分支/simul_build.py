# 边界核对：如果离线重建允许几个单位同一刻建成（规则第 9 行「逐个建成」和临时规则第 4 条「按任意次序」都不允许），
# 能做出的通道全序会比逐个建成多多少。用单位的有序分组（弱序）代替排列，其余同 orders_gen.py。
import itertools, json
from orders_gen import ABSTRACT, expand


def weak_orders(items):
    items = list(items)
    if not items:
        yield []
        return
    for r in range(1, len(items) + 1):
        for first in itertools.combinations(items, r):
            rest = [x for x in items if x not in first]
            for tail in weak_orders(rest):
                yield [list(first)] + tail


res = {}
for nm in ['G1_triangle', 'G2_ring', 'G5_bridges']:
    units, edges = ABSTRACT[nm]
    seq, sim = set(), set()
    for wo in weak_orders(units):
        rank = {u: i for i, blk in enumerate(wo) for u in blk}
        t = [max(rank[a], rank[b]) for a, b in edges]
        groups = {}
        for i, ti in enumerate(t):
            groups.setdefault(ti, []).append(i)
        bs = [groups[k] for k in sorted(groups)]
        for s in expand(bs):
            sim.add(s)
            if all(len(b) == 1 for b in wo):
                seq.add(s)
    lab = ['%s%s' % e for e in edges]
    res[nm] = {'one_by_one': len(seq), 'with_simultaneous_builds': len(sim),
               'extra': sorted('<'.join(lab[i] for i in s) for s in sim - seq)}
print(json.dumps(res, ensure_ascii=False, indent=1))
json.dump(res, open('simul_build.json', 'w'), ensure_ascii=False, indent=1)
