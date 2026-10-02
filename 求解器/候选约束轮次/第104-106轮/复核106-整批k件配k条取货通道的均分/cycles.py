#!/usr/bin/env python3
"""循环均分的独立核对：不用「差至多 2」，直接看状态图里的每个环。

状态：(首格剩余步数, 取货格件数)，本机在空首格中任选（覆盖任何级别、次序、成功记录、
离线读法），整批 bsize 件可在任一步开头进入（放宽，件数不超过 cap）。
边带上这一步哪一路成功。对每个强连通分量、每一路 j，尝试给节点赋势 phi_j，使每条分量内的边
满足 phi_j(v) = phi_j(u) + [成功的是第 0 路] - [成功的是第 j 路]。
能赋上 <=> 分量内每个环上第 0 路与第 j 路件数相等。
对照：bsize=1（不是整批）应当找到不等的环。
"""
import json, sys, time
from collections import deque


def build(k, cap, bsize):
    start = []
    for inv in range(cap + 1):
        start.append(((0,) * k, inv))
    idx, nodes, edges = {}, [], []
    dq = deque()
    for s in start:
        idx[s] = len(nodes); nodes.append(s); edges.append([]); dq.append(s)
    while dq:
        s = dq.popleft()
        cells, inv = s
        c2 = tuple(c - 1 if c > 0 else 0 for c in cells)
        outs = []
        for add in (0, bsize):
            if inv + add > cap:
                continue
            i2 = inv + add
            free = [i for i in range(k) if c2[i] == 0]
            if i2 == 0 or not free:
                outs.append(((c2, i2), -1))
            else:
                for x in free:
                    c3 = list(c2); c3[x] = 8
                    outs.append(((tuple(c3), i2 - 1), x))
        for t, x in outs:
            if t not in idx:
                idx[t] = len(nodes); nodes.append(t); edges.append([]); dq.append(t)
            edges[idx[s]].append((idx[t], x))
    return nodes, edges


def scc(n, edges):
    index = [-1] * n; low = [0] * n; onst = [False] * n; comp = [-1] * n
    st = []; c = 0; counter = 0
    for root in range(n):
        if index[root] != -1:
            continue
        work = [(root, 0)]
        index[root] = low[root] = counter; counter += 1; st.append(root); onst[root] = True
        while work:
            v, i = work[-1]
            if i < len(edges[v]):
                work[-1] = (v, i + 1)
                w = edges[v][i][0]
                if index[w] == -1:
                    index[w] = low[w] = counter; counter += 1; st.append(w); onst[w] = True
                    work.append((w, 0))
                elif onst[w]:
                    low[v] = min(low[v], index[w])
            else:
                work.pop()
                if work:
                    u = work[-1][0]
                    low[u] = min(low[u], low[v])
                if low[v] == index[v]:
                    while True:
                        w = st.pop(); onst[w] = False; comp[w] = c
                        if w == v:
                            break
                    c += 1
    return comp, c


def check(k, cap, bsize):
    nodes, edges = build(k, cap, bsize)
    comp, nc = scc(len(nodes), edges)
    bad = 0; witness = None; cyc_comps = 0
    members = {}
    for v, cv in enumerate(comp):
        members.setdefault(cv, []).append(v)
    for cv, mem in members.items():
        inner = any(comp[w] == cv for v in mem for w, _ in edges[v])
        if not inner:
            continue
        cyc_comps += 1
        for j in range(1, k):
            phi = {mem[0]: 0}
            dq = deque([mem[0]])
            ok = True
            while dq and ok:
                v = dq.popleft()
                for w, x in edges[v]:
                    if comp[w] != cv:
                        continue
                    d = (1 if x == 0 else 0) - (1 if x == j else 0)
                    if w not in phi:
                        phi[w] = phi[v] + d; dq.append(w)
                    elif phi[w] != phi[v] + d:
                        ok = False
                        if witness is None:
                            witness = dict(route=j, state=str(nodes[v]))
                        break
            if not ok:
                bad += 1
    return dict(states=len(nodes), sccs_with_cycle=cyc_comps, unequal_components=bad,
                witness=witness)


def main(out):
    jobs = [(2, 50, 2), (3, 50, 3), (4, 16, 4), (5, 10, 5), (2, 20, 1), (3, 12, 1)]
    res = {}
    for k, cap, b in jobs:
        t0 = time.time()
        r = check(k, cap, b)
        r['sec'] = round(time.time() - t0, 1)
        key = 'k%d-cap%d-batch%d' % (k, cap, b)
        res[key] = r
        print(key, r, flush=True)
    json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'cycles.json')
