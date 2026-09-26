#!/usr/bin/env python3
"""第81轮B：研磨机双主料锁死的来路示意（局部示意，不是全厂布局，也不是证明的一部分）。

一台研磨机，5 条存货通道，每条是长 3 的传送带队列：
  c1、c2 送蓝铁粉末，c4、c5 送源石粉末，两组按 40 tick 周期各开 20 tick（混做研磨机，两种主料轮流）；
  c3 送砂叶粉末，每 tick 1 件，只在 [W, W+L) 断供（示意胶囊满时混做荞花/砂叶的粉碎机被荞花粉末堵住）。
规则取法：存货格每格一种、上限 50，同种只占一格；开批要满足配方用量，1 tick 一批；
运输格滞留至少 1 tick；首件被拒就停在原地；首件进机的轮询次序按通道编号轮转，
判定先后取“开批先于移动”与“移动先于开批”两种，全部轮询起点都跑一遍。
对照：去掉 c4、c5（单主料研磨机），同样断供。
"""
import json, os
from pathlib import Path

os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
HERE = Path(__file__).resolve().parent
CAP = 50
REC = [({'蓝铁粉末': 2, '砂叶粉末': 1}, '致密蓝铁粉末'), ({'源石粉末': 2, '砂叶粉末': 1}, '致密源石粉末')]


def sources(W, L, mixed):
    def src(ch, t):
        ph = t % 40
        if ch in (0, 1):
            return '蓝铁粉末' if ph < 20 else None
        if ch == 2:
            return None if W <= t < W + L else '砂叶粉末'
        if ch in (3, 4):
            return ('源石粉末' if ph >= 20 else None) if mixed else None
    return src


def accept(slots, k):
    if k in slots:
        return slots[k] < CAP
    return len(slots) < 2


def run(W, L, mixed, order, token0, T=400):
    slots = {'蓝铁粉末': 20, '砂叶粉末': 20}
    q = [[None] * 3 for _ in range(5)]  # q[c][0] 是首格
    src = sources(W, L, mixed)
    token = token0
    made = []
    locked_at = None
    for t in range(T):
        def manufacture():
            for rec, out in REC:
                if all(slots.get(k, 0) >= a for k, a in rec.items()):
                    for k, a in rec.items():
                        slots[k] -= a
                        if slots[k] == 0:
                            del slots[k]
                    return 1
            return 0
        def moves():
            nonlocal token
            # 首件进机：轮询，尝试后立刻传给下一条；成功后接着再试直到一轮都不成功
            progress = True
            while progress:
                progress = False
                for i in range(5):
                    c = (token + i) % 5
                    h = q[c][0]
                    if h is not None and h[1] < t and accept(slots, h[0]):
                        slots[h[0]] = slots.get(h[0], 0) + 1
                        q[c][0] = None
                        token = (c + 1) % 5
                        progress = True
                        break
            # 队列前移（从首格往后，已滞留的前移一格）
            for c in range(5):
                for j in range(1, 3):
                    it = q[c][j]
                    if it is not None and q[c][j - 1] is None and it[1] < t:
                        q[c][j - 1] = (it[0], t)
                        q[c][j] = None
                k = src(c, t)
                if k is not None and q[c][2] is None:
                    q[c][2] = (k, t)
        if order == 'make_first':
            b = manufacture(); moves()
        else:
            moves(); b = manufacture()
        made.append(b)
        pr = [k for k in slots if k != '砂叶粉末']
        if len(pr) == 2 and locked_at is None:
            locked_at = t
    after = sum(made[W + L + 80:])
    return dict(locked_at=locked_at, final_slots=dict(slots), batches_before=sum(made[:W]),
                batches_last=after, ticks_last=T - (W + L + 80))


out = []
for mixed in (True, False):
    for L in (0, 30):
        for order in ('make_first', 'move_first'):
            for token0 in range(5):
                W = 105  # 蓝铁粉末 在格、砂叶断供，随后源石粉末开始到达
                r = run(W, L, mixed, order, token0)
                r.update(mixed=mixed, starve_len=L, order=order, token0=token0)
                out.append(r)
summ = {}
for r in out:
    key = f"{'混做' if r['mixed'] else '单主料'}·断供{r['starve_len']}"
    s = summ.setdefault(key, dict(runs=0, locked=0, min_last=10**9, max_last=0, ticks_last=r['ticks_last']))
    s['runs'] += 1
    s['locked'] += r['locked_at'] is not None
    s['min_last'] = min(s['min_last'], r['batches_last'])
    s['max_last'] = max(s['max_last'], r['batches_last'])
for k, v in summ.items():
    print(k, v)
(HERE / 'grinder_lock_demo.json').write_text(json.dumps(dict(summary=summ, runs=out), ensure_ascii=False, indent=1))
