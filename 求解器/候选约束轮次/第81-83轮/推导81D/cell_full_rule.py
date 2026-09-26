#!/usr/bin/env python3
"""编码三：整个单元（C、A、B、K、四条路、K 的 k 条下游通道）的规则式闭包，与编码一独立写法。

同刻闭包：按规则反复套用到不动（机器、逐格前移、路尾进格、单通道出货、K 出货给就绪的下游通道）；
C 取货格的两条通道不用指针，枚举「本刻准许谁取」(fa, fb) 再查自洽（同编码二）。
流程：随机起态（Φ ≥ S+1/2）→ 一段任意对手（自洽的 (fa,fb) 随机挑、下游随机收）→
固定分配规则（偏 A／偏 B／交替）与下游周期收货模式，跑到（状态, 规则状态, t mod 周期）重复。
在循环里核第 1 节第 3 条：C、B、K 每刻结束时都不空手；K 的下游通道就绪的每刻都取到。
"""
import json, math, random, sys, time

IDLE, WORK, DONE = 0, 1, 2


def closure(st, m, k, fa, fb, acc):
    (C, A, B, K, ca, ac, cb, bk) = st
    C = list(C); A = list(A); B = list(B); K = list(K)
    for X in (C, A, B, K):
        if X[1] == WORK:
            X[1] = DONE
    ca = list(ca); ac = list(ac); cb = list(cb); bk = list(bk)
    batch = {id(C): 2, id(A): 1, id(B): 1, id(K): k}
    tookA = tookB = 0
    served = 0
    ready_down = [bool(a) for a in acc]
    took_down = [False] * k
    while True:
        ch = False
        for X in (C, A, B, K):
            b = batch[id(X)]
            if X[1] == DONE and X[2] + b <= m:
                X[2] += b; X[1] = IDLE; ch = True
            if X[1] == IDLE and X[0] >= 1:
                X[0] -= 1; X[1] = WORK; ch = True
        for path, tgt in ((ca, A), (ac, C), (cb, B), (bk, K)):
            if path[-1] == 1 and tgt[0] < m:
                path[-1] = 0; tgt[0] += 1; ch = True
            for i in range(len(path) - 2, -1, -1):
                if path[i] == 1 and path[i + 1] == 0:
                    path[i + 1] = 2; path[i] = 0; ch = True
        if A[2] >= 1 and ac[0] == 0:
            A[2] -= 1; ac[0] = 2; ch = True
        if B[2] >= 1 and bk[0] == 0:
            B[2] -= 1; bk[0] = 2; ch = True
        if fa and not tookA and C[2] >= 1 and ca[0] == 0:
            C[2] -= 1; ca[0] = 2; tookA = 1; ch = True
        if fb and not tookB and C[2] >= 1 and cb[0] == 0:
            C[2] -= 1; cb[0] = 2; tookB = 1; ch = True
        for j in range(k):
            if ready_down[j] and not took_down[j] and K[2] >= 1:
                K[2] -= 1; took_down[j] = True; ch = True
        if not ch:
            break
    if fa and not tookA: return None
    if fb and not tookB: return None
    if not fa and ca[0] == 0 and C[2] > 0: return None
    if not fb and cb[0] == 0 and C[2] > 0: return None
    norm = lambda p: tuple(1 if x else 0 for x in p)
    nst = (tuple(C), tuple(A), tuple(B), tuple(K), norm(ca), norm(ac), norm(cb), norm(bk))
    starved = sum(1 for j in range(k) if ready_down[j] and not took_down[j])
    return nst, tookA, tookB, starved


def phi(st):
    (C, A, B, K, ca, ac, cb, bk) = st
    return sum(ca) + A[0] + (A[1] != IDLE) + A[2] + sum(ac) + C[0] + (C[1] != IDLE) + C[2] / 2.0


def rand_state(rng, m, k, L):
    def mach(b):
        return (rng.randint(0, m) if rng.random() < 0.5 else rng.randint(0, 2), rng.choice([IDLE, WORK, DONE]),
                rng.randint(0, m - b) if rng.random() < 0.5 else rng.randint(0, 2))
    bits = lambda n: tuple(1 if rng.random() < rng.choice([0.2, 0.8]) else 0 for _ in range(n))
    return (mach(2), mach(1), mach(1), mach(k), bits(L[0]), bits(L[1]), bits(L[2]), bits(L[3]))


