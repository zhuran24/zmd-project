#!/usr/bin/env python3
"""编码二补充 E5：出口侧按任意固定周期（长 1—3 的全部 0/1 串，含全部相位）就绪时，
所有循环里若 Φ 最小值 ≥ S，则 C 在循环的每一刻结束时都不空转（手里总有一批）。
这对应第 4 节「C 从不断料」一步；它不依赖出口侧怎样运行，只用到 B 通道每刻至多取 1 件。"""
import itertools, json, sys, time
sys.path.insert(0, '.')
import cell_exhaustive as ce
IDLE = ce.IDLE


def run(m, L1, L2):
    t0 = time.time()
    S, stall, phi, closure, states = ce.make(m, L1, L2)
    pats = [p for n in (1, 2, 3) for p in itertools.product((0, 1), repeat=n)]
    res = dict(m=m, L1=L1, L2=L2, S=S, patterns=len(pats), cycles=0, cycles_phi_ge_S=0, bad=0, c_idle_cycles_phi_lt_S=0)
    ex = None
    for pat in pats:
        P = len(pat)
        for pol in ('preferA', 'preferB', 'alt'):
            def step(key):
                s, p, ph = key
                ready = bool(pat[ph])
                if pol == 'preferA': cands = [(1, 1), (1, 0), (0, 1), (0, 0)]
                elif pol == 'preferB': cands = [(1, 1), (0, 1), (1, 0), (0, 0)]
                else: cands = [(1, 1), (1, 0), (0, 1), (0, 0)] if p == 0 else [(1, 1), (0, 1), (1, 0), (0, 0)]
                for fa, fb in cands:
                    r = closure(s, ready, fa, fb)
                    if r is not None:
                        nst, a, b, _, cst = r
                        np_ = p
                        if pol == 'alt' and a + b == 1:
                            np_ = 1 if a else 0
                        return (nst, np_, (ph + 1) % P), nst[0][1] == IDLE
                raise RuntimeError
            visited = set()
            for s0 in states:
                for p0 in ((0, 1) if pol == 'alt' else (0,)):
                    for ph0 in range(P):
                        k = (s0, p0, ph0)
                        if k in visited:
                            continue
                        path = []; pos = {}
                        while k not in visited and k not in pos:
                            pos[k] = len(path)
                            nk, cidle = step(k)
                            path.append((k, cidle))
                            k = nk
                        if k in pos:
                            cyc = path[pos[k]:]
                            res['cycles'] += 1
                            pmin = min(phi(x[0][0]) for x in cyc)
                            anyidle = any(x[1] for x in cyc)
                            if pmin >= S:
                                res['cycles_phi_ge_S'] += 1
                                if anyidle:
                                    res['bad'] += 1
                                    ex = ex or (pat, pol, [x[0] for x in cyc][:4])
                            elif anyidle:
                                res['c_idle_cycles_phi_lt_S'] += 1
                        for x in path:
                            visited.add(x[0])
    res['example'] = str(ex)
    res['seconds'] = round(time.time() - t0, 1)
    return res


if __name__ == '__main__':
    from multiprocessing import Pool
    params = [(2, 1, 1), (3, 1, 1), (3, 2, 1), (3, 1, 2), (3, 2, 2), (4, 1, 1), (4, 2, 1), (2, 2, 2), (4, 1, 2)]
    with Pool(2) as pool:
        out = pool.starmap(run, params)
    json.dump(dict(results=out, total_bad=sum(o['bad'] for o in out)), sys.stdout, ensure_ascii=False, indent=1)
