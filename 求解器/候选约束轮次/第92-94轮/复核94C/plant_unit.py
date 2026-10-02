#!/usr/bin/env python3
"""采种单元（C 采种机、A/B 种植机、K 粉碎机）在自写步进模拟器上的实验。
S07：反例重现、400 步保障随机核对、长时间是否断料（旧条文无限期部分的线索）。
S08：Φ 下界随机核对（含 B、K 随机停开与 K 下游随机停收）。
S09：最小存量 Φ(s)=L1+L2+5/2 时的长期批率（旧条文满速部分的线索）。
"""
import json, random, sys
from stepsim import World, Machine, Sink, Element

S, P, D = 'seed', 'plant', 'powder'


def mk_unit(rng, L1, L2, LB, LK, k, Lpow, ranks=None, sink_pattern=None, init='full',
            Kpattern=None):
    w = World()
    C = Machine('C', [({P: 1}, S, 2, 8)], 1)
    A = Machine('A', [({S: 1}, P, 1, 8)], 1)
    B = Machine('B', [({S: 1}, P, 1, 8)], 1)
    K = Machine('K', [({P: 1}, D, k, 8)], 1)
    ms = [C, A, B, K]
    rk = ranks or {}
    for i, m in enumerate(ms):
        m.rank = rk.get(m.name, i)
    w.nts = ms
    ra = lambda: rng.randrange(100)
    CA = w.chain(C, A, [L1], ranks=[ra()], out_rank=rk.get('CA', 0), name='CA')
    CB = w.chain(C, B, [LB], ranks=[ra()], out_rank=rk.get('CB', 1), name='CB')
    AC = w.chain(A, C, [L2], ranks=[ra()], out_rank=0, name='AC')
    BK = w.chain(B, K, [LK], ranks=[ra()], out_rank=0, name='BK')
    sinks = []
    for j in range(k):
        sk = Sink(f'Z{j}', pattern=(sink_pattern[j] if sink_pattern else None))
        w.chain(K, sk, [Lpow], ranks=[ra()], out_rank=rk.get(f'K{j}', j), name=f'KZ{j}')
        sinks.append(sk)
    w.finalize()
    return w, C, A, B, K, dict(CA=CA, CB=CB, AC=AC, BK=BK), sinks


def fill(el, kind, entered=-8):
    for e in el:
        e.cells = [[kind, entered] for _ in e.cells]


def phi(C, A, routes):
    v = 0.0
    v += sum(e.count(S) for e in routes['CA'])
    v += A.in_count(S)
    v += (A.out[1] if A.out else 0)
    v += sum(e.count(P) for e in routes['AC'])
    v += C.in_count(P)
    v += 1 if A.cache is not None else 0
    v += 1 if C.cache is not None else 0
    v += (C.out[1] if C.out else 0) / 2
    return v


def rand_cache(rng, prod, q):
    r = rng.randrange(3)
    if r == 0:
        return None
    if r == 1:
        return ('run', rng.randint(1, 8), prod, q)
    return ('done', prod, q)


# ---------------------------------------------------------------- S07
def s07_counterexample():
    """推导席反例：K 存货 50、取货 48、缓存有完成的一批 3 件，第 0 步开批后存货 49，第 1 步才补回。"""
    out = []
    for perm in range(6):
        rng = random.Random(perm)
        w, C, A, B, K, R, sinks = mk_unit(rng, 1, 1, 1, 1, 3, 1)
        for m, kind in ((C, P), (A, S), (B, S), (K, P)):
            m.inp = [[kind, 50]]
        C.out = [S, 50]; A.out = [P, 50]; B.out = [P, 50]; K.out = [D, 48]
        C.cache = ('done', S, 2); A.cache = ('done', P, 1); B.cache = ('done', P, 1)
        K.cache = ('done', D, 3)
        for nm, kind in (('CA', S), ('CB', S), ('AC', P), ('BK', P)):
            fill(R[nm], kind)
        for e in w.elements:
            if e.name.startswith('KZ'):
                e.cells = [[D, -8]]
        # 研磨机只能再收一件：第一个粉末汇点只在第 0 步收一件，其余不收
        sinks[0].pattern = lambda t: t == 0
        sinks[1].pattern = lambda t: False
        sinks[2].pattern = lambda t: False
        rec = []
        for t in range(3):
            w.step()
            rec.append(dict(t=t, K_in=K.in_count(P), K_out=K.out[1] if K.out else 0,
                            K_cache=K.cache))
        out.append(rec)
    return out


