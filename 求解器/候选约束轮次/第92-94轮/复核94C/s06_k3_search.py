#!/usr/bin/env python3
"""S06 旧条文循环态部分的线索搜索（k=3）：固定 θ=0 的“每刻就绪”下，有没有周期运行让三条通道流量不等。
抽象模型（与 s06_graph.py 同一套语义）：每条通道按“收件时的相位 p”决定滞留 D∈[8, 15-p]（p=0 时 ≤15），
这是固定 θ 下每刻都有空着时点的充要条件；整批 3 件按周期模式尝试进格（相隔≥8 步，取货格≤50）。
只搜周期策略，是启发式搜索，不是穷举。"""
import json, random, math


def simulate(k, D, arr, T, queue0, steps=4000):
    L = T * 8 // math.gcd(T, 8)
    cells = [-1] * k     # 收件后已过步数，-1 空
    rec = [0] * k        # 收件相位
    queue = list(queue0)
    o = 0
    last_arr = -100
    seen = {}
    counts = [0] * k
    hist = []
    for t in range(steps):
        # 阶段1
        if (t % T) in arr and t - last_arr >= 8 and o + k <= 50:
            o += k
            last_arr = t
        # 阶段2：按策略移出
        for i in range(k):
            if cells[i] >= 0 and cells[i] >= D[i][rec[i]]:
                cells[i] = -1
        # 阶段3：机器判定
        if o > 0:
            for ch in queue:
                if cells[ch] == -1:
                    cells[ch] = 0
                    rec[ch] = t % 8
                    o -= 1
                    counts[ch] += 1
                    queue.remove(ch)
                    queue.append(ch)
                    break
        for i in range(k):
            if cells[i] >= 0:
                cells[i] += 1
        key = (t % L, tuple(cells), tuple(rec), tuple(queue), o, min(t - last_arr, 9))
        hist.append(tuple(counts))
        if key in seen:
            t0 = seen[key]
            c0 = hist[t0]
            diff = tuple(counts[i] - c0[i] for i in range(k))
            return diff, t - t0, t0
        seen[key] = t
    return None, None, None


def run(nsamp, seed):
    rng = random.Random(seed)
    k = 3
    found = []
    nper = 0
    for s in range(nsamp):
        D = [[rng.randint(8, 15 if p == 0 else max(8, 15 - p)) for p in range(8)] for _ in range(k)]
        # 偏置：让一条通道多半短滞留，一条长滞留
        if rng.random() < 0.5:
            D[0] = [8] * 8
        T = rng.choice([8, 16, 24, 32, 40, 48, 56, 64])
        arr = set()
        for x in range(T):
            if rng.random() < 0.3:
                arr.add(x)
        queue0 = rng.sample(range(k), k)
        diff, per, t0 = simulate(k, D, arr, T, queue0)
        if diff is None:
            continue
        nper += 1
        if len(set(diff)) > 1:
            found.append(dict(D=D, T=T, arr=sorted(arr), queue0=queue0, diff=diff, period=per, t0=t0))
            if len(found) >= 5:
                break
    return dict(samples=nsamp, periodic=nper, unequal=len(found), examples=found)


if __name__ == '__main__':
    res = run(40000, 77)
    json.dump(res, open('s06_k3_search.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False)[:3000])
