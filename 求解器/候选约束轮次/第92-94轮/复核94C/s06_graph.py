#!/usr/bin/env python3
"""S06 抽象状态图（自写，不用 sim2、不用推导席脚本）。

一台机器的取货格（件数 o，封顶 cap）由整批 k 件进入，相邻两批进格至少隔 8 步
（1 tick 配方的最快节奏；更慢的配方是其子集）。k 条取货通道同属一级，
取货侧顺序：从未成功的在前（按接通先后，离线可任意重排这部分），
其余按上次成功从早到晚。每条首格收件后滞留至少 8 步。

模式 exact：首格收件后恰在第 8 步、机器判定前移出（修正版前提）。
  检查：从“全空”起每次成功都落在队首 —— 等价于成功序列按固定循环轮转。
模式 window：旧条文“每刻就绪”，固定 θ=0，每个 [8n,8n+8) 内每条首格都有空着的时点；
  移出时刻由下游任意决定（年龄 >=8 才能移出）。检查：是否存在两路取件数之差非零的环。
"""
import json, sys
ALLINIT = True
from collections import deque


def run_exact(k, cap):
    # 状态：(cells, queue, never, o, s)
    # cells: tuple，每格 -1 空 或 年龄 0..7（本步开始时的年龄）
    # queue: 尝试顺序（含从未成功的，从未成功者在前）
    # never: 从未成功集合（frozenset）
    import itertools
    init = []
    for perm in itertools.permutations(range(k)):
        for nn in range(k + 1):
            never = frozenset(perm[:nn])
            for o in range(cap + 1):
                for s in range(9):
                    init.append(((-1,) * k, perm, never, o, s))
    seen = set(init)
    dq = deque(init)
    edges = 0
    viol = []
    while dq:
        st = dq.popleft()
        cells, queue, never, o, s = st
        # 阶段1：可选整批进格
        opts = [False]
        if s >= 8 and o + k <= cap:
            opts.append(True)
        for arrive in opts:
            o1 = o + k if arrive else o
            s1 = 0 if arrive else min(s + 1, 8)
            # 离线：从未成功的前缀可任意重排
            nevers = [q for q in queue if q in never]
            rest = [q for q in queue if q not in never]
            prefixes = list(itertools.permutations(nevers)) if nevers else [()]
            for pre in prefixes:
                q0 = list(pre) + rest
                # 阶段2：年龄 8 的移出（exact）
                c = [(-1 if (x == 8) else x) for x in cells]
                # 年龄在本步开始时 = x；x==8 意味着收件后第8步 -> 移出
                # 阶段3：机器判定
                succ = None
                if o1 > 0:
                    for ch in q0:
                        if c[ch] == -1:
                            succ = ch
                            break
                o2 = o1
                nq = q0
                nv = never
                if succ is not None:
                    if succ != q0[0]:
                        viol.append(dict(state=str(st), succ=succ, order=q0))
                    o2 -= 1
                    c[succ] = 0
                    nq = [x for x in q0 if x != succ] + [succ]
                    nv = never - {succ}
                # 步末年龄+1
                c2 = tuple((-1 if x == -1 else x + 1) for x in c)
                nst = (c2, tuple(nq), frozenset(nv), o2, s1)
                edges += 1
                if nst not in seen:
                    seen.add(nst)
                    dq.append(nst)
    return dict(k=k, cap=cap, states=len(seen), edges=edges, head_violations=len(viol),
                example=viol[:2])


