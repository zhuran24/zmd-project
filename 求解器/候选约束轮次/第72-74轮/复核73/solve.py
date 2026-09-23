#!/usr/bin/env python3
"""Independent coordinate MILP; no submitted script or edge table imported.
The same independently generated integer rows can run in HiGHS or CP-SAT.
"""
from recompute import *

def build(j=None,cap=184,project=True,fixed=False,P=10):
    bs=units(project)
    lower=[];upper=[];names=[];rows=[];lbs=[];ubs=[]
    def var(name,lo=0,hi=1):
        i=len(names);names.append(name);lower.append(lo);upper.append(hi);return i
    def add(row,lo=-math.inf,hi=math.inf):
        rows.append({i:c for i,c in row.items() if c});lbs.append(lo);ubs.append(hi)
    vs=[var('unit_'+str(i)) for i in range(len(bs))]
    incidence=defaultdict(list)
    for i,b in enumerate(bs):
        for c in cells(b['rect']):incidence[c].append(i)
    occ={c:var('occupancy_'+str(c)) for c in sorted(incidence)}
    for c,v in occ.items():add({v:-1,**{i:1 for i in incidence[c]}},0,0)
    for i,b in enumerate(bs):
        for side,n in zip(b['ports'],b['needs']):
            row=Counter({i:n})
            row.update(occ[c] for c in side if c in occ)
            add(row,hi=len(side))
    patterns=warehouses();pv=[var('warehouse_'+str(g)) for g,ps in patterns]
    add({v:1 for v in pv},1,1)
    for c,v in occ.items():
        covering=[pv[k] for k,(g,ps) in enumerate(patterns) if c in ps]
        if covering:add({v:1,**{k:1 for k in covering}},hi=1)
    exceptions=[]
    for i,b in enumerate(bs):
        if b['kind']!='l':continue
        dirs=[var('input_'+str((i,t))) for t in (0,1)]
        weak=var('two_input_'+str(i));exceptions.append(weak)
        add({dirs[0]:1,dirs[1]:1,i:-1},0,0)
        add({weak:1,i:-1},hi=0)
        for t,side in enumerate(b['ports']):
            row=Counter({dirs[t]:3,weak:-1})
            row.update(occ[c] for c in side if c in occ)
            add(row,hi=len(side))
    add({v:1 for v in exceptions},hi=1)
    pp=[i for i,b in enumerate(bs) if b['kind']=='p']
    mm=[i for i,b in enumerate(bs) if b['kind'] in ('s','m','l')]
    add({i:1 for i in pp},0 if project else P,P)
    J={i:bs[i]['j'] for i in pp if bs[i]['j']}
    if j is not None:add(J,j,j)
    for kind,n in [('s',131),('m',48),('l',38),('c',1)]:
        add({i:1 for i,b in enumerate(bs) if b['kind']==kind},hi=n)
    repeat=[]
    for i in mm:
        r=bs[i]['rect']
        cover=[k for k in pp if intersects(r,(bs[k]['rect'][0]-5,bs[k]['rect'][1]-5,12,12))]
        z=var('repeat_'+str(i),0,P-1);repeat.append(z)
        add({i:-1,**{k:1 for k in cover}},lo=0)
        # Selected: z >= n-1; unselected: n<=P makes this automatic.
        add({z:1,i:-(P-1),**{k:-1 for k in cover}},lo=-P)
        add({z:1,i:-(P-1)},hi=0)
    add({**{i:bs[i]['loss'] for i in pp},**{z:1 for z in repeat}},hi=23*P-217)
    weights={i:sum(len(cells(b['rect'])&e) for e in EDGES)+2*b['j'] for i,b in enumerate(bs)}
    const=16*P+sum(map(len,EDGES))
    add(weights,lo=const-cap)
    if fixed:
        d=read('第72-74轮/推导72/witness185.json')
        chosen={(b['kind'],tuple(b[k] for k in ('x','y','w','h')),{'h':0,'v':1,'-':-1}[b['axis']]) for b in d['chosen']}
        found=set()
        for i,b in enumerate(bs):
            key=(b['kind'],b['rect'],b['axis']);val=int(key in chosen)
            add({i:1},val,val)
            if val:found.add(key)
        assert found==chosen
    summary=dict(units=len(bs),kinds=dict(Counter(b['kind'] for b in bs)),variables=len(names),constraints=len(rows),
                 project=project,J=j,P=P,cap=cap,fixed=fixed,edge_tables_used=False,score_lower_bound_imposed=False)
    return bs,names,lower,upper,rows,lbs,ubs,weights,const,summary

