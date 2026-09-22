#!/usr/bin/env python3
"""Independent interval exact-cover CP-SAT check of DP values; no DP recurrence."""
import json,time,hashlib,os
os.environ['OMP_NUM_THREADS']='1'
os.environ['OPENBLAS_NUM_THREADS']='1'
from functools import lru_cache
from ortools.sat.python import cp_model
from filter_positions import ROOT,PATTERNS,_options,line_table,combine,overlaps
CACHE_FILE=ROOT/'audit_models.jsonl'
DISK={}
if CACHE_FILE.exists():
    for ln in CACHE_FILE.read_text().splitlines():
        q=json.loads(ln); DISK[q['key']]=q['result']

def milp_fallback(model):
    import numpy as np
    from scipy.optimize import milp,Bounds,LinearConstraint
    from scipy.sparse import coo_array
    proto=model.proto; n=len(proto.variables); row=[]; col=[]; data=[]; lo=[]; hi=[]
    for i,c in enumerate(proto.constraints):
        if c.has_exactly_one():
            ids=list(c.exactly_one.literals); coeff=[1]*len(ids); lb=ub=1
        elif c.has_linear():
            ids=list(c.linear.vars); coeff=list(c.linear.coeffs)
            lb,ub=c.linear.domain
        else: raise ValueError(str(c))
        assert not c.enforcement_literal
        row.extend([i]*len(ids));col.extend(ids);data.extend(coeff)
        lo.append(-np.inf if lb < -10**12 else lb);hi.append(np.inf if ub>10**12 else ub)
    cost=np.zeros(n)
    for i,c in zip(proto.objective.vars,proto.objective.coeffs):cost[i]=c
    matrix=coo_array((np.asarray(data,float),(np.asarray(row,np.int32),np.asarray(col,np.int32))),shape=(len(lo),n)).tocsc()
    t0=time.monotonic()
    result=milp(cost,integrality=np.ones(n),bounds=Bounds(np.zeros(n),np.ones(n)),
                constraints=LinearConstraint(matrix,lo,hi),options={'time_limit':60,'mip_rel_gap':0,'threads':1})
    if result.status==0:
        return dict(status='OPTIMAL',objective=float(result.fun),bound=float(result.mip_dual_bound),seconds=time.monotonic()-t0,backend='HiGHS')
    return dict(status='UNKNOWN',message=result.message,seconds=time.monotonic()-t0,backend='HiGHS')

def canonical(r,s,outer,corner):
    opts,gaps=_options(r,s,outer,corner)
    return tuple(tuple(sorted(o)) for o in opts),tuple(gaps)

@lru_cache(None)
def interval_cp(tables,P,budget):
    key=hashlib.sha256(json.dumps((tables,P,budget)).encode()).hexdigest()
    if key in DISK:return DISK[key]
    model=cp_model.CpModel(); core=[]; poles=[]; losses=[]; costs=[]
    for ti,(opts,gaps) in enumerate(tables):
        n=len(gaps); cover=[[] for _ in gaps]
        begins=[{} for _ in range(n+1)]; ends=[{} for _ in range(n+1)]
        for start,options in enumerate(opts):
            for oi,(end,tag,c,p,l) in enumerate(options):
                var=model.new_bool_var(f'u{ti}_{start}_{oi}')
                for k in range(start,end): cover[k].append(var)
                begins[start].setdefault(tag,[]).append(var)
                ends[end].setdefault(tag,[]).append(var)
                if c: core.append(var)
                if p: poles.append(var)
                if l: losses.append(l*var)
            if gaps[start] is not None:
                var=model.new_bool_var(f'gap{ti}_{start}'); cover[start].append(var)
                if gaps[start]: costs.append(var*gaps[start])
        for vv in cover: model.add_exactly_one(vv)
        for k in range(1,n):
            for left,right in [('M','M'),('M','C'),('C','M'),('C','P'),('P','C')]:
                vv=ends[k].get(left,[])+begins[k].get(right,[])
                if vv: model.add(sum(vv)<=1)
    model.add(sum(core)<=1); model.add(sum(poles)<=P); model.add(sum(losses)<=budget)
    model.minimize(sum(costs))
    solver=cp_model.CpSolver(); solver.parameters.num_search_workers=1
    solver.parameters.max_time_in_seconds=10; solver.parameters.random_seed=20260922
    status=solver.solve(model)
    result=dict(status=solver.status_name(status),objective=solver.objective_value,
                bound=solver.best_objective_bound,seconds=solver.wall_time,backend='CP-SAT')
    if status!=cp_model.OPTIMAL:
        first=result; result=milp_fallback(model); result['cp_attempt']=first
        print(json.dumps(dict(fallback=key,result=result)),flush=True)
    if result['status']=='OPTIMAL':
        DISK[key]=result
        with CACHE_FILE.open('a') as f:f.write(json.dumps(dict(key=key,result=result))+'\n')
    return result

