"""Independent encoding B. No imports from any other project program.

Builds explicit occupancy Boolean variables and conditional port vacancies.
Only official 23 / 14 machine counts are used, including in the boundary case.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:10])
import json,time,hashlib,argparse
from pathlib import Path
from collections import defaultdict,Counter
from ortools.sat.python import cp_model
OUT=Path(__file__).resolve().parent

def enumerate_objects(wall):
    objects=[]
    # Scan a common square of anchors; then test rectangular intersection.
    for x in range(-5,12):
        for y in range(-5,12):
            for typ,w,h,vertical in [('s',3,3,False),('s',3,3,True),('m',5,5,False),('m',5,5,True),('l',4,6,False),('l',6,4,True)]:
                if x+w<=0 or y+h<=0:continue
                if x<7 and x+w>5 and y<7 and y+h>5:continue
                if wall and x+w>7:continue
                body={(xx,yy) for xx in range(x,x+w) for yy in range(y,y+h)}
                if vertical:ports=[[(xx,y-1) for xx in range(x,x+w)],[(xx,y+h) for xx in range(x,x+w)]]
                else:ports=[[(x-1,yy) for yy in range(y,y+h)],[(x+w,yy) for yy in range(y,y+h)]]
                ports=[[c for c in ps if not(5<=c[0]<7 and 5<=c[1]<7) and (not wall or c[0]<7)] for ps in ports]
                if min(map(len,ports))==0:continue
                objects.append(dict(kind=typ,r=[x,y,w,h],axis=int(vertical),body=body,ports=ports))
    return objects

def build(wall,threshold=None,maximize=True,fix=None,engine='cp'):
    objects=enumerate_objects(wall);m=cp_model.CpModel()
    chosen=[m.new_bool_var('chosen%d'%k) for k in range(len(objects))]
    inc=defaultdict(list)
    for i,z in enumerate(objects):
        for c in z['body']:inc[c].append(i)
    occupied={c:m.new_bool_var('occupied%s'%str(c)) for c in sorted(inc)}
    for c,ids in inc.items():m.add(occupied[c]==sum(chosen[i] for i in ids))
    for i,z in enumerate(objects):
        for ps in z['ports']:
            # Each selected manufacturing unit has a free cell on both port sides.
            m.add(sum(occupied[c] for c in ps if c in occupied)<=len(ps)-1).only_enforce_if(chosen[i])
    m.add(sum(chosen)<=14 if wall else sum(chosen)<=23)
    score=sum((2 if z['kind']=='s' else 3)*v for z,v in zip(objects,chosen))
    if threshold is not None:m.add(score>=threshold)
    if maximize:m.maximize(score)
    if fix is not None:
        keys={(d['kind'],*d['r'],d['axis']) for d in fix}
        for z,v in zip(objects,chosen):m.add(v==int((z['kind'],*z['r'],z['axis']) in keys))
        assert len(keys)==len(fix)
    return m,objects,chosen,score

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--wall',action='store_true');ap.add_argument('--threshold',type=int)
    ap.add_argument('--seconds',type=int,default=120);ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--name',required=True);ap.add_argument('--fixed');ap.add_argument('--engine',choices=['cp','highs'],default='cp')
    args=ap.parse_args();start=time.monotonic()
    fixed=json.loads(Path(args.fixed).read_text())['chosen'] if args.fixed else None
    m,objects,chosen,score=build(args.wall,args.threshold,args.threshold is None,fixed)
    source=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out=dict(args=vars(args),objects=len(objects),source_sha256=source,model_sha256=hashlib.sha256(str(m.proto).encode()).hexdigest(),uses_boundary_13=False)
    print('built',len(objects),'variables',len(m.proto.variables),flush=True)
    values=None
    if args.engine=='cp':
        solver=cp_model.CpSolver();solver.parameters.num_search_workers=args.workers
        solver.parameters.max_time_in_seconds=args.seconds;solver.parameters.log_search_progress=True
        solver.parameters.linearization_level=2;solver.parameters.random_seed=7803
        st=solver.solve(m);out.update(status=solver.status_name(st),objective=solver.objective_value,bound=solver.best_objective_bound,stats=solver.response_stats())
        if st in (cp_model.FEASIBLE,cp_model.OPTIMAL):values=[solver.value(v) for v in chosen]
    else:
        # A separate explicit integer matrix, not exported from encoding A.
        import numpy as np
        from scipy.optimize import milp,Bounds,LinearConstraint
        from scipy.sparse import coo_matrix
        n=len(objects);inc=defaultdict(list)
        for i,z in enumerate(objects):
            for c in z['body']:inc[c].append(i)
        rows=[];rhs=[]
        for c in sorted(inc):rows.append(Counter({i:1 for i in inc[c]}));rhs.append(1)
        for i,z in enumerate(objects):
            for ps in z['ports']:
                r=Counter({i:1})
                for c in ps:r.update(inc[c])
                rows.append(r);rhs.append(len(ps))
        rows.append(Counter({i:1 for i in range(n)}));rhs.append(14 if args.wall else 23)
        coeff=np.array([2 if z['kind']=='s' else 3 for z in objects])
        if args.threshold is not None:rows.append(Counter({i:-int(v) for i,v in enumerate(coeff)}));rhs.append(-args.threshold)
        ri=[];ci=[];co=[]
        for j,r in enumerate(rows):
            for i,v in r.items():ri.append(j);ci.append(i);co.append(v)
        mat=coo_matrix((co,(ri,ci)),shape=(len(rows),n)).tocsc()
        result=milp(np.zeros(n) if args.threshold is not None else -coeff,integrality=np.ones(n),bounds=Bounds(np.zeros(n),np.ones(n)),constraints=LinearConstraint(mat,-np.inf,np.array(rhs)),options={'disp':True,'time_limit':args.seconds,'threads':args.workers,'mip_rel_gap':0.0})
        out.update(status={0:'OPTIMAL',1:'UNKNOWN',2:'INFEASIBLE'}.get(result.status,str(result.status)),message=result.message)
        if result.x is not None:values=[round(v) for v in result.x]
    if values is not None:
        out['chosen']=[{k:z[k] for k in ('kind','r','axis')} for z,v in zip(objects,values) if v]
        out['counts']=dict(Counter(z['kind'] for z,v in zip(objects,values) if v))
        out['score']=sum((2 if z['kind']=='s' else 3)*v for z,v in zip(objects,values))
    out['seconds']=time.monotonic()-start
    (OUT/(args.name+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print({k:v for k,v in out.items() if k not in ('stats','chosen')},flush=True)
if __name__=='__main__':main()
