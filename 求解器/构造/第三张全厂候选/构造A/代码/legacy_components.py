#!/usr/bin/env python3
"""Re-run unmodified legacy geometry and average-flow modules, not formal ledgers.

The full legacy version gates are NOT claimed adapted to the 77-condition rules.
The wrapper binds the current frozen sources and reports only module diagnostics.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
import sys,json,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];seat=sys.argv[1];candidate=Path(sys.argv[2]);sys.path.insert(0,str(BASE/('检查器'+seat)));d=json.loads(candidate.read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert d['source_fingerprints']=={k:sha(BASE/'依据快照'/n) for k,n in [('rules','《明日方舟：终末地》游戏规则.txt'),('task','求解任务.txt'),('constraints','求解约束.txt')]}
result=dict(seat=seat,scope='unmodified geometry and average-flow modules only; full 77-condition/version gate not adapted',candidate_sha256=sha(candidate),static_pass=False,runtime_certified=False)
if seat=='A':
    from schema import validate
    validate(d);result['strict_v1_syntax']=True
    from geometry import Geometry
    from flow import Flow
    class Report:
        def __init__(self):self.checks={}
        def check(self,k,ok,basis,detail):
            q=self.checks.setdefault(k,dict(status='PASS',count=0,failures=[]));q['count']+=1
            if not ok:q['status']='FAIL';q['failures'].append(detail)
        def na(self,k,basis,detail):self.checks.setdefault(k,dict(status='NA',detail=detail))
        def blocked(self,k,basis,detail):self.checks[k]=dict(status='BLOCKED',detail=detail)
        def alias(self,k,other,basis):self.checks[k]=dict(status=self.checks.get(other,{}).get('status','UNKNOWN'),alias=other)
    r=Report();g=Geometry(d,r).build();lp=Flow(g).build();flow,x=lp.run(30)
    result.update(geometry_checks=r.checks,geometry=dict(occupied_cells=len(g.occ),channels=len(g.channels),paths=len(g.path_decomposition),maximum=g.maximum,power_all=all(g.power[u['id']] for u in d['layout']['machines'])),flow=flow)
else:
    from geometry import Geometry,Checks,structural,check_rectangle
    from interfaces import check_interfaces
    from flow import build
    cc=Checks();g=Geometry(d['layout'],cc);structural(d,g,cc);check_rectangle(d,g,cc);ok=check_interfaces(d,g,cc);lp=build(d,g);flow,x=lp.solve(30)
    result.update(geometry_checks=cc.records,geometry=dict(occupied_cells=len(g.occ),channels=len(g.edges),paths=len(g.paths),maximum=g.rectangle,power_all=all(g.powered[u['id']] for u in d['layout']['machines'])),interfaces_ok=ok,flow=flow)
result['implementation_sha256']={p.name:sha(p) for p in (BASE/('检查器'+seat)).glob('*.py')};(BASE/('检查器'+seat)/'组件复查结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps({k:result[k] for k in ('seat','geometry','flow')},ensure_ascii=False,default=str))