def trial(seed):
    rng = random.Random(seed)
    m = rng.choice([50, 50, 4, 6, 10])
    k = rng.choice([2, 3])
    L = [rng.randint(1, 6) for _ in range(4)]
    S = L[0] + L[1] + 2
    st = rand_state(rng, m, k, L)
    tries = 0
    while phi(st) < S + 0.5:
        (C, A, B, K, ca, ac, cb, bk) = st
        if A[0] < m:
            A = (A[0] + 1, A[1], A[2])
        else:
            C = (min(m, C[0] + 1), C[1], C[2])
        st = (C, A, B, K, ca, ac, cb, bk)
        tries += 1
        if tries > 10 * m:
            return dict(seed=seed, skipped=True)
    # 任意对手一段
    for t in range(rng.choice([50, 300, 1000])):
        acc = [rng.random() < rng.choice([0.0, 0.5, 1.0]) for _ in range(k)]
        opts = []
        for fa in (0, 1):
            for fb in (0, 1):
                r = closure(st, m, k, fa, fb, acc)
                if r is not None:
                    opts.append(r)
        st = rng.choice(opts)[0]
    pol = rng.choice(['preferA', 'preferB', 'alt'])
    per = [rng.randint(1, 5) for _ in range(k)]
    q = [rng.randint(0, p) for p in per]
    ph = [rng.randrange(p) for p in per]
    lcm = 1
    for p in per:
        lcm = lcm * p // math.gcd(lcm, p)
    ptr = 0
    seen = {}
    hist = []
    for t in range(400000):
        key = (st, ptr, t % lcm)
        if key in seen:
            cyc = hist[seen[key]:]
            n = len(cyc)
            return dict(seed=seed, m=m, k=k, L=L, S=S, pol=pol, per=per, q=q, cycle=n,
                        phi_min=min(h[0] for h in cyc),
                        c_idle=sum(h[1] for h in cyc), b_idle=sum(h[2] for h in cyc), k_idle=sum(h[3] for h in cyc),
                        starved=sum(h[4] for h in cyc), k_rate=sum(h[5] for h in cyc) / n)
        seen[key] = len(hist)
        acc = [((t + ph[j]) % per[j]) < q[j] for j in range(k)]
        if pol == 'preferA': cands = [(1, 1), (1, 0), (0, 1), (0, 0)]
        elif pol == 'preferB': cands = [(1, 1), (0, 1), (1, 0), (0, 0)]
        else: cands = [(1, 1), (1, 0), (0, 1), (0, 0)] if ptr == 0 else [(1, 1), (0, 1), (1, 0), (0, 0)]
        for fa, fb in cands:
            r = closure(st, m, k, fa, fb, acc)
            if r is not None:
                break
        nst, a, b, starved = r
        if pol == 'alt' and a + b == 1:
            ptr = 1 if a else 0
        st = nst
        hist.append((phi(st), st[0][1] == IDLE, st[2][1] == IDLE, st[3][1] == IDLE, starved, st[3][1] == WORK))
    return dict(seed=seed, nocycle=True)


if __name__ == '__main__':
    n = int(sys.argv[1]); base = int(sys.argv[2])
    t0 = time.time()
    out = [trial(base * 1000000 + i) for i in range(n)]
    ok = [o for o in out if 'cycle' in o]
    agg = dict(trials=n, cycles=len(ok), skipped=sum(1 for o in out if o.get('skipped')),
               nocycle=sum(1 for o in out if o.get('nocycle')),
               phi_below_S=sum(1 for o in ok if o['phi_min'] < o['S']),
               with_c_idle=sum(1 for o in ok if o['c_idle']), with_b_idle=sum(1 for o in ok if o['b_idle']),
               with_k_idle=sum(1 for o in ok if o['k_idle']), with_starved=sum(1 for o in ok if o['starved']),
               partial_demand_cycles=sum(1 for o in ok if any(qq < pp for qq, pp in zip(o['q'], o['per']))),
               seconds=round(time.time() - t0, 1))
    bad = [o for o in ok if o['c_idle'] or o['b_idle'] or o['k_idle'] or o['starved']][:10]
    json.dump(dict(agg=agg, bad=bad), sys.stdout, ensure_ascii=False, indent=1)
