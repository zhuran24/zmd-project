#!/usr/bin/env python3
"""停机态三份修正版的两处数字核对（三审自写，只用标准库，配方从正式游戏规则现读）。

一、机型下限：按两种成品 3/5、11/20 个/tick，只有两种矿石从仓库来、其余物品不入库，
    用分数逐级倒推各配方批次率，乘配方时长得各机型每 tick 所需加工时间，向上取整即台数下限。
二、研磨机进入两种主料占格的走法：两个存货物品格只放蓝铁粉末、源石粉末、荞花粉末、砂叶粉末（没有误料），
    同种只占一格、每格 1—50 件；列出全部「进一件」「开一批」的一步转移，数出从不是两种主料占格到两种主料占格的全部转移，
    并核两种主料占格以后再也开不了批、也离不开这个状态。
"""
import json
import math
from fractions import Fraction as Fr
from itertools import product

from engine import RECIPES

MAIN = ['蓝铁粉末', '源石粉末', '荞花粉末']
SAND = '砂叶粉末'


def lower_bounds():
    rec = {}
    for typ, rs in RECIPES.items():
        for ins, out, n, d in rs:
            rec.setdefault(out, []).append((typ, ins, n, d))
    need = {'高容谷地电池': Fr(3, 5), '精选荞愈胶囊': Fr(11, 20)}
    work = {}
    batches = {}

    def add(typ, ins, n, d, rate_out):
        b = rate_out / n
        work[typ] = work.get(typ, 0) + b * d
        batches[(typ, tuple(sorted(ins)))] = batches.get((typ, tuple(sorted(ins))), 0) + b
        for it, a in ins.items():
            need[it] = need.get(it, 0) + b * a

    order = ['高容谷地电池', '精选荞愈胶囊', '钢制零件', '钢质瓶', '致密源石粉末', '细磨荞花粉末', '钢块',
             '致密蓝铁粉末', '蓝铁粉末', '源石粉末', '蓝铁块']
    for it in order:
        opts = [r for r in rec[it] if it != '蓝铁块' or '蓝铁矿' in r[1]]   # 蓝铁粉末回炼 r=0
        typ, ins, n, d = opts[0]
        add(typ, ins, n, d, need[it])
    # 植物：粉碎用量 f、采种 a、种植 z：2a=z，z=a+f
    sand_powder = need.get('砂叶粉末', 0)
    q_powder = need.get('荞花粉末', 0)
    for plant, pw, k in (('砂叶', sand_powder, 3), ('荞花', q_powder, 2)):
        f = pw / k
        a = f
        z = 2 * a
        work['粉碎机'] += f
        work['采种机'] = work.get('采种机', 0) + a
        work['种植机'] = work.get('种植机', 0) + z
    return {k: (str(v), math.ceil(v)) for k, v in work.items()}


def grinder_states():
    items = MAIN + [SAND]
    cells = [None] + [(it, n) for it in items for n in range(1, 51)]
    states = []
    for a, b in product(cells, cells):
        if a and b and a[0] == b[0]:
            continue
        states.append((a, b))
    return states


def is_double_main(s):
    a, b = s
    return bool(a and b and a[0] in MAIN and b[0] in MAIN)


def arrive(s, x):
    a, b = s
    for idx, c in enumerate((a, b)):
        if c and c[0] == x:
            if c[1] >= 50:
                return None
            n = list(s)
            n[idx] = (x, c[1] + 1)
            return tuple(n)
    for idx, c in enumerate((a, b)):
        if c is None:
            n = list(s)
            n[idx] = (x, 1)
            return tuple(n)
    return None


def starts(s):
    out = []
    cnt = {c[0]: c[1] for c in s if c}
    for ins, _, _, _ in RECIPES['研磨机']:
        if all(cnt.get(k, 0) >= v for k, v in ins.items()):
            n = []
            for c in s:
                if c and c[0] in ins:
                    left = c[1] - ins[c[0]]
                    n.append((c[0], left) if left else None)
                else:
                    n.append(c)
            out.append(tuple(n))
    return out


def grinder_check():
    states = grinder_states()
    enter_arrive = enter_start = 0
    kinds = {}
    leave = 0
    for s in states:
        succ = [(('进', x), arrive(s, x)) for x in MAIN + [SAND]] + [(('开批',), t) for t in starts(s)]
        for how, t in succ:
            if t is None:
                continue
            if is_double_main(s):
                if not is_double_main(t):
                    leave += 1
                continue
            if is_double_main(t):
                if how[0] == '开批':
                    enter_start += 1
                else:
                    enter_arrive += 1
                    a, b = s
                    filled = a if a else b
                    empty = (a is None) or (b is None)
                    key = 'one_main_one_empty' if empty and filled and filled[0] in MAIN and how[1] != filled[0] else 'other'
                    kinds[key] = kinds.get(key, 0) + 1
    dm_can_start = sum(1 for s in states if is_double_main(s) and starts(s))
    return dict(states=len(states), enter_by_arrival=enter_arrive, enter_by_start=enter_start, entry_kinds=kinds,
                double_main_can_start=dm_can_start, double_main_leave_transitions=leave)


if __name__ == '__main__':
    print(json.dumps(dict(机型下限=lower_bounds(), 研磨机两种主料占格=grinder_check()), ensure_ascii=False))