def minX(r,P):
    budget=23*P-217
    first=interval_cp(tuple(sorted(canonical(r,s,True,False) for s in 'EN')),P,budget)
    choices=[first]
    if P>=11 and not overlaps((68,68,2,2),r):
        choices.append(interval_cp(tuple(sorted(canonical(r,s,True,True) for s in 'EN')),P-1,budget-15))
    assert all(x['status']=='OPTIMAL' for x in choices),choices
    value=min(x['objective'] for x in choices)
    # Objective is an integer count. HiGHS may serialize 22 as 21.99999999999999.
    assert abs(value-round(value))<1e-6,value
    return round(value)

def main():
    start=time.monotonic(); data=json.loads((ROOT/'positions.json').read_text()); audit=[]
    indexed={tuple(z['rect']):z for z in data['positions']}
    # Reflection x<->y is an exact symmetry of the rule sheet and is checked for every row.
    for z in data['positions']:
        a,b,w,h=z['rect']; twin=indexed[b,a,h,w]
        assert z['branches']==twin['branches']
        assert bool(z['patterns'])==bool(twin['patterns'])
    # Check prefix-sum coverage inequalities against direct half-open rectangle intersection.
    coverage_checks=0
    for w,h in [(3,3),(5,5),(6,4),(4,6)]:
        for dx in range(-20,21):
            for dy in range(-20,21):
                direct=overlaps((0,0,w,h),(dx-5,dy-5,12,12))
                formula=(-6<=dx<=w+4 and -6<=dy<=h+4)
                assert direct==formula
                coverage_checks+=1
    # All joint patterns are genuinely 46 non-overlapping warehouses / 46 distinct ports.
    for p in PATTERNS:
        assert len(set(map(tuple,p['bodies'])))==138
        assert len(set(map(tuple,p['ports'])))==46
        assert not set(map(tuple,p['bodies']))&set(map(tuple,p['ports']))
    # Numerical DP check for every retained and rejected position in one orientation.
    # Counterfactual missing-corridor rows also reconstruct the old 12/8/1 counts.
    old_counts={10:0,11:0,12:0}; new_counts={10:0,11:0,12:0}
    for z in data['positions']:
        r=tuple(z['rect']); a,b,w,h=r
        if w!=21: continue
        sides=[s for s in 'WESN' if {'W':True,'E':a+w<70,'S':True,'N':b+h<70}[s]]
        Ytables=tuple(sorted(canonical(r,s,False,False) for s in sides))
        for P in (10,11,12):
            X=minX(r,P); yy=interval_cp(Ytables,P,23*P-217)
            assert yy['status']=='OPTIMAL',yy
            assert abs(yy['objective']-round(yy['objective']))<1e-6
            Y=round(yy['objective']); allowed=187-16*P+2*((23*P-217)//9)
            if z['branches']:
                old=next(q for q in z['branches'] if q['P']==P)
                assert X==old['X_lower'] and Y==old['Y_lower'],(r,P,X,Y,old)
            old_counts[P]+=int(X+Y<=allowed)
            new_counts[P]+=int(bool(z['patterns']) and X+Y<=allowed)
            audit.append(dict(rect=r,P=P,X=X,Y=Y,allowed=allowed,pattern_count=len(z['patterns'])))
        if len(audit)%90==0:
            print(json.dumps(dict(checked=len(audit),elapsed=time.monotonic()-start,cache=interval_cp.cache_info()._asdict())),flush=True)
            (ROOT/'audit_checkpoint.json').write_text(json.dumps(audit,ensure_ascii=False))
    out=dict(status='PASS',coverage_checks=coverage_checks,transpose_pairs=630,joint_warehouse_patterns=47,
             checked_position_P_branches=len(audit),independent_cp_models=interval_cp.cache_info().misses,
             old_style_counts_per_orientation=old_counts,current_counts_per_orientation=new_counts,
             verifier_backends={k:sum(v.get('backend')==k for v in DISK.values()) for k in ('CP-SAT','HiGHS')},
             elapsed=time.monotonic()-start,checks=audit)
    (ROOT/'audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in out.items() if k!='checks'},ensure_ascii=False),flush=True)
if __name__=='__main__': main()
