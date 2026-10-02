#!/usr/bin/env python3
"""含同轴相邻桥的 150 界定向枚举：CA、AC 满且成熟（正向来源），A、C 库存与缓存取边界值，B 侧每次都收，
CA/AC 用三种含相邻桥的进路；记各起态以后步末最小 Φ−L1−L2（半件单位）与是否违例。"""
import itertools, json, random
from seedunit import Unit, SEED, PLANT, POWDER
from engine import Belt
SEGS = [
    {'CA': [('br', 2)], 'AC': [('br', 3)], 'CB': [('belt', 1)], 'BK': [('belt', 1)]},
    {'CA': [('belt', 1), ('br', 2), ('belt', 1)], 'AC': [('br', 2), ('belt', 2)], 'CB': [('br', 2)], 'BK': [('belt', 1)]},
    {'CA': [('belt', 2)], 'AC': [('belt', 1), ('br', 3)], 'CB': [('belt', 1), ('br', 2)], 'BK': [('br', 2)]},
]
def caches():
    return [None, ('done',)] + [('run', r) for r in (1, 2, 7, 8)]
res = dict(states=0, violations=0, min_over_floor2=None, min_example=None)
for si, segs in enumerate(SEGS):
    for ain, aout, cin, cout, ac, cc, order_seed in itertools.product(
            (48, 49, 50), (48, 49, 50), (48, 49, 50), (0, 1, 2, 3, 47, 48, 49, 50), caches(), caches(), (0, 1)):
        rng = random.Random(order_seed)
        u = Unit(rng, k=2, n_out=2, segs=segs)
        u.fill_path('CA', SEED, 1.0, age_lo=-12); u.fill_path('AC', PLANT, 1.0, age_lo=-12)
        u.fill_path('CB', SEED, 0.0); u.fill_path('BK', PLANT, 0.0)
        A, C, B, K = u.A, u.C, u.B, u.K
        A.slots[0] = [SEED, ain]; A.out_kind, A.out_n = PLANT, aout; A.cache = ac
        C.slots[0] = [PLANT, cin]; C.out_kind, C.out_n = (SEED if cout else None), cout; C.cache = cc
        B.slots[0] = [None, 0]; B.out_n = 0; B.out_kind = None; B.cache = None
        w = u.w
        phi_s = u.phi2(); floor = 2 * (u.L1 + u.L2 + 150); bound = min(phi_s - 1, floor)
        mn = 10**9
        for t in range(120):
            w.step()
            ph = u.phi2()
            if ph < bound:
                res['violations'] += 1
                break
            mn = min(mn, ph - 2 * (u.L1 + u.L2))
        res['states'] += 1
        if phi_s - 1 > floor and (res['min_over_floor2'] is None or mn - 300 < res['min_over_floor2']):
            res['min_over_floor2'] = mn - 300
            res['min_example'] = dict(segs=si, ain=ain, aout=aout, cin=cin, cout=cout, ac=ac, cc=cc,
                                      phi_s_minus_L=(phi_s - 2 * (u.L1 + u.L2)) / 2)
print(json.dumps(res, ensure_ascii=False, default=str))
