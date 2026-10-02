#!/usr/bin/env python3
"""Independent countdown model: no-blockage exact old-Phi-threshold checks."""
import importlib.util,pathlib,json
OUT=pathlib.Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('plant',OUT/'plant_probe.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
res=[]
for lens in [(1,1,1,1),(2,1,3,1),(3,1,6,1)]:
 q=m.Plant(lens);q.i=[lens[0]+lens[2]+2,0,0,0];q.o=[1,0,0,0];q.last=[-99,-100];initial=q.short();hist=[];seen={};period=None
 for t in range(20000):
  q.step()
  if t>10000:
   st=q.state()
   if st in seen:period=t-seen[st];break
   seen[st]=t
 assert period is not None
 for _ in range(period):q.step();hist.append(q.short())
 res.append(dict(initial=initial,period=period,phi2_range=[min(x['phi2'] for x in hist),max(x['phi2'] for x in hist)],empty=[sum(x['r'][i]==0 for x in hist) for i in range(4)],cycle=hist))
(OUT/'plant_low_threshold.json').write_text(json.dumps(res,ensure_ascii=False,indent=2))
print(json.dumps([{k:v for k,v in r.items() if k!='cycle'} for r in res],ensure_ascii=False))
