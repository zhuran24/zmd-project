#!/usr/bin/env python3
"""复核94A：「取货分级」严格层数差为什么是必要的——小构型逐取值比较。

构型（只为说明规则第 28、33 行的组合，不是达标布局）：
  机器 M 有两条取货通道：
    chH：M → 汇流器 J（直接接汇流器，自成一级 H）；J → 带 a → 机器 N。
    chW：M → 分流器 P（其余通道合为一级 W）；P → 带 d → 机器 N；P → 带 x → 准入口 y → 机器 N。
  层数：a=1、J=2；d=1；y=1、x=2；P 按 d 数为 2，按 x 数为 3。
  L_H=2，L_W∈{2,3}。
对 chH、chW 两种接通先后 × P 的两种数法，按规则第 33 行比较两级。
编码一：本文件自写的层数递归与级别比较。
编码二：sim2 的 layers_for 与 Unit.channels（非运输单位取货侧按级排序）。
"""
import json, pathlib, sys

down = {'J': ['a'], 'a': [], 'P': ['d', 'x'], 'd': [], 'x': ['y'], 'y': []}
def layers(choice):
    memo = {}
    def L(e):
        if e in memo: return memo[e]
        ds = down[e]
        if len(ds) > 1: ds = [choice[e]]
        v = 1 if not ds else L(ds[0]) + 1
        memo[e] = v; return v
    return {e: L(e) for e in down}

rows1 = []
for choice in ({'P': 'd'}, {'P': 'x'}):
    lv = layers(choice)
    for first in ('chH', 'chW'):
        conn = {'chH': 0 if first == 'chH' else 1, 'chW': 0 if first == 'chW' else 1}
        key = {'H': (lv['J'], conn['chH']), 'W': (lv['P'], conn['chW'])}
        top = min(key, key=lambda g: key[g])
        rows1.append(dict(P按=choice['P'], 先接通=first, L_H=lv['J'], L_W=lv['P'], 高一级=top))

# 编码二
sim2 = pathlib.Path(__file__).resolve().parents[3] / '规则修订' / '2026-09-30-迟滞' / 'sim2'
sys.path.insert(0, str(sim2))
import simulator as S
rows2 = []
for ch in ('d', 'x'):
    for first in ('chH', 'chW'):
        M, N = S.Machine('M'), S.Sink('N')
        J, P = S.Merger('J'), S.Splitter('P')
        a, d, x, y = S.Belt('a'), S.Belt('d'), S.Belt('x'), S.Gate('y')
        rH, rW = (0, 1) if first == 'chH' else (1, 0)
        M.connect(J, rH); M.connect(P, rW)
        J.connect(a, 10); a.connect(N, 11)
        P.connect(d, 12); d.connect(N, 13)
        P.connect(x, 14); x.connect(y, 15); y.connect(N, 16)
        nodes = [M, N, J, P, a, d, x, y]
        lv = S.layers_for(nodes, {'P': ch})
        class Wd: pass
        w = Wd(); w.layers = lv
        order = M.channels('output', w)
        top = 'H' if order[0].dst.name == 'J' else 'W'
        rows2.append(dict(P按=ch, 先接通=first, L_H=lv['J'], L_W=lv['P'], 高一级=top))

res = dict(encoding1=rows1, encoding2=rows2, agree=rows1 == rows2,
           W_above_H_cases=[r for r in rows1 if r['高一级'] == 'W'])
pathlib.Path('grade_order_toy.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps(res, ensure_ascii=False, indent=1))
