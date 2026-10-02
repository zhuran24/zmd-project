# 「采种单元不断料」修订版逐条随机核对（编码甲；编码乙另由 xcheck.py 逐步对照）。
# 起态按候选前提：四机存取货 50、缓存各一批（进行中余 1..8 步或已完成），CA、AC、CB、BK 全满且年龄随机，
# K 各取货通道（1..3 格）内容随机，轮询先后随机。对手决定 K 各通道末格何时离开，并随机离线重排。
# 每个完整步末检查：四缓存不空；B、K 存货≥49；B 取货≥49；K 取货≥50−k；CB、BK 首格非空（=腾空当步补上）；
# K 各首格连续空着的步末数≤n−1。另对「末格成熟就放」的对手找循环，核平均批次率。
# 用法: python3 -B s09_check.py 例数 步数 种子
import sys, random, json
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import sim_a as SA

S0 = 100
RESET = len(sys.argv) > 4 and sys.argv[4] == 'reset'
PRESET = float(sys.argv[5]) if len(sys.argv) > 5 else 0.05


def norm(st, t):
    A, B, C, K, CA, AC, CB, BK, KCH, pc, pk = st
    def m(x):
        return (x[0], x[1], x[2] - t if x[2] >= 0 else x[2])
    def cs(p):
        return tuple(-1 if e < 0 else min(t - e, 8) for e in p)
    def rk(p):
        return tuple(sorted(range(len(p)), key=lambda i: p[i]))
    return (m(A), m(B), m(C), m(K), cs(CA), cs(AC), cs(CB), cs(BK), tuple(cs(p) for p in KCH), rk(pc), rk(pk))


