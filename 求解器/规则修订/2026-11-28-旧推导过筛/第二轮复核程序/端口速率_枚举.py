# 端口速率：一个容量 1、滞留 8 步的运输物品格，经它的某个存货端口进格、某个取货端口出格。
# 穷举 N 步内所有满足「格里至多 1 件、进格后停满 8 步才可出格、出格同一步可再进下一件」的进出序列，
# 求任意连续 8 步（1 tick）内经同一端口通过的最大件数。
from functools import lru_cache
N = 40
best = {'in': 0, 'out': 0}
# 状态：(t, 格里是否有货, 进格步, 最近若干次进/出的时刻)
import itertools

def explore():
    maxin = maxout = 0
    # 用 DFS：每步可选 [出格?][进格?]；同一步先出后进（同一步内移动有先后、耗时 0）
    stack = [(0, None, (), ())]  # (t, enter_step or None, ins, outs)
    seen = set()
    while stack:
        t, e, ins, outs = stack.pop()
        def win(xs):
            return max((sum(1 for y in xs if x <= y < x + 8) for x in xs), default=0)
        maxin = max(maxin, win(ins)); maxout = max(maxout, win(outs))
        if t == N:
            continue
        key = (t, None if e is None else min(t - e, 8), ins[-2:] if ins else (), outs[-2:] if outs else ())
        key = (t, e, ins[-1:] , outs[-1:])
        if key in seen: continue
        seen.add(key)
        opts = []
        # 不动
        opts.append((e, ins, outs))
        cur_e, cur_ins, cur_outs = e, ins, outs
        # 出格
        if e is not None and t - e >= 8:
            e2, outs2 = None, outs + (t,)
            opts.append((e2, ins, outs2))
            # 出后同一步再进
            opts.append((t, ins + (t,), outs2))
        if e is None:
            opts.append((t, ins + (t,), outs))
        for (ne, ni, no) in opts:
            stack.append((t + 1, ne, ni, no))
    return maxin, maxout

mi, mo = explore()
print('任意连续 8 步内同一存货端口最多进格', mi, '件；同一取货端口最多出格', mo, '件')
# 对照：若把桥接器一条边上的存货、取货两个端口当成一个，两相邻桥接器同轴两方向各走 1 件可在同一步通过同一条边
print('同一条边两方向各 1 件同步通过时合计 2 件（只说明桥的一条边上是两个端口，不能合并计）')