def run(a):
    start=time.monotonic()
    bs,names,lb,ub,rows,rl,ru,weights,const,summary=build(a.j,a.cap,not a.full,a.fixed,a.P)
    summary['script_sha256']=digest(Path(__file__))
    summary['geometry_script_sha256']=digest(OUT/'recompute.py')
    summary['matrix_sha256']=hashlib.sha256(json.dumps([rows,rl,ru,lb,ub],sort_keys=True).encode()).hexdigest()
    print('BUILT',json.dumps(summary),flush=True)
    summary['build_seconds']=time.monotonic()-start
    if a.engine=='cp':
        import ortools
        from ortools.sat.python import cp_model
        m=cp_model.CpModel()
        v=[m.new_int_var(l,h,n) for l,h,n in zip(lb,ub,names)]
        for row,l,h in zip(rows,rl,ru):
            expr=sum(c*v[i] for i,c in row.items())
            if l==h:m.add(expr==int(l))
            else:
                if math.isfinite(l):m.add(expr>=int(l))
                if math.isfinite(h):m.add(expr<=int(h))
        m.minimize(const-sum(c*v[i] for i,c in weights.items()))
        s=cp_model.CpSolver();s.parameters.num_search_workers=1;s.parameters.max_time_in_seconds=a.seconds
        s.parameters.random_seed=73;s.parameters.linearization_level=2;s.parameters.log_search_progress=True
        status=s.solve(m)
        summary.update(engine='CP-SAT',version=ortools.__version__,status=s.status_name(status),stats=s.response_stats())
        if status in (cp_model.FEASIBLE,cp_model.OPTIMAL):
            x=[s.value(z) for z in v]
            summary.update(S=round(s.objective_value),bound=s.best_objective_bound,chosen=[b for i,b in enumerate(bs) if x[i]])
        else:x=None
    else:
        import numpy as np
        import scipy
        from scipy.optimize import milp,Bounds,LinearConstraint
        from scipy.sparse import coo_matrix
        rr=[];cc=[];vv=[]
        for k,row in enumerate(rows):
            for i,c in row.items():rr.append(k);cc.append(i);vv.append(c)
        mat=coo_matrix((np.array(vv,dtype=float),(rr,cc)),shape=(len(rows),len(names))).tocsc()
        obj=np.zeros(len(names))
        for i,c in weights.items():obj[i]=-c
        result=milp(obj,integrality=np.ones(len(names)),bounds=Bounds(lb,ub),constraints=LinearConstraint(mat,rl,ru),
                    options=dict(time_limit=a.seconds,mip_rel_gap=0,disp=True,threads=1))
        summary.update(engine='HiGHS',version=scipy.__version__,status=int(result.status),message=result.message)
        x=None if result.x is None else [int(round(z)) for z in result.x]
        if x is not None:
            summary.update(S=const+round(result.fun),bound=const+result.mip_dual_bound,
                           chosen=[b for i,b in enumerate(bs) if x[i]])
    if x is not None:
        assert all(l<=z<=h for z,l,h in zip(x,lb,ub))
        for row,l,h in zip(rows,rl,ru):
            val=sum(c*x[i] for i,c in row.items());assert l<=val<=h
        summary['integer_rows_checked']=True
    summary['elapsed']=time.monotonic()-start
    save(a.name,summary)
    print('RESULT',json.dumps({k:v for k,v in summary.items() if k not in ('chosen','stats')}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--engine',choices=['cp','highs'],default='cp')
    p.add_argument('--j',type=int);p.add_argument('--cap',type=int,default=184);p.add_argument('--P',type=int,default=10)
    p.add_argument('--seconds',type=float,default=300);p.add_argument('--full',action='store_true')
    p.add_argument('--fixed',action='store_true');p.add_argument('--name',default='solve')
    run(p.parse_args())
