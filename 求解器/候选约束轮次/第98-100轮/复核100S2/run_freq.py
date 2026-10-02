#!/usr/bin/env python3
"""复核100S2：离线无限反复（每 1—40 步重排一次接通先后，成功记录随机保留或清空），
协议核心一直收货，测长窗口交付数。用法 run_freq.py START COUNT"""
import sys, json, random, time
from engine_a import Factory
from net import BAT, CAP

def one(seed, total=30000, w0=10000):
    rng = random.Random(seed)
    f = Factory(seed, lengths='rand', maxlen=[1, 3, 8, 20][seed % 4], check=True)
    nxt = rng.randint(1, 40)
    b0 = c0 = None
    sent0 = None
    noff = 0
    while f.t < total:
        if f.t == nxt:
            f.offline(rng.random() < 0.5)
            noff += 1
            nxt = f.t + rng.randint(1, 40)
        if f.t == w0:
            b0, c0 = f.delivered[BAT], f.delivered[CAP]
            sent0 = [b.sent for b in f.belts]
        f.step()
    W = total - w0
    ore = [f.belts[i].sent - sent0[i] for i in range(len(f.belts)) if f.belts[i].src in f.src]
    return dict(seed=seed, offlines=noff, window_steps=W,
                battery=f.delivered[BAT] - b0, battery_target=0.6 * W / 8,
                capsule=f.delivered[CAP] - c0, capsule_target=0.55 * W / 8,
                ore_min=min(ore), ore_max=max(ore), ore_target=W / 8,
                nviol=len(f.violations))

if __name__ == '__main__':
    a, n = int(sys.argv[1]), int(sys.argv[2])
    for s in range(a, a + n):
        t0 = time.time()
        r = one(s)
        r['secs'] = round(time.time() - t0, 1)
        print(json.dumps(r, ensure_ascii=False), flush=True)
