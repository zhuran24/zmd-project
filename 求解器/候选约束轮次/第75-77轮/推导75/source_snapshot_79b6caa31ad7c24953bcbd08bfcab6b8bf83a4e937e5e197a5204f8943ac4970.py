#!/usr/bin/env python3
"""Residual common-group certificate after fixing retained unit bodies.
Subtract actual known-machine coverage from each pole capacity, then exclude
all fixed bodies and the 46 forced first-transport cells from missing blocks.
"""
from pathlib import Path
from collections import deque
import json,argparse,hashlib
import verify75
OUT=Path(__file__).resolve().parent
def rect(b):return verify75.footprint(b)
def overlap(r,s):return max(r[0],s[0])<min(r[0]+r[2],s[0]+s[2]) and max(r[1],s[1])<min(r[1]+r[3],s[1]+s[3])
def flow(groups,caps):
    # Independent integral residual network; verify75 uses expanded slots.
    coords=sorted(set().union(*groups));index={xy:i+len(caps)+1 for i,xy in enumerate(coords)};sink=len(caps)+len(coords)+1;adj=[[] for _ in range(sink+1)]
    def add(a,b,c):adj[a].append([b,c,len(adj[b])]);adj[b].append([a,0,len(adj[a])-1])
    for p,cap in enumerate(caps):
        add(0,p+1,cap)
        for xy in sorted(groups[p]):add(p+1,index[xy],1)
    for n in index.values():add(n,sink,1)
    total=0
    while True:
        prev={0:None};queue=deque([0])
        while queue and sink not in prev:
            u=queue.popleft()
            for e,(v,c,_) in enumerate(adj[u]):
                if c>0 and v not in prev:prev[v]=(u,e);queue.append(v)
        if sink not in prev:break
        v=sink
        while v:
            u,e=prev[v];rev=adj[u][e][2];adj[u][e][1]-=1;adj[v][rev][1]+=1;v=u
        total+=1
    inv={n:xy for xy,n in index.items()};cert=[]
    for p in range(len(caps)):
        for v,c,_ in adj[p+1]:
            if v in inv and c==0:cert.append([p,list(inv[v])])
    assert len(cert)==total and len({tuple(xy) for _,xy in cert})==total
    assert all(tuple(xy) in groups[p] for p,xy in cert)
    assert all(sum(q==p for q,_ in cert)<=c for p,c in enumerate(caps))
    return total,cert
def certify(data,forced=True):
    original=verify75.check(data)
    units=data['chosen'];poles=[b for b in units if b['kind']=='p'];machines=[b for b in units if b['kind'] in ('s','m','l')]
    forbidden=set().union(*(rect(b) for b in units));forbidden_rects=[tuple(b[k] for k in ('x','y','w','h')) for b in units]
    if forced:
        forbidden.update(map(tuple,original['warehouse_first_cells']));forbidden_rects.extend((x,y,1,1) for x,y in original['warehouse_first_cells'])
    hole=verify75.rect(49,17,21,53);centers=[];residual=[];known=[]
    for b,cap in zip(poles,original['capacities']):
        power=verify75.rect(b['x']-5,b['y']-5,12,12);n=sum(bool(power&rect(m)) for m in machines);known.append(n);residual.append(cap-n);assert residual[-1]>=0
        A=set();B=set();pr=(b['x']-5,b['y']-5,12,12)
        for x in range(2,69):
            for y in range(2,69):
                square=verify75.rect(x-1,y-1,3,3)
                if not square&hole and not square&forbidden and square&power:A.add((x,y))
                r=(x-1,y-1,3,3)
                if not overlap(r,(49,17,21,53)) and overlap(r,pr) and not any(overlap(r,obstacle) for obstacle in forbidden_rects):B.add((x,y))
        assert A==B;centers.append(A)
    parts=[]
    for a in range(3):
        for b in range(3):
            gs=[{((x+a)//3,(y+b)//3) for x,y in cs} for cs in centers];best=(10000,0,0,0);cuts=[]
            for mask in range(1<<len(poles)):
                ins=set();outside=0
                for p in range(len(poles)):
                    if mask>>p&1:ins.update(gs[p])
                    else:outside+=residual[p]
                bound=outside+len(ins);cuts.append(bound)
                if bound<best[0]:best=(bound,mask,outside,len(ins))
            value,cert=flow(gs,residual);other=verify75.matching(gs,residual);assert value==best[0]==len(other)
            parts.append(dict(shift=[a,b],upper=best[0],mask=best[1],outside_capacity=best[2],inside_union=best[3],all_union=len(set().union(*gs)),matching=cert,expanded_slot_matching=other,all_subset_bounds=cuts))
    return dict(status='PASS',S=data['S'],known_manufacturing=len(machines),remaining_required=217-len(machines),known_coverage_per_pole=known,
                capacities=original['capacities'],residual_capacities=residual,loss=original['loss'],known_repeats=original['repeats'],forced_first_cells=forced,
                pole_positions=original['pole_positions'],center_counts=list(map(len,centers)),centers=[sorted(c) for c in centers],partitions=parts,
                residual_upper=min(r['upper'] for r in parts),total_manufacturing_upper=len(machines)+min(r['upper'] for r in parts))
def main():
    p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--name',required=True);p.add_argument('--no-forced',action='store_true');a=p.parse_args()
    r=certify(json.loads(Path(a.file).read_text()),not a.no_forced);r['source_sha256']=hashlib.sha256(Path(a.file).read_bytes()).hexdigest();r['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (OUT/(a.name+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print({k:r[k] for k in ('status','known_manufacturing','remaining_required','residual_capacities','residual_upper','total_manufacturing_upper')});print([g['upper'] for g in r['partitions']])
if __name__=='__main__':main()
