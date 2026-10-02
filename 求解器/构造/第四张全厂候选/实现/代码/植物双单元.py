#!/usr/bin/env python3
"""在指定外框中联合摆放两个完整采种单元及其逐格运输。

这是局部模板搜索；边界输出是待接的接口，不冒充全厂。
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:3])
import json,sys,importlib.util
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('module_cp',BASE/'代码/局部联合模型.py')
cp=importlib.util.module_from_spec(sp);sp.loader.exec_module(cp)

def spec(n=2):
    roles=[];labels=[];demand=[]
    for i in range(n):
        for name,kind,inc,nout in [('A','中',{'C':1},1),('B','中',{'C':1},1),('C','中',{'A':1},2),('K','小',{'B':1},3)]:
            uid=f'{name}{i}';lab={f'{k}{i}':v for k,v in inc.items()}
            roles.append(dict(name=uid,kind=kind,count=1,**{'in':list(lab)},out=[uid],in_count=lab,n_out=nout))
            labels.append(uid)
        demand.append((f'K{i}',[0,1,2,3],3))
    return dict(labels=labels,roles=roles,supply=[],demand=demand)

if __name__=='__main__':
    w,h,t=map(int,sys.argv[1:4]);n=int(sys.argv[4]) if len(sys.argv)>4 else 2
    r=cp.build(spec(n),w,h,threads=3,tlimit=t,minimize=True)
    dest=BASE/'实验'/f'植物{n}单元-{w}x{h}.json'
    dest.write_text(json.dumps(r,ensure_ascii=False,indent=1))
    print(json.dumps({k:v for k,v in r.items() if k not in ('layout','grid')},ensure_ascii=False),flush=True)
    print('\n'.join(r.get('grid',[])),flush=True)
