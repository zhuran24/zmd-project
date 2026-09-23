#!/usr/bin/env python3
"""Compare three geometric enumerators and both independent center encodings."""
import os
os.sched_setaffinity(0,set(range(12)))
from pathlib import Path
from collections import Counter
import json,hashlib
import cp72,mip72,geometry74
OUT=Path(__file__).resolve().parent;cp72.ROUNDS=mip72.ROUNDS=OUT.parents[1]
def key(b):return tuple(b[k] for k in ('kind','x','y','w','h','axis'))
def normalized(bs):
    return {key(b):(tuple(tuple(sorted(map(tuple,s))) for s in b['ports']),tuple(b['needs']),b['j'],b['loss']) for b in bs}
A=cp72.domain();B=mip72.get_domain();assert normalized(A)==normalized(B)
third=[]
for b in geometry74.boundary_domain():
    x,y,w,h=b['r'];third.append(dict(kind=b['kind'],x=x,y=y,w=w,h=h,axis=('h','v')[b['axis']],ports=b['ports'],needs=b['needs'],j=0,loss=0))
assert normalized([b for b in A if b['kind']!='p'])==normalized(third)
caps=json.loads((OUT/'capacities.json').read_text());loss={tuple(r['p']):r['loss'] for r in caps}
assert all(b['loss']==loss[b['x'],b['y']] for b in A if b['kind']=='p')
def relevant(p,machines):
    if p['j'] or cp72.cells(p['x'],p['y'],2,2)&cp72.TARGET:return True
    return any(p['x']-5<b['x']+b['w'] and b['x']<p['x']+7 and p['y']-5<b['y']+b['h'] and b['y']<p['y']+7 for b in machines)
machines=[b for b in A if b['kind'] in ('s','m','l')];keep=[b for b in A if b['kind']!='p' or relevant(b,machines)]
assert len(keep)==1945
center_records=0;group_records=0
for p in [b for b in A if b['kind']=='p']:
    x,y=p['x'],p['y'];own=cp72.cells(x,y,2,2);cs=set()
    for cx in range(max(2,x-6),min(68,x+7)+1):
        for cy in range(max(2,y-6),min(68,y+7)+1):
            small=cp72.cells(cx-1,cy-1,3,3)
            if not small&cp72.HOLE and not small&own:cs.add((cx,cy))
    other=geometry74.centers((x,y));assert cs==other
    center_records+=len(cs)
    for a in range(3):
        for b in range(3):group_records+=len({((cx+a)//3,(cy+b)//3) for cx,cy in cs})
r=dict(status='PASS',domains=3,all_options=len(A),counts=dict(Counter(b['kind'] for b in A)),projected_options=len(keep),deleted_poles=len(A)-len(keep),pole_center_pairs=center_records,pole_partition_group_pairs=group_records,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(OUT/'domain_audit.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(r)
