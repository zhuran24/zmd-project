# 编码甲、乙逐步全状态对照：随机起态、随机对手（CB 末端或 K 各口末端何时收货）、随机离线重排。
# 用法: python3 -B xcheck.py 模式(s08|s09) 例数 步数 种子
import sys, random, json
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import sim_a as SA
import sim_b as SB

S0 = 100


def rand_cache(rnd, s0):
    r = rnd.random()
    if r < 0.15:
        return -1
    if r < 0.4:
        return -2
    return s0 + rnd.randint(1, 8)


def rand_cells(rnd, L, pfull, s0):
    return tuple((s0 - rnd.randint(0, 9)) if rnd.random() < pfull else -1 for _ in range(L))


def rand_count(rnd, cap):
    r = rnd.random()
    if r < 0.3:
        return cap
    if r < 0.45:
        return cap - 1
    if r < 0.6:
        return rnd.randint(0, 3)
    return rnd.randint(0, cap)


def to_b(stA, Ls, k, n, mode):
    A, B, C, K, CA, AC, CB, BK, KCH, pollC, pollK = stA
    L1, L2, L3, L4, lk = Ls
    dec = {}
    def mk_rule(key):
        return lambda t: dec.get((key, t), False)
    if mode == 's08':
        net = SB.Net('cur')
        Cm = SB.Machine('C', 'plant', 'seed', 2)
        Am = SB.Machine('A', 'seed', 'plant', 1)
        sinkB = SB.Sink('Bside', mk_rule('cb'))
        net.machines = [Am, Cm]
        ca = SB.path(net, 'CA', L1, Cm, Am)
        cb = SB.path(net, 'CB', L3, Cm, sinkB)
        ac = SB.path(net, 'AC', L2, Am, Cm)
        net.order = SB.chain_order([ca, cb, ac])
        net.A, net.C, net.CA, net.CB, net.AC = Am, Cm, ca, cb, ac
        net.B = net.K = None
        net.BK, net.KP = [], []
    else:
        sinks = [SB.Sink(f'Kd{i}', mk_rule(('k', i))) for i in range(n)]
        net = SB.plant_unit(L1, L2, L3, L4, k, [(lk, sinks[i]) for i in range(n)])
    net.t = S0
    def setm(m, tup):
        m.inp, m.out = tup[0], tup[1]
        c = tup[2]
        m.busy = None
        m.done = 0
        if c == -2:
            m.done = m.batch
        elif c >= 0:
            m.busy = c - S0
    setm(net.A, A)
    setm(net.C, C)
    if mode != 's08':
        setm(net.B, B)
        setm(net.K, K)
    def setc(cs, tup, item):
        for c, e in zip(cs, tup):
            if e >= 0:
                c.item, c.age, c.frm = item, S0 - e, 'prev'
            else:
                c.item = None
    setc(net.CA, CA, 'seed')
    setc(net.AC, AC, 'plant')
    setc(net.CB, CB, 'seed')
    if mode != 's08':
        setc(net.BK, BK, 'plant')
        for cs, tup in zip(net.KP, KCH):
            setc(cs, tup, 'powder')
    # 轮询队列：按甲的键排序
    def setq(m, chans, poll):
        order = sorted(range(len(chans)), key=lambda i: poll[i])
        m.queue = [chans[i] for i in order]
        m.never = set(id(chans[i]) for i in range(len(chans)) if poll[i] < SA.NEVER // 2)
    setq(net.C, [net.CA[0], net.CB[0]], pollC)
    if mode != 's08':
        setq(net.K, [p[0] for p in net.KP], pollK)
    return net, dec


def from_b(net, mode, n):
    t = net.t
    def gm(m):
        if m is None:
            return None
        c = -1
        if m.done > 0:
            c = -2
        elif m.busy is not None:
            c = t + m.busy
        return (m.inp, m.out, c)
    def gc(cs):
        return tuple((t - c.age) if c.item is not None else -1 for c in cs)
    return (gm(net.A), gm(net.B) if mode != 's08' else None, gm(net.C), gm(net.K) if mode != 's08' else None,
            gc(net.CA), gc(net.AC), gc(net.CB), gc(net.BK) if mode != 's08' else None,
            tuple(gc(p) for p in net.KP) if mode != 's08' else ())


def strip(stA):
    return stA[:9]


def run(mode, cases, steps, seed):
    rnd = random.Random(seed)
    mism = 0
    total = 0
    for case in range(cases):
        L1, L2, L3, L4 = (rnd.randint(1, 4) for _ in range(4))
        k = rnd.choice([2, 3])
        n = rnd.randint(0, k)
        lk = rnd.randint(1, 3)
        cfg = SA.Cfg(k=k, cap=50, has_b=(mode != 's08'), has_k=(mode != 's08'))
        if mode == 's09':
            # 满库存起态（候选「采种单元不断料」的前提），运输格年龄、缓存余时随机
            A = (50, 50, rnd.choice([-2] + [S0 + r for r in range(1, 9)]))
            C = (50, 50, rnd.choice([-2] + [S0 + r for r in range(1, 9)]))
            B = (50, 50, rnd.choice([-2] + [S0 + r for r in range(1, 9)]))
            K = (50, 50, rnd.choice([-2] + [S0 + r for r in range(1, 9)]))
            CA = rand_cells(rnd, L1, 1.0, S0)
            AC = rand_cells(rnd, L2, 1.0, S0)
            CB = rand_cells(rnd, L3, 1.0, S0)
            BK = rand_cells(rnd, L4, 1.0, S0)
            KCH = tuple(rand_cells(rnd, lk, rnd.random(), S0) for _ in range(n))
        else:
            A = (rand_count(rnd, 50), rand_count(rnd, 50), rand_cache(rnd, S0))
            C = (rand_count(rnd, 50), rand_count(rnd, 50), rand_cache(rnd, S0))
            B = K = None
            CA = rand_cells(rnd, L1, rnd.random(), S0)
            AC = rand_cells(rnd, L2, rnd.random(), S0)
            CB = rand_cells(rnd, L3, rnd.random(), S0)
            BK = None
            KCH = ()
            n = 0
        pollC = tuple(rnd.sample([SA.NEVER, SA.NEVER + 1, 40, 60], 2))
        pollK = tuple(SA.NEVER + i for i in rnd.sample(range(n), n)) if n else ()
        st = (A, B, C, K, CA, AC, CB, BK, KCH, pollC, pollK)
        net, dec = to_b(st, (L1, L2, L3, L4, lk), k, n, mode)
        pacc = rnd.choice([0.05, 0.3, 0.7, 1.0])
        for t in range(S0 + 1, S0 + 1 + steps):
            rel_cb = rnd.random() < pacc
            rel_k = tuple(rnd.random() < pacc for _ in range(n))
            dec[('cb', t)] = rel_cb
            for i in range(n):
                dec[(('k', i), t)] = rel_k[i]
            if rnd.random() < 0.01:
                perm_seed = rnd.random()
                r1 = random.Random(perm_seed)
                st = st[:9] + (SA.offline(st[9], r1),) + st[10:]
                r2 = random.Random(perm_seed)
                net.offline(net.C, r2)
                if n:
                    r1 = random.Random(perm_seed + 1)
                    st = st[:10] + (SA.offline(st[10], r1),)
                    r2 = random.Random(perm_seed + 1)
                    net.offline(net.K, r2)
            st, sc, sk, _ = SA.step(st, t, cfg, rel_cb=rel_cb, rel_k=rel_k)
            net.step()
            total += 1
            a = strip(st)
            b = from_b(net, mode, n)
            if a != b or SA.phi2(st) != SB.phi2(net):
                mism += 1
                if mism <= 3:
                    print('MISMATCH case', case, 't', t, '\nA', a, '\nB', b)
                break
    return {'模式': mode, '例数': cases, '每例步数': steps, '逐步对照总步数': total, '不一致': mism}


if __name__ == '__main__':
    mode, cases, steps, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    res = run(mode, cases, steps, seed)
    print(json.dumps(res, ensure_ascii=False))
    fn = __file__.rsplit('/', 1)[0] + f'/xcheck_{mode}.json'
    json.dump(res, open(fn, 'w'), ensure_ascii=False, indent=1)