def make_adv(rnd, n):
    kind = rnd.choice(['rand', 'period', 'stall', 'burst', 'free'])
    if kind == 'rand':
        p = rnd.choice([0.02, 0.2, 0.5, 0.9])
        return kind, (lambda t, i: rnd.random() < p)
    if kind == 'period':
        qs = [rnd.randint(8, 20) for _ in range(n)]
        ph = [rnd.randint(0, 19) for _ in range(n)]
        return kind, (lambda t, i: (t + ph[i]) % qs[i] == 0)
    if kind == 'stall':
        a = rnd.randint(50, 600)
        b = a + rnd.randint(50, 600)
        return kind, (lambda t, i: not (S0 + a <= t < S0 + b))
    if kind == 'burst':
        q = rnd.randint(9, 60)
        return kind, (lambda t, i: (t // q) % 2 == 0)
    return kind, (lambda t, i: True)


def one(rnd, steps):
    L = [rnd.randint(1, 5) for _ in range(4)]
    k = rnd.choice([2, 3])
    n = rnd.randint(0, k)
    lk = rnd.randint(1, 3)
    cfg = SA.Cfg(k=k, cap=50)
    cache = lambda: rnd.choice([-2] + [S0 + r for r in range(1, 9)])
    full = lambda Lx: tuple(S0 - rnd.randint(0, 9) for _ in range(Lx))
    st = ((50, 50, cache()), (50, 50, cache()), (50, 50, cache()), (50, 50, cache()),
          full(L[0]), full(L[1]), full(L[2]), full(L[3]),
          tuple(tuple((S0 - rnd.randint(0, 9)) if rnd.random() < 0.5 else -1 for _ in range(lk)) for _ in range(n)),
          tuple(rnd.sample([SA.NEVER, SA.NEVER + 1, 30, 70], 2)),
          tuple(SA.NEVER + i for i in rnd.sample(range(n), n)))
    assert SA.phi2(st) == 2 * (L[0] + L[1] + 177)
    kind, adv = make_adv(rnd, n)
    viol = []
    maxwait = 0
    wait = [0] * n
    batches = {'A': 0, 'B': 0, 'C': 0, 'K': 0}
    kwait_steps = 0
    seen = {}
    cyc = None
    hist = []
    for t in range(S0 + 1, S0 + 1 + steps):
        if RESET and rnd.random() < PRESET:
            # 离线清空轮询成功记录（临时规则第 4 条的一种读法）：全部通道视为从未成功，接通先后任意
            pc = list(range(2)); rnd.shuffle(pc)
            pk = list(range(n)); rnd.shuffle(pk)
            st = st[:9] + (tuple(SA.NEVER + r for r in pc), tuple(SA.NEVER + r for r in pk))
        elif rnd.random() < 0.01:
            st = st[:9] + (SA.offline(st[9], rnd), SA.offline(st[10], rnd))
        rel = tuple(adv(t, i) for i in range(n))
        prev = st
        st, sc, sk, left = SA.step(st, t, cfg, rel_k=rel)
        A, B, C, K, CA, AC, CB, BK, KCH, pc, pk = st
        for nm, x in (('A', A), ('B', B), ('C', C), ('K', K)):
            if x[2] == -1:
                viol.append((t, nm + '缓存空'))
            if x[2] == t + 8:
                batches[nm] += 1
        if K[2] == -2:
            kwait_steps += 1
        if B[0] < 49: viol.append((t, 'B存货<49'))
        if K[0] < 49: viol.append((t, 'K存货<49'))
        if B[1] < 49: viol.append((t, 'B取货<49'))
        if K[1] < 50 - k: viol.append((t, 'K取货<50-k'))
        if CB[0] < 0: viol.append((t, 'CB首格步末空'))
        if BK[0] < 0: viol.append((t, 'BK首格步末空'))
        for i in range(n):
            if KCH[i][0] < 0:
                wait[i] += 1
                maxwait = max(maxwait, wait[i])
                if wait[i] > n - 1:
                    viol.append((t, f'K口{i}等待{wait[i]}>n-1'))
            else:
                wait[i] = 0
        hist.append((dict(batches), kwait_steps, sk))
        if kind == 'free' and cyc is None:
            key = norm(st, t)
            if key in seen:
                t0 = seen[key]
                h0 = hist[t0 - S0 - 1]
                h1 = hist[-1]
                per = t - t0
                cyc = {'周期步数': per,
                       '周期内批数': {m: h1[0][m] - h0[0][m] for m in 'ABCK'},
                       '周期内K完成批等待步数': h1[1] - h0[1]}
            else:
                seen[key] = t
        if len(viol) > 5:
            break
    return {'L': L, 'k': k, 'n': n, 'lk': lk, '对手': kind, '违例': viol[:5], 'K口最长连续空步末数': maxwait,
            '循环': cyc}


if __name__ == '__main__':
    cases, steps, seed = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    rnd = random.Random(seed)
    res = [one(rnd, steps) for _ in range(cases)]
    nv = sum(1 for r in res if r['违例'])
    mw = {}
    for r in res:
        key = f"n={r['n']}"
        mw[key] = max(mw.get(key, 0), r['K口最长连续空步末数'])
    cycles = [r for r in res if r['循环']]
    bad_rate = [r for r in cycles if r['循环']['周期内K完成批等待步数'] == 0 and
                any(r['循环']['周期内批数'][m] * 8 != r['循环']['周期步数'] for m in 'ABCK')]
    import re
    kinds = {}
    for r in res:
        for _, lab in r['违例']:
            key = re.sub(r'口\d+等待\d+', '口等待超n-1', lab)
            kinds[key] = kinds.get(key, 0) + 1
    summ = {'例数': cases, '每例步数': steps, '种子': seed, '离线清空轮询记录': RESET, '有违例的例数': nv, '违例种类计数(每例至多记6条)': kinds,
            '各n下K口最长连续空步末数': mw,
            '找到循环的例数(对手=成熟就放)': len(cycles),
            '其中K从不等待且四机均每tick一批': sum(1 for r in cycles if r['循环']['周期内K完成批等待步数'] == 0) - len(bad_rate),
            '其中K从不等待但批次率不是每tick一批': len(bad_rate),
            '其中K有等待': sum(1 for r in cycles if r['循环']['周期内K完成批等待步数'] > 0)}
    print(json.dumps(summ, ensure_ascii=False))
    out = {'汇总': summ, '违例样例': [r for r in res if r['违例']][:5], '循环样例': cycles[:5]}
    json.dump(out, open(__file__.rsplit('/', 1)[0] + f'/s09_check_seed{seed}' + ('_reset' if RESET else '') + '.json', 'w'), ensure_ascii=False, indent=1)