def s07_random(nrun, steps=400, seed=1):
    rng = random.Random(seed)
    viol = []
    stats = dict(runs=0, min_out={1: 99, 2: 99, 3: 99}, max_refill=0)
    for r in range(nrun):
        k = rng.choice([2, 3])
        L1, L2, LB, LK, Lp = (rng.randint(1, 4) for _ in range(5))
        names = ['C', 'A', 'B', 'K', 'CA', 'CB'] + [f'K{j}' for j in range(k)]
        ranks = {n: rng.randrange(1000) for n in names}
        pats = []
        for j in range(k):
            mode = rng.randrange(3)
            if mode == 0:
                pats.append(lambda t: True)
            elif mode == 1:
                per = rng.randint(1, 30)
                ph = rng.randrange(per)
                pats.append(lambda t, per=per, ph=ph: t % per == ph)
            else:
                rr = random.Random(rng.randrange(10**9))
                seq = [rr.random() < 0.5 for _ in range(steps + 10)]
                pats.append(lambda t, seq=seq: seq[t])
        w, C, A, B, K, R, sinks = mk_unit(rng, L1, L2, LB, LK, k, Lp, ranks, pats)
        kv = {'C': 2, 'A': 1, 'B': 1, 'K': k}
        for m, kind, prod in ((C, P, S), (A, S, P), (B, S, P), (K, P, D)):
            m.inp = [[kind, 50]]
            q = kv[m.name]
            m.out = [prod, rng.randint(50 - q, 50)]
            m.cache = rand_cache(rng, prod, q)
        for nm, kind in (('CA', S), ('CB', S), ('AC', P), ('BK', P)):
            fill(R[nm], kind, entered=-rng.randint(8, 20))
        for e in w.elements:
            if e.name.startswith('KZ'):
                e.cells = [[D, -rng.randint(8, 20)] for _ in e.cells]
        # 取货格下界在每次送出后检查（库存只在送出时下降）
        firsts = {m.name: list(m.out_routes) for m in (C, A, B, K)}
        empty_since = {}
        judg_count = {m.name: 0 for m in (C, A, B, K)}
        for t in range(steps):
            # 记录首格空出：在机器判定前看
            w.step()
            for m in (C, A, B, K):
                judg_count[m.name] += 1
                o = m.out[1] if m.out else 0
                q = kv[m.name]
                stats['min_out'][q] = min(stats['min_out'][q], o)
                if o < 50 - 3 * q:
                    viol.append(('out', r, t, m.name, o))
                if m.cache is None:
                    viol.append(('cache', r, t, m.name))
            stats['runs'] = r + 1
        # 回填：用发送记录与首格占用重建（首格空出的步 = 首格物品离开的步）
    return dict(viol=viol[:10], nviol=len(viol), **stats)


