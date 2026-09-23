#!/usr/bin/env python3
"""Cross-encoding domain comparison and fixed physical witness replay."""
import json,time,hashlib,warnings,copy
from pathlib import Path
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from ortools.sat.python import cp_model
import cp72,mip72,check_witness,grid_certificate
OUT=Path(__file__).resolve().parent
def read(n):return json.loads((OUT/n).read_text())
def key(b):return tuple(b[k] for k in ('kind','x','y','w','h','axis'))
def canonical(bs):
    return sorted((key(b),tuple(tuple(sorted(map(tuple,e))) for e in b['ports']),tuple(b['needs']),b['j'],b['loss']) for b in bs)
start=time.monotonic();A=cp72.domain();B=mip72.get_domain();assert canonical(A)==canonical(B)
w=read('projected_cp.json');checked=check_witness.check(w);assert checked['P']==10 and checked['S']==185
# Store a clean witness independent of exploratory metadata.
clean={k:w[k] for k in ('S','warehouse_gaps','chosen')};clean['scope']='boundary geometry and power relaxation only';(OUT/'witness185.json').write_text(json.dumps(clean,ensure_ascii=False,indent=2)+'\n')
keys={key(b) for b in w['chosen']}
m,bs,v,score,gaps=cp72.build(cap=185)
for b,x in zip(bs,v):m.add(x==int(key(b) in keys))
for g,k in zip(gaps,w['warehouse_gaps']):m.add(g==k//3)
s=cp_model.CpSolver();s.parameters.num_search_workers=1;s.parameters.max_time_in_seconds=30;st=s.solve(m)
assert st==cp_model.OPTIMAL and s.value(score)==185
src,bs,obj,constant,gaps=mip72.build(cap=185)
for i,b in enumerate(bs):src.lb[i]=src.ub[i]=int(key(b) in keys)
for gs,k in zip(gaps,w['warehouse_gaps']):src.lb[gs[k//3]]=1
with warnings.catch_warnings():
    warnings.simplefilter('ignore');r=milp(obj,integrality=src.integrality,bounds=Bounds(src.lb,src.ub),constraints=LinearConstraint(src.matrix(),src.lo,src.hi),options={'time_limit':30,'threads':1})
assert r.status==0 and round(r.fun+constant)==185
cert=grid_certificate.certify(checked);assert cert['global_upper']==184
bad=copy.deepcopy(clean);bad['chosen'].append(copy.deepcopy(bad['chosen'][-1]))
try:check_witness.check(bad)
except AssertionError:mutation=True
else:raise AssertionError('duplicate pole not rejected')
bad=copy.deepcopy(clean);bad['S']=184
try:check_witness.check(bad)
except AssertionError:mutation2=True
else:raise AssertionError('wrong objective not rejected')
# Compare global-center group generation by a full cell implementation against
# independent half-open rectangle arithmetic for every admitted physical pole.
groups_count=0
for b in A:
    if b['kind']!='p':continue
    px,py=b['x'],b['y'];physical=set()
    for x in range(max(2,px-6),min(68,px+7)+1):
        for y in range(max(2,py-6),min(68,py+7)+1):
            cells=cp72.cells(x-1,y-1,3,3)
            if not (cells&cp72.HOLE or cells&cp72.cells(px,py,2,2)):physical.add((x,y))
    assert physical==grid_certificate.centers(px,py)
    groups_count+=1
manifest=read('input_manifest.json');root=OUT.parents[3]
for p,d in manifest.items():assert hashlib.sha256((root/p).read_bytes()).hexdigest()==d['sha256'],p
out=dict(status='PASS',domain_units=len(A),canonical_domains_equal=True,physical_poles=groups_count,corner_multiplicity_checked=[{'cell':[48,69],'weight':mip72.measured((48,69))},{'cell':[69,16],'weight':mip72.measured((69,16))}],fixed_witness_cp='OPTIMAL',fixed_witness_highs='OPTIMAL',S=185,grid_upper=184,mutations_rejected=['duplicate pole','wrong objective'],inputs_unchanged=True,seconds=time.monotonic()-start)
assert all(d['weight']==2 for d in out['corner_multiplicity_checked'])
(OUT/'audit72.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(out)
