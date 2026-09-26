#!/usr/bin/env python3
"""B 组（停机态合计）里研磨机两格状态的独立枚举：
1) 进入「两格两种主料」（乙）的全部一步转移，看是否只有「一格主料、一格空、另一种主料进空格」；
2) 大制造单位纯料两格：凡凑不齐一批的库存，是否存在两种原料的首件都收不下（即纯料不入丙）；
3) 丙的「收不下」判定与规则逐字一致：同种格满 50，或无同种格且两格都有货。"""
import json, itertools
CAP = 50
MAIN = ['蓝铁粉末', '源石粉末', '荞花粉末']
SAND = '砂叶粉末'
KINDS = MAIN + [SAND]
REC = [{m: 2, SAND: 1} for m in MAIN]


def states():
    cells = [None] + [(k, c) for k in KINDS for c in range(1, CAP + 1)]
    for a in cells:
        for b in cells:
            if a is not None and b is not None and a[0] == b[0]:
                continue
            yield (a, b)


def is_yi(s):
    ks = [g[0] for g in s if g is not None]
    return len(ks) == 2 and all(k in MAIN for k in ks)


def can_accept(s, k):
    for g in s:
        if g is not None and g[0] == k:
            return g[1] < CAP
    return any(g is None for g in s)


def accept(s, k):
    s = list(s)
    for i, g in enumerate(s):
        if g is not None and g[0] == k:
            s[i] = (k, g[1] + 1); return tuple(s)
    for i, g in enumerate(s):
        if g is None:
            s[i] = (k, 1); return tuple(s)


def stock(s, k):
    for g in s:
        if g is not None and g[0] == k:
            return g[1]
    return 0


def starts(s):
    out = []
    for r in REC:
        if all(stock(s, k) >= a for k, a in r.items()):
            t = list(s)
            for i, g in enumerate(t):
                if g is not None and g[0] in r:
                    c = g[1] - r[g[0]]
                    t[i] = None if c == 0 else (g[0], c)
            out.append(tuple(t))
    return out


n = 0; into_yi = []; start_into_yi = 0
for s in states():
    n += 1
    if is_yi(s):
        continue
    for k in KINDS:
        if can_accept(s, k):
            t = accept(s, k)
            if is_yi(t):
                into_yi.append((s, k))
    for t in starts(s):
        if is_yi(t):
            start_into_yi += 1
shape_ok = all((a is None) != (b is None) and ((a or b)[0] in MAIN) and k in MAIN and k != (a or b)[0] for (a, b), k in into_yi)
res = {'grinder_states': n, 'into_yi_transitions': len(into_yi), 'all_are_one_main_one_empty_other_main': shape_ok,
       'start_into_yi': start_into_yi}

# 2) 纯料大机：配方 aA+bB，两格只放 A、B；凑不齐一批时两种首件同时收不下的库存数
pure = {}
for name, (A, a, B, b) in {'研磨蓝铁': ('蓝铁粉末', 2, SAND, 1), '研磨源石': ('源石粉末', 2, SAND, 1),
                            '研磨荞花': ('荞花粉末', 2, SAND, 1), '封装': ('钢制零件', 10, '致密源石粉末', 15),
                            '灌装': ('钢质瓶', 10, '细磨荞花粉末', 10)}.items():
    bad = 0; short = 0
    for xa in range(0, CAP + 1):
        for xb in range(0, CAP + 1):
            s = tuple(g for g in ((A, xa) if xa else None, (B, xb) if xb else None))
            if xa >= a and xb >= b:
                continue
            short += 1
            if not can_accept(s, A) and not can_accept(s, B):
                bad += 1
    pure[name] = {'short_states': short, 'both_first_items_refused': bad}
res['pure_two_material'] = pure
print(json.dumps(res, ensure_ascii=False, indent=1))
