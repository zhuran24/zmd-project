#!/usr/bin/env python3
"""固定模块对角区出口的容量放宽检查，未放其余机身。"""
import json,os,hashlib
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
from collections import defaultdict
from pathlib import Path
import networkx as nx
BASE=Path(__file__).resolve().parents[1]
import sys
p=json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv)>1 else json.loads((BASE/'依据快照/粗坐标.json').read_text())
D=[(1,0),(0,1),(-1,0),(0,-1)]
occupied=set()
for u in p['machines']+p['warehouse_outlets']+p['power_stalls']:
    occupied.update((x,y) for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1))
for x in range(63,69):
    for y in range(14,20):occupied.add((x,y))
sp={u['id']:u for u in p['machines']}
axis=defaultdict(set)
for r in p['routes_fixed']:
    cs=[tuple(z) for z in r['cells']]
    for k,c in enumerate(cs):
        ds=[]
        if k:ds.append(D.index((cs[k-1][0]-c[0],cs[k-1][1]-c[1])))
        elif r['source'] in sp:ds.append(sp[r['source']]['Din'])
        elif r['source'] and r['source'].startswith('W'):ds.append(3 if c[1]==1 else 2)
        if k+1<len(cs):ds.append(D.index((cs[k+1][0]-c[0],cs[k+1][1]-c[1])))
        elif r['target'] in sp:ds.append((sp[r['target']]['Din']+2)%4)
        if len(ds)==2:
            axis[c].update([ds[0]%2] if (ds[0]+2)%4==ds[1] else [0,1])
# 每条方格边容量1；转弯和桥接器按宽松端口节点处理。
g=nx.DiGraph();INF=1000
for y in range(1,70):
    for x in range(1,70):
        c=x,y
        if c in occupied:continue
        for a in (0,1):
            if a in axis[c]:continue
            g.add_edge((c,a,'i'),(c,a,'o'),capacity=1)
            if not axis[c]:g.add_edge((c,a,'o'),(c,1-a,'i'),capacity=1)
            for d in [a,a+2]:
                n=x+D[d][0],y+D[d][1]
                if 1<=n[0]<70 and 1<=n[1]<70 and n not in occupied and a not in axis[n]:
                    g.add_edge((c,a,'o'),(n,a,'i'),capacity=1)
            if x<=18 and y<=18:g.add_edge('SOURCE',(c,a,'i'),capacity=INF)
            if (x>=19 and y>=19) or x>=37 or y>=37:g.add_edge((c,a,'o'),'SINK',capacity=INF)
v,(ss,tt)=nx.minimum_cut(g,'SOURCE','SINK')
cut=[dict(source=str(a),target=str(b),capacity=d['capacity']) for a,b,d in g.edges(data=True) if a in ss and b in tt]
r=dict(schema='fixed-planning-cut-relaxation-v1',input_sha256=hashlib.sha256((Path(sys.argv[1]) if len(sys.argv)>1 else BASE/'依据快照/粗坐标.json').read_bytes()).hexdigest(),maximum_exit_relaxation=v,required_powder_paths=12,cut=cut,
       scope='固定四模块、取货口、供电桩和已定运输轴；未放角区及其他180台机身。忽略未用端口自动通道等限制。容量不足才可否定固定规划。')
(Path(sys.argv[2]) if len(sys.argv)>2 else BASE/'证据/规划角区出口容量.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
print(json.dumps(r,ensure_ascii=False))
