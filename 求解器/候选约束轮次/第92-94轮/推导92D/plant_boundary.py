#!/usr/bin/env python3
"""Cross-check initial inventory/timer boundary, not a reachability claim."""
import pathlib,importlib.util,json,sys
OUT=pathlib.Path(__file__).resolve().parent
def imp(name,file):
 sp=importlib.util.spec_from_file_location(name,OUT/file);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m
p=imp('plant_countdown','plant_probe.py');n=imp('plant_objects','plant_sim2_nine.py');s=n.s
results=[]
for remaining in [8,7]:
 q=p.Plant();q.i=[50,50,0,0];q.o=[49,50,0,0];q.r=[remaining,remaining,0,0];q.routes=[[0],[-1],[0],[-1]]
 w,ms,rs,es,ss=n.build(False)
 for j,m in enumerate(ms):
  m.slots[0]=[s.Item('plant' if j in (0,3) else 'seed') for _ in range(q.i[j])]
  m.output=[s.Item('seed' if j==0 else ('powder' if j==3 else 'plant')) for _ in range(q.o[j])]
  if j<2:m.running=m.recipes[0];m.remaining=remaining
 for j,b in enumerate(rs):b.cells=[s.Item('seed' if j<2 else 'plant',entered=-1) if q.routes[j][0]>=0 else None]
 hist=[]
 for t in range(20):
  q.step();w.step();a=q.short();b=n.snap(w,ms,rs,es,ss)
  for key in ['i','o','r','phi2']:assert a[key]==b[key],(remaining,t,key,a,b)
  assert a['routes']==b['routes'][:4]
  hist.append(dict(t=q.t,i=a['i'],o=a['o'],r=a['r'],routes=a['routes'],phi2=a['phi2']))
 result=dict(initial_remaining=remaining,initial_phi2=357,minimum_phi2=min(x['phi2'] for x in hist),old_bound_phi2=356,revised_bound_phi2=304,models_agree=True,reachability='remaining8 and input50 is not a completed-step state; numerical boundary only' if remaining==8 else 'one-step timer/inventory consistency satisfied; full debug history not constructed',trace=hist)
 assert result['minimum_phi2']>=result['revised_bound_phi2'];results.append(result)
(OUT/'plant_boundary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps([{k:v for k,v in r.items() if k!='trace'} for r in results],ensure_ascii=False))
