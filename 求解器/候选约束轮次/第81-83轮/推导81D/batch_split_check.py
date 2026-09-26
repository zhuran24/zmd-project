#!/usr/bin/env python3
"""「一批 k 件、k 条取货通道」的均分引理，两种写法互核。

写法甲（逐件模拟）：取货格初存 s0 件（0..m），每刻可能先有一批 k 件整批进入（格内放得下才进），
k 条通道各有首格；对手决定每条通道本刻首格空不空（就绪）、判定次序与轮询指针（离线可改）。
就绪通道每刻至多取 1 件；闭包时就绪且没取到的通道，格内必为 0。
检查：在「全部通道每刻都就绪」的任一时间段里，各通道取到件数的最大差 ≤1；
      段内「有通道就绪却没取到」的刻至多 1 个，且只在段首格内件数不是 k 的倍数时出现。
写法乙（穷举）：小 m、小 k，状态=（格内件数、机器是否有待出一批），对全部对手选择穷举长度 ≤T 的段，
      求各通道件数差的最大值。
"""
import itertools, json, random, sys


def instant(s, has_batch, k, m, order, ptr):
    """返回 (新 s, 每条通道取到否, 本刻是否进了一批, 新 ptr)。全部通道就绪。"""
    took = [0] * k
    passed = False
    changed = True
    while changed:
        changed = False
        for tp in order:
            if tp == 'pass':
                if has_batch and not passed and s + k <= m:
                    s += k; passed = True; changed = True
            else:
                j = tp
                if took[j] or s < 1:
                    continue
                movable = [i for i in range(k) if not took[i]]
                # 从指针起第一条能动的
                first = None
                for d in range(k):
                    c = (ptr + d) % k
                    if c in movable:
                        first = c; break
                if first != j:
                    continue
                took[j] = 1; s -= 1; ptr = (j + 1) % k; changed = True
    return s, took, passed, ptr


def sim(seed):
    rng = random.Random(seed)
    k = rng.choice([2, 3, 4])
    m = rng.choice([50, 7, 10])
    s = rng.randint(0, m)
    ptr = rng.randrange(k)
    counts = [0] * k
    partial = 0
    first_s = s
    for t in range(rng.choice([10, 100, 1000])):
        has_batch = rng.random() < rng.choice([0.3, 0.8, 1.0])
        order = ['pass'] + list(range(k))
        rng.shuffle(order)
        if rng.random() < 0.3:
            ptr = rng.randrange(k)
        s, took, passed, ptr = instant(s, has_batch, k, m, order, ptr)
        for j in range(k):
            counts[j] += took[j]
        if 0 < sum(took) < k or (sum(took) == 0 and False):
            partial += 1
        if sum(took) < k and s != 0:
            return dict(seed=seed, bad='ready-not-taken-but-stock', s=s)
    diff = max(counts) - min(counts)
    ok = diff <= 1 and partial <= 1 and (partial == 0 or first_s % k != 0)
    return dict(seed=seed, k=k, m=m, diff=diff, partial=partial, first_s=first_s, ok=ok)


def exhaustive(k, m, T):
    worst = 0
    orders = list(itertools.permutations(['pass'] + list(range(k))))
    frontier = set()
    for s0 in range(m + 1):
        for p0 in range(k):
            frontier.add((s0, p0, (0,) * k, s0 % k == 0))
    for t in range(T):
        nf = set()
        for (s, ptr, cnt, aligned) in frontier:
            for hb in (False, True):
                for newptr in range(k):
                    for order in orders:
                        ns, took, _, np_ = instant(s, hb, k, m, list(order), newptr)
                        nc = [c + d for c, d in zip(cnt, took)]
                        base = min(nc)
                        nc = tuple(c - base for c in nc)
                        worst = max(worst, max(nc))
                        if aligned and max(nc) > 0:
                            return dict(k=k, m=m, T=T, bad='aligned start gave imbalance', state=(s, ptr, cnt))
                        nf.add((ns, np_, nc, aligned))
        frontier = nf
    return dict(k=k, m=m, T=T, worst_diff=worst, final_states=len(frontier))


if __name__ == '__main__':
    res = [sim(i) for i in range(20000)]
    bad = [r for r in res if not r.get('ok')]
    ex = [exhaustive(2, 6, 8), exhaustive(3, 7, 6), exhaustive(4, 9, 4)]
    json.dump(dict(random_runs=len(res), random_bad=bad[:10], exhaustive=ex), sys.stdout, ensure_ascii=False, indent=1)
