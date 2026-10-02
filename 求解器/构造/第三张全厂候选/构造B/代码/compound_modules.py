import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,sys,time
from pathlib import Path
import module_cp as cp
BASE=Path(__file__).resolve().parents[1];c=json.loads((BASE/'依据/S2接法.json').read_text())
def blue(j): return [f'{p}{k}' for k in (2*j-1,2*j) for p in ('T','KB')]+[f'B{j}',f'R{j}']
def ore(j): return [f'U{2*j-1}',f'U{2*j}',f'O{j}']
def plant(p,j): return [f'{p}A{j}',f'{p}B{j}',f'{p}C{j}',f'S{j}' if p=='S' else f'KQ{j}']
def make(ids,sides=[0,1,2,3]):
 labels=set();roles=[];supply={};demand={}
 for m in c['machines']:
  u=m['id']
  if u not in ids:continue
  inc={};outs=[f for f in c['feeds'] if f['source']==u]
  for f in c['feeds']:
   if f['target']!=u:continue
   l=f['source'] if f['source']!='CORE' else 'CORE'+str(f['source_port_index']);labels.add(l);inc[l]=inc.get(l,0)+1
   if f['source'] not in ids: supply[l]=supply.get(l,0)+1
  labels.add(u)
  roles.append(dict(name=u,kind='中' if m['model'] in ['种植机','采种机'] else '大' if m['model'] in ['研磨机','封装机','灌装机'] else '小',count=1,**{'in':list(inc)},out=[u],in_count=inc,n_out=len(outs)))
  demand[u]=sum(f['target'] not in ids for f in outs)
 return dict(labels=sorted(labels),roles=roles,supply=[(k,sides,v) for k,v in supply.items()],demand=[(k,sides,v) for k,v in demand.items() if v])
if __name__=='__main__':
 names={'sand_blue':plant('S',1)+blue(1),'sand_ore':plant('S',2)+ore(2),'qplant':plant('Q',1)+['Q1'],'blue':blue(1),'ore':ore(2),'last':plant('S',12)+plant('S',13)+plant('Q',6)+blue(17)+['H6','Q6','F4']}
 cat=sys.argv[1];w,h=int(sys.argv[2]),int(sys.argv[3]);t=int(sys.argv[4]) if len(sys.argv)>4 else 45
 s=make(names[cat]);(BASE/'模块'/f'{cat}-spec.json').write_text(json.dumps(s,ensure_ascii=False,indent=2))
 r=cp.build(s,w,h,threads=4,tlimit=t,minimize=True)
 r['machine_ids']=names[cat]
 (BASE/'模块'/f'{cat}-{w}x{h}.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
 print(cat,w,h,r['status'],r['wall'],r.get('T'),flush=True)
 if 'grid' in r:print('\n'.join(r['grid']),flush=True)
