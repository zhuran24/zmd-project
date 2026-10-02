#!/usr/bin/env python3
"""复用两份旧几何模块，桥端口替换为S2B双向端口。未运行旧版完整闸门或LP。"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,{6})
import json,sys,hashlib
from pathlib import Path
B=Path(__file__).resolve().parents[1];seat=sys.argv[1];p=Path(sys.argv[2]);d=json.loads(p.read_text())
sys.path.insert(0,str(B/f'旧检查器{seat}'))
ref=lambda q:(q['unit'],q['side'],q['offset'])
decl={(ref(e['from']),ref(e['to'])) for e in d['design']['physical_channels']}
class Report:
    def __init__(self):self.checks={}
    def check(self,k,ok,basis,detail):
        q=self.checks.setdefault(k,dict(status='PASS',failures=[]))
        if not ok:q['status']='FAIL';q['failures'].append(detail)
    def na(self,k,*a):pass
    def blocked(self,k,*a):pass
    def alias(self,k,*a):pass
if seat=='A':
    from geometry import Geometry
    r=Report();g=Geometry(d,r).build();actual=set(g.channels);rect=g.maximum
    result=dict(occupied_cells=len(g.occ),channels=len(actual),maximum_empty_rectangle=rect,powered_machines=sum(bool(g.power[u['id']]) for u in d['layout']['machines']),checks=r.checks)
else:
    from geometry import Geometry,Checks,maximum_empty
    r=Checks();g=Geometry(d['layout'],r);actual=set(g.edges);rect=maximum_empty(g.occ)
    result=dict(occupied_cells=len(g.occ),channels=len(actual),maximum_empty_rectangle=rect,powered_machines=sum(bool(g.powered[u['id']]) for u in d['layout']['machines']),checks=r.records)
result.update(candidate_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),channels_equal=actual==decl,missing_declared=[str(v) for v in actual-decl],absent_actual=[str(v) for v in decl-actual],scope='仅占格、尺寸、边界、供电、全部双向实体通道与最大空矩形；旧版受限类闸门、LP和运行检查未适配。',geometry_sources={q.name:hashlib.sha256(q.read_bytes()).hexdigest() for q in (B/f'旧检查器{seat}').glob('*.py')})
(B/'证据'/f'旧{seat}复查.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in ['checks','geometry_sources','missing_declared','absent_actual']},ensure_ascii=False))
