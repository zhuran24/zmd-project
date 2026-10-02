#!/usr/bin/env python3
"""复核100S2：引擎甲与 sim2 逐步比对完整状态（机器各格、取货、缓存余时、每条带各格货龄、
成品累计）。用法 xcheck.py START COUNT STEPS"""
import sys, json, random, time
from engine_a import Factory
from engine_sim2 import make_world, reconnect, sim2_state, a_state
from net import BAT, CAP

def one(seed, steps):
    rng = random.Random(seed)
    hist = ['clear', 'keep'][seed % 2]
    fa = Factory(seed, lengths='rand', maxlen=[1, 3, 6][seed % 3], check=False)
    w, lookup, belts, sink = make_world(fa)
    ev = {}
    t = 0
    while t < steps:
        t += rng.randint(30, 600)
        ev[t] = rng.choice(['off', 'stopB', 'stopC', 'open', 'capB', 'capC'])
    mism = None
    for step in range(steps):
        e = ev.get(fa.t)
        if e == 'off':
            fa.offline(hist == 'keep')
            reconnect(fa, w, lookup, belts, hist == 'keep')
        elif e in ('stopB', 'stopC'):
            fa.accept[BAT if e == 'stopB' else CAP] = False
        elif e == 'open':
            for k in (BAT, CAP):
                fa.accept[k] = True
                fa.cap_left[k] = None
                sink.cap_left[k] = None
        elif e in ('capB', 'capC'):
            k = BAT if e == 'capB' else CAP
            n = rng.randint(0, 3)
            fa.cap_left[k] = n
            sink.cap_left[k] = n
        fa.step()
        w.step()
        sa, sb = a_state(fa), sim2_state(fa, w, lookup, belts)
        if sa != sb or fa.delivered[BAT] != sink.count[BAT] or fa.delivered[CAP] != sink.count[CAP]:
            diff = [i for i in range(len(sa)) if sa[i] != sb[i]][:3]
            mism = dict(step=fa.t, diff=[(i, str(sa[i]), str(sb[i])) for i in diff],
                        dA=dict(fa.delivered), dB=dict(sink.count))
            break
    return dict(seed=seed, history=hist, steps=fa.t, mismatch=mism,
                battery=fa.delivered[BAT], capsule=fa.delivered[CAP], events=len(ev))

if __name__ == '__main__':
    a, n, steps = map(int, sys.argv[1:4])
    for s in range(a, a + n):
        t0 = time.time()
        r = one(s, steps)
        r['secs'] = round(time.time() - t0, 1)
        print(json.dumps(r, ensure_ascii=False), flush=True)
