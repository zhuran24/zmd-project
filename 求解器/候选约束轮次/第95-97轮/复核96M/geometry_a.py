"""Fresh grid set-packing encoding; no imports from derivation or earlier audits."""
from ortools.sat.python import cp_model
from pathlib import Path
from collections import defaultdict
import json, time, argparse
OUT=Path(__file__).resolve().parent

def line(g):
    cells=[x for x in range(70) if x!=g]
    triples=[cells[i:i+3] for i in range(0,69,3)]
    assert all(b==a+1 and c==b+1 for a,b,c in triples)
    return [t[1] for t in triples]

def generate(gl,gb):
    ore={(1,y) for y in line(gl)}|{(x,1) for x in line(gb)}
    assert len(ore)==46
    candidates=[]
    for source in sorted(ore):
        x,y=source
        # The source at (1,1) belongs to the side with the nonzero gap.
        side='L' if x==1 and y in line(gl) else 'B'
        for offset in range(3):
            x0,y0=(2,y-offset) if side=='L' else (x-offset,2)
            body=frozenset((a,b) for a in range(x0,x0+3) for b in range(y0,y0+3))
            if min(x0,y0)<1 or max(x0,y0)>67 or body&ore:continue
            candidates.append((side,source,body,(x0,y0)))
    return ore,candidates

def branch(gl,gb,mode,rect=None):
    ore,raw=generate(gl,gb)
    fixed=set(); extra=0; witnesses=[]
    if mode:
        side='L' if gl else 'B'; g=gl or gb
        src=line(g); below=max(p for p in src if p<g); top=min(p for p in src if p>g)
        assert top-below==4
        local={(a,b) for a in range(1,4) for b in range(below+1,top)}
        fixed=local if side=='L' else {(b,a) for a,b in local}
        extra=2 if mode==1 or g==3 else 3
        if mode==2:
            for y in (below,top):
                if g==3 and y==below:continue
                for x in (2,3):witnesses.append((x,y) if side=='L' else (y,x))
    forbidden=set()
    if rect:
        b,h=rect
        forbidden={(x,y) for x in range(2,8) for y in range(b,b+h)}
    if fixed&forbidden:return None
    choices=[v for v in raw if not v[2]&(fixed|forbidden)]
    m=cp_model.CpModel(); v=[m.new_bool_var('normal_%d'%i) for i in range(len(choices))]
    cell=defaultdict(list); source=defaultdict(list)
    for i,(_,s,body,_) in enumerate(choices):
        source[s].append(v[i])
        for p in body:cell[p].append(v[i])
    for lst in cell.values():
        if len(lst)>1:m.add_at_most_one(lst)
    for lst in source.values():
        if len(lst)>1:m.add_at_most_one(lst)
    if gl==3:m.add(sum(v[i] for i,x in enumerate(choices) if x[0]=='B')<=22)
    if gb==3:m.add(sum(v[i] for i,x in enumerate(choices) if x[0]=='L')<=22)
    if mode==2:
        av=[]
        for k,p in enumerate(witnesses):
            if p in forbidden:continue
            w=m.new_bool_var('second_%d'%k);av.append(w)
            for obj in cell[p]:m.add(w+obj<=1)
        m.add(sum(av)>=1)
    m.maximize(sum(v)); solver=cp_model.CpSolver()
    solver.parameters.num_search_workers=1
    solver.parameters.max_time_in_seconds=10
    status=solver.solve(m)
    if status==cp_model.INFEASIBLE:return 'infeasible'
    if status!=cp_model.OPTIMAL:raise RuntimeError((gl,gb,mode,rect,solver.status_name(status)))
    value=46+int(round(solver.objective_value))+extra
    return {'value':value,'selected':[list(x[3]) for i,x in enumerate(choices) if solver.value(v[i])],
            'bound':46+int(round(solver.best_objective_bound))+extra,'status':'OPTIMAL'}

def cases():
    for gl in range(0,70,3):
        for gb in range(0,70,3):
            if gl and gb:continue
            modes=range(3) if gl not in (0,69) or gb not in (0,69) else (0,)
            for mode in modes:yield gl,gb,mode

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scope',action='store_true');args=parser.parse_args()
    rows=[];excluded=0;start=time.monotonic()
    for gl,gb,mode in cases():
        ore,_=generate(gl,gb)
        configs=[None]
        if args.scope:
            configs=[(b,h) for h in range(6,10) for b in range(3,70-h) if sum(1 for x,y in ore if x==1 and b<=y<b+h)<=2]
        for rect in configs:
            result=branch(gl,gb,mode,rect)
            if result is None:excluded+=1; continue
            d=0 if rect is None else sum(1 for x,y in ore if x==1 and rect[0]<=y<rect[0]+rect[1])
            if result=='infeasible':
                rows.append({'key':[gl,gb,mode,*(() if rect is None else rect)],'status':'INFEASIBLE','d':d});continue
            rows.append({'key':[gl,gb,mode,*(() if rect is None else rect)],'d':d,**result})
        if args.scope and len(rows)//1000!=(len(rows)-len(configs))//1000:print('completed',len(rows),flush=True)
    name='scope_a' if args.scope else 'corner_a'
    answer={'encoding':'grid_CP-SAT','rows':rows,'fixed_conflicts':excluded,'count':len(rows),
            'max':max(r['value']+r['d'] for r in rows if 'value' in r),'seconds':time.monotonic()-start}
    (OUT/(name+'.json')).write_text(json.dumps(answer,separators=(',',':'))+'\n')
    print({k:v for k,v in answer.items() if k!='rows'},flush=True)
if __name__=='__main__':main()
