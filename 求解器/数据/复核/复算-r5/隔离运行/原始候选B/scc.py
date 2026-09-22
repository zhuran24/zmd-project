#!/usr/bin/env python3
# 在 design.py 导出的 channels.csv 上算实例级有向图的强连通分量。
# 覆盖范围：只看「哪台机器向哪台机器送料」的有向图，不含几何、不含时序。
# 用途：活性（死锁）分析的范围界定——DAG 部分不成环，成环的只有 SCC 部分。
import csv, sys
from collections import defaultdict
rows = list(csv.DictReader(open("channels.csv", encoding="utf-8")))
g = defaultdict(set); nodes = set()
for r in rows:
    s, d = r["源机器id"], r["目标机器id"]
    nodes.add(s); nodes.add(d); g[s].add(d)
# Tarjan
idx = {}; low = {}; on = {}; st = []; out = []; c = [0]
def strong(v):
    work = [(v, iter(g[v]))]
    idx[v] = low[v] = c[0]; c[0] += 1; st.append(v); on[v] = True
    while work:
        u, it = work[-1]
        adv = False
        for w in it:
            if w not in idx:
                idx[w] = low[w] = c[0]; c[0] += 1; st.append(w); on[w] = True
                work.append((w, iter(g[w]))); adv = True; break
            elif on.get(w):
                low[u] = min(low[u], idx[w])
        if adv: continue
        work.pop()
        if work:
            low[work[-1][0]] = min(low[work[-1][0]], low[u])
        if low[u] == idx[u]:
            comp = []
            while True:
                w = st.pop(); on[w] = False; comp.append(w)
                if w == u: break
            out.append(comp)
for v in sorted(nodes):
    if v not in idx: strong(v)
big = [c for c in out if len(c) > 1]
mach = {r["机器id"]: r["配方"] for r in csv.DictReader(open("machines.csv", encoding="utf-8"))}
print(f"节点 {len(nodes)}，SCC {len(out)} 个，其中规模 >1 的 {len(big)} 个")
for comp in sorted(big, key=len, reverse=True):
    from collections import Counter
    print(f"  规模 {len(comp)}：", dict(Counter(mach.get(m, m.split('M')[0] or m) for m in comp)))
print(f"规模 1 的 SCC（即不在任何环上的节点）{len(out)-len(big)} 个")
