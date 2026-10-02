# 「采种单元的回路存量下界」全过程随机核对（容量 50，编码甲）。
# 起态任取（A、C 存取货偏向 0、49、50，缓存空/进行中/已完成未进，CA、AC、CB 各格随机），
# 对手随机决定 CB 末端何时收货（含长停、周期、随机），随机离线重排。
# 每个完整步末核 Φ ≥ min(Φ(s)−1/2, L1+L2+150)；同时记相对 151.5 的最小余量与各 BB 第二个 B 步末的 Φ−L1−L2 最小值。
# 用法: python3 -B s08_random.py 例数 步数 种子
import sys, random, json
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import sim_a as SA

S0 = 100


def rc(rnd):
    r = rnd.random()
    if r < 0.35:
        return 50
    if r < 0.5:
        return 49
    if r < 0.65:
        return rnd.randint(0, 3)
    return rnd.randint(0, 50)


def one(rnd, steps):
    L1, L2, L3 = rnd.randint(1, 5), rnd.randint(1, 5), rnd.randint(1, 4)
    cfg = SA.Cfg(k=3, cap=50, has_b=False, has_k=False)
    cache = lambda: rnd.choice([-1, -2] + [S0 + r for r in range(1, 9)])
    cells = lambda Lx, p: tuple((S0 - rnd.randint(0, 9)) if rnd.random() < p else -1 for _ in range(Lx))
    pfill = rnd.choice([0.3, 0.9, 1.0])
    st = ((rc(rnd), rc(rnd), cache()), None, (rc(rnd), rc(rnd), cache()), None,
          cells(L1, pfill), cells(L2, pfill), cells(L3, rnd.random()), None, (),
          tuple(rnd.sample([SA.NEVER, SA.NEVER + 1, 30, 70], 2)), ())
    L = L1 + L2
    p0 = SA.phi2(st)
    b150 = min(p0 - 1, 2 * (L + 150))
    b1515 = min(p0 - 1, 2 * L + 303)
    kind = rnd.choice(['rand', 'period', 'stall'])
    p = rnd.choice([0.05, 0.3, 0.8, 1.0])
    q = rnd.randint(8, 30)
    a = rnd.randint(0, 400)
    lastB = False
    worst150 = worst1515 = 10**9
    minbb = None
    for t in range(S0 + 1, S0 + 1 + steps):
        if kind == 'rand':
            rel = rnd.random() < p
        elif kind == 'period':
            rel = t % q == 0
        else:
            rel = not (S0 + a <= t < S0 + a + 300)
        if rnd.random() < 0.01:
            st = st[:9] + (SA.offline(st[9], rnd), ())
        st, sc, _, _ = SA.step(st, t, cfg, rel_cb=rel)
        v = SA.phi2(st)
        worst150 = min(worst150, v - b150)
        worst1515 = min(worst1515, v - b1515)
        if sc == 'B':
            if lastB:
                mb = (v - 2 * L) / 2
                minbb = mb if minbb is None else min(minbb, mb)
            lastB = True
        elif sc == 'A':
            lastB = False
    return worst150, worst1515, minbb


if __name__ == '__main__':
    cases, steps, seed = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    rnd = random.Random(seed)
    w150 = w1515 = 10**9
    mbb = None
    nbb = 0
    for _ in range(cases):
        a, b, c = one(rnd, steps)
        w150 = min(w150, a)
        w1515 = min(w1515, b)
        if c is not None:
            nbb += 1
            mbb = c if mbb is None else min(mbb, c)
    out = {'例数': cases, '每例步数': steps, '种子': seed,
           '相对候选下界(150)的最小余量(2Φ单位)': w150,
           '相对细化下界(151.5)的最小余量(2Φ单位)': w1515,
           '出现BB的例数': nbb, 'BB第二个B步末Φ−L1−L2的最小值': mbb}
    print(json.dumps(out, ensure_ascii=False))
    json.dump(out, open(__file__.rsplit('/', 1)[0] + f'/s08_random_seed{seed}.json', 'w'), ensure_ascii=False, indent=1)
