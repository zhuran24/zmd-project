#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
import json
OUT=Path(__file__).resolve().parent

def cells(d):return {(x,y) for x in range(d['x'],d['x']+d['w']) for y in range(d['y'],d['y']+d['h'])}
def check(path):
 a=json.loads(path.read_text())
 if 'chosen' not in a:return {'file':path.name,'status':a['status'],'no_witness':True}
 ds=a['chosen'];occupied=set();bycell={}
 for i,d in enumerate(ds):
  cs=cells(d);assert not occupied&cs;occupied|=cs
  assert all(1<=x<70 and 1<=y<70 and not(x>=49 and y>=17) for x,y in cs)
  for c in cs:bycell[c]=i
 for d in ds:
  for ps,n in zip(d['ports'],d['needs']):assert sum(tuple(c) not in occupied for c in ps)>=n
 ps=[d for d in ds if d['kind']=='p'];ms=[d for d in ds if d['kind'] in ('s','m','l')]
 assert len(ps)==a['P']
 repeated=[]
 for d in ms:
  poles=[(p['x'],p['y']) for p in ps if d['x']<p['x']+7 and p['x']-5<d['x']+d['w'] and d['y']<p['y']+7 and p['y']-5<d['y']+d['h']]
  assert poles
  repeated.append(dict(rect=[d['x'],d['y'],d['w'],d['h']],poles=poles,charge=len(poles)-1))
 lines=[[(69,y) for y in range(1,17)],[(x,69) for x in range(1,49)],[(48,y) for y in range(17,70)],[(x,16) for x in range(49,70)]]
 gaps=[sum(c not in occupied for c in l) for l in lines];J=sum(d['j'] for d in ps);S=16*a['P']-2*J+sum(gaps)
 assert S==a['upper']
 lsum=sum(d['loss'] for d in ps);repeat=sum(d['charge'] for d in repeated)
 return dict(file=path.name,status=a['status'],S=S,gaps=gaps,J=J,selected_counts=dict(Counter(d['kind'] for d in ds)),pole_loss=lsum,known_machine_repeat=repeat,budget=23*a['P']-217,combined_charge=lsum+repeat,overlap_budget_pass=lsum+repeat<=23*a['P']-217,repeated=repeated)
if __name__=='__main__':
 out=[check(p) for p in OUT.glob('search_P*.json')]
 (OUT/'search_inspection.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print(json.dumps([{k:v for k,v in d.items() if k!='repeated'} for d in out],ensure_ascii=False))
