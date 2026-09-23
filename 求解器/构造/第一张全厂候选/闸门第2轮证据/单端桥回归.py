#!/usr/bin/env python3
"""只复核首轮漏边反例的几何层；不构成全厂正例。"""
import sys,json,copy
from pathlib import Path
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;BASE=HERE.parent
which=sys.argv[1];sys.path.insert(0,str(BASE/('检查器'+which)))
d=json.loads((HERE/'候选只读快照.json').read_text())
d['layout']['machines']=[];d['layout']['power_poles']=[]
d['layout']['warehouse_outlets']=[u for u in d['layout']['warehouse_outlets'] if u['id']=='OUT_L00']
d['layout']['transport']=[{'id':'BR_TEST','x':1,'y':2,'type':'bridge','H_in':2,'V_in':None}]
d['design']['physical_channels']=[]
if which=='A':
    from check_full import Report
    from geometry import Geometry
    c=Report();g=Geometry(d,c).build();edges=g.channels
    detail=[c.checks[k] for k in ['N4a','N5a']]
    assert all(v['status']=='violation' for v in detail)
else:
    from geometry import Checks,Geometry,structural
    c=Checks();g=Geometry(d['layout'],c);structural(d,g,c);edges=g.edges
    detail=[v for v in c.records if v['check'] in ['N4a','N5a']]
    assert any(v['status']=='FAIL' and v['check']=='N4a' for v in detail)
    assert any(v['status']=='FAIL' and v['check']=='N5a' for v in detail)
assert set(edges)=={(('OUT_L00',0,1),('BR_TEST',2,0))}
result={'scope':'局部几何回归，非候选修改，不运行流层','checker':which,'channels':edges,'checks':detail,'expected_edge_preserved':True}
(HERE/(which+'单端桥回归.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
