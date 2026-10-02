#!/usr/bin/env python3
"""复核103H：H06 的 H 支（L+150 / L+176）是否真正被测到、能否被压到。
高起态（Φ(s) 接近 L+177），CB 出口由对手任意收（B 换成出口，放宽），离线保留/清空随机。
统计：Φ(s)-1/2 > L+H 的例子里 Φ(t)-(L+H) 的最小值；准备截面 H=150，实际步末 H=176；段首按清空离线重算。"""
import json, random, sys
from fractions import Fraction as Fr
import plant

def one(rng, normal, offmode):
    cfg = dict(k=2, n=0, L=[rng.randrange(1, 7), rng.randrange(1, 7), rng.randrange(1, 4), 1], Bmode='adv')
    L1, L2 = cfg['L'][0], cfg['L'][1]; L = L1 + L2
    st = {'belts': {'CA': [-rng.randrange(0, 12) for _ in range(L1)],
                    'AC': [-rng.randrange(0, 12) for _ in range(L2)],
                    'CB': [(-rng.randrange(0, 12) if rng.random() < 0.5 else None) for _ in range(cfg['L'][2])]},
          'm': {'C': {'inp': rng.choice([50, 50, 49, 48]), 'out': rng.choice([50, 49, 48, 47, 46]), 'cache': rng.choice(['done', rng.randrange(1, 9)])},
                'A': {'inp': rng.choice([50, 50, 49]), 'out': rng.choice([50, 50, 49]), 'cache': rng.choice(['done', rng.randrange(1, 9), None])}},
          'connC': rng.sample([0, 1], 2), 'lastC': [None if rng.random() < 0.5 else -rng.randrange(1, 20) - 0.1 * i for i in range(2)],
          'connK': [], 'lastK': []}
    A = plant.EngA(cfg, st)
    t0 = 1
    pat = rng.choice(['always', 'bursty', 'rare'])
    def acc(t):
        if pat == 'always': return {'sinkB': True}
        if pat == 'rare': return {'sinkB': rng.random() < 0.2}
        return {'sinkB': (t // rng.choice([3, 9, 17])) % 2 == 0}
    if normal:
        A.step(1, acc(1)); t0 = 2
    H = 176 if normal else 150
    phis = A.phi(); phiseg = phis; Hseg = H
    best = None; viol = 0
    for t in range(t0, 700):
        if offmode != 'none' and rng.random() < 0.05:
            md = offmode if offmode != 'mixed' else rng.choice(['keep', 'clear'])
            A.offline(md, rng.sample([0, 1], 2), [])
            phiseg = A.phi()
            Hseg = 176 if t > 1 else H   # 准备截面上（第 1 步前）的离线不产生实际步末
        A.step(t, acc(t))
        ph = A.phi()
        if phiseg - Fr(1, 2) > L + Hseg:
            d = ph - (L + Hseg)
            best = d if best is None else min(best, d)
            if d < 0: viol += 1
        elif ph < phiseg - Fr(1, 2):
            viol += 1
    return best, viol, normal

def main():
    rng = random.Random(int(sys.argv[2]) if len(sys.argv) > 2 else 9)
    res = {}
    for normal in (False, True):
        for offmode in ('none', 'keep', 'clear', 'mixed'):
            bests = []; viol = 0; n = 0
            for it in range(1500):
                b, v, _ = one(rng, normal, offmode)
                n += 1; viol += v
                if b is not None: bests.append(b)
            res[f'{"normal176" if normal else "prep150"}_{offmode}'] = dict(cases=n, hbranch_cases=len(bests), violations=viol,
                                                                            min_phi_minus_LH=str(min(bests)) if bests else None)
    json.dump(res, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))

if __name__ == '__main__':
    main()
