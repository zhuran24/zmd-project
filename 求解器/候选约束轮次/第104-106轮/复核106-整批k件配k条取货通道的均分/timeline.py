#!/usr/bin/env python3
"""编码 B：按绝对时刻记账的随机运行（与 graph.py 不共用代码）。

本机：只做 1 件原料 -> k 件产物、时长 8 步的配方；原料随机到达存货格（上限 50）；
每步开头先结束到时的制造，缓存格的一批在取货格放得下时整批进入（上限 50），
本机判定时按选路规则送 1 件，步末能开就开下一批（上一批已全部进入取货格）。
首格：第 t 步收的件在第 t+8 步本机判定之前腾空（候选的前件，具体单位怎样做到见 sim2_check.py）。
离线（两步之间，随机）：retain 只换接通先后；clear 全部记录清空并换接通先后；
partial 随机一部分清空。汇流器情形（merge）离线时级别的先后也可变。
检查（全部用逐对暴力枚举连续子词，O(n^2)）：
  g   从起点起任一时间段两路件数差的最大值
  s   不含离线的段内的最大值
  srot 段内是否固定轮转；grot 整个词是否固定轮转
"""
import json, random, sys


def max_pair_diff(word, k):
    n = len(word)
    best = 0
    for a in range(n):
        cnt = [0] * k
        for b in range(a, n):
            cnt[word[b]] += 1
            d = max(cnt) - min(cnt)
            if d > best:
                best = d
    return best


def is_rotation(word, k):
    for idx, x in enumerate(word):
        if idx < k:
            if x in word[:idx]:
                return False
        elif x != word[idx - k]:
            return False
    return True


def run(rng, k, policy, offmode, steps):
    raw = rng.choice([0, 0, 1, 2, 5, rng.randint(0, 50)])
    out = rng.choice([0, 1, k - 1, k, k + 1, 2 * k, rng.randint(0, 50)])
    running = None if rng.random() < 0.5 else rng.randint(1, 8)  # 剩余步数
    cache = 0
    p_raw = rng.choice([0.01, 0.02, 0.04, 0.06, 0.09, 0.125, 0.2, 1.0])
    p_off = rng.choice([0.0, 0.01, 0.05, 0.2])
    conn = list(range(k)); rng.shuffle(conn)           # 接通名次
    last = [None if rng.random() < 0.5 else -rng.randint(1, 100) for _ in range(k)]
    recv = [-10 ** 6] * k                                 # 起点首格全空
    mfirst = rng.random() < 0.5
    word, segs, cur = [], [], []
    for t in range(steps):
        if t > 0 and rng.random() < p_off:
            segs.append(cur); cur = []
            rng.shuffle(conn)
            if offmode == 'clear':
                last = [None] * k
            elif offmode == 'partial':
                last = [None if rng.random() < 0.5 else v for v in last]
            mfirst = rng.random() < 0.5
        # 步开头：结束到时的制造，缓存整批进取货格
        if running is not None:
            running -= 1
            if running == 0:
                running = None; cache = k
        if cache and out + cache <= 50:
            out += cache; cache = 0
        if rng.random() < p_raw and raw < 50:
            raw += 1
        # 本机判定
        if out > 0:
            free = [i for i in range(k) if t >= recv[i] + 8]
            pick = None
            if free:
                if policy == 'any':
                    pick = rng.choice(free)
                else:
                    def key(i):
                        return (0, conn[i], 0) if last[i] is None else (1, 0, last[i])
                    if policy == 'lru':
                        pick = min(free, key=key)
                    else:  # merge：第 0 路是汇流器、自成一级
                        if mfirst and 0 in free:
                            pick = 0
                        else:
                            ordin = [i for i in free if i != 0]
                            pick = min(ordin, key=key) if ordin else 0
            if pick is not None:
                out -= 1; recv[pick] = t; last[pick] = t
                word.append(pick); cur.append(pick)
                if cache and out + cache <= 50:   # 腾出位置后整批立即进入
                    out += cache; cache = 0
        # 步末：开始能开始的制造
        if running is None and cache == 0 and raw > 0:
            raw -= 1; running = 8
    segs.append(cur)
    return word, segs, p_off


def main(out, seed, n):
    rng = random.Random(seed)
    res = {}
    for k in (2, 3):
        for policy in ('lru', 'merge', 'any'):
            for offmode in ('retain', 'clear', 'partial'):
                agg = dict(runs=0, max_g=0, max_s=0, srot_fail=0, grot_fail=0,
                           grot_fail_with_offline=0, attain_g2=0)
                for _ in range(n):
                    word, segs, p_off = run(rng, k, policy, offmode, rng.choice([240, 480]))
                    g = max_pair_diff(word, k)
                    s = max(max_pair_diff(sg, k) for sg in segs)
                    agg['runs'] += 1
                    agg['max_g'] = max(agg['max_g'], g)
                    agg['max_s'] = max(agg['max_s'], s)
                    agg['attain_g2'] += (g == 2)
                    if not all(is_rotation(sg, k) for sg in segs):
                        agg['srot_fail'] += 1
                    if not is_rotation(word, k):
                        agg['grot_fail'] += 1
                        if len(segs) > 1:
                            agg['grot_fail_with_offline'] += 1
                key = '%d-%s-%s' % (k, policy, offmode)
                res[key] = agg
                print(key, agg, flush=True)
    json.dump(res, open(out, 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
