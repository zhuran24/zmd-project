#!/usr/bin/env python3
"""关键数字两套编码互核：Φ 的上限与 150/176 界（分数与 2Φ 整数），清单21的 400 步与 50−3k_v，
E28 的 8n/(8n+1)（公式与分流器先判时的逐步模拟），E28 的层数公式（递推与公式）。"""
import json, random
from fractions import Fraction as F
from engine import Belt, Cell, Gate, Splitter, Sink, Source, World, link
out = {}
# Φ：分数编码
phimax = 50 + 50 + 50 + 1 + 1 + F(50, 2)
b150 = 49 + 50 + 49 + 1 + 1
b176 = 50 + 50 + 50 + 1 + 1 + F(49, 2) - F(1, 2)
# 2Φ 整数编码
phimax2 = 2 * (50 * 3 + 2) + 50
b150_2 = 2 * (49 + 50 + 49 + 2)
b176_2 = 2 * (50 * 3 + 2) + 49 - 1
out['Phi'] = dict(max=str(phimax), max2=phimax2, b150=b150, b150_2=b150_2, b176=str(b176), b176_2=b176_2,
                  agree=(phimax * 2 == phimax2 and b150 * 2 == b150_2 and b176 * 2 == b176_2))
# 清单21
out['C21'] = dict(steps=50 * 8, lower={kv: 50 - 3 * kv for kv in (1, 2, 3)})
# E28：公式与模拟
def e28_sim(n, m_extra=2, steps=6000):
    src = Source('src', 'x'); feed = Belt('feed', 1)
    S = Splitter('S')
    d1 = Gate('d1'); d2 = Belt('d2', 1)          # 断头支 k=2
    f1 = Belt('f1', n); f2 = Gate('f2'); f3 = Belt('f3', 1); sk = Sink('sk')   # 活支 m=3
    link(src, feed); link(feed, S); link(S, d1); link(d1, d2); link(S, f1); link(f1, f2); link(f2, f3); link(f3, sk)
    nodes = [src, feed, S, d1, d2, f1, f2, f3, sk]
    # 按断支数层：d2=1,d1=1,S=2；活支 f3=1,f2=2,f1=3；feed=S+1
    layers = dict(d2=1, d1=1, S=2, f3=1, f2=2, f1=3, feed=3)
    w = World(nodes, random.Random(0), layers=layers)
    order = sorted(w.build_units())
    w.offline_build(order=order)
    for _ in range(steps):
        w.step()
    got0 = sk.got
    for _ in range(8 * 9 * 17 * 25 * 2):
        w.step()
    return F(sk.got - got0, 8 * 9 * 17 * 25 * 2) * 8
out['E28'] = {n: dict(formula=str(F(8 * n, 8 * n + 1)), sim_live_per_tick=str(e28_sim(n)),
                      le=(e28_sim(n) <= F(8 * n, 8 * n + 1))) for n in (1, 2, 3, 4)}
# E28 层数：断头支 k 个元件首元件 k−1、按断支数的分流器 k；活支 m 个元件首带 m
def chain_layers(k, has_out):
    lay = [None] * k
    for i in range(k - 1, -1, -1):
        if i == k - 1:
            lay[i] = 1
        else:
            nxt_sends = (i + 1 < k - 1) or has_out
            lay[i] = lay[i + 1] + 1 if nxt_sends else 1
    return lay
ok = True
for k in range(2, 9):
    for m in range(2, 9):
        dead = chain_layers(k, False); live = chain_layers(m, True)
        ok &= (dead[0] == k - 1 and dead[0] + 1 == k and live[0] == m)
out['E28_layers_k_m_2_8_ok'] = ok
print(json.dumps(out, ensure_ascii=False, indent=1))
