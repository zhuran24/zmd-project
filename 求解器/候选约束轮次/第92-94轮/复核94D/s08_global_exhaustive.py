# 「采种单元的回路存量下界」全过程穷举（容量 Cap=2，L1=L2=1，CB 一格，B 一侧为对手）。编码甲的单步函数。
# 状态（相对化）：A、C 各 (存货 0..Cap, 取货 0..Cap, 缓存 空/已完成未进/进行中余 1..8)；CA、AC、CB 各格 空/年龄 0..8（8=已成熟）；
# 轮询 5 种：两路都成功过且 CA 较早 / CB 较早；CA 从未成功；CB 从未成功；两路都从未成功（此时离线可任意改接通先后，由对手每步选）。
# 对手每步还选 CB 末格（若成熟）是否被 B 一侧收走。共 Cap 小时全部状态。
# 对每个状态 x 求 m(x)=x 及其以后一切步末 2Φ 的最小值；检查每个起态 s 之后的最小 2Φ ≥ min(2Φ(s)−1, 2(L1+L2)+2K)，
# 对 K=3Cap（候选写法）、3Cap+1.5（本席细化）、3Cap+2（更强、应失败）各查一遍。
import sys, json, time, itertools
import numpy as np
from multiprocessing import Pool
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import sim_a as SA

CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 2
# 第二个参数 reset：离线时轮询成功记录也可能清空（对应临时规则第 4 条「全部重建」若清空记录的读法），对手每步可把轮询置为「两路都从未成功」
RESET = len(sys.argv) > 2 and sys.argv[2] == 'reset'
T0 = 100
NM = (CAP + 1) * (CAP + 1) * 10
NCELL = 10
NP = 5


def m_dec(i):
    c = i % 10
    i //= 10
    out = i % (CAP + 1)
    inp = i // (CAP + 1)
    cache = -1 if c == 0 else (-2 if c == 1 else T0 + (c - 1))
    return (inp, out, cache)


def m_enc(m, t):
    inp, out, c = m
    code = 0 if c == -1 else (1 if c == -2 else 1 + (c - t))
    assert 0 <= code <= 9, (m, t)
    return (inp * (CAP + 1) + out) * 10 + code


def cell_dec(i):
    return -1 if i == 0 else T0 - (i - 1)


def cell_enc(e, t):
    return 0 if e < 0 else 1 + min(t - e, 8)


def poll_dec(p, order):
    if p == 0:
        return (40, 60)
    if p == 1:
        return (60, 40)
    if p == 2:
        return (SA.NEVER, 60)
    if p == 3:
        return (60, SA.NEVER)
    return (SA.NEVER, SA.NEVER + 1) if order == 0 else (SA.NEVER + 1, SA.NEVER)


def poll_enc(pc):
    a, b = pc
    na, nb = a < SA.NEVER // 2, b < SA.NEVER // 2
    if na and nb:
        return 4
    if na:
        return 2
    if nb:
        return 3
    return 0 if a < b else 1


def idx(a, c, ca, ac, cb, p):
    return ((((a * NM + c) * NCELL + ca) * NCELL + ac) * NCELL + cb) * NP + p


def work(arange):
    cfg = SA.Cfg(k=3, cap=CAP, has_b=False, has_k=False)
    n_per_a = NM * NCELL ** 3 * NP
    lo, hi = arange
    NS = 6 if RESET else 4
    succ = np.zeros(((hi - lo) * n_per_a, NS), dtype=np.int32)
    phi = np.zeros((hi - lo) * n_per_a, dtype=np.int16)
    t = T0 + 1
    for a in range(lo, hi):
        A = m_dec(a)
        for c in range(NM):
            C = m_dec(c)
            for ca, ac, cb in itertools.product(range(NCELL), repeat=3):
                CA, AC, CB = (cell_dec(ca),), (cell_dec(ac),), (cell_dec(cb),)
                for p in range(NP):
                    i = idx(a, c, ca, ac, cb, p) - lo * n_per_a
                    outs = []
                    opts = [(p, 0), (p, 1)] if p == 4 else [(p, 0)]
                    if RESET and p != 4:
                        opts += [(4, 0), (4, 1)]
                    st0 = (A, None, C, None, CA, AC, CB, None, (), poll_dec(p, 0), ())
                    phi[i] = SA.phi2(st0)
                    for (pp, o) in opts:
                        st = (A, None, C, None, CA, AC, CB, None, (), poll_dec(pp, o), ())
                        for rel in (False, True):
                            s2, _, _, _ = SA.step(st, t, cfg, rel_cb=rel)
                            j = idx(m_enc(s2[0], t), m_enc(s2[2], t), cell_enc(s2[4][0], t), cell_enc(s2[5][0], t),
                                    cell_enc(s2[6][0], t), poll_enc(s2[9]))
                            outs.append(j)
                    while len(outs) < NS:
                        outs.append(outs[-1])
                    outs = outs[:NS] if not RESET else (outs + [outs[-1]] * 6)[:6] if len(outs) <= 6 else sorted(set(outs))[:6]
                    succ[i] = outs
    return lo, succ, phi


if __name__ == '__main__':
    t0 = time.time()
    na = NM
    chunks = [(i, min(i + 6, na)) for i in range(0, na, 6)]
    with Pool(3) as pool:
        res = pool.map(work, chunks)
    res.sort(key=lambda r: r[0])
    succ = np.concatenate([r[1] for r in res])
    phi = np.concatenate([r[2] for r in res]).astype(np.int32)
    N = len(phi)
    t1 = time.time()
    m = phi.copy()
    it = 0
    while True:
        it += 1
        nm = np.minimum(m, m[succ].min(axis=1))
        if np.array_equal(nm, m):
            break
        m = nm
    fut = m[succ].min(axis=1)
    L = 2
    out = {'Cap': CAP, '离线清空轮询记录': RESET, 'L1': 1, 'L2': 1, '状态数': int(N), '传播轮数': it,
           '建图秒': round(t1 - t0, 1), '总秒': None}
    for name, K2 in (('K=3Cap(候选写法)', 6 * CAP), ('K=3Cap+1.5(细化)', 6 * CAP + 3), ('K=3Cap+2(更强)', 6 * CAP + 4)):
        bound = np.minimum(phi - 1, 2 * L + K2)
        bad = np.nonzero(fut < bound)[0]
        out[name] = {'违例起态数': int(len(bad))}
        if len(bad):
            b = int(bad[0])
            out[name]['一例'] = {'起态编号': b, '2Φ(s)': int(phi[b]), '之后最小2Φ': int(fut[b]), '下界2Φ': int(bound[b])}
    tab = {}
    for v in np.unique(phi):
        sel = phi == v
        tab[str((int(v) - 2 * L) / 2)] = (int(fut[sel].min()) - 2 * L) / 2
    out['各起态Φ(s)−L1−L2下之后最小Φ−L1−L2'] = tab
    out['总秒'] = round(time.time() - t0, 1)
    print(json.dumps(out, ensure_ascii=False))
    json.dump(out, open(__file__.rsplit('/', 1)[0] + f'/s08_global_exhaustive_cap{CAP}' + ('_reset' if RESET else '') + '.json', 'w'), ensure_ascii=False, indent=1)
