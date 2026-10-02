#!/usr/bin/env python3
"""抽查清单21（植物专机一一配对满库存不断料，n=1 即一个采种单元）：
按条文起态，进路含同轴相邻桥，另在 BK 上放一座另一轴有通道的交叉桥，并按“整台单位”读临时第1条（最不利读法），
核第0—399步：各机缓存不空、取货格≥50−3k_v、首格空后在接下来 k_v 次本机判定内收到一件。"""
import json, random, sys
from seedunit import Unit, SEED, PLANT, POWDER
from engine import Item, Belt, Cell
def one(rng, unit_reading, cross):
    k = rng.choice([2, 3])
    segs = None
    if cross:
        segs = {p: [('belt', rng.randint(1, 4)), ('br', rng.randint(1, 3))] for p in ('CA', 'AC', 'CB')}
        segs['BK'] = [('belt', 1), ('br', 1), ('belt', 1), ('br', 1), ('belt', 1)]
    u = Unit(rng, k=k, n_out=k, segs=segs, cross=cross, bridge_unit_reading=unit_reading)
    kv = {'C': 2, 'A': 1, 'B': 1, 'K': k}
    for p, kind in (('CA', SEED), ('AC', PLANT), ('CB', SEED), ('BK', PLANT)):
        u.fill_path(p, kind, 1.0, age_lo=-30)
        for (e, j, pu) in u.paths[p][1]:
            it = e.cells[j] if isinstance(e, Belt) else e.item
            it.entered = min(it.entered, -8)       # 已停留至少 1 tick
    for m, i, o in ((u.C, PLANT, SEED), (u.A, SEED, PLANT), (u.B, SEED, PLANT), (u.K, PLANT, POWDER)):
        m.slots[0] = [i, 50]
        m.out_kind, m.out_n = o, rng.randint(50 - kv[m.name], 50)
        r = rng.random()
        m.cache = None if r < 0.3 else (('run', rng.randint(1, 8)) if r < 0.7 else ('done',))
    for e in u.kout:
        if isinstance(e, Belt):
            e.cells = [None] * len(e.cells)
        else:
            e.item = None
    if cross:
        u.cross_nodes[1].cells[0] = Item('z', -20, 'Zs')
        u.cross_nodes[2].item = Item('z', -20, 'Z.in#0')
        u.cross_nodes[3].cells[0] = Item('z', -20, u.cross_nodes[2].unit)
    w = u.w
    firsts = {'C': [u.paths['CA'][0][0], u.paths['CB'][0][0]], 'A': [u.paths['AC'][0][0]],
              'B': [u.paths['BK'][0][0]], 'K': list(u.kout)}
    mach = {'C': u.C, 'A': u.A, 'B': u.B, 'K': u.K}
    waits = {}
    maxw = {m: 0 for m in mach}
    for t in range(400):
        w.step()
        T = w.t - 1
        for name, m in mach.items():
            if not m.cache_nonempty():
                return dict(ok=False, t=T, err=name + '缓存空')
            if m.out_n < 50 - 3 * kv[name]:
                return dict(ok=False, t=T, err=name + '取货<50-3kv')
            for e in firsts[name]:
                fc = e.cells[0] if isinstance(e, Belt) else e.item
                key = e.name
                if fc is None:
                    waits.setdefault(key, T)
                else:
                    if key in waits:
                        wt = T - waits.pop(key)   # 本机判定次数 = wt+1
                        maxw[name] = max(maxw[name], wt + 1)
                        if wt + 1 > kv[name]:
                            return dict(ok=False, t=T, err=f'{name}首格等{wt+1}次判定>k_v')
        if cross and not unit_reading:
            pass
    return dict(ok=True, maxw=maxw, Kin=u.K.inv(PLANT))
mode = sys.argv[1]; N = int(sys.argv[2]); seed = int(sys.argv[3])
rng = random.Random(seed)
res = [one(random.Random(rng.getrandbits(64)), mode == 'unit', True) for _ in range(N)]
res2 = [one(random.Random(rng.getrandbits(64)), mode == 'unit', False) for _ in range(N)]
bad = [r for r in res + res2 if not r['ok']]
mw = {}
for r in res + res2:
    if r['ok']:
        for k, v in r['maxw'].items():
            mw[k] = max(mw.get(k, 0), v)
print(json.dumps(dict(mode=mode, N=2 * N, fail=len(bad), first=bad[:3], max_judgements_to_refill=mw,
                      min_K_input_at_399=min(r['Kin'] for r in res if r['ok']) if any(r['ok'] for r in res) else None),
                 ensure_ascii=False))
