#!/usr/bin/env python3
"""三审自写：植物专机一一配对里单台机器取货物品格的下界（取货格从至少 50−k 起，始终至少 50−3k）。

一台 1 tick 配方的机器，每批 k 件，恰 k 条取货通道，原料一直够（配对的首次失败归纳里成立）。
时间取 1/q tick 的格点，相位任意；对手控制：各首格旧物何时被下游取走（至少停满 1 tick 后）、
同一时刻里取货与整批进格的先后（取最坏：先取后进）、哪几条通道拿到货。
起态：取货格 g ∈ [50−k, 50]，缓存格里一批还差任意子步完成、或已完成在等进格，各首格任意。
穷举全部可达状态，求同一时刻内任一时点取货格件数的最小值。
"""
import itertools
import json
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent


def explore(k, q, cap=50):
    E = 'E'
    ages = list(range(q + 1)) + [E]
    starts = []
    for g in range(cap - k, cap + 1):
        for cache in [('run', r) for r in range(q + 1)] + [('wait',)]:  # r=q 即缓存空、放手时刻开批
            for ch in itertools.combinations_with_replacement(ages, k):
                starts.append((g, cache, tuple(sorted(ch, key=str))))
    seen = set(starts)
    dq = deque(starts)
    worst = cap
    while dq:
        g, cache, ch = dq.popleft()
        # 状态里记的是上一时刻结束时的停留子步数；到这一时刻先加 1（封顶 q，q 即已停满 1 tick）
        ch = [c if c == E else min(q, c + 1) for c in ch]
        freeable = [j for j in range(k) if ch[j] != E and ch[j] >= q]
        for fr in itertools.chain.from_iterable(itertools.combinations(freeable, n) for n in range(len(freeable) + 1)):
            c2 = ch[:]
            for j in fr:
                c2[j] = E
            ca = cache
            if ca[0] == 'run' and ca[1] == 0:
                ca = ('wait',)
            empty = [j for j in range(k) if c2[j] == E]
            e = len(empty)
            if ca[0] == 'wait' and g - min(e, g) <= cap - k:
                takes = min(e, g + k)
                lo = g - min(e, g)
                g2 = g + k - takes
                ca2 = ('run', q - 1)  # 进格后立刻开下一批，q 个子步后完成（下一步起算）
            else:
                takes = min(e, g)
                g2 = g - takes
                lo = g2
                ca2 = ca if ca[0] == 'wait' else ('run', ca[1] - 1)
            worst = min(worst, lo)
            for who in itertools.combinations(empty, takes):
                c3 = []
                for j in range(k):
                    if j in who:
                        c3.append(0)
                    elif c2[j] == E:
                        c3.append(E)
                    else:
                        c3.append(c2[j])
                st = (g2, ca2, tuple(sorted(c3, key=str)))
                if st not in seen:
                    seen.add(st)
                    dq.append(st)
    return worst, len(seen)


def main():
    res = []
    for k in (1, 2, 3):
        for q in (1, 2, 3, 4):
            worst, n = explore(k, q)
            res.append({'k': k, '每 tick 子步数 q': q, '取货格最小件数': worst, '条文下界 50−3k': 50 - 3 * k, '可达状态数': n})
            print(res[-1])
    ok = all(r['取货格最小件数'] >= r['条文下界 50−3k'] for r in res)
    (HERE / 'out' / 'pairing_buffer.json').write_text(json.dumps({'全部不低于 50−3k': ok, '明细': res}, ensure_ascii=False, indent=1))
    print('全部不低于 50−3k:', ok)


if __name__ == '__main__':
    main()
