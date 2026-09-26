"""No pole may touch X/Y once the sole boundary pole is on the inner band.
Exact interval recursion; independent global interval MILP cross-check.
"""
from geometry77 import *
from itertools import product
from functools import lru_cache
import os,time
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'

def main():
    units=read(OUT/'domain.json'); machines=[u for u in units if u['kind']!='p']
    shared=[u for u in machines if sum(bool(cells(u['r'])&set(line)) for line in LINES)>1]
    assert not shared
    pole_candidates=[]
    for d in read(OUT/'capacities.json'):
        if d['cap']>=20 and not edge_count(d['p']) and cells((*d['p'],2,2))&WEIGHTS.keys():pole_candidates.append(d)
    assert not pole_candidates
    options=[];tables=[];witness=[]
    for k,line in enumerate(LINES):
        opts=set()
        for u in machines:
            indexes=[i for i,c in enumerate(line) if c in cells(u['r'])]
            if not indexes:continue
            left,right=min(indexes),max(indexes)+1
            span=u['r'][3] if k in (0,2) else u['r'][2]
            kind='C' if u['kind']=='c' else 'M';whole=right-left==span
            opts.add((left,right,kind if whole else 'Z',int(kind=='C')))
        opts=sorted(opts);options.append(opts)
        at={i:[o for o in opts if o[0]==i] for i in range(len(line))}
        @lru_cache(None)
        def rec(pos,last,ncore):
            if pos==len(line):return (0,[]) if ncore==0 else (10**6,[])
            cost,trail=rec(pos+1,'G',ncore);best=(1+cost,[('gap',pos)]+trail)
            for left,right,kind,c in at[pos]:
                if c>ncore or (last in ('M','C') and kind in ('M','C')):continue
                cost,trail=rec(right,kind,ncore-c)
                if cost<best[0]:best=(cost,[(left,right,kind,c)]+trail)
            return best
        tables.append([rec(0,'G',c)[0] for c in (0,1)])
        witness.append([rec(0,'G',c)[1] for c in (0,1)])
    branches=[]
    for selected in product((0,1),repeat=4):
        if sum(selected)>1:continue
        branches.append(dict(core_per_line=selected,min_gaps=sum(tables[i][c] for i,c in enumerate(selected))))
    # Independent formulation: one variable per interval; only interval
    # non-overlap and prohibited immediately adjacent complete bodies.
    import numpy as np
    from scipy.optimize import milp,Bounds,LinearConstraint
    from scipy.sparse import coo_matrix
    variables=[(k,o) for k,opts in enumerate(options) for o in opts]
    rows=[]
    for k,line in enumerate(LINES):
        for pos in range(len(line)):
            rows.append(([i for i,(a,o) in enumerate(variables) if a==k and o[0]<=pos<o[1]],1))
    rows.append(([i for i,(_,o) in enumerate(variables) if o[3]],1))
    for i,(k,o) in enumerate(variables):
        if o[2] not in ('M','C'):continue
        for j,(a,z) in enumerate(variables):
            if a==k and z[2] in ('M','C') and o[1]==z[0]:rows.append(([i,j],1))
    ri=[];ci=[]
    for k,(indices,b) in enumerate(rows):
        for i in indices:ri.append(k);ci.append(i)
    mat=coo_matrix((np.ones(len(ri)),(ri,ci)),shape=(len(rows),len(variables))).tocsc()
    r=milp(np.array([-(o[1]-o[0]) for _,o in variables]),integrality=np.ones(len(variables)),
      bounds=Bounds(np.zeros(len(variables)),np.ones(len(variables))),constraints=LinearConstraint(mat,-np.inf,np.ones(len(rows))),
      options={'threads':1,'mip_rel_gap':0.0,'time_limit':60})
    assert r.status==0
    n=138+round(r.fun);assert n==min(b['min_gaps'] for b in branches)
    result=dict(lines=[dict(length=len(line),min_gaps_without_core=tables[i][0],min_gaps_with_core=tables[i][1],
      options=options[i],plans=witness[i]) for i,line in enumerate(LINES)],
      core_branches=branches,minimum_gap_sum=n,independent_milp_status='OPTIMAL',independent_milp_minimum=n,
      shared_machine_or_core_options=0,nonedge_poles_of_cap20_touching_counted_edges=0)
    save('no_pole_edges.json',result)
    print({k:v for k,v in result.items() if k!='lines'},flush=True)
if __name__=='__main__':main()