def run_window(k, cap, maxage=15):
    """旧条文“每刻就绪”（θ固定）。找两路取件数差非零的环（k=2 时 w=succ0-succ1）。"""
    import itertools
    # 状态：(phase, cells(年龄或-1), queue, o, s, flags)；只看全部成功过之后（never 空）
    init = []
    cellopts = [-1] + list(range(0, maxage + 1))
    for perm in itertools.permutations(range(k)):
        for o in range(cap + 1):
            for s in range(9):
                if ALLINIT:
                    for cs in itertools.product(cellopts, repeat=k):
                        init.append((0, cs, perm, o, s, (False,) * k))
                else:
                    init.append((0, (-1,) * k, perm, o, s, (False,) * k))
    seen = {}
    adj = {}
    dq = deque(init)
    for x in init:
        seen[x] = True
    while dq:
        st = dq.popleft()
        ph, cells, queue, o, s, flags = st
        out = []
        opts = [False]
        if s >= 8 and o + k <= cap:
            opts.append(True)
        for arrive in opts:
            o1 = o + k if arrive else o
            s1 = 0 if arrive else min(s + 1, 8)
            # 阶段2：每条年龄>=8 的可选移出
            choices = []
            for ch in range(k):
                x = cells[ch]
                if x == -1:
                    choices.append([(x, True)])  # 空着：有空时点
                elif x >= 8:
                    ch_opts = [(-1, True)]
                    if x < maxage:
                        ch_opts.append((x, False))
                    choices.append(ch_opts)
                else:
                    choices.append([(x, False)])
            for combo in itertools.product(*choices):
                c = [cc for cc, _ in combo]
                fl = [flags[i] or combo[i][1] for i in range(k)]
                succ = None
                if o1 > 0:
                    for ch in queue:
                        if c[ch] == -1:
                            succ = ch
                            break
                o2 = o1
                nq = list(queue)
                if succ is not None:
                    o2 -= 1
                    c[succ] = 0
                    nq = [x for x in queue if x != succ] + [succ]
                if ph == 7 and not all(fl):
                    continue
                nph = (ph + 1) % 8
                nfl = (False,) * k if nph == 0 else tuple(fl)
                c2 = tuple((-1 if x == -1 else x + 1) for x in c)
                w = [0] * k
                if succ is not None:
                    w[succ] = 1
                nst = (nph, c2, tuple(nq), o2, s1, nfl)
                out.append((nst, tuple(w)))
                if nst not in seen:
                    seen[nst] = True
                    dq.append(nst)
        adj[st] = out
    # SCC（迭代 Tarjan）
    index = {}
    low = {}
    onst = set()
    stack = []
    sccid = {}
    comp_order = []
    idx = 0
    nodes = list(adj.keys())
    for root in nodes:
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            v, i = work.pop()
            if i == 0:
                index[v] = low[v] = idx
                idx += 1
                stack.append(v)
                onst.add(v)
            recurse = False
            nbrs = adj.get(v, [])
            while i < len(nbrs):
                wv = nbrs[i][0]
                i += 1
                if wv not in index:
                    work.append((v, i))
                    work.append((wv, 0))
                    recurse = True
                    break
                elif wv in onst:
                    low[v] = min(low[v], index[wv])
            if recurse:
                continue
            if low[v] == index[v]:
                comp = []
                while True:
                    x = stack.pop()
                    onst.discard(x)
                    sccid[x] = v
                    comp.append(x)
                    if x == v:
                        break
                comp_order.append(v)
            if work:
                u = work[-1][0]
                low[u] = min(low[u], low[v])
    # 每个 SCC 内对 w_j - w_0 检查势函数
    bad = []
    comps = {}
    for v, r in sccid.items():
        comps.setdefault(r, []).append(v)
    for r, comp in comps.items():
        if len(comp) == 1:
            v = comp[0]
            if not any(n == v for n, _ in adj[v]):
                continue
        cs = set(comp)
        for j in range(1, k):
            pot = {comp[0]: 0}
            dq2 = deque([comp[0]])
            ok = True
            while dq2 and ok:
                v = dq2.popleft()
                for n, w in adj[v]:
                    if n not in cs:
                        continue
                    val = pot[v] + w[j] - w[0]
                    if n not in pot:
                        pot[n] = val
                        dq2.append(n)
                    elif pot[n] != val:
                        ok = False
                        bad.append(dict(scc_size=len(comp), pair=(0, j), at=str(v)))
                        break
            # 无向一致性：上面只沿有向边传播；SCC 内有向可达，足以检出不一致
    # 最大路径失衡（w_j-w_0）：无非零环时按 SCC 势函数加凝聚图 DP
    maxdev = None
    if not bad:
        # 势
        pot = {}
        for r, comp in comps.items():
            cs = set(comp)
            pot[comp[0]] = [0] * k
            dq2 = deque([comp[0]])
            while dq2:
                v = dq2.popleft()
                for n, w in adj[v]:
                    if n in cs and n not in pot:
                        pot[n] = [pot[v][j] + w[j] - w[0] for j in range(k)]
                        dq2.append(n)
        # 按 Tarjan 产出顺序（逆拓扑）计算 L(v)=max 路径权（j=1 对 0），M(v)=min
        order = []
        seenr = set()
        for v in index:  # 不保证顺序；改用 tarjan 完成序：sccid 记录时的顺序
            pass
        res = {}
        for j in range(1, k):
            Lmax = {}
            Lmin = {}
            # 逆拓扑：Tarjan 弹出 SCC 的顺序即逆拓扑序
            for r in comp_order:
                comp = comps[r]
                cs = set(comp)
                best = -10**9
                worst = 10**9
                for u in comp:
                    bu = 0
                    wu = 0
                    for n, w in adj[u]:
                        if n not in cs:
                            bu = max(bu, w[j] - w[0] + Lmax[n] + pot[n][j] - pot[n][j])
                            wu = min(wu, w[j] - w[0] + Lmin[n])
                    best = max(best, pot[u][j] + bu)
                    worst = min(worst, pot[u][j] + wu)
                for v in comp:
                    Lmax[v] = best - pot[v][j]
                    Lmin[v] = worst - pot[v][j]
            res[j] = (max(Lmax.values()), min(Lmin.values()))
        maxdev = res
    return dict(k=k, cap=cap, states=len(adj), sccs=len(comps), nonzero_cycle_sccs=len(bad),
                example=bad[:3], path_imbalance_max_min=maxdev)


if __name__ == '__main__':
    res = {}
    for k in (2, 3):
        res[f'exact_k{k}'] = run_exact(k, 3 * k)
        print(res[f'exact_k{k}'], flush=True)
    res['window_k2_allinit'] = run_window(2, 6)
    print(res['window_k2_allinit'], flush=True)
    json.dump(res, open(__file__.replace('.py', '.json'), 'w'), ensure_ascii=False, indent=1)
