#!/usr/bin/env python3
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,{2})
import json,importlib.util,sys
from pathlib import Path
B=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('localcp',B/'代码/局部联合模型.py');cp=importlib.util.module_from_spec(sp);sp.loader.exec_module(cp)
spec=dict(labels=['蓝铁矿','蓝铁块','蓝铁粉末'],roles=[
    dict(name='矿石精炼炉',kind='小',count=12,**{'in':['蓝铁矿']},out=['蓝铁块'],in_count={'蓝铁矿':1},n_out=1),
    dict(name='蓝铁块粉碎机',kind='小',count=12,**{'in':['蓝铁块']},out=['蓝铁粉末'],in_count={'蓝铁块':1},n_out=1)],
    supply=[('蓝铁矿',[2,3],12)],demand=[('蓝铁粉末',[0,1],12)],
    supply_points={'蓝铁矿':[(0,1+3*k,2) for k in range(6)]+[(1+3*k,0,3) for k in range(6)]},
    demand_points={'蓝铁粉末':[(17,k,0) for k in [0,4,13,14,15,16]]+[(k,17,1) for k in [0,4,13,14,15,16]]})
limit=int(sys.argv[1]) if len(sys.argv)>1 else 300
if len(sys.argv)>2:spec.pop("demand_points")
r=cp.build(spec,18,18,threads=1,tlimit=limit,minimize=True)
(B/('实验/角区18x18-自由出口.json' if len(sys.argv)>2 else '实验/角区18x18.json')).write_text(json.dumps(r,ensure_ascii=False,indent=1))
print(json.dumps({k:v for k,v in r.items() if k not in ['layout','grid']},ensure_ascii=False),flush=True)
print('\n'.join(r.get('grid',[])),flush=True)
