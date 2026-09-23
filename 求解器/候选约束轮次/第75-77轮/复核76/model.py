"""Independent linear integer boundary relaxation, without inherited tables.
One mathematical matrix; CP-SAT and HiGHS are two execution backends.
"""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from geometry import *
import argparse,time,hashlib,warnings
from collections import defaultdict
class Matrix:
    def __init__(self): self.names=[];self.ub=[];self.rows=[];self.lo=[];self.hi=[]
    def var(self,name,upper=1):
        self.names.append(name);self.ub.append(upper);return len(self.ub)-1
    def add(self,row,lo=None,hi=None):
        row={k:v for k,v in row.items() if v};self.rows.append(row);self.lo.append(lo);self.hi.append(hi)
    def eq(self,row,value):self.add(row,value,value)
def build(P,cap,j=None,full=False,fixed=None):
    us=domains(P,full);mat=Matrix()
    for u in us:mat.var(str(tuple(u[k] for k in ('kind','x','y','w','h','axis'))))
    inc=defaultdict(list)
    for i,u in enumerate(us):
        for c in body(u):inc[c].append(i)
    occ={}
    for c,ids in sorted(inc.items()):
        o=mat.var('occupied'+str(c));occ[c]=o
        mat.eq(dict([(o,-1)]+[(i,1) for i in ids]),0)
    for i,u in enumerate(us):
        ss=ports(u)
        for no,s in enumerate(ss):
            need=2 if u['kind']=='c' and no==6 else 1
            row=Counter({i:need});row.update(occ[c] for c in s if c in occ)
            mat.add(row,hi=len(s))
    # Exactly one of all 47 coupled boundary configurations.
    bv=[]
    for gaps,ff in bands():
        b=mat.var('warehouse'+str(gaps));bv.append(b)
        for c in ff:
            if c in occ:mat.add({b:1,occ[c]:1},hi=1)
    mat.eq({b:1 for b in bv},1)
    # Pick an input side for each selected large unit. Side choices sum to u.
    exceptions=[]
    for i,u in enumerate(us):
        if u['kind']!='l':continue
        d=[mat.var('input'+str((i,s))) for s in (0,1)]
        mat.eq({d[0]:1,d[1]:1,i:-1},0)
        e=mat.var('two_ports'+str(i));exceptions.append(e);mat.add({e:1,i:-1},hi=0)
        for v,s in zip(d,ports(u)):
            row=Counter({v:3,e:-1});row.update(occ[c] for c in s if c in occ)
            mat.add(row,hi=len(s))
    mat.add({e:1 for e in exceptions},hi=1)
    ps=[i for i,u in enumerate(us) if u['kind']=='p']
    if full:mat.eq({i:1 for i in ps},P)
    else:mat.add({i:1 for i in ps},hi=P)
    if j is not None:mat.eq({i:edge(us[i]) for i in ps},j)
    for kind,n in [('s',131),('m',48),('l',38),('c',1)]:
        mat.add({i:1 for i,u in enumerate(us) if u['kind']==kind},hi=n)
    repeat=[]
    for i,u in enumerate(us):
        if u['kind'] not in ('s','m','l'):continue
        touching=[p for p in ps if powered(u,us[p])]
        mat.add(dict([(i,-1)]+[(p,1) for p in touching]),lo=0)
        z=mat.var('repeat'+str(i),P-1);repeat.append(z)
        mat.add({z:1,i:-(P-1)},hi=0)
        # n <= z+1 if u=1; n<=P if u=0.
        mat.add(dict([(z,-1),(i,P-1)]+[(p,1) for p in touching]),hi=P)
    loss={i:us[i]['loss'] for i in ps}
    mat.add(dict(list(loss.items())+[(z,1) for z in repeat]),hi=23*P-217)
    # S=16P+138 - weighted occupied boundary cells - 2J.
    gain={i:sum(WEIGHT[c] for c in body(u))+2*(edge(u) if u['kind']=='p' else 0) for i,u in enumerate(us)}
    mat.add(gain,lo=16*P+138-cap)
    if fixed is not None:
        d=json.loads(Path(fixed).read_text());keys={tuple(u[k] for k in ('kind','x','y','w','h','axis')) for u in d['chosen']}
        found=set()
        for i,u in enumerate(us):
            key=tuple(u[k] for k in ('kind','x','y','w','h','axis'))
            mat.eq({i:1},int(key in keys))
            if key in keys:found.add(key)
        assert found==keys
    return mat,us,gain
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--P',type=int,default=10);ap.add_argument('--j',type=int);ap.add_argument('--cap',type=int,default=187)
    ap.add_argument('--engine',choices=['cp','highs'],default='cp');ap.add_argument('--seconds',type=int,default=600);ap.add_argument('--workers',type=int,default=2);ap.add_argument('--full',action='store_true');ap.add_argument('--fixed');ap.add_argument('--name',required=True)
    a=ap.parse_args();t=time.monotonic();m,us,gain=build(a.P,a.cap,a.j,a.full,a.fixed)
    digest=hashlib.sha256(json.dumps([m.ub,m.rows,m.lo,m.hi],sort_keys=True).encode()).hexdigest()
    result=dict(arguments=vars(a),units=dict(Counter(u['kind'] for u in us)),variables=len(m.ub),constraints=len(m.rows),matrix_sha256=digest,source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (OUT/'geometry.py',Path(__file__))},build_seconds=time.monotonic()-t)
    print(result,flush=True);values=None
    if a.engine=='cp':
        from ortools.sat.python import cp_model
        import ortools
        cp=cp_model.CpModel();vs=[cp.new_int_var(0,b,n) for b,n in zip(m.ub,m.names)]
        for row,lo,hi in zip(m.rows,m.lo,m.hi):
            expr=sum(vs[i]*v for i,v in row.items())
            if lo is not None:cp.add(expr>=lo)
            if hi is not None:cp.add(expr<=hi)
        s=cp_model.CpSolver();s.parameters.max_time_in_seconds=a.seconds;s.parameters.num_search_workers=a.workers;s.parameters.log_search_progress=True;s.parameters.linearization_level=2;s.parameters.random_seed=76
        st=s.solve(cp);result.update(status=s.status_name(st),version=ortools.__version__,stats=s.response_stats())
        if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):values=[s.value(v) for v in vs]
    else:
        import numpy as np, scipy
        from scipy.optimize import milp,Bounds,LinearConstraint
        from scipy.sparse import coo_matrix
        rr=[];cc=[];dd=[]
        for k,row in enumerate(m.rows):
            for i,v in row.items():rr.append(k);cc.append(i);dd.append(v)
        A=coo_matrix((np.array(dd,dtype=float),(rr,cc)),shape=(len(m.rows),len(m.ub))).tocsc()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            r=milp(np.zeros(len(m.ub)),integrality=np.ones(len(m.ub)),bounds=Bounds(np.zeros(len(m.ub)),m.ub),constraints=LinearConstraint(A,[-np.inf if v is None else v for v in m.lo],[np.inf if v is None else v for v in m.hi]),options={'time_limit':a.seconds,'threads':a.workers,'disp':True,'mip_rel_gap':0.0})
        result.update(status={0:'OPTIMAL',1:'UNKNOWN',2:'INFEASIBLE'}.get(r.status,str(r.status)),message=r.message,version=scipy.__version__)
        if r.x is not None:values=[round(v) for v in r.x]
    if values is not None:
        assert all(0<=v<=b for v,b in zip(values,m.ub))
        for row,lo,hi in zip(m.rows,m.lo,m.hi):
            val=sum(values[i]*v for i,v in row.items())
            assert (lo is None or val>=lo) and (hi is None or val<=hi)
        result.update(S=16*a.P+138-sum(gain[i]*values[i] for i in gain),chosen=[u for i,u in enumerate(us) if values[i]])
    result['seconds']=time.monotonic()-t;dump(a.name+'.json',result);print({k:v for k,v in result.items() if k not in ('chosen','stats')},flush=True)
if __name__=='__main__':main()
