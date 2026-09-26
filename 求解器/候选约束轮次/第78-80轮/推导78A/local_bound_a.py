"""Final encoding A: local integer packing with occupied-cell linear rows.

The only imported geometric count bounds are the OFFICIAL 23 (general) and
14 (one boundary) manufacturing-unit limits. No candidate is a premise.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:10])
from pathlib import Path
from collections import Counter,defaultdict
from fractions import Fraction
import json,time,hashlib,argparse
OUT=Path(__file__).resolve().parent
SPECS=[('s',3,3,0),('s',3,3,1),('m',5,5,0),('m',5,5,1),('l',6,4,1),('l',4,6,0)]

def rectangle(x,y,w,h):return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}
def make_model(wall):
    pole=rectangle(5,5,2,2)
    def valid(c):return c not in pole and (not wall or c[0]<=6)
    objects=[]
    for kind,w,h,axis in SPECS:
        for x in range(1-w,12):
            for y in range(1-h,12):
                body=rectangle(x,y,w,h)
                if not all(valid(c) for c in body):continue
                ports=([[(x-1,j) for j in range(y,y+h)],[(x+w,j) for j in range(y,y+h)]] if axis==0 else
                       [[(i,y-1) for i in range(x,x+w)],[(i,y+h) for i in range(x,x+w)]])
                ports=[[c for c in ps if valid(c)] for ps in ports]
                if all(ports):objects.append(dict(kind=kind,r=[x,y,w,h],axis=axis,body=sorted(body),ports=ports))
    incidence=defaultdict(list)
    for i,z in enumerate(objects):
        for c in z['body']:incidence[tuple(c)].append(i)
    rows=[]
    for c in sorted(incidence):rows.append(dict(label=['cell',*c],terms=[[i,1] for i in incidence[c]],rhs=1))
    for i,z in enumerate(objects):
        for k,ps in enumerate(z['ports']):
            co=Counter({i:1})
            for c in ps:co.update(incidence[tuple(c)])
            rows.append(dict(label=['port',i,k],terms=sorted(co.items()),rhs=len(ps)))
    rows.append(dict(label=['official_count'],terms=[[i,1] for i in range(len(objects))],rhs=14 if wall else 23))
    return dict(wall=wall,objects=objects,rows=rows,coefficients=[2 if z['kind']=='s' else 3 for z in objects])

def write(name,d):
    (OUT/name).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')

def solve(data,threshold,seconds,workers,name,fixed=None):
    from ortools.sat.python import cp_model
    import ortools
    start=time.monotonic();model=cp_model.CpModel();vs=[model.new_bool_var('u%d'%i) for i in range(len(data['objects']))]
    for row in data['rows']:model.add(sum(vs[i]*v for i,v in row['terms'])<=row['rhs'])
    score=sum(v*c for v,c in zip(vs,data['coefficients']))
    if threshold is not None:model.add(score>=threshold)
    else:model.maximize(score)
    if fixed:
        keys={(z['kind'],*z['r'],z['axis']) for z in fixed}
        for z,v in zip(data['objects'],vs):model.add(v==int((z['kind'],*z['r'],z['axis']) in keys))
    solver=cp_model.CpSolver();solver.parameters.num_search_workers=workers
    solver.parameters.max_time_in_seconds=seconds;solver.parameters.log_search_progress=True
    solver.parameters.linearization_level=2;solver.parameters.random_seed=7802
    status=solver.solve(model)
    result=dict(wall=data['wall'],threshold=threshold,status=solver.status_name(status),solver_version=ortools.__version__,
                seconds=time.monotonic()-start,model_sha256=hashlib.sha256(str(model.proto).encode()).hexdigest(),
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),stats=solver.response_stats())
    if status in (cp_model.FEASIBLE,cp_model.OPTIMAL):
        result['chosen']=[{k:z[k] for k in ('kind','r','axis')} for z,v in zip(data['objects'],vs) if solver.value(v)]
        result['counts']=dict(Counter(z['kind'] for z in result['chosen']));result['score']=solver.value(score)
    write(name+'.json',result);print({k:v for k,v in result.items() if k not in ('chosen','stats')},flush=True)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--wall',action='store_true');ap.add_argument('--threshold',type=int)
    ap.add_argument('--seconds',type=int,default=120);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--name',required=True);ap.add_argument('--fixed')
    a=ap.parse_args();data=make_model(a.wall);filename='final_wall_model_a.json' if a.wall else 'final_general_model_a.json'
    write(filename,data);print('model',len(data['objects']),len(data['rows']),flush=True)
    fixed=json.loads(Path(a.fixed).read_text())['chosen'] if a.fixed else None
    solve(data,a.threshold,a.seconds,a.workers,a.name,fixed)
if __name__=='__main__':main()
