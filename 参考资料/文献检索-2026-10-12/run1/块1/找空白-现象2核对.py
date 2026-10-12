#!/usr/bin/env python3
"""块1-1 的最小核对：现象 2「一支收不下的分流器，另一支降到 8n/(8n+1)」。

两部分，互相独立：
  sim(n, order)  按我对规则的一种读法逐步模拟（不是仓库内核，读法见下）；
  teg(n, b)      加倍定时事件图：正向弧时延 8 步、令牌=物品；元件级反向弧时延 b 步、令牌=空位；
                 用「存在势 r 使 r(v)-r(u) <= 令牌 - Θ·时延」二分求最大 Θ（Bufistov 2008 定理 2.1 的形式）。
读法（没过内核）：元件内物品在步开始和每次元件间移动之后按「下游先」连续前移；
元件间移动按组的级别依次判定；滞留 8 步；S 由上游满箱在非元件阶段补满；末端总收。
布局：S(分流器，另一支堵死) -> seg(n 格，一个元件) -> J(1 格元件) -> seg2(3 格) -> 收货单位。
order 是元件组的判定先后：'S' 表示 S->seg 组，'seg' 表示 seg->J 组，'J' 表示 J->seg2 组，'sink' 表示 seg2->收货。
"""
D = 8

def sim(n, order, m=3, T=80000):
    S, seg, J, seg2 = [-D], [-D]*n, [-D], [-D]*m
    t = 0
    def internal(a):
        ch = True
        while ch:
            ch = False
            for i in range(len(a)-2, -1, -1):
                if a[i] is not None and a[i+1] is None and t - a[i] >= D:
                    a[i+1], a[i] = t, None; ch = True
    outs = []
    for t in range(T):
        internal(seg); internal(seg2)
        for g in order:
            if g == 'sink' and seg2[-1] is not None and t-seg2[-1] >= D:
                seg2[-1] = None; outs.append(t)
            elif g == 'S' and S[0] is not None and t-S[0] >= D and seg[0] is None:
                seg[0], S[0] = t, None
            elif g == 'J' and J[0] is not None and t-J[0] >= D and seg2[0] is None:
                seg2[0], J[0] = t, None
            elif g == 'seg' and seg[-1] is not None and t-seg[-1] >= D and J[0] is None:
                J[0], seg[-1] = t, None
            internal(seg); internal(seg2)
        if S[0] is None:
            S[0] = t
    h = [x for x in outs if x >= T//2]
    return len(h) / ((T - T//2) / D)          # 件/tick

def teg(n, b):
    # 变迁 0..n：第 k 次「物品进 seg 第 k+1 格」(k=0 为 S->seg)，第 n 个为 seg->J
    arcs = []
    for k in range(n):                        # 第 k+1 格：正向（物品，8 步）、格级反向（空位，0 步）
        arcs.append((k, k+1, 1, D)); arcs.append((k+1, k, 0, 0))
    arcs.append((n, 0, 0, b))                 # 元件级反向弧：seg->J 之后 S 才能补，时延 b，令牌=seg 里的空位(堵满时 0)
    arcs.append((0, 0, 1, D)); arcs.append((n, n, 1, D))   # S、J 各自的滞留自环
    def ok(th):
        dist = [0.0]*(n+1)
        for _ in range(n+2):
            ch = False
            for u, v, tok, d in arcs:
                w = tok - th*d
                if dist[u] + w < dist[v] - 1e-12:
                    dist[v] = dist[u] + w; ch = True
            if not ch:
                return True
        return False
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo+hi)/2
        lo, hi = (mid, hi) if ok(mid) else (lo, mid)
    return lo*D                               # 件/tick

if __name__ == '__main__':
    print('n  模拟:下游先  模拟:S先于seg->J  事件图b=0  事件图b=1  8n/(8n+1)')
    for n in range(1, 6):
        print(n, round(sim(n, ['sink','J','seg','S']), 4), round(sim(n, ['sink','S','J','seg']), 4),
              round(teg(n, 0), 4), round(teg(n, 1), 4), round(8*n/(8*n+1), 4))
