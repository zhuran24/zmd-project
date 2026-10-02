#!/usr/bin/env python3
"""复核94E 抽查：步进规则下「混做连续批次出货」能否加强。

一台粉碎机混做砂叶（每批 3 件砂叶粉末）与源矿（每批 1 件源石粉末；平均每批才能是 2 件），只有两条取货通道、两条都接受两种粉末。
放宽状态图同 c45_seed_mc.py（自写，同一套规则落实），另记「上一批开的是哪种」。
求：最大批次率（应为 1 批/tick）；在势函数紧边子图的强连通部分（含全部满载循环）里，是否有「连开两批砂叶」的边。
若没有，则步进规则下这种满载粉碎机连续砂叶批次至多一批（正式条目写的是至多两批，仍成立但不紧）。
"""
import json
from array import array
from fractions import Fraction
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

K = {0: 3, 1: 1}  # 0=砂叶粉末 3 件/批，1=源石粉末（或蓝铁粉末）1 件/批
NP, NK, NC, NL = 19, 101, 10, 3  # NL: 上一批种类 0/1/无(2)


def enc(prod, pick, c0, c1, last):
    return ((((prod * NK + pick) * NC + c0) * NC + c1) * NL) + last


def dec(i):
    last = i % NL; i //= NL
    c1 = i % NC; i //= NC
    c0 = i % NC; i //= NC
    pick = i % NK; i //= NK
    return i, pick, c0, c1, last


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
    return None if v == 0 else ((v - 1) // 50, (v - 1) % 50 + 1)


def try_move(prod, pick):
    info = p_info(prod)
    if info[0] == 'done':
        kind = info[1]; pi = pk_info(pick)
        if pi is None:
            return 0, pk(kind, K[kind])
        if pi[0] == kind and pi[1] + K[kind] <= 50:
            return 0, pk(kind, pi[1] + K[kind])
    return prod, pick


def trans(i):
    prod, pick, c0, c1, last = dec(i)
    info = p_info(prod)
    if info[0] == 'run':
        r = info[2] - 1
        prod = 17 + info[1] if r == 0 else p_run(info[1], r)
    ch = [0 if c == 0 else min(c + 1, 9) for c in (c0, c1)]
    prod, pick = try_move(prod, pick)
    out = []
    for d0 in ([ch[0]] if ch[0] != 9 else [9, 0]):
        for d1 in ([ch[1]] if ch[1] != 9 else [9, 0]):
            chs = [d0, d1]
            send_opts = [(pick, tuple(chs))]
            pi = pk_info(pick)
            if pi is not None:
                for j in (0, 1):
                    if chs[j] == 0:
                        nc = list(chs); nc[j] = 1
                        send_opts.append((pk(pi[0], pi[1] - 1), tuple(nc)))
            for (pick2, chs2) in send_opts:
                prod2, pick3 = try_move(prod, pick2)
                outs = [(prod2, 0, 0, last)]
                if prod2 == 0:
                    for kd in (0, 1):
                        outs.append((p_run(kd, 8), 1, 1 if (kd == 0 and last == 0) else 0, kd))
                for (prod3, w, flag, last2) in outs:
                    out.append((enc(prod3, pick3, chs2[0], chs2[1], last2), w, flag))
    return out


def main():
    N = NP * NK * NC * NC * NL
    src, dst, w, fl = array('i'), array('i'), array('b'), array('b')
    for i in range(N):
        for (t, ww, f) in trans(i):
            src.append(i); dst.append(t); w.append(ww); fl.append(f)
    src = np.frombuffer(src, dtype=np.int32).astype(np.int64)
    dst = np.frombuffer(dst, dtype=np.int32).astype(np.int64)
    w = np.frombuffer(w, dtype=np.int8).astype(np.int64)
    fl = np.frombuffer(fl, dtype=np.int8).copy()
    lam = Fraction(1, 8)
    wp = 8 * w - 1
    starts = np.flatnonzero(np.r_[True, src[1:] != src[:-1]])
    assert len(starts) == N
    h = np.zeros(N, dtype=np.int64)
    for it in range(100000):
        nh = np.maximum(h, np.maximum.reduceat(wp + h[dst], starts))
        if np.array_equal(nh, h):
            break
        h = nh
    ok = bool(np.all(h[src] >= wp + h[dst]))
    tight = h[src] == wp + h[dst]
    ts, td, tf = src[tight], dst[tight], fl[tight]
    g = csr_matrix((np.ones(len(ts)), (ts, td)), shape=(N, N))
    ncomp, lab = connected_components(g, directed=True, connection='strong')
    intra = lab[ts] == lab[td]
    # 满载循环是否存在（紧子图里有非平凡强连通分量）；是否含「连开两批砂叶」
    rec = dict(states=N, edges=int(len(src)), max_rate_le_1_certificate=ok, bf_iterations=it,
               tight_scc_edges=int(intra.sum()), consecutive_sand_in_full_rate_cycles=int((tf[intra] == 1).sum()))
    # 对照：如果允许最大率低一点，连开两批砂叶是否可行（找含 flag 的任意循环）
    all_g = csr_matrix((np.ones(len(src)), (src, dst)), shape=(N, N))
    nc2, lab2 = connected_components(all_g, directed=True, connection='strong')
    rec['consecutive_sand_possible_in_some_cycle'] = bool(((fl == 1) & (lab2[src] == lab2[dst])).any())
    print(rec)
    json.dump(rec, open(__file__.replace('.py', '.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
