#!/usr/bin/env python3
"""线索试验（不是证明）：K 下游按固定周期部分收货时，循环态里 K 会不会断料。

用编码一的逐刻模拟。先跑一段任意对手（起始 Φ ≥ S+1/2），然后固定判定次序、不再离线，
K 的每条下游通道按「(t+相位) mod 周期 < 收货刻数」收货，跑到（状态, t mod 周期最小公倍数）重复。
记录循环里：K 开批率、K 因取货格放不下而停的刻数、K 空转（没料可开）的刻数、
「通道断料」次数（本刻收货的下游通道多于 K 实际送出的件数，即 K 取货格被取空）。
"""
import json, math, random, sys
sys.path.insert(0, '.')
from cell_sweep_sim import Cell, IDLE, WORK, DONE


def probe(seed):
    rng = random.Random(seed)
    m = 50
    L1, L2, L3, L4 = [rng.randint(1, 6) for _ in range(4)]
    k = rng.choice([2, 3])
    c = Cell(m, L1, L2, L3, L4, k, rng)
    c.randomize(rng.choice([0.0, 0.3, 1.0]))
    S = L1 + L2 + 2
    while c.phi() < S + 0.5:
        if c.M['A'][0] < m:
            c.M['A'][0] += 1
        else:
            c.M['C'][0] = min(m, c.M['C'][0] + 1)
    phi0 = c.phi()
    for step in range(rng.choice([100, 500, 1500])):
        order = c.tmpl[:]; rng.shuffle(order)
        acc = [rng.random() < 0.5 for _ in range(k)]
        c.step(order, acc, rng.choice('AB') if rng.random() < 0.1 else None)
    per = [rng.randint(1, 6) for _ in range(k)]
    q = [rng.randint(0, p) for p in per]
    if rng.random() < 0.3:
        q = per[:]            # 全收
        q[0] = rng.randint(0, per[0])  # 只有一条部分收
    ph = [rng.randrange(p) for p in per]
    lcm = 1
    for p in per:
        lcm = lcm * p // math.gcd(lcm, p)
    order = c.tmpl[:]; rng.shuffle(order)
    seen = {}
    hist = []
    for step in range(300000):
        key = (c.key(), step % lcm)
        if key in seen:
            cyc = hist[seen[key]:]
            n = len(cyc)
            return dict(seed=seed, L=(L1, L2, L3, L4), k=k, per=per, q=q, phi0=phi0,
                        cycle_len=n, demand_per_tick=round(sum(qq / pp for qq, pp in zip(q, per)), 4),
                        k_rate=round(sum(h[0] for h in cyc) / n, 4),
                        k_outblocked=sum(h[1] for h in cyc), k_idle=sum(h[2] for h in cyc),
                        chan_starved=sum(h[3] for h in cyc), phi_min=min(h[4] for h in cyc), S=S,
                        c_idle=sum(h[5] for h in cyc), b_idle=sum(h[6] for h in cyc))
        seen[key] = len(hist)
        acc = [((step + ph[j]) % per[j]) < q[j] for j in range(k)]
        took, ready, blocked, ks, kob = c.step(order, acc, None)
        kidle = (c.M['K'][1] == IDLE)
        starved = 1 if c.last_kout < sum(acc) else 0
        cidle = 1 if c.M['C'][1] == IDLE else 0
        bidle = 1 if c.M['B'][1] == IDLE else 0
        hist.append((1 if ks else 0, 1 if kob else 0, 1 if kidle else 0, starved, c.phi(), cidle, bidle))
    return dict(seed=seed, nocycle=True)


if __name__ == '__main__':
    n = int(sys.argv[1]); base = int(sys.argv[2])
    out = [probe(base * 100000 + i) for i in range(n)]
    agg = dict(runs=len(out), nocycle=sum(1 for o in out if o.get('nocycle')),
               with_k_idle=sum(1 for o in out if o.get('k_idle')),
               with_chan_starved=sum(1 for o in out if o.get('chan_starved')),
               with_outblocked=sum(1 for o in out if o.get('k_outblocked')),
               with_c_idle=sum(1 for o in out if o.get('c_idle')),
               with_b_idle=sum(1 for o in out if o.get('b_idle')),
               phi_below_S=sum(1 for o in out if o.get('phi_min', 1e9) < o.get('S', 0)))
    ex = [o for o in out if o.get('chan_starved') or o.get('k_idle') or o.get('c_idle') or o.get('b_idle')][:8]
    json.dump(dict(agg=agg, examples=ex), sys.stdout, ensure_ascii=False, indent=1)
