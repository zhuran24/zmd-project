#!/usr/bin/env python3
"""两套编码外部量不一致的网络逐个诊断：是否都含「从一台单位出发、只经运输单位又回到这台单位」的进路。
sim2 已知错 2：按元件而不是按单位判「不移回刚离开的单位」，会把这种进路上回到起点单位的物品挡住；规则第 24 行只禁止移回刚离开的那个单位（运输单位）。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from netgen import gen

def self_return(desc):
    U = desc['units']; out = {}
    for a, b, r in desc['channels']:
        out.setdefault(a, []).append(b)
    nt = [u for u, d in U.items() if d['type'] in ('src', 'mach', 'sink')]
    res = []
    for v in nt:
        # 只经运输单位能否回到 v
        stack = [x for x in out.get(v, []) if U[x]['type'] not in ('src', 'mach', 'sink')]
        seen = set()
        while stack:
            x = stack.pop()
            if x in seen: continue
            seen.add(x)
            for y in out.get(x, []):
                if y == v: res.append(v)
                elif U[y]['type'] not in ('src', 'mach', 'sink'): stack.append(y)
    return sorted(set(res))

seeds = [int(s) for s in sys.argv[1:]]
rep = {}
for s in seeds:
    rep[s] = self_return(gen(s, allow_gate_filters=(s % 2 == 0)))
# 对照：B 组（奇数种子）里含自返进路的网络有多少
cnt = sum(1 for s in range(1000, 2000) if s % 2 == 1 and self_return(gen(s, allow_gate_filters=False)))
print(json.dumps(dict(mismatch_nets=rep, odd_nets_with_self_return=cnt, odd_nets=500), ensure_ascii=False))