def s07_refill(nrun, steps=400, seed=7):
    """首格空出后，最迟在第 k_v 次本机判定收到。逐步在机器判定前后观察首格。"""
    rng = random.Random(seed)
    worst = {}
    bad = []
    for r in range(nrun):
        k = rng.choice([2, 3])
        L = [rng.randint(1, 3) for _ in range(5)]
        names = ['C', 'A', 'B', 'K', 'CA', 'CB'] + [f'K{j}' for j in range(k)]
        ranks = {n: rng.randrange(1000) for n in names}
        rr = random.Random(rng.randrange(10**9))
        seqs = [[rr.random() < 0.6 for _ in range(steps + 10)] for _ in range(k)]
        pats = [lambda t, s=s: s[t] for s in seqs]
        w, C, A, B, K, R, sinks = mk_unit(rng, L[0], L[1], L[2], L[3], k, L[4], ranks, pats)
        kv = {'C': 2, 'A': 1, 'B': 1, 'K': k}
        for m, kind, prod in ((C, P, S), (A, S, P), (B, S, P), (K, P, D)):
            m.inp = [[kind, 50]]
            m.out = [prod, rng.randint(50 - kv[m.name], 50)]
            m.cache = rand_cache(rng, prod, kv[m.name])
        for nm, kind in (('CA', S), ('CB', S), ('AC', P), ('BK', P)):
            fill(R[nm], kind, entered=-rng.randint(8, 20))
        for e in w.elements:
            if e.name.startswith('KZ'):
                e.cells = [[D, -rng.randint(8, 20)] for _ in e.cells]
        # 包装机器判定：判定前看哪些首格空着
        waiting = {}  # (machine, element) -> 已经历的本机判定次数
        for m in (C, A, B, K):
            orig = m.judge

            def jd(t, m=m, orig=orig):
                for e in m.out_routes:
                    if e.first_empty():
                        waiting[(m.name, e.name)] = waiting.get((m.name, e.name), 0) + 1
                got = orig(t)
                if got is not None:
                    key = (m.name, got.name)
                    n = waiting.pop(key, None)
                    if n is not None:
                        worst[m.name] = max(worst.get(m.name, 0), n)
                        if n > kv[m.name]:
                            bad.append((r, t, key, n))
                return got
            m.judge = jd
        for t in range(steps):
            w.step()
        for key, n in waiting.items():
            if n > kv[key[0]]:
                bad.append((r, 'end', key, n))
    return dict(runs=nrun, worst_judgements=worst, bad=bad[:10], nbad=len(bad))


def long_run(nrun, steps, seed=3, sinkmode='free'):
    """旧条文无限期部分的线索：满起态、长时间运行，看有没有机器步末缓存空、存货见底。"""
    rng = random.Random(seed)
    res = []
    for r in range(nrun):
        k = rng.choice([2, 3])
        L = [rng.randint(1, 5) for _ in range(5)]
        names = ['C', 'A', 'B', 'K', 'CA', 'CB'] + [f'K{j}' for j in range(k)]
        ranks = {n: rng.randrange(1000) for n in names}
        if sinkmode == 'free':
            pats = [lambda t: True for _ in range(k)]
        else:
            rr = random.Random(rng.randrange(10**9))
            pats = []
            for j in range(k):
                per = rr.randint(8, 12)
                pats.append(lambda t, per=per: t % per == 0)
        w, C, A, B, K, R, sinks = mk_unit(rng, L[0], L[1], L[2], L[3], k, L[4], ranks, pats)
        kv = {'C': 2, 'A': 1, 'B': 1, 'K': k}
        for m, kind, prod in ((C, P, S), (A, S, P), (B, S, P), (K, P, D)):
            m.inp = [[kind, 50]]
            m.out = [prod, rng.randint(50 - kv[m.name], 50)]
            m.cache = rand_cache(rng, prod, kv[m.name])
        for nm, kind in (('CA', S), ('CB', S), ('AC', P), ('BK', P)):
            fill(R[nm], kind, entered=-rng.randint(8, 20))
        for e in w.elements:
            if e.name.startswith('KZ'):
                e.cells = [[D, -rng.randint(8, 20)] for _ in e.cells]
        first_empty = {}
        mins = {m.name: 50 for m in (C, A, B, K)}
        for t in range(steps):
            w.step()
            for m in (C, A, B, K):
                mins[m.name] = min(mins[m.name], m.in_count(m.recipes[0][0] and list(m.recipes[0][0])[0]))
                if m.cache is None and m.name not in first_empty:
                    first_empty[m.name] = t
        starts = {m.name: len([x for x in m.starts if x >= steps - 8000]) for m in (C, A, B, K)}
        res.append(dict(r=r, k=k, L=L, first_cache_empty=first_empty, min_input=mins,
                        starts_last8000=starts))
    return res


if __name__ == '__main__':
    what = sys.argv[1]
    out = {}
    if what == 's07':
        out['counterexample'] = s07_counterexample()
        out['random400'] = s07_random(3000)
        out['refill400'] = s07_refill(2000)
    elif what == 'long':
        out['long_free'] = long_run(40, 40000, seed=3, sinkmode='free')
        out['long_periodic'] = long_run(40, 40000, seed=4, sinkmode='periodic')
    json.dump(out, open(f's07_{what}.json', 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(out, ensure_ascii=False, default=str)[:3000])
