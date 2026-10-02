#!/usr/bin/env python3
"""复核94E：一台每批 2 件、配方 1 tick 的制造单位（采种机）+ 两条取货通道的放宽状态图。

自写，不导入推导席脚本或 sim2。按快照规则第 13、17—18、23—27、36 行：
- 每步：先结束到时的制造（开工后第 8 步开头结束，产物进缓存格）；缓存里做好的一批在取货物品格空着或同种且放得下（≤50）时整批进格
  （随时移动，每个微相位后都试）；再判定元件（两条通道的首运输物品格：成熟 8 步后可被下游取走，放宽为取或不取）；
  再判定本机（至多送出一件到一个空着且接受该种的通道首格，放宽为也可不送）；最后开始能开始的制造（放宽为可开可不开、种类任选，原料视作充足）。
- 取货物品格只放一种物品，上限 50。
变体：
  restricted ：通道 j 只接受第 j 种（每种种子各至多一路）——候选「制造取货连续同种段步数界」的 8/9；
  unrestricted：两通道都接受两种——候选「满载采种双路逐种均分」：满速 1 批/tick 时每种在两路均分；
  single     ：只做一种、只走一路——1/2。
最大平均开工数用整数势函数证书核验（reduceat 版 Bellman-Ford）；达到性用确定性策略跑循环。
逐种均分：在势函数的紧边子图（含全部最优循环）里，对每个强连通分量检查「某种经通道0件数−经通道1件数」是上边界（coboundary），
即紧子图里每个循环该差为 0。
"""
import json, sys, itertools
from fractions import Fraction
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

NP, NK, NC = 19, 101, 10  # prod, pick, ch


def enc(prod, pick, c0, c1):
    return ((prod * NK + pick) * NC + c0) * NC + c1


def dec(i):
    c1 = i % NC; i //= NC
    c0 = i % NC; i //= NC
    pick = i % NK; i //= NK
    return i, pick, c0, c1


def p_run(kind, r):
    return 1 + kind * 8 + (r - 1)


