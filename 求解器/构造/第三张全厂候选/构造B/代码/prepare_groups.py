import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import json,sys,time
from pathlib import Path
import module_cp as cp
B=Path(__file__).resolve().parents[1]
c=json.loads((B/'依据/S2接法.json').read_text())
G={}
for k in range(1,4):
 ids=[f'E{k}']+[f'{v}{j}' for j in range(2*k-1,2*k+1) for v in ['B','R','P']]+[f'O{j}' for j in range(3*k-2,3*k+1)]+[f'U{j}' for j in range(6*k-5,6*k+1)]+[f'{v}{j}' for j in range(4*k-3,4*k+1) for v in ['T','KB']]+[f'{v}{j}' for j in range(2*k-1,2*k+1) for v in ['S','SA','SB','SC']]
 G[f'E{k}']=ids
for k in range(1,5):
 hs=([1,2],[3,4],[5],[6])[k-1];bs=([7,8,9,10],[11,12,13,14],[15,16],[17])[k-1];ss=([7,8],[9,10],[11],[12,13])[k-1]
 ids=[f'F{k}']+[f'{v}{j}' for j in hs for v in ['H','Q','KQ','QA','QB','QC']]+[f'{v}{j}' for j in bs for v in ['B','R']]+[f'{v}{j}' for j in bs for v in ['T','KB']]+[f'{v}{j}' for i in bs for j in [2*i-1,2*i] for v in ['T','KB']]+[f'{v}{j}' for j in ss for v in ['S','SA','SB','SC']]
 # replace the redundant short indices
 ids=[f'F{k}']+[f'{v}{j}' for j in hs for v in ['H','Q','KQ','QA','QB','QC']]+[f'{v}{j}' for j in bs for v in ['B','R']]+[f'{v}{j}' for i in bs for j in [2*i-1,2*i] for v in ['T','KB']]+[f'{v}{j}' for j in ss for v in ['S','SA','SB','SC']]
 G[f'F{k}']=ids
assert sum(map(len,G.values()))==230
(B/'依据/groups.json').write_text(json.dumps(G,ensure_ascii=False,indent=2))
def spec(group):
 ids=G[group];roles=[];labels=set();supply=[];demand=[]
 for m in c['machines']:
  if m['id'] not in ids: continue
  uid=m['id'];incoming=[f for f in c['feeds'] if f['target']==uid];outgoing=[f for f in c['feeds'] if f['source']==uid]
  inc={}
  for f in incoming:
   label=f['source'] if f['source']!='CORE' else 'CORE'+str(f['source_port_index'])
   inc[label]=inc.get(label,0)+1;labels.add(label)
   if f['source'] not in ids: supply.append((label,[3],1))
  labels.add(uid)
  role=dict(name=uid,kind='中' if m['model'] in ['种植机','采种机'] else '大' if m['model'] in ['研磨机','封装机','灌装机'] else '小',count=1,**{'in':list(inc)},out=[uid],in_count=inc,n_out=len(outgoing))
  roles.append(role)
  for f in outgoing:
   if f['target'] not in ids: demand.append((uid,[0,1,2],1))
 return dict(labels=sorted(labels),roles=roles,supply=supply,demand=demand)
if __name__=='__main__':
 g,w,h=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]);t=int(sys.argv[4]) if len(sys.argv)>4 else 120
 s=spec(g);(B/'模块'/f'{g}-spec.json').write_text(json.dumps(s,ensure_ascii=False,indent=2))
 r=cp.build(s,w,h,threads=4,tlimit=t,minimize=False)
 (B/'模块'/f'{g}-{w}x{h}.json').write_text(json.dumps(r,ensure_ascii=False,indent=2))
 print(g,w,h,r['status'],r['wall'],r.get('T'),flush=True)
 if 'grid' in r:print('\n'.join(r['grid']),flush=True)
