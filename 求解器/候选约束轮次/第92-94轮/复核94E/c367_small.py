#!/usr/bin/env python3
"""复核94E：候选「满速取货的逐步相位」「研磨单路换主料步数余量」「接箱末格失败判定收费」的小型独立核对。自写，只用标准库。

A 相位（编码一，状态图）：一个非运输单位每步至多送一件，接 c 条通道，各通道首运输物品格成熟 8 步后下游可取可不取（放宽）。
  求最大平均送出率（势函数证书），并在紧边子图的强连通部分里检查：各通道首格在每步末都有货、年龄两两不同（=余数互异且固定）。
A 相位（编码二，枚举）：周期 P∈{8,16,24}，枚举每步「送往哪条通道或不送」的循环时序，满足同通道循环间隔≥8，
  取每条通道恰 P/8 件的全部时序，检查每条通道的送货步余数唯一、各通道余数互异。
C 研磨换主料：前批（主料 P1）在第 s 步末开工之后，求后批改用 P2 的最早开工步。P2 只有一条存货通道（冷却 8 步），
  砂叶粉末、P1 来货放宽为每步任意件；存货物品格两格、一格一种、同种只占一格、上限 50；
  起态枚举开工后两格剩余（P1 0..3、砂叶粉末 0..3）。对照：P2 有两条通道。
D 接箱：一个只往箱子送货的运输物品格，箱子每步可收可拒（放宽），格空时上游可补可不补。
  编码一：势函数证明每个循环里 8·出件+成熟拒收次数 ≤ 步数；编码二：绝对步号记事件的随机运行，逐件核对停留 ≥ 8+拒收次数。
"""
import itertools, json
from collections import deque


def potential(nodes, edges, maxit=10 ** 6):
    h = {v: 0 for v in nodes}
    for it in range(maxit):
        ch = False
        for (a, b, w) in edges:
            if w + h[b] > h[a]:
                h[a] = w + h[b]; ch = True
        if not ch:
            return h, it
        if it > len(nodes) + 5:
            return None, it
    return None, maxit


def scc(nodes, edges):
    adj = {v: [] for v in nodes}
    radj = {v: [] for v in nodes}
    for a, b in edges:
        adj[a].append(b); radj[b].append(a)
    order, seen = [], set()
    for v in nodes:
        if v in seen:
            continue
        stack = [(v, iter(adj[v]))]; seen.add(v)
        while stack:
            u, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                order.append(u); stack.pop()
            elif nxt not in seen:
                seen.add(nxt); stack.append((nxt, iter(adj[nxt])))
    comp = {}
    for v in reversed(order):
        if v in comp:
            continue
        comp[v] = v; st = [v]
        while st:
            u = st.pop()
            for w in radj[u]:
                if w not in comp:
                    comp[w] = v; st.append(w)
    return comp


# ---------- A 相位 ----------
E = -1


def unit_graph(c):
    vals = [E] + list(range(9))
    nodes = list(itertools.product(vals, repeat=c))
    edges = []
    for s in nodes:
        aged = [x if x == E else min(x + 1, 8) for x in s]
        drain_opts = [[x] if x != 8 else [x, E] for x in aged]
        for d in itertools.product(*drain_opts):
            outs = [(tuple(d), 0)]
            for j in range(c):
                if d[j] == E:
                    nd = list(d); nd[j] = 0
                    outs.append((tuple(nd), 1))
            for (t, w) in outs:
                edges.append((s, t, w))
    return nodes, edges


def phase_mc(c):
    nodes, edges = unit_graph(c)
    k = min(c, 8)
    wp = [(a, b, 8 * w - k) for (a, b, w) in edges]
    h, it = potential(nodes, wp)
    ok = h is not None and all(h[a] >= w + h[b] for (a, b, w) in wp)
    tight = [(a, b) for (a, b, w) in wp if h[a] == w + h[b]]
    comp = scc(nodes, tight)
    inscc = set()
    for a, b in tight:
        if comp[a] == comp[b]:
            inscc.add(a); inscc.add(b)
    # 紧子图循环上的状态：每格都有货、年龄两两不同、年龄<8（步末）
    good = all(all(x != E and x < 8 for x in s) and len(set(s)) == c for s in inscc)
    return dict(c=c, states=len(nodes), edges=len(edges), max_rate_per_tick=k, certificate_ok=ok,
                tight_cycle_states=len(inscc), all_full_distinct_ages=good)


def phase_enum(c, P):
    """枚举周期 P 的时序：每步送往通道 0..c-1 之一或不送；每通道恰 P/8 件且循环间隔≥8。"""
    need = P // 8
    found = 0
    bad = 0
    sched = [None] * P
    cnt = [0] * c

    def ok_cyclic(seq):
        for j in range(c):
            ts = [t for t in range(P) if seq[t] == j]
            if len(ts) != need:
                return False
            for a, b in zip(ts, ts[1:] + [ts[0] + P]):
                if b - a < 8:
                    return False
        return True

    def rec(t):
        nonlocal found, bad
        if t == P:
            if ok_cyclic(sched):
                found += 1
                res = []
                for j in range(c):
                    rs = {tt % 8 for tt in range(P) if sched[tt] == j}
                    if len(rs) != 1:
                        bad += 1; return
                    res.append(rs.pop())
                if len(set(res)) != c:
                    bad += 1
            return
        rem = P - t
        if sum(need - x for x in cnt) > rem:
            return
        for j in list(range(c)) + [None]:
            if j is not None:
                if cnt[j] >= need:
                    continue
                # 线性间隔剪枝
                last = max((tt for tt in range(t) if sched[tt] == j), default=None)
                if last is not None and t - last < 8:
                    continue
                cnt[j] += 1
            sched[t] = j
            rec(t + 1)
            sched[t] = None
            if j is not None:
                cnt[j] -= 1

    rec(0)
    return dict(c=c, P=P, full_rate_schedules=found, violating=bad)


