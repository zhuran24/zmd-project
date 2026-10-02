#!/usr/bin/env python3
"""复核94A：若按同目录 临时规则.md 第4条（离线相当于按任意次序重建，接通时刻=两端中后建成者的建成时刻），
哪些接通先后到得了。只作旁注，不作本复核的前提。
例一：一串单位 A–T–B–C，通道 c1=(A,T)、c2=(T,B)、c3=(B,C)；问 c1<c3<c2 能否出现。
例二：取货分级小构型 M→J（chH）、M→P（chW）；问 chW 严格早于 chH 能否出现。"""
import itertools, json
res = {}
seen = set()
for order in itertools.permutations('ATBC'):
    b = {u: i for i, u in enumerate(order)}
    c1, c2, c3 = max(b['A'], b['T']), max(b['T'], b['B']), max(b['B'], b['C'])
    seen.add((c1 < c3 < c2))
res['chain_c1_lt_c3_lt_c2_reachable'] = True in seen
ok = []
for order in itertools.permutations('MJP'):
    b = {u: i for i, u in enumerate(order)}
    chH, chW = max(b['M'], b['J']), max(b['M'], b['P'])
    if chW < chH:
        ok.append(''.join(order))
res['toy_chW_before_chH_build_orders'] = ok
json.dump(res, open('temp_rule4_orders.json', 'w'), ensure_ascii=False)
print(res)
