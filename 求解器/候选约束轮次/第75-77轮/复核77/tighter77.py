"""Add only independently regenerated line bounds to the review model."""
from model77 import *
from ortools.sat.python import cp_model

def main():
    started=time.monotonic();m,units,reward,warehouse=build(1,184)
    checks=read(OUT/'edge_checks.json')
    case=next(c for c in checks['local']['cases'] if c['mask']==[0,0])
    for line,tab in zip(LINES,case['lines']):
        line=set(line);meet=[i for i,u in enumerate(units) if cells(u['r'])&line]
        candidates=[(state,cost) for state,cost in tab['frontier'] if state[2]<=13]
        flags=[m.var() for _ in candidates]
        m.row([(v,1) for v in flags],1,1)
        for k,kind in [(0,'c'),(1,'p')]:
            m.row([(i,1) for i in meet if units[i]['kind']==kind]+[(v,-state[k]) for v,(state,cost) in zip(flags,candidates)],0,0)
        m.row([(i,units[i]['loss']) for i in meet if units[i]['kind']=='p']+[(v,-state[2]) for v,(state,cost) in zip(flags,candidates)],lo=0)
        m.row([(i,len(cells(units[i]['r'])&line)+2*units[i]['j']) for i in meet]+[(v,cost) for v,(state,cost) in zip(flags,candidates)],hi=len(line))
    cm=cp_model.CpModel();vs=[cm.new_int_var(lo,hi,str(i)) for i,(lo,hi) in enumerate(m.bounds)]
    for terms,lo,hi in m.rows:
        expr=sum(vs[i]*v for i,v in terms)
        if lo is not None:cm.add(expr>=lo)
        if hi is not None:cm.add(expr<=hi)
    metadata=dict(J=1,cap=184,units=len(units),rows=len(m.rows),variables=len(m.bounds),
      model_sha256=hashlib.sha256(json.dumps([m.bounds,m.rows]).encode()).hexdigest(),
      code_sha256={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ['geometry77.py','model77.py','edges77.py','tighter77.py']})
    print(metadata,flush=True)
    solver=cp_model.CpSolver();solver.parameters.num_search_workers=4;solver.parameters.max_time_in_seconds=600
    solver.parameters.linearization_level=2;solver.parameters.log_search_progress=True;solver.parameters.random_seed=7711
    status=solver.solve(cm);metadata.update(status=solver.status_name(status),stats=solver.response_stats(),seconds=time.monotonic()-started)
    save('J1_cap184_rebuilt_edges.json',metadata);print(metadata,flush=True)
if __name__=='__main__':main()