def p_info(p):
    if p == 0:
        return ('idle',)
    if p <= 16:
        return ('run', (p - 1) // 8, (p - 1) % 8 + 1)
    return ('done', p - 17)


def pk(kind, cnt):
    return 0 if cnt == 0 else 1 + kind * 50 + (cnt - 1)


def pk_info(v):
    if v == 0:
        return None
    return ((v - 1) // 50, (v - 1) % 50 + 1)


def try_move(prod, pick):
    info = p_info(prod)
    if info[0] == 'done':
        kind = info[1]
        pi = pk_info(pick)
        if pi is None:
            return 0, pk(kind, 2)
        if pi[0] == kind and pi[1] + 2 <= 50:
            return 0, pk(kind, pi[1] + 2)
    return prod, pick


def trans(i, accepts, kinds):
    prod, pick, c0, c1 = dec(i)
    # 1 结束到时的制造 + 通道格变老
    info = p_info(prod)
    if info[0] == 'run':
        r = info[2] - 1
        prod = 17 + info[1] if r == 0 else p_run(info[1], r)
    ch = [0 if c == 0 else min(c + 1, 9) for c in (c0, c1)]
    prod, pick = try_move(prod, pick)
    out = []
    # 3 元件判定：成熟（编码 9=年龄 8）的通道首格可被取走或不取
    drain_opts = [[c] if c != 9 else [c, 0] for c in ch]
    for d0 in drain_opts[0]:
        for d1 in drain_opts[1]:
            chs = [d0, d1]
            # 4 本机判定
            send_opts = [(pick, tuple(chs), None)]
            pi = pk_info(pick)
            if pi is not None:
                for j in (0, 1):
                    if chs[j] == 0 and pi[0] in accepts[j]:
                        nc = list(chs); nc[j] = 1
                        send_opts.append((pk(pi[0], pi[1] - 1), tuple(nc), (pi[0], j)))
            for (pick2, chs2, sent) in send_opts:
                prod2, pick3 = try_move(prod, pick2)
                # 6 开工
                st_opts = [(prod2, 0)]
                if prod2 == 0:
                    for kd in kinds:
                        st_opts.append((p_run(kd, 8), 1))
                for (prod3, w) in st_opts:
                    out.append((enc(prod3, pick3, chs2[0], chs2[1]), w, sent))
    return out


def build(accepts, kinds):
    from array import array
    N = NP * NK * NC * NC
    src, dst, w, sk, sj = array('i'), array('i'), array('b'), array('b'), array('b')
    for i in range(N):
        for (t, ww, sent) in trans(i, accepts, kinds):
            src.append(i); dst.append(t); w.append(ww)
            sk.append(-1 if sent is None else sent[0]); sj.append(-1 if sent is None else sent[1])
    return (N, np.frombuffer(src, dtype=np.int32).astype(np.int64), np.frombuffer(dst, dtype=np.int32).astype(np.int64),
            np.frombuffer(w, dtype=np.int8).astype(np.int64), np.frombuffer(sk, dtype=np.int8).copy(),
            np.frombuffer(sj, dtype=np.int8).copy())


def potential(N, src, dst, wp, maxit=100000):
    starts = np.flatnonzero(np.r_[True, src[1:] != src[:-1]])
    assert len(starts) == N
    h = np.zeros(N, dtype=np.int64)
    for it in range(maxit):
        cand = wp + h[dst]
        nh = np.maximum(h, np.maximum.reduceat(cand, starts))
        if np.array_equal(nh, h):
            return h, it
        h = nh
    return None, maxit


def policy_rate(accepts, kinds, alternate=True, steps=4000):
    """确定性策略：总是取走成熟件、能送就送（通道 0 优先）、能开就开，种类逐批轮换（或只做 kinds[0]）。"""
    i = enc(0, 0, 0, 0)
    nextkind = 0
    seen = {}
    ws = []
    t = 0
    while True:
        key = (i, nextkind % len(kinds))
        if key in seen:
            t0 = seen[key]
            cyc = ws[t0:]
            return Fraction(8 * sum(cyc), len(cyc)), len(cyc)
        seen[key] = t
        best = None
        for (tt, ww, sent) in trans(i, accepts, kinds):
            prod, pick, c0, c1 = dec(tt)
            # 偏好：两格都取走（不存在年龄 8 留格）、送了、开了且种类对
            info = p_info(prod)
            started_kind = info[1] if (ww == 1) else None
            if ww == 1 and alternate and started_kind != kinds[nextkind % len(kinds)]:
                continue
            score = (c0 != 9) + (c1 != 9), sent is not None, ww
            if best is None or score > best[0]:
                best = (score, tt, ww)
        _, i, ww = best
        if ww == 1:
            nextkind += 1
        ws.append(ww)
        t += 1


def balance_check(N, src, dst, wp, h, sk, sj):
    tight = (h[src] == wp + h[dst])
    ts, td = src[tight], dst[tight]
    res = {}
    if len(ts) == 0:
        return dict(tight_edges=0)
    g = csr_matrix((np.ones(len(ts)), (ts, td)), shape=(N, N))
    ncomp, lab = connected_components(g, directed=True, connection='strong')
    intra = lab[ts] == lab[td]
    es, ed = ts[intra], td[intra]
    out = dict(tight_edges=int(len(ts)), scc_edges=int(len(es)))
    for kind in (0, 1):
        imb = np.where((sk[tight][intra] == kind) & (sj[tight][intra] == 0), 1, 0) - \
              np.where((sk[tight][intra] == kind) & (sj[tight][intra] == 1), 1, 0)
        # BFS 赋势
        pot = {}
        adj = {}
        for a, b, v in zip(es.tolist(), ed.tolist(), imb.tolist()):
            adj.setdefault(a, []).append((b, v))
            adj.setdefault(b, []).append((a, -v))
        ok = True
        for s0 in adj:
            if s0 in pot:
                continue
            pot[s0] = 0
            stack = [s0]
            while stack:
                u = stack.pop()
                for (v, d) in adj[u]:
                    # 边 u->v 上 imb=d 要求 pot[u]-pot[v]=d
                    want = pot[u] - d
                    if v in pot:
                        if pot[v] != want:
                            ok = False
                    else:
                        pot[v] = want; stack.append(v)
        out[f'kind{kind}_coboundary'] = ok
        out[f'kind{kind}_nonzero_imb_edges'] = int(np.count_nonzero(imb))
    return out


def main():
    variants = {
        'restricted': (({0}, {1}), (0, 1), Fraction(1, 9)),
        'unrestricted': (({0, 1}, {0, 1}), (0, 1), Fraction(1, 8)),
        'single': (({0}, set()), (0,), Fraction(1, 16)),
    }
    which = sys.argv[1:] or list(variants)
    results = {}
    for name in which:
        accepts, kinds, lam = variants[name]
        N, src, dst, w, sk, sj = build(accepts, kinds)
        wp = lam.denominator * w - lam.numerator
        h, it = potential(N, src, dst, wp)
        ok = h is not None and bool(np.all(h[src] >= wp + h[dst]))
        pr, plen = policy_rate(accepts, kinds, alternate=(len(kinds) > 1))
        rec = dict(states=N, edges=int(len(src)), claimed_max_batches_per_tick=str(lam * 8), certificate_ok=ok,
                   bf_iterations=it, policy_rate=str(pr), policy_cycle_steps=plen, tight=(pr == lam * 8))
        if name == 'unrestricted' and ok:
            rec['balance'] = balance_check(N, src, dst, wp, h, sk, sj)
        print(name, rec, flush=True)
        results[name] = rec
    json.dump(results, open(__file__.replace('.py', '_' + '_'.join(which) + '.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
