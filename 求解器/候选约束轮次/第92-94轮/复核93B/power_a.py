"""Fresh CP-SAT coverage relaxation, cell packing + direct side inequalities.
Single thread; successes are completed finite infeasibility searches, not formal SAT proofs.
"""
import argparse, json, time, hashlib
from pathlib import Path
from ortools.sat.python import cp_model
OUT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=float,default=180);args=parser.parse_args()

def build(edge):
    pole={(x,y) for x in (5,6) for y in (5,6)}
    opts=[]
    for width,height,axes,weight in [(3,3,('x','y'),2),(5,5,('x','y'),3),(6,4,('y',),3),(4,6,('x',),3)]:
        for x in range(1-width,12):
            for y in range(1-height,12):
                cells={(x+i,y+j) for i in range(width) for j in range(height)}
                if cells&pole or edge and x+width-1>6:continue
                for axis in axes:
                    sides=([{(x-1,y+j) for j in range(height)},{(x+width,y+j) for j in range(height)}] if axis=='x' else [{(x+i,y-1) for i in range(width)},{(x+i,y+height) for i in range(width)}])
                    sides=[{c for c in s if c not in pole and (not edge or c[0]<=6)} for s in sides]
                    if not all(sides):continue
                    opts.append((x,y,width,height,axis,weight,cells,sides))
    return opts

results=[]
for edge in (False,True):
    options=build(edge);model=cp_model.CpModel();z=[model.new_bool_var(f'p{i}') for i in range(len(options))]
    bycell={}
    for i,o in enumerate(options):
        for c in o[6]:bycell.setdefault(c,[]).append(i)
    for indices in bycell.values():model.add(sum(z[i] for i in indices)<=1)
    for i,o in enumerate(options):
        for side in o[7]:
            coeff={}
            for c in side:
                for j in bycell.get(c,[]):coeff[j]=coeff.get(j,0)+1
            model.add(sum(v*z[j] for j,v in coeff.items())+z[i]<=len(side))
    count=sum(z);weight=sum(o[5]*z[i] for i,o in enumerate(options))
    model.add(count<=14 if edge else count<=24)
    for kind,target in [('count',14 if edge else 24),('weight',30 if edge else 55)]:
        if kind=='weight':model.add(count<=13 if edge else count<=23)
        threshold=model.new_bool_var(f'bound_{kind}')
        model.add((count if kind=='count' else weight)>=target).only_enforce_if(threshold)
        model.clear_assumptions();model.add_assumption(threshold)
        solver=cp_model.CpSolver();solver.parameters.num_search_workers=1;solver.parameters.max_time_in_seconds=args.seconds
        start=time.monotonic();status=solver.solve(model)
        record={'edge':edge,'kind':kind,'target':target,'options':len(options),'status':solver.status_name(status),'seconds':time.monotonic()-start,'branches':solver.num_branches,'conflicts':solver.num_conflicts}
        results.append(record);print(json.dumps(record),flush=True)
        model.clear_assumptions();model.add(threshold==0)
        if kind=='count' and status!=cp_model.INFEASIBLE:break
    encoded=[[o[0],o[1],o[2],o[3],o[4],o[5]] for o in options]
    (OUT/f'power_a_domain_{edge}.json').write_text(json.dumps(sorted(encoded),ensure_ascii=False)+'\n')
    (OUT/'power_a.json').write_text(json.dumps(results,indent=2)+'\n')
