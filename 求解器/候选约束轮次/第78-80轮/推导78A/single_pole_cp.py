"""Integer local power tables, with exact LP-equality cuts if requested."""
from single_pole_lp import matrix
from geometry_a import *
from ortools.sat.python import cp_model
from fractions import Fraction as F
import argparse,time,hashlib

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--wall',action='store_true');ap.add_argument('--a',type=int,default=2)
    ap.add_argument('--wm',type=int,default=1);ap.add_argument('--wl',type=int,default=1)
    ap.add_argument('--threshold',type=int);ap.add_argument('--seconds',type=int,default=120)
    ap.add_argument('--workers',type=int,default=4);ap.add_argument('--name',required=True);ap.add_argument('--face',action='store_true')
    args=ap.parse_args();start=time.monotonic();objs,rows,A,rhs_array=matrix(args.wall)
    m=cp_model.CpModel();vs=[m.new_bool_var('u%d'%i) for i in range(len(objs))]
    for co,b in rows:m.add(sum(vs[i]*a for i,a in co.items())<=b)
    coeff=[args.a+(args.wm if z['kind']=='m' else args.wl if z['kind']=='l' else 0) for z in objs]
    objective=sum(v*a for v,a in zip(vs,coeff))
    if args.threshold is None:m.maximize(objective)
    else:m.add(objective>=args.threshold)
    face_info=None
    if args.face:
        import numpy as np
        from scipy.optimize import linprog
        res=linprog(-np.array(coeff),A_ub=A,b_ub=rhs_array,bounds=(0,1),method='highs',options={'threads':1})
        assert res.success
        yy=[F(float(max(0,-q))).limit_denominator(1000000) for q in res.ineqlin.marginals]
        cc=[F(0) for _ in objs];rhs=F(0)
        for yyj,(row,bb) in zip(yy,rows):
            rhs+=yyj*bb
            for i,aa in row.items():cc[i]+=yyj*aa
        repairs=[max(F(0),F(co)-ci) for co,ci in zip(coeff,cc)]
        rhs+=sum(repairs)
        face_info=dict(upper=str(rhs),rows=sum(bool(q) for q in yy),bounds=sum(bool(q) for q in repairs))
        cert=dict(wall=args.wall,coefficients=coeff,rows=[[i,q.numerator,q.denominator] for i,q in enumerate(yy) if q],
                  bounds=[[i,q.numerator,q.denominator] for i,q in enumerate(repairs) if q],upper=str(rhs))
        dump(args.name+'_dual.json',cert)
        assert args.threshold==rhs
        for q,(row,bb) in zip(yy,rows):
            if q:m.add(sum(vs[i]*aa for i,aa in row.items())==bb)
        for i,(q,ci,co) in enumerate(zip(repairs,cc,coeff)):
            if q:m.add(vs[i]==1)
            if ci+q>co:m.add(vs[i]==0)
    solver=cp_model.CpSolver();solver.parameters.num_search_workers=args.workers
    solver.parameters.max_time_in_seconds=args.seconds;solver.parameters.log_search_progress=True
    solver.parameters.linearization_level=2;solver.parameters.random_seed=7802
    print('built',len(objs),len(rows),'seconds',time.monotonic()-start,flush=True)
    st=solver.solve(m)
    out=dict(args=vars(args),status=solver.status_name(st),objective=solver.objective_value,bound=solver.best_objective_bound,
             seconds=time.monotonic()-start,model_sha256=hashlib.sha256(str(m.proto).encode()).hexdigest(),face=face_info,stats=solver.response_stats())
    if st in (cp_model.FEASIBLE,cp_model.OPTIMAL):
        selected=[z for z,v in zip(objs,vs) if solver.value(v)]
        out['chosen']=[{k:z[k] for k in ('kind','r','axis')} for z in selected]
        out['counts']=dict(Counter(z['kind'] for z in selected));out['score']=solver.value(objective)
    dump(args.name+'.json',out);print({k:v for k,v in out.items() if k not in ('chosen','stats')},flush=True)
if __name__=='__main__':main()
