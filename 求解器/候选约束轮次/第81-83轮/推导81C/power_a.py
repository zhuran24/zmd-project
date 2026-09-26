"""Encoding A: cell-set enumeration and direct integer port inequalities."""
import os
os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:5]))
from pathlib import Path
from collections import defaultdict, Counter
import itertools, json, time, hashlib
from ortools.sat.python import cp_model

OUT = Path(__file__).resolve().parent

def generate(edge):
    area = set(itertools.product(range(12), repeat=2))
    pole = set(itertools.product((5,6), repeat=2))
    result = []
    for x,y in itertools.product(range(-6,13), repeat=2):
        for w,h in ((3,3),(5,5),(6,4),(4,6)):
            body = {(x+i,y+j) for i in range(w) for j in range(h)}
            if not body & area or body & pole or (edge and any(a>6 for a,b in body)):
                continue
            for axis in ((0,1) if w==h else (1,) if w==6 else (0,)):
                step = (1,0) if axis==0 else (0,1)
                sides=[]
                for sign in (-1,1):
                    sd={(a+sign*step[0],b+sign*step[1]) for a,b in body
                        if (a+sign*step[0],b+sign*step[1]) not in body}
                    sd={g for g in sd if g not in pole and (not edge or g[0]<=6)}
                    sides.append(sd)
                if all(sides):
                    result.append(dict(key=[x,y,w,h,axis],body=sorted(body),sides=[sorted(s) for s in sides],weight=2 if w==3 else 3))
    return result

def solve(edge, threshold, unit=False):
    opts=generate(edge); m=cp_model.CpModel()
    u=[m.NewBoolVar('u'+str(i)) for i in range(len(opts))]
    occ=defaultdict(list)
    for i,o in enumerate(opts):
        for g in o['body']: occ[g].append(i)
    for ids in occ.values(): m.Add(sum(u[i] for i in ids)<=1)
    for i,o in enumerate(opts):
        for sd in o['sides']:
            terms=Counter({i:1})
            for g in sd: terms.update(occ.get(g,[]))
            m.Add(sum(c*u[j] for j,c in terms.items())<=len(sd))
    m.Add(sum(u)<= (14 if edge else 23))
    m.Add(sum((1 if unit else o['weight'])*u[i] for i,o in enumerate(opts))>=threshold)
    solver=cp_model.CpSolver()
    solver.parameters.num_workers=3
    solver.parameters.max_time_in_seconds=600
    solver.parameters.log_search_progress=True
    start=time.monotonic(); st=solver.Solve(m)
    name=('edge' if edge else 'general')+('_count' if unit else '_weight')
    result=dict(encoding='A direct integer inequalities',edge=edge,unit=unit,threshold=threshold,
        options=len(opts),status=solver.StatusName(st),seconds=time.monotonic()-start,
        workers=3,model_sha256=hashlib.sha256(str(m.Proto()).encode()).hexdigest(),response=solver.ResponseStats())
    if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        result['chosen']=[o for i,o in enumerate(opts) if solver.Value(u[i])]
    (OUT/(name+'_a.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (OUT/(name+'_domain_a.json')).write_text(json.dumps(opts,separators=(',',':'))+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='chosen'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    solve(False,55)
    solve(True,30)
    solve(True,14,True)
