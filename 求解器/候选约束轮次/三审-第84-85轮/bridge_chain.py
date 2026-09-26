#!/usr/bin/env python3
"""三审自写：存货首件死锁里「上一个运输单位是桥接器」的永久性核对。

放宽模型（比规则宽，只可能多出可达状态）：M 的一条存货通道的上一个单位是一串同轴桥接器
c_1…c_L（c_1 贴 M），远端单位 V 对这一轴的那条边只有三种可能：只取货（向链供货）、
只存货（从链收货）、没有端口。忽略滞留（任何时刻任何合法移动都可以发生），
每件物品带「刚离开的单位」标记：可以是链上相邻格、V，或「无」（调试期遗留、来路已拆，
向两边都可走）。M 此刻只收「好」物品，c_1 的首件是「坏」物品（收不下）。
问：能否到达 c_1 放着「好」物品的状态（那样 M 就能收到新件）。结论应为：不能。
"""
import itertools
import json
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
EMPTY = None


# 位置 0 是 M 一侧（物品不会从 M 来），1..L 是链格，L+1 是 V。


def moves(state, L, far):
    """state: tuple of cells 1..L, each None or (kind, came_from) with came_from in {i-1,i+1,'none'}"""
    cells = list(state)
    out = []
    for idx in range(L):
        pos = idx + 1
        it = cells[idx]
        if it is EMPTY:
            continue
        kind, came = it
        # 向 M（位置 0）：只有 c_1，且 M 只收好物品
        if pos == 1 and came != 0 and kind == 'good':
            out.append(('M收到', None))
        # 向链上相邻格
        for nxt in (pos - 1, pos + 1):
            if nxt < 1 or nxt > L:
                continue
            if came == nxt:
                continue
            if cells[nxt - 1] is EMPTY:
                new = cells[:]
                new[nxt - 1] = (kind, pos)
                new[idx] = EMPTY
                out.append(('移', tuple(new)))
        # 向 V
        if pos == L and far == 'sink' and came != L + 1:
            new = cells[:]
            new[idx] = EMPTY
            out.append(('进V', tuple(new)))
    # V 供货
    if far == 'supply' and cells[L - 1] is EMPTY:
        for kind in ('good', 'bad'):
            new = cells[:]
            new[L - 1] = (kind, L + 1)
            out.append(('V供', tuple(new)))
    return out


def run(L, far):
    starts = []
    per_cell = []
    for pos in range(1, L + 1):
        opts = [EMPTY]
        for kind in ('good', 'bad'):
            for came in (pos - 1, pos + 1, 'none'):
                if pos == 1 and came == 0:
                    continue  # 物品不会从 M 来（M 这条边只有存货端口）
                if pos == L and came == L + 1 and far != 'supply':
                    continue  # V 不供货就不会有从 V 来的物品
                opts.append((kind, came))
        per_cell.append(opts)
    for combo in itertools.product(*per_cell):
        if combo[0] is EMPTY or combo[0][0] != 'bad':
            continue  # 前提：c_1 放着收不下的首件
        starts.append(tuple(combo))
    seen = set(starts)
    dq = deque(starts)
    received = 0
    while dq:
        s = dq.popleft()
        for tag, ns in moves(s, L, far):
            if tag == 'M收到':
                received += 1
                continue
            if ns not in seen:
                seen.add(ns)
                dq.append(ns)
    return {'链长': L, '远端': far, '起态数': len(starts), '可达状态数': len(seen), 'M收到新件的次数': received}


def control():
    """对照：c_1 空着、远端供货时，M 应能收到新件（说明检查查得出）。"""
    L, far = 3, 'supply'
    start = (None, None, None)
    seen = {start}
    dq = deque([start])
    got = 0
    while dq:
        s = dq.popleft()
        for tag, ns in moves(s, L, far):
            if tag == 'M收到':
                got += 1
                continue
            if ns not in seen:
                seen.add(ns)
                dq.append(ns)
    return got


def main():
    ctrl = control()
    print('对照（c_1 空、远端供货）M 收到新件的转移数:', ctrl)
    assert ctrl > 0
    res = []
    for L in range(1, 6):
        for far in ('supply', 'sink', 'none'):
            r = run(L, far)
            res.append(r)
            print(r)
    ok = all(r['M收到新件的次数'] == 0 for r in res)
    (HERE / 'out' / 'bridge_chain.json').write_text(json.dumps({'全部不能收到新件': ok, '对照收到次数': ctrl, '明细': res}, ensure_ascii=False, indent=1))
    print('全部不能收到新件:', ok)


if __name__ == '__main__':
    main()
