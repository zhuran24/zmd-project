#!/usr/bin/env python3
"""Exact global power-group max flow, with independently enumerated min cuts.
The certificate contains an integral matching and all 2^P subset cut values.
"""
from pathlib import Path
from collections import deque
import json,sys
OUT=Path(__file__).resolve().parent
def centers(px,py):
    out=set()
    for x in range(2,69):
        for y in range(2,69):
            # A 3x3 block centered at (x,y); half-open rectangle intersection.
            if x+2>49 and y+2>17:continue
            if not(x-1<px+7 and px-5<x+2 and y-1<py+7 and py-5<y+2):continue
            if x-1<px+2 and px<x+2 and y-1<py+2 and py<y+2:continue
            out.add((x,y))
    return out
def flow(groups,caps):
    coords=sorted(set.union(*groups));gi={p:i+1+len(groups) for i,p in enumerate(coords)};sink=1+len(groups)+len(coords);edges=[[] for _ in range(sink+1)]
    def edge(a,b,c):edges[a].append([b,c,len(edges[b])]);edges[b].append([a,0,len(edges[a])-1])
    for i,(g,c) in enumerate(zip(groups,caps)):
        edge(0,i+1,c)
        for xy in sorted(g):edge(i+1,gi[xy],1)
    for n in gi.values():edge(n,sink,1)
    value=0
    while True:
        prev={0:None};q=deque([0])
        while q and sink not in prev:
            n=q.popleft()
            for j,(to,cap,rev) in enumerate(edges[n]):
                if cap>0 and to not in prev:prev[to]=(n,j);q.append(to)
        if sink not in prev:break
        n=sink
        while n:
            a,j=prev[n];to,cap,rev=edges[a][j];edges[a][j][1]-=1;edges[n][rev][1]+=1;n=a
        value+=1
    inverse={n:xy for xy,n in gi.items()};matching=[]
    for i in range(len(groups)):
        for to,cap,rev in edges[i+1]:
            if to in inverse and cap==0:matching.append([i,list(inverse[to])])
    assert len(matching)==value and len({tuple(g) for _,g in matching})==value
    for i,g in matching:assert tuple(g) in groups[i]
    for i,c in enumerate(caps):assert sum(j==i for j,g in matching)<=c
    return value,matching
def certify(check):
    poles=check['power'];sets=[centers(*p['position']) for p in poles];caps=[p['cap'] for p in poles];results=[]
    for a in range(3):
        for b in range(3):
            groups=[{((x+a)//3,(y+b)//3) for x,y in c} for c in sets]
            cuts=[];best=None
            for mask in range(1<<len(poles)):
                union=set();outside=0
                for i in range(len(poles)):
                    if mask>>i&1:union.update(groups[i])
                    else:outside+=caps[i]
                cost=outside+len(union);cuts.append(cost)
                if best is None or cost<best['upper']:best={'upper':cost,'mask':mask,'poles_in_cut':[i for i in range(len(poles)) if mask>>i&1],'outside_capacity':outside,'union_groups':len(union)}
            maxflow,matching=flow(groups,caps)
            assert maxflow==best['upper']
            results.append(dict(shift=[a,b],union_groups=len(set.union(*groups)),**{'min_cut':best},flow=maxflow,matching=matching,all_subset_cut_values=cuts))
    return dict(status='PASS',S=check['S'],pole_positions=[p['position'] for p in poles],capacities=caps,individual_capacity_sum=sum(caps),partitions=results,global_upper=min(r['flow'] for r in results),required=217)
if __name__=='__main__':
    path=Path(sys.argv[1]);r=certify(json.loads(path.read_text()));(OUT/(path.stem+'_grid.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print({'status':r['status'],'S':r['S'],'individual_capacity_sum':r['individual_capacity_sum'],'union_groups':[d['union_groups'] for d in r['partitions']],'maxflows':[d['flow'] for d in r['partitions']],'global_upper':r['global_upper']})
