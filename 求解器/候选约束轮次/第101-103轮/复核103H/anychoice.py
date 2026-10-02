#!/usr/bin/env python3
"""复核103H：H05 的「跨离线差至多 2、循环均分」是否与选路规则无关。
把本机在空首格之间的选择完全交给对手（不看轮询、级别），穷举抽象状态（同 polling.py 的库存放宽）。
若仍 e<=2，则首单位为无其他来路的汇流器（取货优先级自成一级）时这两项结论照样成立。
另：对照「单件到货」应出现 e>2。"""
import json, sys
from collections import deque

def bfs_any(k, single=False, limit=2):
    add = 1 if single else k
    E = 3 * k
    def inv_add(c):
        if c[0] == 'x':
            v = c[1] + add
            return ('x', v) if v < E else ('b', v % k)
        return ('b', (c[1] + add) % k)
    def inv_sub(c):
        if c[0] == 'x':
            return [('x', c[1] - 1)]
        r = c[1]
        return [('b', k - 1), ('x', E - 1)] if r == 0 else [('b', r - 1)]
    invs = [('x', v) for v in range(E)] + [('b', r) for r in range(k)]
    init = [((0,) * k, c, 0) for c in invs]
    seen = set(init); dq = deque(init); maxe = 0; bad = False
    while dq:
        r, c, e = dq.popleft()
        for when in (0, 1, 2):
            c1 = inv_add(c) if when == 1 else c
            has = not (c1[0] == 'x' and c1[1] == 0)
            free = [i for i in range(k) if r[i] == 0]
            branches = []
            if has and free:
                for ch in free:   # 对手任选一个空首格；本机有货且有空首格时必送（「依次尝试」直到成功）
                    rr = list(r); rr[ch] = 8
                    d = 1 if ch == 0 else (-1 if ch == 1 else 0)
                    for c2 in inv_sub(c1):
                        branches.append((tuple(rr), c2, max(0, e + d)))
            else:
                branches.append((r, c1, e))
            for (r3, c3, e3) in branches:
                if when == 2: c3 = inv_add(c3)
                r4 = tuple(max(0, x - 1) for x in r3)
                maxe = max(maxe, e3)
                if e3 > limit:
                    bad = True; continue
                ns = (r4, c3, e3)
                if ns not in seen:
                    seen.add(ns); dq.append(ns)
    return dict(states=len(seen), violation=bad, max_e=maxe)

res = {}
for k in (2, 3, 4):
    res[f'k{k}_batch_anychoice'] = bfs_any(k)
for k in (2, 3):
    res[f'k{k}_single_anychoice_control'] = bfs_any(k, single=True)
json.dump(res, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False))
