#!/usr/bin/env python3
"""三审第 86—87 轮：「整批k件配k条取货通道的均分」里「段首件数」的读法（本目录自写）。

一台制造单位的取货物品格（上限 cap）只由整批进入、每批 k 件；k 条取货通道的首运输物品格只从它收货。
时间取 1/q tick 格点：批的开工、完成与各首格旧货何时被下游拿走（满 1 tick 后）都由随机对手定，
一个时刻里整批进格、各通道取货、下游拿走按随机先后做到没有可动为止。「刻」从随机起点 θ 起每 q 个子步一段。
一条通道在某刻「就绪」：这一刻里某个时点（含一个时刻的判定之间）首格是空的。
对每一段「k 条每刻都就绪」的连续刻，核：
  (a) 段内任两条通道取件数之差 ≤ 1；
  (b) 段首件数按「这一刻第一个时刻的判定之前」读，是 k 的倍数时，段内每刻都是全取或全不取；
  (c) 对照：段首件数改按「这一刻第一个时刻的判定全部完成后」读，同样的断言会不会失败。
用法：python3 -B batch_start.py 种子 次数
"""
import json
import random
import sys


def one_run(rng):
    k = rng.randint(2, 4)
    q = rng.randint(1, 4)
    cap = rng.choice([k, 2 * k, 50])
    steps = rng.randint(20, 120) * q
    theta = rng.randrange(q)
    n = 0 if rng.random() < 0.3 else rng.randint(0, cap)
    first = [None if rng.random() < 0.5 else -rng.randint(0, q) for _ in range(k)]  # 进格子步
    cache = None                      # 缓存格里一批的完成子步
    starve = rng.random() * 0.8       # 缺料概率
    open_p = rng.random()             # 下游收货概率
    kinds = []                        # 每刻：(段首判定前件数, 段首判定后件数, 各口就绪, 各口取件)
    cur = None
    for t in range(steps):
        if (t - theta) % q == 0 and t >= theta:
            if cur is not None:
                kinds.append(cur)
            cur = {'pre': n, 'post': None, 'ready': [False] * k, 'took': [0] * k}
        # 开工：缓存格空时随机决定有没有料
        if cache is None and rng.random() > starve:
            cache = t + q
        downstream = [rng.random() < open_p for _ in range(k)]
        while True:
            mv = []
            if cache is not None and cache <= t and n + k <= cap:
                mv.append(('enter',))
            for j in range(k):
                if first[j] is None and n > 0:
                    mv.append(('take', j))
                if first[j] is not None and t - first[j] >= q and downstream[j]:
                    mv.append(('leave', j))
            if cur is not None:
                for j in range(k):
                    if first[j] is None:
                        cur['ready'][j] = True
            if not mv:
                break
            m = rng.choice(mv)
            if m[0] == 'enter':
                n += k
                cache = None
                # 同一时刻上一批进格后可以立刻开下一批（有料时）
                if rng.random() > starve:
                    cache = t + q
            elif m[0] == 'take':
                j = m[1]; first[j] = t; n -= 1
                if cur is not None:
                    cur['took'][j] += 1
            else:
                j = m[1]; first[j] = None
                if cur is not None:
                    cur['ready'][j] = True
        if cur is not None and cur['post'] is None:
            cur['post'] = n
    # 只核完整的刻
    res = {'segments': 0, 'diff_viol': 0, 'pre_mult_segments': 0, 'pre_viol': 0,
           'post_mult_segments': 0, 'post_viol': 0}
    ready_all = [all(c['ready']) for c in kinds]
    i = 0
    while i < len(kinds):
        if not ready_all[i]:
            i += 1
            continue
        j = i
        while j < len(kinds) and ready_all[j]:
            j += 1
        # 极大段 [i, j)；其中每个起点 s 起的子段
        for s in range(i, j):
            cum = [0] * k
            mixed_seen = False
            for e in range(s, j):
                took = kinds[e]['took']
                cum = [a + b for a, b in zip(cum, took)]
                res['segments'] += 1
                if max(cum) - min(cum) > 1:
                    res['diff_viol'] += 1
                if 0 < sum(took) < k or len(set(took)) > 1:
                    mixed_seen = True
            if kinds[s]['pre'] % k == 0:
                res['pre_mult_segments'] += 1
                res['pre_viol'] += mixed_seen
            if kinds[s]['post'] % k == 0:
                res['post_mult_segments'] += 1
                res['post_viol'] += mixed_seen
        i = j
    return res


def main():
    seed, runs = int(sys.argv[1]), int(sys.argv[2])
    rng = random.Random(seed)
    agg = {}
    for _ in range(runs):
        for key, v in one_run(rng).items():
            agg[key] = agg.get(key, 0) + v
    agg['runs'] = runs
    agg['seed'] = seed
    print(json.dumps(agg, ensure_ascii=False))


if __name__ == '__main__':
    main()