# ---------- C 研磨换主料 ----------
def grinder_gap(p2_channels=1):
    best = None
    detail = {}
    for p1 in range(0, 4):
        for sa in range(0, 4):
            cells = []
            if p1:
                cells.append(('P1', p1))
            if sa:
                cells.append(('S', sa))
            start = (tuple(sorted(cells)), (0,) * p2_channels, 8)  # 冷却全部就绪（最宽），在制剩 8 步
            q = deque([(start, 0)])
            seen = {start}
            found = None
            while q:
                (cl, cds, r), t = q.popleft()
                if t > 40:
                    break
                t1 = t + 1
                r1 = max(0, r - 1)
                cds1 = tuple(max(0, x - 1) for x in cds)
                d = dict(cl)
                # 判定：P2 每条就绪通道可送 0/1 件；砂叶粉末任意 0..3 件；P1 任意 0..2 件（只会占格）
                nready = sum(1 for x in cds1 if x == 0)
                for k2 in range(nready + 1):
                    for ks in range(0, 4):
                        for k1 in range(0, 3):
                            for perm in itertools.permutations([('P2', k2), ('S', ks), ('P1', k1)]):
                                dd = dict(d); okk = True
                                for kind, k in perm:
                                    if k == 0:
                                        continue
                                    if kind in dd:
                                        if dd[kind] + k > 50:
                                            okk = False; break
                                        dd[kind] += k
                                    elif len(dd) < 2:
                                        dd[kind] = k
                                    else:
                                        okk = False; break
                                if not okk:
                                    continue
                                used = 0; cds2 = list(cds1)
                                for i in range(len(cds2)):
                                    if used < k2 and cds2[i] == 0:
                                        cds2[i] = 8; used += 1
                                # 开工：上一批已结束（r1==0）且有 2 件 P2、1 件砂叶粉末
                                if r1 == 0 and dd.get('P2', 0) >= 2 and dd.get('S', 0) >= 1:
                                    found = t1 if found is None else min(found, t1)
                                    continue
                                key = (tuple(sorted(dd.items())), tuple(cds2), r1)
                                if key not in seen:
                                    seen.add(key); q.append((key, t1))
                if found is not None:
                    break
            detail[f'P1剩{p1}_砂叶剩{sa}'] = found
            if found is not None:
                best = found if best is None else min(best, found)
    return dict(p2_channels=p2_channels, min_gap_steps=best, by_start=detail)


# ---------- D 接箱 ----------
def box_mc():
    nodes = [E] + list(range(9))
    edges = []
    for s in nodes:
        a = s if s == E else min(s + 1, 8)
        opts = []
        if a == 8:
            opts.append((E, 1, 0))   # 箱收下
            opts.append((8, 0, 1))   # 箱拒收：耗掉本步判定
        else:
            opts.append((a, 0, 0))
        for (b, snd, f) in opts:
            for t in ([b, 0] if b == E else [b]):
                edges.append((s, t, 8 * snd + f - 1))
    h, it = potential(nodes, edges)
    ok = h is not None and all(h[a] >= w + h[b] for (a, b, w) in edges)
    return dict(states=len(nodes), edges=len(edges), certificate_no_positive_cycle=ok)


def box_enum(runs=200, steps=400, seed=1):
    """编码二：用绝对进格步号（不是年龄）记事件，随机箱子收/拒、随机上游补货，逐件核对
    出格步−进格步 ≥ 8+该件成熟后被拒次数，并对整段核对 8·出件+拒收次数 ≤ 观测步数+首件残余。"""
    import random
    rnd = random.Random(seed)
    viol = 0; items = 0
    for r in range(runs):
        pacc = rnd.random(); pfill = rnd.random()
        cur = None  # (进格步, 拒收次数)
        for t in range(steps):
            if cur is not None and t - cur[0] >= 8:
                if rnd.random() < pacc:
                    if t - cur[0] < 8 + cur[1]:
                        viol += 1
                    items += 1
                    cur = None
                else:
                    cur = (cur[0], cur[1] + 1)
            if cur is None and rnd.random() < pfill:
                cur = (t, 0)
    return dict(runs=runs, steps=steps, items=items, violations=viol)


def main():
    out = {}
    out['phase_mc'] = [phase_mc(c) for c in (1, 2, 3)]
    out['phase_enum'] = [phase_enum(c, P) for c in (1, 2, 3, 4, 6) for P in (8, 16) if not (c >= 4 and P == 16)] + \
                        [phase_enum(c, 24) for c in (1, 2)]
    out['grinder_one_channel'] = grinder_gap(1)
    out['grinder_two_channels'] = grinder_gap(2)
    out['box_mc'] = box_mc()
    out['box_enum'] = box_enum()
    json.dump(out, open(__file__.replace('.py', '.json'), 'w'), ensure_ascii=False, indent=1)
    for k, v in out.items():
        print(k, v)


if __name__ == '__main__':
    main()
