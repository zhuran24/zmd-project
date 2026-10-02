import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import json,time,sys
from pathlib import Path
import module_cp as cp
BASE=Path(__file__).resolve().parents[1]
def plant(k=3,sides=[0,1,2,3]):
 roles=[]
 for name,kind,count,ip,op,ni,no in [('种植','中',2,'种子','植物',1,1),('采种','中',1,'植物','种子',1,2),('粉碎','小',1,'植物','粉末',1,k)]:
  roles.append(dict(name=name,kind=kind,count=count,**{'in':[ip]},out=[op],in_count={ip:ni},n_out=no))
 return dict(labels=['种子','植物','粉末'],roles=roles,supply=[],demand=[('粉末',sides,k)])
for w,h in [(12,11),(13,11),(12,12),(16,8)]:
 name=f'plant-{w}x{h}'
 r=cp.build(plant(),w,h,threads=4,tlimit=40,minimize=True)
 (BASE/'模块'/f'{name}.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
 print(name,r['status'],r['wall'],r.get('T'),flush=True)
 if 'grid' in r: print('\n'.join(r['grid']),flush=True)
